"""
Repair Engine — Pattern-matching autonomous repair system.

Codifies the fix patterns from 50+ existing fix_*.py scripts into a
reusable registry.  Can match error signatures to known fixes and
apply them using the existing run_fix() pattern from n8n_api_helpers.

Follows the established fix pattern:
    fetch → node_map → mutate → push → log to Events table

Usage:
    from repair_engine import RepairEngine
    engine = RepairEngine(n8n_client)
    result = engine.diagnose_and_repair(workflow_id, error_data)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from autonomy_governor import ActionType, RiskLevel


# ── Repair Pattern ──────────────────────────────────────────

@dataclass
class RepairPattern:
    """A codified repair operation with error signature matching."""
    pattern_id: str
    name: str
    description: str
    error_signatures: List[str]           # Regex patterns for matching
    node_types_affected: List[str]
    fix_function: Callable[[dict], List[str]]  # Takes workflow dict, returns changes
    confidence: float                     # 0.0–1.0 built-in confidence
    risk_level: RiskLevel
    action_type: ActionType               # For governance checks
    requires_deploy_script_update: bool


# ── Built-in fix functions ──────────────────────────────────

def _fix_missing_on_error(wf: dict) -> List[str]:
    """Add continueRegularOutput to nodes lacking onError."""
    changes: List[str] = []
    for node in wf.get("nodes", []):
        ntype = node.get("type", "")
        # Skip trigger nodes and utility nodes
        if any(t in ntype for t in ("Trigger", "trigger", "noOp", "stickyNote")):
            continue
        if "onError" not in node:
            node["onError"] = "continueRegularOutput"
            changes.append(f"Added onError to '{node['name']}'")
    return changes


def _fix_env_ref_in_code(wf: dict) -> List[str]:
    """Replace $env.VAR references in Code nodes with placeholder markers."""
    changes: List[str] = []
    env_re = re.compile(r'\$env\.(\w+)')
    for node in wf.get("nodes", []):
        if node.get("type", "") != "n8n-nodes-base.code":
            continue
        js_code = node.get("parameters", {}).get("jsCode", "")
        matches = env_re.findall(js_code)
        if matches:
            for var in set(matches):
                # Replace with placeholder marker — NEVER embed actual secret values
                placeholder = f"__REPLACE_{var}__"
                js_code = js_code.replace(f"$env.{var}", f"'{placeholder}'")
            node["parameters"]["jsCode"] = js_code
            changes.append(f"Replaced $env refs in Code node '{node['name']}': {', '.join(set(matches))}")
    return changes


def _fix_number_of_outputs(wf: dict) -> List[str]:
    """Add numberOfOutputs to Code nodes that return nested arrays."""
    changes: List[str] = []
    for node in wf.get("nodes", []):
        if node.get("type", "") != "n8n-nodes-base.code":
            continue
        js_code = node.get("parameters", {}).get("jsCode", "")
        params = node.get("parameters", {})
        # Detect multi-output pattern: return [...], [...] or return [items1, items2]
        if "numberOfOutputs" not in params:
            # Check connections to see how many outputs this node feeds
            node_name = node["name"]
            connections = wf.get("connections", {})
            node_conns = connections.get(node_name, {})
            if "main" in node_conns and len(node_conns["main"]) > 1:
                output_count = len(node_conns["main"])
                params["numberOfOutputs"] = output_count
                changes.append(
                    f"Added numberOfOutputs={output_count} to Code node '{node_name}'"
                )
    return changes


def _fix_airtable_mapping_mode(wf: dict) -> List[str]:
    """Fix Airtable create nodes missing columns.mappingMode."""
    changes: List[str] = []
    for node in wf.get("nodes", []):
        ntype = node.get("type", "")
        if "airtable" not in ntype.lower():
            continue
        params = node.get("parameters", {})
        operation = params.get("operation", "")
        if operation == "create" and "columns" not in params:
            params["columns"] = {
                "mappingMode": "autoMapInputData",
                "value": None,
            }
            changes.append(f"Added columns.mappingMode to Airtable create node '{node['name']}'")
        # Fix update nodes using matchingColumns without proper format
        if operation == "update" and "matchingColumns" in params:
            mc = params["matchingColumns"]
            if isinstance(mc, str):
                params["matchingColumns"] = [mc]
                changes.append(f"Fixed matchingColumns format in '{node['name']}'")
    return changes


def _fix_switch_rules_key(wf: dict) -> List[str]:
    """Fix Switch v3 nodes using rules.rules instead of rules.values."""
    changes: List[str] = []
    for node in wf.get("nodes", []):
        if node.get("type", "") != "n8n-nodes-base.switch":
            continue
        params = node.get("parameters", {})
        rules = params.get("rules", {})
        if "rules" in rules and "values" not in rules:
            rules["values"] = rules.pop("rules")
            changes.append(f"Fixed Switch rules key in '{node['name']}' (rules.rules → rules.values)")
        # Remove combinator without caseSensitive (causes crash)
        for val in rules.get("values", []):
            conditions = val.get("conditions", {})
            if "combinator" in conditions and "options" not in conditions:
                del conditions["combinator"]
                changes.append(f"Removed bare combinator in Switch '{node['name']}'")
    return changes


def _fix_duplicate_node_names(wf: dict) -> List[str]:
    """Rename duplicate node names by appending suffix."""
    changes: List[str] = []
    seen: Dict[str, int] = {}
    for node in wf.get("nodes", []):
        name = node.get("name", "")
        if name in seen:
            seen[name] += 1
            new_name = f"{name} ({seen[name]})"
            node["name"] = new_name
            changes.append(f"Renamed duplicate node '{name}' → '{new_name}'")
        else:
            seen[name] = 1
    # Update connection references
    if changes:
        _update_connection_refs(wf)
    return changes


def _fix_continue_on_fail(wf: dict) -> List[str]:
    """Add continueOnFail + alwaysOutputData to HTTP/API nodes."""
    changes: List[str] = []
    api_types = {
        "n8n-nodes-base.httpRequest",
        "n8n-nodes-base.googleSheets",
    }
    for node in wf.get("nodes", []):
        if node.get("type", "") in api_types:
            if not node.get("continueOnFail"):
                node["continueOnFail"] = True
                changes.append(f"Added continueOnFail to '{node['name']}'")
            if not node.get("alwaysOutputData"):
                node["alwaysOutputData"] = True
                changes.append(f"Added alwaysOutputData to '{node['name']}'")
    return changes


def _fix_execution_order(wf: dict) -> List[str]:
    """Ensure settings.executionOrder is 'v1'."""
    changes: List[str] = []
    settings = wf.setdefault("settings", {})
    if settings.get("executionOrder") != "v1":
        settings["executionOrder"] = "v1"
        changes.append("Set settings.executionOrder = 'v1'")
    return changes


def _fix_google_sheets_schema_drift(wf: dict) -> List[str]:
    """Add onError + alwaysOutputData to Google Sheets nodes for schema drift."""
    changes: List[str] = []
    for node in wf.get("nodes", []):
        ntype = node.get("type", "")
        if "googleSheets" not in ntype:
            continue
        modified = False
        if node.get("onError") != "continueRegularOutput":
            node["onError"] = "continueRegularOutput"
            modified = True
        if not node.get("alwaysOutputData"):
            node["alwaysOutputData"] = True
            modified = True
        if modified:
            changes.append(
                f"Added onError+alwaysOutputData to Google Sheets node '{node['name']}'"
            )
    return changes


def _fix_credential_auth_none_mismatch(wf: dict) -> List[str]:
    """Remove authentication=none when a real credential is referenced."""
    changes: List[str] = []
    for node in wf.get("nodes", []):
        params = node.get("parameters", {})
        creds = node.get("credentials", {})
        auth_val = params.get("authentication", "")
        # Node has a credential but auth is explicitly set to none/empty
        if creds and auth_val in ("none", ""):
            has_real_cred = any(
                isinstance(v, dict) and v.get("id")
                for v in creds.values()
            )
            if has_real_cred:
                params.pop("authentication", None)
                changes.append(
                    f"Removed authentication='none' from '{node['name']}' "
                    f"(credential refs: {list(creds.keys())})"
                )
    return changes


def _fix_broken_input_prefix(wf: dict) -> List[str]:
    """Restore missing $input prefix on .all()/.first() calls in Code nodes."""
    changes: List[str] = []
    # Match assignments like `= .all()` or `= .first()` missing the $input prefix
    broken_re = re.compile(r'(=\s*)\.((all|first)\(\))')
    for node in wf.get("nodes", []):
        if node.get("type", "") != "n8n-nodes-base.code":
            continue
        js_code = node.get("parameters", {}).get("jsCode", "")
        if not broken_re.search(js_code):
            continue
        fixed_code = broken_re.sub(r'\1$input.\2', js_code)
        node["parameters"]["jsCode"] = fixed_code
        changes.append(
            f"Restored $input prefix in Code node '{node['name']}'"
        )
    return changes


def _fix_airtable_invalid_select_value(wf: dict) -> List[str]:
    """Add onError to Airtable nodes hitting invalid singleSelect values."""
    changes: List[str] = []
    for node in wf.get("nodes", []):
        ntype = node.get("type", "")
        if "airtable" not in ntype.lower():
            continue
        if node.get("onError") != "continueRegularOutput":
            node["onError"] = "continueRegularOutput"
            changes.append(
                f"Added onError=continueRegularOutput to Airtable node "
                f"'{node['name']}' (invalid select value guard)"
            )
    return changes


# ── Helper ──────────────────────────────────────────────────

def _update_connection_refs(wf: dict) -> None:
    """Rebuild connections dict keys to match current node names."""
    # This is a best-effort helper; full connection rewrite is complex
    pass


# ── Built-in Pattern Registry ──────────────────────────────

BUILTIN_PATTERNS: List[RepairPattern] = [
    RepairPattern(
        pattern_id="missing_on_error",
        name="Missing onError handler",
        description="Workflow crashes because nodes lack onError configuration",
        error_signatures=[
            r"(?i)workflow.*crash",
            r"(?i)unhandled.*error",
            r"(?i)execution.*failed.*no.*error.*handler",
        ],
        node_types_affected=["*"],
        fix_function=_fix_missing_on_error,
        confidence=0.90,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=True,
    ),
    RepairPattern(
        pattern_id="env_ref_in_code",
        name="$env reference in Code node",
        description="n8n Cloud blocks $env access in Code nodes",
        error_signatures=[
            r"\$env\.\w+",
            r"(?i)environment.*variable.*not.*defined",
            r"(?i)\$env.*undefined",
        ],
        node_types_affected=["n8n-nodes-base.code"],
        fix_function=_fix_env_ref_in_code,
        confidence=0.95,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=True,
    ),
    RepairPattern(
        pattern_id="number_of_outputs_missing",
        name="Missing numberOfOutputs in Code node",
        description="Code node with multiple output branches needs numberOfOutputs parameter",
        error_signatures=[
            r"(?i)code.*doesn't.*return.*items.*properly",
            r"(?i)numberOfOutputs",
        ],
        node_types_affected=["n8n-nodes-base.code"],
        fix_function=_fix_number_of_outputs,
        confidence=0.90,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=True,
    ),
    RepairPattern(
        pattern_id="airtable_mapping_mode",
        name="Airtable missing columns.mappingMode",
        description="Airtable create node errors with 'Could not find field fields'",
        error_signatures=[
            r"(?i)could not find field.*fields",
            r"(?i)airtable.*mapping.*mode",
            r"(?i)columns.*mappingMode",
        ],
        node_types_affected=["n8n-nodes-base.airtable"],
        fix_function=_fix_airtable_mapping_mode,
        confidence=0.90,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=True,
    ),
    RepairPattern(
        pattern_id="switch_wrong_key",
        name="Switch v3 wrong rules key",
        description="Switch node uses rules.rules instead of rules.values",
        error_signatures=[
            r"(?i)could not find property option",
            r"(?i)switch.*rules\.rules",
        ],
        node_types_affected=["n8n-nodes-base.switch"],
        fix_function=_fix_switch_rules_key,
        confidence=0.90,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=True,
    ),
    RepairPattern(
        pattern_id="duplicate_node_names",
        name="Duplicate node names",
        description="Workflow has nodes with identical names causing reference errors. "
                    "Connection rewrite not implemented — always escalate.",
        error_signatures=[
            r"(?i)duplicate.*node.*name",
            r"(?i)ambiguous.*node.*reference",
        ],
        node_types_affected=["*"],
        fix_function=_fix_duplicate_node_names,
        confidence=0.20,  # Force escalation: connection rewrite is not implemented
        risk_level=RiskLevel.HIGH,
        action_type=ActionType.REWIRE_CONNECTIONS,
        requires_deploy_script_update=True,
    ),
    RepairPattern(
        pattern_id="missing_continue_on_fail",
        name="API nodes without continueOnFail",
        description="HTTP/API nodes crash workflow on transient errors",
        error_signatures=[
            r"(?i)ECONNRESET",
            r"(?i)ETIMEDOUT",
            r"(?i)ECONNREFUSED",
            r"(?i)socket hang up",
            r"(?i)network.*error",
        ],
        node_types_affected=["n8n-nodes-base.httpRequest", "n8n-nodes-base.googleSheets"],
        fix_function=_fix_continue_on_fail,
        confidence=0.85,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=True,
    ),
    RepairPattern(
        pattern_id="execution_order_v1",
        name="Missing execution order setting",
        description="Workflow settings missing executionOrder = v1",
        error_signatures=[
            r"(?i)execution.*order",
            r"(?i)settings.*executionOrder",
        ],
        node_types_affected=["*"],
        fix_function=_fix_execution_order,
        confidence=0.95,
        risk_level=RiskLevel.LOW,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=False,
    ),
    # ── Delegate-to-self-healing patterns ───────────────────
    # These are detected but NOT fixed by the repair engine;
    # instead they are classified and forwarded to the existing
    # self-healing workflow for immediate retry.
    RepairPattern(
        pattern_id="rate_limited",
        name="API rate limit hit",
        description="429 / rate limit errors — delegate to self-healing retry",
        error_signatures=[
            r"(?i)429",
            r"(?i)rate.limit",
            r"(?i)too.many.requests",
            r"(?i)quota.*exceeded",
        ],
        node_types_affected=["*"],
        fix_function=lambda wf: [],  # No structural fix — self-healing retries
        confidence=0.85,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.RETRY_EXECUTION,
        requires_deploy_script_update=False,
    ),
    RepairPattern(
        pattern_id="airtable_token_expired",
        name="Airtable auth failure",
        description="401 Invalid token — credential needs rotation",
        error_signatures=[
            r"(?i)401.*invalid.*token",
            r"(?i)AUTHENTICATION_REQUIRED",
            r"(?i)airtable.*unauthorized",
        ],
        node_types_affected=["n8n-nodes-base.airtable"],
        fix_function=lambda wf: [],  # Credential rotation is CRITICAL
        confidence=0.95,
        risk_level=RiskLevel.CRITICAL,
        action_type=ActionType.MODIFY_CREDENTIAL_REFS,
        requires_deploy_script_update=False,
    ),
    RepairPattern(
        pattern_id="node_expression_error",
        name="Node expression reference error",
        description="Expression references a non-existent or renamed upstream node",
        error_signatures=[
            r"(?i)expression.*error",
            r"(?i)cannot read.*undefined",
            r"\$\('.*'\)\.first\(\).*Cannot read",
        ],
        node_types_affected=["*"],
        fix_function=lambda wf: [],  # Needs AI to trace correct node name
        confidence=0.50,
        risk_level=RiskLevel.HIGH,
        action_type=ActionType.REWIRE_CONNECTIONS,
        requires_deploy_script_update=True,
    ),
    RepairPattern(
        pattern_id="placeholder_leak",
        name="Placeholder text leak in output",
        description="Output contains [First Name], [Business Name] etc.",
        error_signatures=[
            r"\[First Name\]",
            r"\[Business Name\]",
            r"\[Your Name\]",
            r"\[Company\]",
        ],
        node_types_affected=["n8n-nodes-base.code", "n8n-nodes-base.set"],
        fix_function=lambda wf: [],  # Needs context-specific replacement
        confidence=0.70,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=True,
    ),
    # ── New patterns (2026-04-09) ──────────────────────────────
    RepairPattern(
        pattern_id="google_sheets_schema_drift",
        name="Google Sheets column schema drift",
        description="Google Sheets node fails because column names were updated after setup",
        error_signatures=[
            r"(?i)column names were updated",
            r"(?i)column.*updated.*after.*setup",
        ],
        node_types_affected=["n8n-nodes-base.googleSheets"],
        fix_function=_fix_google_sheets_schema_drift,
        confidence=0.85,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=True,
    ),
    RepairPattern(
        pattern_id="credential_auth_none_mismatch",
        name="Credential present but authentication set to none",
        description="Node has a real credential ID but authentication parameter is 'none', "
                    "causing 401 or 'No cookie auth credentials found'",
        error_signatures=[
            r"(?i)no cookie auth credentials found",
            r"(?i)401.*unauthorized",
            r"(?i)authentication.*none.*credential",
        ],
        node_types_affected=["*"],
        fix_function=_fix_credential_auth_none_mismatch,
        confidence=0.80,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=True,
    ),
    RepairPattern(
        pattern_id="broken_input_prefix",
        name="Missing $input prefix in Code node",
        description="Code node has .all() or .first() without $input prefix, causing SyntaxError",
        error_signatures=[
            r"(?i)unexpected token '\.'",
            r"(?i)syntaxerror.*code.*node",
            r"=\s*\.(all|first)\(\)",
        ],
        node_types_affected=["n8n-nodes-base.code"],
        fix_function=_fix_broken_input_prefix,
        confidence=0.90,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=True,
    ),
    RepairPattern(
        pattern_id="airtable_invalid_select_value",
        name="Airtable invalid singleSelect value",
        description="Airtable rejects a value not in the singleSelect field options",
        error_signatures=[
            r"(?i)insufficient permissions to create new select option",
            r"(?i)invalid.*select.*option",
        ],
        node_types_affected=["n8n-nodes-base.airtable"],
        fix_function=_fix_airtable_invalid_select_value,
        confidence=0.80,
        risk_level=RiskLevel.MEDIUM,
        action_type=ActionType.UPDATE_NODE_PARAMS,
        requires_deploy_script_update=True,
    ),
]


# ── Repair Engine ───────────────────────────────────────────

class RepairEngine:
    """Match errors to repair patterns and apply fixes."""

    def __init__(
        self,
        n8n_client: Any,
        config: Optional[Dict[str, Any]] = None,
        pattern_store: Optional[Any] = None,
    ) -> None:
        self._client = n8n_client
        self._config = config or {}
        self._store = pattern_store
        self._patterns: Dict[str, RepairPattern] = {}
        self._compiled: Dict[str, List[re.Pattern[str]]] = {}
        self._dedup_cache: Dict[str, float] = {}
        self._dedup_cooldown = self._config.get("lifecycle", {}).get(
            "dedup_cooldown_seconds", 300
        )
        self._load_builtin_patterns()

    # ── Pattern registry ────────────────────────────────────

    def _load_builtin_patterns(self) -> None:
        for p in BUILTIN_PATTERNS:
            self.register_pattern(p)

    def register_pattern(self, pattern: RepairPattern) -> None:
        self._patterns[pattern.pattern_id] = pattern
        self._compiled[pattern.pattern_id] = [
            re.compile(sig) for sig in pattern.error_signatures
        ]

    def get_pattern(self, pattern_id: str) -> Optional[RepairPattern]:
        return self._patterns.get(pattern_id)

    def list_patterns(self) -> List[RepairPattern]:
        return list(self._patterns.values())

    # ── Error matching ──────────────────────────────────────

    def match_pattern(self, error_data: Dict[str, Any]) -> Optional[RepairPattern]:
        """Find the best matching repair pattern for an error.

        error_data should contain at least 'message' (error text).
        May also contain 'node_type', 'node_name', 'workflow_id'.
        """
        error_text = error_data.get("message", "")
        node_type = error_data.get("node_type", "")

        best_match: Optional[RepairPattern] = None
        best_score = 0

        for pid, pattern in self._patterns.items():
            compiled = self._compiled[pid]
            match_count = sum(1 for rx in compiled if rx.search(error_text))
            if match_count == 0:
                continue

            # Bonus for node type match
            type_bonus = 0
            if pattern.node_types_affected != ["*"] and node_type:
                if any(nt in node_type for nt in pattern.node_types_affected):
                    type_bonus = 0.2

            score = (match_count / len(compiled)) + type_bonus

            if score > best_score:
                best_score = score
                best_match = pattern

        return best_match

    # ── Deduplication ───────────────────────────────────────

    def is_dedup_blocked(self, workflow_id: str, error_text: str) -> bool:
        """Check if this error was recently processed (5-min cooldown)."""
        key = hashlib.md5(f"{workflow_id}:{error_text}".encode()).hexdigest()
        now = time.time()
        # Evict expired entries to prevent unbounded growth
        self._dedup_cache = {
            k: v for k, v in self._dedup_cache.items()
            if now - v < self._dedup_cooldown
        }
        last_seen = self._dedup_cache.get(key, 0)
        if now - last_seen < self._dedup_cooldown:
            return True
        self._dedup_cache[key] = now
        return False

    # ── Repair execution ────────────────────────────────────

    def diagnose_and_repair(
        self,
        workflow_id: str,
        error_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Full repair cycle: match → apply → record outcome.

        Returns:
            {
                "workflow_id": str,
                "pattern_id": str | None,
                "changes": List[str],
                "success": bool,
                "action": str,  # "applied", "dedup_blocked", "no_match", "no_changes", "error"
                "details": str,
            }
        """
        error_text = error_data.get("message", "")

        # Dedup check
        if self.is_dedup_blocked(workflow_id, error_text):
            return {
                "workflow_id": workflow_id,
                "pattern_id": None,
                "changes": [],
                "success": False,
                "action": "dedup_blocked",
                "details": "Error recently processed, within cooldown window",
            }

        # Match pattern
        pattern = self.match_pattern(error_data)
        if pattern is None:
            return {
                "workflow_id": workflow_id,
                "pattern_id": None,
                "changes": [],
                "success": False,
                "action": "no_match",
                "details": f"No pattern matches error: {error_text[:200]}",
            }

        # Apply fix
        return self.apply_pattern(workflow_id, pattern)

    def apply_pattern(
        self,
        workflow_id: str,
        pattern: RepairPattern,
    ) -> Dict[str, Any]:
        """Apply a specific repair pattern to a workflow."""
        from n8n_api_helpers import safe_get_workflow, safe_update_workflow, make_update_payload

        # Fetch workflow
        wf = safe_get_workflow(self._client, workflow_id)
        if wf is None:
            return {
                "workflow_id": workflow_id,
                "pattern_id": pattern.pattern_id,
                "changes": [],
                "success": False,
                "action": "error",
                "details": f"Failed to fetch workflow {workflow_id}",
            }

        # Backup before modifying
        self._backup(workflow_id, wf)

        # Apply fix function
        try:
            changes = pattern.fix_function(wf)
        except Exception as exc:
            return {
                "workflow_id": workflow_id,
                "pattern_id": pattern.pattern_id,
                "changes": [],
                "success": False,
                "action": "error",
                "details": f"Fix function raised: {exc}",
            }

        if not changes:
            return {
                "workflow_id": workflow_id,
                "pattern_id": pattern.pattern_id,
                "changes": [],
                "success": True,
                "action": "no_changes",
                "details": "Workflow already in correct state",
            }

        # Push update
        payload = make_update_payload(wf)
        result = safe_update_workflow(self._client, workflow_id, payload)
        success = result is not None

        # Record outcome in pattern store
        if self._store is not None:
            self._store.record_outcome(
                pattern.pattern_id,
                workflow_id,
                success=success,
                details={"changes": changes},
            )

        return {
            "workflow_id": workflow_id,
            "pattern_id": pattern.pattern_id,
            "changes": changes,
            "success": success,
            "action": "applied" if success else "error",
            "details": f"Applied {len(changes)} changes" if success else "Push failed",
        }

    # ── Deploy script check ─────────────────────────────────

    def find_deploy_script(self, workflow_name: str) -> Optional[str]:
        """Search tools/deploy_*.py for a matching workflow name."""
        tools_dir = Path(__file__).parent
        for script in tools_dir.glob("deploy_*.py"):
            try:
                content = script.read_text(encoding="utf-8")
                if workflow_name in content:
                    return str(script)
            except OSError:
                continue
        return None

    # ── Backup ──────────────────────────────────────────────

    def _backup(self, workflow_id: str, wf: dict) -> Optional[str]:
        backup_dir = Path(
            self._config.get("lifecycle", {}).get("backup_dir", ".tmp/backups")
        )
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(tz=None).strftime("%Y%m%d%H%M%S")
        path = backup_dir / f"{workflow_id}_{ts}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(wf, f, indent=2, ensure_ascii=False)
            return str(path)
        except OSError:
            return None

    # ── Stats ───────────────────────────────────────────────

    def get_pattern_stats(self) -> Dict[str, Dict[str, Any]]:
        """Return success rates and counts for all patterns."""
        stats: Dict[str, Dict[str, Any]] = {}
        for pid, p in self._patterns.items():
            rate = 0.5
            if self._store:
                rate = self._store.get_success_rate(pid)
            stats[pid] = {
                "name": p.name,
                "confidence": p.confidence,
                "observed_success_rate": rate,
                "risk_level": p.risk_level.name,
            }
        return stats

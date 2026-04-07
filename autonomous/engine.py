"""Autonomous Workflow Engineer — Core Orchestration Engine.

Ties monitoring, classification, scoring, governance, and repair
into a single deterministic pipeline.  Zero LLM calls — all stages
are pure Python following the WAT principle.

Pipeline:
    DETECT → CLASSIFY → SCORE → GOVERN → FIX → VERIFY → LOG

Usage:
    from autonomous.engine import AutonomousEngine
    engine = AutonomousEngine()
    result = engine.run_repair_loop()
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

# Add tools/ to path for imports
_TOOLS_DIR = str(Path(__file__).parent.parent / "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from autonomy_governor import ActionType, AutonomyGovernor, GovernanceDecision, RiskLevel
from confidence_scorer import ConfidenceScore, ConfidenceScorer
from decision_logger import DecisionLogger
from execution_monitor import ExecutionMonitor
from n8n_client import N8nClient
from repair_engine import RepairEngine, RepairPattern
from repair_pattern_store import RepairPatternStore


# ── Pipeline Dataclasses (all frozen/immutable) ───────────────


@dataclass(frozen=True)
class DetectedIssue:
    """A workflow with detected execution errors."""
    workflow_id: str
    workflow_name: str
    error_message: str
    node_type: str
    node_name: str
    error_count: int
    severity: str
    execution_ids: tuple[str, ...]


@dataclass(frozen=True)
class ClassifiedIssue:
    """A detected issue matched (or not) to a repair pattern."""
    issue: DetectedIssue
    pattern_id: Optional[str]
    pattern_name: Optional[str]
    classification: str  # "known_pattern", "partial_match", "novel"
    risk_level: str


@dataclass(frozen=True)
class ScoredIssue:
    """A classified issue with confidence scoring."""
    classified: ClassifiedIssue
    confidence: ConfidenceScore
    recommended_action: str  # "escalate", "propose", "stage", "apply"


@dataclass(frozen=True)
class GovernedIssue:
    """A scored issue with governance decision."""
    scored: ScoredIssue
    decision: GovernanceDecision
    can_proceed: bool


@dataclass(frozen=True)
class FixResult:
    """Result of attempting a fix."""
    governed: GovernedIssue
    applied: bool
    changes: tuple[str, ...]
    backup_path: Optional[str]
    deploy_script_path: Optional[str]
    error: Optional[str]


@dataclass(frozen=True)
class VerifyResult:
    """Verification of a fix's effectiveness."""
    fix: FixResult
    validation_passed: bool
    validation_errors: tuple[str, ...]


@dataclass(frozen=True)
class RepairLoopResult:
    """Aggregate result of a full repair loop run."""
    detected: int
    classified: int
    fixed: int
    proposals_written: int
    escalated: int
    skipped_dedup: int
    errors: tuple[str, ...]
    timestamp: str


# ── Engine ─────────────────────────────────────────────────────


class AutonomousEngine:
    """Central orchestrator for the AWE auto-fix system.

    Wires together all existing tools into a 6-stage pipeline.
    At Tier 1 (Advisory), the engine proposes fixes without applying them.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        self._config_path = config_path or str(
            Path(__file__).parent / "config.yaml"
        )
        self._config = self._load_config()
        auto = self._config.get("autonomous", {})

        # Initialize components
        tier = auto.get("system", {}).get("current_tier", 1)
        self.governor = AutonomyGovernor(current_tier=tier, config=self._config)

        conf_cfg = auto.get("confidence", {})
        self.scorer = ConfidenceScorer(
            threshold_apply=conf_cfg.get("threshold_apply", 0.80),
            threshold_stage=conf_cfg.get("threshold_stage", 0.60),
            threshold_propose=conf_cfg.get("threshold_propose", 0.30),
        )

        paths_cfg = auto.get("paths", {})
        self.logger = DecisionLogger(config={
            "lifecycle": {"decisions_dir": paths_cfg.get("decisions_dir", ".tmp/decisions")}
        })

        self.store = RepairPatternStore(
            store_dir=paths_cfg.get("patterns_dir")
        )

        # Build N8nClient from existing config
        n8n_cfg = self._config.get("n8n", {})
        api_keys = self._config.get("api_keys", {})
        self._n8n = N8nClient(
            base_url=n8n_cfg.get("base_url", "https://ianimmelman89.app.n8n.cloud"),
            api_key=api_keys.get("n8n", ""),
            timeout=n8n_cfg.get("timeout_seconds", 30),
            cache_dir=self._config.get("paths", {}).get("cache_dir", ".tmp/cache"),
        )

        repair_cfg = auto.get("repair", {})
        self.repair = RepairEngine(
            n8n_client=self._n8n,
            config={"lifecycle": {
                "dedup_cooldown_seconds": repair_cfg.get("dedup_cooldown_seconds", 300),
                "backup_dir": paths_cfg.get("backup_dir", ".tmp/backups"),
            }},
            pattern_store=self.store,
        )

        mon_cfg = auto.get("monitoring", {})
        self.monitor = ExecutionMonitor(
            n8n_client=self._n8n,
            alert_threshold=mon_cfg.get("error_alert_threshold", 3),
        )

        self._repair_cfg = repair_cfg
        self._mon_cfg = mon_cfg
        self._auto_cfg = auto

    # ── Configuration ──────────────────────────────────────────

    def _load_config(self) -> dict[str, Any]:
        """Load autonomous config.yaml merged with existing config.json + .env."""
        auto_config: dict[str, Any] = {}
        config_path = Path(self._config_path)
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                auto_config = yaml.safe_load(f) or {}

        # Load existing base config
        try:
            from config_loader import load_config
            base_config = load_config()
        except Exception:
            base_config = {}

        return {**base_config, "autonomous": auto_config}

    @property
    def current_tier(self) -> int:
        return self.governor.current_tier

    @property
    def tier_name(self) -> str:
        return self.governor.tier_name

    # ── Stage 1: DETECT ────────────────────────────────────────

    def detect(self) -> list[DetectedIssue]:
        """Monitor stage — find workflows with execution errors."""
        hours = self._mon_cfg.get("execution_history_hours", 24)
        executions = self.monitor.fetch_recent_executions(hours=hours)
        failing = self.monitor.detect_failing_workflows(executions)

        issues: list[DetectedIssue] = []
        for wf in failing:
            wf_id = wf["workflow_id"]

            # Get the most recent error execution for details
            error_msg, node_type, node_name, exec_ids = self._extract_error_details(
                executions, wf_id
            )

            severity = self._classify_severity(wf["errors"], wf["error_rate"])

            issues.append(DetectedIssue(
                workflow_id=wf_id,
                workflow_name=wf["workflow_name"],
                error_message=error_msg,
                node_type=node_type,
                node_name=node_name,
                error_count=wf["errors"],
                severity=severity,
                execution_ids=tuple(exec_ids),
            ))

        return issues

    # ── Stage 2: CLASSIFY ──────────────────────────────────────

    def classify(self, issue: DetectedIssue) -> ClassifiedIssue:
        """Classification stage — match error to a repair pattern."""
        error_data = {
            "message": issue.error_message,
            "node_type": issue.node_type,
            "node_name": issue.node_name,
            "workflow_id": issue.workflow_id,
        }

        pattern = self.repair.match_pattern(error_data)

        if pattern is None:
            return ClassifiedIssue(
                issue=issue,
                pattern_id=None,
                pattern_name=None,
                classification="novel",
                risk_level="HIGH",
            )

        return ClassifiedIssue(
            issue=issue,
            pattern_id=pattern.pattern_id,
            pattern_name=pattern.name,
            classification="known_pattern",
            risk_level=pattern.risk_level.name,
        )

    # ── Stage 3: SCORE ─────────────────────────────────────────

    def score(self, classified: ClassifiedIssue) -> ScoredIssue:
        """Scoring stage — compute confidence for the proposed fix."""
        pattern_conf: Optional[float] = None
        hist_success: Optional[float] = None
        change_count = 1

        if classified.pattern_id:
            pattern = self.repair.get_pattern(classified.pattern_id)
            if pattern:
                pattern_conf = pattern.confidence
                change_count = 1  # Estimated; actual changes computed at fix time
            hist_success = self.store.get_success_rate(classified.pattern_id)

        # Look up agent owner for risk scoring
        agent_name = self._lookup_agent(classified.issue.workflow_name)

        confidence = self.scorer.score(
            workflow_id=classified.issue.workflow_id,
            pattern_confidence=pattern_conf,
            historical_success=hist_success,
            agent_name=agent_name,
            change_count=change_count,
            test_passed=None,  # No sandbox test at this stage
        )

        return ScoredIssue(
            classified=classified,
            confidence=confidence,
            recommended_action=confidence.action,
        )

    # ── Stage 4: GOVERN ────────────────────────────────────────

    def govern(self, scored: ScoredIssue) -> GovernedIssue:
        """Governance stage — check tier-based approval."""
        # Determine action type from pattern
        action_type = ActionType.UPDATE_NODE_PARAMS
        if scored.classified.pattern_id:
            pattern = self.repair.get_pattern(scored.classified.pattern_id)
            if pattern:
                action_type = pattern.action_type

        agent_name = self._lookup_agent(scored.classified.issue.workflow_name)

        decision = self.governor.evaluate(
            action_type=action_type,
            context={
                "workflow_id": scored.classified.issue.workflow_id,
                "workflow_name": scored.classified.issue.workflow_name,
                "agent_name": agent_name,
            },
        )

        return GovernedIssue(
            scored=scored,
            decision=decision,
            can_proceed=decision.approved,
        )

    # ── Stage 5: FIX ──────────────────────────────────────────

    def fix(self, governed: GovernedIssue) -> FixResult:
        """Fix stage — apply repair or write proposal."""
        issue = governed.scored.classified.issue
        pattern_id = governed.scored.classified.pattern_id
        deploy_script = self.repair.find_deploy_script(issue.workflow_name)

        # At Tier 1 (Advisory): always write proposal, never apply
        if not governed.can_proceed:
            proposal = self._write_proposal(governed)
            return FixResult(
                governed=governed,
                applied=False,
                changes=("Proposal written: " + proposal,) if proposal else (),
                backup_path=None,
                deploy_script_path=deploy_script,
                error=None,
            )

        # Tier 3+: Apply the fix via RepairEngine
        if not pattern_id:
            return FixResult(
                governed=governed,
                applied=False,
                changes=(),
                backup_path=None,
                deploy_script_path=deploy_script,
                error="No pattern matched — cannot auto-fix",
            )

        pattern = self.repair.get_pattern(pattern_id)
        if not pattern:
            return FixResult(
                governed=governed,
                applied=False,
                changes=(),
                backup_path=None,
                deploy_script_path=deploy_script,
                error=f"Pattern {pattern_id} not found in registry",
            )

        result = self.repair.apply_pattern(issue.workflow_id, pattern)
        return FixResult(
            governed=governed,
            applied=result.get("success", False),
            changes=tuple(result.get("changes", [])),
            backup_path=result.get("backup_path"),
            deploy_script_path=deploy_script,
            error=result.get("details") if not result.get("success") else None,
        )

    # ── Stage 6: VERIFY ───────────────────────────────────────

    def verify(self, fix_result: FixResult) -> VerifyResult:
        """Verification stage — validate the fixed workflow."""
        if not fix_result.applied:
            return VerifyResult(
                fix=fix_result,
                validation_passed=True,  # No fix applied, nothing to verify
                validation_errors=(),
            )

        # Basic validation: fetch the workflow and check structure
        errors: list[str] = []
        try:
            from n8n_api_helpers import safe_get_workflow
            wf = safe_get_workflow(
                self._n8n,
                fix_result.governed.scored.classified.issue.workflow_id,
            )
            if wf is None:
                errors.append("Could not fetch workflow after fix")
            elif not wf.get("nodes"):
                errors.append("Workflow has no nodes after fix")
        except Exception as exc:
            errors.append(f"Verification error: {exc}")

        return VerifyResult(
            fix=fix_result,
            validation_passed=len(errors) == 0,
            validation_errors=tuple(errors),
        )

    # ── Stage 7: LOG ──────────────────────────────────────────

    def log_decision(
        self,
        issue: DetectedIssue,
        classified: ClassifiedIssue,
        scored: ScoredIssue,
        governed: GovernedIssue,
        fix_result: FixResult,
        verify_result: VerifyResult,
    ) -> str:
        """Log the full pipeline result to the decision audit trail."""
        outcome = "proposed"
        if fix_result.applied and verify_result.validation_passed:
            outcome = "fixed"
        elif fix_result.applied and not verify_result.validation_passed:
            outcome = "fix_failed_verification"
        elif fix_result.error:
            outcome = "error"
        elif governed.can_proceed is False and scored.recommended_action == "escalate":
            outcome = "escalated"

        decision_id = self.logger.log_decision(
            loop_type="repair",
            workflow_id=issue.workflow_id,
            agent_owner=self._lookup_agent(issue.workflow_name),
            issue_detected=issue.error_message[:500],
            classification=classified.classification,
            confidence_score=scored.confidence.overall,
            risk_level=classified.risk_level,
            action_taken=scored.recommended_action,
            changes_made="; ".join(fix_result.changes) if fix_result.changes else "",
            outcome=outcome,
            backup_path=fix_result.backup_path or "",
        )

        # Log escalation if needed
        if scored.recommended_action == "escalate":
            self.logger.log_escalation(
                workflow_id=issue.workflow_id,
                severity=issue.severity,
                category=classified.classification,
                description=issue.error_message[:500],
                recommended_action="Manual investigation required",
            )

        return decision_id

    # ── Composite Orchestrators ───────────────────────────────

    def run_repair_loop(self) -> RepairLoopResult:
        """Run the full repair pipeline for all detected issues."""
        now = datetime.now(tz=None).isoformat() + "Z"
        issues = self.detect()
        errors: list[str] = []
        fixed = 0
        proposals = 0
        escalated = 0
        skipped = 0
        classified_count = 0

        for issue in issues:
            # Dedup check
            if self.repair.is_dedup_blocked(issue.workflow_id, issue.error_message):
                skipped += 1
                continue

            try:
                classified = self.classify(issue)
                classified_count += 1

                scored = self.score(classified)
                governed = self.govern(scored)
                fix_result = self.fix(governed)
                verify_result = self.verify(fix_result)

                self.log_decision(issue, classified, scored, governed, fix_result, verify_result)

                if fix_result.applied and verify_result.validation_passed:
                    fixed += 1
                elif not governed.can_proceed and scored.recommended_action != "escalate":
                    proposals += 1
                elif scored.recommended_action == "escalate":
                    escalated += 1

            except Exception as exc:
                errors.append(f"{issue.workflow_id}: {exc}")

        return RepairLoopResult(
            detected=len(issues),
            classified=classified_count,
            fixed=fixed,
            proposals_written=proposals,
            escalated=escalated,
            skipped_dedup=skipped,
            errors=tuple(errors),
            timestamp=now,
        )

    def run_status(self) -> dict[str, Any]:
        """Read-only health check — no mutations."""
        hours = self._mon_cfg.get("execution_history_hours", 24)
        executions = self.monitor.fetch_recent_executions(hours=hours)
        workflows = self._n8n.list_workflows(use_cache=True)

        dashboard = self.monitor.generate_health_dashboard(executions, workflows)
        recent_decisions = self.logger.get_recent_decisions(hours=24)
        pattern_stats = self.repair.get_pattern_stats()

        return {
            "dashboard": dashboard,
            "recent_decisions": recent_decisions,
            "pattern_stats": pattern_stats,
            "autonomy_tier": self.current_tier,
            "tier_name": self.tier_name,
            "emergency_stopped": self.governor.is_emergency_stopped,
        }

    # ── Internal Helpers ──────────────────────────────────────

    def _extract_error_details(
        self,
        executions: list[dict[str, Any]],
        workflow_id: str,
    ) -> tuple[str, str, str, list[str]]:
        """Extract error message, node info, and exec IDs from failing executions."""
        error_msg = ""
        node_type = ""
        node_name = ""
        exec_ids: list[str] = []

        for ex in executions:
            ex_wf_id = ex.get("workflowId") or ex.get("workflowData", {}).get("id", "")
            if str(ex_wf_id) != str(workflow_id):
                continue
            if ex.get("status") != "error":
                continue

            exec_ids.append(str(ex.get("id", "")))

            # Try to extract error details from execution data
            if not error_msg:
                data = ex.get("data", {})
                result_data = data.get("resultData", {})
                error = result_data.get("error", {})

                if isinstance(error, dict):
                    error_msg = error.get("message", "")
                    node_name = error.get("node", {}).get("name", "") if isinstance(error.get("node"), dict) else ""
                    node_type = error.get("node", {}).get("type", "") if isinstance(error.get("node"), dict) else ""
                elif isinstance(error, str):
                    error_msg = error

                # Fallback: check run data for last error
                if not error_msg:
                    run_data = result_data.get("runData", {})
                    for nd_name, nd_runs in run_data.items():
                        if isinstance(nd_runs, list):
                            for run in nd_runs:
                                if isinstance(run, dict) and run.get("error"):
                                    err = run["error"]
                                    error_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                                    node_name = nd_name
                                    break
                        if error_msg:
                            break

        if not error_msg:
            error_msg = "Execution failed (no detailed error message available)"

        return error_msg, node_type, node_name, exec_ids[:10]

    @staticmethod
    def _classify_severity(error_count: int, error_rate: float) -> str:
        """Classify issue severity based on error count and rate."""
        if error_rate >= 90 and error_count >= 10:
            return "P1"
        if error_rate >= 70 or error_count >= 7:
            return "P2"
        if error_rate >= 50 or error_count >= 5:
            return "P3"
        return "P4"

    @staticmethod
    def _lookup_agent(workflow_name: str) -> str:
        """Look up the owning agent for a workflow from agent_registry."""
        try:
            from agent_registry import AGENTS
            wf_lower = workflow_name.lower()
            for agent_id, agent in AGENTS.items():
                if hasattr(agent, "workflows"):
                    for wf in agent.workflows:
                        if isinstance(wf, str) and wf.lower() in wf_lower:
                            return agent_id
        except (ImportError, AttributeError):
            pass
        return ""

    def _write_proposal(self, governed: GovernedIssue) -> Optional[str]:
        """Write a fix proposal to autonomous/memory/recommendations/."""
        issue = governed.scored.classified.issue
        classified = governed.scored.classified
        scored = governed.scored

        proposal = {
            "proposal_id": f"PROP-{datetime.now(tz=None).strftime('%Y%m%d%H%M%S')}-{issue.workflow_id[:8]}",
            "timestamp": datetime.now(tz=None).isoformat() + "Z",
            "workflow_id": issue.workflow_id,
            "workflow_name": issue.workflow_name,
            "error_message": issue.error_message[:500],
            "error_count": issue.error_count,
            "severity": issue.severity,
            "pattern_id": classified.pattern_id,
            "pattern_name": classified.pattern_name,
            "classification": classified.classification,
            "confidence_score": scored.confidence.overall,
            "confidence_breakdown": {
                "pattern_match": scored.confidence.pattern_match,
                "historical_success": scored.confidence.historical_success,
                "risk_profile": scored.confidence.risk_profile,
                "change_magnitude": scored.confidence.change_magnitude,
                "test_quality": scored.confidence.test_quality,
            },
            "recommended_action": scored.recommended_action,
            "governance_reason": governed.decision.reason,
            "deploy_script": self.repair.find_deploy_script(issue.workflow_name),
            "note": "ALSO UPDATE deploy script if fix is applied manually",
        }

        proposals_dir = Path(__file__).parent / "memory" / "recommendations"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        path = proposals_dir / f"{proposal['proposal_id']}.json"

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(proposal, f, indent=2, ensure_ascii=False)
            return str(path)
        except OSError as exc:
            print(f"  [AWE] Failed to write proposal: {exc}")
            return None

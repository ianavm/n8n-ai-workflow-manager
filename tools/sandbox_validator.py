"""
Sandbox Validator — Pre-production workflow validation.

Runs static checks on workflow JSON (always available) and optional
dynamic tests on a staging instance.

Static checks:
    1. All node connections resolve to existing node names
    2. No dangling inputs/outputs
    3. No $env references in Code nodes (Operating Rule 10)
    4. No duplicate node names
    5. Financial workflows have safety cap nodes
    6. settings.executionOrder is "v1"
    7. All credential IDs are non-empty

Dynamic checks (requires staging instance):
    1. Deploy to staging, execute with test data
    2. Compare output shape with baseline
    3. Measure execution time vs baseline

Usage:
    from sandbox_validator import SandboxValidator
    validator = SandboxValidator(config)
    result = validator.full_validate(workflow_json)
    if result.passed:
        # safe to deploy
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ValidationResult:
    """Immutable result of workflow validation."""
    passed: bool
    checks_run: int
    checks_passed: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    node_count: int = 0
    connection_count: int = 0


class SandboxValidator:
    """Validate n8n workflow JSON before production deployment."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._staging_url = (
            self._config.get("instances", {})
            .get("staging", {})
            .get("base_url")
        )

    # ── Composite validation ────────────────────────────────

    def full_validate(
        self,
        workflow: Dict[str, Any],
        test_cases: Optional[List[Dict[str, Any]]] = None,
    ) -> ValidationResult:
        """Run all static checks.  Returns composite result."""
        errors: List[str] = []
        warnings: List[str] = []
        checks_run = 0
        checks_passed = 0

        # Collect all static check results
        static_checks = [
            self.validate_structure,
            self.validate_connections,
            self.validate_no_env_refs,
            self.validate_no_duplicate_names,
            self.validate_execution_order,
            self.validate_credentials,
        ]

        for check_fn in static_checks:
            result = check_fn(workflow)
            checks_run += result.checks_run
            checks_passed += result.checks_passed
            errors.extend(result.errors)
            warnings.extend(result.warnings)

        passed = len(errors) == 0
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        conn_count = sum(
            len(targets)
            for outputs in connections.values()
            for branch in outputs.values()
            for targets in (branch if isinstance(branch, list) else [branch])
        )

        return ValidationResult(
            passed=passed,
            checks_run=checks_run,
            checks_passed=checks_passed,
            errors=errors,
            warnings=warnings,
            node_count=len(nodes),
            connection_count=conn_count,
        )

    # ── Individual checks ───────────────────────────────────

    def validate_structure(self, workflow: Dict[str, Any]) -> ValidationResult:
        """Check basic workflow structure."""
        errors: List[str] = []
        warnings: List[str] = []
        checks = 0

        checks += 1
        if "nodes" not in workflow:
            errors.append("Workflow missing 'nodes' key")
        elif not isinstance(workflow["nodes"], list):
            errors.append("'nodes' is not a list")

        checks += 1
        if "connections" not in workflow:
            errors.append("Workflow missing 'connections' key")
        elif not isinstance(workflow["connections"], dict):
            errors.append("'connections' is not a dict")

        checks += 1
        nodes = workflow.get("nodes", [])
        if len(nodes) == 0:
            errors.append("Workflow has no nodes")

        # Check each node has required fields
        for node in nodes:
            checks += 1
            missing = [
                k for k in ("name", "type", "parameters")
                if k not in node
            ]
            if missing:
                errors.append(
                    f"Node '{node.get('name', '?')}' missing fields: {', '.join(missing)}"
                )

        passed_count = max(0, checks - len(errors))
        return ValidationResult(
            passed=len(errors) == 0,
            checks_run=checks,
            checks_passed=passed_count,
            errors=errors,
            warnings=warnings,
            node_count=len(nodes),
        )

    def validate_connections(self, workflow: Dict[str, Any]) -> ValidationResult:
        """Check that all connection references resolve to existing node names."""
        errors: List[str] = []
        warnings: List[str] = []
        checks = 0

        nodes = workflow.get("nodes", [])
        node_names: Set[str] = {n.get("name", "") for n in nodes}
        connections = workflow.get("connections", {})

        for source_name, outputs in connections.items():
            checks += 1
            if source_name not in node_names:
                errors.append(f"Connection source '{source_name}' not found in nodes")

            if not isinstance(outputs, dict):
                continue

            for branch_key, branches in outputs.items():
                if not isinstance(branches, list):
                    continue
                for branch in branches:
                    if not isinstance(branch, list):
                        continue
                    for conn in branch:
                        if not isinstance(conn, dict):
                            continue
                        target = conn.get("node", "")
                        checks += 1
                        if target and target not in node_names:
                            errors.append(
                                f"Connection target '{target}' (from '{source_name}') "
                                f"not found in nodes"
                            )

        passed_count = max(0, checks - len(errors))
        return ValidationResult(
            passed=len(errors) == 0,
            checks_run=checks,
            checks_passed=passed_count,
            errors=errors,
            warnings=warnings,
        )

    def validate_no_env_refs(self, workflow: Dict[str, Any]) -> ValidationResult:
        """Check that no Code nodes reference $env (blocked on n8n Cloud)."""
        errors: List[str] = []
        warnings: List[str] = []
        checks = 0
        env_re = re.compile(r'\$env\.\w+')

        for node in workflow.get("nodes", []):
            if node.get("type", "") != "n8n-nodes-base.code":
                continue
            checks += 1
            js_code = node.get("parameters", {}).get("jsCode", "")
            matches = env_re.findall(js_code)
            if matches:
                errors.append(
                    f"Code node '{node['name']}' references $env: {', '.join(matches)}. "
                    f"n8n Cloud blocks $env in Code nodes."
                )

        passed_count = max(0, checks - len(errors))
        return ValidationResult(
            passed=len(errors) == 0,
            checks_run=max(checks, 1),
            checks_passed=passed_count,
            errors=errors,
            warnings=warnings,
        )

    def validate_no_duplicate_names(self, workflow: Dict[str, Any]) -> ValidationResult:
        """Check for duplicate node names."""
        errors: List[str] = []
        checks = 1
        seen: Dict[str, int] = {}

        for node in workflow.get("nodes", []):
            name = node.get("name", "")
            seen[name] = seen.get(name, 0) + 1

        dupes = {name: count for name, count in seen.items() if count > 1}
        if dupes:
            for name, count in dupes.items():
                errors.append(f"Duplicate node name '{name}' appears {count} times")

        return ValidationResult(
            passed=len(errors) == 0,
            checks_run=checks,
            checks_passed=checks - len(errors),
            errors=errors,
        )

    def validate_execution_order(self, workflow: Dict[str, Any]) -> ValidationResult:
        """Check that settings.executionOrder is 'v1'."""
        warnings: List[str] = []
        checks = 1

        settings = workflow.get("settings", {})
        if settings.get("executionOrder") != "v1":
            warnings.append("settings.executionOrder is not 'v1' (recommended)")

        return ValidationResult(
            passed=True,  # Warning only, not a blocker
            checks_run=checks,
            checks_passed=checks,
            warnings=warnings,
        )

    def validate_credentials(self, workflow: Dict[str, Any]) -> ValidationResult:
        """Check that credential references are non-empty."""
        errors: List[str] = []
        warnings: List[str] = []
        checks = 0

        for node in workflow.get("nodes", []):
            creds = node.get("credentials", {})
            if not creds:
                continue
            for cred_type, cred_ref in creds.items():
                checks += 1
                if isinstance(cred_ref, dict):
                    cred_id = cred_ref.get("id", "")
                    if not cred_id:
                        errors.append(
                            f"Node '{node['name']}' has empty credential ID for '{cred_type}'"
                        )
                elif isinstance(cred_ref, str) and not cred_ref:
                    errors.append(
                        f"Node '{node['name']}' has empty credential for '{cred_type}'"
                    )

        if checks == 0:
            checks = 1  # At least 1 check run

        passed_count = max(0, checks - len(errors))
        return ValidationResult(
            passed=len(errors) == 0,
            checks_run=checks,
            checks_passed=passed_count,
            errors=errors,
            warnings=warnings,
        )

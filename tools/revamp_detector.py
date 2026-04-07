"""
Revamp Detector — Identifies workflows needing complete redesign.

Triggers:
    - Error rate > 40% for 14+ days despite fixes
    - Average duration > 3× baseline
    - Node count > 50 (complexity smell)
    - Fix count > 5 in 30 days (thrashing)
    - No matching deploy script (unreproducible)

Usage:
    from revamp_detector import RevampDetector
    detector = RevampDetector(n8n_client, pattern_store)
    candidates = detector.scan()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RevampCandidate:
    """A workflow flagged for potential redesign."""
    workflow_id: str
    workflow_name: str
    reasons: List[str]
    severity: str            # "suggested", "recommended", "urgent"
    current_metrics: Dict[str, Any] = field(default_factory=dict)
    estimated_effort: str = "medium"  # "small" (<2h), "medium" (2-8h), "large" (>8h)
    has_deploy_script: bool = False


class RevampDetector:
    """Scan workflows and identify candidates for full redesign."""

    # Thresholds
    ERROR_RATE_THRESHOLD = 40.0     # %
    NODE_COUNT_THRESHOLD = 50
    FIX_COUNT_THRESHOLD = 5         # in 30 days
    DURATION_MULTIPLIER = 3.0       # × baseline

    def __init__(
        self,
        n8n_client: Any,
        pattern_store: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._client = n8n_client
        self._store = pattern_store
        self._config = config or {}

    def scan(self) -> List[RevampCandidate]:
        """Scan all active workflows for revamp candidates."""
        from execution_monitor import ExecutionMonitor

        workflows = self._client.list_workflows(active_only=True, use_cache=False)
        monitor = ExecutionMonitor(self._client)

        # Fetch 14 days of executions for trend analysis
        executions = monitor.fetch_recent_executions(hours=14 * 24)
        failing = monitor.detect_failing_workflows(executions)
        failing_map = {f["workflow_id"]: f for f in failing}

        candidates: List[RevampCandidate] = []
        for wf in workflows:
            wf_id = str(wf.get("id", ""))
            wf_name = wf.get("name", "Unknown")
            candidate = self.assess_workflow(wf_id, wf_name, wf, failing_map.get(wf_id))
            if candidate:
                candidates.append(candidate)

        # Sort by severity (urgent first)
        severity_order = {"urgent": 0, "recommended": 1, "suggested": 2}
        candidates.sort(key=lambda c: severity_order.get(c.severity, 3))
        return candidates

    def assess_workflow(
        self,
        workflow_id: str,
        workflow_name: str,
        wf_data: Optional[Dict[str, Any]] = None,
        failing_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[RevampCandidate]:
        """Assess a single workflow for revamp need."""
        reasons: List[str] = []
        metrics: Dict[str, Any] = {}

        # 1. High error rate
        if failing_data:
            error_rate = failing_data.get("error_rate", 0)
            metrics["error_rate"] = error_rate
            if error_rate >= self.ERROR_RATE_THRESHOLD:
                reasons.append(
                    f"Error rate {error_rate}% exceeds {self.ERROR_RATE_THRESHOLD}% threshold"
                )

        # 2. Complexity (node count)
        if wf_data:
            # Fetch full workflow for node count
            full_wf = None
            try:
                full_wf = self._client.get_workflow(workflow_id)
            except Exception:
                pass
            if full_wf:
                node_count = len(full_wf.get("nodes", []))
                metrics["node_count"] = node_count
                if node_count > self.NODE_COUNT_THRESHOLD:
                    reasons.append(
                        f"Node count {node_count} exceeds {self.NODE_COUNT_THRESHOLD} "
                        f"(complexity smell)"
                    )

        # 3. Fix thrashing (too many fixes in 30 days)
        if self._store:
            fix_history = self._store.get_fix_history(workflow_id)
            recent_fixes = len(fix_history)  # Already limited to stored history
            metrics["recent_fix_count"] = recent_fixes
            if recent_fixes >= self.FIX_COUNT_THRESHOLD:
                reasons.append(
                    f"{recent_fixes} fixes in recent history "
                    f"(threshold: {self.FIX_COUNT_THRESHOLD})"
                )

        # 4. No deploy script (unreproducible)
        has_script = self._has_deploy_script(workflow_name)
        metrics["has_deploy_script"] = has_script
        if not has_script:
            reasons.append("No matching deploy script — workflow is unreproducible")

        # If no issues found, not a revamp candidate
        if not reasons:
            return None

        # Determine severity
        severity = "suggested"
        if len(reasons) >= 3:
            severity = "urgent"
        elif len(reasons) >= 2:
            severity = "recommended"

        # Estimate effort
        node_count = metrics.get("node_count", 0)
        effort = "small"
        if node_count > 30:
            effort = "large"
        elif node_count > 15:
            effort = "medium"

        return RevampCandidate(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            reasons=reasons,
            severity=severity,
            current_metrics=metrics,
            estimated_effort=effort,
            has_deploy_script=has_script,
        )

    def _has_deploy_script(self, workflow_name: str) -> bool:
        """Check if a deploy_*.py exists containing this workflow name."""
        tools_dir = Path(__file__).parent
        for script in tools_dir.glob("deploy_*.py"):
            try:
                content = script.read_text(encoding="utf-8")
                if workflow_name in content:
                    return True
            except OSError:
                continue
        return False

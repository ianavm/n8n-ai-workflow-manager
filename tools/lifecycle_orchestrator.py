"""
Lifecycle Orchestrator — Central state machine for the AWLM.

Drives four autonomous execution loops:
    1. Repair   — detect → classify → fix → test → apply → log
    2. Optimize — analyze → propose → test → apply → compare
    3. Build    — spec → generate → validate → deploy
    4. Revamp   — scan → assess → recommend

Contains NO business logic — dispatches to action engines and
enforces governance via the AutonomyGovernor.

Usage:
    python tools/lifecycle_orchestrator.py repair          # One repair cycle
    python tools/lifecycle_orchestrator.py optimize        # One optimise cycle
    python tools/lifecycle_orchestrator.py revamp-scan     # Scan for revamp candidates
    python tools/lifecycle_orchestrator.py build spec.json # Build from spec
    python tools/lifecycle_orchestrator.py status          # Show system status
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from config_loader import load_config
from n8n_client import N8nClient
from n8n_api_helpers import build_client_safe
from execution_monitor import ExecutionMonitor
from repair_engine import RepairEngine
from repair_pattern_store import RepairPatternStore
from sandbox_validator import SandboxValidator
from confidence_scorer import ConfidenceScorer
from autonomy_governor import (
    ActionType,
    AutonomyGovernor,
    GovernanceDecision,
    RiskLevel,
)
from decision_logger import DecisionLogger


# ── Loop types ──────────────────────────────────────────────
class LoopType(Enum):
    REPAIR = "repair"
    OPTIMIZE = "optimize"
    BUILD = "build"
    REVAMP = "revamp"


@dataclass
class LoopContext:
    """Mutable context carried through a single loop iteration."""
    loop_type: LoopType
    workflow_id: str = ""
    workflow_name: str = ""
    agent_owner: str = ""
    trigger_source: str = ""
    changes_made: List[str] = field(default_factory=list)
    decision_log: List[Dict[str, Any]] = field(default_factory=list)
    dry_run: bool = False


# ── Orchestrator ────────────────────────────────────────────
class LifecycleOrchestrator:
    """Central state machine for autonomous workflow lifecycle management."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or load_config()
        self._lc = self._config.get("lifecycle", {})

        # Build subsystems
        self._client = build_client_safe(self._config)
        if self._client is None:
            raise RuntimeError("Cannot initialise n8n client — check config")

        alert_threshold = self._config.get("monitoring", {}).get("error_alert_threshold", 3)
        self._monitor = ExecutionMonitor(self._client, alert_threshold=alert_threshold)
        self._pattern_store = RepairPatternStore(self._lc.get("pattern_store_dir"))
        self._repair = RepairEngine(self._client, self._config, self._pattern_store)
        self._validator = SandboxValidator(self._config)
        self._scorer = ConfidenceScorer(
            threshold_apply=self._lc.get("confidence_threshold_apply", 0.80),
            threshold_stage=self._lc.get("confidence_threshold_stage", 0.60),
            threshold_propose=self._lc.get("confidence_threshold_propose", 0.30),
        )
        self._governor = AutonomyGovernor(
            current_tier=self._lc.get("autonomy_tier", 3),
            config=self._config,
        )
        self._logger = DecisionLogger(self._config)

    # ── Public loop entry points ────────────────────────────

    def run_repair_loop(self) -> Dict[str, Any]:
        """One full repair cycle: detect → classify → score → govern → fix → log."""
        print("\n" + "=" * 60)
        print(f"AWLM REPAIR LOOP  [{datetime.now(tz=None).isoformat()}Z]")
        print(f"Tier: {self._governor.current_tier} ({self._governor.tier_name})")
        print("=" * 60)

        # 1. DETECT
        issues = self._detect_issues()
        if not issues:
            print("\n  No failing workflows detected.")
            return {"loop": "repair", "issues": 0, "actions": []}

        print(f"\n  Detected {len(issues)} failing workflow(s).")
        self._logger.log_detection(issues)

        # 2-7. Process each issue
        actions: List[Dict[str, Any]] = []
        for issue in issues:
            result = self._process_repair(issue)
            actions.append(result)

        # Summary
        applied = sum(1 for a in actions if a.get("action") == "applied")
        proposed = sum(1 for a in actions if a.get("action") == "propose")
        escalated = sum(1 for a in actions if a.get("action") == "escalate")
        blocked = sum(1 for a in actions if a.get("action") == "governance_denied")

        print(f"\n{'=' * 60}")
        print(f"REPAIR LOOP COMPLETE")
        print(f"  Applied:   {applied}")
        print(f"  Proposed:  {proposed}")
        print(f"  Escalated: {escalated}")
        print(f"  Blocked:   {blocked}")
        print(f"{'=' * 60}")

        return {
            "loop": "repair",
            "issues": len(issues),
            "actions": actions,
            "summary": {
                "applied": applied,
                "proposed": proposed,
                "escalated": escalated,
                "blocked": blocked,
            },
        }

    def run_optimization_loop(self) -> Dict[str, Any]:
        """One optimisation cycle (placeholder — Phase 3)."""
        print("\n[AWLM] Optimization loop not yet implemented (Phase 3).")
        return {"loop": "optimize", "status": "not_implemented"}

    def run_build_loop(self, spec_path: str) -> Dict[str, Any]:
        """Build a workflow from spec (placeholder — Phase 4)."""
        print(f"\n[AWLM] Build loop not yet implemented (Phase 4). Spec: {spec_path}")
        return {"loop": "build", "status": "not_implemented", "spec": spec_path}

    def run_revamp_scan(self) -> Dict[str, Any]:
        """Scan for workflows needing revamp (placeholder — Phase 4)."""
        print("\n[AWLM] Revamp scan not yet implemented (Phase 4).")
        return {"loop": "revamp", "status": "not_implemented"}

    def run_status(self) -> Dict[str, Any]:
        """Show AWLM system status."""
        print("\n" + "=" * 60)
        print("AWLM SYSTEM STATUS")
        print("=" * 60)
        print(f"  Autonomy Tier: {self._governor.current_tier} ({self._governor.tier_name})")
        print(f"  Emergency Stop: {'ACTIVE' if self._governor.is_emergency_stopped else 'Off'}")
        print(f"  Repair Patterns: {len(self._repair.list_patterns())}")

        # Pattern stats
        stats = self._repair.get_pattern_stats()
        print(f"\n  Pattern Stats:")
        for pid, s in stats.items():
            print(f"    {pid}: confidence={s['confidence']:.2f}, "
                  f"observed={s['observed_success_rate']:.2f}, "
                  f"risk={s['risk_level']}")

        # Recent decisions
        recent = self._logger.get_recent_decisions(hours=24)
        print(f"\n  Decisions (last 24h): {len(recent)}")
        for d in recent[:5]:
            print(f"    [{d.get('Action_Taken', '?')}] {d.get('Workflow_ID', '?')}: "
                  f"{d.get('Classification', '?')} → {d.get('Outcome', '?')}")

        return {
            "tier": self._governor.current_tier,
            "patterns": len(self._repair.list_patterns()),
            "recent_decisions": len(recent),
        }

    # ── Internal: detection ─────────────────────────────────

    def _detect_issues(self) -> List[Dict[str, Any]]:
        """Fetch recent executions and identify failing workflows."""
        hours = max(1, self._lc.get("repair_loop_interval_minutes", 15) / 60 * 2)
        executions = self._monitor.fetch_recent_executions(hours=int(hours))
        failing = self._monitor.detect_failing_workflows(executions)
        return failing

    # ── Internal: per-issue repair ──────────────────────────

    def _process_repair(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single failing workflow through the repair pipeline."""
        wf_id = issue.get("workflow_id", "")
        wf_name = issue.get("workflow_name", "")
        error_rate = issue.get("error_rate", 0)
        error_count = issue.get("errors", 0)

        print(f"\n  --- Processing: {wf_name} ({wf_id}) ---")
        print(f"      Error rate: {error_rate}% ({error_count} errors)")

        # Resolve agent owner
        agent_owner = self._resolve_agent(wf_id)

        # Build error data from the most recent error execution
        error_data = self._get_latest_error(wf_id)
        error_text = error_data.get("message", "Unknown error")
        print(f"      Latest error: {error_text[:120]}")

        # 2. CLASSIFY — match to repair pattern
        pattern = self._repair.match_pattern(error_data)
        pattern_id = pattern.pattern_id if pattern else "novel"
        pattern_conf = pattern.confidence if pattern else None
        print(f"      Pattern: {pattern_id} (confidence={pattern_conf})")

        # 3. SCORE
        hist_success = None
        if pattern:
            hist_success = self._pattern_store.get_success_rate(pattern.pattern_id)

        score = self._scorer.score(
            workflow_id=wf_id,
            pattern_confidence=pattern_conf,
            historical_success=hist_success,
            agent_name=agent_owner,
            change_count=1 if pattern else 0,
        )
        print(f"      Confidence: {score.overall:.3f} → action={score.action}")

        # 4. GOVERN
        action_type = pattern.action_type if pattern else ActionType.UPDATE_NODE_PARAMS
        gov = self._governor.evaluate(
            action_type,
            context={
                "workflow_id": wf_id,
                "workflow_name": wf_name,
                "agent_name": agent_owner,
            },
        )
        print(f"      Governance: {'APPROVED' if gov.approved else 'DENIED'} — {gov.reason}")

        # Branch on action
        if score.action == "escalate" or not pattern:
            return self._handle_escalation(
                wf_id, wf_name, agent_owner, error_text, pattern_id, score
            )

        if not gov.approved:
            return self._handle_governance_denied(
                wf_id, wf_name, agent_owner, error_text, pattern_id, score, gov
            )

        if score.action == "propose":
            return self._handle_proposal(
                wf_id, wf_name, agent_owner, error_text, pattern_id, pattern, score
            )

        # 5. FIX (action is "apply" or "stage")
        return self._handle_apply(
            wf_id, wf_name, agent_owner, error_text, pattern, score, gov
        )

    # ── Action handlers ─────────────────────────────────────

    def _handle_escalation(
        self, wf_id: str, wf_name: str, agent: str,
        error_text: str, pattern_id: str, score: Any,
    ) -> Dict[str, Any]:
        print(f"      → ESCALATING (score too low or novel error)")
        self._logger.log_escalation(
            workflow_id=wf_id,
            severity="P2" if score.overall >= 0.2 else "P1",
            category="repair",
            description=f"[{wf_name}] {error_text[:500]}",
            recommended_action=f"Pattern={pattern_id}, confidence={score.overall:.3f}",
        )
        self._logger.log_decision(
            loop_type="repair",
            workflow_id=wf_id,
            agent_owner=agent,
            issue_detected=error_text[:500],
            classification=pattern_id,
            confidence_score=score.overall,
            risk_level=score.action,
            action_taken="escalate",
            outcome="escalated",
        )
        return {"workflow_id": wf_id, "action": "escalate", "pattern": pattern_id}

    def _handle_governance_denied(
        self, wf_id: str, wf_name: str, agent: str,
        error_text: str, pattern_id: str, score: Any, gov: GovernanceDecision,
    ) -> Dict[str, Any]:
        print(f"      → GOVERNANCE DENIED: {gov.reason}")
        self._logger.log_decision(
            loop_type="repair",
            workflow_id=wf_id,
            agent_owner=agent,
            issue_detected=error_text[:500],
            classification=pattern_id,
            confidence_score=score.overall,
            risk_level=gov.risk_level.name,
            action_taken="governance_denied",
            outcome="blocked",
        )
        return {"workflow_id": wf_id, "action": "governance_denied", "reason": gov.reason}

    def _handle_proposal(
        self, wf_id: str, wf_name: str, agent: str,
        error_text: str, pattern_id: str, pattern: Any, score: Any,
    ) -> Dict[str, Any]:
        deploy_script = self._repair.find_deploy_script(wf_name)
        print(f"      → PROPOSING fix (confidence {score.overall:.3f} < apply threshold)")
        if deploy_script:
            print(f"      → Deploy script found: {deploy_script}")
        self._logger.log_decision(
            loop_type="repair",
            workflow_id=wf_id,
            agent_owner=agent,
            issue_detected=error_text[:500],
            classification=pattern_id,
            confidence_score=score.overall,
            risk_level=pattern.risk_level.name if pattern else "UNKNOWN",
            action_taken="propose",
            changes_made=f"Proposed: {pattern.name}" if pattern else "Novel — needs manual review",
            outcome="pending_review",
        )
        return {
            "workflow_id": wf_id,
            "action": "propose",
            "pattern": pattern_id,
            "deploy_script": deploy_script,
        }

    def _handle_apply(
        self, wf_id: str, wf_name: str, agent: str,
        error_text: str, pattern: Any, score: Any, gov: GovernanceDecision,
    ) -> Dict[str, Any]:
        print(f"      → APPLYING fix: {pattern.name}")

        # Apply the repair
        result = self._repair.apply_pattern(wf_id, pattern)
        success = result.get("success", False)
        changes = result.get("changes", [])

        if changes:
            print(f"      → Changes: {', '.join(changes[:5])}")

        # Validate the patched workflow
        if success and changes:
            from n8n_api_helpers import safe_get_workflow
            patched = safe_get_workflow(self._client, wf_id)
            if patched:
                vr = self._validator.full_validate(patched)
                if not vr.passed:
                    print(f"      → VALIDATION FAILED: {', '.join(vr.errors[:3])}")
                    # Rollback would happen here in production
                    success = False

        # Check if deploy script needs updating
        deploy_script = self._repair.find_deploy_script(wf_name)
        if deploy_script and pattern.requires_deploy_script_update:
            print(f"      ⚠ Deploy script needs manual update: {deploy_script}")

        outcome = "success" if success else "failed"
        self._logger.log_decision(
            loop_type="repair",
            workflow_id=wf_id,
            agent_owner=agent,
            issue_detected=error_text[:500],
            classification=pattern.pattern_id,
            confidence_score=score.overall,
            risk_level=pattern.risk_level.name,
            action_taken="apply",
            changes_made="; ".join(changes) if changes else "No changes needed",
            outcome=outcome,
        )

        return {
            "workflow_id": wf_id,
            "action": "applied" if success else "failed",
            "pattern": pattern.pattern_id,
            "changes": changes,
            "deploy_script_update_needed": (
                deploy_script if pattern.requires_deploy_script_update else None
            ),
        }

    # ── Helpers ─────────────────────────────────────────────

    def _resolve_agent(self, workflow_id: str) -> str:
        """Look up which agent owns this workflow."""
        try:
            from agent_registry import AGENTS
            for name, agent in AGENTS.items():
                # Agent workflow IDs use uppercase prefix (e.g., "ACC_WF01")
                # Actual n8n IDs are different; check by prefix match
                for wf_ref in agent.workflows:
                    if wf_ref.lower() in workflow_id.lower():
                        return name
        except ImportError:
            pass
        return ""

    def _get_latest_error(self, workflow_id: str) -> Dict[str, Any]:
        """Fetch the most recent error execution for a workflow."""
        try:
            errors = self._client.list_executions(
                workflow_id=workflow_id, status="error", limit=1
            )
            if errors:
                ex = errors[0]
                # Extract error message from execution data
                data = ex.get("data", {})
                if isinstance(data, dict):
                    result_data = data.get("resultData", {})
                    run_data = result_data.get("runData", {})
                    for node_name, node_runs in run_data.items():
                        if isinstance(node_runs, list):
                            for run in node_runs:
                                error = run.get("error", {})
                                if error:
                                    return {
                                        "message": error.get("message", str(error)),
                                        "node_name": node_name,
                                        "node_type": run.get("source", [{}])[0].get("type", "")
                                            if run.get("source") else "",
                                        "execution_id": ex.get("id", ""),
                                    }
                # Fallback: use stoppedAt error
                return {
                    "message": ex.get("stoppedAt", "Unknown error"),
                    "execution_id": ex.get("id", ""),
                }
        except Exception as exc:
            return {"message": f"Failed to fetch error: {exc}"}
        return {"message": "No error executions found"}

    def close(self) -> None:
        """Release resources."""
        if self._client:
            self._client.close()


# ── CLI ─────────────────────────────────────────────────────

def main() -> int:
    modes = {
        "repair": "Run one repair cycle",
        "optimize": "Run one optimisation cycle",
        "revamp-scan": "Scan for revamp candidates",
        "status": "Show AWLM system status",
    }

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("Autonomous Workflow Lifecycle Manager (AWLM)")
        print(f"\nUsage: python {Path(__file__).name} <mode> [args]")
        print("\nModes:")
        for name, desc in modes.items():
            print(f"  {name:15} — {desc}")
        print(f"  {'build <spec>':15} — Build workflow from spec file")
        return 0

    mode = sys.argv[1]

    orch = None
    try:
        orch = LifecycleOrchestrator()

        if mode == "repair":
            orch.run_repair_loop()
        elif mode == "optimize":
            orch.run_optimization_loop()
        elif mode == "revamp-scan":
            orch.run_revamp_scan()
        elif mode == "status":
            orch.run_status()
        elif mode == "build":
            if len(sys.argv) < 3:
                print("Usage: python lifecycle_orchestrator.py build <spec.json>")
                return 1
            orch.run_build_loop(sys.argv[2])
        else:
            print(f"Unknown mode: {mode}")
            print(f"Available: {', '.join(modes.keys())}, build")
            return 1

        return 0

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        return 1
    except Exception as exc:
        print(f"\nError: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if orch is not None:
            orch.close()


if __name__ == "__main__":
    sys.exit(main())

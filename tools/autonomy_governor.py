"""
Autonomy Governor — 5-Tier Governance for the AWLM.

Gates every autonomous action against risk classification and the current
autonomy tier.  Reads safety caps from agent_registry.py.

Tiers:
    1 (Advisory)        — Log only, no actions.
    2 (Supervised)      — Log + backup.  All fixes need approval.
    3 (Semi-autonomous) — Low + medium risk auto.  High/critical need approval.
    4 (Autonomous)      — Low + medium + high auto.  Critical needs approval.
    5 (Near-full)       — All auto except emergency-stop.

Usage:
    from autonomy_governor import AutonomyGovernor, ActionType
    gov = AutonomyGovernor(current_tier=3)
    decision = gov.evaluate(ActionType.UPDATE_NODE_PARAMS, {"workflow_id": "abc"})
    if decision.approved:
        # proceed
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


# ── Risk Levels ─────────────────────────────────────────────
class RiskLevel(Enum):
    LOW = 1       # Read-only, monitoring, logging, backup
    MEDIUM = 2    # Node param changes, retry execution, activate/deactivate
    HIGH = 3      # Structural changes (insert/remove nodes, rewire), new deploys
    CRITICAL = 4  # Deletion, financial WF changes, credential changes


# ── Action Types ────────────────────────────────────────────
class ActionType(Enum):
    # Low risk
    LOG_EVENT = "log_event"
    FETCH_METRICS = "fetch_metrics"
    GENERATE_REPORT = "generate_report"
    EXPORT_BACKUP = "export_backup"

    # Medium risk
    RETRY_EXECUTION = "retry_execution"
    UPDATE_NODE_PARAMS = "update_node_params"
    ACTIVATE_WORKFLOW = "activate_workflow"
    DEACTIVATE_WORKFLOW = "deactivate_workflow"
    DEACTIVATE_REACTIVATE = "deactivate_reactivate"

    # High risk
    INSERT_NODE = "insert_node"
    REMOVE_NODE = "remove_node"
    REWIRE_CONNECTIONS = "rewire_connections"
    DEPLOY_NEW_WORKFLOW = "deploy_new_workflow"
    UPDATE_DEPLOY_SCRIPT = "update_deploy_script"

    # Critical risk
    DELETE_WORKFLOW = "delete_workflow"
    MODIFY_FINANCIAL_WORKFLOW = "modify_financial_workflow"
    MODIFY_CREDENTIAL_REFS = "modify_credential_refs"
    BULK_DEACTIVATE = "bulk_deactivate"


# Action → Risk mapping
RISK_MAP: Dict[ActionType, RiskLevel] = {
    ActionType.LOG_EVENT:               RiskLevel.LOW,
    ActionType.FETCH_METRICS:           RiskLevel.LOW,
    ActionType.GENERATE_REPORT:         RiskLevel.LOW,
    ActionType.EXPORT_BACKUP:           RiskLevel.LOW,

    ActionType.RETRY_EXECUTION:         RiskLevel.MEDIUM,
    ActionType.UPDATE_NODE_PARAMS:      RiskLevel.MEDIUM,
    ActionType.ACTIVATE_WORKFLOW:       RiskLevel.MEDIUM,
    ActionType.DEACTIVATE_WORKFLOW:     RiskLevel.MEDIUM,
    ActionType.DEACTIVATE_REACTIVATE:   RiskLevel.MEDIUM,

    ActionType.INSERT_NODE:             RiskLevel.HIGH,
    ActionType.REMOVE_NODE:             RiskLevel.HIGH,
    ActionType.REWIRE_CONNECTIONS:      RiskLevel.HIGH,
    ActionType.DEPLOY_NEW_WORKFLOW:     RiskLevel.HIGH,
    ActionType.UPDATE_DEPLOY_SCRIPT:    RiskLevel.HIGH,

    ActionType.DELETE_WORKFLOW:          RiskLevel.CRITICAL,
    ActionType.MODIFY_FINANCIAL_WORKFLOW: RiskLevel.CRITICAL,
    ActionType.MODIFY_CREDENTIAL_REFS:  RiskLevel.CRITICAL,
    ActionType.BULK_DEACTIVATE:         RiskLevel.CRITICAL,
}

# Tier N auto-approves actions with risk_level.value <= N
# Exception: CRITICAL always requires approval at tiers < 5
TIER_NAMES = {
    1: "Advisory",
    2: "Supervised",
    3: "Semi-autonomous",
    4: "Autonomous",
    5: "Near-full",
}

# Agents whose workflows are always treated as CRITICAL risk
FINANCIAL_AGENTS = frozenset({"finance", "financial_intel"})

# Workflow names protected from autonomous modification
DEFAULT_PROTECTED = frozenset({"Self-Healing"})


# ── Governance Decision ─────────────────────────────────────
@dataclass(frozen=True)
class GovernanceDecision:
    action_type: ActionType
    risk_level: RiskLevel
    autonomy_tier_required: int
    current_tier: int
    approved: bool
    requires_human: bool
    reason: str
    timestamp: str


# ── Governor ────────────────────────────────────────────────
class AutonomyGovernor:
    """Gate autonomous actions against a configurable autonomy tier."""

    def __init__(
        self,
        current_tier: int = 3,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        if current_tier not in TIER_NAMES:
            raise ValueError(f"Invalid tier {current_tier}; must be 1-5")
        self.current_tier = current_tier
        self._config = config or {}
        self._protected: frozenset[str] = frozenset(
            self._config.get("lifecycle", {}).get("protected_workflows", [])
        ) | DEFAULT_PROTECTED
        self._emergency_stopped = False

    # ── Public API ──────────────────────────────────────────

    def evaluate(
        self,
        action_type: ActionType,
        context: Optional[Dict[str, Any]] = None,
    ) -> GovernanceDecision:
        """Decide whether *action_type* is permitted at the current tier.

        *context* may contain:
            workflow_id, workflow_name, agent_name, amount_zar
        """
        ctx = context or {}
        now = datetime.now(tz=None).isoformat() + "Z"

        if self._emergency_stopped:
            return GovernanceDecision(
                action_type=action_type,
                risk_level=RISK_MAP.get(action_type, RiskLevel.CRITICAL),
                autonomy_tier_required=99,
                current_tier=self.current_tier,
                approved=False,
                requires_human=True,
                reason="Emergency stop is active — all actions blocked",
                timestamp=now,
            )

        risk = self._effective_risk(action_type, ctx)
        tier_required = self._tier_required(risk)
        approved = self.current_tier >= tier_required
        requires_human = not approved

        reason = self._build_reason(action_type, risk, tier_required, approved, ctx)

        return GovernanceDecision(
            action_type=action_type,
            risk_level=risk,
            autonomy_tier_required=tier_required,
            current_tier=self.current_tier,
            approved=approved,
            requires_human=requires_human,
            reason=reason,
            timestamp=now,
        )

    def check_safety_caps(
        self,
        agent_name: str,
        amount_zar: float,
    ) -> bool:
        """Return True if *amount_zar* is within the agent's safety caps."""
        try:
            from agent_registry import get_agent
        except ImportError:
            return True  # Fail-open if registry unavailable

        agent = get_agent(agent_name)
        if agent is None or not agent.safety_caps:
            return True

        auto_approve = agent.safety_caps.get("auto_approve_zar")
        if auto_approve is not None and amount_zar > auto_approve:
            return False
        return True

    def emergency_stop(self) -> None:
        """Block all autonomous actions until manually reset."""
        self._emergency_stopped = True

    def reset_emergency_stop(self) -> None:
        """Re-enable autonomous actions after emergency stop."""
        self._emergency_stopped = False

    @property
    def is_emergency_stopped(self) -> bool:
        return self._emergency_stopped

    @property
    def tier_name(self) -> str:
        return TIER_NAMES[self.current_tier]

    # ── Internal helpers ────────────────────────────────────

    def _effective_risk(
        self,
        action_type: ActionType,
        ctx: Dict[str, Any],
    ) -> RiskLevel:
        """Compute effective risk, elevating for financial agents or protected WFs."""
        base_risk = RISK_MAP.get(action_type, RiskLevel.CRITICAL)

        # Financial agent → always CRITICAL
        agent_name = ctx.get("agent_name", "")
        if agent_name in FINANCIAL_AGENTS:
            return RiskLevel.CRITICAL

        # Protected workflow → always CRITICAL
        wf_name = ctx.get("workflow_name", "")
        if wf_name in self._protected:
            return RiskLevel.CRITICAL

        return base_risk

    @staticmethod
    def _tier_required(risk: RiskLevel) -> int:
        """Minimum tier needed to auto-approve a given risk level.

        LOW    → tier 1 (always auto)
        MEDIUM → tier 3
        HIGH   → tier 4
        CRITICAL → tier 5
        """
        mapping = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 3,
            RiskLevel.HIGH: 4,
            RiskLevel.CRITICAL: 5,
        }
        return mapping.get(risk, 5)

    @staticmethod
    def _build_reason(
        action_type: ActionType,
        risk: RiskLevel,
        tier_required: int,
        approved: bool,
        ctx: Dict[str, Any],
    ) -> str:
        if approved:
            return (
                f"Auto-approved: {action_type.value} ({risk.name} risk) "
                f"at tier {tier_required}"
            )
        parts = [
            f"Denied: {action_type.value} requires tier {tier_required} "
            f"({risk.name} risk), current tier is lower."
        ]
        agent = ctx.get("agent_name")
        if agent and agent in FINANCIAL_AGENTS:
            parts.append("Elevated to CRITICAL: financial agent.")
        wf_name = ctx.get("workflow_name")
        if wf_name and wf_name in DEFAULT_PROTECTED:
            parts.append(f"Elevated to CRITICAL: '{wf_name}' is protected.")
        return " ".join(parts)

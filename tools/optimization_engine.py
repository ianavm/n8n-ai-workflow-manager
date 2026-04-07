"""
Optimization Engine — Identifies and proposes performance improvements.

Extends WorkflowAnalyzer with actionable proposals for:
    - Missing error handling (onError, continueOnFail)
    - Dead nodes (nodes not connected)
    - AI token reduction opportunities
    - Execution order settings

Usage:
    from optimization_engine import OptimizationEngine
    engine = OptimizationEngine(n8n_client)
    proposals = engine.analyze_workflow(workflow_id)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from autonomy_governor import ActionType, RiskLevel


@dataclass(frozen=True)
class OptimizationProposal:
    """A concrete optimization that can be applied to a workflow."""
    proposal_id: str
    workflow_id: str
    optimization_type: str
    description: str
    estimated_improvement: str
    confidence: float
    risk_level: RiskLevel
    action_type: ActionType
    changes: List[Dict[str, Any]] = field(default_factory=list)


class OptimizationEngine:
    """Analyse workflows and propose performance improvements."""

    def __init__(self, n8n_client: Any, config: Optional[Dict[str, Any]] = None) -> None:
        self._client = n8n_client
        self._config = config or {}

    def analyze_workflow(self, workflow_id: str) -> List[OptimizationProposal]:
        """Run all optimization checks against a single workflow."""
        from n8n_api_helpers import safe_get_workflow
        wf = safe_get_workflow(self._client, workflow_id)
        if not wf:
            return []

        proposals: List[OptimizationProposal] = []
        proposals.extend(self._check_error_handling(workflow_id, wf))
        proposals.extend(self._check_dead_nodes(workflow_id, wf))
        proposals.extend(self._check_ai_token_usage(workflow_id, wf))
        proposals.extend(self._check_execution_settings(workflow_id, wf))
        proposals.extend(self._check_missing_always_output(workflow_id, wf))
        return proposals

    def analyze_all_workflows(self) -> Dict[str, List[OptimizationProposal]]:
        """Analyze all active workflows.  Returns {wf_id: [proposals]}."""
        workflows = self._client.list_workflows(active_only=True, use_cache=False)
        results: Dict[str, List[OptimizationProposal]] = {}
        for wf in workflows:
            wf_id = str(wf.get("id", ""))
            props = self.analyze_workflow(wf_id)
            if props:
                results[wf_id] = props
        return results

    # ── Specific checks ─────────────────────────────────────

    def _check_error_handling(
        self, wf_id: str, wf: Dict[str, Any]
    ) -> List[OptimizationProposal]:
        """Find nodes that lack onError configuration."""
        proposals: List[OptimizationProposal] = []
        skip_types = {"n8n-nodes-base.stickyNote", "n8n-nodes-base.noOp"}
        missing: List[str] = []

        for node in wf.get("nodes", []):
            ntype = node.get("type", "")
            if ntype in skip_types or "Trigger" in ntype or "trigger" in ntype:
                continue
            if "onError" not in node:
                missing.append(node["name"])

        if missing:
            proposals.append(OptimizationProposal(
                proposal_id=f"opt-error-{wf_id[:8]}",
                workflow_id=wf_id,
                optimization_type="error_handling",
                description=f"{len(missing)} node(s) lack onError: {', '.join(missing[:5])}",
                estimated_improvement="Prevents full workflow crash on node errors",
                confidence=0.90,
                risk_level=RiskLevel.MEDIUM,
                action_type=ActionType.UPDATE_NODE_PARAMS,
                changes=[{"add_onError": name} for name in missing],
            ))
        return proposals

    def _check_dead_nodes(
        self, wf_id: str, wf: Dict[str, Any]
    ) -> List[OptimizationProposal]:
        """Find nodes that are not connected to any other node."""
        proposals: List[OptimizationProposal] = []
        nodes = wf.get("nodes", [])
        connections = wf.get("connections", {})

        # Gather all nodes that appear in connections (as source or target)
        connected: Set[str] = set()
        for source, outputs in connections.items():
            connected.add(source)
            if not isinstance(outputs, dict):
                continue
            for _branch_key, branches in outputs.items():
                if not isinstance(branches, list):
                    continue
                for branch in branches:
                    if not isinstance(branch, list):
                        continue
                    for conn in branch:
                        if isinstance(conn, dict):
                            connected.add(conn.get("node", ""))

        # Triggers are allowed to have no incoming connections
        dead: List[str] = []
        for node in nodes:
            name = node.get("name", "")
            ntype = node.get("type", "")
            if "Trigger" in ntype or "trigger" in ntype:
                continue
            if "stickyNote" in ntype:
                continue
            if name not in connected:
                dead.append(name)

        if dead:
            proposals.append(OptimizationProposal(
                proposal_id=f"opt-dead-{wf_id[:8]}",
                workflow_id=wf_id,
                optimization_type="dead_nodes",
                description=f"{len(dead)} disconnected node(s): {', '.join(dead[:5])}",
                estimated_improvement="Cleaner workflow, reduced confusion",
                confidence=0.85,
                risk_level=RiskLevel.HIGH,  # Removing nodes is structural
                action_type=ActionType.REMOVE_NODE,
                changes=[{"remove_node": name} for name in dead],
            ))
        return proposals

    def _check_ai_token_usage(
        self, wf_id: str, wf: Dict[str, Any]
    ) -> List[OptimizationProposal]:
        """Find AI nodes that could use a cheaper model."""
        proposals: List[OptimizationProposal] = []
        expensive_models = {"gpt-4o", "claude-3-opus", "claude-opus"}
        cheap_alternatives = {"gpt-4o-mini", "claude-3-haiku", "claude-haiku"}

        candidates: List[Dict[str, str]] = []
        for node in wf.get("nodes", []):
            ntype = node.get("type", "")
            if "openAi" not in ntype and "anthropic" not in ntype and "lmChat" not in ntype:
                continue
            params = node.get("parameters", {})
            model = params.get("model", params.get("modelId", ""))
            if any(exp in model.lower() for exp in expensive_models):
                candidates.append({"node": node["name"], "current_model": model})

        if candidates:
            proposals.append(OptimizationProposal(
                proposal_id=f"opt-ai-{wf_id[:8]}",
                workflow_id=wf_id,
                optimization_type="ai_token_reduction",
                description=(
                    f"{len(candidates)} node(s) use expensive models: "
                    f"{', '.join(c['node'] for c in candidates[:3])}"
                ),
                estimated_improvement="50-70% cost reduction per AI call",
                confidence=0.60,  # Model downgrade needs human review
                risk_level=RiskLevel.MEDIUM,
                action_type=ActionType.UPDATE_NODE_PARAMS,
                changes=candidates,
            ))
        return proposals

    def _check_execution_settings(
        self, wf_id: str, wf: Dict[str, Any]
    ) -> List[OptimizationProposal]:
        """Check workflow-level settings."""
        proposals: List[OptimizationProposal] = []
        settings = wf.get("settings", {})

        if settings.get("executionOrder") != "v1":
            proposals.append(OptimizationProposal(
                proposal_id=f"opt-exec-{wf_id[:8]}",
                workflow_id=wf_id,
                optimization_type="execution_settings",
                description="Missing executionOrder='v1' setting",
                estimated_improvement="Predictable node execution order",
                confidence=0.95,
                risk_level=RiskLevel.LOW,
                action_type=ActionType.UPDATE_NODE_PARAMS,
                changes=[{"set_executionOrder": "v1"}],
            ))
        return proposals

    def _check_missing_always_output(
        self, wf_id: str, wf: Dict[str, Any]
    ) -> List[OptimizationProposal]:
        """Find API nodes without alwaysOutputData."""
        proposals: List[OptimizationProposal] = []
        api_types = {
            "n8n-nodes-base.httpRequest",
            "n8n-nodes-base.googleSheets",
            "n8n-nodes-base.airtable",
        }
        missing: List[str] = []
        for node in wf.get("nodes", []):
            if node.get("type", "") in api_types and not node.get("alwaysOutputData"):
                missing.append(node["name"])

        if missing:
            proposals.append(OptimizationProposal(
                proposal_id=f"opt-output-{wf_id[:8]}",
                workflow_id=wf_id,
                optimization_type="always_output_data",
                description=f"{len(missing)} API node(s) without alwaysOutputData",
                estimated_improvement="Prevents downstream nodes from hanging on empty responses",
                confidence=0.85,
                risk_level=RiskLevel.MEDIUM,
                action_type=ActionType.UPDATE_NODE_PARAMS,
                changes=[{"add_alwaysOutputData": name} for name in missing],
            ))
        return proposals

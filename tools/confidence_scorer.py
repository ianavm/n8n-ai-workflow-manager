"""
Confidence Scorer — Multi-factor scoring for autonomous action decisions.

Computes a composite confidence score (0.0–1.0) for a proposed repair or
optimisation, based on:
    1. Pattern match quality  (exact regex > fuzzy > novel)
    2. Historical success rate of the repair pattern
    3. Workflow risk profile   (inverse: low-risk WF → high score)
    4. Change magnitude        (inverse: small change → high score)
    5. Sandbox test results    (pass/fail/partial)

Score bands:
    0.0–0.3  ESCALATE   — Novel error, no pattern, or critical workflow.
    0.3–0.6  PROPOSE    — Fix proposed, wait for human review.
    0.6–0.8  STAGE      — Apply in staging, auto-promote after 1 h if OK.
    0.8–1.0  APPLY      — Apply directly, log for audit.

Usage:
    from confidence_scorer import ConfidenceScorer
    scorer = ConfidenceScorer()
    result = scorer.score(
        workflow_id="abc",
        proposed_fix={"changes": [...]},
        pattern_confidence=0.90,
        historical_success=0.85,
        agent_name="growth_organic",
        change_count=2,
        test_passed=True,
    )
    print(result.action)  # "apply"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


# Agents whose workflows get a risk penalty (lower confidence)
_FINANCIAL_AGENTS = frozenset({"finance", "financial_intel"})
_SENSITIVE_AGENTS = frozenset({"finance", "financial_intel", "growth_paid", "compliance_auditor"})

# Score → action mapping thresholds
_THRESHOLD_APPLY = 0.80
_THRESHOLD_STAGE = 0.60
_THRESHOLD_PROPOSE = 0.30


@dataclass(frozen=True)
class ConfidenceScore:
    """Immutable result of a confidence evaluation."""
    overall: float
    pattern_match: float
    historical_success: float
    risk_profile: float
    change_magnitude: float
    test_quality: float
    action: str          # "escalate" | "propose" | "stage" | "apply"


class ConfidenceScorer:
    """Compute multi-factor confidence scores for autonomous actions."""

    def __init__(
        self,
        threshold_apply: float = _THRESHOLD_APPLY,
        threshold_stage: float = _THRESHOLD_STAGE,
        threshold_propose: float = _THRESHOLD_PROPOSE,
    ) -> None:
        self._t_apply = threshold_apply
        self._t_stage = threshold_stage
        self._t_propose = threshold_propose

    def score(
        self,
        workflow_id: str,
        proposed_fix: Optional[Dict[str, Any]] = None,
        pattern_confidence: Optional[float] = None,
        historical_success: Optional[float] = None,
        agent_name: str = "",
        change_count: int = 1,
        test_passed: Optional[bool] = None,
    ) -> ConfidenceScore:
        """Compute a composite confidence score.

        Args:
            workflow_id: Target workflow.
            proposed_fix: Dict describing the fix (optional metadata).
            pattern_confidence: The repair pattern's built-in confidence (0–1).
                None if no pattern matched (novel error).
            historical_success: Observed success rate from RepairPatternStore.
                None if pattern has never been applied.
            agent_name: Owning agent name from agent_registry.
            change_count: Number of node/connection changes in the fix.
            test_passed: Sandbox validation result.  None = not tested.
        """
        pm = self._score_pattern_match(pattern_confidence)
        hs = self._score_historical(historical_success)
        rp = self._score_risk_profile(agent_name)
        cm = self._score_change_magnitude(change_count)
        tq = self._score_test_quality(test_passed)

        # Weighted composite
        weights = {
            "pattern_match": 0.30,
            "historical_success": 0.25,
            "risk_profile": 0.20,
            "change_magnitude": 0.10,
            "test_quality": 0.15,
        }
        overall = (
            pm * weights["pattern_match"]
            + hs * weights["historical_success"]
            + rp * weights["risk_profile"]
            + cm * weights["change_magnitude"]
            + tq * weights["test_quality"]
        )
        overall = round(min(max(overall, 0.0), 1.0), 3)

        action = self._action_from_score(overall)

        return ConfidenceScore(
            overall=overall,
            pattern_match=round(pm, 3),
            historical_success=round(hs, 3),
            risk_profile=round(rp, 3),
            change_magnitude=round(cm, 3),
            test_quality=round(tq, 3),
            action=action,
        )

    # ── Dimension scorers ───────────────────────────────────

    @staticmethod
    def _score_pattern_match(pattern_confidence: Optional[float]) -> float:
        """Score based on how well the error matched a known pattern."""
        if pattern_confidence is None:
            return 0.15  # Novel error — very low confidence
        return max(0.0, min(1.0, pattern_confidence))

    @staticmethod
    def _score_historical(historical_success: Optional[float]) -> float:
        """Score from the pattern's historical success rate."""
        if historical_success is None:
            return 0.5  # Never applied — neutral
        return max(0.0, min(1.0, historical_success))

    @staticmethod
    def _score_risk_profile(agent_name: str) -> float:
        """Inverse risk: low-risk agent → high score."""
        if agent_name in _FINANCIAL_AGENTS:
            return 0.2   # Financial workflows are inherently risky
        if agent_name in _SENSITIVE_AGENTS:
            return 0.4
        if not agent_name:
            return 0.6   # Unknown agent — moderate
        return 0.9       # Standard workflow — low risk

    @staticmethod
    def _score_change_magnitude(change_count: int) -> float:
        """Inverse: fewer changes → higher confidence."""
        if change_count <= 0:
            return 1.0
        if change_count == 1:
            return 0.95
        if change_count <= 3:
            return 0.80
        if change_count <= 5:
            return 0.60
        return 0.30  # Large change — low confidence

    @staticmethod
    def _score_test_quality(test_passed: Optional[bool]) -> float:
        """Score from sandbox validation results."""
        if test_passed is None:
            return 0.5  # Not tested — neutral
        return 1.0 if test_passed else 0.1

    def _action_from_score(self, score: float) -> str:
        if score >= self._t_apply:
            return "apply"
        if score >= self._t_stage:
            return "stage"
        if score >= self._t_propose:
            return "propose"
        return "escalate"

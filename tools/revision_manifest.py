"""
Revision manifest — finding schema, active-dept filter, classifier.

Consolidates findings from the four Full-Revision audits (health, drift,
quality, SOP) into a single JSONL manifest with a unified schema, then
classifies each finding through ConfidenceScorer and gates through
AutonomyGovernor using the current tier from config.json.

Bands (from confidence_scorer):
    APPLY    — auto-apply if governance allows at current tier
    STAGE    — write patch + escalation record, do not apply
    PROPOSE  — summary-only, no write
    ESCALATE — urgent escalation record + notify
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional

from autonomy_governor import ActionType, AutonomyGovernor, RiskLevel
from confidence_scorer import ConfidenceScorer

log = logging.getLogger(__name__)


# ── Active-dept filter ──────────────────────────────────────────────────

INACTIVE_DEPTS: frozenset[str] = frozenset({
    "_archive",
    "demos",
    "demo-workflows",
    "whatsapp-agent",
    "whatsapp-v2",
    "heygen-video",
    "payfast-dept",
})


def is_active_dept(dept_name: str) -> bool:
    """True if *dept_name* is a production/active department folder."""
    return dept_name not in INACTIVE_DEPTS and not dept_name.startswith(("_", "."))


def iter_active_dept_paths(workflows_root: Path) -> Iterable[Path]:
    """Yield Paths for each active department folder under *workflows_root*."""
    if not workflows_root.is_dir():
        return
    for child in sorted(workflows_root.iterdir()):
        if child.is_dir() and is_active_dept(child.name):
            yield child


# ── Finding schema ──────────────────────────────────────────────────────

class Phase(str, Enum):
    HEALTH = "health"
    DRIFT = "drift"
    QUALITY = "quality"
    SOP = "sop"


class Band(str, Enum):
    APPLY = "apply"
    STAGE = "stage"
    PROPOSE = "propose"
    ESCALATE = "escalate"


_BAND_ORDER = {Band.ESCALATE: 0, Band.PROPOSE: 1, Band.STAGE: 2, Band.APPLY: 3}


@dataclass(frozen=True)
class Finding:
    """A single revision finding. Immutable — use replace() to modify."""
    id: str
    phase: Phase
    dept: str
    workflow_id: str      # n8n workflow ID, or "" for script/doc findings
    file: str              # relative path to the file this finding concerns
    risk: RiskLevel
    action_type: ActionType
    summary: str           # one-line human summary
    detail: str = ""       # full detail / diff / evidence
    fix_patch: Optional[dict[str, Any]] = None  # structured patch data
    agent_owner: str = ""
    confidence_hint: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "phase": self.phase.value,
            "dept": self.dept,
            "workflow_id": self.workflow_id,
            "file": self.file,
            "risk": self.risk.name,
            "action_type": self.action_type.value,
            "summary": self.summary,
            "detail": self.detail,
            "fix_patch": self.fix_patch,
            "agent_owner": self.agent_owner,
            "confidence_hint": self.confidence_hint,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Finding":
        return cls(
            id=d["id"],
            phase=Phase(d["phase"]),
            dept=d["dept"],
            workflow_id=d.get("workflow_id", ""),
            file=d.get("file", ""),
            risk=RiskLevel[d["risk"]],
            action_type=ActionType(d["action_type"]),
            summary=d["summary"],
            detail=d.get("detail", ""),
            fix_patch=d.get("fix_patch"),
            agent_owner=d.get("agent_owner", ""),
            confidence_hint=d.get("confidence_hint", 0.5),
        )


@dataclass(frozen=True)
class ClassifiedFinding:
    """A finding paired with its classification + governance decision."""
    finding: Finding
    band: Band
    overall_confidence: float
    governance_approved: bool
    governance_reason: str
    effective_risk: RiskLevel
    classified_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.finding.to_dict(),
            "band": self.band.value,
            "overall_confidence": self.overall_confidence,
            "governance_approved": self.governance_approved,
            "governance_reason": self.governance_reason,
            "effective_risk": self.effective_risk.name,
            "classified_at": self.classified_at,
        }


# ── Manifest IO ─────────────────────────────────────────────────────────

def write_jsonl(path: Path, items: Iterable[Finding]) -> int:
    """Write findings to *path* as JSONL. Returns count written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> list[Finding]:
    """Read findings from *path* (JSONL)."""
    if not path.exists():
        return []
    out: list[Finding] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(Finding.from_dict(json.loads(line)))
    return out


def consolidate(findings_dir: Path) -> list[Finding]:
    """Merge {health,drift,quality,sop}.jsonl into one ordered list."""
    all_findings: list[Finding] = []
    for phase in Phase:
        all_findings.extend(read_jsonl(findings_dir / f"{phase.value}.jsonl"))
    return all_findings


# ── Classifier ──────────────────────────────────────────────────────────

class RevisionClassifier:
    """Classify Findings into bands via confidence + governance gates."""

    def __init__(
        self,
        governor: AutonomyGovernor,
        scorer: Optional[ConfidenceScorer] = None,
    ) -> None:
        self._governor = governor
        self._scorer = scorer or ConfidenceScorer()

    def classify(self, finding: Finding) -> ClassifiedFinding:
        """Classify a single finding."""
        score = self._scorer.score(
            workflow_id=finding.workflow_id or finding.file,
            proposed_fix=finding.fix_patch,
            pattern_confidence=finding.confidence_hint,
            historical_success=None,
            agent_name=finding.agent_owner,
            change_count=_change_count(finding.fix_patch),
            test_passed=None,
        )

        decision = self._governor.evaluate(
            finding.action_type,
            context={
                "workflow_id": finding.workflow_id,
                "workflow_name": _workflow_name(finding),
                "agent_name": finding.agent_owner,
            },
        )

        band = _band_from_scorer_action(score.action)
        # LOW risk + governor approves → safe to APPLY regardless of scorer's
        # novelty/test penalties. SOP writes and logging have no live-mutation
        # blast radius, so the scorer's "never-been-tested" penalty shouldn't
        # block them.
        if decision.approved and decision.risk_level == RiskLevel.LOW and score.overall >= 0.60:
            band = Band.APPLY
        # Gate downgrade: if governance blocks, downshift band to STAGE or PROPOSE.
        if not decision.approved and band == Band.APPLY:
            band = Band.STAGE
        if decision.risk_level == RiskLevel.CRITICAL and band in (Band.APPLY, Band.STAGE):
            band = Band.PROPOSE

        return ClassifiedFinding(
            finding=finding,
            band=band,
            overall_confidence=score.overall,
            governance_approved=decision.approved,
            governance_reason=decision.reason,
            effective_risk=decision.risk_level,
            classified_at=datetime.now(timezone.utc).isoformat(),
        )

    def classify_all(self, findings: Iterable[Finding]) -> list[ClassifiedFinding]:
        return [self.classify(f) for f in findings]


def _change_count(patch: Optional[dict[str, Any]]) -> int:
    """Estimate change count from a patch dict."""
    if not patch:
        return 1
    changes = patch.get("changes")
    if isinstance(changes, list):
        return max(1, len(changes))
    return 1


def _workflow_name(finding: Finding) -> str:
    """Derive a workflow name hint for governance context."""
    if finding.fix_patch and isinstance(finding.fix_patch, dict):
        name = finding.fix_patch.get("workflow_name")
        if isinstance(name, str):
            return name
    return ""


def _band_from_scorer_action(action: str) -> Band:
    mapping = {
        "apply": Band.APPLY,
        "stage": Band.STAGE,
        "propose": Band.PROPOSE,
        "escalate": Band.ESCALATE,
    }
    return mapping.get(action, Band.PROPOSE)


# ── Summary helpers for the orchestrator report ─────────────────────────

def summarize_by_band(classified: list[ClassifiedFinding]) -> dict[str, int]:
    """Count classified findings by band name."""
    counts: dict[str, int] = {b.value: 0 for b in Band}
    for c in classified:
        counts[c.band.value] += 1
    return counts


def summarize_by_phase(classified: list[ClassifiedFinding]) -> dict[str, int]:
    counts: dict[str, int] = {p.value: 0 for p in Phase}
    for c in classified:
        counts[c.finding.phase.value] += 1
    return counts


def sort_by_urgency(classified: list[ClassifiedFinding]) -> list[ClassifiedFinding]:
    """Sort most-urgent first: ESCALATE > PROPOSE > STAGE > APPLY, then by risk desc."""
    return sorted(
        classified,
        key=lambda c: (_BAND_ORDER[c.band], -c.effective_risk.value),
    )

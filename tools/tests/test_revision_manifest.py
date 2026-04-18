"""Tests for revision_manifest classifier, schema, and active-dept filter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonomy_governor import ActionType, AutonomyGovernor, RiskLevel
from confidence_scorer import ConfidenceScorer
from revision_manifest import (
    Band,
    Finding,
    INACTIVE_DEPTS,
    Phase,
    RevisionClassifier,
    consolidate,
    is_active_dept,
    iter_active_dept_paths,
    read_jsonl,
    sort_by_urgency,
    summarize_by_band,
    summarize_by_phase,
    write_jsonl,
)


# ── Active-dept filter ──────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.parametrize("dept", [
    "accounting-dept", "ads-dept", "lead-scraper",
    "linkedin-dept", "marketing-dept", "re-operations",
])
def test_active_depts_accepted(dept: str) -> None:
    assert is_active_dept(dept)


@pytest.mark.unit
@pytest.mark.parametrize("dept", sorted(INACTIVE_DEPTS))
def test_inactive_depts_rejected(dept: str) -> None:
    assert not is_active_dept(dept)


@pytest.mark.unit
@pytest.mark.parametrize("dept", ["_internal", ".hidden"])
def test_underscore_or_dot_prefix_rejected(dept: str) -> None:
    assert not is_active_dept(dept)


@pytest.mark.unit
def test_iter_active_dept_paths(tmp_path: Path) -> None:
    (tmp_path / "accounting-dept").mkdir()
    (tmp_path / "_archive").mkdir()
    (tmp_path / "demos").mkdir()
    (tmp_path / "whatsapp-agent").mkdir()
    (tmp_path / "lead-scraper").mkdir()
    (tmp_path / "README.md").write_text("not a dir")
    result = [p.name for p in iter_active_dept_paths(tmp_path)]
    assert sorted(result) == ["accounting-dept", "lead-scraper"]


@pytest.mark.unit
def test_iter_active_dept_paths_missing_root(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    assert list(iter_active_dept_paths(missing)) == []


# ── Finding schema ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_finding_roundtrip() -> None:
    f = Finding(
        id="T-1",
        phase=Phase.SOP,
        dept="lead-scraper",
        workflow_id="abc",
        file="workflows/lead-scraper/x.json",
        risk=RiskLevel.LOW,
        action_type=ActionType.GENERATE_REPORT,
        summary="missing SOP",
        detail="stub",
        fix_patch={"kind": "write_file", "target": "x.md", "content": "# stub"},
        agent_owner="growth_organic",
        confidence_hint=0.95,
    )
    d = f.to_dict()
    f2 = Finding.from_dict(d)
    assert f2 == f


@pytest.mark.unit
def test_jsonl_roundtrip(tmp_path: Path) -> None:
    findings = [
        _mk_finding("a", Phase.HEALTH, RiskLevel.LOW, ActionType.LOG_EVENT),
        _mk_finding("b", Phase.QUALITY, RiskLevel.MEDIUM, ActionType.UPDATE_NODE_PARAMS),
    ]
    path = tmp_path / "x.jsonl"
    count = write_jsonl(path, findings)
    assert count == 2
    loaded = read_jsonl(path)
    assert loaded == findings


@pytest.mark.unit
def test_consolidate_merges_all_phases(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "health.jsonl",
                [_mk_finding("h1", Phase.HEALTH, RiskLevel.LOW, ActionType.LOG_EVENT)])
    write_jsonl(tmp_path / "drift.jsonl",
                [_mk_finding("d1", Phase.DRIFT, RiskLevel.MEDIUM,
                             ActionType.UPDATE_DEPLOY_SCRIPT)])
    write_jsonl(tmp_path / "quality.jsonl",
                [_mk_finding("q1", Phase.QUALITY, RiskLevel.HIGH,
                             ActionType.UPDATE_DEPLOY_SCRIPT)])
    write_jsonl(tmp_path / "sop.jsonl",
                [_mk_finding("s1", Phase.SOP, RiskLevel.LOW, ActionType.GENERATE_REPORT)])
    merged = consolidate(tmp_path)
    assert [f.id for f in merged] == ["h1", "d1", "q1", "s1"]


@pytest.mark.unit
def test_consolidate_missing_files_returns_empty(tmp_path: Path) -> None:
    assert consolidate(tmp_path) == []


# ── Classifier ──────────────────────────────────────────────────────────

@pytest.fixture
def tier3_classifier() -> RevisionClassifier:
    return RevisionClassifier(AutonomyGovernor(current_tier=3), ConfidenceScorer())


@pytest.fixture
def tier1_classifier() -> RevisionClassifier:
    return RevisionClassifier(AutonomyGovernor(current_tier=1), ConfidenceScorer())


@pytest.mark.unit
def test_high_confidence_low_risk_goes_apply_at_tier3(tier3_classifier: RevisionClassifier) -> None:
    f = _mk_finding("ok", Phase.SOP, RiskLevel.LOW, ActionType.GENERATE_REPORT,
                    confidence_hint=0.98)
    c = tier3_classifier.classify(f)
    assert c.band == Band.APPLY
    assert c.governance_approved is True


@pytest.mark.unit
def test_high_risk_downgraded_to_stage_at_tier3(tier3_classifier: RevisionClassifier) -> None:
    f = _mk_finding("risky", Phase.DRIFT, RiskLevel.HIGH,
                    ActionType.UPDATE_DEPLOY_SCRIPT, confidence_hint=0.99)
    c = tier3_classifier.classify(f)
    assert c.band == Band.STAGE
    assert c.governance_approved is False


@pytest.mark.unit
def test_critical_risk_goes_propose(tier3_classifier: RevisionClassifier) -> None:
    f = _mk_finding("crit", Phase.QUALITY, RiskLevel.CRITICAL,
                    ActionType.DELETE_WORKFLOW, confidence_hint=0.99)
    c = tier3_classifier.classify(f)
    assert c.band == Band.PROPOSE


@pytest.mark.unit
def test_financial_agent_elevates_to_critical(tier3_classifier: RevisionClassifier) -> None:
    f = _mk_finding("fin", Phase.QUALITY, RiskLevel.MEDIUM,
                    ActionType.UPDATE_NODE_PARAMS,
                    confidence_hint=0.99, agent_owner="finance")
    c = tier3_classifier.classify(f)
    assert c.effective_risk == RiskLevel.CRITICAL
    assert c.band == Band.PROPOSE


@pytest.mark.unit
def test_tier1_blocks_medium_risk(tier1_classifier: RevisionClassifier) -> None:
    f = _mk_finding("med", Phase.HEALTH, RiskLevel.MEDIUM,
                    ActionType.UPDATE_NODE_PARAMS, confidence_hint=0.99)
    c = tier1_classifier.classify(f)
    assert c.governance_approved is False
    assert c.band in (Band.STAGE, Band.PROPOSE)


@pytest.mark.unit
def test_classify_all_preserves_order(tier3_classifier: RevisionClassifier) -> None:
    findings = [
        _mk_finding(f"id-{i}", Phase.SOP, RiskLevel.LOW, ActionType.GENERATE_REPORT)
        for i in range(5)
    ]
    out = tier3_classifier.classify_all(findings)
    assert [c.finding.id for c in out] == [f.id for f in findings]


# ── Summaries / sorting ─────────────────────────────────────────────────

@pytest.mark.unit
def test_summarize_by_band_counts(tier3_classifier: RevisionClassifier) -> None:
    findings = [
        _mk_finding("a", Phase.SOP, RiskLevel.LOW, ActionType.GENERATE_REPORT,
                    confidence_hint=0.95),
        _mk_finding("b", Phase.DRIFT, RiskLevel.HIGH,
                    ActionType.UPDATE_DEPLOY_SCRIPT, confidence_hint=0.95),
        _mk_finding("c", Phase.QUALITY, RiskLevel.CRITICAL,
                    ActionType.DELETE_WORKFLOW, confidence_hint=0.95),
    ]
    classified = tier3_classifier.classify_all(findings)
    counts = summarize_by_band(classified)
    assert counts["apply"] == 1
    assert counts["stage"] == 1
    assert counts["propose"] == 1


@pytest.mark.unit
def test_summarize_by_phase(tier3_classifier: RevisionClassifier) -> None:
    findings = [
        _mk_finding("h", Phase.HEALTH, RiskLevel.LOW, ActionType.LOG_EVENT),
        _mk_finding("h2", Phase.HEALTH, RiskLevel.LOW, ActionType.LOG_EVENT),
        _mk_finding("s", Phase.SOP, RiskLevel.LOW, ActionType.GENERATE_REPORT),
    ]
    classified = tier3_classifier.classify_all(findings)
    counts = summarize_by_phase(classified)
    assert counts["health"] == 2
    assert counts["sop"] == 1
    assert counts["quality"] == 0


@pytest.mark.unit
def test_sort_by_urgency_escalate_first(tier3_classifier: RevisionClassifier) -> None:
    f_apply = _mk_finding("apply", Phase.SOP, RiskLevel.LOW,
                          ActionType.GENERATE_REPORT, confidence_hint=0.99)
    f_propose = _mk_finding("critical", Phase.QUALITY, RiskLevel.CRITICAL,
                            ActionType.DELETE_WORKFLOW, confidence_hint=0.99)
    classified = tier3_classifier.classify_all([f_apply, f_propose])
    ordered = sort_by_urgency(classified)
    assert ordered[0].finding.id == "critical"
    assert ordered[-1].finding.id == "apply"


# ── Helpers ─────────────────────────────────────────────────────────────

def _mk_finding(
    id_: str,
    phase: Phase,
    risk: RiskLevel,
    action_type: ActionType,
    *,
    confidence_hint: float = 0.5,
    agent_owner: str = "",
) -> Finding:
    return Finding(
        id=id_,
        phase=phase,
        dept="test",
        workflow_id=f"wf-{id_}",
        file=f"file-{id_}.json",
        risk=risk,
        action_type=action_type,
        summary=f"summary for {id_}",
        detail="",
        fix_patch=None,
        agent_owner=agent_owner,
        confidence_hint=confidence_hint,
    )

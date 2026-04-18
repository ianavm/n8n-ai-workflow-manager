"""
Full Revision orchestrator — Phases A-F.

Composes the four audit tools (health, drift, quality, SOP) and routes findings
through the confidence scorer + autonomy governor before applying.

Usage:
    python tools/run_full_revision.py --dry-run                # all active depts, no writes
    python tools/run_full_revision.py --dept lead-scraper      # single dept dry-run
    python tools/run_full_revision.py --apply                  # actually write fixes
    python tools/run_full_revision.py --apply --dept lead-scraper

Safety: dry-run is the default. You must pass `--apply` to make changes.

Outputs:
    .tmp/revision/<YYYY-MM-DD>/baseline/        Pre-revision snapshot
    .tmp/revision/<YYYY-MM-DD>/findings/*.jsonl  Per-phase findings
    .tmp/revision/<YYYY-MM-DD>/manifest.jsonl    Classified findings
    reports/revision_<YYYY-MM-DD>.md             Consolidated report
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Ensure sibling tools are importable
sys.path.insert(0, str(Path(__file__).parent))

from autonomy_governor import ActionType, AutonomyGovernor, RiskLevel
from confidence_scorer import ConfidenceScorer
from revision_manifest import (
    Band,
    ClassifiedFinding,
    Finding,
    Phase,
    RevisionClassifier,
    consolidate,
    is_active_dept,
    iter_active_dept_paths,
    sort_by_urgency,
    summarize_by_band,
    summarize_by_phase,
    write_jsonl,
)
from revision_sop_generator import generate_sop_from_file, sop_filename

log = logging.getLogger("run_full_revision")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s")


PROJECT_ROOT = Path(__file__).parent.parent
WORKFLOWS_DIR = PROJECT_ROOT / "workflows"
TOOLS_DIR = PROJECT_ROOT / "tools"
REPORTS_DIR = PROJECT_ROOT / "reports"
CONFIG_PATH = PROJECT_ROOT / "config.json"


# ── Severity mapping for audit_deploy_scripts output ────────────────────

_AUDIT_SEVERITY_TO_RISK: dict[str, RiskLevel] = {
    "CRITICAL": RiskLevel.HIGH,
    "HIGH": RiskLevel.MEDIUM,
    "MEDIUM": RiskLevel.LOW,
    "INFO": RiskLevel.LOW,
}


def _risk_for_severity(sev: str) -> RiskLevel:
    return _AUDIT_SEVERITY_TO_RISK.get(sev.upper(), RiskLevel.LOW)


# ── Config ──────────────────────────────────────────────────────────────

def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def autonomy_tier(config: dict[str, Any]) -> int:
    return int(config.get("lifecycle", {}).get("autonomy_tier", 3))


# ── Options ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RevisionOptions:
    apply: bool
    dept_filter: Optional[str]
    skip_live_health: bool
    report_dir: Path
    revision_dir: Path


def parse_args(argv: Optional[list[str]] = None) -> RevisionOptions:
    parser = argparse.ArgumentParser(
        description="Run a full revision of the AVM n8n workflow estate.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write fixes. Default is dry-run (no writes).",
    )
    parser.add_argument(
        "--dept",
        default=None,
        help="Limit to a single department (e.g., lead-scraper). Default: all active.",
    )
    parser.add_argument(
        "--skip-live-health",
        action="store_true",
        help="Skip Phase B1 (requires live n8n API) — useful in offline environments.",
    )
    args = parser.parse_args(argv)

    date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return RevisionOptions(
        apply=args.apply,
        dept_filter=args.dept,
        skip_live_health=args.skip_live_health,
        report_dir=REPORTS_DIR,
        revision_dir=PROJECT_ROOT / ".tmp" / "revision" / date_stamp,
    )


# ── Runner ──────────────────────────────────────────────────────────────

class FullRevisionRunner:
    """Orchestrator for the Full Revision workflow."""

    def __init__(self, options: RevisionOptions) -> None:
        self.options = options
        self.config = load_config()
        self.tier = autonomy_tier(self.config)
        self.governor = AutonomyGovernor(current_tier=self.tier, config=self.config)
        self.scorer = ConfidenceScorer()
        self.classifier = RevisionClassifier(self.governor, self.scorer)

        self.revision_dir = options.revision_dir
        self.baseline_dir = self.revision_dir / "baseline"
        self.findings_dir = self.revision_dir / "findings"
        self.revision_dir.mkdir(parents=True, exist_ok=True)
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.findings_dir.mkdir(parents=True, exist_ok=True)

    # ── Entry ───────────────────────────────────────────────────────────

    def run(self) -> int:
        mode = "APPLY" if self.options.apply else "DRY-RUN"
        dept_info = self.options.dept_filter or "all active"
        log.info("Full Revision starting — mode=%s, dept=%s, tier=%d",
                 mode, dept_info, self.tier)

        # Phase A: baseline snapshot (always)
        self.phase_a_baseline()

        # Phase B: four audits
        health_findings = self.phase_b1_health()
        drift_findings = self.phase_b2_drift()
        quality_findings = self.phase_b3_quality()
        sop_findings = self.phase_b4_sop()

        write_jsonl(self.findings_dir / "health.jsonl", health_findings)
        write_jsonl(self.findings_dir / "drift.jsonl", drift_findings)
        write_jsonl(self.findings_dir / "quality.jsonl", quality_findings)
        write_jsonl(self.findings_dir / "sop.jsonl", sop_findings)

        # Phase C: consolidate + classify
        all_findings = consolidate(self.findings_dir)
        classified = self.classifier.classify_all(all_findings)
        self._write_manifest(classified)

        # Phase D: apply per band
        applied = self.phase_d_apply(classified) if self.options.apply else []

        # Phase E: verification (only if any applies happened)
        verified = self.phase_e_verify(applied) if applied else []

        # Phase F: report
        report_path = self.phase_f_report(classified, applied, verified)
        log.info("Full Revision complete. Report: %s", report_path)

        # Exit non-zero if any ESCALATE findings
        escalate_count = sum(1 for c in classified if c.band == Band.ESCALATE)
        return 1 if escalate_count else 0

    # ── Phase A: baseline ───────────────────────────────────────────────

    def phase_a_baseline(self) -> None:
        log.info("[A] Baseline snapshot → %s", self.baseline_dir)
        # Copy current deploy scripts + SOPs for rollback reference
        scripts_snap = self.baseline_dir / "tools"
        sops_snap = self.baseline_dir / "workflows"
        scripts_snap.mkdir(parents=True, exist_ok=True)
        sops_snap.mkdir(parents=True, exist_ok=True)

        for deploy_script in TOOLS_DIR.glob("deploy_*.py"):
            shutil.copy2(deploy_script, scripts_snap / deploy_script.name)

        for md_file in WORKFLOWS_DIR.rglob("*.md"):
            if any(part in {"_archive", "demos", "demo-workflows"} for part in md_file.parts):
                continue
            rel = md_file.relative_to(WORKFLOWS_DIR)
            dest = sops_snap / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md_file, dest)

        log.info("[A] Baseline complete: %d scripts, %d SOPs",
                 len(list(scripts_snap.glob("deploy_*.py"))),
                 len(list(sops_snap.rglob("*.md"))))

    # ── Phase B1: health (live) ─────────────────────────────────────────

    def phase_b1_health(self) -> list[Finding]:
        if self.options.skip_live_health:
            log.info("[B1] Skipping live health audit (flag set)")
            return []

        # Import lazily so offline envs without httpx + .env can still dry-run sop/drift.
        try:
            from dotenv import load_dotenv
            load_dotenv(str(PROJECT_ROOT / ".env"))
            import os
            from n8n_client import N8nClient
            base_url = os.getenv("N8N_BASE_URL")
            api_key = os.getenv("N8N_API_KEY")
            if not base_url or not api_key:
                log.warning("[B1] N8N_BASE_URL or N8N_API_KEY missing — skipping live health")
                return []
        except Exception as exc:  # pragma: no cover
            log.warning("[B1] Could not initialize n8n client: %s", exc)
            return []

        log.info("[B1] Live health audit …")
        findings: list[Finding] = []
        try:
            with N8nClient(base_url, api_key) as client:
                live = client.list_workflows(active_only=True, use_cache=False)
                log.info("[B1]   %d active workflows live", len(live))
                for wf in live:
                    wf_id = wf.get("id", "")
                    name = wf.get("name", "<unnamed>")
                    dept = self._dept_for_workflow_name(name)
                    if dept and not is_active_dept(dept):
                        continue

                    executions = client.list_executions(workflow_id=wf_id, limit=20)
                    errors = [e for e in executions if e.get("status") == "error"]
                    total = len(executions)
                    if total == 0:
                        findings.append(self._new_finding(
                            id=f"H-{wf_id}-stale",
                            phase=Phase.HEALTH,
                            dept=dept or "unknown",
                            workflow_id=wf_id,
                            file="",
                            risk=RiskLevel.LOW,
                            action_type=ActionType.LOG_EVENT,
                            summary=f"No executions recently on active workflow: {name}",
                            detail="Workflow is active but has zero recent executions. "
                                   "Either trigger is misconfigured, or workflow is dormant.",
                            confidence_hint=0.9,
                        ))
                        continue
                    fail_rate = len(errors) / total
                    if fail_rate >= 0.5:
                        findings.append(self._new_finding(
                            id=f"H-{wf_id}-fail",
                            phase=Phase.HEALTH,
                            dept=dept or "unknown",
                            workflow_id=wf_id,
                            file="",
                            risk=RiskLevel.MEDIUM,
                            action_type=ActionType.RETRY_EXECUTION,
                            summary=f"High failure rate ({fail_rate:.0%}) on {name}",
                            detail=f"{len(errors)}/{total} recent executions failed.",
                            confidence_hint=0.7,
                        ))
        except Exception as exc:
            log.warning("[B1] Live health audit failed: %s", exc)

        log.info("[B1] %d health findings", len(findings))
        return findings

    # ── Phase B2: drift ─────────────────────────────────────────────────

    def phase_b2_drift(self) -> list[Finding]:
        log.info("[B2] Drift audit — local JSON vs deploy scripts …")
        findings: list[Finding] = []
        for dept_path in self._target_dept_paths():
            for wf_file in dept_path.glob("*.json"):
                deploy_script = self._find_deploy_script(dept_path.name)
                if not deploy_script:
                    findings.append(self._new_finding(
                        id=f"D-{dept_path.name}-{wf_file.stem}-orphan",
                        phase=Phase.DRIFT,
                        dept=dept_path.name,
                        workflow_id="",
                        file=str(wf_file.relative_to(PROJECT_ROOT)),
                        risk=RiskLevel.MEDIUM,
                        action_type=ActionType.UPDATE_DEPLOY_SCRIPT,
                        summary=f"Workflow JSON has no deploy script: {wf_file.name}",
                        detail=f"No tools/deploy_{dept_path.name}*.py found. "
                               "Local JSON and source-of-truth may have diverged.",
                        confidence_hint=0.6,
                    ))
        log.info("[B2] %d drift findings", len(findings))
        return findings

    # ── Phase B3: code quality ──────────────────────────────────────────

    def phase_b3_quality(self) -> list[Finding]:
        log.info("[B3] Code quality audit — deploy_*.py …")
        findings: list[Finding] = []
        try:
            result = subprocess.run(
                [sys.executable, str(TOOLS_DIR / "audit_deploy_scripts.py"), "--json-only"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(PROJECT_ROOT),
            )
            payload = json.loads(result.stdout) if result.stdout.strip() else {}
        except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
            log.warning("[B3] audit_deploy_scripts invocation failed: %s", exc)
            return findings

        scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
        for filepath, report in scripts.items():
            issues = report.get("issues", []) if isinstance(report, dict) else []
            for idx, issue in enumerate(issues):
                dept = self._dept_for_script(Path(filepath).name)
                if dept and not is_active_dept(dept):
                    continue
                if self.options.dept_filter and dept != self.options.dept_filter:
                    continue
                severity = issue.get("severity", "MEDIUM")
                findings.append(self._new_finding(
                    id=f"Q-{Path(filepath).stem}-{issue.get('pattern_id','AP-?')}-{idx}",
                    phase=Phase.QUALITY,
                    dept=dept or "unknown",
                    workflow_id="",
                    file=filepath,
                    risk=_risk_for_severity(severity),
                    action_type=ActionType.UPDATE_DEPLOY_SCRIPT,
                    summary=f"{issue.get('pattern_id','AP-?')} ({severity}) at "
                            f"{Path(filepath).name}:{issue.get('line','?')}",
                    detail=f"{issue.get('message','')} — Fix: {issue.get('fix','')}",
                    confidence_hint=0.5,
                ))
        log.info("[B3] %d quality findings", len(findings))
        return findings

    # ── Phase B4: SOP refresh ───────────────────────────────────────────

    def phase_b4_sop(self) -> list[Finding]:
        log.info("[B4] SOP refresh — JSON vs MD coverage …")
        findings: list[Finding] = []
        for dept_path in self._target_dept_paths():
            for wf_file in dept_path.glob("*.json"):
                expected_sop = dept_path / sop_filename(wf_file)
                dept_sops = list(dept_path.glob("*.md"))
                has_any_sop = bool(dept_sops)
                if not expected_sop.exists() and not has_any_sop:
                    try:
                        sop_content = generate_sop_from_file(wf_file, dept_path.name)
                    except Exception as exc:
                        log.warning("[B4] SOP gen failed for %s: %s", wf_file, exc)
                        continue
                    findings.append(self._new_finding(
                        id=f"S-{dept_path.name}-{wf_file.stem}-missing",
                        phase=Phase.SOP,
                        dept=dept_path.name,
                        workflow_id="",
                        file=str(expected_sop.relative_to(PROJECT_ROOT)),
                        risk=RiskLevel.LOW,
                        action_type=ActionType.GENERATE_REPORT,
                        summary=f"Missing SOP for {wf_file.name}",
                        detail=f"Skeleton generated from workflow JSON ({len(sop_content)} chars).",
                        fix_patch={
                            "kind": "write_file",
                            "target": str(expected_sop),
                            "content": sop_content,
                        },
                        confidence_hint=0.95,
                    ))
        log.info("[B4] %d SOP findings", len(findings))
        return findings

    # ── Phase D: apply ──────────────────────────────────────────────────

    def phase_d_apply(self, classified: list[ClassifiedFinding]) -> list[ClassifiedFinding]:
        log.info("[D] Applying fixes …")
        applied: list[ClassifiedFinding] = []

        try:
            from decision_logger import DecisionLogger
            dlogger: Optional[DecisionLogger] = DecisionLogger(self.config)
        except Exception as exc:
            log.warning("[D] DecisionLogger unavailable: %s (continuing without Airtable log)", exc)
            dlogger = None

        for c in classified:
            if c.band == Band.APPLY and c.finding.action_type == ActionType.GENERATE_REPORT:
                ok = self._apply_write_file(c)
                if ok:
                    applied.append(c)
                    if dlogger:
                        try:
                            dlogger.log_decision(
                                loop_type="revision",
                                workflow_id=c.finding.workflow_id or c.finding.file,
                                agent_owner=c.finding.agent_owner,
                                issue_detected=c.finding.summary,
                                classification=c.finding.phase.value,
                                confidence_score=c.overall_confidence,
                                risk_level=c.effective_risk.name,
                                action_taken="apply",
                                changes_made=f"wrote {c.finding.file}",
                                outcome="success",
                            )
                        except Exception as exc:  # pragma: no cover
                            log.warning("[D] decision log failed: %s", exc)

            elif c.band in (Band.STAGE, Band.ESCALATE) and dlogger:
                try:
                    dlogger.log_escalation(
                        workflow_id=c.finding.workflow_id or c.finding.file,
                        severity="HIGH" if c.band == Band.ESCALATE else "MEDIUM",
                        category=c.finding.phase.value,
                        description=c.finding.summary,
                        recommended_action=c.finding.detail[:500],
                    )
                except Exception as exc:  # pragma: no cover
                    log.warning("[D] escalation log failed: %s", exc)

        log.info("[D] Applied %d / %d findings", len(applied), len(classified))
        return applied

    # ── Phase E: verification ───────────────────────────────────────────

    def phase_e_verify(self, applied: list[ClassifiedFinding]) -> list[ClassifiedFinding]:
        log.info("[E] Verifying applied fixes (%d) …", len(applied))
        verified: list[ClassifiedFinding] = []
        for c in applied:
            patch = c.finding.fix_patch or {}
            if patch.get("kind") == "write_file":
                target = Path(patch.get("target", ""))
                if target.exists() and target.stat().st_size > 0:
                    verified.append(c)
                else:
                    log.warning("[E] Verification failed for %s — file missing/empty", target)
        log.info("[E] Verified %d / %d", len(verified), len(applied))
        return verified

    # ── Phase F: report ─────────────────────────────────────────────────

    def phase_f_report(
        self,
        classified: list[ClassifiedFinding],
        applied: list[ClassifiedFinding],
        verified: list[ClassifiedFinding],
    ) -> Path:
        date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        suffix = "-dry" if not self.options.apply else ""
        report_path = REPORTS_DIR / f"revision_{date_stamp}{suffix}.md"

        band_counts = summarize_by_band(classified)
        phase_counts = summarize_by_phase(classified)

        mode = "APPLY" if self.options.apply else "DRY-RUN"
        scope = self.options.dept_filter or "all active departments"

        # Top 20 most-urgent findings
        top = sort_by_urgency(classified)[:20]

        def fmt_row(c: ClassifiedFinding) -> str:
            return (
                f"| {c.finding.phase.value} | {c.finding.dept} | {c.band.value.upper()} "
                f"| {c.effective_risk.name} | {c.overall_confidence:.2f} "
                f"| {c.finding.summary.replace('|', '\\|')} |"
            )

        lines: list[str] = [
            f"# Revision Report — {date_stamp} ({mode})",
            "",
            f"**Scope:** {scope}  ",
            f"**Autonomy tier:** {self.tier} ({self.governor.tier_name})  ",
            f"**Total findings:** {len(classified)}  ",
            f"**Applied:** {len(applied)}  ",
            f"**Verified:** {len(verified)}  ",
            "",
            "## By band",
            "",
            "| Band | Count |",
            "|---|---|",
            f"| APPLY | {band_counts['apply']} |",
            f"| STAGE | {band_counts['stage']} |",
            f"| PROPOSE | {band_counts['propose']} |",
            f"| ESCALATE | {band_counts['escalate']} |",
            "",
            "## By phase",
            "",
            "| Phase | Count |",
            "|---|---|",
            f"| Health | {phase_counts['health']} |",
            f"| Drift | {phase_counts['drift']} |",
            f"| Quality | {phase_counts['quality']} |",
            f"| SOP | {phase_counts['sop']} |",
            "",
            "## Top 20 most-urgent findings",
            "",
            "| Phase | Dept | Band | Risk | Confidence | Summary |",
            "|---|---|---|---|---|---|",
        ]
        lines.extend(fmt_row(c) for c in top)

        lines.extend([
            "",
            "## Applied fixes",
            "",
        ])
        if applied:
            lines.append("| File | Summary |")
            lines.append("|---|---|")
            for c in applied:
                lines.append(f"| {c.finding.file} | {c.finding.summary.replace('|', '\\|')} |")
        else:
            lines.append("(none — dry-run or nothing applyable)")

        lines.extend([
            "",
            "## Next actions",
            "",
            "- Review STAGE findings in Airtable Escalation_Queue.",
            "- PROPOSE / ESCALATE findings need human triage before any tier promotion.",
            "- Re-run with `--apply` once dry-run looks clean.",
            "",
            "---",
            f"Manifest: `{self.revision_dir / 'manifest.jsonl'}`",
            f"Baseline snapshot: `{self.baseline_dir}`",
        ])

        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path

    # ── Helpers ─────────────────────────────────────────────────────────

    def _target_dept_paths(self) -> list[Path]:
        if self.options.dept_filter:
            candidate = WORKFLOWS_DIR / self.options.dept_filter
            if candidate.is_dir() and is_active_dept(candidate.name):
                return [candidate]
            log.warning("Requested dept '%s' is not active or does not exist",
                        self.options.dept_filter)
            return []
        return list(iter_active_dept_paths(WORKFLOWS_DIR))

    def _find_deploy_script(self, dept: str) -> Optional[Path]:
        candidates = list(TOOLS_DIR.glob(f"deploy_{dept.replace('-', '_')}*.py"))
        if candidates:
            return candidates[0]
        candidates = list(TOOLS_DIR.glob(f"deploy_{dept}*.py"))
        return candidates[0] if candidates else None

    def _dept_for_script(self, filename: str) -> Optional[str]:
        if not filename.startswith("deploy_"):
            return None
        stem = filename[len("deploy_"):].removesuffix(".py")
        # Try direct match first
        hyphen = stem.replace("_", "-")
        for candidate in (hyphen, stem.split("_")[0], stem):
            path = WORKFLOWS_DIR / candidate
            if path.is_dir():
                return candidate
        return stem

    @staticmethod
    def _dept_for_workflow_name(name: str) -> str:
        """Best-effort dept classifier from workflow name prefix."""
        lower = name.lower()
        prefixes = {
            "acc_": "accounting-dept",
            "li-": "linkedin-dept",
            "seo-": "seo-social-dept",
            "ads-": "ads-dept",
            "mkt-": "marketing-dept",
            "fin-": "financial-advisory",
        }
        for prefix, dept in prefixes.items():
            if lower.startswith(prefix):
                return dept
        return ""

    def _new_finding(self, **kwargs: Any) -> Finding:
        return Finding(**kwargs)

    def _write_manifest(self, classified: list[ClassifiedFinding]) -> None:
        path = self.revision_dir / "manifest.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for c in classified:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        log.info("[C] Manifest written → %s (%d findings)", path, len(classified))

    def _apply_write_file(self, c: ClassifiedFinding) -> bool:
        patch = c.finding.fix_patch or {}
        target = Path(patch.get("target", ""))
        content = patch.get("content", "")
        if not target or not content:
            log.warning("[D] Invalid write_file patch for %s", c.finding.id)
            return False
        if target.exists():
            log.info("[D] Target %s exists — skipping (no overwrite in revision)", target)
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        log.info("[D] Wrote %s (%d bytes)", target, len(content))
        return True


# ── Entry point ─────────────────────────────────────────────────────────

def main() -> int:
    options = parse_args()
    runner = FullRevisionRunner(options)
    try:
        return runner.run()
    except KeyboardInterrupt:
        log.warning("Interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())

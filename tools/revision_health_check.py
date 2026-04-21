"""
Run a health sweep across every active n8n workflow.

Pulls the last N executions per active workflow and classifies each:
    GREEN  — most recent execution succeeded
    RED    — most recent execution failed
    DARK   — never executed (scheduled but not yet fired, or stale)

Writes a Markdown report to `.planning/revision-2026-04-21/health-report.md`
and prints a summary table to stdout.

Usage
-----
    python tools/revision_health_check.py                 # default, 20 execs per wf
    python tools/revision_health_check.py --per-wf 50     # deeper history
    python tools/revision_health_check.py --out <path>    # custom report path
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from n8n_client import N8nClient  # noqa: E402

load_dotenv()


def classify(executions: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """Return (status, context) where status is GREEN|RED|DARK."""
    if not executions:
        return "DARK", {"last_exec": None, "recent_failures": 0}

    most_recent = executions[0]
    status = most_recent.get("status") or (
        "success" if most_recent.get("finished") else "error"
    )
    recent_failures = sum(
        1 for e in executions
        if (e.get("status") == "error") or (e.get("finished") is False and e.get("stoppedAt"))
    )
    ctx = {
        "last_exec": most_recent.get("startedAt") or most_recent.get("stoppedAt"),
        "last_status": status,
        "recent_failures": recent_failures,
        "recent_total": len(executions),
    }
    return ("GREEN" if status == "success" else "RED"), ctx


def sweep(client: N8nClient, per_workflow: int) -> list[dict[str, Any]]:
    workflows = client.list_workflows(active_only=True, use_cache=False)
    active = [w for w in workflows if w.get("active")]
    print(f"\nSweeping {len(active)} active workflows (last {per_workflow} exec each)...")

    rows: list[dict[str, Any]] = []
    for wf in sorted(active, key=lambda w: w.get("name", "")):
        wf_id = wf["id"]
        name = wf.get("name", "<unnamed>")
        try:
            execs = client.list_executions(workflow_id=wf_id, limit=per_workflow)
        except Exception as exc:  # noqa: BLE001
            rows.append({
                "id": wf_id, "name": name, "status": "ERROR",
                "note": f"list_executions failed: {exc}",
                "last_exec": None, "recent_failures": 0, "recent_total": 0,
            })
            continue

        status, ctx = classify(execs)
        rows.append({"id": wf_id, "name": name, "status": status, "note": "", **ctx})
        marker = {"GREEN": "OK ", "RED": "!! ", "DARK": ".. ", "ERROR": "?? "}[status]
        last = ctx.get("last_exec") or "never"
        fails = ctx.get("recent_failures", 0)
        tot = ctx.get("recent_total", 0)
        print(f"  {marker} {name:<50} last={last}  failures={fails}/{tot}")
    return rows


def write_report(rows: list[dict[str, Any]], out_path: Path, per_workflow: int) -> None:
    counts = Counter(r["status"] for r in rows)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append("# Active Workflow Health Sweep")
    lines.append("")
    lines.append(f"- Generated: {now}")
    lines.append(f"- Active workflows scanned: {len(rows)}")
    lines.append(f"- Executions inspected per workflow: last {per_workflow}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- GREEN (last run succeeded): **{counts.get('GREEN', 0)}**")
    lines.append(f"- RED (last run failed): **{counts.get('RED', 0)}**")
    lines.append(f"- DARK (no executions in window): **{counts.get('DARK', 0)}**")
    lines.append(f"- ERROR (audit failed): **{counts.get('ERROR', 0)}**")
    lines.append("")

    def section(title: str, statuses: tuple[str, ...]) -> None:
        subset = [r for r in rows if r["status"] in statuses]
        if not subset:
            return
        lines.append(f"## {title} ({len(subset)})")
        lines.append("")
        lines.append("| Workflow | ID | Last exec | Recent fails | Note |")
        lines.append("|---|---|---|---|---|")
        for r in subset:
            last = r.get("last_exec") or "—"
            fails = f'{r.get("recent_failures", 0)}/{r.get("recent_total", 0)}'
            note = r.get("note", "") or ""
            lines.append(f"| {r['name']} | `{r['id']}` | {last} | {fails} | {note} |")
        lines.append("")

    section("RED — Attention", ("RED", "ERROR"))
    section("DARK — No executions", ("DARK",))
    section("GREEN — Healthy", ("GREEN",))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-wf", type=int, default=20,
                        help="Executions to inspect per workflow (default 20)")
    parser.add_argument("--out", type=Path, default=Path(
        ".planning/revision-2026-04-21/health-report.md"))
    args = parser.parse_args()

    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env", file=sys.stderr)
        sys.exit(2)

    with N8nClient(base_url=base_url, api_key=api_key) as client:
        rows = sweep(client, per_workflow=args.per_wf)

    write_report(rows, args.out, per_workflow=args.per_wf)

    red = sum(1 for r in rows if r["status"] in ("RED", "ERROR"))
    sys.exit(1 if red else 0)


if __name__ == "__main__":
    main()

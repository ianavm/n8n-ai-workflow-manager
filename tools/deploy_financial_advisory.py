"""
Master deployer for Financial Advisory CRM n8n workflows.

Manages all FA workflows (FA-01 through FA-10, plus FA-07a/b split).
Each workflow is defined in its own module (deploy_fa_wfXX.py).

Usage:
    python tools/deploy_financial_advisory.py build [fa01|fa02|...|all]
    python tools/deploy_financial_advisory.py deploy [fa01|fa02|...|all]
    python tools/deploy_financial_advisory.py activate [fa01|fa02|...|all]
    python tools/deploy_financial_advisory.py status
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

# Add tools/ to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from n8n_client import N8nClient


# ============================================================
# Workflow Registry
# ============================================================

WORKFLOW_REGISTRY: dict[str, dict[str, str]] = {
    "fa01": {
        "module": "deploy_fa_wf01",
        "name": "FA - Client Intake & Onboarding (FA-01)",
        "filename": "fa01_client_intake.json",
        "description": "Webhook intake, Supabase records, welcome email, adviser notification, schedule discovery",
    },
    "fa02": {
        "module": "deploy_fa_wf02",
        "name": "FA - Meeting Scheduler (FA-02)",
        "filename": "fa02_meeting_scheduler.json",
        "description": "Sub-workflow: calendar availability, Teams meeting creation, confirmations",
    },
    "fa03": {
        "module": "deploy_fa_wf03",
        "name": "FA - Pre-Meeting Prep (FA-03)",
        "filename": "fa03_pre_meeting_prep.json",
        "description": "Scheduled: generate AI briefing 2h before meetings, send to adviser",
    },
    "fa04": {
        "module": "deploy_fa_wf04",
        "name": "FA - Transcript Analysis (FA-04)",
        "filename": "fa04_transcript_analysis.json",
        "description": "Scheduled: poll Graph API for transcripts, AI analysis, store insights",
    },
    "fa05": {
        "module": "deploy_fa_wf05",
        "name": "FA - Post-Meeting Processing (FA-05)",
        "filename": "fa05_post_meeting.json",
        "description": "Sub-workflow: send summary to client, create tasks, trigger pipeline",
    },
    "fa06": {
        "module": "deploy_fa_wf06",
        "name": "FA - Discovery-to-Presentation Pipeline (FA-06)",
        "filename": "fa06_discovery_pipeline.json",
        "description": "Sub-workflow: research analysis, generate advice doc, schedule presentation",
    },
    "fa07a": {
        "module": "deploy_fa_wf07a",
        "name": "FA - Scheduled Reminders (FA-07a)",
        "filename": "fa07a_reminders.json",
        "description": "Scheduled: 24h and 1h meeting reminders via email + WhatsApp",
    },
    "fa07b": {
        "module": "deploy_fa_wf07b",
        "name": "FA - Send Communications (FA-07b)",
        "filename": "fa07b_send_comms.json",
        "description": "Webhook: on-demand send via email, WhatsApp, or Teams",
    },
    "fa08": {
        "module": "deploy_fa_wf08",
        "name": "FA - Compliance & Audit Engine (FA-08)",
        "filename": "fa08_compliance.json",
        "description": "Scheduled daily: consent checks, FICA verification, compliance report",
    },
    "fa09": {
        "module": "deploy_fa_wf09",
        "name": "FA - Document Management (FA-09)",
        "filename": "fa09_documents.json",
        "description": "Webhook: document upload, AI classification, FICA check, adviser notify",
    },
    "fa10": {
        "module": "deploy_fa_wf10",
        "name": "FA - Weekly Reporting (FA-10)",
        "filename": "fa10_reporting.json",
        "description": "Scheduled weekly: aggregate metrics, AI summary, email report, Airtable sync",
    },
}

OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "financial-advisory"


# ============================================================
# Client
# ============================================================


def _get_client() -> N8nClient | None:
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY", "")
    if not api_key:
        print("WARNING: N8N_API_KEY not set. Deploy/activate will fail.")
        return None
    return N8nClient(base_url=base_url, api_key=api_key)


# ============================================================
# Operations
# ============================================================


def build_workflow(key: str) -> dict[str, Any] | None:
    """Build a single workflow JSON by importing its module."""
    entry = WORKFLOW_REGISTRY.get(key)
    if not entry:
        print(f"ERROR: Unknown workflow key '{key}'")
        return None

    try:
        mod = importlib.import_module(entry["module"])
    except ModuleNotFoundError:
        print(f"WARNING: Module '{entry['module']}' not found. Skipping '{key}'.")
        return None

    nodes = mod.build_nodes()
    connections = mod.build_connections()

    workflow = {
        "name": entry["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
        },
    }
    return workflow


def save_json(key: str, workflow: dict[str, Any]) -> Path:
    """Save workflow JSON to disk."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = WORKFLOW_REGISTRY[key]["filename"]
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    node_count = len(workflow.get("nodes", []))
    print(f"  Saved: {path} ({node_count} nodes)")
    return path


def deploy_workflow(key: str, workflow: dict[str, Any]) -> str | None:
    """Deploy workflow to n8n Cloud (inactive)."""
    client = _get_client()
    if not client:
        return None
    try:
        result = client.create_workflow(workflow)
        wf_id = result.get("id", "")
        print(f"  Deployed: {WORKFLOW_REGISTRY[key]['name']} -> {wf_id}")
        return wf_id
    except Exception as e:
        print(f"  ERROR deploying {key}: {e}")
        return None


def activate_workflow(wf_id: str, key: str) -> None:
    """Activate a deployed workflow."""
    client = _get_client()
    if not client:
        return
    try:
        client.activate_workflow(wf_id)
        print(f"  Activated: {WORKFLOW_REGISTRY[key]['name']} ({wf_id})")
    except Exception as e:
        print(f"  ERROR activating {key}: {e}")


def show_status() -> None:
    """Show status of all FA workflows on n8n Cloud."""
    client = _get_client()
    if not client:
        return
    workflows = client.list_workflows()
    fa_workflows = [w for w in workflows if w.get("name", "").startswith("FA -")]
    if not fa_workflows:
        print("No FA workflows found on n8n Cloud.")
        return
    print(f"\nFound {len(fa_workflows)} FA workflow(s):\n")
    for w in sorted(fa_workflows, key=lambda x: x.get("name", "")):
        status = "ACTIVE" if w.get("active") else "inactive"
        print(f"  [{status:8s}] {w['name']} ({w['id']})")


# ============================================================
# CLI
# ============================================================


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "status":
        show_status()
        return

    target = sys.argv[2].lower() if len(sys.argv) > 2 else "all"
    keys = list(WORKFLOW_REGISTRY.keys()) if target == "all" else [target]

    # Validate keys
    for k in keys:
        if k not in WORKFLOW_REGISTRY:
            print(f"ERROR: Unknown workflow '{k}'. Available: {', '.join(WORKFLOW_REGISTRY.keys())}")
            sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Financial Advisory CRM - {command.upper()} ({len(keys)} workflow(s))")
    print(f"{'='*60}\n")

    for key in keys:
        print(f"[{key}] {WORKFLOW_REGISTRY[key]['name']}")
        workflow = build_workflow(key)
        if not workflow:
            continue

        if command in ("build", "deploy", "activate"):
            save_json(key, workflow)

        if command in ("deploy", "activate"):
            wf_id = deploy_workflow(key, workflow)
            if wf_id and command == "activate":
                activate_workflow(wf_id, key)

        print()

    print(f"{'='*60}")
    print(f"Done. {len(keys)} workflow(s) processed.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

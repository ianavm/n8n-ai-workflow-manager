"""
Plug-and-Play Accounting -- WF10 Exception Management

Monitors for overdue tasks and failed workflows. Escalates overdue
tasks (based on escalation_after_days), sends escalation emails,
logs retry tasks for failed workflows, and posts status webhooks.

Usage:
    python tools/deploy_acct_v2_wf10.py build
    python tools/deploy_acct_v2_wf10.py deploy
    python tools/deploy_acct_v2_wf10.py activate
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))
from acct_helpers import (
    SUPABASE_KEY,
    SUPABASE_URL,
    build_workflow_json,
    code_node,
    conn,
    gmail_send,
    if_node,
    manual_trigger,
    noop_node,
    portal_status_webhook,
    respond_webhook,
    schedule_trigger,
    supabase_insert,
    supabase_select,
    supabase_update,
    uid,
    webhook_trigger,
)
from credentials import CREDENTIALS

CRED_GMAIL = CREDENTIALS["gmail"]

# -- Constants ---------------------------------------------------------------

WORKFLOW_NAME = "ACCT-10 Exception Management"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "accounting-v2"
OUTPUT_FILENAME = "wf10_exceptions.json"


# ============================================================================
# NODE BUILDERS
# ============================================================================

def build_nodes() -> list[dict[str, Any]]:
    """Build ~20 nodes for the Exception Management workflow."""
    nodes: list[dict[str, Any]] = []

    # -- 1. Schedule Trigger (every 15min 8-17 M-F) ---------------------------
    nodes.append(schedule_trigger(
        name="Exception Monitor",
        cron="*/15 8-17 * * 1-5",
        position=[200, 0],
    ))

    # -- 2. Webhook Trigger ---------------------------------------------------
    nodes.append(webhook_trigger(
        name="Exception Webhook",
        path="accounting/exception",
        position=[200, 300],
    ))

    # -- 3. Manual Trigger ----------------------------------------------------
    nodes.append(manual_trigger(position=[200, 600]))

    # -- 4. Load Config -------------------------------------------------------
    nodes.append(code_node(
        name="Load Config",
        js_code=(
            "const body = $input.first().json.body || $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    client_id: body.client_id || $env.ACCT_DEFAULT_CLIENT_ID || null,\n"
            "    admin_email: body.admin_email || $env.ACCT_ADMIN_EMAIL || 'ian@anyvisionmedia.com',\n"
            "    owner_email: body.owner_email || $env.ACCT_OWNER_EMAIL || 'ian@anyvisionmedia.com',\n"
            "    escalation_after_days: body.escalation_after_days || 3,\n"
            "    run_time: new Date().toISOString(),\n"
            "  }\n"
            "}];\n"
        ),
        position=[460, 300],
    ))

    # -- 5. Find Overdue Tasks ------------------------------------------------
    nodes.append(supabase_select(
        name="Find Overdue Tasks",
        table="acct_tasks",
        select="*",
        filters="={{ 'status=eq.open&due_at=lt.' + new Date().toISOString() + '&client_id=eq.' + $json.client_id }}",
        position=[720, 200],
    ))

    # -- 6. Has Overdue Tasks? ------------------------------------------------
    nodes.append(if_node(
        name="Has Overdue?",
        left_value="={{ $json.length }}",
        operator_type="number",
        operation="gt",
        right_value="0",
        position=[960, 200],
    ))

    # -- 7. No Overdue (passthrough) ------------------------------------------
    nodes.append(noop_node(
        name="No Overdue Tasks",
        position=[1200, 350],
    ))

    # -- 8. Check Escalation Tier (loop items via Code) -----------------------
    nodes.append(code_node(
        name="Check Escalation",
        js_code=(
            "const tasks = $input.all().map(i => i.json);\n"
            "const config = $('Load Config').first().json;\n"
            "const now = new Date();\n"
            "const threshold = config.escalation_after_days * 24 * 60 * 60 * 1000;\n"
            "\n"
            "const toEscalate = [];\n"
            "for (const task of tasks) {\n"
            "  if (task.status === 'escalated') continue;\n"
            "  const created = new Date(task.created_at);\n"
            "  const age = now.getTime() - created.getTime();\n"
            "  if (age > threshold) {\n"
            "    toEscalate.push({\n"
            "      ...task,\n"
            "      age_days: Math.round(age / (24 * 60 * 60 * 1000)),\n"
            "      admin_email: config.admin_email,\n"
            "      owner_email: config.owner_email,\n"
            "      client_id: config.client_id,\n"
            "    });\n"
            "  }\n"
            "}\n"
            "\n"
            "if (toEscalate.length === 0) {\n"
            "  return [{ json: { _skip: true, client_id: config.client_id } }];\n"
            "}\n"
            "\n"
            "return toEscalate.map(t => ({ json: t }));\n"
        ),
        position=[1200, 100],
    ))

    # -- 9. Should Escalate? (skip items with _skip flag) ---------------------
    nodes.append(if_node(
        name="Should Escalate?",
        left_value="={{ $json._skip }}",
        operator_type="boolean",
        operation="notTrue",
        position=[1460, 100],
    ))

    # -- 10. Escalate Task (update status) ------------------------------------
    nodes.append(code_node(
        name="Prep Escalation Update",
        js_code=(
            "const task = $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    id: task.id,\n"
            "    updatePayload: {\n"
            "      status: 'escalated',\n"
            "      escalated_at: new Date().toISOString(),\n"
            "      updated_at: new Date().toISOString(),\n"
            "    },\n"
            "    task_id: task.id,\n"
            "    task_type: task.task_type,\n"
            "    title: task.title || task.task_type,\n"
            "    age_days: task.age_days,\n"
            "    owner_email: task.owner || task.assigned_to || task.owner_email,\n"
            "    admin_email: task.admin_email,\n"
            "    client_id: task.client_id,\n"
            "  }\n"
            "}];\n"
        ),
        position=[1720, 0],
    ))

    nodes.append(supabase_update(
        name="Update Task Escalated",
        table="acct_tasks",
        match_col="id",
        position=[1980, 0],
    ))

    # -- 11. Send Escalation Email --------------------------------------------
    nodes.append(gmail_send(
        name="Send Escalation Email",
        to_expr="={{ $json.owner_email }},{{ $json.admin_email }}",
        subject_expr="=ESCALATION: {{ $json.title }} ({{ $json.age_days }} days overdue)",
        html_expr=(
            "=<h2 style=\"color:#e53e3e\">Task Escalated</h2>"
            "<p><strong>Task:</strong> {{ $json.title }}</p>"
            "<p><strong>Type:</strong> {{ $json.task_type }}</p>"
            "<p><strong>Age:</strong> {{ $json.age_days }} days overdue</p>"
            "<p><strong>Task ID:</strong> {{ $json.task_id }}</p>"
            "<p>This task has been automatically escalated. Please take immediate action.</p>"
            "<p style=\"color:#888\">AnyVision Media Accounting -- Exception Management</p>"
        ),
        cred=CRED_GMAIL,
        position=[2240, 0],
    ))

    # -- 12. Audit Log: TASK_ESCALATED ----------------------------------------
    nodes.append(code_node(
        name="Audit Escalation",
        js_code=(
            "const item = $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    client_id: item.client_id,\n"
            "    event_type: 'TASK_ESCALATED',\n"
            "    entity_type: 'task',\n"
            "    entity_id: item.task_id || item.id,\n"
            "    action: 'task_escalated',\n"
            "    actor: 'n8n-wf10',\n"
            "    result: 'success',\n"
            "    metadata: { source: 'n8n', age_days: item.age_days, task_type: item.task_type }\n"
            "  }\n"
            "}];\n"
        ),
        position=[2500, 0],
    ))

    nodes.append(supabase_insert(
        name="Audit Log Escalation",
        table="acct_audit_log",
        position=[2760, 0],
        return_rep=False,
    ))

    # -- 13. Status Webhook: task_escalated -----------------------------------
    nodes.append(portal_status_webhook(
        name="Status: task_escalated",
        action="task_escalated",
        position=[3020, 0],
    ))

    # -- 14. Find Failed Workflows (last 24h) ---------------------------------
    nodes.append(supabase_select(
        name="Find Failed Workflows",
        table="acct_workflow_status",
        select="*",
        filters="={{ 'status=eq.failed&started_at=gt.' + new Date(Date.now() - 86400000).toISOString() + '&client_id=eq.' + $json.client_id }}",
        position=[720, 500],
    ))

    # -- 15. Has Failures? ----------------------------------------------------
    nodes.append(if_node(
        name="Has Failures?",
        left_value="={{ $json.length }}",
        operator_type="number",
        operation="gt",
        right_value="0",
        position=[960, 500],
    ))

    # -- 16. No Failures (passthrough) ----------------------------------------
    nodes.append(noop_node(
        name="No Failed Workflows",
        position=[1200, 650],
    ))

    # -- 17. Log Retry Tasks --------------------------------------------------
    nodes.append(code_node(
        name="Build Retry Tasks",
        js_code=(
            "const failures = $input.all().map(i => i.json);\n"
            "const config = $('Load Config').first().json;\n"
            "\n"
            "return failures.map(f => ({\n"
            "  json: {\n"
            "    client_id: config.client_id,\n"
            "    task_type: 'workflow_retry',\n"
            "    title: 'Retry: ' + (f.workflow_name || f.workflow_id),\n"
            "    status: 'open',\n"
            "    entity_id: f.workflow_id || f.id,\n"
            "    owner: config.admin_email,\n"
            "    metadata: {\n"
            "      original_error: f.error_message || 'Unknown',\n"
            "      workflow_id: f.workflow_id,\n"
            "      failed_at: f.started_at,\n"
            "    },\n"
            "    created_at: new Date().toISOString(),\n"
            "    due_at: new Date(Date.now() + 3600000).toISOString(),\n"
            "  }\n"
            "}));\n"
        ),
        position=[1200, 500],
    ))

    nodes.append(supabase_insert(
        name="Insert Retry Tasks",
        table="acct_tasks",
        position=[1460, 500],
    ))

    # -- 18. Audit Log: WORKFLOW_FAILED ---------------------------------------
    nodes.append(code_node(
        name="Audit Failure",
        js_code=(
            "const item = $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    client_id: item.client_id,\n"
            "    event_type: 'WORKFLOW_FAILED',\n"
            "    entity_type: 'workflow',\n"
            "    entity_id: item.entity_id || item.id,\n"
            "    action: 'retry_logged',\n"
            "    actor: 'n8n-wf10',\n"
            "    result: 'success',\n"
            "    metadata: { source: 'n8n', title: item.title }\n"
            "  }\n"
            "}];\n"
        ),
        position=[1720, 500],
    ))

    nodes.append(supabase_insert(
        name="Audit Log Failure",
        table="acct_audit_log",
        position=[1980, 500],
        return_rep=False,
    ))

    # -- 19. Build Response ---------------------------------------------------
    nodes.append(code_node(
        name="Build Response",
        js_code=(
            "const config = $('Load Config').first().json;\n"
            "\n"
            "// Count results from each branch safely\n"
            "let escalated = 0;\n"
            "let retries = 0;\n"
            "try { escalated = $('Check Escalation').all().filter(i => !i.json._skip).length; } catch(e) {}\n"
            "try { retries = $('Build Retry Tasks').all().length; } catch(e) {}\n"
            "\n"
            "return [{\n"
            "  json: {\n"
            "    success: true,\n"
            "    message: 'Exception management run complete',\n"
            "    run_time: config.run_time,\n"
            "    tasks_escalated: escalated,\n"
            "    retry_tasks_created: retries,\n"
            "  }\n"
            "}];\n"
        ),
        position=[3020, 400],
    ))

    # -- 20. Respond Webhook --------------------------------------------------
    nodes.append(respond_webhook(
        name="Respond Webhook",
        position=[3280, 400],
    ))

    return nodes


# ============================================================================
# CONNECTIONS
# ============================================================================

def build_connections() -> dict[str, Any]:
    """Build connections for the Exception Management workflow."""
    return {
        # -- Triggers to Load Config --
        "Exception Monitor": {"main": [[conn("Load Config")]]},
        "Exception Webhook": {"main": [[conn("Load Config")]]},
        "Manual Trigger": {"main": [[conn("Load Config")]]},

        # -- Fan out: overdue tasks + failed workflows --
        "Load Config": {
            "main": [[
                conn("Find Overdue Tasks"),
                conn("Find Failed Workflows"),
            ]],
        },

        # -- Overdue tasks branch --
        "Find Overdue Tasks": {"main": [[conn("Has Overdue?")]]},
        "Has Overdue?": {
            "main": [
                [conn("Check Escalation")],    # true
                [conn("No Overdue Tasks")],    # false
            ],
        },
        "No Overdue Tasks": {"main": [[conn("Build Response")]]},
        "Check Escalation": {"main": [[conn("Should Escalate?")]]},
        "Should Escalate?": {
            "main": [
                [conn("Prep Escalation Update")],  # true (should escalate)
                [conn("Build Response")],           # false (skip)
            ],
        },
        "Prep Escalation Update": {"main": [[conn("Update Task Escalated")]]},
        "Update Task Escalated": {"main": [[conn("Send Escalation Email")]]},
        "Send Escalation Email": {"main": [[conn("Audit Escalation")]]},
        "Audit Escalation": {"main": [[conn("Audit Log Escalation")]]},
        "Audit Log Escalation": {"main": [[conn("Status: task_escalated")]]},
        "Status: task_escalated": {"main": [[conn("Build Response")]]},

        # -- Failed workflows branch --
        "Find Failed Workflows": {"main": [[conn("Has Failures?")]]},
        "Has Failures?": {
            "main": [
                [conn("Build Retry Tasks")],     # true
                [conn("No Failed Workflows")],   # false
            ],
        },
        "No Failed Workflows": {"main": [[conn("Build Response")]]},
        "Build Retry Tasks": {"main": [[conn("Insert Retry Tasks")]]},
        "Insert Retry Tasks": {"main": [[conn("Audit Failure")]]},
        "Audit Failure": {"main": [[conn("Audit Log Failure")]]},
        "Audit Log Failure": {"main": [[conn("Build Response")]]},

        # -- Final response --
        "Build Response": {"main": [[conn("Respond Webhook")]]},
    }


# ============================================================================
# WORKFLOW ASSEMBLY
# ============================================================================

def build_workflow() -> dict[str, Any]:
    """Assemble the complete workflow JSON."""
    return build_workflow_json(
        name=WORKFLOW_NAME,
        nodes=build_nodes(),
        connections=build_connections(),
    )


def save_workflow(workflow: dict[str, Any]) -> Path:
    """Save workflow JSON to file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILENAME
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    return output_path


def print_workflow_stats(workflow: dict[str, Any]) -> None:
    """Print workflow statistics."""
    all_nodes = workflow["nodes"]
    func_nodes = [n for n in all_nodes if n["type"] != "n8n-nodes-base.stickyNote"]
    note_nodes = [n for n in all_nodes if n["type"] == "n8n-nodes-base.stickyNote"]
    conn_count = len(workflow["connections"])
    print(f"  Name: {workflow['name']}")
    print(f"  Nodes: {len(func_nodes)} functional + {len(note_nodes)} sticky notes")
    print(f"  Connections: {conn_count}")


# ============================================================================
# CLI
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ACCT-10 Exception Management -- Builder & Deployer",
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="build",
        choices=["build", "deploy", "activate"],
    )
    parsed = parser.parse_args()
    action = parsed.action

    print("=" * 60)
    print("ACCT-10  EXCEPTION MANAGEMENT")
    print("=" * 60)

    # -- Build ----------------------------------------------------------------
    print("\nBuilding workflow...")
    workflow = build_workflow()
    output_path = save_workflow(workflow)
    print_workflow_stats(workflow)
    print(f"  Saved to: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    # -- Deploy / Activate ----------------------------------------------------
    from config_loader import load_config
    from n8n_client import N8nClient

    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = config["n8n"]["base_url"]

    print(f"\nConnecting to {base_url}...")

    with N8nClient(
        base_url,
        api_key,
        timeout=config["n8n"].get("timeout_seconds", 30),
        cache_dir=config["paths"]["cache_dir"],
    ) as client:
        health = client.health_check()
        if not health["connected"]:
            print(f"  ERROR: Cannot connect to n8n: {health.get('error')}")
            sys.exit(1)
        print("  Connected!")

        existing = None
        try:
            all_wfs = client.list_workflows()
            for wf in all_wfs:
                if wf["name"] == workflow["name"]:
                    existing = wf
                    break
        except Exception:
            pass

        if existing:
            update_payload = {
                "name": workflow["name"],
                "nodes": workflow["nodes"],
                "connections": workflow["connections"],
                "settings": workflow["settings"],
            }
            result = client.update_workflow(existing["id"], update_payload)
            wf_id = result.get("id")
            print(f"  Updated: {result.get('name')} (ID: {wf_id})")
        else:
            create_payload = {
                "name": workflow["name"],
                "nodes": workflow["nodes"],
                "connections": workflow["connections"],
                "settings": workflow["settings"],
            }
            result = client.create_workflow(create_payload)
            wf_id = result.get("id")
            print(f"  Created: {result.get('name')} (ID: {wf_id})")

        if action == "activate" and wf_id:
            print("  Activating...")
            client.activate_workflow(wf_id)
            print("  Activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Triggers:")
    print("  Schedule: every 15min, 08:00-17:00, Mon-Fri")
    print("  POST /accounting/exception  -- webhook trigger")
    print("  Manual trigger for testing")
    print()
    print("Next steps:")
    print("  1. Ensure Supabase tables: acct_tasks, acct_workflow_status, acct_audit_log")
    print("  2. Tasks need: status, due_at, created_at, escalation fields")
    print("  3. Configure Gmail credential for escalation emails")
    print("  4. Test: POST to /accounting/exception with {client_id}")


if __name__ == "__main__":
    main()

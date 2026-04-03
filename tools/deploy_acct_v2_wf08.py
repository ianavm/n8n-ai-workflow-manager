"""
Plug-and-Play Accounting -- WF08 Approval Engine

Handles email-link approvals and rejections for invoices, bills,
and payment reconciliations. Validates token, checks task state,
executes the appropriate action, notifies the owner, and returns
an HTML confirmation page.

Usage:
    python tools/deploy_acct_v2_wf08.py build
    python tools/deploy_acct_v2_wf08.py deploy
    python tools/deploy_acct_v2_wf08.py activate
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
    build_workflow_json,
    code_node,
    conn,
    gmail_send,
    if_node,
    manual_trigger,
    portal_status_webhook,
    respond_webhook,
    supabase_insert,
    supabase_select,
    supabase_update,
    switch_node,
    uid,
    webhook_trigger,
)
from credentials import CREDENTIALS

CRED_GMAIL = CREDENTIALS["gmail"]

# -- Constants ---------------------------------------------------------------

WORKFLOW_NAME = "ACCT-08 Approval Engine"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "accounting-v2"
OUTPUT_FILENAME = "wf08_approvals.json"


# ============================================================================
# NODE BUILDERS
# ============================================================================

def build_nodes() -> list[dict[str, Any]]:
    """Build ~22 nodes for the Approval Engine workflow."""
    nodes: list[dict[str, Any]] = []

    # -- 1. Approve Webhook (GET with query params) ---------------------------
    nodes.append(webhook_trigger(
        name="Approve Webhook",
        path="accounting/approve",
        position=[200, 300],
        method="GET",
    ))

    # -- 2. Reject Webhook (GET with query params) ----------------------------
    nodes.append(webhook_trigger(
        name="Reject Webhook",
        path="accounting/reject",
        position=[200, 600],
        method="GET",
    ))

    # -- 3. Manual Trigger ----------------------------------------------------
    nodes.append(manual_trigger(position=[200, 900]))

    # -- 4. Extract Token & Action (approve path) -----------------------------
    nodes.append(code_node(
        name="Extract Approve Params",
        js_code=(
            "const qs = $input.first().json.query || $input.first().json;\n"
            "if (!qs.token) {\n"
            "  throw new Error('Missing approval token');\n"
            "}\n"
            "return [{\n"
            "  json: {\n"
            "    token: qs.token,\n"
            "    action: 'approve',\n"
            "  }\n"
            "}];\n"
        ),
        position=[460, 300],
    ))

    # -- 5. Extract Token & Action (reject path) ------------------------------
    nodes.append(code_node(
        name="Extract Reject Params",
        js_code=(
            "const qs = $input.first().json.query || $input.first().json;\n"
            "if (!qs.token) {\n"
            "  throw new Error('Missing approval token');\n"
            "}\n"
            "return [{\n"
            "  json: {\n"
            "    token: qs.token,\n"
            "    action: 'reject',\n"
            "  }\n"
            "}];\n"
        ),
        position=[460, 600],
    ))

    # -- 6. Lookup Task by Token ----------------------------------------------
    nodes.append(supabase_select(
        name="Lookup Task",
        table="acct_tasks",
        select="*",
        filters="={{ 'approval_token=eq.' + $json.token }}",
        position=[720, 450],
        single=True,
    ))

    # -- 7. Task Found? -------------------------------------------------------
    nodes.append(if_node(
        name="Task Found?",
        left_value="={{ $json.id }}",
        operator_type="string",
        operation="exists",
        position=[960, 450],
    ))

    # -- 8. Not Found HTML Response -------------------------------------------
    nodes.append(code_node(
        name="Not Found Response",
        js_code=(
            "return [{\n"
            "  json: {\n"
            "    success: false,\n"
            "    html: '<html><body style=\"font-family:sans-serif;text-align:center;padding:60px\">'\n"
            "      + '<h1 style=\"color:#e53e3e\">Task Not Found</h1>'\n"
            "      + '<p>The approval link is invalid or has expired.</p>'\n"
            "      + '</body></html>',\n"
            "  }\n"
            "}];\n"
        ),
        position=[1200, 650],
    ))

    # -- 9. Already Resolved? -------------------------------------------------
    nodes.append(if_node(
        name="Already Resolved?",
        left_value="={{ $json.status }}",
        operator_type="string",
        operation="notEquals",
        right_value="open",
        position=[1200, 350],
    ))

    # -- 10. Already Resolved HTML Response -----------------------------------
    nodes.append(code_node(
        name="Already Resolved Response",
        js_code=(
            "const task = $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    success: false,\n"
            "    html: '<html><body style=\"font-family:sans-serif;text-align:center;padding:60px\">'\n"
            "      + '<h1 style=\"color:#dd6b20\">Already Processed</h1>'\n"
            "      + '<p>This task was already ' + (task.status || 'resolved')\n"
            "      + ' on ' + (task.resolved_at || 'unknown date') + '.</p>'\n"
            "      + '</body></html>',\n"
            "  }\n"
            "}];\n"
        ),
        position=[1460, 200],
    ))

    # -- 11. Task Type Switch -------------------------------------------------
    nodes.append(switch_node(
        name="Task Type Switch",
        rules=[
            {"leftValue": "={{ $json.task_type }}", "rightValue": "invoice_approval", "output": "invoice"},
            {"leftValue": "={{ $json.task_type }}", "rightValue": "bill_approval", "output": "bill"},
            {"leftValue": "={{ $json.task_type }}", "rightValue": "payment_reconciliation", "output": "reconciliation"},
        ],
        position=[1460, 450],
    ))

    # -- 12. Prepare Invoice Update -------------------------------------------
    nodes.append(code_node(
        name="Prepare Invoice Update",
        js_code=(
            "const task = $input.first().json;\n"
            "const action = $('Extract Approve Params').first()?.json?.action\n"
            "  || $('Extract Reject Params').first()?.json?.action\n"
            "  || 'approve';\n"
            "const newStatus = action === 'approve' ? 'approved' : 'rejected';\n"
            "\n"
            "return [{\n"
            "  json: {\n"
            "    id: task.entity_id,\n"
            "    updatePayload: { status: newStatus, updated_at: new Date().toISOString() },\n"
            "    task_id: task.id,\n"
            "    task_type: task.task_type,\n"
            "    approval_action: action,\n"
            "    new_status: newStatus,\n"
            "    client_id: task.client_id,\n"
            "    owner_email: task.owner || task.assigned_to,\n"
            "    entity_type: 'invoice',\n"
            "  }\n"
            "}];\n"
        ),
        position=[1720, 300],
    ))

    # -- 13. Update Invoice Status --------------------------------------------
    nodes.append(supabase_update(
        name="Update Invoice",
        table="acct_invoices",
        match_col="id",
        position=[1980, 300],
    ))

    # -- 14. Prepare Bill Update ----------------------------------------------
    nodes.append(code_node(
        name="Prepare Bill Update",
        js_code=(
            "const task = $input.first().json;\n"
            "const action = $('Extract Approve Params').first()?.json?.action\n"
            "  || $('Extract Reject Params').first()?.json?.action\n"
            "  || 'approve';\n"
            "const newStatus = action === 'approve' ? 'approved' : 'rejected';\n"
            "\n"
            "return [{\n"
            "  json: {\n"
            "    id: task.entity_id,\n"
            "    updatePayload: { status: newStatus, updated_at: new Date().toISOString() },\n"
            "    task_id: task.id,\n"
            "    task_type: task.task_type,\n"
            "    approval_action: action,\n"
            "    new_status: newStatus,\n"
            "    client_id: task.client_id,\n"
            "    owner_email: task.owner || task.assigned_to,\n"
            "    entity_type: 'bill',\n"
            "  }\n"
            "}];\n"
        ),
        position=[1720, 500],
    ))

    # -- 15. Update Bill Status -----------------------------------------------
    nodes.append(supabase_update(
        name="Update Bill",
        table="acct_supplier_bills",
        match_col="id",
        position=[1980, 500],
    ))

    # -- 16. Prepare Reconciliation Update ------------------------------------
    nodes.append(code_node(
        name="Prepare Reconciliation Update",
        js_code=(
            "const task = $input.first().json;\n"
            "const action = $('Extract Approve Params').first()?.json?.action\n"
            "  || $('Extract Reject Params').first()?.json?.action\n"
            "  || 'approve';\n"
            "const newStatus = action === 'approve' ? 'reconciled' : 'disputed';\n"
            "\n"
            "return [{\n"
            "  json: {\n"
            "    id: task.entity_id,\n"
            "    updatePayload: { reconciliation_status: newStatus, updated_at: new Date().toISOString() },\n"
            "    task_id: task.id,\n"
            "    task_type: task.task_type,\n"
            "    approval_action: action,\n"
            "    new_status: newStatus,\n"
            "    client_id: task.client_id,\n"
            "    owner_email: task.owner || task.assigned_to,\n"
            "    entity_type: 'payment',\n"
            "  }\n"
            "}];\n"
        ),
        position=[1720, 700],
    ))

    # -- 17. Update Payment Reconciliation ------------------------------------
    nodes.append(supabase_update(
        name="Update Payment",
        table="acct_payments",
        match_col="id",
        position=[1980, 700],
    ))

    # -- 18. Mark Task Completed ----------------------------------------------
    nodes.append(code_node(
        name="Mark Task Completed",
        js_code=(
            "const item = $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    id: item.task_id,\n"
            "    updatePayload: {\n"
            "      status: 'completed',\n"
            "      approval_action: item.approval_action,\n"
            "      resolved_by: 'email_link',\n"
            "      resolved_at: new Date().toISOString(),\n"
            "      updated_at: new Date().toISOString(),\n"
            "    },\n"
            "    client_id: item.client_id,\n"
            "    owner_email: item.owner_email,\n"
            "    task_type: item.task_type,\n"
            "    approval_action: item.approval_action,\n"
            "    new_status: item.new_status,\n"
            "    entity_type: item.entity_type,\n"
            "  }\n"
            "}];\n"
        ),
        position=[2240, 500],
    ))

    # -- 19. Update Task Status -----------------------------------------------
    nodes.append(supabase_update(
        name="Update Task",
        table="acct_tasks",
        match_col="id",
        position=[2500, 500],
    ))

    # -- 20. Send Confirmation Email ------------------------------------------
    nodes.append(gmail_send(
        name="Send Confirmation Email",
        to_expr="={{ $json.owner_email }}",
        subject_expr="=Approval {{ $json.approval_action }}: {{ $json.task_type }} ({{ $json.entity_type }})",
        html_expr=(
            "=<p>The {{ $json.task_type }} task has been <strong>{{ $json.approval_action }}d</strong>.</p>"
            "<p>Entity: {{ $json.entity_type }} | New status: {{ $json.new_status }}</p>"
            "<p>Resolved at: {{ $json.resolved_at || new Date().toISOString() }}</p>"
            "<p style=\"color:#888\">This is an automated notification from AnyVision Media Accounting.</p>"
        ),
        cred=CRED_GMAIL,
        position=[2760, 500],
    ))

    # -- 21. Audit Log & Status Webhooks --------------------------------------
    nodes.append(code_node(
        name="Audit + Status Prep",
        js_code=(
            "const item = $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    client_id: item.client_id,\n"
            "    event_type: 'TASK_COMPLETED',\n"
            "    entity_type: item.entity_type,\n"
            "    entity_id: item.id,\n"
            "    action: 'task_completed',\n"
            "    actor: 'email_link',\n"
            "    result: 'success',\n"
            "    metadata: {\n"
            "      source: 'n8n',\n"
            "      task_type: item.task_type,\n"
            "      approval_action: item.approval_action,\n"
            "    }\n"
            "  }\n"
            "}];\n"
        ),
        position=[3020, 400],
    ))

    nodes.append(supabase_insert(
        name="Audit Log Insert",
        table="acct_audit_log",
        position=[3280, 400],
        return_rep=False,
    ))

    nodes.append(portal_status_webhook(
        name="Status: task_completed",
        action="task_completed",
        position=[3280, 600],
    ))

    # -- 22. HTML Confirmation Page -------------------------------------------
    nodes.append(code_node(
        name="Build HTML Confirmation",
        js_code=(
            "const item = $('Mark Task Completed').first().json;\n"
            "const action = item.approval_action || 'processed';\n"
            "const color = action === 'approve' ? '#38a169' : '#e53e3e';\n"
            "const label = action === 'approve' ? 'Approved' : 'Rejected';\n"
            "\n"
            "return [{\n"
            "  json: {\n"
            "    success: true,\n"
            "    html: '<html><body style=\"font-family:sans-serif;text-align:center;padding:60px\">'\n"
            "      + '<h1 style=\"color:' + color + '\">' + label + '</h1>'\n"
            "      + '<p>The ' + (item.task_type || 'task') + ' has been <strong>' + action + 'd</strong>.</p>'\n"
            "      + '<p style=\"color:#888\">You can close this window.</p>'\n"
            "      + '</body></html>',\n"
            "  }\n"
            "}];\n"
        ),
        position=[3540, 500],
    ))

    # -- Respond Webhook nodes ------------------------------------------------
    nodes.append(respond_webhook(
        name="Respond Success",
        position=[3800, 500],
    ))

    nodes.append(respond_webhook(
        name="Respond Not Found",
        position=[1460, 650],
    ))

    nodes.append(respond_webhook(
        name="Respond Already Resolved",
        position=[1720, 200],
    ))

    return nodes


# ============================================================================
# CONNECTIONS
# ============================================================================

def build_connections() -> dict[str, Any]:
    """Build connections for the Approval Engine workflow."""
    return {
        # -- Triggers --
        "Approve Webhook": {"main": [[conn("Extract Approve Params")]]},
        "Reject Webhook": {"main": [[conn("Extract Reject Params")]]},
        "Manual Trigger": {"main": [[conn("Extract Approve Params")]]},

        # -- Merge both paths into lookup --
        "Extract Approve Params": {"main": [[conn("Lookup Task")]]},
        "Extract Reject Params": {"main": [[conn("Lookup Task")]]},

        # -- Task validation --
        "Lookup Task": {"main": [[conn("Task Found?")]]},
        "Task Found?": {
            "main": [
                [conn("Already Resolved?")],   # true (found)
                [conn("Not Found Response")],  # false (not found)
            ],
        },
        "Not Found Response": {"main": [[conn("Respond Not Found")]]},
        "Already Resolved?": {
            "main": [
                [conn("Already Resolved Response")],  # true (not open)
                [conn("Task Type Switch")],            # false (still open)
            ],
        },
        "Already Resolved Response": {"main": [[conn("Respond Already Resolved")]]},

        # -- Route by task type --
        "Task Type Switch": {
            "main": [
                [conn("Prepare Invoice Update")],          # invoice
                [conn("Prepare Bill Update")],              # bill
                [conn("Prepare Reconciliation Update")],    # reconciliation
                [conn("Mark Task Completed")],              # fallback
            ],
        },

        # -- Invoice path --
        "Prepare Invoice Update": {"main": [[conn("Update Invoice")]]},
        "Update Invoice": {"main": [[conn("Mark Task Completed")]]},

        # -- Bill path --
        "Prepare Bill Update": {"main": [[conn("Update Bill")]]},
        "Update Bill": {"main": [[conn("Mark Task Completed")]]},

        # -- Reconciliation path --
        "Prepare Reconciliation Update": {"main": [[conn("Update Payment")]]},
        "Update Payment": {"main": [[conn("Mark Task Completed")]]},

        # -- Common completion path --
        "Mark Task Completed": {"main": [[conn("Update Task")]]},
        "Update Task": {"main": [[conn("Send Confirmation Email")]]},
        "Send Confirmation Email": {"main": [[conn("Audit + Status Prep")]]},
        "Audit + Status Prep": {
            "main": [[
                conn("Audit Log Insert"),
                conn("Status: task_completed"),
            ]],
        },
        "Audit Log Insert": {"main": [[conn("Build HTML Confirmation")]]},
        "Build HTML Confirmation": {"main": [[conn("Respond Success")]]},
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
        description="ACCT-08 Approval Engine -- Builder & Deployer",
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
    print("ACCT-08  APPROVAL ENGINE")
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
    print("Webhooks:")
    print("  GET /accounting/approve?token=xxx  -- approve via email link")
    print("  GET /accounting/reject?token=xxx   -- reject via email link")
    print("  Manual trigger for testing")
    print()
    print("Next steps:")
    print("  1. Ensure Supabase tables: acct_tasks, acct_invoices, acct_supplier_bills, acct_payments, acct_audit_log")
    print("  2. Tasks must have approval_token, task_type, entity_id, owner/assigned_to")
    print("  3. Configure Gmail credential for confirmation emails")
    print("  4. Test: GET /accounting/approve?token=<valid-token>")


if __name__ == "__main__":
    main()

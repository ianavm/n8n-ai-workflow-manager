"""
Plug-and-Play Accounting -- WF07 Supplier Payments

Processes approved supplier bills: groups by supplier, generates
remittance advice, records payment in accounting software, updates
bill status, emails remittance, and logs the audit trail.

Usage:
    python tools/deploy_acct_v2_wf07.py build
    python tools/deploy_acct_v2_wf07.py deploy
    python tools/deploy_acct_v2_wf07.py activate
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
    if_node,
    manual_trigger,
    noop_node,
    portal_status_webhook,
    respond_webhook,
    schedule_trigger,
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

WORKFLOW_NAME = "ACCT-07 Supplier Payments"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "accounting-v2"
OUTPUT_FILENAME = "wf07_supplier_payments.json"


# ============================================================================
# NODE BUILDERS
# ============================================================================

def build_nodes() -> list[dict[str, Any]]:
    """Build ~22 nodes for the Supplier Payments workflow."""
    nodes: list[dict[str, Any]] = []

    # -- 1. Webhook Trigger ---------------------------------------------------
    nodes.append(webhook_trigger(
        name="Pay Supplier Webhook",
        path="accounting/pay-supplier",
        position=[200, 300],
    ))

    # -- 2. Schedule Trigger (daily 10:00 M-F) --------------------------------
    nodes.append(schedule_trigger(
        name="Daily Payment Run",
        cron="0 10 * * 1-5",
        position=[200, 0],
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
            "    accounting_software: body.accounting_software || 'none',\n"
            "    payment_method: body.payment_method || 'eft',\n"
            "    owner_email: body.owner_email || $env.ACCT_OWNER_EMAIL || 'ian@anyvisionmedia.com',\n"
            "    run_date: new Date().toISOString().slice(0, 10),\n"
            "  }\n"
            "}];\n"
        ),
        position=[460, 300],
    ))

    # -- 5. Fetch Approved Unpaid Bills ---------------------------------------
    nodes.append(supabase_select(
        name="Fetch Approved Bills",
        table="acct_supplier_bills",
        select="*,acct_suppliers(legal_name,email)",
        filters="={{ 'status=eq.approved&payment_status=eq.unpaid&client_id=eq.' + $json.client_id }}",
        position=[720, 300],
    ))

    # -- 6. Has Bills? --------------------------------------------------------
    nodes.append(if_node(
        name="Has Bills?",
        left_value="={{ $json.length }}",
        operator_type="number",
        operation="gt",
        right_value="0",
        position=[960, 300],
    ))

    # -- 7. No Bills -- respond -----------------------------------------------
    nodes.append(code_node(
        name="No Bills Response",
        js_code=(
            "return [{\n"
            "  json: {\n"
            "    success: true,\n"
            "    message: 'No approved unpaid bills found',\n"
            "    bills_processed: 0,\n"
            "  }\n"
            "}];\n"
        ),
        position=[1200, 500],
    ))

    # -- 8. Group by Supplier -------------------------------------------------
    nodes.append(code_node(
        name="Group by Supplier",
        js_code=(
            "const bills = $input.all().map(i => i.json);\n"
            "const config = $('Load Config').first().json;\n"
            "const groups = {};\n"
            "\n"
            "for (const bill of bills) {\n"
            "  const sid = bill.supplier_id;\n"
            "  if (!groups[sid]) {\n"
            "    groups[sid] = {\n"
            "      supplier_id: sid,\n"
            "      supplier_name: bill.acct_suppliers?.legal_name || 'Unknown',\n"
            "      supplier_email: bill.acct_suppliers?.email || null,\n"
            "      bills: [],\n"
            "      total: 0,\n"
            "      client_id: config.client_id,\n"
            "      accounting_software: config.accounting_software,\n"
            "      payment_method: config.payment_method,\n"
            "      owner_email: config.owner_email,\n"
            "      run_date: config.run_date,\n"
            "    };\n"
            "  }\n"
            "  groups[sid].bills.push({\n"
            "    id: bill.id,\n"
            "    bill_number: bill.bill_number,\n"
            "    amount: Number(bill.amount_due || bill.total_amount || 0),\n"
            "    due_date: bill.due_date,\n"
            "    description: bill.description || bill.bill_number,\n"
            "  });\n"
            "  groups[sid].total += Number(bill.amount_due || bill.total_amount || 0);\n"
            "}\n"
            "\n"
            "return Object.values(groups).map(g => ({\n"
            "  json: { ...g, total: Math.round(g.total * 100) / 100 }\n"
            "}));\n"
        ),
        position=[1200, 200],
    ))

    # -- 9. Generate Remittance Advice ----------------------------------------
    nodes.append(code_node(
        name="Generate Remittance",
        js_code=(
            "const g = $input.first().json;\n"
            "const rows = g.bills.map(b =>\n"
            "  `<tr><td>${b.bill_number}</td><td>${b.description}</td>`\n"
            "  + `<td>${b.due_date || '-'}</td><td style=\"text-align:right\">R ${b.amount.toFixed(2)}</td></tr>`\n"
            ").join('\\n');\n"
            "\n"
            "const html = `\n"
            "<h2>Remittance Advice</h2>\n"
            "<p>Dear ${g.supplier_name},</p>\n"
            "<p>Please find below the details of payment processed on ${g.run_date}:</p>\n"
            "<table border=\"1\" cellpadding=\"6\" cellspacing=\"0\" style=\"border-collapse:collapse\">\n"
            "<tr style=\"background:#f0f0f0\">\n"
            "  <th>Bill #</th><th>Description</th><th>Due Date</th><th>Amount</th>\n"
            "</tr>\n"
            "${rows}\n"
            "<tr style=\"font-weight:bold\">\n"
            "  <td colspan=\"3\">Total</td><td style=\"text-align:right\">R ${g.total.toFixed(2)}</td>\n"
            "</tr>\n"
            "</table>\n"
            "<p>Payment method: ${g.payment_method.toUpperCase()}</p>\n"
            "<p>Kind regards,<br/>AnyVision Media Accounting</p>\n"
            "`;\n"
            "\n"
            "return [{ json: { ...g, remittance_html: html } }];\n"
        ),
        position=[1460, 200],
    ))

    # -- 10. Acct Software Switch ---------------------------------------------
    nodes.append(switch_node(
        name="Acct Software Switch",
        rules=[
            {"leftValue": "={{ $json.accounting_software || 'none' }}", "rightValue": "quickbooks", "output": "quickbooks"},
            {"leftValue": "={{ $json.accounting_software || 'none' }}", "rightValue": "xero", "output": "xero"},
        ],
        position=[1720, 200],
    ))

    # -- 11. Record Payment in QB (placeholder) -------------------------------
    nodes.append(code_node(
        name="Record Payment QB",
        js_code=(
            "// Placeholder: POST bill-payment to QuickBooks/Xero\n"
            "const g = $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    ...g,\n"
            "    external_payment_id: 'placeholder_' + Date.now(),\n"
            "    sync_status: 'pending_implementation',\n"
            "  }\n"
            "}];\n"
        ),
        position=[1980, 100],
    ))

    # -- 12. Skip Sync --------------------------------------------------------
    nodes.append(noop_node(
        name="Skip Sync",
        position=[1980, 400],
    ))

    # -- 13. Update Bills Paid (loop via Code) --------------------------------
    nodes.append(code_node(
        name="Update Bills Paid",
        js_code=(
            "const g = $input.first().json;\n"
            "const today = new Date().toISOString();\n"
            "\n"
            "// Emit one item per bill so downstream Supabase update processes each\n"
            "return g.bills.map(b => ({\n"
            "  json: {\n"
            "    id: b.id,\n"
            "    updatePayload: {\n"
            "      payment_status: 'paid',\n"
            "      payment_date: today,\n"
            "      updated_at: today,\n"
            "    },\n"
            "    client_id: g.client_id,\n"
            "    supplier_id: g.supplier_id,\n"
            "    supplier_name: g.supplier_name,\n"
            "    supplier_email: g.supplier_email,\n"
            "    remittance_html: g.remittance_html,\n"
            "    total: g.total,\n"
            "    owner_email: g.owner_email,\n"
            "    bill_count: g.bills.length,\n"
            "  }\n"
            "}));\n"
        ),
        position=[2240, 200],
    ))

    # -- 14. Patch Bill Status ------------------------------------------------
    nodes.append(supabase_update(
        name="Patch Bill Status",
        table="acct_supplier_bills",
        match_col="id",
        position=[2500, 200],
    ))

    # -- 15. Send Remittance Email --------------------------------------------
    from acct_helpers import gmail_send
    nodes.append(gmail_send(
        name="Send Remittance Email",
        to_expr="={{ $json.supplier_email }}",
        subject_expr="=Remittance Advice — {{ $json.supplier_name }} — {{ $json.total }}",
        html_expr="={{ $json.remittance_html }}",
        cred=CRED_GMAIL,
        position=[2760, 200],
    ))

    # -- 16. Audit Log Prep ---------------------------------------------------
    nodes.append(code_node(
        name="Audit Log Prep",
        js_code=(
            "const item = $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    client_id: item.client_id,\n"
            "    event_type: 'BILL_PAID',\n"
            "    entity_type: 'supplier_bill',\n"
            "    entity_id: item.supplier_id,\n"
            "    action: 'bill_paid',\n"
            "    actor: 'n8n-wf07',\n"
            "    result: 'success',\n"
            "    metadata: {\n"
            "      source: 'n8n',\n"
            "      supplier_name: item.supplier_name,\n"
            "      bill_count: item.bill_count,\n"
            "      total: item.total,\n"
            "    }\n"
            "  }\n"
            "}];\n"
        ),
        position=[3020, 200],
    ))

    # -- 17. Audit Log Insert -------------------------------------------------
    nodes.append(supabase_insert(
        name="Audit Log Insert",
        table="acct_audit_log",
        position=[3280, 200],
        return_rep=False,
    ))

    # -- 18. Status Webhook: bill_updated -------------------------------------
    nodes.append(portal_status_webhook(
        name="Status Webhook",
        action="bill_updated",
        position=[3540, 200],
    ))

    # -- 19. Respond Webhook (success) ----------------------------------------
    nodes.append(code_node(
        name="Build Response",
        js_code=(
            "const items = $('Group by Supplier').all();\n"
            "const totalPaid = items.reduce((s, i) => s + (i.json.total || 0), 0);\n"
            "return [{\n"
            "  json: {\n"
            "    success: true,\n"
            "    message: 'Supplier payments processed',\n"
            "    suppliers_paid: items.length,\n"
            "    total_paid: Math.round(totalPaid * 100) / 100,\n"
            "  }\n"
            "}];\n"
        ),
        position=[3800, 300],
    ))

    # -- 20. Respond Webhook Node ---------------------------------------------
    nodes.append(respond_webhook(
        name="Respond Webhook",
        position=[4060, 300],
    ))

    # -- 21. Respond No Bills Webhook -----------------------------------------
    nodes.append(respond_webhook(
        name="Respond No Bills",
        position=[1460, 500],
    ))

    return nodes


# ============================================================================
# CONNECTIONS
# ============================================================================

def build_connections() -> dict[str, Any]:
    """Build connections for the Supplier Payments workflow."""
    return {
        # -- Triggers to Load Config --
        "Pay Supplier Webhook": {"main": [[conn("Load Config")]]},
        "Daily Payment Run": {"main": [[conn("Load Config")]]},
        "Manual Trigger": {"main": [[conn("Load Config")]]},

        # -- Main flow --
        "Load Config": {"main": [[conn("Fetch Approved Bills")]]},
        "Fetch Approved Bills": {"main": [[conn("Has Bills?")]]},
        "Has Bills?": {
            "main": [
                [conn("Group by Supplier")],   # true
                [conn("No Bills Response")],   # false
            ],
        },
        "No Bills Response": {"main": [[conn("Respond No Bills")]]},

        "Group by Supplier": {"main": [[conn("Generate Remittance")]]},
        "Generate Remittance": {"main": [[conn("Acct Software Switch")]]},
        "Acct Software Switch": {
            "main": [
                [conn("Record Payment QB")],   # quickbooks
                [conn("Record Payment QB")],   # xero (same placeholder)
                [conn("Skip Sync")],           # fallback (none)
            ],
        },
        "Record Payment QB": {"main": [[conn("Update Bills Paid")]]},
        "Skip Sync": {"main": [[conn("Update Bills Paid")]]},

        "Update Bills Paid": {"main": [[conn("Patch Bill Status")]]},
        "Patch Bill Status": {"main": [[conn("Send Remittance Email")]]},
        "Send Remittance Email": {"main": [[conn("Audit Log Prep")]]},
        "Audit Log Prep": {"main": [[conn("Audit Log Insert")]]},
        "Audit Log Insert": {"main": [[conn("Status Webhook")]]},
        "Status Webhook": {"main": [[conn("Build Response")]]},
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
        description="ACCT-07 Supplier Payments -- Builder & Deployer",
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
    print("ACCT-07  SUPPLIER PAYMENTS")
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
    print("  POST /accounting/pay-supplier  -- webhook trigger")
    print("  Schedule: daily 10:00 Mon-Fri")
    print("  Manual trigger for testing")
    print()
    print("Next steps:")
    print("  1. Ensure Supabase tables exist: acct_supplier_bills, acct_suppliers, acct_audit_log")
    print("  2. Configure Gmail credential for remittance emails")
    print("  3. Replace placeholder accounting-software payment recording nodes")
    print("  4. Test: POST to /accounting/pay-supplier with {client_id}")


if __name__ == "__main__":
    main()

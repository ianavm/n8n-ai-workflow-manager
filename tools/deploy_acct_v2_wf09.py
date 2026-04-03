"""
Plug-and-Play Accounting -- WF09 Reporting & Month-End

Generates a management pack: calls five Supabase RPCs (aged
receivables, aged payables, cashflow summary, reconciliation
stats, dashboard KPIs), aggregates them, generates an AI summary
via OpenRouter, builds an HTML management pack email, and sends
it to the owner + finance team.

Usage:
    python tools/deploy_acct_v2_wf09.py build
    python tools/deploy_acct_v2_wf09.py deploy
    python tools/deploy_acct_v2_wf09.py activate
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
    manual_trigger,
    openrouter_ai,
    portal_status_webhook,
    respond_webhook,
    schedule_trigger,
    supabase_insert,
    supabase_rpc,
    uid,
    webhook_trigger,
)
from credentials import CREDENTIALS

CRED_GMAIL = CREDENTIALS["gmail"]
CRED_OPENROUTER = CREDENTIALS["openrouter"]

# -- Constants ---------------------------------------------------------------

WORKFLOW_NAME = "ACCT-09 Reporting & Month-End"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "accounting-v2"
OUTPUT_FILENAME = "wf09_reporting.json"


# ============================================================================
# NODE BUILDERS
# ============================================================================

def build_nodes() -> list[dict[str, Any]]:
    """Build ~24 nodes for the Reporting & Month-End workflow."""
    nodes: list[dict[str, Any]] = []

    # -- 1. Schedule Trigger (last biz day 08:00) -----------------------------
    nodes.append(schedule_trigger(
        name="Month-End Schedule",
        cron="0 8 28-31 * *",
        position=[200, 0],
    ))

    # -- 2. Webhook Trigger ---------------------------------------------------
    nodes.append(webhook_trigger(
        name="Report Webhook",
        path="accounting/generate-report",
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
            "    owner_email: body.owner_email || $env.ACCT_OWNER_EMAIL || 'ian@anyvisionmedia.com',\n"
            "    finance_team: body.finance_team || $env.ACCT_FINANCE_TEAM || '',\n"
            "    months: body.months || 6,\n"
            "    report_date: new Date().toISOString().slice(0, 10),\n"
            "  }\n"
            "}];\n"
        ),
        position=[460, 300],
    ))

    # -- 5. RPC: Aged Receivables ---------------------------------------------
    nodes.append(code_node(
        name="Prep AR RPC",
        js_code=(
            "return [{ json: { p_client_id: $json.client_id } }];\n"
        ),
        position=[720, 100],
    ))
    nodes.append(supabase_rpc(
        name="RPC Aged Receivables",
        function_name="acct_get_aged_receivables",
        position=[980, 100],
    ))

    # -- 6. RPC: Aged Payables ------------------------------------------------
    nodes.append(code_node(
        name="Prep AP RPC",
        js_code=(
            "const config = $('Load Config').first().json;\n"
            "return [{ json: { p_client_id: config.client_id } }];\n"
        ),
        position=[720, 250],
    ))
    nodes.append(supabase_rpc(
        name="RPC Aged Payables",
        function_name="acct_get_aged_payables",
        position=[980, 250],
    ))

    # -- 7. RPC: Cashflow Summary ---------------------------------------------
    nodes.append(code_node(
        name="Prep Cashflow RPC",
        js_code=(
            "const config = $('Load Config').first().json;\n"
            "return [{ json: { p_client_id: config.client_id, p_months: config.months } }];\n"
        ),
        position=[720, 400],
    ))
    nodes.append(supabase_rpc(
        name="RPC Cashflow Summary",
        function_name="acct_get_cashflow_summary",
        position=[980, 400],
    ))

    # -- 8. RPC: Reconciliation Stats -----------------------------------------
    nodes.append(code_node(
        name="Prep Recon RPC",
        js_code=(
            "const config = $('Load Config').first().json;\n"
            "return [{ json: { p_client_id: config.client_id } }];\n"
        ),
        position=[720, 550],
    ))
    nodes.append(supabase_rpc(
        name="RPC Reconciliation Stats",
        function_name="acct_get_reconciliation_stats",
        position=[980, 550],
    ))

    # -- 9. RPC: Dashboard KPIs -----------------------------------------------
    nodes.append(code_node(
        name="Prep KPI RPC",
        js_code=(
            "const config = $('Load Config').first().json;\n"
            "return [{ json: { p_client_id: config.client_id } }];\n"
        ),
        position=[720, 700],
    ))
    nodes.append(supabase_rpc(
        name="RPC Dashboard KPIs",
        function_name="acct_get_dashboard_kpis",
        position=[980, 700],
    ))

    # -- 10. Aggregate All Data -----------------------------------------------
    nodes.append(code_node(
        name="Aggregate Report Data",
        js_code=(
            "const config = $('Load Config').first().json;\n"
            "const ar = $('RPC Aged Receivables').first().json;\n"
            "const ap = $('RPC Aged Payables').first().json;\n"
            "const cashflow = $('RPC Cashflow Summary').first().json;\n"
            "const recon = $('RPC Reconciliation Stats').first().json;\n"
            "const kpis = $('RPC Dashboard KPIs').first().json;\n"
            "\n"
            "// Build a text summary for AI\n"
            "const prompt = [\n"
            "  'Generate a concise management summary for month-end report.',\n"
            "  'Date: ' + config.report_date,\n"
            "  '',\n"
            "  'AGED RECEIVABLES:', JSON.stringify(ar, null, 2),\n"
            "  '',\n"
            "  'AGED PAYABLES:', JSON.stringify(ap, null, 2),\n"
            "  '',\n"
            "  'CASHFLOW (last ' + config.months + ' months):', JSON.stringify(cashflow, null, 2),\n"
            "  '',\n"
            "  'RECONCILIATION:', JSON.stringify(recon, null, 2),\n"
            "  '',\n"
            "  'KPIs:', JSON.stringify(kpis, null, 2),\n"
            "  '',\n"
            "  'Provide: executive summary (3-4 sentences), key highlights, concerns, recommendations.',\n"
            "  'Use ZAR currency. Be specific with numbers.',\n"
            "].join('\\n');\n"
            "\n"
            "return [{\n"
            "  json: {\n"
            "    ...config,\n"
            "    ar, ap, cashflow, recon, kpis,\n"
            "    aiPrompt: prompt,\n"
            "  }\n"
            "}];\n"
        ),
        position=[1240, 400],
    ))

    # -- 11. AI Summary -------------------------------------------------------
    nodes.append(openrouter_ai(
        name="AI Management Summary",
        system_prompt=(
            "You are a South African chartered accountant preparing a month-end management pack. "
            "Write in professional business English. Use ZAR currency. Be concise and data-driven."
        ),
        user_prompt_expr="Generate management summary from the financial data provided.",
        max_tokens=2000,
        cred=CRED_OPENROUTER,
        position=[1500, 400],
    ))

    # -- 12. Build Management Pack HTML ---------------------------------------
    nodes.append(code_node(
        name="Build Management Pack",
        js_code=(
            "const data = $('Aggregate Report Data').first().json;\n"
            "const aiRaw = $input.first().json;\n"
            "const aiSummary = aiRaw.choices?.[0]?.message?.content || 'AI summary unavailable.';\n"
            "\n"
            "const fmt = (v) => {\n"
            "  const n = Number(v) || 0;\n"
            "  return 'R ' + n.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2});\n"
            "};\n"
            "\n"
            "const kpis = data.kpis || {};\n"
            "const recon = data.recon || {};\n"
            "\n"
            "const html = `\n"
            "<div style=\"font-family:sans-serif;max-width:700px;margin:0 auto\">\n"
            "  <h1 style=\"color:#FF6D5A\">Management Pack — ${data.report_date}</h1>\n"
            "  <hr/>\n"
            "\n"
            "  <h2>Executive Summary</h2>\n"
            "  <div style=\"background:#f9f9f9;padding:16px;border-radius:8px;white-space:pre-wrap\">${aiSummary}</div>\n"
            "\n"
            "  <h2>Key Performance Indicators</h2>\n"
            "  <table border=\"1\" cellpadding=\"8\" cellspacing=\"0\" style=\"border-collapse:collapse;width:100%\">\n"
            "    <tr style=\"background:#f0f0f0\"><th>Metric</th><th>Value</th></tr>\n"
            "    <tr><td>Total Receivables</td><td>${fmt(kpis.total_receivables)}</td></tr>\n"
            "    <tr><td>Total Payables</td><td>${fmt(kpis.total_payables)}</td></tr>\n"
            "    <tr><td>Net Position</td><td>${fmt((kpis.total_receivables || 0) - (kpis.total_payables || 0))}</td></tr>\n"
            "    <tr><td>Overdue Invoices</td><td>${kpis.overdue_invoices || 0}</td></tr>\n"
            "    <tr><td>Overdue Bills</td><td>${kpis.overdue_bills || 0}</td></tr>\n"
            "    <tr><td>Reconciliation Rate</td><td>${recon.reconciliation_rate || 'N/A'}%</td></tr>\n"
            "  </table>\n"
            "\n"
            "  <h2>Aged Receivables</h2>\n"
            "  <pre style=\"background:#f9f9f9;padding:12px;border-radius:4px\">${JSON.stringify(data.ar, null, 2)}</pre>\n"
            "\n"
            "  <h2>Aged Payables</h2>\n"
            "  <pre style=\"background:#f9f9f9;padding:12px;border-radius:4px\">${JSON.stringify(data.ap, null, 2)}</pre>\n"
            "\n"
            "  <h2>Cashflow Summary (${data.months} months)</h2>\n"
            "  <pre style=\"background:#f9f9f9;padding:12px;border-radius:4px\">${JSON.stringify(data.cashflow, null, 2)}</pre>\n"
            "\n"
            "  <p style=\"color:#888;font-size:12px\">Generated by AnyVision Media Accounting on ${new Date().toISOString()}</p>\n"
            "</div>\n"
            "`;\n"
            "\n"
            "const recipients = [data.owner_email, data.finance_team].filter(Boolean).join(', ');\n"
            "\n"
            "return [{\n"
            "  json: {\n"
            "    to: recipients,\n"
            "    subject: 'Management Pack — ' + data.report_date,\n"
            "    html: html,\n"
            "    client_id: data.client_id,\n"
            "    report_date: data.report_date,\n"
            "  }\n"
            "}];\n"
        ),
        position=[1760, 400],
    ))

    # -- 13. Send Management Pack Email ---------------------------------------
    nodes.append(gmail_send(
        name="Send Management Pack",
        to_expr="={{ $json.to }}",
        subject_expr="={{ $json.subject }}",
        html_expr="={{ $json.html }}",
        cred=CRED_GMAIL,
        position=[2020, 400],
    ))

    # -- 14. Audit Log Prep ---------------------------------------------------
    nodes.append(code_node(
        name="Audit Log Prep",
        js_code=(
            "const item = $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    client_id: item.client_id || $('Load Config').first().json.client_id,\n"
            "    event_type: 'REPORT_GENERATED',\n"
            "    entity_type: 'report',\n"
            "    entity_id: 'mgmt_pack_' + (item.report_date || new Date().toISOString().slice(0, 10)),\n"
            "    action: 'report_generated',\n"
            "    actor: 'n8n-wf09',\n"
            "    result: 'success',\n"
            "    metadata: { source: 'n8n', report_date: item.report_date }\n"
            "  }\n"
            "}];\n"
        ),
        position=[2280, 400],
    ))

    # -- 15. Audit Log Insert -------------------------------------------------
    nodes.append(supabase_insert(
        name="Audit Log Insert",
        table="acct_audit_log",
        position=[2540, 400],
        return_rep=False,
    ))

    # -- 16. Status Webhook: report_generated ---------------------------------
    nodes.append(portal_status_webhook(
        name="Status: report_generated",
        action="report_generated",
        position=[2800, 400],
    ))

    # -- 17. Build Webhook Response -------------------------------------------
    nodes.append(code_node(
        name="Build Response",
        js_code=(
            "const config = $('Load Config').first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    success: true,\n"
            "    message: 'Management pack generated and sent',\n"
            "    report_date: config.report_date,\n"
            "    sent_to: config.owner_email,\n"
            "  }\n"
            "}];\n"
        ),
        position=[3060, 400],
    ))

    # -- 18. Respond Webhook --------------------------------------------------
    nodes.append(respond_webhook(
        name="Respond Webhook",
        position=[3320, 400],
    ))

    return nodes


# ============================================================================
# CONNECTIONS
# ============================================================================

def build_connections() -> dict[str, Any]:
    """Build connections for the Reporting & Month-End workflow."""
    return {
        # -- Triggers to Load Config --
        "Month-End Schedule": {"main": [[conn("Load Config")]]},
        "Report Webhook": {"main": [[conn("Load Config")]]},
        "Manual Trigger": {"main": [[conn("Load Config")]]},

        # -- Fan out to 5 RPC prep nodes --
        "Load Config": {
            "main": [[
                conn("Prep AR RPC"),
                conn("Prep AP RPC"),
                conn("Prep Cashflow RPC"),
                conn("Prep Recon RPC"),
                conn("Prep KPI RPC"),
            ]],
        },

        # -- RPC calls --
        "Prep AR RPC": {"main": [[conn("RPC Aged Receivables")]]},
        "Prep AP RPC": {"main": [[conn("RPC Aged Payables")]]},
        "Prep Cashflow RPC": {"main": [[conn("RPC Cashflow Summary")]]},
        "Prep Recon RPC": {"main": [[conn("RPC Reconciliation Stats")]]},
        "Prep KPI RPC": {"main": [[conn("RPC Dashboard KPIs")]]},

        # -- Aggregate (wait for all RPCs -- n8n will wait for all inputs) --
        "RPC Aged Receivables": {"main": [[conn("Aggregate Report Data")]]},
        "RPC Aged Payables": {"main": [[conn("Aggregate Report Data")]]},
        "RPC Cashflow Summary": {"main": [[conn("Aggregate Report Data")]]},
        "RPC Reconciliation Stats": {"main": [[conn("Aggregate Report Data")]]},
        "RPC Dashboard KPIs": {"main": [[conn("Aggregate Report Data")]]},

        # -- AI + Build + Send --
        "Aggregate Report Data": {"main": [[conn("AI Management Summary")]]},
        "AI Management Summary": {"main": [[conn("Build Management Pack")]]},
        "Build Management Pack": {"main": [[conn("Send Management Pack")]]},

        # -- Audit + Status + Response --
        "Send Management Pack": {"main": [[conn("Audit Log Prep")]]},
        "Audit Log Prep": {"main": [[conn("Audit Log Insert")]]},
        "Audit Log Insert": {"main": [[conn("Status: report_generated")]]},
        "Status: report_generated": {"main": [[conn("Build Response")]]},
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
        description="ACCT-09 Reporting & Month-End -- Builder & Deployer",
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
    print("ACCT-09  REPORTING & MONTH-END")
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
    print("  Schedule: 08:00 on days 28-31 of each month")
    print("  POST /accounting/generate-report  -- webhook trigger")
    print("  Manual trigger for testing")
    print()
    print("Supabase RPCs required:")
    print("  - acct_get_aged_receivables(p_client_id)")
    print("  - acct_get_aged_payables(p_client_id)")
    print("  - acct_get_cashflow_summary(p_client_id, p_months)")
    print("  - acct_get_reconciliation_stats(p_client_id)")
    print("  - acct_get_dashboard_kpis(p_client_id)")
    print()
    print("Next steps:")
    print("  1. Ensure Supabase RPCs are deployed")
    print("  2. Configure OpenRouter credential for AI summary")
    print("  3. Configure Gmail credential for management pack email")
    print("  4. Test: POST to /accounting/generate-report with {client_id}")


if __name__ == "__main__":
    main()

"""
FA-01: Client Intake & Onboarding

Webhook trigger that receives client intake form submissions,
creates records in Supabase, sends welcome email via Outlook,
notifies adviser via Teams, and schedules discovery meeting.

Usage:
    python tools/deploy_fa_wf01.py build
    python tools/deploy_fa_wf01.py deploy
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fa_helpers import (
    airtable_create_node,
    code_node,
    conn,
    execute_workflow_node,
    if_node,
    merge_node,
    outlook_send_node,
    respond_to_webhook_node,
    supabase_insert_node,
    supabase_query_node,
    supabase_update_node,
    teams_message_node,
    webhook_node,
    build_workflow,
)


FA_FIRM_ID = os.getenv("FA_FIRM_ID", "REPLACE_WITH_FIRM_UUID")
FA_02_WORKFLOW_ID = os.getenv("FA_02_WORKFLOW_ID", "REPLACE_WITH_FA02_ID")


def build_nodes() -> list[dict]:
    """Build all nodes for FA-01 Client Intake."""
    nodes = []

    # ── 1. Webhook Trigger ──────────────────────────────────
    nodes.append(webhook_node(
        "Intake Webhook",
        "advisory/intake",
        [0, 0],
    ))

    # ── 2. Validate Input ───────────────────────────────────
    nodes.append(code_node(
        "Validate Input",
        """
const body = $input.first().json.body || $input.first().json;
const errors = [];

if (!body.first_name) errors.push('first_name is required');
if (!body.last_name) errors.push('last_name is required');
if (!body.email) errors.push('email is required');
if (!body.phone && !body.mobile) errors.push('phone or mobile is required');
if (!body.consent_popia) errors.push('POPIA consent is required');

// Normalize phone to +27 format
let phone = body.phone || body.mobile || '';
if (phone.startsWith('0')) phone = '+27' + phone.substring(1);
phone = phone.replace(/[^+0-9]/g, '');

return [{
  json: {
    valid: errors.length === 0,
    errors,
    data: {
      ...body,
      phone: phone || null,
      mobile: body.mobile ? (body.mobile.startsWith('0') ? '+27' + body.mobile.substring(1) : body.mobile) : null,
      email: (body.email || '').toLowerCase().trim(),
    }
  }
}];
""",
        [300, 0],
    ))

    # ── 3. Check Validation ─────────────────────────────────
    nodes.append(if_node(
        "Is Valid",
        [{
            "leftValue": "={{ $json.valid }}",
            "rightValue": True,
            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
        }],
        [550, 0],
    ))

    # ── 4. Error Response ───────────────────────────────────
    nodes.append(respond_to_webhook_node(
        "Validation Error",
        '={"success": false, "errors": {{ JSON.stringify($json.errors) }}}',
        [550, 200],
        status_code=400,
    ))

    # ── 5. Check Existing Client ────────────────────────────
    nodes.append(supabase_query_node(
        "Check Existing Client",
        "fa_clients",
        f'email=eq.{{{{ $json.data.email }}}}&firm_id=eq.{FA_FIRM_ID}',
        [800, 0],
        select="id,email,pipeline_stage",
    ))

    # ── 6. Existing? ────────────────────────────────────────
    nodes.append(if_node(
        "Client Exists",
        [{
            "leftValue": "={{ $json.length }}",
            "rightValue": 0,
            "operator": {"type": "number", "operation": "gt"},
        }],
        [1050, 0],
    ))

    # ── 7. Create New Client ────────────────────────────────
    nodes.append(supabase_insert_node(
        "Create Client",
        "fa_clients",
        f"""={{{{
  JSON.stringify({{
    firm_id: '{FA_FIRM_ID}',
    first_name: $('Validate Input').first().json.data.first_name,
    last_name: $('Validate Input').first().json.data.last_name,
    email: $('Validate Input').first().json.data.email,
    phone: $('Validate Input').first().json.data.phone,
    mobile: $('Validate Input').first().json.data.mobile,
    title: $('Validate Input').first().json.data.title || null,
    id_number: $('Validate Input').first().json.data.id_number || null,
    date_of_birth: $('Validate Input').first().json.data.date_of_birth || null,
    employer: $('Validate Input').first().json.data.employer || null,
    occupation: $('Validate Input').first().json.data.occupation || null,
    source: $('Validate Input').first().json.data.source || 'intake_form',
    pipeline_stage: 'intake_complete',
    pipeline_updated_at: new Date().toISOString()
  }})
}}}}""",
        [1300, -100],
    ))

    # ── 8. Update Existing Client ───────────────────────────
    nodes.append(supabase_update_node(
        "Update Client",
        "fa_clients",
        "id",
        "={{ $('Check Existing Client').first().json[0].id }}",
        f"""={{{{
  JSON.stringify({{
    phone: $('Validate Input').first().json.data.phone,
    mobile: $('Validate Input').first().json.data.mobile,
    pipeline_stage: 'intake_complete',
    pipeline_updated_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }})
}}}}""",
        [1300, 100],
    ))

    # ── 9. Merge Paths ──────────────────────────────────────
    nodes.append(merge_node("Merge Client", [1550, 0]))

    # ── 10. Extract Client ID ───────────────────────────────
    nodes.append(code_node(
        "Extract Client ID",
        """
const items = $input.all();
// The first non-empty result from create or update
const record = items.find(i => i.json && (i.json.id || (Array.isArray(i.json) && i.json[0])));
let clientId, clientData;

if (record) {
  const data = Array.isArray(record.json) ? record.json[0] : record.json;
  clientId = data.id;
  clientData = data;
} else {
  clientId = 'unknown';
  clientData = {};
}

return [{json: {client_id: clientId, ...clientData}}];
""",
        [1800, 0],
    ))

    # ── 11. Record POPIA Consent ────────────────────────────
    nodes.append(supabase_insert_node(
        "Record POPIA Consent",
        "fa_consent_records",
        f"""={{{{
  JSON.stringify({{
    client_id: $json.client_id,
    firm_id: '{FA_FIRM_ID}',
    consent_type: 'popia_processing',
    granted: true,
    granted_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 24 * 30 * 24 * 60 * 60 * 1000).toISOString(),
    ip_address: $('Intake Webhook').first().json.headers?.['x-forwarded-for'] || 'unknown',
    method: 'electronic'
  }})
}}}}""",
        [2050, -200],
    ))

    # ── 12. Assign Adviser ──────────────────────────────────
    nodes.append(supabase_insert_node(
        "Assign Adviser",
        "fa_adviser_clients",
        f"""={{{{
  JSON.stringify({{
    adviser_id: $('Intake Webhook').first().json.body?.adviser_id || $('Intake Webhook').first().json.adviser_id || 'REPLACE_DEFAULT_ADVISER_ID',
    client_id: $('Extract Client ID').first().json.client_id,
    firm_id: '{FA_FIRM_ID}',
    role: 'primary'
  }})
}}}}""",
        [2050, 0],
    ))

    # ── 13. Airtable Pipeline Record ────────────────────────
    nodes.append(airtable_create_node(
        "Airtable Pipeline",
        os.getenv("FA_AIRTABLE_BASE_ID", "REPLACE"),
        os.getenv("FA_TABLE_PIPELINE", "REPLACE"),
        {
            "Client Name": "={{ $('Extract Client ID').first().json.first_name }} {{ $('Extract Client ID').first().json.last_name }}",
            "Email": "={{ $('Extract Client ID').first().json.email }}",
            "Phone": "={{ $('Extract Client ID').first().json.phone }}",
            "Pipeline Stage": "Intake Complete",
            "Source": "={{ $('Extract Client ID').first().json.source }}",
            "Supabase ID": "={{ $('Extract Client ID').first().json.client_id }}",
        },
        [2050, 200],
    ))

    # ── 14. Send Welcome Email ──────────────────────────────
    nodes.append(outlook_send_node(
        "Send Welcome Email",
        "={{ $('Extract Client ID').first().json.email }}",
        "=Welcome to our advisory firm - Your Financial Advisory Journey",
        """={{ (function() {
  const name = $('Extract Client ID').first().json.first_name;
  return `<h2>Welcome, ${name}!</h2>
  <p>Thank you for choosing us as your financial adviser. Your dedicated adviser will be in touch shortly to schedule your discovery meeting.</p>
  <p>In the meantime, you can access your client portal to view your profile and track your advisory journey.</p>
  <p><a href="${'https://portal.anyvisionmedia.com'}/portal/advisory/dashboard" style="display:inline-block;background:#6C63FF;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;">Access Your Portal</a></p>
  <p>We look forward to helping you achieve your financial goals.</p>`;
})() }}""",
        [2300, -200],
    ))

    # ── 15. Notify Adviser via Teams ────────────────────────
    nodes.append(teams_message_node(
        "Notify Adviser",
        os.getenv("FA_TEAMS_CHAT_ID", "REPLACE_CHAT_ID"),
        """={{ `<b>New Client Intake</b><br>
<b>Name:</b> ${$('Extract Client ID').first().json.first_name} ${$('Extract Client ID').first().json.last_name}<br>
<b>Email:</b> ${$('Extract Client ID').first().json.email}<br>
<b>Phone:</b> ${$('Extract Client ID').first().json.phone || 'N/A'}<br>
<b>Source:</b> ${$('Extract Client ID').first().json.source || 'intake_form'}<br>
<br>Discovery meeting scheduling in progress.` }}""",
        [2300, 0],
    ))

    # ── 16. Log Communication ───────────────────────────────
    nodes.append(supabase_insert_node(
        "Log Welcome Email",
        "fa_communications",
        f"""={{{{
  JSON.stringify({{
    client_id: $('Extract Client ID').first().json.client_id,
    firm_id: '{FA_FIRM_ID}',
    channel: 'email',
    direction: 'outbound',
    subject: 'Welcome Email',
    content: 'Welcome email sent after intake form submission',
    status: 'sent',
    sent_at: new Date().toISOString()
  }})
}}}}""",
        [2550, -200],
    ))

    # ── 17. Schedule Discovery Meeting ──────────────────────
    nodes.append(execute_workflow_node(
        "Schedule Discovery",
        FA_02_WORKFLOW_ID,
        [2550, 0],
    ))

    # ── 18. Success Response ────────────────────────────────
    nodes.append(respond_to_webhook_node(
        "Success Response",
        '={"success": true, "client_id": "{{ $("Extract Client ID").first().json.client_id }}", "message": "Intake processed successfully"}',
        [2800, 0],
    ))

    return nodes


def build_connections() -> dict:
    """Build connection map for FA-01."""
    return {
        "Intake Webhook": {"main": [[conn("Validate Input")]]},
        "Validate Input": {"main": [[conn("Is Valid")]]},
        "Is Valid": {
            "main": [
                [conn("Check Existing Client")],  # TRUE
                [conn("Validation Error")],         # FALSE
            ]
        },
        "Check Existing Client": {"main": [[conn("Client Exists")]]},
        "Client Exists": {
            "main": [
                [conn("Update Client")],   # TRUE (exists)
                [conn("Create Client")],   # FALSE (new)
            ]
        },
        "Create Client": {"main": [[conn("Merge Client", index=0)]]},
        "Update Client": {"main": [[conn("Merge Client", index=1)]]},
        "Merge Client": {"main": [[conn("Extract Client ID")]]},
        "Extract Client ID": {
            "main": [[
                conn("Record POPIA Consent"),
                conn("Assign Adviser"),
                conn("Airtable Pipeline"),
                conn("Send Welcome Email"),
                conn("Notify Adviser"),
            ]]
        },
        "Send Welcome Email": {"main": [[conn("Log Welcome Email")]]},
        "Log Welcome Email": {"main": [[conn("Schedule Discovery")]]},
        "Schedule Discovery": {"main": [[conn("Success Response")]]},
    }


# ============================================================
# CLI
# ============================================================


def main() -> None:
    """Usage: python deploy_fa_wf01.py <build|deploy|activate>"""
    if len(sys.argv) < 2:
        print(main.__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()
    nodes = build_nodes()
    connections = build_connections()
    workflow = build_workflow(
        "FA - Client Intake & Onboarding (FA-01)",
        nodes,
        connections,
        tags=["financial_advisory"],
    )

    output_dir = Path(__file__).parent.parent / "workflows" / "financial-advisory"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "fa01_client_intake.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Built: {output_path} ({len(nodes)} nodes)")

    if command in ("deploy", "activate"):
        try:
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).parent.parent / ".env")
        except ImportError:
            pass
        from n8n_client import N8nClient

        base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
        api_key = os.getenv("N8N_API_KEY", "")
        if not api_key:
            print("ERROR: N8N_API_KEY not set")
            sys.exit(1)

        client = N8nClient(base_url=base_url, api_key=api_key)
        result = client.create_workflow(workflow)
        wf_id = result.get("id", "")
        print(f"Deployed: {wf_id}")

        if command == "activate" and wf_id:
            client.activate_workflow(wf_id)
            print(f"Activated: {wf_id}")


if __name__ == "__main__":
    main()

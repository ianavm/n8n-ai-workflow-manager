"""
FA-08: Compliance & Audit Engine

Daily compliance check (weekdays 06:00). Aggregates POPIA consent,
FAIS disclosure, FICA verification, task completion, and consent
expiry data. Generates AI compliance report and alerts on CRITICAL issues.

Usage:
    python tools/deploy_fa_wf08.py build
"""

from __future__ import annotations

import json
import os
from dotenv import load_dotenv

load_dotenv()
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fa_helpers import (
    ai_analysis_node,
    build_workflow,
    code_node,
    conn,
    if_node,
    outlook_send_node,
    schedule_node,
    supabase_insert_node,
    supabase_query_node,
    supabase_rpc_node,
    teams_message_node,
)


FA_FIRM_ID = os.getenv("FA_FIRM_ID", "ea0fbe19-4612-414a-b00f-f1ce185a1ea3")


def build_nodes() -> list[dict]:
    """Build all nodes for FA-08 Compliance & Audit Engine."""
    nodes = []

    # -- 1. Schedule trigger (daily 06:00 weekdays) --------------
    nodes.append(schedule_node(
        "Schedule Trigger",
        "0 6 * * 1-5",
        [0, 0],
    ))

    # -- 2. Get compliance summary via RPC -----------------------
    nodes.append(supabase_rpc_node(
        "Get Compliance Summary",
        "fa_get_compliance_summary",
        f'={{{{ JSON.stringify({{firm_id: "{FA_FIRM_ID}"}}) }}}}',
        [300, 0],
    ))

    # -- 3. Expiring consent records -----------------------------
    nodes.append(supabase_query_node(
        "Expiring Consents",
        "fa_consent_records",
        (
            "expires_at=lt.{{ $now.plus({days: 30}).toISO() }}"
            "&revoked_at=is.null"
            "&granted=eq.true"
        ),
        [300, 200],
        select="*,client:fa_clients(id,first_name,last_name,email)",
    ))

    # -- 4. Overdue tasks ----------------------------------------
    nodes.append(supabase_query_node(
        "Overdue Tasks",
        "fa_tasks",
        (
            "due_date=lt.{{ $now.toISO() }}"
            "&status=not.in.(completed,cancelled)"
            "&limit=50"
        ),
        [300, 400],
        select="*,client:fa_clients(id,first_name,last_name),adviser:fa_advisers(id,full_name)",
    ))

    # -- 5. Missing disclosures ----------------------------------
    nodes.append(supabase_query_node(
        "Missing Disclosures",
        "fa_meetings",
        (
            "meeting_type=in.(discovery,presentation)"
            "&disclosure_sent=eq.false"
            "&status=not.eq.cancelled"
        ),
        [300, 600],
        select="*,client:fa_clients(id,first_name,last_name),adviser:fa_advisers(id,full_name)",
    ))

    # -- 6. Unverified FICA clients ------------------------------
    nodes.append(supabase_query_node(
        "Unverified FICA",
        "fa_clients",
        (
            "fica_status=not.eq.verified"
            "&pipeline_stage=not.in.(lead,contacted,inactive)"
        ),
        [300, 800],
        select="id,first_name,last_name,email,fica_status,pipeline_stage",
    ))

    # -- 7. Aggregate all compliance data ------------------------
    nodes.append(code_node(
        "Aggregate Compliance",
        """
const summary = $('Get Compliance Summary').first().json;
const expiringConsents = $('Expiring Consents').first().json;
const overdueTasks = $('Overdue Tasks').first().json;
const missingDisclosures = $('Missing Disclosures').first().json;
const unverifiedFica = $('Unverified FICA').first().json;

const consents = Array.isArray(expiringConsents) ? expiringConsents : [];
const tasks = Array.isArray(overdueTasks) ? overdueTasks : [];
const disclosures = Array.isArray(missingDisclosures) ? missingDisclosures : [];
const fica = Array.isArray(unverifiedFica) ? unverifiedFica : [];

// Determine severity levels
const consentSeverity = consents.length > 10 ? 'CRITICAL' : consents.length > 3 ? 'WARNING' : 'OK';
const taskSeverity = tasks.length > 20 ? 'CRITICAL' : tasks.length > 5 ? 'WARNING' : 'OK';
const disclosureSeverity = disclosures.length > 5 ? 'CRITICAL' : disclosures.length > 0 ? 'WARNING' : 'OK';
const ficaSeverity = fica.length > 10 ? 'CRITICAL' : fica.length > 0 ? 'WARNING' : 'OK';

const hasCritical = [consentSeverity, taskSeverity, disclosureSeverity, ficaSeverity].includes('CRITICAL');

return [{json: {
  summary,
  expiring_consents: consents,
  expiring_consents_count: consents.length,
  consent_severity: consentSeverity,
  overdue_tasks: tasks,
  overdue_tasks_count: tasks.length,
  task_severity: taskSeverity,
  missing_disclosures: disclosures,
  missing_disclosures_count: disclosures.length,
  disclosure_severity: disclosureSeverity,
  unverified_fica: fica,
  unverified_fica_count: fica.length,
  fica_severity: ficaSeverity,
  has_critical: hasCritical,
  report_date: new Date().toISOString(),
}}];
""",
        [600, 400],
    ))

    # -- 8. AI compliance report ---------------------------------
    nodes.append(ai_analysis_node(
        "AI Compliance Report",
        (
            "Generate a financial advisory compliance report for a South African firm. "
            "Rate each area: OK/WARNING/CRITICAL. "
            "Areas: POPIA consent expiry, FAIS disclosure compliance, FICA verification status, "
            "task completion rates, consent management. "
            "Provide specific recommendations for each area that is WARNING or CRITICAL. "
            "Format as structured JSON with fields: areas (array of {name, status, count, recommendations}), "
            "overall_rating, executive_summary."
        ),
        "={{ JSON.stringify($json) }}",
        [900, 400],
        max_tokens=4000,
        temperature=0.2,
    ))

    # -- 9. Format HTML report -----------------------------------
    nodes.append(code_node(
        "Format Report",
        """
const data = $('Aggregate Compliance').first().json;
const aiRaw = $input.first().json.choices?.[0]?.message?.content || '{}';

let aiReport;
try {
  aiReport = JSON.parse(aiRaw);
} catch (e) {
  aiReport = {executive_summary: aiRaw, areas: [], overall_rating: 'UNKNOWN'};
}

const severityColor = (s) => {
  if (s === 'CRITICAL') return '#dc2626';
  if (s === 'WARNING') return '#f59e0b';
  return '#16a34a';
};

const badge = (s) => `<span style="display:inline-block;padding:4px 12px;border-radius:4px;color:#fff;font-weight:600;background:${severityColor(s)}">${s}</span>`;

const html = `
<div style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;">
  <h1 style="color:#1e293b;">Daily Compliance Report</h1>
  <p style="color:#64748b;">${new Date().toLocaleDateString('en-ZA', {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'})}</p>

  <h2>Executive Summary</h2>
  <p>${aiReport.executive_summary || 'No summary available.'}</p>

  <h2>Compliance Areas</h2>
  <table style="width:100%;border-collapse:collapse;margin:16px 0;">
    <tr style="background:#f1f5f9;"><th style="padding:12px;text-align:left;">Area</th><th style="padding:12px;">Status</th><th style="padding:12px;">Count</th></tr>
    <tr><td style="padding:12px;border-bottom:1px solid #e2e8f0;">POPIA Consent Expiry</td><td style="padding:12px;text-align:center;border-bottom:1px solid #e2e8f0;">${badge(data.consent_severity)}</td><td style="padding:12px;text-align:center;border-bottom:1px solid #e2e8f0;">${data.expiring_consents_count}</td></tr>
    <tr><td style="padding:12px;border-bottom:1px solid #e2e8f0;">FAIS Disclosure</td><td style="padding:12px;text-align:center;border-bottom:1px solid #e2e8f0;">${badge(data.disclosure_severity)}</td><td style="padding:12px;text-align:center;border-bottom:1px solid #e2e8f0;">${data.missing_disclosures_count}</td></tr>
    <tr><td style="padding:12px;border-bottom:1px solid #e2e8f0;">FICA Verification</td><td style="padding:12px;text-align:center;border-bottom:1px solid #e2e8f0;">${badge(data.fica_severity)}</td><td style="padding:12px;text-align:center;border-bottom:1px solid #e2e8f0;">${data.unverified_fica_count}</td></tr>
    <tr><td style="padding:12px;border-bottom:1px solid #e2e8f0;">Overdue Tasks</td><td style="padding:12px;text-align:center;border-bottom:1px solid #e2e8f0;">${badge(data.task_severity)}</td><td style="padding:12px;text-align:center;border-bottom:1px solid #e2e8f0;">${data.overdue_tasks_count}</td></tr>
  </table>

  ${(aiReport.areas || []).filter(a => a.status !== 'OK').map(a => `
    <div style="background:#fff7ed;border-left:4px solid ${severityColor(a.status)};padding:16px;margin:12px 0;border-radius:4px;">
      <h3>${a.name} - ${badge(a.status)}</h3>
      <ul>${(a.recommendations || []).map(r => '<li>' + r + '</li>').join('')}</ul>
    </div>
  `).join('')}
</div>
`;

return [{json: {html, has_critical: data.has_critical}}];
""",
        [1200, 400],
    ))

    # -- 10. Send report email -----------------------------------
    nodes.append(outlook_send_node(
        "Send Compliance Report",
        os.getenv("FA_COMPLIANCE_EMAIL", "compliance@anyvisionmedia.com"),
        "=Daily Compliance Report - {{ $now.toFormat('dd MMM yyyy') }}",
        "={{ $json.html }}",
        [1500, 400],
    ))

    # -- 11. Check for critical issues ---------------------------
    nodes.append(if_node(
        "Any Critical",
        [{
            "leftValue": "={{ $('Format Report').first().json.has_critical }}",
            "rightValue": True,
            "operator": {"type": "boolean", "operation": "equals"},
        }],
        [1800, 400],
    ))

    # -- 12. Teams alert for critical ----------------------------
    nodes.append(teams_message_node(
        "Alert Compliance Team",
        os.getenv("FA_COMPLIANCE_TEAMS_CHANNEL", ""),
        """={{ '<h3 style="color:#dc2626;">CRITICAL Compliance Alert</h3><p>The daily compliance report has identified CRITICAL issues requiring immediate attention. Please review the compliance report sent to your email.</p><p>Report date: ' + $now.toFormat('dd MMM yyyy HH:mm') + '</p>' }}""",
        [2100, 300],
    ))

    # -- 13. Log audit entry -------------------------------------
    nodes.append(supabase_insert_node(
        "Log Audit Entry",
        "fa_audit_log",
        f"""={{{{
  JSON.stringify({{
    firm_id: '{FA_FIRM_ID}',
    action: 'compliance_report_generated',
    entity_type: 'compliance_report',
    details: {{
      has_critical: $('Format Report').first().json.has_critical,
      report_date: new Date().toISOString()
    }},
    performed_by: 'system',
    created_at: new Date().toISOString()
  }})
}}}}""",
        [1800, 600],
    ))

    return nodes


def build_connections() -> dict:
    """Build connection map for FA-08."""
    return {
        "Schedule Trigger": {"main": [[
            conn("Get Compliance Summary"),
            conn("Expiring Consents"),
            conn("Overdue Tasks"),
            conn("Missing Disclosures"),
            conn("Unverified FICA"),
        ]]},
        "Get Compliance Summary": {"main": [[conn("Aggregate Compliance")]]},
        "Expiring Consents": {"main": [[conn("Aggregate Compliance")]]},
        "Overdue Tasks": {"main": [[conn("Aggregate Compliance")]]},
        "Missing Disclosures": {"main": [[conn("Aggregate Compliance")]]},
        "Unverified FICA": {"main": [[conn("Aggregate Compliance")]]},
        "Aggregate Compliance": {"main": [[conn("AI Compliance Report")]]},
        "AI Compliance Report": {"main": [[conn("Format Report")]]},
        "Format Report": {"main": [[conn("Send Compliance Report")]]},
        "Send Compliance Report": {"main": [[conn("Any Critical"), conn("Log Audit Entry")]]},
        "Any Critical": {"main": [[conn("Alert Compliance Team")], []]},
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python deploy_fa_wf08.py <build|deploy>")
        sys.exit(1)

    nodes = build_nodes()
    connections = build_connections()
    workflow = build_workflow(
        "FA - Compliance & Audit Engine (FA-08)",
        nodes, connections,
        tags=["financial_advisory"],
    )

    output_dir = Path(__file__).parent.parent / "workflows" / "financial-advisory"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "fa08_compliance_audit.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Built: {path} ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()

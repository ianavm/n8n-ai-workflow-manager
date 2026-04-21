"""
FA-10: Weekly Reporting

Monday 07:00 weekly report. Aggregates pipeline, meetings, tasks,
new clients, and compliance data. AI generates executive summary.
Sends HTML report via email and logs snapshot to Airtable.

Usage:
    python tools/deploy_fa_wf10.py build
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
    airtable_create_node,
    build_workflow,
    code_node,
    conn,
    outlook_send_node,
    schedule_node,
    supabase_query_node,
    supabase_rpc_node,
)


FA_FIRM_ID = os.getenv("FA_FIRM_ID", "ea0fbe19-4612-414a-b00f-f1ce185a1ea3")
FA_AIRTABLE_BASE = os.getenv("FA_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")
FA_AIRTABLE_METRICS_TABLE = os.getenv("FA_AIRTABLE_METRICS_TABLE_ID", "REPLACE_WITH_TABLE_ID")


def build_nodes() -> list[dict]:
    """Build all nodes for FA-10 Weekly Reporting."""
    nodes = []

    # -- 1. Schedule trigger (Monday 07:00) ----------------------
    nodes.append(schedule_node(
        "Schedule Trigger",
        "0 7 * * 1",
        [0, 0],
    ))

    # -- 2. Pipeline summary via RPC -----------------------------
    nodes.append(supabase_rpc_node(
        "Get Pipeline Summary",
        "fa_get_pipeline_summary",
        f'={{{{ JSON.stringify({{firm_id: "{FA_FIRM_ID}"}}) }}}}',
        [300, 0],
    ))

    # -- 3. Meetings this week -----------------------------------
    nodes.append(supabase_query_node(
        "Meetings This Week",
        "fa_meetings",
        (
            "created_at=gte.{{ $now.minus({days: 7}).toISO() }}"
            "&select=meeting_type,status"
        ),
        [300, 200],
    ))

    # -- 4. Task stats -------------------------------------------
    nodes.append(supabase_query_node(
        "Task Stats",
        "fa_tasks",
        (
            "select=id,status,due_date,created_at"
            "&or=(created_at.gte.{{ $now.minus({days: 7}).toISO() }},"
            "status.eq.completed,"
            "and(due_date.lt.{{ $now.toISO() }},status.not.in.(completed,cancelled)))"
        ),
        [300, 400],
    ))

    # -- 5. New clients this week --------------------------------
    nodes.append(supabase_query_node(
        "New Clients",
        "fa_clients",
        "created_at=gte.{{ $now.minus({days: 7}).toISO() }}&select=id,first_name,last_name,pipeline_stage",
        [300, 600],
    ))

    # -- 6. Compliance summary via RPC ---------------------------
    nodes.append(supabase_rpc_node(
        "Get Compliance Summary",
        "fa_get_compliance_summary",
        f'={{{{ JSON.stringify({{firm_id: "{FA_FIRM_ID}"}}) }}}}',
        [300, 800],
    ))

    # -- 7. Aggregate all data -----------------------------------
    nodes.append(code_node(
        "Aggregate Report Data",
        """
const pipeline = $('Get Pipeline Summary').first().json;
const meetingsRaw = $('Meetings This Week').first().json;
const tasksRaw = $('Task Stats').first().json;
const newClientsRaw = $('New Clients').first().json;
const compliance = $('Get Compliance Summary').first().json;

const meetings = Array.isArray(meetingsRaw) ? meetingsRaw : [];
const tasks = Array.isArray(tasksRaw) ? tasksRaw : [];
const newClients = Array.isArray(newClientsRaw) ? newClientsRaw : [];

// Meeting aggregation by type and status
const meetingsByType = {};
meetings.forEach(m => {
  const key = m.meeting_type || 'other';
  if (!meetingsByType[key]) meetingsByType[key] = {total: 0, statuses: {}};
  meetingsByType[key].total++;
  const s = m.status || 'unknown';
  meetingsByType[key].statuses[s] = (meetingsByType[key].statuses[s] || 0) + 1;
});

// Task aggregation
const now = new Date();
const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
const completedTasks = tasks.filter(t => t.status === 'completed').length;
const overdueTasks = tasks.filter(t =>
  t.due_date && new Date(t.due_date) < now &&
  !['completed', 'cancelled'].includes(t.status)
).length;
const newTasks = tasks.filter(t =>
  t.created_at && new Date(t.created_at) >= weekAgo
).length;

return [{json: {
  week_ending: now.toISOString(),
  pipeline: pipeline,
  meetings: {
    total: meetings.length,
    by_type: meetingsByType,
  },
  tasks: {
    completed: completedTasks,
    overdue: overdueTasks,
    new: newTasks,
  },
  new_clients: {
    count: newClients.length,
    list: newClients.slice(0, 10),
  },
  compliance: compliance,
}}];
""",
        [600, 400],
    ))

    # -- 8. AI executive summary ---------------------------------
    nodes.append(ai_analysis_node(
        "AI Executive Summary",
        (
            "Generate a concise weekly executive summary for a financial advisory firm. "
            "Highlight key achievements, concerns, and recommendations. "
            "Keep it brief (3-5 paragraphs). Use professional tone suitable for firm leadership. "
            "Include specific numbers from the data provided."
        ),
        "={{ JSON.stringify($json) }}",
        [900, 400],
        max_tokens=2000,
        temperature=0.3,
    ))

    # -- 9. Format HTML report -----------------------------------
    nodes.append(code_node(
        "Format Report",
        """
const data = $('Aggregate Report Data').first().json;
const aiSummary = $input.first().json.choices?.[0]?.message?.content || 'No summary generated.';

const meetingRows = Object.entries(data.meetings.by_type || {}).map(([type, info]) => {
  const statusList = Object.entries(info.statuses).map(([s, c]) => `${s}: ${c}`).join(', ');
  return `<tr><td style="padding:8px;border-bottom:1px solid #e2e8f0;">${type}</td><td style="padding:8px;text-align:center;border-bottom:1px solid #e2e8f0;">${info.total}</td><td style="padding:8px;border-bottom:1px solid #e2e8f0;">${statusList}</td></tr>`;
}).join('');

const clientList = (data.new_clients.list || []).map(c =>
  `<li>${c.first_name} ${c.last_name} (${c.pipeline_stage})</li>`
).join('');

const html = `
<div style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;">
  <h1 style="color:#1e293b;">Weekly Advisory Report</h1>
  <p style="color:#64748b;">Week ending ${new Date().toLocaleDateString('en-ZA', {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'})}</p>

  <div style="background:#f8fafc;border-radius:12px;padding:20px;margin:16px 0;">
    <h2 style="margin-top:0;">Executive Summary</h2>
    ${aiSummary.split('\\n').map(p => p.trim() ? '<p>' + p + '</p>' : '').join('')}
  </div>

  <h2>Key Metrics</h2>
  <div style="display:flex;gap:16px;flex-wrap:wrap;margin:16px 0;">
    <div style="flex:1;min-width:150px;background:#eff6ff;border-radius:12px;padding:20px;text-align:center;">
      <div style="font-size:32px;font-weight:700;color:#2563eb;">${data.new_clients.count}</div>
      <div style="color:#64748b;">New Clients</div>
    </div>
    <div style="flex:1;min-width:150px;background:#f0fdf4;border-radius:12px;padding:20px;text-align:center;">
      <div style="font-size:32px;font-weight:700;color:#16a34a;">${data.meetings.total}</div>
      <div style="color:#64748b;">Meetings</div>
    </div>
    <div style="flex:1;min-width:150px;background:#fefce8;border-radius:12px;padding:20px;text-align:center;">
      <div style="font-size:32px;font-weight:700;color:#ca8a04;">${data.tasks.completed}</div>
      <div style="color:#64748b;">Tasks Completed</div>
    </div>
    <div style="flex:1;min-width:150px;background:${data.tasks.overdue > 5 ? '#fef2f2' : '#f0fdf4'};border-radius:12px;padding:20px;text-align:center;">
      <div style="font-size:32px;font-weight:700;color:${data.tasks.overdue > 5 ? '#dc2626' : '#16a34a'};">${data.tasks.overdue}</div>
      <div style="color:#64748b;">Overdue Tasks</div>
    </div>
  </div>

  <h2>Meetings by Type</h2>
  <table style="width:100%;border-collapse:collapse;margin:16px 0;">
    <tr style="background:#f1f5f9;"><th style="padding:8px;text-align:left;">Type</th><th style="padding:8px;">Count</th><th style="padding:8px;text-align:left;">Statuses</th></tr>
    ${meetingRows || '<tr><td colspan="3" style="padding:8px;text-align:center;">No meetings this week</td></tr>'}
  </table>

  ${data.new_clients.count > 0 ? '<h2>New Clients</h2><ul>' + clientList + '</ul>' : ''}
</div>
`;

return [{json: {
  html,
  new_clients_count: data.new_clients.count,
  meetings_total: data.meetings.total,
  tasks_completed: data.tasks.completed,
  tasks_overdue: data.tasks.overdue,
  tasks_new: data.tasks.new,
}}];
""",
        [1200, 400],
    ))

    # -- 10. Send weekly report email ----------------------------
    nodes.append(outlook_send_node(
        "Send Weekly Report",
        os.getenv("FA_ADMIN_EMAIL", "admin@anyvisionmedia.com"),
        "=Weekly Advisory Report - {{ $now.toFormat('dd MMM yyyy') }}",
        "={{ $json.html }}",
        [1500, 400],
    ))

    # -- 11. Log to Airtable metrics table -----------------------
    nodes.append(airtable_create_node(
        "Log Weekly Metrics",
        FA_AIRTABLE_BASE,
        FA_AIRTABLE_METRICS_TABLE,
        {
            "Week Ending": "={{ $now.toFormat('yyyy-MM-dd') }}",
            "New Clients": "={{ $('Format Report').first().json.new_clients_count }}",
            "Meetings Total": "={{ $('Format Report').first().json.meetings_total }}",
            "Tasks Completed": "={{ $('Format Report').first().json.tasks_completed }}",
            "Tasks Overdue": "={{ $('Format Report').first().json.tasks_overdue }}",
            "Tasks New": "={{ $('Format Report').first().json.tasks_new }}",
        },
        [1500, 600],
    ))

    return nodes


def build_connections() -> dict:
    """Build connection map for FA-10."""
    return {
        "Schedule Trigger": {"main": [[
            conn("Get Pipeline Summary"),
            conn("Meetings This Week"),
            conn("Task Stats"),
            conn("New Clients"),
            conn("Get Compliance Summary"),
        ]]},
        "Get Pipeline Summary": {"main": [[conn("Aggregate Report Data")]]},
        "Meetings This Week": {"main": [[conn("Aggregate Report Data")]]},
        "Task Stats": {"main": [[conn("Aggregate Report Data")]]},
        "New Clients": {"main": [[conn("Aggregate Report Data")]]},
        "Get Compliance Summary": {"main": [[conn("Aggregate Report Data")]]},
        "Aggregate Report Data": {"main": [[conn("AI Executive Summary")]]},
        "AI Executive Summary": {"main": [[conn("Format Report")]]},
        "Format Report": {"main": [[conn("Send Weekly Report"), conn("Log Weekly Metrics")]]},
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python deploy_fa_wf10.py <build|deploy>")
        sys.exit(1)

    nodes = build_nodes()
    connections = build_connections()
    workflow = build_workflow(
        "FA - Weekly Reporting (FA-10)",
        nodes, connections,
        tags=["financial_advisory"],
    )

    output_dir = Path(__file__).parent.parent / "workflows" / "financial-advisory"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "fa10_weekly_reporting.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Built: {path} ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()

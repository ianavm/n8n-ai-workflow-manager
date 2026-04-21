"""
FA-07a: Scheduled Reminders

Runs every 30 minutes during business hours (Mon-Fri 07:00-19:00).
Sends 24-hour and 1-hour meeting reminders via Outlook email and WhatsApp.
Updates reminder flags and logs communications in Supabase.

Usage:
    python tools/deploy_fa_wf07a.py build
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
    build_workflow,
    code_node,
    conn,
    if_node,
    outlook_send_node,
    schedule_node,
    split_in_batches_node,
    supabase_insert_node,
    supabase_query_node,
    supabase_update_node,
    whatsapp_template_node,
)


FA_FIRM_ID = os.getenv("FA_FIRM_ID", "ea0fbe19-4612-414a-b00f-f1ce185a1ea3")


def build_nodes() -> list[dict]:
    """Build all nodes for FA-07a Scheduled Reminders."""
    nodes = []

    # -- 1. Schedule Trigger (every 30min, 07-19 weekdays) ------
    nodes.append(schedule_node(
        "Schedule Trigger",
        "*/30 7-19 * * 1-5",
        [0, 0],
    ))

    # -- 2. Query 24h reminders ----------------------------------
    nodes.append(supabase_query_node(
        "Query 24h Reminders",
        "fa_meetings",
        (
            "reminder_24h_sent=eq.false"
            "&status=in.(scheduled,confirmed)"
            "&scheduled_at=gte.{{ $now.plus({hours: 23}).toISO() }}"
            "&scheduled_at=lte.{{ $now.plus({hours: 25}).toISO() }}"
        ),
        [300, 0],
        select="*,client:fa_clients(*),adviser:fa_advisers(*)",
    ))

    # -- 3. Has 24h reminders? -----------------------------------
    nodes.append(if_node(
        "Has 24h Reminders",
        [{
            "leftValue": "={{ $json.length }}",
            "rightValue": 0,
            "operator": {"type": "number", "operation": "gt"},
        }],
        [600, 0],
    ))

    # -- 4. Split 24h batch --------------------------------------
    nodes.append(split_in_batches_node(
        "Split 24h Batch",
        [900, -100],
        batch_size=1,
    ))

    # -- 5. Send 24h reminder email ------------------------------
    nodes.append(outlook_send_node(
        "Send 24h Email",
        "={{ $json.client.email }}",
        "=Reminder: Your meeting tomorrow with {{ $json.adviser.full_name }}",
        """={{ (function() {
  const m = $json;
  const dt = new Date(m.scheduled_at);
  const dateStr = dt.toLocaleDateString('en-ZA', {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone: 'Africa/Johannesburg'});
  const timeStr = dt.toLocaleTimeString('en-ZA', {hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Johannesburg'});
  return `<h2>Meeting Reminder - Tomorrow</h2>
  <p>Hi ${m.client.first_name},</p>
  <p>This is a friendly reminder that you have a <strong>${m.meeting_type}</strong> meeting scheduled:</p>
  <div style="background:#f0f0ff;border:1px solid #d0d0ff;border-radius:12px;padding:20px;margin:16px 0;">
    <p><strong>Date:</strong> ${dateStr}</p>
    <p><strong>Time:</strong> ${timeStr} (SAST)</p>
    <p><strong>Adviser:</strong> ${m.adviser.full_name}</p>
    <p><strong>Duration:</strong> ${m.duration_minutes || 60} minutes</p>
  </div>
  ${m.teams_meeting_url ? '<p style="text-align:center;"><a href="' + m.teams_meeting_url + '" style="display:inline-block;background:#6264A7;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;">Join Teams Meeting</a></p>' : ''}
  <p>If you need to reschedule, please reply to this email.</p>`;
})() }}""",
        [1200, -200],
    ))

    # -- 6. WhatsApp 24h reminder --------------------------------
    nodes.append(whatsapp_template_node(
        "WhatsApp 24h Reminder",
        "{{ $json.client.mobile }}",
        "fa_reminder_24h",
        """={{ JSON.stringify([
  {type: 'text', text: $json.client.first_name},
  {type: 'text', text: $json.adviser.full_name},
  {type: 'text', text: new Date($json.scheduled_at).toLocaleDateString('en-ZA', {weekday: 'long', month: 'long', day: 'numeric', timeZone: 'Africa/Johannesburg'})},
  {type: 'text', text: new Date($json.scheduled_at).toLocaleTimeString('en-ZA', {hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Johannesburg'})}
]) }}""",
        [1200, 0],
    ))

    # -- 7. Update 24h sent flag ---------------------------------
    nodes.append(supabase_update_node(
        "Mark 24h Sent",
        "fa_meetings",
        "id",
        "={{ $json.id }}",
        '={{ JSON.stringify({reminder_24h_sent: true}) }}',
        [1500, -200],
    ))

    # -- 8. Log 24h email communication --------------------------
    nodes.append(supabase_insert_node(
        "Log 24h Email",
        "fa_communications",
        f"""={{{{
  JSON.stringify({{
    client_id: $json.client_id,
    firm_id: '{FA_FIRM_ID}',
    adviser_id: $json.adviser_id,
    meeting_id: $json.id,
    channel: 'email',
    direction: 'outbound',
    subject: 'Meeting Reminder - 24h',
    status: 'sent',
    sent_at: new Date().toISOString()
  }})
}}}}""",
        [1500, 0],
    ))

    # -- 9. Query 1h reminders ----------------------------------
    nodes.append(supabase_query_node(
        "Query 1h Reminders",
        "fa_meetings",
        (
            "reminder_1h_sent=eq.false"
            "&status=in.(scheduled,confirmed)"
            "&scheduled_at=gte.{{ $now.plus({minutes: 50}).toISO() }}"
            "&scheduled_at=lte.{{ $now.plus({minutes: 70}).toISO() }}"
        ),
        [1800, 0],
        select="*,client:fa_clients(*),adviser:fa_advisers(*)",
    ))

    # -- 10. Has 1h reminders? ----------------------------------
    nodes.append(if_node(
        "Has 1h Reminders",
        [{
            "leftValue": "={{ $json.length }}",
            "rightValue": 0,
            "operator": {"type": "number", "operation": "gt"},
        }],
        [2100, 0],
    ))

    # -- 11. Split 1h batch -------------------------------------
    nodes.append(split_in_batches_node(
        "Split 1h Batch",
        [2400, -100],
        batch_size=1,
    ))

    # -- 12. Send 1h reminder email -----------------------------
    nodes.append(outlook_send_node(
        "Send 1h Email",
        "={{ $json.client.email }}",
        "=Your meeting starts in 1 hour with {{ $json.adviser.full_name }}",
        """={{ (function() {
  const m = $json;
  const timeStr = new Date(m.scheduled_at).toLocaleTimeString('en-ZA', {hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Johannesburg'});
  return `<h2>Your Meeting Starts Soon</h2>
  <p>Hi ${m.client.first_name},</p>
  <p>Your <strong>${m.meeting_type}</strong> meeting with <strong>${m.adviser.full_name}</strong> starts in about 1 hour at <strong>${timeStr} (SAST)</strong>.</p>
  ${m.teams_meeting_url ? '<p style="text-align:center;"><a href="' + m.teams_meeting_url + '" style="display:inline-block;background:#6264A7;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;">Join Teams Meeting Now</a></p>' : ''}`;
})() }}""",
        [2700, -200],
    ))

    # -- 13. WhatsApp 1h reminder --------------------------------
    nodes.append(whatsapp_template_node(
        "WhatsApp 1h Reminder",
        "{{ $json.client.mobile }}",
        "fa_reminder_1h",
        """={{ JSON.stringify([
  {type: 'text', text: $json.client.first_name},
  {type: 'text', text: $json.adviser.full_name},
  {type: 'text', text: new Date($json.scheduled_at).toLocaleTimeString('en-ZA', {hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Johannesburg'})},
  {type: 'text', text: $json.teams_meeting_url || ''}
]) }}""",
        [2700, 0],
    ))

    # -- 14. Update 1h sent flag ---------------------------------
    nodes.append(supabase_update_node(
        "Mark 1h Sent",
        "fa_meetings",
        "id",
        "={{ $json.id }}",
        '={{ JSON.stringify({reminder_1h_sent: true}) }}',
        [3000, -100],
    ))

    return nodes


def build_connections() -> dict:
    """Build connection map for FA-07a."""
    return {
        "Schedule Trigger": {"main": [[conn("Query 24h Reminders")]]},
        "Query 24h Reminders": {"main": [[conn("Has 24h Reminders")]]},
        "Has 24h Reminders": {"main": [[conn("Split 24h Batch")], [conn("Query 1h Reminders")]]},
        "Split 24h Batch": {"main": [[conn("Query 1h Reminders")], [conn("Send 24h Email"), conn("WhatsApp 24h Reminder")]]},
        "Send 24h Email": {"main": [[conn("Mark 24h Sent"), conn("Log 24h Email")]]},
        "WhatsApp 24h Reminder": {"main": [[]]},
        "Mark 24h Sent": {"main": [[]]},
        "Log 24h Email": {"main": [[]]},
        "Query 1h Reminders": {"main": [[conn("Has 1h Reminders")]]},
        "Has 1h Reminders": {"main": [[conn("Split 1h Batch")], []]},
        "Split 1h Batch": {"main": [[], [conn("Send 1h Email"), conn("WhatsApp 1h Reminder")]]},
        "Send 1h Email": {"main": [[conn("Mark 1h Sent")]]},
        "WhatsApp 1h Reminder": {"main": [[]]},
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python deploy_fa_wf07a.py <build|deploy>")
        sys.exit(1)

    nodes = build_nodes()
    connections = build_connections()
    workflow = build_workflow(
        "FA - Scheduled Reminders (FA-07a)",
        nodes, connections,
        tags=["financial_advisory"],
    )

    output_dir = Path(__file__).parent.parent / "workflows" / "financial-advisory"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "fa07a_scheduled_reminders.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Built: {path} ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()

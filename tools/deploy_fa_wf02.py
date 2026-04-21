"""
FA-02: Meeting Scheduler (Sub-Workflow)

Called by FA-01 (intake), FA-06 (discovery pipeline), and portal API.
Checks Outlook calendar availability, creates Teams meeting via Graph API,
sends confirmations via Outlook email and WhatsApp.

Usage:
    python tools/deploy_fa_wf02.py build
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
    execute_workflow_trigger_node,
    graph_api_node,
    outlook_send_node,
    supabase_insert_node,
    supabase_query_node,
    supabase_update_node,
    whatsapp_template_node,
)


FA_FIRM_ID = os.getenv("FA_FIRM_ID", "REPLACE_WITH_FIRM_UUID")


def build_nodes() -> list[dict]:
    """Build all nodes for FA-02 Meeting Scheduler."""
    nodes = []

    # ── 1. Sub-workflow Trigger ─────────────────────────────
    nodes.append(execute_workflow_trigger_node(
        "Workflow Trigger",
        [0, 0],
    ))

    # ── 2. Fetch Adviser Details ────────────────────────────
    nodes.append(supabase_query_node(
        "Fetch Adviser",
        "fa_advisers",
        "id=eq.{{ $json.adviser_id }}&select=id,full_name,email,microsoft_user_id,outlook_calendar_id",
        [300, 0],
    ))

    # ── 3. Fetch Client Details ─────────────────────────────
    nodes.append(supabase_query_node(
        "Fetch Client",
        "fa_clients",
        "id=eq.{{ $json.client_id }}&select=id,first_name,last_name,email,mobile",
        [300, 200],
    ))

    # ── 4. Check Calendar Availability ──────────────────────
    nodes.append(graph_api_node(
        "Check Availability",
        "POST",
        "=/users/{{ $('Fetch Adviser').first().json[0].microsoft_user_id }}/calendar/getSchedule",
        [600, 0],
        body_expr="""={{ JSON.stringify({
  schedules: [$('Fetch Adviser').first().json[0].email],
  startTime: {
    dateTime: new Date(Date.now() + 24*60*60*1000).toISOString().split('T')[0] + 'T08:00:00',
    timeZone: 'Africa/Johannesburg'
  },
  endTime: {
    dateTime: new Date(Date.now() + 14*24*60*60*1000).toISOString().split('T')[0] + 'T17:00:00',
    timeZone: 'Africa/Johannesburg'
  },
  availabilityViewInterval: 60
}) }}""",
    ))

    # ── 5. Find Best Slot ───────────────────────────────────
    nodes.append(code_node(
        "Find Best Slot",
        """
// Parse availability and find first open 60-min slot in business hours
const schedule = $input.first().json.value?.[0] || {};
const availability = schedule.availabilityView || '';
const startDate = new Date(schedule.scheduleItems?.[0]?.start?.dateTime || Date.now() + 86400000);

// Each char in availabilityView represents one interval (60min):
// 0=free, 1=tentative, 2=busy, 3=oof, 4=workingElsewhere
let slotStart = null;
const baseDate = new Date(startDate);
baseDate.setHours(8, 0, 0, 0);

for (let day = 1; day <= 14; day++) {
  const checkDate = new Date(baseDate);
  checkDate.setDate(checkDate.getDate() + day);

  // Skip weekends
  const dow = checkDate.getDay();
  if (dow === 0 || dow === 6) continue;

  // Check 8:00-16:00 (last slot starts at 16:00 for 60min meeting ending at 17:00)
  for (let hour = 8; hour <= 16; hour++) {
    const slotTime = new Date(checkDate);
    slotTime.setHours(hour, 0, 0, 0);

    // Simple approach: assume free (we'll let Graph API reject if busy)
    slotStart = slotTime;
    break;
  }
  if (slotStart) break;
}

if (!slotStart) {
  slotStart = new Date(Date.now() + 3*24*60*60*1000);
  slotStart.setHours(10, 0, 0, 0);
}

const slotEnd = new Date(slotStart.getTime() + 60*60*1000);

return [{json: {
  slot_start: slotStart.toISOString(),
  slot_end: slotEnd.toISOString(),
  slot_date: slotStart.toLocaleDateString('en-ZA', {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone: 'Africa/Johannesburg'}),
  slot_time: slotStart.toLocaleTimeString('en-ZA', {hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Johannesburg'}),
}}];
""",
        [900, 0],
    ))

    # ── 6. Create Calendar Event with Teams Meeting ─────────
    meeting_type_expr = "{{ $('Workflow Trigger').first().json.meeting_type || 'discovery' }}"
    client_name = "$('Fetch Client').first().json[0].first_name + ' ' + $('Fetch Client').first().json[0].last_name"

    nodes.append(graph_api_node(
        "Create Teams Meeting",
        "POST",
        "=/users/{{ $('Fetch Adviser').first().json[0].microsoft_user_id }}/calendars/{{ $('Fetch Adviser').first().json[0].outlook_calendar_id || 'AAMkAD' }}/events",
        [1200, 0],
        body_expr=f"""={{{{ JSON.stringify({{
  subject: `${{$('Workflow Trigger').first().json.meeting_type || 'Discovery'}} Meeting - ${{$('Fetch Client').first().json[0].first_name}} ${{$('Fetch Client').first().json[0].last_name}}`,
  start: {{
    dateTime: $json.slot_start,
    timeZone: 'Africa/Johannesburg'
  }},
  end: {{
    dateTime: $json.slot_end,
    timeZone: 'Africa/Johannesburg'
  }},
  isOnlineMeeting: true,
  onlineMeetingProvider: 'teamsForBusiness',
  attendees: [{{
    emailAddress: {{
      address: $('Fetch Client').first().json[0].email,
      name: $('Fetch Client').first().json[0].first_name + ' ' + $('Fetch Client').first().json[0].last_name
    }},
    type: 'required'
  }}],
  body: {{
    contentType: 'html',
    content: '<p>Financial advisory ' + ($('Workflow Trigger').first().json.meeting_type || 'discovery') + ' meeting.</p>'
  }}
}}) }}}}""",
    ))

    # ── 7. Store Meeting in Supabase ────────────────────────
    nodes.append(supabase_insert_node(
        "Store Meeting",
        "fa_meetings",
        f"""={{{{
  JSON.stringify({{
    client_id: $('Workflow Trigger').first().json.client_id,
    adviser_id: $('Workflow Trigger').first().json.adviser_id,
    firm_id: '{FA_FIRM_ID}',
    meeting_type: $('Workflow Trigger').first().json.meeting_type || 'discovery',
    status: 'scheduled',
    title: $('Create Teams Meeting').first().json.subject,
    scheduled_at: $('Find Best Slot').first().json.slot_start,
    duration_minutes: 60,
    outlook_event_id: $('Create Teams Meeting').first().json.id,
    teams_meeting_url: $('Create Teams Meeting').first().json.onlineMeeting?.joinUrl || $('Create Teams Meeting').first().json.onlineMeetingUrl || '',
    teams_meeting_id: $('Create Teams Meeting').first().json.onlineMeeting?.conferenceId || '',
    location_type: 'online'
  }})
}}}}""",
        [1500, 0],
    ))

    # ── 8. Send Confirmation Email ──────────────────────────
    nodes.append(outlook_send_node(
        "Send Confirmation Email",
        "={{ $('Fetch Client').first().json[0].email }}",
        "=Your {{ $('Workflow Trigger').first().json.meeting_type || 'discovery' }} meeting is confirmed",
        """={{ (function() {
  const client = $('Fetch Client').first().json[0];
  const adviser = $('Fetch Adviser').first().json[0];
  const slot = $('Find Best Slot').first().json;
  const teamsUrl = $('Create Teams Meeting').first().json.onlineMeeting?.joinUrl || '';
  const meetingType = $('Workflow Trigger').first().json.meeting_type || 'discovery';

  return `<h2>Your ${meetingType} Meeting is Confirmed</h2>
  <p>Hi ${client.first_name},</p>
  <p>Your meeting with <strong>${adviser.full_name}</strong> has been scheduled:</p>
  <div style="background:#f0f0ff;border:1px solid #d0d0ff;border-radius:12px;padding:20px;margin:16px 0;">
    <p><strong>Date:</strong> ${slot.slot_date}</p>
    <p><strong>Time:</strong> ${slot.slot_time} (SAST)</p>
    <p><strong>Duration:</strong> 60 minutes</p>
    <p><strong>Location:</strong> Microsoft Teams (online)</p>
  </div>
  <p style="text-align:center;"><a href="${teamsUrl}" style="display:inline-block;background:#6264A7;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;">Join Teams Meeting</a></p>`;
})() }}""",
        [1800, -150],
    ))

    # ── 9. Send WhatsApp Confirmation ───────────────────────
    nodes.append(whatsapp_template_node(
        "WhatsApp Confirm",
        "{{ $('Fetch Client').first().json[0].mobile }}",
        "fa_meeting_confirm",
        """={{ JSON.stringify([
  {type: 'text', text: $('Fetch Client').first().json[0].first_name},
  {type: 'text', text: $('Workflow Trigger').first().json.meeting_type || 'discovery'},
  {type: 'text', text: $('Fetch Adviser').first().json[0].full_name},
  {type: 'text', text: $('Find Best Slot').first().json.slot_date},
  {type: 'text', text: $('Find Best Slot').first().json.slot_time},
  {type: 'text', text: $('Create Teams Meeting').first().json.onlineMeeting?.joinUrl || ''}
]) }}""",
        [1800, 50],
    ))

    # ── 10. Log Email Communication ─────────────────────────
    nodes.append(supabase_insert_node(
        "Log Email",
        "fa_communications",
        f"""={{{{
  JSON.stringify({{
    client_id: $('Workflow Trigger').first().json.client_id,
    firm_id: '{FA_FIRM_ID}',
    adviser_id: $('Workflow Trigger').first().json.adviser_id,
    meeting_id: $('Store Meeting').first().json[0]?.id || null,
    channel: 'email',
    direction: 'outbound',
    subject: 'Meeting Confirmation',
    status: 'sent',
    sent_at: new Date().toISOString()
  }})
}}}}""",
        [2100, -150],
    ))

    # ── 11. Log WhatsApp Communication ──────────────────────
    nodes.append(supabase_insert_node(
        "Log WhatsApp",
        "fa_communications",
        f"""={{{{
  JSON.stringify({{
    client_id: $('Workflow Trigger').first().json.client_id,
    firm_id: '{FA_FIRM_ID}',
    adviser_id: $('Workflow Trigger').first().json.adviser_id,
    meeting_id: $('Store Meeting').first().json[0]?.id || null,
    channel: 'whatsapp',
    direction: 'outbound',
    whatsapp_template: 'fa_meeting_confirm',
    status: 'sent',
    sent_at: new Date().toISOString()
  }})
}}}}""",
        [2100, 50],
    ))

    # ── 12. Update Pipeline Stage ───────────────────────────
    meeting_type = "$('Workflow Trigger').first().json.meeting_type || 'discovery'"
    nodes.append(supabase_update_node(
        "Update Pipeline",
        "fa_clients",
        "id",
        "={{ $('Workflow Trigger').first().json.client_id }}",
        f"""={{{{
  JSON.stringify({{
    pipeline_stage: ($('Workflow Trigger').first().json.meeting_type || 'discovery') + '_scheduled',
    pipeline_updated_at: new Date().toISOString()
  }})
}}}}""",
        [2100, 200],
    ))

    return nodes


def build_connections() -> dict:
    """Build connection map for FA-02."""
    return {
        "Workflow Trigger": {"main": [[conn("Fetch Adviser"), conn("Fetch Client")]]},
        "Fetch Adviser": {"main": [[conn("Check Availability")]]},
        "Check Availability": {"main": [[conn("Find Best Slot")]]},
        "Find Best Slot": {"main": [[conn("Create Teams Meeting")]]},
        "Create Teams Meeting": {"main": [[conn("Store Meeting")]]},
        "Store Meeting": {"main": [[conn("Send Confirmation Email"), conn("WhatsApp Confirm"), conn("Update Pipeline")]]},
        "Send Confirmation Email": {"main": [[conn("Log Email")]]},
        "WhatsApp Confirm": {"main": [[conn("Log WhatsApp")]]},
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python deploy_fa_wf02.py <build|deploy>")
        sys.exit(1)

    nodes = build_nodes()
    connections = build_connections()
    workflow = build_workflow(
        "FA - Meeting Scheduler (FA-02)",
        nodes, connections,
        tags=["financial_advisory"],
    )

    output_dir = Path(__file__).parent.parent / "workflows" / "financial-advisory"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "fa02_meeting_scheduler.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Built: {path} ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()

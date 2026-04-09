"""
AVM Booking Assistant - Workflow Builder & Deployer

Builds 3 booking/calendar workflows as n8n workflow JSON files,
and optionally deploys them to the n8n instance.

Workflows:
    BOOK-01: Meeting Scheduler     (Webhook) - Receive request, check availability, book, confirm
    BOOK-02: Follow-Up Nudge       (Daily 09:00 SAST = 07:00 UTC) - Remind upcoming meetings
    BOOK-03: Calendar Optimizer    (Friday 16:00 SAST = 14:00 UTC) - Weekly calendar analysis

Usage:
    python tools/deploy_booking_assistant.py build              # Build all workflow JSONs
    python tools/deploy_booking_assistant.py build book01       # Build BOOK-01 only
    python tools/deploy_booking_assistant.py build book02       # Build BOOK-02 only
    python tools/deploy_booking_assistant.py build book03       # Build BOOK-03 only
    python tools/deploy_booking_assistant.py deploy             # Build + Deploy (inactive)
    python tools/deploy_booking_assistant.py activate           # Build + Deploy + Activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# -- Credential Constants --
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail AVM"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable PAT"}

# -- Airtable IDs --
ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "appTCh0EeXQp0XqzW")
TABLE_BOOKING_LOG = os.getenv("BOOKING_TABLE_LOG", "REPLACE_AFTER_SETUP")

# -- Config --
AI_MODEL = "anthropic/claude-sonnet-4-20250514"
ALERT_EMAIL = "ian@anyvisionmedia.com"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def uid():
    return str(uuid.uuid4())


def airtable_ref(base, table):
    return {"base": {"__rl": True, "value": base, "mode": "id"},
            "table": {"__rl": True, "value": table, "mode": "id"}}


# ======================================================================
# BOOK-01: Meeting Scheduler (Webhook)
# ======================================================================

def build_book01_nodes():
    nodes = []

    # 1. Webhook Trigger
    nodes.append({"parameters": {"path": "booking-scheduler", "responseMode": "responseNode", "options": {}},
                   "id": uid(), "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
                   "position": [220, 300], "webhookId": uid()})

    # 2. Parse Input (Code)
    nodes.append({"parameters": {"jsCode": """const body = $input.first().json.body || $input.first().json;
return { json: {
  booking_id: 'BOOK-' + Date.now().toString(36).toUpperCase(),
  contact_name: body.contact_name || '',
  contact_email: body.contact_email || '',
  meeting_type: body.meeting_type || 'General',
  preferred_date: body.preferred_date || '',
  duration_min: body.duration_min || 30,
  received_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Parse Input",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [440, 300]})

    # 3. Fetch Calendar Availability (Google Calendar API)
    nodes.append({"parameters": {
        "method": "POST",
        "url": "=" + GOOGLE_CALENDAR_API + "/freeBusy",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "googleCalendarOAuth2Api",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": '={"timeMin":"{{ DateTime.fromISO($json.preferred_date).minus({days:2}).toISO() }}","timeMax":"{{ DateTime.fromISO($json.preferred_date).plus({days:2}).toISO() }}","items":[{"id":"primary"}]}',
        "options": {"timeout": 15000}},
                   "id": uid(), "name": "Fetch Calendar Availability",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [660, 300]})

    # 4. Find Available Slots (Code)
    nodes.append({"parameters": {"jsCode": """const parsed = $('Parse Input').first().json;
const busyData = $input.first().json;
const busySlots = (busyData.calendars && busyData.calendars.primary)
  ? busyData.calendars.primary.busy || []
  : [];
const preferredDate = parsed.preferred_date;
const durationMin = parsed.duration_min || 30;

// Generate candidate slots: preferred_date +/- 2 days, 08:00-17:00 SAST (06:00-15:00 UTC)
const candidates = [];
const baseDate = new Date(preferredDate);
for (let dayOffset = -2; dayOffset <= 2; dayOffset++) {
  const day = new Date(baseDate);
  day.setDate(day.getDate() + dayOffset);
  const dayOfWeek = day.getDay();
  if (dayOfWeek === 0 || dayOfWeek === 6) continue; // skip weekends

  for (let hour = 6; hour <= 14; hour++) {
    for (let min = 0; min < 60; min += 30) {
      const slotStart = new Date(day);
      slotStart.setUTCHours(hour, min, 0, 0);
      const slotEnd = new Date(slotStart.getTime() + durationMin * 60000);
      if (slotEnd.getUTCHours() > 15 || (slotEnd.getUTCHours() === 15 && slotEnd.getUTCMinutes() > 0)) continue;

      const isBusy = busySlots.some(b => {
        const bStart = new Date(b.start);
        const bEnd = new Date(b.end);
        return slotStart < bEnd && slotEnd > bStart;
      });
      if (!isBusy) {
        candidates.push({
          start: slotStart.toISOString(),
          end: slotEnd.toISOString(),
          date_label: slotStart.toISOString().split('T')[0],
          time_label: slotStart.toISOString().split('T')[1].substring(0,5) + ' UTC'
        });
      }
    }
  }
}

return { json: {
  ...parsed,
  available_slots: candidates.slice(0, 20),
  total_available: candidates.length,
}};"""},
                   "id": uid(), "name": "Find Available Slots",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [880, 300]})

    # 5. AI Suggest Best Slots (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 600,
  "messages": [
    {"role": "system", "content": "You are a scheduling assistant for AnyVision Media. Given available time slots, suggest the best 3 options. Consider: proximity to preferred date, morning slots preferred for strategy meetings, afternoon for demos. Output JSON only: {recommended_slots: [{start, end, reason}], selected_slot: {start, end}}"},
    {"role": "user", "content": "Contact: {{ $json.contact_name }}\\nMeeting type: {{ $json.meeting_type }}\\nPreferred date: {{ $json.preferred_date }}\\nDuration: {{ $json.duration_min }} min\\nAvailable slots (first 20):\\n{{ JSON.stringify($json.available_slots.slice(0, 20)) }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Suggest Slots",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [1100, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 6. Extract AI Selection (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let ai = {};
try { ai = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { ai = {}; }
const parsed = $('Find Available Slots').first().json;
const selected = ai.selected_slot || (parsed.available_slots && parsed.available_slots[0]) || {};
return { json: {
  booking_id: parsed.booking_id,
  contact_name: parsed.contact_name,
  contact_email: parsed.contact_email,
  meeting_type: parsed.meeting_type,
  duration_min: parsed.duration_min,
  event_start: selected.start || '',
  event_end: selected.end || '',
  recommended_slots: ai.recommended_slots || [],
  booked_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Extract AI Selection",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [1320, 300]})

    # 7. Create Calendar Event (Google Calendar API)
    nodes.append({"parameters": {
        "method": "POST",
        "url": "=" + GOOGLE_CALENDAR_API + "/calendars/primary/events",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "googleCalendarOAuth2Api",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": '={"summary":"{{ $json.meeting_type }} - {{ $json.contact_name }}","description":"Booking ID: {{ $json.booking_id }}\\nContact: {{ $json.contact_email }}","start":{"dateTime":"{{ $json.event_start }}","timeZone":"Africa/Johannesburg"},"end":{"dateTime":"{{ $json.event_end }}","timeZone":"Africa/Johannesburg"},"attendees":[{"email":"{{ $json.contact_email }}"}],"reminders":{"useDefault":false,"overrides":[{"method":"email","minutes":60},{"method":"popup","minutes":15}]}}',
        "options": {"timeout": 15000}},
                   "id": uid(), "name": "Create Calendar Event",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [1540, 300]})

    # 8. Write to Booking_Log (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_BOOKING_LOG),
        "columns": {"value": {
            "booking_id": "={{ $('Extract AI Selection').first().json.booking_id }}",
            "contact_name": "={{ $('Extract AI Selection').first().json.contact_name }}",
            "contact_email": "={{ $('Extract AI Selection').first().json.contact_email }}",
            "meeting_type": "={{ $('Extract AI Selection').first().json.meeting_type }}",
            "meeting_date": "={{ $('Extract AI Selection').first().json.event_start }}",
            "duration_min": "={{ $('Extract AI Selection').first().json.duration_min }}",
            "status": "Scheduled",
            "follow_up_sent": "false",
            "booked_at": "={{ $('Extract AI Selection').first().json.booked_at }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Booking Log",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1760, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 9. Send Confirmation Email (Gmail)
    nodes.append({"parameters": {
        "sendTo": "={{ $('Extract AI Selection').first().json.contact_email }}",
        "subject": "=Meeting Confirmed: {{ $('Extract AI Selection').first().json.meeting_type }} [{{ $('Extract AI Selection').first().json.booking_id }}]",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">Meeting Confirmed</h2></div>
<div style="padding:20px">
<p>Hi {{ $('Extract AI Selection').first().json.contact_name }},</p>
<p>Your meeting has been scheduled:</p>
<ul>
<li><b>Type:</b> {{ $('Extract AI Selection').first().json.meeting_type }}</li>
<li><b>Date/Time:</b> {{ $('Extract AI Selection').first().json.event_start }}</li>
<li><b>Duration:</b> {{ $('Extract AI Selection').first().json.duration_min }} minutes</li>
<li><b>Booking ID:</b> {{ $('Extract AI Selection').first().json.booking_id }}</li>
</ul>
<p>A calendar invite has been sent to your email. See you there!</p>
<p>Best regards,<br>AnyVision Media</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AnyVision Media - ian@anyvisionmedia.com</div>
</div>""",
        "options": {}},
                   "id": uid(), "name": "Send Confirmation Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1980, 300], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    # 10. Respond Webhook
    nodes.append({"parameters": {"respondWith": "json",
        "responseBody": '={{ JSON.stringify({success: true, booking_id: $("Extract AI Selection").first().json.booking_id, event_start: $("Extract AI Selection").first().json.event_start, event_end: $("Extract AI Selection").first().json.event_end}) }}',
        "options": {}},
                   "id": uid(), "name": "Respond Webhook",
                   "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
                   "position": [2200, 300]})

    return nodes


def build_book01_connections(nodes):
    return {
        "Webhook": {"main": [[{"node": "Parse Input", "type": "main", "index": 0}]]},
        "Parse Input": {"main": [[{"node": "Fetch Calendar Availability", "type": "main", "index": 0}]]},
        "Fetch Calendar Availability": {"main": [[{"node": "Find Available Slots", "type": "main", "index": 0}]]},
        "Find Available Slots": {"main": [[{"node": "AI Suggest Slots", "type": "main", "index": 0}]]},
        "AI Suggest Slots": {"main": [[{"node": "Extract AI Selection", "type": "main", "index": 0}]]},
        "Extract AI Selection": {"main": [[{"node": "Create Calendar Event", "type": "main", "index": 0}]]},
        "Create Calendar Event": {"main": [[{"node": "Write Booking Log", "type": "main", "index": 0}]]},
        "Write Booking Log": {"main": [[{"node": "Send Confirmation Email", "type": "main", "index": 0}]]},
        "Send Confirmation Email": {"main": [[{"node": "Respond Webhook", "type": "main", "index": 0}]]},
    }


# ======================================================================
# BOOK-02: Follow-Up Nudge (Daily 09:00 SAST = 07:00 UTC)
# ======================================================================

def build_book02_nodes():
    nodes = []

    # 1. Schedule Trigger (Daily 07:00 UTC = 09:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 7 * * *"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
                   "position": [220, 300]})

    # 2. Read Upcoming Bookings (Airtable - status=Scheduled, meeting within 48h, follow_up_sent=false)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(ORCH_BASE_ID, TABLE_BOOKING_LOG),
        "filterByFormula": "=AND({status} = 'Scheduled', IS_BEFORE({meeting_date}, DATEADD(TODAY(), 2, 'days')), IS_AFTER({meeting_date}, NOW()), {follow_up_sent} = 'false')",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Read Upcoming Bookings",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [440, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Check if records found (If v2.2)
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $input.all().length }}", "rightValue": 0,
         "operator": {"type": "number", "operation": "gt"}}],
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"}}},
                   "id": uid(), "name": "Has Upcoming Meetings",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2,
                   "position": [660, 300]})

    # 4. Send Reminder Email (Gmail)
    nodes.append({"parameters": {
        "sendTo": "={{ $json.contact_email }}",
        "subject": "=Reminder: {{ $json.meeting_type }} Tomorrow [{{ $json.booking_id }}]",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">Meeting Reminder</h2></div>
<div style="padding:20px">
<p>Hi {{ $json.contact_name }},</p>
<p>Just a friendly reminder about your upcoming meeting:</p>
<ul>
<li><b>Type:</b> {{ $json.meeting_type }}</li>
<li><b>Date/Time:</b> {{ $json.meeting_date }}</li>
<li><b>Duration:</b> {{ $json.duration_min }} minutes</li>
<li><b>Booking ID:</b> {{ $json.booking_id }}</li>
</ul>
<p>Looking forward to connecting with you!</p>
<p>Best regards,<br>AnyVision Media</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AnyVision Media - ian@anyvisionmedia.com</div>
</div>""",
        "options": {}},
                   "id": uid(), "name": "Send Reminder Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [880, 300], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    # 5. Update Booking_Log: follow_up_sent = true (Airtable update)
    nodes.append({"parameters": {"operation": "update", **airtable_ref(ORCH_BASE_ID, TABLE_BOOKING_LOG),
        "columns": {"value": {"follow_up_sent": "true"}},
        "matchingColumns": ["booking_id"],
        "options": {}},
                   "id": uid(), "name": "Mark Follow-Up Sent",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1100, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    return nodes


def build_book02_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Read Upcoming Bookings", "type": "main", "index": 0}]]},
        "Read Upcoming Bookings": {"main": [[{"node": "Has Upcoming Meetings", "type": "main", "index": 0}]]},
        "Has Upcoming Meetings": {"main": [
            [{"node": "Send Reminder Email", "type": "main", "index": 0}],
            [],
        ]},
        "Send Reminder Email": {"main": [[{"node": "Mark Follow-Up Sent", "type": "main", "index": 0}]]},
    }


# ======================================================================
# BOOK-03: Calendar Optimizer (Friday 16:00 SAST = 14:00 UTC)
# ======================================================================

def build_book03_nodes():
    nodes = []

    # 1. Schedule Trigger (Friday 14:00 UTC = 16:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 14 * * 5"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
                   "position": [220, 300]})

    # 2. Fetch Next Week Calendar Events (Google Calendar API)
    nodes.append({"parameters": {
        "method": "GET",
        "url": "=" + GOOGLE_CALENDAR_API + "/calendars/primary/events",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "googleCalendarOAuth2Api",
        "sendQuery": True,
        "queryParameters": {"parameters": [
            {"name": "timeMin", "value": "={{ $now.plus({days: 3}).startOf('week').toISO() }}"},
            {"name": "timeMax", "value": "={{ $now.plus({days: 3}).startOf('week').plus({days: 5}).toISO() }}"},
            {"name": "singleEvents", "value": "true"},
            {"name": "orderBy", "value": "startTime"},
            {"name": "maxResults", "value": "100"},
        ]},
        "options": {"timeout": 15000}},
                   "id": uid(), "name": "Fetch Next Week Events",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [440, 300]})

    # 3. Analyze Meeting Density (Code)
    nodes.append({"parameters": {"jsCode": """const events = $input.first().json.items || [];
const days = {};
let totalMeetingMinutes = 0;

for (const evt of events) {
  const start = new Date(evt.start.dateTime || evt.start.date);
  const end = new Date(evt.end.dateTime || evt.end.date);
  const dayKey = start.toISOString().split('T')[0];
  const durationMin = Math.round((end - start) / 60000);

  if (!days[dayKey]) {
    days[dayKey] = { date: dayKey, events: [], total_minutes: 0, event_count: 0 };
  }
  days[dayKey].events.push({
    summary: evt.summary || 'No title',
    start: evt.start.dateTime || evt.start.date,
    end: evt.end.dateTime || evt.end.date,
    duration_min: durationMin,
  });
  days[dayKey].total_minutes += durationMin;
  days[dayKey].event_count += 1;
  totalMeetingMinutes += durationMin;
}

// Calculate focus time blocks (gaps >= 60 min between 06:00-15:00 UTC)
const focusBlocks = [];
for (const [dayKey, dayData] of Object.entries(days)) {
  const sorted = dayData.events.sort((a, b) => new Date(a.start) - new Date(b.start));
  let prevEnd = new Date(dayKey + 'T06:00:00Z');
  for (const evt of sorted) {
    const evtStart = new Date(evt.start);
    const gapMin = Math.round((evtStart - prevEnd) / 60000);
    if (gapMin >= 60) {
      focusBlocks.push({ date: dayKey, start: prevEnd.toISOString(), end: evtStart.toISOString(), duration_min: gapMin });
    }
    prevEnd = new Date(evt.end);
  }
  const eodGap = Math.round((new Date(dayKey + 'T15:00:00Z') - prevEnd) / 60000);
  if (eodGap >= 60) {
    focusBlocks.push({ date: dayKey, start: prevEnd.toISOString(), end: dayKey + 'T15:00:00Z', duration_min: eodGap });
  }
}

const overloaded = Object.values(days).filter(d => d.total_minutes > 360);
const workHoursPerDay = 540; // 9 hours
const totalWorkMin = Object.keys(days).length * workHoursPerDay;
const meetingRatio = totalWorkMin > 0 ? Math.round((totalMeetingMinutes / totalWorkMin) * 100) : 0;

return { json: {
  total_events: events.length,
  total_meeting_minutes: totalMeetingMinutes,
  meeting_ratio_pct: meetingRatio,
  days: Object.values(days),
  overloaded_days: overloaded.map(d => d.date),
  focus_blocks: focusBlocks,
  analyzed_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Analyze Meeting Density",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [660, 300]})

    # 4. AI Optimization Recommendations (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 1200,
  "messages": [
    {"role": "system", "content": "You are a calendar optimization expert for AnyVision Media. Analyze the meeting schedule and provide actionable recommendations. Consider: meeting density per day, focus time availability, back-to-back meetings, overloaded days. Output JSON: {summary: string, overload_warnings: [{day, issue, suggestion}], rescheduling_suggestions: [{event, reason, suggested_time}], focus_blocks: [{day, time_range, recommended_use}], weekly_score: 0-100}"},
    {"role": "user", "content": "Calendar analysis for next week:\\nTotal events: {{ $json.total_events }}\\nMeeting ratio: {{ $json.meeting_ratio_pct }}%\\nOverloaded days: {{ JSON.stringify($json.overloaded_days) }}\\nDay breakdown: {{ JSON.stringify($json.days) }}\\nFocus blocks: {{ JSON.stringify($json.focus_blocks) }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Calendar Optimization",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [880, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 5. Extract Recommendations (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let ai = {};
try { ai = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { ai = {summary: 'Parse failed', weekly_score: 0}; }
const analysis = $('Analyze Meeting Density').first().json;
return { json: {
  booking_id: 'OPT-' + Date.now().toString(36).toUpperCase(),
  contact_name: 'Calendar Optimizer',
  contact_email: '""" + ALERT_EMAIL + """',
  meeting_type: 'Calendar Optimization Report',
  status: 'Report',
  ai_summary: ai.summary || '',
  weekly_score: ai.weekly_score || 0,
  overload_warnings: ai.overload_warnings || [],
  rescheduling_suggestions: ai.rescheduling_suggestions || [],
  focus_blocks: ai.focus_blocks || [],
  total_events: analysis.total_events,
  meeting_ratio_pct: analysis.meeting_ratio_pct,
  analyzed_at: analysis.analyzed_at,
}};"""},
                   "id": uid(), "name": "Extract Recommendations",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [1100, 300]})

    # 6. Write Analysis to Booking_Log (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_BOOKING_LOG),
        "columns": {"value": {
            "booking_id": "={{ $json.booking_id }}",
            "contact_name": "={{ $json.contact_name }}",
            "contact_email": "={{ $json.contact_email }}",
            "meeting_type": "={{ $json.meeting_type }}",
            "status": "Report",
            "booked_at": "={{ $json.analyzed_at }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Analysis to Log",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1320, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 7. Email Weekly Calendar Report (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=Weekly Calendar Optimization Report - Score: {{ $('Extract Recommendations').first().json.weekly_score }}/100",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">Calendar Optimization Report</h2></div>
<div style="padding:20px">
<h3>Weekly Score: {{ $('Extract Recommendations').first().json.weekly_score }}/100</h3>
<p><b>Total Events:</b> {{ $('Extract Recommendations').first().json.total_events }} | <b>Meeting Ratio:</b> {{ $('Extract Recommendations').first().json.meeting_ratio_pct }}%</p>
<h3>Summary</h3>
<p>{{ $('Extract Recommendations').first().json.ai_summary }}</p>
<h3>Overload Warnings</h3>
<ul>{{ $('Extract Recommendations').first().json.overload_warnings.map(w => '<li><b>' + w.day + ':</b> ' + w.issue + ' -> ' + w.suggestion + '</li>').join('') || '<li>No overloaded days</li>' }}</ul>
<h3>Rescheduling Suggestions</h3>
<ul>{{ $('Extract Recommendations').first().json.rescheduling_suggestions.map(s => '<li><b>' + s.event + ':</b> ' + s.reason + ' -> ' + s.suggested_time + '</li>').join('') || '<li>No rescheduling needed</li>' }}</ul>
<h3>Recommended Focus Blocks</h3>
<ul>{{ $('Extract Recommendations').first().json.focus_blocks.map(f => '<li><b>' + f.day + ' ' + f.time_range + ':</b> ' + f.recommended_use + '</li>').join('') || '<li>No focus blocks identified</li>' }}</ul>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">Generated by AVM Calendar Optimizer</div>
</div>""",
        "options": {}},
                   "id": uid(), "name": "Email Calendar Report",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1540, 300], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_book03_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Fetch Next Week Events", "type": "main", "index": 0}]]},
        "Fetch Next Week Events": {"main": [[{"node": "Analyze Meeting Density", "type": "main", "index": 0}]]},
        "Analyze Meeting Density": {"main": [[{"node": "AI Calendar Optimization", "type": "main", "index": 0}]]},
        "AI Calendar Optimization": {"main": [[{"node": "Extract Recommendations", "type": "main", "index": 0}]]},
        "Extract Recommendations": {"main": [[{"node": "Write Analysis to Log", "type": "main", "index": 0}]]},
        "Write Analysis to Log": {"main": [[{"node": "Email Calendar Report", "type": "main", "index": 0}]]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "book01": {"name": "BOOK-01 Meeting Scheduler", "build_nodes": build_book01_nodes,
               "build_connections": build_book01_connections,
               "filename": "book01_meeting_scheduler.json", "tags": ["booking", "calendar", "webhook"]},
    "book02": {"name": "BOOK-02 Follow-Up Nudge", "build_nodes": build_book02_nodes,
               "build_connections": build_book02_connections,
               "filename": "book02_follow_up_nudge.json", "tags": ["booking", "reminder", "daily"]},
    "book03": {"name": "BOOK-03 Calendar Optimizer", "build_nodes": build_book03_nodes,
               "build_connections": build_book03_connections,
               "filename": "book03_calendar_optimizer.json", "tags": ["booking", "calendar", "optimization"]},
}


def build_workflow_json(key):
    builder = WORKFLOW_BUILDERS[key]
    nodes = builder["build_nodes"]()
    connections = builder["build_connections"](nodes)
    return {
        "name": builder["name"], "nodes": nodes, "connections": connections, "active": False,
        "settings": {"executionOrder": "v1", "saveManualExecutions": True,
                     "callerPolicy": "workflowsFromSameOwner"},
        "tags": builder["tags"],
        "meta": {"templateCredsSetupCompleted": True, "builder": "deploy_booking_assistant.py",
                 "built_at": datetime.now().isoformat()},
    }


def save_workflow(key, workflow_json):
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "booking"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / builder["filename"]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_json, f, indent=2, ensure_ascii=False)
    node_count = len(workflow_json["nodes"])
    print(f"  + {builder['name']:<40} ({node_count} nodes) -> {output_path}")
    return output_path


def deploy_workflow(key, workflow_json, activate=False):
    from n8n_client import N8nClient
    api_key = os.getenv("N8N_API_KEY")
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        sys.exit(1)
    client = N8nClient(base_url, api_key, timeout=30)
    builder = WORKFLOW_BUILDERS[key]
    deploy_payload = {k: v for k, v in workflow_json.items() if k not in ("tags", "meta", "active")}
    resp = client.create_workflow(deploy_payload)
    if resp and "id" in resp:
        wf_id = resp["id"]
        print(f"  + {builder['name']:<40} Deployed -> {wf_id}")
        if activate:
            import time
            time.sleep(2)
            client.activate_workflow(wf_id)
            print(f"    Activated: {wf_id}")
        return wf_id
    else:
        print(f"  - {builder['name']:<40} FAILED to deploy")
        return None


def main():
    if len(sys.argv) < 2:
        print("AVM Booking Assistant - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_booking_assistant.py build              # Build all")
        print("  python tools/deploy_booking_assistant.py build book01       # Build one")
        print("  python tools/deploy_booking_assistant.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_booking_assistant.py activate           # Build + Deploy + Activate")
        print()
        print("Workflows:")
        for key, builder in WORKFLOW_BUILDERS.items():
            print(f"  {key:<12} {builder['name']}")
        sys.exit(0)

    action = sys.argv[1].lower()
    target = sys.argv[2].lower() if len(sys.argv) > 2 else "all"

    if target == "all":
        keys = list(WORKFLOW_BUILDERS.keys())
    elif target in WORKFLOW_BUILDERS:
        keys = [target]
    else:
        print(f"Unknown workflow: {target}")
        print(f"Valid: {', '.join(WORKFLOW_BUILDERS.keys())}")
        sys.exit(1)

    print("=" * 60)
    print("AVM BOOKING ASSISTANT - WORKFLOW BUILDER")
    print("=" * 60)
    print()
    print(f"Action: {action}")
    print(f"Workflows: {', '.join(keys)}")
    print()

    if action == "build":
        print("Building workflow JSONs...")
        print("-" * 40)
        for key in keys:
            wf_json = build_workflow_json(key)
            save_workflow(key, wf_json)
        print()
        print("Build complete. Inspect workflows in: workflows/booking/")

    elif action in ("deploy", "activate"):
        do_activate = action == "activate"
        print(f"Building and deploying ({'+ activating' if do_activate else 'inactive'})...")
        print("-" * 40)
        deployed_ids = {}
        for key in keys:
            wf_json = build_workflow_json(key)
            save_workflow(key, wf_json)
            wf_id = deploy_workflow(key, wf_json, activate=do_activate)
            if wf_id:
                deployed_ids[key] = wf_id
        print()
        if deployed_ids:
            print("Deployed Workflow IDs:")
            for key, wf_id in deployed_ids.items():
                print(f"  {key}: {wf_id}")

    else:
        print(f"Unknown action: {action}")
        print("Valid: build, deploy, activate")
        sys.exit(1)


if __name__ == "__main__":
    main()

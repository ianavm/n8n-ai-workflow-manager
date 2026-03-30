"""
FA Presentation Workflow — Visual-only combined workflow.

Combines all 11 FA workflows into a single n8n canvas for client demos.
Uses sticky notes to label each section. NOT meant to execute.

Usage:
    python tools/deploy_fa_presentation.py build
    python tools/deploy_fa_presentation.py deploy
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass


def uid() -> str:
    return str(uuid.uuid4())


def sticky_note(name: str, content: str, position: list[int],
                width: int = 500, height: int = 200,
                color: int = 1) -> dict:
    """Create a sticky note node for section labeling.

    Colors: 1=yellow, 2=blue, 3=pink, 4=green, 5=purple, 6=gray, 7=red
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [position[0] - 20, position[1] - 80],
        "parameters": {
            "content": content,
            "width": width,
            "height": height,
            "color": color,
        },
    }


def placeholder_node(name: str, node_type: str, position: list[int],
                      type_version: float = 1, params: dict | None = None,
                      credentials: dict | None = None, notes: str = "") -> dict:
    """Create a visual placeholder node."""
    node = {
        "id": uid(),
        "name": name,
        "type": node_type,
        "typeVersion": type_version,
        "position": position,
        "parameters": params or {},
    }
    if credentials:
        node["credentials"] = credentials
    if notes:
        node["notes"] = notes
    return node


def conn(node: str, index: int = 0) -> dict:
    return {"node": node, "type": "main", "index": index}


CRED_OUTLOOK = {"microsoftOutlookOAuth2Api": {"id": "PLACEHOLDER", "name": "Outlook OAuth2 FA"}}
CRED_TEAMS = {"microsoftTeamsOAuth2Api": {"id": "PLACEHOLDER", "name": "Teams OAuth2 FA"}}
CRED_AIRTABLE = {"airtableTokenApi": {"id": "PLACEHOLDER", "name": "Airtable FA"}}


def build_nodes() -> list[dict]:
    nodes = []

    # ================================================================
    # HEADER STICKY NOTE
    # ================================================================
    nodes.append(sticky_note(
        "Header",
        "# Financial Advisory CRM\n\n"
        "**Complete automation system for financial advisory firms**\n\n"
        "- 11 interconnected workflows | 138+ nodes\n"
        "- Microsoft Teams + Outlook integration\n"
        "- AI-powered transcript analysis & insights\n"
        "- FAIS & POPIA compliance built-in\n"
        "- Client portal with real-time sync\n\n"
        "Built by **AnyVision Media** | South Africa",
        [0, -300], width=700, height=280, color=5,
    ))

    # ================================================================
    # ROW 1: FA-01 Client Intake (left) + FA-02 Meeting Scheduler (right)
    # ================================================================
    Y1 = 100

    nodes.append(sticky_note(
        "Section FA-01",
        "## FA-01: Client Intake & Onboarding\nWebhook receives intake form -> validates -> creates client record -> sends welcome email -> notifies adviser -> schedules discovery meeting",
        [0, Y1], width=1400, height=320, color=2,
    ))

    nodes.append(placeholder_node("01 Intake Webhook", "n8n-nodes-base.webhook", [40, Y1 + 100], 1.1,
        {"path": "advisory/intake", "httpMethod": "POST", "responseMode": "responseNode", "options": {}}))
    nodes.append(placeholder_node("01 Validate Input", "n8n-nodes-base.code", [260, Y1 + 100], 2,
        {"jsCode": "// Validate: first_name, last_name, email, phone, consent\n// Normalize SA phone to +27 format", "mode": "runOnceForAllItems"}))
    nodes.append(placeholder_node("01 Check Existing", "n8n-nodes-base.httpRequest", [480, Y1 + 100], 4.2,
        {"method": "GET", "url": "Supabase: fa_clients?email=eq.{email}", "options": {}},
        notes="Supabase REST"))
    nodes.append(placeholder_node("01 Create Client", "n8n-nodes-base.httpRequest", [700, Y1 + 50], 4.2,
        {"method": "POST", "url": "Supabase: fa_clients", "options": {}},
        notes="New client"))
    nodes.append(placeholder_node("01 Update Client", "n8n-nodes-base.httpRequest", [700, Y1 + 180], 4.2,
        {"method": "PATCH", "url": "Supabase: fa_clients/{id}", "options": {}},
        notes="Existing client"))
    nodes.append(placeholder_node("01 Record POPIA", "n8n-nodes-base.httpRequest", [950, Y1 + 50], 4.2,
        {"method": "POST", "url": "Supabase: fa_consent_records", "options": {}},
        notes="POPIA consent"))
    nodes.append(placeholder_node("01 Welcome Email", "n8n-nodes-base.microsoftOutlook", [950, Y1 + 180], 2,
        {"resource": "message", "operation": "send"}, CRED_OUTLOOK,
        notes="Welcome + portal link"))
    nodes.append(placeholder_node("01 Teams Notify", "n8n-nodes-base.microsoftTeams", [1180, Y1 + 50], 2,
        {"resource": "chatMessage", "operation": "create"}, CRED_TEAMS,
        notes="Alert adviser"))
    nodes.append(placeholder_node("01 Schedule Discovery", "n8n-nodes-base.executeWorkflow", [1180, Y1 + 180], 1,
        {"source": "database", "workflowId": "FA-02"},
        notes="-> FA-02"))

    # ================================================================
    # ROW 2: FA-02 Meeting Scheduler
    # ================================================================
    Y2 = 520

    nodes.append(sticky_note(
        "Section FA-02",
        "## FA-02: Meeting Scheduler (Sub-Workflow)\nCheck Outlook calendar availability -> create Teams meeting via Graph API -> send confirmations via email + WhatsApp -> log communications",
        [0, Y2], width=1400, height=320, color=3,
    ))

    nodes.append(placeholder_node("02 Sub-Workflow Trigger", "n8n-nodes-base.executeWorkflowTrigger", [40, Y2 + 100], 1.1))
    nodes.append(placeholder_node("02 Fetch Adviser", "n8n-nodes-base.httpRequest", [260, Y2 + 70], 4.2,
        {"method": "GET", "url": "Supabase: fa_advisers", "options": {}},
        notes="Get MS user ID"))
    nodes.append(placeholder_node("02 Check Calendar", "n8n-nodes-base.httpRequest", [480, Y2 + 70], 4.2,
        {"method": "POST", "url": "Graph API: /users/{id}/calendar/getSchedule", "options": {}},
        notes="Microsoft Graph"))
    nodes.append(placeholder_node("02 Find Slot", "n8n-nodes-base.code", [700, Y2 + 70], 2,
        {"jsCode": "// Find first 60-min open slot\n// Business hours 08:00-17:00 SAST\n// Skip weekends", "mode": "runOnceForAllItems"}))
    nodes.append(placeholder_node("02 Create Teams Meeting", "n8n-nodes-base.httpRequest", [920, Y2 + 70], 4.2,
        {"method": "POST", "url": "Graph API: /users/{id}/events\nisOnlineMeeting: true\nonlineMeetingProvider: teamsForBusiness", "options": {}},
        notes="Calendar event + Teams link"))
    nodes.append(placeholder_node("02 Store Meeting", "n8n-nodes-base.httpRequest", [920, Y2 + 200], 4.2,
        {"method": "POST", "url": "Supabase: fa_meetings", "options": {}},
        notes="Save to DB"))
    nodes.append(placeholder_node("02 Confirm Email", "n8n-nodes-base.microsoftOutlook", [1160, Y2 + 70], 2,
        {"resource": "message", "operation": "send"}, CRED_OUTLOOK,
        notes="Date + Teams link"))
    nodes.append(placeholder_node("02 WhatsApp Confirm", "n8n-nodes-base.httpRequest", [1160, Y2 + 200], 4.2,
        {"method": "POST", "url": "WhatsApp Cloud API: fa_meeting_confirm", "options": {}},
        notes="Template message"))

    # ================================================================
    # ROW 3: FA-03 Pre-Meeting + FA-07a Reminders
    # ================================================================
    Y3 = 940

    nodes.append(sticky_note(
        "Section FA-03",
        "## FA-03: Pre-Meeting Prep\nHourly scan -> 2h before meeting -> fetch client profile + products + history -> AI generates briefing -> send to adviser",
        [0, Y3], width=900, height=280, color=4,
    ))

    nodes.append(placeholder_node("03 Schedule (Hourly)", "n8n-nodes-base.scheduleTrigger", [40, Y3 + 100], 1.2,
        {"rule": {"interval": [{"field": "cronExpression", "expression": "0 * 6-18 * * 1-5"}]}}))
    nodes.append(placeholder_node("03 Upcoming Meetings", "n8n-nodes-base.httpRequest", [260, Y3 + 100], 4.2,
        {"method": "GET", "url": "Supabase: fa_meetings (next 2h)", "options": {}}))
    nodes.append(placeholder_node("03 Fetch Profile", "n8n-nodes-base.httpRequest", [480, Y3 + 100], 4.2,
        {"method": "GET", "url": "Supabase: client + products + dependents", "options": {}}))
    nodes.append(placeholder_node("03 AI Briefing", "n8n-nodes-base.httpRequest", [700, Y3 + 100], 4.2,
        {"method": "POST", "url": "OpenRouter: Claude Sonnet\n\"Generate pre-meeting briefing\"", "options": {}},
        notes="AI Analysis"))
    nodes.append(placeholder_node("03 Email Briefing", "n8n-nodes-base.microsoftOutlook", [700, Y3 + 230], 2,
        {"resource": "message", "operation": "send"}, CRED_OUTLOOK,
        notes="To adviser"))

    # FA-07a Reminders
    nodes.append(sticky_note(
        "Section FA-07a",
        "## FA-07a: Automated Reminders\n24h + 1h before: Email + WhatsApp to client, Teams alert to adviser",
        [980, Y3], width=500, height=280, color=1,
    ))

    nodes.append(placeholder_node("07a Schedule (30min)", "n8n-nodes-base.scheduleTrigger", [1020, Y3 + 100], 1.2,
        {"rule": {"interval": [{"field": "cronExpression", "expression": "*/30 7-19 * * 1-5"}]}}))
    nodes.append(placeholder_node("07a 24h Reminder", "n8n-nodes-base.microsoftOutlook", [1240, Y3 + 80], 2,
        {"resource": "message", "operation": "send"}, CRED_OUTLOOK,
        notes="Email + WhatsApp"))
    nodes.append(placeholder_node("07a 1h Reminder", "n8n-nodes-base.microsoftOutlook", [1240, Y3 + 200], 2,
        {"resource": "message", "operation": "send"}, CRED_OUTLOOK,
        notes="Email + WhatsApp + Teams"))

    # ================================================================
    # ROW 4: FA-04 Transcript + FA-05 Post-Meeting
    # ================================================================
    Y4 = 1340

    nodes.append(sticky_note(
        "Section FA-04",
        "## FA-04: Meeting Recording & Transcription\nPolls Microsoft Graph for transcripts every 15min -> downloads VTT -> AI extracts insights, priorities, objections, action items, compliance flags",
        [0, Y4], width=1400, height=340, color=7,
    ))

    nodes.append(placeholder_node("04 Schedule (15min)", "n8n-nodes-base.scheduleTrigger", [40, Y4 + 100], 1.2,
        {"rule": {"interval": [{"field": "cronExpression", "expression": "*/15 6-20 * * 1-5"}]}}))
    nodes.append(placeholder_node("04 Completed Meetings", "n8n-nodes-base.httpRequest", [260, Y4 + 100], 4.2,
        {"method": "GET", "url": "Supabase: fa_meetings (completed, no transcript)", "options": {}}))
    nodes.append(placeholder_node("04 Resolve Meeting ID", "n8n-nodes-base.httpRequest", [480, Y4 + 100], 4.2,
        {"method": "GET", "url": "Graph API: /onlineMeetings\n?$filter=joinWebUrl eq '{url}'", "options": {}},
        notes="Microsoft Graph"))
    nodes.append(placeholder_node("04 Get Transcript", "n8n-nodes-base.httpRequest", [700, Y4 + 100], 4.2,
        {"method": "GET", "url": "Graph Beta: /transcripts/{id}/content\nAccept: text/vtt", "options": {}},
        notes="VTT download"))
    nodes.append(placeholder_node("04 AI Analysis", "n8n-nodes-base.httpRequest", [920, Y4 + 100], 4.2,
        {"method": "POST", "url": "OpenRouter: Claude Sonnet\nExtract: summary, priorities,\nobjections, action_items,\ncompliance_flags, research_needs,\nsentiment, key_quotes", "options": {}},
        notes="AI Transcript Analysis"))
    nodes.append(placeholder_node("04 Store Insights", "n8n-nodes-base.httpRequest", [1140, Y4 + 100], 4.2,
        {"method": "POST", "url": "Supabase: fa_meeting_insights", "options": {}},
        notes="10 structured fields"))
    nodes.append(placeholder_node("04 Call Post-Meeting", "n8n-nodes-base.executeWorkflow", [1140, Y4 + 230], 1,
        {"source": "database", "workflowId": "FA-05"},
        notes="-> FA-05"))

    # ================================================================
    # ROW 5: FA-05 Post-Meeting + FA-06 Discovery Pipeline
    # ================================================================
    Y5 = 1780

    nodes.append(sticky_note(
        "Section FA-05",
        "## FA-05: Post-Meeting Processing\nGenerate client-friendly summary -> email to client -> create tasks from action items -> trigger discovery pipeline if discovery meeting",
        [0, Y5], width=700, height=300, color=2,
    ))

    nodes.append(placeholder_node("05 Trigger", "n8n-nodes-base.executeWorkflowTrigger", [40, Y5 + 100], 1.1))
    nodes.append(placeholder_node("05 AI Summary", "n8n-nodes-base.httpRequest", [240, Y5 + 100], 4.2,
        {"method": "POST", "url": "OpenRouter: Claude Sonnet\n\"Client-friendly summary\"", "options": {}},
        notes="Exclude compliance flags"))
    nodes.append(placeholder_node("05 Email Summary", "n8n-nodes-base.microsoftOutlook", [460, Y5 + 70], 2,
        {"resource": "message", "operation": "send"}, CRED_OUTLOOK,
        notes="To client"))
    nodes.append(placeholder_node("05 Create Tasks", "n8n-nodes-base.httpRequest", [460, Y5 + 200], 4.2,
        {"method": "POST", "url": "Supabase: fa_tasks (batch)", "options": {}},
        notes="From action_items"))

    # FA-06
    nodes.append(sticky_note(
        "Section FA-06",
        "## FA-06: Discovery -> Presentation Pipeline\nAI research analysis -> generate Record of Advice -> calculate pricing -> schedule presentation meeting",
        [780, Y5], width=700, height=300, color=6,
    ))

    nodes.append(placeholder_node("06 Trigger", "n8n-nodes-base.executeWorkflowTrigger", [820, Y5 + 100], 1.1))
    nodes.append(placeholder_node("06 AI Research", "n8n-nodes-base.httpRequest", [1020, Y5 + 70], 4.2,
        {"method": "POST", "url": "OpenRouter: Claude Sonnet\n\"Analyse gaps, recommend products\"", "options": {}},
        notes="Gap analysis"))
    nodes.append(placeholder_node("06 Record of Advice", "n8n-nodes-base.httpRequest", [1020, Y5 + 200], 4.2,
        {"method": "POST", "url": "OpenRouter: Claude Sonnet\n\"Draft FAIS-compliant RoA\"", "options": {}},
        notes="Compliance doc"))
    nodes.append(placeholder_node("06 Create Pricing", "n8n-nodes-base.httpRequest", [1240, Y5 + 70], 4.2,
        {"method": "POST", "url": "Supabase: fa_pricing (batch)", "options": {}},
        notes="Draft fees"))
    nodes.append(placeholder_node("06 Schedule Presentation", "n8n-nodes-base.executeWorkflow", [1240, Y5 + 200], 1,
        {"source": "database", "workflowId": "FA-02"},
        notes="-> FA-02"))

    # ================================================================
    # ROW 6: FA-07b Comms + FA-09 Documents
    # ================================================================
    Y6 = 2200

    nodes.append(sticky_note(
        "Section FA-07b",
        "## FA-07b: On-Demand Communications\nWebhook trigger -> route by channel (email/WhatsApp/Teams) -> send -> log to audit trail",
        [0, Y6], width=700, height=260, color=3,
    ))

    nodes.append(placeholder_node("07b Webhook", "n8n-nodes-base.webhook", [40, Y6 + 100], 1.1,
        {"path": "advisory/send-comm", "httpMethod": "POST", "responseMode": "responseNode", "options": {}}))
    nodes.append(placeholder_node("07b Route Channel", "n8n-nodes-base.switch", [260, Y6 + 100], 3.2,
        {"rules": {"values": []}, "options": {}},
        notes="email | whatsapp | teams"))
    nodes.append(placeholder_node("07b Send Email", "n8n-nodes-base.microsoftOutlook", [480, Y6 + 60], 2,
        {"resource": "message", "operation": "send"}, CRED_OUTLOOK))
    nodes.append(placeholder_node("07b Send WhatsApp", "n8n-nodes-base.httpRequest", [480, Y6 + 140], 4.2,
        {"method": "POST", "url": "WhatsApp Cloud API", "options": {}}))
    nodes.append(placeholder_node("07b Log Comms", "n8n-nodes-base.httpRequest", [480, Y6 + 220], 4.2,
        {"method": "POST", "url": "Supabase: fa_communications", "options": {}}))

    # FA-09
    nodes.append(sticky_note(
        "Section FA-09",
        "## FA-09: Document Management\nUpload webhook -> AI classification -> FICA check -> auto-verify if complete -> notify adviser",
        [780, Y6], width=700, height=260, color=4,
    ))

    nodes.append(placeholder_node("09 Upload Webhook", "n8n-nodes-base.webhook", [820, Y6 + 100], 1.1,
        {"path": "advisory/document-upload", "httpMethod": "POST", "responseMode": "responseNode", "options": {}}))
    nodes.append(placeholder_node("09 Store File", "n8n-nodes-base.httpRequest", [1020, Y6 + 80], 4.2,
        {"method": "POST", "url": "Supabase Storage: fa-documents/{client}/{type}", "options": {}},
        notes="Private bucket"))
    nodes.append(placeholder_node("09 AI Classify", "n8n-nodes-base.httpRequest", [1020, Y6 + 200], 4.2,
        {"method": "POST", "url": "OpenRouter: Claude Sonnet\n\"Classify document type\"", "options": {}},
        notes="16 document types"))
    nodes.append(placeholder_node("09 FICA Check", "n8n-nodes-base.code", [1240, Y6 + 80], 2,
        {"jsCode": "// Check: ID + proof_of_address + bank_statement\n// If all 3 present -> fica_status = verified", "mode": "runOnceForAllItems"},
        notes="Auto-verify"))
    nodes.append(placeholder_node("09 Notify Adviser", "n8n-nodes-base.microsoftOutlook", [1240, Y6 + 200], 2,
        {"resource": "message", "operation": "send"}, CRED_OUTLOOK))

    # ================================================================
    # ROW 7: FA-08 Compliance + FA-10 Reporting
    # ================================================================
    Y7 = 2580

    nodes.append(sticky_note(
        "Section FA-08",
        "## FA-08: Compliance & Audit Engine\nDaily scan: POPIA consent, FAIS disclosure, FICA verification, overdue tasks, pricing changes -> AI report -> alert on critical issues",
        [0, Y7], width=700, height=280, color=7,
    ))

    nodes.append(placeholder_node("08 Daily Schedule", "n8n-nodes-base.scheduleTrigger", [40, Y7 + 100], 1.2,
        {"rule": {"interval": [{"field": "cronExpression", "expression": "0 6 * * 1-5"}]}}))
    nodes.append(placeholder_node("08 Compliance RPC", "n8n-nodes-base.httpRequest", [240, Y7 + 100], 4.2,
        {"method": "POST", "url": "Supabase RPC: fa_get_compliance_summary", "options": {}},
        notes="6 compliance metrics"))
    nodes.append(placeholder_node("08 AI Report", "n8n-nodes-base.httpRequest", [440, Y7 + 100], 4.2,
        {"method": "POST", "url": "OpenRouter: Claude Sonnet\n\"Rate: OK / WARNING / CRITICAL\"", "options": {}},
        notes="Severity analysis"))
    nodes.append(placeholder_node("08 Email Report", "n8n-nodes-base.microsoftOutlook", [440, Y7 + 220], 2,
        {"resource": "message", "operation": "send"}, CRED_OUTLOOK,
        notes="To compliance officer"))
    nodes.append(placeholder_node("08 Teams Alert", "n8n-nodes-base.microsoftTeams", [640, Y7 + 220], 2,
        {"resource": "chatMessage", "operation": "create"}, CRED_TEAMS,
        notes="If CRITICAL"))

    # FA-10
    nodes.append(sticky_note(
        "Section FA-10",
        "## FA-10: Weekly Reporting & Analytics\nMonday 07:00: pipeline summary, meeting stats, task completion, compliance score -> AI executive summary -> email + Airtable sync",
        [780, Y7], width=700, height=280, color=1,
    ))

    nodes.append(placeholder_node("10 Weekly Schedule", "n8n-nodes-base.scheduleTrigger", [820, Y7 + 100], 1.2,
        {"rule": {"interval": [{"field": "cronExpression", "expression": "0 7 * * 1"}]}}))
    nodes.append(placeholder_node("10 Pipeline Summary", "n8n-nodes-base.httpRequest", [1020, Y7 + 80], 4.2,
        {"method": "POST", "url": "Supabase RPC: fa_get_pipeline_summary", "options": {}},
        notes="11 pipeline stages"))
    nodes.append(placeholder_node("10 Aggregate Stats", "n8n-nodes-base.code", [1020, Y7 + 200], 2,
        {"jsCode": "// Meetings: booked, completed, no-shows\n// Tasks: completed, overdue\n// New clients, compliance score", "mode": "runOnceForAllItems"}))
    nodes.append(placeholder_node("10 AI Summary", "n8n-nodes-base.httpRequest", [1240, Y7 + 80], 4.2,
        {"method": "POST", "url": "OpenRouter: Claude Sonnet\n\"Weekly executive summary\"", "options": {}},
        notes="Highlights + concerns"))
    nodes.append(placeholder_node("10 Email Report", "n8n-nodes-base.microsoftOutlook", [1240, Y7 + 200], 2,
        {"resource": "message", "operation": "send"}, CRED_OUTLOOK,
        notes="To firm admin"))

    # ================================================================
    # FOOTER: Architecture diagram sticky
    # ================================================================
    nodes.append(sticky_note(
        "Architecture",
        "# System Architecture\n\n"
        "```\n"
        "CLIENT PORTAL (Next.js + Supabase)\n"
        "  /portal/advisory/* — Client dashboard, meetings, tasks, documents, pricing\n"
        "  /admin/advisory/*  — Adviser pipeline, compliance, analytics\n"
        "  /api/advisory/*    — 14 REST endpoints with role-based access\n"
        "\n"
        "DATABASE (Supabase PostgreSQL)\n"
        "  16 fa_* tables | Row-Level Security | Audit triggers\n"
        "  3 RPC functions | Storage bucket for documents\n"
        "\n"
        "INTEGRATIONS\n"
        "  Microsoft: Outlook Email + Calendar + Teams Meetings + Graph API Transcripts\n"
        "  WhatsApp: Cloud API template messages (confirmations, reminders)\n"
        "  AI: OpenRouter -> Claude Sonnet (briefings, transcripts, compliance, research)\n"
        "  Airtable: Operational dashboards (pipeline, metrics, compliance log)\n"
        "```\n\n"
        "**Compliance:** FAIS Act (Record of Advice, Fee Disclosure) + POPIA (Consent Management, Data Protection)\n\n"
        "**Multi-Tenant:** Each advisory firm isolated by firm_id across all tables",
        [0, 2960], width=1480, height=420, color=5,
    ))

    return nodes


def build_connections() -> dict:
    """Build visual connections between nodes."""
    return {
        # FA-01 flow
        "01 Intake Webhook": {"main": [[conn("01 Validate Input")]]},
        "01 Validate Input": {"main": [[conn("01 Check Existing")]]},
        "01 Check Existing": {"main": [[conn("01 Create Client"), conn("01 Update Client")]]},
        "01 Create Client": {"main": [[conn("01 Record POPIA")]]},
        "01 Update Client": {"main": [[conn("01 Welcome Email")]]},
        "01 Record POPIA": {"main": [[conn("01 Teams Notify")]]},
        "01 Welcome Email": {"main": [[conn("01 Schedule Discovery")]]},
        "01 Teams Notify": {"main": [[conn("01 Schedule Discovery")]]},

        # FA-02 flow
        "02 Sub-Workflow Trigger": {"main": [[conn("02 Fetch Adviser")]]},
        "02 Fetch Adviser": {"main": [[conn("02 Check Calendar")]]},
        "02 Check Calendar": {"main": [[conn("02 Find Slot")]]},
        "02 Find Slot": {"main": [[conn("02 Create Teams Meeting")]]},
        "02 Create Teams Meeting": {"main": [[conn("02 Store Meeting")]]},
        "02 Store Meeting": {"main": [[conn("02 Confirm Email"), conn("02 WhatsApp Confirm")]]},

        # FA-03 flow
        "03 Schedule (Hourly)": {"main": [[conn("03 Upcoming Meetings")]]},
        "03 Upcoming Meetings": {"main": [[conn("03 Fetch Profile")]]},
        "03 Fetch Profile": {"main": [[conn("03 AI Briefing")]]},
        "03 AI Briefing": {"main": [[conn("03 Email Briefing")]]},

        # FA-07a flow
        "07a Schedule (30min)": {"main": [[conn("07a 24h Reminder")]]},
        "07a 24h Reminder": {"main": [[conn("07a 1h Reminder")]]},

        # FA-04 flow
        "04 Schedule (15min)": {"main": [[conn("04 Completed Meetings")]]},
        "04 Completed Meetings": {"main": [[conn("04 Resolve Meeting ID")]]},
        "04 Resolve Meeting ID": {"main": [[conn("04 Get Transcript")]]},
        "04 Get Transcript": {"main": [[conn("04 AI Analysis")]]},
        "04 AI Analysis": {"main": [[conn("04 Store Insights")]]},
        "04 Store Insights": {"main": [[conn("04 Call Post-Meeting")]]},

        # FA-05 flow
        "05 Trigger": {"main": [[conn("05 AI Summary")]]},
        "05 AI Summary": {"main": [[conn("05 Email Summary"), conn("05 Create Tasks")]]},

        # FA-06 flow
        "06 Trigger": {"main": [[conn("06 AI Research")]]},
        "06 AI Research": {"main": [[conn("06 Record of Advice")]]},
        "06 Record of Advice": {"main": [[conn("06 Create Pricing")]]},
        "06 Create Pricing": {"main": [[conn("06 Schedule Presentation")]]},

        # FA-07b flow
        "07b Webhook": {"main": [[conn("07b Route Channel")]]},
        "07b Route Channel": {"main": [[conn("07b Send Email")], [conn("07b Send WhatsApp")], [conn("07b Log Comms")]]},

        # FA-09 flow
        "09 Upload Webhook": {"main": [[conn("09 Store File")]]},
        "09 Store File": {"main": [[conn("09 AI Classify")]]},
        "09 AI Classify": {"main": [[conn("09 FICA Check")]]},
        "09 FICA Check": {"main": [[conn("09 Notify Adviser")]]},

        # FA-08 flow
        "08 Daily Schedule": {"main": [[conn("08 Compliance RPC")]]},
        "08 Compliance RPC": {"main": [[conn("08 AI Report")]]},
        "08 AI Report": {"main": [[conn("08 Email Report")]]},
        "08 Email Report": {"main": [[conn("08 Teams Alert")]]},

        # FA-10 flow
        "10 Weekly Schedule": {"main": [[conn("10 Pipeline Summary")]]},
        "10 Pipeline Summary": {"main": [[conn("10 Aggregate Stats")]]},
        "10 Aggregate Stats": {"main": [[conn("10 AI Summary")]]},
        "10 AI Summary": {"main": [[conn("10 Email Report")]]},
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python deploy_fa_presentation.py <build|deploy>")
        sys.exit(1)

    command = sys.argv[1].lower()
    nodes = build_nodes()
    connections = build_connections()

    workflow = {
        "name": "FA - Financial Advisory CRM (Presentation Overview)",
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
        },
    }

    output_dir = Path(__file__).parent.parent / "workflows" / "financial-advisory"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "fa_presentation_overview.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    node_count = len([n for n in nodes if n["type"] != "n8n-nodes-base.stickyNote"])
    sticky_count = len([n for n in nodes if n["type"] == "n8n-nodes-base.stickyNote"])
    print(f"Built: {path} ({node_count} nodes + {sticky_count} sticky notes)")

    if command == "deploy":
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


if __name__ == "__main__":
    main()

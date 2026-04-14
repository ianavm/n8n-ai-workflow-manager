"""
Personal Ops / AVM Coach — n8n Workflow Deployment Script

Builds, deploys, and activates the 100-Day Challenge gamification workflows.

Workflows:

    PP-01  Morning Mission Board   Daily 06:30 SAST (cron "30 4 * * *" UTC)
           Reads Google Calendar + PP_Player + 7-day perf snapshots.
           Claude Sonnet generates 6-9 gamified missions aligned to:
             - 100 Day Challenge phase + weekly theme (Mon_Metrics…)
             - Current player difficulty + streak
             - Free calendar slots between 07:00-20:00 SAST
           Creates PP_Missions rows + Google Calendar events,
           writes event IDs back to PP_Missions,
           sends mission board to Telegram (chat 6311361442).

    PP-02  Midday Check-in          Daily 13:00 SAST (cron "0 11 * * *" UTC)
           Pure read, no AI, no writes. Reads today's PP_Missions +
           PP_Player + today's PP_XP_Log. Renders Telegram check-in
           with Must-Complete progress bar, XP earned so far, remaining
           working hours, and a deterministic coach nudge keyed to the
           Must-Complete completion rate.

    PP-03  Evening Review           (Phase 2 — pending)
    PP-04  Weekly Boss Battle       (Phase 4 — pending)
    PP-05  Adaptive Difficulty Tuner (Phase 3 — pending)

Usage:
    python tools/deploy_personal_ops_dept.py build            # build all (inactive, write JSONs)
    python tools/deploy_personal_ops_dept.py build pp01       # build single workflow
    python tools/deploy_personal_ops_dept.py deploy           # push to n8n (inactive)
    python tools/deploy_personal_ops_dept.py activate         # push + activate

Prerequisites (all in .env):
    N8N_API_KEY, N8N_BASE_URL
    AIRTABLE_API_TOKEN, MARKETING_AIRTABLE_BASE_ID
    PP_TABLE_PLAYER, PP_TABLE_MISSIONS, PP_TABLE_PERF_SNAPSHOTS
    PP_TELEGRAM_CHAT_ID, PP_LAUNCH_DATE, PP_GCAL_ID
    OpenRouter / Google Calendar / Telegram / Airtable creds in credentials.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))
from credentials import (  # noqa: E402
    CRED_AIRTABLE,
    CRED_GOOGLE_CALENDAR,
    CRED_OPENROUTER,
)

# AVM Coach uses the AVMCRMBot Telegram bot (chat 6311361442), NOT the
# shared RE Operations bot. Credential lives in n8n with ID Ha3Ewmk9ofbvWyZ9.
CRED_TELEGRAM_AVM_CRM = {
    "id": os.getenv("N8N_CRED_TELEGRAM_AVM_CRM", "Ha3Ewmk9ofbvWyZ9"),
    "name": "Telegram AVMCRMBot",
}

# ============================================================
# CONFIG
# ============================================================

MARKETING_BASE_ID: str = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")

PP_TABLE_PLAYER: str = os.getenv("PP_TABLE_PLAYER", "tblSQ3DJ3o7gv2zli")
PP_TABLE_MISSIONS: str = os.getenv("PP_TABLE_MISSIONS", "tblD66W7bTOoMxczA")
PP_TABLE_XP_LOG: str = os.getenv("PP_TABLE_XP_LOG", "tbldpF8Q2rKuGmKOn")
PP_TABLE_PERF_SNAPSHOTS: str = os.getenv("PP_TABLE_PERF_SNAPSHOTS", "tbl9OoFiM0kxGc48T")
PP_TABLE_BOSS_BATTLES: str = os.getenv("PP_TABLE_BOSS_BATTLES", "tblP7Uj60ase4jWgR")
PP_TABLE_ACHIEVEMENTS: str = os.getenv("PP_TABLE_ACHIEVEMENTS", "tblNoyOJmqfuMm7rI")

PP_TELEGRAM_CHAT_ID: str = os.getenv("PP_TELEGRAM_CHAT_ID", "6311361442")
PP_LAUNCH_DATE: str = os.getenv("PP_LAUNCH_DATE", "2026-04-22")
PP_GCAL_ID: str = os.getenv("PP_GCAL_ID", "primary")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "anthropic/claude-sonnet-4.5"

TIMEZONE = "Africa/Johannesburg"
WORKING_START_HOUR = 7
WORKING_END_HOUR = 20

# Category → Google Calendar colorId
CATEGORY_COLOR_MAP = {
    "Revenue": "11",      # red
    "Growth": "5",        # yellow
    "Build": "9",         # blue
    "Learning": "10",     # green
    "Maintenance": "8",   # gray
}

# Weekday (0=Mon) → 100 Day theme
WEEKDAY_THEME_MAP = {
    0: "Mon_Metrics",
    1: "Tue_Tutorial",
    2: "Wed_Win",
    3: "Thu_Thought",
    4: "Fri_Fails",
    5: "Sat_Strategy",
    6: "Sun_Story",
}


# ============================================================
# HELPERS
# ============================================================

def uid() -> str:
    return str(uuid.uuid4())


def airtable_ref(base_id: str, table_id: str) -> dict:
    return {
        "base": {"__rl": True, "value": base_id, "mode": "id"},
        "table": {"__rl": True, "value": table_id, "mode": "id"},
    }


def pos(col: int, row: int = 0) -> list[int]:
    """Grid position. col=horizontal slot (~260px), row=vertical offset."""
    return [200 + col * 260, 300 + row * 180]


# ============================================================
# NODE BUILDERS
# ============================================================

def node_schedule_cron(name: str, cron_expr: str, position: list) -> dict:
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": position,
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": cron_expr}],
            },
        },
    }


def node_code(name: str, js_code: str, position: list) -> dict:
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": {"jsCode": js_code},
    }


def node_airtable_search(
    name: str,
    base_id: str,
    table_id: str,
    position: list,
    filter_formula: str | None = None,
    limit: int = 10,
) -> dict:
    params: dict = {
        "operation": "search",
        **airtable_ref(base_id, table_id),
        "returnAll": False,
        "limit": limit,
        "options": {},
    }
    if filter_formula:
        params["filterByFormula"] = filter_formula
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "alwaysOutputData": True,
        "position": position,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": params,
    }


def node_airtable_create(
    name: str,
    base_id: str,
    table_id: str,
    position: list,
    column_values: dict[str, str],
) -> dict:
    """Airtable Create with defineBelow mapping.

    column_values: {field_name: n8n_expression_string}. Expressions should
    start with '=' if they contain {{...}}.
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": position,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "create",
            **airtable_ref(base_id, table_id),
            "columns": {
                "mappingMode": "defineBelow",
                "value": column_values,
            },
            "options": {},
        },
    }


def node_airtable_update(
    name: str,
    base_id: str,
    table_id: str,
    position: list,
    matching_columns: list[str],
    column_values: dict[str, str],
) -> dict:
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": position,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "update",
            **airtable_ref(base_id, table_id),
            "columns": {
                "mappingMode": "defineBelow",
                "matchingColumns": matching_columns,
                "value": column_values,
            },
            "options": {},
        },
    }


def node_http_openrouter(
    name: str,
    system_prompt: str,
    user_message_expr: str,
    position: list,
    max_tokens: int = 2500,
    temperature: float = 0.4,
    force_json: bool = True,
    x_title: str = "AVM Coach",
) -> dict:
    body: dict = {
        "model": OPENROUTER_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "__USER_MSG_PLACEHOLDER__"},
        ],
    }
    if force_json:
        body["response_format"] = {"type": "json_object"}

    body_json = json.dumps(body)
    body_json = body_json.replace(
        '"__USER_MSG_PLACEHOLDER__"',
        '"{{ ' + user_message_expr + ' }}"',
    )
    body_expr = "=" + body_json

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": position,
        "credentials": {"openRouterApi": CRED_OPENROUTER},
        "parameters": {
            "method": "POST",
            "url": OPENROUTER_URL,
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "openRouterApi",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "HTTP-Referer", "value": "https://www.anyvisionmedia.com"},
                    {"name": "X-Title", "value": x_title},
                    {"name": "Content-Type", "value": "application/json"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": body_expr,
            "options": {"timeout": 90000},
        },
    }


def node_http_gcal_list(name: str, position: list, calendar_id: str = "primary") -> dict:
    """GET https://www.googleapis.com/calendar/v3/calendars/{id}/events
    timeMin/timeMax come from upstream $json.day_start_iso / day_end_iso."""
    url = f"=https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": position,
        "credentials": {"googleCalendarOAuth2Api": CRED_GOOGLE_CALENDAR},
        "parameters": {
            "method": "GET",
            "url": url,
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "googleCalendarOAuth2Api",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "timeMin", "value": "={{ $json.day_start_iso }}"},
                    {"name": "timeMax", "value": "={{ $json.day_end_iso }}"},
                    {"name": "singleEvents", "value": "true"},
                    {"name": "orderBy", "value": "startTime"},
                    {"name": "maxResults", "value": "50"},
                ],
            },
            "options": {"timeout": 15000},
        },
    }


def node_gcal_create(name: str, position: list, calendar_id: str = "primary") -> dict:
    """Native Google Calendar node — pattern copied from business_email_mgmt_automation.json."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.googleCalendar",
        "typeVersion": 1,
        "onError": "continueRegularOutput",
        "position": position,
        "credentials": {"googleCalendarOAuth2Api": CRED_GOOGLE_CALENDAR},
        "parameters": {
            "calendar": calendar_id,
            "start": "={{ $json.scheduled_start_iso }}",
            "end": "={{ $json.scheduled_end_iso }}",
            "additionalFields": {
                "summary": "=[{{ $json.category }}] {{ $json.title }} - {{ $json.xp_value }}XP",
                "description": "={{ $json.description }}. Tier: {{ $json.tier }}. Theme: {{ $json.linked_100day_theme || 'n/a' }}. Mission ID: {{ $json.mission_id }}",
                "colorId": "={{ $json.color_id }}",
            },
        },
    }


def node_telegram_send(
    name: str,
    chat_id: str,
    text_expr: str,
    position: list,
    reply_markup_expr: str | None = None,
) -> dict:
    additional_fields: dict = {
        "parse_mode": "Markdown",
        "disable_notification": False,
    }
    # Native telegram v1.2 node forwards additionalFields.reply_markup verbatim
    # to the Bot API sendMessage endpoint. Pass a JSON string expression like
    # '={{ $json.reply_markup }}' where $json.reply_markup is already
    # JSON.stringify({inline_keyboard: [[{text, callback_data}, ...]]}).
    if reply_markup_expr:
        additional_fields["reply_markup"] = reply_markup_expr
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "onError": "continueRegularOutput",
        "position": position,
        "credentials": {"telegramApi": CRED_TELEGRAM_AVM_CRM},
        "parameters": {
            "operation": "sendMessage",
            "chatId": chat_id,
            "text": text_expr,
            "additionalFields": additional_fields,
        },
    }


def node_telegram_trigger(name: str, updates: list[str], position: list) -> dict:
    """Telegram Trigger listening to specific update types (e.g. ['callback_query'])."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.telegramTrigger",
        "typeVersion": 1.2,
        "position": position,
        "credentials": {"telegramApi": CRED_TELEGRAM_AVM_CRM},
        "parameters": {
            "updates": updates,
            "additionalFields": {},
        },
    }


def node_telegram_answer_query(
    name: str,
    position: list,
    query_id_expr: str,
    text_expr: str,
) -> dict:
    """Telegram Bot API answerCallbackQuery — dismisses the button spinner
    and (optionally) shows a toast to the tapping user."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "onError": "continueRegularOutput",
        "position": position,
        "credentials": {"telegramApi": CRED_TELEGRAM_AVM_CRM},
        "parameters": {
            "resource": "callback",
            "operation": "answerQuery",
            "queryId": query_id_expr,
            "additionalFields": {
                "text": text_expr,
                "show_alert": False,
            },
        },
    }


def node_airtable_get(
    name: str,
    base_id: str,
    table_id: str,
    position: list,
    record_id_expr: str,
) -> dict:
    """Airtable v2 'get' operation — direct fetch by record id (rec...)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "alwaysOutputData": True,
        "position": position,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "get",
            **airtable_ref(base_id, table_id),
            "id": record_id_expr,
            "options": {},
        },
    }


def node_gcal_update(
    name: str,
    position: list,
    calendar_id: str,
    event_id_expr: str,
    summary_expr: str,
    color_id: str,
) -> dict:
    """Native Google Calendar 'update' operation. `color` in updateFields
    maps to Google's colorId (1-11) — see GoogleCalendar.node.ts:682.

    `calendar` is declared as a resourceLocator in EventDescription.ts:57.
    Pass it in RL shape (not a plain string) so n8n validators accept the
    node on deploy — runtime is lenient but static validators are strict.
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.googleCalendar",
        "typeVersion": 1,
        "onError": "continueRegularOutput",
        "position": position,
        "credentials": {"googleCalendarOAuth2Api": CRED_GOOGLE_CALENDAR},
        "parameters": {
            "operation": "update",
            "calendar": {"__rl": True, "value": calendar_id, "mode": "list"},
            "eventId": event_id_expr,
            "useDefaultReminders": True,
            "updateFields": {
                "summary": summary_expr,
                "color": color_id,
            },
        },
    }


def node_if_truthy(name: str, position: list, value_expr: str) -> dict:
    """n8n If v2 node checking whether `value_expr` is truthy.
    Output 0 = TRUE branch, output 1 = FALSE branch."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": position,
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "loose",
                },
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": value_expr,
                        "rightValue": "",
                        "operator": {
                            "type": "boolean",
                            "operation": "true",
                            "singleValue": True,
                        },
                    },
                ],
                "combinator": "and",
            },
            "options": {},
        },
    }


def node_split_in_batches(name: str, position: list, batch_size: int = 1) -> dict:
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.splitInBatches",
        "typeVersion": 3,
        "position": position,
        "parameters": {
            "batchSize": batch_size,
            "options": {},
        },
    }


# ============================================================
# PP-01: Morning Mission Board
# ============================================================

PP01_SYSTEM_PROMPT = """You are Ian Immelman's AVM Coach.

CONTEXT: Ian is running a "100 Days of Building South Africa's First Million-Dollar AI Company" challenge. You are generating his daily mission board.

ABOUT IAN:
- Solo founder, AnyVision Media (AVM), Johannesburg, ZAR currency, UK English spelling
- Building agency services + digital products + consulting ladder
- Brand: AVM (agency) + Ian Immelman (personal founder brand). Dual-brand strategy.
- Deep n8n + AI automation stack (34+ workflows across 7 departments)

REVENUE LADDER (month-target must align to current phase):
- Month 1-2:  R20K-R40K/mo  (2-3 clients, free AI Audit funnel, R2,500/hr consulting)
- Month 3-4:  R60K-R100K/mo (5-7 clients, digital products R499-R999, case studies)
- Month 5-6:  R100K-R180K/mo (8+ clients, course R1,999-R4,999, events R5-25K)

WEEKDAY CONTENT THEMES (at least ONE Growth mission MUST align with today's theme):
- Mon_Metrics   — Weekly numbers, revenue, honest dashboard
- Tue_Tutorial  — Teach one specific thing (automation, prompt, workflow)
- Wed_Win       — One concrete win (client, deal, system shipped)
- Thu_Thought   — Opinion/essay (AI, SA tech, agency economics)
- Fri_Fails     — What broke this week, lessons
- Sat_Strategy  — Long-form strategic thinking
- Sun_Story     — Personal narrative, connection > conversion

CATEGORIES:
- Revenue      Non-negotiable income work. Always prefer for Must-Complete slots.
- Growth       Content, SEO, ads, brand. Must match weekday theme for ≥1 mission.
- Build        Ship workflows, systems, product features.
- Learning     Must produce an artifact (notes, summary, re-applied lesson).
- Maintenance  Admin, follow-ups, CRM hygiene. Cap at 1-2 per day.

TIERS + XP BANDS (respect Player's difficulty multiplier below):
- Must-Complete  60-120 XP  (2-3 missions, bias Revenue/Growth, non-negotiable)
- High-Value     30-60 XP   (2-3 missions)
- Optional       10-30 XP   (1-3 missions)

DIFFICULTY MULTIPLIER (applied to XP bands):
Easy 0.8× · Normal 1.0× · Hard 1.2× · Legendary 1.4×

HARD CONSTRAINTS:
1. Generate 6-9 missions total.
2. At least ONE Growth mission MUST match today's weekday theme.
3. Total focus time ≤ 360 minutes (6 hours).
4. Respect free calendar slots passed in user message — do not schedule into busy slots.
5. Mission titles start with a verb, ≤80 chars.
6. Descriptions ≤140 chars, concrete deliverable.
7. If pre-launch (day_n < 1): NO ad-spend missions, focus on Build/Growth prep.
8. If an active boss battle exists, reserve ONE Must-Complete slot that advances it.

RESPONSE FORMAT (JSON object with a "missions" array — return nothing else):
{"missions":[
  {
    "title": "Call AquaFlow re R8K retainer renewal",
    "description": "45min discovery call. Offer Growth package with automation audit addon.",
    "category": "Revenue",
    "tier": "Must-Complete",
    "xp_value": 110,
    "est_minutes": 60,
    "preferred_block": "morning",
    "linked_100day_theme": null
  }
]}

preferred_block: "morning" (07:00-11:00) | "midday" (11:00-14:00) | "afternoon" (14:00-17:00) | "evening" (17:00-20:00)
linked_100day_theme: only set for Growth missions matching the weekday theme, else null.
"""


def pp01_nodes() -> list[dict]:
    nodes: list[dict] = []

    # ── 1. Trigger ────────────────────────────────────────────
    nodes.append(node_schedule_cron(
        "Daily 06:30 SAST",
        "30 4 * * *",  # 06:30 SAST = 04:30 UTC
        pos(0, 0),
    ))

    # ── 2. Compute Dates + Context ────────────────────────────
    dates_code = """
// Compute today's context in SAST
const SAST_OFFSET_HOURS = 2;
const now = new Date();
const sastNow = new Date(now.getTime() + SAST_OFFSET_HOURS * 3600 * 1000);
const yyyy = sastNow.getUTCFullYear();
const mm = String(sastNow.getUTCMonth() + 1).padStart(2, '0');
const dd = String(sastNow.getUTCDate()).padStart(2, '0');
const today = `${yyyy}-${mm}-${dd}`;

// Working window in SAST (07:00-20:00 local)
const dayStart = `${today}T07:00:00+02:00`;
const dayEnd = `${today}T20:00:00+02:00`;

// Day N of 100 Day Challenge (launch = 2026-04-22)
const launch = new Date('2026-04-22T00:00:00+02:00');
const todayMidnight = new Date(`${today}T00:00:00+02:00`);
const dayN = Math.floor((todayMidnight - launch) / (86400 * 1000)) + 1;

// Weekday theme
const weekdayNum = sastNow.getUTCDay(); // 0=Sun, 1=Mon...
const themeMap = {1:'Mon_Metrics',2:'Tue_Tutorial',3:'Wed_Win',4:'Thu_Thought',5:'Fri_Fails',6:'Sat_Strategy',0:'Sun_Story'};
const weekdayTheme = themeMap[weekdayNum];
const weekdayName = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][weekdayNum];

// 100 Day phase
let phase = 'Pre-launch';
let monthlyTarget = 'n/a';
if (dayN >= 1 && dayN <= 28) { phase = 'Phase_1_Foundation_W1-4'; monthlyTarget = 'R20K-R40K/mo'; }
else if (dayN >= 29 && dayN <= 56) { phase = 'Phase_2_Proof_W5-8'; monthlyTarget = 'R60K-R100K/mo'; }
else if (dayN >= 57 && dayN <= 84) { phase = 'Phase_3_Scale_W9-12'; monthlyTarget = 'R100K-R140K/mo'; }
else if (dayN >= 85 && dayN <= 98) { phase = 'Phase_4_Push_W13-14'; monthlyTarget = 'R140K-R180K/mo'; }

return [{
  json: {
    today,
    day_start_iso: dayStart,
    day_end_iso: dayEnd,
    day_n: dayN,
    weekday_num: weekdayNum,
    weekday_theme: weekdayTheme,
    weekday_name: weekdayName,
    phase,
    monthly_target: monthlyTarget,
    is_pre_launch: dayN < 1,
  }
}];
""".strip()
    nodes.append(node_code("Compute Dates", dates_code, pos(1, 0)))

    # ── 3. Read Player ────────────────────────────────────────
    nodes.append(node_airtable_search(
        "Read Player",
        MARKETING_BASE_ID,
        PP_TABLE_PLAYER,
        pos(2, 0),
        filter_formula="{Player ID}='ian-immelman'",
        limit=1,
    ))

    # ── 4. Read last-7 Performance Snapshots ──────────────────
    nodes.append(node_airtable_search(
        "Read Perf Snapshots",
        MARKETING_BASE_ID,
        PP_TABLE_PERF_SNAPSHOTS,
        pos(3, 0),
        filter_formula="DATETIME_DIFF(TODAY(), {Date}, 'days')<=7",
        limit=7,
    ))

    # ── 5. Read active boss battle (if any) ───────────────────
    nodes.append(node_airtable_search(
        "Read Active Boss",
        MARKETING_BASE_ID,
        PP_TABLE_BOSS_BATTLES,
        pos(4, 0),
        filter_formula="{Status}='Active'",
        limit=1,
    ))

    # ── 6. Consolidate context + read Google Calendar ─────────
    consolidate_code = """
// Pull everything together into a single item for downstream nodes
const dates = $('Compute Dates').first().json;
const playerItems = $('Read Player').all();
const player = playerItems.length > 0 ? playerItems[0].json : {
  'Player ID': 'ian-immelman',
  'Display Name': 'Ian Immelman',
  'Current XP': 0,
  'Lifetime XP': 0,
  'Level': 1,
  'Current Streak Days': 0,
  'Current Difficulty': 'Normal',
};

const snapshots = $('Read Perf Snapshots').all().map(i => i.json);
const totalAssigned = snapshots.reduce((s, x) => s + (x['Missions Assigned'] || 0), 0);
const totalCompleted = snapshots.reduce((s, x) => s + (x['Missions Completed'] || 0), 0);
const rate7d = totalAssigned > 0 ? Math.round((totalCompleted / totalAssigned) * 100) : 0;

// Read Active Boss runs N times due to upstream fan-out from Read Perf
// Snapshots (N items). With alwaysOutputData=true, zero matches emit a
// synthetic empty {} item — which is truthy, so a plain length check
// would mis-classify "no boss" as "boss exists with all fields undefined"
// and feed garbage into the AI prompt. Pick the first item that has an
// actual Title; if none, treat as no active boss.
const bossItems = $('Read Active Boss').all();
const activeBossRaw = bossItems.find(i => i.json && i.json['Title']);
const activeBoss = activeBossRaw ? activeBossRaw.json : null;

return [{
  json: {
    ...dates,
    player_id: player['Player ID'],
    player_name: player['Display Name'],
    current_xp: player['Current XP'] || 0,
    lifetime_xp: player['Lifetime XP'] || 0,
    level: player['Level'] || 1,
    streak: player['Current Streak Days'] || 0,
    difficulty: player['Current Difficulty'] || 'Normal',
    rate_7d: rate7d,
    snapshots_n: snapshots.length,
    active_boss: activeBoss ? {
      title: activeBoss['Title'],
      narrative: activeBoss['Narrative'],
      target_metric: activeBoss['Target Metric'],
      current_progress: activeBoss['Current Progress'],
      xp_reward: activeBoss['XP Reward'],
    } : null,
  }
}];
""".strip()
    nodes.append(node_code("Consolidate Context", consolidate_code, pos(5, 0)))

    nodes.append(node_http_gcal_list(
        "Read Calendar Today",
        pos(6, 0),
        calendar_id=PP_GCAL_ID,
    ))

    # ── 7. Compute free slots + build AI user message ─────────
    free_slots_code = """
// Compute free slots between existing events in the 07:00-20:00 window
const ctx = $('Consolidate Context').first().json;
const calResp = $input.item.json;  // from HTTP Read Calendar Today
const events = (calResp.items || [])
  .filter(e => e.start && e.start.dateTime && e.status !== 'cancelled')
  .map(e => ({
    start: new Date(e.start.dateTime),
    end: new Date(e.end.dateTime),
    summary: e.summary || 'busy',
  }))
  .sort((a, b) => a.start - b.start);

const windowStart = new Date(ctx.day_start_iso);
const windowEnd = new Date(ctx.day_end_iso);

const freeSlots = [];
let cursor = windowStart;
for (const ev of events) {
  if (ev.end <= windowStart || ev.start >= windowEnd) continue;
  if (ev.start > cursor) {
    const minutes = Math.floor((ev.start - cursor) / 60000);
    if (minutes >= 15) {
      freeSlots.push({
        start_iso: cursor.toISOString(),
        end_iso: ev.start.toISOString(),
        minutes,
      });
    }
  }
  if (ev.end > cursor) cursor = ev.end;
}
if (cursor < windowEnd) {
  const minutes = Math.floor((windowEnd - cursor) / 60000);
  if (minutes >= 15) {
    freeSlots.push({
      start_iso: cursor.toISOString(),
      end_iso: windowEnd.toISOString(),
      minutes,
    });
  }
}

const totalFreeMinutes = freeSlots.reduce((s, slot) => s + slot.minutes, 0);

// Build AI user message
const userMsg = `Generate today's mission board.

TODAY: ${ctx.today} (${ctx.weekday_name}, Day ${ctx.day_n} of 100)
WEEKLY THEME: ${ctx.weekday_theme}
100-DAY PHASE: ${ctx.phase}
MONTHLY TARGET: ${ctx.monthly_target}
PRE-LAUNCH: ${ctx.is_pre_launch}

PLAYER STATE:
- Level ${ctx.level} · ${ctx.current_xp}/500 XP (lifetime ${ctx.lifetime_xp})
- Streak: ${ctx.streak} day(s)
- Difficulty: ${ctx.difficulty}
- Last-7-day completion rate: ${ctx.rate_7d}% across ${ctx.snapshots_n} snapshots

${ctx.active_boss ? `ACTIVE BOSS BATTLE: "${ctx.active_boss.title}" — ${ctx.active_boss.narrative}
  Target: ${ctx.active_boss.target_metric} · Progress: ${ctx.active_boss.current_progress} · Reward: ${ctx.active_boss.xp_reward} XP
  RESERVE ONE Must-Complete slot that advances this boss.` : 'No active boss battle.'}

FREE CALENDAR SLOTS (SAST):
${freeSlots.map(s => `  - ${s.start_iso.substring(11,16)}-${s.end_iso.substring(11,16)} (${s.minutes} min)`).join('\\n') || '  NONE — day is fully booked, generate 2-3 Optional/Maintenance missions only'}
Total free time: ${totalFreeMinutes} minutes.

Return the JSON object with "missions" array. No markdown, no commentary.`;

return [{
  json: {
    ...ctx,
    free_slots: freeSlots,
    total_free_minutes: totalFreeMinutes,
    user_message: userMsg,
  }
}];
""".strip()
    nodes.append(node_code("Compute Free Slots", free_slots_code, pos(7, 0)))

    # ── 8. Call OpenRouter / Claude ───────────────────────────
    nodes.append(node_http_openrouter(
        "AI Generate Missions",
        PP01_SYSTEM_PROMPT,
        "$json.user_message.replace(/\\\\/g, '\\\\\\\\').replace(/\"/g, '\\\\\"').replace(/\\n/g, '\\\\n')",
        pos(8, 0),
        max_tokens=3000,
        temperature=0.4,
        force_json=True,
        x_title="AVM Coach PP-01",
    ))

    # ── 9. Parse + enrich missions with slots ─────────────────
    parse_code = """
// Parse Claude's JSON response and assign time blocks from free slots
const aiResp = $input.item.json;
const ctx = $('Compute Free Slots').first().json;

let content = '';
try {
  content = aiResp.choices?.[0]?.message?.content || '{}';
} catch (e) {
  throw new Error('OpenRouter response missing choices: ' + JSON.stringify(aiResp).substring(0, 500));
}

// Strip markdown code fences if present (```json ... ``` or ``` ... ```)
if (typeof content === 'string') {
  content = content.trim();
  const fenceMatch = content.match(/^```(?:json)?\\s*\\n?([\\s\\S]*?)\\n?```$/);
  if (fenceMatch) content = fenceMatch[1].trim();
}

let parsed;
try {
  parsed = typeof content === 'string' ? JSON.parse(content) : content;
} catch (e) {
  throw new Error('Invalid JSON from AI (first 600 chars): ' + String(content).substring(0, 600));
}

// Accept both {missions:[...]} and raw array [...]
let missions;
if (Array.isArray(parsed)) {
  missions = parsed;
} else if (parsed && Array.isArray(parsed.missions)) {
  missions = parsed.missions;
} else {
  missions = [];
}
if (missions.length === 0) {
  throw new Error('AI returned 0 missions. Raw content: ' + String(content).substring(0, 600));
}

// Category → colorId map
const COLOR_MAP = {
  'Revenue': '11',
  'Growth': '5',
  'Build': '9',
  'Learning': '10',
  'Maintenance': '8',
};

// Greedy-pack missions into free slots (sorted by tier priority, then size)
const TIER_PRIORITY = {'Must-Complete': 0, 'High-Value': 1, 'Optional': 2};
const BLOCK_PREFERENCE = {'morning': 0, 'midday': 1, 'afternoon': 2, 'evening': 3};

const sorted = [...missions].sort((a, b) => {
  const tierDiff = (TIER_PRIORITY[a.tier] ?? 99) - (TIER_PRIORITY[b.tier] ?? 99);
  if (tierDiff !== 0) return tierDiff;
  return (b.est_minutes || 30) - (a.est_minutes || 30);
});

const slots = ctx.free_slots.map(s => ({
  start: new Date(s.start_iso),
  end: new Date(s.end_iso),
  remainingMin: s.minutes,
}));

function buildCalendarBody(mission) {
  // Pre-stringify the entire body in the Code node. The HTTP node will
  // send this string as the raw body (specifyBody: 'string').
  const body = {
    summary: '[' + mission.category + '] ' + mission.title + ' - ' + mission.xp_value + 'XP',
    description: (mission.description || '') + '. Tier: ' + mission.tier + '. Theme: ' + (mission.linked_100day_theme || 'n/a') + '. Mission ID: ' + mission.mission_id,
    start: {dateTime: mission.scheduled_start_iso, timeZone: 'Africa/Johannesburg'},
    end: {dateTime: mission.scheduled_end_iso, timeZone: 'Africa/Johannesburg'},
    colorId: String(mission.color_id),
    reminders: {useDefault: false, overrides: [{method: 'popup', minutes: 10}]},
  };
  return JSON.stringify(body);
}

const enriched = [];
let missionIdx = 0;
for (const m of sorted) {
  const minsNeeded = Math.max(15, m.est_minutes || 30);
  let placed = false;
  for (const slot of slots) {
    if (slot.remainingMin >= minsNeeded) {
      const start = new Date(slot.start);
      const end = new Date(start.getTime() + minsNeeded * 60000);
      slot.start = end;
      slot.remainingMin -= minsNeeded;

      const today = ctx.today;
      const missionId = `pp-${today.replace(/-/g, '')}-${String(missionIdx + 1).padStart(2, '0')}`;
      const mission = {
        mission_id: missionId,
        date: today,
        title: (m.title || '').substring(0, 80),
        description: (m.description || '').substring(0, 140),
        category: m.category || 'Maintenance',
        tier: m.tier || 'Optional',
        xp_value: m.xp_value || 20,
        est_minutes: minsNeeded,
        scheduled_start_iso: start.toISOString(),
        scheduled_end_iso: end.toISOString(),
        source: 'AI_Generated',
        linked_100day_theme: m.linked_100day_theme || null,
        color_id: COLOR_MAP[m.category] || '8',
        ctx_day_n: ctx.day_n,
        ctx_weekday_theme: ctx.weekday_theme,
        ctx_phase: ctx.phase,
      };
      mission.calendar_body = buildCalendarBody(mission);
      enriched.push(mission);
      missionIdx++;
      placed = true;
      break;
    }
  }
  if (!placed) {
    const today = ctx.today;
    const missionId = `pp-${today.replace(/-/g, '')}-${String(missionIdx + 1).padStart(2, '0')}`;
    const mission = {
      mission_id: missionId,
      date: today,
      title: (m.title || '').substring(0, 80) + ' [UNSCHEDULED]',
      description: (m.description || '').substring(0, 140),
      category: m.category || 'Maintenance',
      tier: m.tier || 'Optional',
      xp_value: m.xp_value || 20,
      est_minutes: minsNeeded,
      scheduled_start_iso: `${today}T19:00:00+02:00`,
      scheduled_end_iso: `${today}T19:${String(Math.min(59, minsNeeded)).padStart(2, '0')}:00+02:00`,
      source: 'AI_Generated',
      linked_100day_theme: m.linked_100day_theme || null,
      color_id: COLOR_MAP[m.category] || '8',
      ctx_day_n: ctx.day_n,
      ctx_weekday_theme: ctx.weekday_theme,
      ctx_phase: ctx.phase,
    };
    mission.calendar_body = buildCalendarBody(mission);
    enriched.push(mission);
    missionIdx++;
  }
}

return enriched.map(m => ({json: m}));
""".strip()
    nodes.append(node_code("Parse & Schedule", parse_code, pos(9, 0)))

    # ── 10. Create PP_Missions rows ───────────────────────────
    mission_columns = {
        "Mission ID": "={{ $json.mission_id }}",
        "Date": "={{ $json.date }}",
        "Title": "={{ $json.title }}",
        "Description": "={{ $json.description }}",
        "Category": "={{ $json.category }}",
        "Tier": "={{ $json.tier }}",
        "XP Value": "={{ $json.xp_value }}",
        "Status": "Pending",
        "Est. Minutes": "={{ $json.est_minutes }}",
        "Scheduled Start": "={{ $json.scheduled_start_iso }}",
        "Scheduled End": "={{ $json.scheduled_end_iso }}",
        "Source": "={{ $json.source }}",
        "Linked 100Day Theme": "={{ $json.linked_100day_theme }}",
    }
    nodes.append(node_airtable_create(
        "Create PP_Missions",
        MARKETING_BASE_ID,
        PP_TABLE_MISSIONS,
        pos(10, 0),
        column_values=mission_columns,
    ))

    # ── 11. Split to create one calendar event per mission ────
    nodes.append(node_split_in_batches("Loop Missions", pos(11, 0), batch_size=1))

    # Materialize $json from the Create PP_Missions output (which has
    # .id + .fields) back into a flat mission payload that the Google
    # Calendar node + Merge Event ID can reference via $json.<field>.
    prepare_code = """
const raw = $input.item.json;
const f = raw.fields || raw || {};
return [{
  json: {
    mission_id: f['Mission ID'] || raw.mission_id || '',
    title: f['Title'] || raw.title || '',
    description: f['Description'] || raw.description || '',
    category: f['Category'] || raw.category || 'Maintenance',
    tier: f['Tier'] || raw.tier || 'Optional',
    xp_value: f['XP Value'] || raw.xp_value || 0,
    scheduled_start_iso: f['Scheduled Start'] || raw.scheduled_start_iso || '',
    scheduled_end_iso: f['Scheduled End'] || raw.scheduled_end_iso || '',
    linked_100day_theme: f['Linked 100Day Theme'] || raw.linked_100day_theme || null,
    color_id: raw.color_id || '8',
    airtable_record_id: raw.id || '',
  }
}];
""".strip()
    nodes.append(node_code("Prepare Event", prepare_code, pos(12, 0)))

    nodes.append(node_gcal_create(
        "Create Calendar Event",
        pos(13, 0),
        calendar_id=PP_GCAL_ID,
    ))

    # ── 11b. Merge calendar event ID with upstream mission_id ─
    merge_code = """
// Pull airtable_record_id + mission_id from the Prepare Event upstream
// item, event id from the Create Calendar Event response. Build a single
// payload so the Airtable update can match by Airtable record id (globally
// unique) rather than Mission ID (per-day sequence, collision-prone when
// a manual seed and an automated run share the same day).
const missionItem = $('Prepare Event').item.json;
const calResp = $input.item.json;
const eventId = calResp && calResp.id && !calResp.error ? calResp.id : '';
const calError = calResp && calResp.error ? JSON.stringify(calResp.error).substring(0, 200) : null;
return [{
  json: {
    airtable_record_id: missionItem.airtable_record_id,
    mission_id: missionItem.mission_id,
    event_id: eventId,
    cal_error: calError,
  }
}];
""".strip()
    nodes.append(node_code("Merge Event ID", merge_code, pos(14, 0)))

    # ── 12. Update Airtable with Calendar Event ID ────────────
    # Match on Airtable record id (matchingColumns=['id']) instead of the
    # per-day Mission ID. n8n's Airtable v2 update short-circuits the
    # search-and-match phase when 'id' is in matchingColumns and does a
    # direct PATCH — eliminating the collision risk that caused the
    # 2026-04-13 calendar-id mix-up (see
    # packages/nodes-base/nodes/Airtable/v2/actions/record/update.operation.ts:67).
    nodes.append(node_airtable_update(
        "Update Event ID",
        MARKETING_BASE_ID,
        PP_TABLE_MISSIONS,
        pos(15, 0),
        matching_columns=["id"],
        column_values={
            "id": "={{ $json.airtable_record_id }}",
            "Calendar Event ID": "={{ $json.event_id }}",
        },
    ))

    # ── 13. After loop: render mission board → Telegram ───────
    # Sources from Create PP_Missions so every rendered mission carries its
    # Airtable record id — needed for the tap-to-complete inline buttons
    # that PP-06 resolves via callback_data=`cmpl:<record_id>`.
    render_code = """
// Render mission board markdown for Telegram + build inline keyboard
const ctx = $('Compute Free Slots').first().json;
const createRows = $('Create PP_Missions').all().map(i => i.json);

// Airtable v2 output may come as {id, fields:{...}} or flat {id, ...fields}.
// Mirror the Prepare Event pattern so both shapes work.
const missions = createRows.map(raw => {
  const f = raw.fields || raw || {};
  return {
    airtable_record_id: raw.id || '',
    title: f['Title'] || raw.title || '',
    category: f['Category'] || raw.category || 'Maintenance',
    tier: f['Tier'] || raw.tier || 'Optional',
    xp_value: f['XP Value'] || raw.xp_value || 0,
    scheduled_start_iso: f['Scheduled Start'] || raw.scheduled_start_iso || '',
    est_minutes: f['Est. Minutes'] || raw.est_minutes || 0,
    linked_100day_theme: f['Linked 100Day Theme'] || raw.linked_100day_theme || null,
  };
});

const TIER_EMOJI = {'Must-Complete':'🔴','High-Value':'🟠','Optional':'🔵'};
const byTier = {'Must-Complete':[],'High-Value':[],'Optional':[]};
let n = 1;
for (const m of missions) {
  byTier[m.tier] = byTier[m.tier] || [];
  byTier[m.tier].push({...m, idx: n++});
}

const header = `🎮 *AVM COACH* — ${ctx.weekday_name} ${ctx.today}
Day ${ctx.day_n} of 100 · Phase: ${ctx.phase}
Theme: *${ctx.weekday_theme}* · Monthly target: ${ctx.monthly_target}

Player: Level ${ctx.level} · ${ctx.current_xp}/500 XP · 🔥 ${ctx.streak}-day streak · ${ctx.difficulty}
7-day completion rate: ${ctx.rate_7d}%
`;

let body = '';
// Collect missions in render order for the inline-keyboard button layout.
const orderedMissions = [];
for (const tier of ['Must-Complete', 'High-Value', 'Optional']) {
  const list = byTier[tier] || [];
  if (list.length === 0) continue;
  body += `\\n${TIER_EMOJI[tier]} *${tier.toUpperCase()}* (${list.length})\\n`;
  for (const m of list) {
    const t = (m.scheduled_start_iso || '').substring(11, 16);
    const themeTag = m.linked_100day_theme ? ` [${m.linked_100day_theme}]` : '';
    body += `  ${m.idx}. [${m.category}] ${m.title} — *${m.xp_value} XP*${themeTag}\\n     ${t} · ${m.est_minutes} min\\n`;
    orderedMissions.push(m);
  }
}

const totalXp = missions.reduce((s, m) => s + (m.xp_value || 0), 0);
const totalMin = missions.reduce((s, m) => s + (m.est_minutes || 0), 0);
const footer = `\\n📊 Total board: ${totalXp} XP · ${totalMin} min focus
Tap ✅ below to mark a mission complete.
🎯 Go.`;

// Inline keyboard: 3 buttons per row, text "✅ #N", callback "cmpl:<recId>".
// Filter out missions with no Airtable id (shouldn't happen, defensive).
const buttons = orderedMissions
  .filter(m => m.airtable_record_id)
  .map(m => ({
    text: `✅ #${m.idx}`,
    callback_data: `cmpl:${m.airtable_record_id}`,
  }));
const rows = [];
for (let i = 0; i < buttons.length; i += 3) {
  rows.push(buttons.slice(i, i + 3));
}
const replyMarkup = JSON.stringify({ inline_keyboard: rows });

return [{
  json: {
    telegram_text: header + body + footer,
    mission_count: missions.length,
    total_xp: totalXp,
    reply_markup: replyMarkup,
  }
}];
""".strip()
    # Render Board + Send Telegram live on row 1 (the "done" branch, parallel
    # to the per-mission body loop which fills row 0 columns 12-15).
    nodes.append(node_code("Render Board", render_code, pos(12, 1)))

    nodes.append(node_telegram_send(
        "Send Telegram",
        PP_TELEGRAM_CHAT_ID,
        "={{ $json.telegram_text }}",
        pos(13, 1),
        reply_markup_expr="={{ $json.reply_markup }}",
    ))

    return nodes


def pp01_connections() -> dict:
    """Wire nodes by name — n8n connects via node names, not IDs."""
    return {
        "Daily 06:30 SAST": {"main": [[{"node": "Compute Dates", "type": "main", "index": 0}]]},
        "Compute Dates": {"main": [[{"node": "Read Player", "type": "main", "index": 0}]]},
        "Read Player": {"main": [[{"node": "Read Perf Snapshots", "type": "main", "index": 0}]]},
        "Read Perf Snapshots": {"main": [[{"node": "Read Active Boss", "type": "main", "index": 0}]]},
        "Read Active Boss": {"main": [[{"node": "Consolidate Context", "type": "main", "index": 0}]]},
        "Consolidate Context": {"main": [[{"node": "Read Calendar Today", "type": "main", "index": 0}]]},
        "Read Calendar Today": {"main": [[{"node": "Compute Free Slots", "type": "main", "index": 0}]]},
        "Compute Free Slots": {"main": [[{"node": "AI Generate Missions", "type": "main", "index": 0}]]},
        "AI Generate Missions": {"main": [[{"node": "Parse & Schedule", "type": "main", "index": 0}]]},
        "Parse & Schedule": {"main": [[{"node": "Create PP_Missions", "type": "main", "index": 0}]]},
        "Create PP_Missions": {"main": [[{"node": "Loop Missions", "type": "main", "index": 0}]]},
        "Loop Missions": {
            "main": [
                [{"node": "Render Board", "type": "main", "index": 0}],      # output 0 = "done" after loop
                [{"node": "Prepare Event", "type": "main", "index": 0}],     # output 1 = per-item body
            ]
        },
        "Prepare Event": {"main": [[{"node": "Create Calendar Event", "type": "main", "index": 0}]]},
        "Create Calendar Event": {"main": [[{"node": "Merge Event ID", "type": "main", "index": 0}]]},
        "Merge Event ID": {"main": [[{"node": "Update Event ID", "type": "main", "index": 0}]]},
        "Update Event ID": {"main": [[{"node": "Loop Missions", "type": "main", "index": 0}]]},
        "Render Board": {"main": [[{"node": "Send Telegram", "type": "main", "index": 0}]]},
    }


# ============================================================
# PP-02: Midday Check-in
# ============================================================
#
# Fires at 13:00 SAST daily. Pure reads, no AI, no writes. Reads today's
# missions + player + today's XP log, then sends a deterministic Telegram
# check-in showing Must-Complete progress, XP earned so far, remaining
# working hours, and a static coach nudge keyed to completion rate.
#
# Intentionally dumb: midday is about facts, not coaching prose. If Ian
# wants AI warmth, PP-03 (evening review) handles it.


def pp02_nodes() -> list[dict]:
    nodes: list[dict] = []

    # ── 1. Trigger ────────────────────────────────────────────
    nodes.append(node_schedule_cron(
        "Daily 13:00 SAST",
        "0 11 * * *",  # 13:00 SAST = 11:00 UTC
        pos(0, 0),
    ))

    # ── 2. Compute Dates ──────────────────────────────────────
    dates_code = """
const SAST_OFFSET_HOURS = 2;
const now = new Date();
const sastNow = new Date(now.getTime() + SAST_OFFSET_HOURS * 3600 * 1000);
const yyyy = sastNow.getUTCFullYear();
const mm = String(sastNow.getUTCMonth() + 1).padStart(2, '0');
const dd = String(sastNow.getUTCDate()).padStart(2, '0');
const today = `${yyyy}-${mm}-${dd}`;

const launch = new Date('2026-04-22T00:00:00+02:00');
const todayMidnight = new Date(`${today}T00:00:00+02:00`);
const dayN = Math.floor((todayMidnight - launch) / (86400 * 1000)) + 1;

const weekdayNum = sastNow.getUTCDay();
const themeMap = {1:'Mon_Metrics',2:'Tue_Tutorial',3:'Wed_Win',4:'Thu_Thought',5:'Fri_Fails',6:'Sat_Strategy',0:'Sun_Story'};
const weekdayTheme = themeMap[weekdayNum];
const weekdayName = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][weekdayNum];

// Hours remaining until 20:00 SAST working-window close
const WORKING_END_HOUR_SAST = 20;
const sastHour = sastNow.getUTCHours() + sastNow.getUTCMinutes() / 60;
const hoursRemaining = Math.max(0, WORKING_END_HOUR_SAST - sastHour);
const hoursInt = Math.floor(hoursRemaining);
const minsInt = Math.round((hoursRemaining - hoursInt) * 60);

return [{
  json: {
    today,
    day_n: dayN,
    weekday_theme: weekdayTheme,
    weekday_name: weekdayName,
    hours_remaining: Math.round(hoursRemaining * 10) / 10,
    remaining_label: `${hoursInt}h ${minsInt}m`,
  }
}];
""".strip()
    nodes.append(node_code("Compute Dates", dates_code, pos(1, 0)))

    # ── 3. Read today's missions ──────────────────────────────
    nodes.append(node_airtable_search(
        "Read Today Missions",
        MARKETING_BASE_ID,
        PP_TABLE_MISSIONS,
        pos(2, 0),
        filter_formula="IS_SAME({Date},TODAY(),'day')",
        limit=30,
    ))

    # ── 4. Read player ────────────────────────────────────────
    nodes.append(node_airtable_search(
        "Read Player",
        MARKETING_BASE_ID,
        PP_TABLE_PLAYER,
        pos(3, 0),
        filter_formula="{Player ID}='ian-immelman'",
        limit=1,
    ))

    # ── 5. Read today's XP log ────────────────────────────────
    # Sum XP Delta for true earned-so-far total (includes streak multipliers).
    nodes.append(node_airtable_search(
        "Read Today XP Log",
        MARKETING_BASE_ID,
        PP_TABLE_XP_LOG,
        pos(4, 0),
        filter_formula="AND(IS_SAME({Timestamp},TODAY(),'day'),{Event Type}='Mission_Complete')",
        limit=50,
    ))

    # ── 6. Render check-in message ────────────────────────────
    render_code = r"""
const dates = $('Compute Dates').first().json;

const missionItems = $('Read Today Missions').all();
const missions = missionItems.map(i => i.json).filter(m => m && m['Mission ID']);

const playerItems = $('Read Player').all().filter(i => i.json && i.json['Player ID']);
const player = playerItems.length > 0 ? playerItems[0].json : {
  'Player ID': 'ian-immelman',
  'Current XP': 0,
  'Lifetime XP': 0,
  'Level': 1,
  'Current Streak Days': 0,
  'Current Difficulty': 'Normal',
};

// Dedupe XP log entries by Log ID. Upstream nodes (Read Today Missions
// → Read Player → Read Today XP Log) fan out: 6 missions × 5 log rows =
// 30 duplicated items reach this node. Without dedupe we inflate the
// XP sum 6x. The same pattern applies to any Airtable search sitting
// downstream of a multi-item producer.
const seenLogIds = new Set();
const xpLogItems = $('Read Today XP Log').all()
  .map(i => i.json)
  .filter(e => {
    if (!e || !e['Log ID'] || e['Event Type'] !== 'Mission_Complete') return false;
    if (seenLogIds.has(e['Log ID'])) return false;
    seenLogIds.add(e['Log ID']);
    return true;
  });
const xpEarnedToday = xpLogItems.reduce((s, e) => s + (e['XP Delta'] || 0), 0);

// Tier + status breakdown. Track skipped separately from pending so the
// nudge can say "unblock the skipped one" vs "pick the cheapest pending".
const byTier = {
  'Must-Complete': {total: 0, complete: 0, skipped: 0, pending: []},
  'High-Value':    {total: 0, complete: 0, skipped: 0, pending: []},
  'Optional':      {total: 0, complete: 0, skipped: 0, pending: []},
};

for (const m of missions) {
  const tier = m['Tier'] || 'Optional';
  const status = m['Status'] || 'Pending';
  if (!byTier[tier]) continue;
  byTier[tier].total += 1;
  if (status === 'Complete') {
    byTier[tier].complete += 1;
  } else if (status === 'Skipped' || status === 'Failed') {
    byTier[tier].skipped += 1;
  } else if (status === 'Pending' || status === 'In_Progress') {
    byTier[tier].pending.push({
      title: m['Title'] || '(untitled)',
      category: m['Category'] || 'Maintenance',
      xp: m['XP Value'] || 0,
    });
  }
}

const mustTotal = byTier['Must-Complete'].total;
const mustDone = byTier['Must-Complete'].complete;
const mustSkipped = byTier['Must-Complete'].skipped;
const mustRate = mustTotal > 0 ? mustDone / mustTotal : 1;
const mustPending = byTier['Must-Complete'].pending;

// Static coach nudge. Branching is deliberately layered: skipped/blocked
// Musts are a different failure mode than pending ones and deserve a
// different message.
let nudge;
if (mustTotal === 0) {
  nudge = "No Must-Completes scheduled today. Use the window to push a High-Value forward.";
} else if (mustRate >= 1) {
  nudge = "🔥 Must-Completes nailed before midday. Ride momentum — bank a High-Value next.";
} else if (mustPending.length === 0 && mustSkipped > 0) {
  nudge = `${mustSkipped} Must-Complete skipped, nothing else open. Unblock it, swap it, or accept the hit and double down on High-Value.`;
} else if (mustRate >= 0.5 && mustPending.length > 0) {
  nudge = "Half the Must-Completes still open. Pick the cheapest one to knock out in the next 30 min.";
} else if (mustDone > 0 && mustPending.length > 0) {
  nudge = `${mustPending.length} Must-Complete still open. Drop Optionals, batch the rest before 17:00.`;
} else if (mustPending.length > 0) {
  nudge = `Nothing Must-Complete done yet. Reality check: ${dates.remaining_label} left. Pick ONE Must and start it now.`;
} else {
  nudge = "Must-Complete progress stalled. Check the mission list and either commit or swap.";
}

// Must-Complete progress bar (5 segments)
const barLen = 5;
const filled = Math.round(mustRate * barLen);
const bar = '█'.repeat(filled) + '░'.repeat(barLen - filled);

// Render pending Must list (up to 3)
const pendingLines = mustPending.slice(0, 3).map((m, i) => {
  return `  ${i + 1}. [${m.category}] ${m.title} — ${m.xp} XP`;
}).join('\n');

const level = player['Level'] || 1;
const currentXp = player['Current XP'] || 0;
const streak = player['Current Streak Days'] || 0;
const streakEmoji = streak >= 7 ? '🔥 ' : streak >= 3 ? '⚡ ' : '';
const difficulty = player['Current Difficulty'] || 'Normal';

const body = `⏰ *MIDDAY CHECK-IN* — ${dates.weekday_name} ${dates.today}
Day ${dates.day_n} of 100 · Theme: ${dates.weekday_theme}

Player: Level ${level} · ${currentXp}/500 XP · ${streakEmoji}${streak}-day streak · ${difficulty}
Earned today: *${xpEarnedToday} XP* across ${xpLogItems.length} mission(s)
Working window: *${dates.remaining_label}* left

🔴 Must-Complete: ${bar}  ${mustDone}/${mustTotal}
🟠 High-Value:    ${byTier['High-Value'].complete}/${byTier['High-Value'].total}
🔵 Optional:      ${byTier['Optional'].complete}/${byTier['Optional'].total}
${mustPending.length > 0 ? '\n*Still open (Must-Complete):*\n' + pendingLines : ''}

${nudge}`;

return [{
  json: {
    telegram_text: body,
    xp_earned_today: xpEarnedToday,
    must_complete_rate: mustRate,
    must_pending_count: mustPending.length,
  }
}];
""".strip()
    nodes.append(node_code("Render Check-in", render_code, pos(5, 0)))

    # ── 7. Send Telegram ──────────────────────────────────────
    nodes.append(node_telegram_send(
        "Send Check-in Telegram",
        PP_TELEGRAM_CHAT_ID,
        "={{ $json.telegram_text }}",
        pos(6, 0),
    ))

    return nodes


def pp02_connections() -> dict:
    return {
        "Daily 13:00 SAST": {"main": [[{"node": "Compute Dates", "type": "main", "index": 0}]]},
        "Compute Dates": {"main": [[{"node": "Read Today Missions", "type": "main", "index": 0}]]},
        "Read Today Missions": {"main": [[{"node": "Read Player", "type": "main", "index": 0}]]},
        "Read Player": {"main": [[{"node": "Read Today XP Log", "type": "main", "index": 0}]]},
        "Read Today XP Log": {"main": [[{"node": "Render Check-in", "type": "main", "index": 0}]]},
        "Render Check-in": {"main": [[{"node": "Send Check-in Telegram", "type": "main", "index": 0}]]},
    }


# ============================================================
# PP-03: Evening Review
# ============================================================

PP03_SYSTEM_PROMPT = """You are Ian Immelman's AVM Coach writing the evening review for a 100 Day Challenge gamified daily workflow.

Ian is building AnyVision Media, a SA AI automation agency, with a R20-180K/month revenue ladder over 6 months. You get a short stats block about today's missions and player state. Your job: write a warm, direct, 3-5 line evening review.

Tone:
- First-person to Ian (you/your, not Ian/he)
- Coach, not cheerleader. Be specific about what was strong or weak.
- South African context (ZAR, UK English)
- Never patronising, never generic ("great job!", "keep it up!" are forbidden)

Structure:
Line 1: One concrete observation about TODAY (what worked or what didn't)
Line 2: Connect today to the larger arc (100 Day challenge phase, streak, trend)
Line 3: One specific thing to carry into tomorrow OR one thing to stop doing

Max 400 chars total. No emoji unless the stats block has a streak ≥7. Plain text.
Return ONLY the review text, no JSON, no markdown, no labels."""


def pp03_nodes() -> list[dict]:
    nodes: list[dict] = []

    # ── 1. Trigger ────────────────────────────────────────────
    nodes.append(node_schedule_cron(
        "Daily 20:00 SAST",
        "0 18 * * *",  # 20:00 SAST = 18:00 UTC
        pos(0, 0),
    ))

    # ── 2. Compute Dates ──────────────────────────────────────
    dates_code = """
const SAST_OFFSET_HOURS = 2;
const now = new Date();
const sastNow = new Date(now.getTime() + SAST_OFFSET_HOURS * 3600 * 1000);
const yyyy = sastNow.getUTCFullYear();
const mm = String(sastNow.getUTCMonth() + 1).padStart(2, '0');
const dd = String(sastNow.getUTCDate()).padStart(2, '0');
const today = `${yyyy}-${mm}-${dd}`;

const launch = new Date('2026-04-22T00:00:00+02:00');
const todayMidnight = new Date(`${today}T00:00:00+02:00`);
const dayN = Math.floor((todayMidnight - launch) / (86400 * 1000)) + 1;

const weekdayNum = sastNow.getUTCDay();
const themeMap = {1:'Mon_Metrics',2:'Tue_Tutorial',3:'Wed_Win',4:'Thu_Thought',5:'Fri_Fails',6:'Sat_Strategy',0:'Sun_Story'};
const weekdayTheme = themeMap[weekdayNum];
const weekdayName = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][weekdayNum];

return [{
  json: {
    today,
    day_n: dayN,
    weekday_theme: weekdayTheme,
    weekday_name: weekdayName,
    snapshot_id: `snap-${today.replace(/-/g, '')}`,
  }
}];
""".strip()
    nodes.append(node_code("Compute Dates", dates_code, pos(1, 0)))

    # ── 3. Read today's missions ──────────────────────────────
    nodes.append(node_airtable_search(
        "Read Today Missions",
        MARKETING_BASE_ID,
        PP_TABLE_MISSIONS,
        pos(2, 0),
        filter_formula="IS_SAME({Date},TODAY(),'day')",
        limit=30,
    ))

    # ── 4. Read player ────────────────────────────────────────
    nodes.append(node_airtable_search(
        "Read Player",
        MARKETING_BASE_ID,
        PP_TABLE_PLAYER,
        pos(3, 0),
        filter_formula="{Player ID}='ian-immelman'",
        limit=1,
    ))

    # ── 4b. Check if today's snapshot already exists ──────────
    nodes.append(node_airtable_search(
        "Read Today Snapshot",
        MARKETING_BASE_ID,
        PP_TABLE_PERF_SNAPSHOTS,
        pos(3, 1),
        filter_formula="IS_SAME({Date},TODAY(),'day')",
        limit=1,
    ))

    # ── 4c. Read today's XP log entries (for true XP-earned sum) ──
    # The skill's complete command writes multiplier-adjusted XP to PP_XP_Log.
    # Summing {XP Value} from PP_Missions only gives base XP, missing streak
    # bonuses. Read the log directly so Total XP Earned snapshot matches what
    # actually landed on the player.
    nodes.append(node_airtable_search(
        "Read Today XP Log",
        MARKETING_BASE_ID,
        PP_TABLE_XP_LOG,
        pos(3, 2),
        filter_formula="AND(IS_SAME({Timestamp},TODAY(),'day'),{Event Type}='Mission_Complete')",
        limit=50,
    ))

    # ── 5. Compute stats + reconcile ──────────────────────────
    stats_code = """
const dates = $('Compute Dates').first().json;
const missionItems = $('Read Today Missions').all();
const missions = missionItems.map(i => i.json);
const playerItems = $('Read Player').all();
const player = playerItems.length > 0 ? playerItems[0].json : {
  'Player ID': 'ian-immelman',
  'Current XP': 0,
  'Lifetime XP': 0,
  'Level': 1,
  'Current Streak Days': 0,
  'Longest Streak': 0,
  'Last Active Date': null,
  'Current Difficulty': 'Normal',
};

// Count by status + category
const counts = {Pending: 0, In_Progress: 0, Complete: 0, Skipped: 0, Failed: 0};
const completedByCat = {Revenue: 0, Growth: 0, Build: 0, Learning: 0, Maintenance: 0};
let hardestTier = 'Optional';
const tierOrder = {'Optional': 0, 'High-Value': 1, 'Must-Complete': 2};

// Sum XP from PP_XP_Log today (authoritative, includes streak multipliers).
// Dedupe by Log ID: upstream Airtable reads fan out on multi-item input
// (Read Today Missions emits 6 items → Read Player/Snapshot/XP Log each
// run 6 times → 30 duplicated log rows reach this node). Without dedupe
// we would inflate xpEarned 6x and corrupt the PP_Performance_Snapshot
// write downstream. Confirmed in PP-02 live test on 2026-04-13.
const seenXpLogIds = new Set();
const xpLogItems = $('Read Today XP Log').all()
  .map(i => i.json)
  .filter(e => {
    if (!e || !e['Log ID'] || e['Event Type'] !== 'Mission_Complete') return false;
    if (seenXpLogIds.has(e['Log ID'])) return false;
    seenXpLogIds.add(e['Log ID']);
    return true;
  });
const xpEarned = xpLogItems.reduce((s, e) => s + (e['XP Delta'] || 0), 0);

for (const m of missions) {
  const status = m['Status'] || 'Pending';
  counts[status] = (counts[status] || 0) + 1;
  if (status === 'Complete') {
    const cat = m['Category'] || 'Maintenance';
    completedByCat[cat] = (completedByCat[cat] || 0) + 1;
    const tier = m['Tier'] || 'Optional';
    if ((tierOrder[tier] || 0) > (tierOrder[hardestTier] || 0)) {
      hardestTier = tier;
    }
  }
}

const assigned = missions.length;
const completed = counts.Complete || 0;
const rate = assigned > 0 ? (completed / assigned) : 0;
const avgXp = completed > 0 ? (xpEarned / completed) : 0;

// Streak logic — idempotent via today's snapshot presence, not Last Active Date
// (the skill updates Last Active Date on every mission complete, so we can't
// rely on it to detect "has PP-03 already run today").
// alwaysOutputData emits a synthetic empty item when Airtable returns nothing,
// so check for real content via the Snapshot ID field, not just .length.
const previousStreak = player['Current Streak Days'] || 0;
const longestStreak = player['Longest Streak'] || 0;
const snapshotExists = $('Read Today Snapshot').all().some(i => i.json && i.json['Snapshot ID']);

let newStreak;
let streakAction;
if (snapshotExists) {
  newStreak = previousStreak;
  streakAction = 'idempotent';
} else if (completed >= 1) {
  newStreak = previousStreak + 1;
  streakAction = 'extended';
} else {
  newStreak = 0;
  streakAction = 'broken';
}
const newLongest = Math.max(newStreak, longestStreak);

// Build AI input
const rateBand = rate >= 0.8 ? 'strong' : rate >= 0.5 ? 'mixed' : 'weak';
const pendingTitles = missions.filter(m => (m['Status'] || 'Pending') === 'Pending').map(m => m['Title']).slice(0, 5);
const skippedTitles = missions.filter(m => m['Status'] === 'Skipped').map(m => m['Title']).slice(0, 3);

const userMsg = `STATS FOR EVENING REVIEW

Today: ${dates.today} (${dates.weekday_name}, Day ${dates.day_n} of 100)
Theme: ${dates.weekday_theme}
Player: Level ${player['Level']} · ${player['Lifetime XP']} lifetime XP · difficulty ${player['Current Difficulty']}
Previous streak: ${previousStreak} days
New streak: ${newStreak} days (${streakAction})

Missions assigned: ${assigned}
Completed: ${completed} (${Math.round(rate * 100)}% rate — ${rateBand})
  Revenue: ${completedByCat.Revenue}, Growth: ${completedByCat.Growth}, Build: ${completedByCat.Build}, Learning: ${completedByCat.Learning}, Maintenance: ${completedByCat.Maintenance}
Skipped: ${counts.Skipped || 0}
Still pending: ${counts.Pending || 0}
XP earned today: ${xpEarned}

${pendingTitles.length ? 'Pending titles: ' + pendingTitles.map(t => '"' + t + '"').join(', ') : ''}
${skippedTitles.length ? 'Skipped titles: ' + skippedTitles.map(t => '"' + t + '"').join(', ') : ''}

Write the evening review per your system prompt rules.`;

return [{
  json: {
    ...dates,
    assigned,
    completed,
    rate,
    rate_band: rateBand,
    xp_earned: xpEarned,
    avg_xp: Math.round(avgXp * 10) / 10,
    revenue_completed: completedByCat.Revenue,
    growth_completed: completedByCat.Growth,
    build_completed: completedByCat.Build,
    hardest_tier: hardestTier,
    counts,
    previous_streak: previousStreak,
    new_streak: newStreak,
    longest_streak: newLongest,
    streak_action: streakAction,
    player_id: player['Player ID'],
    player_level: player['Level'] || 1,
    lifetime_xp: player['Lifetime XP'] || 0,
    difficulty: player['Current Difficulty'] || 'Normal',
    pending_titles: pendingTitles,
    skipped_titles: skippedTitles,
    user_message: userMsg,
  }
}];
""".strip()
    nodes.append(node_code("Compute Stats", stats_code, pos(4, 0)))

    # ── 6. Create Performance Snapshot ────────────────────────
    snapshot_columns = {
        "Snapshot ID": "={{ $json.snapshot_id }}",
        "Date": "={{ $json.today }}",
        "Missions Assigned": "={{ $json.assigned }}",
        "Missions Completed": "={{ $json.completed }}",
        "Completion Rate": "={{ $json.rate }}",
        "Total XP Earned": "={{ $json.xp_earned }}",
        "Avg XP Per Mission": "={{ $json.avg_xp }}",
        "Revenue Missions Completed": "={{ $json.revenue_completed }}",
        "Growth Missions Completed": "={{ $json.growth_completed }}",
        "Build Missions Completed": "={{ $json.build_completed }}",
        "Hardest Tier Hit": "={{ $json.hardest_tier }}",
        "Difficulty At Snapshot": "={{ $json.difficulty }}",
    }
    nodes.append(node_airtable_create(
        "Create Snapshot",
        MARKETING_BASE_ID,
        PP_TABLE_PERF_SNAPSHOTS,
        pos(5, 0),
        column_values=snapshot_columns,
    ))

    # ── 7. Update Player streak ───────────────────────────────
    player_columns = {
        "Player ID": "={{ $('Compute Stats').item.json.player_id }}",
        "Current Streak Days": "={{ $('Compute Stats').item.json.new_streak }}",
        "Longest Streak": "={{ $('Compute Stats').item.json.longest_streak }}",
        "Last Active Date": "={{ $('Compute Stats').item.json.today }}",
    }
    nodes.append(node_airtable_update(
        "Update Player Streak",
        MARKETING_BASE_ID,
        PP_TABLE_PLAYER,
        pos(6, 0),
        matching_columns=["Player ID"],
        column_values=player_columns,
    ))

    # ── 8. AI evening review (warm coach voice) ───────────────
    nodes.append(node_http_openrouter(
        "AI Review",
        PP03_SYSTEM_PROMPT,
        "$('Compute Stats').item.json.user_message.replace(/\\\\/g, '\\\\\\\\').replace(/\"/g, '\\\\\"').replace(/\\n/g, '\\\\n')",
        pos(7, 0),
        max_tokens=400,
        temperature=0.5,
        force_json=False,
        x_title="AVM Coach PP-03",
    ))

    # ── 9. Render final message + Telegram ────────────────────
    render_code = """
const stats = $('Compute Stats').first().json;
const aiResp = $input.item.json;

let review = '';
try {
  review = aiResp.choices?.[0]?.message?.content || '';
} catch (e) {
  review = '(AI review unavailable)';
}
// Strip markdown fences if any
review = review.trim().replace(/^```[a-z]*\\s*\\n?/, '').replace(/\\n?```$/, '').trim();

const streakEmoji = stats.new_streak >= 7 ? '🔥 ' : '';
const rateBadge = stats.rate >= 0.8 ? '💪' : stats.rate >= 0.5 ? '🟡' : '🔴';

const missionPct = Math.round(stats.rate * 100);

let streakLine;
if (stats.streak_action === 'extended') {
  streakLine = `${streakEmoji}Streak: ${stats.previous_streak} → ${stats.new_streak} day(s)`;
} else if (stats.streak_action === 'broken') {
  streakLine = `💔 Streak broken (was ${stats.previous_streak})`;
} else {
  streakLine = `Streak: ${stats.new_streak} day(s) (no change)`;
}

const body = `📊 *EVENING REVIEW* — ${stats.weekday_name} ${stats.today}
Day ${stats.day_n} of 100

${rateBadge} ${stats.completed}/${stats.assigned} missions complete (${missionPct}%)
XP earned: ${stats.xp_earned} · Lifetime: ${stats.lifetime_xp}
${streakLine}

${review}
${stats.counts.Pending > 0 ? '\\n⚠️ ' + stats.counts.Pending + ' still pending — mark or carry to tomorrow' : ''}`;

return [{
  json: {
    telegram_text: body,
  }
}];
""".strip()
    nodes.append(node_code("Render Review", render_code, pos(8, 0)))

    nodes.append(node_telegram_send(
        "Send Review Telegram",
        PP_TELEGRAM_CHAT_ID,
        "={{ $json.telegram_text }}",
        pos(9, 0),
    ))

    return nodes


def pp03_connections() -> dict:
    return {
        "Daily 20:00 SAST": {"main": [[{"node": "Compute Dates", "type": "main", "index": 0}]]},
        "Compute Dates": {"main": [[{"node": "Read Today Missions", "type": "main", "index": 0}]]},
        "Read Today Missions": {"main": [[{"node": "Read Player", "type": "main", "index": 0}]]},
        "Read Player": {"main": [[{"node": "Read Today Snapshot", "type": "main", "index": 0}]]},
        "Read Today Snapshot": {"main": [[{"node": "Read Today XP Log", "type": "main", "index": 0}]]},
        "Read Today XP Log": {"main": [[{"node": "Compute Stats", "type": "main", "index": 0}]]},
        "Compute Stats": {"main": [[{"node": "Create Snapshot", "type": "main", "index": 0}]]},
        "Create Snapshot": {"main": [[{"node": "Update Player Streak", "type": "main", "index": 0}]]},
        "Update Player Streak": {"main": [[{"node": "AI Review", "type": "main", "index": 0}]]},
        "AI Review": {"main": [[{"node": "Render Review", "type": "main", "index": 0}]]},
        "Render Review": {"main": [[{"node": "Send Review Telegram", "type": "main", "index": 0}]]},
    }


# ============================================================
# PP-05: Adaptive Difficulty Tuner
# ============================================================


def pp05_nodes() -> list[dict]:
    nodes: list[dict] = []

    # ── 1. Trigger — Sunday 22:00 SAST = Sunday 20:00 UTC ─────
    nodes.append(node_schedule_cron(
        "Weekly Sunday 22:00 SAST",
        "0 20 * * 0",  # minute hour day-of-month month day-of-week (0=Sunday)
        pos(0, 0),
    ))

    # ── 2. Compute Dates (today, 14 days ago ISO) ─────────────
    dates_code = """
const SAST_OFFSET_HOURS = 2;
const now = new Date();
const sastNow = new Date(now.getTime() + SAST_OFFSET_HOURS * 3600 * 1000);
const yyyy = sastNow.getUTCFullYear();
const mm = String(sastNow.getUTCMonth() + 1).padStart(2, '0');
const dd = String(sastNow.getUTCDate()).padStart(2, '0');
const today = `${yyyy}-${mm}-${dd}`;

const launch = new Date('2026-04-22T00:00:00+02:00');
const todayMidnight = new Date(`${today}T00:00:00+02:00`);
const dayN = Math.floor((todayMidnight - launch) / (86400 * 1000)) + 1;

return [{
  json: {
    today,
    day_n: dayN,
    log_id: `xp-${today.replace(/-/g, '')}-2200-tuner`,
  }
}];
""".strip()
    nodes.append(node_code("Compute Dates", dates_code, pos(1, 0)))

    # ── 3. Read Player ────────────────────────────────────────
    nodes.append(node_airtable_search(
        "Read Player",
        MARKETING_BASE_ID,
        PP_TABLE_PLAYER,
        pos(2, 0),
        filter_formula="{Player ID}='ian-immelman'",
        limit=1,
    ))

    # ── 4. Read last 14 snapshots ─────────────────────────────
    nodes.append(node_airtable_search(
        "Read Snapshots",
        MARKETING_BASE_ID,
        PP_TABLE_PERF_SNAPSHOTS,
        pos(3, 0),
        filter_formula="DATETIME_DIFF(TODAY(),{Date},'days')<=14",
        limit=14,
    ))

    # ── 5. Compute tuning decision ────────────────────────────
    tune_code = """
const dates = $('Compute Dates').first().json;
const playerItems = $('Read Player').all();
const player = playerItems.length > 0 ? playerItems[0].json : {
  'Player ID': 'ian-immelman',
  'Current Difficulty': 'Normal',
  'Lifetime XP': 0,
  'Current Streak Days': 0,
};

// Filter out synthetic empty items from alwaysOutputData
const snapshots = $('Read Snapshots').all()
  .map(i => i.json)
  .filter(s => s && s['Snapshot ID']);

// Sort by date ascending (oldest first)
snapshots.sort((a, b) => String(a['Date']).localeCompare(String(b['Date'])));

// Take last 7 (most recent)
const recent = snapshots.slice(-7);
const sampleSize = recent.length;
const avgRate = sampleSize > 0
  ? recent.reduce((s, x) => s + (x['Completion Rate'] || 0), 0) / sampleSize
  : 0;
const totalXp = recent.reduce((s, x) => s + (x['Total XP Earned'] || 0), 0);

const ladder = ['Easy', 'Normal', 'Hard', 'Legendary'];
const currentDifficulty = player['Current Difficulty'] || 'Normal';
const currentIdx = Math.max(0, ladder.indexOf(currentDifficulty));

let action;
let newDifficulty;
let rationale;
const MIN_SAMPLES = 5;

if (sampleSize < MIN_SAMPLES) {
  action = 'hold_insufficient_data';
  newDifficulty = currentDifficulty;
  rationale = `Only ${sampleSize} snapshot(s) in rolling 7-day window, need ${MIN_SAMPLES}. Holding at ${currentDifficulty}.`;
} else if (avgRate >= 0.85 && currentIdx < ladder.length - 1) {
  action = 'bump_up';
  newDifficulty = ladder[currentIdx + 1];
  rationale = `7-day avg completion rate ${Math.round(avgRate * 100)}% (≥85% threshold). Bumping ${currentDifficulty} → ${newDifficulty}.`;
} else if (avgRate >= 0.85 && currentIdx === ladder.length - 1) {
  action = 'hold_at_max';
  newDifficulty = currentDifficulty;
  rationale = `7-day avg ${Math.round(avgRate * 100)}% at max difficulty (${currentDifficulty}). Holding.`;
} else if (avgRate < 0.60 && currentIdx > 0) {
  action = 'step_down_recovery';
  newDifficulty = ladder[currentIdx - 1];
  rationale = `7-day avg ${Math.round(avgRate * 100)}% (<60% recovery threshold). Stepping down ${currentDifficulty} → ${newDifficulty}. Recovery Week flagged.`;
} else if (avgRate < 0.60 && currentIdx === 0) {
  action = 'hold_at_easy';
  newDifficulty = currentDifficulty;
  rationale = `7-day avg ${Math.round(avgRate * 100)}% at min difficulty (${currentDifficulty}). Holding, but consider reducing mission count in PP-01.`;
} else {
  action = 'hold_stable';
  newDifficulty = currentDifficulty;
  rationale = `7-day avg ${Math.round(avgRate * 100)}% in stable band (60-84%). Holding at ${currentDifficulty}.`;
}

const changed = newDifficulty !== currentDifficulty;

// Build short telegram message
const emoji = action === 'bump_up' ? '⬆️' : action === 'step_down_recovery' ? '⬇️' : '➡️';
const telegramText = `${emoji} *PP-05 Adaptive Tuner* — Day ${dates.day_n}
Sample: ${sampleSize} snapshot(s), avg rate ${Math.round(avgRate * 100)}%, XP ${totalXp}
Difficulty: ${currentDifficulty}${changed ? ' → ' + newDifficulty : ' (unchanged)'}
${rationale}`;

return [{
  json: {
    ...dates,
    player_id: player['Player ID'],
    previous_difficulty: currentDifficulty,
    new_difficulty: newDifficulty,
    changed,
    action,
    rationale,
    sample_size: sampleSize,
    avg_rate: avgRate,
    total_xp_window: totalXp,
    lifetime_xp: player['Lifetime XP'] || 0,
    current_streak: player['Current Streak Days'] || 0,
    telegram_text: telegramText,
  }
}];
""".strip()
    nodes.append(node_code("Compute Tuning", tune_code, pos(4, 0)))

    # ── 6. Update Player difficulty (unconditional; updates only when changed) ─
    nodes.append(node_airtable_update(
        "Update Player Difficulty",
        MARKETING_BASE_ID,
        PP_TABLE_PLAYER,
        pos(5, 0),
        matching_columns=["Player ID"],
        column_values={
            "Player ID": "={{ $json.player_id }}",
            "Current Difficulty": "={{ $json.new_difficulty }}",
        },
    ))

    # ── 7. Log the tuning event to PP_XP_Log (audit trail) ────
    nodes.append(node_airtable_create(
        "Log Tuning Event",
        MARKETING_BASE_ID,
        PP_TABLE_XP_LOG,
        pos(6, 0),
        column_values={
            "Log ID": "={{ $('Compute Tuning').item.json.log_id }}",
            "Timestamp": "={{ $now.toISO() }}",
            "Mission Ref": "pp-05-tuner",
            "Event Type": "Difficulty_Tune",
            "XP Delta": 0,
            "Multiplier Applied": 1,
            "Running XP After": "={{ $('Compute Tuning').item.json.lifetime_xp }}",
            "Notes": "={{ $('Compute Tuning').item.json.action + ': ' + $('Compute Tuning').item.json.previous_difficulty + '->' + $('Compute Tuning').item.json.new_difficulty + ' (' + Math.round($('Compute Tuning').item.json.avg_rate * 100) + '% rate)' }}",
        },
    ))

    # ── 8. Send Telegram notification ─────────────────────────
    nodes.append(node_telegram_send(
        "Send Tuner Telegram",
        PP_TELEGRAM_CHAT_ID,
        "={{ $('Compute Tuning').item.json.telegram_text }}",
        pos(7, 0),
    ))

    return nodes


def pp05_connections() -> dict:
    return {
        "Weekly Sunday 22:00 SAST": {"main": [[{"node": "Compute Dates", "type": "main", "index": 0}]]},
        "Compute Dates": {"main": [[{"node": "Read Player", "type": "main", "index": 0}]]},
        "Read Player": {"main": [[{"node": "Read Snapshots", "type": "main", "index": 0}]]},
        "Read Snapshots": {"main": [[{"node": "Compute Tuning", "type": "main", "index": 0}]]},
        "Compute Tuning": {"main": [[{"node": "Update Player Difficulty", "type": "main", "index": 0}]]},
        "Update Player Difficulty": {"main": [[{"node": "Log Tuning Event", "type": "main", "index": 0}]]},
        "Log Tuning Event": {"main": [[{"node": "Send Tuner Telegram", "type": "main", "index": 0}]]},
    }


# ============================================================
# PP-06: Tap-to-Complete Callback Handler
# ============================================================
#
# Webhook-style workflow triggered by Telegram inline-button taps on the
# PP-01 mission board. Single authorised user (Ian, chat 6311361442),
# callback_data format `cmpl:<airtable_record_id>`.
#
# Idempotent: re-tapping a completed mission fires a short-circuit
# "Already logged" toast without writing anything.
#
# Latency budget ~3-5s (well under Telegram's ~15s answerCallbackQuery
# deadline). If Read Mission / Calendar Update stall, the workflow still
# reaches Answer Callback via continueRegularOutput.


def pp06_nodes() -> list[dict]:
    nodes: list[dict] = []
    ian_user_id = int(PP_TELEGRAM_CHAT_ID)  # 6311361442

    # ── 1. Telegram Trigger (callback_query) ─────────────────
    nodes.append(node_telegram_trigger(
        "Callback Trigger",
        ["callback_query"],
        pos(0, 0),
    ))

    # ── 2. Parse Callback ────────────────────────────────────
    # Validates auth + callback shape. Always emits airtable_record_id
    # (empty string on failure) so downstream nodes don't NPE — the
    # Compute Response node is the single place that routes invalid /
    # missing missions to the short-circuit path.
    parse_code = (
        """
const raw = $input.item.json;
const cq = raw.callback_query || raw.body?.callback_query || null;

const defaultOut = {
  valid: false,
  airtable_record_id: '',
  callback_id: '',
  chat_id: '',
  message_id: '',
  from_id: 0,
  reason: '',
  response_text: 'Invalid callback',
};

if (!cq) {
  return [{ json: { ...defaultOut, reason: 'No callback_query in payload' } }];
}

const fromId = cq.from && cq.from.id;
const callbackId = cq.id || '';
const data = cq.data || '';
const msg = cq.message || {};

// Authorisation: only Ian's Telegram user id can mark missions complete.
"""
        f"const IAN_USER_ID = {ian_user_id};"
        """
if (fromId !== IAN_USER_ID) {
  return [{
    json: {
      ...defaultOut,
      callback_id: callbackId,
      reason: 'Unauthorized user ' + fromId,
      response_text: 'Not authorised.',
    },
  }];
}

if (!data.startsWith('cmpl:')) {
  return [{
    json: {
      ...defaultOut,
      callback_id: callbackId,
      reason: 'Unknown callback data: ' + data,
      response_text: 'Unknown action.',
    },
  }];
}

const recordId = data.substring(5);
if (!recordId.startsWith('rec')) {
  return [{
    json: {
      ...defaultOut,
      callback_id: callbackId,
      reason: 'Invalid record id: ' + recordId,
      response_text: 'Invalid mission reference.',
    },
  }];
}

return [{
  json: {
    valid: true,
    airtable_record_id: recordId,
    callback_id: callbackId,
    chat_id: (msg.chat && msg.chat.id) || '',
    message_id: msg.message_id || '',
    from_id: fromId,
    reason: '',
    response_text: '',
  },
}];
""".strip()
    )
    nodes.append(node_code("Parse Callback", parse_code, pos(1, 0)))

    # ── 3. Read Mission by record id ─────────────────────────
    nodes.append(node_airtable_get(
        "Read Mission",
        MARKETING_BASE_ID,
        PP_TABLE_MISSIONS,
        pos(2, 0),
        record_id_expr="={{ $json.airtable_record_id }}",
    ))

    # ── 4. Read Player (always) ──────────────────────────────
    nodes.append(node_airtable_search(
        "Read Player",
        MARKETING_BASE_ID,
        PP_TABLE_PLAYER,
        pos(3, 0),
        filter_formula="{Player ID}='ian-immelman'",
        limit=1,
    ))

    # ── 5. Compute Response ──────────────────────────────────
    # Single source of truth for: XP math, idempotency check,
    # response_text, skip_writes flag, and the updated calendar summary.
    compute_code = """
const parsed = $('Parse Callback').first().json;
const missionItems = $('Read Mission').all();
const missionRaw = missionItems.length > 0 ? missionItems[0].json : null;
const playerItems = $('Read Player').all();
const player = playerItems.length > 0 ? playerItems[0].json : null;

// Short-circuit: auth/shape validation failed upstream
if (!parsed.valid) {
  return [{
    json: {
      ...parsed,
      mission_record_id: '',
      calendar_event_id: '',
      updated_summary: '',
      already_complete: false,
      skip_writes: true,
      xp_delta: 0,
      multiplier: 1.0,
      new_current_xp: 0,
      new_lifetime_xp: 0,
      new_level: 1,
      level_up: false,
      log_id: '',
      timestamp_iso: '',
      today: '',
    },
  }];
}

// Flatten Airtable v2 output (nested .fields or flat both supported)
const m = missionRaw ? (missionRaw.fields || missionRaw) : {};
const missionId = missionRaw && (missionRaw.id || '');
const hasMission = missionId && (m['Mission ID'] || m['Title']);

if (!hasMission) {
  return [{
    json: {
      ...parsed,
      mission_record_id: '',
      calendar_event_id: '',
      updated_summary: '',
      already_complete: false,
      skip_writes: true,
      xp_delta: 0,
      multiplier: 1.0,
      new_current_xp: 0,
      new_lifetime_xp: 0,
      new_level: 1,
      level_up: false,
      log_id: '',
      timestamp_iso: '',
      today: '',
      response_text: 'Mission not found — it may have been cleaned up.',
    },
  }];
}

const status = m['Status'] || '';
const title = m['Title'] || '';
const category = m['Category'] || '';
const xpValue = Number(m['XP Value'] || 0);
const calEventId = m['Calendar Event ID'] || '';

// Idempotent: already complete → emit "Already logged" toast, skip writes
if (status === 'Complete') {
  return [{
    json: {
      ...parsed,
      mission_record_id: missionId,
      calendar_event_id: calEventId,
      updated_summary: '',
      already_complete: true,
      skip_writes: true,
      xp_delta: 0,
      multiplier: 1.0,
      new_current_xp: Number((player && player['Current XP']) || 0),
      new_lifetime_xp: Number((player && player['Lifetime XP']) || 0),
      new_level: Number((player && player['Level']) || 1),
      level_up: false,
      log_id: '',
      timestamp_iso: '',
      today: '',
      response_text: 'Already logged ✅ "' + title.substring(0, 40) + '"',
    },
  }];
}

// Player state
const currentStreak = Number((player && player['Current Streak Days']) || 0);
const currentXp = Number((player && player['Current XP']) || 0);
const lifetimeXp = Number((player && player['Lifetime XP']) || 0);

// Streak multiplier: 3d→1.1×, 7d→1.25×, 14d+→1.5× (streak BEFORE today's bump)
let multiplier = 1.0;
if (currentStreak >= 14) multiplier = 1.5;
else if (currentStreak >= 7) multiplier = 1.25;
else if (currentStreak >= 3) multiplier = 1.1;

const xpDelta = Math.round(xpValue * multiplier);
const newCurrentXp = currentXp + xpDelta;
const newLifetime = lifetimeXp + xpDelta;
const newLevel = Math.floor(newLifetime / 500) + 1;
const levelUp = Math.floor(lifetimeXp / 500) < Math.floor(newLifetime / 500);

// SAST timestamp
const SAST_OFFSET_HOURS = 2;
const now = new Date();
const sastNow = new Date(now.getTime() + SAST_OFFSET_HOURS * 3600 * 1000);
const pad = n => String(n).padStart(2, '0');
const today = `${sastNow.getUTCFullYear()}-${pad(sastNow.getUTCMonth()+1)}-${pad(sastNow.getUTCDate())}`;
const ts = `${today}T${pad(sastNow.getUTCHours())}:${pad(sastNow.getUTCMinutes())}:${pad(sastNow.getUTCSeconds())}+02:00`;

// Log ID: xp-YYYYMMDD-HHMMSS-cb (cb = callback-driven, unique per second)
const logId = `xp-${today.replace(/-/g, '')}-${pad(sastNow.getUTCHours())}${pad(sastNow.getUTCMinutes())}${pad(sastNow.getUTCSeconds())}-cb`;

// Rebuild the calendar event title and prepend ✅
const originalSummary = `[${category}] ${title} - ${xpValue}XP`;
const updatedSummary = originalSummary.startsWith('✅ ') ? originalSummary : `✅ ${originalSummary}`;

const bonusLine = levelUp ? ` · 🎉 LEVEL ${newLevel}!` : '';
const responseText = `Logged ✅ +${xpDelta} XP · ${newCurrentXp}/500${bonusLine}`;

return [{
  json: {
    ...parsed,
    mission_record_id: missionId,
    mission_title: title,
    mission_category: category,
    mission_xp_value: xpValue,
    calendar_event_id: calEventId,
    has_calendar_event: calEventId !== '',
    already_complete: false,
    skip_writes: false,
    xp_delta: xpDelta,
    multiplier,
    new_current_xp: newCurrentXp,
    new_lifetime_xp: newLifetime,
    new_level: newLevel,
    level_up: levelUp,
    log_id: logId,
    timestamp_iso: ts,
    today,
    updated_summary: updatedSummary,
    response_text: responseText,
  },
}];
""".strip()
    nodes.append(node_code("Compute Response", compute_code, pos(4, 0)))

    # ── 6. If Already Complete / Invalid ─────────────────────
    # TRUE (skip_writes) → straight to Answer Callback
    # FALSE → proceed through the write chain
    nodes.append(node_if_truthy(
        "If Skip Writes",
        pos(5, 0),
        value_expr="={{ $json.skip_writes }}",
    ))

    # ── 7. Update Mission Status ─────────────────────────────
    nodes.append(node_airtable_update(
        "Update Mission Status",
        MARKETING_BASE_ID,
        PP_TABLE_MISSIONS,
        pos(6, 0),
        matching_columns=["id"],
        column_values={
            "id": "={{ $('Compute Response').item.json.mission_record_id }}",
            "Status": "Complete",
            "Completed At": "={{ $('Compute Response').item.json.timestamp_iso }}",
        },
    ))

    # ── 8. Log XP ────────────────────────────────────────────
    nodes.append(node_airtable_create(
        "Log XP",
        MARKETING_BASE_ID,
        PP_TABLE_XP_LOG,
        pos(7, 0),
        column_values={
            "Log ID": "={{ $('Compute Response').item.json.log_id }}",
            "Timestamp": "={{ $('Compute Response').item.json.timestamp_iso }}",
            "Mission Ref": "={{ $('Compute Response').item.json.mission_record_id }}",
            "Event Type": "Mission_Complete",
            "XP Delta": "={{ $('Compute Response').item.json.xp_delta }}",
            "Multiplier Applied": "={{ $('Compute Response').item.json.multiplier }}",
            "Running XP After": "={{ $('Compute Response').item.json.new_current_xp }}",
        },
    ))

    # ── 9. Update Player ─────────────────────────────────────
    nodes.append(node_airtable_update(
        "Update Player",
        MARKETING_BASE_ID,
        PP_TABLE_PLAYER,
        pos(8, 0),
        matching_columns=["Player ID"],
        column_values={
            "Player ID": "ian-immelman",
            "Current XP": "={{ $('Compute Response').item.json.new_current_xp }}",
            "Lifetime XP": "={{ $('Compute Response').item.json.new_lifetime_xp }}",
            "Level": "={{ $('Compute Response').item.json.new_level }}",
            "Last Active Date": "={{ $('Compute Response').item.json.today }}",
        },
    ))

    # ── 10. Update Calendar Event (best-effort) ──────────────
    # continueRegularOutput = if Calendar Event ID is empty or Google
    # returns 404, downstream Answer Callback still fires.
    nodes.append(node_gcal_update(
        "Update Calendar Event",
        pos(9, 0),
        calendar_id=PP_GCAL_ID,
        event_id_expr="={{ $('Compute Response').item.json.calendar_event_id }}",
        summary_expr="={{ $('Compute Response').item.json.updated_summary }}",
        color_id="10",
    ))

    # ── 11. Answer Callback ──────────────────────────────────
    # Reads queryId + text from Compute Response (authoritative, survives
    # both the short-circuit and write-chain branches).
    nodes.append(node_telegram_answer_query(
        "Answer Callback",
        pos(10, 0),
        query_id_expr="={{ $('Compute Response').item.json.callback_id }}",
        text_expr="={{ $('Compute Response').item.json.response_text }}",
    ))

    return nodes


def pp06_connections() -> dict:
    """
    Parse → Read Mission → Read Player → Compute Response → If Skip Writes
      TRUE  → Answer Callback                               (short-circuit)
      FALSE → Update Mission → Log XP → Update Player
              → Update Calendar Event → Answer Callback
    Answer Callback has two inbound connections (branches converge).
    """
    return {
        "Callback Trigger": {"main": [[{"node": "Parse Callback", "type": "main", "index": 0}]]},
        "Parse Callback": {"main": [[{"node": "Read Mission", "type": "main", "index": 0}]]},
        "Read Mission": {"main": [[{"node": "Read Player", "type": "main", "index": 0}]]},
        "Read Player": {"main": [[{"node": "Compute Response", "type": "main", "index": 0}]]},
        "Compute Response": {"main": [[{"node": "If Skip Writes", "type": "main", "index": 0}]]},
        "If Skip Writes": {
            "main": [
                # output 0 = TRUE branch → short-circuit
                [{"node": "Answer Callback", "type": "main", "index": 0}],
                # output 1 = FALSE branch → do the writes
                [{"node": "Update Mission Status", "type": "main", "index": 0}],
            ],
        },
        "Update Mission Status": {"main": [[{"node": "Log XP", "type": "main", "index": 0}]]},
        "Log XP": {"main": [[{"node": "Update Player", "type": "main", "index": 0}]]},
        "Update Player": {"main": [[{"node": "Update Calendar Event", "type": "main", "index": 0}]]},
        "Update Calendar Event": {"main": [[{"node": "Answer Callback", "type": "main", "index": 0}]]},
    }


# ============================================================
# WORKFLOW REGISTRY
# ============================================================

WORKFLOW_DEFS: dict[str, dict] = {
    "pp01": {
        "name": "PP-01 Morning Mission Board",
        "build_nodes": pp01_nodes,
        "build_connections": pp01_connections,
        "filename": "pp01_morning_mission_board.json",
        "env_key": "PP01_WORKFLOW_ID",
    },
    "pp02": {
        "name": "PP-02 Midday Check-in",
        "build_nodes": pp02_nodes,
        "build_connections": pp02_connections,
        "filename": "pp02_midday_checkin.json",
        "env_key": "PP02_WORKFLOW_ID",
    },
    "pp03": {
        "name": "PP-03 Evening Review",
        "build_nodes": pp03_nodes,
        "build_connections": pp03_connections,
        "filename": "pp03_evening_review.json",
        "env_key": "PP03_WORKFLOW_ID",
    },
    "pp05": {
        "name": "PP-05 Adaptive Difficulty Tuner",
        "build_nodes": pp05_nodes,
        "build_connections": pp05_connections,
        "filename": "pp05_adaptive_tuner.json",
        "env_key": "PP05_WORKFLOW_ID",
    },
    "pp06": {
        "name": "PP-06 Tap-to-Complete Callback Handler",
        "build_nodes": pp06_nodes,
        "build_connections": pp06_connections,
        "filename": "pp06_tap_to_complete_handler.json",
        "env_key": "PP06_WORKFLOW_ID",
    },
}


# ============================================================
# BUILD / SAVE / DEPLOY
# ============================================================

def build_workflow(wf_id: str) -> dict:
    if wf_id not in WORKFLOW_DEFS:
        valid = ", ".join(WORKFLOW_DEFS.keys())
        raise ValueError(f"Unknown workflow '{wf_id}'. Valid: {valid}")

    wf_def = WORKFLOW_DEFS[wf_id]
    nodes = wf_def["build_nodes"]()
    connections = wf_def["build_connections"]()

    return {
        "name": wf_def["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            # Explicit UTC — do NOT change to Africa/Johannesburg.
            # n8n's ScheduleTrigger interprets cron expressions in the
            # workflow's configured timezone (ScheduleTrigger.node.ts:446).
            # All PP-* crons are written in UTC so they must stay in UTC:
            #   "30 4 * * *"  → 04:30 UTC = 06:30 SAST (PP-01 morning board)
            #   "0 11 * * *"  → 11:00 UTC = 13:00 SAST (PP-02 midday check-in)
            #   "0 18 * * *"  → 18:00 UTC = 20:00 SAST (PP-03 evening review)
            #   "0 20 * * 0"  → Sun 20:00 UTC = Sun 22:00 SAST (PP-05 tuner)
            # IMPORTANT: n8n's PUT /workflows/{id} merges settings server-side.
            # If we omit "timezone" and the live workflow has a stale
            # timezone (e.g. Africa/Johannesburg from an earlier deploy),
            # the stale value persists across redeploys and crons fire 2h
            # early. Explicit "UTC" overwrites any stale value on every PUT.
            "timezone": "UTC",
            "availableInMCP": True,
        },
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def save_workflow(wf_id: str, workflow: dict) -> Path:
    output_dir = Path(__file__).parent.parent / "workflows" / "personal-ops-dept"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / WORKFLOW_DEFS[wf_id]["filename"]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    return output_path


def print_workflow_stats(wf_id: str, workflow: dict) -> None:
    nodes = workflow["nodes"]
    conns = workflow["connections"]
    types: dict[str, int] = {}
    for n in nodes:
        t = n["type"].split(".")[-1]
        types[t] = types.get(t, 0) + 1
    print(f"  {wf_id}: {len(nodes)} nodes, {len(conns)} connection sources")
    for t, c in sorted(types.items(), key=lambda kv: -kv[1]):
        print(f"    - {t}: {c}")


def main() -> None:
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    print("=" * 60)
    print("PERSONAL OPS / AVM COACH — WORKFLOW DEPLOYER")
    print("=" * 60)

    valid_wfs = list(WORKFLOW_DEFS.keys())
    if target == "all":
        workflow_ids = valid_wfs
    elif target in valid_wfs:
        workflow_ids = [target]
    else:
        print(f"ERROR: unknown target '{target}'. Valid: all, {', '.join(valid_wfs)}")
        sys.exit(1)

    # Validate Airtable config
    if not PP_TABLE_PLAYER or not PP_TABLE_MISSIONS:
        print()
        print("ERROR: PP_TABLE_* not set in .env")
        print("  Run: python tools/setup_personal_ops_airtable.py --seed")
        sys.exit(1)

    print(f"Action:  {action}")
    print(f"Target:  {target}")
    print(f"Base ID: {MARKETING_BASE_ID}")
    print(f"Cal ID:  {PP_GCAL_ID}")
    print(f"Chat ID: {PP_TELEGRAM_CHAT_ID}")
    print(f"Launch:  {PP_LAUNCH_DATE}")
    print()

    workflows: dict[str, dict] = {}
    for wf_id in workflow_ids:
        print(f"Building {wf_id}...")
        workflow = build_workflow(wf_id)
        output_path = save_workflow(wf_id, workflow)
        workflows[wf_id] = workflow
        print_workflow_stats(wf_id, workflow)
        print(f"  Saved: {output_path}")
        print()

    if action == "build":
        print("Build complete. Run with 'deploy' to push to n8n.")
        return

    if action not in ("deploy", "activate"):
        print(f"ERROR: unknown action '{action}'. Use: build | deploy | activate")
        sys.exit(1)

    from n8n_client import N8nClient  # noqa: E402

    api_key = os.getenv("N8N_API_KEY")
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")

    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        sys.exit(1)

    print(f"Connecting to {base_url}...")
    with N8nClient(base_url, api_key, timeout=30) as client:
        health = client.health_check()
        if not health.get("connected"):
            print(f"  ERROR: cannot connect: {health.get('error')}")
            sys.exit(1)
        print("  Connected.")
        print()

        deployed_ids: dict[str, str] = {}

        for wf_id, workflow in workflows.items():
            print(f"Deploying {wf_id}...")

            # Prefer explicit ID from .env (avoids stale cache issues)
            env_key = WORKFLOW_DEFS[wf_id]["env_key"]
            existing_id = os.getenv(env_key, "").strip()
            existing = None

            if existing_id:
                try:
                    existing = client.get_workflow(existing_id)
                    print(f"  Found by env {env_key}={existing_id}")
                except Exception as e:
                    print(f"  WARN: {env_key}={existing_id} not found ({e}); searching by name")
                    existing = None

            if not existing:
                try:
                    for wf in client.list_workflows():
                        if wf.get("name") == workflow["name"]:
                            existing = wf
                            break
                except Exception as e:
                    print(f"  WARN: list_workflows failed ({e}); creating fresh")

            payload = {
                "name": workflow["name"],
                "nodes": workflow["nodes"],
                "connections": workflow["connections"],
                "settings": workflow["settings"],
            }

            if existing:
                result = client.update_workflow(existing["id"], payload)
                deployed_ids[wf_id] = result.get("id", existing["id"])
                print(f"  Updated: {result.get('name')} ({deployed_ids[wf_id]})")
            else:
                result = client.create_workflow(payload)
                deployed_ids[wf_id] = result.get("id")
                print(f"  Created: {result.get('name')} ({deployed_ids[wf_id]})")

            if action == "activate" and deployed_ids.get(wf_id):
                print(f"  Activating {wf_id}...")
                client.activate_workflow(deployed_ids[wf_id])
                print("  Activated.")
            print()

        print("=" * 60)
        print("DEPLOYMENT COMPLETE")
        print("=" * 60)
        print("\nDeployed IDs (add to .env):")
        for wf_id, wid in deployed_ids.items():
            env_key = WORKFLOW_DEFS[wf_id]["env_key"]
            print(f"  {env_key}={wid}")


if __name__ == "__main__":
    main()

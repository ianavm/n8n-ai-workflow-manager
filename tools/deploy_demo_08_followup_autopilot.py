"""DEMO-08: Client Follow-Up Autopilot.

Scheduled at 09:00 SAST daily. Reads the ``Follow_Ups`` tab, filters to
rows whose ``Scheduled_For`` is due today or earlier and ``Status=due``,
generates a personalised re-engagement email per row, sends it (or
drafts it, depending on ``Demo_Control.send_real_emails``), then marks
the row as ``sent`` with today's timestamp.

No live/demo branch — the Follow_Ups tab IS the data source in both
modes. In demo mode we also seed two rows so the workflow has something
to process the first time you run it.

Flow::

    Schedule Trigger (09:00 daily) + Webhook Trigger (on-demand)
        -> Demo Config
        -> Read Follow_Ups tab
        -> Filter Due Rows (Code)
        -> Seed Demo Rows If Empty (Code: only fires in demo mode)
        -> Fan Out -> per-row
            -> AI Personalise Follow-Up
            -> Gmail Send / Draft (based on Demo_Control)
            -> Mark Row Sent (Sheets update)
        -> Aggregate Summary
        -> Slack Digest
        -> Audit Log
        -> Respond
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from demo_vol2_shared import (  # noqa: E402
    DemoSpec,
    MODEL_SONNET,
    audit_log,
    build_workflow_envelope,
    code_node,
    gmail_send,
    openrouter_call,
    respond_to_webhook,
    run_cli,
    schedule_trigger,
    set_demo_config,
    sheets_read,
    sheets_update,
    slack_notify,
    uid,
    webhook_trigger,
)

WORKFLOW_NAME = "DEMO-08 Client Follow-Up Autopilot"
WORKFLOW_FILENAME = "demo08_followup_autopilot.json"
WEBHOOK_PATH = "demo08-followup-autopilot"


FIXTURE_SEEDS = [
    {
        "Follow_Up_ID": "FU-DEMO-001",
        "Related_Record": "Q-2026-0123",
        "Contact": "naledi@bluehorizon.co.za",
        "Scheduled_For": "2026-04-19",
        "Type": "check-in",
        "Status": "due",
        "Last_Action": "intro-call-2026-04-12",
        "Notes": "Asked about automation for client onboarding. Decided nothing yet.",
    },
    {
        "Follow_Up_ID": "FU-DEMO-002",
        "Related_Record": "LEAD-88",
        "Contact": "pieter@karoocraft.co.za",
        "Scheduled_For": "2026-04-20",
        "Type": "quote-followup",
        "Status": "due",
        "Last_Action": "quote-sent-2026-04-17",
        "Notes": "Sent freight quote R82k. No response in 3 days.",
    },
]


FOLLOWUP_PROMPT = r"""You are Ian Immelman, founder of AnyVision Media, writing a
personalised re-engagement email based on the follow-up record below.

Rules:
- 3 short sentences. No filler, no emoji, no "just checking in".
- Reference the specific last_action / notes so it reads human.
- End with a concrete next step (a specific time slot, a link, or a
  "reply yes and I'll send the proposal").
- STRICT JSON OUTPUT ONLY, no markdown:
    { "subject": "...", "bodyHtml": "<p>...</p>" }

Record:
""" + "${JSON.stringify($json, null, 2)}"


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    nodes.append(
        schedule_trigger(
            name="Daily 09:00 SAST",
            hour=9,
            minute=0,
            position=(200, 200),
        )
    )
    nodes.append(webhook_trigger(WEBHOOK_PATH, position=(200, 420)))

    nodes.append(set_demo_config(position=(420, 300)))

    nodes.append(
        sheets_read(
            "Read Follow_Ups Tab",
            "Follow_Ups",
            position=(640, 300),
        )
    )

    nodes.append(
        code_node(
            "Filter Due Rows",
            f"""const rows = $input.all().map(i => i.json);
const today = new Date().toISOString().slice(0, 10);
const due = rows.filter(r => (r.Status || '').toLowerCase() === 'due'
  && (r.Scheduled_For || '') <= today);

// If there are no due rows AND we are in demo mode, inject fixture seeds
// so the workflow always has something to show on camera.
const cfg = $('Demo Config').first().json;
if (due.length === 0 && String(cfg.demoMode) === '1') {{
  const seeds = {FIXTURE_SEEDS!r};
  return JSON.parse(JSON.stringify(seeds)).map(s => ({{ json: {{ ...s, _seeded: true }} }}));
}}
return due.map(r => ({{ json: r }}));
""",
            position=(860, 300),
        )
    )

    nodes.append(
        code_node(
            "Build Per-Row Prompt",
            f"""const r = $json;
const prompt = `{FOLLOWUP_PROMPT}`;
return [{{ json: {{ ...r, prompt }} }}];
""",
            position=(1080, 300),
        )
    )

    nodes.append(
        openrouter_call(
            "AI Personalise Follow-Up",
            "$json.prompt",
            model=MODEL_SONNET,
            temperature=0.5,
            max_tokens=500,
            position=(1300, 300),
        )
    )

    nodes.append(
        code_node(
            "Parse Follow-Up",
            """const src = $('Build Per-Row Prompt').first().json;
const resp = $input.first().json || {};
const raw = resp.choices?.[0]?.message?.content || '';
const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
let parsed = {};
try { parsed = cleaned ? JSON.parse(cleaned) : {}; } catch (e) {}
return [{
  json: {
    ...src,
    subject: parsed.subject || `Quick follow-up on ${src.Related_Record || 'our last chat'}`,
    bodyHtml: parsed.bodyHtml || `<p>Hi, just circling back on the ${src.Type || 'follow-up'} from ${src.Last_Action || 'earlier'}. Let me know if helpful.</p><p>Ian</p>`,
  }
}];""",
            position=(1520, 300),
        )
    )

    nodes.append(
        gmail_send(
            "Send Follow-Up Email",
            to_expr="={{ $json.Contact }}",
            subject_expr="={{ $json.subject }}",
            body_expr="={{ $json.bodyHtml }}",
            position=(1740, 300),
        )
    )

    nodes.append(
        sheets_update(
            "Mark Row Sent",
            "Follow_Ups",
            {
                "Follow_Up_ID": "={{ $json.Follow_Up_ID }}",
                "Status": "'sent'",
                "Last_Action": (
                    "={{ 'followup-sent-' + new Date().toISOString().slice(0, 10) }}"
                ),
                "Notes": "={{ $json.Notes }}",
            },
            matching_column="Follow_Up_ID",
            position=(1960, 300),
        )
    )

    nodes.append(
        code_node(
            "Aggregate Summary",
            """const all = $input.all().map(i => i.json);
const runId = $('Demo Config').first().json.runId;
const slackText = all.length === 0
  ? `_No follow-ups due today (run ${runId})._`
  : `*Follow-up autopilot* sent ${all.length} personalised emails:\\n` +
    all.map(r => `- ${r.Contact} (${r.Type || 'follow-up'})`).join('\\n');
return [{
  json: {
    runId,
    processed: all.length,
    contacts: all.map(r => r.Contact),
    slackText,
  }
}];""",
            position=(2200, 300),
        )
    )

    nodes.append(slack_notify("Slack Digest", "$json.slackText", position=(2440, 300)))
    nodes.append(audit_log("DEMO-08", position=(2680, 300)))
    nodes.append(
        respond_to_webhook(
            body_expr=(
                "JSON.stringify({"
                "status: 'complete', "
                "runId: $('Aggregate Summary').first().json.runId, "
                "processed: $('Aggregate Summary').first().json.processed, "
                "contacts: $('Aggregate Summary').first().json.contacts "
                "})"
            ),
            position=(2920, 300),
        )
    )

    return nodes


def build_connections(_nodes: list[dict]) -> dict:
    return {
        "Daily 09:00 SAST": {
            "main": [[{"node": "Demo Config", "type": "main", "index": 0}]]
        },
        "Webhook Trigger": {
            "main": [[{"node": "Demo Config", "type": "main", "index": 0}]]
        },
        "Demo Config": {
            "main": [[{"node": "Read Follow_Ups Tab", "type": "main", "index": 0}]]
        },
        "Read Follow_Ups Tab": {
            "main": [[{"node": "Filter Due Rows", "type": "main", "index": 0}]]
        },
        "Filter Due Rows": {
            "main": [[{"node": "Build Per-Row Prompt", "type": "main", "index": 0}]]
        },
        "Build Per-Row Prompt": {
            "main": [[{"node": "AI Personalise Follow-Up", "type": "main", "index": 0}]]
        },
        "AI Personalise Follow-Up": {
            "main": [[{"node": "Parse Follow-Up", "type": "main", "index": 0}]]
        },
        "Parse Follow-Up": {
            "main": [[{"node": "Send Follow-Up Email", "type": "main", "index": 0}]]
        },
        "Send Follow-Up Email": {
            "main": [[{"node": "Mark Row Sent", "type": "main", "index": 0}]]
        },
        "Mark Row Sent": {
            "main": [[{"node": "Aggregate Summary", "type": "main", "index": 0}]]
        },
        "Aggregate Summary": {
            "main": [[{"node": "Slack Digest", "type": "main", "index": 0}]]
        },
        "Slack Digest": {
            "main": [[{"node": "Audit Log", "type": "main", "index": 0}]]
        },
        "Audit Log": {
            "main": [[{"node": "Respond", "type": "main", "index": 0}]]
        },
    }


def build_workflow() -> dict:
    nodes = build_nodes()
    connections = build_connections(nodes)
    return build_workflow_envelope(WORKFLOW_NAME, nodes, connections)


if __name__ == "__main__":
    run_cli(DemoSpec(WORKFLOW_NAME, WORKFLOW_FILENAME, build_workflow))

"""DEMO-07: Meeting Notes -> Action Machine.

Paste (or POST) a meeting transcript; the workflow extracts action items
with owners and due dates, writes each row to ``Meeting_Actions``, emails
a summary to every attendee, and posts a digest to Slack.

Flow::

    Webhook Trigger (transcript + attendees)
        -> Demo Config (fixture transcript + meeting title)
        -> DEMO_MODE Switch
            -> demo : Load Fixture Meeting
            -> live : Extract Live Meeting
        -> Merge
        -> AI Extract Actions (Sonnet, strict JSON list)
        -> Parse Actions (fan out one item per action)
        -> Log each action to Meeting_Actions
        -> Aggregate Summary (Code)
        -> Send Digest to Attendees (Gmail, one per address)
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
    demo_mode_switch,
    gmail_send,
    openrouter_call,
    respond_to_webhook,
    run_cli,
    set_demo_config,
    sheets_append,
    slack_notify,
    uid,
    webhook_trigger,
)

WORKFLOW_NAME = "DEMO-07 Meeting Notes to Action Machine"
WORKFLOW_FILENAME = "demo07_meeting_notes.json"
WEBHOOK_PATH = "demo07-meeting-notes"


FIXTURE_MEETING = {
    "meetingTitle": "AnyVision <> Fourways Fitness — kickoff",
    "meetingDate": "2026-04-20",
    "attendees": [
        {"name": "Ian Immelman", "email": "ian@anyvisionmedia.com"},
        {"name": "Kagiso Mokoena", "email": "kagiso@fourwaysfitness.co.za"},
        {"name": "Thandi Xaba", "email": "thandi@fourwaysfitness.co.za"},
    ],
    "transcript": (
        "Ian: Great to meet you both. Let's lock in scope. First "
        "priority was the WhatsApp enquiry bot, right?\n"
        "Kagiso: Yes. Every week we miss 30-40 enquiries because nobody "
        "watches the number after 6pm. Thandi, can you export the last "
        "month of messages for Ian by Wednesday?\n"
        "Thandi: I'll pull them from Business Suite and drop in Drive.\n"
        "Ian: Perfect. On my side I'll ship a first draft of the bot by "
        "Friday next week so we can test it over the weekend.\n"
        "Kagiso: Second thing — can we also automate class-booking "
        "follow-ups? Members who book but don't show up.\n"
        "Ian: That's a separate workflow, phase 2. I'll write up scope "
        "and pricing and send it tomorrow.\n"
        "Kagiso: Great. Last thing, invoicing — can Thandi get added "
        "to the invoice email so she can process it properly?\n"
        "Ian: Noted — I'll cc Thandi on every invoice from now."
    ),
}


EXTRACT_PROMPT = r"""You are a meeting-notes processor. From the transcript
below, extract every concrete action item. Output STRICT JSON ONLY
(no markdown fences):

  {
    "summary": "3-sentence summary of the meeting",
    "actions": [
      {
        "description": "what needs to happen, plain English",
        "owner": "name OR email OR 'unassigned'",
        "dueDate": "YYYY-MM-DD or '' if not specified",
        "priority": "high|medium|low"
      }
    ]
  }

Rules:
- Only include items that are genuinely actionable (not descriptions of past events).
- Preserve owner names exactly as mentioned in the transcript.
- Convert relative dates against meetingDate (e.g. 'by Wednesday' -> the next Wed).
- If a phase/workstream is mentioned but not explicitly owned, owner='unassigned'.

Meeting:
""" + "${JSON.stringify($json, null, 2)}"


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    nodes.append(webhook_trigger(WEBHOOK_PATH, position=(200, 300)))

    nodes.append(
        set_demo_config(fixture_payload=FIXTURE_MEETING, position=(420, 300))
    )

    nodes.append(demo_mode_switch(position=(640, 300)))

    nodes.append(
        code_node(
            "Load Fixture Meeting",
            """const cfg = $('Demo Config').first().json;
const m = JSON.parse(cfg.fixtureData);
return [{ json: { ...m, runId: cfg.runId } }];
""",
            position=(860, 200),
        )
    )

    nodes.append(
        code_node(
            "Extract Live Meeting",
            """const cfg = $('Demo Config').first().json;
const body = $json.body || $json;
return [{
  json: {
    meetingTitle: body.meetingTitle || body.title || 'Untitled meeting',
    meetingDate: body.meetingDate || new Date().toISOString().slice(0, 10),
    attendees: Array.isArray(body.attendees) ? body.attendees : [],
    transcript: body.transcript || body.notes || '',
    runId: cfg.runId,
  }
}];""",
            position=(860, 420),
        )
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Merge Meeting Sources",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [1080, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(
        code_node(
            "Build Extract Prompt",
            f"""const m = $input.first().json;
const prompt = `{EXTRACT_PROMPT}`;
return [{{ json: {{ ...m, prompt }} }}];
""",
            position=(1300, 300),
        )
    )

    nodes.append(
        openrouter_call(
            "AI Extract Actions",
            "$json.prompt",
            model=MODEL_SONNET,
            temperature=0.2,
            max_tokens=1500,
            position=(1520, 300),
        )
    )

    nodes.append(
        code_node(
            "Parse & Fan Out Actions",
            """const meeting = $('Build Extract Prompt').first().json;
const resp = $input.first().json || {};
const raw = resp.choices?.[0]?.message?.content || '';
const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
let parsed = { summary: '', actions: [] };
try { parsed = cleaned ? JSON.parse(cleaned) : parsed; } catch (e) {}
const actions = Array.isArray(parsed.actions) ? parsed.actions : [];

// Store summary on a side channel via a single 'summary item' we prefix.
const header = { json: { _kind: 'summary', meeting, summary: parsed.summary || '' } };
const rows = actions.map((a, i) => ({
  json: {
    _kind: 'action',
    meetingTitle: meeting.meetingTitle,
    meetingDate: meeting.meetingDate,
    attendees: meeting.attendees,
    runId: meeting.runId,
    actionIndex: i + 1,
    description: a.description || '',
    owner: a.owner || 'unassigned',
    dueDate: a.dueDate || '',
    priority: (a.priority || 'medium').toLowerCase(),
    status: 'open',
  }
}));
return [header, ...rows];""",
            position=(1740, 300),
        )
    )

    # Filter to only actions for downstream logging.
    nodes.append(
        code_node(
            "Filter Actions Only",
            """return $input.all().filter(i => i.json._kind === 'action');""",
            position=(1960, 200),
        )
    )

    nodes.append(
        sheets_append(
            "Log Meeting Action",
            "Meeting_Actions",
            {
                "Timestamp": "={{ new Date().toISOString() }}",
                "Meeting_Title": "={{ $json.meetingTitle }}",
                "Attendees": (
                    "={{ ($json.attendees || []).map(a => a.name || a.email).join(', ') }}"
                ),
                "Action_Item": "={{ $json.description }}",
                "Owner": "={{ $json.owner }}",
                "Due_Date": "={{ $json.dueDate }}",
                "Status": "={{ $json.status }}",
                "Run_ID": "={{ $json.runId }}",
            },
            position=(2200, 200),
        )
    )

    # Build a single digest item summarising all actions for the email.
    nodes.append(
        code_node(
            "Build Digest",
            """const summaryItem = $('Parse & Fan Out Actions').all()
  .find(i => i.json._kind === 'summary')?.json || {};
const actions = $('Parse & Fan Out Actions').all()
  .filter(i => i.json._kind === 'action')
  .map(i => i.json);

const meeting = summaryItem.meeting || {};
const attendees = (meeting.attendees || []);
const toList = attendees.map(a => a.email).filter(Boolean).join(',');

function esc(s) { return String(s).replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

const rows = actions.map(a => `
  <tr>
    <td>${esc(a.description)}</td>
    <td>${esc(a.owner)}</td>
    <td>${esc(a.dueDate || 'TBD')}</td>
    <td>${esc(a.priority)}</td>
  </tr>`).join('');

const html = `<p>Hi team,</p>
<p>Here is the action list from <b>${esc(meeting.meetingTitle || 'our meeting')}</b> (${esc(meeting.meetingDate || '')}):</p>
<p>${esc(summaryItem.summary || '')}</p>
<table border="1" cellpadding="6" cellspacing="0">
  <thead><tr><th>Action</th><th>Owner</th><th>Due</th><th>Priority</th></tr></thead>
  <tbody>${rows || '<tr><td colspan=4>No actions captured.</td></tr>'}</tbody>
</table>
<p>Ian</p>`;

const slackText = `*${meeting.meetingTitle || 'Meeting'}* — ${actions.length} actions captured\\n` +
  actions.map(a => `- ${a.description} (_${a.owner}, due ${a.dueDate || 'TBD'}_)`).join('\\n');

return [{
  json: {
    meetingTitle: meeting.meetingTitle || '',
    runId: meeting.runId || $('Demo Config').first().json.runId,
    toList,
    actionsCount: actions.length,
    digestHtml: html,
    slackText,
    summary: summaryItem.summary || '',
  }
}];""",
            position=(1960, 420),
        )
    )

    nodes.append(
        gmail_send(
            "Email Digest to Attendees",
            to_expr="={{ $json.toList }}",
            subject_expr="='Action items — ' + $json.meetingTitle",
            body_expr="={{ $json.digestHtml }}",
            position=(2200, 420),
        )
    )

    nodes.append(slack_notify("Slack Digest", "$json.slackText", position=(2440, 420)))

    # Merge the fan-out (logs) and digest branches before audit.
    nodes.append(
        {
            "id": uid(),
            "name": "Merge Branches",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [2680, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(audit_log("DEMO-07", position=(2920, 300)))

    nodes.append(
        respond_to_webhook(
            body_expr=(
                "JSON.stringify({"
                "status: 'complete', "
                "runId: $('Demo Config').first().json.runId, "
                "actionsCount: $('Build Digest').first().json.actionsCount, "
                "summary: $('Build Digest').first().json.summary "
                "})"
            ),
            position=(3160, 300),
        )
    )

    return nodes


def build_connections(_nodes: list[dict]) -> dict:
    return {
        "Webhook Trigger": {
            "main": [[{"node": "Demo Config", "type": "main", "index": 0}]]
        },
        "Demo Config": {
            "main": [[{"node": "DEMO_MODE Switch", "type": "main", "index": 0}]]
        },
        "DEMO_MODE Switch": {
            "main": [
                [{"node": "Load Fixture Meeting", "type": "main", "index": 0}],
                [{"node": "Extract Live Meeting", "type": "main", "index": 0}],
            ]
        },
        "Load Fixture Meeting": {
            "main": [[{"node": "Merge Meeting Sources", "type": "main", "index": 0}]]
        },
        "Extract Live Meeting": {
            "main": [[{"node": "Merge Meeting Sources", "type": "main", "index": 1}]]
        },
        "Merge Meeting Sources": {
            "main": [[{"node": "Build Extract Prompt", "type": "main", "index": 0}]]
        },
        "Build Extract Prompt": {
            "main": [[{"node": "AI Extract Actions", "type": "main", "index": 0}]]
        },
        "AI Extract Actions": {
            "main": [[{"node": "Parse & Fan Out Actions", "type": "main", "index": 0}]]
        },
        "Parse & Fan Out Actions": {
            "main": [
                [
                    {"node": "Filter Actions Only", "type": "main", "index": 0},
                    {"node": "Build Digest", "type": "main", "index": 0},
                ]
            ]
        },
        "Filter Actions Only": {
            "main": [[{"node": "Log Meeting Action", "type": "main", "index": 0}]]
        },
        "Log Meeting Action": {
            "main": [[{"node": "Merge Branches", "type": "main", "index": 0}]]
        },
        "Build Digest": {
            "main": [[{"node": "Email Digest to Attendees", "type": "main", "index": 0}]]
        },
        "Email Digest to Attendees": {
            "main": [[{"node": "Slack Digest", "type": "main", "index": 0}]]
        },
        "Slack Digest": {
            "main": [[{"node": "Merge Branches", "type": "main", "index": 1}]]
        },
        "Merge Branches": {
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

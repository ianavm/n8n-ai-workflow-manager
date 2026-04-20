"""DEMO-09: Email -> CRM Auto-Updater (Before vs After).

The "Before vs After" demo. Before: you get an email with client info and
you copy-paste name/company/phone/ask into a spreadsheet, then maybe
remember to reply. After: the inbox updates your CRM Sheet and fires an
acknowledgement automatically.

Flow::

    Gmail Trigger (INBOX) OR Webhook
        -> Demo Config (fixture email)
        -> DEMO_MODE Switch
            -> demo : Load Fixture Email
            -> live : Normalise Gmail Payload
        -> Merge
        -> AI Extract CRM Fields (Sonnet, strict JSON)
        -> Parse Extracted Fields
        -> Has Actionable Fields? (IF)
            -> yes : Upsert Client Row + Send Acknowledgement
            -> no  : Skip (log audit)
        -> Audit Log
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
    gmail_trigger,
    openrouter_call,
    run_cli,
    set_demo_config,
    sheets_append,
    sheets_update,
    uid,
    webhook_trigger,
)

WORKFLOW_NAME = "DEMO-09 Email -> CRM Auto-Updater"
WORKFLOW_FILENAME = "demo09_email_crm_updater.json"

FIXTURE_EMAIL = {
    "threadId": "thread-fx-09-001",
    "messageId": "msg-fx-09-001",
    "from": "Naledi van Wyk <naledi@bluehorizon.co.za>",
    "subject": "Intro — Blue Horizon Consulting wants to explore automation",
    "body": (
        "Hi Ian,\n\n"
        "We spoke briefly at the JCCI breakfast last month. I run Blue Horizon "
        "Consulting (20-person boutique, mostly corporate strategy work). "
        "We're drowning in admin — client onboarding, status reports, "
        "follow-ups. \n\n"
        "Would love to chat about what automation could do for us. My direct "
        "line is +27 82 413 6609, and I'm generally free after 2pm on "
        "Tuesdays and Thursdays.\n\n"
        "Looking at a 3-6 month engagement, budget R20-40k/mo depending on "
        "scope.\n\n"
        "Naledi\n"
        "Managing Partner | Blue Horizon Consulting"
    ),
    "date": "2026-04-20T08:14:00Z",
}


EXTRACT_PROMPT = r"""You are a CRM data extractor. Read the email below and extract
the sender's structured details. Return STRICT JSON ONLY (no prose, no markdown
fences), with these keys:

  {
    "name": "...",
    "company": "...",
    "email": "...",
    "phone": "...|null",
    "ask": "one-sentence summary of what they want",
    "budgetZAR": "string or null, preserve their wording e.g. 'R20-40k/mo'",
    "availability": "string or null, e.g. 'Tue/Thu after 2pm'",
    "leadScore": 1-10,
    "shouldAcknowledge": true|false,
    "acknowledgementBody": "<p>...</p>" (HTML, 3 short sentences, sign off as Ian)
  }

Rules:
- If you cannot confidently identify a field, use null (never invent data).
- shouldAcknowledge = false only if the email is clearly spam or an auto-
  responder bounce.
- leadScore rubric: 10 = ready-to-buy with budget + timeline; 5 = curious;
  1 = unrelated/noise.

Email:
""" + "${JSON.stringify($json, null, 2)}"


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    nodes.append(
        gmail_trigger(
            name="Gmail Inbox Trigger",
            label_ids=["INBOX"],
            position=(200, 200),
        )
    )
    nodes.append(webhook_trigger("demo09-email-crm", position=(200, 420)))

    nodes.append(
        set_demo_config(fixture_payload=FIXTURE_EMAIL, position=(420, 300))
    )

    nodes.append(demo_mode_switch(position=(640, 300)))

    nodes.append(
        code_node(
            "Load Fixture Email",
            """const cfg = $('Demo Config').first().json;
const m = JSON.parse(cfg.fixtureData);
return [{ json: { ...m, runId: cfg.runId } }];
""",
            position=(860, 200),
        )
    )

    nodes.append(
        code_node(
            "Normalise Gmail Payload",
            """const cfg = $('Demo Config').first().json;
const raw = $json;
const headers = raw.payload?.headers || [];
const h = (n) => headers.find(x => x.name?.toLowerCase() === n.toLowerCase())?.value || '';
return [{
  json: {
    threadId: raw.threadId || raw.id,
    messageId: raw.id,
    from: h('From') || raw.from || 'unknown',
    subject: h('Subject') || raw.subject || '(no subject)',
    body: raw.snippet || raw.textPlain || raw.body || '',
    date: h('Date') || new Date().toISOString(),
    runId: cfg.runId,
  }
}];""",
            position=(860, 420),
        )
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Merge Email Sources",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [1080, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(
        code_node(
            "Build Extract Prompt",
            f"""const msg = $input.first().json;
const prompt = `{EXTRACT_PROMPT}`;
return [{{ json: {{ ...msg, prompt }} }}];
""",
            position=(1300, 300),
        )
    )

    nodes.append(
        openrouter_call(
            "AI Extract CRM Fields",
            "$json.prompt",
            model=MODEL_SONNET,
            temperature=0.2,
            max_tokens=900,
            position=(1520, 300),
        )
    )

    nodes.append(
        code_node(
            "Parse Extracted Fields",
            """const msg = $('Build Extract Prompt').first().json;
const resp = $input.first().json || {};
const raw = resp.choices?.[0]?.message?.content || '';
const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
let parsed = {};
try { parsed = cleaned ? JSON.parse(cleaned) : {}; } catch (e) {}

function deriveEmail(from) {
  const m = String(from).match(/<([^>]+)>/);
  return m ? m[1] : (String(from).includes('@') ? String(from).trim() : '');
}

const emailAddr = parsed.email || deriveEmail(msg.from) || '';
const safeName = parsed.name || String(msg.from).split('<')[0].replace(/\"/g, '').trim() || 'Unknown';

return [{
  json: {
    ...msg,
    clientId: `CLT-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
    name: safeName,
    company: parsed.company || '',
    email: emailAddr,
    phone: parsed.phone || '',
    ask: parsed.ask || msg.subject || '',
    budgetZAR: parsed.budgetZAR || '',
    availability: parsed.availability || '',
    leadScore: Number(parsed.leadScore) || 3,
    shouldAcknowledge: parsed.shouldAcknowledge !== false && !!emailAddr,
    acknowledgementBody: parsed.acknowledgementBody || `<p>Thanks for reaching out — I will come back to you within one business day.</p><p>Ian</p>`,
  }
}];""",
            position=(1740, 300),
        )
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Has Actionable Fields?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [1960, 300],
            "parameters": {
                "conditions": {
                    "options": {
                        "caseSensitive": True,
                        "leftValue": "",
                        "typeValidation": "strict",
                    },
                    "conditions": [
                        {
                            "id": uid(),
                            "leftValue": "={{ $json.shouldAcknowledge }}",
                            "rightValue": True,
                            "operator": {
                                "type": "boolean",
                                "operation": "true",
                            },
                        }
                    ],
                    "combinator": "and",
                },
            },
        }
    )

    nodes.append(
        sheets_update(
            "Upsert Client Row",
            "CRM_Clients",
            {
                "Client_ID": "={{ $json.clientId }}",
                "Name": "={{ $json.name }}",
                "Company": "={{ $json.company }}",
                "Email": "={{ $json.email }}",
                "Phone": "={{ $json.phone }}",
                "Last_Contacted": "={{ new Date().toISOString() }}",
                "Ask": "={{ $json.ask }}",
                "Status": "'inbox-captured'",
                "Notes": (
                    "={{ 'score=' + $json.leadScore + "
                    "' budget=' + $json.budgetZAR + "
                    "' availability=' + $json.availability }}"
                ),
                "Run_ID": "={{ $json.runId }}",
            },
            matching_column="Email",
            position=(2200, 200),
        )
    )

    nodes.append(
        gmail_send(
            "Send Acknowledgement",
            to_expr="={{ $json.email }}",
            subject_expr=(
                "='Got it — ' + ($json.company || $json.name) + ' | next step'"
            ),
            body_expr="={{ $json.acknowledgementBody }}",
            position=(2440, 200),
        )
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Skip Action",
            "type": "n8n-nodes-base.noOp",
            "typeVersion": 1,
            "position": [2200, 420],
            "parameters": {},
        }
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Merge End",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [2680, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(audit_log("DEMO-09", position=(2920, 300)))

    return nodes


def build_connections(_nodes: list[dict]) -> dict:
    return {
        "Gmail Inbox Trigger": {
            "main": [[{"node": "Demo Config", "type": "main", "index": 0}]]
        },
        "Webhook Trigger": {
            "main": [[{"node": "Demo Config", "type": "main", "index": 0}]]
        },
        "Demo Config": {
            "main": [[{"node": "DEMO_MODE Switch", "type": "main", "index": 0}]]
        },
        "DEMO_MODE Switch": {
            "main": [
                [{"node": "Load Fixture Email", "type": "main", "index": 0}],
                [{"node": "Normalise Gmail Payload", "type": "main", "index": 0}],
            ]
        },
        "Load Fixture Email": {
            "main": [[{"node": "Merge Email Sources", "type": "main", "index": 0}]]
        },
        "Normalise Gmail Payload": {
            "main": [[{"node": "Merge Email Sources", "type": "main", "index": 1}]]
        },
        "Merge Email Sources": {
            "main": [[{"node": "Build Extract Prompt", "type": "main", "index": 0}]]
        },
        "Build Extract Prompt": {
            "main": [[{"node": "AI Extract CRM Fields", "type": "main", "index": 0}]]
        },
        "AI Extract CRM Fields": {
            "main": [[{"node": "Parse Extracted Fields", "type": "main", "index": 0}]]
        },
        "Parse Extracted Fields": {
            "main": [[{"node": "Has Actionable Fields?", "type": "main", "index": 0}]]
        },
        "Has Actionable Fields?": {
            "main": [
                [{"node": "Upsert Client Row", "type": "main", "index": 0}],
                [{"node": "Skip Action", "type": "main", "index": 0}],
            ]
        },
        "Upsert Client Row": {
            "main": [[{"node": "Send Acknowledgement", "type": "main", "index": 0}]]
        },
        "Send Acknowledgement": {
            "main": [[{"node": "Merge End", "type": "main", "index": 0}]]
        },
        "Skip Action": {
            "main": [[{"node": "Merge End", "type": "main", "index": 1}]]
        },
        "Merge End": {
            "main": [[{"node": "Audit Log", "type": "main", "index": 0}]]
        },
    }


def build_workflow() -> dict:
    nodes = build_nodes()
    connections = build_connections(nodes)
    return build_workflow_envelope(WORKFLOW_NAME, nodes, connections)


if __name__ == "__main__":
    run_cli(DemoSpec(WORKFLOW_NAME, WORKFLOW_FILENAME, build_workflow))

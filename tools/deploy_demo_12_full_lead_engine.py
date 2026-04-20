"""DEMO-12: Full Lead Handling Engine (Part 2).

Upgraded version of DEMO-11. Same entry point (webform), but now with
every production guardrail you would actually want live:

    1. Email format validation
    2. Dedup check against CRM_Clients (upsert not insert)
    3. AI enrichment (company + intent scoring)
    4. Personalised reply
    5. Slack ping to sales
    6. 24-hour follow-up row auto-scheduled
    7. Full audit trail

Flow::

    Webhook Trigger
        -> Demo Config (fixture payload)
        -> DEMO_MODE Switch
            -> demo : Load Fixture Lead
            -> live : Validate + Normalise Input
        -> Merge
        -> Validate Email (IF: regex)
            -> invalid: Log + Respond 400
            -> valid  : continue
        -> Read CRM_Clients (Sheets read)
        -> Dedup + Score + Build Reply Prompt (Code)
        -> AI Enrich + Draft Reply (Sonnet)
        -> Parse
        -> Upsert CRM_Clients  | Send Gmail Reply
            -> Slack Ping Sales
            -> Schedule 24h Follow-Up (Follow_Ups append)
            -> Audit + Respond
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
    sheets_read,
    sheets_update,
    slack_notify,
    uid,
    webhook_trigger,
)

WORKFLOW_NAME = "DEMO-12 Full Lead Handling Engine"
WORKFLOW_FILENAME = "demo12_full_lead_engine.json"
WEBHOOK_PATH = "demo12-full-lead-engine"


FIXTURE_LEAD = {
    "name": "Lerato Mofokeng",
    "email": "lerato@riverviewlaw.co.za",
    "company": "Riverview Law Chambers",
    "phone": "+27 82 333 0199",
    "source": "landing-page",
    "message": (
        "We're a 12-attorney boutique firm looking to automate client intake, "
        "case-file summaries, and billing reminders. Read your LinkedIn post "
        "on GPTs for legal — would love a 20-min call to compare notes on "
        "security/POPIA considerations. Budget is R30-50k/mo for the first "
        "engagement."
    ),
}


ENRICH_PROMPT = r"""You are a senior SDR for AnyVision Media. For the lead
below, do three things and return STRICT JSON (no fences):

  {
    "industry": "single-line industry classification",
    "companySizeGuess": "SMB|mid-market|enterprise (best guess)",
    "leadScore": 1-10,
    "intent": "hot|question|generic",
    "subjectLine": "...",
    "replyHtml": "<p>...</p> (3-4 sentences, personalised, offer a specific 20-min slot, sign as Ian)"
  }

Inputs include an ``existingClient`` flag. If existingClient=true, the reply
should reference prior context gently; if false, introduce yourself briefly.

Lead:
""" + "${JSON.stringify($json, null, 2)}"


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    nodes.append(webhook_trigger(WEBHOOK_PATH, position=(200, 300)))
    nodes.append(
        set_demo_config(fixture_payload=FIXTURE_LEAD, position=(420, 300))
    )
    nodes.append(demo_mode_switch(position=(640, 300)))

    nodes.append(
        code_node(
            "Load Fixture Lead",
            """const cfg = $('Demo Config').first().json;
const l = JSON.parse(cfg.fixtureData);
return [{ json: { ...l, runId: cfg.runId, source: l.source || 'fixture' } }];""",
            position=(860, 200),
        )
    )

    nodes.append(
        code_node(
            "Validate + Normalise Input",
            """const cfg = $('Demo Config').first().json;
const body = $json.body || $json;
const email = String(body.email || '').trim().toLowerCase();
const emailOk = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email);
return [{
  json: {
    name: body.name || 'there',
    email,
    company: body.company || '',
    phone: body.phone || '',
    source: body.source || 'webhook',
    message: body.message || '',
    runId: cfg.runId,
    emailOk,
  }
}];""",
            position=(860, 420),
        )
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Merge Sources",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [1080, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Validate Email",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [1300, 300],
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
                            "leftValue": (
                                "={{ $json.emailOk !== false "
                                "&& /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test($json.email || '') }}"
                            ),
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
        sheets_read(
            "Read CRM_Clients",
            "CRM_Clients",
            position=(1520, 200),
        )
    )

    nodes.append(
        code_node(
            "Dedup + Build Prompt",
            f"""const existing = $input.all().map(i => i.json);
const lead = $('Validate Email').first().json;
const match = existing.find(r => (r.Email || '').toLowerCase() === lead.email);
const existingClient = Boolean(match);
const prompt = `{ENRICH_PROMPT}`;
return [{{
  json: {{
    ...lead,
    existingClient,
    existingNotes: match ? match.Notes : '',
    clientId: match?.Client_ID || `CLT-${{Date.now()}}-${{Math.floor(Math.random() * 1000)}}`,
    prompt,
  }}
}}];
""",
            position=(1740, 200),
        )
    )

    nodes.append(
        openrouter_call(
            "AI Enrich + Draft Reply",
            "$json.prompt",
            model=MODEL_SONNET,
            temperature=0.4,
            max_tokens=900,
            position=(1960, 200),
        )
    )

    nodes.append(
        code_node(
            "Parse Enrichment",
            """const src = $('Dedup + Build Prompt').first().json;
const resp = $input.first().json || {};
const raw = resp.choices?.[0]?.message?.content || '';
const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
let parsed = {};
try { parsed = cleaned ? JSON.parse(cleaned) : {}; } catch (e) {}

const score = Number(parsed.leadScore) || 5;

return [{
  json: {
    ...src,
    industry: parsed.industry || 'unknown',
    companySizeGuess: parsed.companySizeGuess || 'SMB',
    leadScore: score,
    intent: parsed.intent || 'question',
    hot: score >= 7,
    subjectLine: parsed.subjectLine || `Re: ${src.company || src.name}`,
    replyHtml: parsed.replyHtml || `<p>Thanks for reaching out — I will follow up within one business day.</p><p>Ian</p>`,
  }
}];""",
            position=(2200, 200),
        )
    )

    nodes.append(
        sheets_update(
            "Upsert CRM Client",
            "CRM_Clients",
            {
                "Client_ID": "={{ $json.clientId }}",
                "Name": "={{ $json.name }}",
                "Company": "={{ $json.company }}",
                "Email": "={{ $json.email }}",
                "Phone": "={{ $json.phone }}",
                "Last_Contacted": "={{ new Date().toISOString() }}",
                "Ask": "={{ ($json.message || '').slice(0, 240) }}",
                "Status": (
                    "={{ $json.hot ? 'hot-new' : ($json.existingClient ? 'existing-touch' : 'new') }}"
                ),
                "Notes": (
                    "={{ 'industry=' + $json.industry + "
                    "' size=' + $json.companySizeGuess + "
                    "' score=' + $json.leadScore + "
                    "' intent=' + $json.intent }}"
                ),
                "Run_ID": "={{ $json.runId }}",
            },
            matching_column="Email",
            position=(2440, 100),
        )
    )

    nodes.append(
        gmail_send(
            "Send Reply",
            to_expr="={{ $json.email }}",
            subject_expr="={{ $json.subjectLine }}",
            body_expr="={{ $json.replyHtml }}",
            position=(2440, 260),
        )
    )

    nodes.append(
        slack_notify(
            "Slack Ping Sales",
            (
                "'New lead ' + ($json.hot ? ':fire: ' : '') + "
                "'(' + $json.leadScore + '/10, ' + $json.intent + ')\\n' + "
                "'From: ' + $json.name + ' <' + $json.email + '>\\n' + "
                "'Company: ' + ($json.company || '-') + "
                "'\\nAsk: ' + ($json.message || '').slice(0, 240)"
            ),
            position=(2440, 420),
        )
    )

    nodes.append(
        sheets_append(
            "Schedule 24h Follow-Up",
            "Follow_Ups",
            {
                "Follow_Up_ID": "={{ 'FU-' + $json.clientId }}",
                "Related_Record": "={{ $json.clientId }}",
                "Contact": "={{ $json.email }}",
                "Scheduled_For": (
                    "={{ new Date(Date.now() + 1000*60*60*24)"
                    ".toISOString().slice(0, 10) }}"
                ),
                "Type": "'lead-nurture'",
                "Status": "'due'",
                "Last_Action": "'auto-reply-sent'",
                "Notes": (
                    "={{ 'Check in on ' + $json.company + "
                    "' - score ' + $json.leadScore }}"
                ),
            },
            position=(2680, 260),
        )
    )

    # Invalid-email branch
    nodes.append(
        code_node(
            "Flag Invalid",
            """return [{
  json: {
    status: 'invalid_email',
    runId: $('Demo Config').first().json.runId,
    reason: 'email failed regex validation',
    email: $json.email || '',
  }
}];""",
            position=(1520, 420),
        )
    )

    nodes.append(
        sheets_append(
            "Log Invalid Lead",
            "Leads_Log",
            {
                "Timestamp": "={{ new Date().toISOString() }}",
                "Name": "={{ $json.name || '' }}",
                "Email": "={{ $json.email || '' }}",
                "Source": "'webhook'",
                "Intent": "'invalid-email'",
                "AI_Reply_Preview": "''",
                "Status": "'rejected'",
                "Run_ID": "={{ $json.runId }}",
                "Workflow": "'DEMO-12'",
            },
            position=(1740, 420),
        )
    )

    # Final merge
    nodes.append(
        {
            "id": uid(),
            "name": "Merge End",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [2920, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(audit_log("DEMO-12", position=(3160, 300)))

    nodes.append(
        respond_to_webhook(
            body_expr=(
                "JSON.stringify({"
                "runId: $('Demo Config').first().json.runId, "
                "status: $json.status || 'processed' "
                "})"
            ),
            position=(3400, 300),
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
                [{"node": "Load Fixture Lead", "type": "main", "index": 0}],
                [{"node": "Validate + Normalise Input", "type": "main", "index": 0}],
            ]
        },
        "Load Fixture Lead": {
            "main": [[{"node": "Merge Sources", "type": "main", "index": 0}]]
        },
        "Validate + Normalise Input": {
            "main": [[{"node": "Merge Sources", "type": "main", "index": 1}]]
        },
        "Merge Sources": {
            "main": [[{"node": "Validate Email", "type": "main", "index": 0}]]
        },
        "Validate Email": {
            "main": [
                [{"node": "Read CRM_Clients", "type": "main", "index": 0}],
                [{"node": "Flag Invalid", "type": "main", "index": 0}],
            ]
        },
        "Read CRM_Clients": {
            "main": [[{"node": "Dedup + Build Prompt", "type": "main", "index": 0}]]
        },
        "Dedup + Build Prompt": {
            "main": [[{"node": "AI Enrich + Draft Reply", "type": "main", "index": 0}]]
        },
        "AI Enrich + Draft Reply": {
            "main": [[{"node": "Parse Enrichment", "type": "main", "index": 0}]]
        },
        "Parse Enrichment": {
            "main": [
                [
                    {"node": "Upsert CRM Client", "type": "main", "index": 0},
                    {"node": "Send Reply", "type": "main", "index": 0},
                    {"node": "Slack Ping Sales", "type": "main", "index": 0},
                ]
            ]
        },
        "Upsert CRM Client": {
            "main": [[{"node": "Schedule 24h Follow-Up", "type": "main", "index": 0}]]
        },
        "Send Reply": {
            "main": [[{"node": "Schedule 24h Follow-Up", "type": "main", "index": 0}]]
        },
        "Slack Ping Sales": {
            "main": [[{"node": "Schedule 24h Follow-Up", "type": "main", "index": 0}]]
        },
        "Schedule 24h Follow-Up": {
            "main": [[{"node": "Merge End", "type": "main", "index": 0}]]
        },
        "Flag Invalid": {
            "main": [[{"node": "Log Invalid Lead", "type": "main", "index": 0}]]
        },
        "Log Invalid Lead": {
            "main": [[{"node": "Merge End", "type": "main", "index": 1}]]
        },
        "Merge End": {
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

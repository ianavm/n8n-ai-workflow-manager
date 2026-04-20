"""DEMO-05: Instant Lead Reply Engine.

Webform -> AI intent classification -> personalised reply in under 20s.

Flow::

    Webhook Trigger
        -> Demo Config (inline fixture payload + run ID)
        -> DEMO_MODE Switch
            -> demo  : Load Fixture Lead
            -> live  : Pass Through (uses webhook body)
        -> Merge
        -> Build Classification Prompt
        -> AI Classify & Draft (Claude Sonnet via OpenRouter)
        -> Parse AI Output
        -> Intent Router (Switch: hot / question / spam / generic)
        -> Send Reply (Gmail) for hot + question
        -> Log to Leads_Log (Google Sheets)
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
    uid,
    webhook_trigger,
)

WORKFLOW_NAME = "DEMO-05 Instant Lead Reply Engine"
WORKFLOW_FILENAME = "demo05_lead_reply.json"
WEBHOOK_PATH = "demo05-lead-reply"


FIXTURE_LEAD = {
    "name": "Kagiso Mokoena",
    "email": "kagiso@fourwaysfitness.co.za",
    "company": "Fourways Fitness",
    "phone": "+27 72 555 0199",
    "source": "website-form",
    "message": (
        "Hi Ian, saw your LinkedIn post about AI automation. We're a 4-studio "
        "gym running classes across Joburg, currently drowning in admin — "
        "member follow-ups, class bookings, WhatsApp enquiries. Would love "
        "a demo of what's possible. Any chance of a call this week?"
    ),
}


BRAND_CONTEXT = (
    "AnyVision Media — Johannesburg AI automation agency for SA SMEs. "
    "Typical package R5k-R15k/mo. Founder: Ian Immelman."
)


CLASSIFY_PROMPT = f"""You are the lead-qualifier for ${{cfg.brand}}.

Classify the inbound lead on two axes:
  1. intent: one of [hot, question, spam, generic]
     - hot       = explicit buying signal, demo request, budget or timeline
     - question  = curious, asking general info, objection, comparison
     - spam      = bot/random/crypto/unrelated
     - generic   = fan message, compliment, no ask
  2. urgency: low | medium | high

For intent = hot OR question, draft a short personalised reply (3 short
sentences, HTML allowed, no preamble). Sign off as Ian.
For spam or generic, suggestedReply = null.

Return STRICT JSON (no prose, no markdown fences):
{{{{
  \"intent\": \"...\",
  \"urgency\": \"...\",
  \"reasoning\": \"one sentence\",
  \"suggestedReply\": \"...\" | null,
  \"subjectLine\": \"...\"
}}}}

Brand: ${{cfg.brand}}
Lead:
  Name: ${{lead.name}}
  Email: ${{lead.email}}
  Company: ${{lead.company}}
  Source: ${{lead.source}}
  Message: ${{lead.message}}
"""


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    nodes.append(webhook_trigger(WEBHOOK_PATH, position=(200, 300)))

    nodes.append(
        set_demo_config(
            fixture_payload=FIXTURE_LEAD,
            extras={"brand": BRAND_CONTEXT},
            position=(420, 300),
        )
    )

    nodes.append(demo_mode_switch(position=(640, 300)))

    nodes.append(
        code_node(
            "Load Fixture Lead",
            """const cfg = $('Demo Config').first().json;
const lead = JSON.parse(cfg.fixtureData);
return [{ json: { ...lead, runId: cfg.runId, source: lead.source || 'fixture' } }];
""",
            position=(860, 200),
        )
    )

    nodes.append(
        code_node(
            "Normalise Live Lead",
            """const cfg = $('Demo Config').first().json;
const body = $json.body || $json;
return [{
  json: {
    name: body.name || 'there',
    email: body.email || '',
    company: body.company || '',
    phone: body.phone || '',
    source: body.source || 'webhook',
    message: body.message || '',
    runId: cfg.runId,
  }
}];""",
            position=(860, 420),
        )
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Merge Lead Sources",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [1080, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(
        code_node(
            "Build Classification Prompt",
            f"""const cfg = $('Demo Config').first().json;
const lead = $input.first().json;
const prompt = `{CLASSIFY_PROMPT}`;
return [{{ json: {{ ...lead, prompt }} }}];
""",
            position=(1300, 300),
        )
    )

    nodes.append(
        openrouter_call(
            "AI Classify & Draft",
            "$json.prompt",
            model=MODEL_SONNET,
            temperature=0.4,
            max_tokens=700,
            position=(1520, 300),
        )
    )

    nodes.append(
        code_node(
            "Parse AI Output",
            """const lead = $('Build Classification Prompt').first().json;
const resp = $input.first().json || {};
let raw = '';
try { raw = resp.choices?.[0]?.message?.content || ''; } catch (e) { raw = ''; }
const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
let parsed = {};
try { parsed = cleaned ? JSON.parse(cleaned) : {}; } catch (e) { parsed = {}; }
const intent = (parsed.intent || '').toLowerCase() || 'generic';
return [{
  json: {
    ...lead,
    intent,
    urgency: (parsed.urgency || 'low').toLowerCase(),
    reasoning: parsed.reasoning || 'ai-fallback',
    suggestedReply: parsed.suggestedReply || null,
    subjectLine: parsed.subjectLine || `Re: ${lead.company || 'your enquiry'}`,
    shouldReply: ['hot', 'question'].includes(intent),
  }
}];""",
            position=(1740, 300),
        )
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Intent Router",
            "type": "n8n-nodes-base.switch",
            "typeVersion": 3.2,
            "position": [1960, 300],
            "parameters": {
                "rules": {
                    "values": [
                        {
                            "conditions": {
                                "combinator": "and",
                                "conditions": [
                                    {
                                        "leftValue": "={{ $json.shouldReply }}",
                                        "rightValue": True,
                                        "operator": {
                                            "type": "boolean",
                                            "operation": "true",
                                        },
                                    }
                                ],
                            },
                            "outputKey": "reply",
                        },
                        {
                            "conditions": {
                                "combinator": "and",
                                "conditions": [
                                    {
                                        "leftValue": "={{ $json.shouldReply }}",
                                        "rightValue": True,
                                        "operator": {
                                            "type": "boolean",
                                            "operation": "false",
                                        },
                                    }
                                ],
                            },
                            "outputKey": "noReply",
                        },
                    ]
                },
                "options": {"fallbackOutput": 1},
            },
        }
    )

    nodes.append(
        gmail_send(
            "Send Reply",
            to_expr="={{ $json.email }}",
            subject_expr="={{ $json.subjectLine }}",
            body_expr="={{ $json.suggestedReply }}",
            position=(2200, 200),
        )
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Skip Reply",
            "type": "n8n-nodes-base.noOp",
            "typeVersion": 1,
            "position": [2200, 400],
            "parameters": {},
        }
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Merge Branches",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [2440, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(
        sheets_append(
            "Log Lead",
            "Leads_Log",
            {
                "Timestamp": "={{ new Date().toISOString() }}",
                "Name": "={{ $json.name }}",
                "Email": "={{ $json.email }}",
                "Source": "={{ $json.source }}",
                "Intent": "={{ $json.intent + '/' + $json.urgency }}",
                "AI_Reply_Preview": (
                    "={{ ($json.suggestedReply || '(no reply drafted)').slice(0, 240) }}"
                ),
                "Status": (
                    "={{ $json.shouldReply ? 'replied' : 'logged-only' }}"
                ),
                "Run_ID": "={{ $json.runId }}",
                "Workflow": "'DEMO-05'",
            },
            position=(2680, 300),
        )
    )

    nodes.append(audit_log("DEMO-05", position=(2920, 300)))
    nodes.append(
        respond_to_webhook(
            body_expr=(
                "JSON.stringify({"
                "runId: $('Demo Config').first().json.runId, "
                "intent: $('Parse AI Output').first().json.intent, "
                "urgency: $('Parse AI Output').first().json.urgency, "
                "replied: $('Parse AI Output').first().json.shouldReply, "
                "reply: $('Parse AI Output').first().json.suggestedReply "
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
                [{"node": "Load Fixture Lead", "type": "main", "index": 0}],
                [{"node": "Normalise Live Lead", "type": "main", "index": 0}],
            ]
        },
        "Load Fixture Lead": {
            "main": [[{"node": "Merge Lead Sources", "type": "main", "index": 0}]]
        },
        "Normalise Live Lead": {
            "main": [[{"node": "Merge Lead Sources", "type": "main", "index": 1}]]
        },
        "Merge Lead Sources": {
            "main": [
                [{"node": "Build Classification Prompt", "type": "main", "index": 0}]
            ]
        },
        "Build Classification Prompt": {
            "main": [[{"node": "AI Classify & Draft", "type": "main", "index": 0}]]
        },
        "AI Classify & Draft": {
            "main": [[{"node": "Parse AI Output", "type": "main", "index": 0}]]
        },
        "Parse AI Output": {
            "main": [[{"node": "Intent Router", "type": "main", "index": 0}]]
        },
        "Intent Router": {
            "main": [
                [{"node": "Send Reply", "type": "main", "index": 0}],
                [{"node": "Skip Reply", "type": "main", "index": 0}],
            ]
        },
        "Send Reply": {
            "main": [[{"node": "Merge Branches", "type": "main", "index": 0}]]
        },
        "Skip Reply": {
            "main": [[{"node": "Merge Branches", "type": "main", "index": 1}]]
        },
        "Merge Branches": {
            "main": [[{"node": "Log Lead", "type": "main", "index": 0}]]
        },
        "Log Lead": {
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

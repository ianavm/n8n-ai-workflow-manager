"""DEMO-06: Smart Lead Reply Bot (Inbox).

Triggered by new Gmail messages on a ``leads`` label. Reads the
incoming thread (including context), drafts a thread-aware reply, and
SAVES IT AS A GMAIL DRAFT (not send). The human reviews, tweaks, and
clicks send — automation takes care of the hard 80%, the human keeps
the last mile.

Differs from DEMO-05 (webform-driven, auto-send) by trigger source and
send behaviour. Separate demo because the pitch is different: "you
never stare at a blank reply again" vs "your website replies to leads
instantly".

Flow::

    Gmail Trigger (label:leads)
        -> Demo Config (fixture thread JSON + run id)
        -> DEMO_MODE Switch
            -> demo : Load Fixture Thread (Code)
            -> live : Extract Thread Meta (Code over Gmail payload)
        -> Merge
        -> Build Draft Prompt
        -> AI Draft Reply (Sonnet)
        -> Parse Draft
        -> Gmail Create Draft (in-thread)
        -> Log to Gmail_Drafts_Log + Leads_Log
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
    gmail_draft,
    gmail_trigger,
    openrouter_call,
    run_cli,
    set_demo_config,
    sheets_append,
    uid,
    webhook_trigger,
)

WORKFLOW_NAME = "DEMO-06 Smart Lead Reply Bot (Inbox)"
WORKFLOW_FILENAME = "demo06_inbox_reply_bot.json"


FIXTURE_THREAD = {
    "threadId": "thread-fx-06-001",
    "messageId": "msg-fx-06-002",
    "from": {"name": "Thandi Dlamini", "email": "thandi@greenleaf.co.za"},
    "subject": "Re: Interested in automation — quick question",
    "priorMessages": [
        {
            "from": "ian@anyvisionmedia.com",
            "body": (
                "Hi Thandi — great chatting yesterday. Sending through a short "
                "note on how we'd approach automating your customer follow-ups. "
                "Let me know what you think."
            ),
            "date": "2026-04-18T10:12:00Z",
        }
    ],
    "latestMessage": {
        "body": (
            "Hi Ian, thanks for the note. Two quick questions before we book a "
            "call: (1) do you integrate with Shopify, and (2) what does pricing "
            "look like for a team of 6? Aiming to decide by Friday."
        ),
        "date": "2026-04-20T08:43:00Z",
    },
}


DRAFT_PROMPT = r"""You are Ian Immelman, founder of AnyVision Media (AI automation
agency, Johannesburg). You are drafting a reply to the LATEST message in the
thread below. Keep your voice: direct, warm, specific, no filler, no emoji.

Guidance:
- Answer their exact questions. If you don't know a number, commit to sending
  it in the next reply.
- Always suggest a next step (15-min call, link to a one-pager, or a specific
  timeline).
- 3-5 sentences max. HTML allowed.
- Output STRICT JSON only, no markdown fences:
  { "draftBody": "...", "draftSubject": "Re: ..." }

Thread:
""" + "${JSON.stringify($json, null, 2)}"


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    # Primary trigger: Gmail polling. A secondary webhook trigger is included
    # so the demo can be fired on-demand without waiting for a real email.
    nodes.append(
        gmail_trigger(
            name="Gmail Trigger (leads label)",
            label_ids=["INBOX"],
            position=(200, 200),
        )
    )
    nodes.append(
        webhook_trigger("demo06-inbox-reply-bot", position=(200, 420))
    )

    nodes.append(
        set_demo_config(
            fixture_payload=FIXTURE_THREAD,
            position=(420, 300),
        )
    )

    nodes.append(demo_mode_switch(position=(640, 300)))

    nodes.append(
        code_node(
            "Load Fixture Thread",
            """const cfg = $('Demo Config').first().json;
const t = JSON.parse(cfg.fixtureData);
return [{ json: { ...t, runId: cfg.runId, source: 'fixture' } }];
""",
            position=(860, 200),
        )
    )

    nodes.append(
        code_node(
            "Extract Live Thread",
            """const cfg = $('Demo Config').first().json;
const raw = $json;
const from = raw.from || raw.payload?.headers?.find(h => h.name === 'From')?.value || 'unknown';
const subject = raw.subject || raw.payload?.headers?.find(h => h.name === 'Subject')?.value || '(no subject)';
const body = raw.snippet || raw.textPlain || raw.html || raw.body || '';
return [{
  json: {
    threadId: raw.threadId || raw.id,
    messageId: raw.id,
    from: { name: String(from).split('<')[0].trim(), email: String(from).match(/<([^>]+)>/)?.[1] || from },
    subject,
    latestMessage: { body, date: new Date().toISOString() },
    priorMessages: [],
    runId: cfg.runId,
    source: 'gmail',
  }
}];""",
            position=(860, 420),
        )
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Merge Thread Sources",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [1080, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(
        code_node(
            "Build Draft Prompt",
            f"""const t = $input.first().json;
const prompt = `{DRAFT_PROMPT}`;
return [{{ json: {{ ...t, prompt }} }}];
""",
            position=(1300, 300),
        )
    )

    nodes.append(
        openrouter_call(
            "AI Draft Reply",
            "$json.prompt",
            model=MODEL_SONNET,
            temperature=0.5,
            max_tokens=650,
            position=(1520, 300),
        )
    )

    nodes.append(
        code_node(
            "Parse Draft",
            """const t = $('Build Draft Prompt').first().json;
const resp = $input.first().json || {};
const raw = resp.choices?.[0]?.message?.content || '';
const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
let parsed = { draftBody: null, draftSubject: null };
try { parsed = cleaned ? JSON.parse(cleaned) : parsed; } catch (e) {}
const fallbackBody = (t.latestMessage?.body || '').slice(0, 160);
return [{
  json: {
    ...t,
    draftBody: parsed.draftBody || `Thanks for the note — I will come back to you within the next business day.\\n\\n(Auto-draft fallback based on: ${fallbackBody})`,
    draftSubject: parsed.draftSubject || `Re: ${t.subject || 'your message'}`,
  }
}];""",
            position=(1740, 300),
        )
    )

    nodes.append(
        gmail_draft(
            "Save Draft in Thread",
            to_expr="={{ $json.from.email }}",
            subject_expr="={{ $json.draftSubject }}",
            body_expr="={{ $json.draftBody }}",
            thread_id_expr="={{ $json.threadId }}",
            position=(1960, 260),
        )
    )

    nodes.append(
        sheets_append(
            "Log Draft",
            "Gmail_Drafts_Log",
            {
                "Timestamp": "={{ new Date().toISOString() }}",
                "Thread_ID": "={{ $json.threadId }}",
                "From": "={{ $json.from.email }}",
                "Subject": "={{ $json.draftSubject }}",
                "Draft_Preview": "={{ ($json.draftBody || '').slice(0, 240) }}",
                "Approved": "'pending-review'",
                "Run_ID": "={{ $json.runId }}",
            },
            position=(2200, 260),
        )
    )

    nodes.append(
        sheets_append(
            "Log Lead",
            "Leads_Log",
            {
                "Timestamp": "={{ new Date().toISOString() }}",
                "Name": "={{ $json.from.name }}",
                "Email": "={{ $json.from.email }}",
                "Source": "'gmail-inbox'",
                "Intent": "'inbox-reply'",
                "AI_Reply_Preview": "={{ ($json.draftBody || '').slice(0, 240) }}",
                "Status": "'draft-created'",
                "Run_ID": "={{ $json.runId }}",
                "Workflow": "'DEMO-06'",
            },
            position=(2440, 260),
        )
    )

    nodes.append(audit_log("DEMO-06", position=(2680, 260)))

    return nodes


def build_connections(_nodes: list[dict]) -> dict:
    return {
        "Gmail Trigger (leads label)": {
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
                [{"node": "Load Fixture Thread", "type": "main", "index": 0}],
                [{"node": "Extract Live Thread", "type": "main", "index": 0}],
            ]
        },
        "Load Fixture Thread": {
            "main": [[{"node": "Merge Thread Sources", "type": "main", "index": 0}]]
        },
        "Extract Live Thread": {
            "main": [[{"node": "Merge Thread Sources", "type": "main", "index": 1}]]
        },
        "Merge Thread Sources": {
            "main": [[{"node": "Build Draft Prompt", "type": "main", "index": 0}]]
        },
        "Build Draft Prompt": {
            "main": [[{"node": "AI Draft Reply", "type": "main", "index": 0}]]
        },
        "AI Draft Reply": {
            "main": [[{"node": "Parse Draft", "type": "main", "index": 0}]]
        },
        "Parse Draft": {
            "main": [[{"node": "Save Draft in Thread", "type": "main", "index": 0}]]
        },
        "Save Draft in Thread": {
            "main": [[{"node": "Log Draft", "type": "main", "index": 0}]]
        },
        "Log Draft": {
            "main": [[{"node": "Log Lead", "type": "main", "index": 0}]]
        },
        "Log Lead": {
            "main": [[{"node": "Audit Log", "type": "main", "index": 0}]]
        },
    }


def build_workflow() -> dict:
    nodes = build_nodes()
    connections = build_connections(nodes)
    return build_workflow_envelope(WORKFLOW_NAME, nodes, connections)


if __name__ == "__main__":
    run_cli(DemoSpec(WORKFLOW_NAME, WORKFLOW_FILENAME, build_workflow))

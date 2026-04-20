"""DEMO-10: Logistics Quote Request Handler.

Niche-specific demo for warehousing / 3PL / freight SMBs. Inbound quote
form fields -> AI drafts a quote email with an estimate -> Gmail send ->
Sheet log -> auto-created 72h follow-up reminder row.

Flow::

    Webhook Trigger (origin, destination, weight_kg, pallet_count, ...)
        -> Demo Config (fixture quote request)
        -> DEMO_MODE Switch
            -> demo : Load Fixture Quote
            -> live : Normalise Quote Fields
        -> Merge
        -> Estimate Helper (Code: seed R/km baseline for AI to refine)
        -> AI Draft Quote (Sonnet)
        -> Parse Quote
        -> Send Quote Email (Gmail)
        -> Log Quotes_Log + Create Follow_Up Reminder (parallel)
        -> Merge + Audit + Respond
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

WORKFLOW_NAME = "DEMO-10 Logistics Quote Request Handler"
WORKFLOW_FILENAME = "demo10_logistics_quotes.json"
WEBHOOK_PATH = "demo10-logistics-quote"


FIXTURE_QUOTE = {
    "company": "Karoo Craft Beverages",
    "contactName": "Pieter de Villiers",
    "contactEmail": "pieter@karoocraft.co.za",
    "contactPhone": "+27 82 555 0132",
    "origin": "Port Elizabeth, EC",
    "destination": "Midrand, GP",
    "weightKg": 4200,
    "palletCount": 6,
    "cargoType": "Ambient beverages (glass bottles)",
    "pickupDate": "2026-04-25",
    "notes": "Prefer arrival before 08:00 on 25 April. Forklift on site both ends.",
}


QUOTE_PROMPT = r"""You are a freight-quoting assistant for AnyVision Logistics
(demo company, South African 3PL). Produce a realistic-looking quote for the
inbound request. Output STRICT JSON ONLY (no markdown fences):

  {
    "estimateZAR": <integer, total incl. VAT>,
    "transitDays": <integer>,
    "pricingRationale": "1-sentence, shows the calc: distance, weight, pallet fuel levy",
    "quoteHtml": "<HTML email body, ~150 words, warm but professional, includes estimate, ETA, next step>",
    "subjectLine": "Quote #... -  {origin} -> {destination}",
    "quoteId": "Q-2026-XXXX"
  }

Pricing heuristics (use these as a starting point, then write the rationale):
  - Base: R18/km per pallet for ambient
  - Chilled / hazmat / glass -> +20%
  - Fuel levy: R0.60/km/pallet
  - Overnight / before-08:00 surcharge: R1 200
  - VAT 15% on top
  - Distance reference lanes:
      PE -> Midrand ~= 1 100 km
      Cape Town -> Joburg ~= 1 400 km
      Durban -> Joburg ~= 600 km

Request:
""" + "${JSON.stringify($json, null, 2)}"


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    nodes.append(webhook_trigger(WEBHOOK_PATH, position=(200, 300)))

    nodes.append(
        set_demo_config(fixture_payload=FIXTURE_QUOTE, position=(420, 300))
    )

    nodes.append(demo_mode_switch(position=(640, 300)))

    nodes.append(
        code_node(
            "Load Fixture Quote",
            """const cfg = $('Demo Config').first().json;
const q = JSON.parse(cfg.fixtureData);
return [{ json: { ...q, runId: cfg.runId, source: 'fixture' } }];
""",
            position=(860, 200),
        )
    )

    nodes.append(
        code_node(
            "Normalise Quote Fields",
            """const cfg = $('Demo Config').first().json;
const body = $json.body || $json;
return [{
  json: {
    company: body.company || '',
    contactName: body.contactName || body.name || '',
    contactEmail: body.contactEmail || body.email || '',
    contactPhone: body.contactPhone || body.phone || '',
    origin: body.origin || '',
    destination: body.destination || '',
    weightKg: Number(body.weightKg || body.weight_kg || 0),
    palletCount: Number(body.palletCount || body.pallet_count || 1),
    cargoType: body.cargoType || body.cargo_type || 'general',
    pickupDate: body.pickupDate || body.pickup_date || '',
    notes: body.notes || '',
    runId: cfg.runId,
    source: 'webhook',
  }
}];""",
            position=(860, 420),
        )
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Merge Quote Sources",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [1080, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(
        code_node(
            "Build Quote Prompt",
            f"""const q = $input.first().json;
const prompt = `{QUOTE_PROMPT}`;
return [{{ json: {{ ...q, prompt }} }}];
""",
            position=(1300, 300),
        )
    )

    nodes.append(
        openrouter_call(
            "AI Draft Quote",
            "$json.prompt",
            model=MODEL_SONNET,
            temperature=0.4,
            max_tokens=1000,
            position=(1520, 300),
        )
    )

    nodes.append(
        code_node(
            "Parse Quote",
            """const q = $('Build Quote Prompt').first().json;
const resp = $input.first().json || {};
const raw = resp.choices?.[0]?.message?.content || '';
const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
let parsed = {};
try { parsed = cleaned ? JSON.parse(cleaned) : {}; } catch (e) {}

// Safe fallback if AI fails — rough calc so the demo still produces numbers.
const baseKm = 1100;
const perPallet = 18 * baseKm + 0.60 * baseKm;
const subtotal = perPallet * (q.palletCount || 1);
const fallbackEstimate = Math.round(subtotal * 1.15);

return [{
  json: {
    ...q,
    quoteId: parsed.quoteId || `Q-2026-${Math.floor(Math.random() * 9000 + 1000)}`,
    estimateZAR: Number(parsed.estimateZAR) || fallbackEstimate,
    transitDays: Number(parsed.transitDays) || 2,
    pricingRationale: parsed.pricingRationale || `Estimated from ~${baseKm}km at standard pallet rate`,
    quoteHtml: parsed.quoteHtml || `<p>Hi ${q.contactName},</p><p>Thanks for the request. Preliminary estimate for ${q.origin} -> ${q.destination}: <b>R${fallbackEstimate.toLocaleString()}</b> (excl. any special handling). I will confirm firm pricing within 2 hours once we lock the lane.</p><p>Ian</p>`,
    subjectLine: parsed.subjectLine || `Quote ${parsed.quoteId || 'Q-2026'} - ${q.origin} -> ${q.destination}`,
  }
}];""",
            position=(1740, 300),
        )
    )

    nodes.append(
        gmail_send(
            "Send Quote Email",
            to_expr="={{ $json.contactEmail }}",
            subject_expr="={{ $json.subjectLine }}",
            body_expr="={{ $json.quoteHtml }}",
            position=(1960, 200),
        )
    )

    nodes.append(
        sheets_append(
            "Log Quote",
            "Quotes_Log",
            {
                "Quote_ID": "={{ $json.quoteId }}",
                "Company": "={{ $json.company }}",
                "Origin": "={{ $json.origin }}",
                "Destination": "={{ $json.destination }}",
                "Weight_Kg": "={{ $json.weightKg }}",
                "Pallets": "={{ $json.palletCount }}",
                "Estimate_ZAR": "={{ $json.estimateZAR }}",
                "Sent_At": "={{ new Date().toISOString() }}",
                "Status": "'sent'",
                "Contact_Email": "={{ $json.contactEmail }}",
            },
            position=(2200, 200),
        )
    )

    nodes.append(
        sheets_append(
            "Create 72h Follow-Up",
            "Follow_Ups",
            {
                "Follow_Up_ID": "={{ 'FU-' + $json.quoteId }}",
                "Related_Record": "={{ $json.quoteId }}",
                "Contact": "={{ $json.contactEmail }}",
                "Scheduled_For": (
                    "={{ new Date(Date.now() + 1000*60*60*72)"
                    ".toISOString().slice(0, 10) }}"
                ),
                "Type": "'quote-followup'",
                "Status": "'due'",
                "Last_Action": "'quote-sent'",
                "Notes": (
                    "={{ 'Check in on ' + $json.company + "
                    "' quote R' + $json.estimateZAR }}"
                ),
            },
            position=(2200, 420),
        )
    )

    nodes.append(audit_log("DEMO-10", position=(2680, 300)))

    nodes.append(
        respond_to_webhook(
            body_expr=(
                "JSON.stringify({"
                "status: 'quoted', "
                "quoteId: $('Parse Quote').first().json.quoteId, "
                "estimateZAR: $('Parse Quote').first().json.estimateZAR, "
                "transitDays: $('Parse Quote').first().json.transitDays "
                "})"
            ),
            position=(2920, 300),
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
                [{"node": "Load Fixture Quote", "type": "main", "index": 0}],
                [{"node": "Normalise Quote Fields", "type": "main", "index": 0}],
            ]
        },
        "Load Fixture Quote": {
            "main": [[{"node": "Merge Quote Sources", "type": "main", "index": 0}]]
        },
        "Normalise Quote Fields": {
            "main": [[{"node": "Merge Quote Sources", "type": "main", "index": 1}]]
        },
        "Merge Quote Sources": {
            "main": [[{"node": "Build Quote Prompt", "type": "main", "index": 0}]]
        },
        "Build Quote Prompt": {
            "main": [[{"node": "AI Draft Quote", "type": "main", "index": 0}]]
        },
        "AI Draft Quote": {
            "main": [[{"node": "Parse Quote", "type": "main", "index": 0}]]
        },
        "Parse Quote": {
            "main": [[{"node": "Send Quote Email", "type": "main", "index": 0}]]
        },
        "Send Quote Email": {
            "main": [[{"node": "Log Quote", "type": "main", "index": 0}]]
        },
        "Log Quote": {
            "main": [[{"node": "Create 72h Follow-Up", "type": "main", "index": 0}]]
        },
        "Create 72h Follow-Up": {
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

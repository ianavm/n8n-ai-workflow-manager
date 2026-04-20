# DEMO-12 — Full Lead Handling Engine (Part 2)

> **Headline result:** *"From raw lead to CRM record in 15 seconds."*

## Business problem

DEMO-11 shows the MVP. This is what production actually looks like. Every safety net a real client would demand:

1. **Email validation** (regex) — reject garbage before you burn tokens
2. **Dedup check** against `CRM_Clients` so you upsert, not duplicate
3. **AI enrichment** — industry, company size guess, lead score
4. **Personalised reply** tailored to existing vs new contact
5. **Slack ping to sales** for hot leads (score ≥ 7)
6. **Auto-scheduled 24h follow-up** in `Follow_Ups` (picked up by DEMO-08)
7. **Full audit trail** via `Audit_Log`

This is the narrative "here's what we ship for paying clients."

## Target client

Growing SMBs past the MVP stage. Anyone who's already using a basic lead workflow and needs a production upgrade. The natural upsell from DEMO-11.

## Demo scenario (2 min)

1. Show DEMO-11 first as a reminder. "Great for solo founders. But what happens when the leads keep coming?"
2. Switch to DEMO-12 in n8n. Show the visibly bigger canvas — 20 nodes grouped into clear sections: validation, dedup, AI, fan-out.
3. Fire fixture payload. Watch all 3 post-AI branches light up (CRM upsert, Gmail send, Slack ping).
4. Show the Slack channel — new lead alert.
5. Show `CRM_Clients` — row populated with industry, score, status.
6. Show `Follow_Ups` — 24h row auto-scheduled.
7. Fire a second payload with a garbage email. Watch the IF node reject it, log to `Leads_Log` with status=rejected.
8. "This is what prod looks like. 15 seconds, 3 systems updated, follow-up scheduled, and trash filtered."

## Architecture

```
Webhook Trigger
  -> Demo Config
     -> DEMO_MODE Switch -> Load Fixture / Validate + Normalise
     -> Merge Sources
     -> Validate Email (IF regex)
        -> valid:
           Read CRM_Clients (Sheets read)
           -> Dedup + Build Prompt (Code)
           -> AI Enrich + Draft Reply (Sonnet, 0.4 temp)
           -> Parse Enrichment
           -> [fan out in parallel]
              Upsert CRM Client (Sheets appendOrUpdate, matchingColumns=Email)
              Send Reply (Gmail)
              Slack Ping Sales
           -> Schedule 24h Follow-Up (Follow_Ups append)
        -> invalid:
           Flag Invalid -> Log Invalid Lead (Leads_Log status=rejected)
     -> Merge End
     -> Audit Log
     -> Respond
```

Nodes: **20**. Intentional — enough complexity to show real production structure without becoming spaghetti.

## Demo narration (beats)

1. **0:00** "DEMO-11 is the MVP. This is the production version."
2. **0:10** Pan across the canvas — point to the validation IF, the CRM dedup, the three parallel branches.
3. **0:30** Fire hot-lead fixture. All 3 branches fire simultaneously. Narrate them: "Gmail, CRM, Slack."
4. **1:00** Fire invalid-email payload. "Rejected before burning a token."
5. **1:30** "This is the baseline for every serious lead system. 20 nodes, 15 seconds, zero manual work."

### Best opening shot
Pan across the full canvas from left to right. The three parallel branches all highlighted.

### Before-vs-After angle
- **Before:** Lead gets lost between inbox, CRM, and team chat. Nobody owns follow-up.
- **After:** All 3 systems updated simultaneously. Sales sees it instantly. Follow-up in the diary before lunch.

## Credentials checklist

| Layer | Demo | Production |
|---|---|---|
| Gmail OAuth | shared | client OAuth |
| Google Sheets | demo workbook | client workbook (Sheet + tab names must match) |
| OpenRouter | shared | per-client budget |
| Slack | shared webhook | client workspace webhook |

## Example fixture input

```json
{
  "demoMode": "1"
}
```

Yields (after AI pass):

```json
{
  "name": "Lerato Mofokeng",
  "company": "Riverview Law Chambers",
  "email": "lerato@riverviewlaw.co.za",
  "industry": "Legal services",
  "companySizeGuess": "SMB",
  "leadScore": 8,
  "intent": "hot",
  "clientId": "CLT-17450...",
  "existingClient": false,
  "subjectLine": "Re: Riverview Law Chambers — automation + POPIA",
  "replyHtml": "<p>Lerato — interesting combo, thanks for reaching out. We have 2 other firm clients running intake + billing automations, both POPIA-audited. Tuesday 14:00 for a 20-min call?</p><p>Ian</p>"
}
```

## Example parallel outputs

- `CRM_Clients` row: Client_ID, Name, Company, Email, Phone, Last_Contacted, Ask, Status=hot-new, Notes=industry=Legal size=SMB score=8 intent=hot
- Gmail: reply email sent
- Slack: `New lead :fire: (8/10, hot) From: Lerato Mofokeng <lerato@...>`
- `Follow_Ups`: `FU-CLT-17450...`, scheduled for tomorrow, type=lead-nurture

## Error handling

- Invalid email -> IF-node rejection + `Leads_Log` row with status=rejected. No tokens burned, no follow-up scheduled.
- Sheet read fails -> Dedup step falls back to `existingClient=false`. Upsert still works (insert path).
- AI returns bad JSON -> safe fallback reply and score=5.
- Any branch of the 3-way fan-out fails -> others still complete (onError=continueRegularOutput on Sheets and Gmail).

## Upsell path

- Add Calendly hot-lead auto-booking link in the reply HTML
- Tie scoring to downstream routing: score ≥ 9 skips nurture and goes straight to founder's calendar
- Reply-detection loop — mark `Follow_Ups` as done when the lead replies
- Plug into HubSpot / Pipedrive / Zoho for enterprise CRM needs

## Run it

```bash
python tools/deploy_demo_12_full_lead_engine.py deploy

curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/demo12-full-lead-engine \
  -H "Content-Type: application/json" -d '{"demoMode":"1"}'
```

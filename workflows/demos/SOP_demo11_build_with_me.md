# DEMO-11 — Build-With-Me Minimal Pipeline

> **Headline result:** *"Built this in 90 seconds."*

## Business problem

Nobody believes automation is accessible until they see how few nodes it actually takes. This workflow is deliberately minimal — 6 nodes, linear left-to-right, no switches, no branches. It's the hero shot for the "Build With Me" content format.

Pair it with DEMO-12 (the upgraded version) to show the progression: *"Here's the MVP I built in 90 seconds. Here's what we upgrade to when you want it production-grade."*

## Target client

First-touch leads. Cold audience. People who watched 3 other workflow demos and still think "that looks complicated."

## Demo scenario (90s — built live on camera)

1. **0:00** Open n8n blank canvas. "6 nodes. Go."
2. **0:10** Drag Webhook. Name the path.
3. **0:20** Drag Set node. "This is where inputs go."
4. **0:35** Drag HTTP Request. Paste OpenRouter URL. Pick credential.
5. **0:55** Drag Gmail send. Map `to`, `subject`, `body` to the AI output.
6. **1:10** Drag Google Sheets append. Map columns.
7. **1:20** Drag Respond. Connect. Save.
8. **1:30** Fire a curl. Lead replied to. Sheet logged. Done.

## Architecture

```
Webhook Trigger
  -> Demo Config (set sheetId + normalise form fields)
  -> AI Draft Reply (OpenRouter httpRequest)
  -> [fan out]
     -> Send Reply (Gmail)
        -> Respond
     -> Log to Google Sheet (Leads_Log)
```

Nodes: **6** total. Connections: **4**. That's the pitch.

## Demo narration (beats)

> "Six nodes. A form comes in. AI writes a reply. Gmail sends it. The Sheet logs it. The webhook confirms back to the form. That's it. That's the whole system. You can copy this in your n8n account right now."

### Best opening shot
Blank n8n canvas with a stopwatch overlay.

### Before-vs-After angle
- **Before:** "I should hire an agency to build this."
- **After:** "Oh — I could actually build this myself tonight."

## Credentials checklist

All three are the same canonical demo creds you already have:

| Cred | ID |
|---|---|
| Gmail OAuth | `2IuycrTIgWJZEjBE` |
| Google Sheets | `OkpDXxwI8WcUJp4P` |
| OpenRouter | `9ZgHenDBrFuyboov` |

## Example input

```json
POST /webhook/demo11-build-with-me
{
  "name": "Alex Nkosi",
  "email": "alex@teststudio.co.za",
  "company": "Test Studio",
  "message": "Curious about automation — what's a reasonable starting package?"
}
```

## Example output

- Gmail: HTML reply sent to `alex@teststudio.co.za`.
- Sheet: row appended to `Leads_Log` tab.
- Webhook response:

```json
{
  "status": "replied",
  "runId": "RUN-20260420-090715",
  "emailSentTo": "alex@teststudio.co.za"
}
```

## Error handling

Deliberately minimal — this demo is about simplicity, not resilience. For production, upgrade to DEMO-12 which adds validation, dedup, retries, enrichment, Slack ping.

## Upsell path

Literally just point at DEMO-12. "This is what it looks like when you actually deploy it."

## Run it

```bash
python tools/deploy_demo_11_build_with_me.py deploy

curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/demo11-build-with-me \
  -H "Content-Type: application/json" \
  -d '{"name":"Alex","email":"alex@test.co.za","message":"Interested"}'
```

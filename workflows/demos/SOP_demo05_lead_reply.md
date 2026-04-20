# DEMO-05 — Instant Lead Reply Engine

> **Headline result:** *"Lead replied to in 20 seconds."*

## Business problem

Your website form collects leads 24/7. Your team replies during business hours — at best. Speed-to-lead data says if you respond under 5 min you're 100x more likely to qualify them. Most SMBs average 47 hours. This workflow closes the gap to **20 seconds**, with a personalised AI-drafted reply that reads like you wrote it.

## Target client

Service agencies (marketing, consulting, accounting, legal), coaches with a booking page, B2B SaaS running paid ads. Anyone where the website form is the top of the funnel and the first reply converts the meeting.

## Demo scenario (60s)

1. Screenshare an empty inbox + the master Google Sheet `Leads_Log` tab.
2. Hit the webhook with a test payload (curl, Postman, or a basic HTML form you alt-tab to).
3. ~15 seconds later: the inbox pings with a personalised, brand-voiced reply. The `Leads_Log` tab shows a new row with Intent, AI reply preview, status=replied.
4. Fire a second payload where `message` is spammy ("free crypto giveaway") — watch it get classified `spam`, skip the reply, but still log with status=logged-only.

## Architecture

```
Webhook Trigger
  -> Demo Config (fixture + runId + sheetId)
     -> DEMO_MODE Switch
        -> demo: Load Fixture Lead
        -> live: Normalise Live Lead
     -> Merge Lead Sources
     -> Build Classification Prompt
     -> AI Classify & Draft (Claude Sonnet, temp 0.4)
     -> Parse AI Output (intent, urgency, reasoning, reply, subject)
     -> Intent Router (IF shouldReply)
        -> yes: Send Reply (Gmail)
        -> no : Skip Reply (noOp)
     -> Merge Branches
     -> Log Lead (Sheets append -> Leads_Log)
     -> Audit Log
     -> Respond
```

## Demo narration (beats)

1. **0:00** "Every website form sends me a lead. I used to spend 2 hours a day replying."
2. **0:08** Fire webhook. "That's a new lead — Kagiso from Fourways Fitness."
3. **0:15** Point at inbox pinging. "20 seconds. Not a canned reply — read it."
4. **0:35** Switch to Sheet. "And the row's logged with the intent score. Sales starts their day with a sorted list."
5. **0:55** "This replaces the first 90 seconds of every new-lead interaction. Forever."

### Best opening shot
Split screen: empty inbox on the left, webhook POST terminal on the right. The ping is the payoff.

### Before-vs-After angle
- **Before:** Lead waits ~47 hours. You look disorganised. Half are cold by Monday.
- **After:** Replied inside a minute. You look sharp. Every lead sees the same speed.

## Credentials checklist

| Layer | Demo | Production |
|---|---|---|
| n8n | `N8N_API_KEY`, `N8N_BASE_URL` | same |
| Gmail OAuth | `2IuycrTIgWJZEjBE` | client's own OAuth cred |
| Google Sheets | `OkpDXxwI8WcUJp4P` + `DEMO_SHEET_VOL2_ID` | client-owned sheet |
| OpenRouter | `9ZgHenDBrFuyboov` | client budget cap set |
| Slack | not used | — |

## Example input

```json
POST /webhook/demo05-lead-reply
{
  "demoMode": "1"
}
```

In live mode, forward the full form payload:
```json
{
  "demoMode": "0",
  "name": "Thandi Xaba",
  "email": "thandi@example.co.za",
  "company": "Xaba & Partners",
  "message": "We saw your case study. Want to chat Thursday?"
}
```

## Example output

```json
{
  "runId": "RUN-20260420-082315",
  "intent": "hot",
  "urgency": "high",
  "replied": true,
  "reply": "<p>Thandi — love that you reached out...</p>"
}
```

## Error handling

- AI call fails -> Parse AI Output returns `intent=generic`, `shouldReply=false`. Lead still logged, Sheet row still created.
- Gmail fails -> `onError: continueRegularOutput`. Audit row records failure.
- Invalid `email` field -> Gmail will throw; caught by continueRegularOutput.

## Upsell path

- Add a Calendly / Google Calendar booking link dynamically injected into replies
- Persist conversation thread and generate second-touch follow-up after 48h
- Client-specific brand voice training from past 200 emails
- Switch Sheet -> HubSpot / Pipedrive for enterprise prospects

## Run it

```bash
python tools/deploy_demo_05_lead_reply.py deploy
python tools/deploy_demo_05_lead_reply.py activate

curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/demo05-lead-reply \
  -H "Content-Type: application/json" \
  -d '{"demoMode":"1"}'
```

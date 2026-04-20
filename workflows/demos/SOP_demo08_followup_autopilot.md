# DEMO-08 — Client Follow-Up Autopilot

> **Headline result:** *"Zero forgotten follow-ups, forever."*

## Business problem

"I meant to follow up with Naledi" is the universal SMB sales regret. Every deal has 3-6 touchpoints; humans reliably remember ~2. This workflow runs at 09:00 every day, reads a `Follow_Ups` tab filled by other workflows (DEMO-10, DEMO-12, DEMO-13), writes a personalised re-engagement email per row, sends it, and marks the row done.

The Sheet IS the rules engine. Any workflow can drop a reminder in; this one is the executor.

## Target client

Coaches, retainer agencies, fractional CxOs, anyone with a <30 client book who relies on personal touch. Pair with DEMO-12 so the intake workflow is plumbed into the follow-up engine.

## Demo scenario (45s)

1. Show `Follow_Ups` tab — 2 seeded rows with `Status=due`, scheduled for today or earlier.
2. Fire the webhook (on-demand, so the demo doesn't need to wait until 09:00).
3. ~15 seconds: 2 personalised emails leave your outbox, each referencing the *specific* last interaction ("Following up on the quote I sent Tuesday...").
4. `Follow_Ups` rows flip to `Status=sent`.
5. Slack channel: *"Follow-up autopilot sent 2 personalised emails."*

## Architecture

```
Daily 09:00 SAST (cron) ---\
Webhook Trigger -----------+-> Demo Config
                              -> Read Follow_Ups Tab
                              -> Filter Due Rows (Code)
                                   (if demo mode + empty, seeds 2 fixture rows)
                              -> Build Per-Row Prompt
                              -> AI Personalise Follow-Up (Sonnet)
                              -> Parse Follow-Up
                              -> Send Follow-Up Email (Gmail)
                              -> Mark Row Sent (Sheets update by Follow_Up_ID)
                              -> Aggregate Summary
                              -> Slack Digest
                              -> Audit Log
                              -> Respond
```

## Demo narration (beats)

1. **0:00** "This tab is my follow-up backlog. Every row needs a human touch."
2. **0:06** Trigger webhook. "Pretend it's 09:00 on a Monday."
3. **0:20** Gmail sent folder — 2 new emails, personalised to each contact.
4. **0:35** Back to the Sheet — rows flipped to sent. Run daily, forever.
5. **0:55** "No more 'I meant to follow up'. Just... follow-ups happen."

### Best opening shot
The `Follow_Ups` tab with `Scheduled_For <= today` rows highlighted red.

### Before-vs-After angle
- **Before:** Sticky notes, mental bookmarks, "I'll remember". You lose half.
- **After:** Every scheduled touch goes out, personalised. The Sheet is single-source-of-truth.

## Credentials checklist

| Layer | Demo | Production |
|---|---|---|
| Gmail OAuth | shared AVM cred | client OAuth, respect their signature |
| Google Sheets | demo workbook | client workbook, POPIA-safe share |
| OpenRouter | shared | per-client budget |
| Slack | shared | client workspace webhook |

## Example Follow_Ups row (input)

| Follow_Up_ID | Related_Record | Contact | Scheduled_For | Type | Status | Last_Action | Notes |
|---|---|---|---|---|---|---|---|
| FU-DEMO-002 | LEAD-88 | pieter@karoocraft.co.za | 2026-04-20 | quote-followup | due | quote-sent-2026-04-17 | Sent freight quote R82k. No response in 3 days. |

## Example email sent

> Subject: Quick follow-up on your quote
>
> Hi Pieter — just circling back on the freight quote I sent Wednesday for the PE -> Midrand lane. If R82k sits in the ballpark for what you had in mind, I can hold truck availability for Friday. A quick "yes, let's book" is enough. — Ian

## Error handling

- Empty `Follow_Ups` tab -> in demo mode, inject 2 fixture rows. In live mode, skip gracefully; Slack posts "_No follow-ups due today._"
- AI fails -> fallback copy used (`Hi, just circling back...`)
- Gmail send fails -> row NOT marked sent. Next day's run retries.

## Upsell path

- SMS / WhatsApp channel in addition to email
- Per-contact "last 5 interactions" context pulled into the prompt
- Reply-detection loop — auto-mark row as done when the lead replies
- Weekly "your follow-up conversion rate" dashboard

## Run it

```bash
python tools/deploy_demo_08_followup_autopilot.py deploy
python tools/deploy_demo_08_followup_autopilot.py activate   # enables the daily cron

curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/demo08-followup-autopilot \
  -H "Content-Type: application/json" -d '{"demoMode":"1"}'
```

# DEMO-09 — Email → CRM Auto-Updater

> **Headline result:** *"No more manual Google Sheet updates."*

## Business problem

Every week an email arrives with "hey here's my details, call me on 082...". Someone has to read it, open the CRM Sheet, copy the name, company, phone, their ask, their budget — and then maybe reply. Or maybe not. This workflow reads the email, extracts structured fields with AI, upserts the CRM row, and sends a branded acknowledgement. All of it before you've finished your coffee.

This is the canonical **"Before vs After"** demo — show someone manually copy-pasting vs watching the Sheet row appear.

## Target client

Solo operators drowning in inbox. Inbound-heavy businesses (inbound-only funnels, podcast guests, partnership emails). Fractional agencies where the founder IS the SDR.

## Demo scenario (75s)

1. **Before clip (pre-recorded, 15s):** You in Gmail, copy-pasting 7 fields into a Sheet row. Timer shows 2:14.
2. Switch to live. Point at empty `CRM_Clients` row filter.
3. Fire the webhook (or wait for Gmail trigger). Fixture email is a detailed inbound.
4. ~20s later — `CRM_Clients` row appears, all 8 fields populated correctly. Acknowledgement email lands in the lead's inbox.
5. "The difference between 2 minutes per lead and 2 seconds per lead."

## Architecture

```
Gmail Inbox Trigger -----\
Webhook Trigger ---------+-> Demo Config
                            -> DEMO_MODE Switch
                               -> demo: Load Fixture Email
                               -> live: Normalise Gmail Payload (headers, body)
                            -> Merge Email Sources
                            -> Build Extract Prompt
                            -> AI Extract CRM Fields (Sonnet, strict JSON)
                            -> Parse Extracted Fields
                            -> Has Actionable Fields? (IF shouldAcknowledge)
                               -> yes: Upsert Client Row (Sheets appendOrUpdate by Email)
                                       + Send Acknowledgement (Gmail)
                               -> no : Skip Action (noOp)
                            -> Merge End
                            -> Audit Log
```

## Demo narration (beats)

1. **0:00** Show the Before clip: "That's how 99% of businesses do this today. 2 minutes per email."
2. **0:18** Cut to live. "Now watch."
3. **0:22** Fire the webhook. Cut to the Sheet.
4. **0:35** Rows appear. Name, company, phone, ask, budget — all correct.
5. **0:50** Switch to Gmail. Acknowledgement email to the lead lands: "Got it — Blue Horizon | next step." Professional, branded.
6. **1:10** "Every email from a prospect, captured cleanly, acknowledged. Zero typing."

### Best opening shot
Split-screen Before/After. The Before side is the goldmine — people laugh nervously because it's their own workflow.

### Before-vs-After angle
- **Before:** Read email, open Sheet, type, type, type, forget to reply, 2 min+ per lead.
- **After:** Sheet updates itself. Acknowledgement sent. You read the ask, not the metadata.

## Credentials checklist

| Layer | Demo | Production |
|---|---|---|
| Gmail OAuth | shared | client OAuth + a dedicated label filter like `inbox/leads` |
| Google Sheets | demo sheet | client CRM workbook |
| OpenRouter | shared | per-client |

## Example fixture input (Naledi — Blue Horizon Consulting)

```text
From: Naledi van Wyk <naledi@bluehorizon.co.za>
Subject: Intro — Blue Horizon Consulting wants to explore automation

Hi Ian, we spoke briefly at the JCCI breakfast last month. I run Blue Horizon
Consulting (20-person boutique, mostly corporate strategy work). We're
drowning in admin — client onboarding, status reports, follow-ups.

Would love to chat about what automation could do for us. My direct line is
+27 82 413 6609, and I'm generally free after 2pm on Tuesdays and Thursdays.

Looking at a 3-6 month engagement, budget R20-40k/mo depending on scope.
```

## Example extracted row

| Client_ID | Name | Company | Email | Phone | Last_Contacted | Ask | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| CLT-1745... | Naledi van Wyk | Blue Horizon Consulting | naledi@bluehorizon.co.za | +27 82 413 6609 | 2026-04-20T08:14 | Explore automation for onboarding/status/follow-ups | inbox-captured | score=9 budget=R20-40k/mo availability=Tue/Thu after 2pm |

## Error handling

- AI extraction returns garbage -> Parse step falls back to safe defaults (email from `from` header, name from `from` name).
- Spam/bounce detected (`shouldAcknowledge=false`) -> row skipped, audit logs the rejection.
- Email format unparseable -> Normalise step still produces a minimal row with subject-only note.

## Upsell path

- Attach the original email thread ID so replies auto-link to the CRM row
- OCR business card image attachments (Vision API) for conference lead capture
- Plug in to HubSpot / Pipedrive via their API
- Weekly "inbox ROI" report — which captured leads converted

## Run it

```bash
python tools/deploy_demo_09_email_crm_updater.py deploy
python tools/deploy_demo_09_email_crm_updater.py activate   # enables Gmail trigger

curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/demo09-email-crm \
  -H "Content-Type: application/json" -d '{"demoMode":"1"}'
```

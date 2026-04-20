# AVM Demo Workflows — Sales Playbook

Demo workflows built to be shown cold on prospect calls. Two volumes:

- **Vol. 1** — content-ops demos (Video Clip Factory, UGC Ops, Comment Lead
  Miner, Hook Lab). Airtable-backed. Setup: `tools/setup_demo_airtable.py`.
- **Vol. 2** — lead / admin replacement demos (DEMO-05 through DEMO-13).
  Google Sheets-backed (one master workbook, 9 tabs). Setup:
  `tools/setup_demo_vol2_sheet.py`.

All demos run in `DEMO_MODE=1` with inline fixtures so a cold demo needs
no external API keys beyond Gmail / Sheets / OpenRouter.

---

## Vol. 1 — Content Ops Shortlist

| # | Demo | File | Best for | Live-demo time |
|---|------|------|----------|----------------|
| 1 | **Video Clip Factory** | `demo01_video_clips.json` | Creators, podcasters, agencies, B2B founders with long-form content | ~90s |
| 2 | **UGC Ops Autopilot** | `demo02_ugc_ops.json` | Ecommerce, DTC, CPG brands, performance agencies | ~2m |
| 3 | **Comment Lead Miner** | `demo03_comment_leads.json` | B2B SaaS, service agencies, any brand running content + ads | ~60s |
| 4 | **Hook Lab** | `demo04_hook_lab.json` | Solopreneurs, small teams, copywriters; easy upsell to #1 | ~60s |

---

## Vol. 2 — Lead & Admin Replacement Pack

All 9 workflows share one master sheet — `AVM_Demo_Pack_Vol2` — with 9
tabs (`Leads_Log`, `Meeting_Actions`, `CRM_Clients`, `Follow_Ups`,
`Quotes_Log`, `Reminders`, `Gmail_Drafts_Log`, `Audit_Log`, `Demo_Control`).

| # | Demo | File | Headline | Live-demo time |
|---|------|------|----------|----------------|
| 5 | **Instant Lead Reply Engine** | `demo05_lead_reply.json` | "Lead replied to in 20 seconds" | ~60s |
| 6 | **Smart Lead Reply Bot (Inbox)** | `demo06_inbox_reply_bot.json` | "Every inbox lead gets a draft reply in 10s" | ~60s |
| 7 | **Meeting Notes → Action Machine** | `demo07_meeting_notes.json` | "Meeting notes turned into action items instantly" | ~90s |
| 8 | **Client Follow-Up Autopilot** | `demo08_followup_autopilot.json` | "Zero forgotten follow-ups, forever" | ~45s |
| 9 | **Email → CRM Auto-Updater** | `demo09_email_crm_updater.json` | "No more manual Google Sheet updates" | ~75s |
| 10 | **Logistics Quote Request Handler** | `demo10_logistics_quotes.json` | "Quote request handled automatically" | ~90s |
| 11 | **Build-With-Me Minimal Pipeline** | `demo11_build_with_me.json` | "Built this in 90 seconds" | ~90s (built live) |
| 12 | **Full Lead Handling Engine (Part 2)** | `demo12_full_lead_engine.json` | "From raw lead to CRM record in 15 seconds" | ~2m |
| 13 | **Admin Replacement System** | `demo13_admin_replacement.json` | "Replace 3 admin jobs with one automation" | ~90s |

Each demo has a dedicated SOP at `SOP_demo0X_*.md` with node-by-node
walkthrough, demo narration, example input/output, and upsell path.

---

## Which to open with

For content-ops prospects, lead with Demo 1 (Video Clip Factory).

For **lead / admin prospects** (the much bigger pool):

1. **DEMO-11 Build-With-Me** — opens the room. "Here's what it takes to build this. 6 nodes. 90 seconds."
2. **DEMO-10 Logistics Quote Handler** — niche-specific credibility. Use for warehousing, 3PL, freight prospects, or any vertical where a tailored form exists.
3. **DEMO-13 Admin Replacement System** — the closer. "One workflow, three admin jobs, every lead, forever."

Hold DEMO-07 (Meeting Notes), DEMO-08 (Follow-Up Autopilot), and
DEMO-09 (Email -> CRM) as second-round material after the first yes.

---

## First-time setup — Vol. 2

```bash
# 1. Create the master Google Sheet (requires GOOGLE_APPLICATION_CREDENTIALS)
python tools/setup_demo_vol2_sheet.py

# 2. Paste the printed DEMO_SHEET_VOL2_ID into .env

# 3. (Optional) add SLACK_DEMO_WEBHOOK_URL for DEMO-07/08/12/13

# 4. Build + deploy each workflow:
python tools/deploy_demo_11_build_with_me.py deploy
python tools/deploy_demo_05_lead_reply.py deploy
python tools/deploy_demo_06_inbox_reply_bot.py activate    # Gmail trigger
python tools/deploy_demo_07_meeting_notes.py deploy
python tools/deploy_demo_08_followup_autopilot.py activate # Daily cron
python tools/deploy_demo_09_email_crm_updater.py activate  # Gmail trigger
python tools/deploy_demo_10_logistics_quotes.py deploy
python tools/deploy_demo_12_full_lead_engine.py deploy
python tools/deploy_demo_13_admin_replacement.py deploy
```

Webhook-triggered workflows (05, 07, 10, 11, 12, 13) don't need `activate`
— `deploy` makes them reachable at their test URL. `activate` is only
required for scheduled triggers (DEMO-08) and Gmail pollers (DEMO-06,
DEMO-09).

---

## Running Vol. 2 cold (fixture mode)

Every workflow defaults to `demoMode=1`. Inline fixture data means
nothing external needs to be wired. Only three creds matter:

| Layer | Demo cred ID | Fail mode if missing |
|---|---|---|
| Gmail OAuth | `2IuycrTIgWJZEjBE` | Email step fails; audit logs it; workflow still completes |
| Google Sheets | `OkpDXxwI8WcUJp4P` | Sheet rows not appended; workflow still completes |
| OpenRouter | `9ZgHenDBrFuyboov` | AI fallback copy used; workflow still produces visible output |
| Slack webhook | env var only | Posts to `/DISABLED`, fails soft |

---

## Going live (production mode)

Switch `demoMode=0` on the trigger payload and:

- Gmail: connect client's own OAuth cred
- Google Sheets: create a client-owned workbook mirroring the 9-tab schema (`setup_demo_vol2_sheet.py` can be pointed at an existing ID via `DEMO_SHEET_VOL2_ID`)
- Slack: swap shared webhook for client workspace webhook
- OpenRouter: set per-client budget cap
- POPIA: capture consent on the form; append to `CRM_Clients` only after consent checkbox

---

## Legacy demo: WhatsApp -> AI -> CRM Pipeline

**File:** `whatsapp_ai_crm_demo.json`

### What It Demonstrates

A complete AI-powered message intake pipeline that processes incoming WhatsApp messages in real time:

1. **Webhook Intake** - Receives incoming WhatsApp messages via HTTP POST
2. **AI Classification** - Claude (via OpenRouter) classifies each message into one of four categories: order, lead, inquiry, or complaint
3. **Smart Routing** - A Switch node routes each message down its dedicated processing path
4. **Four Parallel Paths:**
   - **Orders** - AI extracts product, quantity, urgency, and estimated value -> creates an Airtable CRM record -> sends order confirmation
   - **Leads** - AI scores the lead 1-10 with hot/warm/cold priority -> creates an Airtable CRM record -> sends notification and auto-reply
   - **Inquiries** - AI generates a contextual reply using business knowledge (hours, services, location)
   - **Complaints** - Auto-escalation with priority reference number and 30-minute callback promise

### Node Count

20 functional nodes + 5 sticky notes (documentation)

### Client Talking Points

- **Zero manual sorting** - AI classifies every message automatically
- **Instant response** - Customers get a reply within seconds, 24/7
- **CRM integration** - Every order and lead is captured in Airtable automatically
- **Lead scoring** - AI evaluates lead quality so sales prioritizes hot leads first
- **Escalation** - Complaints are never lost; they get immediate priority routing
- **Scalable** - Handles hundreds of messages per hour with no additional staff
- **Customizable** - Classification categories, AI prompts, and CRM fields are all configurable

# WhatsApp Multi-Agent Onboarding Requirements

## Current Status

### Infrastructure (One-Time Setup)

| # | Requirement | Status | Owner | Notes |
|---|-------------|--------|-------|-------|
| 1 | n8n cloud instance | DONE | - | `ianimmelman89.app.n8n.cloud` |
| 2 | n8n API key configured | DONE | - | Saved in `.env` |
| 3 | Airtable base + 4 tables | DONE | - | Base: `appzcZpiIZ6QPtJXT` |
| 4 | Airtable credential in n8n | DONE | - | "Whatsapp Multi Agent" (`CTVAhYlNsJFMX2lE`) |
| 5 | Twilio credential in n8n | DONE | - | (`YzAgDJdx5ZaKbbar`) |
| 6 | Header Auth credential in n8n | DONE | - | "Header Auth account 2" (`xymp9Nho08mRW2Wz`) |
| 7 | OpenRouter credential in n8n | DONE | - | 3 available (2WC, account, account 2) |
| 8 | Meta Business Account | IN PROGRESS | You | Business verification pending on Facebook |
| 9 | WhatsApp Business API app | DONE | You | App ID: `1453028196166220` |
| 10 | Twilio WhatsApp Sandbox | TODO | You | Manual - Twilio Console |
| 11 | Import workflow to n8n | DONE | Claude | Workflow ID: `S6vf4XoN3k6dgEPF` (36 nodes) |
| 12 | Configure workflow (Base IDs, credentials, table IDs) | DONE | Claude | All IDs + credentials mapped |
| 13 | Activate workflow | DONE | Claude | Webhook URLs live |
| 14 | Create agent_001 record in Airtable | DONE | Claude | Record: `recno4wQeoskcpP6W` (pending phone # + token) |
| 15 | Connect Meta webhook to n8n | TODO | You | Use URL below |
| 16 | Update agent record with fresh access token + phone number | TODO | You/Claude | Waiting on business verification |

---

## What YOU Need to Do (Manual Steps)

These cannot be automated. Complete them in order.

### A. Create Meta Business Account (~5 min)

1. Go to **business.facebook.com** → "Create Account"
2. Business name: "AnyVision Media" (or your business name)
3. Enter your name and business email
4. Verify your email
5. Done — you now have a Meta Business Account

### B. Set Up WhatsApp Business API (~10 min)

1. Go to **developers.facebook.com** → "My Apps" → "Create App"
2. App type: **Business**
3. App name: "WhatsApp Multi-Agent"
4. Select your Meta Business Account from step A
5. On the app dashboard, find **WhatsApp** → click "Set Up"
6. Meta gives you a **test phone number** for free — use it for the pilot

**Collect these 3 values** (you'll give them to me):

| Value | Where to Find It |
|-------|------------------|
| **WhatsApp Business Account ID** | WhatsApp → Getting Started page |
| **Phone Number ID** | WhatsApp → Getting Started → "From" dropdown |
| **Temporary Access Token** | WhatsApp → Getting Started → click "Generate" |

> The temporary token expires every 24 hours. Fine for testing. We'll set up a permanent System User token for production later.

### C. Connect Twilio WhatsApp Sandbox (~5 min)

1. Go to **Twilio Console** → Messaging → Settings → WhatsApp Sandbox
2. Follow the instructions (send a join code from your personal WhatsApp to the Twilio sandbox number)
3. Once connected, Twilio can send WhatsApp messages on behalf of agents

### D. Connect Meta Webhook to n8n (~2 min)

**The workflow is now ACTIVE. Complete this step now.**

1. Go to **developers.facebook.com** → Your App → WhatsApp → Configuration
2. Under "Webhook", click "Edit"
3. **Callback URL**: `https://ianimmelman89.app.n8n.cloud/webhook/whatsapp-webhook`
4. **Verify Token**: `whatsapp_multi_agent_verify` (or any string you choose)
5. Subscribe to webhook field: **messages**
6. Click "Verify and Save"

---

## What I (Claude) Will Automate

Once you complete steps A-C above and share the 3 WhatsApp values, I will:

1. **Import the workflow** to n8n via API
2. **Replace all 11 Airtable Base IDs** with `appzcZpiIZ6QPtJXT`
3. **Map table names** to your actual table IDs:
   - Agents → `tblHCkr9weKQAHZoB`
   - Message Log → `tbl72lkYHRbZHIK4u`
   - Blocked Messages → `tbluSD0m6zIAVmsGm`
   - Errors → `tblM6CJi7pyWQWmeD`
4. **Assign credentials** to all nodes:
   - 11 Airtable nodes → "Whatsapp Multi Agent"
   - AI node → OpenRouter credential
   - Send WhatsApp → Twilio
   - Get Contact Info → Header Auth account 2
5. **Activate the workflow** and give you the webhook URL for step D
6. **Create agent record(s)** in Airtable with the WhatsApp details you provide

---

## Per-Agent Requirements

For each agent you onboard, you need:

### Required Information

| Field | Example | Notes |
|-------|---------|-------|
| Agent's full name | "John Smith" | |
| Email | john@company.com | |
| WhatsApp phone number | +12125551234 | Must include + and country code |
| WhatsApp Business Account ID | 123456789012345 | From Meta (step B) |
| WhatsApp Phone Number ID | 987654321098765 | From Meta (step B) |
| WhatsApp Access Token | EAAx... | From Meta (step B) |
| Company name | "AnyVision Media" | |
| Region | "South Africa" | |
| Language | en | ISO language code |
| Timezone | Africa/Johannesburg | IANA timezone |

### Optional / Has Defaults

| Field | Default | Change If... |
|-------|---------|--------------|
| AI model | gpt-4 (via OpenRouter) | You want a different model |
| AI temperature | 0.7 | You want more/less creative responses |
| Max response length | 300 characters | Agents need longer replies |
| Auto-reply enabled | Yes | You want manual-only mode |
| Online threshold | 5 minutes | You want different "agent is typing" timeout |
| Airtable full access | Yes | You want to restrict agent's data access |
| Google Calendar ID | primary | Agent uses a different calendar |

### What Happens When You Add an Agent

1. I add one row to the Agents table in Airtable
2. The agent's WhatsApp number becomes active immediately
3. Any message sent to that number gets routed through the AI
4. All conversations are logged in the Message Log table
5. Zero workflow changes needed — just a database row

---

## Onboarding Sequence (Optimal Order)

```
YOU: Create Meta Business Account (5 min)
 ↓
YOU: Set up WhatsApp Business API + get test number (10 min)
 ↓
YOU: Connect Twilio WhatsApp Sandbox (5 min)
 ↓
YOU: Share 3 WhatsApp values with me
 ↓
CLAUDE: Import workflow + configure + activate (automated)
 ↓
CLAUDE: Give you the webhook URL
 ↓
YOU: Configure Meta webhook (2 min)
 ↓
CLAUDE: Create agent record(s) in Airtable (automated)
 ↓
YOU: Send a test message from your personal WhatsApp
 ↓
DONE — System is live
```

**Total hands-on time for you: ~25 minutes**

---

## Adding More Agents Later (2 minutes each)

Once the system is running, each new agent is just:

1. Get a new WhatsApp number registered in Meta
2. Share the 3 values (Business Account ID, Phone Number ID, Access Token)
3. I add one row to Airtable
4. Send a test message to verify
5. Done — no workflow changes needed

---

## Quick Reference: Credential Map

| n8n Credential | ID | Used By |
|----------------|-----|---------|
| Whatsapp Multi Agent (Airtable) | `CTVAhYlNsJFMX2lE` | 11 Airtable nodes |
| OpenRouter (TBD which one) | `HPAZMuVNbPKnCLx0` | AI Analysis node |
| Twilio | `YzAgDJdx5ZaKbbar` | Send WhatsApp node |
| Header Auth account 2 | `xymp9Nho08mRW2Wz` | Get Contact Info node |

## Quick Reference: Airtable Table Map

| Table | ID | Purpose |
|-------|----|---------|
| Agents | `tblHCkr9weKQAHZoB` | Agent config + WhatsApp credentials |
| Message Log | `tbl72lkYHRbZHIK4u` | All processed messages |
| Blocked Messages | `tbluSD0m6zIAVmsGm` | Filtered/blocked messages |
| Errors | `tblM6CJi7pyWQWmeD` | System error tracking |

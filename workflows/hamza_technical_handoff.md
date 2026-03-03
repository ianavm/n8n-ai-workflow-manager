# WhatsApp Multi-Agent System (Optimized) — Technical Handoff

**To:** Hamza Chaudry (hamzachaudry33@gmail.com)
**From:** Ian Immelman
**Date:** February 2026
**Re:** Backend debugging — WhatsApp Multi-Agent workflow on n8n Cloud

---

Hi Hamza,

Thanks for coming on board to help debug the WhatsApp Multi-Agent System. I've invited you to the n8n Cloud instance — you should receive an email invite shortly. Below is a full technical briefing on the system architecture, the webhook setup, and the specific issues we're running into.

---

## 1. Access Details

| Resource | Value |
|----------|-------|
| **n8n Cloud Instance** | `https://ianimmelman89.app.n8n.cloud` |
| **Your login** | Check your email for the n8n invite (hamzachaudry33@gmail.com) |
| **Owner account** | ian@anyvisionmedia.com |
| **n8n API Key** | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3NGFjNjUwMS0zNWU0LTQwMWUtYWY4NS01ZmUzZmM0NjMxNjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOGUwNWRjYjMtOTIwMC00OTVmLThhMzAtMTQwYzRhMGFjNGU3IiwiaWF0IjoxNzcwNzA1NDAzfQ.C-MV0zEcDirAUjolC0yjRKS6DMZKIr-xUnLiyPkU9a8` |

Once you accept the invite and set your password, you'll have access to the workflows and all credentials listed below.

---

## 2. Workflows on the Instance

There are **3 related workflows** on the instance. The primary one you'll be working on is the first:

| Workflow | n8n ID | Nodes | Status |
|----------|--------|-------|--------|
| **WhatsApp Multi-Agent System (Optimized)** | `lHHuYucWGFCjZ5Wk6h5So` | 36 | INACTIVE |
| WhatsApp Multi-Agent System (With Registration) | `KU18dU39IczuhhK8e8hbe` | ~42 | INACTIVE |
| WhatsApp Single Business Bot (AnyVision Media) | `ihgFJF-ou1X7I3bud6QV5` | ~30 | INACTIVE |

All workflows live under the **"Agent builds"** project (ID: `6gGSJGmtMjCVySac`).

---

## 3. System Architecture Overview

This is a **36-node n8n workflow** that provides AI-powered WhatsApp auto-reply for multiple real estate agents. Each agent is registered in Airtable with their own WhatsApp number, AI settings, and conversation history.

### Message Flow

```
Incoming WhatsApp Message (via webhook)
  → 1️⃣ Parse & validate message (block group messages)
  → 2️⃣ Block group messages
  → 3️⃣ Look up agent in Airtable by destination WhatsApp number
  → 4️⃣ Merge agent profile data with message
  → 5️⃣ Fetch contact info from Facebook Graph API
  → 6️⃣ Check blocking conditions (DNT label, pinned, agent online)
  → 7️⃣ Verify agent is active with auto-reply enabled
  → 8️⃣ Send to GPT-4 for AI analysis (intent, response, optional Airtable CRUD)
  → 9️⃣ Parse AI JSON decision
  → 🔧 Route any Airtable operations (create/read/update/delete)
  → 🎯 Prepare final response with agent signature
  → 📤 Send reply via WhatsApp (currently Twilio node — BROKEN, see Issues)
  → ✅ Log to Airtable Message Log table
```

### Two Sending Backends

The system was originally built with **Twilio** as the WhatsApp sending backend. We've been upgrading to the native **WhatsApp Business Cloud API** (Meta). Both paths exist in the system:

| Backend | n8n Node Type | Current Status |
|---------|--------------|----------------|
| **Twilio** (original) | `n8n-nodes-base.twilio` | **NO CREDENTIALS ATTACHED** to send node |
| **WhatsApp Cloud API** (upgraded) | `n8n-nodes-base.whatsApp` / `whatsAppTrigger` | Business verification PENDING |

---

## 4. Webhook Endpoints

### Multi-Agent System (Optimized) — Workflow `lHHuYucWGFCjZ5Wk6h5So`

| Endpoint | Webhook Path | Full Production URL | Full Test URL | Method | Purpose |
|----------|-------------|---------------------|---------------|--------|---------|
| **Main webhook** | `whatsapp-webhook` | `https://ianimmelman89.app.n8n.cloud/webhook/whatsapp-webhook` | `https://ianimmelman89.app.n8n.cloud/webhook-test/whatsapp-webhook` | GET/POST | Receives all incoming WhatsApp messages |
| **Agent status** | `agent-status` | `https://ianimmelman89.app.n8n.cloud/webhook/agent-status` | `https://ianimmelman89.app.n8n.cloud/webhook-test/agent-status` | POST | Agent online/offline toggle |

### Registration Workflow — Workflow `KU18dU39IczuhhK8e8hbe`

Has the same webhooks as above, plus:

| Endpoint | Webhook Path | Full Production URL | Method | Purpose |
|----------|-------------|---------------------|--------|---------|
| **Agent registration** | `agent-register` | `https://ianimmelman89.app.n8n.cloud/webhook/agent-register` | POST | Self-registration (CORS enabled: `*`) |

### Single Business Bot — Workflow `ihgFJF-ou1X7I3bud6QV5`

| Endpoint | Webhook Path | Full Production URL | Method | Purpose |
|----------|-------------|---------------------|--------|---------|
| **Main webhook** | `business-whatsapp` | `https://ianimmelman89.app.n8n.cloud/webhook/business-whatsapp` | GET/POST | Receives incoming messages |

> **Note:** Production URLs (`/webhook/`) only work when the workflow is **ACTIVE**. Test URLs (`/webhook-test/`) work when the workflow editor is open and you click "Listen for Test Event."

---

## 5. All Credentials (n8n Credentials Panel)

These are the credential IDs referenced across all three workflows. You can view and edit them in **n8n → Settings → Credentials**.

| Credential Name | Type | Credential ID | Used By | Status |
|-----------------|------|---------------|---------|--------|
| **Whatsapp Multi Agent** | `airtableTokenApi` | `ZyBrcAO6fps7YB3u` | All Airtable nodes (multi-agent workflows) | Active |
| **Whatsapp Multi Agent** (alt) | `airtableTokenApi` | `CTVAhYlNsJFMX2lE` | Single Business Bot workflow | Active |
| **OpenAi account 10** | `openAiApi` | `mNXmJ6IgruQfWkPq` | 8️⃣ AI Analysis node | Active |
| **WhatsApp account AVM Multi Agent** | `whatsAppApi` | `dCAz6MBXpOXvMJrq` | WhatsApp Cloud API Send node | Active |
| **WhatsApp OAuth AVM Multi Agent** | `whatsAppTriggerApi` | `rUyqIX1gaBs3ae6Q` | WhatsApp Cloud API Trigger node | Active |
| **Header Auth account 2** | `httpHeaderAuth` | `xymp9Nho08mRW2Wz` | 5️⃣ Get Contact Info (Graph API) | Active |
| **Gmail AVM Tutorial** | `gmailOAuth2` | `EC2l4faLSdgePOM6` | Gmail nodes (if used) | Active |
| **Google Calendar AVM Tutorial** | `googleCalendarOAuth2Api` | `I5zIYf0UxlkUt3KG` | Calendar nodes (if used) | Active |
| **Twilio** | `twilioApi` | *(not assigned to any node)* | 📤 Send WhatsApp node | **NEEDS CONFIG** |

---

## 6. Meta / WhatsApp Business Cloud API Details

| Parameter | Value |
|-----------|-------|
| **WhatsApp Business App ID** | `1453028196166220` |
| **WhatsApp App Secret** | `7ba325604b579e4b230c07a51bc90e20` |
| **WhatsApp Phone Number ID** | `956186580917374` |
| **WhatsApp Business Account ID** | `1926967314871711` |
| **Graph API Version** | `v18.0` |
| **Contact Lookup Endpoint** | `GET https://graph.facebook.com/v18.0/956186580917374/{waId}` |
| **Contact Lookup Auth** | Bearer token via `httpHeaderAuth` credential `xymp9Nho08mRW2Wz` |

### Meta Webhook Configuration (NOT YET DONE)

This is the configuration needed in the Meta Developer Console to connect incoming WhatsApp messages to n8n:

1. Go to **developers.facebook.com** → Your App (ID: `1453028196166220`) → **WhatsApp** → **Configuration**
2. Under Webhooks, click **"Edit"**
3. **Callback URL:** `https://ianimmelman89.app.n8n.cloud/webhook/whatsapp-webhook`
4. **Verify Token:** *(set this in the n8n WhatsApp Trigger node — must match exactly)*
5. **Subscribe to:** `messages`
6. **Important:** The n8n workflow must be **ACTIVE** for the verification handshake to succeed

---

## 7. Airtable Configuration

| Parameter | Value |
|-----------|-------|
| **Airtable Base ID** | `appzcZpiIZ6QPtJXT` |
| **Airtable API Token** | `<REDACTED - see .env>` |

### Airtable Tables

| Table ID | Purpose | Key Fields |
|----------|---------|------------|
| **tblAgents** | Agent profiles | `agent_id`, `agent_name`, `whatsapp_number`, `is_active`, `auto_reply`, `is_online`, `last_seen`, `ai_model`, `ai_temperature`, `company_name`, `region`, `language`, `timezone`, `whatsapp_phone_number_id`, `whatsapp_access_token`, `airtable_base_id` |
| **tblMessageLog** | All processed messages | `timestamp`, `message_id`, `agent_id`, `from_number`, `to_number`, `message_body`, `intent`, `confidence`, `processing_time_ms`, `status` |
| **tblBlockedMessages** | Blocked messages | `timestamp`, `from_number`, `to_number`, `block_reason`, `is_group`, `is_pinned`, `agent_online` |
| **tblErrors** | Workflow errors | `timestamp`, `error_type`, `error_message`, `execution_id`, `workflow_name`, `node_name`, `error_stack` |

---

## 8. Node-by-Node Reference (Optimized Workflow)

| # | Node Name | Type | Credential | Notes |
|---|-----------|------|------------|-------|
| - | Manual Trigger | `manualTrigger` | — | For testing |
| - | 📱 WhatsApp Webhook | `webhook` (v2) | — | Path: `whatsapp-webhook`, webhookId: `whatsapp-webhook` |
| - | 👤 Agent Status Webhook | `webhook` (v2) | — | Path: `agent-status`, webhookId: `agent-status`, POST only |
| 1 | 1️⃣ Parse Message | `code` (v2) | — | Extracts To/From/Body/Media, handles Twilio format |
| 2 | ✅ Valid? | `if` (v2) | — | Checks `parseSuccess === true` |
| 3 | 2️⃣ Block Groups? | `if` (v2) | — | Blocks if `isGroup === true` |
| 4 | 3️⃣ Find Agent | `airtable` (v2) | `ZyBrcAO6fps7YB3u` | **BUG: base ID is `appXXXXXXXXXXXXXX` (placeholder!)** — should be `appzcZpiIZ6QPtJXT` |
| 5 | ✅ Agent Found? | `if` (v2) | — | Checks record ID is not empty |
| 6 | 4️⃣ Merge Agent Data | `code` (v2) | — | **BUG: fallback base ID is `appXXXXXXXXXXXXXX`** — should be `appzcZpiIZ6QPtJXT` |
| 7 | 5️⃣ Get Contact Info | `httpRequest` (v4) | `xymp9Nho08mRW2Wz` | Calls `graph.facebook.com/v18.0/{phoneNumberId}/{waId}` |
| 8 | 6️⃣ Check Blocks | `code` (v2) | — | Checks DNT label, pinned status, agent online |
| 9 | ✅ Process Message? | `if` (v2) | — | Routes blocked vs. processable |
| 10 | 7️⃣ Agent Active? | `if` (v2) | — | Checks `agent.isActive` and `agent.autoReply` |
| 11 | 8️⃣ AI Analysis | `httpRequest` (v4) | `mNXmJ6IgruQfWkPq` | Calls OpenAI `chat/completions`, model from agent profile (default: `gpt-4`) |
| 12 | 9️⃣ Parse AI Decision | `code` (v2) | — | Parses AI JSON response, handles markdown-wrapped JSON |
| 13 | 🔧 Need Airtable? | `if` (v2) | — | Routes based on `airtableOperation.needed` |
| 14 | 🔀 Route Operation | `code` (v2) | — | Validates and routes CRUD operations |
| 15 | ➕ CREATE Record | `airtable` (v2) | `ZyBrcAO6fps7YB3u` | Dynamic base/table from expression |
| 16 | 📖 READ Records | `airtable` (v2) | `ZyBrcAO6fps7YB3u` | Dynamic base/table from expression |
| 17 | ✏️ UPDATE Record | `airtable` (v2) | `ZyBrcAO6fps7YB3u` | Dynamic base/table from expression |
| 18 | 🗑️ DELETE Record | `airtable` (v2) | `ZyBrcAO6fps7YB3u` | Dynamic base/table from expression |
| 19 | 🎯 Prepare Response | `code` (v2) | — | Adds agent signature, calculates processing time |
| 20 | 📤 Send WhatsApp | **`twilio` (v1)** | **NONE** | **CRITICAL BUG: No credential attached! See Issue 1** |
| 21 | ✅ Log Success | `airtable` (v2) | `ZyBrcAO6fps7YB3u` | **BUG: base ID placeholder `appXXXXXXXXXXXXXX`** |
| 22 | ✅ Success Response | `respondToWebhook` | — | Returns JSON to webhook caller |
| 23 | 🚫 Log Blocked | `airtable` (v2) | `ZyBrcAO6fps7YB3u` | **BUG: base ID placeholder `appXXXXXXXXXXXXXX`** |
| 24 | 🚫 Blocked Response | `respondToWebhook` | — | Returns blocked reason |
| 25 | ❌ Log Error | `airtable` (v2) | `ZyBrcAO6fps7YB3u` | **BUG: base ID placeholder `appXXXXXXXXXXXXXX`** |
| 26 | ❌ Error Response | `respondToWebhook` | — | Returns error info |
| 27 | Parse Status | `code` (v2) | — | Validates agent status update request |
| 28 | Find Agent | `airtable` (v2) | `ZyBrcAO6fps7YB3u` | **BUG: base ID placeholder `appXXXXXXXXXXXXXX`** |
| 29 | Update Status | `airtable` (v2) | `ZyBrcAO6fps7YB3u` | **BUG: base ID placeholder `appXXXXXXXXXXXXXX`** |
| 30 | Status Response | `respondToWebhook` | — | Returns agent status update confirmation |
| 31 | ⚠️ Error Trigger | `errorTrigger` | — | Catches all workflow errors |
| 32 | Handle Error | `code` (v2) | — | Formats error data |
| 33 | Log to Airtable | `airtable` (v2) | `ZyBrcAO6fps7YB3u` | Error logging — **BUG: base ID placeholder** |

---

## 9. Issues & Bugs Found

### CRITICAL — Issue 1: "📤 Send WhatsApp" Node Has NO Credentials

The send node (`📤 Send WhatsApp`) in the Optimized workflow uses `n8n-nodes-base.twilio` (typeVersion 1) but **has no credential block attached at all**. The node JSON is:

```json
{
  "name": "📤 Send WhatsApp",
  "type": "n8n-nodes-base.twilio",
  "typeVersion": 1,
  "parameters": {
    "message": "={{ $json.body }}",
    "options": {}
  }
  // NO "credentials" key exists!
}
```

**Fix options:**
- **Option A (Twilio):** Attach a configured Twilio credential and set up the Twilio WhatsApp Sandbox
- **Option B (WhatsApp Cloud API — preferred):** Convert this node from `n8n-nodes-base.twilio` to `n8n-nodes-base.whatsApp` (v1.1) using credential `dCAz6MBXpOXvMJrq` ("WhatsApp account AVM Multi Agent"). The deploy script `tools/deploy_whatsapp_bot.py` has a `convert_twilio_to_whatsapp()` function that does exactly this. The converted node should look like:

```json
{
  "type": "n8n-nodes-base.whatsApp",
  "typeVersion": 1.1,
  "parameters": {
    "operation": "send",
    "phoneNumberId": "956186580917374",
    "recipientPhoneNumber": "={{ $json.to }}",
    "textBody": "={{ $json.body }}",
    "additionalFields": {}
  },
  "credentials": {
    "whatsAppApi": {
      "id": "dCAz6MBXpOXvMJrq",
      "name": "WhatsApp account AVM Multi Agent"
    }
  }
}
```

### CRITICAL — Issue 2: Airtable Base ID Placeholders

Multiple Airtable nodes in the workflow have the base ID hardcoded as `appXXXXXXXXXXXXXX` (a placeholder) instead of the real base ID `appzcZpiIZ6QPtJXT`. This affects **all nodes that use `"mode": "list"`** — specifically:

- **3️⃣ Find Agent** — base: `appXXXXXXXXXXXXXX` (must be `appzcZpiIZ6QPtJXT`)
- **✅ Log Success** — base: `appXXXXXXXXXXXXXX`
- **🚫 Log Blocked** — base: `appXXXXXXXXXXXXXX`
- **❌ Log Error** — base: `appXXXXXXXXXXXXXX`
- **Find Agent** (status flow) — base: `appXXXXXXXXXXXXXX`
- **Update Status** — base: `appXXXXXXXXXXXXXX`
- **Log to Airtable** (error handler) — base: `appXXXXXXXXXXXXXX`

Additionally, the **4️⃣ Merge Agent Data** code node has a fallback that defaults to `appXXXXXXXXXXXXXX`:
```javascript
airtableBaseId: fields.airtable_base_id || 'appXXXXXXXXXXXXXX',
```
This should be changed to:
```javascript
airtableBaseId: fields.airtable_base_id || 'appzcZpiIZ6QPtJXT',
```

> **Note:** The CRUD nodes (CREATE, READ, UPDATE, DELETE) use expression mode `={{ $json.airtableBaseId }}` which pulls from the agent profile, so they're OK *if* the agent's Airtable record has the correct `airtable_base_id` field set. But the fallback still needs fixing.

### BLOCKING — Issue 3: Facebook Business Verification PENDING

Meta Business verification for "AnyVision Media" is still under review. Until it clears, we can only message registered test numbers via the WhatsApp Cloud API.

- **Check status at:** Meta Business Suite → Business Settings → Business Verification
- Submitted all required docs; waiting on Meta's review

### BLOCKING — Issue 4: Meta Webhook Not Connected to n8n

The callback URL has NOT been configured in the Meta Developer Console yet. This means incoming WhatsApp messages have no path into the n8n workflow via the Cloud API route.

**Steps to configure:**
1. Go to `developers.facebook.com` → App ID `1453028196166220` → **WhatsApp** → **Configuration**
2. Under Webhooks, click **"Edit"**
3. Callback URL: `https://ianimmelman89.app.n8n.cloud/webhook/whatsapp-webhook`
4. Verify Token: Set a token in the n8n WhatsApp Trigger node, then use the same token here
5. Subscribe to: `messages`
6. The workflow **MUST** be ACTIVE for the verification handshake to succeed

### Issue 5: Temporary Access Tokens Expire Every 24 Hours

The current WhatsApp API access token is a temporary developer token. For production, we need a permanent System User token:

1. Meta Business Suite → Business Settings → Users → System Users
2. Create a System User (Admin role)
3. Assign the WhatsApp app with Full Control
4. Generate a permanent token with permissions: `whatsapp_business_messaging`, `whatsapp_business_management`, `business_management`

### Issue 6: Facebook/Meta API Errors During Setup

**This is the main reason you're being brought in.** While creating and configuring the Facebook/Meta APIs, we kept running into two recurring errors:

**Error: "unknown error has occurred"**
- This generic Meta error appeared repeatedly during the API setup process
- Often indicates a mismatch between the app configuration and the business account, or a temporary Meta platform issue
- Could also be related to the pending business verification blocking certain API calls

**Error: "unable to find number"**
- This error appeared when trying to work with WhatsApp phone number ID `956186580917374` through the Meta APIs
- Typically means the phone number is not properly registered with WhatsApp Business Account `1926967314871711`, may still be linked to a personal WhatsApp, or needs to be released and re-registered

**Suggested debugging steps:**
1. Verify phone number ID `956186580917374` is properly added to WhatsApp Business Account `1926967314871711` in Meta Business Settings → Accounts → WhatsApp Accounts
2. Ensure the phone number is NOT linked to any personal WhatsApp account (if it is, delete that WhatsApp account first and wait up to 72 hours)
3. Check that App `1453028196166220` is properly linked to the Business Account in the Meta Developer Console
4. Check the [WhatsApp Business API error codes reference](https://developers.facebook.com/docs/whatsapp/error-codes) for specific error codes
5. If errors persist, file a Meta Business Help Center support ticket

### Issue 7: Message Parser Assumes Twilio Format

The **1️⃣ Parse Message** code node in the Optimized workflow currently parses **Twilio webhook format** (fields like `To`, `From`, `Body`, `MessageSid`, `NumMedia`). If we switch to the WhatsApp Cloud API trigger, the incoming data structure is completely different (uses `messages[]`, `contacts[]`, `metadata{}`).

The **Single Business Bot** (workflow `ihgFJF-ou1X7I3bud6QV5`, file `whatsapp_bot_native.json`) already has an updated parser for Cloud API format — you can reference that version. The native parser extracts:
- `message.from` instead of `data.From`
- `message.text.body` instead of `data.Body`
- `metadata.phone_number_id` instead of `data.To`
- `message.id` instead of `data.MessageSid`

---

## 10. Twilio Setup (If Using as Fallback)

| Parameter | Value |
|-----------|-------|
| **n8n Credential Name** | "Twilio" (exists in n8n but has NO Account SID / Auth Token configured) |
| **Webhook Path** | `/whatsapp-webhook` |
| **Send Node** | "📤 Send WhatsApp" — `n8n-nodes-base.twilio` (typeVersion 1) |
| **Message Format** | `whatsapp:+{number}` for to/from fields |

**To configure (if going the Twilio route):**
1. Log into Twilio Console
2. Navigate to **Messaging → Try it out → Send a WhatsApp message**
3. Follow sandbox setup instructions (send a join code from personal WhatsApp to the Twilio sandbox number)
4. Set the sandbox webhook to: `https://ianimmelman89.app.n8n.cloud/webhook/whatsapp-webhook`
5. Add Account SID and Auth Token to the "Twilio" credential in n8n
6. Attach the Twilio credential to the "📤 Send WhatsApp" node

---

## 11. Deploy Script Reference

There's a Python deploy script at `tools/deploy_whatsapp_bot.py` that automates credential discovery and assignment. It can:
- **Discover** all credentials by scanning every workflow on the instance
- **Convert** Twilio nodes to WhatsApp Cloud API nodes automatically
- **Assign** all credentials to the correct nodes
- **Deploy** the updated workflow back to n8n

```bash
python tools/deploy_whatsapp_bot.py discover   # List all credentials (read-only)
python tools/deploy_whatsapp_bot.py build      # Fetch + assign creds + save locally
python tools/deploy_whatsapp_bot.py deploy     # Fetch + assign creds + push to n8n
```

The script targets the "WhatsApp Single Business Bot (AnyVision Media)" workflow but the credential IDs and conversion logic apply to all three workflows.

---

## 12. Priority Action Items

1. **Fix Airtable base ID placeholders** — Replace `appXXXXXXXXXXXXXX` with `appzcZpiIZ6QPtJXT` in all Airtable nodes and code fallbacks
2. **Fix the Send node** — Either attach Twilio credentials OR convert to WhatsApp Cloud API node
3. **Debug Meta API errors** — Resolve "unknown error" and "unable to find number" for phone number ID `956186580917374` / business account `1926967314871711`
4. **Configure Meta webhook** — Point callback URL to `https://ianimmelman89.app.n8n.cloud/webhook/whatsapp-webhook`
5. **Update message parser** — If using Cloud API, switch from Twilio format to Cloud API format
6. **Generate permanent access token** — Replace temporary developer token with System User token
7. **Activate workflow** — Once everything is wired up, set the workflow to ACTIVE

---

Let me know if you have any questions or need clarification on any of this. Happy to jump on a call to walk through the workflow together.

Best,
Ian

# 🟢 WhatsApp Multi-Agent System — Agent Onboarding Guide

> **Workflow:** WhatsApp Multi-Agent System (Optimized)
> **Platform:** n8n Cloud (`ianimmelman89.app.n8n.cloud`)
> **Industry:** Real Estate

---

## 📊 Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| 🟢 n8n Cloud Instance | **LIVE** | Workflow deployed (36 nodes) |
| 🟢 Airtable Base + 4 Tables | **LIVE** | Agents, Message Log, Blocked, Errors |
| 🟢 Twilio Credential | **LIVE** | Connected in n8n |
| 🟢 OpenRouter (GPT-4) | **LIVE** | AI analysis ready |
| 🟢 Workflow Imported & Configured | **LIVE** | All credentials mapped |
| 🟢 Agent 001 Record Created | **LIVE** | Waiting for phone # + token |
| 🟡 Facebook Business Verification | **PENDING** | Under review by Meta |
| 🔴 Twilio WhatsApp Sandbox | **TODO** | Manual — Twilio Console |
| 🔴 Meta Webhook → n8n | **TODO** | 2-minute setup once approved |
| 🔴 Agent Record: Phone + Token | **TODO** | After Meta approves |

> 💡 **Bottom line:** The system is fully built and deployed. Once Facebook approves your business, you're ~25 minutes away from going live.

---

## 🔵 PHASE 1 — First-Time Setup (Do Once)

*Complete these steps in order after Facebook approves your business.*

---

### Step 1️⃣ — Complete Facebook Business Verification

> 🕐 **Time:** Waiting on Meta (currently in progress)
> 👤 **Owner:** You

```
✅ Already submitted — no action needed
⏳ Wait for the approval email from Meta
📧 Check: business.facebook.com → Business Settings → Business Info
```

🟡 **You are here.** Once this clears, move to Step 2.

---

### Step 2️⃣ — Set Up Twilio WhatsApp Sandbox

> 🕐 **Time:** ~5 minutes
> 👤 **Owner:** You

| # | Action | Details |
|---|--------|---------|
| 🅰️ | Go to **Twilio Console** | → Messaging → Settings → WhatsApp Sandbox |
| 🅱️ | Send the join code | From your personal WhatsApp to the Twilio sandbox number |
| 🅲️ | Confirm connection | You'll see a green checkmark in Twilio |

> 💡 This lets Twilio send WhatsApp messages on behalf of your agents.

---

### Step 3️⃣ — Grab Your 3 WhatsApp Values

> 🕐 **Time:** ~2 minutes
> 👤 **Owner:** You
> 📍 **Where:** developers.facebook.com → Your App → WhatsApp → Getting Started

| # | Value | Where to Find It | Example |
|---|-------|-------------------|---------|
| 🔑 | **WhatsApp Business Account ID** | Getting Started page, top section | `123456789012345` |
| 📱 | **Phone Number ID** | "From" dropdown on Getting Started | `987654321098765` |
| 🔐 | **Temporary Access Token** | Click "Generate" on Getting Started | `EAAx...` |

```
📋 Copy all 3 values and share them with Claude
```

> ⚠️ The temporary token expires every 24 hours. Fine for testing.
> We'll set up a permanent System User token for production later.

---

### Step 4️⃣ — Claude Configures Everything (Automated)

> 🕐 **Time:** ~1 minute (automated)
> 🤖 **Owner:** Claude

Once you share the 3 values, Claude will:

```
✅ Update agent_001 record in Airtable with your WhatsApp credentials
✅ Verify the workflow is active and webhook URLs are live
✅ Give you the webhook URL for the next step
```

---

### Step 5️⃣ — Connect Meta Webhook to n8n

> 🕐 **Time:** ~2 minutes
> 👤 **Owner:** You
> 📍 **Where:** developers.facebook.com → Your App → WhatsApp → Configuration

| # | Action | Value |
|---|--------|-------|
| 🅰️ | Open **Webhook** section | Click "Edit" |
| 🅱️ | **Callback URL** | `https://ianimmelman89.app.n8n.cloud/webhook/whatsapp-webhook` |
| 🅲️ | **Verify Token** | `whatsapp_multi_agent_verify` |
| 🅳️ | **Subscribe to** | ☑️ `messages` |
| 🅴️ | Click | **"Verify and Save"** |

> ✅ If successful, Meta will show a green checkmark next to the webhook.

---

### Step 6️⃣ — Send a Test Message

> 🕐 **Time:** ~1 minute
> 👤 **Owner:** You

```
📱 Open WhatsApp on your personal phone
💬 Send "Hello" to the test number Meta gave you
⏳ Wait 5-10 seconds
✅ You should receive an AI-powered response!
```

> 🎉 **If you got a reply — the system is LIVE!**

---

## 🟣 PHASE 2 — Onboarding Real Estate Agents (~2 min each)

*Once the system is live, adding each new agent is just a database row. No workflow changes needed.*

---

### 🏠 How It Works

```
📱 Client sends WhatsApp message
     ↓
🔀 n8n receives it via webhook
     ↓
🔍 Looks up agent by phone number in Airtable
     ↓
🤖 GPT-4 analyzes the message + generates a reply
     ↓
💬 Sends response back via WhatsApp
     ↓
📝 Logs everything (message, response, timing)
```

> Each agent gets their own WhatsApp number, AI settings, and conversation logs.
> **Zero code changes. One Airtable row = one active agent.**

---

### 🆕 To Add a New Real Estate Agent

#### Step A — Register a WhatsApp Number for the Agent

> 📍 **Where:** developers.facebook.com → Your App → WhatsApp → Getting Started

| # | Action |
|---|--------|
| 1 | Click **"Add phone number"** |
| 2 | Enter the agent's business phone number (with country code) |
| 3 | Verify via SMS or voice call |
| 4 | Copy the new **Phone Number ID** |

---

#### Step B — Collect Agent Information

Share the following with Claude for each new agent:

| Field | Example (Real Estate) | Required? |
|-------|----------------------|-----------|
| 🧑 **Full Name** | Sarah Johnson | ✅ Yes |
| 📧 **Email** | sarah@remax-capetown.co.za | ✅ Yes |
| 📱 **WhatsApp Number** | +27821234567 | ✅ Yes (with + and country code) |
| 🔑 **WhatsApp Business Account ID** | 123456789012345 | ✅ Yes |
| 📱 **Phone Number ID** | 987654321098765 | ✅ Yes (from Step A) |
| 🔐 **Access Token** | EAAx... | ✅ Yes |
| 🏢 **Company Name** | RE/MAX Cape Town | ✅ Yes |
| 🌍 **Region** | South Africa | ✅ Yes |
| 🗣️ **Language** | en | ✅ Yes (ISO code) |
| 🕐 **Timezone** | Africa/Johannesburg | ✅ Yes (IANA format) |

---

#### Step C — Claude Creates the Agent Record (Automated)

> 🤖 Claude adds one row to the **Agents** table in Airtable.

```
✅ Agent is immediately active
✅ AI auto-reply is enabled by default
✅ All messages are logged automatically
✅ No workflow restart needed
```

---

#### Step D — Test the Agent's Number

```
📱 Send a WhatsApp message to the agent's number
💬 Example: "Hi, I'm looking for a 3-bedroom house in Sea Point"
⏳ Wait 5-10 seconds
✅ AI should respond with helpful property-related info
```

> 🎉 **Agent is live!** Repeat Steps A–D for each new agent.

---

## 🟠 Optional Settings (Per Agent)

*These have sensible defaults. Only change if needed.*

| Setting | Default | When to Change |
|---------|---------|----------------|
| 🤖 **AI Model** | GPT-4 (via OpenRouter) | Want cheaper/faster? Try `gpt-3.5-turbo` |
| 🌡️ **AI Temperature** | 0.7 | Lower (0.3) = more precise. Higher (0.9) = more creative |
| 📏 **Max Response Length** | 300 chars | Increase for detailed property descriptions |
| 🔄 **Auto-Reply** | Enabled | Disable for manual-only agents |
| ⏱️ **Online Threshold** | 5 minutes | How long before "agent is away" kicks in |
| 📊 **Airtable Full Access** | Yes | Restrict if agent shouldn't see all data |
| 📅 **Google Calendar ID** | primary | Change if agent uses a separate calendar |

> 💡 Tell Claude which settings to change and for which agent. It's a one-field update.

---

## 🔴 Troubleshooting

### ❓ "I sent a message but got no reply"

| Check | How |
|-------|-----|
| Is the workflow active? | n8n dashboard → workflow should show green "Active" |
| Is the agent record active? | Airtable → Agents → `is_active` = `true` |
| Is auto-reply on? | Airtable → Agents → `auto_reply` = `true` |
| Is the webhook connected? | Meta App → WhatsApp → Configuration → green checkmark |
| Is the phone number correct? | Airtable → Agents → `whatsapp_number` matches exactly |

### ❓ "Token expired" / "Unauthorized" errors

```
🔄 Go to developers.facebook.com → Your App → WhatsApp → Getting Started
🔑 Click "Generate" for a new temporary token
📋 Share the new token with Claude to update Airtable
```

> 🛡️ **For production:** Set up a System User token (never expires) via
> Meta Business Settings → System Users → Generate Token

### ❓ "Group messages are being ignored"

```
✅ This is by design! The workflow only processes direct (1-on-1) messages.
📱 Group messages are filtered out at Step 2 of the pipeline.
```

### ❓ "Agent shows as offline"

```
🕐 The system uses a 5-minute online threshold by default
📡 The agent's app needs to ping the status webhook:
   POST https://ianimmelman89.app.n8n.cloud/webhook/agent-status
   Body: { "agent_id": "agent_001", "status": "online" }
```

---

## 📋 Quick Reference

### Airtable Tables

| Table | Purpose | ID |
|-------|---------|-----|
| 🧑 Agents | Agent config + WhatsApp credentials | `tblHCkr9weKQAHZoB` |
| 💬 Message Log | All processed messages | `tbl72lkYHRbZHIK4u` |
| 🚫 Blocked Messages | Filtered/blocked messages | `tbluSD0m6zIAVmsGm` |
| ❌ Errors | System error tracking | `tblM6CJi7pyWQWmeD` |

### n8n Credentials

| Credential | Used By |
|------------|---------|
| 🗃️ Whatsapp Multi Agent (Airtable) | 11 Airtable nodes |
| 🤖 OpenRouter | AI Analysis node |
| 📤 Twilio | Send WhatsApp node |
| 🔒 Header Auth account 2 | Get Contact Info node |

### Key URLs

| URL | Purpose |
|-----|---------|
| `https://ianimmelman89.app.n8n.cloud/webhook/whatsapp-webhook` | Main message webhook |
| `https://ianimmelman89.app.n8n.cloud/webhook/agent-status` | Agent online/offline status |
| `https://ianimmelman89.app.n8n.cloud/webhook/agent-register` | Self-registration (extended version) |

---

## 🗺️ Full Onboarding Flow (Visual Summary)

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  🟡 WAITING: Facebook Business Verification             │
│                                                         │
└────────────────────────┬────────────────────────────────┘
                         │ ✅ Approved!
                         ▼
┌─────────────────────────────────────────────────────────┐
│  🔵 PHASE 1: First-Time Setup (~25 min)                 │
│                                                         │
│  Step 1 ✅ Business verified                            │
│  Step 2 📱 Twilio sandbox connected                     │
│  Step 3 🔑 3 WhatsApp values collected                  │
│  Step 4 🤖 Claude configures Airtable                   │
│  Step 5 🔗 Meta webhook → n8n                           │
│  Step 6 💬 Test message sent & replied                   │
│                                                         │
└────────────────────────┬────────────────────────────────┘
                         │ 🎉 System is LIVE!
                         ▼
┌─────────────────────────────────────────────────────────┐
│  🟣 PHASE 2: Add Agents (~2 min each)                   │
│                                                         │
│  Step A 📱 Register WhatsApp number in Meta             │
│  Step B 📋 Collect agent info (10 fields)               │
│  Step C 🤖 Claude adds Airtable row                     │
│  Step D 💬 Test message → AI replies                     │
│                                                         │
│  🔁 Repeat for each new real estate agent               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

*Last updated: February 2026*
*Workflow: WhatsApp Multi-Agent System (Optimized) — 36 nodes, n8n Cloud*

# Financial Advisory CRM - Setup Guide

## Prerequisites Checklist

- [ ] n8n Cloud account (ianimmelman89.app.n8n.cloud)
- [ ] Microsoft 365 Business account (with Teams + Outlook)
- [ ] Azure Portal access (portal.azure.com)
- [ ] WhatsApp Business API account (Meta Business Manager)
- [ ] Supabase project (qfvsqjsrlnxjplqefhon)
- [ ] OpenRouter API key

---

## 1. Azure AD App Registration

### Step 1: Create App
1. Go to https://portal.azure.com -> Azure Active Directory -> App registrations -> New registration
2. Name: `AnyVision FA CRM`
3. Supported account types: "Accounts in this organizational directory only" (Single tenant)
4. Redirect URI: `https://ianimmelman89.app.n8n.cloud/rest/oauth2-credential/callback`
5. Click Register

### Step 2: Note IDs
- **Application (client) ID** -> save as `AZURE_FA_CLIENT_ID`
- **Directory (tenant) ID** -> save as `AZURE_FA_TENANT_ID`

### Step 3: Create Client Secret
1. Certificates & secrets -> New client secret
2. Description: `n8n FA CRM`
3. Expires: 24 months
4. Copy the **Value** (not Secret ID) -> save as `AZURE_FA_CLIENT_SECRET`

### Step 4: API Permissions
Go to API permissions -> Add a permission -> Microsoft Graph -> Application permissions:

| Permission | Why |
|------------|-----|
| `Calendars.ReadWrite` | Create/read calendar events with Teams meetings |
| `OnlineMeetings.ReadWrite.All` | Create Teams meetings via calendar events |
| `OnlineMeetingTranscript.Read.All` | Read meeting transcripts (beta API) |
| `OnlineMeetingRecording.Read.All` | Read meeting recordings (beta API) |
| `Mail.Send` | Send emails via Outlook |
| `Mail.ReadWrite` | Read/manage emails |
| `ChannelMessage.Send` | Send Teams channel messages |
| `Chat.ReadWrite` | Manage Teams chats |
| `User.Read.All` | Resolve user profiles/IDs |

Then click **Grant admin consent** for the organization.

### Step 5: Enable Application Access Policy (for Teams)
In Microsoft Teams admin center, create an application access policy:
```powershell
New-CsApplicationAccessPolicy -Identity "FA-CRM-Policy" -AppIds "YOUR_CLIENT_ID" -Description "FA CRM n8n access"
Grant-CsApplicationAccessPolicy -PolicyName "FA-CRM-Policy" -Identity "adviser@yourdomain.com"
```

---

## 2. n8n Credential Setup

### Microsoft Outlook OAuth2 API
1. In n8n: Settings -> Credentials -> Add Credential -> Microsoft Outlook OAuth2 API
2. Fill in:
   - Client ID: `{AZURE_FA_CLIENT_ID}`
   - Client Secret: `{AZURE_FA_CLIENT_SECRET}`
   - Tenant ID: `{AZURE_FA_TENANT_ID}`
   - Scope: `https://graph.microsoft.com/.default`
3. Click "Connect" to authorize
4. Save -> note the credential ID
5. Set in `.env`: `N8N_CRED_OUTLOOK_FA={credential_id}`

### Microsoft Teams OAuth2 API
The same Outlook OAuth2 credential works for Teams nodes when used with `predefinedCredentialType`. If n8n requires a separate Teams credential:
1. Add Credential -> Microsoft Teams OAuth2 API
2. Same Client ID, Secret, Tenant ID
3. Save -> note the credential ID
4. Set in `.env`: `N8N_CRED_TEAMS_FA={credential_id}`

### OpenRouter (already exists)
Verify `OPENROUTER_API_KEY` is set in n8n environment variables.

### Supabase (via HTTP headers)
The FA workflows use Supabase REST API with service role key via HTTP headers.
Verify these n8n environment variables are set:
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

---

## 3. WhatsApp Business Setup

### Step 1: Meta Business Manager
1. Go to https://business.facebook.com -> WhatsApp -> Getting Started
2. Create or select a WhatsApp Business Account
3. Add a phone number for the advisory firm

### Step 2: Create Message Templates
In WhatsApp Manager -> Message Templates, create these 5 templates:

#### `fa_meeting_confirm`
Category: UTILITY
Body: `Hi {{1}}, your {{2}} meeting with {{3}} is confirmed for {{4}} at {{5}}. Join via Teams: {{6}}`
- {{1}} = client_first_name
- {{2}} = meeting_type
- {{3}} = adviser_name
- {{4}} = date
- {{5}} = time
- {{6}} = teams_url

#### `fa_reminder_24h`
Category: UTILITY
Body: `Reminder: Your financial advisory meeting is tomorrow at {{1}}. Teams link: {{2}}`
- {{1}} = time
- {{2}} = teams_url

#### `fa_reminder_1h`
Category: UTILITY
Body: `Your meeting starts in 1 hour at {{1}}. Join now: {{2}}`
- {{1}} = time
- {{2}} = teams_url

#### `fa_doc_request`
Category: UTILITY
Body: `Hi {{1}}, please upload your {{2}} to complete your FICA verification. Upload here: {{3}}`
- {{1}} = client_first_name
- {{2}} = document_type
- {{3}} = portal_url

#### `fa_welcome`
Category: MARKETING
Body: `Welcome to {{1}}! Your financial adviser {{2}} will be in touch shortly.`
- {{1}} = firm_name
- {{2}} = adviser_name

### Step 3: Get API Credentials
1. In Meta Business Manager -> WhatsApp -> API Setup
2. Copy **Phone Number ID** -> `FA_WHATSAPP_PHONE_NUMBER_ID`
3. Generate **Permanent Token** -> `FA_WHATSAPP_ACCESS_TOKEN`

---

## 4. Environment Variables

Add all of these to your `.env` file:

```bash
# Azure AD
AZURE_FA_TENANT_ID=your_tenant_id
AZURE_FA_CLIENT_ID=your_client_id
AZURE_FA_CLIENT_SECRET=your_client_secret

# n8n Credential IDs (after creating in n8n UI)
N8N_CRED_OUTLOOK_FA=your_outlook_cred_id
N8N_CRED_TEAMS_FA=your_teams_cred_id

# Firm
FA_FIRM_ID=ea0fbe19-4612-414a-b00f-f1ce185a1ea3

# WhatsApp
FA_WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
FA_WHATSAPP_ACCESS_TOKEN=your_permanent_token

# Webhook Security
N8N_WEBHOOK_SECRET=generate_a_random_32_char_string

# n8n Environment Variables (set in n8n Cloud Settings -> Variables)
# SUPABASE_ANON_KEY=your_anon_key
# SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
# OPENROUTER_API_KEY=your_openrouter_key
# FA_WHATSAPP_PHONE_NUMBER_ID=same_as_above
# FA_WHATSAPP_ACCESS_TOKEN=same_as_above
# FA_TEAMS_CHAT_ID=your_adviser_chat_id
# FA_FIRM_NAME=AnyVision Financial Advisory
# PORTAL_URL=https://portal.anyvisionmedia.com
# FA_COMPLIANCE_EMAIL=compliance@yourdomain.com
```

---

## 5. n8n Environment Variables

In n8n Cloud: Settings -> Variables, add:

| Variable | Value | Used By |
|----------|-------|---------|
| `SUPABASE_ANON_KEY` | Your Supabase anon key | All FA workflows |
| `SUPABASE_SERVICE_ROLE_KEY` | Your Supabase service role key | All FA workflows |
| `OPENROUTER_API_KEY` | Your OpenRouter API key | FA-03,04,05,06,08,10 |
| `FA_WHATSAPP_PHONE_NUMBER_ID` | WhatsApp phone number ID | FA-02,07a |
| `FA_WHATSAPP_ACCESS_TOKEN` | WhatsApp permanent token | FA-02,07a |
| `FA_TEAMS_CHAT_ID` | Adviser's Teams chat ID | FA-01,03,07b,08 |
| `FA_FIRM_NAME` | Advisory firm display name | FA-01 (emails) |
| `PORTAL_URL` | https://portal.anyvisionmedia.com | FA-01 (emails) |
| `FA_COMPLIANCE_EMAIL` | compliance@yourdomain.com | FA-08 |

---

## 6. Workflow Activation Order

**Phase A (safe - monitoring only):**
1. FA-07a Scheduled Reminders (`JjnhoxMX9R5Q0h0V`)
2. FA-08 Compliance Audit (`bmERknvAKhd4L54c`)
3. FA-10 Weekly Reporting (`jk8QDQyOP5VyAwGj`)

**Phase B (sub-workflows - called by others):**
4. FA-02 Meeting Scheduler (`2tbs2BASV132Hq9a`)
5. FA-03 Pre-Meeting Prep (`g0iJU06wQMbcqHdq`)
6. FA-07b Send Comms (`vfHepMY5AK9Z6D3P`)
7. FA-09 Document Management (`v0TfqXNNXsDvEgmh`)

**Phase C (entry point):**
8. FA-01 Client Intake (`0kXaGEfwAdTvSfD0`)

**Phase D (post-meeting - after real meetings happen):**
9. FA-04 Transcript Analysis (`9mh6mj96w8f4tmKU`)
10. FA-05 Post-Meeting Processing (`t7bgW9jDMCBdG0qQ`)
11. FA-06 Discovery Pipeline (`2JqMzIOnBbnINGvL`)

---

## 7. Testing Checklist

### Smoke Test (no real credentials needed)
- [ ] Open each workflow in n8n UI - verify all nodes load without errors
- [ ] Check all connections are correct (no orphan nodes)
- [ ] Verify sub-workflow IDs are set (not REPLACE_*)

### Integration Test (requires Azure AD + Supabase)
- [ ] FA-01: POST to webhook -> verify Supabase fa_clients record created
- [ ] FA-02: Manual trigger -> verify Outlook calendar event + Teams URL
- [ ] FA-07b: POST to webhook -> verify email sent via Outlook
- [ ] FA-08: Manual trigger -> verify compliance summary from Supabase RPC

### End-to-End Test
- [ ] Submit intake form -> FA-01 processes -> FA-02 books meeting
- [ ] Attend Teams meeting -> FA-04 retrieves transcript -> FA-05 sends summary
- [ ] Upload document -> FA-09 classifies -> FICA check runs
- [ ] Review weekly report from FA-10

---

## 8. Deployed Workflow IDs

| Workflow | n8n ID | Nodes |
|----------|--------|-------|
| FA-01 Client Intake | `0kXaGEfwAdTvSfD0` | 18 |
| FA-02 Meeting Scheduler | `2tbs2BASV132Hq9a` | 12 |
| FA-03 Pre-Meeting Prep | `g0iJU06wQMbcqHdq` | 10 |
| FA-04 Transcript Analysis | `9mh6mj96w8f4tmKU` | 16 |
| FA-05 Post-Meeting Processing | `t7bgW9jDMCBdG0qQ` | 12 |
| FA-06 Discovery Pipeline | `2JqMzIOnBbnINGvL` | 12 |
| FA-07a Scheduled Reminders | `JjnhoxMX9R5Q0h0V` | 14 |
| FA-07b Send Comms | `vfHepMY5AK9Z6D3P` | 9 |
| FA-08 Compliance Audit | `bmERknvAKhd4L54c` | 13 |
| FA-09 Document Management | `v0TfqXNNXsDvEgmh` | 11 |
| FA-10 Weekly Reporting | `jk8QDQyOP5VyAwGj` | 11 |
| Presentation Overview | `DhE0NMpGUUKVTmDB` | 74 |

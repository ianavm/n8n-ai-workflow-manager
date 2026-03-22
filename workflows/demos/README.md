# AVM Demo Workflows

Demo workflows for client presentations showcasing AnyVision Media's automation capabilities.

---

## WhatsApp -> AI -> CRM Pipeline

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

### Key Technologies Shown

| Technology | Usage |
|-----------|-------|
| **n8n Webhook** | Real-time HTTP endpoint for message intake |
| **OpenRouter / Claude Sonnet** | AI classification, order extraction, lead scoring, reply generation |
| **Airtable** | CRM record creation (orders and leads) |
| **Switch Router** | Intelligent multi-path routing based on AI output |
| **Code Nodes** | JSON parsing with error handling for AI responses |
| **Respond to Webhook** | Structured JSON response back to the caller |

### How to Use for Client Presentations

#### Option A: Import into n8n (Live Demo)

1. Open n8n Cloud (ianimmelman89.app.n8n.cloud)
2. Create a new workflow and import `whatsapp_ai_crm_demo.json`
3. Replace credential placeholders:
   - `REPLACE_WITH_OPENROUTER_CRED_ID` -> your OpenRouter httpHeaderAuth credential
   - `REPLACE_WITH_AIRTABLE_CRED_ID` -> your Airtable PAT credential
   - `REPLACE_WITH_BASE_ID` -> target Airtable base
   - `REPLACE_WITH_ORDERS_TABLE_ID` -> Orders table in Airtable
   - `REPLACE_WITH_LEADS_TABLE_ID` -> Leads table in Airtable
4. Activate the workflow
5. Send test requests via curl or Postman (see examples below)

#### Option B: Walkthrough (No Setup)

Open the workflow in n8n's editor view. The sticky notes explain each section. Walk through the flow visually:
- Start at "Receive WhatsApp Message" (left)
- Show the AI classification step
- Follow each branch to its outcome
- Highlight the Airtable CRM integration

### Test Payloads

**Order:**
```json
POST /webhook/whatsapp-incoming
{
  "sender_name": "John Smith",
  "phone": "+27821234567",
  "message": "Hi, I'd like to order 5 branded videos for our product launch next month. Budget is around R15,000."
}
```

**Lead:**
```json
POST /webhook/whatsapp-incoming
{
  "sender_name": "Sarah Johnson",
  "phone": "+27839876543",
  "message": "Hi there! I run a small restaurant in Fourways and I'm looking for help with social media marketing. What packages do you offer?"
}
```

**Inquiry:**
```json
POST /webhook/whatsapp-incoming
{
  "sender_name": "Mike van der Berg",
  "phone": "+27841112233",
  "message": "What are your business hours? And do you offer SEO services?"
}
```

**Complaint:**
```json
POST /webhook/whatsapp-incoming
{
  "sender_name": "Lisa Naidoo",
  "phone": "+27825556677",
  "message": "I'm very unhappy with the social media posts from last week. They had spelling errors and the wrong images were used. I want this fixed immediately."
}
```

### Client Talking Points

- **Zero manual sorting** - AI classifies every message automatically
- **Instant response** - Customers get a reply within seconds, 24/7
- **CRM integration** - Every order and lead is captured in Airtable automatically
- **Lead scoring** - AI evaluates lead quality so sales prioritizes hot leads first
- **Escalation** - Complaints are never lost; they get immediate priority routing
- **Scalable** - Handles hundreds of messages per hour with no additional staff
- **Customizable** - Classification categories, AI prompts, and CRM fields are all configurable

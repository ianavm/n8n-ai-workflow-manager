# Financial Advisory CRM - Demo Walkthrough Script

**Duration:** 20 minutes
**Audience:** Discovery Financial Advisory leadership, IT stakeholders
**Presenter:** Ian Immelman, AnyVision Media

---

## Setup (before the demo)

Open two browser tabs:

- **Tab 1:** Admin/Adviser Portal - https://portal.anyvisionmedia.com/admin/login
  - Login: `test@testemail.com` / `Password123!`
- **Tab 2:** n8n Cloud - https://ianimmelman89.app.n8n.cloud
  - Navigate to the "FA - Financial Advisory CRM (Presentation Overview)" workflow

Verify seed data is loaded (4 clients at various pipeline stages, 2 advisers, meetings with AI insights).

---

## Section 1: Opening (2 minutes)

### What to show
Switch to **Tab 2** (n8n). Open the Presentation Overview workflow canvas.

### Script

> "What you're looking at is the technical blueprint of a complete CRM automation system built specifically for financial advisory firms like Discovery."
>
> "This is not a generic off-the-shelf CRM. It was designed from the ground up around the South African regulatory environment -- FAIS and POPIA compliance are not bolt-on features, they're embedded into every workflow."
>
> "The system consists of 11 interconnected workflows with 138 automation nodes. They handle the entire advisory lifecycle: client intake, Teams meeting scheduling, transcript analysis with AI, compliance monitoring, document management, and weekly reporting."
>
> "Let me show you what this looks like from an adviser's perspective."

### Key points
- 11 workflows, 138 nodes
- South African regulatory compliance (FAIS + POPIA) built-in
- Microsoft 365 native (Teams, Outlook)
- AI-powered transcript analysis

---

## Section 2: Adviser Dashboard (3 minutes)

### What to show
Switch to **Tab 1**. Navigate to `/admin/advisory/my-dashboard`.

### Script

> "Every adviser gets their own personalized dashboard the moment they log in. No configuration needed -- it pulls data from their assigned clients automatically."
>
> *Point to each section:*
>
> "At the top we have the key numbers: 4 assigned clients, 3 upcoming meetings, the pipeline breakdown showing where each client sits in the advisory process, and critically -- overdue tasks highlighted in red."
>
> "This is a live view. When n8n processes a new intake form or books a meeting, this dashboard updates in real time via Supabase."
>
> "Notice the pipeline summary -- you can see at a glance how many clients are at each stage: lead, intake complete, discovery scheduled, active. This is the adviser's personal funnel."

### Key points
- Personalized per adviser via RLS (Row-Level Security)
- Real-time data from Supabase
- Pipeline visibility at a glance
- Overdue task tracking prevents things falling through the cracks

---

## Section 3: Client Pipeline (2 minutes)

### What to show
Navigate to `/admin/advisory/pipeline`.

### Script

> "This is the visual pipeline -- think of it as a kanban board for your clients."
>
> "Each card is a client. You can see their current stage, health score, and when they last moved. The stages follow the standard two-meeting advisory process: lead, contacted, intake complete, discovery scheduled, discovery complete, analysis, presentation scheduled, presentation complete, implementation, and active."
>
> "For a firm with 120 advisers and thousands of clients, this view can be filtered by adviser, by office, or by date range. Nothing gets lost."

### Key points
- Kanban-style visual pipeline
- 11 pipeline stages matching the two-meeting advisory process
- Filterable by adviser, office, date
- Health score per client (0-100)

---

## Section 4: Client Deep Dive (3 minutes)

### What to show
Navigate to `/admin/advisory/clients`. Click on **Sipho Nkosi** (active client).

### Script

> "Let's look at a real client profile. Sipho Nkosi -- he's an active client."
>
> *Scroll through the profile:*
>
> "We have the complete 360-degree view. Personal information, contact details, employment and income data, risk tolerance assessment, FICA verification status."
>
> "Scroll down -- dependents. Sipho has listed dependents with beneficiary allocations. This feeds directly into the financial needs analysis."
>
> "Existing products: three active policies across life insurance, retirement annuity, and medical aid. Each with provider, policy number, premium amount, cover amount, and review dates."
>
> "Meeting history: two completed meetings -- the discovery meeting and the presentation. Each one has the full record including Teams recording link, transcript, and AI-generated insights."
>
> "This is the single source of truth. No spreadsheets, no paper files, no information scattered across email threads."

### Key points
- Full personal, financial, and employment profile
- Dependents with beneficiary tracking
- Existing product portfolio
- Complete meeting history with recordings and transcripts
- FICA status tracking

---

## Section 5: AI Meeting Insights (3 minutes)

### What to show
Still on Sipho's profile. Click into the discovery meeting insights section.

### Script

> "This is where the AI really shines. After every Teams meeting, the system automatically retrieves the transcript and runs it through Claude Sonnet for analysis."
>
> "Look at what it extracts:"
>
> *Point to each section:*
>
> "**Priorities** -- what the client said matters most to them. Education funding for children, retirement planning, income protection."
>
> "**Objections** -- concerns raised during the meeting. 'Current premiums feel too high.' 'Not sure about locking money in a retirement annuity.' These are gold for the adviser preparing the presentation."
>
> "**Action items** -- specific follow-ups extracted from the conversation. 'Request updated Discovery Life quote.' 'Send GAP cover comparison.' These automatically become tasks assigned to the adviser."
>
> "**Compliance flags** -- the AI monitors for regulatory triggers. Did the adviser discuss fees? Was FAIS disclosure mentioned? Was risk tolerance assessed? If any of these are missing, the compliance officer gets flagged."
>
> "**Client sentiment** -- positive, neutral, concerned, or negative. Gives the adviser a quick read on how the meeting went."
>
> "**Key quotes** -- direct client quotes pulled from the transcript. Invaluable for preparing the Record of Advice."
>
> "All of this happens automatically. The adviser walks out of a Teams meeting and within minutes has a structured brief ready for follow-up."

### Key points
- Fully automatic -- no manual note-taking required
- Priorities, objections, action items, compliance flags, sentiment, key quotes
- Action items auto-convert to tasks
- Compliance flags route to compliance officer
- AI confidence score on each analysis

---

## Section 6: Tasks and Compliance (2 minutes)

### What to show
Navigate to `/admin/advisory/tasks`. Then switch to `/admin/advisory/compliance`.

### Script

> *On the tasks page:*
>
> "Every action item from meetings, every FICA follow-up, every document request -- they all land here as trackable tasks. Overdue items are highlighted. Each task has a due date, priority, and status."
>
> *Switch to compliance page:*
>
> "The compliance dashboard is the office manager's best friend. At a glance: how many clients are missing POPIA consent, how many lack FAIS disclosure, how many have unverified FICA, how many tasks are overdue."
>
> "FAIS and POPIA compliance is monitored daily by the automated compliance audit workflow. It runs every morning, checks every active client, and flags gaps. No more end-of-year scrambles for the FSCA."

### Key points
- Tasks auto-generated from AI meeting analysis
- Overdue task highlighting
- POPIA consent tracking per client
- FAIS disclosure verification
- FICA status monitoring
- Daily automated compliance audit (FA-08 workflow)

---

## Section 7: Multi-Office Support (2 minutes)

### What to show
Navigate to `/admin/advisory/offices`.

### Script

> "Discovery operates across multiple offices. This system handles that natively."
>
> "Each office is a separate entity with its own advisers, clients, and compliance metrics. The data is completely isolated at the database level using Row-Level Security -- an adviser in Sandton cannot see Pretoria's clients."
>
> "But as head office, you get this bird's-eye view. Total advisers per office, total clients, active clients, meetings this month, and a compliance score."
>
> "If Pretoria's compliance score drops below 80%, you know immediately. You can drill into that office to see exactly which advisers have gaps."

### Key points
- Per-office data isolation via Supabase RLS
- HQ cross-office visibility
- Compliance score per office
- Scalable to any number of offices
- Super admin role for head office oversight

---

## Section 8: Client Portal Preview (2 minutes)

### What to show
Open a new tab or incognito window. Navigate to https://portal.anyvisionmedia.com/portal/login.
Login as: `client@testemail.com` / `Password123!` (if client demo user exists).

### Script

> "Clients get their own secure portal. This is what Sipho sees when he logs in."
>
> "His dashboard shows upcoming meetings with a direct 'Join Teams Meeting' button. No hunting for links in email."
>
> "He can view his meeting insights -- a client-friendly summary, not the full adviser version. He can see his tasks, upload documents for FICA verification, review pricing proposals and accept them digitally."
>
> "The communications page shows every email and notification the system has sent. Full transparency."
>
> "For Discovery, this means fewer support calls. Clients can self-serve for the routine stuff -- checking meeting times, uploading documents, reviewing proposals."

### Portal routes demonstrated
- `/portal/advisory/dashboard` -- Overview with upcoming meetings
- `/portal/advisory/meetings` -- Meeting list with Teams join links
- `/portal/advisory/meetings/[id]` -- Individual meeting detail
- `/portal/advisory/documents` -- Document upload for FICA
- `/portal/advisory/pricing` -- Fee proposals
- `/portal/advisory/pricing/[id]` -- Accept/reject pricing
- `/portal/advisory/insights` -- Client-friendly meeting summaries
- `/portal/advisory/communications` -- Notification history
- `/portal/advisory/profile` -- Personal info management
- `/portal/advisory/tasks` -- Client-facing task list

### Key points
- Clients can join Teams meetings directly from the portal
- Document upload for FICA verification
- Digital fee acceptance flow
- Full communication history
- Reduces support burden on advisers

---

## Section 9: n8n Workflows (2 minutes)

### What to show
Switch to **Tab 2** (n8n). Show the Presentation Overview workflow canvas. Slowly scroll through the 7 sections.

### Script

> "Behind everything you just saw are these 11 workflows running on n8n Cloud."
>
> *Scroll through each section:*
>
> "**FA-01: Client Intake** -- a webhook receives the intake form, validates it, creates the client in Supabase, triggers POPIA consent, and auto-assigns an adviser."
>
> "**FA-02: Meeting Scheduler** -- creates Outlook calendar events with Teams meeting links. Sends confirmation via email and WhatsApp."
>
> "**FA-03: Pre-Meeting Prep** -- the day before a meeting, AI generates a briefing document for the adviser. Client history, existing products, open tasks, compliance status."
>
> "**FA-04: Transcript Analysis** -- after a Teams meeting ends, retrieves the transcript via Microsoft Graph API and runs Claude Sonnet analysis. Extracts priorities, objections, action items, compliance flags."
>
> "**FA-05: Post-Meeting Processing** -- sends the summary to the adviser, creates follow-up tasks, updates the pipeline stage."
>
> "**FA-06: Discovery Pipeline** -- takes the discovery meeting output, runs a financial needs analysis, generates the Record of Advice, calculates pricing, and schedules the presentation meeting."
>
> "**FA-07a/b: Reminders and Communications** -- scheduled reminders at 24h and 1h before meetings. Multi-channel: email via Outlook, WhatsApp via Meta Business API."
>
> "**FA-08: Compliance Audit** -- daily scan of all clients for POPIA consent, FAIS disclosure, FICA status, overdue tasks. Sends a compliance report to the office compliance officer."
>
> "**FA-09: Document Management** -- handles uploads, classifies documents by type, runs FICA verification checks."
>
> "**FA-10: Weekly Reporting** -- every Monday, generates a firm-wide report: pipeline movement, meeting activity, compliance metrics, adviser performance."

### Key points
- Each workflow is independently deployable and testable
- Sub-workflows keep logic modular (FA-02, FA-03, FA-07b, FA-09 are callable)
- Activation is phased: monitoring first, then sub-workflows, then entry points

---

## Section 10: Close (1 minute)

### Script

> "To summarize what we've built:"
>
> - "138 automation nodes handling the complete advisory lifecycle from first contact to active client management."
> - "FAIS and POPIA compliance built in from day one -- not retrofitted."
> - "Native Microsoft 365 integration. Teams meetings, Outlook calendar, Outlook email. No third-party bridging."
> - "AI-powered transcript analysis that turns a 60-minute Teams meeting into structured, actionable intelligence in minutes."
> - "Multi-office support with per-adviser dashboards and head office oversight."
> - "A client self-service portal that reduces support load and improves the client experience."
>
> "This is ready to deploy. Your Azure AD tenant, your branding, your data. Two to three weeks for a full rollout including staff training."
>
> "Questions?"

---

## Talking Points - Common Questions

### "How does this handle 120 advisers?"

> "The system runs on self-hosted n8n with unlimited workflow executions. The database is Supabase (PostgreSQL) which handles concurrent reads from hundreds of users without breaking a sweat. Row-Level Security means each adviser only sees their own clients -- the query planner handles the filtering at the database level, not in application code. We've load-tested with 500+ concurrent sessions."

### "What about data security?"

> "Three layers. First, Supabase Row-Level Security -- every table has RLS policies that enforce firm-level and role-level isolation. An adviser in one office physically cannot query another office's data. Second, audit logging on every mutation -- every create, update, and delete across all 16 tables is logged with who, when, and what changed. Third, POPIA consent tracking is a first-class entity in the database with grant/revoke timestamps, purpose, and expiry tracking."

### "How long to deploy?"

> "Two to three weeks for a full rollout. Week one: Azure AD app registration, n8n credential setup, database migration, seed data import. Week two: portal branding, adviser onboarding, workflow activation in phases. Week three: go-live with monitoring, staff training sessions, and fine-tuning. The database schema is a single migration file -- it runs in under 30 seconds."

### "What's the cost?"

> "Infrastructure is approximately R3,000/month. That covers n8n Cloud (R1,500), Supabase Pro (R500), Vercel hosting (R500), and OpenRouter AI credits (R500 at current usage). On top of that, each adviser needs a Microsoft 365 Business license for Teams and Outlook integration, which Discovery likely already has. There are no per-seat licensing fees for the CRM itself."

### "Can we customize it?"

> "Every firm gets a `config` JSONB column in the database. That controls branding (logo, colours), feature toggles (enable/disable WhatsApp, enable/disable client portal), default meeting duration, reminder timing, compliance rules, and more. The portal supports custom branding per firm. If Discovery wants a specific workflow change -- say, adding a third meeting type or integrating with an internal system -- that's a workflow modification, not a rebuild."

### "What if the AI makes a mistake in transcript analysis?"

> "Every AI insight includes a confidence score. Low-confidence items are flagged for human review. The adviser reviews and approves insights before they're finalized -- the AI assists, it doesn't decide. The compliance flags are conservative by design: they flag potential gaps, and the compliance officer confirms. False positives are better than missed compliance requirements."

### "Can clients book their own meetings?"

> "The current flow has the adviser initiating meeting bookings. Adding client self-scheduling is a single workflow addition -- a webhook endpoint that lets the client pick from available time slots on the adviser's Outlook calendar. The calendar integration already exists in FA-02. We can add this in a follow-up phase."

### "What happens if n8n goes down?"

> "n8n Cloud has 99.9% uptime SLA. If a workflow execution fails, n8n retries automatically up to 3 times. Failed executions are logged and visible in the n8n UI. The portal continues to work independently since it reads directly from Supabase. Critical workflows like compliance audit and reminders have error handling nodes that send alerts to the admin."

---

## Demo Environment Checklist

Before the demo, verify:

- [ ] Portal is accessible at https://portal.anyvisionmedia.com
- [ ] Admin login works: `test@testemail.com` / `Password123!`
- [ ] Client login works: `client@testemail.com` / `Password123!`
- [ ] Seed data is loaded: 4 clients, 2 advisers, meetings with insights
- [ ] n8n Cloud is accessible and Presentation Overview workflow is visible
- [ ] All advisory portal pages load without errors
- [ ] Meeting insights are populated for at least one client (Sipho Nkosi)

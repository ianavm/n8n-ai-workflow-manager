# Financial Advisory CRM - Executive Summary

**AnyVision Media | Automated Financial Advisory Management System**

---

## The Problem

Financial advisory firms manage complex, regulation-heavy client relationships across multiple advisers and offices. Today, most firms rely on spreadsheets, email threads, and manual processes that lead to:

- Compliance gaps discovered only during FSCA audits
- Lost meeting follow-ups and forgotten action items
- No single source of truth for client data
- Hours spent on administrative tasks instead of advising
- Poor visibility for office managers and head office

## The Solution

A purpose-built CRM automation system that handles the full advisory lifecycle -- from first contact to active client management -- with FAIS and POPIA compliance embedded at every step.

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Automation workflows | 11 |
| Total automation nodes | 138 |
| Database tables | 16 (with RLS on all) |
| Portal routes | 45 (20 advisory-specific) |
| Client portal pages | 12 (dashboard, meetings, documents, pricing, insights, comms, profile, tasks) |
| Admin portal pages | 8 (dashboard, clients, pipeline, meetings, tasks, compliance, offices, my-dashboard) |
| Regulatory frameworks | FAIS + POPIA |
| AI models used | Claude Sonnet (transcript analysis, pre-meeting prep, needs analysis) |
| Integrations | Microsoft Teams, Outlook, WhatsApp Business, OpenRouter |
| Deployment time | 2-3 weeks |
| Monthly infrastructure cost | ~R3,000 |

---

## Architecture

```
+------------------------------------------------------------------+
|                        CLIENT PORTAL                              |
|  (Next.js 16 + React 19 + Tailwind v4 on Vercel)                |
|                                                                   |
|  Adviser View            Client View                              |
|  +-----------------+     +-------------------+                    |
|  | My Dashboard    |     | Dashboard         |                    |
|  | Client List     |     | Meetings + Teams  |                    |
|  | Pipeline Board  |     | Documents Upload  |                    |
|  | Meeting Mgmt    |     | Pricing Accept    |                    |
|  | Task Tracker    |     | Insights          |                    |
|  | Compliance      |     | Communications    |                    |
|  | Multi-Office    |     | Profile           |                    |
|  +-----------------+     +-------------------+                    |
+-------------------------------+----------------------------------+
                                |
                      Supabase REST API
                      (RLS enforced)
                                |
+-------------------------------v----------------------------------+
|                     SUPABASE (PostgreSQL)                         |
|                                                                   |
|  16 tables with Row-Level Security                                |
|  fa_firms, fa_advisers, fa_clients, fa_adviser_clients,          |
|  fa_dependents, fa_client_products, fa_meetings,                 |
|  fa_meeting_insights, fa_tasks, fa_documents,                    |
|  fa_pricing, fa_consent_records, fa_communications,              |
|  fa_audit_log, fa_product_types, fa_fee_structures               |
|                                                                   |
|  RPC functions: dashboard, pipeline, compliance, cross-office     |
|  Audit triggers on all mutable tables                            |
|  Storage bucket: fa-documents (50MB, PDF/images/Office)          |
+-------------------------------+----------------------------------+
                                |
                      n8n API / Webhooks
                                |
+-------------------------------v----------------------------------+
|                     n8n CLOUD (11 Workflows)                      |
|                                                                   |
|  FA-01  Client Intake --------> FA-02  Meeting Scheduler          |
|           |                       |                               |
|           v                       v                               |
|  FA-06  Discovery Pipeline   FA-03  Pre-Meeting Prep              |
|           |                       |                               |
|           v                       v                               |
|  FA-05  Post-Meeting <------ FA-04  Transcript Analysis           |
|                                                                   |
|  FA-07a  Scheduled Reminders (24h + 1h)                          |
|  FA-07b  Send Comms (email + WhatsApp)                           |
|  FA-08   Compliance Audit (daily scan)                           |
|  FA-09   Document Management (classify + FICA check)             |
|  FA-10   Weekly Reporting (Monday summary)                       |
+-------------------------------+----------------------------------+
                                |
              +-----------------+-----------------+
              |                 |                 |
     Microsoft 365      OpenRouter AI      WhatsApp Business
     (Teams + Outlook)  (Claude Sonnet)    (Meta API)
```

---

## ROI Calculation

### Time saved per adviser per week

| Task | Manual (hours/week) | Automated (hours/week) | Savings |
|------|--------------------:|----------------------:|--------:|
| Meeting scheduling + calendar management | 2.0 | 0.0 | 2.0 |
| Meeting note transcription and summarization | 3.0 | 0.0 | 3.0 |
| Post-meeting follow-up emails | 1.5 | 0.0 | 1.5 |
| Client data entry and updates | 2.0 | 0.5 | 1.5 |
| Compliance record-keeping | 1.5 | 0.0 | 1.5 |
| Document collection and filing | 1.0 | 0.2 | 0.8 |
| Weekly reporting | 1.0 | 0.0 | 1.0 |
| Reminder calls/emails | 1.0 | 0.0 | 1.0 |
| Pipeline and task tracking | 1.0 | 0.3 | 0.7 |
| **Total** | **14.0** | **1.0** | **13.0** |

### Firm-level impact (120 advisers)

| Metric | Value |
|--------|-------|
| Hours saved per adviser per week | 13.0 |
| Hours saved firm-wide per week | 1,560 |
| Hours saved firm-wide per month | 6,240 |
| Estimated adviser hourly cost (loaded) | R450 |
| Monthly labour savings | R2,808,000 |
| Monthly system cost | R3,000 + M365 licensing |
| **Net monthly savings** | **~R2,805,000** |
| **Annual savings** | **~R33,660,000** |

*Note: Even at 50% efficiency capture (advisers redirecting saved time to revenue-generating activities), the ROI is over 1,000x.*

### Additional revenue uplift

- Advisers reclaim 13 hours/week for client-facing activities
- Faster pipeline velocity (automated follow-ups prevent stalled leads)
- Fewer compliance incidents (daily automated auditing vs annual manual review)
- Client retention improvement via proactive engagement and transparent portal

---

## Advisory Lifecycle: Manual vs Automated

| Step | Manual Process | CRM Automated | Improvement |
|------|---------------|---------------|-------------|
| **Lead capture** | Email or phone, manually entered into spreadsheet | Webhook intake form -> auto-create client in Supabase, assign adviser, send welcome email | Instant, zero data entry |
| **POPIA consent** | Paper form, filed in cabinet, manually tracked | Digital consent recorded with timestamp, auto-tracked, expiry alerts | Auditable, always current |
| **Meeting booking** | Back-and-forth emails, manually create calendar event | Automated Outlook event + Teams link, confirmation email + WhatsApp sent | 1 click, multi-channel confirmation |
| **Pre-meeting prep** | Adviser reviews scattered notes, old emails, product spreadsheet | AI generates briefing doc: client history, products, open tasks, compliance status | 5-page brief generated automatically |
| **Meeting recording** | Handwritten notes during meeting, typed up afterward | Teams auto-records, transcript retrieved via Graph API | No manual transcription |
| **Meeting analysis** | Adviser recalls from memory, writes notes next day | Claude Sonnet extracts priorities, objections, action items, compliance flags within minutes | Structured, consistent, immediate |
| **Follow-up tasks** | Adviser creates own to-do list (often forgotten) | Action items auto-created as tasks with due dates, assigned to adviser | Nothing falls through the cracks |
| **Compliance tracking** | Annual FSCA audit preparation, scramble to find records | Daily automated scan: POPIA, FAIS disclosure, FICA, overdue tasks. Real-time compliance score | Continuous compliance, not annual panic |
| **Document management** | Email attachments, paper copies, inconsistent filing | Upload to portal -> auto-classify by type -> FICA status updated | Searchable, secure, audit-ready |
| **Fee disclosure** | Paper document, client signs, filed | Digital pricing proposal, client accepts in portal, timestamped record | Transparent, traceable, instant |
| **Client communication** | Individual emails, no central record | All communications logged: email, WhatsApp, portal notifications | Full audit trail |
| **Reminders** | Adviser remembers (or doesn't) | Automated 24h and 1h reminders via email + WhatsApp | 100% delivery rate |
| **Reporting** | Manual spreadsheet compilation, hours of work | Automated weekly report: pipeline, meetings, compliance, performance | Monday morning, zero effort |
| **Multi-office oversight** | Separate spreadsheets per office, manual consolidation | Real-time cross-office dashboard with compliance scores | Instant visibility |
| **Record of Advice** | Adviser writes manually after presentation | AI generates draft from discovery meeting analysis + financial needs | Hours saved per client |

---

## Database Design Highlights

- **16 tables** with Row-Level Security on every table
- **Multi-tenant**: `firm_id` on all data tables, RLS enforces isolation
- **Audit logging**: immutable append-only `fa_audit_log` with triggers on all 10 mutable tables
- **Consent tracking**: `fa_consent_records` with grant/revoke timestamps, purpose, lawful basis, expiry
- **South African context**: ZAR currency, SA ID number, FICA status, marital regimes (in/out community, accrual)
- **Product catalogue**: 15 South African product types with provider options (Discovery, Sanlam, Old Mutual, Allan Gray, etc.)
- **Pipeline stages**: 11 stages matching the two-meeting advisory process (lead -> active)

## Security Posture

- Row-Level Security on all 16 tables (no application-level filtering)
- Audit trigger fires on every INSERT, UPDATE, DELETE across 10 tables
- POPIA consent tracked as a first-class entity with lawful basis and expiry
- Client documents in private Supabase storage bucket (50MB limit, allowed MIME types only)
- Portal authentication via Supabase Auth (bcrypt, JWT)
- Per-firm config JSONB allows feature toggles without code changes
- Adviser roles: adviser, compliance_officer, admin, office_manager, super_admin

## Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Automation | n8n Cloud | Visual workflow builder, unlimited executions, self-hostable |
| Database | Supabase (PostgreSQL 15) | RLS, real-time subscriptions, built-in auth, storage |
| Portal | Next.js 16 + React 19 | Server components, fast builds, Vercel deployment |
| Styling | Tailwind v4 | Utility-first, consistent design, dark mode support |
| AI | Claude Sonnet via OpenRouter | Best-in-class reasoning for transcript analysis |
| Calendar | Microsoft Graph API | Native Teams + Outlook integration |
| Messaging | WhatsApp Business API | Approved template messages, high open rate |
| Hosting | Vercel (portal), n8n Cloud (workflows) | Zero-config, auto-scaling |

---

## Deployment Phases

| Phase | Duration | What |
|-------|----------|------|
| Phase A | Week 1 | Azure AD setup, n8n credentials, database migration, seed data |
| Phase B | Week 1-2 | Portal branding, adviser account creation, WhatsApp template approval |
| Phase C | Week 2 | Activate monitoring workflows (reminders, compliance, reporting) |
| Phase D | Week 2-3 | Activate intake + meeting workflows, staff training |
| Phase E | Week 3 | Go-live, activate transcript analysis, full pipeline |

---

**Contact:** Ian Immelman | ian@anyvisionmedia.com | AnyVision Media

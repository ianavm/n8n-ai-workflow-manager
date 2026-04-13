# AnyVision Media — n8n Workflow Manager

> **Owner:** Ian Immelman (ian@anyvisionmedia.com)
> **Framework:** WAT (Workflows, Agents, Tools) — see `CLAUDE.md file.md` for full philosophy
> **n8n Instance:** `ianimmelman89.app.n8n.cloud`

## Architecture

| Layer | Location | Role |
|-------|----------|------|
| **Workflows** | `workflows/` | Markdown SOPs + n8n JSON exports, organized by department |
| **Agents** | Claude (you) | Reads SOPs, orchestrates tools, makes decisions |
| **Tools** | `tools/` | Python scripts for deterministic execution (deploy, fix, monitor, analyze) |

**Core principle:** Probabilistic AI handles reasoning; deterministic Python handles execution. Never chain 5+ AI steps when a script can do it reliably.

## File Map

```
tools/                    Python scripts (see patterns below)
  n8n_client.py           Core API client (httpx, caching, retries)
  run_manager.py          CLI entry: status | monitor | analyze | report | deploy | docs | ai-audit
  workflow_deployer.py    Deploy/export/activate workflows
  execution_monitor.py    Execution monitoring & failure detection
  deploy_*.py             Programmatic workflow builders (per-department)
  fix_*.py                Live workflow patch scripts
  setup_*.py              Airtable base/table creation scripts

workflows/                n8n JSON exports + SOPs
  accounting-dept/        7 workflows (wf01-wf07): invoicing, collections, reconciliation, bills, month-end, audit, exceptions
  marketing-dept/         4 workflows (wf01-wf04): intelligence, strategy, content, distribution
  seo-social-dept/        8 workflows (wf05-wf11 + wf_score): trend discovery, SEO content, publishing, engagement, lead capture, SEO maintenance, analytics, scoring engine
  lead-scraper/           Google Places API scraper (workflow_v2_places_api.json)
  email_classifier_outlook.json   Outlook email classification + routing
  *.md                    SOPs (deployment, monitoring, troubleshooting, AI optimization)

templates/                HTML email templates (accounting + lead outreach), {{placeholder}} vars for n8n
client-portal/            Next.js 16 + Supabase + Tailwind v4 (portal.anyvisionmedia.com)
landing-pages/            Static HTML site on Netlify (www.anyvisionmedia.com)
  deploy/                 Production deployment directory

config.json               Non-secret config: n8n instances, AI models, Airtable base IDs, schedules
.env                      All secrets: API keys, OAuth tokens, Airtable table IDs
.env.template             Template showing required env vars
```

## Reference Resources

### GitHub Access (`Github Access/`, gitignored)
Local copies of reference repos — read-only, for extracting patterns and docs:
- `n8n-master/` — Full n8n source. Node implementations at `packages/nodes-base/nodes/`
- `n8n-workflows-main/` — **4,343 production workflows** in 188 categories. Search `workflows/` by integration folder (Gmail, Airtable, Googlesheets, Openai, Webhook, etc.)
- `ultimate-n8n-ai-workflows-main/` — **3,400+ AI-first workflows**. Key: `workflows/ai-agents/` (by category), `automation/` (948 numbered), `New Workflow/` (56 flagship with READMEs), `gsc-ai-seo-writer/`, `docs/prompt-engineering-tips.md`
- `context7-master/` — MCP server for live API docs (added to `.mcp.json`)
- `awesome-claude-skills-master/` — 40+ Claude skills (skill-creator, mcp-builder, document-skills)
- `LightRAG-main/` — RAG framework with knowledge graphs, PostgreSQL backend
- `n8n-docs/` — Official n8n documentation source (cloned)

### MCP Servers (`.mcp.json`)
GitHub, Supabase, Airtable, Playwright, Context7 (live API docs), n8n (workflow management), QuickBooks (accounting API), Google Workspace (Gmail, Sheets, Slides, Calendar, Drive, Docs)

## Active Departments

### LinkedIn Lead Intelligence (10 workflows)
- Multi-agent AI pipeline: discovery → enrichment → ICP scoring → pain detection → opportunity mapping → outreach → prioritization → CRM sync
- Pipeline: LI-01 Orchestrator (Mon 07:00 SAST) calls LI-02 through LI-09 sequentially, LI-10 (feedback) runs independently
- AI: Claude Sonnet 4 via OpenRouter (6 AI nodes across LI-03 to LI-07 + LI-10)
- Storage: Google Sheets (`133K-AiWyvCaeD8Y_SCzDT7Huxz-TrBY6CXn10jY81uE`) with 10 tabs
- Notifications: Telegram (@AVMCRMBot, chat 6311361442) + Gmail summary
- Deploy: `python tools/deploy_linkedin_dept.py build|deploy|activate`
- Setup: `python tools/setup_linkedin_airtable.py` (original Airtable setup, replaced by Google Sheets)

### Accounting (7 workflows)
- Full AP/AR: invoicing → collections → payments → supplier bills → month-end → audit → exceptions
- Integrations: QuickBooks (OAuth), Airtable, Gmail, HTML email templates
- Context: South African business (ZAR currency, 15% VAT)
- Auto-approve bills < R10,000; escalate > R50,000

### Marketing (4 workflows)
- Pipeline: intelligence (Mon 7:30) → strategy (daily 8:30) → content (daily 9:00) → distribution (daily 10:00)
- AI: Claude Sonnet via OpenRouter (50k daily token budget)
- Publishing: Blotato → TikTok, Instagram, Facebook

### SEO + Social Growth Engine (8 workflows)
- Pipeline: trend discovery (Mon/Thu 6:00) → content production (daily 9:30) → publishing (daily 10:30) → engagement monitoring (every 30min)
- Additional: lead capture (webhook), SEO maintenance (Sun 2:00), analytics & reporting (Mon 6:00)
- Scoring engine sub-workflow: engagement/lead/SEO/composite scores (0-100)
- Airtable: 8 new tables in marketing base (Keywords, SERP Snapshots, Engagement Log, Leads, SEO Audits, Analytics Snapshots, Scoring Log, Content Topics)
- Integrations: SerpAPI, Google PageSpeed API, Blotato (9 platforms), OpenRouter/Claude, Gmail
- Deploy: `python tools/deploy_seo_social_dept.py build|deploy|activate`
- Setup: `python tools/setup_seo_social_airtable.py --seed`

### Social Content Trend Replication (5 workflows)
- Pipeline: trend discovery (daily 6AM) → script extraction → brand adaptation → video production (daily 7AM) → distribution (daily 8AM)
- Discovery: YouTube Data API + Apify Instagram hashtag scraper + Tavily LinkedIn search
- AI: Claude Sonnet via OpenRouter (script extraction, brand adaptation, caption generation)
- Video: Remotion render server (TextOnScreen, QuoteCard, StatGraphic, TalkingHeadOverlay compositions)
- Publishing: Blotato → Instagram, LinkedIn, YouTube (video + platform-specific captions)
- Airtable: 3 tables in marketing base (SC_Trending_Content, SC_Adapted_Scripts, SC_Production_Log)
- Deploy: `python tools/deploy_social_content_dept.py build|deploy|activate`
- Setup: `python tools/setup_social_content_airtable.py --seed`

### Lead Scraper
- Google Places API → Airtable (`app2ALQUP7CKEkHOz`) + Google Sheets
- Targets: Fourways, Johannesburg businesses
- AI cold email generation via Claude Sonnet → Gmail delivery

### Email Classifier (Outlook)
- Polls Outlook every minute via Microsoft Graph
- GPT classifies: department, intent, urgency, tone, spam detection
- Routes to: Accounting_Finance, Customer_Support, Sales, Management, Spam_Irrelevant

### WhatsApp Multi-Agent (INACTIVE)
- 36-node real estate agent system on n8n Cloud
- GPT-4 analysis, Airtable agent profiles
- Status: Pending WhatsApp Business verification; missing Twilio credentials

## Tech Stack

**Core:** n8n Cloud, Python 3, Airtable
**AI:** OpenRouter (preferred) → Claude Sonnet (`anthropic/claude-sonnet-4-20250514`) for qualification/code, GPT-4o for conversation
**Integrations:** QuickBooks, Gmail OAuth, Outlook OAuth, Blotato, Google Places API, WhatsApp Business API, Google Slides/Calendar, SerpAPI, Google PageSpeed API
**Client Portal:** Next.js 16, React 19, TypeScript, Supabase (PostgreSQL + Auth + RLS), Tailwind v4, Recharts
**Hosting:** n8n Cloud (workflows), Vercel (client portal), Netlify (landing pages)

## Development Patterns

### Deploy scripts (`tools/deploy_*.py`)
1. Load `.env` via `python-dotenv`
2. Define `build_nodes()` → returns list of n8n node dicts
3. Define `build_connections()` → returns connection map
4. CLI: `build` (save JSON), `deploy` (POST to n8n API), `activate` (enable triggers)
5. Output: `workflows/{dept}/*.json`

### Fix scripts (`tools/fix_*.py`)
1. Fetch live workflow JSON from n8n by workflow ID
2. Build `node_map = {n["name"]: n for n in nodes}`
3. Mutate specific nodes by name
4. Push patched workflow back to n8n

### General
- All scripts use `N8nClient` from `tools/n8n_client.py` for API calls
- Auth: `X-N8N-API-KEY` header
- Airtable base/table IDs come from `.env`
- n8n credential IDs are hardcoded constants in deploy scripts (not secrets, just internal n8n refs)

## Operating Rules

1. **Check `tools/` first** before building anything new
2. **Search workflow libraries** — Before building a new workflow from scratch, search `Github Access/n8n-workflows-main/workflows/` and `Github Access/ultimate-n8n-ai-workflows-main/` for existing patterns to adapt
3. **Never chain 5+ AI steps** — use a Python script instead
4. **Ask before creating/overwriting workflows** — SOPs are preserved and refined, not replaced
5. **Secrets in `.env` only** — never hardcode API keys
6. **Cloud-first deliverables** — final outputs go to Google Slides, email, etc.
7. **`.tmp/` is disposable** — everything there can be regenerated
8. **Read the full WAT framework** in `CLAUDE.md file.md` for detailed philosophy
9. **Deploy script is source of truth** — ANY fix to a live n8n workflow MUST be simultaneously applied to `tools/deploy_*.py` and `.env`. Fixes applied only to live workflows are wiped on redeployment. After every deploy, run at least one live execution to validate.
10. **No `$env` in Code nodes** — n8n Cloud blocks environment variable access in JavaScript Code nodes. Hardcode values or pass via upstream node parameters.

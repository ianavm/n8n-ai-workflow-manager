# n8n AI Workflow Manager

Production AI automation platform running **196 workflows across 44 departments** — from multi-agent lead intelligence to self-healing error recovery. Built on the **WAT framework** (Workflows, Agents, Tools), where probabilistic AI handles reasoning and deterministic Python handles execution.

## Architecture

```text
┌─────────────────────────────────────────────────────┐
│                    WAT Framework                     │
├──────────────┬──────────────────┬────────────────────┤
│  Workflows   │     Agents       │      Tools         │
│  (n8n JSON)  │  (Claude / GPT)  │    (Python)        │
│              │                  │                    │
│  196 workflow│  Read SOPs,      │  Deploy, monitor,  │
│  definitions │  orchestrate     │  analyze, fix,     │
│  across 44   │  tools, make     │  report — all      │
│  departments │  decisions       │  deterministic     │
└──────────────┴──────────────────┴────────────────────┘
         ▲               │               │
         │          Reads SOPs      Executes via
         │          & context       n8n REST API
         │               │               │
         └───────────────┴───────────────┘
              Feedback loop: execution
              results inform next AI decision
```

**Core principle:** Never chain 5+ AI steps when a Python script can do it reliably.

## Key AI Systems

### Multi-Agent LinkedIn Lead Intelligence (10 workflows)

End-to-end pipeline: discovery → enrichment → ICP scoring → pain detection → opportunity mapping → outreach generation → prioritization → CRM sync → feedback loop. Claude Sonnet handles qualification scoring across 6 AI nodes. Weekly orchestrator triggers the full chain.

### Self-Healing Workflow Engine (AWE)

Autonomous error detection and repair system. 6-stage pipeline with 27 auto-fix patterns, health monitoring across all workflows, and automatic recovery for common failure modes (credential expiry, API rate limits, schema drift, expression errors).

### AI Content Pipeline (6 workflows)

Trend discovery (YouTube + Instagram + LinkedIn) → AI script extraction → brand voice adaptation → Remotion video rendering → multi-platform distribution via Blotato (Instagram, LinkedIn, YouTube, Facebook, TikTok).

### Paid Advertising Intelligence (11 workflows)

AI strategy generation → copy/creative production → campaign building (Google + Meta) → performance monitoring → optimization → creative recycling → attribution → reporting → budget enforcement with real-time spend caps.

### AI-Powered Accounting (10 workflows)

Full AP/AR automation: sales invoicing → collections → payment reconciliation → supplier bill intake → month-end close → master data audit → exception handling. QuickBooks integration, auto-approve below thresholds, escalation above.

### Personal Ops + Gamification

100 Day Challenge execution system with XP tracking, streak mechanics, boss battles, and adaptive difficulty. Morning mission board → midday check-in → evening review → adaptive tuning. Telegram bot for tap-to-complete.

## Tech Stack

| Layer | Stack |
|-------|-------|
| **Orchestration** | n8n Cloud (196 workflows) |
| **AI** | Claude Sonnet via OpenRouter, GPT-4o for conversation |
| **Scripting** | Python 3 (deploy, monitor, fix, analyze) |
| **Data** | Airtable, Supabase (PostgreSQL), Google Sheets |
| **Integrations** | QuickBooks, Gmail, Outlook, Google Workspace, Meta Ads, Google Ads, Blotato, Apify, SerpAPI, Telegram, WhatsApp Business API |
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind v4 (client portal) |
| **Hosting** | n8n Cloud, Vercel, Netlify, Railway |

## Project Structure

```text
tools/                          Python execution layer
  n8n_client.py                 Core API client (httpx, caching, retries)
  deploy_*.py                   Programmatic workflow builders (per department)
  fix_*.py                      Live workflow patch scripts
  setup_*.py                    Airtable table creation scripts
  run_manager.py                CLI: status | monitor | analyze | report

workflows/                      n8n JSON exports organized by department
  linkedin-dept/                10 workflows — lead intelligence pipeline
  ads-dept/                     11 workflows — paid advertising
  accounting-dept/              8 workflows — AP/AR automation
  seo-social-dept/              8 workflows — SEO + social growth
  social-content-dept/          6 workflows — trend replication pipeline
  personal-ops-dept/            5 workflows — gamified daily ops
  re-operations/                19 workflows — real estate ops
  financial-advisory/           12 workflows — FA CRM
  ...and 36 more departments

templates/                      HTML email templates (accounting + outreach)
client-portal/                  Next.js + Supabase client dashboard
landing-pages/                  Static marketing site (Netlify)

.claude/                        AI agent configurations
  agents/                       11 specialized agents (planner, architect, TDD, security...)
  commands/                     Custom Claude Code commands
  skills/                       40+ skills (brainstorming, debugging, deployment...)
```

## How It Works

**Deploy pattern** — Every department has a Python deployer that generates n8n-compatible JSON:

```bash
python tools/deploy_linkedin_dept.py build    # Generate workflow JSONs
python tools/deploy_linkedin_dept.py deploy   # Push to n8n via API
python tools/deploy_linkedin_dept.py activate # Enable triggers
```

**Fix pattern** — Patch live workflows without full redeployment:

```bash
python tools/fix_credential_ids.py            # Fix stale credential refs
python tools/fix_all_credentials.py           # Bulk credential update
```

**Monitor pattern** — Real-time health checks:

```bash
python tools/run_manager.py status            # Quick health check
python tools/run_manager.py monitor           # Execution monitoring
python tools/run_manager.py analyze           # Deep performance analysis
```

## Design Decisions

- **Deploy script is source of truth** — Any fix to a live workflow must also be applied to the deploy script. Live-only fixes are wiped on redeployment.
- **No `$env` in Code nodes** — n8n Cloud blocks environment variable access in JavaScript. Values are passed via upstream node parameters or hardcoded in the deployer.
- **OpenRouter as AI gateway** — Single API key, model switching without credential changes, cost tracking across providers.
- **Airtable for operational data, Supabase for structured data** — Airtable's flexibility for rapidly evolving schemas; PostgreSQL for relational integrity.

## Scale

- **196 workflow definitions** across 44 departments
- **108 commits** of iterative development
- **~30 Python tools** for deployment, monitoring, and analysis
- **11 Claude Code agents** for development assistance
- **40+ skills** for specialized tasks (brainstorming, debugging, security review, video production)

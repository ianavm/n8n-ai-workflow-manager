# System Overview — AVM Autonomous Workflow Engineer

## What This System Does

The Autonomous Workflow Engineer (AWE) is a control layer that sits on top of AnyVision Media's existing n8n automation platform and Python toolchain. It enables Claude Code to autonomously manage the full workflow lifecycle — from design through deployment, monitoring, repair, and optimization — within controlled safety boundaries.

AWE does **not** replace the existing infrastructure. It wraps and orchestrates it:

| Existing Tool | AWE Uses It For |
|---|---|
| `tools/n8n_client.py` | All n8n API operations (CRUD, executions, health) |
| `tools/execution_monitor.py` | Failure detection, error pattern tracking |
| `tools/orchestrator_kpi_engine.py` | Per-agent health scores, anomaly detection |
| `tools/intelligence_engine.py` | Cross-department analytics, forecasting |
| `tools/agent_registry.py` | Agent metadata, escalation chains, safety caps |
| `tools/workflow_deployer.py` | Deploy, export, activate, deactivate workflows |
| `tools/deploy_*.py` (28 scripts) | Department-specific workflow builders |

## What Can Be Fully Automated

| Action | Autonomy Level | Notes |
|---|---|---|
| Monitoring & anomaly detection | Full | Already exists via KPI engine + execution monitor |
| Incident classification | Full | Pattern matching on known error types |
| Documentation updates | Full | SOPs, changelogs, architecture docs |
| Test generation & execution | Full | Node config validation, schema checks |
| Retry tuning & logging improvements | Full | Non-breaking, easily reversible |
| Workflow spec generation from request | Full | Draft specs from business requirements |
| Performance analysis & recommendations | Full | Identify bottlenecks, suggest fixes |

## What Should Stay Supervised

| Action | Reason |
|---|---|
| Production deployment of new workflows | Risk of breaking live automations |
| Payment/invoice logic changes | Financial impact (ZAR caps, VAT, compliance) |
| Credential changes | Security-sensitive, hard to rollback |
| Deleting live workflows | Irreversible |
| Ad budget or bid changes > safety caps | Direct spend impact (R2K/day, R10K/week caps) |
| Schema changes (Airtable, Supabase) | Downstream data breakage |
| API credential rotation | Requires cross-system coordination |

## Maturity Path

```
Phase 0: ADVISORY (NOW)
  └─ AWE observes, reports, and recommends
  └─ All actions require human approval
  └─ Focus: build trust, validate recommendations

Phase 1: SEMI-AUTONOMOUS (Week 3-6)
  └─ Low-risk actions execute automatically
  └─ Medium-risk actions propose + wait for approval
  └─ High-risk actions advisory only
  └─ Focus: close feedback loops, measure accuracy

Phase 2: AUTONOMOUS WITHIN BOUNDS (Month 2-3)
  └─ Full execution loops for low/medium risk
  └─ Self-healing for known failure patterns
  └─ Optimization within policy guardrails
  └─ Focus: expand coverage, refine policies

Phase 3: SELF-IMPROVING (Month 4+)
  └─ Pattern library grows from resolved incidents
  └─ Prompt refinement based on outcome data
  └─ Proactive revamp recommendations
  └─ Focus: reduce human touchpoints to security/financial decisions only
```

## Key Constraints

1. **n8n Cloud limitations** — No `$env` in Code nodes; environment variables passed via parameters or hardcoded
2. **Deploy script is source of truth** — Any fix to a live workflow MUST be simultaneously applied to `tools/deploy_*.py` and `.env`
3. **Safety caps are non-negotiable** — Ad spend (R2K/day), auto-approve invoices (< R10K), escalate (> R50K)
4. **Token budgets** — 22 agents share ~200K tokens/day across opus/sonnet/haiku; AWE orchestration uses separate budget
5. **Single operator** — System designed for Ian + Claude Code, not a team; approval gates route to `ian@anyvisionmedia.com`
6. **WAT principle** — Probabilistic AI handles reasoning; deterministic Python handles execution. Never chain 5+ AI steps when a script can do it reliably

## System Boundary

```
┌─────────────────────────────────────────────────────────────┐
│                     CLAUDE CODE (AWE)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Planner  │ │ Builder  │ │ Debugger │ │ Monitor/     │  │
│  │          │ │          │ │          │ │ Optimizer    │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘  │
│       │             │            │               │          │
│  ┌────▼─────────────▼────────────▼───────────────▼───────┐  │
│  │              ORCHESTRATION ENGINE                      │  │
│  │  (autonomous/engine.py — task routing, loop control)   │  │
│  └──────────────────────┬────────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────▼────────────────────────────────┐  │
│  │            EXISTING PYTHON TOOLCHAIN                   │  │
│  │  n8n_client · execution_monitor · kpi_engine          │  │
│  │  intelligence_engine · agent_registry · deployer      │  │
│  └──────────────────────┬────────────────────────────────┘  │
│                         │                                   │
└─────────────────────────┼───────────────────────────────────┘
                          │
              ┌───────────▼───────────┐
              │    EXTERNAL SYSTEMS   │
              │  n8n Cloud · Airtable │
              │  Gmail · Google Sheets│
              │  Supabase · Telegram  │
              └───────────────────────┘
```

## Current Scale

- **22 agents** across 7 tiers (21 enabled, 1 inactive)
- **~70 deployed workflows** across 7 departments
- **8 Airtable bases** with ~40 tables
- **28 deploy scripts** (source of truth for workflow definitions)
- **3 monitoring engines** (execution, KPI, intelligence)

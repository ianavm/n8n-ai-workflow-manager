# AWE — Autonomous Workflow Engineer

A control layer that sits on top of AnyVision Media's n8n automation platform and Python toolchain, enabling Claude Code to autonomously manage the full workflow lifecycle — from monitoring through repair, optimization, and revamp — within controlled safety boundaries.

## What This System Does

AWE wraps existing tools (`n8n_client`, `execution_monitor`, `kpi_engine`, `intelligence_engine`, `agent_registry`, `workflow_deployer`) into an autonomous pipeline:

```
DETECT → CLASSIFY → SCORE → GOVERN → FIX → VERIFY → LOG
```

At **Tier 1 (Advisory)**, AWE proposes fixes without applying them. At higher tiers, low-risk known-pattern fixes are applied automatically. Financial and security-sensitive changes always require human approval.

## Quick Start

```bash
# 1. Initialize memory directories
python -m autonomous init

# 2. Seed known n8n failure patterns
python -m autonomous seed

# 3. Check system health
python -m autonomous status

# 4. Detect current issues (read-only)
python -m autonomous monitor

# 5. Run repair loop (Tier 1 = proposals only)
python -m autonomous repair

# 6. View decision audit trail
python -m autonomous audit

# 7. List registered patterns
python -m autonomous patterns

# 8. Show/set autonomy tier
python -m autonomous tier        # show current
python -m autonomous tier 2      # set to Tier 2
```

## Architecture

**Hybrid single-agent** — One Claude Code session with role-switching via prompt templates. Not multiple LLM instances. See [ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
┌──────────────────────────────────┐
│      AWE Orchestration Layer     │
│  engine.py · cli.py · config.yaml│
├──────────────────────────────────┤
│  Prompts (14) │ Policies (8)    │
│  Templates (3) │ Memory (JSON)  │
├──────────────────────────────────┤
│    Existing Python Toolchain     │
│  n8n_client · execution_monitor  │
│  kpi_engine · intelligence_engine│
│  agent_registry · deployer · ... │
└──────────────────────────────────┘
```

## Directory Structure

```
autonomous/
├── engine.py              # Core orchestration (detect/classify/score/govern/fix/verify/log)
├── cli.py                 # CLI: status, monitor, repair, audit, patterns, seed, tier, init
├── config.yaml            # Governance, confidence, monitoring, repair settings
├── __init__.py
├── __main__.py            # python -m autonomous entry point
│
├── docs/                  # Design documents
│   ├── SYSTEM_OVERVIEW.md    # Executive summary
│   ├── ARCHITECTURE.md       # Full system architecture
│   ├── OPERATING_MODEL.md    # 9 operational scenarios
│   ├── MEMORY_MODEL.md       # Memory structures & storage
│   ├── EXECUTION_LOOPS.md    # 4 loops, 41 stages
│   ├── TEST_STRATEGY.md      # 9 test categories, 4 scoring frameworks
│   ├── OBSERVABILITY_SPEC.md # Monitoring, anomaly detection, dashboards
│   ├── ROADMAP.md            # 4-phase implementation plan
│   └── START_THIS_WEEK.md    # Immediate action plan
│
├── policies/              # Safety guardrails
│   ├── AUTONOMY_POLICY.md    # 5 tiers with upgrade/downgrade criteria
│   ├── CHANGE_RISK_MATRIX.md # Low/medium/high/prohibited classification
│   ├── APPROVAL_MATRIX.md    # 50 actions with approval conditions
│   ├── DEPLOYMENT_POLICY.md  # 6-step deploy process
│   ├── ROLLBACK_POLICY.md    # 4 rollback methods
│   ├── INCIDENT_SEVERITY.md  # P1-P4 definitions with SLAs
│   ├── SECRETS_POLICY.md     # Secret management rules
│   └── REVAMP_POLICY.md      # Rebuild vs patch criteria
│
├── prompts/               # Agent prompt templates (14)
│   ├── PROMPT_REGISTRY.md    # Index of all prompts
│   ├── planner.md            # Business request → spec draft
│   ├── researcher.md         # Pattern search
│   ├── spec_writer.md        # Draft → formal spec
│   ├── builder.md            # Spec → n8n JSON + deploy script
│   ├── validator.md          # Structural + policy validation
│   ├── tester.md             # Test generation + execution
│   ├── debugger.md           # Root cause diagnosis + fix
│   ├── optimizer.md          # Performance improvements
│   ├── revamp_agent.md       # Rebuild vs patch assessment
│   ├── deployer.md           # Build → deploy → activate
│   ├── rollback_agent.md     # Revert to previous state
│   ├── documentation_agent.md# SOP + changelog maintenance
│   ├── incident_responder.md # First responder triage
│   └── monitoring_analyst.md # KPI interpretation + anomaly detection
│
├── templates/             # Structured templates
│   ├── WORKFLOW_SPEC_TEMPLATE.md  # Workflow spec (with ADS-01 example)
│   ├── INCIDENT_TEMPLATE.md       # Incident report (with JSON schema)
│   └── TEST_CASE_TEMPLATE.md      # Test case (with 3 examples)
│
├── scripts/               # Setup and maintenance scripts
│   ├── seed_patterns.py      # Seed known n8n failure patterns
│   └── init_memory.py        # Create memory directory structure
│
├── memory/                # Persistent operational state (JSON)
├── playbooks/             # Known failure patterns + resolution recipes
├── monitoring/            # Monitoring extensions
├── components/            # Reusable workflow components
└── tests/                 # AWE system tests
```

## Supporting Modules (in `tools/`)

| Module | Purpose |
|---|---|
| `autonomy_governor.py` | Tier-based action approval, risk classification |
| `confidence_scorer.py` | 5-factor weighted confidence scoring |
| `decision_logger.py` | Append-only decision audit trail |
| `repair_engine.py` | Pattern matching, dedup, backup, fix application |
| `repair_pattern_store.py` | JSON pattern store with success rate tracking |

## How to Extend

### Add a new agent prompt

1. Create `autonomous/prompts/{agent_name}.md` following the 10-section structure
2. Add entry to `autonomous/prompts/PROMPT_REGISTRY.md`

### Add a new policy

1. Create `autonomous/policies/{POLICY_NAME}.md`
2. Reference it in `APPROVAL_MATRIX.md` where applicable
3. Update `ARCHITECTURE.md` file map

### Add a new repair pattern

```bash
# Option 1: Seed from code
# Edit autonomous/scripts/seed_patterns.py, add to ADDITIONAL_PATTERNS

# Option 2: Learn from a manual fix (planned for V1)
python -m autonomous learn --workflow-id <id> --fix "description" --pattern-name "name"
```

### Add a new workflow type

1. Create spec from `autonomous/templates/WORKFLOW_SPEC_TEMPLATE.md`
2. Classify risk per `autonomous/policies/CHANGE_RISK_MATRIX.md`
3. Build using existing deploy script patterns (`tools/deploy_*.py`)

## Key Design Decisions

1. **Hybrid single-agent** — one Claude Code session with prompt-switching, not multi-agent
2. **Local JSON memory** — git-trackable, instant access, no API latency
3. **Deploy script is source of truth** — every live fix must also update `tools/deploy_*.py`
4. **No `$env` in Code nodes** — n8n Cloud blocks this
5. **Safety caps are non-negotiable** — R2K/day ads, R10K auto-approve invoices, R50K escalate
6. **WAT principle** — probabilistic AI handles reasoning, deterministic Python handles execution

## Related Docs

- [CLAUDE.md](../CLAUDE.md) — Project-level context for Claude Code
- [config.json](../config.json) — Non-secret config (n8n instances, AI models, schedules)
- [tools/agent_registry.py](../tools/agent_registry.py) — 22-agent registry

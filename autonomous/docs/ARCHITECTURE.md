# Architecture — AVM Autonomous Workflow Engineer

## Architecture Decision: Hybrid Single-Agent with Specialized Prompts

**Recommendation: Single orchestrating agent (Claude Code) with role-switching via prompt templates.**

This is NOT a multi-agent system with separate LLM instances communicating. It is one Claude Code session that loads different prompt templates depending on the current task stage. The "agents" are prompt personas, not separate processes.

### Why Hybrid Single-Agent

| Criterion | Single-Agent (Chosen) | Multi-Agent | Pure Multi-Agent |
|---|---|---|---|
| **Reliability** | High — one context, no handoff failures | Medium — handoff errors | Low — coordination complexity |
| **Token efficiency** | High — shared context, no duplication | Medium — some context shared | Low — each agent re-reads context |
| **Debugging clarity** | High — single log stream | Medium — traceable with IDs | Low — distributed logs |
| **Scalability** | Medium — limited by context window | High — parallel work | High — fully parallel |
| **Operational complexity** | Low — one process | Medium — orchestrator needed | High — message buses, state sync |
| **Maintainability** | High — update one system | Medium — coordinated updates | Low — version each agent separately |

**Key insight:** Our system has ~70 workflows across 7 departments. This is complex enough to need specialized reasoning (via prompts) but not so large that we need parallel autonomous agents. Claude Code's 1M context window + subagent spawning covers our scale.

**When to revisit:** If we exceed 200 workflows or need real-time sub-second autonomous responses, re-evaluate toward multi-agent with message passing.

---

## Module Inventory

### Orchestration Layer

The engine that receives tasks, classifies them, selects the execution loop, and steps through stages.

| Field | Value |
|---|---|
| **Implementation** | `autonomous/engine.py` → `AutonomousEngine` class |
| **Purpose** | Route tasks to correct execution loop, manage state transitions, enforce policies |
| **Inputs** | Task descriptor (type, target workflow, context, urgency) |
| **Outputs** | Execution log, final status (success/escalated/failed), artifacts produced |
| **Success criteria** | Correct loop selected, all stages logged, policies enforced, no unauthorized actions |
| **Failure modes** | Wrong loop selected, stage timeout, policy bypass, infinite loop |
| **Escalation triggers** | Unknown task type, confidence < threshold, policy violation detected |
| **Depends on** | All modules below; `tools/agent_registry.py` for routing; policies for guardrails |

### Planner Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/planner.md` |
| **Purpose** | Receive a business request, decompose it into a workflow specification |
| **Inputs** | Business request (natural language), department context, existing workflow inventory |
| **Outputs** | Draft workflow spec (per `autonomous/templates/WORKFLOW_SPEC_TEMPLATE.md`) |
| **Success criteria** | Spec covers all required fields, risk classified, dependencies identified |
| **Failure modes** | Ambiguous requirements, missing integration details, incorrect risk classification |
| **Escalation triggers** | Cannot determine risk level, conflicting requirements, touches > 3 departments |
| **Existing tools used** | `tools/agent_registry.py` (agent/workflow lookup), search of `workflows/` for similar SOPs |

### Researcher Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/researcher.md` |
| **Purpose** | Search existing workflows, templates, and reference libraries for reusable patterns |
| **Inputs** | Workflow spec draft, keywords, integration names |
| **Outputs** | Reuse report: matching workflows, adaptable patterns, recommended components |
| **Success criteria** | At least 3 pattern candidates evaluated, similarity scores provided |
| **Failure modes** | No matches found (proceed to build from scratch), false positives |
| **Escalation triggers** | None — always produces output (even if "no matches found") |
| **Existing tools used** | File search across `workflows/`, `Github Access/n8n-workflows-main/`, `Github Access/ultimate-n8n-ai-workflows-main/` |

### Spec Writer Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/spec_writer.md` |
| **Purpose** | Convert planner output into a formal, validated workflow specification |
| **Inputs** | Planner draft spec, researcher reuse report |
| **Outputs** | Final workflow spec (strict format per template) |
| **Success criteria** | All required fields populated, risk level assigned, test requirements defined |
| **Failure modes** | Missing fields, inconsistent risk/test requirements |
| **Escalation triggers** | Cannot determine credentials needed, ambiguous integration mapping |
| **Existing tools used** | `autonomous/templates/WORKFLOW_SPEC_TEMPLATE.md` |

### Builder Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/builder.md` |
| **Purpose** | Generate n8n workflow JSON and/or deploy script from specification |
| **Inputs** | Final workflow spec, reusable components, deploy script patterns |
| **Outputs** | `tools/deploy_{dept}.py` code OR `workflows/{dept}/{name}.json`, connection map |
| **Success criteria** | Valid n8n JSON, all nodes connected, credentials referenced correctly |
| **Failure modes** | Invalid node types, broken connections, wrong credential IDs, missing parameters |
| **Escalation triggers** | Unknown node type, no existing credential for required integration |
| **Existing tools used** | Deploy script patterns from `tools/deploy_*.py`, `tools/n8n_client.py` for validation |

### Validator Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/validator.md` |
| **Purpose** | Validate built workflow against its spec — structural, logical, and policy checks |
| **Inputs** | Built workflow JSON, workflow spec, policy files |
| **Outputs** | Validation report: pass/fail per check, issues list with severity |
| **Success criteria** | All critical checks pass, no high-severity issues |
| **Failure modes** | False positives (flags valid patterns), false negatives (misses real issues) |
| **Escalation triggers** | Critical validation failure, unknown node configuration |
| **Checks performed** | Node types valid, connections complete, credentials referenced, risk classification matches policy, no `$env` in Code nodes, safety caps respected |

### Tester Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/tester.md` |
| **Purpose** | Generate test cases from spec, execute tests, report results |
| **Inputs** | Workflow spec, built workflow, test templates |
| **Outputs** | Test suite, execution results, coverage score |
| **Success criteria** | Coverage > 80%, all critical paths tested, no unhandled error paths |
| **Failure modes** | Test data doesn't trigger edge cases, flaky external API tests |
| **Escalation triggers** | Coverage < 60%, cannot create test data for integration |
| **Existing tools used** | `tools/execution_monitor.py` (for execution tracking), n8n API test execution |

### Debugger Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/debugger.md` |
| **Purpose** | Diagnose workflow failures, identify root cause, propose and optionally apply fixes |
| **Inputs** | Execution error data, workflow JSON, incident context, past incident memory |
| **Outputs** | Root cause analysis, fix options (ranked by confidence), applied fix (if within policy) |
| **Success criteria** | Root cause identified correctly, fix resolves the issue without side effects |
| **Failure modes** | Misidentified root cause, fix introduces new issues, fix applied to wrong node |
| **Escalation triggers** | Confidence < 70%, fix touches payment/invoice logic, multiple competing root causes |
| **Existing tools used** | `tools/execution_monitor.py`, `tools/n8n_client.py` (fetch workflow + execution data) |

### Optimizer Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/optimizer.md` |
| **Purpose** | Analyze workflow performance, propose efficiency improvements |
| **Inputs** | Execution history, KPI data, latency metrics, token usage |
| **Outputs** | Optimization report: issues found, proposed changes, expected improvement |
| **Success criteria** | Measurable improvement in target metric (latency, error rate, token usage) |
| **Failure modes** | Optimization degrades other metrics, improvement too small to justify change |
| **Escalation triggers** | Proposed change is medium/high risk, optimization affects > 1 department |
| **Existing tools used** | `tools/orchestrator_kpi_engine.py`, `tools/intelligence_engine.py` |

### Deployer Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/deployer.md` |
| **Purpose** | Manage the build → deploy → activate lifecycle |
| **Inputs** | Validated workflow, deployment policy, risk classification |
| **Outputs** | Deployment result (success/failure), workflow ID, activation status |
| **Success criteria** | Workflow deployed, activated if low-risk, post-deploy validation passes |
| **Failure modes** | Deploy API failure, activation failure, post-deploy validation fails |
| **Escalation triggers** | Medium/high-risk deployment needs approval, API failure after 3 retries |
| **Existing tools used** | `tools/workflow_deployer.py`, `tools/deploy_*.py` patterns, `tools/n8n_client.py` |

### Rollback Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/rollback_agent.md` |
| **Purpose** | Revert a workflow to its previous working state |
| **Inputs** | Workflow ID, failure evidence, previous version (from git or n8n history) |
| **Outputs** | Rollback result, incident report |
| **Success criteria** | Previous version restored, post-rollback validation passes, incident logged |
| **Failure modes** | No previous version available, rollback introduces different issues |
| **Escalation triggers** | Cannot find previous version, rollback fails, cascading failures across workflows |
| **Existing tools used** | `tools/workflow_deployer.py`, git history, `tools/n8n_client.py` |

### Documentation Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/documentation_agent.md` |
| **Purpose** | Generate and update SOPs, changelogs, and architecture docs |
| **Inputs** | Workflow spec, deployment result, incident reports, code changes |
| **Outputs** | Updated markdown docs in `workflows/{dept}/`, changelog entries |
| **Success criteria** | Docs match current workflow state, no stale references |
| **Failure modes** | Docs contradict actual workflow logic, missing sections |
| **Escalation triggers** | None — documentation is always low-risk |
| **Existing tools used** | File system read/write, git for version tracking |

### Monitoring Analyst Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/monitoring_analyst.md` |
| **Purpose** | Interpret KPI data, detect anomalies, decide whether to trigger repair/optimization |
| **Inputs** | KPI snapshots, execution history, anomaly alerts, thresholds from config |
| **Outputs** | Health report, triggered actions (repair loop, optimization loop, escalation) |
| **Success criteria** | Anomalies detected within 15 minutes, false positive rate < 10% |
| **Failure modes** | Missed anomaly, false alarm triggers unnecessary repair |
| **Escalation triggers** | P1/P2 severity detected, multiple departments affected simultaneously |
| **Existing tools used** | `tools/orchestrator_kpi_engine.py`, `tools/intelligence_engine.py`, `tools/execution_monitor.py` |

### Incident Responder Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/incident_responder.md` |
| **Purpose** | First responder for production issues — triage, classify, initiate repair or escalate |
| **Inputs** | Alert from monitoring analyst, execution error data, workflow context |
| **Outputs** | Incident ticket (per template), triage decision (auto-repair vs escalate) |
| **Success criteria** | Correct severity classification, appropriate response initiated within SLA |
| **Failure modes** | Wrong severity, delayed response, incorrect triage |
| **Escalation triggers** | P1 severity, financial impact, data loss risk |
| **Existing tools used** | `tools/execution_monitor.py`, Airtable (incident tracking), Telegram (alerts) |

### Revamp Agent Module

| Field | Value |
|---|---|
| **Prompt** | `autonomous/prompts/revamp_agent.md` |
| **Purpose** | Assess whether a workflow needs full rebuild vs incremental patching |
| **Inputs** | Workflow health history, incident count, age, maintainability score |
| **Outputs** | Revamp recommendation (rebuild/patch/keep), scope assessment, migration plan |
| **Success criteria** | Correct rebuild vs patch decision, realistic scope estimate |
| **Failure modes** | Unnecessary rebuild (waste), missed rebuild need (continued incidents) |
| **Escalation triggers** | Revamp touches > 3 departments, estimated effort > 1 week |
| **Existing tools used** | `tools/intelligence_engine.py` (trend data), git log (change frequency) |

---

## Module Composition Flow

### New Workflow Build

```
Business Request
    │
    ▼
┌──────────┐    ┌────────────┐    ┌─────────────┐
│ Planner  │───▶│ Researcher │───▶│ Spec Writer │
└──────────┘    └────────────┘    └──────┬──────┘
                                         │
                                         ▼
                                  ┌─────────────┐
                                  │   Builder   │
                                  └──────┬──────┘
                                         │
                                         ▼
                              ┌──────────────────┐
                              │    Validator     │
                              └────────┬─────────┘
                                       │
                              ┌────────▼─────────┐
                              │     Tester       │
                              └────────┬─────────┘
                                       │
                                 pass? │
                          ┌────────────┼────────────┐
                          │ yes                      │ no
                          ▼                          ▼
                   ┌─────────────┐          ┌────────────┐
                   │  Deployer   │          │  Debugger  │──▶ loop back
                   └──────┬──────┘          └────────────┘    to Builder
                          │
                          ▼
                   ┌─────────────┐
                   │Documentation│
                   └─────────────┘
```

### Repair Loop

```
Monitoring Analyst (detects anomaly)
    │
    ▼
Incident Responder (triage + classify)
    │
    ├── P1/P2 + low confidence ──▶ ESCALATE to Ian
    │
    ├── Known pattern + high confidence ──▶ Debugger (auto-fix)
    │                                           │
    │                                    ┌──────▼──────┐
    │                                    │  Validator   │
    │                                    └──────┬──────┘
    │                                           │
    │                                    ┌──────▼──────┐
    │                                    │   Tester    │
    │                                    └──────┬──────┘
    │                                           │
    │                              pass? ───────┼───────┐
    │                              yes          │       │ no
    │                              ▼            │       ▼
    │                         Deployer          │   Rollback
    │                                           │
    └── Multiple root causes ──▶ Debugger (ranked hypotheses)
```

### Optimization Loop

```
Monitoring Analyst (detects inefficiency)
    │
    ▼
Optimizer (analyze + propose)
    │
    ▼
Validator (check proposed changes)
    │
    ▼
Tester (compare to baseline)
    │
    ├── improved ──▶ Deployer ──▶ Documentation
    │
    └── degraded ──▶ Discard + log
```

---

## Layering on Existing Tools

AWE does **not** reimplement any existing functionality. It orchestrates:

```
┌─────────────────────────────────────────────────────────────────┐
│                    AWE ORCHESTRATION LAYER                      │
│                    (autonomous/engine.py)                        │
│                                                                 │
│  Prompt Templates     Policy Engine      Memory Store           │
│  (autonomous/         (autonomous/       (autonomous/           │
│   prompts/*.md)        policies/*.md)     memory/)              │
└───────────────┬─────────────────┬──────────────────┬────────────┘
                │                 │                   │
┌───────────────▼─────────────────▼──────────────────▼────────────┐
│                    EXISTING PYTHON TOOLCHAIN                     │
│                                                                  │
│  n8n_client.py          execution_monitor.py                     │
│  ├─ health_check()      ├─ fetch_recent_executions()            │
│  ├─ get_workflow()       ├─ detect_consecutive_errors()          │
│  ├─ create_workflow()    └─ generate_health_dashboard()          │
│  ├─ update_workflow()                                            │
│  ├─ activate_workflow()  orchestrator_kpi_engine.py              │
│  ├─ list_executions()    ├─ compute_all_agent_scores()           │
│  └─ delete_workflow()    ├─ detect_anomalies()                   │
│                          └─ generate_daily_snapshot()             │
│  workflow_deployer.py                                            │
│  ├─ deploy_from_file()   intelligence_engine.py                  │
│  ├─ export_workflow()    ├─ compute_correlations()               │
│  ├─ batch_deploy()       ├─ identify_bottlenecks()               │
│  └─ compare_versions()   ├─ forecast_trend()                     │
│                          └─ detect_cross_dept_anomalies()         │
│  agent_registry.py                                               │
│  ├─ get_agent()          run_manager.py                          │
│  ├─ get_agents_by_tier() ├─ status / monitor / analyze           │
│  ├─ get_escalation_chain()├─ report / deploy / docs              │
│  └─ get_total_token_budget()└─ ai-audit                          │
│                                                                  │
│  deploy_*.py (28 scripts)                                        │
│  ├─ build_nodes() → n8n node list                                │
│  ├─ build_connections() → connection map                         │
│  └─ CLI: build | deploy | activate                               │
└──────────────────────────────────────────────────────────────────┘
```

### What AWE Adds (New Code)

| New Component | Location | Purpose |
|---|---|---|
| `AutonomousEngine` class | `autonomous/engine.py` | Task routing, loop control, policy enforcement |
| CLI entry point | `autonomous/cli.py` | Human interface: `status`, `build`, `repair`, `optimize`, `revamp`, `monitor`, `audit` |
| Config | `autonomous/config.yaml` | Autonomy tiers, thresholds, intervals, alerts |
| 14 prompt templates | `autonomous/prompts/*.md` | Role-specific reasoning instructions |
| 8 policy files | `autonomous/policies/*.md` | Safety guardrails, approval gates, risk matrix |
| Templates | `autonomous/templates/*.md` | Workflow spec, incident report, test case |
| Memory store | `autonomous/memory/` | Incident history, pattern library, decision logs |
| Playbooks | `autonomous/playbooks/` | Known failure patterns and resolution recipes |

---

## Data Flow

```
External Event (n8n execution error, KPI threshold breach, user request)
    │
    ▼
AutonomousEngine.receive_task()
    │
    ├── classify_task() → {type: build|repair|optimize|revamp, risk: low|med|high}
    │
    ├── check_policy() → {allowed: bool, requires_approval: bool}
    │
    ├── load_prompt() → prompt template for current stage
    │
    ├── execute_stage() → stage output + logs
    │
    ├── evaluate_result() → {pass: bool, confidence: float}
    │
    ├── next_stage() or escalate() or rollback()
    │
    └── log_outcome() → memory store + Airtable + Telegram alert
```

## File Map

```
autonomous/
├── engine.py               # Core orchestration engine
├── cli.py                  # CLI entry point
├── config.yaml             # System configuration
├── __init__.py
│
├── docs/
│   ├── SYSTEM_OVERVIEW.md  # Executive summary (this session)
│   ├── ARCHITECTURE.md     # This document
│   ├── OPERATING_MODEL.md  # Scenario-based behavior rules
│   ├── MEMORY_MODEL.md     # Memory structures and storage
│   ├── EXECUTION_LOOPS.md  # Detailed loop definitions (Session 4)
│   ├── TEST_STRATEGY.md    # Testing framework (Session 4)
│   ├── OBSERVABILITY_SPEC.md # Monitoring design (Session 4)
│   ├── ROADMAP.md          # Phased implementation plan (Session 5)
│   └── START_THIS_WEEK.md  # Immediate action plan (Session 5)
│
├── policies/               # Safety guardrails (Session 2)
│   ├── AUTONOMY_POLICY.md
│   ├── CHANGE_RISK_MATRIX.md
│   ├── APPROVAL_MATRIX.md
│   ├── DEPLOYMENT_POLICY.md
│   ├── ROLLBACK_POLICY.md
│   ├── INCIDENT_SEVERITY.md
│   ├── SECRETS_POLICY.md
│   └── REVAMP_POLICY.md
│
├── prompts/                # Agent prompt templates (Session 3)
│   ├── PROMPT_REGISTRY.md
│   ├── planner.md
│   ├── researcher.md
│   ├── spec_writer.md
│   ├── builder.md
│   ├── validator.md
│   ├── tester.md
│   ├── debugger.md
│   ├── optimizer.md
│   ├── revamp_agent.md
│   ├── deployer.md
│   ├── rollback_agent.md
│   ├── documentation_agent.md
│   ├── incident_responder.md
│   └── monitoring_analyst.md
│
├── templates/
│   ├── WORKFLOW_SPEC_TEMPLATE.md
│   ├── INCIDENT_TEMPLATE.md
│   └── TEST_CASE_TEMPLATE.md
│
├── playbooks/              # Known failure patterns + recipes
├── memory/                 # Persistent state (incidents, patterns, decisions)
├── monitoring/             # Monitoring extensions
├── components/             # Reusable workflow components
└── tests/                  # AWE system tests
```

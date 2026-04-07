# Execution Loops — AVM Autonomous Workflow Engineer

> Cross-references: [ARCHITECTURE.md](ARCHITECTURE.md), [OPERATING_MODEL.md](OPERATING_MODEL.md), agent prompts in `autonomous/prompts/`

---

## Loop 1: New Workflow Build (15 Stages)

### Stage 1 — Receive Request

| Field | Value |
|---|---|
| **Objective** | Accept and parse the business request |
| **Inputs** | Natural language request, department, urgency |
| **Outputs** | Structured request object (request type, department, urgency, context) |
| **Pass** | All required fields present (description, department) |
| **Fail** | Missing department or description → ask requester |
| **Next (pass)** | Stage 2 |
| **Next (fail)** | Pause, request clarification |
| **Logging** | Request recorded in `autonomous/memory/decisions/` |
| **Agent** | Orchestration Engine (`autonomous/engine.py`) |

### Stage 2 — Infer Context

| Field | Value |
|---|---|
| **Objective** | Enrich request with agent ownership, existing workflows, integration context |
| **Inputs** | Structured request |
| **Outputs** | Enriched request with owner_agent, related workflows, known integrations |
| **Pass** | Owner agent identified, at least 1 integration determined |
| **Fail** | Cannot determine department ownership → escalate |
| **Next (pass)** | Stage 3 |
| **Next (fail)** | Escalate to Ian |
| **Logging** | Context enrichment details |
| **Agent** | **Planner** (`autonomous/prompts/planner.md`) |

### Stage 3 — Search for Reusable Patterns

| Field | Value |
|---|---|
| **Objective** | Find existing workflows/templates that can be adapted |
| **Inputs** | Enriched request, keywords, integration names |
| **Outputs** | Reuse report with scored candidates |
| **Pass** | At least 3 search sources checked |
| **Fail** | Never fails — always produces report (even if "no matches") |
| **Next (pass)** | Stage 4 |
| **Logging** | Search sources, match count, top candidate |
| **Agent** | **Researcher** (`autonomous/prompts/researcher.md`) |

### Stage 4 — Generate Workflow Spec

| Field | Value |
|---|---|
| **Objective** | Produce a complete workflow specification |
| **Inputs** | Enriched request, reuse report |
| **Outputs** | Final spec per `WORKFLOW_SPEC_TEMPLATE.md` |
| **Pass** | All required fields populated, risk classified, credentials identified |
| **Fail** | Missing required fields OR cannot determine risk level |
| **Next (pass)** | Stage 5 |
| **Next (fail)** | Return to Planner with specific gaps to fill |
| **Logging** | Spec saved to `autonomous/memory/specs/` |
| **Agent** | **Spec Writer** (`autonomous/prompts/spec_writer.md`) |

### Stage 5 — Select Architecture Pattern

| Field | Value |
|---|---|
| **Objective** | Choose workflow structure (linear, branching, loop, sub-workflow) |
| **Inputs** | Final spec, reuse report recommendations |
| **Outputs** | Architecture decision (pattern type, estimated node count) |
| **Pass** | Pattern selected with justification |
| **Fail** | Complexity > 60 nodes → recommend sub-workflow decomposition |
| **Next (pass)** | Stage 6 |
| **Next (fail)** | Re-scope with Planner (split into sub-workflows) |
| **Logging** | Architecture decision in decision log |
| **Agent** | **Builder** (`autonomous/prompts/builder.md`) |

### Stage 6 — Build Workflow

| Field | Value |
|---|---|
| **Objective** | Generate n8n workflow JSON and/or deploy script |
| **Inputs** | Final spec, architecture pattern, reusable components |
| **Outputs** | Deploy script (`tools/deploy_{dept}.py`) + workflow JSON (`workflows/{dept}/`) |
| **Pass** | Valid JSON generated, all nodes connected, credentials referenced |
| **Fail** | Unknown node type, missing credential, broken connections |
| **Next (pass)** | Stage 7 |
| **Next (fail)** | Fix and retry (max 3 attempts), then escalate |
| **Logging** | Build output paths, node count, warnings |
| **Agent** | **Builder** (`autonomous/prompts/builder.md`) |

### Stage 7 — Validate

| Field | Value |
|---|---|
| **Objective** | Check workflow against spec and policies |
| **Inputs** | Built workflow JSON, deploy script, spec, policies |
| **Outputs** | Validation report (pass/fail per check, issues list) |
| **Pass** | Zero critical or high issues |
| **Fail** | Any critical or high issue present |
| **Next (pass)** | Stage 8 |
| **Next (fail)** | Return to Stage 6 (Builder) with issue list |
| **Logging** | Validation report saved to `autonomous/memory/validations/` |
| **Agent** | **Validator** (`autonomous/prompts/validator.md`) |

### Stage 8 — Generate Tests

| Field | Value |
|---|---|
| **Objective** | Create test cases from spec |
| **Inputs** | Spec, built workflow, risk level |
| **Outputs** | Test suite (test IDs, inputs, expected outputs) |
| **Pass** | Coverage > 80% for medium/high risk, > 60% for low |
| **Fail** | Coverage too low, cannot generate meaningful tests |
| **Next (pass)** | Stage 9 |
| **Next (fail)** | Flag coverage gap, proceed with available tests |
| **Logging** | Test suite saved |
| **Agent** | **Tester** (`autonomous/prompts/tester.md`) |

### Stage 9 — Run Tests

| Field | Value |
|---|---|
| **Objective** | Execute test suite, record results |
| **Inputs** | Test suite, workflow (inactive on n8n for Tier 2+, local-only for Tier 0-1) |
| **Outputs** | Test results (pass/fail per test, coverage score) |
| **Pass** | Zero critical path failures, coverage meets threshold |
| **Fail** | Any critical path test fails |
| **Next (pass)** | Stage 10 (if all pass) or Stage 11 (if minor issues) |
| **Next (fail)** | Return to Stage 6 (Builder) with failure details |
| **Logging** | Results saved to `autonomous/memory/test_history/` |
| **Agent** | **Tester** (`autonomous/prompts/tester.md`) |

### Stage 10 — Detect Issues (Post-Test)

| Field | Value |
|---|---|
| **Objective** | Analyze test results for non-obvious issues (flaky tests, edge cases) |
| **Inputs** | Test results, validation report |
| **Outputs** | Issue list (if any) or clean bill of health |
| **Pass** | No additional issues found |
| **Fail** | Issues found that tests didn't catch |
| **Next (pass)** | Stage 12 |
| **Next (fail)** | Stage 11 |
| **Logging** | Issue analysis |
| **Agent** | **Validator** (`autonomous/prompts/validator.md`) |

### Stage 11 — Auto-Fix

| Field | Value |
|---|---|
| **Objective** | Fix issues found in testing/validation |
| **Inputs** | Issue list, workflow JSON, deploy script |
| **Outputs** | Patched workflow + deploy script |
| **Pass** | Fix applied, confidence > 80% |
| **Fail** | Cannot fix with confidence > 80% after 3 attempts |
| **Next (pass)** | Return to Stage 7 (re-validate) |
| **Next (fail)** | Escalate to Ian with diagnosis |
| **Logging** | Fix details, attempt count |
| **Agent** | **Debugger** (`autonomous/prompts/debugger.md`) |

### Stage 12 — Document

| Field | Value |
|---|---|
| **Objective** | Generate/update SOP and changelog |
| **Inputs** | Final spec, deployment details |
| **Outputs** | Updated markdown docs in `workflows/{dept}/` |
| **Pass** | Docs match current implementation |
| **Fail** | Never fails (documentation is always low-risk) |
| **Next (pass)** | Stage 13 |
| **Logging** | Files updated list |
| **Agent** | **Documentation Agent** (`autonomous/prompts/documentation_agent.md`) |

### Stage 13 — Stage Deploy

| Field | Value |
|---|---|
| **Objective** | Deploy workflow as INACTIVE to n8n |
| **Inputs** | Validated workflow, risk level, approval status |
| **Outputs** | Deployment result (workflow ID, inactive status) |
| **Pass** | Workflow deployed successfully as inactive |
| **Fail** | Deploy API error after 3 retries |
| **Next (pass)** | Stage 14 |
| **Next (fail)** | Escalate (n8n API issue) |
| **Logging** | Deployment record in `autonomous/memory/deployments/` |
| **Agent** | **Deployer** (`autonomous/prompts/deployer.md`) |

### Stage 14 — Verify & Activate

| Field | Value |
|---|---|
| **Objective** | Activate workflow per approval policy, verify first executions |
| **Inputs** | Deployed workflow ID, risk level |
| **Outputs** | Activation result, post-deploy verification |
| **Pass** | Low risk: auto-activate + 3 executions pass. Medium: veto window passes. High: Ian approves. |
| **Fail** | Post-deploy execution fails |
| **Next (pass)** | Stage 15 |
| **Next (fail)** | Auto-rollback → **Rollback Agent**, then **Debugger** |
| **Logging** | Activation + verification details |
| **Agent** | **Deployer** (`autonomous/prompts/deployer.md`) |

### Stage 15 — Monitor

| Field | Value |
|---|---|
| **Objective** | Watch workflow health for first 24 hours |
| **Inputs** | Workflow ID, expected KPIs from spec |
| **Outputs** | 24h health report |
| **Pass** | Error rate < 5%, execution time within spec bounds |
| **Fail** | Error rate > 10% or KPIs outside spec → trigger repair loop |
| **Next (pass)** | Build loop complete ✓ |
| **Next (fail)** | Enter **Repair Loop** (Loop 2) |
| **Logging** | Health report in `autonomous/memory/health_reports/` |
| **Agent** | **Monitoring Analyst** (`autonomous/prompts/monitoring_analyst.md`) |

---

## Loop 2: Autonomous Repair (11 Stages)

### Stage 1 — Detect Issue

| Field | Value |
|---|---|
| **Objective** | Identify workflow failure from monitoring data |
| **Inputs** | Execution data, KPI snapshots, anomaly alerts |
| **Outputs** | Issue summary (workflow, error type, frequency, impact) |
| **Pass** | Issue clearly identified with error data |
| **Fail** | Intermittent — cannot reproduce |
| **Next (pass)** | Stage 2 |
| **Next (fail)** | Log as P4, increase monitoring frequency, wait for recurrence |
| **Logging** | Detection event |
| **Agent** | **Monitoring Analyst** |

### Stage 2 — Classify Severity

| Field | Value |
|---|---|
| **Objective** | Assign P1-P4 severity per INCIDENT_SEVERITY.md |
| **Inputs** | Issue summary, department, workflow type |
| **Outputs** | Severity level with justification |
| **Pass** | Severity assigned |
| **Fail** | Never fails — worst case default to P2 |
| **Next (pass)** | Stage 3 |
| **Logging** | Severity classification |
| **Agent** | **Incident Responder** |

### Stage 3 — Inspect Logs

| Field | Value |
|---|---|
| **Objective** | Gather detailed error data from execution logs |
| **Inputs** | Workflow ID, execution IDs |
| **Outputs** | Error messages, failed node, input/output data at failure point |
| **Pass** | Error data retrieved |
| **Fail** | Execution data expired or inaccessible |
| **Next (pass)** | Stage 4 |
| **Next (fail)** | Escalate with "insufficient data for diagnosis" |
| **Logging** | Raw error data captured |
| **Agent** | **Debugger** |

### Stage 4 — Hypothesize Root Causes

| Field | Value |
|---|---|
| **Objective** | Generate ranked list of possible root causes |
| **Inputs** | Error data, known patterns, recent changes (git log) |
| **Outputs** | Hypothesis list (cause, confidence, evidence) |
| **Pass** | At least 1 hypothesis with confidence > 60% |
| **Fail** | All hypotheses < 60% confidence |
| **Next (pass)** | Stage 5 |
| **Next (fail)** | Escalate with all hypotheses for Ian to evaluate |
| **Logging** | All hypotheses with confidence scores |
| **Agent** | **Debugger** |

### Stage 5 — Generate Repair Options

| Field | Value |
|---|---|
| **Objective** | Create fix for top hypothesis |
| **Inputs** | Top hypothesis, workflow JSON, deploy script |
| **Outputs** | Fix (code changes to deploy script + live workflow) |
| **Pass** | Fix generated, confidence > 70% |
| **Fail** | Cannot generate fix with sufficient confidence |
| **Next (pass)** | Stage 6 |
| **Next (fail)** | Escalate |
| **Logging** | Fix details |
| **Agent** | **Debugger** |

### Stage 6 — Test Repair

| Field | Value |
|---|---|
| **Objective** | Validate fix (Tier 2+: test on inactive copy; Tier 0-1: review only) |
| **Inputs** | Fixed workflow |
| **Outputs** | Test result (pass/fail) |
| **Pass** | Fix resolves the issue without new errors |
| **Fail** | Fix doesn't resolve, or introduces new errors |
| **Next (pass)** | Stage 7 |
| **Next (fail)** | Try next hypothesis (Stage 5), max 3 attempts |
| **Logging** | Test results |
| **Agent** | **Tester** |

### Stage 7 — Compare Outcomes

| Field | Value |
|---|---|
| **Objective** | Confirm fix improves situation vs baseline |
| **Inputs** | Pre-fix metrics, post-fix test results |
| **Outputs** | Comparison report (improved / same / degraded) |
| **Pass** | Improvement confirmed |
| **Fail** | No improvement or degradation |
| **Next (pass)** | Stage 8 |
| **Next (fail)** | Rollback test changes, try next hypothesis |
| **Logging** | Comparison metrics |
| **Agent** | **Validator** |

### Stage 8 — Apply Fix

| Field | Value |
|---|---|
| **Objective** | Deploy fix to production (per APPROVAL_MATRIX) |
| **Inputs** | Validated fix, risk level, confidence score |
| **Outputs** | Deployment result |
| **Pass** | Fix deployed, post-deploy verification passes |
| **Fail** | Deployment fails or post-deploy execution fails |
| **Next (pass)** | Stage 10 |
| **Next (fail)** | Stage 9 |
| **Logging** | Deployment record |
| **Agent** | **Deployer** |

### Stage 9 — Rollback if Degraded

| Field | Value |
|---|---|
| **Objective** | Revert to pre-fix state |
| **Inputs** | Backup workflow, deployment ID |
| **Outputs** | Rollback result |
| **Pass** | Previous version restored and verified |
| **Fail** | Cannot rollback → emergency deactivate + escalate |
| **Next (pass)** | Try next hypothesis (Stage 5) or escalate |
| **Next (fail)** | Immediate escalation to Ian |
| **Logging** | Rollback details |
| **Agent** | **Rollback Agent** |

### Stage 10 — Document Incident

| Field | Value |
|---|---|
| **Objective** | Create complete incident record |
| **Inputs** | All data from stages 1-8 |
| **Outputs** | Incident record per INCIDENT_TEMPLATE |
| **Pass** | All required fields populated |
| **Fail** | Never fails |
| **Next (pass)** | Stage 11 |
| **Logging** | Record saved to `autonomous/memory/incidents/` |
| **Agent** | **Documentation Agent** |

### Stage 11 — Store Learning

| Field | Value |
|---|---|
| **Objective** | Update pattern library with new knowledge |
| **Inputs** | Incident record, fix details, root cause |
| **Outputs** | New or updated pattern in `autonomous/memory/patterns/` |
| **Pass** | Pattern stored with tags, confidence, applies_to |
| **Fail** | Never fails |
| **Next (pass)** | Repair loop complete ✓ |
| **Logging** | Pattern update |
| **Agent** | Orchestration Engine |

---

## Loop 3: Optimization (7 Stages)

### Stage 1 — Detect Inefficiency

| Field | Value |
|---|---|
| **Objective** | Identify performance issues from metrics |
| **Inputs** | KPI data, execution history, token usage |
| **Outputs** | Inefficiency summary (metric, current value, expected value) |
| **Pass** | Measurable gap identified (> 10% deviation from optimal) |
| **Fail** | No significant inefficiency found |
| **Next (pass)** | Stage 2 |
| **Next (fail)** | Log "healthy" status, end loop |
| **Agent** | **Monitoring Analyst** |

### Stage 2 — Inspect Metrics

| Field | Value |
|---|---|
| **Objective** | Deep-dive into the specific inefficiency |
| **Inputs** | Inefficiency summary, workflow execution data |
| **Outputs** | Bottleneck analysis (which node, what causes the delay/cost/error) |
| **Pass** | Root bottleneck identified |
| **Fail** | Distributed inefficiency, no single bottleneck |
| **Next (pass)** | Stage 3 |
| **Next (fail)** | Log findings, recommend architectural review (Revamp Agent) |
| **Agent** | **Optimizer** |

### Stage 3 — Propose Improvements

| Field | Value |
|---|---|
| **Objective** | Generate optimization options |
| **Inputs** | Bottleneck analysis |
| **Outputs** | Optimization proposals (ranked by impact, classified by risk) |
| **Pass** | At least 1 proposal with expected improvement > 10% |
| **Fail** | All proposals < 5% improvement → not worth the risk |
| **Next (pass)** | Stage 4 |
| **Next (fail)** | Log "optimization not viable", end loop |
| **Agent** | **Optimizer** |

### Stage 4 — Test Optimization

| Field | Value |
|---|---|
| **Objective** | Apply optimization to test copy, measure results |
| **Inputs** | Top optimization proposal, test workflow |
| **Outputs** | Post-optimization metrics |
| **Pass** | Target metric improved without degrading others |
| **Fail** | No improvement or regression in other metrics |
| **Next (pass)** | Stage 5 |
| **Next (fail)** | Discard optimization, try next proposal |
| **Agent** | **Tester** |

### Stage 5 — Compare to Baseline

| Field | Value |
|---|---|
| **Objective** | Statistical comparison of before vs after |
| **Inputs** | Baseline metrics (7-day average), post-optimization metrics |
| **Outputs** | Comparison report with confidence interval |
| **Pass** | Improvement confirmed with > 80% confidence |
| **Fail** | Improvement within noise margin |
| **Next (pass)** | Stage 6 |
| **Next (fail)** | Discard, log as "inconclusive" |
| **Agent** | **Optimizer** |

### Stage 6 — Apply Optimization

| Field | Value |
|---|---|
| **Objective** | Deploy optimized version to production |
| **Inputs** | Validated optimization, approval (per APPROVAL_MATRIX) |
| **Outputs** | Deployment result |
| **Pass** | Deployed, post-deploy verification passes |
| **Fail** | Post-deploy degradation → rollback |
| **Next (pass)** | Stage 7 |
| **Next (fail)** | Rollback, log failed optimization |
| **Agent** | **Deployer** |

### Stage 7 — Log Outcome

| Field | Value |
|---|---|
| **Objective** | Record results for future reference |
| **Inputs** | All optimization data |
| **Outputs** | Optimization record in `autonomous/memory/optimizations/` |
| **Pass** | Record complete |
| **Fail** | Never fails |
| **Next (pass)** | Optimization loop complete ✓ |
| **Agent** | **Documentation Agent** |

---

## Loop 4: Revamp / Refactor (8 Stages)

### Stage 1 — Trigger Detected

| Field | Value |
|---|---|
| **Objective** | Identify that a workflow needs revamp assessment |
| **Inputs** | Health scores, incident count, age, deprecated node alerts |
| **Outputs** | Revamp trigger reason |
| **Pass** | At least 1 trigger threshold crossed (per REVAMP_POLICY) |
| **Fail** | No triggers found |
| **Next (pass)** | Stage 2 |
| **Next (fail)** | No action needed, end |
| **Agent** | **Monitoring Analyst** |

### Stage 2 — Assess Scope

| Field | Value |
|---|---|
| **Objective** | Compute maintainability score, decide rebuild vs patch |
| **Inputs** | Workflow history, incidents, complexity, test coverage |
| **Outputs** | Revamp assessment (score, recommendation, effort estimate) |
| **Pass** | Clear recommendation (healthy / patch / revamp) |
| **Fail** | Borderline case — recommend conservative option (patch) |
| **Next (pass, revamp)** | Stage 3 |
| **Next (pass, patch)** | Enter Repair Loop with specific issues |
| **Next (pass, healthy)** | End — no action needed |
| **Agent** | **Revamp Agent** |

### Stage 3 — Design Replacement

| Field | Value |
|---|---|
| **Objective** | Create new spec for replacement workflow |
| **Inputs** | Current workflow analysis, current business requirements |
| **Outputs** | New workflow spec (may differ from original if requirements changed) |
| **Pass** | Complete spec addressing all current trigger reasons |
| **Fail** | Cannot determine current requirements → escalate to Ian |
| **Next (pass)** | Stage 4 |
| **Next (fail)** | Escalate |
| **Agent** | **Planner** + **Spec Writer** |

### Stage 4 — Build Parallel

| Field | Value |
|---|---|
| **Objective** | Build replacement workflow alongside live one (no disruption) |
| **Inputs** | New spec |
| **Outputs** | New deploy script + workflow JSON (named `{name} v{N+1}`) |
| **Pass** | Builds, validates, tests pass |
| **Fail** | Build/validate/test failures |
| **Next (pass)** | Stage 5 |
| **Next (fail)** | Fix and retry (max 3), then escalate |
| **Agent** | **Builder** → **Validator** → **Tester** |

### Stage 5 — Test New Version

| Field | Value |
|---|---|
| **Objective** | Full test suite on replacement workflow |
| **Inputs** | New workflow (inactive on n8n) |
| **Outputs** | Test results |
| **Pass** | All tests pass, coverage > 80% |
| **Fail** | Test failures |
| **Next (pass)** | Stage 6 |
| **Next (fail)** | Return to Stage 4 |
| **Agent** | **Tester** |

### Stage 6 — Compare to Old

| Field | Value |
|---|---|
| **Objective** | Side-by-side execution comparison (24-48h) |
| **Inputs** | Old workflow (live), new workflow (test executions) |
| **Outputs** | Comparison: output quality, speed, reliability, cost |
| **Pass** | New version equal or better on all metrics |
| **Fail** | New version worse on any metric |
| **Next (pass)** | Stage 7 |
| **Next (fail)** | Investigate regression, fix, re-compare |
| **Agent** | **Optimizer** (comparison analysis) |

### Stage 7 — Cutover

| Field | Value |
|---|---|
| **Objective** | Replace old workflow with new version |
| **Inputs** | Comparison results, approval (per APPROVAL_MATRIX) |
| **Outputs** | Cutover result |
| **Pass** | New version live, old deactivated, 5 executions verified |
| **Fail** | Cutover fails → rollback to old version |
| **Next (pass)** | Stage 8 |
| **Next (fail)** | Rollback, escalate |
| **Agent** | **Deployer** |

### Stage 8 — Archive Old

| Field | Value |
|---|---|
| **Objective** | Archive previous version, update docs, reset metrics |
| **Inputs** | Old workflow, deployment records |
| **Outputs** | Old workflow in `workflows/{dept}/archive/`, updated SOPs |
| **Pass** | Archive complete, docs updated, maintainability score reset |
| **Fail** | Never fails |
| **Next (pass)** | Revamp loop complete ✓ |
| **Agent** | **Documentation Agent** |

# Operating Model — AVM Autonomous Workflow Engineer

This document defines how AWE behaves in every operational scenario. Each scenario specifies the trigger, assessment steps, action options, decision criteria, escalation path, and logging requirements.

---

## Scenario 1: New Workflow Requested

**Trigger:** User describes a new automation need (e.g., "build a workflow that sends weekly client health reports").

| Step | Action |
|---|---|
| 1. Understand | Parse the request. Identify: department, integrations, trigger type, output format, frequency |
| 2. Search | Researcher module scans `workflows/`, `Github Access/n8n-workflows-main/`, `Github Access/ultimate-n8n-ai-workflows-main/` for similar patterns |
| 3. Plan | Planner module decomposes into workflow spec draft |
| 4. Spec | Spec Writer fills WORKFLOW_SPEC_TEMPLATE with all fields |
| 5. Classify | Assign risk level using CHANGE_RISK_MATRIX |
| 6. Approve | If risk > low: present spec to Ian for approval before building |
| 7. Build | Builder generates deploy script or workflow JSON |
| 8. Validate | Validator checks structure, connections, credentials, policy compliance |
| 9. Test | Tester generates and runs test cases |
| 10. Deploy | Deployer pushes to n8n (inactive by default for medium+ risk) |
| 11. Document | Documentation module updates SOPs and changelogs |
| 12. Monitor | Monitoring analyst watches first 24h of executions |

**Decision criteria:**
- If reuse score > 80% from researcher: adapt existing workflow instead of building from scratch
- If risk = low AND all tests pass: auto-deploy and activate
- If risk = medium: deploy inactive, notify Ian for activation approval
- If risk = high: present full spec + test results, wait for explicit approval

**Escalation:** Cannot determine integrations needed, request touches > 3 departments, conflicting business requirements.

**Logging:** Spec file saved to `autonomous/memory/specs/`, decision log entry, deployment record.

---

## Scenario 2: Existing Workflow Needs Update

**Trigger:** User requests a change, or AWE detects a configuration that needs updating (e.g., API endpoint changed, new field needed).

| Step | Action |
|---|---|
| 1. Identify | Determine which workflow(s) affected and the specific change needed |
| 2. Impact | Assess blast radius: does this change affect downstream workflows? |
| 3. Classify | Risk classification of the change |
| 4. Plan | Generate a change spec (what changes, why, rollback plan) |
| 5. Implement | Apply changes to BOTH live workflow AND deploy script (source of truth rule) |
| 6. Validate | Run validator on updated workflow |
| 7. Test | Run regression tests + targeted tests for the change |
| 8. Deploy | Push updated workflow |
| 9. Verify | Monitor first 3 executions post-change |

**Decision criteria:**
- If change is additive only (new logging, new field, new notification): low risk, auto-apply
- If change modifies existing logic: medium risk, present diff for approval
- If change touches financial/credential/compliance logic: high risk, full approval cycle

**Critical rule:** NEVER update a live workflow without also updating `tools/deploy_*.py`. The deploy script is the source of truth. A fix applied only to live n8n is wiped on redeployment.

**Escalation:** Change affects payment flows, change requires new credentials, downstream impact unclear.

**Logging:** Change spec, before/after diff of deploy script, deployment record.

---

## Scenario 3: Workflow Breaks in Production

**Trigger:** Execution monitor detects consecutive errors (threshold: 3), or KPI engine reports health score drop.

| Step | Action |
|---|---|
| 1. Detect | Monitoring analyst identifies the failure via `execution_monitor.fetch_recent_executions()` |
| 2. Triage | Incident responder classifies severity (P1-P4) using INCIDENT_SEVERITY policy |
| 3. Investigate | Debugger fetches execution data, error messages, workflow JSON |
| 4. Diagnose | Compare error against known patterns in `autonomous/playbooks/` |
| 5. Decide | Known pattern + confidence > 80% → auto-fix. Unknown → escalate. |
| 6. Fix | Apply fix to live workflow AND deploy script |
| 7. Validate | Run validator + tester on fixed workflow |
| 8. Verify | Monitor next 3 executions |
| 9. Document | Create incident report from INCIDENT_TEMPLATE |
| 10. Learn | Store pattern in playbooks if new failure type |

**Decision criteria by severity:**

| Severity | Auto-fix allowed? | Response time target | Notification |
|---|---|---|---|
| P1 (critical) | Only if confidence > 90% AND known pattern | < 15 min | Telegram immediate + email |
| P2 (high) | If confidence > 80% AND known pattern | < 1 hour | Telegram + email summary |
| P3 (medium) | Yes, if confidence > 70% | < 4 hours | Daily summary |
| P4 (low) | Yes | Next business day | Weekly summary |

**Escalation:** Unknown error type, P1 severity with < 90% confidence, fix requires credential change, error in payment/invoice workflow.

**Logging:** Incident record (Airtable), execution error data, fix applied, verification results.

---

## Scenario 4: API Behavior Changes Upstream

**Trigger:** External API returns unexpected response format, new error codes, or deprecation warnings.

| Step | Action |
|---|---|
| 1. Detect | Execution monitor sees new error patterns (HTTP 4xx/5xx, schema mismatch) |
| 2. Classify | Is this transient (retry-able) or permanent (API changed)? |
| 3. Investigate | Check API documentation (Context7 MCP), compare expected vs actual response |
| 4. Assess | How many workflows are affected? Which departments? |
| 5. Plan | Generate update spec for affected workflows |
| 6. Update | Modify Code nodes / HTTP Request nodes to handle new format |
| 7. Test | Run integration tests against live API |
| 8. Deploy | Push fixes |

**Decision criteria:**
- If transient (< 3 occurrences in 1 hour): increase retry count, monitor
- If schema changed but backward-compatible: auto-update parsers, low risk
- If breaking change: escalate immediately, pause affected workflows

**Escalation:** Breaking API change affecting > 2 workflows, authentication flow changed, rate limiting imposed.

**Logging:** API change record, affected workflows, fix applied, test results.

---

## Scenario 5: Output Quality Degrades

**Trigger:** AI node outputs score below quality threshold, business KPIs decline (e.g., email open rate drops, lead quality drops).

| Step | Action |
|---|---|
| 1. Detect | KPI engine detects trend below threshold over 3+ data points |
| 2. Isolate | Which workflow stage causes the degradation? Which AI node? |
| 3. Analyze | Compare recent AI outputs to historical baseline |
| 4. Diagnose | Prompt drift? Model change? Input data quality? |
| 5. Fix options | Prompt refinement, model swap, input validation tightening |
| 6. Test | A/B test proposed fix against current version |
| 7. Apply | If improvement confirmed, deploy prompt/model change |

**Decision criteria:**
- If quality drop < 10% from baseline: monitor, don't act yet
- If quality drop 10-25%: propose fix, auto-apply if prompt-only change
- If quality drop > 25%: escalate, pause affected workflow outputs

**Escalation:** Quality drop in client-facing communications, legal/compliance content quality issues.

**Logging:** Quality metrics over time, root cause analysis, fix applied, A/B test results.

---

## Scenario 6: Reliability Drops Below Threshold

**Trigger:** Workflow success rate drops below 90% over 24h rolling window (or agent-specific threshold from `agent_registry.py`).

| Step | Action |
|---|---|
| 1. Detect | KPI engine: `compute_all_agent_scores()` shows health below threshold |
| 2. Scope | Which specific workflows are failing? Is it one or multiple? |
| 3. Correlate | Intelligence engine: is this correlated with other department failures? |
| 4. Diagnose | Single root cause or multiple independent failures? |
| 5. Prioritize | Fix highest-impact workflow first (by business KPI weight) |
| 6. Fix | Enter repair loop for each affected workflow |
| 7. Verify | Health score must return to threshold within 4 hours |

**Decision criteria:**
- Single workflow failing: standard repair loop
- Multiple workflows, same root cause (e.g., Airtable API down): fix once, apply everywhere
- Multiple workflows, different causes: parallel repair loops, prioritized by impact

**Escalation:** Reliability < 70% for any Tier 1-2 agent, reliability < 50% system-wide.

**Logging:** Health score timeline, affected workflows, repair actions, time-to-recovery.

---

## Scenario 7: Workflow Becomes Outdated

**Trigger:** Revamp agent identifies workflow that hasn't been updated in > 90 days, uses deprecated nodes, or has accumulated > 5 incidents.

| Step | Action |
|---|---|
| 1. Score | Compute maintainability score: age, incident frequency, code complexity, deprecated dependencies |
| 2. Decide | Revamp (full rebuild) vs patch (incremental fixes) |
| 3. Spec | If revamp: generate new spec from current business requirements |
| 4. Build | Build replacement workflow in parallel (don't touch the live one) |
| 5. Test | Run full test suite on replacement |
| 6. Compare | Side-by-side execution: old vs new with same inputs |
| 7. Cutover | If new version passes all tests: replace live workflow |
| 8. Archive | Move old workflow JSON to `workflows/{dept}/archive/` |

**Decision criteria:**
- Maintainability score > 70: patch, don't revamp
- Maintainability score 40-70: patch if < 3 incidents in last 30 days, else revamp
- Maintainability score < 40: revamp
- Deprecated node detected: revamp (deprecated nodes may stop working)

**Escalation:** Revamp touches financial workflows, revamp estimated > 1 week effort.

**Logging:** Maintainability assessment, revamp decision rationale, old/new comparison results.

---

## Scenario 8: Multiple Fix Options Exist

**Trigger:** Debugger identifies 2+ viable fixes for a workflow issue.

| Step | Action |
|---|---|
| 1. Enumerate | List all fix options with confidence scores |
| 2. Score | Rank by: confidence, risk level, reversibility, implementation effort |
| 3. Select | Choose highest-confidence fix that is within autonomous policy bounds |
| 4. Test | Apply top fix in test, verify resolution |
| 5. Fallback | If top fix fails, try next option |
| 6. Exhaust | If all options exhausted or confidence < 60%: escalate |

**Decision criteria:**
- If top fix confidence > 85% AND risk = low: auto-apply
- If top fix confidence 70-85%: apply but monitor closely (3 executions)
- If all fixes < 70% confidence: escalate with ranked options for Ian to choose

**Escalation:** All fixes < 70% confidence, fix options have conflicting trade-offs (e.g., faster but less reliable).

**Logging:** All options enumerated, scores, selection rationale, test results for attempted fixes.

---

## Scenario 9: Confidence Too Low for Autonomous Action

**Trigger:** Any module reports confidence below its action threshold.

| Step | Action |
|---|---|
| 1. Pause | Do NOT take the action |
| 2. Document | Write up what was planned, why confidence is low, what information is missing |
| 3. Present | Send structured summary to Ian via Telegram/email |
| 4. Wait | Hold task in pending state |
| 5. Resume | When Ian provides direction, resume from the paused stage |

**Information to present:**
```
WORKFLOW: [name]
ACTION PLANNED: [description]
CONFIDENCE: [score]%
REASON FOR LOW CONFIDENCE: [specific unknowns]
OPTIONS:
  A) [option + expected outcome]
  B) [option + expected outcome]
  C) Do nothing (consequences)
RECOMMENDED: [option]
AWAITING: Your decision
```

**Decision criteria:**
- Always pause. Low confidence = do not act.
- If no response within 24h: send reminder
- If no response within 48h: apply lowest-risk option (usually "do nothing") and log

**Logging:** Paused task record, options presented, final decision, time-to-resolution.

---

## Cross-Cutting Rules

1. **Every action is logged** — No silent changes. Every stage writes to decision log.
2. **Deploy script = source of truth** — Live workflow fixes must update `tools/deploy_*.py` + `.env`.
3. **No $env in Code nodes** — n8n Cloud blocks this. Hardcode values or pass via parameters.
4. **Safety caps are absolute** — Ad spend R2K/day, invoice auto-approve < R10K, escalate > R50K. AWE cannot override these.
5. **One execution loop at a time per workflow** — No parallel repair + optimize on the same workflow.
6. **Rollback before retry** — If a fix makes things worse, rollback to previous state before trying the next fix.
7. **Escalation chain** — Follows `agent_registry.get_escalation_chain()`: agent → parent → chief → ian@anyvisionmedia.com.
8. **Token budget awareness** — AWE must track its own token usage against the system budget (200K/day total).

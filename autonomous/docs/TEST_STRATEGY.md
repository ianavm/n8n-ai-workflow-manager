# Testing Framework — AVM Autonomous Workflow Engineer

> Cross-references: [EXECUTION_LOOPS.md](EXECUTION_LOOPS.md), [DEPLOYMENT_POLICY.md](../policies/DEPLOYMENT_POLICY.md), Tester prompt (`autonomous/prompts/tester.md`)

---

## Test Categories

### 1. Unit Tests — Node Config Validation

| Field | Value |
|---|---|
| **Objective** | Verify individual node configurations are correct |
| **When it runs** | After build (Stage 7 of Build Loop), before deployment |
| **What it validates** | Node `type` is valid, `typeVersion` is supported, required `parameters` present, Code node syntax is valid JavaScript |
| **Pass/fail** | Pass: all nodes have valid configs. Fail: any node missing required params or using unsupported type |
| **On failure** | Return to Builder with specific node + parameter that failed |
| **Autonomous fix** | Yes — config errors are low-risk and deterministic |

**Example checks:**
- Airtable node has `baseId` and `tableId`
- Code node `jsCode` doesn't reference `$env`
- Switch node uses `rules.values` not `rules.rules`
- Multi-output Code node has `numberOfOutputs` matching return array length

### 2. Component Tests — Sub-Workflow Correctness

| Field | Value |
|---|---|
| **Objective** | Verify isolated sections of a workflow produce correct outputs for given inputs |
| **When it runs** | After build, before deployment |
| **What it validates** | Data transformation logic, branching paths (If/Switch), Code node output shapes |
| **Pass/fail** | Pass: output matches expected for all test inputs. Fail: output differs or errors |
| **On failure** | Return to Builder with input→output mismatch details |
| **Autonomous fix** | Yes — logic errors in Code nodes are fixable with high confidence |

**Example checks:**
- Code node that calculates ROAS returns correct value for sample data
- Switch node routes "Google Ads" records to output 0 and "Meta" to output 1
- Score calculation sub-workflow returns 0-100 for edge case inputs (0, null, max values)

### 3. Integration Tests — API Connectivity

| Field | Value |
|---|---|
| **Objective** | Verify external services are reachable and credentials work |
| **When it runs** | Before deployment (Tier 2+), after credential changes |
| **What it validates** | API responds, auth succeeds, response shape matches expected |
| **Pass/fail** | Pass: API returns 2xx, response has expected fields. Fail: 4xx/5xx or timeout |
| **On failure** | If auth failure: escalate (credential issue). If timeout: retry, then log as P3 |
| **Autonomous fix** | No — credential issues require Ian. Timeout issues: increase timeout parameter only |

**Example checks:**
- Airtable: `GET /v0/{baseId}/{tableId}?maxRecords=1` returns 200
- OpenRouter: `POST /api/v1/chat/completions` with test prompt returns valid response
- n8n API: `GET /api/v1/workflows?limit=1` returns 200

### 4. End-to-End Tests — Full Execution

| Field | Value |
|---|---|
| **Objective** | Run the entire workflow with test data and verify complete flow |
| **When it runs** | Before deployment (medium + high risk), after revamp |
| **What it validates** | Trigger fires, data flows through all nodes, outputs are correct, no errors |
| **Pass/fail** | Pass: workflow completes with `status: success`, outputs match expected. Fail: any node errors |
| **On failure** | Run Debugger on failed node, fix, retest |
| **Autonomous fix** | Depends on risk level — low risk yes, medium with veto, high requires approval |

**Test data strategy:**
- Use `[TEST]` prefix on any records written to Airtable/Google Sheets
- Use test email address (ian+test@anyvisionmedia.com) for email tests
- Use small budget values (R1) for ad-related tests
- Clean up all test artifacts after execution

### 5. Simulation Tests — Mock External APIs

| Field | Value |
|---|---|
| **Objective** | Verify workflow logic with controlled inputs (no real API calls) |
| **When it runs** | During build validation (all risk levels), when real API is unavailable |
| **What it validates** | Branching logic, error handling, data transformations, with deterministic inputs |
| **Pass/fail** | Pass: all paths exercised correctly. Fail: unexpected branching or output |
| **On failure** | Fix logic in Builder, retest |
| **Autonomous fix** | Yes — simulation failures are pure logic issues |

**Mock approach:**
- Replace HTTP Request nodes with Set nodes containing sample response data
- Test each branch of If/Switch nodes with targeted inputs
- Test empty/null/malformed inputs for error handling paths

### 6. Failure Injection Tests — Chaos Engineering

| Field | Value |
|---|---|
| **Objective** | Verify workflow handles failures gracefully |
| **When it runs** | Before deployment (high risk only) |
| **What it validates** | `continueOnFail` works, fallback paths activate, error notifications send |
| **Pass/fail** | Pass: workflow degrades gracefully, doesn't crash, alerts fire. Fail: unhandled exception or silent failure |
| **On failure** | Add missing error handling, retest |
| **Autonomous fix** | Yes — adding `continueOnFail` and error paths is low-risk |

**Injection scenarios:**
- Simulate Airtable 503 (service unavailable)
- Simulate OpenRouter rate limit (429)
- Simulate empty response from Google Ads API
- Simulate malformed JSON from webhook input

### 7. Regression Tests — Post-Change Verification

| Field | Value |
|---|---|
| **Objective** | Verify existing functionality still works after a change |
| **When it runs** | After every change (fix, optimization, revamp) |
| **What it validates** | All previously passing tests still pass |
| **Pass/fail** | Pass: no new failures. Fail: previously passing test now fails (regression) |
| **On failure** | Rollback the change, investigate regression |
| **Autonomous fix** | Rollback is automatic; re-fix requires new diagnosis |

### 8. Schema Tests — Data Shape Validation

| Field | Value |
|---|---|
| **Objective** | Verify data schemas match between systems |
| **When it runs** | Weekly scheduled, and before deployment |
| **What it validates** | Airtable field types match expectations, API response shapes, Google Sheets column layouts |
| **Pass/fail** | Pass: all schemas match. Fail: field missing, type changed, column shifted |
| **On failure** | Log as P3, identify which workflows are affected, propose fixes |
| **Autonomous fix** | Low risk: update field references. High risk: schema migration requires approval |

**Example checks:**
- Airtable Campaigns table has field "Status" (singleSelect with options: Active/Paused/Draft)
- Google Sheets LinkedIn pipeline has columns in expected order
- OpenRouter API response includes `choices[0].message.content`

### 9. Prompt-Output Validation — AI Quality

| Field | Value |
|---|---|
| **Objective** | Verify AI node outputs meet quality standards |
| **When it runs** | After deployment (first 5 executions), after model/prompt changes |
| **What it validates** | Output format matches spec, content is relevant, no hallucinations in structured data |
| **Pass/fail** | Pass: output parseable, relevant, within expected length. Fail: unparseable, irrelevant, or hallucinated data |
| **On failure** | Refine prompt, retest. If model issue: flag for model swap evaluation |
| **Autonomous fix** | Yes for prompt refinements (low risk). No for model swaps (medium risk) |

**Quality checks:**
- JSON output is valid JSON (if expected)
- Strategy recommendations reference real platforms (Google/Meta/TikTok)
- Content output is within word count bounds
- Score values are within 0-100 range

---

## Test Coverage Requirements by Risk Level

| Risk Level | Min Coverage | Unit | Integration | E2E | Failure Injection |
|---|---|---|---|---|---|
| Low | 60% | Required | Optional | Optional | No |
| Medium | 80% | Required | Required | Required | Optional |
| High | 90% | Required | Required | Required | Required |

---

## Scoring Frameworks

### Test Coverage Score (0-100)

```
coverage = (nodes_tested / total_nodes) * 100
```

| Score | Rating | Action |
|---|---|---|
| 90-100 | Excellent | Deploy with confidence |
| 80-89 | Good | Deploy for low/medium risk |
| 60-79 | Adequate | Deploy for low risk only, improve coverage |
| < 60 | Insufficient | Block deployment, add tests |

### Workflow Reliability Score (0-100)

```
reliability = (
    success_rate_7d     * 0.40 +   # % of successful executions in last 7 days
    no_incident_score   * 0.30 +   # 100 if 0 incidents/30d, 50 if 1-2, 0 if >3
    test_pass_rate      * 0.20 +   # % of tests passing in last run
    uptime_score        * 0.10     # 100 if no deactivations/30d, 0 if >2
)
```

### Deploy Readiness Score (0-100)

```
readiness = (
    validation_pass     * 0.30 +   # 100 if all checks pass, 50 if warnings only, 0 if failures
    test_coverage       * 0.25 +   # test coverage score
    test_pass_rate      * 0.25 +   # % of tests passing
    spec_completeness   * 0.10 +   # % of spec fields populated
    rollback_ready      * 0.10     # 100 if backup exists and rollback tested, 0 if not
)
```

| Score | Decision |
|---|---|
| 90-100 | Auto-deploy (Tier 3+ for low risk) |
| 70-89 | Deploy with monitoring (medium risk with approval) |
| 50-69 | Fix issues before deploying |
| < 50 | Block — significant gaps |

### Autonomy Confidence Score (0-100)

Measures how confidently AWE can handle this workflow autonomously:

```
confidence = (
    pattern_match       * 0.30 +   # 100 if known pattern, 50 if similar, 0 if novel
    test_coverage       * 0.25 +   # test coverage score
    reliability_history * 0.20 +   # reliability score over last 30 days
    fix_success_rate    * 0.15 +   # % of auto-fixes that worked (from incident memory)
    complexity_inverse  * 0.10     # 100 if <20 nodes, 50 if 20-40, 0 if >40
)
```

| Score | Autonomy Level |
|---|---|
| 85-100 | Full autonomy within tier policy |
| 70-84 | Autonomy with post-action verification |
| 50-69 | Propose and wait for approval |
| < 50 | Advisory only — recommend but don't act |

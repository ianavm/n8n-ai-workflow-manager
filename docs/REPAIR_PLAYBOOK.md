# AWLM Repair Playbook

## Overview

This playbook documents all built-in repair patterns in the AWLM RepairEngine (`tools/repair_engine.py`). Each pattern matches error signatures via regex and applies a deterministic fix.

## Repair Flow

```
1. DETECT   — ExecutionMonitor identifies failing workflows
2. MATCH    — RepairEngine.match_pattern() runs regex against error text
3. SCORE    — ConfidenceScorer evaluates fix confidence (0.0-1.0)
4. GOVERN   — AutonomyGovernor checks action against current tier
5. APPLY    — Fix function modifies workflow JSON in place
6. VALIDATE — SandboxValidator checks the patched workflow
7. PUSH     — n8n_api_helpers.safe_update_workflow() deploys the fix
8. LOG      — DecisionLogger writes to Airtable + local JSON
```

## Pattern Registry

### 1. missing_on_error
- **Error:** Workflow crashes because nodes lack onError
- **Signatures:** `workflow.*crash`, `unhandled.*error`
- **Fix:** Adds `onError: "continueRegularOutput"` to all non-trigger nodes
- **Confidence:** 0.90 | **Risk:** MEDIUM
- **Deploy script update:** Yes

### 2. env_ref_in_code
- **Error:** n8n Cloud blocks `$env` in Code nodes
- **Signatures:** `\$env\.\w+`, `environment.*variable.*not.*defined`
- **Fix:** Replaces `$env.VAR` with the actual value from `.env`
- **Confidence:** 0.95 | **Risk:** MEDIUM
- **Deploy script update:** Yes
- **Note:** Operating Rule 10 — never use `$env` in n8n Cloud Code nodes

### 3. number_of_outputs_missing
- **Error:** Code node returning nested arrays without `numberOfOutputs`
- **Signatures:** `code.*doesn't.*return.*items.*properly`
- **Fix:** Adds `numberOfOutputs: N` based on connection count from the node
- **Confidence:** 0.90 | **Risk:** MEDIUM
- **Deploy script update:** Yes

### 4. airtable_mapping_mode
- **Error:** Airtable create node missing `columns.mappingMode`
- **Signatures:** `could not find field.*fields`
- **Fix:** Adds `columns: {mappingMode: "autoMapInputData", value: null}`
- **Confidence:** 0.90 | **Risk:** MEDIUM
- **Deploy script update:** Yes

### 5. switch_wrong_key
- **Error:** Switch v3 uses `rules.rules` instead of `rules.values`
- **Signatures:** `could not find property option`
- **Fix:** Renames `rules.rules` to `rules.values`, removes bare `combinator`
- **Confidence:** 0.90 | **Risk:** MEDIUM
- **Deploy script update:** Yes

### 6. duplicate_node_names
- **Error:** Multiple nodes with the same name causing reference errors
- **Signatures:** `duplicate.*node.*name`, `ambiguous.*node.*reference`
- **Fix:** Appends numbered suffix to duplicates: `Node Name (2)`, `Node Name (3)`
- **Confidence:** 0.85 | **Risk:** HIGH (structural)
- **Deploy script update:** Yes

### 7. missing_continue_on_fail
- **Error:** HTTP/API nodes crash workflow on transient network errors
- **Signatures:** `ECONNRESET`, `ETIMEDOUT`, `ECONNREFUSED`, `socket hang up`
- **Fix:** Adds `continueOnFail: true` and `alwaysOutputData: true`
- **Confidence:** 0.85 | **Risk:** MEDIUM
- **Deploy script update:** Yes

### 8. execution_order_v1
- **Error:** Unpredictable node execution order
- **Signatures:** `execution.*order`
- **Fix:** Sets `settings.executionOrder = "v1"`
- **Confidence:** 0.95 | **Risk:** LOW
- **Deploy script update:** No

### 9. rate_limited (delegate)
- **Error:** 429 / rate limit / quota exceeded
- **Signatures:** `429`, `rate.limit`, `too.many.requests`
- **Fix:** None (delegates to existing self-healing workflow for retry)
- **Confidence:** 0.85 | **Risk:** MEDIUM

### 10. airtable_token_expired (escalate)
- **Error:** 401 Invalid token — credential rotation needed
- **Signatures:** `401.*invalid.*token`, `AUTHENTICATION_REQUIRED`
- **Fix:** None (CRITICAL — credential changes require human approval)
- **Confidence:** 0.95 | **Risk:** CRITICAL

### 11. node_expression_error (low confidence)
- **Error:** Expression references non-existent upstream node
- **Signatures:** `expression.*error`, `Cannot read.*undefined`
- **Fix:** None (needs AI to trace correct node name — proposed only)
- **Confidence:** 0.50 | **Risk:** HIGH

### 12. placeholder_leak
- **Error:** Output contains unreplaced placeholders like `[First Name]`
- **Signatures:** `\[First Name\]`, `\[Business Name\]`
- **Fix:** None (needs context-specific replacement — proposed only)
- **Confidence:** 0.70 | **Risk:** MEDIUM

## Adding New Patterns

To register a custom pattern:

```python
from repair_engine import RepairEngine, RepairPattern
from autonomy_governor import ActionType, RiskLevel

def my_fix(wf: dict) -> list:
    changes = []
    # ... modify wf in place ...
    return changes

engine = RepairEngine(client)
engine.register_pattern(RepairPattern(
    pattern_id="my_custom_fix",
    name="Description",
    description="When this error happens...",
    error_signatures=[r"regex.*pattern"],
    node_types_affected=["n8n-nodes-base.httpRequest"],
    fix_function=my_fix,
    confidence=0.80,
    risk_level=RiskLevel.MEDIUM,
    action_type=ActionType.UPDATE_NODE_PARAMS,
    requires_deploy_script_update=True,
))
```

## Pattern Learning

The RepairPatternStore tracks success/failure rates for each pattern. Patterns with a success rate below 50% are automatically demoted to "propose only" — they will match but not auto-apply.

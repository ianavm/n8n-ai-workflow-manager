# Incident Report

> Copy this template to `autonomous/memory/incidents/inc_{date}_{seq}.json` (as structured JSON) and fill all required fields.

---

## Identification

| Field | Value | Required |
|---|---|---|
| **Incident ID** | INC-{YYYY-MM-DD}-{SEQ} | Yes |
| **Severity** | P1 / P2 / P3 / P4 | Yes |
| **Status** | open / investigating / resolved / escalated | Yes |
| **Workflow ID** | | Yes |
| **Workflow Name** | | Yes |
| **Department** | | Yes |
| **Owner Agent** | | Yes |

## Timeline

| Field | Value | Required |
|---|---|---|
| **Detected At** | ISO 8601 timestamp | Yes |
| **Acknowledged At** | ISO 8601 timestamp | Yes |
| **Resolved At** | ISO 8601 timestamp | Yes (if resolved) |
| **Total Resolution Time** | minutes | Yes (if resolved) |
| **Detection Method** | monitoring_analyst / execution_monitor / user_report | Yes |

## Symptoms

| Field | Value | Required |
|---|---|---|
| **Error Message** | Exact error text from execution | Yes |
| **Error Type** | config_error / data_error / api_error / logic_error / platform_error | Yes |
| **Failed Node** | Node name that errored | Yes |
| **Execution IDs** | List of affected execution IDs | Yes |
| **Consecutive Failures** | Count | Yes |
| **User Impact** | Description of business impact | Yes (P1/P2) |

## Root Cause

| Field | Value | Required |
|---|---|---|
| **Root Cause** | Detailed description | Yes |
| **Root Cause Category** | config / data / api / logic / platform | Yes |
| **Confidence** | 0-100% | Yes |
| **Evidence** | Specific data points supporting diagnosis | Yes |
| **Recent Changes** | Any deployments or changes in last 24h | Yes |

## Fix Applied

| Field | Value | Required |
|---|---|---|
| **Fix Description** | What was changed | Yes (if fixed) |
| **Fix Method** | auto_fix / manual_fix / rollback / workaround | Yes (if fixed) |
| **Files Changed** | List of modified files (deploy script, workflow JSON) | Yes (if fixed) |
| **Fix Confidence** | 0-100% | Yes (if fixed) |
| **Deploy Script Updated** | Yes / No / N/A | Yes |

## Verification

| Field | Value | Required |
|---|---|---|
| **Verification Method** | test_execution / monitoring / manual_check | Yes (if fixed) |
| **Executions Post-Fix** | Count successful post-fix executions | Yes (if fixed) |
| **Regression Check** | Pass / Fail / Skipped | Yes (if fixed) |

## Downstream Impact

| Field | Value | Required |
|---|---|---|
| **Downstream Workflows Affected** | List of workflow IDs/names | If applicable |
| **Cascading Failures** | Yes / No | Yes |
| **Data Integrity Impact** | Description (records corrupted, missing, etc.) | If applicable |

## Lessons Learned

| Field | Value | Required |
|---|---|---|
| **What went wrong** | | Yes (P1/P2) |
| **What went right** | | Optional |
| **Pattern ID** | New or existing pattern from `autonomous/memory/patterns/` | If applicable |
| **Prevention Measures** | What to do to prevent recurrence | Yes (P1/P2) |
| **Policy Updates Needed** | Any changes to risk matrix, thresholds, etc. | Optional |

---

## JSON Schema

For programmatic storage in `autonomous/memory/incidents/`:

```json
{
  "incident_id": "INC-2026-04-07-001",
  "severity": "P2",
  "status": "resolved",
  "workflow_id": "cfDyiFLx0X89s3VL",
  "workflow_name": "ADS-05 Optimizer",
  "department": "ads",
  "owner_agent": "growth_paid",
  "detected_at": "2026-04-07T08:15:00Z",
  "acknowledged_at": "2026-04-07T08:16:00Z",
  "resolved_at": "2026-04-07T08:42:00Z",
  "resolution_time_min": 27,
  "detection_method": "monitoring_analyst",
  "error_message": "Code doesn't return items properly",
  "error_type": "config_error",
  "failed_node": "Parse Optimizations",
  "execution_ids": ["exec_123", "exec_124", "exec_125"],
  "consecutive_failures": 3,
  "user_impact": "Optimization recommendations not generated for daily cycle",
  "root_cause": "Missing numberOfOutputs parameter on Code node with 2 output branches",
  "root_cause_category": "config",
  "confidence": 95,
  "evidence": ["Code node returns array of 2 arrays but numberOfOutputs not set"],
  "recent_changes": ["ADS-05 redeployed 2026-04-06 with new parse logic"],
  "fix_description": "Added numberOfOutputs: 2 to Parse Optimizations node parameters",
  "fix_method": "auto_fix",
  "files_changed": ["tools/deploy_ads_dept.py", "workflows/ads-dept/ads-05-optimizer.json"],
  "fix_confidence": 95,
  "deploy_script_updated": true,
  "verification_method": "test_execution",
  "executions_post_fix": 3,
  "regression_check": "pass",
  "downstream_affected": ["ADS-08 Reporting"],
  "cascading_failures": false,
  "lessons_learned": "Always set numberOfOutputs on multi-output Code nodes",
  "pattern_id": "PAT-001",
  "prevention_measures": "Validator now checks for numberOfOutputs on all Code nodes",
  "tags": ["n8n-code-node", "multi-output", "parameter-missing"]
}
```

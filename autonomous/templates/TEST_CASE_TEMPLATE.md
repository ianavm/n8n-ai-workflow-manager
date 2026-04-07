# Test Case Template

> Copy this template for each test case. Store results in `autonomous/memory/test_history/`.

---

## Test Case Definition

| Field | Value |
|---|---|
| **Test ID** | TC-{workflow_abbrev}-{seq} (e.g., TC-ADS01-001) |
| **Test Name** | Short descriptive name |
| **Workflow Under Test** | Workflow name + ID |
| **Test Type** | unit / integration / e2e / simulation / failure_injection / regression / schema / prompt_validation |
| **Risk Level of Workflow** | low / medium / high |
| **Priority** | critical_path / important / nice_to_have |
| **Created** | Date |
| **Last Run** | Date |

## Preconditions

| # | Condition | Required |
|---|---|---|
| 1 | | Yes / No |
| 2 | | Yes / No |

## Test Data

| Input | Value | Source |
|---|---|---|
| | | static / generated / from_airtable / mock |

## Expected Outcome

| Field | Expected Value |
|---|---|
| **Execution Status** | success / error (for failure injection tests) |
| **Output Data** | Expected output shape or values |
| **Side Effects** | Records created, emails sent, etc. |
| **Error Handling** | Expected behavior on failure path |

## Actual Result (Filled After Execution)

| Field | Value |
|---|---|
| **Status** | pass / fail / skip / flaky |
| **Execution ID** | |
| **Actual Output** | |
| **Actual Side Effects** | |
| **Duration** | seconds |
| **Notes** | |

## Cleanup

| Action | Required |
|---|---|
| Delete `[TEST]` records from Airtable | Yes / No |
| Delete test workflow from n8n | Yes / No |
| Revert test data changes | Yes / No |

---

## JSON Schema

For programmatic storage:

```json
{
  "test_id": "TC-ADS01-001",
  "test_name": "ADS-01 generates strategy for all active platforms",
  "workflow_id": "mrzwNb9Eul9Lq2uM",
  "workflow_name": "ADS-01 Strategy Engine",
  "test_type": "e2e",
  "risk_level": "medium",
  "priority": "critical_path",
  "preconditions": [
    "Airtable Performance table has >= 1 record",
    "Airtable Budget_Allocations has entries for Google, Meta, TikTok",
    "OpenRouter API key is valid"
  ],
  "test_data": {
    "performance_records": [
      {"campaign_id": "TEST-001", "platform": "google_ads", "spend": 100, "clicks": 50, "conversions": 5, "roas": 2.5}
    ],
    "budget_allocations": [
      {"platform": "google_ads", "daily_budget": 500, "weekly_budget": 3000}
    ]
  },
  "expected": {
    "status": "success",
    "output": "At least 1 campaign strategy record created per active platform",
    "side_effects": ["Airtable Campaigns record created", "Gmail strategy email sent"],
    "error_handling": "N/A (happy path)"
  },
  "actual": {
    "status": "pass",
    "execution_id": "exec_789",
    "output": "3 campaign strategies created (Google, Meta, TikTok)",
    "side_effects": ["3 Airtable records created", "1 Gmail sent"],
    "duration_sec": 42.5,
    "notes": ""
  },
  "cleanup": {
    "delete_test_records": true,
    "delete_test_workflow": false,
    "revert_data": false
  },
  "run_history": [
    {"date": "2026-04-07", "status": "pass", "duration_sec": 42.5},
    {"date": "2026-04-06", "status": "pass", "duration_sec": 38.1}
  ]
}
```

---

## Example Test Cases by Type

### Unit Test Example

| Field | Value |
|---|---|
| **Test ID** | TC-ADS01-U01 |
| **Test Name** | Budget cap enforcement in Code node |
| **Test Type** | unit |
| **Input** | `{daily_budget: 5000, weekly_budget: 25000}` (exceeds R2K/day cap) |
| **Expected** | Budget capped to `{daily_budget: 2000, weekly_budget: 10000}` |

### Integration Test Example

| Field | Value |
|---|---|
| **Test ID** | TC-ADS01-I01 |
| **Test Name** | Airtable Performance table read |
| **Test Type** | integration |
| **Precondition** | Airtable API accessible, credential valid |
| **Expected** | Returns records array, HTTP 200, each record has `campaign_id` field |

### Failure Injection Example

| Field | Value |
|---|---|
| **Test ID** | TC-ADS01-F01 |
| **Test Name** | OpenRouter API timeout handling |
| **Test Type** | failure_injection |
| **Injection** | Replace OpenRouter URL with non-routable address |
| **Expected** | `continueOnFail` activates, fallback path sends "AI unavailable" email, workflow completes |

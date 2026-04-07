# Workflow Specification Template

> All fields are **required** unless marked *(optional)*.
> Copy this template to `autonomous/memory/specs/{workflow-name}-spec.md` and fill in all fields.

---

## Identification

| Field | Value |
|---|---|
| **Workflow Name** | |
| **Workflow ID** | *(assigned after deployment)* |
| **Version** | 1.0 |
| **Department** | |
| **Owner Agent** | *(from agent_registry.py)* |
| **Created** | |
| **Last Modified** | |
| **Spec Author** | AWE Planner / Ian |

## Business Purpose

| Field | Value |
|---|---|
| **Business Purpose** | *(1-2 sentences: what business outcome does this achieve?)* |
| **Stakeholder** | |
| **Business KPI** | *(measurable business metric this affects)* |
| **Technical KPI** | *(measurable technical metric: execution time, error rate, etc.)* |

## Triggers

| Field | Value |
|---|---|
| **Trigger Type** | schedule / webhook / manual / sub-workflow |
| **Schedule** | *(cron expression or description, e.g., "Mon 07:00 SAST")* |
| **Webhook Path** | *(if webhook)* |
| **Called By** | *(if sub-workflow: parent workflow name)* |

## Data Flow

### Inputs

| Input | Source | Data Type | Required | Example |
|---|---|---|---|---|
| | | | | |

### Outputs

| Output | Destination | Data Type | Example |
|---|---|---|---|
| | | | |

## Dependencies

| Dependency | Type | ID/Name | Required |
|---|---|---|---|
| | upstream_workflow / api / database / sub_workflow | | |

## Integrations & Credentials

| System | Operation | n8n Credential Name | Credential ID |
|---|---|---|---|
| | read / write / create / update / send | | |

## Risk Classification

| Field | Value |
|---|---|
| **Risk Level** | low / medium / high |
| **Risk Justification** | *(why this classification, per CHANGE_RISK_MATRIX.md)* |
| **Department Modifier** | none / +1 (accounting, ads budget) |
| **Effective Risk** | low / medium / high |

## Failure Modes

| # | Failure Mode | Likelihood | Impact | Handling |
|---|---|---|---|---|
| 1 | | low/med/high | low/med/high | retry / fallback / escalate / skip |
| 2 | | | | |
| 3 | | | | |

## Retry & Fallback

| Field | Value |
|---|---|
| **Retry Policy** | *(e.g., 3 retries, 30s backoff)* |
| **Fallback Logic** | *(what happens if all retries fail)* |
| **continueOnFail Nodes** | *(which nodes have continueOnFail: true)* |

## Validation Rules

| Rule | Check | Pass Criteria |
|---|---|---|
| Input validation | | |
| Output validation | | |
| Business logic validation | | |

## Test Requirements

| Test Type | Required | Description |
|---|---|---|
| Unit | yes / no | |
| Integration | yes / no | |
| E2E | yes / no | |
| Failure Injection | yes / no | |

## Monitoring Requirements

| Metric | Threshold | Alert On |
|---|---|---|
| Execution success rate | | < threshold |
| Execution time | | > threshold |
| *(custom metric)* | | |

## Deployment Requirements

| Field | Value |
|---|---|
| **Deploy Script** | `tools/deploy_{dept}.py` |
| **Staging Required** | yes / no |
| **Approval Required** | auto / veto_window / explicit |
| **Post-Deploy Verification** | N executions to monitor |
| **Activation** | auto / manual |

## Rollback Plan

| Field | Value |
|---|---|
| **Rollback Method** | version_restore / deploy_revert / git_revert |
| **Backup Location** | `workflows/{dept}/archive/{name}-prev.json` |
| **Rollback Steps** | *(numbered steps)* |

## Revamp Triggers *(optional)*

| Trigger | Threshold |
|---|---|
| Age without update | > 90 days |
| Incident frequency | > 5 in 30 days |
| Maintainability score | < 40 |

## Audit Notes *(optional)*

*(Any additional context: compliance requirements, client-specific rules, special handling)*

---
---

# FILLED EXAMPLE: ADS-01 Strategy Engine

## Identification

| Field | Value |
|---|---|
| **Workflow Name** | ADS-01 Campaign Strategy Generator |
| **Workflow ID** | mrzwNb9Eul9Lq2uM |
| **Version** | 2.0 |
| **Department** | ads |
| **Owner Agent** | growth_paid |
| **Created** | 2026-04-02 |
| **Last Modified** | 2026-04-04 |
| **Spec Author** | AWE Planner |

## Business Purpose

| Field | Value |
|---|---|
| **Business Purpose** | Generate weekly ad campaign strategies across Google, Meta, and TikTok based on performance data and budget allocation |
| **Stakeholder** | Ian Immelman |
| **Business KPI** | ROAS > 3.0, budget utilization > 85% |
| **Technical KPI** | Execution time < 120s, error rate < 5% |

## Triggers

| Field | Value |
|---|---|
| **Trigger Type** | schedule |
| **Schedule** | Mon 07:00 SAST (`0 7 * * 1` in Africa/Johannesburg) |
| **Webhook Path** | N/A |
| **Called By** | N/A (top of pipeline) |

## Data Flow

### Inputs

| Input | Source | Data Type | Required | Example |
|---|---|---|---|---|
| Campaign performance | Airtable Performance table | JSON records | Yes | `{campaign_id, spend, clicks, conversions, roas}` |
| Budget allocations | Airtable Budget_Allocations table | JSON records | Yes | `{platform, daily_budget, weekly_budget}` |
| Market context | OpenRouter Claude Sonnet | AI-generated text | Yes | Strategy analysis text |

### Outputs

| Output | Destination | Data Type | Example |
|---|---|---|---|
| Campaign strategies | Airtable Campaigns table | Created records | `{name, platform, objective, budget, start_date}` |
| Strategy email | Gmail (ian@anyvisionmedia.com) | HTML email | Weekly strategy summary |
| Event log | Airtable Events table | Created record | `{event_type: "strategy_generated", timestamp}` |

## Dependencies

| Dependency | Type | ID/Name | Required |
|---|---|---|---|
| Airtable Performance data | database | tblH1ztufqk5Kkkln | Yes |
| Airtable Budget Allocations | database | tblhYDUzyzNxnQQXw | Yes |
| OpenRouter API | api | anthropic/claude-sonnet-4 | Yes |
| ADS-04 Performance Monitor | upstream_workflow | rIYu0FHFx741ml8d | Yes (populates performance data) |

## Integrations & Credentials

| System | Operation | n8n Credential Name | Credential ID |
|---|---|---|---|
| Airtable | read (Performance, Budget) + write (Campaigns) | Airtable account | ZyBrcAO6fps7YB3u |
| OpenRouter | AI completion | OpenRouter 2WC | 9ZgHenDBrFuyboov |
| Gmail | send strategy email | Gmail account AVM Tutorial | 2IuycrTIgWJZEjBE |

## Risk Classification

| Field | Value |
|---|---|
| **Risk Level** | medium |
| **Risk Justification** | Generates campaign strategies that influence ad spend allocation; doesn't directly change budgets but informs decisions |
| **Department Modifier** | +1 for ads budget-adjacent |
| **Effective Risk** | medium (no modifier applied — strategy only, not spend execution) |

## Failure Modes

| # | Failure Mode | Likelihood | Impact | Handling |
|---|---|---|---|---|
| 1 | Airtable API timeout on read | Medium | Medium — no strategy generated for the week | Retry 3x, fallback: send "no data" email alert |
| 2 | OpenRouter API error or rate limit | Medium | Medium — no AI analysis | Retry 3x with exponential backoff, fallback: skip AI analysis, use template strategy |
| 3 | Empty performance data (no records) | Low | Low — strategy based on no data | Check record count, if 0: send "insufficient data" email, skip strategy generation |

## Retry & Fallback

| Field | Value |
|---|---|
| **Retry Policy** | 3 retries, 30s exponential backoff on API nodes |
| **Fallback Logic** | If AI fails: generate template-based strategy from historical averages. If Airtable fails: send alert email, skip cycle. |
| **continueOnFail Nodes** | OpenRouter AI node, Gmail send node |

## Validation Rules

| Rule | Check | Pass Criteria |
|---|---|---|
| Input validation | Performance records exist | > 0 records returned from Airtable |
| Output validation | Strategy records created | At least 1 campaign strategy per active platform |
| Business logic validation | Budget within caps | total_budget <= R2,000/day, R10,000/week |

## Test Requirements

| Test Type | Required | Description |
|---|---|---|
| Unit | Yes | Code node logic: budget calculation, platform routing |
| Integration | Yes | Airtable read/write, OpenRouter API call |
| E2E | Yes | Full execution with test data |
| Failure Injection | No | Medium risk — not required |

## Monitoring Requirements

| Metric | Threshold | Alert On |
|---|---|---|
| Execution success rate | > 95% | < 90% over 4 executions |
| Execution time | < 120s | > 180s |
| Strategies generated | >= 1 per platform | 0 strategies in a cycle |

## Deployment Requirements

| Field | Value |
|---|---|
| **Deploy Script** | `tools/deploy_ads_dept.py` |
| **Staging Required** | No (weekly trigger, low blast radius) |
| **Approval Required** | veto_window (1h) |
| **Post-Deploy Verification** | 3 executions |
| **Activation** | Manual (first time), auto thereafter |

## Rollback Plan

| Field | Value |
|---|---|
| **Rollback Method** | version_restore |
| **Backup Location** | `workflows/ads-dept/archive/ads-01-v1.json` |
| **Rollback Steps** | 1. Export current as backup. 2. Push previous JSON via n8n API. 3. Verify with 1 test execution. 4. Update deploy script to match. |

## Revamp Triggers

| Trigger | Threshold |
|---|---|
| Age without update | > 90 days |
| Incident frequency | > 5 in 30 days |
| Maintainability score | < 40 |

## Audit Notes

- Safety caps (R2K/day, R10K/week, R35K/month) are enforced in ADS-03 (publisher), not in ADS-01 (strategy). ADS-01 proposes, ADS-03 enforces.
- OpenRouter model `anthropic/claude-sonnet-4` — update if model ID changes.
- ADS-03 is currently INACTIVE (Google Ads account not enabled). Strategies are generated but not published.

# Observability Specification — AVM Autonomous Workflow Engineer

> Cross-references: [INCIDENT_SEVERITY.md](../policies/INCIDENT_SEVERITY.md), Monitoring Analyst prompt (`autonomous/prompts/monitoring_analyst.md`)

---

## Monitored Metrics

### Workflow Execution Health

| Metric | Source | Collection Method | Frequency |
|---|---|---|---|
| Success rate (per workflow) | n8n executions API | `execution_monitor.fetch_recent_executions()` | Every 15 min |
| Error rate (per workflow) | n8n executions API | Count status=error / total | Every 15 min |
| Timeout rate | n8n executions API | Count status=waiting past deadline | Every 15 min |
| Consecutive errors | n8n executions API | Sequential error count per workflow | Every 15 min |
| Executions per hour | n8n executions API | Count by time bucket | Hourly |

### Latency

| Metric | Source | Collection Method | Frequency |
|---|---|---|---|
| Avg execution time (per workflow) | n8n executions API | `(finishedAt - startedAt)` average | Hourly |
| P95 execution time | n8n executions API | 95th percentile of last 100 executions | Hourly |
| Per-node latency | n8n execution detail | Node-level timing from execution data | On-demand |
| Execution time drift | Computed | Compare current week avg to previous week avg | Daily |

### Retry & Error Patterns

| Metric | Source | Collection Method | Frequency |
|---|---|---|---|
| Retry count (per workflow) | Execution logs | Count retried executions | Hourly |
| Error type distribution | Execution errors | Classify: transient / permanent / config | Hourly |
| Top error messages | Execution errors | Frequency count of error strings | Daily |
| Error correlation | Computed | Cross-workflow error timing overlap | Daily |

### API & Integration Health

| Metric | Source | Collection Method | Frequency |
|---|---|---|---|
| API failure rate (per integration) | Execution node errors | Count failures by node type (Airtable, Gmail, etc.) | Hourly |
| API response time | Execution node timing | Avg time per external API node | Hourly |
| Rate limit hits | HTTP 429 errors | Count from execution data | Hourly |
| Credential validity | n8n health check | `n8n_client.health_check()` | Daily |

### AI Node Quality

| Metric | Source | Collection Method | Frequency |
|---|---|---|---|
| Token usage (per AI node) | OpenRouter API / execution data | Parse token counts from response | Per execution |
| Daily token budget utilization | Aggregated | Sum across all AI nodes | Daily |
| Output quality score | Custom validation | Parse AI output, check format/relevance | Per execution |
| Model error rate | Execution errors | Count AI node failures | Daily |

### Business KPIs

| Metric | Source | Collection Method | Frequency |
|---|---|---|---|
| Invoices processed | Airtable accounting tables | Count new records | Daily |
| Leads captured | Airtable/Google Sheets | Count new leads | Daily |
| Emails sent | Gmail execution logs | Count successful sends | Daily |
| Content published | Airtable content calendar | Count published items | Daily |
| Ad spend (actual vs budget) | Airtable ads performance | Sum spend fields | Daily |
| ROAS | Airtable ads performance | Revenue / spend | Weekly |

---

## Extending Existing Tools

AWE observability builds on top of existing Python tools — it does NOT replace them.

### `execution_monitor.py` Extensions

| Current Capability | AWE Extension |
|---|---|
| `fetch_recent_executions()` — gets raw execution data | Add: classify error types (transient/permanent/config) |
| `detect_consecutive_errors()` — alerts on threshold | Add: correlate across workflows (same API failing?) |
| `generate_health_dashboard()` — text summary | Add: write structured JSON to `autonomous/memory/health_reports/` |

### `orchestrator_kpi_engine.py` Extensions

| Current Capability | AWE Extension |
|---|---|
| `compute_all_agent_scores()` — per-agent health | Add: compute autonomy confidence score |
| `detect_anomalies()` — statistical anomaly detection | Add: trigger Incident Responder when anomaly confirmed |
| `generate_daily_snapshot()` — Airtable write | Add: write to `autonomous/memory/` for local trend analysis |

### `intelligence_engine.py` Extensions

| Current Capability | AWE Extension |
|---|---|
| `compute_correlations()` — cross-dept metric pairs | Add: identify cascading failure patterns |
| `identify_bottlenecks()` — input→output efficiency | Add: feed bottleneck data to Optimizer agent |
| `forecast_trend()` — simple linear forecast | Add: forecast-based revamp trigger (predict when a workflow will degrade) |

---

## Anomaly Detection Thresholds

| Metric | Warning | Alert | Critical | Action |
|---|---|---|---|---|
| Error rate (1h vs 7d avg) | > 2x | > 5x | > 10x | Warning: log. Alert: Incident Responder. Critical: deactivate + P1 |
| Execution time (vs 7d avg) | > 1.5x | > 2x | > 3x | Warning: log. Alert: Optimizer. Critical: Incident Responder |
| Consecutive errors | 2 | 3 | 5 | Warning: log. Alert: Debugger. Critical: deactivate + P1 |
| Health score drop (1h) | > 10 pts | > 20 pts | > 30 pts | Warning: monitor. Alert: investigate. Critical: all-hands |
| Token usage (% daily budget) | > 80% | > 90% | > 100% | Warning: alert Ian. Alert: throttle. Critical: pause AI nodes |
| Missed scheduled runs | 1 | 2 | 3 | Warning: check trigger. Alert: Incident Responder. Critical: P2 |
| API response time (vs avg) | > 2x | > 5x | > 10x | Warning: log. Alert: check API status. Critical: failover |

---

## Logging Schema

Every execution event is logged as structured JSON:

```json
{
  "event_id": "EVT-2026-04-07-001",
  "timestamp": "2026-04-07T08:15:00Z",
  "event_type": "execution_complete | execution_error | anomaly_detected | fix_applied | deployment | rollback",
  "workflow_id": "mrzwNb9Eul9Lq2uM",
  "workflow_name": "ADS-01 Strategy Engine",
  "department": "ads",
  "agent": "growth_paid",
  "execution_id": "12345",
  "status": "success | error | timeout | waiting",
  "duration_sec": 45.2,
  "error": {
    "type": "config_error | data_error | api_error | logic_error | platform_error",
    "message": "",
    "node": "",
    "recoverable": true
  },
  "metrics": {
    "nodes_executed": 12,
    "tokens_used": 1500,
    "api_calls": 3,
    "records_processed": 25
  },
  "awe_action": {
    "action_taken": "none | logged | auto_fixed | escalated | rolled_back",
    "confidence": 95.0,
    "decision_id": "DEC-2026-04-07-001"
  }
}
```

**Storage:** `autonomous/memory/events/` — daily JSON files, rotated monthly.

---

## Auto-Repair Triggers

| Condition | Action | Agent |
|---|---|---|
| 3 consecutive errors on same workflow | Enter Repair Loop | Incident Responder → Debugger |
| Known error pattern matched (confidence > 90%) | Auto-fix | Debugger |
| API timeout + retry exhausted | Increase timeout parameter | Debugger (low-risk auto-fix) |
| Missing `continueOnFail` caused crash | Add `continueOnFail: true` | Debugger (low-risk auto-fix) |
| Airtable field renamed upstream | Update field reference | Debugger (medium risk, veto window) |

## Human Escalation Triggers

| Condition | Notification | Channel |
|---|---|---|
| P1 severity incident | Immediate | Telegram + email |
| P2 severity, auto-fix failed | Within 1h | Telegram |
| Financial workflow any error | Immediate | Telegram |
| Unknown error pattern, confidence < 70% | Within 4h | Telegram + diagnosis report |
| System-wide degradation (> 3 agents) | Immediate | Telegram + email |

## Rollback Triggers

| Condition | Action |
|---|---|
| Post-deploy execution failure (any of first 3) | Auto-rollback |
| Error rate > 50% within 1h of deployment | Auto-rollback |
| Health score drops > 30 points within 1h of change | Auto-rollback |
| Ian sends "ROLLBACK" via Telegram | Immediate rollback |

---

## Dashboard Design

### Real-Time Health Dashboard (Telegram Daily Digest)

```
=== AVM SYSTEM HEALTH — 2026-04-07 ===

OVERALL: ● HEALTHY (score: 87/100)

AGENTS (by tier):
  T1 CHIEF          ● 95  [████████░░]
  T2 FINANCE         ● 88  [████████░░]
  T2 GROWTH_ORGANIC  ● 82  [████████░░]
  T2 GROWTH_PAID     ● 75  [███████░░░]  ⚠ ADS-03 inactive
  T2 PIPELINE        ● 91  [█████████░]
  T3 CLIENT_SUCCESS  ● 85  [████████░░]
  T3 SUPPORT         ● 90  [█████████░]
  T4 SENTINEL        ● 93  [█████████░]
  T4 INTELLIGENCE    ● 87  [████████░░]

24H STATS:
  Executions: 342 (success: 328, error: 14)
  Error rate: 4.1% (target: <5%)
  Avg latency: 23s (target: <60s)
  Token usage: 145K/200K (72%)

INCIDENTS: 1 P3 (auto-resolved), 0 P1/P2
DEPLOYMENTS: 0 today
OPTIMIZATIONS: 1 proposed (SEO-WF10 latency)

AWE TIER: 0 (Advisory)
```

### Weekly Report (Email)

| Section | Content |
|---|---|
| Executive summary | Overall health trend, key metrics vs targets |
| Incident summary | P1-P4 counts, resolution times, patterns |
| Deployment summary | What was deployed, success rate |
| Optimization summary | What was proposed, what was applied, improvement measured |
| Revamp candidates | Workflows approaching maintainability threshold |
| Token budget | Usage vs budget, trending |
| Recommendations | Top 3 actions for the coming week |

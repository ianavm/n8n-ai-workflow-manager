# Monitoring & Alerting SOP

## Objective
Continuously monitor n8n workflow execution health, detect failures early, and respond to issues before they impact operations.

## Prerequisites
- n8n API key configured in `.env`
- `config.json` with monitoring thresholds set
- Execution history available (workflows must have been running)

## Monitoring Thresholds

Configured in `config.json` under `monitoring`:

| Setting | Default | Description |
|---------|---------|-------------|
| `check_interval_minutes` | 15 | How often to check |
| `error_alert_threshold` | 3 | Consecutive failures before alerting |
| `execution_history_days` | 30 | How far back to analyze |

## Running a Monitor Check

```bash
python tools/run_manager.py monitor
```

### What It Does

1. **Connects to n8n** - Verifies instance health
2. **Fetches executions** - Pulls recent execution records
3. **Calculates stats** - Success/failure rates per workflow
4. **Detects failures** - Identifies workflows exceeding error threshold
5. **Finds stale workflows** - Active workflows with no recent executions
6. **Generates dashboard** - Console output with status indicators

### Health Dashboard Output

```
SYSTEM STATUS: HEALTHY
Workflows: 45 total | 32 active | 13 inactive
Executions (last 24h): 1,247 total | 1,198 success | 49 failed
Overall Success Rate: 96.1%

FAILING WORKFLOWS:
  [!] Lead Qualifier Bot - 5 consecutive failures
  [!] WhatsApp Auto-Reply - 3 consecutive failures

STALE WORKFLOWS (active but no executions in 7+ days):
  [?] Old CRM Sync - last run: 2025-01-15
  [?] Test Webhook Handler - last run: 2025-01-20
```

## Interpreting Results

### System Status Levels

| Status | Meaning | Action |
|--------|---------|--------|
| HEALTHY | All workflows running normally | No action needed |
| WARNING | Some failures detected, below threshold | Investigate within 1 hour |
| CRITICAL | Multiple workflows failing above threshold | Investigate immediately |

### Failure Types

| Type | Common Causes | Response |
|------|---------------|----------|
| **API timeout** | External service slow/down | Check third-party service status |
| **Authentication** | Expired credentials | Refresh OAuth tokens or API keys |
| **Rate limiting** | Too many API calls | Reduce execution frequency |
| **Data format** | Unexpected input shape | Check upstream data sources |
| **Node error** | Code bug or config issue | Review node parameters and test data |

## Alerting Strategy

### Automated Monitoring (Recommended)

Set up a scheduled task to run monitoring:

**Windows Task Scheduler:**
```
Action: Start Program
Program: python
Arguments: tools/run_manager.py monitor
Start in: C:\path\to\n8n Agentic Workflows Manager
Trigger: Every 15 minutes
```

**Linux/Mac cron:**
```bash
*/15 * * * * cd /path/to/project && python tools/run_manager.py monitor >> /var/log/n8n_monitor.log 2>&1
```

### Escalation Flow

1. **Auto-detected failure** (via monitor mode)
2. **Check execution logs** in n8n UI for the specific workflow
3. **Identify root cause** (see Failure Types above)
4. **Fix and re-activate** the workflow
5. **Run monitor again** to confirm resolution
6. **Document** the incident and fix

## Key Metrics to Track

| Metric | Healthy Range | Warning | Critical |
|--------|--------------|---------|----------|
| Overall success rate | > 95% | 90-95% | < 90% |
| Consecutive failures | 0-1 | 2-3 | > 3 |
| Stale workflows | 0 | 1-2 | > 3 |
| Avg execution duration | Within 2x baseline | 2-5x baseline | > 5x baseline |

## Output Files

| File | Contents |
|------|----------|
| `.tmp/monitoring_results.json` | Health dashboard data, failing workflows, stale list |
| `.tmp/execution_data.json` | Raw execution records for further analysis |

## Next Steps After Monitoring

- **All healthy:** No action. Schedule next check.
- **Warnings detected:** Run `analyze` mode for deeper investigation.
- **Failures detected:** Fix the workflow, then run `monitor` again.
- **Stale workflows found:** Either deactivate or investigate why they stopped executing.

# Rollback Policy — AVM Autonomous Workflow Engineer

> Cross-references: [DEPLOYMENT_POLICY.md](DEPLOYMENT_POLICY.md), [INCIDENT_SEVERITY.md](INCIDENT_SEVERITY.md), [OPERATING_MODEL.md](../docs/OPERATING_MODEL.md)

## When to Rollback

### Automatic Rollback Triggers (No Approval Needed)

| Trigger | Threshold | Action |
|---|---|---|
| Post-deploy execution failures | Any of first 3 executions fail | Rollback immediately |
| Error rate spike | Error rate > 50% over 1 hour (was < 10% before) | Rollback + alert |
| Consecutive errors | 3+ consecutive errors on previously healthy workflow | Rollback + investigate |
| Health score crash | Agent health score drops > 30 points in 1 hour | Rollback all recent changes to that agent's workflows |

### Manual Rollback Triggers (Escalate to Ian)

| Trigger | Action |
|---|---|
| Business KPI degradation (e.g., invoice accuracy drops) | Alert Ian, propose rollback, wait for decision |
| Data quality issues (wrong records written to Airtable) | Alert Ian, deactivate workflow immediately, propose rollback |
| Credential/auth failure after change | Alert Ian, rollback credential reference (but NOT credential itself) |
| Client-reported issue | Alert Ian, deactivate affected workflow, await direction |

---

## Rollback Methods

### Method 1: n8n Workflow Version Restore

**When:** Live workflow was updated via API (most common).

```python
# Pseudocode — via n8n_client
previous_json = load_backup("workflows/{dept}/archive/{name}-prev.json")
n8n_client.update_workflow(workflow_id, previous_json)
```

**Steps:**
1. Fetch backup from `workflows/{dept}/archive/` (exported before deployment)
2. Push previous version to n8n via `n8n_client.update_workflow()`
3. Verify workflow structure matches backup
4. Run 1 test execution to confirm
5. Log rollback in `autonomous/memory/incidents/`

### Method 2: Deploy Script Revert

**When:** Deploy script was also modified (source-of-truth changes).

**Steps:**
1. `git log tools/deploy_{dept}.py` — find last known-good commit
2. `git show {commit}:tools/deploy_{dept}.py > tools/deploy_{dept}.py` — restore file
3. Re-run `python tools/deploy_{dept}.py build && python tools/deploy_{dept}.py deploy`
4. Verify deployment
5. Log rollback

### Method 3: Git Revert

**When:** Multiple files changed (deploy script + .env + workflow JSON).

**Steps:**
1. `git revert {commit_hash}` — create revert commit
2. Re-deploy affected workflows from reverted deploy script
3. Verify all affected workflows
4. Log rollback

### Method 4: Emergency Deactivation

**When:** Rollback is not immediately possible (no backup, complex interdependency).

**Steps:**
1. `n8n_client.deactivate_workflow(workflow_id)` — stop the bleeding
2. Alert Ian immediately via Telegram
3. Create detailed incident report
4. Wait for manual investigation and resolution

---

## Rollback Verification

After every rollback, verify:

- [ ] Workflow JSON matches the known-good version
- [ ] 1 test execution completes successfully
- [ ] No downstream workflows broken by the rollback
- [ ] Deploy script matches the live workflow (source-of-truth rule)
- [ ] Incident report created with rollback details

---

## Time-to-Rollback Targets

| Risk Level of Change | Max Time to Detect | Max Time to Rollback | Total Recovery Target |
|---|---|---|---|
| Low | 15 min (automatic monitoring) | 5 min (automatic) | 20 min |
| Medium | 15 min | 15 min | 30 min |
| High | 5 min (intensive monitoring) | 30 min (manual approval) | 35 min |

---

## Post-Rollback Actions

1. **Create incident report** from [INCIDENT_TEMPLATE.md](../templates/INCIDENT_TEMPLATE.md)
2. **Store in memory** — incident record with:
   - What was deployed
   - Why it failed
   - How it was rolled back
   - Time to detect, time to rollback
3. **Root cause analysis** — Debugger module investigates why the change failed
4. **Pattern update** — If new failure pattern discovered, add to `autonomous/memory/patterns/`
5. **Re-classify** — If this type of change failed, consider upgrading its risk level in [CHANGE_RISK_MATRIX.md](CHANGE_RISK_MATRIX.md)
6. **Notify Ian** — Telegram summary: what happened, what was rolled back, current status

---

## Backup Requirements

Before ANY deployment, a backup must exist:

| What | Where | Format | Retention |
|---|---|---|---|
| Previous workflow JSON | `workflows/{dept}/archive/{name}-prev.json` | n8n JSON | Until next successful deployment |
| Previous deploy script | Git history | Python | Permanent (git) |
| Previous .env values (relevant lines only) | `autonomous/memory/deployments/{deploy_id}.json` | Key names only (NOT values) | 6 months |

**No backup = no deployment.** If AWE cannot export the current workflow before deploying, the deployment is blocked.

---

## Cascading Rollback

If a rollback on one workflow breaks a downstream workflow:

1. Identify all dependent workflows (from workflow spec `dependencies` field)
2. Rollback dependent workflows in reverse dependency order
3. Verify each rollback independently
4. Alert Ian that cascading rollback occurred
5. Do NOT attempt to re-deploy any of the cascading chain without explicit approval

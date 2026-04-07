# Deployment Policy — AVM Autonomous Workflow Engineer

> Cross-references: [AUTONOMY_POLICY.md](AUTONOMY_POLICY.md), [CHANGE_RISK_MATRIX.md](CHANGE_RISK_MATRIX.md), [ROLLBACK_POLICY.md](ROLLBACK_POLICY.md)

## Core Rule

**Deploy script is source of truth.** Any change to a live n8n workflow MUST be simultaneously applied to `tools/deploy_*.py` and `.env`. Fixes applied only to live workflows are wiped on redeployment.

---

## Pre-Deploy Checklist

Every deployment must satisfy ALL applicable checks:

### Required (All Deployments)

- [ ] Change has a workflow spec or change spec document
- [ ] Risk level classified per [CHANGE_RISK_MATRIX.md](CHANGE_RISK_MATRIX.md)
- [ ] Deploy script updated (not just live workflow)
- [ ] No hardcoded secrets (API keys, tokens, passwords)
- [ ] No `$env` references in Code nodes (n8n Cloud blocks this)
- [ ] All node `typeVersion` fields match n8n Cloud supported versions
- [ ] Connections map is complete (no orphaned nodes)
- [ ] Credential references use correct n8n credential IDs

### Required (Medium + High Risk)

- [ ] Validation passes (validator module, zero critical issues)
- [ ] Tests pass (coverage > 80%)
- [ ] Rollback plan documented and tested
- [ ] Previous version exported (backup via `workflow_deployer.export_workflow()`)
- [ ] Approval received per [APPROVAL_MATRIX.md](APPROVAL_MATRIX.md)

### Required (High Risk Only)

- [ ] Ian has explicitly approved (Telegram/email confirmation)
- [ ] Staging test completed (inactive workflow tested on n8n)
- [ ] Downstream impact assessed (which other workflows depend on this one)
- [ ] Post-deploy monitoring plan defined (what to watch, for how long)

---

## Deployment Process

### Step 1: Build

```bash
python tools/deploy_{dept}.py build
```

- Generates workflow JSON in `workflows/{dept}/`
- Validates node structure locally
- Output: `workflows/{dept}/{workflow_name}.json`

### Step 2: Validate

AWE validator module runs against the generated JSON:
- Node types are valid n8n node types
- All connections reference existing nodes
- Credential IDs exist in n8n (via `n8n_client.list_credentials()`)
- No `$env` in Code node `jsCode` parameters
- Safety caps respected (for ad/financial workflows)
- `numberOfOutputs` set on multi-output Code nodes

### Step 3: Test (Medium + High Risk)

- Create inactive test workflow: `[TEST] {workflow_name}`
- Run test execution via n8n API
- Validate outputs against expected results
- Clean up test workflow after success

### Step 4: Deploy

```bash
python tools/deploy_{dept}.py deploy
```

- POSTs workflow JSON to n8n API via `n8n_client.create_workflow()` or `update_workflow()`
- Records workflow ID
- Workflow is INACTIVE by default

### Step 5: Activate

```bash
python tools/deploy_{dept}.py activate
```

- Activates workflow trigger
- Only proceeds if:
  - Low risk: auto-activate (Tier 3+)
  - Medium risk: approved + 1h veto window passed
  - High risk: Ian explicitly confirmed

### Step 6: Post-Deploy Verification

- Monitor first 3 executions
- Check: successful completion, correct outputs, no error nodes
- If ANY execution fails:
  - Low risk: auto-rollback, log incident
  - Medium/high risk: deactivate immediately, notify Ian, await decision

---

## Deployment by Risk Level

| Risk | Build | Validate | Test | Deploy | Activate | Verify | Approval |
|---|---|---|---|---|---|---|---|
| Low | Required | Required | Optional | Auto (Tier 3+) | Auto (Tier 3+) | 3 executions | None |
| Medium | Required | Required | Required | Auto (Tier 4+) | 1h veto window | 5 executions | Veto-based |
| High | Required | Required | Required | Manual only | Manual only | 10 executions | Explicit |

---

## Batch Deployments

When deploying multiple workflows (e.g., department rewrite):

1. Deploy ALL workflows as INACTIVE first
2. Validate each individually
3. Activate in dependency order (upstream before downstream)
4. Pause 5 minutes between activations
5. Monitor each for 3 successful executions before activating the next
6. If any workflow fails: STOP, do not activate remaining, rollback the failed one

**Example:** Deploying all 8 ADS workflows → activate ADS-01 first (strategy, no dependencies) → verify → ADS-02 (depends on ADS-01) → verify → ... → ADS-08 (reporting, depends on all).

---

## Environment Rules

| Rule | Detail |
|---|---|
| Target | `ianimmelman89.app.n8n.cloud` (production n8n instance) |
| No staging instance | n8n Cloud is single-instance; use inactive workflows with `[TEST]` prefix as staging |
| Test cleanup | Remove `[TEST]` workflows within 24h of creation |
| Credential reuse | Always reference existing n8n credentials by ID; never create new credentials autonomously |
| Branch strategy | Deploy from `master` branch only; feature branches for development |

---

## Post-Deploy Logging

Every deployment creates a record in `autonomous/memory/deployments/`:

```json
{
  "deploy_id": "DEP-2026-04-07-001",
  "workflow_id": "mrzwNb9Eul9Lq2uM",
  "workflow_name": "ADS-01 Strategy Engine",
  "department": "ads",
  "risk_level": "medium",
  "deploy_script": "tools/deploy_ads_dept.py",
  "deployed_at": "2026-04-07T10:00:00Z",
  "activated_at": "2026-04-07T10:05:00Z",
  "verification_status": "passed",
  "executions_monitored": 3,
  "executions_passed": 3,
  "approval_type": "veto_window",
  "approved_by": "auto (no veto received)",
  "rollback_available": true,
  "previous_version_backup": "workflows/ads-dept/archive/ads-01-v2.json"
}
```

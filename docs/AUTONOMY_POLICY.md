# AWLM Autonomy Policy

## Overview

This policy governs the Autonomous Workflow Lifecycle Manager (AWLM) — the system that enables Claude Code to autonomously detect, diagnose, fix, optimise, and revamp n8n workflows within controlled boundaries.

## Autonomy Tiers

| Tier | Name | Description | When to Use |
|------|------|-------------|-------------|
| 1 | Advisory | Log findings only. No actions taken. | First deployment, trust-building. |
| 2 | Supervised | Log + backup. All fixes need explicit approval. | Weeks 2-4 of deployment. |
| 3 | Semi-autonomous | Low + medium risk auto-applied. High/critical need approval. | **DEFAULT** — steady state. |
| 4 | Autonomous | Low + medium + high auto-applied. Critical needs approval. | After 30 days at Tier 3 with >85% success rate. |
| 5 | Near-full | All actions auto-applied. Emergency stop available. | Future consideration only. |

**Current tier:** Set in `config.json` → `lifecycle.autonomy_tier`.

## Risk Classification

### LOW — Read-only and informational
- Fetch metrics and execution data
- Generate reports and dashboards
- Export workflow backups
- Log events and detections

### MEDIUM — Reversible parameter changes
- Retry a failed execution
- Update node parameters (onError, continueOnFail, alwaysOutputData)
- Activate or deactivate a workflow
- Cycle deactivate → reactivate

### HIGH — Structural workflow changes
- Insert or remove nodes
- Rewire connections between nodes
- Deploy a new workflow
- Update a deploy script

### CRITICAL — Irreversible or sensitive changes
- Delete a workflow
- Modify financial workflows (accounting, financial_intel agents)
- Change credential references
- Bulk deactivate workflows

## Special Rules

1. **Financial workflows** — Any workflow owned by `finance` or `financial_intel` agents is treated as CRITICAL risk regardless of the action being taken.
2. **Safety caps** — ZAR limits from `agent_registry.py` are enforced: auto-approve < R10,000, escalate > R50,000.
3. **Protected workflows** — Workflows listed in `config.json` → `lifecycle.protected_workflows` cannot be modified autonomously at any tier.
4. **Deploy script rule** — When a live workflow is patched, the system flags if a corresponding `deploy_*.py` script exists. The deploy script must be updated manually to keep source-of-truth aligned (Operating Rule 9).

## Approval Flow

When an action exceeds the current tier's authority:
1. A record is written to the **Escalation_Queue** Airtable table (Operations Control base)
2. A local decision record is saved to `.tmp/decisions/`
3. The fix is logged as `action_taken: "propose"` with full details
4. Human reviews the proposal and either applies manually or adjusts the tier

## Rollback Policy

Every workflow modification creates:
1. **Pre-fix backup** at `.tmp/backups/{workflow_id}_{timestamp}.json`
2. **Decision_Log entry** with rollback reference
3. **Rollback capability** via `python lifecycle_orchestrator.py rollback <decision_id>`

**Automatic rollback triggers:**
- Error rate increases >20% within 30 minutes of a fix
- Workflow health score drops below the pre-fix score
- Human invokes emergency stop
- Three consecutive failures after fix applied

## Emergency Stop

Invoke via:
```python
from autonomy_governor import AutonomyGovernor
gov = AutonomyGovernor(current_tier=3)
gov.emergency_stop()
```

When active, **all** autonomous actions are blocked until manually reset via `gov.reset_emergency_stop()`.

## Promotion Criteria

To promote from Tier N to Tier N+1:
1. Minimum 30 days operating at Tier N
2. Repair success rate > 85%
3. False positive rate (rollbacks) < 10%
4. Escalation rate < 5 per day
5. No critical incidents caused by autonomous actions

## Token Budget

The AWLM uses AI sparingly — only for novel error classification and fix generation when no regex pattern matches. Estimated daily usage: 1,100-5,500 tokens (vs 194,000/day total budget).

85% of repairs use regex-matched patterns with zero AI cost.

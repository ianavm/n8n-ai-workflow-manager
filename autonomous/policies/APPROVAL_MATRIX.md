# Approval Matrix — AVM Autonomous Workflow Engineer

> Cross-references: [AUTONOMY_POLICY.md](AUTONOMY_POLICY.md), [CHANGE_RISK_MATRIX.md](CHANGE_RISK_MATRIX.md)

## How to Read This Table

- **Auto-Approve Conditions:** When ALL conditions are met, the action proceeds without human review
- **Requires Review By:** Who must approve when auto-approve conditions are NOT met
- **Max Wait:** How long to wait for approval before escalating or applying safe default

---

## Workflow Lifecycle Actions

| # | Action | Risk | Auto-Approve Conditions | Requires Review By | Max Wait |
|---|---|---|---|---|---|
| 1 | Create new workflow spec | Low | Always auto-approve (spec only, no deploy) | — | — |
| 2 | Generate workflow JSON (local file) | Low | Always auto-approve (local only) | — | — |
| 3 | Deploy new workflow (inactive) | Medium | Tier 2+, all tests pass, validation clean | Ian | 24h |
| 4 | Activate workflow trigger | Medium | Tier 3+, risk = low, 3 test executions pass | Ian | 24h |
| 5 | Activate financial workflow trigger | High | Never auto-approve | Ian | 48h |
| 6 | Deactivate workflow | Medium | Tier 3+, workflow has 5+ consecutive errors | Ian | 4h |
| 7 | Delete workflow from n8n | High | Never auto-approve | Ian | 48h |
| 8 | Update existing workflow (low-risk change) | Low | Tier 3+, confidence > 85%, tests pass | — | — |
| 9 | Update existing workflow (medium-risk change) | Medium | Tier 4+, confidence > 90%, rollback tested | Ian (1h veto window) | 4h |
| 10 | Update existing workflow (high-risk change) | High | Never auto-approve | Ian | 48h |

## Code & Script Actions

| # | Action | Risk | Auto-Approve Conditions | Requires Review By | Max Wait |
|---|---|---|---|---|---|
| 11 | Update deploy script (`tools/deploy_*.py`) | Medium | Tier 3+, change matches live workflow fix | Ian | 24h |
| 12 | Create new deploy script | Medium | Tier 2+, generated from approved spec | Ian | 24h |
| 13 | Modify Code node logic (non-financial) | Medium | Tier 3+, confidence > 85%, tests pass | Ian (1h veto) | 4h |
| 14 | Modify Code node logic (financial) | High | Never auto-approve | Ian | 48h |
| 15 | Update Python tool (non-deploy script) | Medium | Tier 3+, tests pass, change < 50 lines | Ian | 24h |

## n8n Configuration Actions

| # | Action | Risk | Auto-Approve Conditions | Requires Review By | Max Wait |
|---|---|---|---|---|---|
| 16 | Change trigger schedule (non-financial) | Medium | Tier 4+, new schedule within 2x of original | Ian (1h veto) | 4h |
| 17 | Change trigger schedule (financial) | High | Never auto-approve | Ian | 48h |
| 18 | Add `continueOnFail` to a node | Low | Tier 3+, confidence > 75% | — | — |
| 19 | Modify retry settings | Low | Tier 3+, increase only (never decrease) | — | — |
| 20 | Change HTTP timeout values | Low | Tier 3+, increase only (max 120s) | — | — |
| 21 | Update n8n credential references | High | Never auto-approve | Ian | 48h |
| 22 | Modify webhook URL or path | High | Never auto-approve | Ian | 24h |

## Data & Integration Actions

| # | Action | Risk | Auto-Approve Conditions | Requires Review By | Max Wait |
|---|---|---|---|---|---|
| 23 | Add Airtable field (additive) | Low | Tier 3+, field does not duplicate existing | — | — |
| 24 | Rename/remove Airtable field | High | Never auto-approve | Ian | 48h |
| 25 | Update Airtable filterByFormula | Medium | Tier 3+, confidence > 85%, tested | Ian (1h veto) | 4h |
| 26 | Update Google Sheets column mappings | Medium | Tier 3+, confidence > 85%, tested | Ian (1h veto) | 4h |
| 27 | Modify Supabase queries or schema | High | Never auto-approve | Ian | 48h |
| 28 | Change API endpoint URL | Medium | Tier 3+, endpoint verified accessible | Ian | 24h |

## Communication & Notification Actions

| # | Action | Risk | Auto-Approve Conditions | Requires Review By | Ian | Max Wait |
|---|---|---|---|---|---|---|
| 29 | Send Telegram alert (system status) | Low | Tier 3+, message is auto-generated status | — | — |
| 30 | Send Telegram alert (incident) | Low | Tier 2+, incident severity P1-P2 | — | — |
| 31 | Update internal documentation | Low | Always auto-approve | — | — |
| 32 | Update client-facing email template | High | Never auto-approve | Ian | 48h |
| 33 | Send email to client | Prohibited | Never auto-approve | Ian | — |

## Monitoring & Repair Actions

| # | Action | Risk | Auto-Approve Conditions | Requires Review By | Max Wait |
|---|---|---|---|---|---|
| 34 | Run health check / fetch executions | Low | Always auto-approve (read-only) | — | — |
| 35 | Create incident report | Low | Always auto-approve | — | — |
| 36 | Apply known-pattern fix (low-risk workflow) | Low | Tier 3+, pattern confidence > 90%, tests pass | — | — |
| 37 | Apply known-pattern fix (medium-risk workflow) | Medium | Tier 3+, pattern confidence > 90%, tests pass | Ian (1h veto) | 4h |
| 38 | Apply known-pattern fix (high-risk workflow) | High | Never auto-approve | Ian | 24h |
| 39 | Rollback workflow to previous version | Medium | Tier 3+, current version has 3+ errors | — | — |
| 40 | Run optimization analysis | Low | Always auto-approve (read-only) | — | — |
| 41 | Apply optimization (low-risk) | Low | Tier 4+, A/B test shows improvement, tests pass | — | — |
| 42 | Trigger revamp assessment | Low | Always auto-approve (assessment only) | — | — |
| 43 | Execute revamp (replace workflow) | High | Never auto-approve | Ian | 48h |

## Git Actions

| # | Action | Risk | Auto-Approve Conditions | Requires Review By | Max Wait |
|---|---|---|---|---|---|
| 44 | Stage files | Low | Tier 3+, files match approved change | — | — |
| 45 | Commit (low-risk changes) | Low | Tier 3+, all tests pass, < 100 lines changed | — | — |
| 46 | Commit (medium/high-risk changes) | Medium | Tier 3+, approved change | Ian | 24h |
| 47 | Push to remote | Medium | Tier 3+, commit approved, branch != main | Ian (1h veto) | 4h |
| 48 | Force push | Prohibited | Never | — | — |
| 49 | Create branch | Low | Tier 2+, follows naming convention | — | — |
| 50 | Create pull request | Medium | Tier 3+, all tests pass, description complete | Ian | 24h |

---

## Veto Window Process

For actions marked "1h veto window":

1. AWE sends Telegram message: `"[AWE] Planning: {action description}. Reply VETO within 1h to block."`
2. Timer starts (1 hour)
3. If Ian replies "VETO" or "STOP" → action cancelled, logged as vetoed
4. If no reply within 1h → action proceeds, logged as "auto-approved (no veto)"
5. Post-execution: Telegram confirmation with result

---

## Escalation When Max Wait Exceeded

If approval is not received within Max Wait:

| Max Wait | Escalation Action |
|---|---|
| 4h | Send Telegram reminder |
| 24h | Send email + Telegram reminder |
| 48h | Apply safe default (usually "do nothing"), log as "timed out" |
| 72h | Downgrade task priority, move to weekly review queue |

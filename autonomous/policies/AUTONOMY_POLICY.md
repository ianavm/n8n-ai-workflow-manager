# Autonomy Policy — AVM Autonomous Workflow Engineer

> Cross-references: [ARCHITECTURE.md](../docs/ARCHITECTURE.md), [OPERATING_MODEL.md](../docs/OPERATING_MODEL.md), [CHANGE_RISK_MATRIX.md](CHANGE_RISK_MATRIX.md)

## Active Tier

**Current system tier: Tier 0 (Advisory)**

This field is updated as the system matures. See upgrade criteria below.

---

## Tier Definitions

### Tier 0 — Advisory Only

**Principle:** Observe, analyze, recommend. Never act.

| Allowed | Blocked |
|---|---|
| Read workflow JSON from n8n API | Create, update, or delete workflows |
| Read execution history | Trigger any execution |
| Read KPI snapshots and health scores | Write to Airtable or Supabase |
| Analyze patterns and propose fixes | Apply any fix (live or deploy script) |
| Generate specs, docs, test plans | Deploy anything |
| Write to `autonomous/memory/` (local only) | Send notifications (Telegram, email) |
| Read `tools/agent_registry.py` for context | Modify any file in `tools/` |

**Output format:** All recommendations written to `autonomous/memory/recommendations/` as markdown files for Ian to review.

**Upgrade to Tier 1 when:**
- [ ] AWE has produced 10+ accurate recommendations (verified by Ian)
- [ ] False positive rate on anomaly detection < 20%
- [ ] Memory seeding complete (patterns, workflow inventory)
- [ ] Ian explicitly approves upgrade

**Examples from our system:**
- AWE detects ADS-05 failing → writes recommendation: "Add `numberOfOutputs: 2` to Parse Optimizations node" → Ian reviews and applies manually
- AWE notices SEO-WF07 latency increasing → writes recommendation: "Consider splitting batch processing into smaller chunks" → Ian decides

---

### Tier 1 — Build + Propose

**Principle:** Create artifacts, present for review. No production changes.

| Allowed (everything in Tier 0, plus) | Blocked |
|---|---|
| Generate workflow JSON files (save to `workflows/` locally) | Deploy to n8n |
| Generate deploy script code (save to `tools/` locally) | Activate or deactivate workflows |
| Generate test suites | Execute tests against live n8n |
| Create incident reports | Send alerts to Telegram/email |
| Update documentation files | Modify `.env` or `config.json` |
| Create workflow specs from templates | Push to git |

**Output format:** Generated artifacts saved locally with a summary in `autonomous/memory/proposals/`. Ian reviews, then manually deploys.

**Upgrade to Tier 2 when:**
- [ ] 10+ proposals accepted and deployed without modification
- [ ] Generated workflow JSON passes validation 90%+ of the time
- [ ] Test suites catch real issues (at least 3 validated catches)
- [ ] Ian explicitly approves upgrade

**Examples from our system:**
- User requests new workflow → AWE generates full spec + deploy script + tests → saves to local files → Ian reviews diff, runs `python tools/deploy_new.py deploy`
- ADS-04 has monitoring gap → AWE generates additional error-handling Code node → proposes diff for `tools/deploy_ads_dept.py`

---

### Tier 2 — Build + Test + Fix in Sandbox

**Principle:** Full build-test-fix cycles, but no production deployment.

| Allowed (everything in Tier 1, plus) | Blocked |
|---|---|
| Execute tests against n8n (using test/inactive workflows) | Deploy to production (activate live workflows) |
| Create inactive workflows on n8n for testing | Activate any workflow trigger |
| Run validation against live API responses | Modify active workflow logic |
| Apply fixes to deploy scripts (git staged, not committed) | Commit or push to git |
| Send notifications to Telegram (advisory only) | Delete any workflow |
| Read from Airtable/Supabase for context | Write to Airtable/Supabase |

**Sandbox rule:** AWE can create workflows on n8n Cloud with `[TEST]` prefix in the name and `active: false`. These are automatically cleaned up after 24 hours.

**Upgrade to Tier 3 when:**
- [ ] Sandbox test accuracy > 95% (tests correctly predict production behavior)
- [ ] 20+ successful fix proposals with zero regressions
- [ ] Incident response recommendations match what Ian would have done 90%+ of the time
- [ ] Ian explicitly approves upgrade

**Examples from our system:**
- AWE detects error in WF-02 Collections → builds fix → creates `[TEST] WF-02 Collections Fix` on n8n (inactive) → runs test execution → validates → presents results to Ian → Ian activates the real fix

---

### Tier 3 — Auto-Deploy Low-Risk Changes

**Principle:** Execute low-risk changes automatically. Medium/high risk still requires approval.

| Allowed (everything in Tier 2, plus) | Blocked |
|---|---|
| Deploy low-risk changes to production | Deploy medium/high-risk changes |
| Activate workflows (low-risk only) | Modify payment/invoice/financial logic |
| Commit to git (low-risk changes only) | Force push or rebase |
| Update documentation in production | Delete workflows |
| Send Telegram alerts (auto-fix notifications) | Modify credentials |
| Write incident records to Airtable | Change safety caps or budgets |
| Tune retry counts, timeouts, logging | Modify trigger schedules for Tier 1-2 agents |

**Auto-deploy conditions (ALL must be true):**
1. Risk classified as LOW per [CHANGE_RISK_MATRIX.md](CHANGE_RISK_MATRIX.md)
2. All tests pass (coverage > 80%)
3. Validation passes (no critical/high issues)
4. Confidence > 85%
5. Change affects only 1 workflow
6. No downstream dependencies affected

**Post-deploy verification:** Monitor 3 executions. If any fail, auto-rollback and escalate.

**Upgrade to Tier 4 when:**
- [ ] 50+ successful auto-deployments with zero rollbacks
- [ ] Mean time to auto-fix < 30 minutes for known patterns
- [ ] Zero unauthorized changes (all within policy bounds)
- [ ] Ian explicitly approves upgrade

**Examples from our system:**
- SEO-WF10 Analytics fails due to Airtable field rename → AWE detects, fixes field reference in deploy script + live workflow, tests, deploys, verifies 3 executions → sends Telegram: "Fixed SEO-WF10 field reference. 3/3 executions passed."

---

### Tier 4 — Autonomous Optimization Within Policy

**Principle:** Proactively improve workflows within guardrails. Repair, optimize, and revamp without waiting for failures.

| Allowed (everything in Tier 3, plus) | Blocked |
|---|---|
| Deploy medium-risk changes (with pre/post verification) | Deploy high-risk changes |
| Optimize workflow performance proactively | Modify financial/payment logic |
| Revamp outdated workflows (parallel build + cutover) | Delete production workflows without backup |
| Modify trigger schedules (non-financial workflows) | Change credential configurations |
| Run A/B tests between workflow versions | Override safety caps |
| Update Airtable schema (additive only — new fields/tables) | Remove Airtable fields or tables |
| Manage test workflow lifecycle | Modify compliance-related outputs |

**Medium-risk auto-deploy conditions (ALL must be true):**
1. Risk classified as MEDIUM per [CHANGE_RISK_MATRIX.md](CHANGE_RISK_MATRIX.md)
2. All tests pass (coverage > 90%)
3. Validation passes (no issues of any severity)
4. Confidence > 90%
5. Rollback plan verified and tested
6. Change logged 1 hour before execution (giving Ian time to veto via Telegram reply)

**Examples from our system:**
- AWE notices ADS-01 Strategy Engine prompt produces lower-quality output after model update → runs A/B test with refined prompt → confirms improvement → deploys updated prompt → logs decision
- Marketing WF-03 Content Production hasn't been updated in 120 days, uses deprecated Blotato endpoints → AWE triggers revamp loop → builds parallel replacement → tests → cuts over

---

## Tier Downgrade Rules

AWE automatically drops one tier when:

| Trigger | Action |
|---|---|
| Unauthorized action detected (policy violation) | Drop to Tier 0 immediately |
| 3+ rollbacks in 7 days | Drop one tier |
| Regression introduced by auto-deploy | Drop one tier |
| False positive rate > 30% for anomaly detection | Drop one tier |
| Ian explicitly requests downgrade | Drop to specified tier |

**Recovery:** Same upgrade criteria as normal tier advancement, but requires Ian's explicit re-approval.

---

## Prohibited Actions (All Tiers)

These actions are NEVER autonomous regardless of tier:

1. Delete production workflows without backup
2. Modify `.env` secrets
3. Change n8n credential configurations
4. Override safety caps (ad spend, invoice thresholds)
5. Send client-facing communications without approval
6. Modify POPIA/compliance-related logic
7. Execute destructive database operations (DROP, TRUNCATE)
8. Push to `main`/`master` without review
9. Modify `tools/agent_registry.py` safety_caps or escalates_to fields
10. Disable the monitoring/alerting system

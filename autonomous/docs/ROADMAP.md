# Roadmap — AVM Autonomous Workflow Engineer

> Cross-references: [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md), [ARCHITECTURE.md](ARCHITECTURE.md), [START_THIS_WEEK.md](START_THIS_WEEK.md)

---

## MVP — Weeks 1-2 (Advisory Mode)

**Goal:** AWE observes, detects, classifies, and proposes fixes — but never applies them. Build trust through accurate recommendations.

### Components

| Component | Status | Notes |
|---|---|---|
| `autonomous/engine.py` — full repair pipeline | Done | 7-stage: detect → classify → score → govern → fix → verify → log |
| `autonomous/cli.py` — 8 CLI commands | Done | status, monitor, repair, audit, patterns, seed, tier, init |
| `autonomous/config.yaml` — operational settings | Done | Governance, confidence, monitoring, repair, paths, alerts |
| `tools/autonomy_governor.py` — tier-based approval | Done | ActionType enum, risk classification, tier policies |
| `tools/confidence_scorer.py` — confidence scoring | Done | 5-factor weighted scoring |
| `tools/decision_logger.py` — audit trail | Done | Decision log + escalation queue |
| `tools/repair_engine.py` — pattern matching + fix | Done | Pattern registry, dedup, backup, fix application |
| `tools/repair_pattern_store.py` — pattern persistence | Done | JSON store with success rate tracking |
| `autonomous/scripts/seed_patterns.py` — initial patterns | Done | Seeds known n8n patterns from CLAUDE.md knowledge |
| `autonomous/scripts/init_memory.py` — directory setup | Done | Creates memory subdirectories |
| Session 1-4 docs (architecture, policies, prompts, loops) | Done | 33 files across docs/, policies/, prompts/, templates/ |

### What to Do

1. Run `python -m autonomous init` — initialize memory directories
2. Run `python -m autonomous seed` — seed known patterns from n8n experience
3. Run `python -m autonomous status` — verify connectivity and baseline health
4. Run `python -m autonomous monitor` — detect current issues (read-only)
5. Run `python -m autonomous repair` — generate proposals (Tier 1 = advisory only)
6. Review proposals in `autonomous/memory/recommendations/`
7. Manually apply any valid proposals, track accuracy

### Success Criteria

- [ ] `status` command shows accurate health dashboard
- [ ] `monitor` detects real issues (validated against manual checks)
- [ ] `repair` generates proposals that are 70%+ accurate
- [ ] Pattern seeding covers the 13+ known n8n issues from CLAUDE.md
- [ ] Decision log correctly records all pipeline runs
- [ ] Zero false actions (nothing applied at Tier 1)

### Risks

- Pattern matching may miss edge cases → refine patterns based on real failures
- Confidence scorer weights may need calibration → adjust after 10+ proposals reviewed
- n8n API rate limits during intensive monitoring → tune check interval

---

## V1 — Weeks 3-6 (Supervised Autonomy)

**Goal:** AWE auto-fixes low-risk known-pattern issues. Medium/high risk remains proposal-only. Close the feedback loop between proposals and outcomes.

### New Capabilities

| Capability | Implementation |
|---|---|
| **Auto-fix low-risk issues** | Upgrade to Tier 3 after MVP criteria met. Governor auto-approves low-risk known-pattern fixes |
| **Post-fix verification** | After applying fix, monitor 3 executions. Auto-rollback if any fail |
| **Pattern learning** | When a manual fix is applied, store it as a new pattern with initial confidence |
| **Telegram notifications** | Enable alerts for P1/P2 incidents and auto-fix confirmations |
| **Workflow memory seeding** | Populate `autonomous/memory/workflows/` from agent_registry + deployed workflow IDs |
| **Incident memory** | Auto-create incident records for every P1-P3 issue detected |

### Implementation Tasks

1. Enable `alerts.telegram_enabled: true` in config.yaml
2. Create Telegram notification helper (using existing Telegram bot @AVMCRMBot, chat 6311361442)
3. Build `autonomous/scripts/seed_workflows.py` — populate workflow memory from agent_registry
4. Add `cmd_learn` to CLI — manually record a fix as a new pattern
5. Upgrade tier to 2, then 3 after validation period
6. Add rollback integration to repair engine (already has backup, needs restore)

### Success Criteria

- [ ] 10+ auto-fixes applied successfully with zero rollbacks
- [ ] Telegram alerts firing for P1/P2 incidents
- [ ] 5+ new patterns learned from manual fixes
- [ ] Workflow memory populated for all ~70 deployed workflows
- [ ] Mean time to auto-fix < 30 minutes for known patterns
- [ ] Zero unauthorized actions (all within Tier 3 policy bounds)

### Risks

- First auto-fix on wrong workflow → rollback mechanism must work perfectly before enabling
- Pattern over-matching (wrong pattern applied) → require confidence > 85% for auto-fix
- Telegram alert fatigue → tune thresholds to avoid P3/P4 noise

---

## V2 — Weeks 7-12 (Autonomous Within Bounds)

**Goal:** AWE handles the optimization and revamp loops. Proactive improvement, not just reactive repair.

### New Capabilities

| Capability | Implementation |
|---|---|
| **Optimization loop** | Detect latency bottlenecks, token waste, retry inefficiency. Propose and apply low-risk optimizations |
| **Revamp assessment** | Compute maintainability scores, flag workflows needing rebuild |
| **Schema validation** | Weekly check that Airtable/Google Sheets schemas match expectations |
| **Scheduled monitoring** | n8n workflow or cron job that runs `python -m autonomous repair` on schedule |
| **Health digest** | Daily Telegram summary of system health |
| **Cross-department correlation** | Use intelligence_engine to detect cascading issues |

### Implementation Tasks

1. Add `cmd_optimize` to CLI — run optimization loop on a specific workflow
2. Add `cmd_revamp` to CLI — run revamp assessment
3. Build `autonomous/monitoring/schema_checker.py` — validate Airtable field types
4. Create n8n workflow "AWE-01 Scheduled Monitor" — runs every 15 min, calls `python -m autonomous repair`
5. Create n8n workflow "AWE-02 Daily Digest" — runs daily 06:00, calls `python -m autonomous status`, sends Telegram
6. Integrate `intelligence_engine.py` into the monitoring analyst stage
7. Upgrade to Tier 4 after V1 criteria met

### Success Criteria

- [ ] Optimization loop identifies and applies 5+ improvements
- [ ] Revamp assessment correctly flags 2+ outdated workflows
- [ ] Schema checker catches 1+ schema drift before it causes failures
- [ ] Scheduled monitoring running 24/7 with < 5% false positive rate
- [ ] Daily digest delivers accurate health summary
- [ ] 50+ successful autonomous actions with zero rollbacks

### Risks

- Optimization changes may be harder to verify than repairs → require A/B comparison
- Scheduled monitoring creates load on n8n Cloud → tune frequency
- Revamp recommendations may be premature → conservative thresholds initially

---

## Mature Platform — Month 4+ (Self-Improving)

**Goal:** AWE learns from every interaction, refines its own patterns and prompts, and reduces human touchpoints to security/financial decisions only.

### New Capabilities

| Capability | Implementation |
|---|---|
| **Pattern auto-refinement** | Adjust pattern confidence based on actual success/failure rates |
| **Prompt performance tracking** | Measure which prompt versions produce better outcomes |
| **Proactive revamp** | Predict when a workflow will degrade (forecast-based triggers) |
| **Build loop** | Generate new workflow specs from business requests |
| **Cross-session learning** | AWE memory persists and improves across Claude Code sessions |
| **Dashboard** | Web-based health dashboard in client portal |

### Implementation Tasks

1. Build confidence auto-calibration (compare predicted vs actual outcomes, adjust weights)
2. Track prompt version → outcome correlation in decision log
3. Add trend forecasting to revamp triggers (from intelligence_engine)
4. Implement build loop stages 1-15 from EXECUTION_LOOPS.md
5. Build portal dashboard page (`/admin/awe`) showing health, incidents, decisions
6. Create pattern export/import for sharing across projects

### Success Criteria

- [ ] Pattern confidence scores auto-calibrate within ±5% of actual success rate
- [ ] Build loop can generate a working workflow spec from a business request
- [ ] Forecast-based revamp triggers catch degradation 2+ weeks before incident
- [ ] Human touchpoints reduced to: security decisions, financial logic, credential rotation
- [ ] Portal dashboard provides real-time visibility

### Risks

- Auto-calibration feedback loop may oscillate → dampen adjustments (max 5% per cycle)
- Build loop is the most complex capability → expect iterative refinement over months
- Portal dashboard requires Supabase/Vercel integration → separate development track

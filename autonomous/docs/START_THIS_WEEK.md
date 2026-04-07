# Start This Week — AVM Autonomous Workflow Engineer

> Concrete actions to get AWE running in advisory mode this week.

---

## Day 1: Initialize & Seed

### Step 1: Initialize memory directories

```bash
cd "c:/Users/ianim/OneDrive/Desktop/Agentic Workflows/Workflow Manager"
python -m autonomous init
```

**Expected:** Creates subdirectories in `autonomous/memory/` (workflows, incidents, patterns, decisions, test_history, specs, events, health_reports, recommendations, optimizations, deployments, revamp_assessments, research, fixes, validations).

### Step 2: Seed known patterns

```bash
python -m autonomous seed
```

**Expected:** Seeds 13+ known n8n failure patterns from CLAUDE.md knowledge (Code node multi-output, Airtable v2 matchingColumns, Switch v3 rules format, $env in Code nodes, etc.).

### Step 3: Verify connectivity

```bash
python -m autonomous status
```

**Expected:** Shows system health dashboard — active/total workflows, execution stats, success rate. If it fails, check `.env` has valid `N8N_API_KEY` and `N8N_BASE_URL`.

---

## Day 2: First Monitor Run

### Step 4: Run detection scan

```bash
python -m autonomous monitor
```

**Expected:** Lists any workflows with consecutive errors or high error rates. This is read-only — no changes made.

### Step 5: Run repair loop (advisory mode)

```bash
python -m autonomous repair
```

**Expected at Tier 1:** Detects issues → classifies → scores → writes proposals to `autonomous/memory/recommendations/`. Zero live changes.

### Step 6: Review proposals

Read the generated proposal files:

```bash
ls autonomous/memory/recommendations/
```

Each proposal JSON contains:
- What's wrong (error message, workflow, node)
- Proposed fix (pattern match, confidence score)
- Risk level and governance decision
- Deploy script that needs updating

**Manual action:** For each valid proposal, apply the fix manually and track whether it worked. This data calibrates the system.

---

## Day 3: Audit & Calibrate

### Step 7: Review decision log

```bash
python -m autonomous audit --hours 72
```

**Expected:** Shows all pipeline decisions — what was detected, classified, scored, and proposed. Look for:
- **False positives:** Issues detected that aren't real problems → tune `monitoring.error_alert_threshold`
- **Missed patterns:** Real issues not matched to patterns → add new patterns
- **Confidence miscalibration:** Scores too high or low → adjust `confidence.weights`

### Step 8: Review pattern effectiveness

```bash
python -m autonomous patterns
```

**Expected:** Lists all patterns with confidence scores and success rates. After manual fixes are applied, success rates update automatically.

---

## Policies to Enforce Immediately

These policies are active from Day 1 regardless of autonomy tier:

| Policy | Enforcement |
|---|---|
| [AUTONOMY_POLICY.md](../policies/AUTONOMY_POLICY.md) | System starts at Tier 1 (Advisory). No auto-actions. |
| [CHANGE_RISK_MATRIX.md](../policies/CHANGE_RISK_MATRIX.md) | All changes classified before any action. |
| [SECRETS_POLICY.md](../policies/SECRETS_POLICY.md) | AWE never reads, logs, or stores secret values. |
| [INCIDENT_SEVERITY.md](../policies/INCIDENT_SEVERITY.md) | P1-P4 classification on every detected issue. |

---

## First Monitoring Setup

### What to monitor

Start with these 3 low-risk, high-value workflows:

| Workflow | ID | Why |
|---|---|---|
| **ADS-04 Performance Monitor** | `rIYu0FHFx741ml8d` | Runs every 6h, pulls metrics — good candidate for failure detection |
| **SEO-WF05 Trend Discovery** | `5XZFaoQxfyJOlqje` | Runs Mon/Thu, moderate complexity — tests classification accuracy |
| **WF-04 Supplier Bills** | `ZEcxIC9M5ehQvsbg` | Runs daily — tests accounting department risk modifier |

### How to focus monitoring

The current config monitors all workflows. To focus on specific ones during calibration, run:

```bash
python -m autonomous monitor
```

Then manually check if the detected issues for these 3 workflows match reality.

---

## First Autonomy Boundaries

| Setting | Value | Config Key |
|---|---|---|
| Current tier | 1 (Advisory) | `system.current_tier: 1` |
| Auto-fix enabled | No | Governed by tier |
| Telegram alerts | Disabled (enable in Week 2) | `alerts.telegram_enabled: false` |
| Error threshold | 3 consecutive errors | `monitoring.error_alert_threshold: 3` |
| Confidence to auto-apply | 80% (not used at Tier 1) | `confidence.threshold_apply: 0.80` |
| Dedup cooldown | 5 minutes | `repair.dedup_cooldown_seconds: 300` |
| Backup before fix | Yes (always) | `repair.backup_before_fix: true` |

---

## First Feedback Loop

The most important feedback loop to close: **proposal accuracy tracking**.

After each `python -m autonomous repair` run:

1. Read proposals in `autonomous/memory/recommendations/`
2. For each proposal, decide: accurate / partially accurate / wrong
3. If accurate: apply the fix manually, mark the pattern as validated
4. If wrong: note why it was wrong → this informs pattern refinement

**Target:** 70%+ proposal accuracy within the first week. If below 50%, tune confidence weights or add more specific patterns.

---

## Verification Commands

Run these to confirm everything is working:

```bash
# System health
python -m autonomous status

# Current tier
python -m autonomous tier

# Pattern inventory
python -m autonomous patterns

# Recent decisions
python -m autonomous audit --hours 24

# Full repair cycle
python -m autonomous repair
```

**All commands are safe at Tier 1** — they read, analyze, and propose but never modify live workflows.

---

## What NOT to Do This Week

1. Do NOT upgrade to Tier 2+ until MVP criteria met (see [ROADMAP.md](ROADMAP.md))
2. Do NOT enable Telegram alerts until you've confirmed low false positive rate
3. Do NOT manually edit `autonomous/config.yaml` confidence weights without reviewing 10+ proposals first
4. Do NOT run `python -m autonomous repair` on a schedule yet — run manually to validate
5. Do NOT bypass the governance layer — if AWE says "escalate", it means confidence is too low

---

## Success Metrics for This Week

| Metric | Target | How to Measure |
|---|---|---|
| `status` runs without error | 100% | Run 3+ times |
| Issues detected match reality | > 80% | Compare `monitor` output to manual n8n check |
| Proposals are accurate | > 70% | Review each proposal, track correct/incorrect |
| Patterns seeded | 13+ | Check `python -m autonomous patterns` |
| Zero false actions | 0 | Verify no live workflow changes (Tier 1 guarantees this) |
| Decision log captures all runs | 100% | Check `python -m autonomous audit` |

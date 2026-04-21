# Airtable API Quota — Status & Action Checklist

**As of 2026-04-21 during revision sweep.**

## Current state

Memory flagged on 2026-04-21 that the Airtable workspace had hit
`PUBLIC_API_BILLING_LIMIT_EXCEEDED` and SC-01 was intentionally left inactive
to avoid an error loop.

Live spot-checks during this revision show Airtable is **currently serving
requests**:

| Workflow | Last Airtable-touching exec | Status |
|---|---|---|
| PP-01 Morning Mission Board | 2026-04-21 04:30 UTC | success |
| PP-03 Evening Review | 2026-04-21 18:00 UTC | success |
| RE-11 Daily Summary | 2026-04-21 03:00 UTC | success |
| Business Email Management | 2026-04-21 18:00 UTC | success |

Most likely the monthly quota rolled over, or a per-endpoint throttle lifted.
SC-01 has been reactivated in this pass because its Airtable cred is valid
and the quota is not currently blocking.

## What was ALSO fixed this pass

The quota symptoms were masking a separate issue: **14 active workflows and
12 inactive workflows** still referenced a deleted Airtable credential
(`j0HMJbsIoJgSpLAS`). Every Airtable call from those workflows was failing
with a 401 "Credential with ID X does not exist" — independently of the
quota state. Those have been repointed to the current cred
`vPjIuQXz26XBX1r9` ("Airtable PAT AVM").

Tool used: `python tools/rotate_credential_ref.py --from OLD --to NEW`.
Keep this tool for future rotations.

## Workflows dependent on Airtable (keep an eye on these when quota tightens)

### Active
- `PP-01 Morning Mission Board` — Airtable-heavy (5 nodes)
- `PP-03 Evening Review` — Airtable-heavy (6 nodes)
- `PP-05 Adaptive Difficulty Tuner` — Airtable-heavy (4 nodes)
- `PP-06 Tap-to-Complete Callback Handler` — Airtable-heavy (5 nodes)
- `PF-01 Create Payment` — Airtable (1 node)
- `PF-02 ITN Handler` — Airtable-heavy (5 nodes)
- `PF-03 Verify Token` — Airtable (1 node)
- `AVM: Website Contact Form` — Airtable (2 nodes)
- `AVM: SEO Lead Capture` — Airtable (2 nodes)
- `SC-02 Script Extraction` — Airtable (1 node)
- `SC-03 Brand Adaptation` — Airtable (2 nodes)
- `SC-04 Video Production` — Airtable (2 nodes)
- `SC-05 Distribution` — Airtable (2 nodes)
- `SC-06 Carousel Post` — Airtable (1 node)
- `SC-01 Trend Discovery` — Airtable (2 nodes) — newly reactivated

### Inactive (won't contribute to quota right now, but will if reactivated)
- FA-10 Weekly Reporting
- ADS suite: Budget Enforcer, Reporting Dashboard, Strategy Generator,
  Campaign Builder, Performance Monitor

## If quota recurs — action checklist

1. **Confirm symptom** — error message in failing execution contains
   `PUBLIC_API_BILLING_LIMIT_EXCEEDED` (HTTP 429).
2. **Check usage** — Airtable workspace billing → API usage graph.
   Identify which base is dominating calls. Likely culprits:
   - marketing base `apptjjBx34z9340tK` (SC + PP + content workflows)
   - leads base `app2ALQUP7CKEkHOz` (lead scraper + Business Email Mgmt)
3. **Choose path:**
   - **(a) Wait for monthly reset** — if within a week of reset, deactivate
     the highest-volume workflows (PP-01, PP-03 run 2x/day) until reset.
   - **(b) Upgrade plan** — Airtable Team → Business lifts API cap
     significantly. Check cost vs. the volume you actually need.
   - **(c) Shift hot writes off Airtable** — SC department already uses
     Google Sheets for high-volume logging. PP_* tables and activity
     logs are candidates for Sheets migration (bigger work, not needed
     unless quota bites repeatedly).
4. **Reactivation checklist after resolution:**
   - Verify SC-01 still active: `python tools/revision_health_check.py`
   - Verify a recent PP-01 exec is green.
   - No code changes needed unless you chose path (c).

## Long-term hardening (future work)

- Add graceful-degrade wrapper on Airtable writes (local queue + retry when
  quota resets). Out of scope for this stabilization pass.
- Centralize workflow-to-Airtable-base dependency map in a YAML so quota
  triage doesn't require code grep.

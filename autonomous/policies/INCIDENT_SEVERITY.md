# Incident Severity Policy — AVM Autonomous Workflow Engineer

> Cross-references: [ROLLBACK_POLICY.md](ROLLBACK_POLICY.md), [APPROVAL_MATRIX.md](APPROVAL_MATRIX.md), [OPERATING_MODEL.md](../docs/OPERATING_MODEL.md)

## Severity Levels

### P1 — Critical

**Definition:** Production is down, data is being lost, or there is direct financial impact.

| Field | Value |
|---|---|
| **Response time** | < 15 minutes |
| **Resolution SLA** | 1 hour |
| **Notification** | Telegram immediate + email |
| **Autonomous action** | Only if confidence > 90% AND known pattern AND rollback ready |
| **Escalation** | Always escalate to Ian, even if auto-fix attempted |

**Examples:**
- WF-01 Invoice Generation sending wrong amounts
- ADS-03 spending above safety cap (R2K/day)
- All workflows in a department failing simultaneously
- Airtable/Supabase write operations corrupting data
- Credential expiry causing cascading auth failures

**AWE response:**
1. Deactivate affected workflow(s) immediately
2. Send Telegram: `"[P1 CRITICAL] {workflow}: {error}. Deactivated. Investigating."`
3. Attempt auto-diagnosis (debugger module)
4. If known pattern with 90%+ confidence: apply fix to inactive copy, test, present results
5. Wait for Ian to approve reactivation

---

### P2 — High

**Definition:** Service degraded, partial failures, or accuracy dropping but no immediate financial impact.

| Field | Value |
|---|---|
| **Response time** | < 1 hour |
| **Resolution SLA** | 4 hours |
| **Notification** | Telegram + email summary |
| **Autonomous action** | If confidence > 80% AND known pattern |
| **Escalation** | If auto-fix fails or confidence < 80% |

**Examples:**
- ADS-05 Optimizer failing intermittently (some executions succeed)
- SEO-WF07 content production generating lower-quality output
- WF-02 Collections sending duplicate reminders
- LinkedIn pipeline LI-04 enrichment returning empty data
- Google Sheets sync falling behind by > 2 hours

**AWE response:**
1. Do NOT deactivate (partial service is better than none)
2. Send Telegram: `"[P2 HIGH] {workflow}: {error}. {N} failures in last hour. Investigating."`
3. Run debugger module
4. If known pattern: apply fix, test, deploy (Tier 3+)
5. If unknown: escalate with diagnosis report

---

### P3 — Medium

**Definition:** Non-critical failure, workaround exists, or single execution failure.

| Field | Value |
|---|---|
| **Response time** | < 4 hours |
| **Resolution SLA** | 24 hours |
| **Notification** | Daily summary digest |
| **Autonomous action** | Yes, if confidence > 70% |
| **Escalation** | Only if fix fails or pattern recurs 3+ times |

**Examples:**
- SEO-WF10 Analytics single execution timeout (retry succeeds)
- Marketing WF-04 Distribution fails for one platform (others succeed)
- ADS-06 Creative Recycler Airtable read returns stale data
- Email classifier misroutes one email (caught by existing fallback)
- Test workflow cleanup didn't run (orphaned `[TEST]` workflow)

**AWE response:**
1. Log incident in memory
2. Check if pattern is known
3. If known: auto-fix during next maintenance window
4. If new pattern but clear cause: fix and add to pattern library
5. Include in daily digest to Ian

---

### P4 — Low

**Definition:** Cosmetic issue, optimization opportunity, or informational alert.

| Field | Value |
|---|---|
| **Response time** | Next business day |
| **Resolution SLA** | 1 week |
| **Notification** | Weekly summary |
| **Autonomous action** | Yes |
| **Escalation** | None (unless it becomes P3 due to recurrence) |

**Examples:**
- Workflow execution time increased by 20% (still within SLA)
- AI node token usage approaching daily budget (not exceeded)
- Documentation is stale (workflow changed but SOP not updated)
- Unused node in workflow (dead code)
- Test coverage dropped below 80% after code change

**AWE response:**
1. Log in memory
2. Auto-fix if straightforward (update docs, clean up nodes)
3. Include in weekly optimization report
4. Track trend (P4 that recurs 5+ times becomes P3)

---

## Severity Classification Flowchart

```
Is there active financial impact (wrong amounts, overspend)?
  ├── YES → P1
  │
  └── NO → Is data being corrupted or lost?
              ├── YES → P1
              │
              └── NO → Is a department fully blocked (all workflows down)?
                          ├── YES → P1
                          │
                          └── NO → Is service degraded (partial failures, quality drop)?
                                      ├── YES → P2
                                      │
                                      └── NO → Did a single execution fail with workaround?
                                                  ├── YES → P3
                                                  │
                                                  └── NO → P4 (optimization/cosmetic)
```

## Severity Escalation Rules

An incident can be upgraded if it worsens:

| Original | Upgrade To | Trigger |
|---|---|---|
| P4 | P3 | Recurs 5+ times in 7 days |
| P3 | P2 | Workaround stops working, or affects > 1 workflow |
| P2 | P1 | Financial impact discovered, or data loss confirmed |

## Department Severity Modifiers

| Department | Default Modifier | Reason |
|---|---|---|
| Accounting | +1 severity | Any failure risks financial inaccuracy |
| Ads | +1 severity for budget-related | Direct ad spend impact |
| LinkedIn Lead Intel | Standard | Pipeline delays, no immediate financial |
| Marketing | Standard | Content delays are recoverable |
| SEO + Social | Standard | Analytics gaps are fillable |
| Support | Standard | Ticket delays handled by SLA |

**Example:** A P3 incident in Accounting workflows is treated as P2 (medium → high).

---

## Incident Tracking

All incidents are recorded in:

1. **Local memory:** `autonomous/memory/incidents/` (JSON per incident)
2. **Airtable:** Events table (`tbl6PqkxZy0Md2Ocf`) in Operations Control base — for dashboard visibility
3. **Decision log:** `autonomous/memory/decisions/` — records what AWE decided and why

### Required Fields

Per [INCIDENT_TEMPLATE.md](../templates/INCIDENT_TEMPLATE.md):

| Field | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| Incident ID | Required | Required | Required | Required |
| Severity | Required | Required | Required | Required |
| Workflow ID + name | Required | Required | Required | Required |
| Detection time | Required | Required | Required | Required |
| Error message | Required | Required | Required | Optional |
| Root cause | Required | Required | Best effort | Optional |
| Fix applied | Required | Required | If applicable | If applicable |
| Verification result | Required | Required | If applicable | Optional |
| Resolution time | Required | Required | Required | Optional |
| Lessons learned | Required | Required | Optional | Optional |
| Pattern ID (if known) | If applicable | If applicable | If applicable | If applicable |

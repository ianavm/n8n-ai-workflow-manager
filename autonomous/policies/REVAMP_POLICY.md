# Revamp Policy — AVM Autonomous Workflow Engineer

> Cross-references: [CHANGE_RISK_MATRIX.md](CHANGE_RISK_MATRIX.md), [DEPLOYMENT_POLICY.md](DEPLOYMENT_POLICY.md), [OPERATING_MODEL.md](../docs/OPERATING_MODEL.md)

## Purpose

Workflows degrade over time: APIs deprecate, business requirements shift, incidents accumulate, and code becomes unmaintainable. This policy defines when and how to rebuild vs patch.

---

## Revamp Triggers

A workflow enters revamp assessment when ANY of these conditions are met:

| Trigger | Threshold | Detection Method |
|---|---|---|
| **Age without update** | > 90 days since last meaningful change | `git log tools/deploy_{dept}.py` |
| **Incident frequency** | > 5 incidents in 30 days | `autonomous/memory/incidents/` count by workflow |
| **Deprecated nodes** | Any node using deprecated n8n version | Validator module scan |
| **Deprecated API** | External API announces deprecation | Monitoring analyst + API docs |
| **Maintainability score** | < 40/100 | Computed from complexity + incident rate + age |
| **Business requirement shift** | Core purpose has changed | User request or spec review |
| **Security concern** | Vulnerability identified | Security review or incident |
| **Performance degradation** | Execution time > 3x historical average | `execution_monitor.py` trending |
| **Repeated patches** | > 3 patches in 30 days to same workflow | `autonomous/memory/decisions/` count |

---

## Maintainability Score

Computed on a 0-100 scale:

```
maintainability = (
    age_score        * 0.20 +   # 100 if <30d, 50 if 30-90d, 20 if 90-180d, 0 if >180d
    incident_score   * 0.30 +   # 100 if 0 incidents/30d, 70 if 1-2, 30 if 3-5, 0 if >5
    complexity_score * 0.20 +   # 100 if <20 nodes, 70 if 20-40, 40 if 40-60, 0 if >60
    test_score       * 0.15 +   # test coverage percentage (0-100)
    patch_score      * 0.15     # 100 if 0 patches/30d, 50 if 1-2, 0 if >3
)
```

| Score | Assessment | Action |
|---|---|---|
| 70-100 | Healthy | Continue normal operations |
| 40-69 | Degrading | Schedule review, patch if < 3 incidents in 30d |
| 0-39 | Needs revamp | Enter revamp decision process |

---

## Revamp vs Patch Decision

```
Maintainability > 70?
  ├── YES → No action needed. Monitor.
  │
  └── NO → Maintainability 40-70?
              ├── YES → < 3 incidents in 30d?
              │           ├── YES → PATCH (incremental fixes)
              │           └── NO → REVAMP
              │
              └── NO (< 40) → Is the workflow < 10 nodes?
                                ├── YES → PATCH (small enough to fix in-place)
                                └── NO → REVAMP
```

### When to PATCH

- Maintainability 40-70 with few incidents
- Small workflows (< 10 nodes) regardless of score
- Single root cause identified (one fix resolves most issues)
- No deprecated nodes or APIs
- Business requirements haven't changed

**Patch process:**
1. Identify specific issues (from incident memory)
2. Apply targeted fixes to deploy script + live workflow
3. Run targeted tests
4. Deploy (per [DEPLOYMENT_POLICY.md](DEPLOYMENT_POLICY.md))
5. Monitor for 7 days
6. Re-score maintainability

### When to REVAMP

- Maintainability < 40
- Deprecated nodes/APIs (will stop working)
- Business requirements fundamentally changed
- > 3 patches in 30 days (patching isn't working)
- Security vulnerability in core logic

---

## Revamp Process: Safe Parallel Rebuild

**Critical rule:** NEVER modify the live workflow during revamp. Build new, test, compare, cutover.

### Phase 1: Specification (1-2 hours)

1. Review original workflow spec (if exists in `autonomous/memory/specs/`)
2. Gather current business requirements (may have changed)
3. Identify what the workflow does TODAY vs what it SHOULD do
4. Write new spec from [WORKFLOW_SPEC_TEMPLATE.md](../templates/WORKFLOW_SPEC_TEMPLATE.md)
5. Risk-classify the revamp per [CHANGE_RISK_MATRIX.md](CHANGE_RISK_MATRIX.md)

### Phase 2: Build Replacement (2-4 hours)

1. Create new deploy script or update existing one
2. Build workflow JSON: `python tools/deploy_{dept}.py build`
3. Researcher module searches for improved patterns
4. Builder module generates replacement workflow
5. Name the replacement `{name} v2` during development

### Phase 3: Validate & Test (1-2 hours)

1. Validator module checks structural integrity
2. Generate test suite from new spec
3. Deploy as inactive `[TEST] {name} v2` on n8n
4. Run test executions
5. Compare outputs against live workflow outputs (same inputs, different versions)

### Phase 4: Side-by-Side Comparison (24-48 hours)

1. Run both old and new workflows for 24h (new one inactive, manual test triggers)
2. Compare:
   - Output quality (are results equivalent or better?)
   - Execution time (is new version faster?)
   - Error rate (is new version more reliable?)
   - Resource usage (token budget, API calls)
3. Document comparison results

### Phase 5: Cutover (30 minutes)

**Requires approval for medium/high-risk workflows.**

1. Export current live workflow: `workflow_deployer.export_workflow()` → archive
2. Deactivate old workflow
3. Deploy new version with original workflow name
4. Activate new version
5. Monitor first 5 executions intensively

### Phase 6: Archive & Document (30 minutes)

1. Move old workflow JSON to `workflows/{dept}/archive/{name}-v{N}.json`
2. Update SOP documentation
3. Create revamp report:
   - Why revamped
   - What changed
   - Test results
   - Comparison metrics
4. Update workflow memory record
5. Reset maintainability score (starts fresh)

---

## Deprecation and Archival

### Workflow Deprecation

When a workflow is no longer needed (business process changed, replaced by different approach):

1. Deactivate the workflow (don't delete immediately)
2. Mark as `[DEPRECATED]` in workflow name
3. Move spec to `autonomous/memory/specs/archive/`
4. Wait 30 days (in case it's needed again)
5. After 30 days with no usage: delete from n8n, archive JSON to `workflows/{dept}/archive/`

### Archive Structure

```
workflows/{dept}/archive/
├── ads-01-strategy-v1.json          # First version
├── ads-01-strategy-v2.json          # Second version (revamped)
├── deprecated-old-email-bot.json    # Deprecated and archived
└── archive_index.json               # Index of all archived workflows
```

---

## Communication Requirements

| Action | Who to Notify | How | When |
|---|---|---|---|
| Revamp assessment triggered | Ian | Telegram (advisory) | When threshold crossed |
| Revamp decision (patch vs rebuild) | Ian | Telegram + summary doc | Before starting build |
| Comparison results ready | Ian | Email with metrics | After Phase 4 |
| Cutover request | Ian | Telegram (approval required for medium+) | Before Phase 5 |
| Cutover complete | Ian | Telegram (confirmation) | After Phase 5 |
| Workflow deprecated | Ian | Telegram (info) | When marked deprecated |

---

## Revamp Frequency Limits

To prevent excessive rebuilding:

| Constraint | Limit |
|---|---|
| Max revamps per workflow per quarter | 1 (if needed again, investigate root cause) |
| Max concurrent revamps per department | 1 (avoid destabilizing a department) |
| Max concurrent revamps system-wide | 3 |
| Minimum time between revamp and next patch | 14 days (let the new version stabilize) |

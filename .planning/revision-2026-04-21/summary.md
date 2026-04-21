# Full Revision — Stabilization Pass

**Date:** 2026-04-21
**Scope chosen:** Stabilization tier (no deep overhaul).

## Before → After

| Metric | Before | After |
|---|---|---|
| Active workflows | 35 | 36 (SC-01 reactivated) |
| Active workflows with MCP access | 2 | 36 |
| Active workflows with dead Airtable cred ref | 14 | 0 |
| Business Email Mgmt validator errors | 2 (Create Follow-Up, Update Lead Status) | 0 |
| Deploy scripts reading env without dotenv | 10 | 0 |
| `$env` in JS Code nodes across deploy scripts | 0 | 0 (verified) |

## What was done

### Live n8n fleet
1. **Enabled `settings.availableInMCP` on all 36 active workflows.** New fleet tool: `tools/enable_mcp_access_all_active.py`. Found and worked around an n8n Cloud PUT schema quirk (`binaryMode`, `executionTimeout` are returned by GET but rejected by PUT as "additional properties"). Tool is idempotent and supports `--check` and `--dry-run`.
2. **Rotated a dead Airtable credential** (`j0HMJbsIoJgSpLAS` → `vPjIuQXz26XBX1r9` "Airtable PAT AVM") across **14 active** and **12 inactive** workflows. 39 node refs rewritten. Root cause of multiple silent failures across SC, PP, PF, AVM Website/SEO Lead surfaces. New fleet tool: `tools/rotate_credential_ref.py`.
3. **Fixed Business Email Mgmt** (`Q0gI2m6ACi9Et3J0`): 4 Google Sheets v4.7 nodes were missing `__rl: True` on `documentId` / `sheetName` resource locators and the required `schema: []` array. Patched source in `tools/deploy_business_email_mgmt.py` + redeployed live. Added `availableInMCP: True` to the workflow's build settings so redeploys never wipe MCP access again.
4. **Reactivated SC-01 Trend Discovery.** It was dark because of yesterday's cred patch; the new cred is good and Airtable is currently serving requests (PP-01 / PP-03 / RE-11 all succeeded today). SC-01 also got MCP access enabled.
5. **Ran a full execution-history health sweep.** New tool: `tools/revision_health_check.py`. Writes `.planning/revision-2026-04-21/health-report.md`. Summary at end of this doc.

### Tooling hygiene
6. **Added `load_dotenv()` to 10 FA deploy scripts** that were reading `FA_*` env vars without loading `.env`. (FA dept is currently inactive, but the scripts would silently misbehave if run.)
7. **Verified `$env` in JS Code nodes is clean** — the only `$env` hits are in HTTP Request headers in demo scripts (with safe `|| 'MISSING'` fallbacks). No live JS Code nodes reference `$env`.
8. **Confirmed `tools/n8n_client.py` is solid** — retries, caching, context manager all good. No changes.

## New / modified files

- **New tools:** `tools/enable_mcp_access_all_active.py`, `tools/revision_health_check.py`, `tools/rotate_credential_ref.py`.
- **Modified tools:** `tools/deploy_business_email_mgmt.py` (Sheets nodes + availableInMCP), `tools/deploy_fa_wf0{2,3,4,5,6,7a,7b,8,9}.py`, `tools/deploy_fa_wf10.py` (dotenv).
- **New artifacts:** `.planning/revision-2026-04-21/{health-report.md, AIRTABLE_QUOTA_RESOLUTION.md, summary.md}`.
- **Regenerated:** `workflows/business_email_mgmt_automation_v2.json`.

## Still open / flagged

- **LI-10 Feedback Loop** — status RED but last failure is 2026-04-01 (3 weeks old). The only 3 recent executions succeeded. Treating as historical; no fix needed unless the failure class reappears.
- **SC-04 Video Production, SC-05 Distribution** — still show RED because their last scheduled executions (2026-04-21 03:00 / 04:00 UTC) were BEFORE my cred rotation patch. They run daily on cron. Next run (~2026-04-22 03:00 UTC) will validate. If they still fail, the Airtable fix wasn't the complete story.
- **AVM: Send Email (Webhook), PF-02 ITN Handler, PP-06 Callback Handler, RE-01 WhatsApp Intake** — never executed in the window. They're all webhook-triggered — no activity is expected unless the upstream source fires. Flag only.
- **Airtable quota** — see `AIRTABLE_QUOTA_RESOLUTION.md`. Quota appears to have cleared (live writes succeeding), but 15 active workflows now depend on Airtable. Handoff doc lists them and the action path if quota tightens again.
- **2 stale git worktrees** in `.claude/worktrees/` (`condescending-germain-2dfaab`, `jovial-meitner-e6ee6d`) — both have uncommitted edits to `.claude/hooks/*.sh`. Not deleted this pass since they contain work you may want to inspect. Delete manually with `git worktree remove` once you've confirmed.
- **14 fix scripts strip `availableInMCP` from settings during redeploy.** Example: `tools/fix_linkedin_gsheets_resilience.py` has a hardcoded `clean_settings` list that doesn't include MCP. If you re-run any of them, MCP access will disappear again on those workflows. Adding `availableInMCP` to those preserved-keys lists is a worthwhile follow-up; deferred this pass.

## Deferred (explicit out-of-scope)

- Archiving 12 dated one-shot fix scripts
- Adding try/except to 35 scripts missing it
- Central workflow ID registry (YAML) to decouple fix scripts from hardcoded IDs
- CI / pre-deploy validator gate
- Portal billing agent-count TODO (backlog)

## Commands for follow-up

```bash
# Re-verify health any time:
python tools/revision_health_check.py

# Re-verify MCP access status:
python tools/enable_mcp_access_all_active.py --check

# Future cred rotations:
python tools/rotate_credential_ref.py --from OLD_ID --to NEW_ID --new-name "Display Name" --active-only --dry-run
```

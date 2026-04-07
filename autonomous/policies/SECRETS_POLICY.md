# Secrets Policy — AVM Autonomous Workflow Engineer

> Cross-references: [AUTONOMY_POLICY.md](AUTONOMY_POLICY.md), [CHANGE_RISK_MATRIX.md](CHANGE_RISK_MATRIX.md)

## What Constitutes a Secret

| Category | Examples | Storage Location |
|---|---|---|
| API keys | `N8N_API_KEY`, `AIRTABLE_API_TOKEN`, `SERPAPI_KEY`, `OPENROUTER_API_KEY` | `.env` only |
| OAuth tokens | Gmail OAuth, Google Ads OAuth, QuickBooks OAuth | `.env` + n8n credential store |
| Database credentials | `SUPABASE_SERVICE_ROLE_KEY`, `NEXT_PUBLIC_SUPABASE_URL` | `.env` only |
| Webhook secrets | Incoming webhook URLs with auth tokens | `.env` only |
| Platform credentials | GitHub PAT, Telegram bot token | `.env` only |
| Encryption keys | Any signing or encryption material | `.env` only |
| Account identifiers with auth implications | n8n credential IDs (internal refs, not secrets but sensitive) | Deploy scripts (hardcoded, acceptable) |

---

## Storage Rules

### Where Secrets MUST Live

| Location | What Goes Here |
|---|---|
| `.env` | ALL secret values — API keys, tokens, passwords |
| `.env.template` | Variable names with placeholder values (for documentation) |
| n8n credential store | OAuth tokens, API keys used in n8n workflow nodes |

### Where Secrets MUST NEVER Appear

| Location | Why |
|---|---|
| Source code (`tools/*.py`, `autonomous/*.py`) | Committed to git, visible in history |
| `config.json` | Committed to git |
| Workflow JSON (`workflows/**/*.json`) | Committed to git |
| `autonomous/memory/` | Readable by any session |
| Claude Code memory (`~/.claude/projects/.../memory/`) | Persists across sessions |
| Log output (stdout, Telegram messages) | Visible to observers |
| Error messages | May be logged or displayed |
| Commit messages | Permanent git history |
| n8n Code nodes (`jsCode` parameter) | Workflow JSON is exported/committed |

---

## AWE Secret Access Rules

### What AWE Can Do

| Action | Allowed | How |
|---|---|---|
| Read `.env` to verify a secret exists | Yes | Check if key is present, never log the value |
| Reference n8n credential IDs in deploy scripts | Yes | IDs are internal refs, not secrets |
| Use `n8n_client.py` (which reads API key from env) | Yes | Key loaded at init, never logged |
| Verify credential validity via n8n health check | Yes | Test connectivity, don't expose credentials |

### What AWE MUST NEVER Do

| Action | Why |
|---|---|
| Log, print, or display any secret value | Exposure risk |
| Include secret values in memory files | Persists across sessions |
| Include secret values in incident reports | Reports may be shared |
| Include secret values in Telegram/email alerts | External channels |
| Modify `.env` file (add, change, or remove entries) | High risk, requires Ian |
| Create new n8n credentials | Requires manual OAuth flow or secret input |
| Rotate secrets autonomously | Multi-system coordination needed |

---

## n8n Cloud Specific Rules

1. **No `$env` in Code nodes** — n8n Cloud blocks environment variable access in JavaScript Code nodes. Values must be hardcoded or passed via upstream node parameters.

2. **Credential references are by ID** — Deploy scripts reference n8n credentials by their internal ID (e.g., `credentialId: "abc123"`). These IDs are not secrets but should not be publicly shared.

3. **OAuth flows are manual** — Gmail, Google Ads, QuickBooks, and other OAuth credentials require browser-based authorization. AWE cannot create or refresh these.

---

## Secret Rotation Policy

| Secret Type | Rotation Frequency | Detection Method | AWE Role |
|---|---|---|---|
| API keys (Airtable, OpenRouter, SerpAPI) | Every 90 days or on suspected exposure | Calendar reminder + auth failure detection | Detect failure, alert Ian |
| OAuth tokens (Gmail, Google Ads) | Auto-refresh (handled by n8n) | Auth failure in execution logs | Detect failure, alert Ian |
| n8n API key | Every 90 days | Calendar reminder | Alert Ian |
| Supabase service role key | Every 90 days | Calendar reminder | Alert Ian |
| GitHub PAT | Every 90 days | API 401 detection | Alert Ian |
| Telegram bot token | On suspected exposure only | Message delivery failure | Alert Ian |

### Rotation Process (Manual — Ian Only)

1. Generate new secret in the provider dashboard
2. Update `.env` with new value
3. Update n8n credential store if applicable
4. Test affected workflows
5. Revoke old secret
6. Update `.env.template` if key name changed
7. Commit `.env.template` changes (NOT `.env`)

---

## Exposure Response

If AWE detects or suspects a secret has been exposed:

### Immediate Actions (Autonomous)

1. **Alert Ian** — Telegram P1: `"[P1 SECURITY] Possible secret exposure: {key_name}. Source: {where found}. DO NOT use this key until rotated."`
2. **Log incident** — Create P1 incident in `autonomous/memory/incidents/`
3. **Do NOT attempt to rotate** — AWE cannot safely modify secrets

### Ian's Actions (Manual)

1. Rotate the exposed secret immediately
2. Audit git history: `git log --all -p -- .env` (should show nothing if .gitignore is correct)
3. Check if `.env` was accidentally committed: `git log --diff-filter=A -- .env`
4. Revoke the exposed key in the provider dashboard
5. Update all systems that use the key
6. Test affected workflows
7. Confirm resolution to AWE

---

## Verification Checks

AWE should periodically verify (read-only):

| Check | Frequency | How |
|---|---|---|
| `.env` exists and is not empty | Every session start | `os.path.exists()` |
| `.env` is in `.gitignore` | Weekly | Read `.gitignore`, verify `.env` is listed |
| No secrets in committed files | Weekly | Grep for common patterns: `sk-`, `pat_`, `Bearer `, API key formats |
| n8n credentials are valid | Daily | `n8n_client.health_check()` |
| Required env vars present | Every deployment | Check all vars referenced in deploy script |

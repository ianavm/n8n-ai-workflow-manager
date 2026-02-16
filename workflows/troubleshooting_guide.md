# n8n Troubleshooting Guide

## Common Issues and Solutions

### Connection Issues

#### Cannot connect to n8n instance
**Symptoms:** `run_manager.py status` fails, "Connection refused" errors

**Checklist:**
1. Verify n8n is running: Check the n8n process or Docker container
2. Check URL: Ensure `N8N_BASE_URL` in `.env` matches the actual instance URL
3. Check port: Default n8n port is 5678 (self-hosted) or custom for cloud
4. Check HTTPS: If using SSL, ensure the certificate is valid
5. Check firewall: Ensure the port is open from your machine
6. Test manually: `curl https://your-n8n-url/api/v1/workflows -H "X-N8N-API-KEY: your-key"`

#### API key authentication fails
**Symptoms:** 401 Unauthorized responses

**Checklist:**
1. Verify key in `.env`: `N8N_API_KEY=your-actual-key`
2. Check key format: No quotes, no trailing whitespace
3. Regenerate key: In n8n UI → Settings → API → Create new key
4. Check permissions: API key must have workflow and execution access

---

### Execution Monitoring Issues

#### No executions found
**Symptoms:** Monitor shows 0 executions

**Possible causes:**
- Workflows are inactive (no triggers firing)
- Execution history pruning is too aggressive in n8n settings
- `execution_history_days` in config is too short
- n8n instance was recently restarted (in-memory execution log cleared)

**Fix:** Check n8n UI → Executions tab. If executions appear there but not via API, the API pagination or date filter may need adjustment.

#### Stale workflow false positives
**Symptoms:** Monitor flags workflows as stale that are actually fine

**Possible causes:**
- Workflow triggers are schedule-based with long intervals (weekly/monthly)
- Webhook-triggered workflows that haven't received traffic

**Fix:** Review the stale detection threshold. Some workflows legitimately run infrequently.

---

### Analysis and Chart Issues

#### Chart generation fails
**Symptoms:** `generate_charts.py` errors out

**Checklist:**
1. Check dependencies: `pip install plotly kaleido pandas`
2. Check kaleido version: `pip install --upgrade kaleido`
3. Check disk space: Charts are saved to `.tmp/charts/`
4. Check data: Ensure `.tmp/execution_data.json` exists and has data

#### Analysis shows no recommendations
**Symptoms:** Empty recommendations in analysis output

**Possible cause:** Not enough execution data to analyze. Need at least a few days of execution history.

---

### Google Slides / Email Issues

#### Google OAuth token expired
**Symptoms:** "Token has been expired or revoked" error

**Fix:**
1. Delete `token.json` from project root
2. Run any Google-dependent tool (e.g., `run_manager.py report`)
3. Complete the OAuth flow in the browser
4. New `token.json` will be created

#### Slides creation fails
**Symptoms:** "HttpError 403" or permission denied

**Checklist:**
1. Ensure Google Slides API is enabled in Cloud Console
2. Ensure Google Drive API is enabled
3. Check OAuth scopes include Slides and Drive
4. Verify `credentials.json` is for the correct Google Cloud project

#### Email sending fails
**Symptoms:** Gmail API error

**Checklist:**
1. Ensure Gmail API is enabled in Cloud Console
2. Check OAuth scopes include Gmail send
3. Verify recipient email in `config.json` is valid
4. Check Gmail sending limits (2,000/day for regular accounts)

---

### Deployment Issues

#### Workflow deploy fails
**Symptoms:** Error when running `workflow_deployer.py deploy`

**Checklist:**
1. Validate JSON: Ensure the workflow file is valid JSON
2. Check node types: All node types must be installed on target n8n instance
3. Check credentials: Referenced credentials must exist on target instance
4. Check n8n version: Some node types require specific n8n versions

#### Deployed workflow won't activate
**Symptoms:** Workflow deploys but activation fails

**Possible causes:**
- Missing credentials referenced by nodes
- Invalid webhook paths (conflicts with existing webhooks)
- Node configuration errors (missing required fields)

**Fix:** Check n8n UI for specific activation error messages.

---

### AI Node Issues

#### AI audit finds no nodes
**Symptoms:** `ai-audit` reports 0 AI nodes

**Possible causes:**
- No LangChain/OpenAI nodes in any workflow
- HTTP Request nodes calling AI APIs aren't detected (URL doesn't match known patterns)
- Code nodes with AI calls use non-standard import patterns

**Fix:** Review `AI_NODE_TYPES` in `ai_node_manager.py` and add any custom AI node types.

#### Cost estimates seem wrong
**Symptoms:** Estimated costs don't match actual API bills

**Note:** Cost estimates are approximations based on:
- Token count estimated from word count (× 1.3 factor)
- Default 100 executions/day assumption
- Static pricing (may be outdated)

**Fix:** Adjust `executions_per_day` parameter and verify current model pricing.

---

### General Python Issues

#### Module not found errors
**Symptoms:** `ImportError` or `ModuleNotFoundError`

**Fix:**
```bash
pip install -r requirements.txt
```

#### Encoding errors on Windows
**Symptoms:** Unicode characters cause crashes

**Fix:** Use `run_manager.bat` which sets UTF-8 encoding, or:
```bash
set PYTHONIOENCODING=utf-8
chcp 65001
```

#### Config loading fails
**Symptoms:** "Error loading config" or missing key errors

**Checklist:**
1. `config.json` exists in project root
2. `.env` file exists with required keys
3. JSON is valid (no trailing commas, proper quoting)
4. Required sections exist: `n8n`, `monitoring`, `reporting`, `email`

---

## Quick Diagnostic Commands

```bash
# Test n8n connection
python tools/n8n_client.py

# Test config loading
python -c "from tools.config_loader import load_config; c = load_config(); print('OK:', list(c.keys()))"

# Test Google auth
python -c "from tools.google_auth import get_google_credentials; get_google_credentials()"

# Check Python dependencies
pip list | findstr /i "requests pandas plotly httpx"

# Check .env contents (Windows)
type .env
```

## Getting Help

1. Check n8n community forum: https://community.n8n.io
2. Check n8n API docs: https://docs.n8n.io/api/
3. Review error logs in n8n UI → Executions → Failed
4. Run `python tools/run_manager.py --help` for mode descriptions

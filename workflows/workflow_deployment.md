# Workflow Deployment SOP

## Objective
Deploy, export, version-control, and manage n8n workflow lifecycle with validation and rollback capabilities.

## Prerequisites
- n8n API key configured in `.env`
- `config.json` with correct `base_url`
- Workflow JSON files ready for deployment (from sibling project or exports)

## Expected Outputs
- Deployed workflows on n8n instance
- `.tmp/workflow_exports/` - Exported workflow JSON backups
- Console confirmation of deployment status

## Deployment Process

### 1. Export Current State (Backup)

**Always back up before deploying changes.**

```bash
python tools/run_manager.py deploy
```

Select `export-all` action. This saves every workflow to `.tmp/workflow_exports/<workflow_name>.json`.

**Verify:** Check that export files exist and contain valid JSON.

### 2. Prepare Workflow JSON

Workflow JSON files should follow n8n's export format:

```json
{
  "name": "My Workflow",
  "nodes": [...],
  "connections": {...},
  "settings": {...}
}
```

**Sources for workflow JSON:**
- Exported from n8n UI (Settings > Export)
- Exported via this tool (`export-all`)
- Sibling project: `../n8n Agentic Workflows/` contains 66+ workflow templates
- Custom-built JSON following n8n schema

### 3. Validate Before Deploying

Compare a local JSON file against the deployed version:

```bash
python tools/workflow_deployer.py compare <workflow_id> <local_file.json>
```

This uses `deepdiff` to show:
- Added/removed nodes
- Changed parameters
- Modified connections

### 4. Deploy Workflow

```bash
python tools/workflow_deployer.py deploy <workflow_file.json>
```

**Process:**
1. Reads and validates the JSON file
2. Creates the workflow via n8n API
3. Reports the new workflow ID
4. Workflow is created in **inactive** state by default

### 5. Activate Workflow

After verifying the deployment looks correct in the n8n UI:

```bash
# Activate via the n8n UI, or programmatically:
python -c "
from tools.config_loader import load_config
from tools.n8n_client import N8nClient
config = load_config()
with N8nClient(config['n8n']['base_url'], config['api_keys']['n8n']) as client:
    client.activate_workflow('<workflow_id>')
    print('Activated')
"
```

### 6. Verify Deployment

After activation, run a monitoring check:

```bash
python tools/run_manager.py monitor
```

Confirm the workflow appears in the active list and executes successfully.

## Batch Operations

### Activate All Workflows
Use with caution - typically you want to activate workflows individually after testing.

### Deactivate All Workflows
Emergency shutdown - deactivates all workflows. Useful during maintenance windows.

## Rollback Procedure

If a deployed workflow causes issues:

1. **Deactivate** the problematic workflow immediately
2. **Check exports** in `.tmp/workflow_exports/` for the previous version
3. **Compare** the current deployed version vs the backup
4. **Re-deploy** the backup version
5. **Activate** the restored workflow
6. **Monitor** for successful executions

## Best Practices

1. **Always export before deploying** - Create backups of the current state
2. **Deploy inactive** - Never auto-activate new deployments in production
3. **Test in staging first** - Use the staging instance configured in `config.json`
4. **Version control** - Keep workflow JSONs in git alongside this project
5. **One at a time** - Deploy and verify workflows individually
6. **Monitor after activation** - Run `monitor` mode within 15 minutes of activating
7. **Document changes** - Run `docs` mode after successful deployment

## Workflow Categories

Organize workflows by category (as defined in `config.json`):

| Category | Examples |
|----------|----------|
| `client_onboarding` | Welcome emails, CRM setup, task creation |
| `whatsapp_agents` | AI chatbots, lead qualification, support |
| `social_media` | Content scheduling, engagement tracking |
| `lead_generation` | Form processing, lead scoring, routing |
| `internal_tools` | Notifications, data sync, backups |
| `ai_agents` | LangChain agents, RAG pipelines, summarization |

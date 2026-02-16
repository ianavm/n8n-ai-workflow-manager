# Workflow Templates

Reusable n8n workflow templates organized by category.

## Categories

| Category | Description | Status |
|----------|-------------|--------|
| `ai_chatbot` | AI-powered conversational agents (WhatsApp, Telegram, web) | Planned |
| `lead_qualification` | Automated lead scoring and routing workflows | Planned |
| `error_notification` | Error detection and alerting workflows | Planned |
| `client_onboarding` | Automated client setup and welcome sequences | Planned |
| `content_automation` | Social media scheduling and content generation | Planned |

## Usage

1. Browse templates by category
2. Copy the JSON file to your working directory
3. Customize parameters (API keys, URLs, prompts)
4. Deploy using the workflow deployer:

```bash
python tools/run_manager.py deploy
```

## Template Structure

Each template JSON follows n8n's standard export format:

```json
{
  "name": "Template Name",
  "nodes": [...],
  "connections": {...},
  "settings": {...}
}
```

## Contributing Templates

To add a new template:

1. Build and test the workflow in n8n
2. Export via n8n UI or `python tools/workflow_deployer.py export-all`
3. Remove any hardcoded credentials or API keys
4. Place the JSON in the appropriate category folder
5. Update this README with the template description

## Sibling Project

The main workflow JSON library lives at `../n8n Agentic Workflows/` with 66+ production workflows. Templates here are simplified, reusable starting points derived from those production workflows.

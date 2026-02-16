# n8n Agentic Workflows Manager

This project uses the **WAT framework** (Workflows, Agents, Tools) to manage n8n automation workflows programmatically. It provides Python tools for deploying, monitoring, analyzing, and optimizing AI-powered n8n workflows.

## Architecture Overview

- **Workflows** (`workflows/`): Markdown SOPs that define objectives, inputs, tools, outputs, and edge cases
- **Agents**: AI coordinators that read workflows and execute tools in the correct sequence
- **Tools** (`tools/`): Python scripts for deterministic execution (n8n API calls, monitoring, analytics, reporting)

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the template and add your API keys:

```bash
cp .env.template .env
```

Edit `.env` and configure:
- `N8N_BASE_URL` - Your n8n instance URL
- `N8N_API_KEY` - Your n8n API key
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY` - AI model keys (optional)
- Google OAuth credentials (for Slides/Gmail reporting)

### 3. Configure n8n Instance

Edit `config.json` with your n8n instance details, monitoring thresholds, and reporting preferences.

### 4. Google OAuth (for reporting)

If using Google Slides reports and email delivery:
1. Download `credentials.json` from Google Cloud Console
2. Place it in the project root
3. On first run, you'll authenticate and generate `token.json`

### 5. Verify Connection

```bash
python tools/n8n_client.py
```

## Project Structure

```
.tmp/              # Temporary files (regenerated as needed)
tools/             # Python scripts for n8n management
workflows/         # Markdown workflow definitions (SOPs)
templates/         # Reusable n8n workflow templates
.env               # API keys and environment variables (gitignored)
CLAUDE.md file.md  # Agent instructions and framework documentation
```

## Tools

| Tool | Purpose |
|------|---------|
| `n8n_client.py` | Core n8n REST API client (workflow CRUD, executions, health check) |
| `workflow_deployer.py` | Deploy, export, activate/deactivate workflows |
| `execution_monitor.py` | Monitor executions, detect failures, health dashboard |
| `workflow_analyzer.py` | Performance analytics with pandas (success rates, trends) |
| `ai_node_manager.py` | AI node scanning, prompt analysis, cost estimation |
| `workflow_docs_generator.py` | Auto-generate workflow documentation |
| `generate_charts.py` | Plotly charts for workflow performance |
| `create_report.py` | Google Slides performance reports |
| `send_email.py` | Gmail delivery for reports and alerts |
| `run_manager.py` | Main orchestrator with multiple operation modes |
| `config_loader.py` | Configuration management |
| `google_auth.py` | Google OAuth handler |

## How It Works

1. **Connect** to your n8n instance via API
2. **Manage** workflows using Python tools (deploy, monitor, analyze)
3. **Optimize** AI nodes and workflow performance
4. **Report** with professional Google Slides presentations delivered via email

## Operation Modes

```bash
python tools/run_manager.py status     # Quick health check
python tools/run_manager.py monitor    # Monitor executions, detect errors
python tools/run_manager.py analyze    # Deep performance analysis with charts
python tools/run_manager.py report     # Full report (Slides + Email)
python tools/run_manager.py deploy     # Deploy workflow from JSON
python tools/run_manager.py docs       # Generate workflow documentation
python tools/run_manager.py ai-audit   # Audit AI nodes across workflows
```

## Core Principles

- **Separation of concerns**: AI handles reasoning, code handles execution
- **Cloud-first deliverables**: Final outputs go to Google Slides, email, etc.
- **Local files are temporary**: Everything in `.tmp/` is disposable
- **Continuous improvement**: Learn from failures and update workflows

See [CLAUDE.md file.md](CLAUDE.md%20file.md) for detailed agent instructions.

# n8n Agentic Workflows Manager - Master SOP

## Objective
Manage, monitor, analyze, and optimize all n8n workflows across your automation infrastructure. This is the master guide covering all 7 operational modes.

## Prerequisites

### Required Setup
- [x] n8n instance running and accessible
- [x] n8n API key in `.env` file (`N8N_API_KEY`)
- [x] `N8N_BASE_URL` set in `.env` (e.g., `https://n8n.yourdomain.com`)
- [x] `config.json` configured with instance details and thresholds
- [x] Google OAuth credentials for reporting (`credentials.json`)
- [x] Email recipient configured in `config.json`
- [x] Dependencies installed: `pip install -r requirements.txt`

### API Access
- n8n REST API: Requires API key with full workflow/execution access
- Google Slides API: For report generation
- Gmail API: For report delivery

## Quick Start

### One-Command Execution
```bash
python tools/run_manager.py status
```

### All Available Modes
```bash
python tools/run_manager.py status      # Quick health check
python tools/run_manager.py monitor     # Full monitoring cycle
python tools/run_manager.py analyze     # Deep performance analysis
python tools/run_manager.py report      # Full report (Slides + Email)
python tools/run_manager.py deploy      # Deploy workflow from JSON
python tools/run_manager.py docs        # Generate documentation
python tools/run_manager.py ai-audit    # Audit AI nodes
```

Or use the Windows launcher:
```bash
run_manager.bat status
```

## Mode Details

### 1. Status Check (`status`)
**Purpose:** Quick health check and workflow overview.

**Steps:**
1. Connects to n8n instance
2. Lists all workflows with active/inactive status
3. Reports connection health

**Output:** Console summary of workflow inventory.

**When to use:** Daily check-in, verifying n8n is online, quick inventory count.

---

### 2. Monitor (`monitor`)
**Purpose:** Full monitoring cycle - fetch executions, detect errors, identify stale workflows.

**Steps:**
1. Connect to n8n and verify health
2. Fetch recent executions across all workflows
3. Calculate success/failure rates per workflow
4. Detect failing workflows exceeding error threshold
5. Identify stale workflows (active but no recent executions)
6. Generate health dashboard

**Output:**
- Console health dashboard with status indicators
- `.tmp/monitoring_results.json` - Full monitoring data
- `.tmp/execution_data.json` - Raw execution records

**When to use:** Regular monitoring (recommend every 15-30 minutes via cron/scheduler).

**See also:** [Monitoring & Alerting SOP](monitoring_and_alerting.md)

---

### 3. Analyze (`analyze`)
**Purpose:** Deep performance analysis with charts and optimization recommendations.

**Steps:**
1. Fetch execution data (calls execution_monitor)
2. Analyze workflow performance metrics (success rates, throughput, duration)
3. Generate 5 performance charts (Plotly)
4. Produce optimization recommendations

**Output:**
- `.tmp/analysis_results.json` - Detailed metrics
- `.tmp/charts/workflow_success_rates.png`
- `.tmp/charts/category_performance.png`
- `.tmp/charts/workflow_comparison.png`
- `.tmp/charts/execution_trend.png`
- `.tmp/charts/duration_scatter.png`

**When to use:** Weekly deep-dive, before client meetings, after deploying new workflows.

---

### 4. Report (`report`)
**Purpose:** End-to-end report generation - analysis + charts + Google Slides + email delivery.

**Steps:**
1. Fetch execution data
2. Analyze workflow performance
3. Generate performance charts
4. Create 7-slide Google Slides presentation
5. Send email with report link
6. Print summary

**Output:**
- Google Slides presentation (shared via link)
- Email delivered to configured recipient
- All intermediate files in `.tmp/`

**When to use:** Weekly/monthly stakeholder reports, client deliverables.

---

### 5. Deploy (`deploy`)
**Purpose:** Deploy, export, and manage workflow lifecycle.

**Actions available:**
- `export-all` - Export all workflows to JSON files
- `deploy <file>` - Deploy a workflow from JSON
- `compare <id> <file>` - Compare deployed vs local version

**When to use:** Deploying new workflows, backing up configurations, version control.

**See also:** [Workflow Deployment SOP](workflow_deployment.md)

---

### 6. Documentation (`docs`)
**Purpose:** Auto-generate markdown documentation from workflow definitions.

**Steps:**
1. Connect to n8n and fetch all workflows
2. Generate full workflow catalog
3. Generate individual docs for each active workflow (with Mermaid flow diagrams)

**Output:**
- `.tmp/workflow_catalog.md` - Full catalog table
- `.tmp/workflow_docs/<workflow_name>.md` - Individual workflow docs

**When to use:** After deploying new workflows, for onboarding documentation, audit preparation.

**See also:** [Workflow Documentation SOP](workflow_documentation.md)

---

### 7. AI Audit (`ai-audit`)
**Purpose:** Scan, analyze, and optimize AI-specific nodes across all workflows.

**Steps:**
1. Scan all workflows for AI nodes (LangChain, OpenAI, HTTP-based AI calls, Code nodes)
2. Analyze prompt quality (persona, output format, examples, constraints)
3. Estimate daily/monthly AI API costs per node
4. Audit security (token limits, input sanitization)

**Output:**
- `.tmp/ai_audit_results.json` - Full audit data

**When to use:** Monthly cost review, before scaling AI workflows, security audits.

**See also:** [AI Node Optimization SOP](ai_node_optimization.md)

## Recommended Schedule

| Frequency | Mode | Purpose |
|-----------|------|---------|
| Every 15 min | `status` | Health check (automate via cron) |
| Hourly | `monitor` | Error detection and alerting |
| Weekly | `analyze` | Performance deep-dive |
| Weekly/Monthly | `report` | Stakeholder report delivery |
| As needed | `deploy` | Workflow deployment and backup |
| After deployments | `docs` | Keep documentation current |
| Monthly | `ai-audit` | Cost and security review |

## Troubleshooting

If any mode fails, check:
1. n8n instance is running: `python tools/n8n_client.py`
2. API key is valid: Check `.env` for `N8N_API_KEY`
3. Network connectivity: Can you reach `N8N_BASE_URL` from this machine?
4. Google OAuth (for report mode): Re-run auth flow if `token.json` is expired

**See also:** [Troubleshooting Guide](troubleshooting_guide.md)

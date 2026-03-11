"""
AVM Autonomous Operations - Combined Overview Builder

Unpacks ALL 27 agent workflow nodes into a single massive workflow
so clients can see the full complexity of the system.

Reads every workflow JSON, repositions nodes into a structured grid
layout with department headers (sticky notes), and combines them into
one visual overview workflow.

Usage:
    python tools/build_avm_combined_overview.py build    # Build JSON
    python tools/build_avm_combined_overview.py deploy   # Build + push to n8n
    python tools/build_avm_combined_overview.py update   # Update existing overview
"""

import json
import os
import sys
import uuid
import glob
import copy
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
AVM_PROJECT_ID = "X8YS2aPAoXgAHLmS"
EXISTING_OVERVIEW_ID = "Zp1gCxlgYtXA9lJO"

BASE_DIR = Path(__file__).parent.parent


def uid():
    return str(uuid.uuid4())


# ── Department Layout Configuration ──────────────────────────────────────────
# Each department gets a row. Workflows within a department are placed side by side.
# Format: (label, color, glob_pattern, workflows_in_order)

DEPARTMENTS = [
    {
        "name": "CENTRAL ORCHESTRATOR",
        "subtitle": "Coordinates all 6 department agents | Health monitoring, event routing, KPI aggregation, weekly reports",
        "color": 1,  # yellow
        "dir": "orchestrator",
        "files": [
            "orch01_health_monitor.json",
            "orch02_cross_dept_router.json",
            "orch03_daily_kpi_aggregation.json",
            "orch04_weekly_report.json",
        ],
    },
    {
        "name": "MARKETING AGENT",
        "subtitle": "Campaign ROI tracking & budget optimization | Enhances existing 4 marketing workflows",
        "color": 2,  # blue
        "dir": "marketing-agent",
        "files": [
            "mkt05_campaign_roi_tracker.json",
            "mkt06_budget_optimizer.json",
        ],
    },
    {
        "name": "FINANCE & ACCOUNTING AGENT",
        "subtitle": "Cash flow forecasting & anomaly detection | Enhances existing 7 accounting workflows",
        "color": 3,  # green
        "dir": "finance-agent",
        "files": [
            "fin08_cash_flow_forecast.json",
            "fin09_anomaly_detector.json",
        ],
    },
    {
        "name": "CONTENT CREATION AGENT",
        "subtitle": "Performance feedback loops & multi-format content generation | AI-driven content strategy",
        "color": 5,  # purple
        "dir": "content-agent",
        "files": [
            "content01_performance_feedback.json",
            "content02_multi_format_generator.json",
        ],
    },
    {
        "name": "CLIENT RELATIONS AGENT",
        "subtitle": "Health scoring, renewal management, onboarding automation & satisfaction monitoring",
        "color": 4,  # orange
        "dir": "client-relations",
        "files": [
            "cr01_client_health_scorer.json",
            "cr02_renewal_manager.json",
            "cr03_onboarding_automation.json",
            "cr04_satisfaction_pulse.json",
        ],
    },
    {
        "name": "CUSTOMER SUPPORT AGENT",
        "subtitle": "AI ticket creation, SLA monitoring, auto-resolution & knowledge base building",
        "color": 6,  # red
        "dir": "support-agent",
        "files": [
            "sup01_ticket_creator.json",
            "sup02_sla_monitor.json",
            "sup03_auto_resolver.json",
            "sup04_kb_builder.json",
        ],
    },
    {
        "name": "WHATSAPP COMMUNICATION AGENT",
        "subtitle": "Conversation analytics, CRM sync & issue detection | Ready for Meta verification",
        "color": 7,  # gray
        "dir": "whatsapp-agent",
        "files": [
            "wa01_conversation_analyzer.json",
            "wa02_crm_sync.json",
            "wa03_issue_detector.json",
        ],
    },
    {
        "name": "INTELLIGENCE LAYER",
        "subtitle": "Cross-department correlations, executive reporting & prompt performance tracking",
        "color": 1,  # yellow
        "dir": "intelligence",
        "files": [
            "intel01_correlator.json",
            "intel02_executive_report.json",
            "intel03_prompt_tracker.json",
        ],
    },
    {
        "name": "SELF-IMPROVEMENT ENGINE",
        "subtitle": "A/B testing, statistical analysis & churn prediction | Continuous optimization",
        "color": 3,  # green
        "dir": "optimization",
        "files": [
            "opt01_ab_test_manager.json",
            "opt02_ab_test_analyzer.json",
            "opt03_churn_predictor.json",
        ],
    },
]

# Layout constants
X_START = 0
Y_START = 0
WORKFLOW_GAP_X = 400       # horizontal gap between workflows in same department
NODE_SPACING_X = 300       # horizontal spacing between nodes within a workflow
DEPT_GAP_Y = 200           # vertical gap between department rows
STICKY_HEIGHT = 120        # sticky note header height
WORKFLOW_LABEL_HEIGHT = 80 # sub-header for each workflow
MAX_NODES_PER_ROW = 8      # wrap nodes after this many


def load_workflow(dept_dir, filename):
    """Load a workflow JSON file."""
    path = BASE_DIR / "workflows" / dept_dir / filename
    if not path.exists():
        print(f"  WARNING: {path} not found, skipping")
        return None
    with open(path, "r") as f:
        return json.load(f)


def get_workflow_bounds(nodes):
    """Get bounding box of nodes (min_x, min_y, max_x, max_y, width, height)."""
    if not nodes:
        return (0, 0, 0, 0, 0, 0)
    xs = [n["position"][0] for n in nodes]
    ys = [n["position"][1] for n in nodes]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return (min_x, min_y, max_x, max_y, max_x - min_x + 300, max_y - min_y + 200)


def reposition_nodes(nodes, offset_x, offset_y):
    """Shift all nodes by offset, normalizing from their current min position."""
    if not nodes:
        return nodes
    min_x = min(n["position"][0] for n in nodes)
    min_y = min(n["position"][1] for n in nodes)
    for n in nodes:
        n["position"] = [
            n["position"][0] - min_x + offset_x,
            n["position"][1] - min_y + offset_y,
        ]
    return nodes


def remap_node_ids(nodes, connections, prefix):
    """
    Give each node a new unique ID and update all connections accordingly.
    Also prefix node names to avoid collisions across workflows.
    """
    id_map = {}
    name_map = {}

    for node in nodes:
        old_id = node["id"]
        new_id = uid()
        id_map[old_id] = new_id
        node["id"] = new_id

        old_name = node["name"]
        new_name = f"{prefix} | {old_name}"
        name_map[old_name] = new_name
        node["name"] = new_name

    # Rebuild connections with new names
    new_connections = {}
    for src_name, outputs in connections.items():
        new_src = name_map.get(src_name, src_name)
        new_outputs = {}
        for output_key, targets in outputs.items():
            new_targets = []
            for target_list in targets:
                new_target_list = []
                for conn in target_list:
                    new_conn = copy.deepcopy(conn)
                    new_conn["node"] = name_map.get(conn["node"], conn["node"])
                    new_target_list.append(new_conn)
                new_targets.append(new_target_list)
            new_outputs[output_key] = new_targets
        new_connections[new_src] = new_outputs

    return nodes, new_connections


def build_combined_workflow():
    """Build the complete combined overview workflow."""
    all_nodes = []
    all_connections = {}
    current_y = Y_START

    # ── Title Banner ─────────────────────────────────────────────────────────
    all_nodes.append({
        "parameters": {
            "content": (
                "# AVM Autonomous Operations\n"
                "## Complete AI Agent System - AnyVision Media\n\n"
                "**27 autonomous workflows** across **9 departments** | "
                "**250+ nodes** | Orchestrated by Central AI\n\n"
                "Built with: n8n Cloud, Claude Sonnet AI, Airtable, Supabase, "
                "Xero, Gmail, WhatsApp Business API, OpenRouter, SerpAPI, Google Workspace\n\n"
                "---\n"
                "Each section below contains the **full production workflow** for that department agent. "
                "Workflows execute autonomously on schedules or webhooks, with the Central Orchestrator "
                "monitoring health, routing events, and generating reports."
            ),
            "height": 260,
            "width": 1800,
            "color": 5,
        },
        "id": uid(),
        "name": "Title Banner",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [X_START, current_y],
    })
    current_y += 300

    # ── Process Each Department ──────────────────────────────────────────────
    for dept_idx, dept in enumerate(DEPARTMENTS):
        dept_start_y = current_y
        dept_max_height = 0

        # Department header sticky
        all_nodes.append({
            "parameters": {
                "content": (
                    f"## {dept['name']}\n\n"
                    f"{dept['subtitle']}\n\n"
                    f"**{len(dept['files'])} workflows** in this department"
                ),
                "height": STICKY_HEIGHT,
                "width": 1800,
                "color": dept["color"],
            },
            "id": uid(),
            "name": f"Header - {dept['name']}",
            "type": "n8n-nodes-base.stickyNote",
            "typeVersion": 1,
            "position": [X_START, current_y],
        })
        current_y += STICKY_HEIGHT + 30

        # Track x position for placing workflows side by side
        wf_x = X_START
        wf_row_max_height = 0

        for wf_idx, wf_file in enumerate(dept["files"]):
            wf_data = load_workflow(dept["dir"], wf_file)
            if not wf_data:
                continue

            wf_name = wf_data.get("name", wf_file.replace(".json", ""))
            wf_nodes = copy.deepcopy(wf_data.get("nodes", []))
            wf_connections = copy.deepcopy(wf_data.get("connections", {}))

            # Filter out existing sticky notes from sub-workflows
            # (we have our own department headers)
            functional_nodes = [
                n for n in wf_nodes
                if n.get("type") != "n8n-nodes-base.stickyNote"
            ]

            if not functional_nodes:
                continue

            # Create a short prefix from the workflow name
            # e.g. "ORCH-01 Health Monitor" -> "ORCH-01"
            prefix_parts = wf_name.split(" ")
            prefix = prefix_parts[0] if prefix_parts else wf_file[:6]
            # Try to get the workflow code (e.g. ORCH-01, MKT-05, etc.)
            for part in prefix_parts:
                if any(c == "-" for c in part) and any(c.isdigit() for c in part):
                    prefix = part
                    break

            # Remap IDs and names
            functional_nodes, remapped_connections = remap_node_ids(
                functional_nodes, wf_connections, prefix
            )

            # Sub-workflow label sticky
            node_count = len(functional_nodes)
            # Determine trigger type
            trigger_type = "Schedule"
            for n in functional_nodes:
                if "webhook" in n.get("type", "").lower():
                    trigger_type = "Webhook"
                    break

            all_nodes.append({
                "parameters": {
                    "content": (
                        f"### {wf_name}\n"
                        f"**{node_count} nodes** | Trigger: {trigger_type}"
                    ),
                    "height": WORKFLOW_LABEL_HEIGHT,
                    "width": max(node_count * NODE_SPACING_X, 600),
                    "color": dept["color"],
                },
                "id": uid(),
                "name": f"Label - {wf_name}",
                "type": "n8n-nodes-base.stickyNote",
                "typeVersion": 1,
                "position": [wf_x, current_y],
            })

            # Position functional nodes below the label
            node_y = current_y + WORKFLOW_LABEL_HEIGHT + 20
            reposition_nodes(functional_nodes, wf_x + 20, node_y)

            # Get bounds after repositioning
            bounds = get_workflow_bounds(functional_nodes)
            wf_width = bounds[4] + 100
            wf_height = bounds[5] + WORKFLOW_LABEL_HEIGHT + 40

            # Add nodes and connections
            all_nodes.extend(functional_nodes)
            all_connections.update(remapped_connections)

            # Track row height
            if wf_height > wf_row_max_height:
                wf_row_max_height = wf_height

            # Move x for next workflow — check if we should wrap
            wf_x += max(wf_width, 600) + WORKFLOW_GAP_X

            # Wrap to next row if too wide (> 5000px)
            if wf_x > 5000 and wf_idx < len(dept["files"]) - 1:
                current_y += wf_row_max_height + 60
                wf_x = X_START
                wf_row_max_height = 0

        current_y += wf_row_max_height + DEPT_GAP_Y

    # ── Integration Footer ───────────────────────────────────────────────────
    all_nodes.append({
        "parameters": {
            "content": (
                "## INTEGRATION LAYER\n\n"
                "| Service | Purpose |\n"
                "|---------|--------|\n"
                "| **n8n Cloud** | Workflow orchestration & execution |\n"
                "| **Airtable** | CRM, content calendar, tickets, KPIs |\n"
                "| **Supabase** | Client portal, auth, real-time data |\n"
                "| **Xero** | Invoicing, payments, P&L, cash flow |\n"
                "| **Gmail** | Email delivery, alerts, reports |\n"
                "| **WhatsApp Business** | Client communication & AI chat |\n"
                "| **OpenRouter / Claude** | AI reasoning across all agents |\n"
                "| **Google Workspace** | Slides, Sheets, Calendar, Drive |\n"
                "| **SerpAPI** | SEO keyword & SERP tracking |\n"
            ),
            "height": 380,
            "width": 800,
            "color": 2,
        },
        "id": uid(),
        "name": "Integration Layer",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [X_START, current_y],
    })

    # Stats banner
    total_functional = sum(
        1 for n in all_nodes
        if n.get("type") != "n8n-nodes-base.stickyNote"
    )
    total_sticky = sum(
        1 for n in all_nodes
        if n.get("type") == "n8n-nodes-base.stickyNote"
    )

    all_nodes.append({
        "parameters": {
            "content": (
                "## SYSTEM STATISTICS\n\n"
                f"- **{total_functional} functional nodes** across 27 workflows\n"
                f"- **{total_sticky} section headers** organizing 9 departments\n"
                f"- **{len(all_connections)} node connections** defining execution flow\n"
                "- **7 AI-powered agents** + 1 Central Orchestrator\n"
                "- **6 integration platforms** connected\n"
                "- **Fully autonomous** with human escalation for critical decisions\n\n"
                "*Built by AnyVision Media using the WAT Framework*\n"
                "*(Workflows, Agents, Tools)*"
            ),
            "height": 340,
            "width": 800,
            "color": 5,
        },
        "id": uid(),
        "name": "Stats Banner",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [900, current_y],
    })

    # Build final workflow
    workflow = {
        "name": "AVM Autonomous Operations - Complete System Overview",
        "nodes": all_nodes,
        "connections": all_connections,
        "settings": {
            "executionOrder": "v1",
            "timezone": "Africa/Johannesburg",
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
        },
    }

    return workflow


def save_workflow(workflow, path):
    """Save workflow JSON to file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(workflow, f, indent=2)
    return path


def deploy_workflow(workflow):
    """Create new workflow in n8n."""
    import httpx
    client = httpx.Client(timeout=30, headers={"X-N8N-API-KEY": N8N_API_KEY})
    r = client.post(
        f"{N8N_BASE_URL}/api/v1/workflows",
        json=workflow,
    )
    if r.status_code in (200, 201):
        wf_id = r.json().get("id", "")
        # Move to AVM project
        client.put(
            f"{N8N_BASE_URL}/api/v1/workflows/{wf_id}/transfer",
            json={"destinationProjectId": AVM_PROJECT_ID},
        )
        return wf_id
    else:
        print(f"Deploy error: {r.status_code} {r.text[:200]}")
        return None


def update_workflow(workflow, workflow_id):
    """Update existing workflow in n8n."""
    import httpx
    client = httpx.Client(timeout=30, headers={"X-N8N-API-KEY": N8N_API_KEY})
    r = client.put(
        f"{N8N_BASE_URL}/api/v1/workflows/{workflow_id}",
        json=workflow,
    )
    if r.status_code == 200:
        return workflow_id
    else:
        print(f"Update error: {r.status_code} {r.text[:300]}")
        return None


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "build"

    print("=" * 70)
    print("AVM AUTONOMOUS OPERATIONS - COMBINED OVERVIEW BUILDER")
    print("=" * 70)
    print()

    print("Building combined overview with all workflow nodes...")
    workflow = build_combined_workflow()

    total_nodes = len(workflow["nodes"])
    functional = sum(1 for n in workflow["nodes"] if n["type"] != "n8n-nodes-base.stickyNote")
    sticky = total_nodes - functional
    connections = len(workflow["connections"])

    print(f"  Total nodes:      {total_nodes}")
    print(f"  Functional nodes: {functional}")
    print(f"  Sticky notes:     {sticky}")
    print(f"  Connections:      {connections}")
    print()

    # Save JSON
    out_path = str(BASE_DIR / "workflows" / "avm_overview_complete_system.json")
    save_workflow(workflow, out_path)
    print(f"  Saved to: {out_path}")

    if action == "deploy":
        print("\nDeploying to n8n (inactive)...")
        wf_id = deploy_workflow(workflow)
        if wf_id:
            print(f"  Deployed as: {wf_id}")
            print(f"  Moved to AVM project")
        else:
            print("  Deploy failed!")

    elif action == "update":
        print(f"\nUpdating existing overview ({EXISTING_OVERVIEW_ID})...")
        wf_id = update_workflow(workflow, EXISTING_OVERVIEW_ID)
        if wf_id:
            print(f"  Updated: {wf_id}")
        else:
            print("  Update failed!")

    print("\nDone.")


if __name__ == "__main__":
    main()

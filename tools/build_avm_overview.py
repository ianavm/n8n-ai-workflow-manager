"""
AVM Autonomous Operations - Complete System Overview Builder

Builds a visual-only n8n workflow that serves as a client-facing demo map
of the entire AVM autonomous operations architecture. Uses sticky notes
and NoOp (placeholder) nodes to show the system layout.

NOT a functional workflow -- purely a visual overview for presentations.

Usage:
    python tools/build_avm_overview.py build     # Build JSON
    python tools/build_avm_overview.py deploy     # Build + Deploy (inactive)
"""

import json
import sys
import uuid
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")

WORKFLOW_NAME = "AVM Autonomous Operations - Complete System Overview"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows"


def uid():
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════
# LAYOUT CONSTANTS
# ══════════════════════════════════════════════════════════════

# Horizontal spacing between nodes in a group
NODE_GAP_X = 260
# Vertical row positions
ROW_0 = 0       # Orchestrator
ROW_1 = 480     # Existing Departments
ROW_2 = 960     # New Departments
ROW_3 = 1480    # Intelligence & Optimization
ROW_4 = 1980    # Integration Layer

# Column starting positions for groups
COL_START = 0
COL_GROUP_GAP = 900  # horizontal gap between department groups

# Sticky note dimensions
STICKY_W_SMALL = 560
STICKY_W_MEDIUM = 700
STICKY_W_LARGE = 1100
STICKY_W_FULL = 3600
STICKY_H_HEADER = 280
STICKY_H_DEPT = 320
STICKY_H_FOOTER = 260

# Sticky note colors: 1=yellow, 2=blue, 3=green, 4=purple, 5=orange, 6=red, 7=gray
COLOR_YELLOW = 1
COLOR_BLUE = 2
COLOR_GREEN = 3
COLOR_PURPLE = 4
COLOR_ORANGE = 5
COLOR_RED = 6
COLOR_GRAY = 7


# ══════════════════════════════════════════════════════════════
# NODE BUILDERS
# ══════════════════════════════════════════════════════════════

def make_sticky(name, content, x, y, width, height, color):
    """Create a sticky note node."""
    return {
        "parameters": {
            "content": content,
            "height": height,
            "width": width,
            "color": color
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [x, y]
    }


def make_noop(name, x, y, notes):
    """Create a NoOp placeholder node with notes displayed in flow."""
    return {
        "parameters": {},
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [x, y],
        "notes": notes,
        "notesInFlow": True
    }


def connect(source_name, target_name):
    """Create a connection dict entry (source -> target, output 0 -> input 0)."""
    return (source_name, target_name)


# ══════════════════════════════════════════════════════════════
# BUILD ALL NODES
# ══════════════════════════════════════════════════════════════

def build_nodes_and_connections():
    nodes = []
    connections_list = []

    # ──────────────────────────────────────────────
    # TITLE BANNER (above everything)
    # ──────────────────────────────────────────────
    nodes.append(make_sticky(
        "Sticky Note - Title Banner",
        (
            "# AVM Autonomous Operations\n"
            "## Complete System Overview\n\n"
            "**AnyVision Media** -- Fully autonomous AI-powered business operations.\n"
            "6 department agents coordinated by a central orchestrator.\n"
            "27 specialized workflows across marketing, finance, content, "
            "client relations, support, and WhatsApp.\n\n"
            "_This is a visual architecture map. Each node represents a production workflow._"
        ),
        COL_START - 50, ROW_0 - 300, STICKY_W_FULL, 220, COLOR_YELLOW
    ))

    # ──────────────────────────────────────────────
    # ROW 0: CENTRAL ORCHESTRATOR
    # ──────────────────────────────────────────────
    orch_x = COL_START + 600
    orch_y = ROW_0

    nodes.append(make_sticky(
        "Sticky Note - Orchestrator",
        (
            "## CENTRAL ORCHESTRATOR\n\n"
            "The brain of the system. Coordinates all 6 department agents.\n"
            "Monitors health, routes cross-department events, aggregates KPIs,\n"
            "and generates weekly executive reports.\n\n"
            "**Trigger:** Cron (15min) + Webhook + Daily/Weekly schedules"
        ),
        orch_x - 80, orch_y - 60, STICKY_W_LARGE, STICKY_H_HEADER + 40, COLOR_YELLOW
    ))

    orch_nodes = []

    n = make_noop("ORCH-01: Health Monitor", orch_x, orch_y + 80,
                  "Polls all agent workflows every 15 min.\n"
                  "Computes health scores (0-100).\n"
                  "Auto-retries failed workflows.\n"
                  "Escalates persistent failures via email.")
    nodes.append(n); orch_nodes.append(n)

    n = make_noop("ORCH-02: Cross-Dept Router", orch_x + NODE_GAP_X, orch_y + 80,
                  "Central event bus (webhook).\n"
                  "Routes events between departments.\n"
                  "Handles: lead_qualified, invoice_paid,\n"
                  "content_published, support_escalated.")
    nodes.append(n); orch_nodes.append(n)

    n = make_noop("ORCH-03: KPI Aggregation", orch_x + NODE_GAP_X * 2, orch_y + 80,
                  "Daily 06:00 SAST aggregation.\n"
                  "Pulls metrics from all departments.\n"
                  "Detects anomalies vs 7-day baseline.\n"
                  "Stores snapshots in Airtable.")
    nodes.append(n); orch_nodes.append(n)

    n = make_noop("ORCH-04: Weekly Report", orch_x + NODE_GAP_X * 3, orch_y + 80,
                  "Monday 07:00 SAST.\n"
                  "Claude generates executive summary.\n"
                  "Includes all KPIs, trends, recommendations.\n"
                  "Delivers via Gmail to stakeholders.")
    nodes.append(n); orch_nodes.append(n)

    # Chain orchestrator nodes
    for i in range(len(orch_nodes) - 1):
        connections_list.append(connect(orch_nodes[i]["name"], orch_nodes[i+1]["name"]))

    # ──────────────────────────────────────────────
    # ROW 1: EXISTING DEPARTMENT AGENTS (Enhanced)
    # ──────────────────────────────────────────────

    # --- MARKETING AGENT ---
    mkt_x = COL_START
    mkt_y = ROW_1

    nodes.append(make_sticky(
        "Sticky Note - Marketing",
        (
            "## MARKETING AGENT\n\n"
            "4 core workflows (MKT 01-04) + 2 new enhancements.\n"
            "Pipeline: Intelligence -> Strategy -> Content -> Distribution.\n"
            "AI budget: 50k Claude tokens/day via OpenRouter.\n\n"
            "**Existing:** MKT-01 Intelligence, MKT-02 Strategy,\n"
            "MKT-03 Content, MKT-04 Distribution"
        ),
        mkt_x - 50, mkt_y - 60, STICKY_W_MEDIUM, STICKY_H_DEPT + 40, COLOR_BLUE
    ))

    mkt_nodes = []

    n = make_noop("MKT-05: ROI Tracker", mkt_x, mkt_y + 120,
                  "Tracks ROI per campaign/channel.\n"
                  "Correlates spend -> leads -> conversions.\n"
                  "Calculates ROAS and CPA.\n"
                  "Feeds data to Budget Optimizer.")
    nodes.append(n); mkt_nodes.append(n)

    n = make_noop("MKT-06: Budget Optimizer", mkt_x + NODE_GAP_X, mkt_y + 120,
                  "AI-driven budget allocation.\n"
                  "Shifts spend to best-performing channels.\n"
                  "Respects minimum spend floors.\n"
                  "Weekly rebalancing cycle.")
    nodes.append(n); mkt_nodes.append(n)

    connections_list.append(connect(mkt_nodes[0]["name"], mkt_nodes[1]["name"]))

    # --- FINANCE AGENT ---
    fin_x = COL_START + COL_GROUP_GAP
    fin_y = ROW_1

    nodes.append(make_sticky(
        "Sticky Note - Finance",
        (
            "## FINANCE AGENT\n\n"
            "7 core workflows (WF 01-07) via Xero integration + 2 new.\n"
            "Full AP/AR: invoicing, collections, payments, reconciliation.\n"
            "Auto-approve bills < R10,000. Escalate > R50,000.\n\n"
            "**Existing:** WF-01 to WF-07 (Invoicing through Exceptions)"
        ),
        fin_x - 50, fin_y - 60, STICKY_W_MEDIUM, STICKY_H_DEPT + 40, COLOR_GREEN
    ))

    fin_nodes = []

    n = make_noop("FIN-08: Cash Flow Forecast", fin_x, fin_y + 120,
                  "14-day rolling cash flow projection.\n"
                  "Pulls from Xero AR/AP aging reports.\n"
                  "AI-enhanced prediction model.\n"
                  "Alerts on projected shortfalls.")
    nodes.append(n); fin_nodes.append(n)

    n = make_noop("FIN-09: Anomaly Detector", fin_x + NODE_GAP_X, fin_y + 120,
                  "Flags unusual transactions in Xero.\n"
                  "Detects: duplicate invoices, unusual amounts,\n"
                  "off-schedule payments, new vendor spikes.\n"
                  "Auto-creates review tasks.")
    nodes.append(n); fin_nodes.append(n)

    connections_list.append(connect(fin_nodes[0]["name"], fin_nodes[1]["name"]))

    # --- CONTENT AGENT ---
    cnt_x = COL_START + COL_GROUP_GAP * 2
    cnt_y = ROW_1

    nodes.append(make_sticky(
        "Sticky Note - Content",
        (
            "## CONTENT AGENT\n\n"
            "SEO + Social Growth Engine (8 workflows WF05-WF11 + scoring).\n"
            "Trend discovery, content production, multi-platform publishing.\n"
            "SerpAPI + Google PageSpeed + Blotato (9 platforms).\n\n"
            "**Existing:** Trend Discovery, SEO Content, Publishing,\n"
            "Engagement, Lead Capture, SEO Maintenance, Analytics"
        ),
        cnt_x - 50, cnt_y - 60, STICKY_W_MEDIUM, STICKY_H_DEPT + 40, COLOR_PURPLE
    ))

    cnt_nodes = []

    n = make_noop("CONTENT-01: Feedback Loop", cnt_x, cnt_y + 120,
                  "Analyzes published content performance.\n"
                  "Feeds engagement data back to strategy.\n"
                  "Auto-adjusts content calendar priorities.\n"
                  "Learns what topics/formats perform best.")
    nodes.append(n); cnt_nodes.append(n)

    n = make_noop("CONTENT-02: Multi-Format Gen", cnt_x + NODE_GAP_X, cnt_y + 120,
                  "Takes approved content briefs.\n"
                  "Generates: blog, social posts, video scripts,\n"
                  "infographics, email newsletters.\n"
                  "One topic -> 5+ format variations.")
    nodes.append(n); cnt_nodes.append(n)

    connections_list.append(connect(cnt_nodes[0]["name"], cnt_nodes[1]["name"]))

    # ──────────────────────────────────────────────
    # ROW 2: NEW DEPARTMENT AGENTS
    # ──────────────────────────────────────────────

    # --- CLIENT RELATIONS ---
    cr_x = COL_START
    cr_y = ROW_2

    nodes.append(make_sticky(
        "Sticky Note - Client Relations",
        (
            "## CLIENT RELATIONS AGENT\n\n"
            "Proactive client health management.\n"
            "Automated onboarding sequences, renewal tracking,\n"
            "satisfaction monitoring, and churn prevention.\n\n"
            "**Integrations:** Airtable CRM, Gmail, Supabase Portal"
        ),
        cr_x - 50, cr_y - 60, STICKY_W_LARGE, STICKY_H_DEPT + 20, COLOR_ORANGE
    ))

    cr_nodes = []

    n = make_noop("CR-01: Health Scorer", cr_x, cr_y + 100,
                  "Weekly client health scoring.\n"
                  "Inputs: engagement, payments, support tickets,\n"
                  "response times, portal activity.\n"
                  "Score: 0-100 with risk classification.")
    nodes.append(n); cr_nodes.append(n)

    n = make_noop("CR-02: Renewal Manager", cr_x + NODE_GAP_X, cr_y + 100,
                  "Tracks contract renewal dates.\n"
                  "60/30/14-day automated reminders.\n"
                  "Generates renewal proposals.\n"
                  "Escalates at-risk renewals to Ian.")
    nodes.append(n); cr_nodes.append(n)

    n = make_noop("CR-03: Onboarding", cr_x + NODE_GAP_X * 2, cr_y + 100,
                  "Automated 14-day onboarding sequence.\n"
                  "Welcome email -> Portal setup -> Kickoff agenda\n"
                  "-> Progress check -> 14-day review.\n"
                  "Creates all Airtable/Supabase records.")
    nodes.append(n); cr_nodes.append(n)

    n = make_noop("CR-04: Satisfaction Pulse", cr_x + NODE_GAP_X * 3, cr_y + 100,
                  "Monthly NPS/CSAT surveys via email.\n"
                  "AI sentiment analysis on responses.\n"
                  "Auto-creates follow-up tasks for low scores.\n"
                  "Tracks satisfaction trends over time.")
    nodes.append(n); cr_nodes.append(n)

    for i in range(len(cr_nodes) - 1):
        connections_list.append(connect(cr_nodes[i]["name"], cr_nodes[i+1]["name"]))

    # --- SUPPORT AGENT ---
    sup_x = COL_START + COL_GROUP_GAP + 300
    sup_y = ROW_2

    nodes.append(make_sticky(
        "Sticky Note - Support",
        (
            "## SUPPORT AGENT\n\n"
            "AI-powered support ticket lifecycle management.\n"
            "Auto-resolves common issues, monitors SLAs,\n"
            "builds knowledge base from resolved tickets.\n\n"
            "**Integrations:** Gmail, Airtable, Claude AI, Portal"
        ),
        sup_x - 50, sup_y - 60, STICKY_W_LARGE, STICKY_H_DEPT + 20, COLOR_RED
    ))

    sup_nodes = []

    n = make_noop("SUP-01: Ticket Creator", sup_x, sup_y + 100,
                  "Ingests from: email, portal, WhatsApp.\n"
                  "AI classifies: category, priority, complexity.\n"
                  "Creates structured ticket in Airtable.\n"
                  "Sends acknowledgment to client.")
    nodes.append(n); sup_nodes.append(n)

    n = make_noop("SUP-02: SLA Monitor", sup_x + NODE_GAP_X, sup_y + 100,
                  "Monitors response & resolution SLAs.\n"
                  "Priority-based: P1=1hr, P2=4hr, P3=24hr.\n"
                  "Escalates breaches automatically.\n"
                  "Tracks SLA compliance percentage.")
    nodes.append(n); sup_nodes.append(n)

    n = make_noop("SUP-03: Auto-Resolver", sup_x + NODE_GAP_X * 2, sup_y + 100,
                  "AI attempts resolution for common issues.\n"
                  "Matches against knowledge base patterns.\n"
                  "Auto-replies with solutions (confidence > 85%).\n"
                  "Escalates uncertain cases to human.")
    nodes.append(n); sup_nodes.append(n)

    n = make_noop("SUP-04: KB Builder", sup_x + NODE_GAP_X * 3, sup_y + 100,
                  "Extracts solutions from resolved tickets.\n"
                  "AI summarizes into knowledge base articles.\n"
                  "Deduplicates and categorizes entries.\n"
                  "Improves Auto-Resolver accuracy over time.")
    nodes.append(n); sup_nodes.append(n)

    for i in range(len(sup_nodes) - 1):
        connections_list.append(connect(sup_nodes[i]["name"], sup_nodes[i+1]["name"]))

    # --- WHATSAPP AGENT ---
    wa_x = COL_START + COL_GROUP_GAP * 2 + 600
    wa_y = ROW_2

    nodes.append(make_sticky(
        "Sticky Note - WhatsApp",
        (
            "## WHATSAPP AGENT\n\n"
            "Enhances existing 36-node WhatsApp system.\n"
            "AI conversation analysis, CRM synchronization,\n"
            "and proactive issue detection.\n\n"
            "**Integrations:** WhatsApp Business API, Airtable, GPT-4o"
        ),
        wa_x - 50, wa_y - 60, STICKY_W_MEDIUM, STICKY_H_DEPT + 20, COLOR_GRAY
    ))

    wa_nodes = []

    n = make_noop("WA-01: Conversation Analyzer", wa_x, wa_y + 100,
                  "AI analyzes WhatsApp conversations.\n"
                  "Detects: sentiment shifts, buying signals,\n"
                  "complaints, urgent requests.\n"
                  "Tags conversations for follow-up.")
    nodes.append(n); wa_nodes.append(n)

    n = make_noop("WA-02: CRM Sync", wa_x + NODE_GAP_X, wa_y + 100,
                  "Syncs WhatsApp interactions to Airtable CRM.\n"
                  "Updates contact records, activity logs.\n"
                  "Links conversations to deals/projects.\n"
                  "Maintains unified client timeline.")
    nodes.append(n); wa_nodes.append(n)

    n = make_noop("WA-03: Issue Detector", wa_x + NODE_GAP_X * 2, wa_y + 100,
                  "Monitors for service issues in messages.\n"
                  "Auto-creates support tickets from complaints.\n"
                  "Detects delivery failures, broken links.\n"
                  "Alerts team to urgent client issues.")
    nodes.append(n); wa_nodes.append(n)

    for i in range(len(wa_nodes) - 1):
        connections_list.append(connect(wa_nodes[i]["name"], wa_nodes[i+1]["name"]))

    # ──────────────────────────────────────────────
    # ROW 3: INTELLIGENCE & OPTIMIZATION
    # ──────────────────────────────────────────────

    # --- INTELLIGENCE LAYER ---
    intel_x = COL_START
    intel_y = ROW_3

    nodes.append(make_sticky(
        "Sticky Note - Intelligence",
        (
            "## INTELLIGENCE LAYER\n\n"
            "Cross-department insights and executive reporting.\n"
            "Correlates data across all agents to find patterns.\n"
            "Tracks AI prompt performance and system efficiency.\n\n"
            "**AI Engine:** Claude Sonnet via OpenRouter"
        ),
        intel_x - 50, intel_y - 60, STICKY_W_LARGE, STICKY_H_DEPT, COLOR_YELLOW
    ))

    intel_nodes = []

    n = make_noop("INTEL-01: Cross-Dept Correlator", intel_x, intel_y + 100,
                  "Finds patterns across departments.\n"
                  "Example: marketing spend -> support volume.\n"
                  "Detects: seasonal trends, bottlenecks,\n"
                  "resource conflicts, optimization opportunities.")
    nodes.append(n); intel_nodes.append(n)

    n = make_noop("INTEL-02: Executive Report", intel_x + NODE_GAP_X, intel_y + 100,
                  "Monthly executive intelligence brief.\n"
                  "AI-generated insights and recommendations.\n"
                  "Delivered via Google Slides + email.\n"
                  "Includes charts, trends, action items.")
    nodes.append(n); intel_nodes.append(n)

    n = make_noop("INTEL-03: Prompt Tracker", intel_x + NODE_GAP_X * 2, intel_y + 100,
                  "Monitors AI prompt performance.\n"
                  "Tracks: token usage, response quality,\n"
                  "latency, cost per department.\n"
                  "Identifies prompts needing optimization.")
    nodes.append(n); intel_nodes.append(n)

    for i in range(len(intel_nodes) - 1):
        connections_list.append(connect(intel_nodes[i]["name"], intel_nodes[i+1]["name"]))

    # --- SELF-IMPROVEMENT ---
    opt_x = COL_START + COL_GROUP_GAP + 600
    opt_y = ROW_3

    nodes.append(make_sticky(
        "Sticky Note - Optimization",
        (
            "## SELF-IMPROVEMENT ENGINE\n\n"
            "The system that makes the system better.\n"
            "A/B tests workflow variations, analyzes results,\n"
            "and predicts potential issues before they happen.\n\n"
            "**Goal:** Continuous autonomous optimization"
        ),
        opt_x - 50, opt_y - 60, STICKY_W_LARGE, STICKY_H_DEPT, COLOR_GREEN
    ))

    opt_nodes = []

    n = make_noop("OPT-01: A/B Test Manager", opt_x, opt_y + 100,
                  "Creates workflow variant experiments.\n"
                  "Splits traffic between A and B versions.\n"
                  "Tracks: completion rate, accuracy, speed.\n"
                  "Runs tests for configurable duration.")
    nodes.append(n); opt_nodes.append(n)

    n = make_noop("OPT-02: Test Analyzer", opt_x + NODE_GAP_X, opt_y + 100,
                  "Statistical analysis of A/B results.\n"
                  "Determines winners with confidence intervals.\n"
                  "Auto-promotes winning variants.\n"
                  "Archives test history for learning.")
    nodes.append(n); opt_nodes.append(n)

    n = make_noop("OPT-03: Churn Predictor", opt_x + NODE_GAP_X * 2, opt_y + 100,
                  "ML-style churn risk prediction.\n"
                  "Inputs: engagement decline, payment delays,\n"
                  "support frequency, portal inactivity.\n"
                  "Triggers proactive retention workflows.")
    nodes.append(n); opt_nodes.append(n)

    for i in range(len(opt_nodes) - 1):
        connections_list.append(connect(opt_nodes[i]["name"], opt_nodes[i+1]["name"]))

    # ──────────────────────────────────────────────
    # ROW 4: INTEGRATION LAYER
    # ──────────────────────────────────────────────
    int_x = COL_START - 50
    int_y = ROW_4

    nodes.append(make_sticky(
        "Sticky Note - Integrations",
        (
            "## INTEGRATION LAYER\n\n"
            "| Service | Role |\n"
            "| --- | --- |\n"
            "| **n8n Cloud** | Workflow orchestration engine |\n"
            "| **Airtable** | CRM, project management, data store |\n"
            "| **Supabase** | Client portal DB, auth, real-time |\n"
            "| **Xero** | Accounting, invoicing, payments (ZAR) |\n"
            "| **Gmail** | Email delivery, notifications, reports |\n"
            "| **WhatsApp Business** | Client messaging, support channel |\n"
            "| **OpenRouter / Claude** | AI reasoning, content generation |\n"
            "| **Google Workspace** | Slides, Sheets, Calendar, Drive |\n"
            "| **SerpAPI** | SEO rank tracking, SERP analysis |\n"
            "| **Blotato** | Multi-platform social publishing (9 platforms) |\n\n"
            "_All integrations use OAuth2 or API key authentication managed in n8n._"
        ),
        int_x, int_y - 60, STICKY_W_FULL, STICKY_H_FOOTER + 160, COLOR_BLUE
    ))

    # ──────────────────────────────────────────────
    # STATS BANNER (bottom)
    # ──────────────────────────────────────────────
    nodes.append(make_sticky(
        "Sticky Note - Stats",
        (
            "## System Statistics\n\n"
            "**27 autonomous workflows** across 6 departments  |  "
            "**4 orchestrator workflows** for coordination  |  "
            "**10+ integrations** connected  |  "
            "**24/7 operation** with health monitoring\n\n"
            "**AI Models:** Claude Sonnet (reasoning/content) + GPT-4o (conversation)  |  "
            "**Data:** Airtable + Supabase (PostgreSQL)  |  "
            "**Currency:** ZAR (South African Rand)  |  "
            "**Owner:** AnyVision Media (ian@anyvisionmedia.com)"
        ),
        int_x, int_y + STICKY_H_FOOTER + 140, STICKY_W_FULL, 180, COLOR_PURPLE
    ))

    # ──────────────────────────────────────────────
    # ORCHESTRATOR -> DEPARTMENT CONNECTIONS
    # ──────────────────────────────────────────────

    # ORCH-01 (Health Monitor) connects down to first node of each department
    orch_health = "ORCH-01: Health Monitor"
    orch_router = "ORCH-02: Cross-Dept Router"

    # Health monitor fans out to all departments
    connections_list.append(connect(orch_health, mkt_nodes[0]["name"]))
    connections_list.append(connect(orch_health, fin_nodes[0]["name"]))
    connections_list.append(connect(orch_health, cnt_nodes[0]["name"]))
    connections_list.append(connect(orch_health, cr_nodes[0]["name"]))
    connections_list.append(connect(orch_health, sup_nodes[0]["name"]))
    connections_list.append(connect(orch_health, wa_nodes[0]["name"]))

    # Cross-dept router also connects to departments
    connections_list.append(connect(orch_router, mkt_nodes[0]["name"]))
    connections_list.append(connect(orch_router, fin_nodes[0]["name"]))
    connections_list.append(connect(orch_router, cnt_nodes[0]["name"]))
    connections_list.append(connect(orch_router, cr_nodes[0]["name"]))
    connections_list.append(connect(orch_router, sup_nodes[0]["name"]))
    connections_list.append(connect(orch_router, wa_nodes[0]["name"]))

    # Intelligence connects back up to orchestrator KPI
    connections_list.append(connect(intel_nodes[0]["name"], "ORCH-03: KPI Aggregation"))
    connections_list.append(connect(intel_nodes[1]["name"], "ORCH-04: Weekly Report"))

    # Optimization connects to intelligence
    connections_list.append(connect(opt_nodes[2]["name"], cr_nodes[0]["name"]))

    return nodes, connections_list


# ══════════════════════════════════════════════════════════════
# BUILD WORKFLOW JSON
# ══════════════════════════════════════════════════════════════

def build_workflow_json():
    """Build the complete n8n workflow JSON."""
    nodes, connections_list = build_nodes_and_connections()

    # Build n8n connections format
    # n8n expects: { "NodeName": { "main": [[{"node": "TargetName", "type": "main", "index": 0}]] } }
    connections = {}
    for source, target in connections_list:
        if source not in connections:
            connections[source] = {"main": [[]]}
        connections[source]["main"][0].append({
            "node": target,
            "type": "main",
            "index": 0
        })

    workflow = {
        "name": WORKFLOW_NAME,
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1"
        },
        "tags": [
            {"name": "overview"},
            {"name": "demo"},
            {"name": "architecture"}
        ],
        "meta": {
            "instanceId": "avm-overview",
            "templateCredsSetupCompleted": True
        }
    }

    return workflow


# ══════════════════════════════════════════════════════════════
# SAVE & DEPLOY
# ══════════════════════════════════════════════════════════════

def save_workflow(workflow_json):
    """Save workflow JSON to file."""
    output_path = OUTPUT_DIR / "avm_overview_complete_system.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_json, f, indent=2, ensure_ascii=False)

    node_count = len(workflow_json["nodes"])
    sticky_count = sum(1 for n in workflow_json["nodes"] if "stickyNote" in n["type"])
    noop_count = sum(1 for n in workflow_json["nodes"] if "noOp" in n["type"])
    conn_count = sum(
        len(targets)
        for src in workflow_json["connections"].values()
        for targets in src["main"]
    )

    print(f"  Saved: {output_path}")
    print(f"  Nodes: {node_count} total ({sticky_count} sticky notes, {noop_count} NoOp nodes)")
    print(f"  Connections: {conn_count}")
    return output_path


def deploy_workflow(workflow_json):
    """Deploy workflow to n8n Cloud (inactive)."""
    import httpx

    if not N8N_API_KEY:
        print("  ERROR: N8N_API_KEY not set in .env")
        return None

    url = f"{N8N_BASE_URL}/api/v1/workflows"
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }

    # Remove tags for API (n8n API creates tags differently)
    payload = dict(workflow_json)
    payload.pop("tags", None)
    payload.pop("meta", None)

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        wf_id = data.get("id", "unknown")
        print(f"  Deployed to n8n -> Workflow ID: {wf_id}")
        print(f"  URL: {N8N_BASE_URL}/workflow/{wf_id}")
        return wf_id
    except httpx.HTTPStatusError as e:
        print(f"  Deploy FAILED: {e.response.status_code} - {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"  Deploy FAILED: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("AVM Autonomous Operations - System Overview Builder")
        print()
        print("Usage:")
        print("  python tools/build_avm_overview.py build     # Build JSON file")
        print("  python tools/build_avm_overview.py deploy    # Build + Deploy to n8n (inactive)")
        print()
        print(f"Output: workflows/avm_overview_complete_system.json")
        sys.exit(0)

    action = sys.argv[1].lower()

    print("=" * 60)
    print("AVM AUTONOMOUS OPERATIONS - SYSTEM OVERVIEW BUILDER")
    print("=" * 60)
    print()

    # Build
    print("Building visual overview workflow...")
    print("-" * 40)
    wf_json = build_workflow_json()
    output_path = save_workflow(wf_json)
    print()

    if action == "deploy":
        print("Deploying to n8n Cloud (inactive)...")
        print("-" * 40)
        wf_id = deploy_workflow(wf_json)
        if wf_id:
            print()
            print(f"Overview workflow deployed successfully.")
            print(f"Open in n8n: {N8N_BASE_URL}/workflow/{wf_id}")
    elif action == "build":
        print(f"Build complete. Open in n8n by importing:")
        print(f"  {output_path}")
    else:
        print(f"Unknown action: {action}")
        print("Valid: build, deploy")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
AVM Autonomous Operations - Orchestrator Airtable Setup

Creates the Operations Control Airtable base with 5 core tables for the
Central Orchestrator agent system. Seeds Agent_Registry with all 7 department agents.

Tables:
    1. Agent_Registry      - Agent catalog, health scores, workflow mappings
    2. Orchestrator_Events  - Central event bus for cross-department routing
    3. KPI_Snapshots        - Daily metrics per agent
    4. Escalation_Queue     - Human escalation with severity/category
    5. Decision_Log         - Audit trail of autonomous AI decisions

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. ORCH_AIRTABLE_BASE_ID set in .env (create a blank base first in Airtable UI)

Usage:
    python tools/setup_orchestrator_airtable.py              # Create all tables
    python tools/setup_orchestrator_airtable.py --seed        # Create tables + seed agents
"""

import os
import sys
import json
import httpx
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# -- Configuration --
ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# -- Status choices reused across tables --
AGENT_STATUS_CHOICES = [
    {"name": "Active", "color": "greenBright"},
    {"name": "Degraded", "color": "yellowBright"},
    {"name": "Down", "color": "redBright"},
    {"name": "Maintenance", "color": "grayBright"},
]

PRIORITY_CHOICES = [
    {"name": "Critical", "color": "redBright"},
    {"name": "High", "color": "orangeBright"},
    {"name": "Medium", "color": "yellowBright"},
    {"name": "Low", "color": "blueBright"},
]

SEVERITY_CHOICES = [
    {"name": "P1", "color": "redBright"},
    {"name": "P2", "color": "orangeBright"},
    {"name": "P3", "color": "yellowBright"},
    {"name": "P4", "color": "blueBright"},
]

# -- Table Definitions --

TABLE_DEFINITIONS = {
    "Agent Registry": {
        "description": "Catalog of all AI agents with health scores, status, and workflow mappings",
        "primary_field": "Agent Name",
        "fields": [
            {"name": "Agent ID", "type": "singleLineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {"choices": AGENT_STATUS_CHOICES},
            },
            {"name": "Health Score", "type": "number", "options": {"precision": 0}},
            {"name": "Last Heartbeat", "type": "dateTime", "options": {"timeZone": "Africa/Johannesburg", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
            {"name": "Workflow IDs", "type": "multilineText"},
            {"name": "KPIs", "type": "multilineText"},
            {"name": "Config", "type": "multilineText"},
            {
                "name": "Department",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Marketing", "color": "blueBright"},
                        {"name": "Finance", "color": "greenBright"},
                        {"name": "Content", "color": "purpleBright"},
                        {"name": "Client Relations", "color": "orangeBright"},
                        {"name": "Customer Support", "color": "yellowBright"},
                        {"name": "WhatsApp", "color": "cyanBright"},
                        {"name": "Orchestrator", "color": "redBright"},
                    ]
                },
            },
            {"name": "Description", "type": "multilineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Orchestrator Events": {
        "description": "Central event bus for cross-department coordination and routing",
        "primary_field": "Event ID",
        "fields": [
            {
                "name": "Event Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "health_check", "color": "greenBright"},
                        {"name": "alert", "color": "redBright"},
                        {"name": "escalation", "color": "orangeBright"},
                        {"name": "cross_dept", "color": "blueBright"},
                        {"name": "kpi_update", "color": "purpleBright"},
                        {"name": "decision", "color": "yellowBright"},
                        {"name": "lead_qualified", "color": "cyanBright"},
                        {"name": "invoice_created", "color": "greenDark1"},
                        {"name": "content_published", "color": "blueDark1"},
                        {"name": "support_ticket", "color": "redDark1"},
                    ]
                },
            },
            {"name": "Source Agent", "type": "singleLineText"},
            {"name": "Target Agent", "type": "singleLineText"},
            {
                "name": "Priority",
                "type": "singleSelect",
                "options": {"choices": PRIORITY_CHOICES},
            },
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Pending", "color": "yellowBright"},
                        {"name": "In Progress", "color": "blueBright"},
                        {"name": "Resolved", "color": "greenBright"},
                        {"name": "Escalated", "color": "redBright"},
                    ]
                },
            },
            {"name": "Payload", "type": "multilineText"},
            {"name": "Resolution", "type": "multilineText"},
            {"name": "Created At", "type": "dateTime", "options": {"timeZone": "Africa/Johannesburg", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
            {"name": "Resolved At", "type": "dateTime", "options": {"timeZone": "Africa/Johannesburg", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
        ],
    },
    "KPI Snapshots": {
        "description": "Daily metrics snapshots per agent for trend analysis and anomaly detection",
        "primary_field": "Snapshot ID",
        "fields": [
            {"name": "Snapshot Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Agent ID", "type": "singleLineText"},
            {"name": "Revenue ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Leads Generated", "type": "number", "options": {"precision": 0}},
            {"name": "Content Published", "type": "number", "options": {"precision": 0}},
            {"name": "Emails Sent", "type": "number", "options": {"precision": 0}},
            {"name": "Messages Handled", "type": "number", "options": {"precision": 0}},
            {"name": "Tickets Resolved", "type": "number", "options": {"precision": 0}},
            {"name": "Success Rate", "type": "number", "options": {"precision": 1}},
            {"name": "Response Time Avg", "type": "number", "options": {"precision": 1}},
            {"name": "Token Usage", "type": "number", "options": {"precision": 0}},
            {"name": "Anomalies", "type": "multilineText"},
        ],
    },
    "Escalation Queue": {
        "description": "Human escalation queue with severity, category, and AI recommendations",
        "primary_field": "Title",
        "fields": [
            {"name": "Agent ID", "type": "singleLineText"},
            {
                "name": "Severity",
                "type": "singleSelect",
                "options": {"choices": SEVERITY_CHOICES},
            },
            {
                "name": "Category",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Workflow Failure", "color": "redBright"},
                        {"name": "Data Anomaly", "color": "orangeBright"},
                        {"name": "Budget Exceeded", "color": "yellowBright"},
                        {"name": "SLA Breach", "color": "redDark1"},
                        {"name": "Manual Required", "color": "grayBright"},
                        {"name": "Security Alert", "color": "purpleBright"},
                        {"name": "Client Churn Risk", "color": "orangeDark1"},
                    ]
                },
            },
            {"name": "Description", "type": "multilineText"},
            {"name": "Recommended Action", "type": "multilineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Open", "color": "redBright"},
                        {"name": "Acknowledged", "color": "yellowBright"},
                        {"name": "Resolved", "color": "greenBright"},
                        {"name": "Dismissed", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Owner", "type": "email"},
            {"name": "Created At", "type": "dateTime", "options": {"timeZone": "Africa/Johannesburg", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
            {"name": "Resolved At", "type": "dateTime", "options": {"timeZone": "Africa/Johannesburg", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
        ],
    },
    "Decision Log": {
        "description": "Audit trail of all autonomous decisions made by AI agents",
        "primary_field": "Decision ID",
        "fields": [
            {"name": "Agent ID", "type": "singleLineText"},
            {
                "name": "Decision Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "auto_retry", "color": "blueBright"},
                        {"name": "deactivate", "color": "redBright"},
                        {"name": "budget_adjust", "color": "greenBright"},
                        {"name": "escalate", "color": "orangeBright"},
                        {"name": "schedule_change", "color": "purpleBright"},
                        {"name": "content_optimize", "color": "cyanBright"},
                        {"name": "lead_qualify", "color": "yellowBright"},
                        {"name": "auto_respond", "color": "greenDark1"},
                    ]
                },
            },
            {"name": "Context", "type": "multilineText"},
            {"name": "Decision", "type": "multilineText"},
            {
                "name": "Outcome",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Success", "color": "greenBright"},
                        {"name": "Failed", "color": "redBright"},
                        {"name": "Pending", "color": "yellowBright"},
                    ]
                },
            },
            {"name": "Confidence", "type": "number", "options": {"precision": 2}},
            {"name": "Created At", "type": "dateTime", "options": {"timeZone": "Africa/Johannesburg", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
        ],
    },
}

# -- Seed Data: Agent Registry --

SEED_AGENTS = [
    {
        "Agent Name": "Marketing AI Agent",
        "Agent ID": "agent_marketing",
        "Status": "Active",
        "Health Score": 100,
        "Department": "Marketing",
        "Workflow IDs": json.dumps([
            "twSg4SfNdlmdITHj",  # MKT WF-01
            "CWQ9zjCTaf56RBe6",  # MKT WF-02
            "ygwBtSysINRWHJxB",  # MKT WF-03
            "ZEcxIC9M5ehQvsbg",  # MKT WF-04
            "5XZFaoQxfyJOlqje",  # SEO WF-05
            "ipsnBC5Xox4DWgBg",  # SEO WF-06
            "u7LSuq6zmAY8P7fU",  # SEO WF-07
            "M67NBeAEHfDIJ9wz",  # SEO WF-08
            "BpZ4LkxKjHoGfjUq",  # SEO WF-09
            "Xlu3tGHgM5DDXnkl",  # SEO WF-10
            "Y80dDSmWQfUlfvib",  # SEO WF-11
            "0US5H9smGsrCUsv7",  # SEO SCORE
        ]),
        "Description": "Manages marketing intelligence, strategy, content production, distribution, SEO/social growth engine, and bridge integrations.",
    },
    {
        "Agent Name": "Content Creation Agent",
        "Agent ID": "agent_content",
        "Status": "Active",
        "Health Score": 100,
        "Department": "Content",
        "Workflow IDs": json.dumps([
            "ygwBtSysINRWHJxB",  # MKT WF-03 (content production)
            "ipsnBC5Xox4DWgBg",  # SEO WF-06 (SEO content)
            "u7LSuq6zmAY8P7fU",  # SEO WF-07 (publishing)
        ]),
        "Description": "Generates blog posts, social media content, video scripts, newsletters. Coordinates with Marketing for high-performing content.",
    },
    {
        "Agent Name": "Finance & Accounting Agent",
        "Agent ID": "agent_finance",
        "Status": "Active",
        "Health Score": 100,
        "Department": "Finance",
        "Workflow IDs": json.dumps([
            "twSg4SfNdlmdITHj",  # ACC WF-01
            "CWQ9zjCTaf56RBe6",  # ACC WF-02
            "ygwBtSysINRWHJxB",  # ACC WF-03
            "ZEcxIC9M5ehQvsbg",  # ACC WF-04
            "f0Wh4SOxbODbs4TE",  # ACC WF-05
            "gwMuSElYqDTRGFKa",  # ACC WF-06
            "EmpOzaaDGqsLvg5j",  # ACC WF-07
        ]),
        "Description": "Manages invoicing, collections, payments reconciliation, supplier bills, month-end close, master data audit, and exception handling. QuickBooks integrated.",
    },
    {
        "Agent Name": "Client Relations Agent",
        "Agent ID": "agent_client_relations",
        "Status": "Active",
        "Health Score": 100,
        "Department": "Client Relations",
        "Workflow IDs": json.dumps([]),
        "Description": "Manages client onboarding, satisfaction tracking, renewal pipeline, and upsell opportunities. CRM-style client understanding.",
    },
    {
        "Agent Name": "Customer Support Agent",
        "Agent ID": "agent_support",
        "Status": "Active",
        "Health Score": 100,
        "Department": "Customer Support",
        "Workflow IDs": json.dumps([]),
        "Description": "Handles support ticket creation, SLA monitoring, auto-resolution from knowledge base, and KB article generation.",
    },
    {
        "Agent Name": "WhatsApp Communication Agent",
        "Agent ID": "agent_whatsapp",
        "Status": "Maintenance",
        "Health Score": 0,
        "Department": "WhatsApp",
        "Workflow IDs": json.dumps([]),
        "Description": "Real-time WhatsApp Business API communication. Conversation analytics, CRM sync, issue detection. INACTIVE pending Meta verification.",
    },
    {
        "Agent Name": "Central Orchestrator",
        "Agent ID": "agent_orchestrator",
        "Status": "Active",
        "Health Score": 100,
        "Department": "Orchestrator",
        "Workflow IDs": json.dumps([]),
        "Description": "Meta-agent that coordinates all department agents. Health monitoring, KPI aggregation, cross-department routing, reporting, and escalation.",
    },
]


def create_table(client, token, base_id, table_name, table_def):
    """Create a table with fields via Airtable API."""
    payload = {
        "name": table_name,
        "description": table_def["description"],
        "fields": [
            {"name": "Name", "type": "singleLineText"},
            *table_def["fields"],
        ],
    }

    resp = client.post(
        f"{AIRTABLE_META_API}/{base_id}/tables",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
    )

    if resp.status_code == 200:
        table_data = resp.json()
        table_id = table_data["id"]
        field_count = len(table_data.get("fields", []))

        # Rename primary field to table-specific name
        primary_name = table_def.get("primary_field", "Name")
        if primary_name != "Name":
            primary_field_id = table_data["fields"][0]["id"]
            rename_resp = client.patch(
                f"{AIRTABLE_META_API}/{base_id}/tables/{table_id}/fields/{primary_field_id}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"name": primary_name},
            )
            if rename_resp.status_code != 200:
                print(f"    Warning: Could not rename primary field: {rename_resp.status_code}")

        return table_id, field_count
    else:
        error_msg = resp.text[:200]
        return None, error_msg


def seed_agent_registry(client, token, base_id, table_id):
    """Seed Agent Registry with all 7 department agents."""
    records = []
    for agent in SEED_AGENTS:
        fields = {
            "Agent Name": agent["Agent Name"],
            "Agent ID": agent["Agent ID"],
            "Status": agent["Status"],
            "Health Score": agent["Health Score"],
            "Department": agent["Department"],
            "Workflow IDs": agent["Workflow IDs"],
            "Description": agent["Description"],
            "Created At": datetime.now().strftime("%Y-%m-%d"),
        }
        records.append({"fields": fields})

    resp = client.post(
        f"{AIRTABLE_API}/{base_id}/{table_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"records": records},
    )

    if resp.status_code == 200:
        return len(resp.json().get("records", []))
    else:
        print(f"    Seed error: {resp.status_code} - {resp.text[:200]}")
        return 0


def main():
    seed_mode = "--seed" in sys.argv

    print("=" * 60)
    print("AVM AUTONOMOUS OPERATIONS - ORCHESTRATOR AIRTABLE SETUP")
    print("=" * 60)
    print()

    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    base_id = ORCH_BASE_ID
    if not base_id:
        print("ERROR: ORCH_AIRTABLE_BASE_ID not set in .env")
        print()
        print("Steps to fix:")
        print("  1. Create a new blank Airtable base called 'Operations Control'")
        print("  2. Copy the base ID from the URL (starts with 'app')")
        print("  3. Set ORCH_AIRTABLE_BASE_ID=appXXX in .env")
        sys.exit(1)

    print(f"Base ID: {base_id}")
    print(f"Tables to create: {len(TABLE_DEFINITIONS)}")
    print(f"Seed mode: {'ON' if seed_mode else 'OFF'}")
    print()

    client = httpx.Client(timeout=30)
    created_tables = {}

    # Create all tables
    print("Creating tables...")
    print("-" * 40)

    for table_name, table_def in TABLE_DEFINITIONS.items():
        table_id, result = create_table(client, token, base_id, table_name, table_def)
        if table_id:
            created_tables[table_name] = table_id
            print(f"  + {table_name:<25} -> {table_id} ({result} fields)")
        else:
            print(f"  - {table_name:<25} FAILED: {result}")

    print()

    # Seed data if requested
    if seed_mode and created_tables:
        print("Seeding data...")
        print("-" * 40)

        if "Agent Registry" in created_tables:
            count = seed_agent_registry(client, token, base_id, created_tables["Agent Registry"])
            print(f"  + Agent Registry: {count} agents seeded")

        print()

    client.close()

    # Summary
    print("=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print()
    print(f"Created: {len(created_tables)}/{len(TABLE_DEFINITIONS)} tables")
    print()

    if created_tables:
        print("Table IDs (add these to .env):")
        print("-" * 40)
        env_key_map = {
            "Agent Registry": "ORCH_TABLE_AGENT_REGISTRY",
            "Orchestrator Events": "ORCH_TABLE_EVENTS",
            "KPI Snapshots": "ORCH_TABLE_KPI_SNAPSHOTS",
            "Escalation Queue": "ORCH_TABLE_ESCALATION_QUEUE",
            "Decision Log": "ORCH_TABLE_DECISION_LOG",
        }
        for name, tid in created_tables.items():
            env_key = env_key_map.get(name, name.upper().replace(" ", "_"))
            print(f"  {env_key}={tid}")
        print()

        # Save to .tmp for reference
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "orchestrator_airtable_ids.json"

        ids_data = {
            "base_id": base_id,
            "tables": {env_key_map.get(name, name): tid for name, tid in created_tables.items()},
            "created_at": datetime.now().isoformat(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ids_data, f, indent=2)
        print(f"Table IDs saved to: {output_path}")

    print()
    print("Next steps:")
    print("  1. Add the table IDs above to your .env file")
    print("  2. Update config.json with the orchestrator section")
    print("  3. Run: python tools/deploy_orchestrator.py build")


if __name__ == "__main__":
    main()

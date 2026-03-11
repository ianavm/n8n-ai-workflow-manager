"""
AVM Support Agent - Airtable Setup

Creates the Support Airtable base with 3 tables:
    1. Tickets          - Support tickets with AI classification and SLA tracking
    2. Knowledge_Base   - KB articles generated from resolved tickets
    3. SLA_Config       - SLA rules per priority level

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. SUPPORT_AIRTABLE_BASE_ID set in .env (create a blank base first in Airtable UI)

Usage:
    python tools/setup_support_airtable.py              # Create all tables
    python tools/setup_support_airtable.py --seed        # Create tables + seed SLA_Config
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
SUPPORT_BASE_ID = os.getenv("SUPPORT_AIRTABLE_BASE_ID", "")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# -- Reusable option dicts --
PRIORITY_CHOICES = [
    {"name": "P1", "color": "redBright"},
    {"name": "P2", "color": "orangeBright"},
    {"name": "P3", "color": "yellowBright"},
    {"name": "P4", "color": "blueBright"},
]

TICKET_STATUS_CHOICES = [
    {"name": "Open", "color": "redBright"},
    {"name": "In_Progress", "color": "blueBright"},
    {"name": "Waiting", "color": "yellowBright"},
    {"name": "Resolved", "color": "greenBright"},
    {"name": "Closed", "color": "grayBright"},
]

KB_CATEGORY_CHOICES = [
    {"name": "FAQ", "color": "blueBright"},
    {"name": "Troubleshooting", "color": "orangeBright"},
    {"name": "How-To", "color": "greenBright"},
    {"name": "Policy", "color": "purpleBright"},
]

DT_OPTIONS = {
    "timeZone": "Africa/Johannesburg",
    "dateFormat": {"name": "iso"},
    "timeFormat": {"name": "24hour"},
}

# -- Table Definitions --

TABLE_DEFINITIONS = {
    "Tickets": {
        "description": "Support tickets with AI priority classification, SLA deadlines, and resolution tracking",
        "primary_field": "ticket_id",
        "fields": [
            {"name": "client_id", "type": "singleLineText"},
            {"name": "client_email", "type": "singleLineText"},
            {"name": "subject", "type": "singleLineText"},
            {"name": "body", "type": "multilineText"},
            {
                "name": "priority",
                "type": "singleSelect",
                "options": {"choices": PRIORITY_CHOICES},
            },
            {
                "name": "status",
                "type": "singleSelect",
                "options": {"choices": TICKET_STATUS_CHOICES},
            },
            {"name": "assigned_to", "type": "singleLineText"},
            {"name": "sla_deadline", "type": "dateTime", "options": DT_OPTIONS},
            {"name": "ai_summary", "type": "multilineText"},
            {"name": "ai_suggestion", "type": "multilineText"},
            {"name": "resolved_at", "type": "dateTime", "options": DT_OPTIONS},
            {"name": "created_at", "type": "dateTime", "options": DT_OPTIONS},
        ],
    },
    "Knowledge_Base": {
        "description": "KB articles auto-generated from resolved tickets for AI auto-resolution",
        "primary_field": "article_id",
        "fields": [
            {"name": "title", "type": "singleLineText"},
            {
                "name": "category",
                "type": "singleSelect",
                "options": {"choices": KB_CATEGORY_CHOICES},
            },
            {"name": "content", "type": "multilineText"},
            {"name": "keywords", "type": "multilineText"},
            {"name": "source_ticket_ids", "type": "multilineText"},
            {"name": "confidence_score", "type": "number", "options": {"precision": 2}},
            {"name": "last_updated", "type": "dateTime", "options": DT_OPTIONS},
            {"name": "created_at", "type": "dateTime", "options": DT_OPTIONS},
        ],
    },
    "SLA_Config": {
        "description": "SLA rules per priority level with response/resolution time targets",
        "primary_field": "priority",
        "fields": [
            {"name": "response_time_hours", "type": "number", "options": {"precision": 0}},
            {"name": "resolution_time_hours", "type": "number", "options": {"precision": 0}},
            {"name": "escalation_email", "type": "singleLineText"},
            {"name": "active", "type": "checkbox"},
        ],
    },
}

# -- Seed Data: SLA_Config --

SEED_SLA = [
    {"priority": "P1", "response_time_hours": 1, "resolution_time_hours": 4,
     "escalation_email": "ian@anyvisionmedia.com", "active": True},
    {"priority": "P2", "response_time_hours": 2, "resolution_time_hours": 8,
     "escalation_email": "ian@anyvisionmedia.com", "active": True},
    {"priority": "P3", "response_time_hours": 4, "resolution_time_hours": 24,
     "escalation_email": "ian@anyvisionmedia.com", "active": True},
    {"priority": "P4", "response_time_hours": 24, "resolution_time_hours": 168,
     "escalation_email": "ian@anyvisionmedia.com", "active": True},
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


def seed_sla_config(client, token, base_id, table_id):
    """Seed SLA_Config with default priority rules."""
    records = []
    for sla in SEED_SLA:
        fields = {
            "priority": sla["priority"],
            "response_time_hours": sla["response_time_hours"],
            "resolution_time_hours": sla["resolution_time_hours"],
            "escalation_email": sla["escalation_email"],
            "active": sla["active"],
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
    print("AVM SUPPORT AGENT - AIRTABLE SETUP")
    print("=" * 60)
    print()

    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    base_id = SUPPORT_BASE_ID
    if not base_id:
        print("ERROR: SUPPORT_AIRTABLE_BASE_ID not set in .env")
        print()
        print("Steps to fix:")
        print("  1. Create a new blank Airtable base called 'Support Agent'")
        print("  2. Copy the base ID from the URL (starts with 'app')")
        print("  3. Set SUPPORT_AIRTABLE_BASE_ID=appXXX in .env")
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

        if "SLA_Config" in created_tables:
            count = seed_sla_config(client, token, base_id, created_tables["SLA_Config"])
            print(f"  + SLA_Config: {count} rules seeded (P1: 1h/4h, P2: 2h/8h, P3: 4h/24h, P4: 24h/168h)")

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
            "Tickets": "SUPPORT_TABLE_TICKETS",
            "Knowledge_Base": "SUPPORT_TABLE_KNOWLEDGE_BASE",
            "SLA_Config": "SUPPORT_TABLE_SLA_CONFIG",
        }
        for name, tid in created_tables.items():
            env_key = env_key_map.get(name, name.upper().replace(" ", "_"))
            print(f"  {env_key}={tid}")
        print()

        # Save to .tmp for reference
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "support_airtable_ids.json"

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
    print("  2. Run: python tools/deploy_support_agent.py build")
    print("  3. Deploy with: python tools/deploy_support_agent.py deploy")


if __name__ == "__main__":
    main()

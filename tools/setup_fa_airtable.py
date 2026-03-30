"""
Setup Airtable tables for Financial Advisory CRM.

Creates 5 operational tables in the FA Airtable base:
  1. FA Pipeline - Client pipeline tracker
  2. FA Meetings - Meeting log
  3. FA Tasks   - Task tracker
  4. FA Compliance Log - Daily compliance results
  5. FA Metrics - Weekly snapshots

Usage:
    python tools/setup_fa_airtable.py [--seed]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

import httpx

AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"
AIRTABLE_API = "https://api.airtable.com/v0"


TABLE_DEFINITIONS = {
    "FA Pipeline": {
        "description": "Client pipeline tracker for financial advisory CRM",
        "primary_field": "Client Name",
        "fields": [
            {"name": "Email", "type": "email"},
            {"name": "Phone", "type": "phoneNumber"},
            {"name": "Adviser", "type": "singleLineText"},
            {
                "name": "Pipeline Stage",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Lead", "color": "grayLight2"},
                        {"name": "Contacted", "color": "cyanLight2"},
                        {"name": "Intake Complete", "color": "tealLight2"},
                        {"name": "Discovery Scheduled", "color": "greenLight2"},
                        {"name": "Discovery Complete", "color": "yellowLight2"},
                        {"name": "Analysis", "color": "orangeLight2"},
                        {"name": "Presentation Scheduled", "color": "redLight2"},
                        {"name": "Presentation Complete", "color": "pinkLight2"},
                        {"name": "Implementation", "color": "purpleLight2"},
                        {"name": "Active", "color": "greenBright"},
                        {"name": "Inactive", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Source", "type": "singleLineText"},
            {"name": "Health Score", "type": "number", "options": {"precision": 0}},
            {"name": "Supabase ID", "type": "singleLineText"},
            {"name": "Next Meeting", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Africa/Johannesburg"}},
            {"name": "Notes", "type": "multilineText"},
            {"name": "Created", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Africa/Johannesburg"}},
        ],
    },
    "FA Meetings": {
        "description": "Meeting log for financial advisory",
        "primary_field": "Title",
        "fields": [
            {"name": "Client", "type": "singleLineText"},
            {"name": "Adviser", "type": "singleLineText"},
            {
                "name": "Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Discovery", "color": "blueLight2"},
                        {"name": "Presentation", "color": "purpleLight2"},
                        {"name": "Review", "color": "greenLight2"},
                        {"name": "Follow Up", "color": "yellowLight2"},
                        {"name": "Ad Hoc", "color": "grayLight2"},
                    ]
                },
            },
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Scheduled", "color": "blueLight2"},
                        {"name": "Confirmed", "color": "cyanLight2"},
                        {"name": "In Progress", "color": "yellowLight2"},
                        {"name": "Completed", "color": "greenBright"},
                        {"name": "Cancelled", "color": "redLight2"},
                        {"name": "No Show", "color": "redBright"},
                        {"name": "Rescheduled", "color": "orangeLight2"},
                    ]
                },
            },
            {"name": "Scheduled At", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Africa/Johannesburg"}},
            {"name": "Teams URL", "type": "url"},
            {
                "name": "Transcript Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "None", "color": "grayLight2"},
                        {"name": "Pending", "color": "yellowLight2"},
                        {"name": "Processing", "color": "orangeLight2"},
                        {"name": "Available", "color": "greenBright"},
                        {"name": "Failed", "color": "redLight2"},
                    ]
                },
            },
            {"name": "Supabase ID", "type": "singleLineText"},
        ],
    },
    "FA Tasks": {
        "description": "Task tracker for financial advisory",
        "primary_field": "Title",
        "fields": [
            {"name": "Client", "type": "singleLineText"},
            {"name": "Assigned To", "type": "singleLineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Pending", "color": "yellowLight2"},
                        {"name": "In Progress", "color": "blueLight2"},
                        {"name": "Waiting", "color": "orangeLight2"},
                        {"name": "Completed", "color": "greenBright"},
                        {"name": "Cancelled", "color": "grayLight2"},
                    ]
                },
            },
            {
                "name": "Priority",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Low", "color": "grayLight2"},
                        {"name": "Medium", "color": "yellowLight2"},
                        {"name": "High", "color": "orangeLight2"},
                        {"name": "Urgent", "color": "redBright"},
                    ]
                },
            },
            {"name": "Due Date", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Africa/Johannesburg"}},
            {"name": "Source", "type": "singleLineText"},
            {"name": "Supabase ID", "type": "singleLineText"},
        ],
    },
    "FA Compliance Log": {
        "description": "Daily compliance check results",
        "primary_field": "Check Date",
        "fields": [
            {"name": "Total Clients", "type": "number", "options": {"precision": 0}},
            {"name": "Missing POPIA Consent", "type": "number", "options": {"precision": 0}},
            {"name": "Missing FAIS Disclosure", "type": "number", "options": {"precision": 0}},
            {"name": "Expired Consent", "type": "number", "options": {"precision": 0}},
            {"name": "Overdue Tasks", "type": "number", "options": {"precision": 0}},
            {"name": "Unverified FICA", "type": "number", "options": {"precision": 0}},
            {"name": "Compliance Score", "type": "number", "options": {"precision": 0}},
            {"name": "Report HTML", "type": "multilineText"},
        ],
    },
    "FA Metrics": {
        "description": "Weekly metric snapshots",
        "primary_field": "Week",
        "fields": [
            {"name": "Meetings Booked", "type": "number", "options": {"precision": 0}},
            {"name": "Meetings Completed", "type": "number", "options": {"precision": 0}},
            {"name": "No Shows", "type": "number", "options": {"precision": 0}},
            {"name": "New Clients", "type": "number", "options": {"precision": 0}},
            {"name": "Conversion Rate", "type": "percent", "options": {"precision": 1}},
            {"name": "Tasks Completed", "type": "number", "options": {"precision": 0}},
            {"name": "Tasks Overdue", "type": "number", "options": {"precision": 0}},
            {"name": "Compliance Score", "type": "number", "options": {"precision": 0}},
        ],
    },
}


def create_table(
    client: httpx.Client,
    token: str,
    base_id: str,
    table_name: str,
    table_def: dict,
) -> tuple[str, int]:
    """Create an Airtable table via Meta API."""
    primary_field_name = table_def.get("primary_field", "Name")

    payload = {
        "name": table_name,
        "description": table_def["description"],
        "fields": [
            {"name": primary_field_name, "type": "singleLineText"},
            *table_def["fields"],
        ],
    }

    resp = client.post(
        f"{AIRTABLE_META_API}/{base_id}/tables",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    if resp.status_code == 200:
        data = resp.json()
        table_id = data["id"]
        field_count = len(data.get("fields", []))
        print(f"  Created: {table_name} ({table_id}) - {field_count} fields")
        return table_id, field_count
    else:
        print(f"  ERROR creating {table_name}: {resp.status_code} {resp.text[:200]}")
        return "", 0


def main() -> None:
    token = os.getenv("AIRTABLE_API_TOKEN", "")
    base_id = os.getenv("FA_AIRTABLE_BASE_ID", "")

    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not set")
        sys.exit(1)
    if not base_id:
        print("ERROR: FA_AIRTABLE_BASE_ID not set")
        sys.exit(1)

    print(f"\nFinancial Advisory Airtable Setup")
    print(f"Base: {base_id}")
    print(f"Tables: {len(TABLE_DEFINITIONS)}\n")

    created_tables: dict[str, str] = {}

    with httpx.Client(timeout=30) as client:
        for table_name, table_def in TABLE_DEFINITIONS.items():
            table_id, _ = create_table(client, token, base_id, table_name, table_def)
            if table_id:
                created_tables[table_name] = table_id

    # Print env vars for .env
    print("\n" + "=" * 60)
    print("Add to .env:")
    print("=" * 60)

    env_map = {
        "FA Pipeline": "FA_TABLE_PIPELINE",
        "FA Meetings": "FA_TABLE_MEETINGS",
        "FA Tasks": "FA_TABLE_TASKS",
        "FA Compliance Log": "FA_TABLE_COMPLIANCE",
        "FA Metrics": "FA_TABLE_METRICS",
    }

    for table_name, env_key in env_map.items():
        table_id = created_tables.get(table_name, "NOT_CREATED")
        print(f"{env_key}={table_id}")

    print(f"\n{len(created_tables)}/{len(TABLE_DEFINITIONS)} tables created.\n")


if __name__ == "__main__":
    main()

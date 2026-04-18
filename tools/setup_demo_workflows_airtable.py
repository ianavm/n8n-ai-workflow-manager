"""
Demo Workflows — Airtable Setup Tool.

Creates 2 tables in the AVM Marketing Airtable base for the three social-media
demo automations (Missed Call Money Back, 5-Minute Lead Responder, Inbox
Autopilot). The Lead Responder re-uses the existing ``Leads`` table
(``tblwOPTPY85Tcj7NJ``), so it is NOT recreated here.

Tables created:
    MCB_Missed_Calls — Twilio missed-call log (Workflow 3)
    IA_Inbox_Log     — AI email triage audit trail (Workflow 2)

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. MARKETING_AIRTABLE_BASE_ID set in .env (apptjjBx34z9340tK)

Usage:
    python tools/setup_demo_workflows_airtable.py              # Create tables
    python tools/setup_demo_workflows_airtable.py --seed       # Create + seed samples
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import httpx
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

DATETIME_OPTIONS = {
    "dateFormat": {"name": "iso"},
    "timeFormat": {"name": "24hour"},
    "timeZone": "Africa/Johannesburg",
}

# -- Shared choices --

CALL_STATUS_CHOICES = [
    {"name": "no-answer", "color": "redBright"},
    {"name": "busy", "color": "orangeBright"},
    {"name": "failed", "color": "redDark1"},
    {"name": "canceled", "color": "grayBright"},
    {"name": "completed", "color": "greenBright"},
]

CALL_WINDOW_CHOICES = [
    {"name": "business-hours", "color": "greenBright"},
    {"name": "after-hours", "color": "blueBright"},
]

MCB_STATUS_CHOICES = [
    {"name": "SMS Sent", "color": "cyanBright"},
    {"name": "Reply Received", "color": "greenBright"},
    {"name": "Booked", "color": "greenDark1"},
    {"name": "No Reply", "color": "grayBright"},
    {"name": "Opted Out", "color": "redBright"},
]

INBOX_CATEGORY_CHOICES = [
    {"name": "URGENT", "color": "redBright"},
    {"name": "CLIENT", "color": "greenBright"},
    {"name": "SALES", "color": "blueBright"},
    {"name": "BILLING", "color": "yellowBright"},
    {"name": "NOISE", "color": "grayBright"},
]

INBOX_ACTION_CHOICES = [
    {"name": "Starred", "color": "yellowBright"},
    {"name": "Draft Created", "color": "blueBright"},
    {"name": "Archived", "color": "grayBright"},
    {"name": "Logged Only", "color": "grayDark1"},
    {"name": "Skipped", "color": "grayDark1"},
]


# -- Table Definitions --

TABLE_DEFINITIONS: dict[str, dict] = {
    "MCB_Missed_Calls": {
        "description": (
            "Missed-call auto-responder log for the Missed Call Money Back workflow. "
            "One row per Twilio call status callback that looked unanswered."
        ),
        "primary_field": "Call ID",
        "fields": [
            {"name": "From Phone", "type": "phoneNumber"},
            {"name": "To Phone", "type": "phoneNumber"},
            {
                "name": "Call Status",
                "type": "singleSelect",
                "options": {"choices": CALL_STATUS_CHOICES},
            },
            {
                "name": "Call Window",
                "type": "singleSelect",
                "options": {"choices": CALL_WINDOW_CHOICES},
            },
            {"name": "Is Repeat Caller", "type": "checkbox", "options": {"color": "blueBright", "icon": "check"}},
            {"name": "SMS Body", "type": "multilineText"},
            {"name": "SMS SID", "type": "singleLineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {"choices": MCB_STATUS_CHOICES},
            },
            {"name": "Reply Text", "type": "multilineText"},
            {
                "name": "Received At",
                "type": "dateTime",
                "options": DATETIME_OPTIONS,
            },
        ],
    },
    "IA_Inbox_Log": {
        "description": (
            "Audit trail for the Inbox Autopilot AI triage workflow. One row per "
            "classified email with category, summary, and action taken."
        ),
        "primary_field": "Log ID",
        "fields": [
            {"name": "Message ID", "type": "singleLineText"},
            {"name": "From", "type": "singleLineText"},
            {"name": "Subject", "type": "singleLineText"},
            {
                "name": "Category",
                "type": "singleSelect",
                "options": {"choices": INBOX_CATEGORY_CHOICES},
            },
            {"name": "Summary", "type": "multilineText"},
            {"name": "Suggested Reply", "type": "multilineText"},
            {
                "name": "Action",
                "type": "singleSelect",
                "options": {"choices": INBOX_ACTION_CHOICES},
            },
            {"name": "Urgent Flagged", "type": "checkbox", "options": {"color": "redBright", "icon": "star"}},
            {
                "name": "Processed At",
                "type": "dateTime",
                "options": DATETIME_OPTIONS,
            },
        ],
    },
}


def get_headers() -> dict[str, str]:
    """Get Airtable API headers."""
    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not set in .env")
        sys.exit(1)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def create_table(table_name: str, table_def: dict) -> str | None:
    """Create a single Airtable table. Returns table ID or None on duplicate/error."""
    headers = get_headers()

    fields = [{"name": table_def["primary_field"], "type": "singleLineText"}]
    for field in table_def["fields"]:
        f: dict = {"name": field["name"], "type": field["type"]}
        if "options" in field:
            f["options"] = field["options"]
        fields.append(f)

    payload = {
        "name": table_name,
        "description": table_def.get("description", ""),
        "fields": fields,
    }

    url = f"{AIRTABLE_META_API}/{MARKETING_BASE_ID}/tables"
    response = httpx.post(url, headers=headers, json=payload, timeout=30)

    if response.status_code == 200:
        result = response.json()
        print(f"  Created: {table_name} (ID: {result['id']})")
        return result["id"]
    if response.status_code == 422 and "DUPLICATE_TABLE_NAME" in response.text:
        print(f"  Already exists: {table_name} (skipping — look up ID in Airtable UI)")
        return None
    print(f"  ERROR creating {table_name}: {response.status_code}")
    print(f"  Response: {response.text[:500]}")
    return None


def seed_missed_calls(table_id: str) -> None:
    """Seed MCB_Missed_Calls with a single demo row so the table is not empty."""
    headers = get_headers()
    now_iso = datetime.now().isoformat()
    records = [
        {
            "fields": {
                "Call ID": "MCB-DEMO-0001",
                "From Phone": "+27821234567",
                "To Phone": "+27109876543",
                "Call Status": "no-answer",
                "Call Window": "business-hours",
                "Is Repeat Caller": False,
                "SMS Body": (
                    "Hey! Sorry I missed your call — I'm on a job right now. "
                    "What can I help you with? I'll text back in 10 min."
                ),
                "SMS SID": "SMdemo0000000000000000000000000001",
                "Status": "SMS Sent",
                "Received At": now_iso,
            }
        }
    ]
    url = f"{AIRTABLE_API}/{MARKETING_BASE_ID}/{table_id}"
    response = httpx.post(url, headers=headers, json={"records": records}, timeout=30)
    if response.status_code == 200:
        print(f"  Seeded 1 sample row in MCB_Missed_Calls")
    else:
        print(f"  WARN seed failed ({response.status_code}): {response.text[:200]}")


def seed_inbox_log(table_id: str) -> None:
    """Seed IA_Inbox_Log with a single demo row so filters/views render."""
    headers = get_headers()
    now_iso = datetime.now().isoformat()
    records = [
        {
            "fields": {
                "Log ID": "IA-DEMO-0001",
                "Message ID": "demo-message-id-000",
                "From": "prospective.client@example.com",
                "Subject": "Interested in your automation services",
                "Category": "SALES",
                "Summary": "Prospect asking about pricing for a 3-workflow build.",
                "Suggested Reply": (
                    "Thanks for reaching out! Happy to run you through a 15-min discovery "
                    "call — here's my calendar link: ..."
                ),
                "Action": "Draft Created",
                "Urgent Flagged": False,
                "Processed At": now_iso,
            }
        }
    ]
    url = f"{AIRTABLE_API}/{MARKETING_BASE_ID}/{table_id}"
    response = httpx.post(url, headers=headers, json={"records": records}, timeout=30)
    if response.status_code == 200:
        print(f"  Seeded 1 sample row in IA_Inbox_Log")
    else:
        print(f"  WARN seed failed ({response.status_code}): {response.text[:200]}")


SEED_FUNCTIONS: dict[str, Callable[[str], None]] = {
    "MCB_Missed_Calls": seed_missed_calls,
    "IA_Inbox_Log": seed_inbox_log,
}

ENV_KEY_MAP = {
    "MCB_Missed_Calls": "DEMO_MCB_TABLE",
    "IA_Inbox_Log": "DEMO_IA_TABLE",
}


def main() -> None:
    seed = "--seed" in sys.argv

    print("=" * 60)
    print("DEMO WORKFLOWS — AIRTABLE SETUP")
    print("=" * 60)
    print(f"Base:      {MARKETING_BASE_ID}")
    print(f"Seed data: {'Yes' if seed else 'No'}")
    print()

    created_ids: dict[str, str] = {}
    for table_name, table_def in TABLE_DEFINITIONS.items():
        print(f"Creating {table_name}...")
        table_id = create_table(table_name, table_def)
        if table_id:
            created_ids[table_name] = table_id
            if seed and table_name in SEED_FUNCTIONS:
                SEED_FUNCTIONS[table_name](table_id)

    print()
    print("=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)

    if created_ids:
        print("\nAdd these to your .env file:\n")
        for table_name, table_id in created_ids.items():
            env_key = ENV_KEY_MAP.get(table_name, f"DEMO_TABLE_{table_name.upper()}")
            print(f"  {env_key}={table_id}")
        print("\nThen run: python tools/deploy_demo_workflows.py deploy")
    else:
        print(
            "\nNo new tables created. Either both already exist, or the API call "
            "failed. Look up existing IDs in the Airtable UI and add them to .env."
        )
    print()


if __name__ == "__main__":
    main()

"""
Bridge Integration - Airtable Field Setup

Adds 5 new fields to the SEO Leads table (tblwOPTPY85Tcj7NJ) in the
Marketing/SEO base (apptjjBx34z9340tK) required by the bridge workflows.

Fields added:
    1. Scraper Record ID - Back-reference to lead scraper base record
    2. Source System     - Origin tracking (Outbound_Scraper / SEO_Inbound / Email_Inbound)
    3. Grade             - From WF-SCORE output (Hot / Warm / Cold)
    4. Nurture Stage     - 0-3 sequence position for warm lead nurture
    5. Next Nurture Date - When next nurture email is due

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. SEO_TABLE_LEADS set in .env (or defaults to tblwOPTPY85Tcj7NJ)

Usage:
    python tools/setup_bridge_fields.py
"""

import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Configuration
AIRTABLE_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TABLE_LEADS = os.getenv("SEO_TABLE_LEADS", "tblwOPTPY85Tcj7NJ")
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# Fields to add
BRIDGE_FIELDS = [
    {
        "name": "Scraper Record ID",
        "type": "singleLineText",
        "description": "Back-reference to record ID in lead scraper Airtable base",
    },
    {
        "name": "Source System",
        "type": "singleSelect",
        "description": "Which system originally created this lead",
        "options": {
            "choices": [
                {"name": "Outbound_Scraper", "color": "blueBright"},
                {"name": "SEO_Inbound", "color": "greenBright"},
                {"name": "Email_Inbound", "color": "orangeBright"},
            ]
        },
    },
    {
        "name": "Grade",
        "type": "singleSelect",
        "description": "Lead quality grade from WF-SCORE scoring engine",
        "options": {
            "choices": [
                {"name": "Hot", "color": "redBright"},
                {"name": "Warm", "color": "orangeBright"},
                {"name": "Cold", "color": "blueBright"},
            ]
        },
    },
    {
        "name": "Nurture Stage",
        "type": "number",
        "description": "Current stage in warm lead nurture sequence (0=not started, 1-3=stages)",
        "options": {"precision": 0},
    },
    {
        "name": "Next Nurture Date",
        "type": "date",
        "description": "When the next nurture email should be sent",
        "options": {"dateFormat": {"name": "iso"}},
    },
]


def add_field(client, token, base_id, table_id, field_def):
    """Add a single field to an existing Airtable table."""
    resp = client.post(
        f"{AIRTABLE_META_API}/{base_id}/tables/{table_id}/fields",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=field_def,
    )

    if resp.status_code == 200:
        data = resp.json()
        return data.get("id"), data.get("name")
    elif resp.status_code == 422 and "already exists" in resp.text.lower():
        return "EXISTS", field_def["name"]
    else:
        return None, f"{resp.status_code}: {resp.text[:200]}"


def main():
    print("=" * 60)
    print("BRIDGE INTEGRATION - AIRTABLE FIELD SETUP")
    print("=" * 60)
    print()

    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    print(f"Base ID: {AIRTABLE_BASE_ID}")
    print(f"Table ID: {TABLE_LEADS}")
    print(f"Fields to add: {len(BRIDGE_FIELDS)}")
    print()

    client = httpx.Client(timeout=30)
    added = 0
    skipped = 0

    print("Adding fields to SEO Leads table...")
    print("-" * 40)

    for field_def in BRIDGE_FIELDS:
        field_id, result = add_field(client, token, AIRTABLE_BASE_ID, TABLE_LEADS, field_def)
        if field_id == "EXISTS":
            print(f"  ~ {field_def['name']:<25} already exists (skipped)")
            skipped += 1
        elif field_id:
            print(f"  + {field_def['name']:<25} -> {field_id}")
            added += 1
        else:
            print(f"  - {field_def['name']:<25} FAILED: {result}")

    client.close()

    print()
    print("=" * 60)
    print(f"COMPLETE: {added} added, {skipped} skipped")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Run: python tools/deploy_bridge_workflows.py build")
    print("  2. Run: python tools/deploy_bridge_workflows.py deploy")
    print("  3. Test each bridge workflow manually")
    print("  4. Run: python tools/deploy_bridge_workflows.py activate")


if __name__ == "__main__":
    main()

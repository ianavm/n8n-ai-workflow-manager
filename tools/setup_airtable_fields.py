"""
Create required fields in Airtable base for Lead Scraper workflow.

Usage:
    python tools/setup_airtable_fields.py
"""

import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


FIELD_DEFINITIONS = [
    {"name": "Business Name", "type": "singleLineText", "description": "Name of the business"},
    {"name": "Email", "type": "email", "description": "Primary contact email"},
    {"name": "Phone", "type": "phoneNumber", "description": "Contact phone number"},
    {"name": "Website", "type": "url", "description": "Business website"},
    {"name": "Address", "type": "singleLineText", "description": "Physical address"},
    {"name": "Industry", "type": "singleLineText", "description": "Business industry/category"},
    {"name": "Location", "type": "singleLineText", "description": "Location searched"},
    {"name": "Rating", "type": "number", "options": {"precision": 1}, "description": "Google Maps rating"},
    {"name": "Social - LinkedIn", "type": "url", "description": "LinkedIn profile URL"},
    {"name": "Social - Facebook", "type": "url", "description": "Facebook page URL"},
    {"name": "Social - Instagram", "type": "url", "description": "Instagram profile URL"},
    {"name": "Lead Score", "type": "number", "options": {"precision": 0}, "description": "Lead quality score 0-100"},
    {
        "name": "Automation Fit",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "high", "color": "greenBright"},
                {"name": "medium", "color": "yellowBright"},
                {"name": "low", "color": "grayBright"}
            ]
        },
        "description": "Automation opportunity fit level"
    },
    {
        "name": "Status",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "New", "color": "blueBright"},
                {"name": "Email Sent", "color": "yellowBright"},
                {"name": "Followed Up", "color": "orangeBright"},
                {"name": "Responded", "color": "greenBright"},
                {"name": "Converted", "color": "greenDark"},
                {"name": "Unsubscribed", "color": "redBright"}
            ]
        },
        "description": "Lead status"
    },
    {"name": "Source", "type": "singleLineText", "description": "Lead source"},
    {"name": "Date Scraped", "type": "date", "options": {"dateFormat": {"name": "iso"}}, "description": "Date lead was scraped"},
    {"name": "Email Sent Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}, "description": "Date outreach email was sent"},
]


def main():
    print("=" * 60)
    print("SETTING UP AIRTABLE FIELDS")
    print("=" * 60)
    print()

    token = os.getenv('AIRTABLE_API_TOKEN')
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not found")
        sys.exit(1)

    base_id = 'app2ALQUP7CKEkHOz'
    table_id = 'tblOsuh298hB9WWrA'

    print(f"Target Base: {base_id}")
    print(f"Target Table: {table_id}")
    print(f"Fields to create: {len(FIELD_DEFINITIONS)}")
    print()

    client = httpx.Client(timeout=30)

    # First, update the primary field (Name -> Business Name)
    print("Step 1: Updating primary field...")
    try:
        # Get current field ID for "Name"
        resp = client.get(
            f'https://api.airtable.com/v0/meta/bases/{base_id}/tables',
            headers={'Authorization': f'Bearer {token}'}
        )

        if resp.status_code != 200:
            print(f"  - Error fetching table schema: {resp.status_code}")
            print(resp.text[:500])
            sys.exit(1)

        tables = resp.json()['tables']
        target_table = next(t for t in tables if t['id'] == table_id)
        primary_field_id = target_table['fields'][0]['id']  # First field is always primary

        # Update it to "Business Name"
        resp = client.patch(
            f'https://api.airtable.com/v0/meta/bases/{base_id}/tables/{table_id}/fields/{primary_field_id}',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={"name": "Business Name", "description": "Name of the business"}
        )

        if resp.status_code == 200:
            print("  + Primary field renamed to 'Business Name'")
        else:
            print(f"  - Error updating primary field: {resp.status_code}")
            print(resp.text[:300])
    except Exception as e:
        print(f"  - Exception: {str(e)[:100]}")
        sys.exit(1)

    # Now create all other fields
    print()
    print("Step 2: Creating additional fields...")
    created = 0
    failed = 0
    skipped = 1  # Business Name already done

    for field_def in FIELD_DEFINITIONS[1:]:  # Skip first (Business Name)
        try:
            resp = client.post(
                f'https://api.airtable.com/v0/meta/bases/{base_id}/tables/{table_id}/fields',
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                json=field_def
            )

            if resp.status_code == 200:
                created += 1
                print(f"  + {field_def['name']:<30} ({field_def['type']})")
            else:
                failed += 1
                print(f"  - {field_def['name']:<30} - ERROR: {resp.status_code}")
                if resp.status_code == 422:
                    error_data = resp.json()
                    print(f"     {error_data.get('error', {}).get('message', '')[:80]}")
        except Exception as e:
            failed += 1
            print(f"  - {field_def['name']:<30} - EXCEPTION: {str(e)[:80]}")

    client.close()

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"+ Created: {created + 1}")  # +1 for updated primary field
    print(f"- Failed:  {failed}")
    print()

    if created + skipped >= len(FIELD_DEFINITIONS):
        print("SUCCESS! All fields are now set up.")
        print()
        print("You can now run: python tools/create_test_leads.py")
    else:
        print("Some fields failed to create. Check errors above.")


if __name__ == "__main__":
    main()

"""
Add Follow-Up Sequence fields to the Lead Scraper Airtable table.

Usage:
    python tools/add_followup_fields.py
"""

import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

BASE_ID = 'app2ALQUP7CKEkHOz'
TABLE_ID = 'tblOsuh298hB9WWrA'

NEW_FIELDS = [
    {
        "name": "Follow Up Stage",
        "type": "number",
        "options": {"precision": 0},
        "description": "0=inactive, 1=initial sent, 2=FU1 sent, 3=FU2 sent, 4=FU3 sent, 5=FU4 sent/complete"
    },
    {
        "name": "Next Follow Up Date",
        "type": "date",
        "options": {"dateFormat": {"name": "iso"}},
        "description": "Date when next follow-up email should be sent"
    },
]


def main():
    print("=" * 60)
    print("ADDING FOLLOW-UP FIELDS TO AIRTABLE")
    print("=" * 60)
    print()

    token = os.getenv('AIRTABLE_API_TOKEN')
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    print(f"Base: {BASE_ID}")
    print(f"Table: {TABLE_ID}")
    print(f"Fields to add: {len(NEW_FIELDS)}")
    print()

    client = httpx.Client(timeout=30)
    created = 0
    failed = 0

    for field_def in NEW_FIELDS:
        try:
            resp = client.post(
                f'https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{TABLE_ID}/fields',
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                json=field_def
            )

            if resp.status_code == 200:
                created += 1
                print(f"  + {field_def['name']:<25} ({field_def['type']})")
            elif resp.status_code == 422:
                error_data = resp.json()
                msg = error_data.get('error', {}).get('message', '')
                if 'already exists' in msg.lower() or 'duplicate' in msg.lower():
                    print(f"  ~ {field_def['name']:<25} (already exists, skipping)")
                    created += 1
                else:
                    failed += 1
                    print(f"  - {field_def['name']:<25} ERROR 422: {msg[:80]}")
            else:
                failed += 1
                print(f"  - {field_def['name']:<25} ERROR {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            failed += 1
            print(f"  - {field_def['name']:<25} EXCEPTION: {str(e)[:80]}")

    client.close()

    print()
    print("=" * 60)
    print(f"Created: {created}  |  Failed: {failed}")
    print("=" * 60)

    if failed == 0:
        print("All fields ready. Next: python tools/patch_lead_status_node.py")
    else:
        print("Some fields failed. Check errors above.")


if __name__ == "__main__":
    main()

"""
HeyGen Video Pipeline - Airtable Setup Tool

Creates 1 table in the AVM Marketing Airtable base (apptjjBx34z9340tK)
for tracking AI-generated property video content.

Table:
    Video_Jobs - Tracks HeyGen video generation requests, scripts, statuses,
                 and distribution results across social platforms.

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. MARKETING_AIRTABLE_BASE_ID set in .env (apptjjBx34z9340tK)

Usage:
    python tools/setup_heygen_airtable.py              # Create table
    python tools/setup_heygen_airtable.py --seed       # Create table + seed sample data
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
MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# -- Shared choices --
VIDEO_STATUS_CHOICES = [
    {"name": "Pending", "color": "blueBright"},
    {"name": "Script_Generated", "color": "cyanBright"},
    {"name": "Generating", "color": "yellowBright"},
    {"name": "Ready", "color": "greenBright"},
    {"name": "Published", "color": "greenDark1"},
    {"name": "Failed", "color": "redBright"},
    {"name": "Cancelled", "color": "grayBright"},
]

ASPECT_RATIO_CHOICES = [
    {"name": "9:16", "color": "purpleBright"},
    {"name": "16:9", "color": "blueBright"},
    {"name": "1:1", "color": "orangeBright"},
]

AVATAR_TYPE_CHOICES = [
    {"name": "Custom_Clone", "color": "greenBright"},
    {"name": "Stock_Avatar", "color": "blueBright"},
    {"name": "Photo_Avatar", "color": "yellowBright"},
]

PROPERTY_TYPE_CHOICES = [
    {"name": "House", "color": "greenBright"},
    {"name": "Apartment", "color": "blueBright"},
    {"name": "Townhouse", "color": "cyanBright"},
    {"name": "Estate", "color": "purpleBright"},
    {"name": "Commercial", "color": "orangeBright"},
    {"name": "Land", "color": "yellowBright"},
    {"name": "Other", "color": "grayBright"},
]

PLATFORM_CHOICES = [
    {"name": "TikTok", "color": "grayDark1"},
    {"name": "Instagram", "color": "purpleBright"},
    {"name": "Facebook", "color": "blueDark1"},
    {"name": "YouTube", "color": "redBright"},
    {"name": "LinkedIn", "color": "blueBright"},
]

# -- Table Definition --

TABLE_DEFINITION = {
    "Video_Jobs": {
        "description": "HeyGen AI video generation jobs for property walkthroughs and social media content",
        "primary_field": "Job ID",
        "fields": [
            {"name": "Property Name", "type": "singleLineText"},
            {
                "name": "Property Type",
                "type": "singleSelect",
                "options": {"choices": PROPERTY_TYPE_CHOICES},
            },
            {"name": "Property Address", "type": "singleLineText"},
            {"name": "Listing Price ZAR", "type": "number", "options": {"precision": 0}},
            {"name": "Property Photos", "type": "multilineText"},
            {"name": "Key Features", "type": "multilineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {"choices": VIDEO_STATUS_CHOICES},
            },
            {
                "name": "Aspect Ratio",
                "type": "singleSelect",
                "options": {"choices": ASPECT_RATIO_CHOICES},
            },
            {
                "name": "Avatar Type",
                "type": "singleSelect",
                "options": {"choices": AVATAR_TYPE_CHOICES},
            },
            {"name": "Avatar ID", "type": "singleLineText"},
            {"name": "Script", "type": "multilineText"},
            {"name": "Script Tone", "type": "singleLineText"},
            {"name": "Video Duration Sec", "type": "number", "options": {"precision": 0}},
            {"name": "HeyGen Video ID", "type": "singleLineText"},
            {"name": "HeyGen Status", "type": "singleLineText"},
            {"name": "Video URL", "type": "url"},
            {"name": "Thumbnail URL", "type": "url"},
            {"name": "Credits Used", "type": "number", "options": {"precision": 1}},
            {
                "name": "Target Platforms",
                "type": "multipleSelects",
                "options": {"choices": PLATFORM_CHOICES},
            },
            {"name": "Published Platforms", "type": "singleLineText"},
            {"name": "TikTok Post ID", "type": "singleLineText"},
            {"name": "Instagram Post ID", "type": "singleLineText"},
            {"name": "Facebook Post ID", "type": "singleLineText"},
            {"name": "Caption", "type": "multilineText"},
            {"name": "Hashtags", "type": "singleLineText"},
            {"name": "Created At", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Africa/Johannesburg"}},
            {"name": "Completed At", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Africa/Johannesburg"}},
            {"name": "Published At", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Africa/Johannesburg"}},
            {"name": "Error Message", "type": "multilineText"},
            {"name": "Source Listing ID", "type": "singleLineText"},
        ],
    },
}


def get_headers():
    """Get Airtable API headers."""
    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not set in .env")
        sys.exit(1)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def create_table(table_name, table_def):
    """Create a single Airtable table."""
    headers = get_headers()

    fields = [{"name": table_def["primary_field"], "type": "singleLineText"}]
    for field in table_def["fields"]:
        f = {"name": field["name"], "type": field["type"]}
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
    elif response.status_code == 422 and "DUPLICATE_TABLE_NAME" in response.text:
        print(f"  Already exists: {table_name} (skipping)")
        return None
    else:
        print(f"  ERROR creating {table_name}: {response.status_code}")
        print(f"  Response: {response.text[:500]}")
        return None


def seed_sample_data(table_id):
    """Seed the Video_Jobs table with sample data."""
    headers = get_headers()

    sample_records = [
        {
            "fields": {
                "Job ID": "VID-001-SAMPLE",
                "Property Name": "Modern 3BR in Fourways",
                "Property Type": "House",
                "Property Address": "42 Cedar Lane, Fourways, Johannesburg",
                "Listing Price ZAR": 2850000,
                "Key Features": "3 bedrooms, 2 bathrooms, double garage, pool, security estate",
                "Status": "Pending",
                "Aspect Ratio": "9:16",
                "Avatar Type": "Custom_Clone",
                "Script Tone": "professional, warm, aspirational",
                "Target Platforms": ["TikTok", "Instagram", "Facebook"],
                "Created At": datetime.now().isoformat(),
            }
        },
        {
            "fields": {
                "Job ID": "VID-002-SAMPLE",
                "Property Name": "Luxury Estate Bryanston",
                "Property Type": "Estate",
                "Property Address": "15 Bryanston Drive, Bryanston, Johannesburg",
                "Listing Price ZAR": 12500000,
                "Key Features": "5 bedrooms, cinema room, staff quarters, 3000sqm plot, north-facing",
                "Status": "Pending",
                "Aspect Ratio": "9:16",
                "Avatar Type": "Custom_Clone",
                "Script Tone": "luxury, exclusive, sophisticated",
                "Target Platforms": ["TikTok", "Instagram", "Facebook", "YouTube"],
                "Created At": datetime.now().isoformat(),
            }
        },
    ]

    url = f"{AIRTABLE_API}/{MARKETING_BASE_ID}/{table_id}"
    response = httpx.post(url, headers=headers, json={"records": sample_records}, timeout=30)

    if response.status_code == 200:
        created = response.json().get("records", [])
        print(f"  Seeded {len(created)} sample records")
    else:
        print(f"  ERROR seeding data: {response.status_code}")
        print(f"  Response: {response.text[:300]}")


def main():
    seed = "--seed" in sys.argv

    print("=" * 60)
    print("HEYGEN VIDEO PIPELINE - AIRTABLE SETUP")
    print("=" * 60)
    print(f"Base: {MARKETING_BASE_ID}")
    print(f"Seed data: {'Yes' if seed else 'No'}")
    print()

    created_ids = {}

    for table_name, table_def in TABLE_DEFINITION.items():
        print(f"Creating {table_name}...")
        table_id = create_table(table_name, table_def)
        if table_id:
            created_ids[table_name] = table_id
            if seed:
                seed_sample_data(table_id)

    print()
    print("=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)

    if created_ids:
        print("\nAdd these to your .env file:")
        print()
        for table_name, table_id in created_ids.items():
            env_key = f"HEYGEN_TABLE_{table_name.upper()}"
            print(f"  {env_key}={table_id}")

        print()
        print("Then update config.json with the table IDs.")
    else:
        print("\nNo new tables created (may already exist).")

    print()


if __name__ == "__main__":
    main()

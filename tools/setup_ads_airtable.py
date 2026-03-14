"""
Paid Advertising Department - Airtable Setup Tool

Creates 8 tables in the AVM Marketing Airtable base (apptjjBx34z9340tK)
for the autonomous marketing agent workflows (ADS-01 through ADS-08).

Located in the "AVM Only" workspace, colocated with existing organic
marketing tables (Content Calendar, Distribution Log, etc.).

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. MARKETING_AIRTABLE_BASE_ID set in .env (apptjjBx34z9340tK)

Usage:
    python tools/setup_ads_airtable.py              # Create all tables
    python tools/setup_ads_airtable.py --seed        # Create tables + seed sample data
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
PLATFORM_CHOICES = [
    {"name": "google_ads", "color": "redBright"},
    {"name": "meta_ads", "color": "blueDark1"},
    {"name": "tiktok_ads", "color": "grayDark1"},
    {"name": "youtube_ads", "color": "redDark1"},
]

STATUS_CAMPAIGN = [
    {"name": "Planned", "color": "blueBright"},
    {"name": "Approved", "color": "cyanBright"},
    {"name": "Launched", "color": "greenBright"},
    {"name": "Active", "color": "greenDark1"},
    {"name": "Paused", "color": "yellowBright"},
    {"name": "Completed", "color": "grayBright"},
    {"name": "Rejected", "color": "redBright"},
]

OBJECTIVE_CHOICES = [
    {"name": "Traffic", "color": "blueBright"},
    {"name": "Conversions", "color": "greenBright"},
    {"name": "Lead_Gen", "color": "purpleBright"},
    {"name": "Awareness", "color": "orangeBright"},
    {"name": "Video_Views", "color": "redBright"},
    {"name": "App_Install", "color": "cyanBright"},
]

PRIORITY_CHOICES = [
    {"name": "High", "color": "redBright"},
    {"name": "Medium", "color": "yellowBright"},
    {"name": "Low", "color": "grayBright"},
]

# -- Table Definitions --

TABLE_DEFINITIONS = {
    "Ad_Campaigns": {
        "description": "Campaign plans and active campaigns across all ad platforms",
        "primary_field": "Campaign Name",
        "fields": [
            {
                "name": "Platform",
                "type": "singleSelect",
                "options": {"choices": PLATFORM_CHOICES},
            },
            {
                "name": "Objective",
                "type": "singleSelect",
                "options": {"choices": OBJECTIVE_CHOICES},
            },
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {"choices": STATUS_CAMPAIGN},
            },
            {"name": "Target Audience", "type": "multilineText"},
            {"name": "Daily Budget ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Lifetime Budget ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Start Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "End Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "External Campaign ID", "type": "singleLineText"},
            {"name": "Key Messages", "type": "multilineText"},
            {
                "name": "Priority",
                "type": "singleSelect",
                "options": {"choices": PRIORITY_CHOICES},
            },
            {"name": "ROAS", "type": "number", "options": {"precision": 2}},
            {"name": "Total Spend ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Total Conversions", "type": "number", "options": {"precision": 0}},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Created By", "type": "singleLineText"},
        ],
    },
    "Ad_Sets": {
        "description": "Ad set / ad group level configuration per campaign",
        "primary_field": "Ad Set Name",
        "fields": [
            {"name": "Campaign Name", "type": "singleLineText"},
            {
                "name": "Platform",
                "type": "singleSelect",
                "options": {"choices": PLATFORM_CHOICES},
            },
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Active", "color": "greenBright"},
                        {"name": "Paused", "color": "yellowBright"},
                        {"name": "Completed", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Targeting", "type": "multilineText"},
            {"name": "Daily Budget ZAR", "type": "number", "options": {"precision": 2}},
            {
                "name": "Bid Strategy",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Lowest_Cost", "color": "greenBright"},
                        {"name": "Cost_Cap", "color": "yellowBright"},
                        {"name": "Bid_Cap", "color": "orangeBright"},
                        {"name": "Target_CPA", "color": "purpleBright"},
                        {"name": "Target_ROAS", "color": "blueBright"},
                    ]
                },
            },
            {"name": "Bid Amount ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "External AdSet ID", "type": "singleLineText"},
            {
                "name": "Placement",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Automatic", "color": "blueBright"},
                        {"name": "Feed", "color": "greenBright"},
                        {"name": "Stories", "color": "purpleBright"},
                        {"name": "Reels", "color": "pinkBright"},
                        {"name": "Search", "color": "orangeBright"},
                        {"name": "Display", "color": "cyanBright"},
                    ]
                },
            },
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Ad_Creatives": {
        "description": "Ad creative variations with copy, headlines, and quality scores",
        "primary_field": "Creative Name",
        "fields": [
            {"name": "Campaign Name", "type": "singleLineText"},
            {
                "name": "Platform",
                "type": "singleSelect",
                "options": {"choices": PLATFORM_CHOICES},
            },
            {
                "name": "Ad Format",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "RSA", "color": "blueBright"},
                        {"name": "Image", "color": "greenBright"},
                        {"name": "Video", "color": "redBright"},
                        {"name": "Carousel", "color": "purpleBright"},
                        {"name": "Collection", "color": "orangeBright"},
                    ]
                },
            },
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Draft", "color": "blueBright"},
                        {"name": "Approved", "color": "cyanBright"},
                        {"name": "Active", "color": "greenBright"},
                        {"name": "Paused", "color": "yellowBright"},
                        {"name": "Retired", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Headlines", "type": "multilineText"},
            {"name": "Descriptions", "type": "multilineText"},
            {"name": "Primary Text", "type": "multilineText"},
            {
                "name": "CTA",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Learn_More", "color": "blueBright"},
                        {"name": "Sign_Up", "color": "greenBright"},
                        {"name": "Contact_Us", "color": "purpleBright"},
                        {"name": "Get_Quote", "color": "orangeBright"},
                        {"name": "Book_Now", "color": "cyanBright"},
                    ]
                },
            },
            {"name": "Quality Score", "type": "number", "options": {"precision": 1}},
            {"name": "External Ad ID", "type": "singleLineText"},
            {"name": "Parent Creative ID", "type": "singleLineText"},
            {"name": "AB Test Group", "type": "singleLineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Ad_Performance": {
        "description": "Daily performance metrics per campaign per platform",
        "primary_field": "Performance ID",
        "fields": [
            {"name": "Campaign Name", "type": "singleLineText"},
            {
                "name": "Platform",
                "type": "singleSelect",
                "options": {"choices": PLATFORM_CHOICES},
            },
            {"name": "Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Impressions", "type": "number", "options": {"precision": 0}},
            {"name": "Clicks", "type": "number", "options": {"precision": 0}},
            {"name": "CTR", "type": "number", "options": {"precision": 4}},
            {"name": "Spend ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Conversions", "type": "number", "options": {"precision": 0}},
            {"name": "CPA ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "ROAS", "type": "number", "options": {"precision": 2}},
            {"name": "CPM ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "CPC ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Video Views", "type": "number", "options": {"precision": 0}},
            {"name": "Engagement Rate", "type": "number", "options": {"precision": 4}},
            {
                "name": "Attribution Source",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Direct", "color": "blueBright"},
                        {"name": "Assisted", "color": "greenBright"},
                        {"name": "First_Touch", "color": "purpleBright"},
                        {"name": "Last_Touch", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "Snapshot Hour", "type": "singleLineText"},
        ],
    },
    "Budget_Allocations": {
        "description": "Weekly/monthly budget allocation plans and actuals across platforms",
        "primary_field": "Allocation Name",
        "fields": [
            {"name": "Period Start", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Period End", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Total Budget ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Google Ads ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Meta Ads ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "TikTok Ads ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Organic Buffer ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Actual Spend ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Variance ZAR", "type": "number", "options": {"precision": 2}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Planned", "color": "blueBright"},
                        {"name": "Active", "color": "greenBright"},
                        {"name": "Completed", "color": "grayBright"},
                    ]
                },
            },
            {"name": "AI Recommendation", "type": "multilineText"},
        ],
    },
    "Audience_Segments": {
        "description": "Target audience definitions per platform with performance notes",
        "primary_field": "Segment Name",
        "fields": [
            {
                "name": "Platform",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        *PLATFORM_CHOICES,
                        {"name": "all", "color": "grayBright"},
                    ]
                },
            },
            {
                "name": "Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Interest", "color": "blueBright"},
                        {"name": "Lookalike", "color": "greenBright"},
                        {"name": "Retargeting", "color": "purpleBright"},
                        {"name": "Custom", "color": "orangeBright"},
                        {"name": "CRM", "color": "cyanBright"},
                    ]
                },
            },
            {"name": "Definition", "type": "multilineText"},
            {"name": "Size Estimate", "type": "number", "options": {"precision": 0}},
            {"name": "Performance Notes", "type": "multilineText"},
            {"name": "External Audience ID", "type": "singleLineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "AB_Tests": {
        "description": "A/B test tracking with variants, metrics, and statistical results",
        "primary_field": "Test Name",
        "fields": [
            {"name": "Campaign Name", "type": "singleLineText"},
            {"name": "Variant A ID", "type": "singleLineText"},
            {"name": "Variant B ID", "type": "singleLineText"},
            {
                "name": "Metric",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "CTR", "color": "blueBright"},
                        {"name": "CPA", "color": "greenBright"},
                        {"name": "ROAS", "color": "purpleBright"},
                        {"name": "Conversion_Rate", "color": "orangeBright"},
                    ]
                },
            },
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Running", "color": "greenBright"},
                        {"name": "Concluded", "color": "blueBright"},
                        {"name": "Cancelled", "color": "grayBright"},
                    ]
                },
            },
            {
                "name": "Winner",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "A", "color": "blueBright"},
                        {"name": "B", "color": "purpleBright"},
                        {"name": "Inconclusive", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Confidence", "type": "number", "options": {"precision": 1}},
            {"name": "Start Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "End Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Results", "type": "multilineText"},
        ],
    },
    "Campaign_Approvals": {
        "description": "Approval queue for campaigns, budget changes, and optimizations",
        "primary_field": "Approval ID",
        "fields": [
            {"name": "Campaign Name", "type": "singleLineText"},
            {
                "name": "Request Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "New_Campaign", "color": "blueBright"},
                        {"name": "Budget_Change", "color": "greenBright"},
                        {"name": "Creative_Update", "color": "purpleBright"},
                        {"name": "Optimization", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "Requested By", "type": "singleLineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Pending", "color": "yellowBright"},
                        {"name": "Approved", "color": "greenBright"},
                        {"name": "Rejected", "color": "redBright"},
                    ]
                },
            },
            {"name": "Details", "type": "multilineText"},
            {"name": "Budget Impact ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Approval URL", "type": "url"},
            {"name": "Approved By", "type": "singleLineText"},
            {"name": "Approved At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Notes", "type": "multilineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
}

# -- Seed Data --

SEED_AUDIENCES = [
    {
        "Segment Name": "SaaS Decision Makers SA",
        "Platform": "all",
        "Type": "Interest",
        "Definition": json.dumps({
            "age_range": "28-55",
            "geo": "South Africa",
            "interests": ["business software", "AI", "automation", "SaaS", "digital transformation"],
            "job_titles": ["CEO", "CTO", "COO", "Head of Operations", "IT Director"],
        }),
        "Size Estimate": 120000,
        "Performance Notes": "Primary target audience for all campaigns",
    },
    {
        "Segment Name": "Website Visitors 30d",
        "Platform": "meta_ads",
        "Type": "Retargeting",
        "Definition": json.dumps({
            "source": "pixel",
            "window": "30_days",
            "url_contains": "anyvisionmedia.com",
            "exclude": "converters",
        }),
        "Size Estimate": 5000,
        "Performance Notes": "Retarget landing page visitors who did not book a call",
    },
    {
        "Segment Name": "Lookalike - Portal Users",
        "Platform": "meta_ads",
        "Type": "Lookalike",
        "Definition": json.dumps({
            "source": "CRM upload of portal.anyvisionmedia.com users",
            "country": "ZA",
            "percentage": "1%",
        }),
        "Size Estimate": 250000,
        "Performance Notes": "Expand reach to users similar to existing clients",
    },
]

SEED_BUDGET = [
    {
        "Allocation Name": "Week 1 - Test Budget",
        "Total Budget ZAR": 3500,
        "Google Ads ZAR": 1500,
        "Meta Ads ZAR": 1500,
        "TikTok Ads ZAR": 0,
        "Organic Buffer ZAR": 500,
        "Actual Spend ZAR": 0,
        "Variance ZAR": 0,
        "Status": "Planned",
        "AI Recommendation": "Start with equal Google/Meta split. Monitor for 7 days before reallocating.",
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


def seed_records(client, token, base_id, table_id, records_data, primary_field):
    """Seed a table with initial records."""
    records = [{"fields": rec} for rec in records_data]

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
    print("PAID ADVERTISING DEPT - AIRTABLE SETUP")
    print("AVM Marketing Base (AVM Only Workspace)")
    print("=" * 60)
    print()

    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    base_id = MARKETING_BASE_ID
    if not base_id:
        print("ERROR: MARKETING_AIRTABLE_BASE_ID not set.")
        print()
        print("Steps to fix:")
        print("  1. Set MARKETING_AIRTABLE_BASE_ID in .env")
        print("  2. Default: apptjjBx34z9340tK (AVM Marketing base)")
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

        if "Audience_Segments" in created_tables:
            count = seed_records(
                client, token, base_id,
                created_tables["Audience_Segments"],
                SEED_AUDIENCES, "Segment Name",
            )
            print(f"  + Audience_Segments: {count} records seeded")

        if "Budget_Allocations" in created_tables:
            count = seed_records(
                client, token, base_id,
                created_tables["Budget_Allocations"],
                SEED_BUDGET, "Allocation Name",
            )
            print(f"  + Budget_Allocations: {count} records seeded")

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
        env_key_map = {
            "Ad_Campaigns": "ADS_TABLE_CAMPAIGNS",
            "Ad_Sets": "ADS_TABLE_ADSETS",
            "Ad_Creatives": "ADS_TABLE_CREATIVES",
            "Ad_Performance": "ADS_TABLE_PERFORMANCE",
            "Budget_Allocations": "ADS_TABLE_BUDGET_ALLOCATIONS",
            "Audience_Segments": "ADS_TABLE_AUDIENCES",
            "AB_Tests": "ADS_TABLE_AB_TESTS",
            "Campaign_Approvals": "ADS_TABLE_APPROVALS",
        }

        print("Table IDs (add these to .env):")
        print("-" * 40)
        for name, tid in created_tables.items():
            env_key = env_key_map.get(name, name.upper().replace(" ", "_"))
            print(f'  {env_key}={tid}')
        print()

        # Save to .tmp for reference
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "ads_airtable_ids.json"

        ids_data = {
            "base_id": base_id,
            "workspace": "AVM Only",
            "tables": {env_key_map.get(name, name): tid for name, tid in created_tables.items()},
            "created_at": datetime.now().isoformat(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ids_data, f, indent=2)
        print(f"Table IDs saved to: {output_path}")

    print()
    print("Next steps:")
    print("  1. Add the table IDs above to your .env file")
    print("  2. Update config.json ads_dept.tables with the IDs")
    print("  3. Create n8n credentials: Google Ads OAuth2, Meta Ads token")
    print("  4. Run: python tools/deploy_ads_dept.py build")


if __name__ == "__main__":
    main()

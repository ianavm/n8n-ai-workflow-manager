"""
SEO + Social Growth Engine - Airtable Base Setup Tool

Creates all 8 required tables in the Marketing Department Airtable base
for the SEO + Social Growth Engine workflows (WF-05 through WF-11 + WF-SCORE).

Extends the existing Marketing base (apptjjBx34z9340tK) rather than creating a new one.

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. MARKETING_AIRTABLE_BASE_ID set in .env (existing marketing base)

Usage:
    python tools/setup_seo_social_airtable.py              # Create all tables
    python tools/setup_seo_social_airtable.py --seed        # Create tables + seed sample data
"""

import os
import sys
import json
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# ── Configuration ──────────────────────────────────────────────
# Uses the SAME marketing base (extending it with SEO/Social tables)
MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# ── Platform choices (reused across tables) ───────────────────
PLATFORM_CHOICES = [
    {"name": "TikTok", "color": "grayDark1"},
    {"name": "Instagram", "color": "pinkBright"},
    {"name": "Facebook", "color": "blueDark1"},
    {"name": "LinkedIn", "color": "blueBright"},
    {"name": "Twitter", "color": "cyanBright"},
    {"name": "YouTube", "color": "redBright"},
    {"name": "Threads", "color": "grayBright"},
    {"name": "Bluesky", "color": "cyanDark1"},
    {"name": "Pinterest", "color": "redDark1"},
]

# ── Table Definitions ──────────────────────────────────────────

TABLE_DEFINITIONS = {
    "Keywords": {
        "description": "Keyword database for SEO tracking - clusters, rankings, scores",
        "primary_field": "Keyword",
        "fields": [
            {"name": "Cluster", "type": "singleLineText"},
            {"name": "Search Volume", "type": "number", "options": {"precision": 0}},
            {"name": "Difficulty", "type": "number", "options": {"precision": 0}},
            {"name": "Current Rank", "type": "number", "options": {"precision": 0}},
            {"name": "Previous Rank", "type": "number", "options": {"precision": 0}},
            {"name": "Rank Change", "type": "number", "options": {"precision": 0}},
            {"name": "Target URL", "type": "url"},
            {"name": "SEO Score", "type": "number", "options": {"precision": 0}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Discovery", "color": "blueBright"},
                        {"name": "Targeting", "color": "yellowBright"},
                        {"name": "Ranked", "color": "greenBright"},
                        {"name": "Lost", "color": "redBright"},
                    ]
                },
            },
            {
                "name": "Source",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "GSC", "color": "blueBright"},
                        {"name": "SerpAPI", "color": "purpleBright"},
                        {"name": "AI_Generated", "color": "orangeBright"},
                        {"name": "Manual", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Last Checked", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "SERP Snapshots": {
        "description": "Historical SERP position tracking per keyword",
        "primary_field": "Snapshot ID",
        "fields": [
            {"name": "Keyword", "type": "singleLineText"},
            {"name": "Check Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Position", "type": "number", "options": {"precision": 0}},
            {"name": "URL", "type": "url"},
            {"name": "Featured Snippet", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "SERP Features", "type": "multilineText"},
            {"name": "Competitor URLs", "type": "multilineText"},
            {
                "name": "Device",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Desktop", "color": "blueBright"},
                        {"name": "Mobile", "color": "orangeBright"},
                    ]
                },
            },
        ],
    },
    "Engagement Log": {
        "description": "Social media engagement metrics per post per platform",
        "primary_field": "Log ID",
        "fields": [
            {
                "name": "Platform",
                "type": "singleSelect",
                "options": {"choices": PLATFORM_CHOICES},
            },
            {"name": "Post ID", "type": "singleLineText"},
            {"name": "Content ID", "type": "singleLineText"},
            {
                "name": "Metric Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "like", "color": "redBright"},
                        {"name": "comment", "color": "blueBright"},
                        {"name": "share", "color": "greenBright"},
                        {"name": "save", "color": "yellowBright"},
                        {"name": "reply", "color": "purpleBright"},
                        {"name": "mention", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "Count", "type": "number", "options": {"precision": 0}},
            {"name": "Engagement Score", "type": "number", "options": {"precision": 0}},
            {"name": "Captured At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Leads": {
        "description": "Lead database with source attribution and scoring",
        "primary_field": "Lead ID",
        "fields": [
            {"name": "Contact Name", "type": "singleLineText"},
            {"name": "Email", "type": "email"},
            {"name": "Phone", "type": "phoneNumber"},
            {"name": "Company", "type": "singleLineText"},
            {
                "name": "Source Channel",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Organic", "color": "greenBright"},
                        {"name": "Social_TikTok", "color": "grayDark1"},
                        {"name": "Social_IG", "color": "pinkBright"},
                        {"name": "Social_LinkedIn", "color": "blueBright"},
                        {"name": "Social_Twitter", "color": "cyanBright"},
                        {"name": "Social_Facebook", "color": "blueDark1"},
                        {"name": "Referral", "color": "purpleBright"},
                        {"name": "Direct", "color": "orangeBright"},
                        {"name": "Paid", "color": "redBright"},
                    ]
                },
            },
            {"name": "Source URL", "type": "url"},
            {"name": "UTM Campaign", "type": "singleLineText"},
            {"name": "UTM Medium", "type": "singleLineText"},
            {"name": "UTM Source", "type": "singleLineText"},
            {"name": "First Touch Content", "type": "singleLineText"},
            {"name": "Lead Score", "type": "number", "options": {"precision": 0}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "New", "color": "blueBright"},
                        {"name": "Contacted", "color": "yellowBright"},
                        {"name": "Qualified", "color": "greenBright"},
                        {"name": "Converted", "color": "greenDark1"},
                        {"name": "Lost", "color": "redBright"},
                    ]
                },
            },
            {"name": "Notes", "type": "multilineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "SEO Audits": {
        "description": "On-page SEO audit results per URL with scores and recommendations",
        "primary_field": "Audit ID",
        "fields": [
            {"name": "URL", "type": "url"},
            {"name": "Audit Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Title Tag", "type": "singleLineText"},
            {"name": "Meta Description", "type": "multilineText"},
            {"name": "H1 Count", "type": "number", "options": {"precision": 0}},
            {"name": "Word Count", "type": "number", "options": {"precision": 0}},
            {"name": "Internal Links", "type": "number", "options": {"precision": 0}},
            {"name": "External Links", "type": "number", "options": {"precision": 0}},
            {"name": "Broken Links", "type": "multilineText"},
            {"name": "Image Alt Missing", "type": "number", "options": {"precision": 0}},
            {"name": "Page Speed Score", "type": "number", "options": {"precision": 0}},
            {"name": "Mobile Friendly", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Schema Markup", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "SEO Score", "type": "number", "options": {"precision": 0}},
            {"name": "Issues", "type": "multilineText"},
            {"name": "Recommendations", "type": "multilineText"},
        ],
    },
    "Analytics Snapshots": {
        "description": "Performance metrics snapshots (daily/weekly/monthly)",
        "primary_field": "Snapshot ID",
        "fields": [
            {
                "name": "Period",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Daily", "color": "blueBright"},
                        {"name": "Weekly", "color": "greenBright"},
                        {"name": "Monthly", "color": "purpleBright"},
                    ]
                },
            },
            {"name": "Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Platform", "type": "singleLineText"},
            {"name": "Followers", "type": "number", "options": {"precision": 0}},
            {"name": "Posts Published", "type": "number", "options": {"precision": 0}},
            {"name": "Total Engagement", "type": "number", "options": {"precision": 0}},
            {"name": "Engagement Rate", "type": "number", "options": {"precision": 2}},
            {"name": "Top Post ID", "type": "singleLineText"},
            {"name": "Impressions", "type": "number", "options": {"precision": 0}},
            {"name": "Clicks", "type": "number", "options": {"precision": 0}},
            {"name": "Conversions", "type": "number", "options": {"precision": 0}},
            {"name": "Revenue Attribution", "type": "number", "options": {"precision": 2}},
        ],
    },
    "Scoring Log": {
        "description": "Score history for content, leads, keywords, and pages",
        "primary_field": "Score ID",
        "fields": [
            {
                "name": "Entity Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Content", "color": "blueBright"},
                        {"name": "Lead", "color": "greenBright"},
                        {"name": "Keyword", "color": "purpleBright"},
                        {"name": "Page", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "Entity ID", "type": "singleLineText"},
            {"name": "Engagement Score", "type": "number", "options": {"precision": 0}},
            {"name": "Lead Score", "type": "number", "options": {"precision": 0}},
            {"name": "SEO Score", "type": "number", "options": {"precision": 0}},
            {"name": "Composite Score", "type": "number", "options": {"precision": 0}},
            {"name": "Scoring Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Reasoning", "type": "multilineText"},
        ],
    },
    "Content Topics": {
        "description": "Topic clusters with pillar pages and keyword targets",
        "primary_field": "Topic",
        "fields": [
            {"name": "Cluster", "type": "singleLineText"},
            {"name": "Pillar Page URL", "type": "url"},
            {"name": "Target Keywords", "type": "multilineText"},
            {"name": "Content Pieces", "type": "number", "options": {"precision": 0}},
            {"name": "Avg SEO Score", "type": "number", "options": {"precision": 0}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Planning", "color": "blueBright"},
                        {"name": "Active", "color": "greenBright"},
                        {"name": "Saturated", "color": "yellowBright"},
                    ]
                },
            },
            {"name": "Last Updated", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
}

# ── Sample Data for Seeding ───────────────────────────────────

SEED_KEYWORDS = [
    {"Keyword": "AI workflow automation South Africa", "Cluster": "AI Automation", "Search Volume": 320, "Difficulty": 35, "Status": "Targeting", "Source": "Manual"},
    {"Keyword": "n8n automation agency", "Cluster": "AI Automation", "Search Volume": 210, "Difficulty": 28, "Status": "Targeting", "Source": "Manual"},
    {"Keyword": "social media management Johannesburg", "Cluster": "Social Media", "Search Volume": 880, "Difficulty": 55, "Status": "Discovery", "Source": "Manual"},
    {"Keyword": "real estate marketing automation", "Cluster": "Real Estate", "Search Volume": 590, "Difficulty": 42, "Status": "Discovery", "Source": "Manual"},
    {"Keyword": "student accommodation marketing", "Cluster": "Real Estate", "Search Volume": 260, "Difficulty": 22, "Status": "Discovery", "Source": "Manual"},
    {"Keyword": "AI chatbot for business", "Cluster": "AI Automation", "Search Volume": 1200, "Difficulty": 62, "Status": "Discovery", "Source": "AI_Generated"},
    {"Keyword": "property investment South Africa", "Cluster": "Real Estate", "Search Volume": 2400, "Difficulty": 68, "Status": "Discovery", "Source": "AI_Generated"},
    {"Keyword": "WhatsApp business automation", "Cluster": "AI Automation", "Search Volume": 720, "Difficulty": 38, "Status": "Targeting", "Source": "Manual"},
]

SEED_CONTENT_TOPICS = [
    {"Topic": "AI Workflow Automation", "Cluster": "AI Automation", "Pillar Page URL": "https://www.anyvisionmedia.com/services/ai-automation", "Target Keywords": '["AI workflow automation", "n8n automation", "business process automation"]', "Content Pieces": 0, "Status": "Active"},
    {"Topic": "Real Estate Marketing", "Cluster": "Real Estate", "Pillar Page URL": "https://www.anyvisionmedia.com/services/real-estate", "Target Keywords": '["real estate marketing", "property marketing automation", "agent marketing tools"]', "Content Pieces": 0, "Status": "Planning"},
    {"Topic": "Social Media Growth", "Cluster": "Social Media", "Pillar Page URL": "https://www.anyvisionmedia.com/services/social-media", "Target Keywords": '["social media management", "content strategy", "engagement growth"]', "Content Pieces": 0, "Status": "Active"},
]


def create_table(client, token, base_id, table_name, table_def):
    """Create a table with fields via Airtable API."""
    payload = {
        "name": table_name,
        "description": table_def["description"],
        "fields": [
            {"name": "Name", "type": "singleLineText"},  # Primary field (required)
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


def seed_keywords(client, token, base_id, table_id):
    """Seed keywords table with initial targets."""
    records = []
    for kw in SEED_KEYWORDS:
        records.append({
            "fields": {
                "Keyword": kw["Keyword"],
                "Cluster": kw["Cluster"],
                "Search Volume": kw["Search Volume"],
                "Difficulty": kw["Difficulty"],
                "Status": kw["Status"],
                "Source": kw["Source"],
                "Created At": datetime.now().strftime("%Y-%m-%d"),
            }
        })

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


def seed_content_topics(client, token, base_id, table_id):
    """Seed content topics with initial clusters."""
    records = []
    for topic in SEED_CONTENT_TOPICS:
        records.append({
            "fields": {
                "Topic": topic["Topic"],
                "Cluster": topic["Cluster"],
                "Pillar Page URL": topic["Pillar Page URL"],
                "Target Keywords": topic["Target Keywords"],
                "Content Pieces": topic["Content Pieces"],
                "Status": topic["Status"],
                "Last Updated": datetime.now().strftime("%Y-%m-%d"),
            }
        })

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
    print("SEO + SOCIAL GROWTH ENGINE - AIRTABLE SETUP")
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
        print("  2. This should be the existing Marketing Department base ID")
        print("  3. The SEO/Social tables will be added to this base")
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

        if "Keywords" in created_tables:
            count = seed_keywords(client, token, base_id, created_tables["Keywords"])
            print(f"  + Keywords: {count} records seeded")

        if "Content Topics" in created_tables:
            count = seed_content_topics(client, token, base_id, created_tables["Content Topics"])
            print(f"  + Content Topics: {count} records seeded")

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
            "Keywords": "SEO_TABLE_KEYWORDS",
            "SERP Snapshots": "SEO_TABLE_SERP_SNAPSHOTS",
            "Engagement Log": "SEO_TABLE_ENGAGEMENT_LOG",
            "Leads": "SEO_TABLE_LEADS",
            "SEO Audits": "SEO_TABLE_SEO_AUDITS",
            "Analytics Snapshots": "SEO_TABLE_ANALYTICS_SNAPSHOTS",
            "Scoring Log": "SEO_TABLE_SCORING_LOG",
            "Content Topics": "SEO_TABLE_CONTENT_TOPICS",
        }
        for name, tid in created_tables.items():
            env_key = env_key_map.get(name, name.upper().replace(" ", "_"))
            print(f'  {env_key}={tid}')
        print()

        # Save to .tmp for reference
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "seo_social_airtable_ids.json"

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
    print("  2. Update config.json with the seo_social_dept section")
    print("  3. Run: python tools/deploy_seo_social_dept.py build")


if __name__ == "__main__":
    main()

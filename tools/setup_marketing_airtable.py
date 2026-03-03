"""
Marketing Department - Airtable Base Setup Tool

Creates all required tables in the Marketing Department Airtable base.
Follows the same pattern as setup_airtable_fields.py.

Prerequisites:
    1. Create a new Airtable base called "Marketing Department" manually
    2. Set AIRTABLE_API_TOKEN in .env
    3. Update MARKETING_BASE_ID below with your new base ID

Usage:
    python tools/setup_marketing_airtable.py              # Create all tables
    python tools/setup_marketing_airtable.py --seed        # Create tables + seed sample data
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
# UPDATE THIS after creating the Airtable base manually
MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# ── Table Definitions ──────────────────────────────────────────

TABLE_DEFINITIONS = {
    "Content Calendar": {
        "description": "Daily content plan — topics, platforms, and status tracking",
        "fields": [
            {"name": "Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {
                "name": "Content Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "social_post", "color": "blueBright"},
                        {"name": "blog_post", "color": "purpleBright"},
                        {"name": "email_campaign", "color": "orangeBright"},
                        {"name": "video_script", "color": "redBright"},
                        {"name": "carousel", "color": "tealBright"},
                    ]
                },
            },
            {"name": "Topic", "type": "singleLineText"},
            {
                "name": "Platform",
                "type": "multipleSelects",
                "options": {
                    "choices": [
                        {"name": "LinkedIn", "color": "blueBright"},
                        {"name": "Twitter", "color": "cyanBright"},
                        {"name": "Instagram", "color": "pinkBright"},
                        {"name": "TikTok", "color": "grayDark1"},
                        {"name": "Facebook", "color": "blueDark1"},
                        {"name": "YouTube", "color": "redBright"},
                        {"name": "Threads", "color": "grayBright"},
                        {"name": "Bluesky", "color": "cyanDark1"},
                        {"name": "Pinterest", "color": "redDark1"},
                    ]
                },
            },
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Planned", "color": "blueBright"},
                        {"name": "In Production", "color": "yellowBright"},
                        {"name": "Draft", "color": "orangeBright"},
                        {"name": "Ready", "color": "greenBright"},
                        {"name": "Published", "color": "greenDark1"},
                        {"name": "Failed", "color": "redBright"},
                    ]
                },
            },
            {"name": "Brief", "type": "multilineText"},
            {"name": "Campaign", "type": "singleLineText"},
        ],
    },
    "Content": {
        "description": "Generated content pieces with quality scores and variations",
        "fields": [
            {"name": "Calendar Entry ID", "type": "singleLineText"},
            {
                "name": "Content Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "social_post", "color": "blueBright"},
                        {"name": "blog_post", "color": "purpleBright"},
                        {"name": "email_campaign", "color": "orangeBright"},
                        {"name": "video_script", "color": "redBright"},
                        {"name": "carousel", "color": "tealBright"},
                    ]
                },
            },
            {"name": "Body", "type": "multilineText"},
            {"name": "Hashtags", "type": "multilineText"},
            {"name": "Hook Variations", "type": "multilineText"},
            {"name": "Selected Hook", "type": "number", "options": {"precision": 0}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Draft", "color": "yellowBright"},
                        {"name": "Ready", "color": "greenBright"},
                        {"name": "Published", "color": "greenDark1"},
                        {"name": "Rejected", "color": "redBright"},
                    ]
                },
            },
            {"name": "Quality Score", "type": "number", "options": {"precision": 0}},
            {"name": "Platform", "type": "singleLineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Publish Queue": {
        "description": "Distribution queue — content waiting to be published",
        "fields": [
            {"name": "Content ID", "type": "singleLineText"},
            {
                "name": "Channel",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "blotato_social", "color": "blueBright"},
                        {"name": "gmail_campaign", "color": "orangeBright"},
                        {"name": "blog", "color": "purpleBright"},
                    ]
                },
            },
            {"name": "Scheduled For", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Queued", "color": "blueBright"},
                        {"name": "Publishing", "color": "yellowBright"},
                        {"name": "Published", "color": "greenDark1"},
                        {"name": "Failed", "color": "redBright"},
                    ]
                },
            },
            {"name": "Published At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Platform Results", "type": "multilineText"},
        ],
    },
    "Distribution Log": {
        "description": "Per-platform publishing results for analytics",
        "fields": [
            {"name": "Content ID", "type": "singleLineText"},
            {"name": "Platform", "type": "singleLineText"},
            {"name": "Published At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Success", "color": "greenBright"},
                        {"name": "Failed", "color": "redBright"},
                    ]
                },
            },
            {"name": "Response", "type": "multilineText"},
        ],
    },
    "System State": {
        "description": "Key-value store for orchestrator state tracking",
        "fields": [
            {"name": "Value", "type": "multilineText"},
            {"name": "Updated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated By", "type": "singleLineText"},
        ],
    },
    "Research Config": {
        "description": "Competitor URLs, RSS feeds, and keywords to monitor",
        "fields": [
            {
                "name": "Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "competitor", "color": "redBright"},
                        {"name": "rss_feed", "color": "orangeBright"},
                        {"name": "keyword", "color": "purpleBright"},
                    ]
                },
            },
            {"name": "URL", "type": "singleLineText"},
            {"name": "Label", "type": "singleLineText"},
            {"name": "Active", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Last Checked", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Notes", "type": "multilineText"},
        ],
    },
    "Research Insights": {
        "description": "AI-analyzed intelligence findings from competitor and trend research",
        "fields": [
            {
                "name": "Source Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "competitor", "color": "redBright"},
                        {"name": "rss", "color": "orangeBright"},
                        {"name": "trend", "color": "blueBright"},
                    ]
                },
            },
            {"name": "Source", "type": "singleLineText"},
            {"name": "Summary", "type": "multilineText"},
            {"name": "Key Themes", "type": "multilineText"},
            {"name": "Content Opportunities", "type": "multilineText"},
            {"name": "Relevance Score", "type": "number", "options": {"precision": 0}},
            {"name": "Week", "type": "singleLineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
}

# ── Sample Data for Seeding ───────────────────────────────────

DEFAULT_TOPICS = [
    "5 ways AI automation saves small businesses 10+ hours per week",
    "Why most businesses waste money on manual processes (and how to fix it)",
    "The difference between automation and AI — explained simply",
    "How we helped a real estate agency automate their lead follow-up",
    "3 signs your business is ready for AI workflow automation",
    "Stop doing this manually: tasks every business should automate today",
    "The ROI of automation: real numbers from real businesses",
]

PLATFORMS = ["LinkedIn", "Twitter", "Instagram", "TikTok", "Facebook", "YouTube", "Threads", "Bluesky", "Pinterest"]

RESEARCH_CONFIG_SEEDS = [
    # Competitors
    {"Key": "competitor_zapier", "Type": "competitor", "URL": "https://zapier.com/blog", "Label": "Zapier Blog", "Active": True, "Notes": "Major automation platform competitor — track their content strategy and product updates"},
    {"Key": "competitor_make", "Type": "competitor", "URL": "https://www.make.com/en/blog", "Label": "Make.com Blog", "Active": True, "Notes": "Visual automation competitor — monitor their positioning and use cases"},
    {"Key": "competitor_n8n", "Type": "competitor", "URL": "https://n8n.io/blog", "Label": "n8n Blog", "Active": True, "Notes": "Our platform provider — stay current on features and community trends"},
    # RSS Feeds
    {"Key": "rss_techcrunch", "Type": "rss_feed", "URL": "https://techcrunch.com/feed", "Label": "TechCrunch", "Active": True, "Notes": "General tech news — AI and automation coverage"},
    {"Key": "rss_thenextweb", "Type": "rss_feed", "URL": "https://thenextweb.com/feed", "Label": "The Next Web", "Active": True, "Notes": "Tech news with business angle"},
    # Keywords
    {"Key": "kw_ai_automation", "Type": "keyword", "URL": "", "Label": "AI automation", "Active": True, "Notes": "Primary service keyword"},
    {"Key": "kw_workflow_automation", "Type": "keyword", "URL": "", "Label": "workflow automation", "Active": True, "Notes": "Core technology keyword"},
    {"Key": "kw_nocode", "Type": "keyword", "URL": "", "Label": "no-code tools", "Active": True, "Notes": "Adjacent market keyword"},
]

SYSTEM_STATE_SEEDS = [
    {"Key": "last_content_run", "Value": json.dumps({"timestamp": None, "items_created": 0}), "Updated By": "setup"},
    {"Key": "last_distribution_run", "Value": json.dumps({"timestamp": None, "items_published": 0}), "Updated By": "setup"},
    {"Key": "daily_token_count", "Value": json.dumps({"date": None, "tokens": 0, "budget": 50000}), "Updated By": "setup"},
    {"Key": "system_status", "Value": json.dumps({"status": "active", "paused_workflows": []}), "Updated By": "setup"},
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

        # Rename primary field from "Name" to something table-specific
        primary_rename = {
            "Content Calendar": "Title",
            "Content": "Title",
            "Publish Queue": "Queue ID",
            "Distribution Log": "Log ID",
            "System State": "Key",
            "Research Config": "Key",
            "Research Insights": "Title",
        }
        if table_name in primary_rename:
            primary_field_id = table_data["fields"][0]["id"]
            rename_resp = client.patch(
                f"{AIRTABLE_META_API}/{base_id}/tables/{table_id}/fields/{primary_field_id}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"name": primary_rename[table_name]},
            )
            if rename_resp.status_code != 200:
                print(f"    Warning: Could not rename primary field: {rename_resp.status_code}")

        return table_id, field_count
    else:
        error_msg = resp.text[:200]
        return None, error_msg


def seed_content_calendar(client, token, base_id, table_id):
    """Seed the content calendar with 7 days of sample topics."""
    today = datetime.now()
    records = []

    for i, topic in enumerate(DEFAULT_TOPICS):
        date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        records.append({
            "fields": {
                "Title": f"Day {i+1}: {topic[:50]}",
                "Date": date,
                "Content Type": "social_post",
                "Topic": topic,
                "Platform": PLATFORMS,
                "Status": "Planned",
                "Brief": f"Create engaging social media content about: {topic}. Target audience: small to medium businesses.",
                "Campaign": "General Brand Awareness",
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


def seed_system_state(client, token, base_id, table_id):
    """Seed system state with initial configuration."""
    records = []
    for item in SYSTEM_STATE_SEEDS:
        records.append({
            "fields": {
                "Key": item["Key"],
                "Value": item["Value"],
                "Updated At": datetime.now().strftime("%Y-%m-%d"),
                "Updated By": item["Updated By"],
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


def seed_research_config(client, token, base_id, table_id):
    """Seed research config with default competitors, RSS feeds, and keywords."""
    records = []
    for item in RESEARCH_CONFIG_SEEDS:
        fields = {
            "Key": item["Key"],
            "Type": item["Type"],
            "Label": item["Label"],
            "Active": item["Active"],
            "Notes": item["Notes"],
        }
        if item["URL"]:
            fields["URL"] = item["URL"]
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
    print("MARKETING DEPARTMENT - AIRTABLE SETUP")
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
        print("  1. Go to https://airtable.com and create a new base called 'Marketing Department'")
        print("  2. Copy the base ID from the URL (starts with 'app...')")
        print("  3. Add to .env: MARKETING_AIRTABLE_BASE_ID=appXXXXXXXXXX")
        print("  4. Or set it directly in this file: MARKETING_BASE_ID = 'appXXXXXXXXXX'")
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

        if "Content Calendar" in created_tables:
            count = seed_content_calendar(client, token, base_id, created_tables["Content Calendar"])
            print(f"  + Content Calendar: {count} records seeded (7 days of topics)")

        if "System State" in created_tables:
            count = seed_system_state(client, token, base_id, created_tables["System State"])
            print(f"  + System State: {count} records seeded")

        if "Research Config" in created_tables:
            count = seed_research_config(client, token, base_id, created_tables["Research Config"])
            print(f"  + Research Config: {count} records seeded (competitors, RSS feeds, keywords)")

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
        print("Table IDs (save these for config.json):")
        print("-" * 40)
        for name, tid in created_tables.items():
            config_key = name.lower().replace(" ", "_")
            print(f'  "{config_key}": "{tid}"')
        print()

        # Also save to .tmp for easy reference
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "marketing_airtable_ids.json"

        ids_data = {
            "base_id": base_id,
            "tables": {name.lower().replace(" ", "_"): tid for name, tid in created_tables.items()},
            "created_at": datetime.now().isoformat(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ids_data, f, indent=2)
        print(f"Table IDs saved to: {output_path}")

    print()
    print("Next steps:")
    print("  1. Add MARKETING_AIRTABLE_BASE_ID to .env (if not already)")
    print("  2. Update config.json with the table IDs above")
    print("  3. Run: python tools/deploy_marketing_dept.py build")


if __name__ == "__main__":
    main()

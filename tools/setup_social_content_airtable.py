"""
Social Content Trend Replication - Airtable Setup Tool

Creates 3 tables in the AVM Marketing Airtable base (apptjjBx34z9340tK)
for the Social Content pipeline (SC-01 through SC-05).

Tables:
    SC_Trending_Content - Discovered trending videos across platforms
    SC_Adapted_Scripts  - Brand-adapted scripts ready for production
    SC_Production_Log   - Render and publish audit trail

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. MARKETING_AIRTABLE_BASE_ID set in .env (apptjjBx34z9340tK)

Usage:
    python tools/setup_social_content_airtable.py              # Create tables
    python tools/setup_social_content_airtable.py --seed       # Create + seed sample data
"""

import os
import sys
import json
import httpx
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# -- Configuration --
MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# -- Shared choices --

PLATFORM_CHOICES = [
    {"name": "Instagram", "color": "purpleBright"},
    {"name": "LinkedIn", "color": "blueBright"},
    {"name": "YouTube", "color": "redBright"},
]

CONTENT_CATEGORY_CHOICES = [
    {"name": "How-to", "color": "greenBright"},
    {"name": "Listicle", "color": "blueBright"},
    {"name": "Quote", "color": "purpleBright"},
    {"name": "Stat-graphic", "color": "orangeBright"},
    {"name": "Reaction", "color": "yellowBright"},
    {"name": "Story", "color": "cyanBright"},
    {"name": "Tutorial", "color": "tealBright"},
]

TRENDING_STATUS_CHOICES = [
    {"name": "Discovered", "color": "blueBright"},
    {"name": "Extracted", "color": "cyanBright"},
    {"name": "Adapted", "color": "greenBright"},
    {"name": "Skipped", "color": "grayBright"},
]

VIDEO_TYPE_CHOICES = [
    {"name": "Text-on-screen", "color": "greenBright"},
    {"name": "Quote-card", "color": "purpleBright"},
    {"name": "Stat-graphic", "color": "orangeBright"},
    {"name": "Talking-head-script", "color": "blueBright"},
]

SCRIPT_STATUS_CHOICES = [
    {"name": "Adapted", "color": "blueBright"},
    {"name": "Script_Ready", "color": "cyanBright"},
    {"name": "Rendering", "color": "yellowBright"},
    {"name": "Rendered", "color": "greenBright"},
    {"name": "Publishing", "color": "tealBright"},
    {"name": "Published", "color": "greenDark1"},
    {"name": "Failed", "color": "redBright"},
]

COMPOSITION_CHOICES = [
    {"name": "TextOnScreen", "color": "greenBright"},
    {"name": "QuoteCard", "color": "purpleBright"},
    {"name": "StatGraphic", "color": "orangeBright"},
    {"name": "TalkingHeadOverlay", "color": "blueBright"},
]

LOG_ACTION_CHOICES = [
    {"name": "Render_Started", "color": "yellowBright"},
    {"name": "Render_Complete", "color": "greenBright"},
    {"name": "Render_Failed", "color": "redBright"},
    {"name": "Publish_Success", "color": "greenDark1"},
    {"name": "Publish_Failed", "color": "redDark1"},
]

LOG_PLATFORM_CHOICES = [
    {"name": "Instagram", "color": "purpleBright"},
    {"name": "LinkedIn", "color": "blueBright"},
    {"name": "YouTube", "color": "redBright"},
    {"name": "TikTok", "color": "grayDark1"},
    {"name": "Facebook", "color": "blueDark1"},
    {"name": "Twitter", "color": "cyanBright"},
]

DATETIME_OPTIONS = {
    "dateFormat": {"name": "iso"},
    "timeFormat": {"name": "24hour"},
    "timeZone": "Africa/Johannesburg",
}

# -- Table Definitions --

TABLE_DEFINITIONS: dict[str, dict] = {
    "SC_Trending_Content": {
        "description": "Trending short-form videos discovered across Instagram Reels, LinkedIn, and YouTube Shorts",
        "primary_field": "Trend ID",
        "fields": [
            {
                "name": "Platform",
                "type": "singleSelect",
                "options": {"choices": PLATFORM_CHOICES},
            },
            {"name": "Source URL", "type": "url"},
            {"name": "Source Creator", "type": "singleLineText"},
            {"name": "Title", "type": "singleLineText"},
            {"name": "View Count", "type": "number", "options": {"precision": 0}},
            {"name": "Like Count", "type": "number", "options": {"precision": 0}},
            {"name": "Comment Count", "type": "number", "options": {"precision": 0}},
            {
                "name": "Engagement Rate",
                "type": "number",
                "options": {"precision": 2},
            },
            {
                "name": "Content Category",
                "type": "singleSelect",
                "options": {"choices": CONTENT_CATEGORY_CHOICES},
            },
            {"name": "Transcript", "type": "multilineText"},
            {"name": "Template Pattern", "type": "multilineText"},
            {"name": "Virality Score", "type": "number", "options": {"precision": 0}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {"choices": TRENDING_STATUS_CHOICES},
            },
            {"name": "Skip Reason", "type": "singleLineText"},
            {
                "name": "Discovered At",
                "type": "dateTime",
                "options": DATETIME_OPTIONS,
            },
        ],
    },
    "SC_Adapted_Scripts": {
        "description": "Brand-adapted scripts ready for Remotion video production and Blotato distribution",
        "primary_field": "Script ID",
        "fields": [
            {"name": "Source Trend ID", "type": "singleLineText"},
            {
                "name": "Video Type",
                "type": "singleSelect",
                "options": {"choices": VIDEO_TYPE_CHOICES},
            },
            {"name": "Script Text", "type": "multilineText"},
            {"name": "Hook", "type": "singleLineText"},
            {"name": "CTA", "type": "singleLineText"},
            {"name": "Visual Notes", "type": "multilineText"},
            {"name": "Caption Instagram", "type": "multilineText"},
            {"name": "Caption LinkedIn", "type": "multilineText"},
            {"name": "Caption YouTube", "type": "multilineText"},
            {"name": "Hashtags", "type": "singleLineText"},
            {"name": "Thumbnail Prompt", "type": "multilineText"},
            {"name": "Estimated Duration Sec", "type": "number", "options": {"precision": 0}},
            {
                "name": "Remotion Composition",
                "type": "singleSelect",
                "options": {"choices": COMPOSITION_CHOICES},
            },
            {"name": "Remotion Props JSON", "type": "multilineText"},
            {"name": "Video URL", "type": "url"},
            {"name": "Thumbnail URL", "type": "url"},
            {"name": "Quality Score", "type": "number", "options": {"precision": 0}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {"choices": SCRIPT_STATUS_CHOICES},
            },
            {"name": "Error Message", "type": "multilineText"},
            {
                "name": "Created At",
                "type": "dateTime",
                "options": DATETIME_OPTIONS,
            },
            {
                "name": "Published At",
                "type": "dateTime",
                "options": DATETIME_OPTIONS,
            },
        ],
    },
    "SC_Production_Log": {
        "description": "Audit trail for Remotion rendering and Blotato publishing operations",
        "primary_field": "Log ID",
        "fields": [
            {"name": "Script ID", "type": "singleLineText"},
            {
                "name": "Action",
                "type": "singleSelect",
                "options": {"choices": LOG_ACTION_CHOICES},
            },
            {
                "name": "Platform",
                "type": "singleSelect",
                "options": {"choices": LOG_PLATFORM_CHOICES},
            },
            {
                "name": "Duration Sec",
                "type": "number",
                "options": {"precision": 1},
            },
            {"name": "Response", "type": "multilineText"},
            {
                "name": "Created At",
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
    """Create a single Airtable table. Returns table ID or None."""
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
    elif response.status_code == 422 and "DUPLICATE_TABLE_NAME" in response.text:
        print(f"  Already exists: {table_name} (skipping)")
        return None
    else:
        print(f"  ERROR creating {table_name}: {response.status_code}")
        print(f"  Response: {response.text[:500]}")
        return None


def seed_trending_content(table_id: str) -> None:
    """Seed SC_Trending_Content with sample data."""
    headers = get_headers()

    records = [
        {
            "fields": {
                "Trend ID": "TR-20260412-YT-SAMPLE",
                "Platform": "YouTube",
                "Source URL": "https://youtube.com/shorts/example1",
                "Source Creator": "@marketingtips",
                "Title": "3 AI Tools Every Marketer Needs in 2026",
                "View Count": 245000,
                "Like Count": 18200,
                "Comment Count": 342,
                "Engagement Rate": 7.57,
                "Content Category": "Listicle",
                "Virality Score": 82,
                "Status": "Discovered",
                "Discovered At": datetime.now().isoformat(),
            }
        },
        {
            "fields": {
                "Trend ID": "TR-20260412-IG-SAMPLE",
                "Platform": "Instagram",
                "Source URL": "https://instagram.com/reel/example2",
                "Source Creator": "@agencylife",
                "Title": "Why Your Agency Is Losing Clients (and How to Fix It)",
                "View Count": 89000,
                "Like Count": 7100,
                "Comment Count": 215,
                "Engagement Rate": 8.22,
                "Content Category": "How-to",
                "Virality Score": 75,
                "Status": "Discovered",
                "Discovered At": datetime.now().isoformat(),
            }
        },
        {
            "fields": {
                "Trend ID": "TR-20260412-LI-SAMPLE",
                "Platform": "LinkedIn",
                "Source URL": "https://linkedin.com/posts/example3",
                "Source Creator": "Digital Marketing Pro",
                "Title": "I automated 80% of my agency workflows. Here's what happened.",
                "View Count": 42000,
                "Like Count": 3200,
                "Comment Count": 187,
                "Engagement Rate": 8.07,
                "Content Category": "Story",
                "Virality Score": 71,
                "Status": "Discovered",
                "Discovered At": datetime.now().isoformat(),
            }
        },
    ]

    url = f"{AIRTABLE_API}/{MARKETING_BASE_ID}/{table_id}"
    response = httpx.post(url, headers=headers, json={"records": records}, timeout=30)

    if response.status_code == 200:
        created = response.json().get("records", [])
        print(f"  Seeded {len(created)} sample trending records")
    else:
        print(f"  ERROR seeding trending data: {response.status_code}")
        print(f"  Response: {response.text[:300]}")


def seed_adapted_scripts(table_id: str) -> None:
    """Seed SC_Adapted_Scripts with sample data."""
    headers = get_headers()

    records = [
        {
            "fields": {
                "Script ID": "SCR-20260412-SAMPLE",
                "Source Trend ID": "TR-20260412-YT-SAMPLE",
                "Video Type": "Text-on-screen",
                "Script Text": (
                    "Hook: Stop wasting hours on manual marketing tasks.\n"
                    "Point 1: AI workflow automation handles your follow-ups 24/7.\n"
                    "Point 2: Smart lead scoring tells you who's ready to buy.\n"
                    "Point 3: Automated reporting saves 10+ hours per week.\n"
                    "CTA: Follow for more automation tips."
                ),
                "Hook": "Stop wasting hours on manual marketing tasks",
                "CTA": "Follow for more automation tips",
                "Visual Notes": (
                    "Scene 1: Bold text reveal on dark gradient with brand orange accent.\n"
                    "Scene 2-4: Each point slides in with icon animation.\n"
                    "Scene 5: CTA card with AnyVision Media logo."
                ),
                "Caption Instagram": (
                    "3 ways AI is changing agency life forever.\n\n"
                    "We automated 80% of our workflows and here's what happened:\n\n"
                    "Save this for later.\n\n"
                    "#digitalmarketing #aiautomation #agencylife #marketingtips"
                ),
                "Caption LinkedIn": (
                    "Manual marketing tasks are costing your agency more than you think.\n\n"
                    "Here are 3 AI automations that saved us 40+ hours per week:\n\n"
                    "1. Automated follow-up sequences\n"
                    "2. AI-powered lead scoring\n"
                    "3. Real-time reporting dashboards\n\n"
                    "What would you automate first?"
                ),
                "Caption YouTube": (
                    "3 AI Tools Every Marketing Agency Needs in 2026 | AnyVision Media"
                ),
                "Hashtags": "#digitalmarketing #aiautomation #agencylife #marketingtips #southafrica",
                "Thumbnail Prompt": "Bold text '3 AI Tools' on dark gradient with orange glow, marketing dashboard background",
                "Estimated Duration Sec": 30,
                "Remotion Composition": "TextOnScreen",
                "Quality Score": 85,
                "Status": "Adapted",
                "Created At": datetime.now().isoformat(),
            }
        },
    ]

    url = f"{AIRTABLE_API}/{MARKETING_BASE_ID}/{table_id}"
    response = httpx.post(url, headers=headers, json={"records": records}, timeout=30)

    if response.status_code == 200:
        created = response.json().get("records", [])
        print(f"  Seeded {len(created)} sample script records")
    else:
        print(f"  ERROR seeding script data: {response.status_code}")
        print(f"  Response: {response.text[:300]}")


# Mapping of table names to their seed functions
SEED_FUNCTIONS: dict[str, callable] = {
    "SC_Trending_Content": seed_trending_content,
    "SC_Adapted_Scripts": seed_adapted_scripts,
    # SC_Production_Log has no seed data (populated by workflows)
}


def main() -> None:
    seed = "--seed" in sys.argv

    print("=" * 60)
    print("SOCIAL CONTENT TREND REPLICATION - AIRTABLE SETUP")
    print("=" * 60)
    print(f"Base: {MARKETING_BASE_ID}")
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
        env_map = {
            "SC_Trending_Content": "SC_TABLE_TRENDING",
            "SC_Adapted_Scripts": "SC_TABLE_SCRIPTS",
            "SC_Production_Log": "SC_TABLE_PRODUCTION_LOG",
        }
        for table_name, table_id in created_ids.items():
            env_key = env_map.get(table_name, f"SC_TABLE_{table_name.upper()}")
            print(f"  {env_key}={table_id}")

        print("\nThen run: python tools/deploy_social_content_dept.py build")
    else:
        print("\nNo new tables created (may already exist).")

    print()


if __name__ == "__main__":
    main()

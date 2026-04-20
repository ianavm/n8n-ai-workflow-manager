"""
Demo Workflows — Airtable Setup

Creates all tables required by the four demo workflows in the AVM
Marketing Airtable base (apptjjBx34z9340tK).

Tables:
    DEMO_Hook_Experiments    (Demo 4 — Hook Lab)
    DEMO_Comment_Leads       (Demo 3 — Comment Lead Miner)
    DEMO_Video_Clips         (Demo 1 — Video Clip Factory)
    DEMO_UGC_Campaigns       (Demo 2 — UGC Ops Autopilot)
    DEMO_UGC_Creators        (Demo 2 — UGC Ops Autopilot)
    DEMO_UGC_Outreach        (Demo 2 — UGC Ops Autopilot)

Prerequisites:
    AIRTABLE_API_TOKEN + MARKETING_AIRTABLE_BASE_ID in .env

Usage:
    python tools/setup_demo_airtable.py           # Create all 6 tables
    python tools/setup_demo_airtable.py --only hook,comment  # Just some
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

import httpx
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

DATETIME_OPTS = {
    "dateFormat": {"name": "iso"},
    "timeFormat": {"name": "24hour"},
    "timeZone": "Africa/Johannesburg",
}

PLATFORM_CHOICES = [
    {"name": "instagram", "color": "purpleBright"},
    {"name": "linkedin", "color": "blueBright"},
    {"name": "tiktok", "color": "grayDark1"},
    {"name": "youtube", "color": "redBright"},
    {"name": "facebook", "color": "blueDark1"},
    {"name": "twitter", "color": "cyanBright"},
]

# ==================================================================
# TABLE DEFINITIONS
# ==================================================================

ANGLE_CHOICES = [
    {"name": "curiosity", "color": "cyanBright"},
    {"name": "contrarian", "color": "redBright"},
    {"name": "fomo", "color": "orangeBright"},
    {"name": "social-proof", "color": "greenBright"},
    {"name": "transformation", "color": "purpleBright"},
]

CATEGORY_CHOICES = [
    {"name": "pricing", "color": "greenBright"},
    {"name": "demo-request", "color": "orangeBright"},
    {"name": "objection", "color": "yellowBright"},
    {"name": "endorsement", "color": "blueBright"},
    {"name": "support", "color": "purpleBright"},
    {"name": "spam", "color": "grayBright"},
    {"name": "generic", "color": "grayLight1"},
]

TIER_CHOICES = [
    {"name": "high", "color": "redBright"},
    {"name": "medium", "color": "orangeBright"},
    {"name": "low", "color": "grayBright"},
]

STATUS_UGC_CAMPAIGN = [
    {"name": "Sourcing", "color": "yellowBright"},
    {"name": "Outreach", "color": "blueBright"},
    {"name": "In Production", "color": "orangeBright"},
    {"name": "Complete", "color": "greenBright"},
    {"name": "Cancelled", "color": "grayBright"},
]

STATUS_UGC_CREATOR = [
    {"name": "Qualified", "color": "greenBright"},
    {"name": "Disqualified", "color": "grayBright"},
    {"name": "Accepted", "color": "blueBright"},
    {"name": "Rejected", "color": "redBright"},
    {"name": "Delivered", "color": "purpleBright"},
]

STATUS_UGC_OUTREACH = [
    {"name": "sent", "color": "greenBright"},
    {"name": "simulated_sent", "color": "cyanBright"},
    {"name": "failed", "color": "redBright"},
    {"name": "replied", "color": "purpleBright"},
]

CLIP_SOURCE_CHOICES = [
    {"name": "fixture", "color": "grayLight1"},
    {"name": "live", "color": "greenBright"},
]

LEAD_SOURCE_CHOICES = [
    {"name": "fixture", "color": "grayLight1"},
    {"name": "apify", "color": "orangeBright"},
    {"name": "webhook", "color": "blueBright"},
    {"name": "graph-api", "color": "purpleBright"},
]

CREATOR_SOURCE_CHOICES = [
    {"name": "fixture", "color": "grayLight1"},
    {"name": "apify", "color": "orangeBright"},
    {"name": "manual", "color": "blueBright"},
]


TABLE_DEFINITIONS: dict[str, dict] = {
    "DEMO_Hook_Experiments": {
        "description": "Hook Lab — per-variation log + winner picks from Demo 4",
        "primary_field": "Experiment ID",
        "env_key": "DEMO_TABLE_HOOK_EXPERIMENTS",
        "fields": [
            {"name": "Variation Idx", "type": "number", "options": {"precision": 0}},
            {"name": "Platform", "type": "singleSelect", "options": {"choices": PLATFORM_CHOICES}},
            {"name": "Angle", "type": "singleSelect", "options": {"choices": ANGLE_CHOICES}},
            {"name": "Hook", "type": "multilineText"},
            {"name": "CTA", "type": "singleLineText"},
            {"name": "Idea", "type": "multilineText"},
            {"name": "Is Winner", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Winner Rationale", "type": "multilineText"},
            {"name": "Score 24h", "type": "number", "options": {"precision": 3}},
            {"name": "Impressions", "type": "number", "options": {"precision": 0}},
            {"name": "Engagement Rate", "type": "number", "options": {"precision": 2}},
            {"name": "Created At", "type": "dateTime", "options": DATETIME_OPTS},
        ],
    },
    "DEMO_Comment_Leads": {
        "description": "Comment Lead Miner — AI-scored social comments from Demo 3",
        "primary_field": "Comment ID",
        "env_key": "DEMO_TABLE_COMMENT_LEADS",
        "fields": [
            {"name": "Run ID", "type": "singleLineText"},
            {"name": "Platform", "type": "singleSelect", "options": {"choices": PLATFORM_CHOICES}},
            {"name": "Post URL", "type": "url"},
            {"name": "Username", "type": "singleLineText"},
            {"name": "Comment Text", "type": "multilineText"},
            {"name": "Intent Score", "type": "number", "options": {"precision": 0}},
            {"name": "Category", "type": "singleSelect", "options": {"choices": CATEGORY_CHOICES}},
            {"name": "Tier", "type": "singleSelect", "options": {"choices": TIER_CHOICES}},
            {"name": "Reasoning", "type": "multilineText"},
            {"name": "Suggested Reply", "type": "multilineText"},
            {"name": "Likes", "type": "number", "options": {"precision": 0}},
            {"name": "Source", "type": "singleSelect", "options": {"choices": LEAD_SOURCE_CHOICES}},
            {"name": "Commented At", "type": "dateTime", "options": DATETIME_OPTS},
            {"name": "Created At", "type": "dateTime", "options": DATETIME_OPTS},
        ],
    },
    "DEMO_Video_Clips": {
        "description": "Video Clip Factory — per-clip output + captions from Demo 1",
        "primary_field": "Video ID",
        "env_key": "DEMO_TABLE_VIDEO_CLIPS",
        "fields": [
            {"name": "Title", "type": "singleLineText"},
            {"name": "Source URL", "type": "url"},
            {"name": "Segment Idx", "type": "number", "options": {"precision": 0}},
            {"name": "Start Sec", "type": "number", "options": {"precision": 0}},
            {"name": "End Sec", "type": "number", "options": {"precision": 0}},
            {"name": "Duration Sec", "type": "number", "options": {"precision": 0}},
            {"name": "Hook", "type": "multilineText"},
            {"name": "Summary", "type": "multilineText"},
            {"name": "Retention Score", "type": "number", "options": {"precision": 0}},
            {"name": "Clip URL", "type": "url"},
            {"name": "Caption TikTok", "type": "multilineText"},
            {"name": "Caption Instagram", "type": "multilineText"},
            {"name": "Caption YouTube", "type": "multilineText"},
            {"name": "Caption LinkedIn", "type": "multilineText"},
            {"name": "Source", "type": "singleSelect", "options": {"choices": CLIP_SOURCE_CHOICES}},
            {"name": "Created At", "type": "dateTime", "options": DATETIME_OPTS},
        ],
    },
    "DEMO_UGC_Campaigns": {
        "description": "UGC Ops Autopilot — campaign header records from Demo 2",
        "primary_field": "Campaign ID",
        "env_key": "DEMO_TABLE_UGC_CAMPAIGNS",
        "fields": [
            {"name": "Brand", "type": "singleLineText"},
            {"name": "Product Name", "type": "singleLineText"},
            {"name": "Product Brief", "type": "multilineText"},
            {"name": "Niche", "type": "singleLineText"},
            {"name": "Deliverables", "type": "singleLineText"},
            {"name": "Budget Per Creator", "type": "number", "options": {"precision": 0}},
            {"name": "Quantity", "type": "number", "options": {"precision": 0}},
            {"name": "Status", "type": "singleSelect", "options": {"choices": STATUS_UGC_CAMPAIGN}},
            {"name": "Created At", "type": "dateTime", "options": DATETIME_OPTS},
        ],
    },
    "DEMO_UGC_Creators": {
        "description": "UGC Ops Autopilot — scored creators per campaign from Demo 2",
        "primary_field": "Creator Row ID",
        "env_key": "DEMO_TABLE_UGC_CREATORS",
        "fields": [
            {"name": "Campaign ID", "type": "singleLineText"},
            {"name": "Handle", "type": "singleLineText"},
            {"name": "Platform", "type": "singleSelect", "options": {"choices": PLATFORM_CHOICES}},
            {"name": "Followers", "type": "number", "options": {"precision": 0}},
            {"name": "Avg Views", "type": "number", "options": {"precision": 0}},
            {"name": "Engagement Rate", "type": "number", "options": {"precision": 2}},
            {"name": "Niche", "type": "singleLineText"},
            {"name": "Sample Post", "type": "multilineText"},
            {"name": "Email", "type": "email"},
            {"name": "Rate Card", "type": "number", "options": {"precision": 0}},
            {"name": "Fit Score", "type": "number", "options": {"precision": 0}},
            {"name": "Fit Reasoning", "type": "multilineText"},
            {"name": "Outreach Subject", "type": "singleLineText"},
            {"name": "Outreach Body", "type": "multilineText"},
            {"name": "Status", "type": "singleSelect", "options": {"choices": STATUS_UGC_CREATOR}},
            {"name": "Source", "type": "singleSelect", "options": {"choices": CREATOR_SOURCE_CHOICES}},
            {"name": "Created At", "type": "dateTime", "options": DATETIME_OPTS},
        ],
    },
    "DEMO_UGC_Outreach": {
        "description": "UGC Ops Autopilot — outreach message log from Demo 2",
        "primary_field": "Outreach Row ID",
        "env_key": "DEMO_TABLE_UGC_OUTREACH",
        "fields": [
            {"name": "Campaign ID", "type": "singleLineText"},
            {"name": "Handle", "type": "singleLineText"},
            {"name": "Email", "type": "email"},
            {"name": "Subject", "type": "singleLineText"},
            {"name": "Body", "type": "multilineText"},
            {"name": "Status", "type": "singleSelect", "options": {"choices": STATUS_UGC_OUTREACH}},
            {"name": "Message ID", "type": "singleLineText"},
            {"name": "Sent At", "type": "dateTime", "options": DATETIME_OPTS},
        ],
    },
}


ONLY_KEYS: dict[str, list[str]] = {
    "hook": ["DEMO_Hook_Experiments"],
    "comment": ["DEMO_Comment_Leads"],
    "video": ["DEMO_Video_Clips"],
    "ugc": ["DEMO_UGC_Campaigns", "DEMO_UGC_Creators", "DEMO_UGC_Outreach"],
}


# ==================================================================
# HELPERS
# ==================================================================


def get_headers() -> dict[str, str]:
    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not set in .env")
        sys.exit(1)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def create_table(table_name: str, table_def: dict) -> str | None:
    headers = get_headers()

    fields: list[dict] = [{"name": table_def["primary_field"], "type": "singleLineText"}]
    for f in table_def["fields"]:
        row = {"name": f["name"], "type": f["type"]}
        if "options" in f:
            row["options"] = f["options"]
        fields.append(row)

    payload = {
        "name": table_name,
        "description": table_def.get("description", ""),
        "fields": fields,
    }

    url = f"{AIRTABLE_META_API}/{MARKETING_BASE_ID}/tables"
    resp = httpx.post(url, headers=headers, json=payload, timeout=30)

    if resp.status_code == 200:
        tid = resp.json()["id"]
        print(f"  CREATED  {table_name}  → {tid}")
        return tid
    if resp.status_code == 422 and "DUPLICATE_TABLE_NAME" in resp.text:
        print(f"  EXISTS   {table_name}  (skipping)")
        return None
    print(f"  ERROR    {table_name}  → {resp.status_code}")
    print(f"           {resp.text[:300]}")
    return None


# ==================================================================
# MAIN
# ==================================================================


def main() -> None:
    args = sys.argv[1:]
    only: list[str] = []
    if "--only" in args:
        idx = args.index("--only")
        if idx + 1 < len(args):
            keys = [k.strip().lower() for k in args[idx + 1].split(",") if k.strip()]
            for k in keys:
                if k in ONLY_KEYS:
                    only.extend(ONLY_KEYS[k])
                else:
                    print(f"Unknown --only key: {k} (allowed: hook, comment, video, ugc)")
                    sys.exit(1)

    target = list(TABLE_DEFINITIONS.keys()) if not only else only

    print("=" * 60)
    print("DEMO WORKFLOWS — AIRTABLE SETUP")
    print("=" * 60)
    print(f"Base: {MARKETING_BASE_ID}")
    print(f"Tables: {', '.join(target)}")
    print()

    created: dict[str, str] = {}
    for name in target:
        tid = create_table(name, TABLE_DEFINITIONS[name])
        if tid:
            created[name] = tid

    print()
    print("=" * 60)
    if created:
        print("Add these to your .env file:")
        print()
        for name, tid in created.items():
            env_key = TABLE_DEFINITIONS[name]["env_key"]
            print(f"  {env_key}={tid}")
        print()
        print("Then redeploy the demo workflow(s) so they pick up the IDs.")
    else:
        print("No new tables created (all may already exist).")
    print("=" * 60)


if __name__ == "__main__":
    main()

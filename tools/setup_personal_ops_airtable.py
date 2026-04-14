"""
Personal Ops / AVM Coach — Airtable Base Setup Tool

Creates 6 gamification tables (PP_*) in the existing Marketing Department Airtable
base for the AVM Coach system (PP-01 through PP-05 workflows).

Extends the Marketing base (apptjjBx34z9340tK) rather than creating a new one.

Tables:
    PP_Player               — Player stats (XP, level, streak, difficulty) — single row
    PP_Missions             — Daily mission board (the gamified task list)
    PP_XP_Log               — Immutable audit log of every XP change
    PP_Achievements         — Unlockable badges
    PP_Boss_Battles         — Weekly high-impact challenges
    PP_Performance_Snapshots — Daily aggregates for adaptive difficulty tuning

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. MARKETING_AIRTABLE_BASE_ID set in .env

Usage:
    python tools/setup_personal_ops_airtable.py              # Create all tables
    python tools/setup_personal_ops_airtable.py --seed       # Create tables + seed Ian as Player + starter achievements
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MARKETING_BASE_ID: str = os.getenv("MARKETING_AIRTABLE_BASE_ID", "")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

LAUNCH_DATE = "2026-04-22"  # Day 1 of the 100 Day Challenge


TABLE_DEFINITIONS: dict[str, dict] = {
    "PP_Player": {
        "description": "Player stats: XP, level, streak, current difficulty. Single-row table for Ian.",
        "primary_field": "Player ID",
        "fields": [
            {"name": "Display Name", "type": "singleLineText"},
            {"name": "Current XP", "type": "number", "options": {"precision": 0}},
            {"name": "Lifetime XP", "type": "number", "options": {"precision": 0}},
            {"name": "Level", "type": "number", "options": {"precision": 0}},
            {"name": "Current Streak Days", "type": "number", "options": {"precision": 0}},
            {"name": "Longest Streak", "type": "number", "options": {"precision": 0}},
            {"name": "Last Active Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {
                "name": "Current Difficulty",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Easy", "color": "greenBright"},
                        {"name": "Normal", "color": "blueBright"},
                        {"name": "Hard", "color": "orangeBright"},
                        {"name": "Legendary", "color": "redBright"},
                    ]
                },
            },
            {"name": "Weekly Boss Active", "type": "checkbox", "options": {"icon": "check", "color": "yellowBright"}},
            {"name": "Joined At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "PP_Missions": {
        "description": "Daily mission board — gamified tasks generated from Google Calendar + AI.",
        "primary_field": "Mission ID",
        "fields": [
            {"name": "Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Title", "type": "singleLineText"},
            {"name": "Description", "type": "multilineText"},
            {
                "name": "Category",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Revenue", "color": "redBright"},
                        {"name": "Growth", "color": "yellowBright"},
                        {"name": "Build", "color": "blueBright"},
                        {"name": "Learning", "color": "greenBright"},
                        {"name": "Maintenance", "color": "grayBright"},
                    ]
                },
            },
            {
                "name": "Tier",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Must-Complete", "color": "redBright"},
                        {"name": "High-Value", "color": "orangeBright"},
                        {"name": "Optional", "color": "blueBright"},
                    ]
                },
            },
            {"name": "XP Value", "type": "number", "options": {"precision": 0}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Pending", "color": "grayBright"},
                        {"name": "In_Progress", "color": "yellowBright"},
                        {"name": "Complete", "color": "greenBright"},
                        {"name": "Skipped", "color": "blueBright"},
                        {"name": "Failed", "color": "redBright"},
                    ]
                },
            },
            {"name": "Est. Minutes", "type": "number", "options": {"precision": 0}},
            {"name": "Calendar Event ID", "type": "singleLineText"},
            {
                "name": "Scheduled Start",
                "type": "dateTime",
                "options": {
                    "dateFormat": {"name": "iso"},
                    "timeFormat": {"name": "24hour"},
                    "timeZone": "Africa/Johannesburg",
                },
            },
            {
                "name": "Scheduled End",
                "type": "dateTime",
                "options": {
                    "dateFormat": {"name": "iso"},
                    "timeFormat": {"name": "24hour"},
                    "timeZone": "Africa/Johannesburg",
                },
            },
            {
                "name": "Source",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "AI_Generated", "color": "blueBright"},
                        {"name": "Manual", "color": "grayBright"},
                        {"name": "Calendar_Import", "color": "purpleBright"},
                        {"name": "Boss_Battle", "color": "redBright"},
                    ]
                },
            },
            {
                "name": "Linked 100Day Theme",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Mon_Metrics", "color": "blueBright"},
                        {"name": "Tue_Tutorial", "color": "greenBright"},
                        {"name": "Wed_Win", "color": "yellowBright"},
                        {"name": "Thu_Thought", "color": "purpleBright"},
                        {"name": "Fri_Fails", "color": "orangeBright"},
                        {"name": "Sat_Strategy", "color": "tealBright"},
                        {"name": "Sun_Story", "color": "pinkBright"},
                    ]
                },
            },
            {
                "name": "Completed At",
                "type": "dateTime",
                "options": {
                    "dateFormat": {"name": "iso"},
                    "timeFormat": {"name": "24hour"},
                    "timeZone": "Africa/Johannesburg",
                },
            },
            {"name": "Reflection Note", "type": "multilineText"},
        ],
    },
    "PP_XP_Log": {
        "description": "Immutable audit log of every XP event (mission complete, bonuses, penalties).",
        "primary_field": "Log ID",
        "fields": [
            {
                "name": "Timestamp",
                "type": "dateTime",
                "options": {
                    "dateFormat": {"name": "iso"},
                    "timeFormat": {"name": "24hour"},
                    "timeZone": "Africa/Johannesburg",
                },
            },
            {"name": "Mission Ref", "type": "singleLineText"},
            {
                "name": "Event Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Mission_Complete", "color": "greenBright"},
                        {"name": "Streak_Bonus", "color": "yellowBright"},
                        {"name": "Boss_Bonus", "color": "redBright"},
                        {"name": "Achievement_Unlock", "color": "purpleBright"},
                        {"name": "Penalty", "color": "grayBright"},
                        {"name": "Difficulty_Tune", "color": "blueBright"},
                    ]
                },
            },
            {"name": "XP Delta", "type": "number", "options": {"precision": 0}},
            {"name": "Multiplier Applied", "type": "number", "options": {"precision": 2}},
            {"name": "Running XP After", "type": "number", "options": {"precision": 0}},
            {"name": "Notes", "type": "singleLineText"},
        ],
    },
    "PP_Achievements": {
        "description": "Unlockable badges that fire when specific conditions are met.",
        "primary_field": "Achievement Key",
        "fields": [
            {"name": "Display Name", "type": "singleLineText"},
            {"name": "Description", "type": "multilineText"},
            {"name": "Icon Emoji", "type": "singleLineText"},
            {"name": "XP Reward", "type": "number", "options": {"precision": 0}},
            {"name": "Unlock Condition", "type": "multilineText"},
            {"name": "Unlocked", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {
                "name": "Unlocked At",
                "type": "dateTime",
                "options": {
                    "dateFormat": {"name": "iso"},
                    "timeFormat": {"name": "24hour"},
                    "timeZone": "Africa/Johannesburg",
                },
            },
            {
                "name": "Category",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Revenue", "color": "redBright"},
                        {"name": "Growth", "color": "yellowBright"},
                        {"name": "Build", "color": "blueBright"},
                        {"name": "Learning", "color": "greenBright"},
                        {"name": "Streak", "color": "orangeBright"},
                        {"name": "Meta", "color": "purpleBright"},
                    ]
                },
            },
        ],
    },
    "PP_Boss_Battles": {
        "description": "Weekly high-impact challenges tied to the 100 Day Challenge revenue ladder.",
        "primary_field": "Boss ID",
        "fields": [
            {"name": "Week Start", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Title", "type": "singleLineText"},
            {"name": "Narrative", "type": "multilineText"},
            {
                "name": "Category",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Revenue", "color": "redBright"},
                        {"name": "Growth", "color": "yellowBright"},
                        {"name": "Build", "color": "blueBright"},
                        {"name": "Learning", "color": "greenBright"},
                    ]
                },
            },
            {"name": "Target Metric", "type": "singleLineText"},
            {"name": "Current Progress", "type": "number", "options": {"precision": 0}},
            {"name": "XP Reward", "type": "number", "options": {"precision": 0}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Preview", "color": "grayBright"},
                        {"name": "Active", "color": "yellowBright"},
                        {"name": "Won", "color": "greenBright"},
                        {"name": "Failed", "color": "redBright"},
                    ]
                },
            },
            {
                "name": "Linked 100Day Phase",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Phase_1_Foundation_W1-4", "color": "blueBright"},
                        {"name": "Phase_2_Proof_W5-8", "color": "greenBright"},
                        {"name": "Phase_3_Scale_W9-12", "color": "yellowBright"},
                        {"name": "Phase_4_Push_W13-14", "color": "redBright"},
                    ]
                },
            },
            {
                "name": "Created By",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "AI_Generated", "color": "blueBright"},
                        {"name": "Manual", "color": "grayBright"},
                    ]
                },
            },
        ],
    },
    "PP_Performance_Snapshots": {
        "description": "Daily aggregates powering adaptive difficulty tuning.",
        "primary_field": "Snapshot ID",
        "fields": [
            {"name": "Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Missions Assigned", "type": "number", "options": {"precision": 0}},
            {"name": "Missions Completed", "type": "number", "options": {"precision": 0}},
            {"name": "Completion Rate", "type": "percent", "options": {"precision": 1}},
            {"name": "Total XP Earned", "type": "number", "options": {"precision": 0}},
            {"name": "Avg XP Per Mission", "type": "number", "options": {"precision": 1}},
            {"name": "Revenue Missions Completed", "type": "number", "options": {"precision": 0}},
            {"name": "Growth Missions Completed", "type": "number", "options": {"precision": 0}},
            {"name": "Build Missions Completed", "type": "number", "options": {"precision": 0}},
            {
                "name": "Hardest Tier Hit",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Optional", "color": "blueBright"},
                        {"name": "High-Value", "color": "orangeBright"},
                        {"name": "Must-Complete", "color": "redBright"},
                    ]
                },
            },
            {
                "name": "Difficulty At Snapshot",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Easy", "color": "greenBright"},
                        {"name": "Normal", "color": "blueBright"},
                        {"name": "Hard", "color": "orangeBright"},
                        {"name": "Legendary", "color": "redBright"},
                    ]
                },
            },
        ],
    },
}


ENV_KEY_MAP: dict[str, str] = {
    "PP_Player": "PP_TABLE_PLAYER",
    "PP_Missions": "PP_TABLE_MISSIONS",
    "PP_XP_Log": "PP_TABLE_XP_LOG",
    "PP_Achievements": "PP_TABLE_ACHIEVEMENTS",
    "PP_Boss_Battles": "PP_TABLE_BOSS_BATTLES",
    "PP_Performance_Snapshots": "PP_TABLE_PERF_SNAPSHOTS",
}


SEED_PLAYER: dict[str, object] = {
    "Player ID": "ian-immelman",
    "Display Name": "Ian Immelman",
    "Current XP": 0,
    "Lifetime XP": 0,
    "Level": 1,
    "Current Streak Days": 0,
    "Longest Streak": 0,
    "Current Difficulty": "Normal",
    "Weekly Boss Active": False,
    "Joined At": datetime.now().strftime("%Y-%m-%d"),
}


SEED_ACHIEVEMENTS: list[dict[str, object]] = [
    {
        "Achievement Key": "first_steps",
        "Display Name": "First Steps",
        "Description": "Complete your first mission.",
        "Icon Emoji": "👟",
        "XP Reward": 25,
        "Unlock Condition": '{"event":"mission_complete","count":1}',
        "Category": "Meta",
    },
    {
        "Achievement Key": "revenue_hunter_1",
        "Display Name": "Revenue Hunter",
        "Description": "Complete 10 Revenue missions.",
        "Icon Emoji": "💰",
        "XP Reward": 100,
        "Unlock Condition": '{"category":"Revenue","count":10}',
        "Category": "Revenue",
    },
    {
        "Achievement Key": "content_machine",
        "Display Name": "Content Machine",
        "Description": "Complete 3+ Growth missions in a single day.",
        "Icon Emoji": "🎬",
        "XP Reward": 75,
        "Unlock Condition": '{"category":"Growth","count_in_day":3}',
        "Category": "Growth",
    },
    {
        "Achievement Key": "automation_architect",
        "Display Name": "Automation Architect",
        "Description": "Ship or improve one n8n workflow.",
        "Icon Emoji": "🤖",
        "XP Reward": 100,
        "Unlock Condition": '{"category":"Build","count":1}',
        "Category": "Build",
    },
    {
        "Achievement Key": "streak_week_1",
        "Display Name": "Consistency I",
        "Description": "Hit a 7-day completion streak.",
        "Icon Emoji": "🔥",
        "XP Reward": 150,
        "Unlock Condition": '{"streak_days":7}',
        "Category": "Streak",
    },
    {
        "Achievement Key": "streak_week_2",
        "Display Name": "Consistency II",
        "Description": "Hit a 14-day completion streak.",
        "Icon Emoji": "🔥",
        "XP Reward": 300,
        "Unlock Condition": '{"streak_days":14}',
        "Category": "Streak",
    },
    {
        "Achievement Key": "level_5",
        "Display Name": "Level 5 Operator",
        "Description": "Reach level 5 (2,500 lifetime XP).",
        "Icon Emoji": "⭐",
        "XP Reward": 200,
        "Unlock Condition": '{"level":5}',
        "Category": "Meta",
    },
    {
        "Achievement Key": "boss_slayer_1",
        "Display Name": "Boss Slayer",
        "Description": "Win your first Weekly Boss Battle.",
        "Icon Emoji": "🏆",
        "XP Reward": 250,
        "Unlock Condition": '{"boss_wins":1}',
        "Category": "Meta",
    },
    {
        "Achievement Key": "launch_day",
        "Display Name": "Launch Day",
        "Description": "Survive Day 1 of the 100 Day Challenge.",
        "Icon Emoji": "🚀",
        "XP Reward": 500,
        "Unlock Condition": '{"date":"2026-04-22","rate":0.8}',
        "Category": "Meta",
    },
]


def create_table(
    client: httpx.Client,
    token: str,
    base_id: str,
    table_name: str,
    table_def: dict,
) -> tuple[str | None, int | str]:
    """Create a table with a stub 'Name' primary field, then rename to primary_field.

    Returns (table_id, field_count) on success, (None, error_msg) on failure.
    """
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

    if resp.status_code != 200:
        return None, resp.text[:300]

    table_data = resp.json()
    table_id = table_data["id"]
    field_count = len(table_data.get("fields", []))

    primary_name = table_def.get("primary_field", "Name")
    if primary_name != "Name":
        primary_field_id = table_data["fields"][0]["id"]
        rename_resp = client.patch(
            f"{AIRTABLE_META_API}/{base_id}/tables/{table_id}/fields/{primary_field_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"name": primary_name},
        )
        if rename_resp.status_code != 200:
            print(f"    Warning: primary field rename failed ({rename_resp.status_code}): {rename_resp.text[:200]}")

    return table_id, field_count


def seed_player(client: httpx.Client, token: str, base_id: str, table_id: str) -> int:
    """Seed the single PP_Player row for Ian."""
    resp = client.post(
        f"{AIRTABLE_API}/{base_id}/{table_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"records": [{"fields": SEED_PLAYER}]},
    )
    if resp.status_code == 200:
        return len(resp.json().get("records", []))
    print(f"    Player seed error: {resp.status_code} - {resp.text[:300]}")
    return 0


def seed_achievements(client: httpx.Client, token: str, base_id: str, table_id: str) -> int:
    """Seed the starter achievement catalog (batched by 10)."""
    records = [{"fields": dict(a)} for a in SEED_ACHIEVEMENTS]
    resp = client.post(
        f"{AIRTABLE_API}/{base_id}/{table_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"records": records},
    )
    if resp.status_code == 200:
        return len(resp.json().get("records", []))
    print(f"    Achievements seed error: {resp.status_code} - {resp.text[:300]}")
    return 0


def main() -> None:
    seed_mode = "--seed" in sys.argv

    print("=" * 60)
    print("PERSONAL OPS / AVM COACH — AIRTABLE SETUP")
    print("=" * 60)
    print()

    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    base_id = MARKETING_BASE_ID
    if not base_id:
        print("ERROR: MARKETING_AIRTABLE_BASE_ID not set in .env")
        sys.exit(1)

    print(f"Base ID:         {base_id}")
    print(f"Launch date:     {LAUNCH_DATE} (Day 1 of 100 Day Challenge)")
    print(f"Tables to create: {len(TABLE_DEFINITIONS)}")
    print(f"Seed mode:       {'ON' if seed_mode else 'OFF'}")
    print()

    client = httpx.Client(timeout=30)
    created_tables: dict[str, str] = {}

    print("Creating tables...")
    print("-" * 40)
    for table_name, table_def in TABLE_DEFINITIONS.items():
        table_id, result = create_table(client, token, base_id, table_name, table_def)
        if table_id:
            created_tables[table_name] = table_id
            print(f"  + {table_name:<30} -> {table_id} ({result} fields)")
        else:
            print(f"  - {table_name:<30} FAILED: {result}")
    print()

    if seed_mode and created_tables:
        print("Seeding data...")
        print("-" * 40)
        if "PP_Player" in created_tables:
            n = seed_player(client, token, base_id, created_tables["PP_Player"])
            print(f"  + PP_Player:       {n} record(s) (Ian Immelman, Level 1, Normal)")
        if "PP_Achievements" in created_tables:
            n = seed_achievements(client, token, base_id, created_tables["PP_Achievements"])
            print(f"  + PP_Achievements: {n} record(s) starter catalog")
        print()

    client.close()

    print("=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print()
    print(f"Created: {len(created_tables)}/{len(TABLE_DEFINITIONS)} tables")
    print()

    if created_tables:
        print("Table IDs (add these to .env):")
        print("-" * 40)
        for name, tid in created_tables.items():
            env_key = ENV_KEY_MAP.get(name, name.upper())
            print(f"  {env_key}={tid}")
        print()
        print(f"  PP_GCAL_ID=primary")
        print(f"  PP_TELEGRAM_CHAT_ID=6311361442")
        print(f"  PP_LAUNCH_DATE={LAUNCH_DATE}")
        print()

        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "personal_ops_airtable_ids.json"

        ids_data = {
            "base_id": base_id,
            "tables": {ENV_KEY_MAP.get(name, name): tid for name, tid in created_tables.items()},
            "launch_date": LAUNCH_DATE,
            "created_at": datetime.now().isoformat(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ids_data, f, indent=2)
        print(f"Table IDs saved to: {output_path}")

    print()
    print("Next steps:")
    print("  1. Copy the PP_TABLE_* lines above into .env")
    print("  2. Write the Claude Code skill at ~/.claude/skills/avm-coach/")
    print("  3. Build PP-01 morning mission board workflow via tools/deploy_personal_ops_dept.py")


if __name__ == "__main__":
    main()

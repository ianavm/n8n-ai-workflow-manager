"""
Social Media Builds — Airtable Base Setup.

Creates a standalone Airtable base named "Social Media Builds" that holds all
tables used by the three social-media demo workflows:

    MCB_Missed_Calls  — Twilio missed-call log        (Workflow 3)
    IA_Inbox_Log      — AI email triage audit trail   (Workflow 2)
    SL_Leads          — Speed-to-Lead demo lead rows  (Workflow 1)

The existing production `Leads` table in the Marketing base is intentionally
NOT moved — it is written to by live workflows (Website Contact Form, SEO
Lead Capture). Speed-to-Lead gets its own isolated demo table here.

Prerequisites:
    AIRTABLE_API_TOKEN set in .env with scopes:
        data.records:read, data.records:write, schema.bases:write
    The token's user must have access to the Airtable workspace below.

Usage:
    python tools/setup_social_media_builds_base.py         # create + seed
    python tools/setup_social_media_builds_base.py --dry   # print what would be created
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)

# Workspace the base will live in. Looked up via:
#   GET /v0/meta/bases/{existingBaseId} -> workspaceId
# Change if you want the base in a different Airtable workspace.
WORKSPACE_ID = os.getenv("AIRTABLE_WORKSPACE_ID", "wsphbx1QkB2KEz53y")
BASE_NAME = "Social Media Builds"

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

DATETIME_OPTIONS = {
    "dateFormat": {"name": "iso"},
    "timeFormat": {"name": "24hour"},
    "timeZone": "Africa/Johannesburg",
}
DATE_OPTIONS = {"dateFormat": {"name": "iso"}}

# -- Select choices --

CALL_STATUS_CHOICES = [
    {"name": "no-answer", "color": "redBright"},
    {"name": "busy", "color": "orangeBright"},
    {"name": "failed", "color": "redDark1"},
    {"name": "canceled", "color": "grayBright"},
    {"name": "completed", "color": "greenBright"},
]
CALL_WINDOW_CHOICES = [
    {"name": "business-hours", "color": "greenBright"},
    {"name": "after-hours", "color": "blueBright"},
]
MCB_STATUS_CHOICES = [
    {"name": "SMS Sent", "color": "cyanBright"},
    {"name": "Reply Received", "color": "greenBright"},
    {"name": "Booked", "color": "greenDark1"},
    {"name": "No Reply", "color": "grayBright"},
    {"name": "Opted Out", "color": "redBright"},
]
INBOX_CATEGORY_CHOICES = [
    {"name": "URGENT", "color": "redBright"},
    {"name": "CLIENT", "color": "greenBright"},
    {"name": "SALES", "color": "blueBright"},
    {"name": "BILLING", "color": "yellowBright"},
    {"name": "NOISE", "color": "grayBright"},
]
INBOX_ACTION_CHOICES = [
    {"name": "Starred", "color": "yellowBright"},
    {"name": "Draft Created", "color": "blueBright"},
    {"name": "Archived", "color": "grayBright"},
    {"name": "Logged Only", "color": "grayDark1"},
    {"name": "Skipped", "color": "grayDark1"},
]
# Replicate the production Leads schema so SL_Leads is schema-compatible
# with any future merge back into the main Leads table.
LEAD_SOURCE_CHANNEL_CHOICES = [
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
LEAD_STATUS_CHOICES = [
    {"name": "New", "color": "blueBright"},
    {"name": "Contacted", "color": "yellowBright"},
    {"name": "Qualified", "color": "greenBright"},
    {"name": "Converted", "color": "greenDark1"},
    {"name": "Lost", "color": "redBright"},
]
LEAD_SOURCE_SYSTEM_CHOICES = [
    {"name": "Outbound_Scraper", "color": "blueBright"},
    {"name": "SEO_Inbound", "color": "greenBright"},
    {"name": "Email_Inbound", "color": "orangeBright"},
]
LEAD_GRADE_CHOICES = [
    {"name": "Hot", "color": "redBright"},
    {"name": "Warm", "color": "orangeBright"},
    {"name": "Cold", "color": "blueBright"},
]


# -- Table schemas (shape expected by POST /meta/bases) --

TABLES_PAYLOAD = [
    {
        "name": "MCB_Missed_Calls",
        "description": (
            "Missed-call auto-responder log for Workflow 3 (Missed Call Money "
            "Back). One row per Twilio status callback flagged as unanswered."
        ),
        "fields": [
            {"name": "Call ID", "type": "singleLineText"},
            {"name": "From Phone", "type": "phoneNumber"},
            {"name": "To Phone", "type": "phoneNumber"},
            {"name": "Call Status", "type": "singleSelect",
             "options": {"choices": CALL_STATUS_CHOICES}},
            {"name": "Call Window", "type": "singleSelect",
             "options": {"choices": CALL_WINDOW_CHOICES}},
            {"name": "Is Repeat Caller", "type": "checkbox",
             "options": {"color": "blueBright", "icon": "check"}},
            {"name": "SMS Body", "type": "multilineText"},
            {"name": "SMS SID", "type": "singleLineText"},
            {"name": "Status", "type": "singleSelect",
             "options": {"choices": MCB_STATUS_CHOICES}},
            {"name": "Reply Text", "type": "multilineText"},
            {"name": "Received At", "type": "dateTime",
             "options": DATETIME_OPTIONS},
        ],
    },
    {
        "name": "IA_Inbox_Log",
        "description": (
            "Audit trail for Workflow 2 (Inbox Autopilot). One row per "
            "classified email with category, summary, and action taken."
        ),
        "fields": [
            {"name": "Log ID", "type": "singleLineText"},
            {"name": "Message ID", "type": "singleLineText"},
            {"name": "From", "type": "singleLineText"},
            {"name": "Subject", "type": "singleLineText"},
            {"name": "Category", "type": "singleSelect",
             "options": {"choices": INBOX_CATEGORY_CHOICES}},
            {"name": "Summary", "type": "multilineText"},
            {"name": "Suggested Reply", "type": "multilineText"},
            {"name": "Action", "type": "singleSelect",
             "options": {"choices": INBOX_ACTION_CHOICES}},
            {"name": "Urgent Flagged", "type": "checkbox",
             "options": {"color": "redBright", "icon": "star"}},
            {"name": "Processed At", "type": "dateTime",
             "options": DATETIME_OPTIONS},
        ],
    },
    {
        "name": "SL_Leads",
        "description": (
            "Demo Leads table for Workflow 1 (5-Minute Lead Responder). "
            "Schema-compatible with the production Leads table in the "
            "Marketing base so demo records can be merged upstream if wanted."
        ),
        "fields": [
            {"name": "Lead ID", "type": "singleLineText"},
            {"name": "Contact Name", "type": "singleLineText"},
            {"name": "Email", "type": "email"},
            {"name": "Phone", "type": "phoneNumber"},
            {"name": "Company", "type": "singleLineText"},
            {"name": "Source Channel", "type": "singleSelect",
             "options": {"choices": LEAD_SOURCE_CHANNEL_CHOICES}},
            {"name": "Source URL", "type": "url"},
            {"name": "UTM Source", "type": "singleLineText"},
            {"name": "UTM Medium", "type": "singleLineText"},
            {"name": "UTM Campaign", "type": "singleLineText"},
            {"name": "First Touch Content", "type": "singleLineText"},
            {"name": "Notes", "type": "multilineText"},
            {"name": "Status", "type": "singleSelect",
             "options": {"choices": LEAD_STATUS_CHOICES}},
            {"name": "Source System", "type": "singleSelect",
             "options": {"choices": LEAD_SOURCE_SYSTEM_CHOICES}},
            {"name": "Grade", "type": "singleSelect",
             "options": {"choices": LEAD_GRADE_CHOICES}},
            {"name": "Created At", "type": "date", "options": DATE_OPTIONS},
        ],
    },
]


def get_headers() -> dict[str, str]:
    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not set in .env")
        sys.exit(1)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def base_already_exists(name: str) -> str | None:
    """Return the ID of an existing base with this name, else None."""
    r = httpx.get(
        f"{AIRTABLE_META_API}",
        headers=get_headers(),
        timeout=20,
    )
    if r.status_code != 200:
        return None
    for b in r.json().get("bases", []):
        if b.get("name", "").strip().lower() == name.strip().lower():
            return b["id"]
    return None


def create_base() -> tuple[str, dict[str, str]]:
    """Create the base. Returns (base_id, {table_name: table_id})."""
    payload = {
        "name": BASE_NAME,
        "workspaceId": WORKSPACE_ID,
        "tables": TABLES_PAYLOAD,
    }
    r = httpx.post(
        AIRTABLE_META_API,
        headers=get_headers(),
        json=payload,
        timeout=60,
    )
    if r.status_code != 200:
        print(f"  ERROR creating base: {r.status_code}")
        print(f"  Response: {r.text[:600]}")
        sys.exit(1)

    data = r.json()
    base_id = data["id"]
    table_ids = {t["name"]: t["id"] for t in data.get("tables", [])}
    print(f"  Created base: {base_id}")
    for name, tid in table_ids.items():
        print(f"    Table: {name:<22} {tid}")
    return base_id, table_ids


def seed_samples(base_id: str, table_ids: dict[str, str]) -> None:
    """Insert one demo row per table so empty-table checks pass."""
    headers = get_headers()
    now_iso = datetime.now().isoformat()
    today_iso = datetime.now().date().isoformat()

    seeds = {
        "MCB_Missed_Calls": [
            {
                "fields": {
                    "Call ID": "MCB-DEMO-0001",
                    "From Phone": "+27821234567",
                    "To Phone": "+27109876543",
                    "Call Status": "no-answer",
                    "Call Window": "business-hours",
                    "Is Repeat Caller": False,
                    "SMS Body": (
                        "Hey! Sorry I missed your call — I'm on a job right "
                        "now. What can I help you with? I'll text back in 10 "
                        "min."
                    ),
                    "SMS SID": "SMdemo0000000000000000000000000001",
                    "Status": "SMS Sent",
                    "Received At": now_iso,
                }
            }
        ],
        "IA_Inbox_Log": [
            {
                "fields": {
                    "Log ID": "IA-DEMO-0001",
                    "Message ID": "demo-message-id-000",
                    "From": "prospective.client@example.com",
                    "Subject": "Interested in your automation services",
                    "Category": "SALES",
                    "Summary": "Prospect asking about pricing for a 3-workflow build.",
                    "Suggested Reply": (
                        "Thanks for reaching out! Happy to run you through a "
                        "15-min discovery call — here's my calendar link: ..."
                    ),
                    "Action": "Draft Created",
                    "Urgent Flagged": False,
                    "Processed At": now_iso,
                }
            }
        ],
        "SL_Leads": [
            {
                "fields": {
                    "Lead ID": "SL-DEMO-0001",
                    "Contact Name": "Demo Lead",
                    "Email": "demo.lead@example.com",
                    "Phone": "+27821234567",
                    "Company": "Demo Corp",
                    "Source Channel": "Organic",
                    "Source URL": "https://www.anyvisionmedia.com/",
                    "UTM Source": "instagram",
                    "UTM Medium": "social",
                    "UTM Campaign": "demo-video",
                    "First Touch Content": "speed-to-lead demo",
                    "Notes": "Seed row from setup_social_media_builds_base.py",
                    "Status": "New",
                    "Source System": "SEO_Inbound",
                    "Grade": "Warm",
                    "Created At": today_iso,
                }
            }
        ],
    }

    for table_name, records in seeds.items():
        table_id = table_ids.get(table_name)
        if not table_id:
            continue
        r = httpx.post(
            f"{AIRTABLE_API}/{base_id}/{table_id}",
            headers=headers,
            json={"records": records},
            timeout=30,
        )
        if r.status_code == 200:
            print(f"    Seeded 1 row in {table_name}")
        else:
            print(f"    WARN seed failed for {table_name} ({r.status_code}): {r.text[:200]}")


def main() -> None:
    dry = "--dry" in sys.argv

    print("=" * 62)
    print("SOCIAL MEDIA BUILDS — AIRTABLE BASE SETUP")
    print("=" * 62)
    print(f"Workspace: {WORKSPACE_ID}")
    print(f"Base name: {BASE_NAME}")
    print()

    if dry:
        print("Dry run — no changes will be made.")
        print(f"Would create {len(TABLES_PAYLOAD)} tables:")
        for t in TABLES_PAYLOAD:
            print(f"  {t['name']} ({len(t['fields'])} fields)")
        return

    existing = base_already_exists(BASE_NAME)
    if existing:
        print(f"Base '{BASE_NAME}' already exists at id {existing}.")
        print("Delete it in the Airtable UI first if you want a fresh base.")
        print("Exiting without changes.")
        sys.exit(0)

    print("Creating base...")
    base_id, table_ids = create_base()
    print()
    print("Seeding sample rows...")
    seed_samples(base_id, table_ids)
    print()

    print("=" * 62)
    print("SETUP COMPLETE")
    print("=" * 62)
    print()
    print("Add these to your .env:")
    print()
    print(f"  SOCIAL_BUILDS_BASE_ID={base_id}")
    env_map = {
        "MCB_Missed_Calls": "DEMO_MCB_TABLE",
        "IA_Inbox_Log": "DEMO_IA_TABLE",
        "SL_Leads": "DEMO_LEAD_TABLE",
    }
    for table_name, env_key in env_map.items():
        tid = table_ids.get(table_name, "<missing>")
        print(f"  {env_key}={tid}")
    print()
    print("Then redeploy:")
    print("  python tools/deploy_demo_workflows.py deploy")


if __name__ == "__main__":
    main()

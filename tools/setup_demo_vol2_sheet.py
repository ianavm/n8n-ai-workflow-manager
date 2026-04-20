"""Create the master ``AVM_Demo_Pack_Vol2`` Google Sheet with all 9 demo tabs.

The Vol. 2 demo workflows (DEMO-05 through DEMO-13) all read from and write
to a single spreadsheet. This script provisions that spreadsheet end-to-end:

    1. Authenticates against Google Sheets + Drive via a service-account key
       (``GOOGLE_APPLICATION_CREDENTIALS`` env var, same convention used
       elsewhere in the repo).
    2. Creates (or reuses) a spreadsheet titled ``AVM_Demo_Pack_Vol2``.
    3. Ensures all 9 tabs exist with the canonical header row.
    4. Seeds ``Demo_Control`` with the default toggle rows.
    5. Prints the ``DEMO_SHEET_VOL2_ID`` env var to paste into ``.env``.

Idempotent: re-running only creates what is missing. Safe to re-run after
schema tweaks.

Usage::

    python tools/setup_demo_vol2_sheet.py

Required env::

    GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
    # optional — if set, reuse rather than create:
    DEMO_SHEET_VOL2_ID=<existing-sheet-id>
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

SHEET_TITLE = "AVM_Demo_Pack_Vol2"


@dataclass(frozen=True)
class TabSpec:
    name: str
    headers: tuple[str, ...]
    seed_rows: tuple[tuple[str, ...], ...] = ()


TABS: tuple[TabSpec, ...] = (
    TabSpec(
        "Leads_Log",
        ("Timestamp", "Name", "Email", "Source", "Intent",
         "AI_Reply_Preview", "Status", "Run_ID", "Workflow"),
    ),
    TabSpec(
        "Meeting_Actions",
        ("Timestamp", "Meeting_Title", "Attendees", "Action_Item",
         "Owner", "Due_Date", "Status", "Run_ID"),
    ),
    TabSpec(
        "CRM_Clients",
        ("Client_ID", "Name", "Company", "Email", "Phone",
         "Last_Contacted", "Ask", "Status", "Notes", "Run_ID"),
    ),
    TabSpec(
        "Follow_Ups",
        ("Follow_Up_ID", "Related_Record", "Contact", "Scheduled_For",
         "Type", "Status", "Last_Action", "Notes"),
    ),
    TabSpec(
        "Quotes_Log",
        ("Quote_ID", "Company", "Origin", "Destination", "Weight_Kg",
         "Pallets", "Estimate_ZAR", "Sent_At", "Status", "Contact_Email"),
    ),
    TabSpec(
        "Reminders",
        ("Reminder_ID", "Topic", "Due_At", "Owner",
         "Source_Workflow", "Status", "Notes"),
    ),
    TabSpec(
        "Gmail_Drafts_Log",
        ("Timestamp", "Thread_ID", "From", "Subject",
         "Draft_Preview", "Approved", "Run_ID"),
    ),
    TabSpec(
        "Audit_Log",
        ("Workflow", "Run_ID", "Timestamp", "Action",
         "Status", "Error_Message"),
    ),
    TabSpec(
        "Demo_Control",
        ("Param", "Value", "Notes"),
        seed_rows=(
            ("demo_mode", "1", "Global demo mode toggle — 1 = fixture, 0 = live"),
            ("slack_enabled", "1", "Post to Slack webhook when high-intent matches"),
            ("send_real_emails", "0", "Gmail send vs draft-only during demo"),
        ),
    ),
)


def _load_services():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Missing google-api-python-client + google-auth. Install with:\n"
            "  pip install google-api-python-client google-auth"
        ) from exc

    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not Path(creds_path).exists():
        raise SystemExit(
            "GOOGLE_APPLICATION_CREDENTIALS not set or file missing. "
            "Point it at a service-account JSON key with Drive + Sheets scope."
        )

    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return (
        build("sheets", "v4", credentials=creds, cache_discovery=False),
        build("drive", "v3", credentials=creds, cache_discovery=False),
    )


def _ensure_spreadsheet(sheets_svc, drive_svc) -> str:
    existing_id = os.getenv("DEMO_SHEET_VOL2_ID")
    if existing_id:
        print(f"Reusing existing sheet: {existing_id}")
        return existing_id

    body = {"properties": {"title": SHEET_TITLE}}
    result = sheets_svc.spreadsheets().create(body=body, fields="spreadsheetId").execute()
    sheet_id = result["spreadsheetId"]
    print(f"Created spreadsheet '{SHEET_TITLE}' => {sheet_id}")

    share_with = os.getenv("DEMO_SHEET_SHARE_WITH")
    if share_with:
        drive_svc.permissions().create(
            fileId=sheet_id,
            body={"type": "user", "role": "writer", "emailAddress": share_with},
            sendNotificationEmail=False,
        ).execute()
        print(f"Shared with {share_with} as writer")

    return sheet_id


def _existing_tabs(sheets_svc, sheet_id: str) -> dict[str, int]:
    meta = sheets_svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    return {s["properties"]["title"]: s["properties"]["sheetId"]
            for s in meta["sheets"]}


def _ensure_tab(sheets_svc, sheet_id: str, tab: TabSpec, existing: dict[str, int]) -> None:
    if tab.name in existing:
        print(f"  [skip] {tab.name} already exists")
    else:
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab.name}}}]},
        ).execute()
        print(f"  [new]  {tab.name}")

    # Always (idempotently) reset the header row.
    sheets_svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{tab.name}!A1",
        valueInputOption="RAW",
        body={"values": [list(tab.headers)]},
    ).execute()

    if tab.seed_rows:
        sheets_svc.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{tab.name}!A2",
            valueInputOption="RAW",
            body={"values": [list(row) for row in tab.seed_rows]},
        ).execute()


def _drop_default_sheet1(sheets_svc, sheet_id: str) -> None:
    """New spreadsheets ship with a default ``Sheet1`` — remove it if unused."""

    existing = _existing_tabs(sheets_svc, sheet_id)
    if "Sheet1" not in existing:
        return
    # Only delete if it still has the default generated state — skip if renamed.
    try:
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"deleteSheet": {"sheetId": existing["Sheet1"]}}]},
        ).execute()
        print("  [cleanup] removed default Sheet1")
    except Exception as exc:  # pragma: no cover
        print(f"  [cleanup] skipped Sheet1 removal: {exc}")


def main() -> int:
    sheets_svc, drive_svc = _load_services()
    sheet_id = _ensure_spreadsheet(sheets_svc, drive_svc)

    existing = _existing_tabs(sheets_svc, sheet_id)
    print("\nProvisioning tabs...")
    for tab in TABS:
        _ensure_tab(sheets_svc, sheet_id, tab, existing)
        existing = _existing_tabs(sheets_svc, sheet_id)

    _drop_default_sheet1(sheets_svc, sheet_id)

    print("\n" + "=" * 60)
    print("Setup complete. Add this line to your .env:")
    print(f"  DEMO_SHEET_VOL2_ID={sheet_id}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

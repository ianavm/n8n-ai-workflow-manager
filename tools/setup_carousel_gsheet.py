"""Create the ``AVM Carousel Engine`` Google Sheet used by SC-07.

SC-07 (``tools/deploy_sc07_carousel_engine.py``) is sheet-driven: each row
in the ``Carousels`` tab is one carousel, and the workflow polls the sheet
every 5 minutes for rows marked ``Approved`` that are ready to ship.

This script provisions that sheet end-to-end:

    1. Authenticates via a service-account key
       (``GOOGLE_APPLICATION_CREDENTIALS`` -- same convention as
       ``tools/setup_demo_vol2_sheet.py``).
    2. Creates or reuses a spreadsheet titled ``AVM Carousel Engine``.
    3. Ensures ``Carousels``, ``Post Log`` and ``Errors`` tabs exist with
       the canonical header row.
    4. Adds a ``Status`` dropdown (data validation) on the Carousels tab.
    5. Prints the ``CAROUSEL_GSHEET_ID`` env var to paste into ``.env``.

Idempotent: re-running only creates what is missing. Safe after schema edits.

Usage::

    python tools/setup_carousel_gsheet.py

Required env::

    GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
    # optional -- if set, reuse rather than create:
    CAROUSEL_GSHEET_ID=<existing-sheet-id>
    # optional -- share with a specific user:
    CAROUSEL_SHEET_SHARE_WITH=ian@anyvisionmedia.com
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


SHEET_TITLE = "AVM Carousel Engine"

STATUS_OPTIONS = ("Draft", "Approved", "Posting", "Posted", "Failed", "Paused")


@dataclass(frozen=True)
class TabSpec:
    name: str
    headers: tuple[str, ...]
    seed_rows: tuple[tuple[str, ...], ...] = ()
    status_column: int | None = None  # zero-based index for Status dropdown


CAROUSEL_HEADERS: tuple[str, ...] = (
    "Carousel ID",
    "Title",
    "Status",
    "Scheduled At",
    "Image URLs",
    "IG Caption",
    "LI Caption",
    "FB Caption",
    "Hashtags IG",
    "Hashtags LI",
    "Approved By",
    "Approved At",
    "Posted At",
    "Blotato Schedule IDs",
    "Last Error",
    "Retry Count",
)

POST_LOG_HEADERS: tuple[str, ...] = (
    "Log ID",
    "Carousel ID",
    "Platform",
    "Status",
    "Blotato Schedule ID",
    "Scheduled At",
    "Response Summary",
    "Error",
    "Created At",
)

ERRORS_HEADERS: tuple[str, ...] = (
    "Carousel ID",
    "Platform",
    "Error",
    "Payload",
    "Created At",
)


TABS: tuple[TabSpec, ...] = (
    TabSpec(
        name="Carousels",
        headers=CAROUSEL_HEADERS,
        status_column=CAROUSEL_HEADERS.index("Status"),
    ),
    TabSpec(name="Post Log", headers=POST_LOG_HEADERS),
    TabSpec(name="Errors", headers=ERRORS_HEADERS),
)


def _load_services():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:
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
    existing_id = os.getenv("CAROUSEL_GSHEET_ID")
    if existing_id and "REPLACE" not in existing_id:
        logger.info("Reusing existing sheet: %s", existing_id)
        return existing_id

    body = {"properties": {"title": SHEET_TITLE}}
    result = sheets_svc.spreadsheets().create(body=body, fields="spreadsheetId").execute()
    sheet_id = result["spreadsheetId"]
    logger.info("Created spreadsheet '%s' => %s", SHEET_TITLE, sheet_id)

    share_with = os.getenv("CAROUSEL_SHEET_SHARE_WITH")
    if share_with:
        drive_svc.permissions().create(
            fileId=sheet_id,
            body={"type": "user", "role": "writer", "emailAddress": share_with},
            sendNotificationEmail=False,
        ).execute()
        logger.info("Shared with %s as writer", share_with)

    return sheet_id


def _existing_tabs(sheets_svc, sheet_id: str) -> dict[str, int]:
    meta = sheets_svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    return {
        s["properties"]["title"]: s["properties"]["sheetId"]
        for s in meta["sheets"]
    }


def _ensure_tab(sheets_svc, sheet_id: str, tab: TabSpec, existing: dict[str, int]) -> None:
    if tab.name in existing:
        logger.info("  [skip] %s already exists", tab.name)
    else:
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab.name}}}]},
        ).execute()
        logger.info("  [new]  %s", tab.name)

    # Always reset header row idempotently.
    sheets_svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{tab.name}'!A1",
        valueInputOption="RAW",
        body={"values": [list(tab.headers)]},
    ).execute()

    if tab.seed_rows:
        sheets_svc.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{tab.name}'!A2",
            valueInputOption="RAW",
            body={"values": [list(row) for row in tab.seed_rows]},
        ).execute()


def _add_status_validation(
    sheets_svc,
    sheet_id: str,
    tab_name: str,
    sheet_tab_id: int,
    col_index: int,
) -> None:
    """Add a Status dropdown to col `col_index` on tab `sheet_tab_id`."""

    request = {
        "setDataValidation": {
            "range": {
                "sheetId": sheet_tab_id,
                "startRowIndex": 1,  # skip header
                "startColumnIndex": col_index,
                "endColumnIndex": col_index + 1,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": v} for v in STATUS_OPTIONS],
                },
                "strict": True,
                "showCustomUi": True,
            },
        }
    }
    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [request]},
    ).execute()
    logger.info("  [validation] Status dropdown added on '%s'!%s", tab_name, chr(ord('A') + col_index))


def _freeze_header_row(sheets_svc, sheet_id: str, sheet_tab_id: int) -> None:
    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={
            "requests": [{
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_tab_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            }]
        },
    ).execute()


def _drop_default_sheet1(sheets_svc, sheet_id: str) -> None:
    existing = _existing_tabs(sheets_svc, sheet_id)
    if "Sheet1" not in existing:
        return
    try:
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"deleteSheet": {"sheetId": existing["Sheet1"]}}]},
        ).execute()
        logger.info("  [cleanup] removed default Sheet1")
    except Exception as exc:
        logger.info("  [cleanup] skipped Sheet1 removal: %s", exc)


def main() -> int:
    sheets_svc, drive_svc = _load_services()
    sheet_id = _ensure_spreadsheet(sheets_svc, drive_svc)

    existing = _existing_tabs(sheets_svc, sheet_id)
    logger.info("\nProvisioning tabs...")
    for tab in TABS:
        _ensure_tab(sheets_svc, sheet_id, tab, existing)
        existing = _existing_tabs(sheets_svc, sheet_id)

        sheet_tab_id = existing[tab.name]
        _freeze_header_row(sheets_svc, sheet_id, sheet_tab_id)
        if tab.status_column is not None:
            _add_status_validation(
                sheets_svc, sheet_id, tab.name, sheet_tab_id, tab.status_column
            )

    _drop_default_sheet1(sheets_svc, sheet_id)

    logger.info("\n%s", "=" * 60)
    logger.info("Setup complete. Add this line to your .env:")
    logger.info("  CAROUSEL_GSHEET_ID=%s", sheet_id)
    logger.info("%s", "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

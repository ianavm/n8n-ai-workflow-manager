"""
Gmail label verifier for the Business Email Management workflow.

Lists all Gmail labels on ian@anyvisionmedia.com, compares each against the
expected IDs used by tools/deploy_business_email_mgmt.py, and prints a status
table. Optionally creates any missing named labels and prints the new IDs so
they can be pasted into .env.

Usage:
    python tools/verify_gmail_labels.py                 # read-only audit
    python tools/verify_gmail_labels.py --create-missing  # create missing labels
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.insert(0, str(Path(__file__).parent))
from google_auth import GoogleAuthenticator

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass


GMAIL_LABELS_SCOPE = "https://www.googleapis.com/auth/gmail.labels"


@dataclass(frozen=True)
class LabelSpec:
    """Expected Gmail label — display name plus the env var carrying its ID."""
    display_name: str
    env_var: str
    default_id: str


EXPECTED_LABELS: tuple[LabelSpec, ...] = (
    LabelSpec("Finance", "EMAIL_LABEL_FINANCE", "Label_1"),
    LabelSpec("Support", "EMAIL_LABEL_SUPPORT", "Label_2"),
    LabelSpec("Sales", "EMAIL_LABEL_SALES", "Label_3"),
    LabelSpec("Management", "EMAIL_LABEL_MANAGEMENT", "Label_4"),
    LabelSpec("General", "EMAIL_LABEL_GENERAL", "Label_5"),
    LabelSpec("Urgent", "EMAIL_LABEL_URGENT", "Label_7"),
    LabelSpec("Junk", "EMAIL_LABEL_JUNK", "Label_8"),
    LabelSpec("DNT", "EMAIL_LABEL_DNT", "Label_9"),
    LabelSpec("n8n", "EMAIL_LABEL_N8N", "Label_10"),
)


def get_gmail_service():
    """Authenticate with gmail.labels scope (separate token file to avoid
    disturbing the existing send-only token)."""
    project_root = Path(__file__).parent.parent
    token_path = project_root / "token_gmail_labels.json"
    auth = GoogleAuthenticator(
        credentials_path=str(project_root / "credentials.json"),
        token_path=str(token_path),
        scopes=[GMAIL_LABELS_SCOPE],
    )
    creds = auth.authenticate()
    return build("gmail", "v1", credentials=creds)


def fetch_live_labels(service) -> dict[str, dict]:
    """Return {name_lower: label_dict} for every label on the account."""
    response = service.users().labels().list(userId="me").execute()
    return {lbl["name"].lower(): lbl for lbl in response.get("labels", [])}


def audit_labels(live: dict[str, dict]) -> list[tuple[LabelSpec, str, str, str]]:
    """For each expected label, produce (spec, expected_id, live_id, status)."""
    rows: list[tuple[LabelSpec, str, str, str]] = []
    for spec in EXPECTED_LABELS:
        expected_id = os.getenv(spec.env_var, spec.default_id)
        live_entry = live.get(spec.display_name.lower())
        if not live_entry:
            rows.append((spec, expected_id, "—", "MISSING"))
            continue
        live_id = live_entry["id"]
        status = "OK" if live_id == expected_id else "ID DRIFT"
        rows.append((spec, expected_id, live_id, status))
    return rows


def print_table(rows: list[tuple[LabelSpec, str, str, str]]) -> None:
    print()
    print(f"{'NAME':<14}{'ENV VAR':<26}{'EXPECTED':<14}{'LIVE':<14}STATUS")
    print("-" * 82)
    for spec, expected, live_id, status in rows:
        print(
            f"{spec.display_name:<14}"
            f"{spec.env_var:<26}"
            f"{expected:<14}"
            f"{live_id:<14}"
            f"{status}"
        )
    print()


def print_orphans(live: dict[str, dict]) -> None:
    """List user-created labels not referenced by the workflow."""
    expected_names = {s.display_name.lower() for s in EXPECTED_LABELS}
    orphans = [
        lbl for name, lbl in live.items()
        if lbl.get("type") == "user" and name not in expected_names
    ]
    if not orphans:
        return
    print("Orphan user labels (exist in Gmail, not referenced by workflow):")
    for lbl in orphans:
        print(f"  - {lbl['name']}  ({lbl['id']})")
    print()


def create_missing(service, rows: list[tuple[LabelSpec, str, str, str]]) -> None:
    """Create any MISSING labels and print the new IDs."""
    missing = [spec for spec, _, _, status in rows if status == "MISSING"]
    if not missing:
        print("No missing labels to create.")
        return
    print("Creating missing labels...")
    for spec in missing:
        try:
            result = service.users().labels().create(
                userId="me",
                body={
                    "name": spec.display_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            ).execute()
            print(f"  Created {spec.display_name} -> {result['id']}")
            print(f"    Add to .env:  {spec.env_var}={result['id']}")
        except HttpError as err:
            print(f"  Failed to create {spec.display_name}: {err}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--create-missing",
        action="store_true",
        help="Create any MISSING labels and print their new IDs.",
    )
    args = parser.parse_args()

    try:
        service = get_gmail_service()
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        return 1

    live = fetch_live_labels(service)
    rows = audit_labels(live)
    print_table(rows)
    print_orphans(live)

    drifted = [r for r in rows if r[3] == "ID DRIFT"]
    if drifted:
        print("Labels with ID drift — update .env:")
        for spec, _, live_id, _ in drifted:
            print(f"  {spec.env_var}={live_id}")
        print()

    if args.create_missing:
        create_missing(service, rows)

    missing_count = sum(1 for r in rows if r[3] == "MISSING")
    drift_count = len(drifted)
    if missing_count or drift_count:
        print(f"Result: {missing_count} missing, {drift_count} drifted.")
        return 2
    print(f"Result: all {len(EXPECTED_LABELS)} labels OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

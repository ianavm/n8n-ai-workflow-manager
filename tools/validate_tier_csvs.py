"""Validate Tier 2 + Tier 3 import CSVs are structurally sound.

Since Airtable API is quota-blocked, this validates the source files rather than
the imported records. Checks: CSV parses cleanly, no duplicate Lead IDs, all
singleSelect fields use known-good values, Source Metadata is valid JSON per row.

Usage:
    python tools/validate_tier_csvs.py
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("csv_validate")

ROOT = Path(__file__).parent.parent
FILES = [
    ROOT / "workflows" / "linkedin-dept" / "tier2-import.csv",
    ROOT / "workflows" / "linkedin-dept" / "tier3-import.csv",
]

EXPECTED_FIELDS = {
    "Lead ID", "Full Name", "First Name", "Last Name", "Title",
    "Company Name", "Industry", "Location", "LinkedIn URL",
    "Company Website", "Employee Count", "Source", "Status",
    "POPIA Consent", "Source Metadata",
}

VALID_SOURCE = {"CSV_Upload"}  # Must match existing Airtable options
VALID_STATUS = {"New"}
VALID_POPIA = {"Pending"}


def validate_file(path: Path) -> tuple[int, list[str]]:
    """Returns (record_count, list_of_issues)."""
    issues: list[str] = []
    seen_ids: set[str] = set()
    record_count = 0

    if not path.exists():
        return 0, [f"File not found: {path}"]

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            return 0, ["File has no header row"]

        field_set = set(reader.fieldnames)
        missing = EXPECTED_FIELDS - field_set
        extra = field_set - EXPECTED_FIELDS
        if missing:
            issues.append(f"Missing fields: {sorted(missing)}")
        if extra:
            issues.append(f"Unexpected fields: {sorted(extra)}")

        for row_num, row in enumerate(reader, start=2):
            record_count += 1
            lead_id = row.get("Lead ID", "").strip()
            if not lead_id:
                issues.append(f"Row {row_num}: missing Lead ID")
                continue

            if lead_id in seen_ids:
                issues.append(f"Row {row_num}: duplicate Lead ID '{lead_id}'")
            seen_ids.add(lead_id)

            source = row.get("Source", "").strip()
            if source not in VALID_SOURCE:
                issues.append(f"Row {row_num} ({lead_id}): invalid Source '{source}'")

            status = row.get("Status", "").strip()
            if status not in VALID_STATUS:
                issues.append(f"Row {row_num} ({lead_id}): invalid Status '{status}'")

            popia = row.get("POPIA Consent", "").strip()
            if popia not in VALID_POPIA:
                issues.append(f"Row {row_num} ({lead_id}): invalid POPIA Consent '{popia}'")

            metadata = row.get("Source Metadata", "").strip()
            if not metadata:
                issues.append(f"Row {row_num} ({lead_id}): empty Source Metadata")
            else:
                try:
                    parsed = json.loads(metadata)
                    if not isinstance(parsed, dict):
                        issues.append(f"Row {row_num} ({lead_id}): Source Metadata is not a JSON object")
                    elif not parsed.get("tier"):
                        issues.append(f"Row {row_num} ({lead_id}): metadata missing 'tier' field")
                except json.JSONDecodeError as exc:
                    issues.append(f"Row {row_num} ({lead_id}): invalid JSON in Source Metadata: {exc}")

            full = row.get("Full Name", "").strip()
            if not full:
                issues.append(f"Row {row_num} ({lead_id}): missing Full Name")

            co = row.get("Company Name", "").strip()
            if not co:
                issues.append(f"Row {row_num} ({lead_id}): missing Company Name")

    return record_count, issues


def main() -> int:
    total_records = 0
    total_issues = 0
    all_ids: dict[str, Path] = {}

    for f in FILES:
        print()
        print("=" * 70)
        print(f"  {f.name}")
        print("=" * 70)

        n, issues = validate_file(f)
        total_records += n
        print(f"  Records: {n}")

        if issues:
            total_issues += len(issues)
            print(f"  Issues ({len(issues)}):")
            for i in issues:
                print(f"    - {i}")
        else:
            print("  [OK] Clean — no structural issues")

        # Track IDs across files for cross-file duplicates
        try:
            with f.open("r", newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    lid = row.get("Lead ID", "").strip()
                    if lid and lid in all_ids and all_ids[lid] != f:
                        print(f"  [FAIL] CROSS-FILE duplicate Lead ID '{lid}' (also in {all_ids[lid].name})")
                        total_issues += 1
                    if lid:
                        all_ids[lid] = f
        except FileNotFoundError:
            pass

    print()
    print("-" * 70)
    print(f"  Total records across both CSVs: {total_records}")
    print(f"  Total issues: {total_issues}")
    if total_issues == 0:
        print("  [OK] Both CSVs are structurally valid and safe to import")
    print("-" * 70)

    return 0 if total_issues == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

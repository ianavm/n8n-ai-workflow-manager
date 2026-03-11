"""
Document Intake - Google Sheets Setup Script

Creates the tracking spreadsheet structure (6 tabs) and seeds Admin_Config.
Prints column headers for manual pasting or uses the Google Workspace MCP
server to create the sheet automatically.

Usage:
    python tools/setup_di_sheets.py --print-headers    # Print headers for manual setup
    python tools/setup_di_sheets.py --seed             # Print headers + seed Admin_Config data
"""

import sys
import json

# -- Tab Definitions -----------------------------------------------------

TABS = {
    "Document_Log": [
        "doc_id", "intake_timestamp", "sender_email", "sender_name",
        "email_subject", "original_filename", "file_hash_sha256",
        "file_size_bytes", "raw_drive_file_id", "raw_drive_url",
        "doc_type", "doc_type_confidence", "property_address",
        "erf_number", "unit_number", "scheme_name",
        "buyer_name", "seller_name", "agent_name",
        "transaction_date", "reference_number", "property_id",
        "final_drive_file_id", "final_drive_url",
        "status", "review_reason", "reviewed_by", "reviewed_at",
        "error_message",
    ],
    "Property_Registry": [
        "property_id", "display_address", "street_number", "street_name",
        "suburb", "city", "province", "erf_number", "unit_number",
        "scheme_name", "drive_folder_id", "drive_folder_url",
        "created_at", "doc_count", "last_doc_date",
    ],
    "Review_Queue": [
        "review_id", "doc_id", "reason", "ai_doc_type", "ai_confidence",
        "raw_drive_url", "original_filename", "sender_email",
        "assigned_to", "assigned_at", "status",
        "admin_action", "correct_doc_type", "correct_property_id",
        "admin_notes", "admin_email",
    ],
    "Audit_Log": [
        "audit_id", "timestamp", "actor", "action", "doc_id",
        "before_value", "after_value", "notes",
    ],
    "Admin_Config": [
        "config_key", "config_value", "description", "updated_at",
    ],
    "Duplicate_Log": [
        "dupe_id", "detected_at", "original_doc_id", "duplicate_doc_id",
        "file_hash", "sender_email", "original_filename", "action_taken",
    ],
}

# -- Admin_Config Seed Data -----------------------------------------------

ADMIN_CONFIG_SEED = [
    {
        "config_key": "confidence_threshold",
        "config_value": "0.75",
        "description": "Minimum AI confidence to auto-file (0.0-1.0)",
    },
    {
        "config_key": "incoming_folder_id",
        "config_value": "REPLACE_WITH_FOLDER_ID",
        "description": "Google Drive folder ID for Incoming_Documents/",
    },
    {
        "config_key": "properties_folder_id",
        "config_value": "REPLACE_WITH_FOLDER_ID",
        "description": "Google Drive folder ID for Properties/ root",
    },
    {
        "config_key": "notification_email",
        "config_value": "ian@anyvisionmedia.com",
        "description": "Email address for notifications and alerts",
    },
    {
        "config_key": "duplicate_action",
        "config_value": "flag",
        "description": "What to do with duplicates: flag or skip",
    },
    {
        "config_key": "max_pdf_pages",
        "config_value": "50",
        "description": "Maximum PDF pages to extract text from",
    },
]


def print_headers():
    """Print tab-separated headers for each sheet tab."""
    print("=" * 60)
    print("DOCUMENT INTAKE - GOOGLE SHEETS SETUP")
    print("=" * 60)
    print()
    print("Create a new Google Sheets spreadsheet named:")
    print("  'Real Estate Document Tracker'")
    print()
    print("Then create these 6 tabs and paste the headers into row 1:")
    print()

    for tab_name, columns in TABS.items():
        print(f"--- Tab: {tab_name} ({len(columns)} columns) ---")
        print("\t".join(columns))
        print()

    print("=" * 60)
    print("IMPORTANT: After creating the spreadsheet:")
    print("  1. Copy the spreadsheet ID from the URL")
    print("     URL format: https://docs.google.com/spreadsheets/d/{ID}/edit")
    print("  2. Set DI_SHEETS_ID in your .env file")
    print("  3. Set up data validation dropdowns on Review_Queue tab:")
    print("     - Column L (admin_action): approve, reclassify, create_property, flag_error")
    print("     - Column M (correct_doc_type): FICA, Offer_to_Purchase, Mandate, ...")
    print("=" * 60)


def print_seed_data():
    """Print seed data for Admin_Config tab."""
    print()
    print("--- Admin_Config Seed Data ---")
    print("Paste these rows into the Admin_Config tab (after the header row):")
    print()

    for row in ADMIN_CONFIG_SEED:
        print(f"{row['config_key']}\t{row['config_value']}\t{row['description']}\t")

    print()
    print("IMPORTANT: Replace the REPLACE_WITH_FOLDER_ID values with your")
    print("actual Google Drive folder IDs after creating the folders.")


def main():
    args = sys.argv[1:]

    if "--print-headers" in args or not args:
        print_headers()

    if "--seed" in args:
        print_headers()
        print_seed_data()

    if "--json" in args:
        # Output as JSON for programmatic use
        output = {
            "tabs": {name: cols for name, cols in TABS.items()},
            "seed": ADMIN_CONFIG_SEED,
        }
        print(json.dumps(output, indent=2))

    if not args:
        print()
        print("Usage:")
        print("  python tools/setup_di_sheets.py --print-headers")
        print("  python tools/setup_di_sheets.py --seed")
        print("  python tools/setup_di_sheets.py --json")


if __name__ == "__main__":
    main()

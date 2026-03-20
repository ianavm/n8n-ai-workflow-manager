"""
Accounting Department - Airtable Base Setup Tool

Creates all required tables in the Accounting Department Airtable base.
Follows the same pattern as setup_marketing_airtable.py.

Prerequisites:
    1. Create a new Airtable base called "Accounting Department" manually
    2. Set AIRTABLE_API_TOKEN in .env
    3. Set ACCOUNTING_AIRTABLE_BASE_ID in .env with your new base ID

Usage:
    python tools/setup_accounting_airtable.py              # Create all tables
    python tools/setup_accounting_airtable.py --seed        # Create tables + seed config data
"""

import os
import sys
import json
import httpx
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# ── Configuration ──────────────────────────────────────────────
ACCOUNTING_BASE_ID = os.getenv("ACCOUNTING_AIRTABLE_BASE_ID", "")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# ── Table Definitions ──────────────────────────────────────────

TABLE_DEFINITIONS = {
    "Customers": {
        "description": "Customer master data for invoicing and accounts receivable",
        "fields": [
            {"name": "Legal Name", "type": "singleLineText"},
            {"name": "Trading Name", "type": "singleLineText"},
            {"name": "Email", "type": "email"},
            {"name": "Phone", "type": "phoneNumber"},
            {"name": "Billing Address", "type": "multilineText"},
            {"name": "VAT Number", "type": "singleLineText"},
            {
                "name": "Default Payment Terms",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "COD", "color": "redBright"},
                        {"name": "7 days", "color": "orangeBright"},
                        {"name": "14 days", "color": "yellowBright"},
                        {"name": "30 days", "color": "greenBright"},
                        {"name": "60 days", "color": "blueBright"},
                    ]
                },
            },
            {"name": "Credit Limit", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {
                "name": "Risk Flag",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Low", "color": "greenBright"},
                        {"name": "Medium", "color": "yellowBright"},
                        {"name": "High", "color": "redBright"},
                    ]
                },
            },
            {
                "name": "Preferred Channel",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Email", "color": "blueBright"},
                        {"name": "WhatsApp", "color": "greenBright"},
                        {"name": "Both", "color": "purpleBright"},
                    ]
                },
            },
            {"name": "QuickBooks Customer ID", "type": "singleLineText"},
            {"name": "Active", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Suppliers": {
        "description": "Supplier master data for accounts payable and bill processing",
        "fields": [
            {"name": "VAT Number", "type": "singleLineText"},
            {"name": "Email", "type": "email"},
            {"name": "Phone", "type": "phoneNumber"},
            {"name": "Bank Details Hash", "type": "singleLineText"},
            {"name": "QuickBooks Customer ID", "type": "singleLineText"},
            {
                "name": "Default Category",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Software", "color": "blueBright"},
                        {"name": "Hosting", "color": "cyanBright"},
                        {"name": "Marketing", "color": "pinkBright"},
                        {"name": "Office", "color": "yellowBright"},
                        {"name": "Professional Services", "color": "purpleBright"},
                        {"name": "Travel", "color": "orangeBright"},
                        {"name": "Equipment", "color": "grayBright"},
                        {"name": "Other", "color": "grayDark1"},
                    ]
                },
            },
            {
                "name": "Payment Terms",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "COD", "color": "redBright"},
                        {"name": "7 days", "color": "orangeBright"},
                        {"name": "14 days", "color": "yellowBright"},
                        {"name": "30 days", "color": "greenBright"},
                    ]
                },
            },
            {"name": "Active", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Products Services": {
        "description": "Product and service catalog for invoice line items",
        "fields": [
            {"name": "Description", "type": "multilineText"},
            {"name": "Unit Price", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {
                "name": "VAT Rate Code",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "STANDARD_15", "color": "blueBright"},
                        {"name": "ZERO_RATED", "color": "greenBright"},
                        {"name": "EXEMPT", "color": "yellowBright"},
                    ]
                },
            },
            {"name": "Revenue Account Code", "type": "singleLineText"},
            {"name": "Cost Account Code", "type": "singleLineText"},
            {"name": "Active", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
        ],
    },
    "Invoices": {
        "description": "Invoice tracking for accounts receivable",
        "fields": [
            {"name": "Invoice Number", "type": "singleLineText"},
            {"name": "Customer ID", "type": "singleLineText"},
            {"name": "Customer Name", "type": "singleLineText"},
            {"name": "Issue Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Due Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Draft", "color": "grayBright"},
                        {"name": "Pending Approval", "color": "yellowBright"},
                        {"name": "Sent", "color": "blueBright"},
                        {"name": "Partial", "color": "orangeBright"},
                        {"name": "Paid", "color": "greenDark1"},
                        {"name": "Overdue", "color": "redBright"},
                        {"name": "Disputed", "color": "purpleBright"},
                        {"name": "Cancelled", "color": "grayDark1"},
                    ]
                },
            },
            {"name": "Subtotal", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "VAT Amount", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "Total", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "Amount Paid", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "Balance Due", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "Currency", "type": "singleLineText"},
            {"name": "Line Items JSON", "type": "multilineText"},
            {"name": "PDF URL", "type": "url"},
            {"name": "QuickBooks Invoice ID", "type": "singleLineText"},
            {
                "name": "Source",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "CRM", "color": "blueBright"},
                        {"name": "Web Form", "color": "greenBright"},
                        {"name": "WhatsApp", "color": "cyanBright"},
                        {"name": "Manual", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Reminder Count", "type": "number", "options": {"precision": 0}},
            {"name": "Last Reminder Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Next Reminder Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Dispute Reason", "type": "multilineText"},
            {"name": "Dispute Owner", "type": "singleLineText"},
            {"name": "Created By", "type": "singleLineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Sent At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Payments": {
        "description": "Payment records for reconciliation",
        "fields": [
            {"name": "Invoice Refs", "type": "singleLineText"},
            {"name": "Amount", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "Date Received", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {
                "name": "Method",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "EFT", "color": "blueBright"},
                        {"name": "Stripe", "color": "purpleBright"},
                        {"name": "PayFast", "color": "greenBright"},
                        {"name": "Cash", "color": "yellowBright"},
                        {"name": "Credit Card", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "Reference Text", "type": "singleLineText"},
            {
                "name": "Reconciliation Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Unmatched", "color": "redBright"},
                        {"name": "Matched", "color": "greenBright"},
                        {"name": "Partial Match", "color": "yellowBright"},
                        {"name": "Manual Review", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "QuickBooks Payment ID", "type": "singleLineText"},
            {"name": "Gateway Transaction ID", "type": "singleLineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Supplier Bills": {
        "description": "Supplier bill tracking for accounts payable",
        "fields": [
            {"name": "Supplier Name", "type": "singleLineText"},
            {"name": "Supplier Ref", "type": "singleLineText"},
            {"name": "Bill Number", "type": "singleLineText"},
            {"name": "Bill Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Due Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Subtotal", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "VAT Amount", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {"name": "Total Amount", "type": "currency", "options": {"precision": 2, "symbol": "R"}},
            {
                "name": "Category",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Software", "color": "blueBright"},
                        {"name": "Hosting", "color": "cyanBright"},
                        {"name": "Marketing", "color": "pinkBright"},
                        {"name": "Office", "color": "yellowBright"},
                        {"name": "Professional Services", "color": "purpleBright"},
                        {"name": "Travel", "color": "orangeBright"},
                        {"name": "Equipment", "color": "grayBright"},
                        {"name": "Other", "color": "grayDark1"},
                    ]
                },
            },
            {"name": "Cost Center", "type": "singleLineText"},
            {"name": "Attachment URL", "type": "url"},
            {"name": "OCR Raw JSON", "type": "multilineText"},
            {
                "name": "Approval Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Pending", "color": "yellowBright"},
                        {"name": "Auto Approved", "color": "greenBright"},
                        {"name": "Awaiting Approval", "color": "orangeBright"},
                        {"name": "Approved", "color": "greenDark1"},
                        {"name": "Rejected", "color": "redBright"},
                    ]
                },
            },
            {"name": "Approver", "type": "singleLineText"},
            {"name": "Approved At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {
                "name": "Payment Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Unpaid", "color": "redBright"},
                        {"name": "Scheduled", "color": "yellowBright"},
                        {"name": "Paid", "color": "greenDark1"},
                    ]
                },
            },
            {"name": "QuickBooks Bill ID", "type": "singleLineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Tasks": {
        "description": "Human task queue for approvals, exceptions, and escalations",
        "fields": [
            {
                "name": "Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Invoice Approval", "color": "blueBright"},
                        {"name": "Bill Approval", "color": "purpleBright"},
                        {"name": "Payment Reconciliation", "color": "greenBright"},
                        {"name": "Dispute Resolution", "color": "orangeBright"},
                        {"name": "Exception Review", "color": "redBright"},
                        {"name": "Month End Task", "color": "cyanBright"},
                    ]
                },
            },
            {
                "name": "Priority",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Low", "color": "grayBright"},
                        {"name": "Medium", "color": "yellowBright"},
                        {"name": "High", "color": "orangeBright"},
                        {"name": "Urgent", "color": "redBright"},
                    ]
                },
            },
            {"name": "Owner", "type": "singleLineText"},
            {
                "name": "Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Open", "color": "blueBright"},
                        {"name": "In Progress", "color": "yellowBright"},
                        {"name": "Completed", "color": "greenDark1"},
                        {"name": "Escalated", "color": "redBright"},
                    ]
                },
            },
            {"name": "Related Record ID", "type": "singleLineText"},
            {"name": "Related Table", "type": "singleLineText"},
            {"name": "Description", "type": "multilineText"},
            {"name": "Resolution Notes", "type": "multilineText"},
            {"name": "Approval Token", "type": "singleLineText"},
            {"name": "Due At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Completed At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Audit Log": {
        "description": "Immutable audit trail for all accounting actions",
        "fields": [
            {"name": "Workflow Name", "type": "singleLineText"},
            {
                "name": "Event Type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "INVOICE_CREATED", "color": "blueBright"},
                        {"name": "INVOICE_SENT", "color": "cyanBright"},
                        {"name": "INVOICE_UPDATED", "color": "yellowBright"},
                        {"name": "PAYMENT_RECEIVED", "color": "greenBright"},
                        {"name": "PAYMENT_RECONCILED", "color": "greenDark1"},
                        {"name": "BILL_CREATED", "color": "purpleBright"},
                        {"name": "BILL_APPROVED", "color": "purpleDark1"},
                        {"name": "BILL_PAID", "color": "tealBright"},
                        {"name": "REMINDER_SENT", "color": "orangeBright"},
                        {"name": "DISPUTE_OPENED", "color": "redBright"},
                        {"name": "DISPUTE_RESOLVED", "color": "redDark1"},
                        {"name": "QBO_SYNC", "color": "grayBright"},
                        {"name": "MONTH_END_CLOSE", "color": "grayDark1"},
                        {"name": "EXCEPTION", "color": "pinkBright"},
                        {"name": "MASTER_DATA_CHANGE", "color": "tealDark1"},
                    ]
                },
            },
            {"name": "Record Type", "type": "singleLineText"},
            {"name": "Record ID", "type": "singleLineText"},
            {"name": "Action Taken", "type": "multilineText"},
            {"name": "Actor", "type": "singleLineText"},
            {
                "name": "Result",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Success", "color": "greenBright"},
                        {"name": "Failed", "color": "redBright"},
                        {"name": "Partial", "color": "yellowBright"},
                    ]
                },
            },
            {"name": "Error Details", "type": "multilineText"},
            {"name": "Metadata JSON", "type": "multilineText"},
            {"name": "Created At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "System Config": {
        "description": "Key-value store for VAT rates, thresholds, approval rules, and runtime state",
        "fields": [
            {"name": "Value", "type": "multilineText"},
            {"name": "Updated At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated By", "type": "singleLineText"},
        ],
    },
}

# ── Seed Data ─────────────────────────────────────────────────

SYSTEM_CONFIG_SEEDS = [
    {
        "Key": "vat_standard_rate",
        "Value": json.dumps({"rate": 0.15, "code": "STANDARD_15", "label": "Standard 15%"}),
        "Updated By": "setup",
    },
    {
        "Key": "vat_zero_rate",
        "Value": json.dumps({"rate": 0.0, "code": "ZERO_RATED", "label": "Zero Rated"}),
        "Updated By": "setup",
    },
    {
        "Key": "vat_exempt",
        "Value": json.dumps({"rate": 0.0, "code": "EXEMPT", "label": "VAT Exempt"}),
        "Updated By": "setup",
    },
    {
        "Key": "approval_threshold",
        "Value": json.dumps({"auto_approve_below": 10000, "currency": "ZAR"}),
        "Updated By": "setup",
    },
    {
        "Key": "high_value_invoice_threshold",
        "Value": json.dumps({"threshold": 50000, "currency": "ZAR", "requires_approval": True}),
        "Updated By": "setup",
    },
    {
        "Key": "reminder_cadence",
        "Value": json.dumps({
            "t_minus_3": True, "due_date": True, "t_plus_3": True,
            "t_plus_7": True, "t_plus_14": True,
        }),
        "Updated By": "setup",
    },
    {
        "Key": "default_currency",
        "Value": json.dumps({"code": "ZAR", "symbol": "R", "country": "ZA"}),
        "Updated By": "setup",
    },
    {
        "Key": "company_details",
        "Value": json.dumps({
            "name": "AnyVision Media",
            "registration": "REPLACE",
            "vat_number": "REPLACE",
            "address": "Johannesburg, South Africa",
            "email": "accounts@anyvisionmedia.com",
            "bank_name": "REPLACE",
            "bank_account": "REPLACE",
            "bank_branch": "REPLACE",
        }),
        "Updated By": "setup",
    },
    {
        "Key": "invoice_prefix",
        "Value": json.dumps({"prefix": "AVM", "next_number": 1001}),
        "Updated By": "setup",
    },
    {
        "Key": "payfast_config",
        "Value": json.dumps({"merchant_id": "REPLACE", "passphrase": "REPLACE", "sandbox": True}),
        "Updated By": "setup",
    },
]

SAMPLE_PRODUCTS = [
    {
        "Item Code": "WEB-DEV",
        "Description": "Website Design & Development",
        "Unit Price": 15000,
        "VAT Rate Code": "STANDARD_15",
        "Revenue Account Code": "200",
        "Active": True,
    },
    {
        "Item Code": "AI-AUTO",
        "Description": "AI Workflow Automation Setup",
        "Unit Price": 25000,
        "VAT Rate Code": "STANDARD_15",
        "Revenue Account Code": "200",
        "Active": True,
    },
    {
        "Item Code": "SMM-MONTHLY",
        "Description": "Social Media Management (Monthly)",
        "Unit Price": 8000,
        "VAT Rate Code": "STANDARD_15",
        "Revenue Account Code": "200",
        "Active": True,
    },
    {
        "Item Code": "CONSULT-HR",
        "Description": "Consulting (per hour)",
        "Unit Price": 1500,
        "VAT Rate Code": "STANDARD_15",
        "Revenue Account Code": "200",
        "Active": True,
    },
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

        # Rename primary field to something table-specific
        primary_rename = {
            "Customers": "Customer ID",
            "Suppliers": "Supplier ID",
            "Products Services": "Item Code",
            "Invoices": "Invoice ID",
            "Payments": "Payment ID",
            "Supplier Bills": "Bill ID",
            "Tasks": "Task ID",
            "Audit Log": "Timestamp",
            "System Config": "Key",
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


def seed_system_config(client, token, base_id, table_id):
    """Seed system config with VAT rates, thresholds, and company details."""
    records = []
    for item in SYSTEM_CONFIG_SEEDS:
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


def seed_products(client, token, base_id, table_id):
    """Seed products/services catalog with sample items."""
    records = []
    for item in SAMPLE_PRODUCTS:
        records.append({
            "fields": {
                "Item Code": item["Item Code"],
                "Description": item["Description"],
                "Unit Price": item["Unit Price"],
                "VAT Rate Code": item["VAT Rate Code"],
                "Revenue Account Code": item["Revenue Account Code"],
                "Active": item["Active"],
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


def main():
    seed_mode = "--seed" in sys.argv

    print("=" * 60)
    print("ACCOUNTING DEPARTMENT - AIRTABLE SETUP")
    print("=" * 60)
    print()

    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    base_id = ACCOUNTING_BASE_ID
    if not base_id:
        print("ERROR: ACCOUNTING_AIRTABLE_BASE_ID not set.")
        print()
        print("Steps to fix:")
        print("  1. Go to https://airtable.com and create a new base called 'Accounting Department'")
        print("  2. Copy the base ID from the URL (starts with 'app...')")
        print("  3. Add to .env: ACCOUNTING_AIRTABLE_BASE_ID=appXXXXXXXXXX")
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

        if "System Config" in created_tables:
            count = seed_system_config(client, token, base_id, created_tables["System Config"])
            print(f"  + System Config: {count} records seeded (VAT rates, thresholds, company details)")

        if "Products Services" in created_tables:
            count = seed_products(client, token, base_id, created_tables["Products Services"])
            print(f"  + Products Services: {count} records seeded (sample services)")

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
        print("Add these to your .env file:")
        print("-" * 40)

        env_key_map = {
            "Customers": "ACCOUNTING_TABLE_CUSTOMERS",
            "Suppliers": "ACCOUNTING_TABLE_SUPPLIERS",
            "Products Services": "ACCOUNTING_TABLE_PRODUCTS_SERVICES",
            "Invoices": "ACCOUNTING_TABLE_INVOICES",
            "Payments": "ACCOUNTING_TABLE_PAYMENTS",
            "Supplier Bills": "ACCOUNTING_TABLE_SUPPLIER_BILLS",
            "Tasks": "ACCOUNTING_TABLE_TASKS",
            "Audit Log": "ACCOUNTING_TABLE_AUDIT_LOG",
            "System Config": "ACCOUNTING_TABLE_SYSTEM_CONFIG",
        }

        for name, tid in created_tables.items():
            env_key = env_key_map.get(name, name.upper().replace(" ", "_"))
            print(f"  {env_key}={tid}")

        print()

        # Save to .tmp for easy reference
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "accounting_airtable_ids.json"

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
    print("  1. Add table IDs to .env (shown above)")
    print("  2. Update config.json with the accounting_dept section")
    print("  3. Run: python tools/deploy_accounting_dept.py build")


if __name__ == "__main__":
    main()

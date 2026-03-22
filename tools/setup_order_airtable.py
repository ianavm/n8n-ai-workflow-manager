"""
WhatsApp Order-to-Invoice - Airtable Table Setup Tool

Creates 2 required tables in the Lead Scraper Airtable base
for the WhatsApp Order-to-Invoice automation system:
  - Order_Sessions: Tracks each customer ordering session state
  - Product_Catalog: Product inventory with prices synced from Xero

Uses the existing Lead Scraper base (app2ALQUP7CKEkHOz) which already
has client-facing tables.

Prerequisites:
    1. AIRTABLE_API_TOKEN set in .env
    2. ORDER_AIRTABLE_BASE_ID set in .env (default: app2ALQUP7CKEkHOz)

Usage:
    python tools/setup_order_airtable.py              # Create tables
    python tools/setup_order_airtable.py --seed        # Create tables + seed sample products
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

# -- Configuration --------------------------------------------------------
ORDER_BASE_ID = os.getenv("ORDER_AIRTABLE_BASE_ID", "app2ALQUP7CKEkHOz")

AIRTABLE_API = "https://api.airtable.com/v0"
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"

# -- Table Definitions -----------------------------------------------------

TABLE_DEFINITIONS = {
    "Order_Sessions": {
        "description": "Tracks each WhatsApp ordering session from category selection through invoice delivery",
        "primary_field": "Session_ID",
        "fields": [
            {"name": "Customer_Phone", "type": "singleLineText"},
            {"name": "Customer_Name", "type": "singleLineText"},
            {
                "name": "State",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "AWAITING_CATEGORY", "color": "blueBright"},
                        {"name": "AWAITING_SIZE", "color": "cyanBright"},
                        {"name": "AWAITING_QUANTITY", "color": "purpleBright"},
                        {"name": "QUOTE_CREATED", "color": "yellowBright"},
                        {"name": "PENDING_APPROVAL", "color": "orangeBright"},
                        {"name": "APPROVED", "color": "greenBright"},
                        {"name": "REJECTED", "color": "redBright"},
                        {"name": "INVOICE_SENT", "color": "greenDark1"},
                    ]
                },
            },
            {
                "name": "Selected_Category",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Polymailers", "color": "blueBright"},
                        {"name": "Boxes", "color": "orangeBright"},
                        {"name": "Tapes", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Selected_Size", "type": "singleLineText"},
            {"name": "Selected_Quantity", "type": "number", "options": {"precision": 0}},
            {"name": "Xero_Item_Code", "type": "singleLineText"},
            {"name": "Xero_Contact_ID", "type": "singleLineText"},
            {"name": "Xero_Quote_ID", "type": "singleLineText"},
            {"name": "Xero_Quote_Number", "type": "singleLineText"},
            {"name": "Xero_Invoice_ID", "type": "singleLineText"},
            {"name": "Unit_Price_ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "Line_Total_ZAR", "type": "number", "options": {"precision": 2}},
            {
                "name": "Approval_Status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Pending", "color": "yellowBright"},
                        {"name": "Approved", "color": "greenBright"},
                        {"name": "Rejected", "color": "redBright"},
                        {"name": "Feedback_Given", "color": "orangeBright"},
                    ]
                },
            },
            {"name": "Rejection_Feedback", "type": "multilineText"},
            {"name": "Rejection_Count", "type": "number", "options": {"precision": 0}},
            {"name": "Created_At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
            {"name": "Updated_At", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
    "Product_Catalog": {
        "description": "Product inventory with Xero item codes, pricing, and VAT rates",
        "primary_field": "Xero_Item_Code",
        "fields": [
            {"name": "Product_Name", "type": "singleLineText"},
            {
                "name": "Category",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Polymailers", "color": "blueBright"},
                        {"name": "Boxes", "color": "orangeBright"},
                        {"name": "Tapes", "color": "grayBright"},
                    ]
                },
            },
            {"name": "Size", "type": "singleLineText"},
            {"name": "Description", "type": "multilineText"},
            {"name": "Unit_Price_ZAR", "type": "number", "options": {"precision": 2}},
            {"name": "VAT_Rate", "type": "number", "options": {"precision": 2}},
            {"name": "Is_Active", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Last_Synced", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        ],
    },
}

# -- Seed Data for Product Catalog -----------------------------------------

SEED_PRODUCTS = [
    {
        "Xero_Item_Code": "PM-A4",
        "Product_Name": "Polymailer A4",
        "Category": "Polymailers",
        "Size": "25x35cm",
        "Unit_Price_ZAR": 3.50,
        "VAT_Rate": 0.15,
        "Is_Active": True,
    },
    {
        "Xero_Item_Code": "PM-A3",
        "Product_Name": "Polymailer A3",
        "Category": "Polymailers",
        "Size": "32x45cm",
        "Unit_Price_ZAR": 5.00,
        "VAT_Rate": 0.15,
        "Is_Active": True,
    },
    {
        "Xero_Item_Code": "PM-LG",
        "Product_Name": "Polymailer Large",
        "Category": "Polymailers",
        "Size": "40x55cm",
        "Unit_Price_ZAR": 7.50,
        "VAT_Rate": 0.15,
        "Is_Active": True,
    },
    {
        "Xero_Item_Code": "BX-SM",
        "Product_Name": "Box Small",
        "Category": "Boxes",
        "Size": "20x15x10cm",
        "Unit_Price_ZAR": 12.00,
        "VAT_Rate": 0.15,
        "Is_Active": True,
    },
    {
        "Xero_Item_Code": "BX-MD",
        "Product_Name": "Box Medium",
        "Category": "Boxes",
        "Size": "30x25x15cm",
        "Unit_Price_ZAR": 18.00,
        "VAT_Rate": 0.15,
        "Is_Active": True,
    },
    {
        "Xero_Item_Code": "BX-LG",
        "Product_Name": "Box Large",
        "Category": "Boxes",
        "Size": "45x35x25cm",
        "Unit_Price_ZAR": 28.00,
        "VAT_Rate": 0.15,
        "Is_Active": True,
    },
    {
        "Xero_Item_Code": "TP-24",
        "Product_Name": "Tape 24mm",
        "Category": "Tapes",
        "Size": "24mm x 66m",
        "Unit_Price_ZAR": 15.00,
        "VAT_Rate": 0.15,
        "Is_Active": True,
    },
    {
        "Xero_Item_Code": "TP-48",
        "Product_Name": "Tape 48mm",
        "Category": "Tapes",
        "Size": "48mm x 66m",
        "Unit_Price_ZAR": 22.00,
        "VAT_Rate": 0.15,
        "Is_Active": True,
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

        # Rename primary field to table-specific name
        primary_name = table_def.get("primary_field", "Name")
        if primary_name != "Name":
            primary_field_id = table_data["fields"][0]["id"]
            rename_resp = client.patch(
                f"{AIRTABLE_META_API}/{base_id}/tables/{table_id}/fields/{primary_field_id}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"name": primary_name},
            )
            if rename_resp.status_code != 200:
                print(f"    Warning: Could not rename primary field: {rename_resp.status_code}")

        return table_id, field_count
    else:
        error_msg = resp.text[:200]
        return None, error_msg


def seed_products(client, token, base_id, table_id):
    """Seed product catalog with initial inventory."""
    records = []
    for product in SEED_PRODUCTS:
        records.append({
            "fields": {
                "Xero_Item_Code": product["Xero_Item_Code"],
                "Product_Name": product["Product_Name"],
                "Category": product["Category"],
                "Size": product["Size"],
                "Unit_Price_ZAR": product["Unit_Price_ZAR"],
                "VAT_Rate": product["VAT_Rate"],
                "Is_Active": product["Is_Active"],
                "Last_Synced": datetime.now().strftime("%Y-%m-%d"),
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
    print("WHATSAPP ORDER-TO-INVOICE - AIRTABLE SETUP")
    print("=" * 60)
    print()

    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    base_id = ORDER_BASE_ID
    if not base_id:
        print("ERROR: ORDER_AIRTABLE_BASE_ID not set.")
        print()
        print("Steps to fix:")
        print("  1. Set ORDER_AIRTABLE_BASE_ID in .env")
        print("  2. Default is app2ALQUP7CKEkHOz (Lead Scraper base)")
        print("  3. The Order tables will be added to this base")
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

        if "Product_Catalog" in created_tables:
            count = seed_products(client, token, base_id, created_tables["Product_Catalog"])
            print(f"  + Product_Catalog: {count} records seeded")

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
        print("Add these to .env:")
        print("-" * 40)
        env_key_map = {
            "Order_Sessions": "ORDER_TABLE_SESSIONS",
            "Product_Catalog": "ORDER_TABLE_PRODUCTS",
        }
        for name, tid in created_tables.items():
            env_key = env_key_map.get(name, name.upper().replace(" ", "_"))
            print(f"  {env_key}={tid}")
        print()

        # Save to .tmp for reference
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "order_airtable_ids.json"

        ids_data = {
            "base_id": base_id,
            "tables": {env_key_map.get(name, name): tid for name, tid in created_tables.items()},
            "created_at": datetime.now().isoformat(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ids_data, f, indent=2)
        print(f"Table IDs saved to: {output_path}")

    print()
    print("Next steps:")
    print("  1. Add the table IDs above to your .env file")
    print("  2. Deploy the WhatsApp Order-to-Invoice workflow")
    print("  3. Verify product catalog data in Airtable")


if __name__ == "__main__":
    main()

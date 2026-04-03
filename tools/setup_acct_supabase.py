"""
Seed Supabase acct_config for a new client (Plug-and-Play Accounting Module).

Usage:
    python tools/setup_acct_supabase.py                          # Seed for AVM default client
    python tools/setup_acct_supabase.py --client-id <uuid>       # Seed for specific client
    python tools/setup_acct_supabase.py --seed-demo              # Also insert demo customers/products

Requires:
    SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
"""

import argparse
import json
import os
import sys
from typing import Any

try:
    import httpx
except ImportError:
    sys.exit("ERROR: httpx not installed. Run: pip install httpx")

from dotenv import load_dotenv

load_dotenv()

# ============================================================
# Supabase connection
# ============================================================
SUPABASE_URL = os.getenv("SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", ""))
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    sys.exit("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")


def supabase_post(table: str, data: dict[str, Any]) -> dict[str, Any]:
    """Insert a record via Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    resp = httpx.post(url, json=data, headers=headers, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"ERROR inserting into {table}: {resp.status_code} {resp.text}")
        return {}
    result = resp.json()
    return result[0] if isinstance(result, list) else result


def supabase_get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    """Query records via Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    resp = httpx.get(url, params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"ERROR querying {table}: {resp.status_code} {resp.text}")
        return []
    return resp.json()


# ============================================================
# Default config (from config.json accounting_dept)
# ============================================================
DEFAULT_CONFIG: dict[str, Any] = {
    "company_legal_name": "AnyVision Media (Pty) Ltd",
    "company_trading_name": "AnyVision Media",
    "company_vat_number": "",
    "company_address": {
        "street": "",
        "city": "Johannesburg",
        "province": "Gauteng",
        "postal_code": "",
        "country": "South Africa",
    },
    "company_bank_details": {
        "bank_name": "",
        "account_number": "",
        "branch_code": "",
        "account_type": "Current",
        "swift": "",
    },
    "default_currency": "ZAR",
    "vat_rate": 0.15,
    "invoice_prefix": "INV",
    "invoice_next_number": 1001,
    "default_payment_terms": "30 days",
    "auto_approve_bills_below": 1000000,  # R10,000 in cents
    "high_value_threshold": 5000000,  # R50,000 in cents
    "payment_match_tolerance": 50.00,
    "reminder_cadence_days": [-3, 0, 3, 7, 14],
    "escalation_after_days": 14,
    "accounting_software": "none",
    "accounting_software_config": {},
    "payment_gateway": "none",
    "payment_gateway_config": {},
    "ocr_provider": "ai",
    "ocr_config": {},
    "comms_email": "gmail",
    "comms_chat": "none",
    "comms_config": {},
    "file_storage": "none",
    "file_storage_config": {},
    "modules_enabled": {
        "invoicing": True,
        "collections": True,
        "payments": True,
        "bills": True,
        "reporting": True,
        "approvals": True,
        "exceptions": True,
        "supplier_payments": True,
    },
    "workflow_ids": {},
}


DEMO_CUSTOMERS = [
    {
        "legal_name": "TechFlow Solutions (Pty) Ltd",
        "trading_name": "TechFlow",
        "email": "accounts@techflow.co.za",
        "phone": "+27 11 555 0101",
        "billing_address": "42 Innovation Drive, Sandton, 2196",
        "vat_number": "4123456789",
        "payment_terms": "30 days",
        "credit_limit": 10000000,  # R100,000
        "risk_flag": "low",
        "preferred_channel": "email",
    },
    {
        "legal_name": "Green Earth Consulting CC",
        "trading_name": "Green Earth",
        "email": "finance@greenearth.co.za",
        "phone": "+27 21 555 0202",
        "billing_address": "8 Ocean View Road, Cape Town, 8001",
        "payment_terms": "14 days",
        "credit_limit": 5000000,  # R50,000
        "risk_flag": "low",
        "preferred_channel": "email",
    },
    {
        "legal_name": "Rapid Logistics SA",
        "email": "billing@rapidlogistics.co.za",
        "phone": "+27 12 555 0303",
        "billing_address": "15 Warehouse Lane, Pretoria, 0001",
        "payment_terms": "7 days",
        "credit_limit": 2000000,  # R20,000
        "risk_flag": "medium",
        "preferred_channel": "both",
    },
]

DEMO_PRODUCTS = [
    {
        "item_code": "WEB-DEV",
        "description": "Website Development",
        "unit_price": 1500000,  # R15,000
        "vat_rate_code": "standard_15",
    },
    {
        "item_code": "SEO-MO",
        "description": "SEO Monthly Retainer",
        "unit_price": 599900,  # R5,999
        "vat_rate_code": "standard_15",
    },
    {
        "item_code": "ADS-MO",
        "description": "Paid Advertising Management",
        "unit_price": 499900,  # R4,999
        "vat_rate_code": "standard_15",
    },
    {
        "item_code": "AI-AUTO",
        "description": "AI Automation Setup",
        "unit_price": 2500000,  # R25,000
        "vat_rate_code": "standard_15",
    },
    {
        "item_code": "CONSULT",
        "description": "Consulting (per hour)",
        "unit_price": 200000,  # R2,000
        "vat_rate_code": "standard_15",
    },
]


def seed_config(client_id: str) -> bool:
    """Create acct_config row for a client."""
    # Check if config already exists
    existing = supabase_get("acct_config", {"client_id": f"eq.{client_id}", "select": "id"})
    if existing:
        print(f"Config already exists for client {client_id}. Skipping.")
        return True

    config_data = {**DEFAULT_CONFIG, "client_id": client_id}
    result = supabase_post("acct_config", config_data)
    if result:
        print(f"Created acct_config for client {client_id}")
        return True
    return False


def seed_demo_data(client_id: str) -> None:
    """Insert demo customers and products."""
    print("\nSeeding demo customers...")
    for cust in DEMO_CUSTOMERS:
        data = {**cust, "client_id": client_id}
        result = supabase_post("acct_customers", data)
        if result:
            print(f"  Created customer: {cust['legal_name']}")

    print("\nSeeding demo products...")
    for prod in DEMO_PRODUCTS:
        data = {**prod, "client_id": client_id}
        result = supabase_post("acct_products", data)
        if result:
            print(f"  Created product: {prod['item_code']} - {prod['description']}")


def get_default_client_id() -> str | None:
    """Get the first active client from the clients table."""
    clients = supabase_get("clients", {"status": "eq.active", "select": "id", "limit": "1"})
    if clients:
        return clients[0]["id"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Supabase accounting config")
    parser.add_argument("--client-id", help="Client UUID to seed config for")
    parser.add_argument("--seed-demo", action="store_true", help="Also seed demo customers and products")
    args = parser.parse_args()

    client_id = args.client_id
    if not client_id:
        client_id = get_default_client_id()
        if not client_id:
            sys.exit("ERROR: No active clients found. Provide --client-id or create a client first.")
        print(f"Using first active client: {client_id}")

    print(f"\n{'='*60}")
    print("Plug-and-Play Accounting Module - Supabase Setup")
    print(f"{'='*60}")
    print(f"Client ID: {client_id}")
    print(f"Supabase:  {SUPABASE_URL}")
    print()

    success = seed_config(client_id)
    if not success:
        sys.exit("Failed to seed config. Check Supabase connection and migration status.")

    if args.seed_demo:
        seed_demo_data(client_id)

    print(f"\n{'='*60}")
    print("Setup complete!")
    print(f"{'='*60}")
    print("\nNext steps:")
    print("  1. Configure settings via portal: /admin/accounting/settings")
    print("  2. Deploy workflows: python tools/deploy_acct_dept.py build")
    print("  3. Activate workflows: python tools/deploy_acct_dept.py activate")


if __name__ == "__main__":
    main()

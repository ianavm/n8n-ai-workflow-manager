"""
Pilot Agent Provisioning Script

Provisions a new real estate agent for the WhatsApp AI pilot:
1. Creates Airtable agent record (WhatsApp Multi-Agent base)
2. Creates Supabase client + agent_profile + whatsapp_connection records
3. Sends welcome email via Gmail API (through n8n webhook)

Usage:
    python tools/provision_pilot_agent.py --config agent.json
    python tools/provision_pilot_agent.py --name "John Smith" --agency "RE/MAX Fourways" \\
        --email john@remax.co.za --phone +27821234567 --areas "Fourways,Sandton"

    python tools/provision_pilot_agent.py --list          # List all pilot agents
    python tools/provision_pilot_agent.py --deactivate ID # Deactivate an agent
"""

import os
import sys
import json
import re
import uuid
import argparse
import secrets
import string
import urllib.parse
import httpx
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# ── Configuration ──

AIRTABLE_TOKEN = os.getenv("AIRTABLE_API_TOKEN", "")
AIRTABLE_BASE_ID = "appzcZpiIZ6QPtJXT"
TABLE_AGENTS = "tblHCkr9weKQAHZoB"
TABLE_PROPERTIES = "tblUFcG2FXrc0gsAj"

SUPABASE_URL = os.getenv("SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", ""))
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

PORTAL_URL = "https://portal.anyvisionmedia.com"

# Default pilot agent settings
DEFAULTS = {
    "bot_type": "real_estate",
    "working_hours": "08:00-17:00",
    "working_days": "1,2,3,4,5",
    "language": "English",
    "timezone": "Africa/Johannesburg",
    "region": "Johannesburg, South Africa",
    "conversation_window": 10,
    "handoff_confidence_threshold": 0.4,
    "max_messages_per_hour": 30,
    "specialization": "residential",
    "welcome_message": (
        "Hi there! I'm the AI assistant for {agency}. "
        "I can help you find properties, schedule viewings, and answer questions "
        "about the buying or renting process. How can I help you today?"
    ),
    "after_hours_message": (
        "Thanks for your message! Our office hours are {hours}. "
        "I'll make sure {agent_name} gets back to you first thing. "
        "If urgent, please call directly."
    ),
}


def validate_agent_config(data):
    """Validate agent config fields. Returns list of error strings (empty = valid)."""
    errors = []
    # name: must be a non-empty string
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("'name' must be a non-empty string")
    # email: basic email regex
    email = data.get("email", "")
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        errors.append(f"'email' is invalid: {email!r}")
    # phone: +27XXXXXXXXX or empty
    phone = data.get("phone", "")
    if phone and not re.fullmatch(r'\+27\d{9}', phone):
        errors.append(f"'phone' must match +27XXXXXXXXX format or be empty, got: {phone!r}")
    return errors


def generate_temp_password(length=16):
    """Generate a secure temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def airtable_request(method, endpoint, data=None):
    """Make an Airtable API request."""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.request(method, url, headers=headers, json=data, timeout=15)
    except httpx.TimeoutException:
        print(f"  Airtable request timed out: {method} {endpoint}")
        return None
    except httpx.RequestError as e:
        print(f"  Airtable network error: {e}")
        return None
    if resp.status_code not in (200, 201):
        print(f"  Airtable error: {resp.status_code} {resp.text[:200]}")
        return None
    return resp.json()


def supabase_request(method, endpoint, data=None):
    """Make a Supabase REST API request."""
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    try:
        resp = httpx.request(method, url, headers=headers, json=data, timeout=15)
    except httpx.TimeoutException:
        print(f"  Supabase request timed out: {method} {endpoint}")
        return None
    except httpx.RequestError as e:
        print(f"  Supabase network error: {e}")
        return None
    if resp.status_code not in (200, 201):
        print(f"  Supabase error: {resp.status_code} {resp.text[:200]}")
        return None
    return resp.json()


def supabase_auth_request(method, endpoint, data=None):
    """Make a Supabase Auth Admin API request."""
    url = f"{SUPABASE_URL}/auth/v1/admin/{endpoint}"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.request(method, url, headers=headers, json=data, timeout=15)
    except httpx.TimeoutException:
        print(f"  Supabase Auth request timed out: {method} {endpoint}")
        return None
    except httpx.RequestError as e:
        print(f"  Supabase Auth network error: {e}")
        return None
    if resp.status_code not in (200, 201):
        print(f"  Supabase Auth error: {resp.status_code} {resp.text[:200]}")
        return None
    return resp.json()


def create_airtable_agent(agent_data):
    """Create agent record in Airtable Agents table."""
    print("\n[1/4] Creating Airtable agent record...")

    agent_id = f"agent_{agent_data['name'].lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}"
    welcome_msg = DEFAULTS["welcome_message"].format(
        agency=agent_data.get("agency", "our agency")
    )
    after_hours_msg = DEFAULTS["after_hours_message"].format(
        hours=agent_data.get("working_hours", DEFAULTS["working_hours"]),
        agent_name=agent_data["name"].split()[0],
    )

    fields = {
        "agent_id": agent_id,
        "agent_name": agent_data["name"],
        "company_name": agent_data.get("agency", ""),
        "email": agent_data["email"],
        "whatsapp_number": agent_data["phone"],
        "region": agent_data.get("region", DEFAULTS["region"]),
        "language": agent_data.get("language", DEFAULTS["language"]),
        "timezone": DEFAULTS["timezone"],
        "is_active": True,
        "auto_reply": True,
        "bot_type": DEFAULTS["bot_type"],
        "working_hours": agent_data.get("working_hours", DEFAULTS["working_hours"]),
        "working_days": agent_data.get("working_days", DEFAULTS["working_days"]),
        "welcome_message": agent_data.get("welcome_message", welcome_msg),
        "after_hours_message": agent_data.get("after_hours_message", after_hours_msg),
        "notification_email": agent_data["email"],
        "notification_phone": agent_data["phone"],
        "handoff_confidence_threshold": DEFAULTS["handoff_confidence_threshold"],
        "max_messages_per_hour": DEFAULTS["max_messages_per_hour"],
        "conversation_window": DEFAULTS["conversation_window"],
        "specialization": agent_data.get("specialization", DEFAULTS["specialization"]),
        "custom_area_info": agent_data.get("area_info", ""),
        "listing_url": agent_data.get("listing_url", ""),
    }

    result = airtable_request("POST", TABLE_AGENTS, {"fields": fields})
    if result:
        record_id = result.get("id", "unknown")
        print(f"  Created: {agent_id} (record: {record_id})")
        return {"agent_id": agent_id, "airtable_record_id": record_id}
    return None


def create_supabase_client(agent_data):
    """Create Supabase auth user + client record."""
    print("\n[2/4] Creating Supabase client record...")

    temp_password = generate_temp_password()

    # Create auth user
    auth_result = supabase_auth_request("POST", "users", {
        "email": agent_data["email"],
        "password": temp_password,
        "email_confirm": True,
    })

    if not auth_result:
        print("  Failed to create auth user")
        return None

    auth_user_id = auth_result.get("id")
    if not auth_user_id:
        print(f"  Unexpected auth response: {json.dumps(auth_result)[:200]}")
        return None

    print(f"  Auth user created: {auth_user_id}")

    # Create client record
    client_data = {
        "auth_user_id": auth_user_id,
        "email": agent_data["email"].lower().strip(),
        "full_name": agent_data["name"],
        "company_name": agent_data.get("agency"),
        "status": "active",
    }

    client_result = supabase_request("POST", "clients", client_data)
    if not client_result:
        print("  Failed to create client record")
        return None

    client_id = client_result[0]["id"] if isinstance(client_result, list) else client_result.get("id")
    print(f"  Client created: {client_id}")

    return {
        "auth_user_id": auth_user_id,
        "client_id": client_id,
        "temp_password": temp_password,
    }


def create_agent_profile(client_id, agent_id, agent_data):
    """Create agent_profiles record in Supabase."""
    print("\n[3/4] Creating Supabase agent profile + WhatsApp connection...")

    # Agent profile
    profile_data = {
        "client_id": client_id,
        "agent_id": agent_id,
        "agent_name": agent_data["name"],
        "phone_number": agent_data["phone"],
        "email": agent_data["email"],
        "is_online": False,
        "business_hours_start": agent_data.get("working_hours", DEFAULTS["working_hours"]).split("-")[0],
        "business_hours_end": agent_data.get("working_hours", DEFAULTS["working_hours"]).split("-")[1],
        "timezone": DEFAULTS["timezone"],
    }

    profile_result = supabase_request("POST", "agent_profiles", profile_data)
    if profile_result:
        print(f"  Agent profile created")
    else:
        print("  WARNING: Agent profile creation failed (may already exist)")

    # WhatsApp connection (pending until number is registered)
    connection_data = {
        "client_id": client_id,
        "display_phone_number": agent_data["phone"],
        "business_name": agent_data.get("agency", ""),
        "status": "pending",
        "coexistence_enabled": True,
    }

    conn_result = supabase_request("POST", "whatsapp_connections", connection_data)
    if conn_result:
        print(f"  WhatsApp connection created (status: pending)")
    else:
        print("  WARNING: WhatsApp connection creation failed (may already exist)")


def send_welcome_email(agent_data, temp_password):
    """Log welcome email details (send via portal or manually)."""
    print("\n[4/4] Welcome email details...")
    print(f"  To: {agent_data['email']}")
    print(f"  Subject: Welcome to AnyVision Media WhatsApp AI Pilot")
    print(f"  Portal URL: {PORTAL_URL}/portal/login")
    print(f"  TEMP PASSWORD (shown once, not saved): {temp_password}")
    print(f"  (Agent should change password on first login)")


def provision_agent(agent_data):
    """Full provisioning pipeline for a pilot agent."""
    print("=" * 60)
    print(f"PROVISIONING PILOT AGENT: {agent_data['name']}")
    print(f"Agency: {agent_data.get('agency', 'N/A')}")
    print(f"Email: {agent_data['email']}")
    print(f"Phone: {agent_data['phone']}")
    print("=" * 60)

    # Validate required fields
    required = ["name", "email", "phone"]
    missing = [f for f in required if not agent_data.get(f)]
    if missing:
        print(f"\nERROR: Missing required fields: {', '.join(missing)}")
        sys.exit(1)

    # Idempotency check — prevent duplicate agents
    safe_email = urllib.parse.quote(agent_data["email"], safe='')
    existing = airtable_request(
        "GET",
        f"{TABLE_AGENTS}?filterByFormula={{email}}='{safe_email}'"
    )
    if existing and existing.get("records"):
        print(f"\nERROR: Agent with email {agent_data['email']} already exists in Airtable")
        print(f"  Record ID: {existing['records'][0]['id']}")
        print(f"  Use --deactivate to deactivate, or manually delete before re-provisioning")
        sys.exit(1)

    # Step 1: Airtable agent
    airtable_result = create_airtable_agent(agent_data)
    if not airtable_result:
        print("\nFAILED: Could not create Airtable agent record")
        sys.exit(1)

    # Step 2: Supabase client
    supabase_result = create_supabase_client(agent_data)
    if not supabase_result:
        print("\nFAILED: Supabase client creation failed. Rolling back Airtable record...")
        rollback = airtable_request(
            "DELETE",
            f"{TABLE_AGENTS}/{airtable_result['airtable_record_id']}"
        )
        if rollback is not None:
            print(f"  Rolled back Airtable record: {airtable_result['airtable_record_id']}")
        else:
            print(f"  WARNING: Could not delete Airtable record {airtable_result['airtable_record_id']}. Remove manually.")
        sys.exit(1)
    else:
        temp_password = supabase_result["temp_password"]

        # Step 3: Agent profile + WhatsApp connection
        create_agent_profile(
            supabase_result["client_id"],
            airtable_result["agent_id"],
            agent_data,
        )

    # Step 4: Welcome email details
    send_welcome_email(agent_data, temp_password)

    # Summary
    print("\n" + "=" * 60)
    print("PROVISIONING COMPLETE")
    print("=" * 60)
    print(f"  Airtable agent_id: {airtable_result['agent_id']}")
    if supabase_result:
        print(f"  Supabase client_id: {supabase_result['client_id']}")
    print(f"  Portal login: {PORTAL_URL}/portal/login")
    print(f"\n  NEXT STEPS:")
    print(f"  1. Register agent's WhatsApp number in Meta Cloud API")
    print(f"  2. Update Airtable agent record with phone_number_id from Meta")
    print(f"  3. Share temp password with agent (or send invite email)")
    print(f"  4. Agent logs in, toggles AI to 'Auto' mode")
    print(f"  5. Test by sending a WhatsApp message to their business number")

    return {
        "agent_id": airtable_result["agent_id"],
        "airtable_record_id": airtable_result["airtable_record_id"],
        "client_id": supabase_result["client_id"] if supabase_result else None,
        "temp_password": temp_password,
    }


def list_agents():
    """List all pilot agents from Airtable."""
    print("\nPILOT AGENTS")
    print("=" * 60)

    result = airtable_request("GET", f"{TABLE_AGENTS}?fields%5B%5D=agent_id&fields%5B%5D=agent_name&fields%5B%5D=company_name&fields%5B%5D=email&fields%5B%5D=is_active&fields%5B%5D=auto_reply&fields%5B%5D=bot_type")
    if not result:
        print("  Failed to fetch agents")
        return

    records = result.get("records", [])
    if not records:
        print("  No agents found")
        return

    for r in records:
        f = r.get("fields", {})
        status = "ACTIVE" if f.get("is_active") and f.get("auto_reply") else "INACTIVE"
        print(f"  [{status:8s}] {f.get('agent_name', '?'):20s} | {f.get('company_name', ''):20s} | {f.get('email', '')}")

    print(f"\n  Total: {len(records)} agents")


def main():
    parser = argparse.ArgumentParser(description="Provision a pilot agent for WhatsApp AI")
    parser.add_argument("--config", help="Path to JSON config file with agent data")
    parser.add_argument("--name", help="Agent full name")
    parser.add_argument("--agency", help="Agency/company name")
    parser.add_argument("--email", help="Agent email address")
    parser.add_argument("--phone", help="Agent WhatsApp number (e.g., +27821234567)")
    parser.add_argument("--areas", help="Areas served, comma-separated (e.g., Fourways,Sandton)")
    parser.add_argument("--hours", default="08:00-17:00", help="Business hours (default: 08:00-17:00)")
    parser.add_argument("--specialization", default="residential",
                        choices=["residential", "commercial", "both", "luxury", "rental"])
    parser.add_argument("--listing-url", help="URL to agent's property listings")
    parser.add_argument("--area-info", help="Local area knowledge for AI context")
    parser.add_argument("--list", action="store_true", help="List all pilot agents")
    parser.add_argument("--deactivate", metavar="AGENT_ID", help="Deactivate an agent by agent_id")

    args = parser.parse_args()

    # Validate credentials
    if not AIRTABLE_TOKEN:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    if not args.list and not args.deactivate:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env for provisioning")
            print("  -> Cannot provision agents without Supabase credentials")
            sys.exit(1)

    if args.list:
        list_agents()
        return

    if args.deactivate:
        # Validate agent_id format to prevent formula injection
        if not re.fullmatch(r'agent_[a-z0-9_]{1,60}', args.deactivate):
            print(f"ERROR: Invalid agent_id format: {args.deactivate}")
            print("  Expected format: agent_<name>_<hex> (e.g., agent_john_smith_a1b2c3)")
            sys.exit(1)

        print(f"\nDeactivating agent: {args.deactivate}")
        safe_id = urllib.parse.quote(args.deactivate, safe='')
        result = airtable_request(
            "GET",
            f"{TABLE_AGENTS}?filterByFormula={{agent_id}}='{safe_id}'"
        )
        if result and result.get("records"):
            record_id = result["records"][0]["id"]
            airtable_request("PATCH", f"{TABLE_AGENTS}/{record_id}", {
                "fields": {"is_active": False, "auto_reply": False}
            })
            print(f"  Deactivated: {args.deactivate}")
        else:
            print(f"  Agent not found: {args.deactivate}")
        return

    # Allowed fields for agent config (whitelist to prevent injection)
    ALLOWED_FIELDS = {
        "name", "email", "phone", "agency", "areas", "working_hours",
        "working_days", "specialization", "listing_url", "area_info",
        "region", "language", "welcome_message", "after_hours_message",
    }

    # Build agent data from config file or CLI args
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"ERROR: Config file not found: {args.config}")
            sys.exit(1)
        try:
            raw_data = json.loads(config_path.read_text())
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in config file: {e}")
            sys.exit(1)
        agent_data = {k: v for k, v in raw_data.items() if k in ALLOWED_FIELDS}
        # Validate config fields
        config_errors = validate_agent_config(agent_data)
        if config_errors:
            print("ERROR: Config validation failed:")
            for err in config_errors:
                print(f"  - {err}")
            sys.exit(1)
    elif args.name and args.email and args.phone:
        agent_data = {
            "name": args.name,
            "agency": args.agency or "",
            "email": args.email,
            "phone": args.phone,
            "areas": args.areas or "",
            "working_hours": args.hours,
            "specialization": args.specialization,
            "listing_url": args.listing_url or "",
            "area_info": args.area_info or "",
        }
        # Build region from areas if provided
        if args.areas:
            agent_data["region"] = args.areas.replace(",", ", ")
    else:
        parser.print_help()
        print("\nERROR: Provide either --config or --name --email --phone")
        sys.exit(1)

    provision_agent(agent_data)


if __name__ == "__main__":
    main()

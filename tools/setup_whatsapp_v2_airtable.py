"""
Add required fields to WhatsApp Multi-Agent Airtable tables for v2/v3.

Adds:
- Agents table: bot_type, custom_system_prompt, openrouter_model, conversation_window,
  working_hours, working_days, after_hours_message, welcome_message,
  notification_email, notification_phone, handoff_confidence_threshold,
  max_messages_per_hour
- Message Log table: direction, conversation_id, whatsapp_message_id,
  is_welcome, handoff_triggered, response_type
- Blocked Messages table: opt_out fields for POPIA compliance + new block reasons

Usage:
    python tools/setup_whatsapp_v2_airtable.py
"""

import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Airtable IDs
BASE_ID = "appzcZpiIZ6QPtJXT"
TABLE_AGENTS = "tblHCkr9weKQAHZoB"
TABLE_MESSAGE_LOG = "tbl72lkYHRbZHIK4u"
TABLE_BLOCKED = "tbluSD0m6zIAVmsGm"

# Fields to add to Agents table
AGENT_FIELDS = [
    {
        "name": "bot_type",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "business", "color": "blueBright"},
                {"name": "real_estate", "color": "greenBright"},
                {"name": "custom", "color": "purpleBright"},
            ]
        },
        "description": "Type of bot (determines system prompt)",
    },
    {
        "name": "custom_system_prompt",
        "type": "multilineText",
        "description": "Custom system prompt for bot_type=custom",
    },
    {
        "name": "openrouter_model",
        "type": "singleLineText",
        "description": "OpenRouter model ID (e.g. anthropic/claude-sonnet-4-20250514)",
    },
    {
        "name": "conversation_window",
        "type": "number",
        "options": {"precision": 0},
        "description": "Number of messages to include in AI context (default 10)",
    },
    # --- v3 fields for 10-agent support ---
    {
        "name": "working_hours",
        "type": "singleLineText",
        "description": "Business hours e.g. '08:00-17:00' (null = always on)",
    },
    {
        "name": "working_days",
        "type": "singleLineText",
        "description": "Active days CSV e.g. '1,2,3,4,5' for Mon-Fri (null = all days)",
    },
    {
        "name": "after_hours_message",
        "type": "multilineText",
        "description": "Custom after-hours auto-reply message",
    },
    {
        "name": "welcome_message",
        "type": "multilineText",
        "description": "First-contact welcome message for new customers",
    },
    {
        "name": "notification_email",
        "type": "email",
        "description": "Email for human handoff alerts (defaults to agent email)",
    },
    {
        "name": "notification_phone",
        "type": "singleLineText",
        "description": "Personal WhatsApp number for handoff alerts (optional)",
    },
    {
        "name": "handoff_confidence_threshold",
        "type": "number",
        "options": {"precision": 2},
        "description": "AI confidence below which triggers human handoff (default 0.4)",
    },
    {
        "name": "max_messages_per_hour",
        "type": "number",
        "options": {"precision": 0},
        "description": "Per-contact rate limit per hour (default 30)",
    },
    # --- Language support ---
    {
        "name": "default_language",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "English", "color": "blueBright"},
                {"name": "Afrikaans", "color": "greenBright"},
                {"name": "isiZulu", "color": "yellowBright"},
                {"name": "Sesotho", "color": "orangeBright"},
                {"name": "isiXhosa", "color": "purpleBright"},
            ]
        },
        "description": "Agent's default response language (fallback when auto-detect uncertain)",
    },
    {
        "name": "supported_languages",
        "type": "singleLineText",
        "description": "Comma-separated languages agent supports, e.g. 'English,Afrikaans,isiZulu'. Empty = all SA languages.",
    },
]

# Fields to add to Message Log table
MESSAGE_LOG_FIELDS = [
    {
        "name": "direction",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "inbound", "color": "blueBright"},
                {"name": "outbound", "color": "greenBright"},
            ]
        },
        "description": "Message direction (inbound from customer, outbound from bot)",
    },
    {
        "name": "conversation_id",
        "type": "singleLineText",
        "description": "Composite key: {agent_id}_{phone_number}",
    },
    {
        "name": "whatsapp_message_id",
        "type": "singleLineText",
        "description": "Meta's wamid.XXX message ID",
    },
    # --- v3 fields ---
    {
        "name": "is_welcome",
        "type": "checkbox",
        "description": "Whether this was a first-contact welcome message",
    },
    {
        "name": "handoff_triggered",
        "type": "checkbox",
        "description": "Whether this message triggered a human handoff",
    },
    {
        "name": "response_type",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "ai_response", "color": "blueBright"},
                {"name": "after_hours", "color": "yellowBright"},
                {"name": "welcome", "color": "greenBright"},
                {"name": "opt_out", "color": "purpleBright"},
                {"name": "handoff", "color": "orangeBright"},
            ]
        },
        "description": "Type of response sent (ai_response, after_hours, welcome, opt_out, handoff)",
    },
]

# Fields to add to Blocked Messages table (opt-out compliance)
BLOCKED_FIELDS = [
    {
        "name": "block_reason",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "group_message", "color": "grayBright"},
                {"name": "agent_not_found", "color": "orangeBright"},
                {"name": "agent_online", "color": "yellowBright"},
                {"name": "rate_limited", "color": "redBright"},
                {"name": "user_opted_out", "color": "purpleBright"},
                {"name": "after_hours", "color": "tealBright"},
                {"name": "previously_opted_out", "color": "pinkBright"},
                {"name": "unknown", "color": "grayBright"},
            ]
        },
        "description": "Reason the message was blocked",
    },
    {
        "name": "opt_out_confirmed",
        "type": "checkbox",
        "description": "Whether an opt-out confirmation was sent to the user",
    },
]


def add_fields(token, base_id, table_id, table_name, fields):
    """Add fields to an Airtable table."""
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables/{table_id}/fields"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print(f"\n  Table: {table_name} ({table_id})")
    created = 0
    skipped = 0

    for field in fields:
        try:
            resp = httpx.post(url, headers=headers, json=field, timeout=15)

            if resp.status_code == 200:
                print(f"    + {field['name']} ({field['type']})")
                created += 1
            elif resp.status_code == 422:
                error_msg = resp.json().get("error", {}).get("message", "")
                if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                    print(f"    = {field['name']} (already exists)")
                    skipped += 1
                else:
                    print(f"    ! {field['name']} FAILED: {error_msg}")
            else:
                print(f"    ! {field['name']} FAILED: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            print(f"    ! {field['name']} ERROR: {e}")

    print(f"    Result: {created} created, {skipped} skipped")
    return created


def main():
    print("=" * 60)
    print("WHATSAPP v2 - AIRTABLE SCHEMA SETUP")
    print("=" * 60)

    token = os.getenv("AIRTABLE_API_TOKEN")
    if not token:
        print("\nERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)

    print(f"\n  Base: {BASE_ID}")

    total = 0
    total += add_fields(token, BASE_ID, TABLE_AGENTS, "Agents", AGENT_FIELDS)
    total += add_fields(token, BASE_ID, TABLE_MESSAGE_LOG, "Message Log", MESSAGE_LOG_FIELDS)
    total += add_fields(token, BASE_ID, TABLE_BLOCKED, "Blocked Messages", BLOCKED_FIELDS)

    print(f"\n  Total fields created: {total}")
    print("\nDone!")


if __name__ == "__main__":
    main()

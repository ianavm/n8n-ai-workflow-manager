"""
Centralized n8n credential ID references.

All deploy scripts should import credential constants from here
instead of defining their own. Credential IDs can be overridden
via environment variables for multi-client setups.

Usage:
    from credentials import CREDENTIALS
    cred_gmail = CREDENTIALS["gmail"]
"""

import os


def _cred(env_key, default_id, name):
    """Build a credential reference dict, allowing env override."""
    return {
        "id": os.getenv(env_key, default_id),
        "name": name,
    }


# Default credential IDs (AnyVision Media internal n8n references)
CREDENTIALS = {
    "gmail": _cred("N8N_CRED_GMAIL", "2IuycrTIgWJZEjBE", "Gmail account AVM Tutorial"),
    "airtable": _cred("N8N_CRED_AIRTABLE", "ZyBrcAO6fps7YB3u", "Airtable account"),
    "openrouter": _cred("N8N_CRED_OPENROUTER", "9ZgHenDBrFuyboov", "OpenRouter 2WC"),
    "xero": _cred("ACCOUNTING_XERO_CRED_ID", "REPLACE", "Xero OAuth2 AVM"),
    "whatsapp_send": _cred("N8N_CRED_WHATSAPP", "dCAz6MBXpOXvMJrq", "WhatsApp account AVM Multi Agent"),
    "whatsapp_trigger": _cred("N8N_CRED_WHATSAPP_TRIGGER", "rUyqIX1gaBs3ae6Q", "WhatsApp OAuth AVM Multi Agent"),
    "whatsapp_airtable": _cred("N8N_CRED_WHATSAPP_AIRTABLE", "CTVAhYlNsJFMX2lE", "Whatsapp Multi Agent"),
    "google_sheets": _cred("N8N_CRED_GOOGLE_SHEETS", "OkpDXxwI8WcUJp4P", "Google Sheets account"),
}

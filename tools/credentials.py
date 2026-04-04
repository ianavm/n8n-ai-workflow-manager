"""
Shared credential references for n8n workflow deployment scripts.

All deploy scripts should import credential constants from here
instead of defining their own. Credential IDs can be overridden
via environment variables for multi-client setups.

These are internal n8n credential IDs (not secrets).

Usage:
    from credentials import CREDENTIALS
    cred_gmail = CREDENTIALS["gmail"]

    # Or use convenience constants directly:
    from credentials import CRED_GMAIL, CRED_OPENROUTER
"""

import os


def _cred(env_key, default_id, name):
    """Build a credential reference dict, allowing env override."""
    return {
        "id": os.getenv(env_key, default_id),
        "name": name,
    }


# ============================================================
# Default credential IDs (AnyVision Media internal n8n refs)
# ============================================================

CREDENTIALS = {
    # ── AI Gateway ──────────────────────────────────────────
    "openrouter": _cred(
        "N8N_CRED_OPENROUTER", "9ZgHenDBrFuyboov", "OpenRouter 2WC"
    ),
    "openai": _cred(
        "N8N_CRED_OPENAI", "mNXmJ6IgruQfWkPq", "OpenAi account 10"
    ),

    # ── Google Services ─────────────────────────────────────
    "gmail": _cred(
        "N8N_CRED_GMAIL", "2IuycrTIgWJZEjBE", "Gmail account AVM Tutorial"
    ),
    "gmail_oauth2": _cred(
        "N8N_CRED_GMAIL_OAUTH2", "EC2l4faLSdgePOM6", "Gmail AVM Tutorial"
    ),
    "google_sheets": _cred(
        "N8N_CRED_GOOGLE_SHEETS", "OkpDXxwI8WcUJp4P", "Google Sheets AVM Tutorial"
    ),
    "google_calendar": _cred(
        "N8N_CRED_GOOGLE_CALENDAR", "I5zIYf0UxlkUt3KG", "Google Calendar AVM Tutorial"
    ),
    "google_drive": _cred(
        "N8N_CRED_GDRIVE", "h1nJlw5vhziBMlh8", "Google Drive OAuth2"
    ),

    # ── Airtable ────────────────────────────────────────────
    "airtable": _cred(
        "N8N_CRED_AIRTABLE", "ZyBrcAO6fps7YB3u", "Airtable account"
    ),
    "airtable_lead_scraper": _cred(
        "N8N_CRED_AIRTABLE_LEAD_SCRAPER", "7TtMl7ZnJFpC4RGk", "Lead Scraper Airtable"
    ),
    "airtable_whatsapp": _cred(
        "N8N_CRED_WHATSAPP_AIRTABLE", "CTVAhYlNsJFMX2lE", "Whatsapp Multi Agent"
    ),

    # ── Accounting / Finance ────────────────────────────────
    "quickbooks": _cred(
        "ACCOUNTING_QBO_CRED_ID", "REPLACE", "QuickBooks OAuth2 AVM"
    ),
    "stripe": _cred(
        "ACCOUNTING_STRIPE_CRED_ID", "REPLACE", "Stripe API AVM"
    ),
    "xero": _cred(
        "ACCOUNTING_XERO_CRED_ID", "REPLACE", "Xero OAuth2"
    ),
    "payfast": _cred(
        "ACCOUNTING_PAYFAST_CRED_ID", "REPLACE", "PayFast API"
    ),
    "yoco": _cred(
        "ACCOUNTING_YOCO_CRED_ID", "REPLACE", "Yoco API"
    ),

    # ── WhatsApp Business ───────────────────────────────────
    "whatsapp_send": _cred(
        "N8N_CRED_WHATSAPP", "dCAz6MBXpOXvMJrq", "WhatsApp account AVM Multi Agent"
    ),
    "whatsapp_trigger": _cred(
        "N8N_CRED_WHATSAPP_TRIGGER", "rUyqIX1gaBs3ae6Q", "WhatsApp OAuth AVM Multi Agent"
    ),

    # ── Social Media ────────────────────────────────────────
    "blotato": _cred(
        "N8N_CRED_BLOTATO", "hhRiqZrWNlqvmYZR", "Blotato AVM"
    ),

    # ── Microsoft ───────────────────────────────────────────
    "outlook": _cred(
        "N8N_CRED_OUTLOOK", "PLACEHOLDER_OUTLOOK", "Microsoft Outlook OAuth2"
    ),
    "outlook_fa": _cred(
        "N8N_CRED_OUTLOOK_FA", "PLACEHOLDER_OUTLOOK_FA", "Microsoft Outlook OAuth2 FA"
    ),
    "teams_fa": _cred(
        "N8N_CRED_TEAMS_FA", "PLACEHOLDER_TEAMS_FA", "Microsoft Teams OAuth2 FA"
    ),

    # ── Telegram ───────────────────────────────────────────
    "telegram": _cred(
        "N8N_CRED_TELEGRAM", "37DtsPS5RQYxY2i1", "Telegram RE Operations Bot"
    ),

    # ── Ad Platforms ────────────────────────────────────────
    "google_ads": _cred(
        "N8N_CRED_GOOGLE_ADS", "REPLACE_AFTER_SETUP", "Google Ads OAuth2"
    ),
    "meta_ads": _cred(
        "N8N_CRED_META_ADS", "REPLACE_AFTER_SETUP", "Meta Ads Graph API"
    ),
    "tiktok_ads": _cred(
        "N8N_CRED_TIKTOK_ADS", "REPLACE_AFTER_SETUP", "TikTok Ads HTTP Auth"
    ),
    "linkedin_ads": _cred(
        "N8N_CRED_LINKEDIN_ADS", "REPLACE_AFTER_SETUP", "LinkedIn Ads OAuth2"
    ),

    # ── Infrastructure ──────────────────────────────────────
    "http_header_auth": _cred(
        "N8N_CRED_HTTP_HEADER_AUTH", "xymp9Nho08mRW2Wz", "Header Auth account 2"
    ),
    "n8n_api": _cred(
        "SELFHEALING_N8N_API_CRED_ID", "REPLACE_WITH_N8N_HEADER_AUTH_CRED", "n8n API Key"
    ),
}


# ============================================================
# Convenience constants (for backwards compatibility)
# ============================================================

# AI
CRED_OPENROUTER = CREDENTIALS["openrouter"]
CRED_OPENAI = CREDENTIALS["openai"]

# Google
CRED_GMAIL = CREDENTIALS["gmail"]
CRED_GMAIL_OAUTH2 = CREDENTIALS["gmail_oauth2"]
CRED_GOOGLE_SHEETS = CREDENTIALS["google_sheets"]
CRED_GOOGLE_CALENDAR = CREDENTIALS["google_calendar"]
CRED_GOOGLE_DRIVE = CREDENTIALS["google_drive"]

# Airtable
CRED_AIRTABLE = CREDENTIALS["airtable"]
CRED_AIRTABLE_LEAD_SCRAPER = CREDENTIALS["airtable_lead_scraper"]
CRED_AIRTABLE_WHATSAPP = CREDENTIALS["airtable_whatsapp"]

# Accounting
CRED_QUICKBOOKS = CREDENTIALS["quickbooks"]
CRED_STRIPE = CREDENTIALS["stripe"]
CRED_XERO = CREDENTIALS["xero"]
CRED_PAYFAST = CREDENTIALS["payfast"]
CRED_YOCO = CREDENTIALS["yoco"]

# WhatsApp
CRED_WHATSAPP_SEND = CREDENTIALS["whatsapp_send"]
CRED_WHATSAPP_TRIGGER = CREDENTIALS["whatsapp_trigger"]

# Social Media
CRED_BLOTATO = CREDENTIALS["blotato"]

# Microsoft
CRED_OUTLOOK = CREDENTIALS["outlook"]
CRED_OUTLOOK_FA = CREDENTIALS["outlook_fa"]
CRED_TEAMS_FA = CREDENTIALS["teams_fa"]

# Telegram
CRED_TELEGRAM = CREDENTIALS["telegram"]

# Infrastructure
CRED_HTTP_HEADER_AUTH = CREDENTIALS["http_header_auth"]
CRED_N8N_API = CREDENTIALS["n8n_api"]


# Ad Platforms
CRED_GOOGLE_ADS = CREDENTIALS["google_ads"]
CRED_META_ADS = CREDENTIALS["meta_ads"]
CRED_TIKTOK_ADS = CREDENTIALS["tiktok_ads"]
CRED_LINKEDIN_ADS = CREDENTIALS["linkedin_ads"]


def get_client_credentials(
    client_id: str,
    platform: str,
    supabase_url: str | None = None,
    supabase_key: str | None = None,
) -> dict:
    """Fetch per-client credential ID from Supabase mkt_config.

    Falls back to default AVM credentials if client-specific not found.

    Args:
        client_id: UUID of the client.
        platform: Ad platform key (google_ads, meta_ads, tiktok_ads, linkedin_ads, blotato).
        supabase_url: Supabase project URL (reads from env if not provided).
        supabase_key: Supabase service role key (reads from env if not provided).

    Returns:
        dict with 'id' and 'name' keys for n8n credential reference.
    """
    import httpx

    url = supabase_url or os.getenv("SUPABASE_URL", "")
    key = supabase_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        # Fall back to defaults
        return CREDENTIALS.get(platform, {"id": "MISSING", "name": platform})

    try:
        resp = httpx.get(
            f"{url}/rest/v1/mkt_config",
            params={"client_id": f"eq.{client_id}", "select": "n8n_credentials"},
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
            },
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json()
        if rows and len(rows) > 0:
            creds = rows[0].get("n8n_credentials", {})
            cred_id = creds.get(f"{platform}_cred_id")
            if cred_id:
                return {"id": cred_id, "name": f"{platform} (client {client_id[:8]})"}
    except Exception:
        pass

    # Fall back to default
    return CREDENTIALS.get(platform, {"id": "MISSING", "name": platform})


def validate_credentials():
    """Check all credential entries for placeholder IDs.

    Returns True if every credential has a real ID,
    False if any contain 'PLACEHOLDER' or 'REPLACE'.
    """
    all_valid = True
    for key, cred in CREDENTIALS.items():
        cred_id = cred.get("id", "")
        if "PLACEHOLDER" in cred_id.upper() or "REPLACE" in cred_id.upper():
            print(f"WARNING: Credential '{key}' has placeholder ID: {cred_id}")
            all_valid = False
    return all_valid

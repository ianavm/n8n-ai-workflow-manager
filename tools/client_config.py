"""
Multi-client configuration loader.

Loads per-client settings from config.json's "clients" section and
resolves secrets from environment variables. Each client gets their
own Airtable base, webhook path prefix, and credential references.

Usage:
    from client_config import get_client_config, list_clients

    # Get a specific client's config
    client = get_client_config("client_acme")
    print(client["name"])           # "ACME Corp"
    print(client["airtable_base"])  # "appXXXXXXXXXXXXXX"
    print(client["airtable_token"]) # resolved from env var

    # List all configured clients
    for client_id in list_clients():
        print(client_id)
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).parent.parent
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


def _load_config():
    """Load config.json."""
    config_path = _project_root / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"config.json not found at {config_path}")
    with open(config_path, "r") as f:
        return json.load(f)


def list_clients():
    """Return list of configured client IDs."""
    config = _load_config()
    clients = config.get("clients", {})
    return list(clients.keys())


def get_client_config(client_id):
    """
    Get configuration for a specific client.

    Args:
        client_id: The client identifier (key in config.json's "clients" section)

    Returns:
        dict with keys: name, airtable_base, airtable_token, webhook_prefix,
        xero_tenant_id, gmail_credential_id, and any other client-specific settings.

    Raises:
        KeyError: If client_id not found in config.json
        ValueError: If required environment variable is missing
    """
    config = _load_config()
    clients = config.get("clients", {})

    if client_id not in clients:
        available = ", ".join(clients.keys()) if clients else "(none configured)"
        raise KeyError(
            f"Client '{client_id}' not found in config.json. "
            f"Available clients: {available}"
        )

    client = clients[client_id].copy()

    # Resolve Airtable token from environment variable
    token_env_key = client.get("airtable_token_env", "")
    if token_env_key:
        token = os.getenv(token_env_key)
        if not token:
            raise ValueError(
                f"Environment variable '{token_env_key}' not set for client '{client_id}'. "
                f"Add it to .env file."
            )
        client["airtable_token"] = token
    else:
        # Fallback to global Airtable token
        client["airtable_token"] = os.getenv("AIRTABLE_API_TOKEN", "")

    # Resolve webhook auth token if client-specific
    webhook_token_env = client.get("webhook_token_env", "")
    if webhook_token_env:
        client["webhook_token"] = os.getenv(webhook_token_env, "")
    else:
        client["webhook_token"] = os.getenv("WEBHOOK_AUTH_TOKEN", "")

    return client


def get_default_client():
    """
    Get the default client config (AnyVision Media / first client).
    Useful for backwards compatibility during migration.
    """
    clients = list_clients()
    if not clients:
        # No clients configured yet - return legacy defaults from env
        return {
            "name": "AnyVision Media",
            "airtable_base": os.getenv("ACCOUNTING_AIRTABLE_BASE_ID", ""),
            "airtable_token": os.getenv("AIRTABLE_API_TOKEN", ""),
            "webhook_prefix": "",
            "xero_tenant_id": os.getenv("ACCOUNTING_XERO_TENANT_ID", ""),
            "webhook_token": os.getenv("WEBHOOK_AUTH_TOKEN", ""),
        }
    return get_client_config(clients[0])

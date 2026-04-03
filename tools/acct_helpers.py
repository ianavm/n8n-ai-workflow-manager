"""
Shared node builders for the Plug-and-Play Accounting module.

All deploy_acct_wf*.py scripts import from here to stay DRY.
These helpers generate n8n node dicts for common patterns:
- Supabase reads/writes (replacing Airtable)
- Status webhook posts to portal
- Audit log entries
- Accounting software adapter (Switch + HTTP)
- Common triggers (schedule, manual, webhook)
"""

import os
import uuid
from typing import Any

# ── Environment ──────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", "REPLACE"))
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "REPLACE")
PORTAL_URL = os.getenv("PORTAL_URL", "https://portal.anyvisionmedia.com")
N8N_WEBHOOK_SECRET = os.getenv("N8N_WEBHOOK_SECRET", "REPLACE")
OPENROUTER_MODEL = os.getenv("ACCT_AI_MODEL", "anthropic/claude-sonnet-4-20250514")


def uid() -> str:
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ============================================================
# TRIGGER NODES
# ============================================================

def schedule_trigger(name: str, cron: str, position: list[int]) -> dict[str, Any]:
    """Schedule trigger node."""
    return {
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": cron}]}
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": position,
        "typeVersion": 1.2,
    }


def manual_trigger(position: list[int] | None = None) -> dict[str, Any]:
    """Manual trigger for testing."""
    return {
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": position or [200, 600],
        "typeVersion": 1,
    }


def webhook_trigger(
    name: str, path: str, position: list[int],
    method: str = "POST", response_mode: str = "responseNode",
) -> dict[str, Any]:
    """Webhook trigger node."""
    return {
        "parameters": {
            "httpMethod": method,
            "path": path,
            "options": {},
            "responseMode": response_mode,
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.webhook",
        "position": position,
        "typeVersion": 2,
        "webhookId": uid(),
    }


# ============================================================
# SUPABASE NODES (via HTTP Request)
# ============================================================

def supabase_select(
    name: str,
    table: str,
    select: str = "*",
    filters: str = "",
    position: list[int] | None = None,
    single: bool = False,
) -> dict[str, Any]:
    """HTTP Request node that queries Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
    if filters:
        url += f"&{filters}"
    headers_params = {
        "parameters": [
            {"name": "apikey", "value": SUPABASE_KEY},
            {"name": "Authorization", "value": f"Bearer {SUPABASE_KEY}"},
        ]
    }
    if single:
        headers_params["parameters"].append(
            {"name": "Accept", "value": "application/vnd.pgrst.object+json"}
        )
    return {
        "parameters": {
            "method": "GET",
            "url": url,
            "sendHeaders": True,
            "headerParameters": headers_params,
            "options": {"response": {"response": {"responseFormat": "json"}}},
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "position": position or [400, 400],
        "typeVersion": 4.2,
        "alwaysOutputData": True,
    }


def supabase_insert(
    name: str,
    table: str,
    position: list[int] | None = None,
    return_rep: bool = True,
) -> dict[str, Any]:
    """HTTP Request node that inserts into Supabase. Body comes from previous node's JSON."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    prefer = "return=representation" if return_rep else "return=minimal"
    return {
        "parameters": {
            "method": "POST",
            "url": url,
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": SUPABASE_KEY},
                    {"name": "Authorization", "value": f"Bearer {SUPABASE_KEY}"},
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Prefer", "value": prefer},
                ]
            },
            "sendBody": True,
            "bodyParameters": {"parameters": []},
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json) }}",
            "options": {"response": {"response": {"responseFormat": "json"}}},
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "position": position or [600, 400],
        "typeVersion": 4.2,
    }


def supabase_update(
    name: str,
    table: str,
    match_col: str = "id",
    position: list[int] | None = None,
) -> dict[str, Any]:
    """HTTP Request PATCH to update a record. Uses $json.{match_col} for the filter."""
    url = f"={SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{{{{ $json.{match_col} }}}}"
    return {
        "parameters": {
            "method": "PATCH",
            "url": url,
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": SUPABASE_KEY},
                    {"name": "Authorization", "value": f"Bearer {SUPABASE_KEY}"},
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Prefer", "value": "return=representation"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json.updatePayload || $json) }}",
            "options": {"response": {"response": {"responseFormat": "json"}}},
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "position": position or [800, 400],
        "typeVersion": 4.2,
    }


def supabase_rpc(
    name: str,
    function_name: str,
    position: list[int] | None = None,
) -> dict[str, Any]:
    """HTTP Request POST to call a Supabase RPC function."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/{function_name}"
    return {
        "parameters": {
            "method": "POST",
            "url": url,
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": SUPABASE_KEY},
                    {"name": "Authorization", "value": f"Bearer {SUPABASE_KEY}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json) }}",
            "options": {"response": {"response": {"responseFormat": "json"}}},
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "position": position or [600, 400],
        "typeVersion": 4.2,
    }


# ============================================================
# STATUS & AUDIT NODES
# ============================================================

def portal_status_webhook(
    name: str,
    action: str,
    position: list[int] | None = None,
) -> dict[str, Any]:
    """POST status update to portal webhook. The Code node before this must set $json with the data."""
    url = f"{PORTAL_URL}/api/webhooks/n8n-accounting"
    return {
        "parameters": {
            "method": "POST",
            "url": url,
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "x-n8n-webhook-secret", "value": N8N_WEBHOOK_SECRET},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f'={{{{ JSON.stringify({{action: "{action}", data: $json}}) }}}}',
            "options": {
                "response": {"response": {"responseFormat": "json"}},
                "timeout": 10000,
            },
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "position": position or [1200, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    }


def audit_log_code(
    name: str,
    event_type: str,
    entity_type: str,
    actor: str,
    position: list[int] | None = None,
) -> dict[str, Any]:
    """Code node that prepares an audit log entry, then must connect to a Supabase insert or portal webhook."""
    js = (
        f"const item = $input.first().json;\n"
        f"return [{{\n"
        f"  json: {{\n"
        f"    client_id: item.client_id,\n"
        f"    event_type: '{event_type}',\n"
        f"    entity_type: '{entity_type}',\n"
        f"    entity_id: item.id || item.entity_id,\n"
        f"    action: '{event_type.lower()}',\n"
        f"    actor: '{actor}',\n"
        f"    result: 'success',\n"
        f"    metadata: {{ source: 'n8n' }}\n"
        f"  }}\n"
        f"}}];\n"
    )
    return {
        "parameters": {"jsCode": js},
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "position": position or [1000, 400],
        "typeVersion": 2,
    }


# ============================================================
# LOGIC NODES
# ============================================================

def code_node(
    name: str,
    js_code: str,
    position: list[int] | None = None,
) -> dict[str, Any]:
    """Generic JavaScript Code node."""
    return {
        "parameters": {"jsCode": js_code},
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "position": position or [600, 600],
        "typeVersion": 2,
    }


def set_node(
    name: str,
    assignments: list[dict[str, str]],
    position: list[int] | None = None,
) -> dict[str, Any]:
    """Set/Variable assignment node."""
    return {
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": a["name"], "value": a["value"], "type": a.get("type", "string")}
                    for a in assignments
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.set",
        "position": position or [400, 400],
        "typeVersion": 3.4,
    }


def if_node(
    name: str,
    left_value: str,
    operator_type: str,
    operation: str,
    right_value: str = "",
    position: list[int] | None = None,
) -> dict[str, Any]:
    """Conditional If node."""
    condition: dict[str, Any] = {
        "id": uid(),
        "leftValue": left_value,
        "operator": {"type": operator_type, "operation": operation},
    }
    if right_value:
        condition["rightValue"] = right_value
    return {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [condition],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "position": position or [800, 400],
        "typeVersion": 2,
    }


def switch_node(
    name: str,
    rules: list[dict[str, str]],
    position: list[int] | None = None,
) -> dict[str, Any]:
    """Switch node with string equality rules."""
    return {
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "conditions": [{
                                "leftValue": r["leftValue"],
                                "rightValue": r["rightValue"],
                                "operator": {"type": "string", "operation": "equals"},
                            }]
                        },
                        "renameOutput": True,
                        "outputKey": r["output"],
                    }
                    for r in rules
                ]
            },
            "options": {"fallbackOutput": "extra"},
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.switch",
        "position": position or [600, 400],
        "typeVersion": 3.2,
    }


def noop_node(name: str, position: list[int] | None = None) -> dict[str, Any]:
    """No operation (passthrough) node."""
    return {
        "parameters": {},
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.noOp",
        "position": position or [800, 800],
        "typeVersion": 1,
    }


def respond_webhook(
    name: str,
    position: list[int] | None = None,
) -> dict[str, Any]:
    """Respond to Webhook node (JSON response)."""
    return {
        "parameters": {
            "respondWith": "json",
            "options": {},
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.respondToWebhook",
        "position": position or [1400, 800],
        "typeVersion": 1.1,
    }


# ============================================================
# GMAIL NODE
# ============================================================

def gmail_send(
    name: str,
    to_expr: str,
    subject_expr: str,
    html_expr: str,
    cred: dict[str, str],
    position: list[int] | None = None,
) -> dict[str, Any]:
    """Gmail send node."""
    return {
        "parameters": {
            "sendTo": to_expr,
            "subject": subject_expr,
            "emailType": "html",
            "message": html_expr,
            "options": {"appendAttribution": False},
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.gmail",
        "position": position or [1200, 600],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": cred},
    }


# ============================================================
# OPENROUTER AI NODE (via HTTP Request)
# ============================================================

def openrouter_ai(
    name: str,
    system_prompt: str,
    user_prompt_expr: str,
    max_tokens: int = 1500,
    cred: dict[str, str] | None = None,
    position: list[int] | None = None,
) -> dict[str, Any]:
    """OpenRouter API call via HTTP Request."""
    body = (
        f'{{"model": "{OPENROUTER_MODEL}",'
        f' "messages": [{{"role": "system", "content": "{system_prompt}"}},'
        f' {{"role": "user", "content": "{{{{ $json.aiPrompt || \'{user_prompt_expr}\' }}}}"}}],'
        f' "max_tokens": {max_tokens}}}'
    )
    node: dict[str, Any] = {
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "HTTP-Referer", "value": "https://anyvisionmedia.com"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"={body}",
            "options": {"response": {"response": {"responseFormat": "json"}}},
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "position": position or [800, 600],
        "typeVersion": 4.2,
    }
    if cred:
        node["credentials"] = {"httpHeaderAuth": cred}
    return node


# ============================================================
# MULTI-TENANT CONFIG NODES
# ============================================================

def load_all_configs_node(
    name: str = "Load All Configs",
    position: list[int] | None = None,
) -> dict[str, Any]:
    """Fetch ALL active client configs from acct_config. Used by schedule-triggered
    workflows to iterate over every client. Returns array of config rows."""
    return supabase_select(
        name=name,
        table="acct_config",
        select="*",
        filters="order=created_at.asc",
        position=position or [400, 400],
    )


def load_config_for_client_node(
    name: str = "Load Client Config",
    position: list[int] | None = None,
) -> dict[str, Any]:
    """Code node that resolves config for a specific client.

    For webhooks: uses client_id from the request body.
    For schedule loops: uses client_id from the current loop item.
    Falls back to first config if no client_id is available (single-tenant mode).
    """
    js = (
        "// Resolve client_id from webhook body, loop item, or fallback\n"
        "const input = $input.first().json;\n"
        "const body = input.body || input;\n"
        "const clientId = body.client_id || input.client_id || null;\n"
        "\n"
        "if (!clientId) {\n"
        "  // Single-tenant fallback: pass through input as config\n"
        "  // (assumes input IS the config from Load All Configs loop)\n"
        "  return [{ json: { ...input, _configResolved: true } }];\n"
        "}\n"
        "\n"
        "// Multi-tenant: we have a client_id, pass it forward\n"
        "// The next node should fetch config filtered by this client_id\n"
        "return [{ json: { ...input, client_id: clientId, _configResolved: true } }];\n"
    )
    return code_node(name=name, js_code=js, position=position or [500, 400])


def client_loop_node(
    name: str = "Loop Per Client",
    position: list[int] | None = None,
) -> dict[str, Any]:
    """splitInBatches node that processes one client config at a time.
    Connect Load All Configs -> this -> per-client workflow logic."""
    return {
        "parameters": {"batchSize": 1, "options": {}},
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.splitInBatches",
        "position": position or [600, 400],
        "typeVersion": 3,
    }


def resolve_config_node(
    name: str = "Resolve Config",
    position: list[int] | None = None,
) -> dict[str, Any]:
    """Code node placed after client_loop that extracts config and client_id
    from the current loop item. Downstream nodes use $json.config.* and $json.client_id."""
    js = (
        "// Extract config from loop item (each item IS a config row from acct_config)\n"
        "const config = $input.first().json;\n"
        "return [{\n"
        "  json: {\n"
        "    client_id: config.client_id,\n"
        "    config: config,\n"
        "    vat_rate: parseFloat(config.vat_rate) || 0.15,\n"
        "    currency: config.default_currency || 'ZAR',\n"
        "    invoice_prefix: config.invoice_prefix || 'INV',\n"
        "    high_value_threshold: config.high_value_threshold || 5000000,\n"
        "    auto_approve_below: config.auto_approve_bills_below || 1000000,\n"
        "    accounting_software: config.accounting_software || 'none',\n"
        "    payment_gateway: config.payment_gateway || 'none',\n"
        "    ocr_provider: config.ocr_provider || 'ai',\n"
        "    comms_email: config.comms_email || 'gmail',\n"
        "    comms_chat: config.comms_chat || 'none',\n"
        "    reminder_cadence_days: config.reminder_cadence_days || [-3,0,3,7,14],\n"
        "    escalation_after_days: config.escalation_after_days || 14,\n"
        "    modules_enabled: config.modules_enabled || {},\n"
        "  }\n"
        "}];\n"
    )
    return code_node(name=name, js_code=js, position=position or [800, 400])


def supabase_select_for_client(
    name: str,
    table: str,
    select: str = "*",
    extra_filters: str = "",
    position: list[int] | None = None,
) -> dict[str, Any]:
    """Supabase select scoped to the current client_id from upstream.
    Uses expression to dynamically inject client_id filter."""
    base_filter = "client_id=eq.{{ $json.client_id }}"
    filters = f"{base_filter}&{extra_filters}" if extra_filters else base_filter
    url = f"={SUPABASE_URL}/rest/v1/{table}?select={select}&{filters}"
    return {
        "parameters": {
            "method": "GET",
            "url": url,
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": SUPABASE_KEY},
                    {"name": "Authorization", "value": f"Bearer {SUPABASE_KEY}"},
                ]
            },
            "options": {"response": {"response": {"responseFormat": "json"}}},
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "position": position or [600, 400],
        "typeVersion": 4.2,
        "alwaysOutputData": True,
    }


# ============================================================
# WORKFLOW ASSEMBLY
# ============================================================

def build_workflow_json(
    name: str,
    nodes: list[dict[str, Any]],
    connections: dict[str, Any],
) -> dict[str, Any]:
    """Assemble a complete n8n workflow JSON."""
    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def conn(target: str, index: int = 0) -> dict[str, Any]:
    """Shorthand for a connection entry."""
    return {"node": target, "type": "main", "index": index}

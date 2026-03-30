"""
Shared node-builder helpers for Financial Advisory n8n workflows.

All FA deploy scripts (deploy_fa_wf01.py through deploy_fa_wf10.py)
import these helpers to build n8n node dicts consistently.

Usage:
    from fa_helpers import (
        uid, conn, supabase_query_node, supabase_insert_node,
        supabase_update_node, supabase_rpc_node, outlook_send_node,
        teams_message_node, graph_api_node, ai_analysis_node,
        whatsapp_template_node, webhook_node, schedule_node,
        execute_workflow_trigger_node, execute_workflow_node,
        code_node, if_node, split_in_batches_node, switch_node,
        respond_to_webhook_node, merge_node, no_op_node,
    )
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from credentials import CRED_OUTLOOK_FA, CRED_OPENROUTER, CRED_AIRTABLE


# ============================================================
# Constants
# ============================================================

SUPABASE_URL = os.getenv(
    "SUPABASE_URL", "https://qfvsqjsrlnxjplqefhon.supabase.co"
)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
GRAPH_API_BASE = "https://graph.microsoft.com"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
WHATSAPP_API_BASE = "https://graph.facebook.com/v21.0"
FA_WHATSAPP_PHONE_ID = os.getenv("FA_WHATSAPP_PHONE_NUMBER_ID", "")


# ============================================================
# Utilities
# ============================================================


def uid() -> str:
    """Generate a UUID for n8n node IDs."""
    return str(uuid.uuid4())


def conn(node: str, index: int = 0, conn_type: str = "main") -> dict[str, Any]:
    """Build a connection target dict."""
    return {"node": node, "type": conn_type, "index": index}


def _base_node(
    name: str,
    node_type: str,
    type_version: float,
    position: list[int],
    parameters: dict[str, Any],
    credentials: dict[str, Any] | None = None,
    on_error: str | None = None,
    retry: bool = False,
) -> dict[str, Any]:
    """Build a base n8n node dict."""
    node: dict[str, Any] = {
        "id": uid(),
        "name": name,
        "type": node_type,
        "typeVersion": type_version,
        "position": position,
        "parameters": parameters,
    }
    if credentials:
        node["credentials"] = credentials
    if on_error:
        node["onError"] = on_error
    if retry:
        node["retryOnFail"] = True
        node["maxTries"] = 3
        node["waitBetweenTries"] = 2000
    return node


# ============================================================
# Supabase REST Nodes (via HTTP Request)
# ============================================================


def _supabase_headers() -> dict[str, str]:
    return {
        "apikey": "={{ $env.SUPABASE_ANON_KEY }}",
        "Authorization": "=Bearer {{ $env.SUPABASE_SERVICE_ROLE_KEY }}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def supabase_query_node(
    name: str,
    table: str,
    query_params: str,
    position: list[int],
    select: str = "*",
) -> dict[str, Any]:
    """HTTP Request GET to Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
    if query_params:
        url += f"&{query_params}"
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.httpRequest",
        type_version=4.2,
        position=position,
        parameters={
            "method": "GET",
            "url": url,
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": "={{ $env.SUPABASE_ANON_KEY }}"},
                    {
                        "name": "Authorization",
                        "value": "=Bearer {{ $env.SUPABASE_SERVICE_ROLE_KEY }}",
                    },
                ]
            },
            "options": {"response": {"response": {"fullResponse": False}}},
        },
        retry=True,
    )


def supabase_insert_node(
    name: str,
    table: str,
    body_expr: str,
    position: list[int],
) -> dict[str, Any]:
    """HTTP Request POST to Supabase REST API."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.httpRequest",
        type_version=4.2,
        position=position,
        parameters={
            "method": "POST",
            "url": f"{SUPABASE_URL}/rest/v1/{table}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": "={{ $env.SUPABASE_ANON_KEY }}"},
                    {
                        "name": "Authorization",
                        "value": "=Bearer {{ $env.SUPABASE_SERVICE_ROLE_KEY }}",
                    },
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Prefer", "value": "return=representation"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": body_expr,
            "options": {},
        },
        retry=True,
    )


def supabase_update_node(
    name: str,
    table: str,
    match_column: str,
    match_expr: str,
    body_expr: str,
    position: list[int],
) -> dict[str, Any]:
    """HTTP Request PATCH to Supabase REST API."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.httpRequest",
        type_version=4.2,
        position=position,
        parameters={
            "method": "PATCH",
            "url": f"={SUPABASE_URL}/rest/v1/{table}?{match_column}=eq.{match_expr}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": "={{ $env.SUPABASE_ANON_KEY }}"},
                    {
                        "name": "Authorization",
                        "value": "=Bearer {{ $env.SUPABASE_SERVICE_ROLE_KEY }}",
                    },
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Prefer", "value": "return=representation"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": body_expr,
            "options": {},
        },
        retry=True,
    )


def supabase_rpc_node(
    name: str,
    function_name: str,
    params_expr: str,
    position: list[int],
) -> dict[str, Any]:
    """HTTP Request POST to Supabase RPC endpoint."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.httpRequest",
        type_version=4.2,
        position=position,
        parameters={
            "method": "POST",
            "url": f"{SUPABASE_URL}/rest/v1/rpc/{function_name}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": "={{ $env.SUPABASE_ANON_KEY }}"},
                    {
                        "name": "Authorization",
                        "value": "=Bearer {{ $env.SUPABASE_SERVICE_ROLE_KEY }}",
                    },
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": params_expr,
            "options": {},
        },
        retry=True,
    )


# ============================================================
# Microsoft Outlook / Teams / Graph Nodes
# ============================================================


def outlook_send_node(
    name: str,
    to_expr: str,
    subject_expr: str,
    body_expr: str,
    position: list[int],
    body_content_type: str = "html",
) -> dict[str, Any]:
    """Microsoft Outlook v2 send message node."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.microsoftOutlook",
        type_version=2,
        position=position,
        parameters={
            "resource": "message",
            "operation": "send",
            "bodyContentType": body_content_type,
            "bodyContent": body_expr,
            "toRecipients": to_expr,
            "subject": subject_expr,
            "additionalFields": {},
        },
        credentials={"microsoftOutlookOAuth2Api": CRED_OUTLOOK_FA},
        retry=True,
    )


def teams_message_node(
    name: str,
    chat_id_expr: str,
    message_expr: str,
    position: list[int],
    content_type: str = "html",
) -> dict[str, Any]:
    """Microsoft Teams v2 chat message node."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.microsoftTeams",
        type_version=2,
        position=position,
        parameters={
            "resource": "chatMessage",
            "operation": "create",
            "chatId": chat_id_expr,
            "contentType": content_type,
            "message": message_expr,
        },
        credentials={"microsoftTeamsOAuth2Api": CRED_OUTLOOK_FA},
        retry=True,
    )


def graph_api_node(
    name: str,
    method: str,
    url_path: str,
    position: list[int],
    body_expr: str | None = None,
    api_version: str = "v1.0",
) -> dict[str, Any]:
    """HTTP Request to Microsoft Graph API with OAuth2 credential."""
    params: dict[str, Any] = {
        "method": method,
        "url": f"={GRAPH_API_BASE}/{api_version}{url_path}",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "microsoftOutlookOAuth2Api",
        "options": {},
    }
    if body_expr and method in ("POST", "PATCH", "PUT"):
        params["sendBody"] = True
        params["specifyBody"] = "json"
        params["jsonBody"] = body_expr
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.httpRequest",
        type_version=4.2,
        position=position,
        parameters=params,
        credentials={"microsoftOutlookOAuth2Api": CRED_OUTLOOK_FA},
        retry=True,
    )


# ============================================================
# AI Analysis Node (OpenRouter)
# ============================================================


def ai_analysis_node(
    name: str,
    system_prompt: str,
    user_prompt_expr: str,
    position: list[int],
    max_tokens: int = 4000,
    temperature: float = 0.3,
    model: str = "anthropic/claude-sonnet-4-20250514",
) -> dict[str, Any]:
    """HTTP Request POST to OpenRouter for AI analysis."""
    body = (
        '={\n'
        f'  "model": "{model}",\n'
        f'  "max_tokens": {max_tokens},\n'
        f'  "temperature": {temperature},\n'
        '  "messages": [\n'
        '    {"role": "system", "content": '
        + repr(system_prompt)
        + "},\n"
        '    {"role": "user", "content": '
        + user_prompt_expr
        + "}\n"
        "  ]\n"
        "}"
    )
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.httpRequest",
        type_version=4.2,
        position=position,
        parameters={
            "method": "POST",
            "url": OPENROUTER_URL,
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "Authorization",
                        "value": "=Bearer {{ $env.OPENROUTER_API_KEY }}",
                    },
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": body,
            "options": {},
        },
        retry=True,
    )


# ============================================================
# WhatsApp Cloud API Node
# ============================================================


def whatsapp_template_node(
    name: str,
    phone_expr: str,
    template_name: str,
    params_expr: str,
    position: list[int],
) -> dict[str, Any]:
    """HTTP Request POST to WhatsApp Cloud API for template messages."""
    body = (
        "={\n"
        '  "messaging_product": "whatsapp",\n'
        f'  "to": {phone_expr},\n'
        '  "type": "template",\n'
        '  "template": {\n'
        f'    "name": "{template_name}",\n'
        '    "language": {"code": "en"},\n'
        "    \"components\": [{\"type\": \"body\", \"parameters\": "
        + params_expr
        + "}]\n"
        "  }\n"
        "}"
    )
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.httpRequest",
        type_version=4.2,
        position=position,
        parameters={
            "method": "POST",
            "url": f"{WHATSAPP_API_BASE}/{FA_WHATSAPP_PHONE_ID}/messages",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "Authorization",
                        "value": "=Bearer {{ $env.FA_WHATSAPP_ACCESS_TOKEN }}",
                    },
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": body,
            "options": {},
        },
        retry=True,
    )


# ============================================================
# Standard n8n Nodes
# ============================================================


def webhook_node(
    name: str,
    path: str,
    position: list[int],
    http_method: str = "POST",
    response_mode: str = "responseNode",
) -> dict[str, Any]:
    """Webhook v1.1 trigger node."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.webhook",
        type_version=1.1,
        position=position,
        parameters={
            "path": path,
            "httpMethod": http_method,
            "responseMode": response_mode,
            "options": {},
        },
    )


def schedule_node(
    name: str,
    cron_expr: str,
    position: list[int],
) -> dict[str, Any]:
    """Schedule Trigger v1.2 node."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.scheduleTrigger",
        type_version=1.2,
        position=position,
        parameters={
            "rule": {
                "interval": [{"field": "cronExpression", "expression": cron_expr}]
            },
        },
    )


def execute_workflow_trigger_node(
    name: str,
    position: list[int],
) -> dict[str, Any]:
    """Execute Workflow Trigger v1.1 (sub-workflow entry point)."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.executeWorkflowTrigger",
        type_version=1.1,
        position=position,
        parameters={},
    )


def execute_workflow_node(
    name: str,
    workflow_id_expr: str,
    position: list[int],
    input_data_expr: str | None = None,
) -> dict[str, Any]:
    """Execute Workflow v1 (call sub-workflow)."""
    params: dict[str, Any] = {
        "source": "database",
        "workflowId": workflow_id_expr,
    }
    if input_data_expr:
        params["mode"] = "each"
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.executeWorkflow",
        type_version=1,
        position=position,
        parameters=params,
    )


def code_node(
    name: str,
    js_code: str,
    position: list[int],
) -> dict[str, Any]:
    """Code v2 node (JavaScript)."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.code",
        type_version=2,
        position=position,
        parameters={"jsCode": js_code, "mode": "runOnceForAllItems"},
    )


def if_node(
    name: str,
    conditions: list[dict[str, Any]],
    position: list[int],
    combinator: str = "and",
) -> dict[str, Any]:
    """If v2 node with strict type validation."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.if",
        type_version=2,
        position=position,
        parameters={
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": conditions,
                "combinator": combinator,
            },
            "options": {},
        },
    )


def switch_node(
    name: str,
    rules: list[dict[str, Any]],
    position: list[int],
    fallback_output: int = -1,
) -> dict[str, Any]:
    """Switch v3.2 node."""
    params: dict[str, Any] = {
        "rules": {"values": rules},
        "options": {},
    }
    if fallback_output >= 0:
        params["options"]["fallbackOutput"] = fallback_output
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.switch",
        type_version=3.2,
        position=position,
        parameters=params,
    )


def split_in_batches_node(
    name: str,
    position: list[int],
    batch_size: int = 1,
) -> dict[str, Any]:
    """Split In Batches v3 node."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.splitInBatches",
        type_version=3,
        position=position,
        parameters={"batchSize": batch_size, "options": {}},
    )


def respond_to_webhook_node(
    name: str,
    body_expr: str,
    position: list[int],
    status_code: int = 200,
) -> dict[str, Any]:
    """Respond to Webhook v1.1 node (JSON response)."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.respondToWebhook",
        type_version=1.1,
        position=position,
        parameters={
            "respondWith": "json",
            "responseBody": body_expr,
            "options": {"responseCode": status_code},
        },
    )


def merge_node(
    name: str,
    position: list[int],
    mode: str = "combineByPosition",
) -> dict[str, Any]:
    """Merge v3 node."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.merge",
        type_version=3,
        position=position,
        parameters={"combineBy": mode, "options": {}},
    )


def no_op_node(name: str, position: list[int]) -> dict[str, Any]:
    """No-op v1 node (routing placeholder)."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.noOp",
        type_version=1,
        position=position,
        parameters={},
    )


def airtable_create_node(
    name: str,
    base_id_expr: str,
    table_id_expr: str,
    columns: dict[str, str],
    position: list[int],
) -> dict[str, Any]:
    """Airtable v2.1 create record node."""
    return _base_node(
        name=name,
        node_type="n8n-nodes-base.airtable",
        type_version=2.1,
        position=position,
        parameters={
            "operation": "create",
            "base": {"__rl": True, "value": base_id_expr, "mode": "id"},
            "table": {"__rl": True, "value": table_id_expr, "mode": "id"},
            "columns": {"mappingMode": "defineBelow", "value": columns},
            "options": {},
        },
        credentials={"airtableTokenApi": CRED_AIRTABLE},
    )


# ============================================================
# Workflow Assembly Helpers
# ============================================================


def build_workflow(
    name: str,
    nodes: list[dict[str, Any]],
    connections: dict[str, Any],
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble a complete n8n workflow JSON.

    Only includes fields accepted by the n8n REST API v1:
    name, nodes, connections, settings.
    """
    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
        },
    }

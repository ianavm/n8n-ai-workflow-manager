"""
Deploys a reusable "Blotato Admin Proxy" workflow.

This workflow accepts a webhook POST with a dynamic Blotato API request
({method, path, body}) and forwards it to https://backend.blotato.com/v2/*
using the existing 'Blotato AVM' credential via predefinedCredentialType.

It's a Swiss-army utility for one-off Blotato API operations (get accounts,
list schedules, cancel posts, etc.) without having to build a new workflow
every time. Call it via n8n MCP's test_workflow or via direct webhook POST.

Usage:
    python tools/deploy_blotato_admin.py build
    python tools/deploy_blotato_admin.py deploy
    python tools/deploy_blotato_admin.py activate

Payload shape (POST body to the webhook):
    {
        "method": "GET" | "POST" | "DELETE" | "PUT" | "PATCH",
        "path": "/users/me/accounts/23022/subaccounts",
        "body": { ... optional ... }
    }
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))
from credentials import CRED_BLOTATO  # noqa: E402

WORKFLOW_NAME = "Blotato Admin Proxy"
WORKFLOW_FILENAME = "blotato_admin_proxy.json"
WEBHOOK_PATH = "blotato-admin-proxy"
BLOTATO_API_BASE = "https://backend.blotato.com/v2"


def uid() -> str:
    return str(uuid.uuid4())


def build_nodes() -> list[dict]:
    return [
        {
            "id": uid(),
            "name": "Webhook Trigger",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [200, 400],
            "webhookId": WEBHOOK_PATH,
            "parameters": {
                "httpMethod": "POST",
                "path": WEBHOOK_PATH,
                "responseMode": "lastNode",
                "options": {},
            },
        },
        {
            "id": uid(),
            "name": "Blotato HTTP",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [460, 400],
            "credentials": {"blotatoApi": CRED_BLOTATO},
            "parameters": {
                "method": "={{ $json.body?.method || $json.method || 'GET' }}",
                "url": (
                    "={{ '"
                    + BLOTATO_API_BASE
                    + "' + ($json.body?.path || $json.path || '') }}"
                ),
                "authentication": "predefinedCredentialType",
                "nodeCredentialType": "blotatoApi",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify($json.body?.body || $json.innerBody || {}) }}",
                "options": {"timeout": 60000},
            },
            "onError": "continueRegularOutput",
        },
        {
            "id": uid(),
            "name": "Wrap Response",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [720, 400],
            "parameters": {
                "jsCode": """const resp = $input.first().json || {};
return [{ json: { ok: !resp.error, response: resp } }];""",
            },
        },
    ]


def build_connections() -> dict:
    return {
        "Webhook Trigger": {"main": [[{"node": "Blotato HTTP", "type": "main", "index": 0}]]},
        "Blotato HTTP": {"main": [[{"node": "Wrap Response", "type": "main", "index": 0}]]},
    }


def build_workflow() -> dict:
    return {
        "name": WORKFLOW_NAME,
        "nodes": build_nodes(),
        "connections": build_connections(),
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


def save_workflow(workflow: dict) -> Path:
    output_dir = Path(__file__).parent.parent / "workflows"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / WORKFLOW_FILENAME
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    return output_path


def deploy_workflow(workflow: dict, activate: bool = False) -> str:
    from n8n_client import N8nClient

    api_key = os.getenv("N8N_API_KEY")
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    if not api_key:
        raise RuntimeError("N8N_API_KEY not set in .env")

    with N8nClient(base_url, api_key, timeout=30) as client:
        if not client.health_check()["connected"]:
            raise RuntimeError("Cannot connect to n8n")

        existing = None
        for wf in client.list_workflows():
            if wf["name"] == workflow["name"]:
                existing = wf
                break

        payload = {
            "name": workflow["name"],
            "nodes": workflow["nodes"],
            "connections": workflow["connections"],
            "settings": workflow["settings"],
        }

        if existing:
            result = client.update_workflow(existing["id"], payload)
            wf_id = result.get("id") or existing["id"]
            print(f"  Updated: {wf_id}")
        else:
            result = client.create_workflow(payload)
            wf_id = result.get("id")
            print(f"  Created: {wf_id}")

        if activate and wf_id:
            client.activate_workflow(wf_id)
            print("  Activated")

        return wf_id or ""


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "build"
    print(f"BLOTATO ADMIN PROXY: {action}")
    wf = build_workflow()
    print(f"  Saved: {save_workflow(wf)}")
    if action == "build":
        return
    if action in ("deploy", "activate"):
        wf_id = deploy_workflow(wf, activate=(action == "activate"))
        print(f"  Workflow ID: {wf_id}")
        print(f"  Webhook path: /{WEBHOOK_PATH}")


if __name__ == "__main__":
    main()

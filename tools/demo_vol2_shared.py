"""Shared helpers for Demo Pack Vol. 2 deploy scripts (DEMO-05 through DEMO-13).

All 9 workflows in the Vol. 2 demo pack use Google Sheets as their data
layer (Airtable quota reached) and share an identical deploy / save /
CLI harness. This module centralises:

    * Node factory helpers for the repeated node shapes (webhook,
      Demo Config, DEMO_MODE Switch, OpenRouter HTTP, Gmail send/draft,
      Google Sheets append/read/update, Slack webhook, respond, audit).
    * The build -> save -> deploy -> activate CLI loop.

Each deploy_demo_*.py script defines its own ``build_nodes`` and
``build_connections``, composes them with :func:`build_workflow_envelope`,
and calls :func:`run_cli`.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from dotenv import load_dotenv

# ------------------------------------------------------------------
# Env + credential bootstrap
# ------------------------------------------------------------------

_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_PATH)

sys.path.insert(0, str(Path(__file__).parent))

from credentials import CRED_GMAIL, CRED_GOOGLE_SHEETS, CRED_OPENROUTER  # noqa: E402

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_SONNET = "anthropic/claude-sonnet-4-20250514"
MODEL_HAIKU = "anthropic/claude-haiku-4-5"

DEMO_SHEET_ENV_KEY = "DEMO_SHEET_VOL2_ID"
SLACK_WEBHOOK_ENV_KEY = "SLACK_DEMO_WEBHOOK_URL"


def demo_sheet_id() -> str:
    """Resolve the master demo Sheet ID, with a placeholder fallback."""

    return os.getenv(DEMO_SHEET_ENV_KEY, "REPLACE_WITH_SHEET_ID")


def uid() -> str:
    return str(uuid.uuid4())


# ------------------------------------------------------------------
# Node factories
# ------------------------------------------------------------------


Position = tuple[int, int]


def webhook_trigger(
    path: str,
    *,
    name: str = "Webhook Trigger",
    method: str = "POST",
    response_mode: str = "responseNode",
    position: Position = (200, 300),
) -> dict:
    """Build a standard n8n webhook trigger node."""

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": list(position),
        "webhookId": path,
        "parameters": {
            "httpMethod": method,
            "path": path,
            "responseMode": response_mode,
            "options": {},
        },
    }


def schedule_trigger(
    *,
    name: str = "Daily 09:00 SAST",
    hour: int = 9,
    minute: int = 0,
    position: Position = (200, 520),
) -> dict:
    """Cron-style trigger that fires once a day at the given time."""

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": list(position),
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": f"0 {minute} {hour} * * *",
                    }
                ]
            }
        },
    }


def gmail_trigger(
    *,
    name: str = "Gmail Trigger",
    label_ids: Iterable[str] = ("INBOX",),
    position: Position = (200, 300),
) -> dict:
    """Poll Gmail for new messages matching the given labels."""

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.gmailTrigger",
        "typeVersion": 1.2,
        "position": list(position),
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "parameters": {
            "pollTimes": {"item": [{"mode": "everyMinute"}]},
            "simple": False,
            "filters": {"labelIds": list(label_ids)},
            "options": {},
        },
    }


def set_demo_config(
    *,
    fixture_payload: Any | None = None,
    extras: dict[str, str] | None = None,
    name: str = "Demo Config",
    position: Position = (420, 410),
) -> dict:
    """Build the canonical ``Demo Config`` Set node.

    ``fixture_payload`` is JSON-serialised once at build time and stored in a
    ``fixtureData`` string field the fixture loader parses at runtime.
    """

    assignments: list[dict[str, str]] = [
        {
            "id": uid(),
            "name": "demoMode",
            "type": "string",
            "value": "={{ String($json.demoMode ?? '1') }}",
        },
        {
            "id": uid(),
            "name": "runId",
            "type": "string",
            "value": "={{ 'RUN-' + $now.toFormat('yyyyLLdd-HHmmss') }}",
        },
        {
            "id": uid(),
            "name": "sheetId",
            "type": "string",
            "value": f"={{{{ $env.{DEMO_SHEET_ENV_KEY} || '{demo_sheet_id()}' }}}}",
        },
        {
            "id": uid(),
            "name": "slackWebhook",
            "type": "string",
            "value": f"={{{{ $env.{SLACK_WEBHOOK_ENV_KEY} || '' }}}}",
        },
    ]

    if fixture_payload is not None:
        assignments.append(
            {
                "id": uid(),
                "name": "fixtureData",
                "type": "string",
                "value": json.dumps(fixture_payload, ensure_ascii=False),
            }
        )

    for key, value in (extras or {}).items():
        assignments.append(
            {"id": uid(), "name": key, "type": "string", "value": value}
        )

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": list(position),
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {"assignments": assignments},
            "options": {},
        },
    }


def demo_mode_switch(
    *,
    name: str = "DEMO_MODE Switch",
    position: Position = (640, 410),
) -> dict:
    """Binary switch on ``demoMode`` — output 0 = demo, output 1 = live."""

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": list(position),
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "combinator": "and",
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.demoMode }}",
                                    "rightValue": "1",
                                    "operator": {
                                        "type": "string",
                                        "operation": "equals",
                                    },
                                }
                            ],
                        },
                        "outputKey": "demo",
                    },
                    {
                        "conditions": {
                            "combinator": "and",
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.demoMode }}",
                                    "rightValue": "0",
                                    "operator": {
                                        "type": "string",
                                        "operation": "equals",
                                    },
                                }
                            ],
                        },
                        "outputKey": "live",
                    },
                ]
            },
            "options": {"fallbackOutput": 0},
        },
    }


def code_node(
    name: str,
    js_code: str,
    *,
    position: Position = (860, 300),
    mode: str = "runOnceForAllItems",
) -> dict:
    """Wrap a JS snippet in an n8n Code node."""

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": list(position),
        "parameters": {"mode": mode, "jsCode": js_code},
    }


def openrouter_call(
    name: str,
    prompt_expr: str,
    *,
    model: str = MODEL_SONNET,
    temperature: float = 0.3,
    max_tokens: int = 1500,
    system_prompt: str | None = None,
    position: Position = (1520, 410),
) -> dict:
    """HTTP Request node that posts a single-message prompt to OpenRouter.

    ``prompt_expr`` must be a JS expression that resolves to the user content
    string (e.g. ``"$json.prompt"`` or ``"'Classify: ' + $json.text"``).
    """

    if system_prompt is None:
        body = (
            "={{ JSON.stringify({ "
            f"model: '{model}', "
            f"max_tokens: {max_tokens}, "
            f"temperature: {temperature}, "
            "messages: [{role: 'user', content: " + prompt_expr + "}] "
            "}) }}"
        )
    else:
        escaped_system = system_prompt.replace("\\", "\\\\").replace("'", "\\'")
        body = (
            "={{ JSON.stringify({ "
            f"model: '{model}', "
            f"max_tokens: {max_tokens}, "
            f"temperature: {temperature}, "
            "messages: ["
            f"{{role: 'system', content: '{escaped_system}'}}, "
            "{role: 'user', content: " + prompt_expr + "}"
            "] }) }}"
        )

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": list(position),
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "parameters": {
            "method": "POST",
            "url": OPENROUTER_URL,
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": body,
            "options": {"timeout": 60000},
        },
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 5000,
    }


def sheets_append(
    name: str,
    tab: str,
    column_map: dict[str, str],
    *,
    position: Position = (2200, 410),
) -> dict:
    """Append one row to the master demo sheet, resolving ``sheetId`` at runtime."""

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": list(position),
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "parameters": {
            "operation": "append",
            "documentId": {
                "__rl": True,
                "mode": "id",
                "value": "={{ $('Demo Config').first().json.sheetId }}",
            },
            "sheetName": {"__rl": True, "mode": "name", "value": tab},
            "columns": {
                "mappingMode": "defineBelow",
                "value": column_map,
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    }


def sheets_read(
    name: str,
    tab: str,
    *,
    position: Position = (860, 410),
    range_expr: str = "A:Z",
) -> dict:
    """Read all rows from a tab on the master demo sheet."""

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": list(position),
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "parameters": {
            "operation": "read",
            "documentId": {
                "__rl": True,
                "mode": "id",
                "value": "={{ $('Demo Config').first().json.sheetId }}",
            },
            "sheetName": {"__rl": True, "mode": "name", "value": tab},
            "options": {"range": range_expr},
        },
        "onError": "continueRegularOutput",
    }


def sheets_update(
    name: str,
    tab: str,
    column_map: dict[str, str],
    *,
    matching_column: str,
    position: Position = (2200, 410),
) -> dict:
    """Upsert a row on the master demo sheet keyed by ``matching_column``."""

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": list(position),
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "parameters": {
            "operation": "appendOrUpdate",
            "documentId": {
                "__rl": True,
                "mode": "id",
                "value": "={{ $('Demo Config').first().json.sheetId }}",
            },
            "sheetName": {"__rl": True, "mode": "name", "value": tab},
            "columns": {
                "mappingMode": "defineBelow",
                "value": column_map,
                "matchingColumns": [matching_column],
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    }


def gmail_send(
    name: str,
    *,
    to_expr: str,
    subject_expr: str,
    body_expr: str,
    position: Position = (1960, 260),
) -> dict:
    """Gmail send message node, HTML body."""

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": list(position),
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "parameters": {
            "sendTo": to_expr,
            "subject": subject_expr,
            "emailType": "html",
            "message": body_expr,
            "options": {"appendAttribution": False},
        },
    }


def gmail_draft(
    name: str,
    *,
    to_expr: str,
    subject_expr: str,
    body_expr: str,
    thread_id_expr: str | None = None,
    position: Position = (1960, 260),
) -> dict:
    """Save a draft in Gmail instead of sending."""

    params: dict[str, Any] = {
        "resource": "draft",
        "operation": "create",
        "subject": subject_expr,
        "message": body_expr,
        "emailType": "html",
        "options": {"sendTo": to_expr, "appendAttribution": False},
    }
    if thread_id_expr:
        params["options"]["threadId"] = thread_id_expr

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": list(position),
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "parameters": params,
    }


def slack_notify(
    name: str,
    text_expr: str,
    *,
    position: Position = (2440, 260),
) -> dict:
    """Post to the demo Slack webhook URL carried on Demo Config."""

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": list(position),
        "parameters": {
            "method": "POST",
            "url": (
                "={{ $('Demo Config').first().json.slackWebhook "
                "|| 'https://hooks.slack.com/services/DISABLED' }}"
            ),
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ text: " + text_expr + " }) }}",
            "options": {"timeout": 10000},
        },
        "onError": "continueRegularOutput",
    }


def audit_log(
    workflow_label: str,
    *,
    action_expr: str = "'run_complete'",
    status_expr: str = "'ok'",
    error_expr: str = "''",
    position: Position = (3120, 410),
) -> dict:
    """Append a single row to the ``Audit_Log`` tab summarising the run."""

    return sheets_append(
        "Audit Log",
        "Audit_Log",
        {
            "Workflow": f"'{workflow_label}'",
            "Run_ID": "={{ $('Demo Config').first().json.runId }}",
            "Timestamp": "={{ new Date().toISOString() }}",
            "Action": "={{ " + action_expr + " }}",
            "Status": "={{ " + status_expr + " }}",
            "Error_Message": "={{ " + error_expr + " }}",
        },
        position=position,
    )


def respond_to_webhook(
    *,
    name: str = "Respond",
    body_expr: str = "JSON.stringify($json)",
    position: Position = (3340, 410),
) -> dict:
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": list(position),
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ " + body_expr + " }}",
            "options": {},
        },
    }


# ------------------------------------------------------------------
# Envelope + build / save / deploy helpers
# ------------------------------------------------------------------


def build_workflow_envelope(
    name: str,
    nodes: list[dict],
    connections: dict[str, Any],
) -> dict:
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


def save_workflow(workflow: dict, filename: str) -> Path:
    output_dir = Path(__file__).parent.parent / "workflows" / "demos"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    return output_path


def deploy_workflow(workflow: dict, *, activate: bool = False) -> str:
    from n8n_client import N8nClient

    api_key = os.getenv("N8N_API_KEY")
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    if not api_key:
        raise RuntimeError("N8N_API_KEY not set in .env")

    with N8nClient(base_url, api_key, timeout=30) as client:
        health = client.health_check()
        if not health["connected"]:
            raise RuntimeError(f"Cannot connect to n8n: {health.get('error')}")

        existing = next(
            (wf for wf in client.list_workflows() if wf["name"] == workflow["name"]),
            None,
        )

        payload = {
            "name": workflow["name"],
            "nodes": workflow["nodes"],
            "connections": workflow["connections"],
            "settings": workflow["settings"],
        }
        if existing:
            result = client.update_workflow(existing["id"], payload)
            wf_id = result.get("id") or existing["id"]
        else:
            result = client.create_workflow(payload)
            wf_id = result.get("id")

        if activate and wf_id:
            client.activate_workflow(wf_id)

        return wf_id or ""


@dataclass(frozen=True)
class DemoSpec:
    """Single-source-of-truth descriptor passed to :func:`run_cli`."""

    workflow_name: str
    filename: str
    build_workflow: Callable[[], dict]
    preflight_warnings: Callable[[], list[str]] | None = None


def run_cli(spec: DemoSpec) -> None:
    """Drive the build/deploy/activate CLI for a single demo script."""

    action = sys.argv[1] if len(sys.argv) > 1 else "build"

    print("=" * 60)
    print(f"{spec.workflow_name}: {action}")
    print("=" * 60)

    if spec.preflight_warnings:
        for warn in spec.preflight_warnings():
            print(f"WARNING: {warn}")

    if demo_sheet_id() == "REPLACE_WITH_SHEET_ID":
        print(
            f"WARNING: {DEMO_SHEET_ENV_KEY} not set — sheet nodes will fail at "
            "runtime. Run: python tools/setup_demo_vol2_sheet.py"
        )
    if not os.getenv(SLACK_WEBHOOK_ENV_KEY):
        print(
            f"NOTE: {SLACK_WEBHOOK_ENV_KEY} not set — Slack nodes post to a "
            "disabled URL and fail soft."
        )

    workflow = spec.build_workflow()
    output_path = save_workflow(workflow, spec.filename)
    print(
        f"Built {len(workflow['nodes'])} nodes, "
        f"{len(workflow['connections'])} connections"
    )
    print(f"Saved: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' or 'activate' to push to n8n.")
        return

    if action in ("deploy", "activate"):
        print("\nDeploying to n8n...")
        wf_id = deploy_workflow(workflow, activate=(action == "activate"))
        print(f"\nWorkflow ID: {wf_id}")

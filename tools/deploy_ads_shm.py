"""
AVM Ads: Self-Healing Monitor — Deploy Script

Builds the ADS SHM workflow that checks all ADS workflows for recent failures
every 2 hours and reports via email + writes to the Postgres Brain.

Nodes:
    1. Schedule Trigger (cron: 0 */2 * * *)
    2. Check Recent Failures (GET n8n API executions?status=error)
    3. Analyze Failures (Code: filter ADS workflows, last 4 hours)
    4. Has Failures? (If: $json.healthy === false)
    5. Send Failure Summary (Gmail → ian@anyvisionmedia.com) — true branch
    6. All Healthy (NoOp) — false branch
    7. Write to Brain (Execute Workflow → Brain Writer) — parallel from step 3

Usage:
    python tools/deploy_ads_shm.py build      # Build JSON
    python tools/deploy_ads_shm.py deploy     # Build + Deploy (inactive)
    python tools/deploy_ads_shm.py activate   # Build + Deploy + Activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# ── Constants ──────────────────────────────────────────────────
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")

CRED_N8N_API = {
    "id": os.getenv("SELFHEALING_N8N_API_CRED_ID", "xymp9Nho08mRW2Wz"),
    "name": "n8n API Header Auth",
}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}

BRAIN_WF_ID = "XpGdo7DKv3XEpqZc"
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
WORKFLOW_NAME = "AVM Ads: Self-Healing Monitor"

# ADS workflow IDs to monitor
ADS_WORKFLOWS = {
    "mrzwNb9Eul9Lq2uM": "ADS-01 Strategy",
    "7BBjmuvwF1l8DMQX": "ADS-02 Creative",
    "rIYu0FHFx741ml8d": "ADS-04 Monitor",
    "cfDyiFLx0X89s3VL": "ADS-05 Optimizer",
    "bXxRU6rBC4kKw8bZ": "ADS-06 Recycler",
    "HkhBl7f69GckvEpY": "ADS-07 Attribution",
    "m8Kjjiy9jwliykOo": "ADS-08 Report",
}


def uid() -> str:
    return str(uuid.uuid4())


# ── Code Node Scripts ──────────────────────────────────────────

SCRIPT_ANALYZE = """
// Check for ADS workflow failures in the last 4 hours
const resp = $input.first().json;
const executions = resp.data || [];
const now = Date.now();
const fourHoursAgo = now - (4 * 60 * 60 * 1000);

// ADS workflow IDs to monitor (updated 2026-04-09)
const ADS_WORKFLOWS = {ADS_MAP};

const recentFailures = [];
for (const exec of executions) {
  if (!ADS_WORKFLOWS[exec.workflowId]) continue;
  const stoppedAt = new Date(exec.stoppedAt).getTime();
  if (stoppedAt < fourHoursAgo) continue;
  recentFailures.push({
    executionId: exec.id,
    workflowId: exec.workflowId,
    workflowName: ADS_WORKFLOWS[exec.workflowId],
    stoppedAt: exec.stoppedAt,
    status: exec.status,
  });
}

if (recentFailures.length === 0) {
  return [{json: {healthy: true, message: 'All ADS workflows healthy', checkedAt: new Date().toISOString()}}];
}

return [{json: {
  healthy: false,
  failureCount: recentFailures.length,
  failures: recentFailures,
  checkedAt: new Date().toISOString(),
}}];
""".replace(
    "{ADS_MAP}",
    json.dumps({k: v for k, v in ADS_WORKFLOWS.items()}, indent=2),
)


# ── Node Builders ──────────────────────────────────────────────

def build_nodes() -> list:
    nodes = []

    # 1. Schedule Trigger — every 2 hours
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "0 */2 * * *"}]
            }
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [250, 300],
        "typeVersion": 1.2,
    })

    # 2. Check Recent Failures — GET n8n API
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": f"{N8N_BASE_URL}/api/v1/executions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "status", "value": "error"},
                    {"name": "limit", "value": "20"},
                ]
            },
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Check Recent Failures",
        "type": "n8n-nodes-base.httpRequest",
        "position": [500, 300],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
    })

    # 3. Analyze Failures — Code node
    nodes.append({
        "parameters": {"jsCode": SCRIPT_ANALYZE},
        "id": uid(),
        "name": "Analyze Failures",
        "type": "n8n-nodes-base.code",
        "position": [750, 300],
        "typeVersion": 2,
    })

    # 4. Has Failures? — If node
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "combinator": "and",
                "conditions": [{
                    "leftValue": "={{$json.healthy}}",
                    "operator": {
                        "type": "boolean",
                        "operation": "false",
                        "singleValue": True,
                    },
                }],
            }
        },
        "id": uid(),
        "name": "Has Failures?",
        "type": "n8n-nodes-base.if",
        "position": [1000, 300],
        "typeVersion": 2.2,
    })

    # 5. Send Failure Summary — Gmail
    nodes.append({
        "parameters": {
            "operation": "send",
            "sendTo": ALERT_EMAIL,
            "subject": '={{"ADS Health Check: " + $json.failureCount + " failure(s) detected"}}',
            "emailType": "html",
            "message": '={{"<h2>ADS Self-Healing Monitor</h2><p>" + $json.failureCount + " failure(s) in last 4 hours:</p><pre>" + JSON.stringify($json.failures, null, 2) + "</pre><p>If failures persist, manual review is needed.</p>"}}',
            "options": {},
        },
        "id": uid(),
        "name": "Send Failure Summary",
        "type": "n8n-nodes-base.gmail",
        "position": [1250, 200],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # 6. All Healthy — NoOp
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "All Healthy",
        "type": "n8n-nodes-base.noOp",
        "position": [1250, 450],
        "typeVersion": 1,
    })

    # 7. Write to Brain — Execute Workflow
    nodes.append({
        "parameters": {
            "workflowId": {"__rl": True, "mode": "id", "value": BRAIN_WF_ID},
            "options": {"waitForSubWorkflow": False},
            "inputData": {
                "values": [
                    {"name": "source", "value": "=n8n:ADS-SHM"},
                    {"name": "source_type", "value": "=workflow"},
                    {
                        "name": "event_type",
                        "value": '={{ $json.healthy ? "execution_success" : "alert" }}',
                    },
                    {
                        "name": "severity",
                        "value": '={{ $json.healthy ? "info" : ($json.failureCount > 3 ? "critical" : "warning") }}',
                    },
                    {"name": "department", "value": "=ads"},
                    {
                        "name": "summary",
                        "value": '={{ $json.healthy ? "All ADS workflows healthy" : $json.failureCount + " ADS workflow failures detected" }}',
                    },
                    {"name": "details", "value": "={{ JSON.stringify($json) }}"},
                    {"name": "entity_id", "value": "=5k1OKJuaAWVPf7Lb"},
                    {"name": "entity_name", "value": "=ADS-SHM Self-Healing Monitor"},
                ],
            },
        },
        "id": uid(),
        "name": "Write to Brain",
        "type": "n8n-nodes-base.executeWorkflow",
        "position": [1000, 500],
        "typeVersion": 1.2,
        "onError": "continueRegularOutput",
    })

    return nodes


def build_connections() -> dict:
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Check Recent Failures", "type": "main", "index": 0}]]
        },
        "Check Recent Failures": {
            "main": [[{"node": "Analyze Failures", "type": "main", "index": 0}]]
        },
        "Analyze Failures": {
            "main": [[
                {"node": "Has Failures?", "type": "main", "index": 0},
                {"node": "Write to Brain", "type": "main", "index": 0},
            ]]
        },
        "Has Failures?": {
            "main": [
                [{"node": "Send Failure Summary", "type": "main", "index": 0}],
                [{"node": "All Healthy", "type": "main", "index": 0}],
            ]
        },
    }


def build() -> dict:
    return {
        "name": WORKFLOW_NAME,
        "nodes": build_nodes(),
        "connections": build_connections(),
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
    }


def save_json(workflow: dict) -> str:
    out_dir = Path(__file__).parent.parent / "workflows" / "brain"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "ads_shm.json"
    with open(path, "w") as f:
        json.dump(workflow, f, indent=2)
    print(f"  Saved: {path}")
    return str(path)


def deploy(workflow: dict) -> str:
    import httpx
    headers = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}

    resp = httpx.get(
        f"{N8N_BASE_URL}/api/v1/workflows",
        headers=headers,
        params={"limit": 100},
    )
    resp.raise_for_status()
    existing = [w for w in resp.json()["data"] if w["name"] == WORKFLOW_NAME]

    if existing:
        wf_id = existing[0]["id"]
        print(f"  Updating existing workflow {wf_id}...")
        resp = httpx.put(
            f"{N8N_BASE_URL}/api/v1/workflows/{wf_id}",
            headers=headers,
            json=workflow,
        )
    else:
        print("  Creating new workflow...")
        resp = httpx.post(
            f"{N8N_BASE_URL}/api/v1/workflows",
            headers=headers,
            json=workflow,
        )

    resp.raise_for_status()
    wf_id = resp.json()["id"]
    print(f"  Deployed: {WORKFLOW_NAME} ({wf_id})")
    return wf_id


def activate(wf_id: str) -> None:
    import httpx
    headers = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}
    resp = httpx.post(
        f"{N8N_BASE_URL}/api/v1/workflows/{wf_id}/activate",
        headers=headers,
    )
    resp.raise_for_status()
    print(f"  Activated: {wf_id}")


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "build"

    print(f"\n{'='*60}")
    print(f"  AVM Ads: Self-Healing Monitor — {action.upper()}")
    print(f"{'='*60}\n")

    workflow = build()
    save_json(workflow)

    if action in ("deploy", "activate"):
        wf_id = deploy(workflow)
        if action == "activate":
            activate(wf_id)

    print("\n  Done.\n")


if __name__ == "__main__":
    main()

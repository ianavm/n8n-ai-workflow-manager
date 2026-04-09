"""
ADS Comprehensive Fix — 2026-04-09

Patches ALL live ADS workflows to match updated deploy scripts:

1. ADS-07: Add continueOnFail to Write Attribution
2. ADS-08: Switch Log Report Event from autoMapInputData to defineBelow
3. ADS-05: Switch Log Auto Changes + Create Approval Requests to defineBelow
4. ADS-02: Add empty-result guard (Has Campaigns?) before Route by Platform
5. ADS-SHM: Fix broken $input/$json references + stale ADS-06 workflow ID

Credential fix (Header Auth account 2 → X-N8N-API-KEY) already applied via API.

Usage:
    python tools/fix_ads_comprehensive_2026_04_09.py
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from config_loader import load_config
from n8n_client import N8nClient

# Live workflow IDs
WF_ADS_02 = "7BBjmuvwF1l8DMQX"
WF_ADS_05 = "cfDyiFLx0X89s3VL"
WF_ADS_07 = "HkhBl7f69GckvEpY"
WF_ADS_08 = "m8Kjjiy9jwliykOo"
WF_ADS_SHM = "5k1OKJuaAWVPf7Lb"

# Airtable refs
ORCH_BASE_ID = "appTCh0EeXQp0XqzW"
TABLE_ORCH_EVENTS = "tblgHAw52EyUcIkWR"
MARKETING_BASE_ID = "apptjjBx34z9340tK"
TABLE_APPROVALS = "tblov57B8uj09ZF2k"
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Whatsapp Multi Agent"}


def uid() -> str:
    return str(uuid.uuid4())


def build_client(config: dict) -> N8nClient:
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def deploy(client: N8nClient, wf_id: str, wf: dict) -> dict:
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    return client.update_workflow(wf_id, payload)


# ─────────────────────────────────────────────────────────────
# FIX 1: ADS-07 — Add continueOnFail to Write Attribution
# ─────────────────────────────────────────────────────────────

def fix_ads07(client: N8nClient) -> bool:
    print("\n" + "=" * 60)
    print("FIX 1: ADS-07 — Add continueOnFail to Write Attribution")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_07)
    node_map = {n["name"]: n for n in wf["nodes"]}

    write_node = node_map.get("Write Attribution")
    if not write_node:
        print("  ERROR: 'Write Attribution' not found")
        return False

    if write_node.get("continueOnFail"):
        print("  SKIP: continueOnFail already set")
        return True

    write_node["continueOnFail"] = True
    print("  Added continueOnFail: true")

    deploy(client, WF_ADS_07, wf)
    print("  Deployed ADS-07")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 2: ADS-08 — Switch Log Report Event to defineBelow
# ─────────────────────────────────────────────────────────────

def fix_ads08(client: N8nClient) -> bool:
    print("\n" + "=" * 60)
    print("FIX 2: ADS-08 — Switch Log Report Event to defineBelow")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_08)
    node_map = {n["name"]: n for n in wf["nodes"]}

    log_node = node_map.get("Log Report Event")
    if not log_node:
        print("  ERROR: 'Log Report Event' not found")
        return False

    mapping = log_node["parameters"].get("columns", {}).get("mappingMode", "")
    if mapping == "defineBelow":
        print("  SKIP: Already using defineBelow")
        return True

    print(f"  Current mappingMode: {mapping}")
    log_node["parameters"]["columns"] = {
        "mappingMode": "defineBelow",
        "value": {
            "Event Type": "={{ $json['Event Type'] }}",
            "Source Agent": "={{ $json['Source Agent'] }}",
            "Priority": "={{ $json['Priority'] }}",
            "Status": "={{ $json['Status'] }}",
            "Payload": "={{ $json['Payload'] }}",
            "Created At": "={{ $json['Created At'] }}",
        },
    }
    log_node["continueOnFail"] = True
    print("  Switched to defineBelow with explicit field mapping")

    deploy(client, WF_ADS_08, wf)
    print("  Deployed ADS-08")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 3: ADS-05 — Switch both Airtable nodes to defineBelow
# ─────────────────────────────────────────────────────────────

APPROVAL_FIELDS = {
    "Campaign Name": "={{ $json['Campaign Name'] }}",
    "Request Type": "={{ $json['Request Type'] }}",
    "Requested By": "={{ $json['Requested By'] }}",
    "Status": "={{ $json['Status'] }}",
    "Details": "={{ $json['Details'] }}",
    "Created At": "={{ $json['Created At'] }}",
}


def fix_ads05(client: N8nClient) -> bool:
    print("\n" + "=" * 60)
    print("FIX 3: ADS-05 — Switch Airtable nodes to defineBelow")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_05)
    node_map = {n["name"]: n for n in wf["nodes"]}

    changed = False
    for name in ["Log Auto Changes", "Create Approval Requests"]:
        node = node_map.get(name)
        if not node:
            print(f"  WARNING: '{name}' not found")
            continue

        mapping = node["parameters"].get("columns", {}).get("mappingMode", "")
        if mapping == "defineBelow":
            print(f"  SKIP: '{name}' already uses defineBelow")
            continue

        print(f"  [{name}] {mapping} -> defineBelow")
        node["parameters"]["columns"] = {
            "mappingMode": "defineBelow",
            "value": dict(APPROVAL_FIELDS),
        }
        changed = True

    if not changed:
        print("  No changes needed")
        return True

    deploy(client, WF_ADS_05, wf)
    print("  Deployed ADS-05")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 4: ADS-02 — Add empty-result guard before Switch
# ─────────────────────────────────────────────────────────────

def fix_ads02(client: N8nClient) -> bool:
    print("\n" + "=" * 60)
    print("FIX 4: ADS-02 — Add empty-result guard before Switch")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_02)
    node_map = {n["name"]: n for n in wf["nodes"]}

    if "Has Campaigns?" in node_map:
        print("  SKIP: 'Has Campaigns?' guard already exists")
        return True

    read_node = node_map.get("Read Campaign Plans")
    switch_node = node_map.get("Route by Platform")
    if not read_node or not switch_node:
        print("  ERROR: Required nodes not found")
        return False

    # Position between Read and Switch
    rx, ry = read_node["position"]
    sx, sy = switch_node["position"]
    mid_x = (rx + sx) // 2
    mid_y = (ry + sy) // 2

    guard_node = {
        "id": uid(),
        "name": "Has Campaigns?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [mid_x, mid_y],
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "combinator": "and",
                "conditions": [
                    {
                        "leftValue": "={{$input.all().length > 0}}",
                        "operator": {
                            "type": "boolean",
                            "operation": "true",
                            "singleValue": True,
                        },
                    }
                ],
            },
        },
    }
    wf["nodes"].append(guard_node)

    # Rewire: Read Campaign Plans -> Has Campaigns? -> Route by Platform
    conns = wf["connections"]
    conns["Read Campaign Plans"]["main"][0] = [
        {"node": "Has Campaigns?", "type": "main", "index": 0}
    ]
    conns["Has Campaigns?"] = {
        "main": [
            [{"node": "Route by Platform", "type": "main", "index": 0}],
            [],
        ]
    }

    print("  Inserted 'Has Campaigns?' If node")
    print("  Rewired: Read Campaign Plans -> Has Campaigns? -> Route by Platform")
    print("  False branch (no campaigns) terminates gracefully")

    deploy(client, WF_ADS_02, wf)
    print("  Deployed ADS-02")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 5: ADS-SHM — Fix broken expressions + stale workflow ID
# ─────────────────────────────────────────────────────────────

SHM_ANALYZE_CODE = r"""
// Check for ADS workflow failures in the last 4 hours
const resp = $input.first().json;
const executions = resp.data || [];
const now = Date.now();
const fourHoursAgo = now - (4 * 60 * 60 * 1000);

// ADS workflow IDs to monitor (updated 2026-04-09)
const ADS_WORKFLOWS = {
  'mrzwNb9Eul9Lq2uM': 'ADS-01 Strategy',
  '7BBjmuvwF1l8DMQX': 'ADS-02 Creative',
  'rIYu0FHFx741ml8d': 'ADS-04 Monitor',
  'cfDyiFLx0X89s3VL': 'ADS-05 Optimizer',
  'bXxRU6rBC4kKw8bZ': 'ADS-06 Recycler',
  'HkhBl7f69GckvEpY': 'ADS-07 Attribution',
  'm8Kjjiy9jwliykOo': 'ADS-08 Report',
};

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
"""


def fix_ads_shm(client: N8nClient) -> bool:
    print("\n" + "=" * 60)
    print("FIX 5: ADS-SHM — Fix expressions + stale workflow ID")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_SHM)
    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    # Fix Analyze Failures code node
    code_node = node_map.get("Analyze Failures")
    if code_node:
        old_code = code_node["parameters"].get("jsCode", "")
        if "$input" not in old_code or "vOal0o4dGC1K4VML" in old_code:
            code_node["parameters"]["jsCode"] = SHM_ANALYZE_CODE
            changes.append("Analyze Failures: fixed $input ref + updated ADS-06 ID")
        else:
            changes.append("Analyze Failures: already correct")

    # Fix Has Failures? If node — broken $json ref
    if_node = node_map.get("Has Failures?")
    if if_node:
        conditions = if_node["parameters"].get("conditions", {}).get("conditions", [])
        if conditions and "={{.healthy}}" in str(conditions[0].get("leftValue", "")):
            conditions[0]["leftValue"] = "={{$json.healthy}}"
            changes.append("Has Failures?: fixed $json.healthy reference")
        else:
            changes.append("Has Failures?: already correct")

    # Fix Send Failure Summary Gmail node — broken $json refs
    gmail_node = node_map.get("Send Failure Summary")
    if gmail_node:
        params = gmail_node["parameters"]
        fixed_gmail = False
        if ".failureCount" in params.get("subject", "") and "$json" not in params.get("subject", ""):
            params["subject"] = '={{"ADS Health Check: " + $json.failureCount + " failure(s) detected"}}'
            fixed_gmail = True
        if ".failureCount" in params.get("message", "") and "$json" not in params.get("message", ""):
            params["message"] = (
                '={{"<h2>ADS Self-Healing Monitor</h2>'
                '<p>" + $json.failureCount + " failure(s) in last 4 hours:</p>'
                '<pre>" + JSON.stringify($json.failures, null, 2) + "</pre>'
                '<p>If failures persist, manual review is needed.</p>"}}'
            )
            fixed_gmail = True
        changes.append(f"Send Failure Summary: {'fixed $json refs' if fixed_gmail else 'already correct'}")

    for c in changes:
        print(f"  {c}")

    deploy(client, WF_ADS_SHM, wf)
    print("  Deployed ADS-SHM")
    return True


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    config = load_config()
    client = build_client(config)

    print("ADS Comprehensive Fix — 2026-04-09")
    print("=" * 60)

    results = {}
    results["ADS-07 continueOnFail"] = fix_ads07(client)
    results["ADS-08 defineBelow"] = fix_ads08(client)
    results["ADS-05 defineBelow"] = fix_ads05(client)
    results["ADS-02 empty guard"] = fix_ads02(client)
    results["ADS-SHM expressions"] = fix_ads_shm(client)

    print("\n" + "=" * 60)
    print("RESULTS:")
    for name, ok in results.items():
        print(f"  {name}: {'SUCCESS' if ok else 'FAILED'}")
    all_ok = all(results.values())
    print(f"\nOverall: {'ALL PASSED' if all_ok else 'SOME FAILED'}")
    print("=" * 60)

    if not all_ok:
        sys.exit(1)

"""
ADS-07 & ADS-08 — Fix Priority/Status select values (2026-04-09)

Both workflows' Code nodes were manually patched to use Priority='Low' and
Status='Resolved', but the Orchestrator_Events table (tblgHAw52EyUcIkWR)
uses P1/P2/P3/P4 and Pending/Processing/Completed/Failed.

This restores the correct values matching the deploy script and Airtable schema.

Usage:
    python tools/fix_ads07_priority_2026_04_09.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from config_loader import load_config
from n8n_client import N8nClient

WF_ADS_07 = "HkhBl7f69GckvEpY"
WF_ADS_08 = "m8Kjjiy9jwliykOo"

ADS07_CORRECT_CODE = r"""
// Transform AI Attribution Analyst response into Orchestrator Events fields
const aiResp = $input.first().json;
const content = aiResp.choices?.[0]?.message?.content || JSON.stringify(aiResp);

return [{json: {
  'Event Type': 'kpi_update',
  'Source Agent': 'ADS-07',
  'Priority': 'P4',
  'Status': 'Completed',
  'Payload': typeof content === 'string' ? content : JSON.stringify(content),
  'Created At': new Date().toISOString(),
}}];
"""

ADS08_CORRECT_CODE = r"""
// Transform Gmail send response into Orchestrator Events fields
const gmailResp = $input.first().json;

return [{json: {
  'Event Type': 'kpi_update',
  'Source Agent': 'ADS-08',
  'Priority': 'P4',
  'Status': 'Completed',
  'Payload': JSON.stringify({
    messageId: gmailResp.id || '',
    threadId: gmailResp.threadId || '',
    sentAt: new Date().toISOString(),
  }),
  'Created At': new Date().toISOString(),
}}];
"""


def build_client(config: dict) -> N8nClient:
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def deploy(client: N8nClient, wf_id: str, wf: dict) -> dict:
    """Push updated workflow to n8n."""
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    return client.update_workflow(wf_id, payload)


def _detect_values(code: str) -> tuple[str, str]:
    """Detect current Priority and Status values in JS code."""
    low = "'Low'"
    p4 = "'P4'"
    resolved = "'Resolved'"
    completed = "'Completed'"
    priority = "Low" if low in code else "P4" if p4 in code else "UNKNOWN"
    status = "Resolved" if resolved in code else "Completed" if completed in code else "UNKNOWN"
    return priority, status


def fix_code_node(client: N8nClient, wf_id: str, wf_label: str,
                  code_node_name: str, correct_code: str) -> bool:
    """Fix Priority/Status values in a Code node."""
    print(f"\n{'=' * 60}")
    print(f"FIX: {wf_label} — Correct Priority/Status in '{code_node_name}'")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    node_map = {n["name"]: n for n in wf["nodes"]}

    code_node = node_map.get(code_node_name)
    if not code_node:
        print(f"  ERROR: '{code_node_name}' node not found")
        return False

    current_code = code_node["parameters"].get("jsCode", "")
    priority_val, status_val = _detect_values(current_code)
    print(f"  Current Priority: {priority_val}")
    print(f"  Current Status:   {status_val}")

    if priority_val == "P4" and status_val == "Completed":
        print("  SKIP: Values already correct (P4/Completed)")
        return True

    code_node["parameters"]["jsCode"] = correct_code
    print(f"  Updated Priority: {priority_val} -> P4")
    print(f"  Updated Status:   {status_val} -> Completed")

    deploy(client, wf_id, wf)
    print(f"  Deployed {wf_label} successfully")
    return True


if __name__ == "__main__":
    config = load_config()
    c = build_client(config)

    print("ADS Orchestrator Events — Fix Priority/Status Select Values")
    print("=" * 60)

    results = {}

    results["ADS-07"] = fix_code_node(
        c, WF_ADS_07, "ADS-07 Attribution Engine",
        "Format Attribution Data", ADS07_CORRECT_CODE,
    )

    results["ADS-08"] = fix_code_node(
        c, WF_ADS_08, "ADS-08 Reporting Dashboard",
        "Format Report Log", ADS08_CORRECT_CODE,
    )

    print("\n" + "=" * 60)
    print("RESULTS:")
    for name, ok in results.items():
        print(f"  {name}: {'SUCCESS' if ok else 'FAILED'}")
    print("=" * 60)

    if not all(results.values()):
        sys.exit(1)

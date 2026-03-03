"""Fix the Parse Airtable Response node code in the follow-up workflow."""

import sys
import json
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

FU_WORKFLOW_ID = Path(__file__).parent.parent / ".tmp" / "follow_up_workflow_id.txt"


PARSE_CODE = "\n".join([
    "const resp = $input.first().json;",
    "const records = resp.records || [];",
    "if (records.length === 0) return [];",
    "return records.map(r => ({ json: { id: r.id, fields: r.fields } }));",
])


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    workflow_id = FU_WORKFLOW_ID.read_text().strip()
    print(f"Workflow ID: {workflow_id}")

    with httpx.Client(timeout=120) as client:
        resp = client.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers)
        wf = resp.json()

        for node in wf["nodes"]:
            if node["name"] == "Parse Airtable Response":
                node["parameters"]["jsCode"] = PARSE_CODE
                print(f"Fixed Parse code. Preview: {PARSE_CODE[:80]}...")
                break

        # Deploy
        client.post(f"{base_url}/api/v1/workflows/{workflow_id}/deactivate", headers=headers)
        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{workflow_id}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        client.post(f"{base_url}/api/v1/workflows/{workflow_id}/activate", headers=headers)

        print("Deployed. Waiting 8s...")
        time.sleep(8)

        # Find the test webhook path
        webhook_path = None
        for node in wf["nodes"]:
            if node["name"] == "Test Webhook":
                webhook_path = node["parameters"]["path"]
                break

        if webhook_path:
            print(f"Triggering: {base_url}/webhook/{webhook_path}")
            trigger_resp = client.post(
                f"{base_url}/webhook/{webhook_path}",
                json={"test": True},
                timeout=120
            )
            print(f"Trigger response: {trigger_resp.status_code}")
            if trigger_resp.status_code == 200:
                print(f"Success! Response: {trigger_resp.text[:300]}")
            else:
                print(f"Error: {trigger_resp.text[:300]}")

            # Check execution
            time.sleep(10)
            resp = client.get(
                f"{base_url}/api/v1/executions?workflowId={workflow_id}&limit=2&includeData=true",
                headers=headers
            )
            execs = resp.json().get("data", [])
            for ex in execs[:1]:
                print(f"\n=== Execution {ex['id']}: {ex['status']} ===")
                rd = ex.get("data", {}).get("resultData", {})
                if ex["status"] == "error":
                    err = rd.get("error", {})
                    print(f"  ERROR: {err.get('message', '')[:300]}")
                    print(f"  Node: {rd.get('lastNodeExecuted', 'unknown')}")
                run_data = rd.get("runData", {})
                for node_name, runs in sorted(run_data.items()):
                    if "note" in node_name.lower() or "sticky" in node_name.lower():
                        continue
                    for run in runs:
                        items = run.get("data", {}).get("main", [[]])[0]
                        err_msg = ""
                        if run.get("error"):
                            err_msg = f" ERROR: {run['error'].get('message', '')[:150]}"
                        print(f"  {node_name}: {len(items)} items{err_msg}")


if __name__ == "__main__":
    main()

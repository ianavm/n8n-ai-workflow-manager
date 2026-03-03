"""Quick scraper workflow test with maxResults=3."""

import sys
import json
import uuid
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

WORKFLOW_ID = "uq4hnH0YHfhYOOzO"


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    with httpx.Client(timeout=180) as client:
        # Get workflow and temporarily set maxResults to 3
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        wf = resp.json()

        for node in wf["nodes"]:
            if node["name"] == "Search Config":
                code = node["parameters"]["jsCode"]
                code = code.replace("maxResults: 20", "maxResults: 3")
                node["parameters"]["jsCode"] = code
                break

        # Add webhook
        wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "Test Webhook"]
        wf["connections"].pop("Test Webhook", None)

        webhook_path = f"test-scraper-{uuid.uuid4().hex[:8]}"
        wf["nodes"].append({
            "parameters": {
                "httpMethod": "POST",
                "path": webhook_path,
                "responseMode": "lastNode",
                "options": {}
            },
            "id": str(uuid.uuid4()),
            "name": "Test Webhook",
            "type": "n8n-nodes-base.webhook",
            "position": [200, 800],
            "typeVersion": 2,
            "webhookId": str(uuid.uuid4())
        })
        wf["connections"]["Test Webhook"] = {
            "main": [[{"node": "Search Config", "type": "main", "index": 0}]]
        }

        # Deploy
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/deactivate", headers=headers)
        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers, json=payload)
        resp.raise_for_status()
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate", headers=headers)

        print(f"Deployed with maxResults=3")
        print(f"Waiting 8s...")
        time.sleep(8)

        print(f"Triggering: {base_url}/webhook/{webhook_path}")
        trigger_resp = client.post(
            f"{base_url}/webhook/{webhook_path}",
            json={"test": True},
            timeout=180
        )
        print(f"Trigger response: {trigger_resp.status_code}")

        # Wait for pipeline to complete (scraping takes time)
        time.sleep(10)

        # Check execution
        resp = client.get(
            f"{base_url}/api/v1/executions?workflowId={WORKFLOW_ID}&limit=3&includeData=true",
            headers=headers
        )
        execs = resp.json().get("data", [])

        for ex in execs[:2]:
            status = ex["status"]
            ex_id = ex["id"]
            print(f"\n=== Execution {ex_id}: {status} ===")

            rd = ex.get("data", {}).get("resultData", {})
            if status == "error":
                err = rd.get("error", {})
                safe_msg = err.get("message", "").encode("ascii", "replace").decode("ascii")
                print(f"  ERROR: {safe_msg[:300]}")
                print(f"  Node: {rd.get('lastNodeExecuted', 'unknown')}")

            run_data = rd.get("runData", {})
            for node_name, runs in sorted(run_data.items()):
                if "note" in node_name.lower() or "sticky" in node_name.lower():
                    continue
                for run in runs:
                    items = run.get("data", {}).get("main", [[]])[0]
                    err_msg = ""
                    if run.get("error"):
                        e = run["error"].get("message", "").encode("ascii", "replace").decode("ascii")
                        err_msg = f" ERROR: {e[:100]}"
                    print(f"  {node_name}: {len(items)} items{err_msg}")

        # Cleanup: restore maxResults and remove webhook
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        wf = resp.json()
        wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "Test Webhook"]
        wf["connections"].pop("Test Webhook", None)

        for node in wf["nodes"]:
            if node["name"] == "Search Config":
                code = node["parameters"]["jsCode"]
                code = code.replace("maxResults: 3", "maxResults: 20")
                node["parameters"]["jsCode"] = code
                break

        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/deactivate", headers=headers)
        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        client.put(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers, json=payload)
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate", headers=headers)
        print("\nRestored maxResults=20, removed webhook, activated")


if __name__ == "__main__":
    main()

"""
Test the Follow-Up Sequence workflow end-to-end.

1. Set a test lead's Next Follow Up Date to today so it gets picked up
2. Add a temp Webhook trigger to the follow-up workflow
3. Trigger via production webhook (with retry)
4. Wait for execution and check results
5. Clean up (remove webhook)
"""

import os
import sys
import json
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

FU_WORKFLOW_ID = Path(__file__).parent.parent / ".tmp" / "follow_up_workflow_id.txt"
AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_TABLE_ID = "tblOsuh298hB9WWrA"


def get_latest_execution(client, base_url, headers, workflow_id):
    """Get the most recent execution for a workflow."""
    resp = client.get(
        f"{base_url}/api/v1/executions?workflowId={workflow_id}&limit=1",
        headers=headers
    )
    data = resp.json().get("data", [])
    return data[0] if data else None


def main():
    config = load_config()
    n8n_api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    n8n_headers = {"X-N8N-API-KEY": n8n_api_key, "Content-Type": "application/json"}

    airtable_token = os.getenv("AIRTABLE_API_TOKEN")
    if not airtable_token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)
    at_headers = {
        "Authorization": f"Bearer {airtable_token}",
        "Content-Type": "application/json"
    }

    workflow_id = FU_WORKFLOW_ID.read_text().strip()
    print(f"Follow-Up Workflow: {workflow_id}")

    with httpx.Client(timeout=120) as client:
        # Record the latest execution ID BEFORE our test
        before_exec = get_latest_execution(client, base_url, n8n_headers, workflow_id)
        before_exec_id = before_exec["id"] if before_exec else None
        print(f"Last execution before test: {before_exec_id}")

        # === STEP 1: Find a test lead with Stage >= 1 ===
        print("\n--- Step 1: Find a test lead ---")
        at_url = (
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
            f"?filterByFormula=AND({{Follow Up Stage}}>=1,{{Follow Up Stage}}<=4)"
            f"&maxRecords=5"
        )
        resp = client.get(at_url, headers=at_headers)
        resp.raise_for_status()
        records = resp.json().get("records", [])

        if not records:
            print("ERROR: No leads with Follow Up Stage >= 1 found. Cannot test.")
            return

        test_record = records[0]
        test_id = test_record["id"]
        test_fields = test_record["fields"]
        test_email = test_fields.get("Email", "unknown")
        original_date = test_fields.get("Next Follow Up Date", "")
        original_stage = test_fields.get("Follow Up Stage", 1)
        print(f"Test lead: {test_email} (record: {test_id})")
        print(f"  Current stage: {original_stage}, Next FU date: {original_date}")

        # === STEP 2: Set Next Follow Up Date to today ===
        print("\n--- Step 2: Set follow-up date to today ---")
        today = "2026-02-20"
        patch_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}/{test_id}"
        resp = client.patch(
            patch_url,
            headers=at_headers,
            json={"fields": {"Next Follow Up Date": today}, "typecast": True}
        )
        resp.raise_for_status()
        print(f"  Set Next Follow Up Date to {today}")

        # === STEP 3: Add temp webhook and deploy ===
        print("\n--- Step 3: Add temp webhook trigger ---")
        resp = client.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=n8n_headers)
        wf = resp.json()

        webhook_path = "test-fu-" + str(uuid.uuid4())[:8]
        webhook_node = {
            "parameters": {"path": webhook_path, "options": {}, "responseMode": "lastNode"},
            "id": str(uuid.uuid4()),
            "name": "Test Webhook Trigger",
            "type": "n8n-nodes-base.webhook",
            "position": [100, 100],
            "typeVersion": 2,
            "webhookId": str(uuid.uuid4())
        }
        wf["nodes"].append(webhook_node)

        # Connect webhook to Check Bounced Emails
        wf["connections"]["Test Webhook Trigger"] = {
            "main": [[{"node": "Check Bounced Emails", "type": "main", "index": 0}]]
        }

        # Deploy
        client.post(f"{base_url}/api/v1/workflows/{workflow_id}/deactivate", headers=n8n_headers)
        time.sleep(2)

        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{workflow_id}",
            headers=n8n_headers,
            json=payload
        )
        resp.raise_for_status()

        resp = client.post(f"{base_url}/api/v1/workflows/{workflow_id}/activate", headers=n8n_headers)
        print(f"  Deployed with webhook path: {webhook_path}")

        # Wait for webhook registration
        print("  Waiting 8s for webhook registration...")
        time.sleep(8)

        # === STEP 4: Trigger the webhook ===
        print("\n--- Step 4: Trigger follow-up workflow ---")
        webhook_url = f"{base_url}/webhook/{webhook_path}"
        print(f"  Trying: {webhook_url}")

        triggered = False
        for attempt in range(3):
            try:
                resp = client.post(webhook_url, json={"test": True}, timeout=90)
                print(f"  Attempt {attempt+1}: status={resp.status_code}")
                if resp.status_code == 200:
                    triggered = True
                    print(f"  Webhook triggered successfully!")
                    break
                elif resp.status_code == 404:
                    print(f"  Webhook not found yet, waiting 5s...")
                    time.sleep(5)
            except httpx.ReadTimeout:
                print(f"  Attempt {attempt+1}: timed out (workflow may still be running)")
                triggered = True  # Timeout usually means it's processing
                break
            except Exception as e:
                print(f"  Attempt {attempt+1}: {e}")
                time.sleep(5)

        if not triggered:
            print("  WARNING: Could not trigger webhook. Checking for new executions anyway...")

        # === STEP 5: Wait and check execution ===
        print("\n--- Step 5: Check execution results ---")
        # Poll for a new execution (different from before_exec_id)
        new_exec = None
        for wait in range(12):  # Up to 60 seconds
            time.sleep(5)
            latest = get_latest_execution(client, base_url, n8n_headers, workflow_id)
            if latest and latest["id"] != before_exec_id:
                new_exec = latest
                print(f"  New execution found: {new_exec['id']} (status: {new_exec.get('status')})")
                # Wait for it to finish if still running
                if not new_exec.get("finished", False) and new_exec.get("status") != "error":
                    print(f"  Still running, waiting...")
                    continue
                break
            print(f"  Waiting for execution... ({(wait+1)*5}s)")

        if not new_exec:
            print("  ERROR: No new execution found after 60s")
            # Still cleanup
        elif new_exec:
            exec_id = new_exec["id"]
            status = new_exec.get("status", "unknown")
            finished = new_exec.get("finished", False)
            print(f"\n  Execution: {exec_id}")
            print(f"  Status: {status}, Finished: {finished}")

            # Get full execution data
            resp = client.get(
                f"{base_url}/api/v1/executions/{exec_id}?includeData=true",
                headers=n8n_headers
            )
            exec_data = resp.json()

            if "data" in exec_data and "resultData" in exec_data["data"]:
                run_data = exec_data["data"]["resultData"]["runData"]
                print(f"\n  Nodes executed ({len(run_data)}):")
                errors = []
                for node_name, node_runs in run_data.items():
                    if node_name == "Test Webhook Trigger":
                        continue
                    run = node_runs[0] if node_runs else {}
                    items_out = 0
                    err_msg = ""
                    if run.get("error"):
                        err_msg = run['error'].get('message', 'unknown')[:100]
                        errors.append(f"{node_name}: {err_msg}")
                    elif run.get("data") and run["data"].get("main"):
                        for output in run["data"]["main"]:
                            if output:
                                items_out += len(output)
                    status_str = f"ERROR: {err_msg}" if err_msg else "OK"
                    print(f"    {node_name}: {status_str} ({items_out} items)")

                # Show key results
                for key_node in ["Aggregate Follow-Up Results", "Send Follow-Up Summary"]:
                    if key_node in run_data:
                        runs = run_data[key_node]
                        if runs and runs[0].get("data", {}).get("main"):
                            for output in runs[0]["data"]["main"]:
                                if output:
                                    for item in output:
                                        j = item.get("json", {})
                                        if j:
                                            print(f"\n  {key_node} output:")
                                            print(f"    {json.dumps(j, indent=2)[:600]}")

                if errors:
                    print(f"\n  ERRORS FOUND:")
                    for e in errors:
                        print(f"    - {e}")
                else:
                    print(f"\n  ALL NODES EXECUTED SUCCESSFULLY")

        # === STEP 6: Clean up ===
        print("\n--- Step 6: Cleanup ---")
        resp = client.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=n8n_headers)
        wf = resp.json()

        wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "Test Webhook Trigger"]
        if "Test Webhook Trigger" in wf["connections"]:
            del wf["connections"]["Test Webhook Trigger"]

        client.post(f"{base_url}/api/v1/workflows/{workflow_id}/deactivate", headers=n8n_headers)
        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{workflow_id}",
            headers=n8n_headers,
            json=payload
        )
        resp.raise_for_status()
        client.post(f"{base_url}/api/v1/workflows/{workflow_id}/activate", headers=n8n_headers)
        print("  Removed test webhook, workflow re-activated")

        # Verify
        resp = client.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=n8n_headers)
        final = resp.json()
        func_nodes = [n for n in final["nodes"] if "stickyNote" not in n["type"]]
        print(f"  Final: {len(func_nodes)} functional nodes, Active: {final.get('active')}")

        print("\n=== FOLLOW-UP WORKFLOW TEST COMPLETE ===")


if __name__ == "__main__":
    main()

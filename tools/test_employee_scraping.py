"""
Test the enhanced employee email scraping by triggering the scraper
with a small maxResults (3) and checking if sub-pages were scraped.
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

WORKFLOW_ID = "uq4hnH0YHfhYOOzO"


def get_latest_execution(client, base_url, headers, workflow_id):
    resp = client.get(
        f"{base_url}/api/v1/executions?workflowId={workflow_id}&limit=1",
        headers=headers
    )
    data = resp.json().get("data", [])
    return data[0] if data else None


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    h = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    with httpx.Client(timeout=120) as c:
        # Record last execution
        before = get_latest_execution(c, base_url, h, WORKFLOW_ID)
        before_id = before["id"] if before else None
        print(f"Last execution before test: {before_id}")

        # Temporarily reduce maxResults to 3 for quick test
        print("\nSetting maxResults=3 for test...")
        resp = c.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=h)
        wf = resp.json()

        # Save original Search Config code
        original_code = None
        for node in wf["nodes"]:
            if node["name"] == "Search Config":
                original_code = node["parameters"]["jsCode"]
                # Replace maxResults: 20 with maxResults: 3
                node["parameters"]["jsCode"] = original_code.replace(
                    "maxResults: 20", "maxResults: 3"
                )
                break

        # Set schedule trigger to fire every 1 minute
        original_schedule = None
        for node in wf["nodes"]:
            if node["name"] == "Schedule Trigger":
                original_schedule = json.dumps(node["parameters"])
                node["parameters"] = {
                    "rule": {"interval": [{"field": "minutes", "minutesInterval": 1}]}
                }
                break

        # Deploy
        c.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/deactivate", headers=h)
        time.sleep(2)
        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = c.put(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=h, json=payload)
        resp.raise_for_status()
        c.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate", headers=h)
        print("Deployed with maxResults=3 and 1-minute schedule")

        # Wait for new execution
        print("\nWaiting for execution...")
        new_exec = None
        for i in range(24):  # Up to 4 minutes
            time.sleep(10)
            latest = get_latest_execution(c, base_url, h, WORKFLOW_ID)
            if latest and latest["id"] != before_id:
                status = latest.get("status", "?")
                finished = latest.get("finished", False)
                print(f"  [{(i+1)*10}s] New execution: {latest['id']} status={status}")
                if finished or status in ("error", "success"):
                    new_exec = latest
                    break
            else:
                print(f"  [{(i+1)*10}s] Waiting...")

        if new_exec:
            exec_id = new_exec["id"]
            print(f"\nExecution {exec_id} - Status: {new_exec.get('status')}")

            # Get full details
            resp = c.get(f"{base_url}/api/v1/executions/{exec_id}?includeData=true", headers=h)
            exec_data = resp.json()

            if "data" in exec_data and "resultData" in exec_data["data"]:
                run_data = exec_data["data"]["resultData"]["runData"]
                print(f"\nNodes executed ({len(run_data)}):")
                errors = []
                for node_name, node_runs in run_data.items():
                    run = node_runs[0] if node_runs else {}
                    items_out = 0
                    err_msg = ""
                    if run.get("error"):
                        err_msg = run['error'].get('message', 'unknown')[:120]
                        errors.append(f"{node_name}: {err_msg}")
                    elif run.get("data") and run["data"].get("main"):
                        for output in run["data"]["main"]:
                            if output:
                                items_out += len(output)
                    status_str = f"ERROR: {err_msg}" if err_msg else "OK"
                    print(f"  {node_name}: {status_str} ({items_out} items)")

                # Show Extract Contact Info results
                if "Extract Contact Info" in run_data:
                    runs = run_data["Extract Contact Info"]
                    for run in runs:
                        if run.get("data", {}).get("main"):
                            for output in run["data"]["main"]:
                                if output:
                                    for item in output:
                                        j = item.get("json", {})
                                        if j:
                                            biz = j.get("businessName", "?")
                                            emails = j.get("emails", [])
                                            email_data = j.get("emailData", [])
                                            pages = j.get("pagesScraped", 0)
                                            print(f"\n  Business: {biz}")
                                            print(f"  Pages scraped: {pages}")
                                            print(f"  Emails found: {len(emails)}")
                                            for ed in email_data:
                                                name = ed.get("contactName", "")
                                                personal = ed.get("isPersonal", False)
                                                e = ed.get("email", "")
                                                tag = "[PERSONAL]" if personal else "[GENERIC]"
                                                name_str = f" ({name})" if name else ""
                                                print(f"    {tag} {e}{name_str}")

                if errors:
                    print(f"\nERRORS:")
                    for e in errors:
                        print(f"  - {e}")
                else:
                    print(f"\nALL NODES EXECUTED SUCCESSFULLY")
        else:
            print("\nTIMEOUT: No new execution found")

        # === RESTORE ORIGINAL SETTINGS ===
        print("\nRestoring original settings...")
        resp = c.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=h)
        wf = resp.json()

        for node in wf["nodes"]:
            if node["name"] == "Search Config" and original_code:
                node["parameters"]["jsCode"] = original_code
            if node["name"] == "Schedule Trigger" and original_schedule:
                node["parameters"] = json.loads(original_schedule)

        c.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/deactivate", headers=h)
        time.sleep(2)
        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = c.put(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=h, json=payload)
        resp.raise_for_status()
        c.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate", headers=h)
        print("Restored maxResults=20 and daily 9AM schedule")

        print("\n=== TEST COMPLETE ===")


if __name__ == "__main__":
    main()

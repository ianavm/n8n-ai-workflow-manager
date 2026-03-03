"""
Full revision test: End-to-end verification of both workflows.

1. Scraper workflow: trigger, verify Search Config code node, pipeline, area rotation
2. Follow-up workflow: trigger, verify bounce detection, follow-up email, Airtable update

Usage:
    python tools/full_revision_test.py
"""

import sys
import json
import uuid
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

SCRAPER_WORKFLOW_ID = "uq4hnH0YHfhYOOzO"
FU_WORKFLOW_ID_FILE = Path(__file__).parent.parent / ".tmp" / "follow_up_workflow_id.txt"


def add_test_webhook(client, headers, base_url, workflow_id, target_node):
    """Add a temporary webhook trigger to a workflow, returns webhook path."""
    resp = client.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers)
    wf = resp.json()

    # Remove old test webhook
    wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "Test Webhook"]
    wf["connections"].pop("Test Webhook", None)

    webhook_path = f"test-rev-{uuid.uuid4().hex[:8]}"
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
        "main": [[{"node": target_node, "type": "main", "index": 0}]]
    }

    client.post(f"{base_url}/api/v1/workflows/{workflow_id}/deactivate", headers=headers)
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"})
    }
    resp = client.put(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers, json=payload)
    resp.raise_for_status()
    client.post(f"{base_url}/api/v1/workflows/{workflow_id}/activate", headers=headers)

    return webhook_path, wf


def remove_test_webhook(client, headers, base_url, workflow_id):
    """Remove the temporary webhook trigger."""
    resp = client.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers)
    wf = resp.json()
    wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "Test Webhook"]
    wf["connections"].pop("Test Webhook", None)

    client.post(f"{base_url}/api/v1/workflows/{workflow_id}/deactivate", headers=headers)
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"})
    }
    resp = client.put(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers, json=payload)
    resp.raise_for_status()
    client.post(f"{base_url}/api/v1/workflows/{workflow_id}/activate", headers=headers)


def check_execution(client, headers, base_url, workflow_id, label=""):
    """Check the latest execution for a workflow."""
    resp = client.get(
        f"{base_url}/api/v1/executions?workflowId={workflow_id}&limit=1&includeData=true",
        headers=headers
    )
    execs = resp.json().get("data", [])
    if not execs:
        print(f"  [{label}] No executions found")
        return None

    ex = execs[0]
    status = ex["status"]
    ex_id = ex["id"]
    print(f"\n  [{label}] Execution {ex_id}: {status}")

    rd = ex.get("data", {}).get("resultData", {})
    if status == "error":
        err = rd.get("error", {})
        print(f"    ERROR: {err.get('message', '')[:300]}")
        print(f"    Node: {rd.get('lastNodeExecuted', 'unknown')}")

    run_data = rd.get("runData", {})
    node_results = {}
    for node_name, runs in sorted(run_data.items()):
        if "note" in node_name.lower() or "sticky" in node_name.lower():
            continue
        for run in runs:
            items = run.get("data", {}).get("main", [[]])[0]
            err_msg = ""
            if run.get("error"):
                err_msg = f" ERROR: {run['error'].get('message', '')[:100]}"
            node_results[node_name] = {"items": len(items), "error": err_msg}
            print(f"    {node_name}: {len(items)} items{err_msg}")

    return {"status": status, "id": ex_id, "nodes": node_results}


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}
    fu_workflow_id = FU_WORKFLOW_ID_FILE.read_text().strip()

    issues = []

    with httpx.Client(timeout=180) as client:
        # ============================================================
        # TEST 1: SCRAPER WORKFLOW
        # ============================================================
        print("=" * 60)
        print("TEST 1: SCRAPER WORKFLOW")
        print("=" * 60)

        # Temporarily set maxResults to 3 for quick test
        resp = client.get(f"{base_url}/api/v1/workflows/{SCRAPER_WORKFLOW_ID}", headers=headers)
        wf = resp.json()
        original_max_results = None
        for node in wf["nodes"]:
            if node["name"] == "Search Config":
                code = node["parameters"]["jsCode"]
                if "maxResults: 20" in code:
                    original_max_results = "20"
                    code = code.replace("maxResults: 20", "maxResults: 3")
                    node["parameters"]["jsCode"] = code
                    print("  Set maxResults to 3 for test")
                break

        # Save the modified workflow temporarily (we'll add webhook later)
        client.post(f"{base_url}/api/v1/workflows/{SCRAPER_WORKFLOW_ID}/deactivate", headers=headers)
        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        client.put(f"{base_url}/api/v1/workflows/{SCRAPER_WORKFLOW_ID}", headers=headers, json=payload)
        client.post(f"{base_url}/api/v1/workflows/{SCRAPER_WORKFLOW_ID}/activate", headers=headers)

        # Add webhook
        webhook_path, _ = add_test_webhook(
            client, headers, base_url, SCRAPER_WORKFLOW_ID, "Search Config"
        )

        print(f"  Webhook: {base_url}/webhook/{webhook_path}")
        print("  Waiting 8s for n8n to register...")
        time.sleep(8)

        print("  Triggering scraper workflow...")
        trigger_resp = client.post(
            f"{base_url}/webhook/{webhook_path}",
            json={"test": True},
            timeout=180
        )
        print(f"  Trigger response: {trigger_resp.status_code}")

        time.sleep(5)
        result = check_execution(client, headers, base_url, SCRAPER_WORKFLOW_ID, "SCRAPER")

        if result:
            nodes = result.get("nodes", {})

            # Check critical nodes
            if "Search Config" not in nodes:
                issues.append("SCRAPER: Search Config node did not execute")
            elif nodes["Search Config"]["error"]:
                issues.append(f"SCRAPER: Search Config error: {nodes['Search Config']['error']}")

            if "Places Text Search" not in nodes:
                issues.append("SCRAPER: Places Text Search did not execute")
            elif nodes["Places Text Search"]["items"] == 0:
                issues.append("SCRAPER: Places Text Search returned 0 results")

            if "Score Leads" in nodes and nodes["Score Leads"]["items"] > 0:
                print(f"\n    Score Leads found {nodes['Score Leads']['items']} leads")

            if "Upsert to Airtable" in nodes:
                print(f"    Upserted {nodes['Upsert to Airtable']['items']} to Airtable")

            if "Filter New Leads" in nodes:
                print(f"    New leads: {nodes['Filter New Leads']['items']}")

            if "Aggregate Results" not in nodes:
                issues.append("SCRAPER: Aggregate Results did not execute")
            elif nodes["Aggregate Results"]["error"]:
                issues.append(f"SCRAPER: Aggregate Results error: {nodes['Aggregate Results']['error']}")

            if "Update Lead Status" in nodes and nodes["Update Lead Status"]["error"]:
                issues.append(f"SCRAPER: Update Lead Status error: {nodes['Update Lead Status']['error']}")

            if result["status"] == "error":
                issues.append(f"SCRAPER: Execution failed")
        else:
            issues.append("SCRAPER: No execution found after trigger")

        # Cleanup: remove webhook, restore maxResults
        remove_test_webhook(client, headers, base_url, SCRAPER_WORKFLOW_ID)
        if original_max_results:
            resp = client.get(f"{base_url}/api/v1/workflows/{SCRAPER_WORKFLOW_ID}", headers=headers)
            wf = resp.json()
            for node in wf["nodes"]:
                if node["name"] == "Search Config":
                    code = node["parameters"]["jsCode"]
                    code = code.replace("maxResults: 3", f"maxResults: {original_max_results}")
                    node["parameters"]["jsCode"] = code
                    break
            client.post(f"{base_url}/api/v1/workflows/{SCRAPER_WORKFLOW_ID}/deactivate", headers=headers)
            payload = {
                "name": wf["name"],
                "nodes": wf["nodes"],
                "connections": wf["connections"],
                "settings": wf.get("settings", {"executionOrder": "v1"})
            }
            client.put(f"{base_url}/api/v1/workflows/{SCRAPER_WORKFLOW_ID}", headers=headers, json=payload)
            client.post(f"{base_url}/api/v1/workflows/{SCRAPER_WORKFLOW_ID}/activate", headers=headers)
            print("\n  Restored maxResults to 20, removed webhook")

        # ============================================================
        # TEST 2: FOLLOW-UP WORKFLOW
        # ============================================================
        print("\n" + "=" * 60)
        print("TEST 2: FOLLOW-UP WORKFLOW")
        print("=" * 60)

        # First ensure we have a lead ready for follow-up
        # Reset test lead to Stage 1, Next FU = today
        import os
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")
        at_token = os.getenv("AIRTABLE_API_TOKEN")

        # Check if our test lead needs resetting
        resp = httpx.get(
            "https://api.airtable.com/v0/app2ALQUP7CKEkHOz/tblOsuh298hB9WWrA/recQenRhvflMCzlHw",
            headers={"Authorization": f"Bearer {at_token}"},
            timeout=30
        )
        test_lead = resp.json()["fields"]
        current_stage = test_lead.get("Follow Up Stage", 0)
        print(f"  Test lead (La Piazza): Stage={current_stage}, Status={test_lead.get('Status')}")

        if current_stage >= 4 or current_stage == 0:
            # Reset for testing
            httpx.patch(
                "https://api.airtable.com/v0/app2ALQUP7CKEkHOz/tblOsuh298hB9WWrA/recQenRhvflMCzlHw",
                headers={"Authorization": f"Bearer {at_token}", "Content-Type": "application/json"},
                json={
                    "fields": {
                        "Follow Up Stage": 1,
                        "Next Follow Up Date": "2026-02-20",
                        "Status": "Email Sent"
                    },
                    "typecast": True
                },
                timeout=30
            )
            print("  Reset test lead to Stage 1, Next FU = today")

        # Add webhook to follow-up workflow
        webhook_path, _ = add_test_webhook(
            client, headers, base_url, fu_workflow_id, "Check Bounced Emails"
        )

        print(f"  Webhook: {base_url}/webhook/{webhook_path}")
        print("  Waiting 8s for n8n to register...")
        time.sleep(8)

        print("  Triggering follow-up workflow...")
        trigger_resp = client.post(
            f"{base_url}/webhook/{webhook_path}",
            json={"test": True},
            timeout=180
        )
        print(f"  Trigger response: {trigger_resp.status_code}")

        time.sleep(10)
        result = check_execution(client, headers, base_url, fu_workflow_id, "FOLLOW-UP")

        if result:
            nodes = result.get("nodes", {})

            # Check bounce detection
            if "Check Bounced Emails" not in nodes:
                issues.append("FOLLOW-UP: Check Bounced Emails did not execute")
            elif nodes["Check Bounced Emails"]["error"]:
                issues.append(f"FOLLOW-UP: Check Bounced Emails error: {nodes['Check Bounced Emails']['error']}")
            else:
                print(f"\n    Bounce check: {nodes['Check Bounced Emails']['items']} bounce emails found")

            if "Extract Bounced Addresses" in nodes:
                print(f"    Bounced addresses extracted: {nodes['Extract Bounced Addresses']['items']}")

            if "Fetch Due Follow-Ups" in nodes:
                print(f"    Leads due for follow-up: {nodes['Fetch Due Follow-Ups']['items']}")

            if "Parse Airtable Response" in nodes:
                if nodes["Parse Airtable Response"]["error"]:
                    issues.append(f"FOLLOW-UP: Parse error: {nodes['Parse Airtable Response']['error']}")

            if "Prepare Follow-Up Context" in nodes:
                if nodes["Prepare Follow-Up Context"]["error"]:
                    issues.append(f"FOLLOW-UP: Prepare context error: {nodes['Prepare Follow-Up Context']['error']}")

            if "AI Generate Follow-Up" in nodes:
                if nodes["AI Generate Follow-Up"]["error"]:
                    issues.append(f"FOLLOW-UP: AI generation error: {nodes['AI Generate Follow-Up']['error']}")

            if "Format Follow-Up Email" in nodes:
                if nodes["Format Follow-Up Email"]["error"]:
                    issues.append(f"FOLLOW-UP: Format email error: {nodes['Format Follow-Up Email']['error']}")

            if "Send Follow-Up Email" in nodes:
                if nodes["Send Follow-Up Email"]["error"]:
                    issues.append(f"FOLLOW-UP: Send email error: {nodes['Send Follow-Up Email']['error']}")
                else:
                    print(f"    Follow-up email sent: {nodes['Send Follow-Up Email']['items']}")

            if "Update Follow-Up Stage" in nodes:
                if nodes["Update Follow-Up Stage"]["error"]:
                    issues.append(f"FOLLOW-UP: Airtable update error: {nodes['Update Follow-Up Stage']['error']}")
                else:
                    print(f"    Airtable stage updated: {nodes['Update Follow-Up Stage']['items']}")

            if "Send Follow-Up Summary" in nodes:
                print(f"    Summary email sent: {nodes['Send Follow-Up Summary']['items']}")

            if result["status"] == "error":
                issues.append(f"FOLLOW-UP: Execution failed")
        else:
            issues.append("FOLLOW-UP: No execution found after trigger")

        # Verify Airtable was updated
        resp = httpx.get(
            "https://api.airtable.com/v0/app2ALQUP7CKEkHOz/tblOsuh298hB9WWrA/recQenRhvflMCzlHw",
            headers={"Authorization": f"Bearer {at_token}"},
            timeout=30
        )
        test_lead = resp.json()["fields"]
        print(f"\n  Test lead after follow-up:")
        print(f"    Status: {test_lead.get('Status')}")
        print(f"    Follow Up Stage: {test_lead.get('Follow Up Stage')}")
        print(f"    Next Follow Up Date: {test_lead.get('Next Follow Up Date')}")

        new_stage = test_lead.get("Follow Up Stage", 0)
        if new_stage <= 1:
            issues.append(f"FOLLOW-UP: Airtable stage not advanced (still {new_stage})")

        # Cleanup: remove webhook
        remove_test_webhook(client, headers, base_url, fu_workflow_id)
        print("\n  Removed test webhook")

        # ============================================================
        # FINAL REPORT
        # ============================================================
        print("\n" + "=" * 60)
        print("FULL REVISION REPORT")
        print("=" * 60)

        # Verify both workflows are active
        for wf_id, name in [(SCRAPER_WORKFLOW_ID, "Scraper"), (fu_workflow_id, "Follow-Up")]:
            resp = client.get(f"{base_url}/api/v1/workflows/{wf_id}", headers=headers)
            wf = resp.json()
            active = wf.get("active")
            node_count = len([n for n in wf["nodes"] if "stickyNote" not in n["type"]])
            print(f"\n  {name} Workflow:")
            print(f"    ID: {wf_id}")
            print(f"    Active: {active}")
            print(f"    Nodes: {node_count}")
            if not active:
                issues.append(f"{name}: Workflow is not active!")

        if issues:
            print(f"\n  ISSUES FOUND ({len(issues)}):")
            for i, issue in enumerate(issues, 1):
                print(f"    {i}. {issue}")
        else:
            print("\n  ALL CHECKS PASSED - Both workflows are working correctly!")

        return issues


if __name__ == "__main__":
    issues = main()
    sys.exit(1 if issues else 0)

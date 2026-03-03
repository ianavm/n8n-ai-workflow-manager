"""
Patch the existing Lead Scraper workflow's Update Lead Status node
to seed Follow Up Stage and Next Follow Up Date after initial email send.

Usage:
    python tools/patch_lead_status_node.py
"""

import sys
import json
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

    with httpx.Client(timeout=60) as client:
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        wf = resp.json()

        patched = False
        for node in wf["nodes"]:
            if node["name"] == "Update Lead Status":
                cols = node["parameters"]["columns"]

                # Add Follow Up Stage = 1 (initial email sent, first follow-up pending)
                cols["value"]["Follow Up Stage"] = "=1"

                # Add Next Follow Up Date = today + 2 days
                cols["value"]["Next Follow Up Date"] = (
                    "={{ (() => { const d = new Date(); "
                    "d.setDate(d.getDate() + 2); "
                    "return d.toISOString().split('T')[0]; })() }}"
                )

                # Add schema entries for the new fields
                cols["schema"].append({
                    "id": "Follow Up Stage",
                    "type": "number",
                    "display": True,
                    "displayName": "Follow Up Stage"
                })
                cols["schema"].append({
                    "id": "Next Follow Up Date",
                    "type": "string",
                    "display": True,
                    "displayName": "Next Follow Up Date"
                })

                patched = True
                print("Patched Update Lead Status node:")
                print(f"  + Follow Up Stage = 1")
                print(f"  + Next Follow Up Date = today + 2 days")
                break

        if not patched:
            print("ERROR: Could not find 'Update Lead Status' node")
            sys.exit(1)

        # Deploy
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/deactivate", headers=headers)

        update_payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
            headers=headers,
            json=update_payload
        )
        resp.raise_for_status()

        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate", headers=headers)
        print("\nWorkflow updated and activated.")

        # Verify
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        final = resp.json()
        for node in final["nodes"]:
            if node["name"] == "Update Lead Status":
                field_names = list(node["parameters"]["columns"]["value"].keys())
                print(f"Verified fields: {field_names}")
                break
        print(f"Active: {final.get('active')}")


if __name__ == "__main__":
    main()

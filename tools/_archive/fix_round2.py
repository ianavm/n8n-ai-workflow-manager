"""Fix round 2: Normalize fields structure + AI promptType + remove webhook"""

import sys
import json
import uuid
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

        for node in wf["nodes"]:
            # FIX 1: Normalize Lead Record - handle nested fields
            if node["name"] == "Normalize Lead Record":
                print("[FIX 1] Updating Normalize for nested fields...")
                node["parameters"]["jsCode"] = "\n".join([
                    "// Normalize Airtable upsert response back to camelCase",
                    "// Airtable response: {id, createdTime, fields: {...}}",
                    "const record = $json;",
                    "const f = record.fields || record;",
                    "return {",
                    "  json: {",
                    "    airtableId: record.id || '',",
                    "    businessName: f['Business Name'] || '',",
                    "    email: f['Email'] || '',",
                    "    phone: f['Phone'] || '',",
                    "    website: f['Website'] || '',",
                    "    address: f['Address'] || '',",
                    "    industry: f['Industry'] || '',",
                    "    location: f['Location'] || '',",
                    "    rating: f['Rating'] || 0,",
                    "    linkedin: f['Social - LinkedIn'] || '',",
                    "    facebook: f['Social - Facebook'] || '',",
                    "    instagram: f['Social - Instagram'] || '',",
                    "    leadScore: f['Lead Score'] || 0,",
                    "    automationFit: f['Automation Fit'] || '',",
                    "    status: f['Status'] || '',",
                    "    source: f['Source'] || '',",
                    "    datescraped: f['Date Scraped'] || '',",
                    "    notes: f['Notes'] || '',",
                    "    isNew: !f['Status']",
                    "  }",
                    "};",
                ])

            # FIX 2: AI Generate Email - set promptType
            if node["name"] == "AI Generate Email":
                print("[FIX 2] Setting promptType=define...")
                node["parameters"]["promptType"] = "define"

        # FIX 3: Remove temp webhook trigger
        wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "Test Webhook Trigger"]
        wf["connections"].pop("Test Webhook Trigger", None)
        print("[FIX 3] Removed temp webhook")

        # Add fresh webhook for testing
        webhook_path = "test-lead-scraper-" + str(uuid.uuid4())[:8]
        webhook_node = {
            "parameters": {
                "httpMethod": "POST",
                "path": webhook_path,
                "responseMode": "lastNode",
                "options": {}
            },
            "id": str(uuid.uuid4()),
            "name": "Test Webhook Trigger",
            "type": "n8n-nodes-base.webhook",
            "position": [200, 700],
            "typeVersion": 2,
            "webhookId": str(uuid.uuid4())
        }
        wf["nodes"].append(webhook_node)
        wf["connections"]["Test Webhook Trigger"] = {
            "main": [[{"node": "Search Config", "type": "main", "index": 0}]]
        }

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

        print(f"\nDeployed and activated")
        print(f"Webhook: {base_url}/webhook/{webhook_path}")

        # Save path
        Path(".tmp/test_webhook_path.txt").write_text(webhook_path)


if __name__ == "__main__":
    main()

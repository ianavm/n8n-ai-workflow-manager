"""Fix round 3: Only fix Normalize + add chatInput for AI node"""

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

            # FIX 2: AI Generate Email - REVERT promptType, keep as-is
            if node["name"] == "AI Generate Email":
                print("[FIX 2] Reverting AI Generate Email promptType...")
                # Remove the promptType we added - let it use default
                node["parameters"].pop("promptType", None)
                # The prompt parameter stays as is

        # FIX 3: Add a Prepare AI Input code node between Rate Limit Emails
        # and AI Generate Email that sets chatInput for the chainLlm auto mode
        print("[FIX 3] Adding Prepare AI Input node...")
        prepare_ai_node = {
            "parameters": {
                "jsCode": "\n".join([
                    "const leadData = $json;",
                    "const biz = leadData.businessName || 'your business';",
                    "const ind = leadData.industry || 'your industry';",
                    "const loc = leadData.location || 'the area';",
                    "const web = leadData.website || '';",
                    "",
                    "const prompt = `You are a business automation consultant specializing in workflow optimization and lead generation systems.",
                    "",
                    "Write a compelling, consultative cold outreach email that offers genuine value.",
                    "",
                    "BUSINESS CONTEXT:",
                    "- Business: ${biz}",
                    "- Industry: ${ind}",
                    "- Location: ${loc}",
                    "- Website: ${web}",
                    "",
                    "YOUR VALUE PROPOSITION:",
                    "We help ${ind} businesses in ${loc} automate repetitive tasks to:",
                    "1. Close deals 3x faster through automated follow-ups",
                    "2. Save 15-20 hours/week by eliminating manual data entry",
                    "3. Generate 40% more leads with automated marketing workflows",
                    "",
                    "INSTRUCTIONS:",
                    "1. Subject line (max 55 chars): Reference their specific pain point",
                    "2. Opening: Show you understand their industry challenges",
                    "3. Body (100-130 words): ONE specific automation opportunity, quick win example, ROI in concrete terms",
                    "4. CTA: Offer a FREE 15-min automation audit",
                    "5. Tone: Consultative expert, NOT salesy",
                    "6. NO buzzwords like leverage, synergy, cutting-edge",
                    "7. NO generic openers like I hope this finds you well",
                    "",
                    'OUTPUT FORMAT (JSON only, no markdown):',
                    '{"subject": "...", "body": "...", "cta_text": "Would a quick 15-min call this week work?"}`;',
                    "",
                    "return {",
                    "  json: {",
                    "    ...leadData,",
                    "    chatInput: prompt",
                    "  }",
                    "};",
                ])
            },
            "id": str(uuid.uuid4()),
            "name": "Prepare AI Input",
            "type": "n8n-nodes-base.code",
            "position": [3370, 60],
            "typeVersion": 2,
        }

        # Insert the node
        wf["nodes"].append(prepare_ai_node)

        # Rewire: Rate Limit Emails -> Prepare AI Input -> AI Generate Email
        # (was: Rate Limit Emails -> AI Generate Email)
        wf["connections"]["Rate Limit Emails"] = {
            "main": [[{"node": "Prepare AI Input", "type": "main", "index": 0}]]
        }
        wf["connections"]["Prepare AI Input"] = {
            "main": [[{"node": "AI Generate Email", "type": "main", "index": 0}]]
        }

        # Shift AI Generate and downstream nodes right
        position_shifts = {
            "AI Generate Email": [3590, 60],
            "Format Email": [3810, 60],
            "Send Outreach Email": [4030, 60],
            "Update Lead Status": [4250, 60],
        }
        for node in wf["nodes"]:
            if node["name"] in position_shifts:
                node["position"] = position_shifts[node["name"]]

        # Remove temp webhook, add fresh one
        wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "Test Webhook Trigger"]
        wf["connections"].pop("Test Webhook Trigger", None)

        webhook_path = "test-ls-" + str(uuid.uuid4())[:8]
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
        Path(".tmp/test_webhook_path.txt").write_text(webhook_path)


if __name__ == "__main__":
    main()

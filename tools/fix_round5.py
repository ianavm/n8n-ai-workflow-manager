"""Fix round 5: Sheets error handling + Prepare AI Input all items"""

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
            # FIX 1: Append to Sheets - add error handling
            if node["name"] == "Append to Sheets":
                print("[FIX 1] Adding error handling to Append to Sheets...")
                node["onError"] = "continueRegularOutput"
                # Also try using sheet name instead of gid
                node["parameters"]["sheetName"] = {
                    "__rl": True,
                    "value": "gid=0",
                    "mode": "list",
                    "cachedResultName": "Sheet1",
                    "cachedResultUrl": "https://docs.google.com/spreadsheets/d/1vZl87q8tgJDrc3dcv-a2pwr7KKJcC3FeUkIPCeJCt-A/edit#gid=0"
                }

            # FIX 2: Prepare AI Input - process all items
            if node["name"] == "Prepare AI Input":
                print("[FIX 2] Fixing Prepare AI Input to handle all items...")
                node["parameters"]["jsCode"] = "\n".join([
                    "const items = $input.all();",
                    "return items.map(item => {",
                    "  const leadData = item.json;",
                    "  const biz = leadData.businessName || 'your business';",
                    "  const ind = leadData.industry || 'your industry';",
                    "  const loc = leadData.location || 'the area';",
                    "  const web = leadData.website || '';",
                    "",
                    "  const prompt = `You are a business automation consultant specializing in workflow optimization.",
                    "",
                    "Write a compelling cold outreach email that offers genuine value.",
                    "",
                    "BUSINESS CONTEXT:",
                    "- Business: ${biz}",
                    "- Industry: ${ind}",
                    "- Location: ${loc}",
                    "- Website: ${web}",
                    "",
                    "YOUR VALUE PROPOSITION:",
                    "We help ${ind} businesses automate repetitive tasks to:",
                    "1. Close deals 3x faster through automated follow-ups",
                    "2. Save 15-20 hours/week eliminating manual data entry",
                    "3. Generate 40% more leads with automated marketing",
                    "",
                    "INSTRUCTIONS:",
                    "1. Subject line (max 55 chars): Reference their specific pain point",
                    "2. Opening: Show understanding of their industry challenges",
                    "3. Body (100-130 words): ONE automation opportunity, quick win, ROI",
                    "4. CTA: Offer FREE 15-min automation audit",
                    "5. Tone: Consultative, NOT salesy",
                    "6. NO buzzwords or generic openers",
                    "",
                    'OUTPUT FORMAT (JSON only, no markdown):',
                    '{"subject": "...", "body": "...", "cta_text": "Would a quick 15-min call work?"}`;',
                    "",
                    "  return {",
                    "    json: {",
                    "      ...leadData,",
                    "      chatInput: prompt",
                    "    }",
                    "  };",
                    "});",
                ])

            # FIX 3: Format Email - use $('Prepare AI Input') instead of $('Filter New Leads')
            # Since Prepare AI Input has the lead data in $json (it passes leadData through)
            if node["name"] == "Format Email":
                print("[FIX 3] Fixing Format Email to reference Prepare AI Input...")
                node["parameters"]["jsCode"] = "\n".join([
                    "const input = $input.first().json;",
                    "const leadData = $('Prepare AI Input').item.json;",
                    "const config = $('Search Config').first().json;",
                    "",
                    "// Parse AI response - chainLlm returns text in 'text' field",
                    "let emailContent;",
                    "try {",
                    "  const rawText = input.text || input.response || JSON.stringify(input);",
                    "  const jsonMatch = rawText.match(/\\{[\\s\\S]*\\}/);",
                    "  emailContent = JSON.parse(jsonMatch[0]);",
                    "} catch (e) {",
                    "  const industryName = leadData.industry || 'your industry';",
                    "  emailContent = {",
                    "    subject: `Automate ${industryName} workflows - save 15h/week`,",
                    "    body: `Hi ${leadData.businessName || 'there'},\\n\\nI work with ${industryName} businesses in ${leadData.location} to automate time-consuming tasks.\\n\\nMost businesses save 15-20 hours per week after implementing simple automation workflows.\\n\\nWould love to show you a few quick wins - no cost, just value.`,",
                    "    cta_text: 'Would a quick 15-minute call this week work?'",
                    "  };",
                    "}",
                    "",
                    "const htmlBody = '<div style=\"font-family:Segoe UI,Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;\">' +",
                    "  '<div style=\"padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;\">' +",
                    "  '<h1 style=\"margin:0;font-size:22px;color:#1A1A2E;\">' + config.senderCompany + '</h1>' +",
                    "  '<p style=\"margin:8px 0 0;font-size:13px;color:#666;\">Business Automation & Lead Generation</p></div>' +",
                    "  '<div style=\"padding:30px 40px;\">' +",
                    "  '<p style=\"font-size:15px;line-height:1.6;color:#333;\">' + emailContent.body + '</p>' +",
                    "  '<p style=\"font-size:15px;line-height:1.6;color:#333;\">' + emailContent.cta_text + '</p>' +",
                    "  '<p style=\"font-size:15px;line-height:1.6;color:#333;margin-top:24px;\">Best regards,<br>' +",
                    "  '<strong>' + config.senderName + '</strong><br>' +",
                    "  '<span style=\"color:#666;\">' + config.senderTitle + '</span><br>' +",
                    "  '<span style=\"color:#666;\">' + config.senderCompany + '</span></p></div>' +",
                    "  '<div style=\"padding:20px 40px;background:#f8f8f8;border-top:1px solid #eee;\">' +",
                    "  '<p style=\"font-size:11px;color:#999;\">You received this because your business was listed on Google Maps. Reply &quot;unsubscribe&quot; to be removed.</p></div></div>';",
                    "",
                    "return {",
                    "  json: {",
                    "    to: leadData.email,",
                    "    subject: emailContent.subject,",
                    "    htmlBody: htmlBody,",
                    "    leadEmail: leadData.email,",
                    "    businessName: leadData.businessName,",
                    "    automationFit: leadData.automationFit",
                    "  }",
                    "};",
                ])

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

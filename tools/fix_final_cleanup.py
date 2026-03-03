"""Final cleanup: Fix Format Email all items, remove webhook, restore production config"""

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

        for node in wf["nodes"]:
            # FIX 1: Format Email - handle ALL items using index matching
            # Avoids paired-item resolution through chainLlm by using positional matching
            if node["name"] == "Format Email":
                print("[FIX 1] Fixing Format Email to handle all items via index matching...")
                node["parameters"]["jsCode"] = "\n".join([
                    "const items = $input.all();",
                    "const allLeads = $('Prepare AI Input').all();",
                    "const config = $('Search Config').first().json;",
                    "",
                    "return items.map((item, index) => {",
                    "  const input = item.json;",
                    "  const leadData = allLeads[index]?.json || {};",
                    "",
                    "  // Parse AI response - chainLlm returns text in 'text' field",
                    "  let emailContent;",
                    "  try {",
                    "    const rawText = input.text || input.response || JSON.stringify(input);",
                    "    const jsonMatch = rawText.match(/\\{[\\s\\S]*\\}/);",
                    "    emailContent = JSON.parse(jsonMatch[0]);",
                    "  } catch (e) {",
                    "    const industryName = leadData.industry || 'your industry';",
                    "    emailContent = {",
                    "      subject: `Automate ${industryName} workflows - save 15h/week`,",
                    "      body: `Hi ${leadData.businessName || 'there'},\\n\\nI work with ${industryName} businesses in ${leadData.location} to automate time-consuming tasks.\\n\\nMost businesses save 15-20 hours per week after implementing simple automation workflows.\\n\\nWould love to show you a few quick wins - no cost, just value.`,",
                    "      cta_text: 'Would a quick 15-minute call this week work?'",
                    "    };",
                    "  }",
                    "",
                    "  const htmlBody = '<div style=\"font-family:Segoe UI,Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;\">' +",
                    "    '<div style=\"padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;\">' +",
                    "    '<h1 style=\"margin:0;font-size:22px;color:#1A1A2E;\">' + config.senderCompany + '</h1>' +",
                    "    '<p style=\"margin:8px 0 0;font-size:13px;color:#666;\">Business Automation & Lead Generation</p></div>' +",
                    "    '<div style=\"padding:30px 40px;\">' +",
                    "    '<p style=\"font-size:15px;line-height:1.6;color:#333;\">' + emailContent.body + '</p>' +",
                    "    '<p style=\"font-size:15px;line-height:1.6;color:#333;\">' + emailContent.cta_text + '</p>' +",
                    "    '<p style=\"font-size:15px;line-height:1.6;color:#333;margin-top:24px;\">Best regards,<br>' +",
                    "    '<strong>' + config.senderName + '</strong><br>' +",
                    "    '<span style=\"color:#666;\">' + config.senderTitle + '</span><br>' +",
                    "    '<span style=\"color:#666;\">' + config.senderCompany + '</span></p></div>' +",
                    "    '<div style=\"padding:20px 40px;background:#f8f8f8;border-top:1px solid #eee;\">' +",
                    "    '<p style=\"font-size:11px;color:#999;\">You received this because your business was listed on Google Maps. Reply &quot;unsubscribe&quot; to be removed.</p></div></div>';",
                    "",
                    "  return {",
                    "    json: {",
                    "      to: leadData.email,",
                    "      subject: emailContent.subject,",
                    "      htmlBody: htmlBody,",
                    "      leadEmail: leadData.email,",
                    "      businessName: leadData.businessName,",
                    "      automationFit: leadData.automationFit",
                    "    }",
                    "  };",
                    "});",
                ])

            # FIX 2: Restore production maxResults (from test value of 3 to 20)
            if node["name"] == "Search Config":
                print("[FIX 2] Restoring production maxResults to 20...")
                # Update the jsCode to set maxResults to 20
                if "jsCode" in node["parameters"]:
                    code = node["parameters"]["jsCode"]
                    code = code.replace("maxResults: 3", "maxResults: 20")
                    code = code.replace("maxResults:3", "maxResults: 20")
                    node["parameters"]["jsCode"] = code

        # FIX 3: Remove temp Test Webhook Trigger
        print("[FIX 3] Removing Test Webhook Trigger node...")
        wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "Test Webhook Trigger"]
        wf["connections"].pop("Test Webhook Trigger", None)

        # Print final node list
        print("\n--- Final workflow nodes ---")
        for n in sorted(wf["nodes"], key=lambda x: x.get("position", [0, 0])[0]):
            print(f"  {n['name']} ({n['type']})")
        print(f"Total: {len(wf['nodes'])} nodes")

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

        # Activate for production
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate", headers=headers)
        print("\nWorkflow deployed and ACTIVATED for production!")

        # Verify final state
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        final = resp.json()
        print(f"Active: {final.get('active')}")
        print(f"Name: {final.get('name')}")

        # Count nodes by type
        node_types = {}
        for n in final["nodes"]:
            t = n["type"].split(".")[-1]
            node_types[t] = node_types.get(t, 0) + 1
        print("\nNode type breakdown:")
        for t, count in sorted(node_types.items()):
            print(f"  {t}: {count}")


if __name__ == "__main__":
    main()

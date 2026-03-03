"""
Fix Lead Scraper Workflow - Resolve paired item expression errors.

Root cause: Score Leads Code node breaks n8n's paired-item tracking, causing
$('Score Leads').item.json.* to fail with "Multiple matches found" in downstream nodes.

Fix:
1. Remove Check Airtable Exists + Is New Lead? + Update in Airtable (3 nodes)
2. Modify Create in Airtable → becomes Upsert (already has matchingColumns)
3. Connect Score Leads → Upsert directly (uses $json.*, no paired item needed)
4. Add Normalize Code node after Upsert to map Airtable response → camelCase
5. Fix all downstream references
"""

import sys
import json
import uuid
import copy

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "uq4hnH0YHfhYOOzO"
AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_TABLE_ID = "tblOsuh298hB9WWrA"


def uid():
    return str(uuid.uuid4())


def fix_workflow(wf):
    """Apply all fixes to the workflow."""
    nodes = wf["nodes"]
    connections = wf["connections"]

    # Index nodes by name
    node_map = {n["name"]: n for n in nodes}

    # ── FIX 1: Remove Score Leads sort ──
    print("  [1] Fixing Score Leads - removing sort...")
    score_node = node_map["Score Leads"]
    code = score_node["parameters"]["jsCode"]
    # Remove the sort line
    code = code.replace(
        "\n// Sort by lead score descending (prioritize high-fit businesses)\nresults.sort((a, b) => b.json.leadScore - a.json.leadScore);\n",
        "\n"
    )
    score_node["parameters"]["jsCode"] = code

    # ── FIX 2: Remove Check Airtable Exists, Is New Lead?, Update in Airtable ──
    print("  [2] Removing Check Airtable Exists, Is New Lead?, Update in Airtable...")
    remove_names = ["Check Airtable Exists", "Is New Lead?", "Update in Airtable"]
    nodes[:] = [n for n in nodes if n["name"] not in remove_names]

    # Remove their connections
    for name in remove_names:
        connections.pop(name, None)

    # ── FIX 3: Modify Create in Airtable → Upsert to Airtable ──
    print("  [3] Converting Create in Airtable -> Upsert to Airtable...")
    create_node = node_map["Create in Airtable"]
    create_node["name"] = "Upsert to Airtable"

    # Change all $('Score Leads').item.json.* references to $json.*
    # and remove Status from the upsert (so existing records keep their status)
    create_node["parameters"]["columns"]["value"] = {
        "Business Name": "={{ $json.businessName }}",
        "Email": "={{ $json.email }}",
        "Phone": "={{ $json.phone }}",
        "Website": "={{ $json.website }}",
        "Address": "={{ $json.address }}",
        "Industry": "={{ $json.industry }}",
        "Location": "={{ $json.location }}",
        "Rating": "={{ $json.rating }}",
        "Social - LinkedIn": "={{ $json.linkedin }}",
        "Social - Facebook": "={{ $json.facebook }}",
        "Social - Instagram": "={{ $json.instagram }}",
        "Lead Score": "={{ $json.leadScore }}",
        "Source": "={{ $json.source }}",
        "Date Scraped": "={{ $json.datescraped }}",
        "Notes": "={{ $json.notes }}",
        "Automation Fit": "={{ $json.automationFit }}"
    }

    # Update schema to match (remove Status, add Automation Fit and Notes)
    create_node["parameters"]["columns"]["schema"] = [
        {"id": "Business Name", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Business Name", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Email", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Email", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Phone", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Phone", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Website", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Website", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Address", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Address", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Industry", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Industry", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Location", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Location", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Rating", "type": "number", "display": True, "removed": False, "required": False, "displayName": "Rating", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Social - LinkedIn", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Social - LinkedIn", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Social - Facebook", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Social - Facebook", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Social - Instagram", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Social - Instagram", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Lead Score", "type": "number", "display": True, "removed": False, "required": False, "displayName": "Lead Score", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Source", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Source", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Date Scraped", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Date Scraped", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Notes", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Notes", "defaultMatch": False, "canBeUsedToMatch": True},
        {"id": "Automation Fit", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Automation Fit", "defaultMatch": False, "canBeUsedToMatch": True},
    ]

    # Keep matchingColumns and add continueOnFail for resilience
    create_node["parameters"]["columns"]["matchingColumns"] = ["Email"]
    create_node["onError"] = "continueRegularOutput"

    # Reposition (where Check Airtable used to be)
    create_node["position"] = [2580, 260]

    # ── FIX 4: Add Normalize Lead Record code node ──
    print("  [4] Adding Normalize Lead Record code node...")
    normalize_node = {
        "parameters": {
            "jsCode": (
                "// Normalize Airtable upsert response back to camelCase for downstream use\n"
                "const record = $json;\n"
                "return {\n"
                "  json: {\n"
                "    airtableId: record.id || '',\n"
                "    businessName: record['Business Name'] || '',\n"
                "    email: record['Email'] || '',\n"
                "    phone: record['Phone'] || '',\n"
                "    website: record['Website'] || '',\n"
                "    address: record['Address'] || '',\n"
                "    industry: record['Industry'] || '',\n"
                "    location: record['Location'] || '',\n"
                "    rating: record['Rating'] || 0,\n"
                "    linkedin: record['Social - LinkedIn'] || '',\n"
                "    facebook: record['Social - Facebook'] || '',\n"
                "    instagram: record['Social - Instagram'] || '',\n"
                "    leadScore: record['Lead Score'] || 0,\n"
                "    automationFit: record['Automation Fit'] || '',\n"
                "    status: record['Status'] || '',\n"
                "    source: record['Source'] || '',\n"
                "    datescraped: record['Date Scraped'] || '',\n"
                "    notes: record['Notes'] || '',\n"
                "    isNew: !record['Status']\n"
                "  }\n"
                "};"
            )
        },
        "id": uid(),
        "name": "Normalize Lead Record",
        "type": "n8n-nodes-base.code",
        "position": [2800, 260],
        "typeVersion": 2,
        "alwaysOutputData": True
    }
    nodes.append(normalize_node)

    # ── FIX 5: Fix Append to Sheets - use $json.* directly ──
    print("  [5] Fixing Append to Sheets references...")
    sheets_node = node_map["Append to Sheets"]
    sheets_node["parameters"]["columns"]["value"] = {
        "Business Name": "={{ $json.businessName }}",
        "Email": "={{ $json.email }}",
        "Phone": "={{ \"'\" + ($json.phone || '') }}",
        "Website": "={{ $json.website }}",
        "Address": "={{ $json.address }}",
        "Industry": "={{ $json.industry }}",
        "Location": "={{ $json.location }}",
        "Rating": "={{ $json.rating }}",
        "LinkedIn": "={{ $json.linkedin }}",
        "Facebook": "={{ $json.facebook }}",
        "Instagram": "={{ $json.instagram }}",
        "Lead Score": "={{ $json.leadScore }}",
        "Status": "={{ $json.status || 'New' }}",
        "Date Scraped": "={{ $json.datescraped }}",
        "Automation Fit": "={{ $json.automationFit }}"
    }
    # Update schema to include Automation Fit
    sheets_node["parameters"]["columns"]["schema"] = [
        {"id": "Business Name", "type": "string", "display": True, "displayName": "Business Name"},
        {"id": "Email", "type": "string", "display": True, "displayName": "Email"},
        {"id": "Phone", "type": "string", "display": True, "displayName": "Phone"},
        {"id": "Website", "type": "string", "display": True, "displayName": "Website"},
        {"id": "Address", "type": "string", "display": True, "displayName": "Address"},
        {"id": "Industry", "type": "string", "display": True, "displayName": "Industry"},
        {"id": "Location", "type": "string", "display": True, "displayName": "Location"},
        {"id": "Rating", "type": "string", "display": True, "displayName": "Rating"},
        {"id": "LinkedIn", "type": "string", "display": True, "displayName": "LinkedIn"},
        {"id": "Facebook", "type": "string", "display": True, "displayName": "Facebook"},
        {"id": "Instagram", "type": "string", "display": True, "displayName": "Instagram"},
        {"id": "Lead Score", "type": "string", "display": True, "displayName": "Lead Score"},
        {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
        {"id": "Date Scraped", "type": "string", "display": True, "displayName": "Date Scraped"},
        {"id": "Automation Fit", "type": "string", "display": True, "displayName": "Automation Fit"},
    ]
    # Move position
    sheets_node["position"] = [3040, 260]

    # ── FIX 6: Fix Filter New Leads - check isNew flag ──
    print("  [6] Fixing Filter New Leads...")
    filter_node = node_map["Filter New Leads"]
    filter_node["parameters"]["conditions"] = {
        "options": {
            "version": 2,
            "leftValue": "",
            "caseSensitive": True,
            "typeValidation": "strict"
        },
        "combinator": "and",
        "conditions": [
            {
                "id": uid(),
                "operator": {
                    "type": "boolean",
                    "operation": "true",
                    "singleValue": True
                },
                "leftValue": "={{ $json.isNew }}",
                "rightValue": ""
            },
            {
                "id": uid(),
                "operator": {
                    "type": "string",
                    "operation": "exists",
                    "singleValue": True
                },
                "leftValue": "={{ $json.email }}",
                "rightValue": ""
            }
        ]
    }
    filter_node["position"] = [3280, 160]

    # ── FIX 7: Fix Format Email - use Filter New Leads reference instead of Score Leads ──
    print("  [7] Fixing Format Email code...")
    format_node = node_map["Format Email"]
    format_node["parameters"]["jsCode"] = (
        "const input = $input.first().json;\n"
        "const leadData = $('Filter New Leads').item.json;\n"
        "const config = $('Search Config').first().json;\n"
        "\n"
        "// Parse AI response - chainLlm returns text in 'text' field\n"
        "let emailContent;\n"
        "try {\n"
        "  const rawText = input.text || input.response || JSON.stringify(input);\n"
        "  const jsonMatch = rawText.match(/\\{[\\s\\S]*\\}/);\n"
        "  emailContent = JSON.parse(jsonMatch[0]);\n"
        "} catch (e) {\n"
        "  const industryName = leadData.industry || 'your industry';\n"
        "  emailContent = {\n"
        "    subject: `Automate ${industryName} workflows - save 15h/week`,\n"
        "    body: `Hi ${leadData.businessName || 'there'},\\n\\nI work with ${industryName} businesses in ${leadData.location} to automate time-consuming tasks like follow-ups, scheduling, and lead nurturing.\\n\\nMost ${industryName} businesses we work with save 15-20 hours per week and close deals 3x faster after implementing simple automation workflows.\\n\\nWould love to show you a few quick wins specific to ${industryName} - no cost, just value.`,\n"
        "    cta_text: 'Would a quick 15-minute call this week work?'\n"
        "  };\n"
        "}\n"
        "\n"
        "const htmlBody = '<div style=\"font-family:Segoe UI,Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;\">' +\n"
        "  '<div style=\"padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;\">' +\n"
        "  '<h1 style=\"margin:0;font-size:22px;color:#1A1A2E;\">' + config.senderCompany + '</h1>' +\n"
        "  '<p style=\"margin:8px 0 0;font-size:13px;color:#666;\">Business Automation & Lead Generation</p></div>' +\n"
        "  '<div style=\"padding:30px 40px;\">' +\n"
        "  '<p style=\"font-size:15px;line-height:1.6;color:#333;\">' + emailContent.body + '</p>' +\n"
        "  '<p style=\"font-size:15px;line-height:1.6;color:#333;\">' + emailContent.cta_text + '</p>' +\n"
        "  '<p style=\"font-size:15px;line-height:1.6;color:#333;margin-top:24px;\">Best regards,<br>' +\n"
        "  '<strong>' + config.senderName + '</strong><br>' +\n"
        "  '<span style=\"color:#666;\">' + config.senderTitle + '</span><br>' +\n"
        "  '<span style=\"color:#666;\">' + config.senderCompany + '</span></p></div>' +\n"
        "  '<div style=\"padding:20px 40px;background:#f8f8f8;border-top:1px solid #eee;\">' +\n"
        "  '<p style=\"font-size:11px;color:#999;\">You received this because your business was listed on Google Maps. Reply &quot;unsubscribe&quot; to be removed.</p></div></div>';\n"
        "\n"
        "return {\n"
        "  json: {\n"
        "    to: leadData.email,\n"
        "    subject: emailContent.subject,\n"
        "    htmlBody: htmlBody,\n"
        "    leadEmail: leadData.email,\n"
        "    businessName: leadData.businessName,\n"
        "    automationFit: leadData.automationFit\n"
        "  }\n"
        "};"
    )

    # ── FIX 8: Fix Update Lead Status - reference Format Email data ──
    print("  [8] Fixing Update Lead Status references...")
    update_status_node = node_map["Update Lead Status"]
    update_status_node["parameters"]["columns"]["value"] = {
        "Status": "Email Sent",
        "Email Sent Date": "={{ new Date().toISOString().split('T')[0] }}",
        "Notes": "={{ $('Format Email').item.json.subject }}",
        "Email": "={{ $('Format Email').item.json.leadEmail }}"
    }
    update_status_node["parameters"]["columns"]["schema"] = [
        {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
        {"id": "Email Sent Date", "type": "string", "display": True, "displayName": "Email Sent Date"},
        {"id": "Notes", "type": "string", "display": True, "displayName": "Notes"},
        {"id": "Email", "type": "string", "display": True, "displayName": "Email"},
    ]
    update_status_node["parameters"]["columns"]["matchingColumns"] = ["Email"]

    # ── FIX 9: Fix Aggregate Results - keep $('Score Leads').all() (safe, no paired item) ──
    print("  [9] Aggregate Results uses .all() - OK, no change needed")

    # ── FIX 10: Rewire connections ──
    print("  [10] Rewiring connections...")

    # Remove old connections that reference deleted nodes
    connections.pop("Check Airtable Exists", None)
    connections.pop("Is New Lead?", None)
    connections.pop("Update in Airtable", None)
    connections.pop("Create in Airtable", None)

    # Score Leads → Upsert to Airtable (was Score Leads → Check Airtable Exists)
    connections["Score Leads"] = {
        "main": [[{"node": "Upsert to Airtable", "type": "main", "index": 0}]]
    }

    # Upsert to Airtable → Normalize Lead Record
    connections["Upsert to Airtable"] = {
        "main": [[{"node": "Normalize Lead Record", "type": "main", "index": 0}]]
    }

    # Normalize Lead Record → [Append to Sheets, Filter New Leads, Aggregate Results]
    connections["Normalize Lead Record"] = {
        "main": [[
            {"node": "Append to Sheets", "type": "main", "index": 0},
            {"node": "Filter New Leads", "type": "main", "index": 0},
            {"node": "Aggregate Results", "type": "main", "index": 0}
        ]]
    }

    # Remove Append to Sheets → Filter New Leads/Aggregate Results (now from Normalize)
    connections.pop("Append to Sheets", None)

    # Keep the email pipeline: Filter New Leads → Rate Limit → AI Generate → Format → Send → Update
    # These connections should already exist, just verify
    assert "Filter New Leads" in connections, "Missing Filter New Leads connection"
    assert "Rate Limit Emails" in connections, "Missing Rate Limit Emails connection"
    assert "AI Generate Email" in connections, "Missing AI Generate Email connection"
    assert "Format Email" in connections, "Missing Format Email connection"
    assert "Send Outreach Email" in connections, "Missing Send Outreach Email connection"

    # Keep: Aggregate Results → Send Summary
    assert "Aggregate Results" in connections, "Missing Aggregate Results connection"

    # Keep: Error Trigger → Error Notification
    assert "Error Trigger" in connections, "Missing Error Trigger connection"

    # ── FIX 11: Reposition nodes for clean layout ──
    print("  [11] Repositioning nodes for clean layout...")
    positions = {
        "Score Leads": [2360, 260],
        "Upsert to Airtable": [2580, 260],
        "Normalize Lead Record": [2800, 260],
        "Append to Sheets": [3040, 260],
        "Filter New Leads": [3040, 60],
        "Rate Limit Emails": [3260, 60],
        "AI Generate Email": [3480, 60],
        "Format Email": [3700, 60],
        "Send Outreach Email": [3920, 60],
        "Update Lead Status": [4140, 60],
        "Aggregate Results": [3040, 460],
        "Send Summary": [3260, 460],
    }
    for node in nodes:
        if node["name"] in positions:
            node["position"] = positions[node["name"]]

    # Update sticky notes for the CRM section
    for node in nodes:
        if node.get("type") == "n8n-nodes-base.stickyNote":
            content = node.get("parameters", {}).get("content", "")
            if "CRM Storage" in content:
                node["parameters"]["content"] = (
                    "## STAGE 5: CRM Storage\n\n"
                    "**Airtable** (primary): Upsert - creates new or updates existing by Email\n"
                    "**Google Sheets** (mirror): Appends all leads for easy sharing"
                )

    # Rebuild node_map after changes
    node_names = [n["name"] for n in nodes if "stickyNote" not in n["type"]]
    print(f"\n  Final nodes: {len(node_names)}")
    print(f"  Connections: {len(connections)}")

    return wf


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    print("=" * 60)
    print("LEAD SCRAPER FIX - Deploy")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:
        # 1. Fetch current workflow
        print("\n[FETCH] Getting current workflow...")
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        print(f"  Got: {wf['name']} (nodes: {len(wf['nodes'])})")

        # 2. Apply fixes
        print("\n[FIX] Applying fixes...")
        wf = fix_workflow(wf)

        # 3. Save fixed version locally
        from pathlib import Path
        output_path = Path(__file__).parent.parent / ".tmp" / "lead_scraper_fixed_v3.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVE] Saved fixed workflow to {output_path}")

        # 4. Deploy to n8n
        print("\n[DEPLOY] Pushing to n8n...")
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
        result = resp.json()
        print(f"  Deployed: {result['name']} (ID: {result['id']})")
        print(f"  Active: {result.get('active')}")

    print("\n" + "=" * 60)
    print("FIX DEPLOYED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()

"""
Full revision fix script - 2026-03-19 Session 5

Patches 15 failing n8n workflows via the n8n API:

Fix 1:  CRM-01 (EiuQcBeQG7AVcbYE) - Remove dead Xero reference
Fix 2:  BRIDGE-01 (IqODyj5suLusrkIx) - Fix Airtable field mapping
Fix 3:  BRIDGE-04 (OlHyOU8mHxJ1uZuc) - Fix missing email/subject in Format Cold HTML
Fix 4:  DATA-02 (oMFz2y6ntoqcYxkZ) + KM-01 (yl6JUOIkQstPhGQp) - OpenRouter credential swap
Fix 5:  INTEL-04 (gijDxxcJjHMHnaUn) + INTEL-06 (sbEwotSVpnyqrQtG) + CRM-02 (Up3ROwbRMHVjZhvc) - Fix JSON.stringify expression + credential swap
Fix 6:  QA-03 (N0VEU3RHsq3OIoqR) - Airtable field name fix
Fix 7:  DEVOPS-02 (VuBUg4r0BLL81KIF) - Airtable array field fix
Fix 8:  QA-01 (oWZ6VTwbYOflPAMS) - Missing columns.mappingMode fix
Fix 9:  CURE-01 (mYMT5IxJUl9TPMcV) - Paired item error fix
Fix 10: COMPLY-02 (EXnkfN49D36P9LFE) + KM-02 (Nw5LtlkQZGc3tDJF) - OpenRouter credential swap

Usage:
    python tools/fix_revision_2026_03_19_s5.py          # fix all
    python tools/fix_revision_2026_03_19_s5.py crm01    # fix single
"""

import sys
import json
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
from n8n_client import N8nClient


# Credential IDs
OLD_OPENROUTER_CRED = {"httpHeaderAuth": {"id": "87T4lIBmU8si87Ms", "name": "OpenRouter Bearer"}}
NEW_OPENROUTER_CRED = {"httpHeaderAuth": {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}}


def build_client(config):
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def deploy_workflow(client, workflow_id, wf):
    """Push patched workflow to n8n, stripping read-only fields."""
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    result = client.update_workflow(workflow_id, payload)
    return result


def swap_openrouter_cred(node):
    """Swap OpenRouter Bearer -> OpenRouter 2WC on a node. Returns True if changed."""
    creds = node.get("credentials", {})
    if creds.get("httpHeaderAuth", {}).get("id") == "87T4lIBmU8si87Ms":
        node["credentials"] = dict(creds)
        node["credentials"]["httpHeaderAuth"] = {
            "id": "9ZgHenDBrFuyboov",
            "name": "OpenRouter 2WC",
        }
        return True
    return False


# ---------------------------------------------------------------
# FIX 1: CRM-01 - Remove dead Xero reference
# ---------------------------------------------------------------

def fix_crm01(client):
    """Remove Fetch Xero Contacts node and update Merge Data to only use Airtable."""
    wf_id = "EiuQcBeQG7AVcbYE"

    print("\n" + "=" * 60)
    print("FIX 1: CRM-01 Hourly Sync - Remove Xero reference")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    # 1. Remove "Fetch Xero Contacts" node from nodes array
    xero_node = node_map.get("Fetch Xero Contacts")
    if xero_node:
        wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "Fetch Xero Contacts"]
        changes.append("Removed 'Fetch Xero Contacts' node")
    else:
        print("  WARNING: 'Fetch Xero Contacts' node not found")

    # 2. Fix connections FROM "Set Sync Window" - remove connection to Xero
    conns = wf.get("connections", {})
    ssw_conns = conns.get("Set Sync Window", {}).get("main", [[]])
    if ssw_conns and len(ssw_conns) > 0:
        original_count = len(ssw_conns[0])
        ssw_conns[0] = [c for c in ssw_conns[0] if c.get("node") != "Fetch Xero Contacts"]
        if len(ssw_conns[0]) < original_count:
            changes.append("Removed Set Sync Window -> Fetch Xero Contacts connection")

    # 3. Remove connections FROM "Fetch Xero Contacts"
    if "Fetch Xero Contacts" in conns:
        del conns["Fetch Xero Contacts"]
        changes.append("Removed Fetch Xero Contacts -> Merge Data connection")

    # 4. Update "Merge Data" Code node to only use Airtable
    merge_node = node_map.get("Merge Data")
    if merge_node:
        merge_node["parameters"]["jsCode"] = (
            "// Normalize Airtable leads into unified format\n"
            "const airtableRecords = $('Fetch Airtable Leads').all().map(i => i.json);\n"
            "\n"
            "const unified = [];\n"
            "\n"
            "for (const rec of airtableRecords) {\n"
            "  unified.push({\n"
            "    email: (rec.Email || rec.email || '').toLowerCase().trim(),\n"
            "    name: rec.Name || rec.name || '',\n"
            "    phone: rec.Phone || rec.phone || '',\n"
            "    company: rec.Company || rec.company || '',\n"
            "    source: 'Airtable',\n"
            "    lastModified: rec['Last Modified'] || rec.lastModified || '',\n"
            "    rawId: rec.id || '',\n"
            "  });\n"
            "}\n"
            "\n"
            "const valid = unified.filter(r => r.email && r.email.includes('@'));\n"
            "\n"
            "return [{ json: {\n"
            "  totalAirtable: airtableRecords.length,\n"
            "  totalXero: 0,\n"
            "  totalUnified: valid.length,\n"
            "  records: valid,\n"
            "} }];"
        )
        changes.append("Updated 'Merge Data' code to use only Airtable leads")
    else:
        print("  WARNING: 'Merge Data' node not found")

    # 5. Update sticky note to remove Xero mention
    sticky = node_map.get("Sticky Note")
    if sticky and "parameters" in sticky:
        content = sticky["parameters"].get("content", "")
        if "Xero" in content or "xero" in content.lower():
            sticky["parameters"]["content"] = (
                "## CRM-01: Hourly Sync\n"
                "Fetches modified Airtable leads, normalizes into\n"
                "unified format. Syncs to unified CRM table,\n"
                "creates or updates records."
            )
            changes.append("Updated sticky note to remove Xero mention")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ---------------------------------------------------------------
# FIX 2: BRIDGE-01 - Fix Airtable field mapping
# ---------------------------------------------------------------

def fix_bridge01(client):
    """Fix Split New Leads field names + remove matchingColumns from create."""
    wf_id = "IqODyj5suLusrkIx"

    print("\n" + "=" * 60)
    print("FIX 2: BRIDGE-01 Lead Sync - Fix Airtable field mapping")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    # Fix "Split New Leads" Code node field names
    split_node = node_map.get("Split New Leads")
    if split_node:
        split_node["parameters"]["jsCode"] = (
            "const items = $json.newLeads || [];\n"
            "const result = items.map(lead => {\n"
            "  const mapped = {\n"
            "    Email: lead.Email || '',\n"
            "    'Contact Name': lead.Name || '',\n"
            "    Phone: lead.Phone || '',\n"
            "    Company: lead.Company || '',\n"
            "    'Source Channel': lead.Source || 'Direct',\n"
            "    'UTM Medium': lead.Medium || '',\n"
            "    'UTM Campaign': lead.Campaign || '',\n"
            "    'Source URL': lead['Page URL'] || '',\n"
            "    'Lead Score': lead['Lead Score'] || 0,\n"
            "    Status: lead.Status || 'New',\n"
            "    'Created At': lead['Created At'] || '',\n"
            "  };\n"
            "  return { json: mapped };\n"
            "});\n"
            "return result;"
        )
        changes.append("Updated 'Split New Leads' field names to match Airtable schema")
    else:
        print("  WARNING: 'Split New Leads' node not found")

    # Fix "Create in SEO Table" - remove matchingColumns from create
    create_node = node_map.get("Create in SEO Table")
    if create_node:
        columns = create_node["parameters"].get("columns", {})
        if "matchingColumns" in columns:
            del columns["matchingColumns"]
            changes.append("Removed matchingColumns from 'Create in SEO Table' (invalid for create)")
        # Ensure mappingMode is set
        columns["mappingMode"] = "autoMapInputData"
        create_node["parameters"]["columns"] = columns
    else:
        print("  WARNING: 'Create in SEO Table' node not found")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ---------------------------------------------------------------
# FIX 3: BRIDGE-04 - Fix missing email/subject in Format Cold HTML
# ---------------------------------------------------------------

def fix_bridge04(client):
    """Fix Format Cold HTML to preserve email and subject from upstream."""
    wf_id = "OlHyOU8mHxJ1uZuc"

    print("\n" + "=" * 60)
    print("FIX 3: BRIDGE-04 Warm Lead Nurture - Fix missing email/subject")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    # Fix "Format Cold HTML" - preserve email and subject
    cold_html_node = node_map.get("Format Cold HTML")
    if cold_html_node:
        old_code = cold_html_node["parameters"].get("jsCode", "")
        # The node gets input from "AI Generate Cold Email" (OpenRouter response)
        # and needs to pass email/subject from "Prepare Cold Context"
        new_code = (
            "// Get AI-generated email content from OpenRouter response\n"
            "const aiResp = $json;\n"
            "const aiContent = (aiResp.choices && aiResp.choices[0])\n"
            "  ? aiResp.choices[0].message.content\n"
            "  : '';\n"
            "\n"
            "// Preserve email and subject from upstream Prepare Cold Context\n"
            "const upstream = $('Prepare Cold Context').first().json;\n"
            "const email = upstream.email || upstream.Email || '';\n"
            "const subject = upstream.subject || upstream.Subject\n"
            "  || 'AnyVision Media - Let us help grow your business';\n"
            "const name = upstream.name || upstream.Name || '';\n"
            "\n"
            "// Format as branded HTML\n"
            "const htmlBody = `<div style=\"font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;\">\n"
            "  <div style=\"background: #FF6D5A; padding: 16px; border-radius: 8px 8px 0 0;\">\n"
            "    <h2 style=\"color: white; margin: 0;\">AnyVision Media</h2>\n"
            "  </div>\n"
            "  <div style=\"background: white; padding: 20px; border: 1px solid #e0e0e0; border-radius: 0 0 8px 8px;\">\n"
            "    ${aiContent.replace(/\\n/g, '<br>')}\n"
            "    <hr style=\"border: 1px solid #eee; margin-top: 20px;\">\n"
            "    <p style=\"color: #888; font-size: 11px;\">AnyVision Media | Johannesburg, South Africa</p>\n"
            "  </div>\n"
            "</div>`;\n"
            "\n"
            "return [{ json: {\n"
            "  email: email,\n"
            "  subject: subject,\n"
            "  name: name,\n"
            "  htmlBody: htmlBody,\n"
            "} }];"
        )
        cold_html_node["parameters"]["jsCode"] = new_code
        changes.append("Updated 'Format Cold HTML' to preserve email, subject, name from upstream")
    else:
        print("  WARNING: 'Format Cold HTML' node not found")

    # Also fix the warm path "Format HTML" with the same pattern
    format_html_node = node_map.get("Format HTML")
    if format_html_node:
        new_code = (
            "// Get AI-generated email content\n"
            "const aiResp = $json;\n"
            "const aiContent = (aiResp.choices && aiResp.choices[0])\n"
            "  ? aiResp.choices[0].message.content\n"
            "  : '';\n"
            "\n"
            "// Preserve email and subject from upstream Prepare Context\n"
            "const upstream = $('Prepare Context').first().json;\n"
            "const email = upstream.email || upstream.Email || '';\n"
            "const subject = upstream.subject || upstream.Subject\n"
            "  || 'Following up on your interest';\n"
            "const name = upstream.name || upstream.Name || '';\n"
            "\n"
            "const htmlBody = `<div style=\"font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;\">\n"
            "  <div style=\"background: #FF6D5A; padding: 16px; border-radius: 8px 8px 0 0;\">\n"
            "    <h2 style=\"color: white; margin: 0;\">AnyVision Media</h2>\n"
            "  </div>\n"
            "  <div style=\"background: white; padding: 20px; border: 1px solid #e0e0e0; border-radius: 0 0 8px 8px;\">\n"
            "    ${aiContent.replace(/\\n/g, '<br>')}\n"
            "    <hr style=\"border: 1px solid #eee; margin-top: 20px;\">\n"
            "    <p style=\"color: #888; font-size: 11px;\">AnyVision Media | Johannesburg, South Africa</p>\n"
            "  </div>\n"
            "</div>`;\n"
            "\n"
            "return [{ json: {\n"
            "  email: email,\n"
            "  subject: subject,\n"
            "  name: name,\n"
            "  htmlBody: htmlBody,\n"
            "} }];"
        )
        format_html_node["parameters"]["jsCode"] = new_code
        changes.append("Updated 'Format HTML' (warm path) to preserve email, subject, name")

    # Also fix "Format Follow-Up HTML"
    followup_html_node = node_map.get("Format Follow-Up HTML")
    if followup_html_node:
        new_code = (
            "// Get AI-generated follow-up content\n"
            "const aiResp = $json;\n"
            "const aiContent = (aiResp.choices && aiResp.choices[0])\n"
            "  ? aiResp.choices[0].message.content\n"
            "  : '';\n"
            "\n"
            "const upstream = $('Prepare Follow-Up Context').first().json;\n"
            "const email = upstream.email || upstream.Email || '';\n"
            "const subject = upstream.subject || upstream.Subject\n"
            "  || 'Quick follow-up from AnyVision Media';\n"
            "const name = upstream.name || upstream.Name || '';\n"
            "\n"
            "const htmlBody = `<div style=\"font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;\">\n"
            "  <div style=\"background: #FF6D5A; padding: 16px; border-radius: 8px 8px 0 0;\">\n"
            "    <h2 style=\"color: white; margin: 0;\">AnyVision Media</h2>\n"
            "  </div>\n"
            "  <div style=\"background: white; padding: 20px; border: 1px solid #e0e0e0; border-radius: 0 0 8px 8px;\">\n"
            "    ${aiContent.replace(/\\n/g, '<br>')}\n"
            "    <hr style=\"border: 1px solid #eee; margin-top: 20px;\">\n"
            "    <p style=\"color: #888; font-size: 11px;\">AnyVision Media | Johannesburg, South Africa</p>\n"
            "  </div>\n"
            "</div>`;\n"
            "\n"
            "return [{ json: {\n"
            "  email: email,\n"
            "  subject: subject,\n"
            "  name: name,\n"
            "  htmlBody: htmlBody,\n"
            "} }];"
        )
        followup_html_node["parameters"]["jsCode"] = new_code
        changes.append("Updated 'Format Follow-Up HTML' to preserve email, subject, name")

    # Swap OpenRouter credentials on all AI nodes
    for ai_name in ["AI Generate Email", "AI Generate Cold Email", "AI Generate Follow-Up"]:
        ai_node = node_map.get(ai_name)
        if ai_node and swap_openrouter_cred(ai_node):
            changes.append(f"Swapped OpenRouter credential on '{ai_name}'")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ---------------------------------------------------------------
# FIX 4: DATA-02 + KM-01 - OpenRouter credential swap
# ---------------------------------------------------------------

def fix_data02(client):
    """Swap OpenRouter credential on DATA-02."""
    wf_id = "oMFz2y6ntoqcYxkZ"

    print("\n" + "=" * 60)
    print("FIX 4a: DATA-02 Daily Trend Dashboard - OpenRouter credential")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    ai_node = node_map.get("AI Trend Insights")
    if ai_node and swap_openrouter_cred(ai_node):
        changes.append("Swapped OpenRouter credential on 'AI Trend Insights'")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


def fix_km01(client):
    """Swap OpenRouter credential on KM-01."""
    wf_id = "yl6JUOIkQstPhGQp"

    print("\n" + "=" * 60)
    print("FIX 4b: KM-01 Document Indexer - OpenRouter credential")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    ai_node = node_map.get("AI Summarize and Tag")
    if ai_node and swap_openrouter_cred(ai_node):
        changes.append("Swapped OpenRouter credential on 'AI Summarize and Tag'")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ---------------------------------------------------------------
# FIX 5: INTEL-04, INTEL-06, CRM-02 - Fix JSON.stringify expression
# ---------------------------------------------------------------

def _insert_code_node_before(wf, ai_node_name, code_node_name, code_js, upstream_node_name):
    """Insert a Code node before an AI HTTP Request node, rewiring connections.

    Returns list of change descriptions.
    """
    node_map = {n["name"]: n for n in wf["nodes"]}
    conns = wf["connections"]
    changes = []

    ai_node = node_map.get(ai_node_name)
    if not ai_node:
        print(f"  WARNING: '{ai_node_name}' node not found")
        return changes

    # Create the new Code node positioned just before the AI node
    ai_pos = ai_node.get("position", [1100, 300])
    code_node = {
        "parameters": {
            "jsCode": code_js,
        },
        "id": str(uuid.uuid4()),
        "name": code_node_name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [ai_pos[0] - 100, ai_pos[1] + 150],
    }

    # Move AI node right to make space
    ai_node["position"] = [ai_pos[0] + 120, ai_pos[1]]

    wf["nodes"].append(code_node)
    changes.append(f"Added '{code_node_name}' Code node before '{ai_node_name}'")

    # Rewire: upstream -> code_node -> ai_node
    # Find who connects TO ai_node_name and redirect to code_node_name
    for src_name, src_conns in conns.items():
        if "main" not in src_conns:
            continue
        for output_idx, output_targets in enumerate(src_conns["main"]):
            for i, target in enumerate(output_targets):
                if target.get("node") == ai_node_name:
                    output_targets[i] = {"node": code_node_name, "type": "main", "index": 0}
                    changes.append(f"Redirected '{src_name}' -> '{code_node_name}'")

    # Add code_node -> ai_node connection
    conns[code_node_name] = {
        "main": [[{"node": ai_node_name, "type": "main", "index": 0}]]
    }
    changes.append(f"Added '{code_node_name}' -> '{ai_node_name}' connection")

    # Update the AI node to use the pre-built body from code node
    # Remove the broken expression-based jsonBody
    params = ai_node["parameters"]
    params["sendBody"] = True
    params["specifyBody"] = "json"
    params["jsonBody"] = "={{ $json.requestBody }}"

    # Ensure method is POST
    params["method"] = "POST"

    changes.append(f"Updated '{ai_node_name}' to use pre-built body from '{code_node_name}'")

    return changes


def fix_intel04(client):
    """Fix INTEL-04 JSON.stringify expression + swap credential."""
    wf_id = "gijDxxcJjHMHnaUn"

    print("\n" + "=" * 60)
    print("FIX 5a: INTEL-04 Competitive Scan - Fix AI body expression")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    code_js = (
        "// Build the OpenRouter request body with findings data\n"
        "const findings = $json.findings || [];\n"
        "const body = {\n"
        "  model: 'anthropic/claude-sonnet-4-20250514',\n"
        "  max_tokens: 1500,\n"
        "  messages: [\n"
        "    {\n"
        "      role: 'system',\n"
        "      content: 'You are a competitive intelligence analyst for AnyVision Media, a South African digital agency in Johannesburg. Analyze search results for competitive intelligence. For each finding, classify its Category as one of: Pricing, Service, Hiring, Market, Regulatory. Rate Significance as High, Medium, or Low. Return a JSON array of objects with keys: competitor, finding, category, significance. Be concise and specific.'\n"
        "    },\n"
        "    {\n"
        "      role: 'user',\n"
        "      content: 'Analyze these search results for competitive intelligence. Identify new competitor activities, pricing changes, service launches, or market shifts relevant to a South African digital agency:\\n\\n' + JSON.stringify(findings, null, 2)\n"
        "    }\n"
        "  ]\n"
        "};\n"
        "return [{ json: { requestBody: JSON.stringify(body) } }];"
    )

    inserted = _insert_code_node_before(wf, "AI Analyze Changes", "Prepare AI Body", code_js, "Parse Results")
    changes.extend(inserted)

    # Swap credential
    node_map = {n["name"]: n for n in wf["nodes"]}
    ai_node = node_map.get("AI Analyze Changes")
    if ai_node and swap_openrouter_cred(ai_node):
        changes.append("Swapped OpenRouter credential on 'AI Analyze Changes'")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


def fix_intel06(client):
    """Fix INTEL-06 JSON.stringify expression + swap credential."""
    wf_id = "sbEwotSVpnyqrQtG"

    print("\n" + "=" * 60)
    print("FIX 5b: INTEL-06 Regulatory Alert - Fix AI body expression")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    code_js = (
        "// Build the OpenRouter request body with findings data\n"
        "const findings = $json.findings || [];\n"
        "const body = {\n"
        "  model: 'anthropic/claude-sonnet-4-20250514',\n"
        "  max_tokens: 1500,\n"
        "  messages: [\n"
        "    {\n"
        "      role: 'system',\n"
        "      content: 'You are a regulatory compliance analyst for AnyVision Media, a South African digital agency. Analyze regulatory search results and classify each finding. For each, provide: regulation (name/reference), description (1-2 sentences), impact (High/Medium/Low), action_required (specific action the business should take). Return a JSON array. Focus on POPIA, advertising standards, digital marketing laws, and data protection regulations relevant to South Africa.'\n"
        "    },\n"
        "    {\n"
        "      role: 'user',\n"
        "      content: 'Classify these regulatory findings for business impact:\\n\\n' + JSON.stringify(findings, null, 2)\n"
        "    }\n"
        "  ]\n"
        "};\n"
        "return [{ json: { requestBody: JSON.stringify(body) } }];"
    )

    inserted = _insert_code_node_before(wf, "AI Classify Impact", "Prepare AI Body", code_js, "Check New Alerts")
    changes.extend(inserted)

    # Swap credential
    node_map = {n["name"]: n for n in wf["nodes"]}
    ai_node = node_map.get("AI Classify Impact")
    if ai_node and swap_openrouter_cred(ai_node):
        changes.append("Swapped OpenRouter credential on 'AI Classify Impact'")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


def fix_crm02(client):
    """Fix CRM-02 JSON.stringify expression + swap credential."""
    wf_id = "Up3ROwbRMHVjZhvc"

    print("\n" + "=" * 60)
    print("FIX 5c: CRM-02 Nightly Dedup - Fix AI body expression")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    code_js = (
        "// Build the OpenRouter request body with duplicate groups\n"
        "const duplicateGroups = $json.duplicateGroups || [];\n"
        "const body = {\n"
        "  model: 'anthropic/claude-sonnet-4-20250514',\n"
        "  max_tokens: 2000,\n"
        "  messages: [\n"
        "    {\n"
        "      role: 'system',\n"
        "      content: 'You are a CRM data quality assistant. For each duplicate group, determine which record to keep as primary and what data to merge from duplicates. Return valid JSON array with objects: {keepId, mergeFromIds: [], mergedFields: {name, phone, company}}. Pick the record with the most complete data as primary. Merge non-empty fields from duplicates into the primary.'\n"
        "    },\n"
        "    {\n"
        "      role: 'user',\n"
        "      content: 'Analyze these duplicate groups and decide merges:\\n' + JSON.stringify(duplicateGroups, null, 2)\n"
        "    }\n"
        "  ]\n"
        "};\n"
        "return [{ json: { requestBody: JSON.stringify(body), duplicateGroups: duplicateGroups } }];"
    )

    inserted = _insert_code_node_before(wf, "AI Merge Decision", "Prepare AI Body", code_js, "Duplicates Found?")
    changes.extend(inserted)

    # Swap credential
    node_map = {n["name"]: n for n in wf["nodes"]}
    ai_node = node_map.get("AI Merge Decision")
    if ai_node and swap_openrouter_cred(ai_node):
        changes.append("Swapped OpenRouter credential on 'AI Merge Decision'")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ---------------------------------------------------------------
# FIX 6: QA-03 - Airtable field name fix
# ---------------------------------------------------------------

def fix_qa03(client):
    """Switch Write Benchmark from autoMapInputData to defineBelow with correct fields."""
    wf_id = "N0VEU3RHsq3OIoqR"

    print("\n" + "=" * 60)
    print("FIX 6: QA-03 Performance Benchmark - Airtable field mapping")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    write_node = node_map.get("Write Benchmark")
    if write_node:
        write_node["parameters"]["columns"] = {
            "mappingMode": "defineBelow",
            "value": {
                "Date": "={{ $json.date }}",
                "URL": "={{ $json.url }}",
                "Name": "={{ $json.name }}",
                "Performance Score": "={{ $json.performance_score }}",
                "Accessibility Score": "={{ $json.accessibility_score }}",
                "SEO Score": "={{ $json.seo_score }}",
                "Best Practices Score": "={{ $json.best_practices_score }}",
                "LCP ms": "={{ $json.lcp_ms }}",
                "FID ms": "={{ $json.fid_ms }}",
                "CLS": "={{ $json.cls }}",
                "Passed": "={{ $json.passed }}",
                "Reason": "={{ $json.reason }}",
            },
        }
        changes.append("Switched 'Write Benchmark' to defineBelow with capitalized field names")
    else:
        print("  WARNING: 'Write Benchmark' node not found")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ---------------------------------------------------------------
# FIX 7: DEVOPS-02 - Airtable array field fix
# ---------------------------------------------------------------

def fix_devops02(client):
    """Switch Write Check Results to defineBelow, map only scalar fields."""
    wf_id = "VuBUg4r0BLL81KIF"

    print("\n" + "=" * 60)
    print("FIX 7: DEVOPS-02 Credential Rotation Alert - Airtable field fix")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    write_node = node_map.get("Write Check Results")
    if write_node:
        write_node["parameters"]["columns"] = {
            "mappingMode": "defineBelow",
            "value": {
                "Total": "={{ $json.total }}",
                "Expiring Count": "={{ $json.expiring_count }}",
                "Expired Count": "={{ $json.expired_count }}",
                "Needs Alert": "={{ $json.needs_alert }}",
                "Checked At": "={{ $json.checked_at }}",
                "Summary": "={{ $json.summary }}",
            },
        }
        changes.append("Switched 'Write Check Results' to defineBelow (excluded 'credentials' array)")
    else:
        print("  WARNING: 'Write Check Results' node not found")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ---------------------------------------------------------------
# FIX 8: QA-01 - Missing columns.mappingMode fix
# ---------------------------------------------------------------

def fix_qa01(client):
    """Fix Write Results - add mappingMode and exclude failed_tests array."""
    wf_id = "oWZ6VTwbYOflPAMS"

    print("\n" + "=" * 60)
    print("FIX 8: QA-01 Daily Smoke Test - Fix Write Results Airtable node")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    write_node = node_map.get("Write Results")
    if write_node:
        columns = write_node["parameters"].get("columns", {})
        # It already has value dict with field mappings, just needs mappingMode
        if "mappingMode" not in columns:
            columns["mappingMode"] = "defineBelow"
            changes.append("Added missing 'mappingMode: defineBelow' to 'Write Results'")
        # Ensure the value dict doesn't include failed_tests
        value = columns.get("value", {})
        if "failed_tests" in value:
            del value["failed_tests"]
            changes.append("Removed 'failed_tests' array field from Write Results")
        columns["value"] = value
        write_node["parameters"]["columns"] = columns
    else:
        print("  WARNING: 'Write Results' node not found")

    # Also fix the Set Test URLs Code node - it returns bare objects without {json:} wrapper
    set_urls_node = node_map.get("Set Test URLs")
    if set_urls_node:
        old_code = set_urls_node["parameters"].get("jsCode", "")
        if "{json:" not in old_code and "\"url\":" in old_code:
            new_code = (
                "return [\n"
                "  {json: {\"url\": \"https://portal.anyvisionmedia.com/login\", \"name\": \"Portal Login\", \"expect\": \"portal\"}},\n"
                "  {json: {\"url\": \"https://portal.anyvisionmedia.com/dashboard\", \"name\": \"Portal Dashboard\", \"expect\": \"portal\"}},\n"
                "  {json: {\"url\": \"https://www.anyvisionmedia.com\", \"name\": \"Landing Page Home\", \"expect\": \"AnyVision\"}},\n"
                "  {json: {\"url\": \"https://www.anyvisionmedia.com/about\", \"name\": \"Landing Page About\", \"expect\": \"AnyVision\"}},\n"
                "  {json: {\"url\": \"https://www.anyvisionmedia.com/services\", \"name\": \"Landing Page Services\", \"expect\": \"AnyVision\"}}\n"
                "];"
            )
            set_urls_node["parameters"]["jsCode"] = new_code
            changes.append("Wrapped Set Test URLs return values in {json:} format")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ---------------------------------------------------------------
# FIX 9: CURE-01 - Paired item error fix
# ---------------------------------------------------------------

def fix_cure01(client):
    """Fix Detect Duplicates to use $input.all() instead of $json."""
    wf_id = "mYMT5IxJUl9TPMcV"

    print("\n" + "=" * 60)
    print("FIX 9: CURE-01 Nightly Dedup Scan - Paired item error fix")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    dedup_node = node_map.get("Detect Duplicates")
    if dedup_node:
        new_code = (
            "// Use $input.all() to avoid paired item errors\n"
            "const items = $input.all();\n"
            "const records = items.map(i => i.json);\n"
            "\n"
            "// Group by normalized email\n"
            "const emailGroups = {};\n"
            "for (const rec of records) {\n"
            "  const email = (rec.Email || rec.email || '').toLowerCase().trim();\n"
            "  if (!email || !email.includes('@')) continue;\n"
            "  if (!emailGroups[email]) emailGroups[email] = [];\n"
            "  emailGroups[email].push(rec);\n"
            "}\n"
            "\n"
            "const duplicateGroups = [];\n"
            "let totalDuplicates = 0;\n"
            "\n"
            "for (const [email, group] of Object.entries(emailGroups)) {\n"
            "  if (group.length <= 1) continue;\n"
            "  const scored = group.map(r => {\n"
            "    const fields = ['Name', 'Email', 'Phone', 'Company', 'Source'];\n"
            "    const filled = fields.filter(f => r[f] && String(r[f]).trim()).length;\n"
            "    return { record: r, score: filled };\n"
            "  });\n"
            "  scored.sort((a, b) => b.score - a.score);\n"
            "  const dupIds = scored.slice(1).map(s => s.record.id || '');\n"
            "  totalDuplicates += dupIds.length;\n"
            "  duplicateGroups.push({\n"
            "    email,\n"
            "    primaryId: scored[0].record.id || '',\n"
            "    duplicateIds: dupIds,\n"
            "    count: group.length,\n"
            "  });\n"
            "}\n"
            "\n"
            "return [{ json: {\n"
            "  totalRecords: records.length,\n"
            "  duplicateGroupCount: duplicateGroups.length,\n"
            "  totalDuplicates: totalDuplicates,\n"
            "  duplicateGroups: duplicateGroups,\n"
            "  scannedAt: new Date().toISOString(),\n"
            "} }];"
        )
        dedup_node["parameters"]["jsCode"] = new_code
        changes.append("Rewrote 'Detect Duplicates' to use $input.all() (fixes paired item error)")
    else:
        print("  WARNING: 'Detect Duplicates' node not found")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ---------------------------------------------------------------
# FIX 10: COMPLY-02 + KM-02 - OpenRouter credential swap
# ---------------------------------------------------------------

def fix_comply02(client):
    """Swap OpenRouter credential on COMPLY-02."""
    wf_id = "EXnkfN49D36P9LFE"

    print("\n" + "=" * 60)
    print("FIX 10a: COMPLY-02 Ad Policy Check - OpenRouter credential")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    # Find any HTTP Request node calling openrouter.ai
    for node in wf["nodes"]:
        node_type = node.get("type", "")
        if node_type != "n8n-nodes-base.httpRequest":
            continue
        url = node.get("parameters", {}).get("url", "")
        if "openrouter.ai" in url:
            if swap_openrouter_cred(node):
                changes.append(f"Swapped OpenRouter credential on '{node['name']}'")

            # Also check for broken expression body
            body = node.get("parameters", {}).get("jsonBody", "")
            if "+ JSON.stringify(" in body:
                # Same pattern as Fix 5: insert Code node before this one
                print(f"  Found broken JSON.stringify expression in '{node['name']}'")
                # Build code to prepare body
                code_js = (
                    "// Build the OpenRouter request body\n"
                    "const inputData = $json;\n"
                    "const body = {\n"
                    "  model: 'anthropic/claude-sonnet-4-20250514',\n"
                    "  max_tokens: 1500,\n"
                    "  messages: [\n"
                    "    {\n"
                    "      role: 'system',\n"
                    "      content: 'You are a South African advertising compliance analyst. Check ad copy for POPIA, ASA, and platform policy violations. For each ad, return JSON: {ad_id, violations: [{rule, severity, description}], compliant: boolean}. Return a JSON array.'\n"
                    "    },\n"
                    "    {\n"
                    "      role: 'user',\n"
                    "      content: 'Check these ads for policy compliance:\\n\\n' + JSON.stringify(inputData, null, 2)\n"
                    "    }\n"
                    "  ]\n"
                    "};\n"
                    "return [{ json: { requestBody: JSON.stringify(body) } }];"
                )
                inserted = _insert_code_node_before(wf, node["name"], "Prepare AI Body", code_js, "Aggregate Ad Data")
                changes.extend(inserted)

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


def fix_km02(client):
    """Swap OpenRouter credential on KM-02."""
    wf_id = "Nw5LtlkQZGc3tDJF"

    print("\n" + "=" * 60)
    print("FIX 10b: KM-02 Contradiction Detector - OpenRouter credential")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    for node in wf["nodes"]:
        node_type = node.get("type", "")
        if node_type != "n8n-nodes-base.httpRequest":
            continue
        url = node.get("parameters", {}).get("url", "")
        if "openrouter.ai" in url:
            if swap_openrouter_cred(node):
                changes.append(f"Swapped OpenRouter credential on '{node['name']}'")

            body = node.get("parameters", {}).get("jsonBody", "")
            if "+ JSON.stringify(" in body:
                print(f"  Found broken JSON.stringify expression in '{node['name']}'")
                code_js = (
                    "// Build the OpenRouter request body\n"
                    "const inputData = $json;\n"
                    "const body = {\n"
                    "  model: 'anthropic/claude-sonnet-4-20250514',\n"
                    "  max_tokens: 1500,\n"
                    "  messages: [\n"
                    "    {\n"
                    "      role: 'system',\n"
                    "      content: 'You are a knowledge base quality analyst. Compare documents on the same topic and identify contradictions, inconsistencies, or outdated information. For each contradiction, return JSON: {doc1, doc2, topic, contradiction, severity: High/Medium/Low, recommendation}. Return a JSON array.'\n"
                    "    },\n"
                    "    {\n"
                    "      role: 'user',\n"
                    "      content: 'Find contradictions in these documents grouped by topic:\\n\\n' + JSON.stringify(inputData, null, 2)\n"
                    "    }\n"
                    "  ]\n"
                    "};\n"
                    "return [{ json: { requestBody: JSON.stringify(body) } }];"
                )
                inserted = _insert_code_node_before(wf, node["name"], "Prepare AI Body", code_js, "Has Topic Groups")
                changes.extend(inserted)

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ---------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------

ALL_FIXES = [
    ("crm01", fix_crm01, "CRM-01: Remove Xero reference"),
    ("bridge01", fix_bridge01, "BRIDGE-01: Fix Airtable field mapping"),
    ("bridge04", fix_bridge04, "BRIDGE-04: Fix missing email/subject"),
    ("data02", fix_data02, "DATA-02: OpenRouter credential"),
    ("km01", fix_km01, "KM-01: OpenRouter credential"),
    ("intel04", fix_intel04, "INTEL-04: Fix JSON.stringify + credential"),
    ("intel06", fix_intel06, "INTEL-06: Fix JSON.stringify + credential"),
    ("crm02", fix_crm02, "CRM-02: Fix JSON.stringify + credential"),
    ("qa03", fix_qa03, "QA-03: Airtable field mapping"),
    ("devops02", fix_devops02, "DEVOPS-02: Airtable array field"),
    ("qa01", fix_qa01, "QA-01: Missing columns.mappingMode"),
    ("cure01", fix_cure01, "CURE-01: Paired item error"),
    ("comply02", fix_comply02, "COMPLY-02: OpenRouter credential"),
    ("km02", fix_km02, "KM-02: OpenRouter credential"),
]


def fix_all(client):
    """Run all fixes."""
    all_changes = []
    errors = []

    for key, fn, desc in ALL_FIXES:
        try:
            changes = fn(client)
            all_changes.extend(changes)
        except Exception as e:
            msg = f"ERROR fixing {desc}: {e}"
            print(f"  {msg}")
            errors.append(msg)

    return all_changes, errors


def main():
    config = load_config()

    # Parse CLI args
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    print("=" * 60)
    print("FULL REVISION FIX - 2026-03-19 Session 5")
    print(f"Target: {target}")
    print("=" * 60)

    with build_client(config) as client:
        if target == "all":
            all_changes, errors = fix_all(client)
        else:
            # Find matching fix
            found = False
            all_changes = []
            errors = []
            for key, fn, desc in ALL_FIXES:
                if key == target:
                    found = True
                    try:
                        changes = fn(client)
                        all_changes.extend(changes)
                    except Exception as e:
                        msg = f"ERROR fixing {desc}: {e}"
                        print(f"  {msg}")
                        errors.append(msg)
                    break
            if not found:
                print(f"Unknown target: {target}")
                print(f"Valid targets: all, {', '.join(k for k, _, _ in ALL_FIXES)}")
                sys.exit(1)

    # Summary
    print("\n" + "=" * 60)
    print(f"COMPLETE - {len(all_changes)} fixes deployed, {len(errors)} errors")
    print("=" * 60)
    for i, c in enumerate(all_changes, 1):
        print(f"  {i}. {c}")
    if errors:
        print("\nERRORS:")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()

"""
Fix Business Email Management Automation - HTML email formatting + branded signature.

Problem: Two email-sending nodes send plain text with no HTML and no signature.
  - Line breaks (\n) don't render in email clients
  - No branded AnyVision Media signature

Fix:
1. Parse AI Response: adds html_response field (formatted HTML with signature)
2. Send Thank You: replaces plain text with branded HTML message
3. Create Reply: switches from suggested_response to html_response

Usage:
    python tools/fix_email_formatting.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "g2uPmEBbAEtz9YP4L8utG"

# Branded HTML signature from email-signature.html
SIGNATURE_HTML = '''<table cellpadding="0" cellspacing="0" border="0" style="font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif;font-size:14px;line-height:1.4;color:#333333;">
  <tr>
    <td style="vertical-align:top;padding-right:18px;">
      <a href="https://www.anyvisionmedia.com" target="_blank" style="text-decoration:none;">
        <img src="https://www.anyvisionmedia.com/logo-icon.png" alt="AnyVision Media" width="70" style="display:block;border:0;width:70px;height:70px;" />
      </a>
    </td>
    <td style="vertical-align:top;padding-left:18px;border-left:3px solid #6C63FF;">
      <table cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-size:20px;font-weight:700;color:#0A0F1C;padding-bottom:2px;letter-spacing:-0.3px;">
            Ian
          </td>
        </tr>
        <tr>
          <td style="font-size:13px;font-weight:400;color:#6B7280;padding-bottom:10px;">
            Founder&nbsp;&nbsp;&#183;&nbsp;&nbsp;<span style="color:#6C63FF;font-weight:600;">AnyVision Media</span>
          </td>
        </tr>
        <tr>
          <td style="padding-bottom:10px;">
            <table cellpadding="0" cellspacing="0" border="0" width="200">
              <tr>
                <td width="100" style="height:2px;background-color:#6C63FF;font-size:0;line-height:0;">&nbsp;</td>
                <td width="100" style="height:2px;background-color:#00D4AA;font-size:0;line-height:0;">&nbsp;</td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="font-size:12px;color:#333333;padding-bottom:3px;">
            <a href="mailto:ian@anyvisionmedia.com" style="color:#6C63FF;text-decoration:none;font-weight:500;">ian@anyvisionmedia.com</a>
          </td>
        </tr>
        <tr>
          <td style="font-size:12px;color:#333333;padding-bottom:3px;">
            <a href="https://www.anyvisionmedia.com" target="_blank" style="color:#6C63FF;text-decoration:none;font-weight:500;">www.anyvisionmedia.com</a>
          </td>
        </tr>
        <tr>
          <td style="font-size:11px;color:#9CA3AF;padding-top:2px;">
            Johannesburg, South Africa
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>'''

# Static HTML for the "Send Thank You" node
THANK_YOU_HTML = (
    '<div style="font-family:\'Segoe UI\',\'Helvetica Neue\',Arial,sans-serif;font-size:14px;line-height:1.5;color:#333333;">'
    '<p style="margin:0 0 12px 0;">Hi {{ $json.sender_name }},</p>'
    '<p style="margin:0 0 12px 0;">Thank you so much for getting back to us! We really appreciate your interest.</p>'
    '<p style="margin:0 0 12px 0;">I\'ll be in touch shortly to discuss how AnyVision Media can help you further. '
    'In the meantime, if you have any questions, feel free to reply to this email.</p>'
    '<p style="margin:0 0 12px 0;">Looking forward to connecting!</p>'
    '<br>'
    + SIGNATURE_HTML
    + '</div>'
)


def fix_parse_ai_response(node_map):
    """Add html_response field to Parse AI Response output."""
    print("  [1] Adding html_response field to Parse AI Response...")
    parse_node = node_map["Parse AI Response"]
    code = parse_node["parameters"]["jsCode"]

    if "html_response" in code:
        print("      html_response already present, skipping")
        return

    # Escape signature for embedding in a JS template literal
    sig_for_js = SIGNATURE_HTML.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

    # The IIFE that converts plain text -> HTML paragraphs + signature
    html_response_js = (
        "      html_response: (() => {\n"
        "        const text = parsed.suggested_response || '';\n"
        "        if (!text) return '';\n"
        "        const paragraphs = text.split(/\\n\\n+/);\n"
        "        const htmlParagraphs = paragraphs\n"
        "          .map(p => p.replace(/\\n/g, '<br>'))\n"
        "          .map(p => '<p style=\"margin:0 0 12px 0;font-family:Segoe UI,Helvetica Neue,Arial,sans-serif;font-size:14px;line-height:1.5;color:#333333;\">' + p + '</p>')\n"
        "          .join('');\n"
        f"        const signature = `{sig_for_js}`;\n"
        "        return '<div style=\"font-family:Segoe UI,Helvetica Neue,Arial,sans-serif;\">' + htmlParagraphs + '<br>' + signature + '</div>';\n"
        "      })(),"
    )

    # Insert after the suggested_response line
    anchor = "      suggested_response: parsed.suggested_response || '',"
    if anchor not in code:
        print("      WARNING: Could not find suggested_response anchor in jsCode")
        print("      Attempting alternative anchor...")
        # Try without leading spaces
        anchor = "suggested_response: parsed.suggested_response || '',"
        if anchor not in code:
            print("      ERROR: Cannot locate suggested_response in Parse AI Response jsCode")
            return

    replacement = anchor + "\n" + html_response_js
    code = code.replace(anchor, replacement, 1)
    parse_node["parameters"]["jsCode"] = code
    print("      Added html_response IIFE after suggested_response")


def fix_send_thank_you(node_map):
    """Replace plain text Send Thank You with HTML + signature."""
    print("  [2] Replacing Send Thank You with HTML formatted message...")
    if "Send Thank You" not in node_map:
        print("      WARNING: Send Thank You node not found")
        return
    node = node_map["Send Thank You"]
    node["parameters"]["message"] = THANK_YOU_HTML
    print("      Message replaced with HTML + branded signature")


def fix_create_reply(node_map):
    """Switch Create Reply from plain text to HTML response."""
    print("  [3] Switching Create Reply to use html_response...")
    if "Create Reply" not in node_map:
        print("      WARNING: Create Reply node not found")
        return
    node = node_map["Create Reply"]
    old_msg = node["parameters"].get("message", "")
    node["parameters"]["message"] = "={{ $json.html_response }}"
    print(f"      Message changed: {old_msg[:50]}... -> ={{{{ $json.html_response }}}}")


def fix_workflow(wf):
    """Apply HTML email formatting + branded signature."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}

    fix_parse_ai_response(node_map)
    fix_send_thank_you(node_map)
    fix_create_reply(node_map)

    print("\n  All fixes applied successfully!")
    return wf


def main():
    config = load_config()
    base_url = config["n8n"]["base_url"].rstrip("/")
    api_key = config["api_keys"]["n8n"]

    headers = {
        "X-N8N-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    # Fetch live workflow
    print(f"Fetching workflow {WORKFLOW_ID}...")
    resp = httpx.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers, timeout=30)
    resp.raise_for_status()
    wf = resp.json()
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    # Idempotency check
    parse_node = next((n for n in wf["nodes"] if n["name"] == "Parse AI Response"), None)
    if parse_node and "html_response" in parse_node["parameters"].get("jsCode", ""):
        print("  WARNING: Parse AI Response already contains html_response. Skipping to avoid double-patching.")
        print("  To re-apply, restore from backup first.")
        return

    # Save backup
    backup_path = "workflows/business_email_mgmt_backup_pre_html_formatting.json"
    with open(backup_path, "w") as f:
        json.dump(wf, f, indent=2)
    print(f"  Backup saved to {backup_path}")

    # Apply fixes
    wf = fix_workflow(wf)

    # Save patched JSON locally
    local_path = "workflows/business_email_mgmt_automation.json"
    with open(local_path, "w") as f:
        json.dump(wf, f, indent=2)
    print(f"  Patched JSON saved to {local_path}")

    # Push to n8n
    print("Pushing patched workflow to n8n...")
    update_payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": {"executionOrder": "v1"},
    }
    resp = httpx.put(
        f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
        headers=headers,
        json=update_payload,
        timeout=30
    )
    if resp.status_code >= 400:
        print(f"  ERROR {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    result = resp.json()
    print(f"  Workflow updated: {result.get('name')} (v{result.get('versionId', 'unknown')})")

    # Workflow stays INACTIVE (matching current state)
    print("  Note: Workflow left INACTIVE (as before). Activate manually when ready.")

    print("\n=== DONE ===")
    print("Changes made:")
    print("  [1] Parse AI Response: added html_response field (plain text -> HTML paragraphs + signature)")
    print("  [2] Send Thank You: replaced plain text with HTML + branded signature")
    print("  [3] Create Reply: switched from suggested_response to html_response")
    print("\nTo verify:")
    print("  1. Open the workflow in n8n editor")
    print("  2. Check Parse AI Response code node for html_response IIFE")
    print("  3. Check Send Thank You message for HTML content")
    print("  4. Check Create Reply message for html_response reference")
    print("  5. Use 'Test workflow' with a sample email to confirm HTML renders correctly")


if __name__ == "__main__":
    main()

"""
Fix Lead Scraper - Professional Email Overhaul.

Previous fix (fix_lead_scraper_placeholders.py) added anti-placeholder prompt
rules and stripPlaceholders(), but emails STILL go out broken because:

1. Format Email node has onError:continueRegularOutput -> if the JS errors
   (e.g. $('Prepare AI Input') reference breaks), raw AI output passes through
2. allLeads[index] indexing desyncs when items get filtered between nodes
3. AI still generates USD ($) amounts — no ZAR instruction in prompt
4. Bullet points (dot bullets) render inline — no \n before each bullet
5. AI adds its own sign-off ("Best, [Your Name]") PLUS template adds another
6. CTA duplicated: AI body CTA + template cta_text + template signature
7. No validation gate between Format Email and Send — broken emails go out

This script patches all 7 issues in the live workflow.
"""

import sys
import json

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "uq4hnH0YHfhYOOzO"


# ── NEW NODE CODE ──────────────────────────────────────────────────────────

PREPARE_AI_INPUT_CODE = r"""const items = $input.all();
return items.map(item => {
  const leadData = item.json;
  const biz = leadData.businessName || 'your business';
  const ind = leadData.industry || 'your industry';
  const loc = leadData.location || 'your area';
  const web = leadData.website || '';
  const contactName = leadData.contactName || '';

  const greeting = contactName
    ? `Address the recipient by first name: ${contactName.split(' ')[0]}`
    : 'Start with "Hi there," - do NOT use [First Name] or any bracket placeholder';

  const prompt = `You are a business automation consultant at AnyVision Media, based in South Africa.

Write a short, personalised cold outreach email.

=== ABSOLUTE RULES (violating ANY = email is rejected) ===
1. NEVER use bracket placeholders: [First Name], [Industry], [Business Name], [Your Name], [Company], [Location], etc.
2. NEVER use US dollars ($). ALL currency must be South African Rand using "R" prefix (e.g. R50,000).
3. NEVER add a sign-off like "Best," or "Regards," or "Kind regards," — the email template adds the signature automatically.
4. Each bullet point or numbered item MUST be on its own line. Use \\n before each bullet.
5. The body must be plain text with \\n for line breaks. No HTML, no markdown.

=== BUSINESS CONTEXT ===
- Business: ${biz}
- Industry: ${ind}
- Location: ${loc}
- Website: ${web}

=== INSTRUCTIONS ===
1. Subject line (max 55 chars): Reference their specific business type or a pain point
2. ${greeting}
3. Body (80-120 words max):
   - Open with ONE specific pain point for ${ind} businesses
   - Mention ONE concrete automation win (e.g. "automate follow-ups", "eliminate manual data entry")
   - Include ONE proof point using Rand: "We helped a Johannesburg firm save R25,000/month in admin costs"
   - End with: "Would a quick 15-minute call work to explore this?"
4. Tone: Consultative, professional, NOT salesy. No exclamation marks.
5. Do NOT include any sign-off, name, or closing — just end after the CTA question.

=== OUTPUT FORMAT (strict JSON, no markdown fences) ===
{"subject": "Your subject here", "body": "Hi there,\\n\\nFirst paragraph here.\\n\\nSecond paragraph here.\\n\\nWould a quick 15-minute call work to explore this?"}

=== EXAMPLE OUTPUT ===
{"subject": "Automate patient reminders at your practice", "body": "Hi there,\\n\\nMost dental practices in Sandton spend 10+ hours a week on manual appointment reminders and follow-ups. That is time your team could spend on patient care.\\n\\nWe helped a Johannesburg healthcare practice save R25,000 per month by automating their reminder system and reducing no-shows by 40%.\\n\\nWould a quick 15-minute call work to explore this?"}`;

  return {
    json: {
      ...leadData,
      chatInput: prompt,
      _email: leadData.email,
      _contactName: contactName,
      _businessName: biz,
      _industry: ind,
      _location: loc
    }
  };
});"""


FORMAT_EMAIL_CODE = r"""const items = $input.all();
const config = $('Search Config').first().json;

function sanitize(str) {
  return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

return items.map((item, index) => {
  const input = item.json;

  // Carry lead data through from AI input (avoids index desync)
  let leadData = {};
  try {
    const allLeads = $('Prepare AI Input').all();
    leadData = allLeads[index]?.json || {};
  } catch (e) {
    // If reference fails, fall back to data carried through the chain
    leadData = {};
  }
  // Prefer data carried on the item itself (set in Prepare AI Input via _fields)
  const contactName = input._contactName || leadData.contactName || '';
  const businessName = input._businessName || leadData.businessName || '';
  const industry = input._industry || leadData.industry || '';
  const location = input._location || leadData.location || '';
  const leadEmail = input._email || leadData.email || '';

  // Parse AI response
  let emailContent;
  let usedFallback = false;
  try {
    const rawText = input.text || input.response || JSON.stringify(input);
    const jsonMatch = rawText.match(/\{[\s\S]*\}/);
    emailContent = JSON.parse(jsonMatch[0]);
    if (!emailContent.subject || !emailContent.body) throw new Error('missing fields');
  } catch (e) {
    usedFallback = true;
    const industryName = industry || 'your industry';
    const greeting = contactName ? `Hi ${contactName.split(' ')[0]}` : 'Hi there';
    emailContent = {
      subject: `Automate ${industryName} workflows - save 15h/week`,
      body: `${greeting},\n\nI work with ${industryName} businesses in ${location || 'your area'} to automate time-consuming tasks like follow-ups, data entry, and reporting.\n\nWe helped a Johannesburg firm save R25,000 per month by automating their admin workflows.\n\nWould a quick 15-minute call work to explore this?`
    };
  }

  // ── SAFETY NET 1: Strip bracket placeholders ──
  function stripPlaceholders(text) {
    if (!text) return text;
    const map = {
      'First Name': contactName ? contactName.split(' ')[0] : 'there',
      'Business Name': businessName || 'your business',
      'Company Name': businessName || 'your business',
      'Industry': industry || 'your industry',
      'Location': location || 'your area',
      'Your Name': 'Ian Immelman',
      'Sender Name': 'Ian Immelman',
      'Company': 'AnyVision Media',
      'similar location/region': location || 'your area',
      'similar location': location || 'your area',
      'region': location || 'your area'
    };
    let result = text;
    for (const [ph, rep] of Object.entries(map)) {
      const escaped = ph.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      result = result.replace(new RegExp('\\[' + escaped + '\\]', 'gi'), rep);
    }
    // Catch any remaining [Capitalised Word] patterns
    result = result.replace(/\[([A-Z][a-z]+(?:\s[A-Za-z/]+){0,3})\]/g, (match, inner) => {
      const l = inner.toLowerCase();
      if (l.includes('name')) return contactName ? contactName.split(' ')[0] : 'there';
      if (l.includes('industry')) return industry || 'your industry';
      if (l.includes('location') || l.includes('region') || l.includes('area')) return location || 'your area';
      if (l.includes('company') || l.includes('business')) return businessName || 'your business';
      return inner;
    });
    // Catch "Hi [anything]"
    result = result.replace(/Hi\s+\[.*?\]/gi, contactName ? 'Hi ' + contactName.split(' ')[0] : 'Hi there');
    return result;
  }

  emailContent.subject = stripPlaceholders(emailContent.subject);
  emailContent.body = stripPlaceholders(emailContent.body);

  // ── SAFETY NET 2: Convert USD to ZAR ──
  emailContent.body = emailContent.body.replace(/\$(\d[\d,]*)/g, 'R$1');
  emailContent.subject = emailContent.subject.replace(/\$(\d[\d,]*)/g, 'R$1');

  // ── SAFETY NET 3: Strip AI-generated sign-offs (template adds its own) ──
  emailContent.body = emailContent.body
    .replace(/\n*(Best|Regards|Kind regards|Warm regards|Cheers|Sincerely|Thanks|Thank you),?\s*\n.*/si, '')
    .trim();

  // ── SAFETY NET 4: Fix bullet formatting ──
  // Ensure bullets are on their own lines
  emailContent.body = emailContent.body
    .replace(/([^\n])\s*([•\-\*]\s)/g, '$1\n$2')
    .replace(/([^\n])(\d+\.\s)/g, '$1\n$2');

  // ── VALIDATION: Reject if placeholders remain ──
  const hasPlaceholders = /\[[A-Z][a-z]*(?:\s[A-Za-z]+)*\]/.test(emailContent.body + ' ' + emailContent.subject);
  if (hasPlaceholders) {
    // Force fallback
    const greeting = contactName ? `Hi ${contactName.split(' ')[0]}` : 'Hi there';
    const industryName = industry || 'your industry';
    emailContent = {
      subject: `Automate ${industryName} workflows - save 15h/week`,
      body: `${greeting},\n\nI work with ${industryName} businesses in ${location || 'your area'} to automate time-consuming tasks like follow-ups, data entry, and reporting.\n\nWe helped a Johannesburg firm save R25,000 per month by automating their admin workflows.\n\nWould a quick 15-minute call work to explore this?`
    };
  }

  // ── BUILD HTML ──
  const bodyHtml = sanitize(emailContent.body)
    .replace(/\\n/g, '<br>')
    .replace(/\n/g, '<br>')
    .replace(/<br>\s*([•\-\*])/g, '<br>$1')
    .replace(/<br><br><br>/g, '<br><br>');

  const htmlBody = '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">' +
    '<div style="padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;">' +
    '<h1 style="margin:0;font-size:22px;color:#1A1A2E;">' + sanitize(config.senderCompany) + '</h1>' +
    '<p style="margin:8px 0 0;font-size:13px;color:#666;">Business Automation & Lead Generation</p></div>' +
    '<div style="padding:30px 40px;">' +
    '<div style="font-size:15px;line-height:1.7;color:#333;">' + bodyHtml + '</div>' +
    '<p style="font-size:15px;line-height:1.6;color:#333;margin-top:28px;">Best regards,<br>' +
    '<strong>' + sanitize(config.senderName) + '</strong><br>' +
    '<span style="color:#666;">' + sanitize(config.senderTitle) + '</span><br>' +
    '<span style="color:#666;">' + sanitize(config.senderCompany) + '</span></p></div>' +
    '<div style="padding:20px 40px;background:#f8f8f8;border-top:1px solid #eee;">' +
    '<p style="font-size:11px;color:#999;margin:0;">You received this because your business is listed on Google Maps. ' +
    'Reply &quot;unsubscribe&quot; to be removed.</p></div></div>';

  return {
    json: {
      to: leadEmail,
      subject: emailContent.subject,
      htmlBody: htmlBody,
      leadEmail: leadEmail,
      businessName: businessName,
      contactName: contactName,
      automationFit: input.automationFit || leadData.automationFit || '',
      _valid: !!(leadEmail && emailContent.subject && emailContent.body),
      _usedFallback: usedFallback || hasPlaceholders
    }
  };
});"""


VALIDATE_EMAIL_NODE = {
    "parameters": {
        "conditions": {
            "options": {
                "version": 2,
                "caseSensitive": True,
                "typeValidation": "strict"
            },
            "combinator": "and",
            "conditions": [
                {
                    "operator": {
                        "type": "boolean",
                        "operation": "true"
                    },
                    "leftValue": "={{ $json._valid }}",
                    "rightValue": ""
                },
                {
                    "operator": {
                        "type": "string",
                        "operation": "notContains"
                    },
                    "leftValue": "={{ $json.htmlBody }}",
                    "rightValue": "[First Name]"
                },
                {
                    "operator": {
                        "type": "string",
                        "operation": "notContains"
                    },
                    "leftValue": "={{ $json.htmlBody }}",
                    "rightValue": "[Business Name]"
                },
                {
                    "operator": {
                        "type": "string",
                        "operation": "notContains"
                    },
                    "leftValue": "={{ $json.htmlBody }}",
                    "rightValue": "[Your Name]"
                },
                {
                    "operator": {
                        "type": "string",
                        "operation": "notContains"
                    },
                    "leftValue": "={{ $json.htmlBody }}",
                    "rightValue": "[Industry]"
                }
            ]
        },
        "options": {}
    },
    "id": "val-email-gate-001",
    "name": "Validate Email Clean",
    "type": "n8n-nodes-base.if",
    "position": [3928, 64],
    "typeVersion": 2.2
}


def fix_workflow(wf):
    """Patch Prepare AI Input, Format Email, and add validation gate."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}
    connections = wf["connections"]

    # ── FIX 1: Prepare AI Input ──
    print("  [1] Patching Prepare AI Input...")
    prep = node_map["Prepare AI Input"]
    prep["parameters"]["jsCode"] = PREPARE_AI_INPUT_CODE
    print("    -> ZAR currency rule added")
    print("    -> No sign-off rule added")
    print("    -> Proper \\n line break examples")
    print("    -> Lead data carried as _fields for downstream access")

    # ── FIX 2: Format Email ──
    print("  [2] Patching Format Email...")
    fmt = node_map["Format Email"]
    fmt["parameters"]["jsCode"] = FORMAT_EMAIL_CODE
    # Remove onError so failures don't silently pass raw AI output
    if "onError" in fmt:
        del fmt["onError"]
        print("    -> Removed onError:continueRegularOutput (was hiding failures)")
    print("    -> Lead data lookup uses carried _fields (no index desync)")
    print("    -> USD->ZAR conversion safety net")
    print("    -> AI sign-off stripping (template has its own)")
    print("    -> Bullet point line-break fix")
    print("    -> Placeholder validation with forced fallback")
    print("    -> Removed duplicate CTA (template no longer adds separate cta_text)")
    print("    -> _valid flag for downstream gate")

    # ── FIX 3: Insert Validate Email gate between Format Email and Send ──
    print("  [3] Adding Validate Email gate node...")

    # Get Send Outreach Email position and shift it right
    send_node = node_map["Send Outreach Email"]
    old_send_x = send_node["position"][0]
    old_send_y = send_node["position"][1]

    # Place validate node where Format Email outputs to
    VALIDATE_EMAIL_NODE["position"] = [old_send_x, old_send_y]
    # Shift send node right by 220px
    send_node["position"] = [old_send_x + 220, old_send_y]

    # Add the validation node to the workflow
    nodes.append(VALIDATE_EMAIL_NODE)
    node_map["Validate Email Clean"] = VALIDATE_EMAIL_NODE
    print("    -> Node added at position", VALIDATE_EMAIL_NODE["position"])

    # ── FIX 4: Rewire connections ──
    print("  [4] Rewiring connections...")

    # Format Email currently connects to Send Outreach Email
    # Change it to connect to Validate Email Clean
    if "Format Email" in connections:
        fmt_conns = connections["Format Email"]
        for output_key, output_list in fmt_conns.items():
            for conn_group in output_list:
                for conn in conn_group:
                    if conn["node"] == "Send Outreach Email":
                        conn["node"] = "Validate Email Clean"
                        print("    -> Format Email -> Validate Email Clean")

    # Validate Email Clean: true (output 0) -> Send Outreach Email
    # false (output 1) -> nowhere (email gets dropped)
    connections["Validate Email Clean"] = {
        "main": [
            [{"node": "Send Outreach Email", "type": "main", "index": 0}],
            []  # false output — dropped
        ]
    }
    print("    -> Validate Email Clean (true) -> Send Outreach Email")
    print("    -> Validate Email Clean (false) -> dropped (not sent)")

    return wf


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    print("=" * 60)
    print("LEAD SCRAPER FIX - Professional Email Overhaul")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:
        # 1. Fetch
        print("\n[FETCH] Getting current workflow...")
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

        # 2. Fix
        print("\n[FIX] Applying email overhaul...")
        wf = fix_workflow(wf)

        # 3. Save locally
        from pathlib import Path
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "lead_scraper_email_fix.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVE] Saved to {output_path}")

        # 4. Deploy
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
        print(f"  Nodes: {len(result['nodes'])}")

    print("\n" + "=" * 60)
    print("FIX DEPLOYED SUCCESSFULLY")
    print("=" * 60)
    print("\nChanges made:")
    print("  1. Prepare AI Input: ZAR-only, no sign-off, proper line breaks, example output")
    print("  2. Prepare AI Input: lead data carried as _fields (survives chain breaks)")
    print("  3. Format Email: removed onError:continueRegularOutput")
    print("  4. Format Email: lead lookup uses _fields (no index desync)")
    print("  5. Format Email: USD->ZAR, sign-off strip, bullet fix, placeholder validation")
    print("  6. Format Email: forced fallback if ANY placeholder survives")
    print("  7. Format Email: single CTA, single signature (no duplicates)")
    print("  8. NEW: Validate Email Clean gate - blocks emails with [placeholders]")
    print("  9. Connections rewired: Format Email -> Validate -> Send")


if __name__ == "__main__":
    main()

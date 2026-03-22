"""
Fix Lead Scraper - Remove bracket placeholder emails.

Problem: AI generates emails with [First Name], [Industry], [Business Name], [Your Name]
instead of using the actual data. Clients receive unpersonalized template emails.

Root causes:
1. Prepare AI Input prompt doesn't explicitly forbid [placeholder] syntax
2. When Contact is "Unknown", AI hallucinates [First Name] brackets
3. Format Email node has no validation to catch leftover placeholders

Fixes:
1. Prepare AI Input - add CRITICAL anti-placeholder rules to the prompt
2. Format Email - add stripPlaceholders() safety net before sending
"""

import sys
import json

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "uq4hnH0YHfhYOOzO"


def fix_workflow(wf):
    """Patch Prepare AI Input and Format Email to eliminate bracket placeholders."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}

    # ── FIX 1: Prepare AI Input - rewrite prompt to forbid placeholders ──
    print("  [1] Patching Prepare AI Input prompt...")
    prep_node = node_map["Prepare AI Input"]

    new_prep_code = r"""const items = $input.all();
return items.map(item => {
  const leadData = item.json;
  const biz = leadData.businessName || 'your business';
  const ind = leadData.industry || 'your industry';
  const loc = leadData.location || 'the area';
  const web = leadData.website || '';
  const contactName = leadData.contactName || '';

  const greeting = contactName
    ? `Address the recipient as: ${contactName.split(' ')[0]}`
    : 'Start with "Hi there," — do NOT use [First Name] or any bracket placeholder';

  const prompt = `You are a business automation consultant at AnyVision Media.

Write a compelling cold outreach email that offers genuine value.

CRITICAL RULES — MUST FOLLOW:
- ABSOLUTELY NEVER use bracket placeholders like [First Name], [Industry], [Business Name], [Your Name], [Company], [Location], [similar location/region], etc.
- If you do not know the contact's name, write "Hi there," — NEVER "Hi [First Name]"
- Use ONLY the actual data provided below. If a field says "Unknown" or is empty, omit it gracefully.
- Every sentence must use real information, not template variables.
- Violating these rules makes the email unusable.

BUSINESS CONTEXT:
- Business: ${biz}
- Industry: ${ind}
- Location: ${loc}
- Website: ${web}

YOUR VALUE PROPOSITION:
We help ${ind} businesses automate repetitive tasks to:
1. Close deals 3x faster through automated follow-ups
2. Save 15-20 hours/week eliminating manual data entry
3. Generate 40% more leads with automated marketing

INSTRUCTIONS:
1. Subject line (max 55 chars): Reference their specific business or pain point
2. ${greeting}
3. Body (100-130 words): ONE specific automation opportunity for ${ind}, a quick win, and ROI
4. CTA: Offer a FREE 15-min automation audit — no obligation
5. Tone: Consultative, NOT salesy
6. Sign off as: Ian Immelman, Director at AnyVision Media
7. NO buzzwords, NO generic openers, NO bracket placeholders

OUTPUT FORMAT (JSON only, no markdown):
{"subject": "...", "body": "...", "cta_text": "Would a quick 15-min call work?"}`;

  return {
    json: {
      ...leadData,
      chatInput: prompt
    }
  };
});"""

    prep_node["parameters"]["jsCode"] = new_prep_code
    print("    -> Added CRITICAL anti-placeholder rules")
    print("    -> Fixed greeting to explicitly say no brackets when contact unknown")

    # ── FIX 2: Format Email - add placeholder safety net ──
    print("  [2] Patching Format Email with placeholder safety net...")
    format_node = node_map["Format Email"]

    new_format_code = r"""const items = $input.all();
const allLeads = $('Prepare AI Input').all();
const config = $('Search Config').first().json;

// Sanitize text to prevent XSS in HTML emails
function sanitize(str) {
  return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

return items.map((item, index) => {
  const input = item.json;
  const leadData = allLeads[index]?.json || {};
  const contactName = leadData.contactName || '';
  const businessName = leadData.businessName || '';
  const industry = leadData.industry || '';
  const location = leadData.location || '';

  let emailContent;
  try {
    const rawText = input.text || input.response || JSON.stringify(input);
    const jsonMatch = rawText.match(/\{[\s\S]*\}/);
    emailContent = JSON.parse(jsonMatch[0]);
  } catch (e) {
    const industryName = industry || 'your industry';
    const greeting = contactName ? `Hi ${contactName.split(' ')[0]}` : 'Hi there';
    emailContent = {
      subject: `Automate ${industryName} workflows - save 15h/week`,
      body: `${greeting},\n\nI work with ${industryName} businesses in ${location || 'your area'} to automate time-consuming tasks.\n\nMost businesses save 15-20 hours per week after implementing simple automation workflows.\n\nWould love to show you a few quick wins - no cost, just value.`,
      cta_text: 'Would a quick 15-minute call this week work?'
    };
  }

  // SAFETY NET: Replace any [bracket placeholders] the AI may have generated
  function stripPlaceholders(text) {
    if (!text) return text;
    const replacements = {
      'First Name': contactName ? contactName.split(' ')[0] : 'there',
      'Business Name': businessName || 'your business',
      'Company Name': businessName || 'your business',
      'Industry': industry || 'your industry',
      'Location': location || 'your area',
      'similar location/region': location || 'your area',
      'similar location': location || 'your area',
      'Your Name': config.senderName || 'Ian Immelman',
      'Sender Name': config.senderName || 'Ian Immelman',
      'Company': config.senderCompany || 'AnyVision Media',
      'region': location || 'your area'
    };
    let result = text;
    for (const [placeholder, replacement] of Object.entries(replacements)) {
      result = result.replace(new RegExp('\\[' + placeholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\]', 'gi'), replacement);
    }
    // Catch any remaining [Xxx Yyy] patterns that look like placeholders
    result = result.replace(/\[([A-Z][a-z]+(?:\s[A-Za-z/]+){0,3})\]/g, (match, inner) => {
      const lower = inner.toLowerCase();
      if (lower.includes('name')) return contactName ? contactName.split(' ')[0] : (businessName || 'there');
      if (lower.includes('industry')) return industry || 'your industry';
      if (lower.includes('location') || lower.includes('region') || lower.includes('area')) return location || 'your area';
      if (lower.includes('company') || lower.includes('business')) return businessName || 'your business';
      return inner; // Strip brackets but keep text
    });
    // Last resort: catch "Hi [anything]" pattern
    result = result.replace(/Hi\s+\[.*?\]/gi, contactName ? 'Hi ' + contactName.split(' ')[0] : 'Hi there');
    return result;
  }

  emailContent.subject = stripPlaceholders(emailContent.subject);
  emailContent.body = stripPlaceholders(emailContent.body);
  emailContent.cta_text = stripPlaceholders(emailContent.cta_text);

  // Build HTML body with line breaks
  const bodyHtml = sanitize(emailContent.body).replace(/\\n/g, '<br>').replace(/\n/g, '<br>');

  const htmlBody = '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">' +
    '<div style="padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;">' +
    '<h1 style="margin:0;font-size:22px;color:#1A1A2E;">' + sanitize(config.senderCompany) + '</h1>' +
    '<p style="margin:8px 0 0;font-size:13px;color:#666;">Business Automation & Lead Generation</p></div>' +
    '<div style="padding:30px 40px;">' +
    '<p style="font-size:15px;line-height:1.6;color:#333;">' + bodyHtml + '</p>' +
    '<p style="font-size:15px;line-height:1.6;color:#333;">' + sanitize(emailContent.cta_text) + '</p>' +
    '<p style="font-size:15px;line-height:1.6;color:#333;margin-top:24px;">Best regards,<br>' +
    '<strong>' + sanitize(config.senderName) + '</strong><br>' +
    '<span style="color:#666;">' + sanitize(config.senderTitle) + '</span><br>' +
    '<span style="color:#666;">' + sanitize(config.senderCompany) + '</span></p></div>' +
    '<div style="padding:20px 40px;background:#f8f8f8;border-top:1px solid #eee;">' +
    '<p style="font-size:11px;color:#999;">This email was sent because your business is publicly listed on Google. If you do not wish to receive further communication, simply reply with the word &quot;unsubscribe&quot; and you will be permanently removed within 24 hours.</p></div></div>';

  return {
    json: {
      to: leadData.email,
      subject: sanitize(emailContent.subject),
      htmlBody: htmlBody,
      leadEmail: leadData.email,
      businessName: businessName,
      contactName: contactName,
      automationFit: leadData.automationFit
    }
  };
});"""

    format_node["parameters"]["jsCode"] = new_format_code
    print("    -> Added stripPlaceholders() safety net function")
    print("    -> Catches [First Name], [Industry], [Business Name], etc.")
    print("    -> Last-resort catch for Hi [anything] pattern")

    return wf


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    print("=" * 60)
    print("LEAD SCRAPER FIX - Remove Bracket Placeholders")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:
        # 1. Fetch current workflow
        print("\n[FETCH] Getting current workflow...")
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        print(f"  Got: {wf['name']} (nodes: {len(wf['nodes'])})")

        # 2. Apply fixes
        print("\n[FIX] Applying placeholder fixes...")
        wf = fix_workflow(wf)

        # 3. Save fixed version locally
        from pathlib import Path
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "lead_scraper_fixed_placeholders.json"
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
    print("\nChanges made:")
    print("  1. Prepare AI Input: prompt now FORBIDS bracket placeholders")
    print("  2. Prepare AI Input: says 'Hi there' when contact name unknown")
    print("  3. Format Email: stripPlaceholders() catches any surviving [Xxx]")
    print("  4. Format Email: last-resort regex replaces Hi [anything] -> Hi there")


if __name__ == "__main__":
    main()

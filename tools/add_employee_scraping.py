"""
Enhance the Lead Scraper to also scrape sub-pages (/about, /team, /staff, etc.)
for employee email addresses and names.

Changes:
1. Add "Contact Name" field to Airtable
2. Update Extract Contact Info to fetch sub-pages and extract employee names
3. Update Upsert to Airtable to include Contact Name
4. Update Score Leads to boost score for personal emails
5. Update Normalize Lead Record to include contactName
6. Update Prepare AI Input to use contact name
7. Update Format Email to use contact name in greeting

Usage:
    python tools/add_employee_scraping.py
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

WORKFLOW_ID = "uq4hnH0YHfhYOOzO"
AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_TABLE_ID = "tblOsuh298hB9WWrA"


# ============================================================
# Enhanced Extract Contact Info - fetches sub-pages too
# ============================================================
EXTRACT_CONTACT_CODE = "\n".join([
    "const inputData = $input.first().json;",
    "const homepageHtml = inputData.data || inputData.body || '';",
    "",
    "// Get original business data from the loop",
    "let original;",
    "try {",
    "  original = $('Loop Over Businesses').item.json;",
    "} catch(e) {",
    "  original = inputData;",
    "}",
    "",
    "const website = (original.website || '').replace(/\\/$/, '');",
    "",
    "// === FETCH SUB-PAGES FOR EMPLOYEE EMAILS ===",
    "const subPaths = ['/about', '/about-us', '/team', '/our-team', '/staff', '/people', '/contact', '/contact-us'];",
    "let allHtml = homepageHtml;",
    "const pageHtmlMap = { homepage: homepageHtml };",
    "",
    "if (website) {",
    "  try {",
    "    const controller = new AbortController();",
    "    const timeout = setTimeout(() => controller.abort(), 30000);",
    "",
    "    const fetches = subPaths.map(path =>",
    "      fetch(website + path, {",
    "        signal: controller.signal,",
    "        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },",
    "        redirect: 'follow'",
    "      })",
    "      .then(async r => {",
    "        if (r.ok) {",
    "          const text = await r.text();",
    "          return { path, html: text };",
    "        }",
    "        return { path, html: '' };",
    "      })",
    "      .catch(() => ({ path, html: '' }))",
    "    );",
    "",
    "    const results = await Promise.allSettled(fetches);",
    "    clearTimeout(timeout);",
    "",
    "    for (const r of results) {",
    "      if (r.status === 'fulfilled' && r.value.html) {",
    "        allHtml += '\\n' + r.value.html;",
    "        pageHtmlMap[r.value.path] = r.value.html;",
    "      }",
    "    }",
    "  } catch(e) {",
    "    // Sub-page fetching failed, continue with homepage only",
    "  }",
    "}",
    "",
    "// === EMAIL EXTRACTION (on combined HTML) ===",
    "const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.(?!jpeg|jpg|png|gif|webp|svg|css|js)[a-zA-Z]{2,}/g;",
    "const rawEmails = allHtml.match(emailRegex) || [];",
    "",
    "const emails = [...new Set(rawEmails.map(e => e.toLowerCase()))].filter(email => {",
    "  const [local, domain] = email.split('@');",
    "  if (!local || !domain || !domain.includes('.')) return false;",
    "  if (local.length < 2) return false;",
    "  if (domain.length < 4) return false;",
    "  const tld = domain.split('.').pop();",
    "  if (tld.length < 2) return false;",
    "  const domainName = domain.split('.')[0];",
    "  if (domainName.length < 2) return false;",
    "  const blacklist = ['example','test','sentry','wixpress','email.com','domain.com',",
    "    'yoursite','noreply','no-reply','unsubscribe','mailer-daemon','postmaster'];",
    "  if (blacklist.some(b => email.includes(b))) return false;",
    "  const domainParts = domain.split('.');",
    "  if (domainParts.some(p => p.length <= 1)) return false;",
    "  if (/^\\d/.test(domainName)) return false;",
    "  return true;",
    "});",
    "",
    "// === NAME EXTRACTION (from team/staff/about pages) ===",
    "// Try to find names associated with emails",
    "const nameMap = {};",
    "",
    "// Strategy 1: Look for mailto: links with nearby text",
    "// Pattern: <a href=\"mailto:john@example.com\">John Smith</a>",
    "const mailtoRegex = /<a[^>]*href=[\"']mailto:([^\"'?]+)[^>]*>([^<]+)<\\/a>/gi;",
    "let match;",
    "while ((match = mailtoRegex.exec(allHtml)) !== null) {",
    "  const email = match[1].toLowerCase().trim();",
    "  const linkText = match[2].trim();",
    "  // If the link text looks like a name (not the email itself)",
    "  if (linkText && !linkText.includes('@') && /^[A-Z][a-z]/.test(linkText)) {",
    "    nameMap[email] = linkText;",
    "  }",
    "}",
    "",
    "// Strategy 2: Look for name patterns near email addresses in the HTML",
    "// Find each email in the HTML and look for names within 500 chars before it",
    "const namePattern = /\\b([A-Z][a-z]{1,15}(?:\\s[A-Z][a-z]{1,15}){1,2})\\b/g;",
    "for (const email of emails) {",
    "  if (nameMap[email]) continue; // Already found via mailto",
    "  const emailIndex = allHtml.toLowerCase().indexOf(email);",
    "  if (emailIndex === -1) continue;",
    "",
    "  // Look in a window around the email (500 chars before, 200 after)",
    "  const start = Math.max(0, emailIndex - 500);",
    "  const end = Math.min(allHtml.length, emailIndex + email.length + 200);",
    "  const context = allHtml.substring(start, end);",
    "",
    "  // Strip HTML tags for cleaner matching",
    "  const textContext = context.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ');",
    "",
    "  // Find name-like patterns (2-3 capitalized words)",
    "  const names = [];",
    "  let nm;",
    "  while ((nm = namePattern.exec(textContext)) !== null) {",
    "    const candidate = nm[1].trim();",
    "    // Filter out common non-name patterns",
    "    const skipWords = ['About Us', 'Our Team', 'Contact Us', 'Get In', 'Read More',",
    "      'Learn More', 'Find Out', 'Follow Us', 'Sign Up', 'Log In', 'Terms Of',",
    "      'Privacy Policy', 'All Rights', 'South Africa', 'Cape Town', 'New York',",
    "      'United States', 'Web Design', 'Social Media', 'Google Maps'];",
    "    if (!skipWords.some(sw => candidate.includes(sw)) && candidate.length > 4) {",
    "      names.push(candidate);",
    "    }",
    "  }",
    "",
    "  // Pick the closest name to the email",
    "  if (names.length > 0) {",
    "    nameMap[email] = names[names.length - 1]; // Last name before email is usually closest",
    "  }",
    "}",
    "",
    "// Strategy 3: Infer name from email prefix (e.g. john.smith@ -> John Smith)",
    "for (const email of emails) {",
    "  if (nameMap[email]) continue;",
    "  const prefix = email.split('@')[0];",
    "  const genericPrefixes = ['info','contact','admin','support','sales','hello',",
    "    'enquiries','office','reception','mail','general','team','help','billing',",
    "    'accounts','hr','marketing','press','media','careers','jobs','apply','recruit'];",
    "  if (genericPrefixes.includes(prefix.toLowerCase())) continue;",
    "",
    "  // Check if prefix looks like a name (has dot or underscore separator)",
    "  if (/^[a-z]+[._][a-z]+$/i.test(prefix)) {",
    "    const parts = prefix.split(/[._]/);",
    "    const inferredName = parts.map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(' ');",
    "    if (inferredName.length >= 5) {",
    "      nameMap[email] = inferredName;",
    "    }",
    "  }",
    "}",
    "",
    "// === CLASSIFY EMAILS ===",
    "const genericPrefixes = ['info','contact','admin','support','sales','hello',",
    "  'enquiries','office','reception','mail','general','team','help','billing',",
    "  'accounts','hr','marketing','press','media','careers','jobs','apply','recruit'];",
    "",
    "const emailData = emails.map(email => {",
    "  const prefix = email.split('@')[0].toLowerCase();",
    "  const isGeneric = genericPrefixes.includes(prefix);",
    "  return {",
    "    email: email,",
    "    contactName: nameMap[email] || '',",
    "    isPersonal: !isGeneric",
    "  };",
    "});",
    "",
    "// === PHONE EXTRACTION ===",
    "const phoneRegex = /(?:\\+\\d{1,3}[\\s.-]?)?\\(?\\d{2,4}\\)?[\\s.-]?\\d{3,4}[\\s.-]?\\d{3,4}/g;",
    "const rawPhones = allHtml.match(phoneRegex) || [];",
    "const phones = [...new Set(rawPhones)].filter(p => p.replace(/\\D/g, '').length >= 7);",
    "",
    "// === SOCIAL MEDIA EXTRACTION ===",
    "const linkedinRegex = /https?:\\/\\/(?:www\\.)?linkedin\\.com\\/(?:company|in)\\/[^\\s\"'<>)]+/gi;",
    "const facebookRegex = /https?:\\/\\/(?:www\\.)?facebook\\.com\\/[^\\s\"'<>)]+/gi;",
    "const instagramRegex = /https?:\\/\\/(?:www\\.)?instagram\\.com\\/[^\\s\"'<>)]+/gi;",
    "",
    "const linkedin = (allHtml.match(linkedinRegex) || [])[0] || '';",
    "const facebook = (allHtml.match(facebookRegex) || [])[0] || '';",
    "const instagram = (allHtml.match(instagramRegex) || [])[0] || '';",
    "",
    "// Count pages scraped",
    "const pagesScraped = Object.keys(pageHtmlMap).filter(k => pageHtmlMap[k].length > 100).length;",
    "",
    "// Return result with email classification",
    "const result = {",
    "  businessName: original.businessName || '',",
    "  website: original.website || '',",
    "  address: original.address || '',",
    "  phone: phones[0] || original.phone || '',",
    "  rating: original.rating || 0,",
    "  industry: original.industry || '',",
    "  location: original.location || '',",
    "  emails: emailData.map(e => e.email),",
    "  emailData: emailData,",
    "  linkedin: linkedin,",
    "  facebook: facebook,",
    "  instagram: instagram,",
    "  pagesScraped: pagesScraped",
    "};",
    "",
    "return { json: result };",
])


# ============================================================
# Updated Score Leads - includes contactName, boosts personal emails
# ============================================================
SCORE_LEADS_CODE = "\n".join([
    "const items = $input.all();",
    "const seen = new Set();",
    "const results = [];",
    "",
    "const highFitIndustries = [",
    "  'real estate', 'law', 'legal', 'attorney', 'medical', 'dental', 'clinic',",
    "  'consulting', 'agency', 'marketing', 'insurance', 'accounting', 'finance',",
    "  'restaurant', 'retail', 'salon', 'fitness', 'gym', 'spa', 'hotel'",
    "];",
    "const mediumFitIndustries = [",
    "  'manufacturing', 'logistics', 'construction', 'contractor', 'plumbing',",
    "  'electrician', 'hvac', 'landscaping', 'cleaning', 'automotive'",
    "];",
    "",
    "for (let i = 0; i < items.length; i++) {",
    "  const item = items[i];",
    "  const email = (item.json.email || item.json.emails || '').toString().toLowerCase().trim();",
    "  if (!email || seen.has(email)) continue;",
    "  seen.add(email);",
    "",
    "  const industry = (item.json.industry || '').toLowerCase();",
    "  const businessName = (item.json.businessName || '').toLowerCase();",
    "",
    "  // Find contact name from emailData if available",
    "  let contactName = '';",
    "  let isPersonal = false;",
    "  const emailData = item.json.emailData || [];",
    "  const matchedData = emailData.find(e => e.email === email);",
    "  if (matchedData) {",
    "    contactName = matchedData.contactName || '';",
    "    isPersonal = matchedData.isPersonal || false;",
    "  }",
    "",
    "  let score = 0;",
    "  if (email) score += 20;",
    "  if (item.json.phone) score += 15;",
    "  if (item.json.businessName) score += 15;",
    "  if (item.json.address) score += 10;",
    "  if (item.json.rating > 0) score += 10;",
    "  if (item.json.linkedin || item.json.facebook || item.json.instagram) score += 10;",
    "  if (item.json.website) score += 10;",
    "  if (item.json.phone && email) score += 10;",
    "",
    "  // BONUS: Personal email (employee) vs generic (info@)",
    "  if (isPersonal) score += 15;",
    "  if (contactName) score += 5;",
    "",
    "  // BONUS: Automation fit",
    "  let automationFit = 'medium';",
    "  let automationBonus = 0;",
    "  const checkInd = (list, text) => list.some(t => text.includes(t));",
    "  if (checkInd(highFitIndustries, industry) || checkInd(highFitIndustries, businessName)) {",
    "    automationFit = 'high'; automationBonus = 20;",
    "  } else if (checkInd(mediumFitIndustries, industry) || checkInd(mediumFitIndustries, businessName)) {",
    "    automationFit = 'medium'; automationBonus = 10;",
    "  } else {",
    "    automationFit = 'low'; automationBonus = 5;",
    "  }",
    "  score += automationBonus;",
    "",
    "  results.push({",
    "    json: {",
    "      businessName: item.json.businessName || '',",
    "      email: email,",
    "      contactName: contactName,",
    "      phone: item.json.phone || '',",
    "      website: item.json.website || '',",
    "      address: item.json.address || '',",
    "      industry: item.json.industry || '',",
    "      location: item.json.location || '',",
    "      rating: item.json.rating || 0,",
    "      linkedin: item.json.linkedin || '',",
    "      facebook: item.json.facebook || '',",
    "      instagram: item.json.instagram || '',",
    "      leadScore: Math.min(score, 100),",
    "      automationFit: automationFit,",
    "      status: 'New',",
    "      source: 'Johannesburg Lead Scraper',",
    "      datescraped: new Date().toISOString().split('T')[0],",
    "      notes: `Automation fit: ${automationFit}. ${contactName ? 'Contact: ' + contactName + '. ' : ''}Target for ${automationFit === 'high' ? 'CRM + follow-up automation' : automationFit === 'medium' ? 'workflow automation' : 'basic lead capture'}`",
    "    },",
    "    pairedItem: { item: i }",
    "  });",
    "}",
    "",
    "return results.length > 0 ? results : [{ json: { _empty: true }, pairedItem: { item: 0 } }];",
])


# ============================================================
# Updated Normalize Lead Record - includes contactName
# ============================================================
NORMALIZE_CODE = "\n".join([
    "const items = $input.all();",
    "return items.map(item => {",
    "  const record = item.json;",
    "  const f = record.fields || record;",
    "  return {",
    "    json: {",
    "      airtableId: record.id || '',",
    "      businessName: f['Business Name'] || '',",
    "      email: f['Email'] || '',",
    "      contactName: f['Contact Name'] || '',",
    "      phone: f['Phone'] || '',",
    "      website: f['Website'] || '',",
    "      address: f['Address'] || '',",
    "      industry: f['Industry'] || '',",
    "      location: f['Location'] || '',",
    "      rating: f['Rating'] || 0,",
    "      linkedin: f['Social - LinkedIn'] || '',",
    "      facebook: f['Social - Facebook'] || '',",
    "      instagram: f['Social - Instagram'] || '',",
    "      leadScore: f['Lead Score'] || 0,",
    "      automationFit: f['Automation Fit'] || '',",
    "      status: f['Status'] || '',",
    "      source: f['Source'] || '',",
    "      datescraped: f['Date Scraped'] || '',",
    "      notes: f['Notes'] || '',",
    "      isNew: !f['Status']",
    "    }",
    "  };",
    "});",
])


# ============================================================
# Updated Prepare AI Input - uses contact name
# ============================================================
PREPARE_AI_CODE = "\n".join([
    "const items = $input.all();",
    "return items.map(item => {",
    "  const leadData = item.json;",
    "  const biz = leadData.businessName || 'your business';",
    "  const ind = leadData.industry || 'your industry';",
    "  const loc = leadData.location || 'the area';",
    "  const web = leadData.website || '';",
    "  const contactName = leadData.contactName || '';",
    "",
    "  const greeting = contactName",
    "    ? `Address the recipient by their first name: ${contactName.split(' ')[0]}`",
    "    : 'Use a friendly but professional greeting (e.g. \"Hi there\" or reference the business name)';",
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
    "- Contact: ${contactName || 'Unknown'}",
    "",
    "YOUR VALUE PROPOSITION:",
    "We help ${ind} businesses automate repetitive tasks to:",
    "1. Close deals 3x faster through automated follow-ups",
    "2. Save 15-20 hours/week eliminating manual data entry",
    "3. Generate 40% more leads with automated marketing",
    "",
    "INSTRUCTIONS:",
    "1. Subject line (max 55 chars): Reference their specific pain point",
    "2. ${greeting}",
    "3. Body (100-130 words): ONE automation opportunity, quick win, ROI",
    "4. CTA: Offer FREE 15-min automation audit",
    "5. Tone: Consultative, NOT salesy",
    "6. NO buzzwords or generic openers",
    "",
    "OUTPUT FORMAT (JSON only, no markdown):",
    "{\"subject\": \"...\", \"body\": \"...\", \"cta_text\": \"Would a quick 15-min call work?\"}`;",
    "",
    "  return {",
    "    json: {",
    "      ...leadData,",
    "      chatInput: prompt",
    "    }",
    "  };",
    "});",
])


# ============================================================
# Updated Format Email - uses contact name in greeting
# ============================================================
FORMAT_EMAIL_CODE = "\n".join([
    "const items = $input.all();",
    "const allLeads = $('Prepare AI Input').all();",
    "const config = $('Search Config').first().json;",
    "",
    "return items.map((item, index) => {",
    "  const input = item.json;",
    "  const leadData = allLeads[index]?.json || {};",
    "  const contactName = leadData.contactName || '';",
    "",
    "  let emailContent;",
    "  try {",
    "    const rawText = input.text || input.response || JSON.stringify(input);",
    "    const jsonMatch = rawText.match(/\\{[\\s\\S]*\\}/);",
    "    emailContent = JSON.parse(jsonMatch[0]);",
    "  } catch (e) {",
    "    const industryName = leadData.industry || 'your industry';",
    "    const greeting = contactName ? `Hi ${contactName.split(' ')[0]}` : `Hi ${leadData.businessName || 'there'}`;",
    "    emailContent = {",
    "      subject: `Automate ${industryName} workflows - save 15h/week`,",
    "      body: `${greeting},\\n\\nI work with ${industryName} businesses in ${leadData.location} to automate time-consuming tasks.\\n\\nMost businesses save 15-20 hours per week after implementing simple automation workflows.\\n\\nWould love to show you a few quick wins - no cost, just value.`,",
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
    "      contactName: contactName,",
    "      automationFit: leadData.automationFit",
    "    }",
    "  };",
    "});",
])


def main():
    config = load_config()
    n8n_api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    n8n_headers = {"X-N8N-API-KEY": n8n_api_key, "Content-Type": "application/json"}

    airtable_token = os.getenv("AIRTABLE_API_TOKEN")
    if not airtable_token:
        print("ERROR: AIRTABLE_API_TOKEN not found in .env")
        sys.exit(1)
    at_headers = {
        "Authorization": f"Bearer {airtable_token}",
        "Content-Type": "application/json"
    }

    with httpx.Client(timeout=60) as client:

        # === STEP 1: Add Contact Name field to Airtable ===
        print("=== Step 1: Add Contact Name field to Airtable ===")
        try:
            resp = client.post(
                f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables/{AIRTABLE_TABLE_ID}/fields",
                headers=at_headers,
                json={
                    "name": "Contact Name",
                    "type": "singleLineText",
                    "description": "Name of the contact person (extracted from website team/about pages)"
                }
            )
            if resp.status_code == 200:
                print("  Added 'Contact Name' field")
            elif resp.status_code == 422 and "already exists" in resp.text.lower():
                print("  'Contact Name' field already exists")
            else:
                print(f"  Airtable response: {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            print(f"  Warning: {e}")

        # === STEP 2: Get and update the workflow ===
        print("\n=== Step 2: Update workflow nodes ===")
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=n8n_headers)
        wf = resp.json()

        for node in wf["nodes"]:
            # Update Extract Contact Info
            if node["name"] == "Extract Contact Info":
                node["parameters"]["jsCode"] = EXTRACT_CONTACT_CODE
                print("  Updated: Extract Contact Info (sub-page scraping + name extraction)")

            # Update Score Leads
            if node["name"] == "Score Leads":
                node["parameters"]["jsCode"] = SCORE_LEADS_CODE
                print("  Updated: Score Leads (personal email bonus + contactName)")

            # Update Upsert to Airtable - add Contact Name field
            if node["name"] == "Upsert to Airtable":
                cols = node["parameters"]["columns"]
                cols["value"]["Contact Name"] = "={{ $json.contactName }}"
                cols["schema"].append({
                    "id": "Contact Name",
                    "type": "string",
                    "display": True,
                    "removed": False,
                    "required": False,
                    "displayName": "Contact Name",
                    "defaultMatch": False,
                    "canBeUsedToMatch": True
                })
                print("  Updated: Upsert to Airtable (added Contact Name field)")

            # Update Normalize Lead Record
            if node["name"] == "Normalize Lead Record":
                node["parameters"]["jsCode"] = NORMALIZE_CODE
                print("  Updated: Normalize Lead Record (includes contactName)")

            # Update Prepare AI Input
            if node["name"] == "Prepare AI Input":
                node["parameters"]["jsCode"] = PREPARE_AI_CODE
                print("  Updated: Prepare AI Input (uses contact name)")

            # Update Format Email
            if node["name"] == "Format Email":
                node["parameters"]["jsCode"] = FORMAT_EMAIL_CODE
                print("  Updated: Format Email (uses contact name in greeting)")

        # === STEP 3: Deploy ===
        print("\n=== Step 3: Deploy ===")
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/deactivate", headers=n8n_headers)

        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
            headers=n8n_headers,
            json=payload
        )
        resp.raise_for_status()
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate", headers=n8n_headers)

        # Verify
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=n8n_headers)
        final = resp.json()
        func_nodes = [n for n in final["nodes"] if "stickyNote" not in n["type"]]
        print(f"\nDeployed. Active: {final.get('active')}")
        print(f"Nodes: {len(func_nodes)} functional")

        print("\nEnhancements deployed:")
        print("  1. Extract Contact Info now scrapes /about, /team, /staff, /people, /contact sub-pages")
        print("  2. Extracts employee names via mailto links, HTML proximity, and email prefix patterns")
        print("  3. Classifies emails as personal vs generic")
        print("  4. Score Leads gives +15 bonus for personal emails, +5 for having a contact name")
        print("  5. Contact Name saved to Airtable")
        print("  6. AI email generation uses contact name for personalized greeting")
        print("  7. Format Email addresses contacts by first name when available")


if __name__ == "__main__":
    main()

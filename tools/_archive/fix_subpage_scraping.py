"""
Fix sub-page scraping by using proper n8n HTTP Request nodes instead of
fetch() inside the Code node (which is sandboxed in n8n Cloud).

Adds 2 new nodes to the scraping loop:
1. Build Sub-Page URLs (Code) - creates multiple items with sub-page URLs
2. Scrape Sub-Pages (HTTP Request) - fetches each sub-page

Then modifies Extract Contact Info to aggregate HTML from all pages.

New connection flow inside the loop:
  Scrape Website -> Rate Limit Wait -> Build Sub-Page URLs -> Scrape Sub-Pages
  -> Extract Contact Info -> Loop Over Businesses

Usage:
    python tools/fix_subpage_scraping.py
"""

import sys
import json
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

WORKFLOW_ID = "uq4hnH0YHfhYOOzO"


# Code node that builds sub-page URLs from the website
BUILD_URLS_CODE = "\n".join([
    "// Get the homepage data and original business info",
    "const inputData = $input.first().json;",
    "const homepageHtml = inputData.data || inputData.body || '';",
    "",
    "let original;",
    "try {",
    "  original = $('Loop Over Businesses').item.json;",
    "} catch(e) {",
    "  original = inputData;",
    "}",
    "",
    "const website = (original.website || '').replace(/\\/$/, '');",
    "if (!website) {",
    "  // No website, just pass through homepage data",
    "  return [{ json: { pageHtml: homepageHtml, isHomepage: true, business: original } }];",
    "}",
    "",
    "// Build sub-page URLs to try",
    "const subPaths = ['/about', '/about-us', '/team', '/our-team', '/staff', '/people', '/contact', '/contact-us'];",
    "",
    "// First item is the homepage HTML (already fetched)",
    "const items = [{ json: { pageHtml: homepageHtml, isHomepage: true, url: website, business: original } }];",
    "",
    "// Add sub-page items (to be fetched by the next HTTP Request node)",
    "for (const path of subPaths) {",
    "  items.push({",
    "    json: {",
    "      pageHtml: '',",
    "      isHomepage: false,",
    "      url: website + path,",
    "      business: original",
    "    }",
    "  });",
    "}",
    "",
    "return items;",
])


# Updated Extract Contact Info that aggregates HTML from multiple pages
EXTRACT_CONTACT_CODE = "\n".join([
    "// Aggregate HTML from all pages (homepage + sub-pages)",
    "const allItems = $input.all();",
    "let allHtml = '';",
    "let pagesScraped = 0;",
    "let business = {};",
    "",
    "for (const item of allItems) {",
    "  const j = item.json;",
    "  // Homepage item has the original HTML in pageHtml",
    "  // Sub-page items have the fetched HTML in data or body",
    "  let html = '';",
    "  if (j.isHomepage) {",
    "    html = j.pageHtml || '';",
    "    business = j.business || {};",
    "  } else {",
    "    html = j.data || j.body || j.pageHtml || '';",
    "  }",
    "  if (html && html.length > 100) {",
    "    allHtml += '\\n' + html;",
    "    pagesScraped++;",
    "  }",
    "}",
    "",
    "// Fallback to get business data from loop",
    "if (!business.website) {",
    "  try { business = $('Loop Over Businesses').item.json; }",
    "  catch(e) { business = allItems[0]?.json?.business || {}; }",
    "}",
    "",
    "// === EMAIL EXTRACTION ===",
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
    "// === NAME EXTRACTION ===",
    "const nameMap = {};",
    "",
    "// Strategy 1: mailto links",
    "const mailtoRegex = /<a[^>]*href=[\"']mailto:([^\"'?]+)[^>]*>([^<]+)<\\/a>/gi;",
    "let match;",
    "while ((match = mailtoRegex.exec(allHtml)) !== null) {",
    "  const email = match[1].toLowerCase().trim();",
    "  const linkText = match[2].trim();",
    "  if (linkText && !linkText.includes('@') && /^[A-Z][a-z]/.test(linkText)) {",
    "    nameMap[email] = linkText;",
    "  }",
    "}",
    "",
    "// Strategy 2: Names near email addresses",
    "const namePattern = /\\b([A-Z][a-z]{1,15}(?:\\s[A-Z][a-z]{1,15}){1,2})\\b/g;",
    "for (const email of emails) {",
    "  if (nameMap[email]) continue;",
    "  const emailIndex = allHtml.toLowerCase().indexOf(email);",
    "  if (emailIndex === -1) continue;",
    "  const start = Math.max(0, emailIndex - 500);",
    "  const end = Math.min(allHtml.length, emailIndex + email.length + 200);",
    "  const context = allHtml.substring(start, end);",
    "  const textContext = context.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ');",
    "  const names = [];",
    "  let nm;",
    "  while ((nm = namePattern.exec(textContext)) !== null) {",
    "    const candidate = nm[1].trim();",
    "    const skipWords = ['About Us', 'Our Team', 'Contact Us', 'Get In', 'Read More',",
    "      'Learn More', 'Find Out', 'Follow Us', 'Sign Up', 'Log In', 'Terms Of',",
    "      'Privacy Policy', 'All Rights', 'South Africa', 'Cape Town', 'New York',",
    "      'United States', 'Web Design', 'Social Media', 'Google Maps'];",
    "    if (!skipWords.some(sw => candidate.includes(sw)) && candidate.length > 4) {",
    "      names.push(candidate);",
    "    }",
    "  }",
    "  if (names.length > 0) nameMap[email] = names[names.length - 1];",
    "}",
    "",
    "// Strategy 3: Infer from email prefix (e.g. john.smith@)",
    "for (const email of emails) {",
    "  if (nameMap[email]) continue;",
    "  const prefix = email.split('@')[0];",
    "  const genericPrefixes = ['info','contact','admin','support','sales','hello',",
    "    'enquiries','office','reception','mail','general','team','help','billing',",
    "    'accounts','hr','marketing','press','media','careers','jobs','apply','recruit'];",
    "  if (genericPrefixes.includes(prefix.toLowerCase())) continue;",
    "  if (/^[a-z]+[._][a-z]+$/i.test(prefix)) {",
    "    const parts = prefix.split(/[._]/);",
    "    const inferredName = parts.map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(' ');",
    "    if (inferredName.length >= 5) nameMap[email] = inferredName;",
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
    "  return { email, contactName: nameMap[email] || '', isPersonal: !isGeneric };",
    "});",
    "",
    "// === PHONE EXTRACTION ===",
    "const phoneRegex = /(?:\\+\\d{1,3}[\\s.-]?)?\\(?\\d{2,4}\\)?[\\s.-]?\\d{3,4}[\\s.-]?\\d{3,4}/g;",
    "const rawPhones = allHtml.match(phoneRegex) || [];",
    "const phones = [...new Set(rawPhones)].filter(p => p.replace(/\\D/g, '').length >= 7);",
    "",
    "// === SOCIAL MEDIA ===",
    "const linkedin = (allHtml.match(/https?:\\/\\/(?:www\\.)?linkedin\\.com\\/(?:company|in)\\/[^\\s\"'<>)]+/gi) || [])[0] || '';",
    "const facebook = (allHtml.match(/https?:\\/\\/(?:www\\.)?facebook\\.com\\/[^\\s\"'<>)]+/gi) || [])[0] || '';",
    "const instagram = (allHtml.match(/https?:\\/\\/(?:www\\.)?instagram\\.com\\/[^\\s\"'<>)]+/gi) || [])[0] || '';",
    "",
    "return { json: {",
    "  businessName: business.businessName || '',",
    "  website: business.website || '',",
    "  address: business.address || '',",
    "  phone: phones[0] || business.phone || '',",
    "  rating: business.rating || 0,",
    "  industry: business.industry || '',",
    "  location: business.location || '',",
    "  emails: emailData.map(e => e.email),",
    "  emailData: emailData,",
    "  linkedin, facebook, instagram,",
    "  pagesScraped",
    "} };",
])


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    with httpx.Client(timeout=60) as client:
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        wf = resp.json()

        # === ADD NEW NODES ===

        # 1. Build Sub-Page URLs (Code node)
        build_urls_id = str(uuid.uuid4())
        build_urls_node = {
            "parameters": {"jsCode": BUILD_URLS_CODE},
            "id": build_urls_id,
            "name": "Build Sub-Page URLs",
            "type": "n8n-nodes-base.code",
            "position": [2260, 600],  # Between Rate Limit Wait and Extract Contact Info
            "typeVersion": 2,
            "alwaysOutputData": True,
            "onError": "continueRegularOutput"
        }

        # 2. Scrape Sub-Pages (HTTP Request node)
        scrape_subpages_id = str(uuid.uuid4())
        scrape_subpages_node = {
            "parameters": {
                "url": "={{ $json.url }}",
                "options": {
                    "allowUnauthorizedCerts": True,
                    "timeout": 8000,
                    "response": {
                        "response": {
                            "fullResponse": True
                        }
                    },
                    "headers": {
                        "parameters": [{
                            "name": "User-Agent",
                            "value": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        }]
                    },
                    "redirect": {
                        "redirect": {
                            "followRedirects": True,
                            "maxRedirects": 3
                        }
                    }
                }
            },
            "id": scrape_subpages_id,
            "name": "Scrape Sub-Pages",
            "type": "n8n-nodes-base.httpRequest",
            "position": [2480, 600],
            "typeVersion": 4.2,
            "onError": "continueRegularOutput",
            "alwaysOutputData": True
        }

        wf["nodes"].append(build_urls_node)
        wf["nodes"].append(scrape_subpages_node)
        print("Added: Build Sub-Page URLs (Code)")
        print("Added: Scrape Sub-Pages (HTTP Request)")

        # === UPDATE EXTRACT CONTACT INFO ===
        for node in wf["nodes"]:
            if node["name"] == "Extract Contact Info":
                node["parameters"]["jsCode"] = EXTRACT_CONTACT_CODE
                # Move position to the right to make room
                node["position"] = [2700, 600]
                print("Updated: Extract Contact Info (aggregates multi-page HTML)")
                break

        # === REWIRE CONNECTIONS ===
        # Current: Rate Limit Wait -> Extract Contact Info -> Loop Over Businesses
        # New: Rate Limit Wait -> Build Sub-Page URLs -> Scrape Sub-Pages -> Extract Contact Info -> Loop

        # The homepage item passes through Build Sub-Page URLs without being re-fetched
        # (isHomepage: true items skip the HTTP Request via the url field already having been fetched)
        # Actually, the HTTP Request will try to re-fetch the homepage too. Let me handle that:
        # The Build Sub-Page URLs node passes homepage HTML in pageHtml field.
        # The Scrape Sub-Pages HTTP Request will fetch the sub-page URLs.
        # For the homepage item (isHomepage: true), the URL is just the website root.
        # The HTTP Request will re-fetch it but that's OK - the Extract node handles merging.
        # Actually, to avoid re-fetching homepage, I should only include sub-page items for the HTTP Request.
        # But then the homepage HTML needs to be passed through somehow.
        #
        # Better approach: Build Sub-Page URLs outputs ALL items including homepage.
        # The HTTP Request node's URL expression {{ $json.url }} will fetch all of them.
        # For the homepage item, this re-fetches it (minor duplication but simpler).
        # Extract Contact Info aggregates all responses.

        wf["connections"]["Rate Limit Wait"] = {
            "main": [[{"node": "Build Sub-Page URLs", "type": "main", "index": 0}]]
        }
        wf["connections"]["Build Sub-Page URLs"] = {
            "main": [[{"node": "Scrape Sub-Pages", "type": "main", "index": 0}]]
        }
        wf["connections"]["Scrape Sub-Pages"] = {
            "main": [[{"node": "Extract Contact Info", "type": "main", "index": 0}]]
        }
        # Extract Contact Info -> Loop (already exists, just confirm)
        wf["connections"]["Extract Contact Info"] = {
            "main": [[{"node": "Loop Over Businesses", "type": "main", "index": 0}]]
        }

        print("Rewired: Rate Limit Wait -> Build Sub-Page URLs -> Scrape Sub-Pages -> Extract Contact Info -> Loop")

        # === DEPLOY ===
        print("\nDeploying...")
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/deactivate", headers=headers)

        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate", headers=headers)

        # Verify
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        final = resp.json()
        func_nodes = [n for n in final["nodes"] if "stickyNote" not in n["type"]]
        print(f"\nDeployed. Active: {final.get('active')}")
        print(f"Nodes: {len(func_nodes)} functional")

        print("\nScraping loop now:")
        print("  Loop -> Scrape Website (homepage) -> Rate Limit (2s)")
        print("       -> Build Sub-Page URLs (creates 9 items: homepage + 8 sub-pages)")
        print("       -> Scrape Sub-Pages (HTTP Request, fetches each URL)")
        print("       -> Extract Contact Info (aggregates all HTML, extracts emails + names)")
        print("       -> Back to Loop")


if __name__ == "__main__":
    main()

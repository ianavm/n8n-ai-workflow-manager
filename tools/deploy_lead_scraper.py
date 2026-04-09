"""
Lead Scraper & CRM Automation - Workflow Builder & Deployer

Builds the optimized workflow JSON and deploys it to n8n.
Replaces workflow uq4hnH0YHfhYOOzO with the enhanced version.

Usage:
    python tools/deploy_lead_scraper.py build     # Build JSON only
    python tools/deploy_lead_scraper.py deploy    # Build + Deploy
    python tools/deploy_lead_scraper.py activate  # Build + Deploy + Activate
"""

import json
import sys
import uuid
from pathlib import Path
from datetime import datetime


# ── Configuration ──────────────────────────────────────────────

WORKFLOW_ID = "uq4hnH0YHfhYOOzO"
WORKFLOW_NAME = "Lead Generating Web Scraper & CRM Automation"

# Credentials (from n8n instance)
CRED_GOOGLE_SHEETS = {"id": "OkpDXxwI8WcUJp4P", "name": "Google Sheets AVM Tutorial"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}

# Airtable IDs (Dedicated Lead Scraper Base)
AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_TABLE_ID = "tblOsuh298hB9WWrA"

# Google Sheet
SHEET_DOC_ID = "1E9_OSvO6F37iG9wh_gaetPT3IzuwdeSNbomIPXzKu94"


def uid():
    return str(uuid.uuid4())


# ── Node Builders ──────────────────────────────────────────────

def build_nodes():
    """Build all workflow nodes."""
    nodes = []

    # ── STAGE 1: Triggers & Config ──

    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "weeks", "triggerAtDay": [1], "triggerAtHour": 9}]
            }
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 300],
        "typeVersion": 1.2
    })

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 500],
        "typeVersion": 1
    })

    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "searchQuery", "value": "dentists", "type": "string"},
                    {"id": uid(), "name": "location", "value": "Johannesburg", "type": "string"},
                    {"id": uid(), "name": "maxResults", "value": "50", "type": "number"},
                    {"id": uid(), "name": "senderName", "value": "Ian Immelman", "type": "string"},
                    {"id": uid(), "name": "senderCompany", "value": "AnyVision Media", "type": "string"},
                    {"id": uid(), "name": "senderTitle", "value": "Director", "type": "string"},
                    {"id": uid(), "name": "senderEmail", "value": "ian@anyvisionmedia.com", "type": "string"}
                ]
            }
        },
        "id": uid(),
        "name": "Search Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 400],
        "typeVersion": 3.4
    })

    # ── STAGE 2: Google Maps Scraping ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const config = $input.first().json;\n"
                "const query = encodeURIComponent(config.location + ' ' + config.searchQuery);\n"
                "const url = 'https://www.google.com/maps/search/' + query;\n"
                "return {\n"
                "  json: {\n"
                "    ...config,\n"
                "    mapsUrl: url\n"
                "  }\n"
                "};"
            )
        },
        "id": uid(),
        "name": "Build Maps URL",
        "type": "n8n-nodes-base.code",
        "position": [660, 400],
        "typeVersion": 2
    })

    nodes.append({
        "parameters": {
            "url": "={{ $json.mapsUrl }}",
            "options": {
                "allowUnauthorizedCerts": True,
                "response": {
                    "response": {
                        "fullResponse": True
                    }
                }
            }
        },
        "id": uid(),
        "name": "Scrape Google Maps",
        "type": "n8n-nodes-base.httpRequest",
        "position": [880, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput"
    })

    nodes.append({
        "parameters": {
            "jsCode": (
                "const html = $input.first().json.data || '';\n"
                "const config = $('Search Config').first().json;\n"
                "\n"
                "// Extract website URLs from Google Maps HTML\n"
                "const urlRegex = /https?:\\/\\/[^\\/\\s\"'>]+/g;\n"
                "const allUrls = html.match(urlRegex) || [];\n"
                "\n"
                "// Filter out Google/system domains\n"
                "const blockedDomains = ['google', 'gstatic', 'googleapis', 'schema', 'ggpht', 'youtube', 'goo.gl'];\n"
                "const validUrls = [...new Set(allUrls)].filter(url => {\n"
                "  const lower = url.toLowerCase();\n"
                "  return !blockedDomains.some(d => lower.includes(d));\n"
                "});\n"
                "\n"
                "// Try to extract business names from Maps HTML\n"
                "// Google Maps embeds business data in various patterns\n"
                "const nameRegex = /\\[\"([^\"]{3,60})\"(?:,null){0,3},\"https?:\\/\\//g;\n"
                "const names = [];\n"
                "let nameMatch;\n"
                "while ((nameMatch = nameRegex.exec(html)) !== null) {\n"
                "  names.push(nameMatch[1]);\n"
                "}\n"
                "\n"
                "// Try to extract addresses\n"
                "const addressRegex = /\\[\"(\\d+[^\"]{5,80}(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Blvd|Way|Lane|Ln|Ct|Pl)[^\"]{0,40})\"/gi;\n"
                "const addresses = [];\n"
                "let addrMatch;\n"
                "while ((addrMatch = addressRegex.exec(html)) !== null) {\n"
                "  addresses.push(addrMatch[1]);\n"
                "}\n"
                "\n"
                "// Try to extract phone numbers from Maps data\n"
                "const phoneRegex = /(?:\\+\\d{1,3}[\\s.-]?)?\\(?\\d{2,4}\\)?[\\s.-]?\\d{3,4}[\\s.-]?\\d{3,4}/g;\n"
                "const phones = [...new Set((html.match(phoneRegex) || []))];\n"
                "\n"
                "// Try to extract ratings\n"
                "const ratingRegex = /\\[(\\d\\.\\d),\"\\d+ review/g;\n"
                "const ratings = [];\n"
                "let rateMatch;\n"
                "while ((rateMatch = ratingRegex.exec(html)) !== null) {\n"
                "  ratings.push(parseFloat(rateMatch[1]));\n"
                "}\n"
                "\n"
                "// Build business objects - match URLs with any extracted metadata\n"
                "const maxResults = parseInt(config.maxResults) || 50;\n"
                "const businesses = validUrls.slice(0, maxResults).map((url, i) => ({\n"
                "  businessName: names[i] || '',\n"
                "  website: url.split('/').slice(0, 3).join('/'),\n"
                "  address: addresses[i] || '',\n"
                "  phone: phones[i] || '',\n"
                "  rating: ratings[i] || 0,\n"
                "  industry: config.searchQuery,\n"
                "  location: config.location\n"
                "}));\n"
                "\n"
                "if (businesses.length === 0) {\n"
                "  return [{ json: { error: 'No businesses found', urlCount: allUrls.length } }];\n"
                "}\n"
                "\n"
                "return businesses.map(b => ({ json: b }));"
            )
        },
        "id": uid(),
        "name": "Extract Business Data",
        "type": "n8n-nodes-base.code",
        "position": [1100, 400],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput"
    })

    # ── STAGE 3: Website Scraping & Enrichment ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "combinator": "and",
                "conditions": [
                    {"id": uid(), "operator": {"type": "string", "operation": "notContains"}, "leftValue": "={{ $json.website }}", "rightValue": "google"},
                    {"id": uid(), "operator": {"type": "string", "operation": "notContains"}, "leftValue": "={{ $json.website }}", "rightValue": "gstatic"},
                    {"id": uid(), "operator": {"type": "string", "operation": "exists", "singleValue": True}, "leftValue": "={{ $json.website }}", "rightValue": ""}
                ]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Filter Valid URLs",
        "type": "n8n-nodes-base.filter",
        "position": [1320, 400],
        "typeVersion": 2.2
    })

    nodes.append({
        "parameters": {
            "compareValue": "={{ $json.website }}",
            "options": {}
        },
        "id": uid(),
        "name": "Remove Duplicate URLs",
        "type": "n8n-nodes-base.removeDuplicates",
        "position": [1520, 400],
        "typeVersion": 2
    })

    nodes.append({
        "parameters": {"options": {}},
        "id": uid(),
        "name": "Loop Over Businesses",
        "type": "n8n-nodes-base.splitInBatches",
        "position": [1720, 400],
        "typeVersion": 3
    })

    nodes.append({
        "parameters": {
            "url": "={{ $json.website }}",
            "options": {
                "allowUnauthorizedCerts": True,
                "timeout": 10000,
                "response": {
                    "response": {
                        "fullResponse": True
                    }
                }
            }
        },
        "id": uid(),
        "name": "Scrape Website",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1920, 600],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput"
    })

    nodes.append({
        "parameters": {"amount": 2},
        "id": uid(),
        "name": "Rate Limit Wait",
        "type": "n8n-nodes-base.wait",
        "position": [2140, 600],
        "webhookId": uid(),
        "typeVersion": 1.1
    })

    nodes.append({
        "parameters": {
            "jsCode": (
                "const html = $input.first().json.data || $input.first().json.body || '';\n"
                "const original = $('Loop Over Businesses').item.json;\n"
                "\n"
                "// Email extraction (exclude image extensions)\n"
                "const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.(?!jpeg|jpg|png|gif|webp|svg|css|js)[a-zA-Z]{2,}/g;\n"
                "const rawEmails = html.match(emailRegex) || [];\n"
                "const emails = [...new Set(rawEmails.map(e => e.toLowerCase()))];\n"
                "\n"
                "// Phone extraction\n"
                "const phoneRegex = /(?:\\+\\d{1,3}[\\s.-]?)?\\(?\\d{2,4}\\)?[\\s.-]?\\d{3,4}[\\s.-]?\\d{3,4}/g;\n"
                "const rawPhones = html.match(phoneRegex) || [];\n"
                "const phones = [...new Set(rawPhones)].filter(p => p.replace(/\\D/g, '').length >= 7);\n"
                "\n"
                "// Social media extraction\n"
                "const linkedinRegex = /https?:\\/\\/(?:www\\.)?linkedin\\.com\\/(?:company|in)\\/[^\\s\"'<>)]+/gi;\n"
                "const facebookRegex = /https?:\\/\\/(?:www\\.)?facebook\\.com\\/[^\\s\"'<>)]+/gi;\n"
                "const instagramRegex = /https?:\\/\\/(?:www\\.)?instagram\\.com\\/[^\\s\"'<>)]+/gi;\n"
                "\n"
                "const linkedin = (html.match(linkedinRegex) || [])[0] || '';\n"
                "const facebook = (html.match(facebookRegex) || [])[0] || '';\n"
                "const instagram = (html.match(instagramRegex) || [])[0] || '';\n"
                "\n"
                "// Merge with original business data\n"
                "const result = {\n"
                "  businessName: original.businessName || '',\n"
                "  website: original.website || '',\n"
                "  address: original.address || '',\n"
                "  phone: phones[0] || original.phone || '',\n"
                "  rating: original.rating || 0,\n"
                "  industry: original.industry || '',\n"
                "  location: original.location || '',\n"
                "  emails: emails,\n"
                "  linkedin: linkedin,\n"
                "  facebook: facebook,\n"
                "  instagram: instagram\n"
                "};\n"
                "\n"
                "return { json: result };"
            )
        },
        "id": uid(),
        "name": "Extract Contact Info",
        "type": "n8n-nodes-base.code",
        "position": [2360, 600],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput"
    })

    # ── STAGE 4: Data Processing & Scoring ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "combinator": "and",
                "conditions": [
                    {"id": uid(), "operator": {"type": "array", "operation": "notEmpty", "singleValue": True}, "leftValue": "={{ $json.emails }}", "rightValue": ""}
                ]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Filter Has Email",
        "type": "n8n-nodes-base.filter",
        "position": [1920, 260],
        "typeVersion": 2.2
    })

    nodes.append({
        "parameters": {
            "fieldToSplitOut": "emails",
            "options": {}
        },
        "id": uid(),
        "name": "Split Emails",
        "type": "n8n-nodes-base.splitOut",
        "position": [2140, 260],
        "typeVersion": 1
    })

    nodes.append({
        "parameters": {
            "jsCode": (
                "const items = $input.all();\n"
                "const seen = new Set();\n"
                "const results = [];\n"
                "\n"
                "for (const item of items) {\n"
                "  const email = (item.json.emails || '').toString().toLowerCase().trim();\n"
                "  if (!email || seen.has(email)) continue;\n"
                "  seen.add(email);\n"
                "\n"
                "  // Calculate lead score (0-100)\n"
                "  let score = 0;\n"
                "  if (email) score += 20;\n"
                "  if (item.json.phone) score += 15;\n"
                "  if (item.json.businessName) score += 15;\n"
                "  if (item.json.address) score += 10;\n"
                "  if (item.json.rating > 0) score += 10;\n"
                "  if (item.json.linkedin || item.json.facebook || item.json.instagram) score += 10;\n"
                "  if (item.json.website) score += 10;\n"
                "  if (item.json.phone && email) score += 10; // bonus for multiple contact methods\n"
                "\n"
                "  results.push({\n"
                "    json: {\n"
                "      ...item.json,\n"
                "      email: email,\n"
                "      leadScore: score,\n"
                "      status: 'New',\n"
                "      source: 'Google Maps Scraper',\n"
                "      datescraped: new Date().toISOString().split('T')[0]\n"
                "    }\n"
                "  });\n"
                "}\n"
                "\n"
                "return results.length > 0 ? results : [{ json: { _empty: true } }];"
            )
        },
        "id": uid(),
        "name": "Score Leads",
        "type": "n8n-nodes-base.code",
        "position": [2360, 260],
        "typeVersion": 2,
        "alwaysOutputData": True
    })

    # ── STAGE 5: CRM Storage (Dual Write) ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID, "cachedResultName": "n8n Workflows"},
            "table": {"__rl": True, "mode": "list", "value": AIRTABLE_TABLE_ID, "cachedResultName": "Leads"},
            "filterByFormula": "=({Email} = \"{{ $json.email }}\")"
        },
        "id": uid(),
        "name": "Check Airtable Exists",
        "type": "n8n-nodes-base.airtable",
        "position": [2580, 260],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "alwaysOutputData": True,
        "credentials": {
            "airtableTokenApi": CRED_AIRTABLE
        }
    })

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "combinator": "and",
                "conditions": [
                    {"id": uid(), "operator": {"type": "object", "operation": "empty", "singleValue": True}, "leftValue": "={{ $json }}", "rightValue": ""}
                ]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Is New Lead?",
        "type": "n8n-nodes-base.if",
        "position": [2800, 260],
        "typeVersion": 2.2
    })

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID, "cachedResultName": "n8n Workflows"},
            "table": {"__rl": True, "mode": "list", "value": AIRTABLE_TABLE_ID, "cachedResultName": "Leads"},
            "columns": {
                "value": {
                    "Business Name": "={{ $('Score Leads').item.json.businessName }}",
                    "Email": "={{ $('Score Leads').item.json.email }}",
                    "Phone": "={{ $('Score Leads').item.json.phone }}",
                    "Website": "={{ $('Score Leads').item.json.website }}",
                    "Address": "={{ $('Score Leads').item.json.address }}",
                    "Industry": "={{ $('Score Leads').item.json.industry }}",
                    "Location": "={{ $('Score Leads').item.json.location }}",
                    "Rating": "={{ $('Score Leads').item.json.rating }}",
                    "Social - LinkedIn": "={{ $('Score Leads').item.json.linkedin }}",
                    "Social - Facebook": "={{ $('Score Leads').item.json.facebook }}",
                    "Social - Instagram": "={{ $('Score Leads').item.json.instagram }}",
                    "Lead Score": "={{ $('Score Leads').item.json.leadScore }}",
                    "Status": "New",
                    "Source": "Google Maps Scraper",
                    "Date Scraped": "={{ $('Score Leads').item.json.datescraped }}"
                },
                "schema": [
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
                    {"id": "Status", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Status", "defaultMatch": False, "canBeUsedToMatch": True},
                    {"id": "Source", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Source", "defaultMatch": False, "canBeUsedToMatch": True},
                    {"id": "Date Scraped", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Date Scraped", "defaultMatch": False, "canBeUsedToMatch": True}
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Email"]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Create in Airtable",
        "type": "n8n-nodes-base.airtable",
        "position": [3040, 160],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {
            "airtableTokenApi": CRED_AIRTABLE
        }
    })

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID, "cachedResultName": "n8n Workflows"},
            "table": {"__rl": True, "mode": "list", "value": AIRTABLE_TABLE_ID, "cachedResultName": "Leads"},
            "columns": {
                "value": {
                    "Phone": "={{ $('Score Leads').item.json.phone }}",
                    "Social - LinkedIn": "={{ $('Score Leads').item.json.linkedin }}",
                    "Social - Facebook": "={{ $('Score Leads').item.json.facebook }}",
                    "Social - Instagram": "={{ $('Score Leads').item.json.instagram }}",
                    "Lead Score": "={{ $('Score Leads').item.json.leadScore }}"
                },
                "schema": [
                    {"id": "Phone", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Phone", "defaultMatch": False, "canBeUsedToMatch": True},
                    {"id": "Social - LinkedIn", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Social - LinkedIn", "defaultMatch": False, "canBeUsedToMatch": True},
                    {"id": "Social - Facebook", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Social - Facebook", "defaultMatch": False, "canBeUsedToMatch": True},
                    {"id": "Social - Instagram", "type": "string", "display": True, "removed": False, "required": False, "displayName": "Social - Instagram", "defaultMatch": False, "canBeUsedToMatch": True},
                    {"id": "Lead Score", "type": "number", "display": True, "removed": False, "required": False, "displayName": "Lead Score", "defaultMatch": False, "canBeUsedToMatch": True}
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Email"]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Update in Airtable",
        "type": "n8n-nodes-base.airtable",
        "position": [3040, 380],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {
            "airtableTokenApi": CRED_AIRTABLE
        }
    })

    nodes.append({
        "parameters": {
            "operation": "append",
            "documentId": {
                "__rl": True,
                "value": SHEET_DOC_ID,
                "mode": "list",
                "cachedResultName": "LEAD GEN EMAILSCRAPER",
                "cachedResultUrl": f"https://docs.google.com/spreadsheets/d/{SHEET_DOC_ID}/edit?usp=drivesdk"
            },
            "sheetName": {
                "__rl": True,
                "value": "gid=0",
                "mode": "list",
                "cachedResultName": "Sheet1",
                "cachedResultUrl": f"https://docs.google.com/spreadsheets/d/{SHEET_DOC_ID}/edit#gid=0"
            },
            "columns": {
                "value": {
                    "Business Name": "={{ $('Score Leads').item.json.businessName }}",
                    "Email": "={{ $('Score Leads').item.json.email }}",
                    "Phone": "={{ $('Score Leads').item.json.phone }}",
                    "Website": "={{ $('Score Leads').item.json.website }}",
                    "Address": "={{ $('Score Leads').item.json.address }}",
                    "Industry": "={{ $('Score Leads').item.json.industry }}",
                    "Location": "={{ $('Score Leads').item.json.location }}",
                    "Rating": "={{ $('Score Leads').item.json.rating }}",
                    "LinkedIn": "={{ $('Score Leads').item.json.linkedin }}",
                    "Facebook": "={{ $('Score Leads').item.json.facebook }}",
                    "Instagram": "={{ $('Score Leads').item.json.instagram }}",
                    "Lead Score": "={{ $('Score Leads').item.json.leadScore }}",
                    "Status": "={{ $('Score Leads').item.json.status }}",
                    "Date Scraped": "={{ $('Score Leads').item.json.datescraped }}"
                },
                "schema": [
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
                    {"id": "Date Scraped", "type": "string", "display": True, "displayName": "Date Scraped"}
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Email"]
            },
            "options": {"useAppend": True}
        },
        "id": uid(),
        "name": "Append to Sheets",
        "type": "n8n-nodes-base.googleSheets",
        "position": [3280, 260],
        "typeVersion": 4.5,
        "onError": "continueRegularOutput",
        "credentials": {
            "googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS
        }
    })

    # ── STAGE 6: Email Outreach Pipeline ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "strict"},
                "combinator": "and",
                "conditions": [
                    {"id": uid(), "operator": {"type": "string", "operation": "exists", "singleValue": True}, "leftValue": "={{ $json.id }}", "rightValue": ""}
                ]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Filter New Leads",
        "type": "n8n-nodes-base.filter",
        "position": [3500, 160],
        "typeVersion": 2.2
    })

    nodes.append({
        "parameters": {"amount": 30},
        "id": uid(),
        "name": "Rate Limit Emails",
        "type": "n8n-nodes-base.wait",
        "position": [3700, 160],
        "webhookId": uid(),
        "typeVersion": 1.1
    })

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "{\n  \"model\": \"anthropic/claude-sonnet-4-20250514\",\n  \"max_tokens\": 500,\n  \"messages\": [\n    {\n      \"role\": \"system\",\n      \"content\": \"You are a professional business development writer. Write a short, personalized cold outreach email to a business owner.\\n\\nINSTRUCTIONS:\\n1. Write a subject line (max 50 chars) specific to their business type\\n2. Write a personalized opening referencing their industry\\n3. Write 2-3 sentences with a clear value proposition\\n4. End with a low-commitment CTA\\n5. Keep body under 150 words\\n6. Professional, friendly tone - NOT salesy\\n7. No exclamation marks excess\\n\\nOUTPUT FORMAT (JSON only):\\n{\\\"subject\\\": \\\"...\\\", \\\"body\\\": \\\"...\\\", \\\"cta_text\\\": \\\"...\\\"}\"\n    },\n    {\n      \"role\": \"user\",\n      \"content\": \"Business: {{ $('Score Leads').item.json.businessName }}\\nIndustry: {{ $('Score Leads').item.json.industry }}\\nLocation: {{ $('Score Leads').item.json.location }}\\nWebsite: {{ $('Score Leads').item.json.website }}\"\n    }\n  ]\n}",
            "options": {}
        },
        "id": uid(),
        "name": "Generate Personalized Email",
        "type": "n8n-nodes-base.httpRequest",
        "position": [3920, 160],
        "typeVersion": 4.2,
        "credentials": {
            "httpHeaderAuth": CRED_OPENROUTER
        },
        "onError": "continueRegularOutput"
    })

    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const leadData = $('Score Leads').item.json;\n"
                "const config = $('Search Config').first().json;\n"
                "\n"
                "// Parse AI response\n"
                "let emailContent;\n"
                "try {\n"
                "  const content = input.choices[0].message.content;\n"
                "  // Try to parse JSON from the response\n"
                "  const jsonMatch = content.match(/\\{[\\s\\S]*\\}/);\n"
                "  emailContent = JSON.parse(jsonMatch[0]);\n"
                "} catch (e) {\n"
                "  // Fallback template\n"
                "  emailContent = {\n"
                "    subject: `Partnership opportunity for ${leadData.businessName || 'your business'}`,\n"
                "    body: `I noticed ${leadData.businessName || 'your business'} in ${leadData.location} and wanted to reach out about a potential collaboration that could benefit your ${leadData.industry} practice.`,\n"
                "    cta_text: 'Would a brief 10-minute call this week work to explore this?'\n"
                "  };\n"
                "}\n"
                "\n"
                "// Build HTML email from template\n"
                "const htmlBody = `\n"
                "<div style=\"font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;\">\n"
                "  <div style=\"padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;\">\n"
                "    <h1 style=\"margin:0;font-size:22px;color:#1A1A2E;\">${config.senderCompany}</h1>\n"
                "  </div>\n"
                "  <div style=\"padding:30px 40px;\">\n"
                "    <p style=\"font-size:15px;line-height:1.6;color:#333;\">${emailContent.body}</p>\n"
                "    <p style=\"font-size:15px;line-height:1.6;color:#333;\">${emailContent.cta_text}</p>\n"
                "    <p style=\"font-size:15px;line-height:1.6;color:#333;margin-top:24px;\">\n"
                "      Best regards,<br><strong>${config.senderName}</strong><br>\n"
                "      <span style=\"color:#666;\">${config.senderTitle}</span><br>\n"
                "      <span style=\"color:#666;\">${config.senderCompany}</span>\n"
                "    </p>\n"
                "  </div>\n"
                "  <div style=\"padding:20px 40px;background:#f8f8f8;border-top:1px solid #eee;\">\n"
                "    <p style=\"font-size:11px;color:#999;\">You received this because your business was listed publicly on Google Maps. Reply \\\"unsubscribe\\\" to be removed.</p>\n"
                "  </div>\n"
                "</div>`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    to: leadData.email,\n"
                "    subject: emailContent.subject,\n"
                "    htmlBody: htmlBody,\n"
                "    leadEmail: leadData.email,\n"
                "    businessName: leadData.businessName\n"
                "  }\n"
                "};"
            )
        },
        "id": uid(),
        "name": "Format Email",
        "type": "n8n-nodes-base.code",
        "position": [4140, 160],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput"
    })

    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.to }}",
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.htmlBody }}",
            "options": {}
        },
        "id": uid(),
        "name": "Send Outreach Email",
        "type": "n8n-nodes-base.gmail",
        "position": [4360, 160],
        "typeVersion": 2.1,
        "credentials": {
            "gmailOAuth2": CRED_GMAIL
        },
        "onError": "continueRegularOutput"
    })

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID, "cachedResultName": "n8n Workflows"},
            "table": {"__rl": True, "mode": "list", "value": AIRTABLE_TABLE_ID, "cachedResultName": "Leads"},
            "columns": {
                "value": {
                    "Status": "Email Sent",
                    "Email Sent Date": "={{ new Date().toISOString().split('T')[0] }}",
                    "Notes": "={{ $('Format Email').item.json.subject }}"
                },
                "schema": [
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Email Sent Date", "type": "string", "display": True, "displayName": "Email Sent Date"},
                    {"id": "Notes", "type": "string", "display": True, "displayName": "Notes"}
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Email"]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Update Lead Status",
        "type": "n8n-nodes-base.airtable",
        "position": [4580, 160],
        "typeVersion": 2.1,
        "credentials": {
            "airtableTokenApi": CRED_AIRTABLE
        },
        "onError": "continueRegularOutput"
    })

    # ── STAGE 7: Notifications & Error Handling ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const items = $('Score Leads').all();\n"
                "const config = $('Search Config').first().json;\n"
                "\n"
                "const totalLeads = items.filter(i => !i.json._empty).length;\n"
                "const avgScore = totalLeads > 0\n"
                "  ? Math.round(items.reduce((sum, i) => sum + (i.json.leadScore || 0), 0) / totalLeads)\n"
                "  : 0;\n"
                "\n"
                "const now = new Date().toLocaleString('en-ZA', { timeZone: 'Africa/Johannesburg' });\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    subject: `Lead Scraper Complete: ${totalLeads} leads found`,\n"
                "    body: [\n"
                "      `<h2>Lead Scraper Run Complete</h2>`,\n"
                "      `<p><strong>Date:</strong> ${now}</p>`,\n"
                "      `<p><strong>Search:</strong> ${config.searchQuery} in ${config.location}</p>`,\n"
                "      `<hr>`,\n"
                "      `<p><strong>Total Leads Found:</strong> ${totalLeads}</p>`,\n"
                "      `<p><strong>Average Lead Score:</strong> ${avgScore}/100</p>`,\n"
                "      `<hr>`,\n"
                "      `<p>Check your <a href=\"https://airtable.com/${'" + AIRTABLE_BASE_ID + "'\">Airtable CRM</a> for details.</p>`\n"
                "    ].join('\\n')\n"
                "  }\n"
                "};"
            )
        },
        "id": uid(),
        "name": "Aggregate Results",
        "type": "n8n-nodes-base.code",
        "position": [3500, 460],
        "typeVersion": 2,
        "alwaysOutputData": True
    })

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.body }}",
            "options": {}
        },
        "id": uid(),
        "name": "Send Summary",
        "type": "n8n-nodes-base.gmail",
        "position": [3720, 460],
        "typeVersion": 2.1,
        "credentials": {
            "gmailOAuth2": CRED_GMAIL
        },
        "onError": "continueRegularOutput"
    })

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 740],
        "typeVersion": 1
    })

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "Lead Scraper ERROR - {{ $json.workflow.name }}",
            "emailType": "html",
            "message": "=<h2>Workflow Error Alert</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {}
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 740],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {
            "gmailOAuth2": CRED_GMAIL
        }
    })

    # ── STICKY NOTES (Documentation) ──

    notes = [
        {
            "content": "## STAGE 1: Triggers & Configuration\n\n**Schedule:** Runs weekly on Monday 9AM\n**Manual:** Click 'Test workflow' for ad-hoc runs\n**Config:** Set your search query, location, and sender details",
            "position": [160, 140], "width": 340, "height": 140
        },
        {
            "content": "## STAGE 2: Google Maps Scraping\n\nScrapes Google Maps HTML for business listings.\nExtracts names, websites, addresses, phones, ratings.",
            "position": [620, 240], "width": 340, "height": 120
        },
        {
            "content": "## STAGE 3: Website Scraping & Enrichment\n\nVisits each business website with rate limiting.\nExtracts emails, phone numbers, and social media links.",
            "position": [1280, 520], "width": 360, "height": 120
        },
        {
            "content": "## STAGE 4: Scoring & Dedup\n\nScores leads 0-100 based on data completeness.\nDeduplicates by email address.",
            "position": [1880, 120], "width": 340, "height": 100
        },
        {
            "content": "## STAGE 5: CRM Storage\n\n**Airtable** (primary): Creates new or updates existing records\n**Google Sheets** (mirror): Appends all leads for easy sharing",
            "position": [2540, 80], "width": 380, "height": 100
        },
        {
            "content": "## STAGE 6: AI Email Outreach\n\nAI generates personalized cold email per lead.\nSent via Gmail with branded HTML template.\nAirtable status updated to 'Email Sent'.",
            "position": [3460, 40], "width": 380, "height": 100
        },
        {
            "content": "## STAGE 7: Notifications\n\nSummary email after each run.\nError alerts on failures.",
            "position": [3460, 380], "width": 340, "height": 80
        }
    ]

    for i, note in enumerate(notes):
        nodes.append({
            "parameters": {
                "content": note["content"],
                "height": note.get("height", 140),
                "width": note.get("width", 340)
            },
            "id": f"sticky-{i+1}",
            "type": "n8n-nodes-base.stickyNote",
            "position": note["position"],
            "typeVersion": 1,
            "name": f"Note {i+1}"
        })

    return nodes


def build_connections():
    """Build all node connections."""
    return {
        # Triggers → Config
        "Schedule Trigger": {
            "main": [[{"node": "Search Config", "type": "main", "index": 0}]]
        },
        "Manual Trigger": {
            "main": [[{"node": "Search Config", "type": "main", "index": 0}]]
        },
        # Config → Scraping
        "Search Config": {
            "main": [[{"node": "Build Maps URL", "type": "main", "index": 0}]]
        },
        "Build Maps URL": {
            "main": [[{"node": "Scrape Google Maps", "type": "main", "index": 0}]]
        },
        "Scrape Google Maps": {
            "main": [[{"node": "Extract Business Data", "type": "main", "index": 0}]]
        },
        "Extract Business Data": {
            "main": [[{"node": "Filter Valid URLs", "type": "main", "index": 0}]]
        },
        # Filtering → Loop
        "Filter Valid URLs": {
            "main": [[{"node": "Remove Duplicate URLs", "type": "main", "index": 0}]]
        },
        "Remove Duplicate URLs": {
            "main": [[{"node": "Loop Over Businesses", "type": "main", "index": 0}]]
        },
        # Loop: output 0 = done → post-processing, output 1 = loop → scrape
        "Loop Over Businesses": {
            "main": [
                [{"node": "Filter Has Email", "type": "main", "index": 0}],
                [{"node": "Scrape Website", "type": "main", "index": 0}]
            ]
        },
        # Loop body
        "Scrape Website": {
            "main": [[{"node": "Rate Limit Wait", "type": "main", "index": 0}]]
        },
        "Rate Limit Wait": {
            "main": [[{"node": "Extract Contact Info", "type": "main", "index": 0}]]
        },
        "Extract Contact Info": {
            "main": [[{"node": "Loop Over Businesses", "type": "main", "index": 0}]]
        },
        # Post-loop processing
        "Filter Has Email": {
            "main": [[{"node": "Split Emails", "type": "main", "index": 0}]]
        },
        "Split Emails": {
            "main": [[{"node": "Score Leads", "type": "main", "index": 0}]]
        },
        "Score Leads": {
            "main": [[{"node": "Check Airtable Exists", "type": "main", "index": 0}]]
        },
        # CRM branching
        "Check Airtable Exists": {
            "main": [[{"node": "Is New Lead?", "type": "main", "index": 0}]]
        },
        # If true (no existing record) → Create, If false → Update
        "Is New Lead?": {
            "main": [
                [{"node": "Create in Airtable", "type": "main", "index": 0}],
                [{"node": "Update in Airtable", "type": "main", "index": 0}]
            ]
        },
        # Both Airtable paths → Sheets
        "Create in Airtable": {
            "main": [[{"node": "Append to Sheets", "type": "main", "index": 0}]]
        },
        "Update in Airtable": {
            "main": [[{"node": "Append to Sheets", "type": "main", "index": 0}]]
        },
        # Sheets → Email outreach (new leads) + Summary (all)
        "Append to Sheets": {
            "main": [[
                {"node": "Filter New Leads", "type": "main", "index": 0},
                {"node": "Aggregate Results", "type": "main", "index": 0}
            ]]
        },
        # Email outreach pipeline
        "Filter New Leads": {
            "main": [[{"node": "Rate Limit Emails", "type": "main", "index": 0}]]
        },
        "Rate Limit Emails": {
            "main": [[{"node": "Generate Personalized Email", "type": "main", "index": 0}]]
        },
        "Generate Personalized Email": {
            "main": [[{"node": "Format Email", "type": "main", "index": 0}]]
        },
        "Format Email": {
            "main": [[{"node": "Send Outreach Email", "type": "main", "index": 0}]]
        },
        "Send Outreach Email": {
            "main": [[{"node": "Update Lead Status", "type": "main", "index": 0}]]
        },
        # Summary notification
        "Aggregate Results": {
            "main": [[{"node": "Send Summary", "type": "main", "index": 0}]]
        },
        # Error handling
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]]
        }
    }


def build_workflow():
    """Build the complete workflow JSON."""
    return {
        "name": WORKFLOW_NAME,
        "nodes": build_nodes(),
        "connections": build_connections(),
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner"
        },
        "staticData": None,
        "meta": {
            "templateCredsSetupCompleted": True
        },
        "pinData": {},
        "tags": []
    }


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "build"

    # Add tools dir to path
    sys.path.insert(0, str(Path(__file__).parent))

    print("=" * 60)
    print("LEAD SCRAPER & CRM AUTOMATION - WORKFLOW BUILDER")
    print("=" * 60)

    # Build workflow JSON
    print("\nBuilding workflow JSON...")
    workflow = build_workflow()

    node_count = len([n for n in workflow["nodes"] if n["type"] != "n8n-nodes-base.stickyNote"])
    note_count = len([n for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.stickyNote"])
    conn_count = len(workflow["connections"])

    print(f"  Nodes: {node_count} functional + {note_count} sticky notes")
    print(f"  Connections: {conn_count}")

    # Save to file
    output_dir = Path(__file__).parent.parent / ".tmp"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "lead_scraper_optimized.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"  Saved to: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    # Deploy to n8n
    if action in ("deploy", "activate"):
        from config_loader import load_config
        from n8n_client import N8nClient

        config = load_config()
        api_key = config["api_keys"]["n8n"]
        base_url = config["n8n"]["base_url"]

        print(f"\nConnecting to {base_url}...")

        with N8nClient(base_url, api_key,
                       timeout=config["n8n"].get("timeout_seconds", 30),
                       cache_dir=config["paths"]["cache_dir"]) as client:

            health = client.health_check()
            if not health["connected"]:
                print(f"  ERROR: Cannot connect to n8n: {health.get('error')}")
                sys.exit(1)
            print("  Connected!")

            # Update existing workflow (only send fields the API accepts)
            print(f"\nDeploying to workflow {WORKFLOW_ID}...")
            update_payload = {
                "name": workflow["name"],
                "nodes": workflow["nodes"],
                "connections": workflow["connections"],
                "settings": {"executionOrder": "v1"}
            }
            result = client.update_workflow(WORKFLOW_ID, update_payload)
            print(f"  Deployed: {result.get('name')} (ID: {result.get('id')})")

            if action == "activate":
                print("\nActivating workflow...")
                client.activate_workflow(WORKFLOW_ID)
                print("  Workflow activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"\nWorkflow: {WORKFLOW_NAME}")
    print(f"ID: {WORKFLOW_ID}")
    print(f"Airtable Table: Leads ({AIRTABLE_TABLE_ID})")
    print(f"Google Sheet: LEAD GEN EMAILSCRAPER")
    print(f"\nNext steps:")
    print(f"  1. Open workflow in n8n UI to verify node connections")
    print(f"  2. Update 'Search Config' node with your target industry/location")
    print(f"  3. Verify credential bindings (Airtable, Gmail, Google Sheets)")
    print(f"  4. Test with Manual Trigger on a small batch first")


if __name__ == "__main__":
    main()

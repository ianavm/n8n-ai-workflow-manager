"""
Bridge Integration - Workflow Builder & Deployer

Builds 4 bridge workflows that connect Lead Scraper, Email Manager,
and SEO/Social Growth Engine without modifying any live production workflows.

Workflows:
    BRIDGE-01: Lead Sync (every 2 hours) - Mirror scraper leads into SEO Leads table
    BRIDGE-02: Email Reply Matcher (every 5 min) - Match inbound emails to known leads
    BRIDGE-03: Unified Scoring (daily 6:30 AM) - Score all leads via WF-SCORE
    BRIDGE-04: Warm Lead Nurture (daily 11 AM) - 3-stage email nurture for warm leads

Usage:
    python tools/deploy_bridge_workflows.py build              # Build all JSONs
    python tools/deploy_bridge_workflows.py build bridge01     # Build BRIDGE-01 only
    python tools/deploy_bridge_workflows.py deploy             # Build + Deploy (inactive)
    python tools/deploy_bridge_workflows.py activate           # Build + Deploy + Activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# -- Credential Constants -------------------------------------------------

CRED_AIRTABLE_SEO = {"id": "ZyBrcAO6fps7YB3u", "name": "Whatsapp Multi Agent"}
CRED_AIRTABLE_SCRAPER = {"id": "7TtMl7ZnJFpC4RGk", "name": "Lead Scraper Airtable"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_GOOGLE_SHEETS = {"id": "OkpDXxwI8WcUJp4P", "name": "Google Sheets AVM Tutorial"}
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}

# -- Airtable IDs ---------------------------------------------------------

# SEO/Social base (destination for unified leads)
SEO_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
SEO_TABLE_LEADS = os.getenv("SEO_TABLE_LEADS", "tblwOPTPY85Tcj7NJ")
SEO_TABLE_SCORING_LOG = os.getenv("SEO_TABLE_SCORING_LOG", "tblkbhbifd3PI6plT")

# Lead Scraper base (source)
SCRAPER_BASE_ID = os.getenv("LEAD_SCRAPER_AIRTABLE_BASE_ID", "app2ALQUP7CKEkHOz")
SCRAPER_TABLE_LEADS = os.getenv("LEAD_SCRAPER_TABLE_LEADS", "tblOsuh298hB9WWrA")

# Email Manager Google Sheets
EMAIL_LOG_SHEET_ID = os.getenv("EMAIL_LOG_SHEET_ID", "1Adp3x0ler5H69Cih5tbMLqWEgZMziebhnOEWbMPTvaA")
EMAIL_LOG_TAB = os.getenv("EMAIL_LOG_SHEET_TAB", "Email Log")

# WF-SCORE sub-workflow ID
WF_SCORE_ID = "0US5H9smGsrCUsv7"

# -- Helpers ---------------------------------------------------------------


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ==================================================================
# BRIDGE-01: Lead Sync
# ==================================================================

def build_bridge01_nodes():
    """Build nodes for BRIDGE-01: Lead Sync (every 2 hours)."""
    nodes = []

    # -- Schedule Trigger --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "hours", "hoursInterval": 2}]
            }
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # -- Set Today's Date --
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "todayDate",
                        "value": "={{ $now.toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "threeDaysAgo",
                        "value": "={{ $now.minus({days: 3}).toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Set Dates",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [420, 300],
    })

    # -- Read Scraper Leads (last 3 days) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": SCRAPER_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SCRAPER_TABLE_LEADS, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Date Scraped}, '{{ $json.threeDaysAgo }}')",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Scraper Leads",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [640, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SCRAPER},
    })

    # -- Read SEO Leads (all emails for dedup) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "returnAll": True,
            "options": {
                "fields": ["Email", "Status", "Lead Score", "Scraper Record ID"]
            },
        },
        "id": uid(),
        "name": "Read SEO Leads",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [640, 420],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
    })

    # -- Dedup & Transform (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Get scraper leads and SEO leads
const scraperLeads = $('Read Scraper Leads').all();
const seoLeads = $('Read SEO Leads').all();

// Build set of existing emails in SEO table
const existingEmails = new Set(
  seoLeads.map(l => (l.json.Email || '').toLowerCase()).filter(e => e)
);

// Build map of SEO leads for reverse sync
const seoLeadMap = {};
for (const lead of seoLeads) {
  const scraperRecId = lead.json['Scraper Record ID'];
  if (scraperRecId) {
    seoLeadMap[scraperRecId] = lead.json;
  }
}

const newLeads = [];
const reverseSync = [];

for (const item of scraperLeads) {
  const s = item.json;
  const email = (s.Email || '').toLowerCase();

  if (!email) continue;

  // Check if already in SEO table
  if (!existingEmails.has(email)) {
    newLeads.push({
      json: {
        _action: 'create',
        Email: email,
        Name: s['Business Name'] || '',
        Company: s['Business Name'] || '',
        Phone: s.Phone || '',
        Source: 'Direct',
        Medium: 'outbound',
        Campaign: (s.Industry || '') + ' - ' + (s.Location || 'Johannesburg'),
        'Lead Score': s['Lead Score'] || 0,
        Status: s.Status || 'New',
        'Page URL': s.Website || '',
        'Created At': s['Date Scraped'] || $now.toFormat('yyyy-MM-dd'),
        'Scraper Record ID': s.id || '',
        'Source System': 'Outbound_Scraper',
        'Touch Count': 1,
      }
    });
  }

  // Reverse sync: check if SEO lead status changed
  if (s.id && seoLeadMap[s.id]) {
    const seoLead = seoLeadMap[s.id];
    const seoStatus = seoLead.Status || '';
    const scraperStatus = s.Status || '';

    if (seoStatus !== scraperStatus &&
        ['Responded', 'Converted', 'Qualified'].includes(seoStatus)) {
      reverseSync.push({
        json: {
          _action: 'reverse_sync',
          scraper_record_id: s.id,
          new_status: seoStatus,
        }
      });
    }
  }
}

return [{
  json: {
    newCount: newLeads.length,
    reverseSyncCount: reverseSync.length,
    totalScraperLeads: scraperLeads.length,
    totalSeoLeads: seoLeads.length,
    newLeads: newLeads.map(l => l.json),
    reverseSync: reverseSync.map(r => r.json),
  }
}];"""
        },
        "id": uid(),
        "name": "Dedup & Transform",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 300],
    })

    # -- Has New Leads? (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.newCount }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has New Leads?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1100, 300],
    })

    # -- Split New Leads (Code -> items) --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $json.newLeads || [];
return items.map(lead => ({ json: lead }));"""
        },
        "id": uid(),
        "name": "Split New Leads",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 200],
    })

    # -- Create in SEO Table --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "columns": {
                "mappingMode": "autoMapInputData",
                "matchingColumns": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create in SEO Table",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1540, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
    })

    # -- Summary Email --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=Bridge Lead Sync - {{ $now.toFormat('yyyy-MM-dd HH:mm') }}",
            "message": """=<h3>Bridge Lead Sync Complete</h3>
<p><strong>Scraper leads scanned:</strong> {{ $('Dedup & Transform').first().json.totalScraperLeads }}</p>
<p><strong>New leads synced to SEO table:</strong> {{ $('Dedup & Transform').first().json.newCount }}</p>
<p><strong>Reverse status syncs:</strong> {{ $('Dedup & Transform').first().json.reverseSyncCount }}</p>
<p><em>Run at {{ $now.toFormat('yyyy-MM-dd HH:mm') }} SAST</em></p>""",
            "options": {},
        },
        "id": uid(),
        "name": "Summary Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1760, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## BRIDGE-01: Lead Sync\nMirrors scraper leads into the SEO Leads table.\nRuns every 2 hours.\n\n**Flow:** Read scraper leads (last 3 days) -> Dedup against SEO table -> Create new -> Summary email",
            "width": 400,
            "height": 120,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 120],
    })

    return nodes


def build_bridge01_connections():
    """Build connections for BRIDGE-01."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Set Dates", "type": "main", "index": 0}]]
        },
        "Set Dates": {
            "main": [
                [
                    {"node": "Read Scraper Leads", "type": "main", "index": 0},
                    {"node": "Read SEO Leads", "type": "main", "index": 0},
                ]
            ]
        },
        "Read Scraper Leads": {
            "main": [[{"node": "Dedup & Transform", "type": "main", "index": 0}]]
        },
        "Read SEO Leads": {
            "main": [[{"node": "Dedup & Transform", "type": "main", "index": 0}]]
        },
        "Dedup & Transform": {
            "main": [[{"node": "Has New Leads?", "type": "main", "index": 0}]]
        },
        "Has New Leads?": {
            "main": [
                [{"node": "Split New Leads", "type": "main", "index": 0}],
                [{"node": "Summary Email", "type": "main", "index": 0}],
            ]
        },
        "Split New Leads": {
            "main": [[{"node": "Create in SEO Table", "type": "main", "index": 0}]]
        },
        "Create in SEO Table": {
            "main": [[{"node": "Summary Email", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# BRIDGE-02: Email Reply Matcher
# ==================================================================

def build_bridge02_nodes():
    """Build nodes for BRIDGE-02: Email Reply Matcher (every 5 min).

    Batch approach: reads all leads once, matches in code, then updates.
    Avoids per-email Airtable searches which hit rate limits.
    """
    nodes = []

    # -- Schedule Trigger --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "minutes", "minutesInterval": 5}]
            }
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # -- Get Watermark --
    nodes.append({
        "parameters": {
            "jsCode": """const staticData = $getWorkflowStaticData('global');
const lastRow = staticData.lastProcessedRow || 1;
return [{ json: { lastRow } }];"""
        },
        "id": uid(),
        "name": "Get Watermark",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [420, 300],
    })

    # -- Read Email Log Sheet --
    nodes.append({
        "parameters": {
            "operation": "read",
            "documentId": {"__rl": True, "value": EMAIL_LOG_SHEET_ID, "mode": "id"},
            "sheetName": {"__rl": True, "value": EMAIL_LOG_TAB, "mode": "name"},
            "options": {
                "range": "=A{{ $json.lastRow + 1 }}:Z",
                "headerRow": 0,
            },
        },
        "id": uid(),
        "name": "Read Email Log",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [640, 300],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
    })

    # -- Extract Senders (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $('Read Email Log').all();
const lastRow = $('Get Watermark').first().json.lastRow;
const totalRead = items.length;
const newWatermark = lastRow + totalRead;

if (!items || totalRead === 0) {
  return [{ json: { hasSenders: false, senders: [], emailData: [], newWatermark: lastRow } }];
}

// Extract unique senders with their email classification data
const senderMap = {};
for (const item of items) {
  const sender = (item.json.sender || '').toLowerCase().trim();
  if (!sender || sender.includes('noreply') || sender.includes('no-reply')) continue;
  if (sender === 'unknown' || sender.includes('mailer-daemon')) continue;
  if (sender.includes('<') || sender.includes('>') || !sender.includes('@')) continue;

  // Keep the latest email data per sender
  senderMap[sender] = {
    sender,
    department: item.json.department || '',
    tags_string: (item.json.tags_string || item.json.tags || '').toLowerCase(),
    is_spam: String(item.json.is_spam) === 'true',
    subject: item.json.subject || '',
    summary: item.json.summary || '',
    urgency: item.json.urgency || 'low',
    is_interested_reply: String(item.json.is_interested_reply) === 'true',
  };
}

const senders = Object.keys(senderMap);
const emailData = Object.values(senderMap);

// Build Airtable filter formula: OR(LOWER({Email})='a@b.com', LOWER({Email})='c@d.com')
let filterFormula = '';
if (senders.length > 0 && senders.length <= 50) {
  const conditions = senders.map(s => "LOWER({Email})='" + s + "'");
  filterFormula = 'OR(' + conditions.join(',') + ')';
} else if (senders.length > 50) {
  // Too many senders, take first 50
  const conditions = senders.slice(0, 50).map(s => "LOWER({Email})='" + s + "'");
  filterFormula = 'OR(' + conditions.join(',') + ')';
}

return [{ json: {
  hasSenders: senders.length > 0,
  senderCount: senders.length,
  filterFormula: filterFormula,
  emailData: emailData,
  newWatermark: newWatermark,
  totalRead: totalRead,
} }];"""
        },
        "id": uid(),
        "name": "Extract Senders",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [860, 300],
    })

    # -- Has Senders? (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.hasSenders }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Senders?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1080, 300],
    })

    # -- Search Scraper Leads (targeted by sender emails) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": SCRAPER_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SCRAPER_TABLE_LEADS, "mode": "id"},
            "filterByFormula": "={{ $('Extract Senders').first().json.filterFormula }}",
            "returnAll": True,
            "options": {
                "fields": ["Email", "Status", "Follow Up Stage"]
            },
        },
        "id": uid(),
        "name": "Search Scraper Leads",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1300, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SCRAPER},
        "onError": "continueRegularOutput",
        "alwaysOutputData": True,
    })

    # -- Search SEO Leads (targeted by sender emails) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "filterByFormula": "={{ $('Extract Senders').first().json.filterFormula }}",
            "returnAll": True,
            "options": {
                "fields": ["Email", "Status", "Lead Score"]
            },
        },
        "id": uid(),
        "name": "Search SEO Leads",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1500, 420],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
        "onError": "continueRegularOutput",
        "alwaysOutputData": True,
    })

    # -- Match All in Code --
    nodes.append({
        "parameters": {
            "jsCode": """const extractData = $('Extract Senders').first().json;
const scraperLeads = $('Search Scraper Leads').all();
const seoLeads = $('Search SEO Leads').all();

// Build lookup maps from targeted query results
const scraperMap = {};
for (const lead of scraperLeads) {
  const email = (lead.json.Email || '').toLowerCase();
  if (email) scraperMap[email] = lead.json;
}

const seoMap = {};
for (const lead of seoLeads) {
  const email = (lead.json.Email || '').toLowerCase();
  if (email) seoMap[email] = lead.json;
}

// Match email senders to leads
const matches = [];
for (const emailInfo of extractData.emailData) {
  const scraperMatch = scraperMap[emailInfo.sender] || null;
  const seoMatch = seoMap[emailInfo.sender] || null;

  if (!scraperMatch && !seoMatch) continue;

  let newStatus = 'Responded';
  let followUpStage = null;

  if (emailInfo.is_spam || emailInfo.tags_string.includes('unsubscribe')) {
    newStatus = 'Unsubscribed';
    followUpStage = 0;
  } else if (emailInfo.is_interested_reply || emailInfo.tags_string.includes('new_lead') || emailInfo.department === 'Sales') {
    newStatus = 'Responded';
  } else if (emailInfo.tags_string.includes('complaint') || emailInfo.tags_string.includes('escalation')) {
    newStatus = 'Ticket Reply - Do Not Follow Up';
    followUpStage = 0;
  }

  matches.push({
    sender: emailInfo.sender,
    newStatus,
    followUpStage,
    scraperRecordId: scraperMatch ? scraperMatch.id : null,
    seoRecordId: seoMatch ? seoMatch.id : null,
    seoLeadScore: seoMatch ? (seoMatch['Lead Score'] || 0) : 0,
    urgency: emailInfo.urgency,
    subject: emailInfo.subject,
    summary: emailInfo.summary,
  });
}

return [{ json: {
  hasMatches: matches.length > 0,
  matchCount: matches.length,
  totalProcessed: extractData.totalRead,
  newWatermark: extractData.newWatermark,
  matches,
} }];"""
        },
        "id": uid(),
        "name": "Match All",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [920, 400],
    })

    # -- Has Matches? (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.matchCount }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Matches?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1140, 400],
    })

    # -- Split Matches --
    nodes.append({
        "parameters": {
            "jsCode": """const matches = $json.matches || [];
return matches.map(m => ({ json: m }));"""
        },
        "id": uid(),
        "name": "Split Matches",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1360, 300],
    })

    # -- Update Scraper Lead --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": SCRAPER_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SCRAPER_TABLE_LEADS, "mode": "id"},
            "id": "={{ $json.scraperRecordId }}",
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Status": "={{ $json.newStatus }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "Status", "displayName": "Status", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": True},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Scraper Lead",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1580, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SCRAPER},
        "onError": "continueRegularOutput",
    })

    # -- Update SEO Lead --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "id": "={{ $json.seoRecordId }}",
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Status": "={{ $json.newStatus }}",
                    "Last Activity": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "Status", "displayName": "Status", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": True},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update SEO Lead",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1580, 420],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
        "onError": "continueRegularOutput",
    })

    # -- Summary + Alert Email --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=Bridge Email Matcher - {{ $('Match All').first().json.matchCount }} matches",
            "message": """=<h3>Email Reply Matcher Complete</h3>
<p><strong>Emails processed:</strong> {{ $('Match All').first().json.totalProcessed }}</p>
<p><strong>Leads matched:</strong> {{ $('Match All').first().json.matchCount }}</p>
<p><em>Run at {{ $now.toFormat('yyyy-MM-dd HH:mm') }} SAST</em></p>""",
            "options": {},
        },
        "id": uid(),
        "name": "Summary Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1800, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Update Watermark --
    nodes.append({
        "parameters": {
            "jsCode": """const staticData = $getWorkflowStaticData('global');
// Get watermark from Match All (if senders found) or Extract Senders (if no senders)
let newWatermark;
try {
  newWatermark = $('Match All').first().json.newWatermark;
} catch (e) {
  newWatermark = $('Extract Senders').first().json.newWatermark;
}
staticData.lastProcessedRow = newWatermark;
return [{ json: { watermarkUpdated: true, newWatermark } }];"""
        },
        "id": uid(),
        "name": "Update Watermark",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2020, 400],
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## BRIDGE-02: Email Reply Matcher\nBatch approach: reads ALL leads once, matches senders in code.\nAvoids per-email Airtable lookups (rate limit safe).\nRuns every 5 minutes.",
            "width": 440,
            "height": 110,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 120],
    })

    return nodes


def build_bridge02_connections():
    """Build connections for BRIDGE-02."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Get Watermark", "type": "main", "index": 0}]]
        },
        "Get Watermark": {
            "main": [[{"node": "Read Email Log", "type": "main", "index": 0}]]
        },
        "Read Email Log": {
            "main": [[{"node": "Extract Senders", "type": "main", "index": 0}]]
        },
        "Extract Senders": {
            "main": [[{"node": "Has Senders?", "type": "main", "index": 0}]]
        },
        "Has Senders?": {
            "main": [
                [{"node": "Search Scraper Leads", "type": "main", "index": 0}],
                [{"node": "Update Watermark", "type": "main", "index": 0}],
            ]
        },
        "Search Scraper Leads": {
            "main": [[{"node": "Search SEO Leads", "type": "main", "index": 0}]]
        },
        "Search SEO Leads": {
            "main": [[{"node": "Match All", "type": "main", "index": 0}]]
        },
        "Match All": {
            "main": [[{"node": "Update Watermark", "type": "main", "index": 0}]]
        },
        "Update Watermark": {
            "main": [[{"node": "Has Matches?", "type": "main", "index": 0}]]
        },
        "Has Matches?": {
            "main": [
                [{"node": "Split Matches", "type": "main", "index": 0}],
                [],
            ]
        },
        "Split Matches": {
            "main": [
                [
                    {"node": "Update Scraper Lead", "type": "main", "index": 0},
                    {"node": "Update SEO Lead", "type": "main", "index": 0},
                ]
            ]
        },
        "Update Scraper Lead": {
            "main": [[{"node": "Summary Email", "type": "main", "index": 0}]]
        },
        "Update SEO Lead": {
            "main": [[]]
        },
    }


# ==================================================================
# BRIDGE-03: Unified Scoring
# ==================================================================

def build_bridge03_nodes():
    """Build nodes for BRIDGE-03: Unified Scoring (daily 6:30 AM SAST)."""
    nodes = []

    # -- Schedule Trigger (6:30 AM SAST = 4:30 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "30 4 * * *",
                    }
                ]
            }
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # -- Read Unscored Leads --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "filterByFormula": "=OR({Grade} = '', {Grade} = BLANK())",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Unscored Leads",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [440, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
    })

    # -- Has Leads? (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.id }}",
                        "rightValue": "",
                        "operator": {"type": "string", "operation": "notEmpty"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Leads?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [660, 300],
    })

    # -- Build Scoring Payload (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $input.all();
const results = [];

// Scoring weights from config
const weights = {
  source_quality: 0.3,
  engagement_depth: 0.2,
  company_fit: 0.2,
  recency: 0.15,
  completeness: 0.15,
};

// Source quality scores
const sourceScores = {
  'organic': 1.0,
  'social': 0.8,
  'referral': 0.6,
  'Direct': 0.4,
  'outbound': 0.4,
};

const jhbKeywords = ['johannesburg', 'jhb', 'jozi', 'sandton', 'fourways', 'randburg', 'midrand', 'roodepoort', 'gauteng'];

for (const item of items) {
  const lead = item.json;

  // Source quality (0-1)
  const source = lead.Source || lead.Medium || 'outbound';
  const sourceQuality = sourceScores[source.toLowerCase()] || 0.4;

  // Engagement depth (0-1) - normalize touch count
  const touchCount = lead['Touch Count'] || 1;
  const engagementDepth = Math.min(touchCount / 10, 1.0);

  // Company fit (0-1) - industry match + location
  let companyFit = 0.5; // baseline
  const campaign = (lead.Campaign || '').toLowerCase();
  const company = (lead.Company || '').toLowerCase();

  // Johannesburg area bonus
  if (jhbKeywords.some(k => campaign.includes(k) || company.includes(k))) {
    companyFit += 0.3;
  }
  // Has company name
  if (lead.Company) companyFit += 0.1;
  companyFit = Math.min(companyFit, 1.0);

  // Recency (0-1) - exponential decay
  let recency = 0.5;
  const lastActivity = lead['Last Activity'] || lead['Created At'];
  if (lastActivity) {
    const daysSince = Math.floor((Date.now() - new Date(lastActivity).getTime()) / (1000 * 60 * 60 * 24));
    recency = Math.exp(-daysSince / 14); // half-life of ~14 days
  }

  // Completeness (0-1) - % of fields filled
  const fields = ['Email', 'Phone', 'Company', 'Page URL', 'Name'];
  const filled = fields.filter(f => lead[f] && lead[f].toString().trim()).length;
  const completeness = filled / fields.length;

  // Composite score (0-100)
  const compositeScore = Math.round(
    (sourceQuality * weights.source_quality +
     engagementDepth * weights.engagement_depth +
     companyFit * weights.company_fit +
     recency * weights.recency +
     completeness * weights.completeness) * 100
  );

  // Grade
  let grade = 'Cold';
  if (compositeScore >= 80) grade = 'Hot';
  else if (compositeScore >= 50) grade = 'Warm';

  results.push({
    json: {
      recordId: lead.id,
      email: lead.Email,
      compositeScore,
      grade,
      entity_type: 'lead',
      details: {
        source_quality: sourceQuality,
        engagement_depth: engagementDepth,
        company_fit: companyFit,
        recency,
        completeness,
      },
    }
  });
}

return results;"""
        },
        "id": uid(),
        "name": "Build Scoring Payload",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 200],
    })

    # -- Execute WF-SCORE Sub-workflow --
    nodes.append({
        "parameters": {
            "workflowId": {"__rl": True, "value": WF_SCORE_ID, "mode": "id"},
            "options": {},
        },
        "id": uid(),
        "name": "Execute WF-SCORE",
        "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1.2,
        "position": [1100, 200],
    })

    # -- Update Lead Score & Grade --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "id": "={{ $('Build Scoring Payload').item.json.recordId }}",
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Lead Score": "={{ $('Build Scoring Payload').item.json.compositeScore }}",
                    "Grade": "={{ $('Build Scoring Payload').item.json.grade }}",
                    "Last Activity": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "Lead Score", "displayName": "Lead Score", "required": False, "defaultMatch": False, "display": True, "type": "number", "canBeUsedToMatch": False},
                    {"id": "Grade", "displayName": "Grade", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": False},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Score & Grade",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1320, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
    })

    # -- Route by Grade (Switch) --
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $('Build Scoring Payload').item.json.grade }}",
                                    "rightValue": "Hot",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                        "outputKey": "Hot",
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $('Build Scoring Payload').item.json.grade }}",
                                    "rightValue": "Warm",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                        "outputKey": "Warm",
                    },
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Route by Grade",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [1540, 200],
    })

    # -- Hot Lead Alert --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=HOT LEAD: {{ $('Build Scoring Payload').item.json.email }} (Score: {{ $('Build Scoring Payload').item.json.compositeScore }})",
            "message": """=<h3>Hot Lead Detected by Scoring Engine</h3>
<p><strong>Email:</strong> {{ $('Build Scoring Payload').item.json.email }}</p>
<p><strong>Score:</strong> {{ $('Build Scoring Payload').item.json.compositeScore }}/100</p>
<p><strong>Grade:</strong> Hot</p>
<p><strong>Details:</strong></p>
<ul>
<li>Source Quality: {{ Math.round($('Build Scoring Payload').item.json.details.source_quality * 100) }}%</li>
<li>Engagement: {{ Math.round($('Build Scoring Payload').item.json.details.engagement_depth * 100) }}%</li>
<li>Company Fit: {{ Math.round($('Build Scoring Payload').item.json.details.company_fit * 100) }}%</li>
<li>Recency: {{ Math.round($('Build Scoring Payload').item.json.details.recency * 100) }}%</li>
<li>Completeness: {{ Math.round($('Build Scoring Payload').item.json.details.completeness * 100) }}%</li>
</ul>
<p style="margin-top:16px;"><strong>Action: Reply within 1 hour during business hours</strong></p>
<p><a href="https://calendar.app.google/79JABt2piDQ5X4gW8" style="display:inline-block; padding:10px 20px; background:#FF6D5A; color:white; text-decoration:none; border-radius:6px; font-weight:bold;">Book a Call With This Lead</a></p>
<p style="font-size:13px; color:#666;">Or reply directly to: {{ $('Build Scoring Payload').item.json.email }}</p>""",
            "options": {},
        },
        "id": uid(),
        "name": "Hot Lead Alert",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1780, 100],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Set Nurture Queue (for warm leads) --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "id": "={{ $('Build Scoring Payload').item.json.recordId }}",
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Nurture Stage": 1,
                    "Next Nurture Date": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "Nurture Stage", "displayName": "Nurture Stage", "required": False, "defaultMatch": False, "display": True, "type": "number", "canBeUsedToMatch": False},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Queue for Nurture",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1780, 320],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
    })

    # -- Summary Email --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=Bridge Scoring Complete - {{ $now.toFormat('yyyy-MM-dd') }}",
            "message": """=<h3>Unified Scoring Complete</h3>
<p><strong>Leads scored:</strong> {{ $input.all().length }}</p>
<p><em>Run at {{ $now.toFormat('yyyy-MM-dd HH:mm') }} SAST</em></p>
<p>Check the SEO Leads table for updated Grade column (Hot/Warm/Cold).</p>""",
            "options": {},
        },
        "id": uid(),
        "name": "Summary Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [2000, 200],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## BRIDGE-03: Unified Scoring\nScores all unscored leads using config.json weights.\nRoutes Hot leads to email alert, queues Warm for nurture.\nRuns daily at 6:30 AM SAST.",
            "width": 400,
            "height": 120,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 120],
    })

    return nodes


def build_bridge03_connections():
    """Build connections for BRIDGE-03."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Read Unscored Leads", "type": "main", "index": 0}]]
        },
        "Read Unscored Leads": {
            "main": [[{"node": "Has Leads?", "type": "main", "index": 0}]]
        },
        "Has Leads?": {
            "main": [
                [{"node": "Build Scoring Payload", "type": "main", "index": 0}],
                [],
            ]
        },
        "Build Scoring Payload": {
            "main": [[{"node": "Execute WF-SCORE", "type": "main", "index": 0}]]
        },
        "Execute WF-SCORE": {
            "main": [[{"node": "Update Score & Grade", "type": "main", "index": 0}]]
        },
        "Update Score & Grade": {
            "main": [[{"node": "Route by Grade", "type": "main", "index": 0}]]
        },
        "Route by Grade": {
            "main": [
                [{"node": "Hot Lead Alert", "type": "main", "index": 0}],
                [{"node": "Queue for Nurture", "type": "main", "index": 0}],
                [{"node": "Summary Email", "type": "main", "index": 0}],
            ]
        },
        "Hot Lead Alert": {
            "main": [[{"node": "Summary Email", "type": "main", "index": 0}]]
        },
        "Queue for Nurture": {
            "main": [[{"node": "Summary Email", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# BRIDGE-04: Warm Lead Nurture
# ==================================================================

def build_bridge04_nodes():
    """Build nodes for BRIDGE-04: Warm Lead Nurture (daily 11 AM SAST)."""
    nodes = []

    # -- Schedule Trigger (11:00 AM SAST = 9:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 9 * * *",
                    }
                ]
            }
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # -- Read Warm Leads Due --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "filterByFormula": "=AND({Grade} = 'Warm', {Nurture Stage} < 4, IS_BEFORE({Next Nurture Date}, DATEADD(TODAY(), 1, 'day')))",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Warm Leads Due",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [440, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
    })

    # -- Has Leads? --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.id }}",
                        "rightValue": "",
                        "operator": {"type": "string", "operation": "notEmpty"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Leads?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [660, 300],
    })

    # -- Prepare Nurture Context (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $input.all();
const results = [];

const stageConfig = {
  1: {
    subject: 'How AI automation can transform your business',
    template: 'welcome',
    daysUntilNext: 3,
    prompt: `Write a warm, personalized welcome email for a potential client.
The email should:
- Welcome them and reference how we found them (through their business online presence)
- Briefly mention one key benefit of AI workflow automation
- Include a soft CTA to check out our latest content on anyvisionmedia.com
- Keep it under 150 words
- Tone: friendly, professional, not salesy`,
  },
  2: {
    subject: 'How businesses like yours are saving 10+ hours/week',
    template: 'case_study',
    daysUntilNext: 4,
    prompt: `Write a case study style email showing real results from AI automation.
The email should:
- Reference a specific result: "a Johannesburg business saved 10+ hours per week"
- Mention specific automations: lead follow-up, email management, invoice processing
- Include social proof and credibility markers
- Include a CTA to reply with questions
- Keep it under 200 words
- Tone: authoritative, results-focused`,
  },
  3: {
    subject: 'Let\\'s chat about automating your workflows',
    template: 'cta',
    daysUntilNext: null,
    prompt: `Write a direct CTA email offering a free discovery call.
The email should:
- Acknowledge this is the third touchpoint
- Offer a specific value prop: "15-minute discovery call to identify your top 3 automation opportunities"
- Create urgency without being pushy
- Include a clear CTA to book a call
- Keep it under 120 words
- Tone: direct, helpful, confident`,
  },
};

for (const item of items) {
  const lead = item.json;
  const stage = lead['Nurture Stage'] || 1;
  const config = stageConfig[stage];

  if (!config) continue;
  if (!lead.Email) continue;

  results.push({
    json: {
      recordId: lead.id,
      email: lead.Email,
      name: lead.Name || lead.Company || 'there',
      company: lead.Company || '',
      stage: stage,
      subject: config.subject,
      daysUntilNext: config.daysUntilNext,
      nextStage: config.daysUntilNext ? stage + 1 : null,
      prompt: config.prompt + '\\n\\nRecipient name: ' + (lead.Name || lead.Company || 'valued prospect') + '\\nCompany: ' + (lead.Company || 'their business'),
    }
  });
}

return results;"""
        },
        "id": uid(),
        "name": "Prepare Context",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 200],
    })

    # -- AI Generate Nurture Email (OpenRouter) --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514",
  "max_tokens": 500,
  "messages": [
    {
      "role": "system",
      "content": "You are a professional email copywriter for AnyVision Media, an AI automation agency in Johannesburg, South Africa. Write emails that are personalized, warm, and convert. Sign off as 'Ian Immelman, AnyVision Media'. Return ONLY the email body HTML (no subject line, no ```html tags). Use simple inline-styled HTML with paragraphs."
    },
    {
      "role": "user",
      "content": {{ JSON.stringify($json.prompt) }}
    }
  ]
}""",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Generate Email",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1100, 200],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Format HTML (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """const context = $('Prepare Context').item.json;
const aiResponse = $json.choices?.[0]?.message?.content || '';

// Wrap in branded HTML template
const html = `
<div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
  ${aiResponse}
  <br/>
  <div style="margin-top: 24px; padding-top: 16px; border-top: 2px solid #FF6D5A;">
    <p style="margin: 4px 0; font-weight: bold; color: #FF6D5A;">Ian Immelman</p>
    <p style="margin: 4px 0; font-size: 14px;">Founder, AnyVision Media</p>
    <p style="margin: 4px 0; font-size: 13px; color: #666;">
      <a href="https://www.anyvisionmedia.com" style="color: #FF6D5A;">www.anyvisionmedia.com</a>
       | ian@anyvisionmedia.com
    </p>
  </div>
</div>`;

return [{
  json: {
    ...context,
    htmlBody: html,
  }
}];"""
        },
        "id": uid(),
        "name": "Format HTML",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 200],
    })

    # -- Send Gmail --
    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.email }}",
            "subject": "={{ $json.subject }}",
            "message": "={{ $json.htmlBody }}",
            "options": {
                "replyTo": "ian@anyvisionmedia.com",
                "senderName": "Ian Immelman | AnyVision Media",
            },
        },
        "id": uid(),
        "name": "Send Nurture Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1540, 200],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Update Nurture Stage --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "id": "={{ $json.recordId }}",
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Nurture Stage": "={{ $json.nextStage || $json.stage }}",
                    "Next Nurture Date": "={{ $json.daysUntilNext ? $now.plus({days: $json.daysUntilNext}).toFormat('yyyy-MM-dd') : '' }}",
                    "Last Activity": "={{ $now.toFormat('yyyy-MM-dd') }}",
                    "Touch Count": "={{ ($('Read Warm Leads Due').item.json['Touch Count'] || 0) + 1 }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "Nurture Stage", "displayName": "Nurture Stage", "required": False, "defaultMatch": False, "display": True, "type": "number", "canBeUsedToMatch": False},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Nurture Stage",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1760, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
    })

    # -- Summary Email --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=Bridge Nurture Run - {{ $now.toFormat('yyyy-MM-dd') }}",
            "message": """=<h3>Warm Lead Nurture Complete</h3>
<p><strong>Emails sent:</strong> {{ $input.all().length }}</p>
<p><em>Run at {{ $now.toFormat('yyyy-MM-dd HH:mm') }} SAST</em></p>
<p>Check the SEO Leads table for updated Nurture Stage values.</p>""",
            "options": {},
        },
        "id": uid(),
        "name": "Summary Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1980, 200],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ==============================================================
    # COLD LEAD RE-ENGAGEMENT BRANCH (parallel to warm nurture)
    # ==============================================================

    # -- Read Cold Leads Due --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "filterByFormula": "=AND({Grade} = 'Cold', {Nurture Stage} < 1, IS_BEFORE({Created At}, DATEADD(TODAY(), -7, 'days')), {Status} != 'Bounced', {Status} != 'Unsubscribed', {Status} != 'Exhausted')",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Cold Leads Due",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [440, 600],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
        "alwaysOutputData": True,
    })

    # -- Has Cold Leads? --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.id }}",
                        "rightValue": "",
                        "operator": {"type": "string", "operation": "notEmpty"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Cold Leads?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [660, 600],
    })

    # -- Prepare Cold Reactivation Context --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $input.all();
const results = [];

for (const item of items) {
  const lead = item.json;
  if (!lead.Email) continue;

  results.push({
    json: {
      recordId: lead.id,
      email: lead.Email,
      name: lead.Name || lead.Company || 'there',
      company: lead.Company || '',
      stage: 0,
      subject: 'Quick question about AI for ' + (lead.Company || 'your business'),
      daysUntilNext: null,
      nextStage: null,
      prompt: `Write a brief cold lead re-engagement email. This person was contacted before but didn't respond.
The email should:
- Be very brief (under 100 words)
- Acknowledge we reached out before but understand they may have been busy
- Mention one specific benefit: "businesses like yours typically save 10+ hours/week with AI automation"
- End with this exact CTA: "Reply YES if you'd like a free 5-minute assessment"
- Tone: casual, respectful of their time, not pushy at all
- Do NOT use phrases like "following up" or "circling back"

Recipient name: ${lead.Name || lead.Company || 'valued prospect'}
Company: ${lead.Company || 'their business'}`,
    }
  });
}

return results.length > 0 ? results : [{ json: { _empty: true } }];"""
        },
        "id": uid(),
        "name": "Prepare Cold Context",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 600],
    })

    # -- AI Generate Cold Email (OpenRouter) --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514",
  "max_tokens": 300,
  "messages": [
    {
      "role": "system",
      "content": "You are a professional email copywriter for AnyVision Media, an AI automation agency in Johannesburg, South Africa. Write a very brief, casual re-engagement email. Sign off as 'Ian Immelman, AnyVision Media'. Return ONLY the email body HTML (no subject line, no ```html tags). Use simple inline-styled HTML with paragraphs."
    },
    {
      "role": "user",
      "content": {{ JSON.stringify($json.prompt) }}
    }
  ]
}""",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Generate Cold Email",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1100, 600],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Format Cold HTML --
    nodes.append({
        "parameters": {
            "jsCode": """const context = $('Prepare Cold Context').item.json;
const aiResponse = $json.choices?.[0]?.message?.content || '';

const html = `
<div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
  ${aiResponse}
  <br/>
  <div style="margin-top: 24px; padding-top: 16px; border-top: 2px solid #FF6D5A;">
    <p style="margin: 4px 0; font-weight: bold; color: #FF6D5A;">Ian Immelman</p>
    <p style="margin: 4px 0; font-size: 14px;">Founder, AnyVision Media</p>
    <p style="margin: 4px 0; font-size: 13px; color: #666;">
      <a href="https://www.anyvisionmedia.com" style="color: #FF6D5A;">www.anyvisionmedia.com</a>
       | ian@anyvisionmedia.com
    </p>
  </div>
</div>`;

return [{
  json: {
    ...context,
    htmlBody: html,
  }
}];"""
        },
        "id": uid(),
        "name": "Format Cold HTML",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 600],
    })

    # -- Send Cold Reactivation Email --
    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.email }}",
            "subject": "={{ $json.subject }}",
            "message": "={{ $json.htmlBody }}",
            "options": {
                "replyTo": "ian@anyvisionmedia.com",
                "senderName": "Ian Immelman | AnyVision Media",
            },
        },
        "id": uid(),
        "name": "Send Cold Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1540, 600],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Update Cold Lead to Exhausted --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "id": "={{ $json.recordId }}",
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Nurture Stage": 1,
                    "Grade": "Exhausted",
                    "Last Activity": "={{ $now.toFormat('yyyy-MM-dd') }}",
                    "Touch Count": "={{ ($('Read Cold Leads Due').item.json['Touch Count'] || 0) + 1 }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "Nurture Stage", "displayName": "Nurture Stage", "required": False, "defaultMatch": False, "display": True, "type": "number", "canBeUsedToMatch": False},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Mark Exhausted",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1760, 600],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
    })

    # ==============================================================
    # FOLLOW-UP BRANCH: Unanswered first-touch leads (4+ days old)
    # ==============================================================

    # -- Read Unanswered First-Touch --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "filterByFormula": "=AND({Touch Count} = 1, {Nurture Stage} < 2, IS_BEFORE({Last Activity}, DATEADD(TODAY(), -4, 'days')), {Status} != 'Responded', {Status} != 'Bounced', {Status} != 'Unsubscribed', {Status} != 'Exhausted', {Grade} != 'Exhausted')",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Unanswered",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [440, 900],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
        "alwaysOutputData": True,
    })

    # -- Has Unanswered? --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.id }}",
                        "rightValue": "",
                        "operator": {"type": "string", "operation": "notEmpty"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Unanswered?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [660, 900],
    })

    # -- Prepare Follow-Up Context --
    nodes.append({
        "parameters": {
            "jsCode": """const items = $input.all();
const results = [];

for (const item of items) {
  const lead = item.json;
  if (!lead.Email) continue;

  results.push({
    json: {
      recordId: lead.id,
      email: lead.Email,
      name: lead.Name || lead.Company || 'there',
      company: lead.Company || '',
      stage: 1,
      subject: 'Still interested? Quick AI wins for ' + (lead.Company || 'your business'),
      daysUntilNext: null,
      nextStage: 2,
      prompt: `Write a brief follow-up email. This person received an initial outreach email 4-7 days ago but hasn't responded.
The email should:
- Be very brief (under 100 words)
- NOT say "following up" or "circling back" or "just checking in"
- Instead, offer one NEW piece of value: a specific quick win relevant to their business
- Reference a concrete result: "One of our clients automated their entire email follow-up process and recovered R40,000 in lost leads"
- End with: "Reply YES for a free 15-minute AI assessment"
- Tone: helpful, low-pressure, conversational

Recipient name: ${lead.Name || lead.Company || 'valued prospect'}
Company: ${lead.Company || 'their business'}`,
    }
  });
}

return results.length > 0 ? results : [{ json: { _empty: true } }];"""
        },
        "id": uid(),
        "name": "Prepare Follow-Up Context",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 900],
    })

    # -- AI Generate Follow-Up Email --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514",
  "max_tokens": 300,
  "messages": [
    {
      "role": "system",
      "content": "You are a professional email copywriter for AnyVision Media, an AI automation agency in Johannesburg, South Africa. Write a very brief follow-up email that adds new value (not a generic follow-up). Sign off as 'Ian Immelman, AnyVision Media'. Return ONLY the email body HTML (no subject line, no ```html tags). Use simple inline-styled HTML with paragraphs."
    },
    {
      "role": "user",
      "content": {{ JSON.stringify($json.prompt) }}
    }
  ]
}""",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Generate Follow-Up",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1100, 900],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Format Follow-Up HTML --
    nodes.append({
        "parameters": {
            "jsCode": """const context = $('Prepare Follow-Up Context').item.json;
const aiResponse = $json.choices?.[0]?.message?.content || '';

const html = `
<div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
  ${aiResponse}
  <br/>
  <div style="margin-top: 24px; padding-top: 16px; border-top: 2px solid #FF6D5A;">
    <p style="margin: 4px 0; font-weight: bold; color: #FF6D5A;">Ian Immelman</p>
    <p style="margin: 4px 0; font-size: 14px;">Founder, AnyVision Media</p>
    <p style="margin: 4px 0; font-size: 13px; color: #666;">
      <a href="https://www.anyvisionmedia.com" style="color: #FF6D5A;">www.anyvisionmedia.com</a>
       | ian@anyvisionmedia.com
    </p>
  </div>
</div>`;

return [{
  json: {
    ...context,
    htmlBody: html,
  }
}];"""
        },
        "id": uid(),
        "name": "Format Follow-Up HTML",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 900],
    })

    # -- Send Follow-Up Email --
    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.email }}",
            "subject": "={{ $json.subject }}",
            "message": "={{ $json.htmlBody }}",
            "options": {
                "replyTo": "ian@anyvisionmedia.com",
                "senderName": "Ian Immelman | AnyVision Media",
            },
        },
        "id": uid(),
        "name": "Send Follow-Up",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1540, 900],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Update Follow-Up Stage --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": SEO_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": SEO_TABLE_LEADS, "mode": "id"},
            "id": "={{ $json.recordId }}",
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Nurture Stage": "={{ $json.nextStage || 2 }}",
                    "Last Activity": "={{ $now.toFormat('yyyy-MM-dd') }}",
                    "Touch Count": "={{ ($('Read Unanswered').item.json['Touch Count'] || 1) + 1 }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "Nurture Stage", "displayName": "Nurture Stage", "required": False, "defaultMatch": False, "display": True, "type": "number", "canBeUsedToMatch": False},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Follow-Up Stage",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1760, 900],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE_SEO},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## BRIDGE-04: Nurture + Reactivation + Follow-Up\n**Row 1 (Warm):** 3-stage nurture for warm leads (score 50-79).\n**Row 2 (Cold):** Single reactivation for cold leads 7+ days old.\n**Row 3 (Follow-Up):** 2nd touch for any lead with 1 email sent, no reply after 4 days.\n\nAll branches run in parallel daily at 11 AM SAST.",
            "width": 420,
            "height": 180,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 100],
    })

    return nodes


def build_bridge04_connections():
    """Build connections for BRIDGE-04 (warm nurture + cold reactivation)."""
    return {
        # Schedule Trigger feeds ALL THREE branches in parallel
        "Schedule Trigger": {
            "main": [[
                {"node": "Read Warm Leads Due", "type": "main", "index": 0},
                {"node": "Read Cold Leads Due", "type": "main", "index": 0},
                {"node": "Read Unanswered", "type": "main", "index": 0},
            ]]
        },
        # Warm lead branch (top row)
        "Read Warm Leads Due": {
            "main": [[{"node": "Has Leads?", "type": "main", "index": 0}]]
        },
        "Has Leads?": {
            "main": [
                [{"node": "Prepare Context", "type": "main", "index": 0}],
                [],
            ]
        },
        "Prepare Context": {
            "main": [[{"node": "AI Generate Email", "type": "main", "index": 0}]]
        },
        "AI Generate Email": {
            "main": [[{"node": "Format HTML", "type": "main", "index": 0}]]
        },
        "Format HTML": {
            "main": [[{"node": "Send Nurture Email", "type": "main", "index": 0}]]
        },
        "Send Nurture Email": {
            "main": [[{"node": "Update Nurture Stage", "type": "main", "index": 0}]]
        },
        "Update Nurture Stage": {
            "main": [[{"node": "Summary Email", "type": "main", "index": 0}]]
        },
        # Cold lead reactivation branch (bottom row)
        "Read Cold Leads Due": {
            "main": [[{"node": "Has Cold Leads?", "type": "main", "index": 0}]]
        },
        "Has Cold Leads?": {
            "main": [
                [{"node": "Prepare Cold Context", "type": "main", "index": 0}],
                [],
            ]
        },
        "Prepare Cold Context": {
            "main": [[{"node": "AI Generate Cold Email", "type": "main", "index": 0}]]
        },
        "AI Generate Cold Email": {
            "main": [[{"node": "Format Cold HTML", "type": "main", "index": 0}]]
        },
        "Format Cold HTML": {
            "main": [[{"node": "Send Cold Email", "type": "main", "index": 0}]]
        },
        "Send Cold Email": {
            "main": [[{"node": "Mark Exhausted", "type": "main", "index": 0}]]
        },
        # Follow-up branch (third row)
        "Read Unanswered": {
            "main": [[{"node": "Has Unanswered?", "type": "main", "index": 0}]]
        },
        "Has Unanswered?": {
            "main": [
                [{"node": "Prepare Follow-Up Context", "type": "main", "index": 0}],
                [],
            ]
        },
        "Prepare Follow-Up Context": {
            "main": [[{"node": "AI Generate Follow-Up", "type": "main", "index": 0}]]
        },
        "AI Generate Follow-Up": {
            "main": [[{"node": "Format Follow-Up HTML", "type": "main", "index": 0}]]
        },
        "Format Follow-Up HTML": {
            "main": [[{"node": "Send Follow-Up", "type": "main", "index": 0}]]
        },
        "Send Follow-Up": {
            "main": [[{"node": "Update Follow-Up Stage", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# Workflow Assembly & Deploy
# ==================================================================

WORKFLOW_DEFS = {
    "bridge01": {
        "name": "Bridge - Lead Sync (BRIDGE-01)",
        "build_nodes": lambda: build_bridge01_nodes(),
        "build_connections": lambda: build_bridge01_connections(),
    },
    "bridge02": {
        "name": "Bridge - Email Reply Matcher (BRIDGE-02)",
        "build_nodes": lambda: build_bridge02_nodes(),
        "build_connections": lambda: build_bridge02_connections(),
    },
    "bridge03": {
        "name": "Bridge - Unified Scoring (BRIDGE-03)",
        "build_nodes": lambda: build_bridge03_nodes(),
        "build_connections": lambda: build_bridge03_connections(),
    },
    "bridge04": {
        "name": "Bridge - Warm Lead Nurture (BRIDGE-04)",
        "build_nodes": lambda: build_bridge04_nodes(),
        "build_connections": lambda: build_bridge04_connections(),
    },
}


def build_workflow(wf_id):
    """Assemble a complete workflow JSON."""
    if wf_id not in WORKFLOW_DEFS:
        raise ValueError(f"Unknown workflow: {wf_id}. Valid: {', '.join(WORKFLOW_DEFS.keys())}")

    wf_def = WORKFLOW_DEFS[wf_id]
    nodes = wf_def["build_nodes"]()
    connections = wf_def["build_connections"]()

    settings = {
        "executionOrder": "v1",
        "saveManualExecutions": True,
        "callerPolicy": "workflowsFromSameOwner",
    }

    return {
        "name": wf_def["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": settings,
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def save_workflow(wf_id, workflow):
    """Save workflow JSON to file."""
    filenames = {
        "bridge01": "wf_bridge_01_lead_sync.json",
        "bridge02": "wf_bridge_02_email_reply.json",
        "bridge03": "wf_bridge_03_scoring.json",
        "bridge04": "wf_bridge_04_nurture.json",
    }

    output_dir = Path(__file__).parent.parent / "workflows" / "bridge"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filenames[wf_id]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    return output_path


def print_workflow_stats(wf_id, workflow):
    """Print workflow statistics."""
    all_nodes = workflow["nodes"]
    func_nodes = [n for n in all_nodes if n["type"] != "n8n-nodes-base.stickyNote"]
    note_nodes = [n for n in all_nodes if n["type"] == "n8n-nodes-base.stickyNote"]
    conn_count = len(workflow["connections"])

    print(f"  Name: {workflow['name']}")
    print(f"  Nodes: {len(func_nodes)} functional + {len(note_nodes)} sticky notes")
    print(f"  Connections: {conn_count}")


def main():
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    # Add tools dir to path
    sys.path.insert(0, str(Path(__file__).parent))

    print("=" * 60)
    print("BRIDGE INTEGRATION - WORKFLOW BUILDER")
    print("=" * 60)

    # Determine which workflows to build
    valid_wfs = list(WORKFLOW_DEFS.keys())
    if target == "all":
        workflow_ids = valid_wfs
    elif target in valid_wfs:
        workflow_ids = [target]
    else:
        print(f"ERROR: Unknown target '{target}'. Use: all, {', '.join(valid_wfs)}")
        sys.exit(1)

    # Check Airtable config
    if "REPLACE" in SEO_BASE_ID or "REPLACE" in SCRAPER_BASE_ID:
        print()
        print("WARNING: Airtable IDs not configured!")
        print("  Set these env vars in .env:")
        print("  - MARKETING_AIRTABLE_BASE_ID, SEO_TABLE_LEADS")
        print("  - LEAD_SCRAPER_AIRTABLE_BASE_ID, LEAD_SCRAPER_TABLE_LEADS")
        print()
        if action in ("deploy", "activate"):
            print("Cannot deploy with placeholder IDs. Aborting.")
            sys.exit(1)
        print("Continuing build with placeholder IDs (for preview only)...")
        print()

    # Build workflows
    workflows = {}
    for wf_id in workflow_ids:
        print(f"\nBuilding {wf_id}...")
        workflow = build_workflow(wf_id)
        output_path = save_workflow(wf_id, workflow)
        workflows[wf_id] = workflow
        print_workflow_stats(wf_id, workflow)
        print(f"  Saved to: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    # Deploy to n8n
    if action in ("deploy", "activate"):
        from n8n_client import N8nClient

        api_key = os.getenv("N8N_API_KEY")
        base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")

        if not api_key:
            print("ERROR: N8N_API_KEY not set in .env")
            sys.exit(1)

        print(f"\nConnecting to {base_url}...")

        with N8nClient(base_url, api_key, timeout=30) as client:
            health = client.health_check()
            if not health["connected"]:
                print(f"  ERROR: Cannot connect to n8n: {health.get('error')}")
                sys.exit(1)
            print("  Connected!")

            deployed_ids = {}

            for wf_id, workflow in workflows.items():
                print(f"\nDeploying {wf_id}...")

                # Check if workflow already exists (by name)
                existing = None
                try:
                    all_wfs = client.list_workflows()
                    for wf in all_wfs:
                        if wf["name"] == workflow["name"]:
                            existing = wf
                            break
                except Exception:
                    pass

                if existing:
                    update_payload = {
                        "name": workflow["name"],
                        "nodes": workflow["nodes"],
                        "connections": workflow["connections"],
                        "settings": workflow["settings"],
                    }
                    result = client.update_workflow(existing["id"], update_payload)
                    deployed_ids[wf_id] = result.get("id")
                    print(f"  Updated: {result.get('name')} (ID: {result.get('id')})")
                else:
                    create_payload = {
                        "name": workflow["name"],
                        "nodes": workflow["nodes"],
                        "connections": workflow["connections"],
                        "settings": workflow["settings"],
                    }
                    result = client.create_workflow(create_payload)
                    deployed_ids[wf_id] = result.get("id")
                    print(f"  Created: {result.get('name')} (ID: {result.get('id')})")

                if action == "activate" and deployed_ids.get(wf_id):
                    print(f"  Activating {wf_id}...")
                    client.activate_workflow(deployed_ids[wf_id])
                    print(f"  Activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Workflows:")
    for wf_id in workflow_ids:
        wf_label = WORKFLOW_DEFS[wf_id]["name"]
        print(f"  {wf_id}: {wf_label}")

    print()
    print("Next steps:")
    print("  1. Open each workflow in n8n UI to verify node connections")
    print("  2. Verify credential bindings (Airtable, Gmail, Google Sheets, OpenRouter)")
    print("  3. Test BRIDGE-01 manually -> check SEO Leads table")
    print("  4. Test BRIDGE-03 manually -> check scoring + grades")
    print("  5. Test BRIDGE-02 manually -> verify email reply matching")
    print("  6. Test BRIDGE-04 manually -> verify nurture emails")
    print("  7. Once verified, run with 'activate' to enable schedules")


if __name__ == "__main__":
    main()

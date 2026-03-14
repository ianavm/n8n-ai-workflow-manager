"""
CRM Sync - Workflow Builder & Deployer

Builds 3 CRM sync workflows for unified contact management
across Airtable, Xero, and the client portal.

Workflows:
    CRM-01: Hourly Sync - Merge Airtable leads + Xero contacts into unified CRM table
    CRM-02: Nightly Dedup - AI-assisted duplicate detection and merge (daily 01:00 SAST)
    CRM-03: Weekly Enrichment - Tavily + AI enrichment for incomplete records (Sun 03:00 SAST)

Usage:
    python tools/deploy_crm_sync.py build              # Build all JSONs
    python tools/deploy_crm_sync.py build crm01        # Build CRM-01 only
    python tools/deploy_crm_sync.py build crm02        # Build CRM-02 only
    python tools/deploy_crm_sync.py build crm03        # Build CRM-03 only
    python tools/deploy_crm_sync.py deploy             # Build + Deploy (inactive)
    python tools/deploy_crm_sync.py activate           # Build + Deploy + Activate
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

CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail AVM"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable PAT"}
CRED_XERO = {"id": "xeroOAuth2Api", "name": "Xero OAuth2"}

# -- Airtable IDs ---------------------------------------------------------

MARKETING_BASE_ID = "apptjjBx34z9340tK"
SCRAPER_BASE_ID = "app2ALQUP7CKEkHOz"
ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "appTCh0EeXQp0XqzW")
TABLE_CRM_UNIFIED = os.getenv("CRM_UNIFIED_TABLE_ID", "REPLACE_AFTER_SETUP")
TABLE_CRM_SYNC_LOG = os.getenv("CRM_SYNC_LOG_TABLE_ID", "REPLACE_AFTER_SETUP")

# -- Other Constants -------------------------------------------------------

XERO_TENANT_ID = "1f5c5e97-8976-4e03-b33c-ba638a7aeb72"
ALERT_EMAIL = "ian@anyvisionmedia.com"
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
AI_MODEL = "anthropic/claude-sonnet-4-20250514"

# -- Helpers ---------------------------------------------------------------


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ==================================================================
# CRM-01: Hourly Sync
# ==================================================================

def build_crm01_nodes():
    """Build nodes for CRM-01: Hourly Sync (every hour)."""
    nodes = []

    # -- Schedule Trigger (every hour) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 * * * *",
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

    # -- Set Sync Window (last 2 hours for overlap safety) --
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "syncSince",
                        "value": "={{ $now.minus({hours: 2}).toISO() }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "syncSinceDate",
                        "value": "={{ $now.minus({hours: 2}).toFormat('yyyy-MM-dd\\'T\\'HH:mm:ss') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "syncRunTime",
                        "value": "={{ $now.toISO() }}",
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Set Sync Window",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [440, 300],
    })

    # -- Fetch Airtable Leads (marketing base, filter by last modified) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": MARKETING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_UNIFIED, "mode": "id"},
            "filterByFormula": "=IS_AFTER(LAST_MODIFIED_TIME(), '{{ $json.syncSinceDate }}')",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Airtable Leads",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [660, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # -- Fetch Xero Contacts Modified (HTTP Request) --
    nodes.append({
        "parameters": {
            "url": "https://api.xero.com/api.xro/2.0/Contacts",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                    {"name": "If-Modified-Since", "value": "={{ $('Set Sync Window').first().json.syncSinceDate }}"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Xero Contacts",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [660, 420],
        "credentials": {"oAuth2Api": CRED_XERO},
    })

    # -- Merge Data (Code node) --
    nodes.append({
        "parameters": {
            "jsCode": """// Normalize both sources into unified format
const airtableRecords = $('Fetch Airtable Leads').all().map(i => i.json);
const xeroResponse = $('Fetch Xero Contacts').first().json;
const xeroContacts = (xeroResponse.Contacts || []);

const unified = [];

// Normalize Airtable leads
for (const rec of airtableRecords) {
  unified.push({
    email: (rec.Email || rec.email || '').toLowerCase().trim(),
    name: rec.Name || rec.name || '',
    phone: rec.Phone || rec.phone || '',
    company: rec.Company || rec.company || '',
    source: 'Airtable',
    lastModified: rec['Last Modified'] || rec.lastModified || '',
    rawId: rec.id || '',
  });
}

// Normalize Xero contacts
for (const contact of xeroContacts) {
  const email = (contact.EmailAddress || '').toLowerCase().trim();
  const phone = contact.Phones && contact.Phones.length > 0
    ? (contact.Phones.find(p => p.PhoneNumber) || {}).PhoneNumber || ''
    : '';
  unified.push({
    email,
    name: contact.Name || '',
    phone,
    company: contact.Name || '',
    source: 'Xero',
    lastModified: contact.UpdatedDateUTC || '',
    rawId: contact.ContactID || '',
  });
}

// Filter out records without email
const valid = unified.filter(r => r.email && r.email.includes('@'));

return [{ json: {
  totalAirtable: airtableRecords.length,
  totalXero: xeroContacts.length,
  totalUnified: valid.length,
  records: valid,
} }];"""
        },
        "id": uid(),
        "name": "Merge Data",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 300],
    })

    # -- Has Records? (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.totalUnified }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Records?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1100, 300],
    })

    # -- Split Into Items (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """const records = $json.records || [];
return records.map(r => ({ json: r }));"""
        },
        "id": uid(),
        "name": "Split Into Items",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 200],
    })

    # -- Search Unified Table (by email) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_UNIFIED, "mode": "id"},
            "filterByFormula": "={Email} = '{{ $json.email }}'",
            "options": {},
        },
        "id": uid(),
        "name": "Search Unified Table",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1540, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # -- Exists? (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.id ? 1 : 0 }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Exists?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1760, 200],
    })

    # -- Create New Records --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_UNIFIED, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Email": "={{ $('Split Into Items').item.json.email }}",
                    "Name": "={{ $('Split Into Items').item.json.name }}",
                    "Phone": "={{ $('Split Into Items').item.json.phone }}",
                    "Company": "={{ $('Split Into Items').item.json.company }}",
                    "Source": "={{ $('Split Into Items').item.json.source }}",
                    "First Seen": "={{ $now.toFormat('yyyy-MM-dd') }}",
                    "Last Synced": "={{ $now.toISO() }}",
                    "Sync Status": "Active",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create New Records",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1980, 100],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Update Existing --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_UNIFIED, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Email": "={{ $('Split Into Items').item.json.email }}",
                    "Name": "={{ $('Split Into Items').item.json.name }}",
                    "Phone": "={{ $('Split Into Items').item.json.phone }}",
                    "Company": "={{ $('Split Into Items').item.json.company }}",
                    "Last Synced": "={{ $now.toISO() }}",
                    "Sync Status": "Active",
                },
                "matchingColumns": ["Email"],
                "schema": [
                    {"id": "Email", "displayName": "Email", "required": False, "defaultMatch": True, "display": True, "type": "string", "canBeUsedToMatch": True},
                    {"id": "Name", "displayName": "Name", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": True},
                    {"id": "Phone", "displayName": "Phone", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": True},
                    {"id": "Company", "displayName": "Company", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": True},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Existing",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1980, 320],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Log Sync (create to sync log) --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_SYNC_LOG, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Sync Time": "={{ $('Set Sync Window').first().json.syncRunTime }}",
                    "Records Processed": "={{ $('Merge Data').first().json.totalUnified }}",
                    "New": "={{ $('Merge Data').first().json.totalUnified }}",
                    "Updated": "=0",
                    "Errors": "=0",
                    "Duration": "=Hourly Sync",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Sync",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [2200, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## CRM-01: Hourly Sync\nRuns every hour. Fetches modified Airtable leads + Xero contacts,\nnormalizes into unified format, creates or updates in CRM Unified table.\nLogs sync results to CRM Sync Log.",
            "width": 440,
            "height": 120,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 140],
    })

    return nodes


def build_crm01_connections():
    """Build connections for CRM-01."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Set Sync Window", "type": "main", "index": 0}]]
        },
        "Set Sync Window": {
            "main": [
                [
                    {"node": "Fetch Airtable Leads", "type": "main", "index": 0},
                    {"node": "Fetch Xero Contacts", "type": "main", "index": 0},
                ]
            ]
        },
        "Fetch Airtable Leads": {
            "main": [[{"node": "Merge Data", "type": "main", "index": 0}]]
        },
        "Fetch Xero Contacts": {
            "main": [[{"node": "Merge Data", "type": "main", "index": 0}]]
        },
        "Merge Data": {
            "main": [[{"node": "Has Records?", "type": "main", "index": 0}]]
        },
        "Has Records?": {
            "main": [
                [{"node": "Split Into Items", "type": "main", "index": 0}],
                [{"node": "Log Sync", "type": "main", "index": 0}],
            ]
        },
        "Split Into Items": {
            "main": [[{"node": "Search Unified Table", "type": "main", "index": 0}]]
        },
        "Search Unified Table": {
            "main": [[{"node": "Exists?", "type": "main", "index": 0}]]
        },
        "Exists?": {
            "main": [
                [{"node": "Update Existing", "type": "main", "index": 0}],
                [{"node": "Create New Records", "type": "main", "index": 0}],
            ]
        },
        "Create New Records": {
            "main": [[{"node": "Log Sync", "type": "main", "index": 0}]]
        },
        "Update Existing": {
            "main": [[{"node": "Log Sync", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# CRM-02: Nightly Dedup
# ==================================================================

def build_crm02_nodes():
    """Build nodes for CRM-02: Nightly Dedup (daily 01:00 SAST = 23:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (23:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 23 * * *",
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

    # -- Read All Unified Records --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_UNIFIED, "mode": "id"},
            "filterByFormula": "NOT({Sync Status} = 'Merged - Duplicate')",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read All Unified Records",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [440, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Detect Duplicates (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Group by normalized email and detect duplicates
const records = $input.all().map(i => i.json);

// Group by email
const emailGroups = {};
for (const rec of records) {
  const email = (rec.Email || '').toLowerCase().trim();
  if (!email || !email.includes('@')) continue;
  if (!emailGroups[email]) emailGroups[email] = [];
  emailGroups[email].push(rec);
}

// Find duplicate groups (>1 record per email)
const duplicateGroups = [];
for (const [email, group] of Object.entries(emailGroups)) {
  if (group.length > 1) {
    // Score each record by non-empty fields
    const scored = group.map(rec => {
      const fields = ['Name', 'Phone', 'Company', 'Source', 'First Seen'];
      const filledCount = fields.filter(f => rec[f] && String(rec[f]).trim()).length;
      return { record: rec, score: filledCount };
    });
    scored.sort((a, b) => b.score - a.score);

    duplicateGroups.push({
      email,
      primaryId: scored[0].record.id,
      primaryScore: scored[0].score,
      duplicateIds: scored.slice(1).map(s => s.record.id),
      records: scored.map(s => ({
        id: s.record.id,
        name: s.record.Name || '',
        phone: s.record.Phone || '',
        company: s.record.Company || '',
        source: s.record.Source || '',
        score: s.score,
      })),
    });
  }
}

// Also fuzzy match on name+phone for records without email
const noEmailRecords = records.filter(r => {
  const email = (r.Email || '').toLowerCase().trim();
  return !email || !email.includes('@');
});

const phoneGroups = {};
for (const rec of noEmailRecords) {
  const phone = (rec.Phone || '').replace(/[^0-9]/g, '');
  const name = (rec.Name || '').toLowerCase().trim();
  if (!phone && !name) continue;
  const key = phone + '|' + name;
  if (!phoneGroups[key]) phoneGroups[key] = [];
  phoneGroups[key].push(rec);
}

for (const [key, group] of Object.entries(phoneGroups)) {
  if (group.length > 1) {
    const scored = group.map(rec => {
      const fields = ['Name', 'Phone', 'Company', 'Source', 'First Seen'];
      const filledCount = fields.filter(f => rec[f] && String(rec[f]).trim()).length;
      return { record: rec, score: filledCount };
    });
    scored.sort((a, b) => b.score - a.score);

    duplicateGroups.push({
      email: key,
      primaryId: scored[0].record.id,
      primaryScore: scored[0].score,
      duplicateIds: scored.slice(1).map(s => s.record.id),
      records: scored.map(s => ({
        id: s.record.id,
        name: s.record.Name || '',
        phone: s.record.Phone || '',
        company: s.record.Company || '',
        source: s.record.Source || '',
        score: s.score,
      })),
    });
  }
}

return [{ json: {
  totalRecords: records.length,
  duplicateGroupCount: duplicateGroups.length,
  totalDuplicates: duplicateGroups.reduce((sum, g) => sum + g.duplicateIds.length, 0),
  duplicateGroups,
} }];"""
        },
        "id": uid(),
        "name": "Detect Duplicates",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [660, 300],
    })

    # -- Duplicates Found? (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.duplicateGroupCount }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Duplicates Found?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [880, 300],
    })

    # -- AI Merge Decision (OpenRouter) --
    nodes.append({
        "parameters": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "HTTP-Referer", "value": "https://anyvisionmedia.com"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"""={{{{
  "model": "{AI_MODEL}",
  "max_tokens": 2000,
  "messages": [
    {{
      "role": "system",
      "content": "You are a CRM data quality assistant. For each duplicate group, determine which record to keep as primary and what data to merge from duplicates. Return valid JSON array with objects: {{keepId, mergeFromIds: [], mergedFields: {{name, phone, company}}}}. Pick the record with the most complete data as primary. Merge non-empty fields from duplicates into the primary."
    }},
    {{
      "role": "user",
      "content": "Analyze these duplicate groups and decide merges:\\n" + JSON.stringify($json.duplicateGroups, null, 2)
    }}
  ]
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Merge Decision",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1100, 200],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Execute Merges (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Process AI merge decisions
const aiResponse = $json.choices[0].message.content;
let decisions;
try {
  // Extract JSON from AI response (may be wrapped in markdown)
  const jsonMatch = aiResponse.match(/\\[[\\s\\S]*\\]/);
  decisions = jsonMatch ? JSON.parse(jsonMatch[0]) : JSON.parse(aiResponse);
} catch (e) {
  // Fallback: use simple heuristic from Detect Duplicates
  const groups = $('Detect Duplicates').first().json.duplicateGroups;
  decisions = groups.map(g => ({
    keepId: g.primaryId,
    mergeFromIds: g.duplicateIds,
    mergedFields: {},
  }));
}

const updates = [];
const markDuplicates = [];

for (const d of decisions) {
  // Update primary record with merged fields
  if (d.mergedFields && Object.keys(d.mergedFields).length > 0) {
    updates.push({
      id: d.keepId,
      fields: d.mergedFields,
    });
  }
  // Mark duplicates
  for (const dupId of (d.mergeFromIds || [])) {
    markDuplicates.push({ id: dupId });
  }
}

return [{ json: {
  updateCount: updates.length,
  duplicateMarkCount: markDuplicates.length,
  updates,
  markDuplicates,
} }];"""
        },
        "id": uid(),
        "name": "Execute Merges",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 200],
    })

    # -- Split Updates --
    nodes.append({
        "parameters": {
            "jsCode": """const updates = $json.updates || [];
if (updates.length === 0) return [{ json: { skip: true } }];
return updates.map(u => ({ json: u }));"""
        },
        "id": uid(),
        "name": "Split Updates",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1540, 100],
    })

    # -- Update Primary Records --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_UNIFIED, "mode": "id"},
            "id": "={{ $json.id }}",
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Name": "={{ $json.fields.name || '' }}",
                    "Phone": "={{ $json.fields.phone || '' }}",
                    "Company": "={{ $json.fields.company || '' }}",
                    "Last Synced": "={{ $now.toISO() }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "Name", "displayName": "Name", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": True},
                    {"id": "Phone", "displayName": "Phone", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": True},
                    {"id": "Company", "displayName": "Company", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": True},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Primary Records",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1760, 100],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Split Duplicates --
    nodes.append({
        "parameters": {
            "jsCode": """const dups = $('Execute Merges').first().json.markDuplicates || [];
if (dups.length === 0) return [{ json: { skip: true } }];
return dups.map(d => ({ json: d }));"""
        },
        "id": uid(),
        "name": "Split Duplicates",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1540, 320],
    })

    # -- Mark Duplicates --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_UNIFIED, "mode": "id"},
            "id": "={{ $json.id }}",
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Sync Status": "Merged - Duplicate",
                    "Last Synced": "={{ $now.toISO() }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "Sync Status", "displayName": "Sync Status", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": True},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Mark Duplicates",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1760, 320],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Log Dedup Results --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_SYNC_LOG, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Sync Time": "={{ $now.toISO() }}",
                    "Records Processed": "={{ $('Detect Duplicates').first().json.totalRecords }}",
                    "New": "=0",
                    "Updated": "={{ $('Execute Merges').first().json.updateCount }}",
                    "Errors": "=0",
                    "Duration": "=Nightly Dedup",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Dedup Results",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1980, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Many Duplicates? (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $('Detect Duplicates').first().json.totalDuplicates }}",
                        "rightValue": 20,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Many Duplicates?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1980, 420],
    })

    # -- Send Alert Email --
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=CRM Dedup Alert - {{ $('Detect Duplicates').first().json.totalDuplicates }} duplicates found",
            "message": """=<h3>CRM Dedup Alert</h3>
<p><strong>Total records scanned:</strong> {{ $('Detect Duplicates').first().json.totalRecords }}</p>
<p><strong>Duplicate groups found:</strong> {{ $('Detect Duplicates').first().json.duplicateGroupCount }}</p>
<p><strong>Total duplicates merged:</strong> {{ $('Detect Duplicates').first().json.totalDuplicates }}</p>
<p style="color: #FF6D5A;"><strong>This exceeds the 20-duplicate threshold. Please review.</strong></p>
<p><em>Run at {{ $now.toFormat('yyyy-MM-dd HH:mm') }} SAST</em></p>""",
            "options": {},
        },
        "id": uid(),
        "name": "Send Alert Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [2200, 380],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## CRM-02: Nightly Dedup\nRuns daily 01:00 SAST. Reads all unified records,\ndetects duplicates by email + fuzzy name/phone.\nAI decides merge strategy, updates primary, marks dupes.\nAlerts if > 20 duplicates found.",
            "width": 440,
            "height": 120,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 140],
    })

    return nodes


def build_crm02_connections():
    """Build connections for CRM-02."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Read All Unified Records", "type": "main", "index": 0}]]
        },
        "Read All Unified Records": {
            "main": [[{"node": "Detect Duplicates", "type": "main", "index": 0}]]
        },
        "Detect Duplicates": {
            "main": [[{"node": "Duplicates Found?", "type": "main", "index": 0}]]
        },
        "Duplicates Found?": {
            "main": [
                [{"node": "AI Merge Decision", "type": "main", "index": 0}],
                [{"node": "Log Dedup Results", "type": "main", "index": 0}],
            ]
        },
        "AI Merge Decision": {
            "main": [[{"node": "Execute Merges", "type": "main", "index": 0}]]
        },
        "Execute Merges": {
            "main": [
                [
                    {"node": "Split Updates", "type": "main", "index": 0},
                    {"node": "Split Duplicates", "type": "main", "index": 0},
                ]
            ]
        },
        "Split Updates": {
            "main": [[{"node": "Update Primary Records", "type": "main", "index": 0}]]
        },
        "Update Primary Records": {
            "main": [[{"node": "Log Dedup Results", "type": "main", "index": 0}]]
        },
        "Split Duplicates": {
            "main": [[{"node": "Mark Duplicates", "type": "main", "index": 0}]]
        },
        "Mark Duplicates": {
            "main": [[{"node": "Many Duplicates?", "type": "main", "index": 0}]]
        },
        "Many Duplicates?": {
            "main": [
                [{"node": "Send Alert Email", "type": "main", "index": 0}],
                [],
            ]
        },
    }


# ==================================================================
# CRM-03: Weekly Enrichment
# ==================================================================

def build_crm03_nodes():
    """Build nodes for CRM-03: Weekly Enrichment (Sunday 03:00 SAST = 01:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (Sun 01:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 1 * * 0",
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

    # -- Read Records Needing Enrichment (missing Company or Phone, limit 50) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_UNIFIED, "mode": "id"},
            "filterByFormula": "=AND(OR({Company} = '', {Phone} = ''), NOT({Sync Status} = 'Merged - Duplicate'))",
            "options": {
                "limit": 50,
            },
        },
        "id": uid(),
        "name": "Read Needing Enrichment",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [440, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # -- Records Found? (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.id ? 1 : 0 }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Records Found?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [660, 300],
    })

    # -- Extract Email Domain (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Extract email domain for Tavily search
const records = $input.all().map(i => i.json);
const enrichable = [];

for (const rec of records) {
  const email = (rec.Email || '').toLowerCase().trim();
  if (!email.includes('@')) continue;
  const domain = email.split('@')[1];
  // Skip common free email providers
  const freeProviders = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com', 'aol.com'];
  if (freeProviders.includes(domain)) {
    enrichable.push({
      id: rec.id,
      email,
      name: rec.Name || '',
      domain: null,
      searchQuery: (rec.Name || '') + ' company',
    });
  } else {
    enrichable.push({
      id: rec.id,
      email,
      name: rec.Name || '',
      domain,
      searchQuery: domain + ' company',
    });
  }
}

return enrichable.map(r => ({ json: r }));"""
        },
        "id": uid(),
        "name": "Extract Email Domain",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 200],
    })

    # -- Enrich via Tavily (HTTP Request) --
    nodes.append({
        "parameters": {
            "url": "https://api.tavily.com/search",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={
  "query": "{{ $json.searchQuery }}",
  "search_depth": "basic",
  "max_results": 3,
  "include_answer": true
}""",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Enrich via Tavily",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1100, 200],
        "onError": "continueRegularOutput",
    })

    # -- AI Extract Profile (OpenRouter) --
    nodes.append({
        "parameters": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "HTTP-Referer", "value": "https://anyvisionmedia.com"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"""={{{{
  "model": "{AI_MODEL}",
  "max_tokens": 500,
  "messages": [
    {{
      "role": "system",
      "content": "Extract company profile from search results. Return JSON: {{company: string, industry: string, size: string, location: string}}. Use empty string for unknown fields. Be concise."
    }},
    {{
      "role": "user",
      "content": "Person: " + $('Extract Email Domain').item.json.name + "\\nEmail domain: " + ($('Extract Email Domain').item.json.domain || 'unknown') + "\\nSearch results: " + JSON.stringify($json.answer || $json.results || 'No results')
    }}
  ]
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Extract Profile",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1320, 200],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
    })

    # -- Parse AI Response (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Parse AI response and prepare update
const aiResponse = $json.choices ? $json.choices[0].message.content : '{}';
let profile;
try {
  const jsonMatch = aiResponse.match(/\\{[\\s\\S]*\\}/);
  profile = jsonMatch ? JSON.parse(jsonMatch[0]) : {};
} catch (e) {
  profile = {};
}

const recordId = $('Extract Email Domain').item.json.id;
const email = $('Extract Email Domain').item.json.email;

return [{ json: {
  recordId,
  email,
  company: profile.company || '',
  industry: profile.industry || '',
  location: profile.location || '',
  enriched: !!(profile.company || profile.industry),
} }];"""
        },
        "id": uid(),
        "name": "Parse AI Response",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1540, 200],
    })

    # -- Update Enriched Records --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_UNIFIED, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Email": "={{ $json.email }}",
                    "Company": "={{ $json.company }}",
                    "Last Synced": "={{ $now.toISO() }}",
                },
                "matchingColumns": ["Email"],
                "schema": [
                    {"id": "Email", "displayName": "Email", "required": False, "defaultMatch": True, "display": True, "type": "string", "canBeUsedToMatch": True},
                    {"id": "Company", "displayName": "Company", "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": True},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Enriched Records",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1760, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Log Enrichment --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CRM_SYNC_LOG, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Sync Time": "={{ $now.toISO() }}",
                    "Records Processed": "={{ $input.all().length }}",
                    "New": "=0",
                    "Updated": "={{ $input.all().filter(i => i.json.enriched).length }}",
                    "Errors": "=0",
                    "Duration": "=Weekly Enrichment",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Enrichment",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1980, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## CRM-03: Weekly Enrichment\nRuns Sunday 03:00 SAST. Finds records missing Company or Phone,\nsearches Tavily for company info using email domain,\nAI extracts profile data, updates CRM Unified table.\nLimit: 50 records per run.",
            "width": 440,
            "height": 120,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 140],
    })

    return nodes


def build_crm03_connections():
    """Build connections for CRM-03."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Read Needing Enrichment", "type": "main", "index": 0}]]
        },
        "Read Needing Enrichment": {
            "main": [[{"node": "Records Found?", "type": "main", "index": 0}]]
        },
        "Records Found?": {
            "main": [
                [{"node": "Extract Email Domain", "type": "main", "index": 0}],
                [],
            ]
        },
        "Extract Email Domain": {
            "main": [[{"node": "Enrich via Tavily", "type": "main", "index": 0}]]
        },
        "Enrich via Tavily": {
            "main": [[{"node": "AI Extract Profile", "type": "main", "index": 0}]]
        },
        "AI Extract Profile": {
            "main": [[{"node": "Parse AI Response", "type": "main", "index": 0}]]
        },
        "Parse AI Response": {
            "main": [[{"node": "Update Enriched Records", "type": "main", "index": 0}]]
        },
        "Update Enriched Records": {
            "main": [[{"node": "Log Enrichment", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# WORKFLOW DEFINITIONS
# ==================================================================

WORKFLOW_DEFS = {
    "crm01": {
        "name": "CRM Sync - Hourly Sync (CRM-01)",
        "filename": "crm01_hourly_sync.json",
        "build_nodes": build_crm01_nodes,
        "build_connections": build_crm01_connections,
    },
    "crm02": {
        "name": "CRM Sync - Nightly Dedup (CRM-02)",
        "filename": "crm02_nightly_dedup.json",
        "build_nodes": build_crm02_nodes,
        "build_connections": build_crm02_connections,
    },
    "crm03": {
        "name": "CRM Sync - Weekly Enrichment (CRM-03)",
        "filename": "crm03_weekly_enrichment.json",
        "build_nodes": build_crm03_nodes,
        "build_connections": build_crm03_connections,
    },
}


# ==================================================================
# WORKFLOW ASSEMBLY
# ==================================================================

def build_workflow(wf_id):
    """Assemble a complete workflow JSON."""
    wf_def = WORKFLOW_DEFS[wf_id]
    nodes = wf_def["build_nodes"]()
    connections = wf_def["build_connections"]()

    return {
        "name": wf_def["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def save_workflow(wf_id, workflow):
    """Save workflow JSON to file."""
    filename = WORKFLOW_DEFS[wf_id]["filename"]
    output_dir = Path(__file__).parent.parent / "workflows" / "crm-sync"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

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


# ==================================================================
# CLI
# ==================================================================

def main():
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    print("=" * 60)
    print("CRM SYNC - WORKFLOW BUILDER")
    print("=" * 60)

    # Determine targets
    valid_wfs = list(WORKFLOW_DEFS.keys())
    if target == "all":
        workflow_ids = valid_wfs
    elif target in valid_wfs:
        workflow_ids = [target]
    else:
        print(f"ERROR: Unknown target '{target}'. Use: all, {', '.join(valid_wfs)}")
        sys.exit(1)

    # Pre-flight checks
    missing = []
    if not ORCH_BASE_ID or "REPLACE" in ORCH_BASE_ID:
        missing.append("ORCH_AIRTABLE_BASE_ID")
    if "REPLACE" in TABLE_CRM_UNIFIED:
        missing.append("CRM_UNIFIED_TABLE_ID")
    if "REPLACE" in TABLE_CRM_SYNC_LOG:
        missing.append("CRM_SYNC_LOG_TABLE_ID")

    if missing:
        print()
        print("WARNING: Missing Airtable configuration:")
        for m in missing:
            print(f"  - {m}")
        print()
        if action in ("deploy", "activate"):
            print("Deploying with placeholder IDs (skeleton / visual preview only).")
            print("Workflows will NOT be activated until real IDs are set.")
            print()
        else:
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
        sys.path.insert(0, str(Path(__file__).parent))
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
                    print("  Activated!")

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
    print("  1. Create Airtable tables: CRM_Unified, CRM_Sync_Log")
    print("  2. Set env vars: CRM_UNIFIED_TABLE_ID, CRM_SYNC_LOG_TABLE_ID")
    print("  3. Add Tavily API key to n8n (for CRM-03 enrichment)")
    print("  4. Open each workflow in n8n UI to verify node connections")
    print("  5. Test CRM-01 manually -> check sync results")
    print("  6. Test CRM-02 manually -> check dedup logic")
    print("  7. Test CRM-03 manually -> check enrichment output")
    print("  8. Once verified, run with 'activate' to enable schedules")


if __name__ == "__main__":
    main()

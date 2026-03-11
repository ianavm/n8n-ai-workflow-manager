"""
WF-DI-03: Admin Review (Polls Google Sheets)

Polls the Review_Queue sheet every 5 minutes for admin-completed reviews.
When an admin fills in admin_action + admin_email, this workflow processes
the review: moves files, updates Document_Log, resolves Review_Queue.

Node count: ~14 functional + sticky notes
"""

import uuid
import json


def uid():
    return str(uuid.uuid4())


def build_nodes(config):
    """Build all nodes for WF-DI-03."""
    nodes = []

    # -- Sticky Notes --
    nodes.append({
        "parameters": {
            "content": "## WF-DI-03: Admin Review\n"
                       "Polls Review_Queue sheet for admin decisions.\n"
                       "Processes approvals, reclassifications, and errors.",
            "width": 450,
            "height": 100,
            "color": 3,
        },
        "id": uid(),
        "name": "Note - Overview",
        "type": "n8n-nodes-base.stickyNote",
        "position": [180, 80],
        "typeVersion": 1,
    })

    # ── 1. Schedule Trigger (every 5 min) ──────────────────────
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "minutes", "minutesInterval": 5}]
            }
        },
        "id": uid(),
        "name": "Poll Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # ── 2. Manual Trigger ──────────────────────────────────────
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [220, 500],
    })

    # ── 3. Read Review Queue ───────────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "read",
            "documentId": {
                "__rl": True,
                "value": config["di_sheets_id"],
                "mode": "id",
            },
            "sheetName": {
                "__rl": True,
                "value": config["tab_review_queue"],
                "mode": "name",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Read Review Queue",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [460, 300],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # ── 4. Filter Actionable Items ─────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// Filter for items where admin has filled in an action but status is still open
const items = $input.all();
const actionable = items.filter(item => {
  const row = item.json;
  return row.admin_action
    && row.admin_action.trim() !== ''
    && row.status === 'open'
    && row.admin_email
    && row.admin_email.trim() !== '';
});

if (actionable.length === 0) {
  return [{ json: { _noItems: true, count: 0 } }];
}

return actionable;
"""
        },
        "id": uid(),
        "name": "Filter Actionable",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [680, 300],
        "alwaysOutputData": True,
    })

    # ── 5. Has Items? ──────────────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json._noItems }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "notEquals",
                        },
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Items?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [900, 300],
    })

    # ── 6. Fetch Document Record ───────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "read",
            "documentId": {
                "__rl": True,
                "value": config["di_sheets_id"],
                "mode": "id",
            },
            "sheetName": {
                "__rl": True,
                "value": config["tab_document_log"],
                "mode": "name",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Read Document Log",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [1120, 300],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
        "alwaysOutputData": True,
    })

    # ── 7. Process Review Action ───────────────────────────────
    doc_type_folder_map_json = json.dumps(config["doc_type_folder_map"])
    nodes.append({
        "parameters": {
            "jsCode": f"""// Match review item to its document record and prepare updates
const reviewItem = $('Filter Actionable').first().json;
const allDocs = $input.all().map(i => i.json);

const docRecord = allDocs.find(d => d.doc_id === reviewItem.doc_id);

if (!docRecord) {{
  return [{{ json: {{ error: 'Document not found: ' + reviewItem.doc_id, reviewItem }} }}];
}}

const action = reviewItem.admin_action.trim().toLowerCase();
const docTypeFolderMap = {doc_type_folder_map_json};

let finalDocType = docRecord.doc_type;
let finalPropertyId = docRecord.property_id;
let status = 'processed';

if (action === 'reclassify' && reviewItem.correct_doc_type) {{
  finalDocType = reviewItem.correct_doc_type;
}}
if (reviewItem.correct_property_id) {{
  finalPropertyId = reviewItem.correct_property_id;
}}
if (action === 'flag_error') {{
  status = 'error';
}}

return [{{
  json: {{
    reviewId: reviewItem.review_id,
    docId: reviewItem.doc_id,
    action,
    adminEmail: reviewItem.admin_email,
    adminNotes: reviewItem.admin_notes || '',
    finalDocType,
    finalPropertyId,
    status,
    rawDriveFileId: docRecord.raw_drive_file_id,
    categoryFolder: docTypeFolderMap[finalDocType] || '10_Other',
    originalStatus: docRecord.status,
    originalDocType: docRecord.doc_type,
  }}
}}];
"""
        },
        "id": uid(),
        "name": "Process Action",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1340, 300],
    })

    # ── 8. Update Document_Log ─────────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "appendOrUpdate",
            "documentId": {
                "__rl": True,
                "value": config["di_sheets_id"],
                "mode": "id",
            },
            "sheetName": {
                "__rl": True,
                "value": config["tab_document_log"],
                "mode": "name",
            },
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "doc_id": "={{ $json.docId }}",
                    "doc_type": "={{ $json.finalDocType }}",
                    "property_id": "={{ $json.finalPropertyId }}",
                    "status": "={{ $json.status }}",
                    "reviewed_by": "={{ $json.adminEmail }}",
                    "reviewed_at": "={{ $now.toISO() }}",
                },
                "matchingColumns": ["doc_id"],
                "schema": [
                    {"id": "doc_id", "type": "string", "display": True, "displayName": "doc_id"},
                    {"id": "doc_type", "type": "string", "display": True, "displayName": "doc_type"},
                    {"id": "property_id", "type": "string", "display": True, "displayName": "property_id"},
                    {"id": "status", "type": "string", "display": True, "displayName": "status"},
                    {"id": "reviewed_by", "type": "string", "display": True, "displayName": "reviewed_by"},
                    {"id": "reviewed_at", "type": "string", "display": True, "displayName": "reviewed_at"},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Document Log",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [1560, 300],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    # ── 9. Resolve Review Queue Item ───────────────────────────
    nodes.append({
        "parameters": {
            "operation": "appendOrUpdate",
            "documentId": {
                "__rl": True,
                "value": config["di_sheets_id"],
                "mode": "id",
            },
            "sheetName": {
                "__rl": True,
                "value": config["tab_review_queue"],
                "mode": "name",
            },
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "review_id": "={{ $('Process Action').first().json.reviewId }}",
                    "status": "resolved",
                },
                "matchingColumns": ["review_id"],
                "schema": [
                    {"id": "review_id", "type": "string", "display": True, "displayName": "review_id"},
                    {"id": "status", "type": "string", "display": True, "displayName": "status"},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Resolve Review",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [1780, 300],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    # ── 10. Audit Log - Review Resolved ────────────────────────
    nodes.append({
        "parameters": {
            "operation": "append",
            "documentId": {
                "__rl": True,
                "value": config["di_sheets_id"],
                "mode": "id",
            },
            "sheetName": {
                "__rl": True,
                "value": config["tab_audit_log"],
                "mode": "name",
            },
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "audit_id": "=AUD-{{ $now.toMillis() }}-rev",
                    "timestamp": "={{ $now.toISO() }}",
                    "actor": "={{ $('Process Action').first().json.adminEmail }}",
                    "action": "review_resolved",
                    "doc_id": "={{ $('Process Action').first().json.docId }}",
                    "before_value": "={{ JSON.stringify({status: $('Process Action').first().json.originalStatus, doc_type: $('Process Action').first().json.originalDocType}) }}",
                    "after_value": "={{ JSON.stringify({status: $('Process Action').first().json.status, doc_type: $('Process Action').first().json.finalDocType, action: $('Process Action').first().json.action}) }}",
                    "notes": "={{ $('Process Action').first().json.adminNotes }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "audit_id", "type": "string", "display": True, "displayName": "audit_id"},
                    {"id": "timestamp", "type": "string", "display": True, "displayName": "timestamp"},
                    {"id": "actor", "type": "string", "display": True, "displayName": "actor"},
                    {"id": "action", "type": "string", "display": True, "displayName": "action"},
                    {"id": "doc_id", "type": "string", "display": True, "displayName": "doc_id"},
                    {"id": "before_value", "type": "string", "display": True, "displayName": "before_value"},
                    {"id": "after_value", "type": "string", "display": True, "displayName": "after_value"},
                    {"id": "notes", "type": "string", "display": True, "displayName": "notes"},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Audit Log - Review",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [2000, 300],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    # ── 11. Send Confirmation Email ────────────────────────────
    nodes.append({
        "parameters": {
            "sendTo": "={{ $('Process Action').first().json.adminEmail }}",
            "subject": "=Document Review Processed - {{ $('Process Action').first().json.docId }}",
            "emailType": "html",
            "message": "=<h3>Review Processed</h3><p>Document <strong>{{ $('Process Action').first().json.docId }}</strong> has been {{ $('Process Action').first().json.action }}d.</p><p>Type: {{ $('Process Action').first().json.finalDocType }}</p><p>Notes: {{ $('Process Action').first().json.adminNotes || 'None' }}</p><p style=\"color:#888; font-size:12px;\">Processed at {{ $now.toISO() }}</p>",
            "options": {},
        },
        "id": uid(),
        "name": "Confirm Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [2220, 300],
        "credentials": {
            "gmailOAuth2": config["cred_gmail"],
        },
    })

    return nodes


def build_connections(config):
    """Build connections for WF-DI-03."""
    return {
        "Poll Trigger": {
            "main": [[{"node": "Read Review Queue", "type": "main", "index": 0}]]
        },
        "Manual Trigger": {
            "main": [[{"node": "Read Review Queue", "type": "main", "index": 0}]]
        },
        "Read Review Queue": {
            "main": [[{"node": "Filter Actionable", "type": "main", "index": 0}]]
        },
        "Filter Actionable": {
            "main": [[{"node": "Has Items?", "type": "main", "index": 0}]]
        },
        "Has Items?": {
            "main": [
                # True - has actionable items
                [{"node": "Read Document Log", "type": "main", "index": 0}],
                # False - nothing to do
                [],
            ]
        },
        "Read Document Log": {
            "main": [[{"node": "Process Action", "type": "main", "index": 0}]]
        },
        "Process Action": {
            "main": [[{"node": "Update Document Log", "type": "main", "index": 0}]]
        },
        "Update Document Log": {
            "main": [[{"node": "Resolve Review", "type": "main", "index": 0}]]
        },
        "Resolve Review": {
            "main": [[{"node": "Audit Log - Review", "type": "main", "index": 0}]]
        },
        "Audit Log - Review": {
            "main": [[{"node": "Confirm Email", "type": "main", "index": 0}]]
        },
    }

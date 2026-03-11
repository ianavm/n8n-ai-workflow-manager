"""
WF-DI-01: Email Intake + Raw Storage

Monitors Outlook mailbox for emails with attachments, downloads them,
uploads to Google Drive Incoming_Documents/, checks for duplicates,
and triggers the Document Processing sub-workflow.

Node count: ~18 functional + sticky notes
"""

import uuid


def uid():
    return str(uuid.uuid4())


def build_nodes(config):
    """Build all nodes for WF-DI-01."""
    nodes = []

    # -- Sticky Notes for documentation --
    nodes.append({
        "parameters": {
            "content": "## WF-DI-01: Email Intake + Raw Storage\n"
                       "Monitors Outlook for emails with attachments.\n"
                       "Downloads, deduplicates, uploads to Google Drive,\n"
                       "and triggers WF-DI-02 for processing.",
            "width": 500,
            "height": 140,
            "color": 4,
        },
        "id": uid(),
        "name": "Note - Overview",
        "type": "n8n-nodes-base.stickyNote",
        "position": [180, 80],
        "typeVersion": 1,
    })

    # ── 1. Outlook Trigger ──────────────────────────────────────
    nodes.append({
        "parameters": {
            "pollTimes": {
                "item": [{"mode": "everyMinute"}]
            },
            "filters": {
                "hasAttachments": True,
            },
            "options": {
                "downloadAttachments": True,
            },
        },
        "id": uid(),
        "name": "Outlook Trigger",
        "type": "n8n-nodes-base.microsoftOutlookTrigger",
        "typeVersion": 1,
        "position": [220, 300],
        "credentials": {
            "microsoftOutlookOAuth2Api": config["cred_outlook"],
        },
    })

    # ── 2. Manual Trigger (testing) ─────────────────────────────
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [220, 500],
    })

    # ── 3. Prepare Email + Split Attachments ────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// Extract email metadata and split into one item per attachment
const items = $input.all();
const results = [];

for (const item of items) {
  const email = item.json;
  const senderEmail = email.sender?.emailAddress?.address
    || email.from?.emailAddress?.address || 'unknown';
  const senderName = email.sender?.emailAddress?.name
    || email.from?.emailAddress?.name || '';
  const subject = email.subject || '(no subject)';
  const receivedAt = email.receivedDateTime || email.createdDateTime || new Date().toISOString();
  const messageId = email.id || '';

  // Get all binary keys (attachments downloaded by trigger)
  const binaryKeys = item.binary ? Object.keys(item.binary) : [];

  if (binaryKeys.length === 0) {
    // No binary attachments - skip
    continue;
  }

  for (const binaryKey of binaryKeys) {
    const binaryData = item.binary[binaryKey];
    const fileName = binaryData.fileName || `attachment_${Date.now()}`;
    const mimeType = binaryData.mimeType || 'application/octet-stream';
    const fileSize = binaryData.fileSize || 0;

    results.push({
      json: {
        senderEmail,
        senderName,
        subject,
        receivedAt,
        messageId,
        fileName,
        mimeType,
        fileSize,
        binaryKey,
        intakeTimestamp: new Date().toISOString(),
      },
      binary: {
        data: binaryData,
      },
    });
  }
}

if (results.length === 0) {
  results.push({ json: { _noAttachments: true } });
}

return results;
"""
        },
        "id": uid(),
        "name": "Split Attachments",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [480, 300],
        "alwaysOutputData": True,
    })

    # ── 4. Has Attachments? ─────────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json._noAttachments }}",
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
        "name": "Has Attachments?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [700, 300],
    })

    # ── 5. Generate Doc ID + File Hash ──────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """const crypto = require('crypto');
const items = $input.all();
const results = [];

for (const item of items) {
  const binaryData = item.binary?.data;
  let fileHash = 'no_binary';

  if (binaryData && binaryData.data) {
    // binaryData.data is base64 encoded
    const buffer = Buffer.from(binaryData.data, 'base64');
    fileHash = crypto.createHash('sha256').update(buffer).digest('hex');
  }

  const random4 = Math.random().toString(36).slice(2, 6);
  const docId = `DOC-${Date.now()}-${random4}`;

  results.push({
    json: {
      ...item.json,
      docId,
      fileHash,
    },
    binary: item.binary,
  });
}

return results;
"""
        },
        "id": uid(),
        "name": "Generate Hash + ID",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [920, 300],
    })

    # ── 6. Check for Duplicate Hash ─────────────────────────────
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
        "position": [1140, 300],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # ── 7. Check Duplicate ──────────────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// Check if the file hash already exists in Document_Log
const currentItem = $('Generate Hash + ID').first().json;
const fileHash = currentItem.fileHash;
const existingDocs = $input.all().map(i => i.json);

const duplicate = existingDocs.find(doc =>
  doc.file_hash_sha256 === fileHash && doc.file_hash_sha256 !== 'no_binary'
);

return [{
  json: {
    ...currentItem,
    isDuplicate: !!duplicate,
    duplicateOfDocId: duplicate ? duplicate.doc_id : null,
  },
  binary: $('Generate Hash + ID').first().binary,
}];
"""
        },
        "id": uid(),
        "name": "Check Duplicate",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1360, 300],
    })

    # ── 8. Is Duplicate? ────────────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.isDuplicate }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "equals",
                        },
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Is Duplicate?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1580, 300],
    })

    # ── 9. Log Duplicate ────────────────────────────────────────
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
                "value": config["tab_duplicate_log"],
                "mode": "name",
            },
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "dupe_id": "=DUP-{{ $now.toMillis() }}",
                    "detected_at": "={{ $now.toISO() }}",
                    "original_doc_id": "={{ $json.duplicateOfDocId }}",
                    "duplicate_doc_id": "={{ $json.docId }}",
                    "file_hash": "={{ $json.fileHash }}",
                    "sender_email": "={{ $json.senderEmail }}",
                    "original_filename": "={{ $json.fileName }}",
                    "action_taken": "flagged",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "dupe_id", "type": "string", "display": True, "displayName": "dupe_id"},
                    {"id": "detected_at", "type": "string", "display": True, "displayName": "detected_at"},
                    {"id": "original_doc_id", "type": "string", "display": True, "displayName": "original_doc_id"},
                    {"id": "duplicate_doc_id", "type": "string", "display": True, "displayName": "duplicate_doc_id"},
                    {"id": "file_hash", "type": "string", "display": True, "displayName": "file_hash"},
                    {"id": "sender_email", "type": "string", "display": True, "displayName": "sender_email"},
                    {"id": "original_filename", "type": "string", "display": True, "displayName": "original_filename"},
                    {"id": "action_taken", "type": "string", "display": True, "displayName": "action_taken"},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Duplicate",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [1800, 200],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    # ── 10. Audit Log - Duplicate ───────────────────────────────
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
                    "audit_id": "=AUD-{{ $now.toMillis() }}-dup",
                    "timestamp": "={{ $now.toISO() }}",
                    "actor": "system",
                    "action": "duplicate_detected",
                    "doc_id": "={{ $json.docId }}",
                    "before_value": "",
                    "after_value": "={{ JSON.stringify({duplicate_of: $json.duplicateOfDocId, hash: $json.fileHash}) }}",
                    "notes": "Duplicate file detected during intake",
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
        "name": "Audit Log - Duplicate",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [2020, 200],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    # ── 11. Upload to Google Drive ──────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "upload",
            "name": "={{ $now.format('yyyyMMdd_HHmmss') + '_' + $json.fileName }}",
            "folderId": {
                "__rl": True,
                "value": config["di_incoming_folder_id"],
                "mode": "id",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Upload to Drive",
        "type": "n8n-nodes-base.googleDrive",
        "typeVersion": 3,
        "position": [1800, 400],
        "credentials": {
            "googleDriveOAuth2Api": config["cred_google_drive"],
        },
    })

    # ── 12. Build Document Log Entry ────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// Merge upload result with original metadata
const uploadResult = $input.first().json;
const original = $('Check Duplicate').first().json;

return [{
  json: {
    doc_id: original.docId,
    intake_timestamp: original.intakeTimestamp,
    sender_email: original.senderEmail,
    sender_name: original.senderName,
    email_subject: original.subject,
    original_filename: original.fileName,
    file_hash_sha256: original.fileHash,
    file_size_bytes: original.fileSize || 0,
    raw_drive_file_id: uploadResult.id || '',
    raw_drive_url: uploadResult.webViewLink || uploadResult.webContentLink || '',
    doc_type: '',
    doc_type_confidence: '',
    property_address: '',
    erf_number: '',
    unit_number: '',
    scheme_name: '',
    buyer_name: '',
    seller_name: '',
    agent_name: '',
    transaction_date: '',
    reference_number: '',
    property_id: '',
    final_drive_file_id: '',
    final_drive_url: '',
    status: 'pending',
    review_reason: '',
    reviewed_by: '',
    reviewed_at: '',
    error_message: '',
    mimeType: original.mimeType,
  }
}];
"""
        },
        "id": uid(),
        "name": "Build Log Entry",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2020, 400],
    })

    # ── 13. Log to Document_Log ─────────────────────────────────
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
                "value": config["tab_document_log"],
                "mode": "name",
            },
            "columns": {
                "mappingMode": "autoMapInputData",
                "value": {},
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log to Document_Log",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [2240, 400],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    # ── 14. Audit Log - Intake ──────────────────────────────────
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
                    "audit_id": "=AUD-{{ $now.toMillis() }}-int",
                    "timestamp": "={{ $now.toISO() }}",
                    "actor": "system",
                    "action": "intake",
                    "doc_id": "={{ $('Build Log Entry').first().json.doc_id }}",
                    "before_value": "",
                    "after_value": "={{ JSON.stringify({status: 'pending', file: $('Build Log Entry').first().json.original_filename}) }}",
                    "notes": "Document ingested from Outlook email",
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
        "name": "Audit Log - Intake",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [2460, 400],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    # ── 15. Trigger WF-DI-02 ───────────────────────────────────
    nodes.append({
        "parameters": {
            "workflowId": {
                "__rl": True,
                "value": config["wf_di_02_id"],
                "mode": "id",
            },
            "options": {
                "waitForSubWorkflow": False,
            },
        },
        "id": uid(),
        "name": "Trigger Processing",
        "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1.1,
        "position": [2680, 400],
    })

    return nodes


def build_connections(config):
    """Build connections for WF-DI-01."""
    return {
        "Outlook Trigger": {
            "main": [[{"node": "Split Attachments", "type": "main", "index": 0}]]
        },
        "Manual Trigger": {
            "main": [[{"node": "Split Attachments", "type": "main", "index": 0}]]
        },
        "Split Attachments": {
            "main": [[{"node": "Has Attachments?", "type": "main", "index": 0}]]
        },
        "Has Attachments?": {
            "main": [
                # True branch - has attachments
                [{"node": "Generate Hash + ID", "type": "main", "index": 0}],
                # False branch - no attachments, end
                [],
            ]
        },
        "Generate Hash + ID": {
            "main": [[{"node": "Read Document Log", "type": "main", "index": 0}]]
        },
        "Read Document Log": {
            "main": [[{"node": "Check Duplicate", "type": "main", "index": 0}]]
        },
        "Check Duplicate": {
            "main": [[{"node": "Is Duplicate?", "type": "main", "index": 0}]]
        },
        "Is Duplicate?": {
            "main": [
                # True branch - duplicate
                [{"node": "Log Duplicate", "type": "main", "index": 0}],
                # False branch - new document
                [{"node": "Upload to Drive", "type": "main", "index": 0}],
            ]
        },
        "Log Duplicate": {
            "main": [[{"node": "Audit Log - Duplicate", "type": "main", "index": 0}]]
        },
        "Upload to Drive": {
            "main": [[{"node": "Build Log Entry", "type": "main", "index": 0}]]
        },
        "Build Log Entry": {
            "main": [[{"node": "Log to Document_Log", "type": "main", "index": 0}]]
        },
        "Log to Document_Log": {
            "main": [[{"node": "Audit Log - Intake", "type": "main", "index": 0}]]
        },
        "Audit Log - Intake": {
            "main": [[{"node": "Trigger Processing", "type": "main", "index": 0}]]
        },
    }

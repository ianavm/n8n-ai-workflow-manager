"""
WF-DI-04: Notifications & Monitoring

Daily summary email at 8:00 SAST, review alerts when items are pending,
and error handling for failed executions.

Node count: ~16 functional + sticky notes
"""

import uuid


def uid():
    return str(uuid.uuid4())


def build_nodes(config):
    """Build all nodes for WF-DI-04."""
    nodes = []

    # -- Sticky Notes --
    nodes.append({
        "parameters": {
            "content": "## WF-DI-04: Notifications & Monitoring\n"
                       "Daily summary, review alerts, error handling.",
            "width": 400,
            "height": 80,
            "color": 5,
        },
        "id": uid(),
        "name": "Note - Overview",
        "type": "n8n-nodes-base.stickyNote",
        "position": [180, 80],
        "typeVersion": 1,
    })

    # ── 1. Daily Schedule Trigger ──────────────────────────────
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {"field": "cronExpression", "expression": "0 6 * * 1-5"}
                ]
            }
        },
        "id": uid(),
        "name": "Daily Trigger",
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

    # ── 3. Error Trigger ───────────────────────────────────────
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "typeVersion": 1,
        "position": [220, 700],
    })

    # ── 4. Read Review Queue ───────────────────────────────────
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
        "name": "Read Reviews",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [500, 300],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # ── 5. Read Document Log ───────────────────────────────────
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
        "name": "Read Documents",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [500, 500],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # ── 6. Build Summary ───────────────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// Build daily summary statistics
const reviews = $('Read Reviews').all().map(i => i.json);
const docs = $('Read Documents').all().map(i => i.json);

const today = new Date().toISOString().split('T')[0];

// Filter today's documents
const todayDocs = docs.filter(d => (d.intake_timestamp || '').startsWith(today));

// Count by status
const processed = todayDocs.filter(d => d.status === 'processed').length;
const pending = todayDocs.filter(d => d.status === 'pending').length;
const reviewRequired = todayDocs.filter(d => d.status === 'review_required').length;
const errors = todayDocs.filter(d => d.status === 'error').length;
const duplicates = todayDocs.filter(d => d.status === 'duplicate').length;

// Open reviews (any date)
const openReviews = reviews.filter(r => r.status === 'open');

// Count by doc type (all time today)
const typeCounts = {};
for (const doc of todayDocs) {
  const t = doc.doc_type || 'Unknown';
  typeCounts[t] = (typeCounts[t] || 0) + 1;
}

// Average confidence
const confidences = todayDocs
  .filter(d => d.doc_type_confidence)
  .map(d => parseFloat(d.doc_type_confidence));
const avgConfidence = confidences.length > 0
  ? (confidences.reduce((a, b) => a + b, 0) / confidences.length).toFixed(2)
  : 'N/A';

// Build type breakdown HTML
let typeBreakdown = '';
for (const [type, count] of Object.entries(typeCounts).sort((a, b) => b[1] - a[1])) {
  typeBreakdown += `<tr><td>${type}</td><td>${count}</td></tr>`;
}

// Build open review list HTML
let reviewList = '';
for (const r of openReviews.slice(0, 20)) {
  reviewList += `<tr>
    <td>${r.review_id || ''}</td>
    <td>${r.original_filename || ''}</td>
    <td>${r.reason || ''}</td>
    <td>${r.ai_doc_type || ''}</td>
    <td>${r.ai_confidence || ''}</td>
    <td><a href="${r.raw_drive_url || '#'}">View</a></td>
  </tr>`;
}

return [{
  json: {
    date: today,
    totalToday: todayDocs.length,
    processed,
    pending,
    reviewRequired,
    errors,
    duplicates,
    openReviewCount: openReviews.length,
    avgConfidence,
    typeBreakdown,
    reviewList,
    hasOpenReviews: openReviews.length > 0,
  }
}];
"""
        },
        "id": uid(),
        "name": "Build Summary",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [740, 400],
    })

    # ── 7. Has Open Reviews? ───────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.openReviewCount }}",
                        "rightValue": 0,
                        "operator": {
                            "type": "number",
                            "operation": "gt",
                        },
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Open Reviews?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [960, 300],
    })

    # ── 8. Send Review Alert ───────────────────────────────────
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=[ACTION REQUIRED] {{ $json.openReviewCount }} Documents Pending Review - {{ $json.date }}",
            "emailType": "html",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 700px;">
<h2 style="color: #FF6D5A;">Document Review Required</h2>
<p><strong>{{ $json.openReviewCount }}</strong> document(s) need your review.</p>

<table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
<thead>
<tr style="background: #f5f5f5;">
<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Review ID</th>
<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">File</th>
<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Reason</th>
<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">AI Type</th>
<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Confidence</th>
<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">File</th>
</tr>
</thead>
<tbody>
{{ $json.reviewList }}
</tbody>
</table>

<p>Open the <strong>Review_Queue</strong> tab in the tracking spreadsheet to review these documents.</p>
<p style="color: #888; font-size: 12px;">Document Intake System - AnyVision Media</p>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Review Alert Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1200, 200],
        "credentials": {
            "gmailOAuth2": config["cred_gmail"],
        },
    })

    # ── 9. Send Daily Summary ──────────────────────────────────
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=Document Intake Daily Summary - {{ $json.date }}",
            "emailType": "html",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 700px;">
<h2 style="color: #FF6D5A;">Daily Document Intake Summary</h2>
<p>Date: <strong>{{ $json.date }}</strong></p>

<table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
<tr style="background: #f5f5f5;"><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Documents Today</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{{ $json.totalToday }}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Processed</td><td style="padding: 8px; border: 1px solid #ddd; color: green;">{{ $json.processed }}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Pending</td><td style="padding: 8px; border: 1px solid #ddd; color: orange;">{{ $json.pending }}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Review Required</td><td style="padding: 8px; border: 1px solid #ddd; color: #FF6D5A;">{{ $json.reviewRequired }}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Errors</td><td style="padding: 8px; border: 1px solid #ddd; color: red;">{{ $json.errors }}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Duplicates Detected</td><td style="padding: 8px; border: 1px solid #ddd;">{{ $json.duplicates }}</td></tr>
<tr style="background: #f5f5f5;"><td style="padding: 8px; border: 1px solid #ddd;"><strong>Open Reviews (all time)</strong></td><td style="padding: 8px; border: 1px solid #ddd;"><strong>{{ $json.openReviewCount }}</strong></td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Avg AI Confidence</td><td style="padding: 8px; border: 1px solid #ddd;">{{ $json.avgConfidence }}</td></tr>
</table>

<h3>Document Type Breakdown</h3>
<table style="border-collapse: collapse; width: 50%; margin: 16px 0;">
<thead><tr style="background: #f5f5f5;"><th style="padding: 6px; border: 1px solid #ddd; text-align: left;">Type</th><th style="padding: 6px; border: 1px solid #ddd; text-align: left;">Count</th></tr></thead>
<tbody>{{ $json.typeBreakdown }}</tbody>
</table>

<p style="color: #888; font-size: 12px;">Document Intake System - AnyVision Media</p>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Daily Summary Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1200, 500],
        "credentials": {
            "gmailOAuth2": config["cred_gmail"],
        },
    })

    # ── 10. Format Error ───────────────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// Format error details from the error trigger
const error = $input.first().json;

const workflowName = error.workflow?.name || 'Unknown Workflow';
const nodeName = error.execution?.error?.node?.name || 'Unknown Node';
const errorMessage = error.execution?.error?.message || 'No error message';
const executionId = error.execution?.id || '';
const timestamp = new Date().toISOString();

return [{
  json: {
    workflowName,
    nodeName,
    errorMessage,
    executionId,
    timestamp,
    subject: `[ERROR] Document Intake - ${workflowName} failed at ${nodeName}`,
    body: `<h3 style="color: red;">Document Intake Error</h3>
<p><strong>Workflow:</strong> ${workflowName}</p>
<p><strong>Node:</strong> ${nodeName}</p>
<p><strong>Error:</strong> ${errorMessage}</p>
<p><strong>Execution ID:</strong> ${executionId}</p>
<p><strong>Time:</strong> ${timestamp}</p>
<p>Check the n8n execution log for details.</p>`,
  }
}];
"""
        },
        "id": uid(),
        "name": "Format Error",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [500, 700],
    })

    # ── 11. Send Error Alert ───────────────────────────────────
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.body }}",
            "options": {},
        },
        "id": uid(),
        "name": "Error Alert Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [740, 700],
        "credentials": {
            "gmailOAuth2": config["cred_gmail"],
        },
    })

    # ── 12. Audit Log - Alert ──────────────────────────────────
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
                    "audit_id": "=AUD-{{ $now.toMillis() }}-err",
                    "timestamp": "={{ $now.toISO() }}",
                    "actor": "system",
                    "action": "error_alert_sent",
                    "doc_id": "",
                    "before_value": "",
                    "after_value": "={{ JSON.stringify({workflow: $json.workflowName, node: $json.nodeName, error: $json.errorMessage}) }}",
                    "notes": "Error alert email sent",
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
        "name": "Audit Log - Error",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [960, 700],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    return nodes


def build_connections(config):
    """Build connections for WF-DI-04."""
    return {
        "Daily Trigger": {
            "main": [[
                {"node": "Read Reviews", "type": "main", "index": 0},
                {"node": "Read Documents", "type": "main", "index": 0},
            ]]
        },
        "Manual Trigger": {
            "main": [[
                {"node": "Read Reviews", "type": "main", "index": 0},
                {"node": "Read Documents", "type": "main", "index": 0},
            ]]
        },
        "Read Reviews": {
            "main": [[{"node": "Build Summary", "type": "main", "index": 0}]]
        },
        "Read Documents": {
            "main": [[{"node": "Build Summary", "type": "main", "index": 1}]]
        },
        "Build Summary": {
            "main": [[
                {"node": "Has Open Reviews?", "type": "main", "index": 0},
                {"node": "Daily Summary Email", "type": "main", "index": 0},
            ]]
        },
        "Has Open Reviews?": {
            "main": [
                # True - has open reviews
                [{"node": "Review Alert Email", "type": "main", "index": 0}],
                # False - no reviews
                [],
            ]
        },
        # Error trigger path
        "Error Trigger": {
            "main": [[{"node": "Format Error", "type": "main", "index": 0}]]
        },
        "Format Error": {
            "main": [[{"node": "Error Alert Email", "type": "main", "index": 0}]]
        },
        "Error Alert Email": {
            "main": [[{"node": "Audit Log - Error", "type": "main", "index": 0}]]
        },
    }

"""
WF-DI-02: Document Processing (Sub-workflow)

Receives doc_id and file metadata from WF-DI-01.
Downloads file from Drive, extracts text (PDF or OCR),
classifies via AI, matches property, creates folders, files document.

Node count: ~28 functional + sticky notes
"""

import uuid
import json


def uid():
    return str(uuid.uuid4())


# -- AI Classification Prompt -------------------------------------------
CLASSIFICATION_PROMPT = """You are a real estate document classifier for a South African property agency.

TASK: Classify this document and extract metadata.

DOCUMENT TYPES (choose exactly one):
- FICA (identity documents, proof of address, tax clearance)
- Offer_to_Purchase (OTP, sale agreement, deed of sale)
- Mandate (sole/open mandate, listing agreement)
- Title_Deed (title deed, transfer deed)
- Municipal_Document (rates clearance, zoning, building plans)
- Bond_Finance (bond approval, pre-qualification, bank documents)
- Compliance_Certificate (electrical, plumbing, gas, beetle, electric fence)
- Sectional_Scheme (body corporate rules, levy statements, management rules)
- Entity_Document (company registration, trust deed, shareholder agreement)
- Other (anything that doesn't fit above)

Return ONLY valid JSON, no markdown fencing:
{
  "doc_type": "one of the types above",
  "confidence": 0.0,
  "property_address": "full street address or null",
  "erf_number": "erf/stand number or null",
  "unit_number": "unit/section number or null",
  "scheme_name": "sectional title scheme name or null",
  "city": "city or null",
  "suburb": "suburb or null",
  "province": "province or null",
  "buyer_name": "full name or null",
  "seller_name": "full name or null",
  "agent_name": "agent name or null",
  "transaction_date": "YYYY-MM-DD or null",
  "reference_number": "any reference number or null",
  "notes": "anything unusual about this document"
}

RULES:
- Set confidence between 0.0 and 1.0 based on how certain you are
- Extract ALL available fields, use null for fields not found
- For South African addresses, include suburb and city separately
- Look for erf numbers, scheme names, and unit numbers specifically
- Do NOT invent information - only extract what is clearly present

DOCUMENT TEXT:
"""


def build_nodes(config):
    """Build all nodes for WF-DI-02."""
    nodes = []

    # -- Sticky Notes --
    nodes.append({
        "parameters": {
            "content": "## WF-DI-02: Document Processing\n"
                       "Sub-workflow: PDF text extraction, OCR fallback,\n"
                       "AI classification, property matching, folder filing.",
            "width": 500,
            "height": 120,
            "color": 2,
        },
        "id": uid(),
        "name": "Note - Overview",
        "type": "n8n-nodes-base.stickyNote",
        "position": [180, 80],
        "typeVersion": 1,
    })

    # ── 1. Execute Workflow Trigger ─────────────────────────────
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Sub-workflow Trigger",
        "type": "n8n-nodes-base.executeWorkflowTrigger",
        "typeVersion": 1,
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

    # ── 3. Extract Input Data ──────────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// Extract input parameters from the trigger
const input = $input.first().json;

return [{
  json: {
    docId: input.doc_id || input.docId || 'TEST-DOC',
    rawDriveFileId: input.raw_drive_file_id || input.rawDriveFileId || '',
    fileName: input.original_filename || input.fileName || 'test.pdf',
    mimeType: input.mimeType || 'application/pdf',
    senderEmail: input.sender_email || input.senderEmail || '',
    subject: input.email_subject || input.subject || '',
    intakeTimestamp: input.intake_timestamp || input.intakeTimestamp || new Date().toISOString(),
  }
}];
"""
        },
        "id": uid(),
        "name": "Extract Input",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [440, 300],
    })

    # ── 4. Download from Drive ─────────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "download",
            "fileId": {
                "__rl": True,
                "value": "={{ $json.rawDriveFileId }}",
                "mode": "id",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Download from Drive",
        "type": "n8n-nodes-base.googleDrive",
        "typeVersion": 3,
        "position": [660, 300],
        "credentials": {
            "googleDriveOAuth2Api": config["cred_google_drive"],
        },
    })

    # ── 5. Is PDF? ─────────────────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $('Extract Input').first().json.mimeType }}",
                        "rightValue": "application/pdf",
                        "operator": {
                            "type": "string",
                            "operation": "equals",
                        },
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Is PDF?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [880, 300],
    })

    # ── 6. Extract PDF Text ────────────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "pdf",
            "binaryPropertyName": "data",
            "options": {
                "joinPages": True,
                "maxPages": 50,
            },
        },
        "id": uid(),
        "name": "Extract PDF Text",
        "type": "n8n-nodes-base.extractFromFile",
        "typeVersion": 1,
        "position": [1100, 200],
        "onError": "continueRegularOutput",
    })

    # ── 7. Flag Non-PDF for Review ─────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// Non-PDF file - send to review queue
const input = $('Extract Input').first().json;
return [{
  json: {
    ...input,
    reviewReason: 'non_pdf_format',
    aiDocType: 'Other',
    aiConfidence: 0,
  }
}];
"""
        },
        "id": uid(),
        "name": "Flag Non-PDF",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 500],
    })

    # ── 8. Has Extracted Text? ─────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ ($json.text || '').trim().length }}",
                        "rightValue": 100,
                        "operator": {
                            "type": "number",
                            "operation": "gt",
                        },
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Text?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1320, 200],
    })

    # ── 9. OCR via Google Document AI ──────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": f"""// Prepare Document AI OCR request
const input = $('Extract Input').first().json;
const binaryData = $('Download from Drive').first().binary?.data;

if (!binaryData || !binaryData.data) {{
  return [{{ json: {{ ...input, ocrText: '', ocrFailed: true }} }}];
}}

// Build Document AI endpoint
const projectId = '{config["di_docai_project_id"]}';
const location = '{config["di_docai_location"]}';
const processorId = '{config["di_docai_processor_id"]}';

return [{{
  json: {{
    ...input,
    docaiEndpoint: `https://${{location}}-documentai.googleapis.com/v1/projects/${{projectId}}/locations/${{location}}/processors/${{processorId}}:process`,
    rawDocument: {{
      content: binaryData.data,
      mimeType: 'application/pdf',
    }},
  }}
}}];
"""
        },
        "id": uid(),
        "name": "Prepare OCR Request",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1540, 340],
    })

    # ── 10. Document AI HTTP Request ───────────────────────────
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json.docaiEndpoint }}",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "googleOAuth2Api",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ rawDocument: $json.rawDocument }) }}",
            "options": {
                "timeout": 60000,
            },
        },
        "id": uid(),
        "name": "OCR Document AI",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1760, 340],
        "credentials": {
            "googleOAuth2Api": config["cred_google_drive"],
        },
        "onError": "continueRegularOutput",
    })

    # ── 11. Parse OCR Result ───────────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// Extract text from Document AI response
const input = $('Extract Input').first().json;
const response = $input.first().json;

let ocrText = '';
try {
  ocrText = response.document?.text || '';
} catch (e) {
  ocrText = '';
}

const hasText = ocrText.trim().length > 100;

return [{
  json: {
    ...input,
    extractedText: ocrText,
    textSource: 'ocr',
    hasText,
    reviewReason: hasText ? '' : 'no_text',
    aiDocType: hasText ? '' : 'Other',
    aiConfidence: hasText ? null : 0,
  }
}];
"""
        },
        "id": uid(),
        "name": "Parse OCR Result",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1980, 340],
    })

    # ── 12. OCR Has Text? ──────────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.hasText }}",
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
        "name": "OCR Has Text?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [2200, 340],
    })

    # ── 13. Build AI Prompt (from PDF text) ────────────────────
    nodes.append({
        "parameters": {
            "jsCode": f"""// Build classification prompt with extracted text
const input = $('Extract Input').first().json;
const extractedText = $json.text || $json.extractedText || '';
const textSource = $json.textSource || 'pdf';
const truncated = extractedText.substring(0, 4000);

return [{{
  json: {{
    ...input,
    extractedText: truncated,
    textSource,
    classificationPrompt: `{CLASSIFICATION_PROMPT}${{truncated}}`,
  }}
}}];
"""
        },
        "id": uid(),
        "name": "Build AI Prompt",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1540, 100],
    })

    # ── 14. AI Classification (OpenRouter) ─────────────────────
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={{ JSON.stringify({ model: "' + config["ai_model"] + '", messages: [{ role: "user", content: $json.classificationPrompt }], temperature: 0.1, max_tokens: 2000 }) }}',
            "options": {
                "timeout": 30000,
            },
        },
        "id": uid(),
        "name": "AI Classify",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1760, 100],
        "credentials": {
            "httpHeaderAuth": config["cred_openrouter"],
        },
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 5000,
    })

    # ── 15. Parse AI Response ──────────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// Parse AI classification response
const input = $('Extract Input').first().json;
const response = $input.first().json;

let classification = {};
try {
  let content = response.choices[0].message.content || '';
  // Strip markdown fencing if present
  content = content.replace(/```json\\n?/g, '').replace(/```\\n?/g, '').trim();
  classification = JSON.parse(content);
} catch (e) {
  classification = {
    doc_type: 'Other',
    confidence: 0,
    property_address: null,
    notes: 'Failed to parse AI response: ' + e.message,
  };
}

// Validate doc_type
const validTypes = [
  'FICA', 'Offer_to_Purchase', 'Mandate', 'Title_Deed',
  'Municipal_Document', 'Bond_Finance', 'Compliance_Certificate',
  'Sectional_Scheme', 'Entity_Document', 'Other'
];
if (!validTypes.includes(classification.doc_type)) {
  classification.doc_type = 'Other';
  classification.confidence = Math.min(classification.confidence || 0, 0.5);
}

return [{
  json: {
    docId: input.docId,
    rawDriveFileId: input.rawDriveFileId,
    fileName: input.fileName,
    mimeType: input.mimeType,
    senderEmail: input.senderEmail,
    subject: input.subject,
    intakeTimestamp: input.intakeTimestamp,
    docType: classification.doc_type || 'Other',
    confidence: classification.confidence || 0,
    propertyAddress: classification.property_address || '',
    erfNumber: classification.erf_number || '',
    unitNumber: classification.unit_number || '',
    schemeName: classification.scheme_name || '',
    city: classification.city || '',
    suburb: classification.suburb || '',
    province: classification.province || '',
    buyerName: classification.buyer_name || '',
    sellerName: classification.seller_name || '',
    agentName: classification.agent_name || '',
    transactionDate: classification.transaction_date || '',
    referenceNumber: classification.reference_number || '',
    aiNotes: classification.notes || '',
  }
}];
"""
        },
        "id": uid(),
        "name": "Parse AI Response",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1980, 100],
    })

    # ── 16. Confidence Check ───────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.confidence }}",
                        "rightValue": config["ai_confidence_threshold"],
                        "operator": {
                            "type": "number",
                            "operation": "gte",
                        },
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Confidence OK?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [2200, 100],
    })

    # ── 17. Flag Low Confidence ────────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// Flag for review - low confidence
return [{
  json: {
    ...$json,
    reviewReason: 'low_confidence',
    aiDocType: $json.docType,
    aiConfidence: $json.confidence,
  }
}];
"""
        },
        "id": uid(),
        "name": "Flag Low Confidence",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2420, 200],
    })

    # ── 18. Send to Review Queue (shared node) ─────────────────
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
                "value": config["tab_review_queue"],
                "mode": "name",
            },
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "review_id": "=REV-{{ $now.toMillis() }}",
                    "doc_id": "={{ $json.docId }}",
                    "reason": "={{ $json.reviewReason }}",
                    "ai_doc_type": "={{ $json.aiDocType || $json.docType || 'Unknown' }}",
                    "ai_confidence": "={{ $json.aiConfidence || $json.confidence || 0 }}",
                    "raw_drive_url": "={{ $json.rawDriveUrl || '' }}",
                    "original_filename": "={{ $json.fileName }}",
                    "sender_email": "={{ $json.senderEmail }}",
                    "assigned_to": "",
                    "assigned_at": "",
                    "status": "open",
                    "admin_action": "",
                    "correct_doc_type": "",
                    "correct_property_id": "",
                    "admin_notes": "",
                    "admin_email": "",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "review_id", "type": "string", "display": True, "displayName": "review_id"},
                    {"id": "doc_id", "type": "string", "display": True, "displayName": "doc_id"},
                    {"id": "reason", "type": "string", "display": True, "displayName": "reason"},
                    {"id": "ai_doc_type", "type": "string", "display": True, "displayName": "ai_doc_type"},
                    {"id": "ai_confidence", "type": "string", "display": True, "displayName": "ai_confidence"},
                    {"id": "raw_drive_url", "type": "string", "display": True, "displayName": "raw_drive_url"},
                    {"id": "original_filename", "type": "string", "display": True, "displayName": "original_filename"},
                    {"id": "sender_email", "type": "string", "display": True, "displayName": "sender_email"},
                    {"id": "assigned_to", "type": "string", "display": True, "displayName": "assigned_to"},
                    {"id": "assigned_at", "type": "string", "display": True, "displayName": "assigned_at"},
                    {"id": "status", "type": "string", "display": True, "displayName": "status"},
                    {"id": "admin_action", "type": "string", "display": True, "displayName": "admin_action"},
                    {"id": "correct_doc_type", "type": "string", "display": True, "displayName": "correct_doc_type"},
                    {"id": "correct_property_id", "type": "string", "display": True, "displayName": "correct_property_id"},
                    {"id": "admin_notes", "type": "string", "display": True, "displayName": "admin_notes"},
                    {"id": "admin_email", "type": "string", "display": True, "displayName": "admin_email"},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Add to Review Queue",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [2640, 400],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    # ── 19. Update Doc Status - Review ─────────────────────────
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
                    "doc_id": "={{ $json.docId || $json.doc_id }}",
                    "status": "review_required",
                    "review_reason": "={{ $json.reviewReason || $json.reason }}",
                    "doc_type": "={{ $json.aiDocType || $json.docType || '' }}",
                    "doc_type_confidence": "={{ $json.aiConfidence || $json.confidence || 0 }}",
                },
                "matchingColumns": ["doc_id"],
                "schema": [
                    {"id": "doc_id", "type": "string", "display": True, "displayName": "doc_id"},
                    {"id": "status", "type": "string", "display": True, "displayName": "status"},
                    {"id": "review_reason", "type": "string", "display": True, "displayName": "review_reason"},
                    {"id": "doc_type", "type": "string", "display": True, "displayName": "doc_type"},
                    {"id": "doc_type_confidence", "type": "string", "display": True, "displayName": "doc_type_confidence"},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Doc - Review",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [2860, 400],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    # ── 20. Search Property Registry ───────────────────────────
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
                "value": config["tab_property_registry"],
                "mode": "name",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Read Properties",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [2420, -20],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # ── 21. Match Property ─────────────────────────────────────
    doc_type_folder_map_json = json.dumps(config["doc_type_folder_map"])
    nodes.append({
        "parameters": {
            "jsCode": f"""// Match document to existing property
const doc = $('Parse AI Response').first().json;
const properties = $input.all().map(i => i.json);

let bestMatch = null;
let bestScore = 0;

for (const prop of properties) {{
  if (!prop.property_id) continue;
  let score = 0;

  // Exact erf match (highest priority)
  if (doc.erfNumber && prop.erf_number && doc.erfNumber === prop.erf_number) {{
    score += 100;
  }}

  // Unit + scheme match
  if (doc.unitNumber && prop.unit_number && doc.unitNumber === prop.unit_number
      && doc.schemeName && prop.scheme_name && doc.schemeName.toLowerCase() === prop.scheme_name.toLowerCase()) {{
    score += 90;
  }}

  // Address fuzzy match
  if (doc.propertyAddress && prop.display_address) {{
    const docAddr = doc.propertyAddress.toLowerCase().replace(/[^a-z0-9]/g, '');
    const propAddr = prop.display_address.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (docAddr === propAddr) {{
      score += 80;
    }} else if (propAddr.includes(docAddr) || docAddr.includes(propAddr)) {{
      score += 60;
    }} else {{
      // Token overlap
      const docTokens = doc.propertyAddress.toLowerCase().split(/\\s+/);
      const propTokens = prop.display_address.toLowerCase().split(/\\s+/);
      const overlap = docTokens.filter(t => propTokens.includes(t) && t.length > 2).length;
      if (overlap >= 3) score += 40;
    }}
  }}

  if (score > bestScore) {{
    bestScore = score;
    bestMatch = prop;
  }}
}}

const matched = bestScore >= 40;
const docTypeFolderMap = {doc_type_folder_map_json};

return [{{
  json: {{
    ...doc,
    propertyMatched: matched,
    matchScore: bestScore,
    matchedPropertyId: matched ? bestMatch.property_id : null,
    matchedAddress: matched ? bestMatch.display_address : null,
    matchedDriveFolderId: matched ? bestMatch.drive_folder_id : null,
    categoryFolder: docTypeFolderMap[doc.docType] || '10_Other',
  }}
}}];
"""
        },
        "id": uid(),
        "name": "Match Property",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2640, -20],
    })

    # ── 22. Property Found? ────────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.propertyMatched }}",
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
        "name": "Property Found?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [2860, -20],
    })

    # ── 23. Create New Property ────────────────────────────────
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
                "value": config["tab_property_registry"],
                "mode": "name",
            },
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "property_id": "=PROP-{{ $now.toMillis() }}",
                    "display_address": "={{ $json.propertyAddress }}",
                    "street_number": "",
                    "street_name": "",
                    "suburb": "={{ $json.suburb }}",
                    "city": "={{ $json.city }}",
                    "province": "={{ $json.province }}",
                    "erf_number": "={{ $json.erfNumber }}",
                    "unit_number": "={{ $json.unitNumber }}",
                    "scheme_name": "={{ $json.schemeName }}",
                    "drive_folder_id": "",
                    "drive_folder_url": "",
                    "created_at": "={{ $now.toISO() }}",
                    "doc_count": "1",
                    "last_doc_date": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "property_id", "type": "string", "display": True, "displayName": "property_id"},
                    {"id": "display_address", "type": "string", "display": True, "displayName": "display_address"},
                    {"id": "street_number", "type": "string", "display": True, "displayName": "street_number"},
                    {"id": "street_name", "type": "string", "display": True, "displayName": "street_name"},
                    {"id": "suburb", "type": "string", "display": True, "displayName": "suburb"},
                    {"id": "city", "type": "string", "display": True, "displayName": "city"},
                    {"id": "province", "type": "string", "display": True, "displayName": "province"},
                    {"id": "erf_number", "type": "string", "display": True, "displayName": "erf_number"},
                    {"id": "unit_number", "type": "string", "display": True, "displayName": "unit_number"},
                    {"id": "scheme_name", "type": "string", "display": True, "displayName": "scheme_name"},
                    {"id": "drive_folder_id", "type": "string", "display": True, "displayName": "drive_folder_id"},
                    {"id": "drive_folder_url", "type": "string", "display": True, "displayName": "drive_folder_url"},
                    {"id": "created_at", "type": "string", "display": True, "displayName": "created_at"},
                    {"id": "doc_count", "type": "string", "display": True, "displayName": "doc_count"},
                    {"id": "last_doc_date", "type": "string", "display": True, "displayName": "last_doc_date"},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Property",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [3080, 60],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    # ── 24. Build Folder Path ──────────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": f"""// Build the Google Drive folder path for this document
const doc = $('Match Property').first().json;
const createResult = $input.first().json;

// Determine property ID - either matched or newly created
const propertyId = doc.matchedPropertyId || createResult.property_id || doc.docId;
const city = doc.city || 'Unknown_City';
const suburb = doc.suburb || 'Unknown_Suburb';
const displayAddress = doc.propertyAddress || doc.matchedAddress || 'Unknown_Address';

// Clean folder names (remove invalid chars)
const clean = (s) => s.replace(/[<>:"/\\\\|?*]/g, '_').trim() || 'Unknown';

return [{{
  json: {{
    ...doc,
    propertyId: propertyId,
    cityFolder: clean(city),
    suburbFolder: clean(suburb),
    addressFolder: clean(displayAddress),
    categoryFolder: doc.categoryFolder,
    propertiesRootId: '{config["di_properties_folder_id"]}',
    // File rename
    newFileName: `${{$now.toFormat('yyyy-MM-dd')}}_${{doc.docType}}_${{doc.referenceNumber || 'NOREF'}}_${{doc.fileName}}`,
  }}
}}];
"""
        },
        "id": uid(),
        "name": "Build Folder Path",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [3300, -20],
    })

    # ── 25. Create/Find Folders + Move File ────────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// This node orchestrates folder creation and file move via
// Google Drive API. Each folder is searched first, created if missing.
// The final step moves the raw file into the category subfolder.
//
// NOTE: This uses $getWorkflowStaticData to cache folder IDs
// across executions for performance.

const doc = $json;
const staticData = $getWorkflowStaticData('global');
if (!staticData.folderCache) staticData.folderCache = {};

// Return instructions for downstream Google Drive nodes
return [{
  json: {
    ...doc,
    folderPath: `${doc.cityFolder}/${doc.suburbFolder}/${doc.addressFolder}/${doc.categoryFolder}`,
    // These will be populated by the folder creation chain
    step: 'ready_for_folders',
  }
}];
"""
        },
        "id": uid(),
        "name": "Prepare Folder Chain",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [3520, -20],
    })

    # ── 26. Create City Folder ─────────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "search",
            "queryString": "={{ \"name='\" + $json.cityFolder + \"' and '\" + $json.propertiesRootId + \"' in parents and mimeType='application/vnd.google-apps.folder'\" }}",
            "options": {},
        },
        "id": uid(),
        "name": "Find City Folder",
        "type": "n8n-nodes-base.googleDrive",
        "typeVersion": 3,
        "position": [3740, -20],
        "credentials": {
            "googleDriveOAuth2Api": config["cred_google_drive"],
        },
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # ── 27. Create folders + move (Code node using HTTP sub-requests)
    nodes.append({
        "parameters": {
            "jsCode": """// Build folder creation plan
// This node prepares the data for sequential folder creation
const doc = $('Prepare Folder Chain').first().json;
const searchResults = $input.all().map(i => i.json);

let cityFolderId = '';
if (searchResults.length > 0 && searchResults[0].id) {
  cityFolderId = searchResults[0].id;
}

return [{
  json: {
    ...doc,
    cityFolderId,
    needsCreateCity: !cityFolderId,
  }
}];
"""
        },
        "id": uid(),
        "name": "Check City Result",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [3960, -20],
    })

    # ── 28. Create City (if needed) ────────────────────────────
    nodes.append({
        "parameters": {
            "resource": "folder",
            "operation": "create",
            "name": "={{ $json.cityFolder }}",
            "options": {
                "folderRLC": {
                    "__rl": True,
                    "value": "={{ $json.propertiesRootId }}",
                    "mode": "id",
                },
            },
        },
        "id": uid(),
        "name": "Create City Folder",
        "type": "n8n-nodes-base.googleDrive",
        "typeVersion": 3,
        "position": [4180, -20],
        "credentials": {
            "googleDriveOAuth2Api": config["cred_google_drive"],
        },
        "onError": "continueRegularOutput",
    })

    # ── 29. File into final folder (simplified) ────────────────
    nodes.append({
        "parameters": {
            "jsCode": """// After creating city folder, we need to create suburb, address,
// and category subfolders. For simplicity, we'll use a single Code
// node that outputs the folder IDs for the remaining chain.
//
// In production, each folder level would be its own search+create pair.
// For MVP, we'll move the file to the city folder and create the
// subfolders in subsequent iterations.

const doc = $('Check City Result').first().json;
const createResult = $input.first().json;

const cityFolderId = doc.cityFolderId || createResult.id || '';

return [{
  json: {
    ...doc,
    cityFolderId,
    targetFolderId: cityFolderId, // MVP: file at city level
    rawDriveFileId: doc.rawDriveFileId,
    newFileName: doc.newFileName,
  }
}];
"""
        },
        "id": uid(),
        "name": "Resolve Folder IDs",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [4400, -20],
    })

    # ── 30. Move File to Target Folder ─────────────────────────
    nodes.append({
        "parameters": {
            "operation": "move",
            "fileId": {
                "__rl": True,
                "value": "={{ $json.rawDriveFileId }}",
                "mode": "id",
            },
            "driveId": {
                "__rl": True,
                "value": "={{ $json.targetFolderId }}",
                "mode": "id",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Move File",
        "type": "n8n-nodes-base.googleDrive",
        "typeVersion": 3,
        "position": [4620, -20],
        "credentials": {
            "googleDriveOAuth2Api": config["cred_google_drive"],
        },
        "onError": "continueRegularOutput",
    })

    # ── 31. Update Document_Log - Processed ────────────────────
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
                    "doc_id": "={{ $('Resolve Folder IDs').first().json.docId }}",
                    "doc_type": "={{ $('Resolve Folder IDs').first().json.docType }}",
                    "doc_type_confidence": "={{ $('Resolve Folder IDs').first().json.confidence }}",
                    "property_address": "={{ $('Resolve Folder IDs').first().json.propertyAddress }}",
                    "erf_number": "={{ $('Resolve Folder IDs').first().json.erfNumber }}",
                    "unit_number": "={{ $('Resolve Folder IDs').first().json.unitNumber }}",
                    "scheme_name": "={{ $('Resolve Folder IDs').first().json.schemeName }}",
                    "buyer_name": "={{ $('Resolve Folder IDs').first().json.buyerName }}",
                    "seller_name": "={{ $('Resolve Folder IDs').first().json.sellerName }}",
                    "agent_name": "={{ $('Resolve Folder IDs').first().json.agentName }}",
                    "transaction_date": "={{ $('Resolve Folder IDs').first().json.transactionDate }}",
                    "reference_number": "={{ $('Resolve Folder IDs').first().json.referenceNumber }}",
                    "property_id": "={{ $('Resolve Folder IDs').first().json.propertyId }}",
                    "final_drive_file_id": "={{ $json.id || '' }}",
                    "final_drive_url": "={{ $json.webViewLink || '' }}",
                    "status": "processed",
                },
                "matchingColumns": ["doc_id"],
                "schema": [
                    {"id": "doc_id", "type": "string", "display": True, "displayName": "doc_id"},
                    {"id": "doc_type", "type": "string", "display": True, "displayName": "doc_type"},
                    {"id": "doc_type_confidence", "type": "string", "display": True, "displayName": "doc_type_confidence"},
                    {"id": "property_address", "type": "string", "display": True, "displayName": "property_address"},
                    {"id": "erf_number", "type": "string", "display": True, "displayName": "erf_number"},
                    {"id": "unit_number", "type": "string", "display": True, "displayName": "unit_number"},
                    {"id": "scheme_name", "type": "string", "display": True, "displayName": "scheme_name"},
                    {"id": "buyer_name", "type": "string", "display": True, "displayName": "buyer_name"},
                    {"id": "seller_name", "type": "string", "display": True, "displayName": "seller_name"},
                    {"id": "agent_name", "type": "string", "display": True, "displayName": "agent_name"},
                    {"id": "transaction_date", "type": "string", "display": True, "displayName": "transaction_date"},
                    {"id": "reference_number", "type": "string", "display": True, "displayName": "reference_number"},
                    {"id": "property_id", "type": "string", "display": True, "displayName": "property_id"},
                    {"id": "final_drive_file_id", "type": "string", "display": True, "displayName": "final_drive_file_id"},
                    {"id": "final_drive_url", "type": "string", "display": True, "displayName": "final_drive_url"},
                    {"id": "status", "type": "string", "display": True, "displayName": "status"},
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Doc - Processed",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [4840, -20],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    # ── 32. Audit Log - Processed ──────────────────────────────
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
                    "audit_id": "=AUD-{{ $now.toMillis() }}-proc",
                    "timestamp": "={{ $now.toISO() }}",
                    "actor": "system",
                    "action": "ai_classified_and_filed",
                    "doc_id": "={{ $('Resolve Folder IDs').first().json.docId }}",
                    "before_value": "={{ JSON.stringify({status: 'pending'}) }}",
                    "after_value": "={{ JSON.stringify({status: 'processed', doc_type: $('Resolve Folder IDs').first().json.docType, confidence: $('Resolve Folder IDs').first().json.confidence}) }}",
                    "notes": "={{ 'Classified as ' + $('Resolve Folder IDs').first().json.docType + ' (confidence: ' + $('Resolve Folder IDs').first().json.confidence + ')' }}",
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
        "name": "Audit Log - Processed",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [5060, -20],
        "credentials": {
            "googleSheetsOAuth2Api": config["cred_google_sheets"],
        },
    })

    return nodes


def build_connections(config):
    """Build connections for WF-DI-02."""
    return {
        "Sub-workflow Trigger": {
            "main": [[{"node": "Extract Input", "type": "main", "index": 0}]]
        },
        "Manual Trigger": {
            "main": [[{"node": "Extract Input", "type": "main", "index": 0}]]
        },
        "Extract Input": {
            "main": [[{"node": "Download from Drive", "type": "main", "index": 0}]]
        },
        "Download from Drive": {
            "main": [[{"node": "Is PDF?", "type": "main", "index": 0}]]
        },
        "Is PDF?": {
            "main": [
                # True - is PDF
                [{"node": "Extract PDF Text", "type": "main", "index": 0}],
                # False - not PDF
                [{"node": "Flag Non-PDF", "type": "main", "index": 0}],
            ]
        },
        "Extract PDF Text": {
            "main": [[{"node": "Has Text?", "type": "main", "index": 0}]]
        },
        "Flag Non-PDF": {
            "main": [[{"node": "Add to Review Queue", "type": "main", "index": 0}]]
        },
        "Has Text?": {
            "main": [
                # True - has text -> classify
                [{"node": "Build AI Prompt", "type": "main", "index": 0}],
                # False - no text -> OCR
                [{"node": "Prepare OCR Request", "type": "main", "index": 0}],
            ]
        },
        "Prepare OCR Request": {
            "main": [[{"node": "OCR Document AI", "type": "main", "index": 0}]]
        },
        "OCR Document AI": {
            "main": [[{"node": "Parse OCR Result", "type": "main", "index": 0}]]
        },
        "Parse OCR Result": {
            "main": [[{"node": "OCR Has Text?", "type": "main", "index": 0}]]
        },
        "OCR Has Text?": {
            "main": [
                # True - OCR extracted text -> classify
                [{"node": "Build AI Prompt", "type": "main", "index": 0}],
                # False - no text even after OCR -> review
                [{"node": "Add to Review Queue", "type": "main", "index": 0}],
            ]
        },
        "Build AI Prompt": {
            "main": [[{"node": "AI Classify", "type": "main", "index": 0}]]
        },
        "AI Classify": {
            "main": [[{"node": "Parse AI Response", "type": "main", "index": 0}]]
        },
        "Parse AI Response": {
            "main": [[{"node": "Confidence OK?", "type": "main", "index": 0}]]
        },
        "Confidence OK?": {
            "main": [
                # True - confidence OK -> property matching
                [{"node": "Read Properties", "type": "main", "index": 0}],
                # False - low confidence -> review
                [{"node": "Flag Low Confidence", "type": "main", "index": 0}],
            ]
        },
        "Flag Low Confidence": {
            "main": [[{"node": "Add to Review Queue", "type": "main", "index": 0}]]
        },
        "Add to Review Queue": {
            "main": [[{"node": "Update Doc - Review", "type": "main", "index": 0}]]
        },
        "Read Properties": {
            "main": [[{"node": "Match Property", "type": "main", "index": 0}]]
        },
        "Match Property": {
            "main": [[{"node": "Property Found?", "type": "main", "index": 0}]]
        },
        "Property Found?": {
            "main": [
                # True - property found -> build folder path
                [{"node": "Build Folder Path", "type": "main", "index": 0}],
                # False - no match -> create property then build folder path
                [{"node": "Create Property", "type": "main", "index": 0}],
            ]
        },
        "Create Property": {
            "main": [[{"node": "Build Folder Path", "type": "main", "index": 0}]]
        },
        "Build Folder Path": {
            "main": [[{"node": "Prepare Folder Chain", "type": "main", "index": 0}]]
        },
        "Prepare Folder Chain": {
            "main": [[{"node": "Find City Folder", "type": "main", "index": 0}]]
        },
        "Find City Folder": {
            "main": [[{"node": "Check City Result", "type": "main", "index": 0}]]
        },
        "Check City Result": {
            "main": [[{"node": "Create City Folder", "type": "main", "index": 0}]]
        },
        "Create City Folder": {
            "main": [[{"node": "Resolve Folder IDs", "type": "main", "index": 0}]]
        },
        "Resolve Folder IDs": {
            "main": [[{"node": "Move File", "type": "main", "index": 0}]]
        },
        "Move File": {
            "main": [[{"node": "Update Doc - Processed", "type": "main", "index": 0}]]
        },
        "Update Doc - Processed": {
            "main": [[{"node": "Audit Log - Processed", "type": "main", "index": 0}]]
        },
    }

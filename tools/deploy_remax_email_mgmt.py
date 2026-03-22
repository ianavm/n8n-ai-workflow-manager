"""
RE/MAX Admin Email Management System
Master sub-workflow + per-agent template for RE/MAX admin staff.

Architecture:
    Master (1 instance) = Shared AI brain (Claude Sonnet via OpenRouter)
    Agent Template (6-10 instances) = Per-admin Outlook trigger + routing + filing

Features:
    - AI email classification with RE/MAX real estate categories
    - Professional draft replies with RE/MAX branding
    - Document detection + Google Drive filing (10 doc types)
    - Follow-up tracking with Google Calendar + shared tracker sheet
    - Outlook category routing (7 categories + Urgent)
    - Error logging to Google Sheets

Usage:
    python tools/deploy_remax_email_mgmt.py master build
    python tools/deploy_remax_email_mgmt.py master deploy
    python tools/deploy_remax_email_mgmt.py template build
    python tools/deploy_remax_email_mgmt.py template deploy
    python tools/deploy_remax_email_mgmt.py onboard "Sarah Jones" "sarah@remax.co.za" <outlook_cred_id>
"""

import json
import sys
import uuid
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# -- Credential Constants -------------------------------------------------

CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GOOGLE_SHEETS = {"id": "OkpDXxwI8WcUJp4P", "name": "Google Sheets AVM Tutorial"}
CRED_GOOGLE_CALENDAR = {"id": "I5zIYf0UxlkUt3KG", "name": "Google Calendar AVM Tutorial"}
CRED_GOOGLE_DRIVE = {
    "id": os.getenv("REMAX_GDRIVE_CRED_ID", "h1nJlw5vhziBMlh8"),
    "name": "Google Drive AVM Tutorial",
}

# Outlook credential placeholder (replaced per agent)
CRED_OUTLOOK_PLACEHOLDER = {
    "id": "YOUR_OUTLOOK_CREDENTIAL_ID",
    "name": "Outlook - AGENT_NAME_HERE",
}

# -- Sheet / Drive IDs ----------------------------------------------------

REMAX_SHEET_ID = os.getenv("REMAX_EMAIL_SHEET_ID", "REPLACE_AFTER_SETUP")
REMAX_DRIVE_ROOT = os.getenv("REMAX_DRIVE_ROOT_FOLDER", "REPLACE_AFTER_SETUP")
REMAX_MASTER_WF_ID = os.getenv("REMAX_MASTER_WF_ID", "REPLACE_AFTER_DEPLOY")

# Drive folder IDs per doc type (populated from env or placeholder)
DRIVE_FOLDER_MAP = {
    "FICA": os.getenv("REMAX_DRIVE_FICA", "REPLACE"),
    "Offer_to_Purchase": os.getenv("REMAX_DRIVE_OTP", "REPLACE"),
    "Mandate": os.getenv("REMAX_DRIVE_MANDATE", "REPLACE"),
    "Title_Deed": os.getenv("REMAX_DRIVE_TITLE_DEED", "REPLACE"),
    "Municipal": os.getenv("REMAX_DRIVE_MUNICIPAL", "REPLACE"),
    "Bond_Finance": os.getenv("REMAX_DRIVE_BOND", "REPLACE"),
    "Compliance_Cert": os.getenv("REMAX_DRIVE_COMPLIANCE", "REPLACE"),
    "Sectional_Scheme": os.getenv("REMAX_DRIVE_SECTIONAL", "REPLACE"),
    "Entity_Docs": os.getenv("REMAX_DRIVE_ENTITY", "REPLACE"),
    "Other": os.getenv("REMAX_DRIVE_OTHER", "REPLACE"),
}

# -- Helpers (reused from deploy_outlook_email_mgmt.py) --------------------


def uid():
    return str(uuid.uuid4())


def outlook_node(name, resource, operation, message_id_expr, position,
                 update_fields=None, additional_fields=None, cred=None):
    node = {
        "parameters": {
            "resource": resource,
            "operation": operation,
            "messageId": message_id_expr,
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.microsoftOutlook",
        "typeVersion": 2,
        "position": position,
        "credentials": {"microsoftOutlookOAuth2Api": cred or CRED_OUTLOOK_PLACEHOLDER},
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 1000,
    }
    if update_fields:
        node["parameters"]["updateFields"] = update_fields
    if additional_fields:
        node["parameters"]["additionalFields"] = additional_fields
    return node


def categorize_node(name, category, position, cred=None):
    return outlook_node(
        name, "message", "update",
        "={{ $json.original_message_id }}",
        position,
        update_fields={"categories": [category]},
        cred=cred,
    )


def mark_read_node(name, msg_id_expr, position, cred=None):
    return outlook_node(
        name, "message", "update",
        msg_id_expr, position,
        update_fields={"isRead": True},
        cred=cred,
    )


def if_node(name, conditions, combinator, position,
            type_validation="strict", case_sensitive=True):
    return {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": case_sensitive,
                    "leftValue": "",
                    "typeValidation": type_validation,
                },
                "conditions": conditions,
                "combinator": combinator,
            },
            "options": {},
        },
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": position,
    }


def noop_node(name, position):
    return {
        "parameters": {},
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": position,
    }


def cond(left, op_type, operation, right=None, cond_id=None):
    c = {
        "id": cond_id or uid(),
        "leftValue": left,
        "operator": {"type": op_type, "operation": operation},
    }
    if right is not None:
        c["rightValue"] = right
    return c


# -- RE/MAX System Prompt -------------------------------------------------

REMAX_SYSTEM_PROMPT = r"""You are the AI Email Assistant for a RE/MAX real estate franchise office in South Africa. You help admin staff manage their email communications with real estate agents, clients, and internal staff.

## Your Task
Analyze each incoming email and return ONLY a valid JSON object. No markdown, no backticks, no explanation.

## Office Context
- Company: RE/MAX (real estate franchise)
- Staff: Admin team supporting 30+ real estate agents
- Location: South Africa
- Common workflows: agent compliance (FICA), listing administration, commission processing, training coordination

## JSON Output Format
{
  "sender": "<email address>",
  "sender_name": "<display name>",
  "subject": "<subject line>",
  "intent": "<1 sentence: what the sender wants>",
  "tone": "<formal|informal|urgent|angry|friendly|neutral>",
  "urgency": "<high|medium|low>",
  "action_required": true or false,
  "category": "<ONE of: Agent_Compliance, Listing_Admin, Commission, Training, General_Inquiry, Internal, Spam>",
  "document_type": "<ONE of: FICA, Offer_to_Purchase, Mandate, Title_Deed, Municipal, Bond_Finance, Compliance_Cert, Sectional_Scheme, Entity_Docs, None>",
  "has_document": true or false,
  "tags": ["<from tag list below>"],
  "is_spam": true or false,
  "suggested_response": "<professional draft reply if action_required, else null>",
  "summary": "<1-2 sentence summary>",
  "escalation_needed": true or false,
  "follow_up_required": true or false,
  "follow_up_date": "<YYYY-MM-DD or null>",
  "follow_up_reason": "<why follow-up is needed, or null>"
}

## Category Classification Rules
- **Agent_Compliance**: FICA document submissions, compliance certificates, agent registration, license renewals, FFC (Fidelity Fund Certificates), regulatory requirements
- **Listing_Admin**: New mandates, sole/open mandate agreements, listing details, property photos, marketing requests, price changes, listing withdrawals
- **Commission**: Commission queries, commission statements, commission disputes, payment schedules, commission splits, referral fees
- **Training**: Training schedules, CPD (Continuing Professional Development) points, onboarding materials, exam registrations, workshop invitations
- **General_Inquiry**: Office matters, IT support, general questions, stationery requests, maintenance issues
- **Internal**: Inter-office communications, management directives, policy updates, meeting minutes, announcements
- **Spam**: Irrelevant external marketing, phishing, newsletters not subscribed to

## Document Type Detection Rules
Set has_document=true and document_type if the email:
- Has attachments AND mentions document-related keywords
- Explicitly states "attached is my FICA" / "please find the mandate" / etc.
- References a document type even without attachment (set has_document based on attachment info)

Document types:
- **FICA**: ID copies, proof of address, bank statements (for FICA compliance)
- **Offer_to_Purchase**: OTP, purchase agreements, sale agreements
- **Mandate**: Sole mandate, open mandate, listing agreement, agency agreement
- **Title_Deed**: Title deed copies, deed of transfer
- **Municipal**: Rates clearance, municipal accounts, zoning certificates
- **Bond_Finance**: Bond approvals, pre-qualification letters, finance documents
- **Compliance_Cert**: Compliance certificates, electrical COC, plumbing COC, beetle certificates
- **Sectional_Scheme**: Body corporate rules, levy statements, sectional title plans
- **Entity_Docs**: Trust deeds, company registration (CIPC), partnership agreements, resolutions
- **None**: No document detected

## Available Tags
Follow_Up, Deadline, Missing_Docs, New_Listing, Commission_Query, Compliance, Urgent, Agent_Onboarding, Price_Change, Withdrawal, Referral

## Urgency Rules
HIGH if:
- Deadline mentioned within 48 hours
- Compliance deadline approaching
- Commission dispute or payment issue
- Legal matter or regulatory requirement
- Words: "urgent", "ASAP", "immediately", "deadline"

## Follow-Up Detection Rules
Set follow_up_required=true if:
- Email mentions a deadline -> extract the date into follow_up_date (YYYY-MM-DD)
- Email requests documents that are not yet submitted -> follow_up_reason = "Waiting for [document type]"
- Email asks a question that needs a response -> follow_up_reason = "Response needed: [topic]"
- Agent promises to submit something -> follow_up_reason = "Agent to submit [item]"
If no specific date mentioned, set follow_up_date to null (the system will default to +2 business days).

## Response Writing Rules
When action_required is true, draft a professional reply:
- Address the agent/sender by name
- Be direct and professional (admin-to-agent tone)
- Reference specific documents or deadlines when relevant
- Include clear next steps or action items
- Keep it concise (3-4 paragraphs max)
- Use proper line breaks (\n\n between paragraphs)
- End with the admin's name (will be inserted by system)

When action_required is false or is_spam is true, set suggested_response to null.

CRITICAL: Return ONLY the JSON object. No other text."""

# -- RE/MAX Signature HTML -------------------------------------------------

REMAX_SIGNATURE_HTML = (
    '<table cellpadding="0" cellspacing="0" border="0" '
    'style="font-family:\'Segoe UI\',\'Helvetica Neue\',Arial,sans-serif;'
    'font-size:14px;line-height:1.4;color:#333333;">'
    '<tr>'
    '<td style="vertical-align:top;padding-right:18px;">'
    '<img src="https://upload.wikimedia.org/wikipedia/en/thumb/a/a5/'
    'RE/MAX_logo.svg/200px-RE/MAX_logo.svg.png" alt="RE/MAX" '
    'width="80" style="display:block;border:0;width:80px;" />'
    '</td>'
    '<td style="vertical-align:top;padding-left:18px;border-left:3px solid #DC3545;">'
    '<table cellpadding="0" cellspacing="0" border="0">'
    '<tr><td style="font-size:18px;font-weight:700;color:#003DA5;padding-bottom:2px;">'
    '{{ $json.agent_name || "Admin" }}</td></tr>'
    '<tr><td style="font-size:13px;color:#6B7280;padding-bottom:8px;">'
    'Administration&nbsp;&nbsp;&#183;&nbsp;&nbsp;'
    '<span style="color:#DC3545;font-weight:600;">RE/MAX</span></td></tr>'
    '<tr><td style="padding-bottom:8px;">'
    '<table cellpadding="0" cellspacing="0" border="0" width="160">'
    '<tr><td width="80" style="height:2px;background-color:#DC3545;font-size:0;'
    'line-height:0;">&nbsp;</td>'
    '<td width="80" style="height:2px;background-color:#003DA5;font-size:0;'
    'line-height:0;">&nbsp;</td></tr></table></td></tr>'
    '<tr><td style="font-size:12px;color:#333333;padding-bottom:2px;">'
    '<a href="mailto:{{ $json.agent_email || \'admin@remax.co.za\' }}" '
    'style="color:#003DA5;text-decoration:none;font-weight:500;">'
    '{{ $json.agent_email || "admin@remax.co.za" }}</a></td></tr>'
    '</table></td></tr></table>'
)

# -- JavaScript Code Blocks ------------------------------------------------

# Escape signature for JS template literal
_sig_js = REMAX_SIGNATURE_HTML.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

MASTER_PARSE_AI_JS = (
    r"""const items = $input.all();
const results = [];

for (const item of items) {
  const emailData = $('Execute Workflow Trigger').first().json;

  let parsed;
  try {
    let aiContent = item.json.output || '';
    if (!aiContent && item.json.choices) {
      aiContent = item.json.choices[0].message.content;
    }
    const cleaned = aiContent
      .replace(/```json\n?/g, '')
      .replace(/```\n?/g, '')
      .trim();
    parsed = JSON.parse(cleaned);
  } catch (e) {
    parsed = {
      sender: emailData.from || 'unknown',
      sender_name: 'Unknown',
      subject: emailData.subject || 'No Subject',
      intent: 'Classification failed - manual review required',
      tone: 'neutral',
      urgency: 'medium',
      action_required: true,
      category: 'General_Inquiry',
      document_type: 'None',
      has_document: false,
      tags: ['Follow_Up'],
      is_spam: false,
      suggested_response: null,
      summary: 'Email could not be auto-classified. Manual review required.',
      escalation_needed: true,
      follow_up_required: true,
      follow_up_date: null,
      follow_up_reason: 'Classification failed - needs manual review'
    };
  }

  results.push({
    json: {
      original_from: emailData.from || '',
      original_to: emailData.to || '',
      original_subject: emailData.subject || '',
      original_date: emailData.date || '',
      original_body: emailData.body || '',
      original_message_id: emailData.messageId || '',
      original_thread_id: emailData.threadId || '',
      has_original_attachments: emailData.hasAttachments || false,
      attachment_names: emailData.attachmentNames || '',
      agent_name: emailData.agentName || 'Admin',
      agent_email: emailData.agentEmail || '',
      sender: parsed.sender || emailData.from || '',
      sender_name: parsed.sender_name || 'Unknown',
      subject: parsed.subject || emailData.subject || '',
      intent: parsed.intent || '',
      tone: parsed.tone || 'neutral',
      urgency: parsed.urgency || 'medium',
      action_required: parsed.action_required || false,
      category: parsed.category || 'General_Inquiry',
      document_type: parsed.document_type || 'None',
      has_document: parsed.has_document || false,
      tags: parsed.tags || [],
      tags_string: (parsed.tags || []).join(', '),
      is_spam: parsed.is_spam || false,
      suggested_response: parsed.suggested_response || '',
      summary: parsed.summary || '',
      escalation_needed: parsed.escalation_needed || false,
      follow_up_required: parsed.follow_up_required || false,
      follow_up_date: parsed.follow_up_date || null,
      follow_up_reason: parsed.follow_up_reason || null,
      processed_at: new Date().toISOString()
    }
  });
}

return results;"""
)

MASTER_COMPUTE_FOLLOWUP_JS = r"""const items = $input.all();

return items.map(item => {
  const d = item.json;
  let follow_up_date = d.follow_up_date;

  // If follow-up required but no date, compute +2 business days
  if (d.follow_up_required && !follow_up_date) {
    const now = new Date();
    let daysAdded = 0;
    const target = new Date(now);
    while (daysAdded < 2) {
      target.setDate(target.getDate() + 1);
      const dow = target.getDay();
      if (dow !== 0 && dow !== 6) daysAdded++;
    }
    follow_up_date = target.toISOString().split('T')[0];
  }

  return {
    json: {
      ...d,
      follow_up_date
    }
  };
});"""

MASTER_BUILD_HTML_JS = (
    r"""const items = $input.all();

return items.map(item => {
  const d = item.json;
  const text = d.suggested_response || '';

  let html_response = '';
  if (text) {
    const paragraphs = text.split(/\n\n+/);
    const htmlParagraphs = paragraphs
      .map(p => p.replace(/\n/g, '<br>'))
      .map(p => '<p style="margin:0 0 12px 0;font-family:Segoe UI,Helvetica Neue,Arial,sans-serif;font-size:14px;line-height:1.5;color:#333333;">' + p + '</p>')
      .join('');
    const signature = `"""
    + _sig_js
    + r"""`;
    html_response = '<div style="font-family:Segoe UI,Helvetica Neue,Arial,sans-serif;">' + htmlParagraphs + '<br>' + signature + '</div>';
  }

  return {
    json: {
      ...d,
      html_response
    }
  };
});"""
)

TEMPLATE_PREPARE_EMAIL_JS = r"""// ---- CUSTOMIZE THESE PER AGENT ----
const AGENT_NAME = 'AGENT_NAME_HERE';
const AGENT_EMAIL = 'AGENT_EMAIL_HERE';
// ------------------------------------

const items = $input.all();
const results = [];

for (const item of items) {
  const senderAddress = item.json.sender?.emailAddress?.address
    || item.json.from?.emailAddress?.address || '';
  const senderName = item.json.sender?.emailAddress?.name
    || item.json.from?.emailAddress?.name || '';

  // Extract attachment info for AI prompt
  const attachmentNames = [];
  if (item.json.hasAttachments && item.binary) {
    for (const key of Object.keys(item.binary)) {
      attachmentNames.push(item.binary[key].fileName || key);
    }
  }

  const emailData = {
    from: senderName ? `${senderName} <${senderAddress}>` : senderAddress,
    to: (item.json.toRecipients || [])
      .map(r => r.emailAddress?.address || '').join(', '),
    subject: item.json.subject || '',
    date: item.json.receivedDateTime || item.json.createdDateTime
      || new Date().toISOString(),
    body: (item.json.bodyPreview
      || (item.json.body?.content || '').replace(/<[^>]*>/g, '')
      || '').substring(0, 3000),
    hasAttachments: item.json.hasAttachments || false,
    attachmentNames: attachmentNames.join(', '),
    messageId: item.json.id || '',
    threadId: item.json.conversationId || '',
    agentName: AGENT_NAME,
    agentEmail: AGENT_EMAIL
  };

  const classificationPrompt = `Analyze this email for a RE/MAX admin office. Return ONLY valid JSON.

From: ${emailData.from}
Subject: ${emailData.subject}
Date: ${emailData.date}
Body:
${emailData.body}
Attachments: ${emailData.hasAttachments ? emailData.attachmentNames || 'Yes (names unknown)' : 'None'}`;

  results.push({
    json: {
      ...emailData,
      classificationPrompt
    }
  });
}

return results;"""

TEMPLATE_DETERMINE_FOLDER_JS = r"""const items = $input.all();

// Document type -> Google Drive folder ID mapping
// These are populated at deploy time from config/env
const FOLDER_MAP = """ + json.dumps(DRIVE_FOLDER_MAP, indent=2) + r""";

const DEFAULT_FOLDER = FOLDER_MAP['Other'] || '""" + REMAX_DRIVE_ROOT + r"""';

return items.map(item => {
  const docType = item.json.document_type || 'Other';
  const folderId = FOLDER_MAP[docType] || DEFAULT_FOLDER;

  return {
    json: {
      ...item.json,
      target_folder_id: folderId,
      target_folder_name: docType
    }
  };
});"""

TEMPLATE_BUILD_DOC_LOG_JS = r"""const items = $input.all();
const classified = $('Classify Email (Sub-Workflow)').first().json;

return items.map(item => {
  return {
    json: {
      date: new Date().toISOString(),
      admin_name: classified.agent_name || 'Admin',
      sender: classified.sender || '',
      sender_name: classified.sender_name || '',
      document_type: classified.document_type || 'Other',
      filename: item.json.name || item.json.fileName || 'unknown',
      drive_link: item.json.webViewLink || item.json.webContentLink || '',
      drive_file_id: item.json.id || '',
      property_reference: '',
      email_subject: classified.original_subject || ''
    }
  };
});"""

TEMPLATE_BUILD_FOLLOWUP_JS = r"""const item = $input.first().json;

const fuId = 'FU-' + Date.now() + '-' + Math.random().toString(36).substring(2, 6);

return [{
  json: {
    id: fuId,
    created_date: new Date().toISOString(),
    admin_name: item.agent_name || 'Admin',
    agent_name: item.sender_name || 'Unknown',
    agent_email: item.sender || '',
    subject: item.original_subject || item.subject || '',
    category: item.category || '',
    follow_up_reason: item.follow_up_reason || 'Follow-up required',
    follow_up_date: item.follow_up_date || '',
    status: 'Open',
    notes: '',
    completed_date: ''
  }
}];"""

FORMAT_ERROR_JS = r"""const error = $input.first().json;
return [{ json: {
  timestamp: new Date().toISOString(),
  workflow_name: error.workflow?.name || 'RE/MAX Email Agent',
  node_name: error.execution?.error?.node?.name || 'unknown',
  error_message: error.execution?.error?.message || 'Unknown error',
  execution_id: error.execution?.id || 'unknown'
}}];"""


# ==================================================================
# MASTER SUB-WORKFLOW
# ==================================================================

def build_master_nodes():
    nodes = []

    # 1. Execute Workflow Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Execute Workflow Trigger",
        "type": "n8n-nodes-base.executeWorkflowTrigger",
        "typeVersion": 1,
        "position": [200, 400],
    })

    # 2. AI Agent
    nodes.append({
        "parameters": {
            "promptType": "define",
            "text": "={{ $json.classificationPrompt }}",
            "options": {
                "systemMessage": REMAX_SYSTEM_PROMPT,
                "maxIterations": 1,
                "returnIntermediateSteps": False,
                "maxTokens": 2000,
            },
        },
        "type": "@n8n/n8n-nodes-langchain.agent",
        "typeVersion": 3.1,
        "position": [480, 400],
        "id": uid(),
        "name": "AI Agent",
    })

    # 3. OpenRouter Chat Model
    nodes.append({
        "parameters": {
            "model": "anthropic/claude-sonnet-4-20250514",
            "options": {},
        },
        "type": "@n8n/n8n-nodes-langchain.lmChatOpenRouter",
        "typeVersion": 1,
        "position": [400, 680],
        "id": uid(),
        "name": "OpenRouter Chat Model",
        "credentials": {"openRouterApi": CRED_OPENROUTER},
    })

    # 4. Simple Memory
    nodes.append({
        "parameters": {
            "sessionIdType": "customKey",
            "sessionKey": "={{ $('Execute Workflow Trigger').item.json.messageId }}",
        },
        "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
        "typeVersion": 1.3,
        "position": [520, 680],
        "id": uid(),
        "name": "Simple Memory",
    })

    # 5. Parse AI Response
    nodes.append({
        "parameters": {"jsCode": MASTER_PARSE_AI_JS},
        "id": uid(),
        "name": "Parse AI Response",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [760, 400],
    })

    # 6. Compute Follow-Up Date
    nodes.append({
        "parameters": {"jsCode": MASTER_COMPUTE_FOLLOWUP_JS},
        "id": uid(),
        "name": "Compute Follow-Up Date",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1000, 400],
    })

    # 7. Build HTML Response
    nodes.append({
        "parameters": {"jsCode": MASTER_BUILD_HTML_JS},
        "id": uid(),
        "name": "Build HTML Response",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1240, 400],
    })

    # 8. Sticky Note
    nodes.append({
        "parameters": {
            "content": (
                "## RE/MAX Email Master - AI Classification Brain\n\n"
                "**Called by:** Per-agent template workflows via Execute Sub-Workflow\n\n"
                "**Input:** Email data (from, subject, body, attachments, agentName)\n"
                "**Output:** Classification JSON with category, document_type,\n"
                "follow_up fields, suggested_response as HTML\n\n"
                "**AI Model:** Claude Sonnet via OpenRouter\n"
                "**Categories:** Agent_Compliance, Listing_Admin, Commission,\n"
                "Training, General_Inquiry, Internal, Spam\n\n"
                "Update classification logic HERE and ALL agents get the fix."
            ),
            "height": 380,
            "width": 350,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [-40, 300],
    })

    return nodes


def build_master_connections():
    def conn(node, index=0):
        return {"node": node, "type": "main", "index": index}

    return {
        "Execute Workflow Trigger": {"main": [[conn("AI Agent")]]},
        "AI Agent": {"main": [[conn("Parse AI Response")]]},
        "OpenRouter Chat Model": {"ai_languageModel": [[conn("AI Agent")]]},
        "Simple Memory": {"ai_memory": [[conn("AI Agent")]]},
        "Parse AI Response": {"main": [[conn("Compute Follow-Up Date")]]},
        "Compute Follow-Up Date": {"main": [[conn("Build HTML Response")]]},
    }


def build_master_workflow():
    return {
        "name": "RE/MAX Email Master - AI Classification",
        "nodes": build_master_nodes(),
        "connections": build_master_connections(),
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "staticData": None,
        "tags": [],
    }


# ==================================================================
# AGENT TEMPLATE
# ==================================================================

def build_template_nodes(agent_name="AGENT_NAME_HERE",
                         agent_email="AGENT_EMAIL_HERE",
                         outlook_cred=None):
    if outlook_cred is None:
        outlook_cred = CRED_OUTLOOK_PLACEHOLDER

    nodes = []

    # Customize JS with agent details
    prepare_js = TEMPLATE_PREPARE_EMAIL_JS.replace(
        "AGENT_NAME_HERE", agent_name
    ).replace("AGENT_EMAIL_HERE", agent_email)

    # ---- A. Triggers & Pre-Processing ----

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "When clicking 'Test workflow'",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [208, 160],
    })

    nodes.append({
        "parameters": {
            "pollTimes": {"item": [{"mode": "everyMinute"}]},
            "filters": {},
            "options": {"downloadAttachments": True},
        },
        "id": uid(),
        "name": "Outlook Trigger",
        "type": "n8n-nodes-base.microsoftOutlookTrigger",
        "typeVersion": 1,
        "position": [208, 432],
        "credentials": {"microsoftOutlookOAuth2Api": outlook_cred},
    })

    nodes.append(if_node(
        "Has DNT Category?",
        [cond("={{ ($json.categories || []).includes('DNT') }}",
              "boolean", "true", True, "dnt-check")],
        "and", [380, 432], type_validation="loose",
    ))

    nodes.append(noop_node("Skip - DNT", [380, 620]))

    # ---- B. Classification ----

    nodes.append({
        "parameters": {"jsCode": prepare_js},
        "id": uid(),
        "name": "Prepare Email Data",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [560, 432],
    })

    nodes.append({
        "parameters": {
            "source": "database",
            "workflowId": REMAX_MASTER_WF_ID,
        },
        "id": uid(),
        "name": "Classify Email (Sub-Workflow)",
        "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1.1,
        "position": [780, 432],
    })

    # ---- C. Category Routing ----

    categories = [
        "Spam", "Agent_Compliance", "Listing_Admin",
        "Commission", "Training", "General_Inquiry", "Internal"
    ]
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "options": {
                                "caseSensitive": True,
                                "leftValue": "",
                                "typeValidation": "strict",
                            },
                            "conditions": [cond(
                                "={{ $json.category }}", "string", "equals",
                                cat if cat != "Spam" else "Spam",
                                f"cat-{cat}"
                            )],
                            "combinator": "and",
                        }
                    }
                    for cat in categories
                ]
            },
            "options": {"fallbackOutput": "extra"},
        },
        "id": uid(),
        "name": "Route by Category",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3,
        "position": [1000, 432],
    })

    cat_nodes = [
        ("Categorize Spam", "Spam", [1260, 80]),
        ("Categorize Compliance", "Agent_Compliance", [1260, 240]),
        ("Categorize Listing", "Listing_Admin", [1260, 400]),
        ("Categorize Commission", "Commission", [1260, 560]),
        ("Categorize Training", "Training", [1260, 720]),
        ("Categorize General", "General_Inquiry", [1260, 880]),
        ("Categorize Internal", "Internal", [1260, 1040]),
        ("Categorize General Fallback", "General_Inquiry", [1260, 1160]),
    ]
    for name, cat, pos in cat_nodes:
        nodes.append(categorize_node(name, cat, pos, cred=outlook_cred))

    nodes.append(mark_read_node(
        "Mark Spam Read",
        "={{ $('Classify Email (Sub-Workflow)').first().json.original_message_id }}",
        [1520, 80], cred=outlook_cred,
    ))

    # ---- D. Urgency ----

    nodes.append(if_node(
        "Is Urgent?",
        [cond("={{ $json.urgency }}", "string", "equals", "high")],
        "and", [1000, 1400],
    ))
    nodes.append(categorize_node("Categorize Urgent", "Urgent", [1260, 1360], cred=outlook_cred))
    nodes.append(noop_node("Not Urgent", [1260, 1480]))

    # ---- E. No-Reply Detection ----

    nodes.append(if_node(
        "Is No-Reply?",
        [
            cond("={{ $json.sender }}", "string", "contains", "noreply"),
            cond("={{ $json.sender }}", "string", "contains", "no-reply"),
            cond("={{ $json.sender }}", "string", "contains", "donotreply"),
        ],
        "or", [1000, 1640],
        type_validation="loose", case_sensitive=False,
    ))
    nodes.append(mark_read_node(
        "Mark No-Reply Read", "={{ $json.original_message_id }}",
        [1260, 1600], cred=outlook_cred,
    ))
    nodes.append(noop_node("Not No-Reply", [1260, 1720]))

    # ---- F. Draft Reply ----

    nodes.append(if_node(
        "Reply Needed?",
        [
            cond("={{ $json.action_required }}", "boolean", "true", True, "rn-action"),
            cond("={{ $json.suggested_response }}", "string", "notEmpty", cond_id="rn-resp"),
            cond("={{ $json.is_spam }}", "boolean", "false", False, "rn-notspam"),
            cond("={{ $json.sender }}", "string", "notContains", "noreply", "rn-nr1"),
            cond("={{ $json.sender }}", "string", "notContains", "no-reply", "rn-nr2"),
            cond("={{ $json.sender }}", "string", "notContains", "donotreply", "rn-nr3"),
        ],
        "and", [1000, 1900],
        type_validation="loose", case_sensitive=False,
    ))

    nodes.append({
        "parameters": {
            "resource": "draft",
            "operation": "create",
            "additionalFields": {
                "subject": "=Re: {{ $json.original_subject }}",
                "bodyContent": "={{ $json.html_response }}",
                "bodyContentType": "HTML",
                "toRecipients": "={{ $json.sender }}",
            },
        },
        "id": uid(),
        "name": "Create Draft Reply",
        "type": "n8n-nodes-base.microsoftOutlook",
        "typeVersion": 2,
        "position": [1260, 1860],
        "credentials": {"microsoftOutlookOAuth2Api": outlook_cred},
        "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 1000,
    })

    nodes.append(mark_read_node(
        "Mark Replied Read",
        "={{ $('Classify Email (Sub-Workflow)').first().json.original_message_id }}",
        [1520, 1860], cred=outlook_cred,
    ))

    nodes.append(noop_node("No Reply Needed", [1260, 1980]))

    # ---- G. Document Filing ----

    nodes.append(if_node(
        "Has Document?",
        [
            cond("={{ $json.has_document }}", "boolean", "true", True, "doc-flag"),
            cond("={{ $json.has_original_attachments }}", "boolean", "true", True, "doc-attach"),
        ],
        "and", [1000, 2200],
    ))

    # Fetch attachments (binary doesn't survive sub-workflow call)
    nodes.append({
        "parameters": {
            "resource": "messageAttachment",
            "operation": "getAll",
            "messageId": "={{ $json.original_message_id }}",
            "output": "binary",
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Attachments",
        "type": "n8n-nodes-base.microsoftOutlook",
        "typeVersion": 2,
        "position": [1260, 2160],
        "credentials": {"microsoftOutlookOAuth2Api": outlook_cred},
        "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 1000,
    })

    nodes.append({
        "parameters": {"jsCode": TEMPLATE_DETERMINE_FOLDER_JS},
        "id": uid(),
        "name": "Determine Drive Folder",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1520, 2160],
    })

    nodes.append({
        "parameters": {
            "operation": "upload",
            "name": "={{ $now.format('yyyyMMdd_HHmmss') + '_' + ($json.name || $json.fileName || 'attachment') }}",
            "folderId": {
                "__rl": True,
                "value": "={{ $json.target_folder_id }}",
                "mode": "id",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Upload to Google Drive",
        "type": "n8n-nodes-base.googleDrive",
        "typeVersion": 3,
        "position": [1760, 2160],
        "credentials": {"googleDriveOAuth2Api": CRED_GOOGLE_DRIVE},
    })

    nodes.append({
        "parameters": {"jsCode": TEMPLATE_BUILD_DOC_LOG_JS},
        "id": uid(),
        "name": "Build Doc Log Entry",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2000, 2160],
    })

    nodes.append({
        "parameters": {
            "operation": "append",
            "documentId": {"mode": "id", "value": REMAX_SHEET_ID},
            "sheetName": {"mode": "name", "value": "Document_Log"},
            "columns": {"mappingMode": "autoMapInputData", "value": {}},
            "options": {},
        },
        "id": uid(),
        "name": "Log Document to Sheet",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [2240, 2160],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
    })

    nodes.append(noop_node("No Documents", [1260, 2300]))

    # ---- H. Follow-Up Tracking ----

    nodes.append(if_node(
        "Follow-Up Required?",
        [cond("={{ $json.follow_up_required }}", "boolean", "true", True)],
        "and", [1000, 2500],
    ))

    nodes.append({
        "parameters": {"jsCode": TEMPLATE_BUILD_FOLLOWUP_JS},
        "id": uid(),
        "name": "Build Follow-Up Entry",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1260, 2460],
    })

    nodes.append({
        "parameters": {
            "operation": "append",
            "documentId": {"mode": "id", "value": REMAX_SHEET_ID},
            "sheetName": {"mode": "name", "value": "Follow_Up_Tracker"},
            "columns": {"mappingMode": "autoMapInputData", "value": {}},
            "options": {},
        },
        "id": uid(),
        "name": "Log Follow-Up to Sheet",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [1520, 2420],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
    })

    nodes.append({
        "parameters": {
            "calendar": "primary",
            "start": "={{ $json.follow_up_date + 'T09:00:00' }}",
            "end": "={{ $json.follow_up_date + 'T09:30:00' }}",
            "additionalFields": {
                "description": (
                    "=Follow-up reminder (auto-generated)\n\n"
                    "Agent: {{ $json.agent_name }} ({{ $json.agent_email }})\n"
                    "Category: {{ $json.category }}\n"
                    "Reason: {{ $json.follow_up_reason }}\n"
                    "Subject: {{ $json.subject }}"
                ),
                "summary": "=Follow up: {{ $json.agent_name }} - {{ $json.follow_up_reason }}",
            },
        },
        "id": uid(),
        "name": "Create Calendar Reminder",
        "type": "n8n-nodes-base.googleCalendar",
        "typeVersion": 1,
        "position": [1520, 2540],
        "credentials": {"googleCalendarOAuth2Api": CRED_GOOGLE_CALENDAR},
    })

    nodes.append(noop_node("No Follow-Up", [1260, 2600]))

    # ---- I. Logging & Errors ----

    nodes.append({
        "parameters": {
            "operation": "append",
            "documentId": {"mode": "id", "value": REMAX_SHEET_ID},
            "sheetName": {"mode": "name", "value": "Email_Log"},
            "columns": {"mappingMode": "autoMapInputData", "value": {}},
            "options": {},
        },
        "id": uid(),
        "name": "Log to Email Sheet",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [1000, 2760],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
    })

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "typeVersion": 1,
        "position": [208, -200],
    })

    nodes.append({
        "parameters": {"jsCode": FORMAT_ERROR_JS},
        "id": uid(),
        "name": "Format Error Alert",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [464, -200],
    })

    nodes.append({
        "parameters": {
            "operation": "append",
            "documentId": {"mode": "id", "value": REMAX_SHEET_ID},
            "sheetName": {"mode": "name", "value": "Error_Log"},
            "columns": {"mappingMode": "autoMapInputData", "value": {}},
            "options": {},
        },
        "id": uid(),
        "name": "Log Error to Sheet",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [720, -200],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
    })

    # ---- Sticky Notes ----
    nodes.append({
        "parameters": {
            "content": (
                f"## RE/MAX Email Agent: {agent_name}\n\n"
                "**Outlook Categories Required:**\n"
                "Agent_Compliance (green), Listing_Admin (blue),\n"
                "Commission (orange), Training (purple),\n"
                "General_Inquiry (gray), Internal (yellow),\n"
                "Spam (red), Urgent (red)\n\n"
                "**Customization:**\n"
                "- AGENT_NAME / AGENT_EMAIL in Prepare Email Data\n"
                "- Outlook credential on all Outlook nodes\n"
                "- Master workflow ID in Classify Email node"
            ),
            "height": 380,
            "width": 350,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [-16, 80],
    })

    return nodes


def build_template_connections():
    def conn(node, index=0):
        return {"node": node, "type": "main", "index": index}

    return {
        "When clicking 'Test workflow'": {"main": [[conn("Prepare Email Data")]]},
        "Outlook Trigger": {"main": [[conn("Has DNT Category?")]]},
        "Has DNT Category?": {
            "main": [
                [conn("Skip - DNT")],
                [conn("Prepare Email Data")],
            ]
        },
        "Prepare Email Data": {"main": [[conn("Classify Email (Sub-Workflow)")]]},
        "Classify Email (Sub-Workflow)": {
            "main": [[
                conn("Route by Category"),
                conn("Is Urgent?"),
                conn("Is No-Reply?"),
                conn("Reply Needed?"),
                conn("Has Document?"),
                conn("Follow-Up Required?"),
                conn("Log to Email Sheet"),
            ]]
        },
        "Route by Category": {
            "main": [
                [conn("Categorize Spam")],
                [conn("Categorize Compliance")],
                [conn("Categorize Listing")],
                [conn("Categorize Commission")],
                [conn("Categorize Training")],
                [conn("Categorize General")],
                [conn("Categorize Internal")],
                [conn("Categorize General Fallback")],
            ]
        },
        "Categorize Spam": {"main": [[conn("Mark Spam Read")]]},
        "Is Urgent?": {
            "main": [[conn("Categorize Urgent")], [conn("Not Urgent")]]
        },
        "Is No-Reply?": {
            "main": [[conn("Mark No-Reply Read")], [conn("Not No-Reply")]]
        },
        "Reply Needed?": {
            "main": [[conn("Create Draft Reply")], [conn("No Reply Needed")]]
        },
        "Create Draft Reply": {"main": [[conn("Mark Replied Read")]]},
        "Has Document?": {
            "main": [[conn("Fetch Attachments")], [conn("No Documents")]]
        },
        "Fetch Attachments": {"main": [[conn("Determine Drive Folder")]]},
        "Determine Drive Folder": {"main": [[conn("Upload to Google Drive")]]},
        "Upload to Google Drive": {"main": [[conn("Build Doc Log Entry")]]},
        "Build Doc Log Entry": {"main": [[conn("Log Document to Sheet")]]},
        "Follow-Up Required?": {
            "main": [[conn("Build Follow-Up Entry")], [conn("No Follow-Up")]]
        },
        "Build Follow-Up Entry": {
            "main": [[conn("Log Follow-Up to Sheet"), conn("Create Calendar Reminder")]]
        },
        "Error Trigger": {"main": [[conn("Format Error Alert")]]},
        "Format Error Alert": {"main": [[conn("Log Error to Sheet")]]},
    }


def build_template_workflow(agent_name="AGENT_NAME_HERE",
                            agent_email="AGENT_EMAIL_HERE",
                            outlook_cred=None):
    return {
        "name": f"RE/MAX Email Agent - {agent_name}",
        "nodes": build_template_nodes(agent_name, agent_email, outlook_cred),
        "connections": build_template_connections(),
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "staticData": None,
        "tags": [],
    }


# ==================================================================
# CLI
# ==================================================================

def get_n8n_client():
    sys.path.insert(0, str(Path(__file__).parent))
    from n8n_client import N8nClient

    api_key = os.getenv("N8N_API_KEY")
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        sys.exit(1)
    return N8nClient(base_url, api_key, timeout=30), base_url


def deploy_workflow(wf, action):
    client, base_url = get_n8n_client()
    print(f"\nConnecting to {base_url}...")

    with client:
        health = client.health_check()
        if not health["connected"]:
            print(f"  ERROR: Cannot connect: {health.get('error')}")
            sys.exit(1)
        print("  Connected!")

        existing = None
        try:
            for w in client.list_workflows():
                if w["name"] == wf["name"]:
                    existing = w
                    break
        except Exception:
            pass

        # Strip read-only fields for API
        api_payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {}),
        }

        if existing:
            wf_id = existing["id"]
            print(f"  Updating existing workflow {wf_id}...")
            client.update_workflow(wf_id, api_payload)
            print(f"  Updated! ID: {wf_id}")
        else:
            print("  Creating new workflow...")
            result = client.create_workflow(api_payload)
            wf_id = result.get("id", "unknown")
            print(f"  Deployed! ID: {wf_id}")

        if action == "activate":
            client.activate_workflow(wf_id)
            print(f"  Activated!")

        return wf_id


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python tools/deploy_remax_email_mgmt.py master [build|deploy|activate]")
        print("  python tools/deploy_remax_email_mgmt.py template [build|deploy|activate]")
        print("  python tools/deploy_remax_email_mgmt.py onboard <name> <email> <outlook_cred_id>")
        sys.exit(1)

    target = sys.argv[1].lower()
    output_dir = Path(__file__).parent.parent / "workflows" / "remax" / "email-classifier"
    output_dir.mkdir(parents=True, exist_ok=True)

    if target == "master":
        action = sys.argv[2].lower()
        print("Building RE/MAX Email Master sub-workflow...")
        wf = build_master_workflow()
        node_count = len([n for n in wf["nodes"] if "stickyNote" not in n["type"]])
        print(f"  {node_count} functional nodes")

        path = output_dir / "remax_email_master.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"  Saved to {path}")

        if action in ("deploy", "activate"):
            wf_id = deploy_workflow(wf, action)
            print(f"\n  Master Workflow ID: {wf_id}")
            print("  -> Set REMAX_MASTER_WF_ID={} in .env".format(wf_id))

    elif target == "template":
        action = sys.argv[2].lower()
        print("Building RE/MAX Email Agent Template...")
        wf = build_template_workflow()
        node_count = len([n for n in wf["nodes"] if "stickyNote" not in n["type"]])
        print(f"  {node_count} functional nodes")

        path = output_dir / "remax_email_agent_template.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"  Saved to {path}")

        if action in ("deploy", "activate"):
            wf_id = deploy_workflow(wf, action)
            print(f"\n  Template Workflow ID: {wf_id}")

        _print_template_checklist()

    elif target == "onboard":
        if len(sys.argv) < 5:
            print("Usage: onboard <name> <email> <outlook_cred_id>")
            sys.exit(1)

        agent_name = sys.argv[2]
        agent_email = sys.argv[3]
        outlook_cred_id = sys.argv[4]
        outlook_cred = {
            "id": outlook_cred_id,
            "name": f"Outlook - {agent_name}",
        }

        slug = re.sub(r'[^a-z0-9]+', '_', agent_name.lower()).strip('_')
        print(f"Onboarding agent: {agent_name} ({agent_email})...")

        wf = build_template_workflow(agent_name, agent_email, outlook_cred)
        node_count = len([n for n in wf["nodes"] if "stickyNote" not in n["type"]])
        print(f"  {node_count} functional nodes")

        path = output_dir / f"remax_email_agent_{slug}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"  Saved to {path}")

        wf_id = deploy_workflow(wf, "deploy")
        print(f"\n  Agent Workflow ID: {wf_id}")
        print(f"  Agent: {agent_name} ({agent_email})")
        print(f"  Outlook Credential: {outlook_cred_id}")
        print(f"\n  -> Workflow deployed INACTIVE. Test before activating.")
        _print_agent_checklist(agent_name)

    else:
        print(f"Unknown target: {target}")
        print("Use: master, template, or onboard")
        sys.exit(1)


def _print_template_checklist():
    print("\n--- Agent Template Checklist ---")
    print("To onboard a new admin agent:")
    print("  python tools/deploy_remax_email_mgmt.py onboard <name> <email> <outlook_cred_id>")
    print()
    print("Pre-requisites:")
    print("  1. Create Outlook OAuth2 credential in n8n for the admin")
    print("  2. Set REMAX_MASTER_WF_ID in .env (deploy master first)")
    print("  3. Create Google Sheet with tabs: Email_Log, Follow_Up_Tracker, Document_Log, Error_Log")
    print("  4. Create Google Drive folders: 01_FICA through 10_Other")
    print("  5. Set REMAX_EMAIL_SHEET_ID and REMAX_DRIVE_* vars in .env")


def _print_agent_checklist(agent_name):
    print(f"\n--- Setup Checklist for {agent_name} ---")
    print("1. Admin must create 8 Outlook categories:")
    print("   Agent_Compliance (green), Listing_Admin (blue),")
    print("   Commission (orange), Training (purple),")
    print("   General_Inquiry (gray), Internal (yellow),")
    print("   Spam (red), Urgent (red)")
    print("2. Send 5 test emails (compliance, commission, listing, spam, internal)")
    print("3. Verify categories applied + drafts created")
    print("4. Activate workflow in n8n")


if __name__ == "__main__":
    main()

"""
Business Email Management - Outlook Edition
Full-featured AI email triage for Outlook, equivalent to the Gmail version.

Translates all 19 features from Business Email Management Automation (Gmail)
to Microsoft Outlook via Microsoft Graph API.

Features:
    - AI classification via Claude Sonnet (OpenRouter)
    - Department routing with Outlook categories
    - Auto-draft replies with branded HTML signature
    - Lead detection + Google Calendar follow-ups
    - Interested reply handling (auto thank-you + DNT)
    - Opt-out / bounce detection + DNT
    - Ticket reference number detection (13 regex patterns)
    - No-reply sender detection
    - eftcorp domain blocking
    - Sender-level DNT check via Google Sheets
    - Thread reply limit (signature detection)
    - Email logging to Google Sheets
    - Airtable lead status updates
    - Error logging to Google Sheets (no circular Outlook dependency)

Usage:
    python tools/deploy_outlook_email_mgmt.py build       # Build JSON only
    python tools/deploy_outlook_email_mgmt.py deploy      # Build + Deploy (inactive)
    python tools/deploy_outlook_email_mgmt.py activate    # Build + Deploy + Activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# -- Credential Constants -------------------------------------------------

CRED_OUTLOOK = {
    "id": os.getenv("N8N_CRED_OUTLOOK", "YOUR_CREDENTIAL_ID"),
    "name": "Microsoft Outlook OAuth2"
}
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GOOGLE_SHEETS = {"id": "OkpDXxwI8WcUJp4P", "name": "Google Sheets AVM Tutorial"}
CRED_GOOGLE_CALENDAR = {"id": "I5zIYf0UxlkUt3KG", "name": "Google Calendar AVM Tutorial"}
CRED_AIRTABLE = {"id": "7TtMl7ZnJFpC4RGk", "name": "Lead Scraper Airtable"}

# -- Sheet / Table IDs ----------------------------------------------------

EMAIL_LOG_SHEET_ID = os.getenv(
    "EMAIL_LOG_SHEET_ID", "1Adp3x0ler5H69Cih5tbMLqWEgZMziebhnOEWbMPTvaA"
)
LEADS_SHEET_ID = os.getenv(
    "LEADS_SHEET_ID", "1G2P9gYuPKtqhDkkJaTVLbuA_yxj_IqTI7vuCfhFLklM"
)
AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_LEADS_TABLE = "tblOsuh298hB9WWrA"

# -- Helpers ---------------------------------------------------------------


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


def outlook_node(name, resource, operation, message_id_expr, position,
                 update_fields=None, additional_fields=None):
    """Build a Microsoft Outlook node dict."""
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
        "onError": "continueRegularOutput",
        "position": position,
        "credentials": {
            "microsoftOutlookOAuth2Api": CRED_OUTLOOK
        },
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 1000,
    }
    if update_fields:
        node["parameters"]["updateFields"] = update_fields
    if additional_fields:
        node["parameters"]["additionalFields"] = additional_fields
    return node


def categorize_node(name, category, position):
    """Build an Outlook 'update categories' node."""
    return outlook_node(
        name, "message", "update",
        "={{ $json.original_message_id }}",
        position,
        update_fields={"categories": [category]},
    )


def mark_read_node(name, message_id_expr, position):
    """Build an Outlook 'mark as read' node."""
    return outlook_node(
        name, "message", "update",
        message_id_expr,
        position,
        update_fields={"isRead": True},
    )


def if_node(name, conditions, combinator, position, type_validation="strict",
            case_sensitive=True):
    """Build an If node v2."""
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
    """Build a No-Op node."""
    return {
        "parameters": {},
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": position,
    }


def cond(left, op_type, operation, right=None, cond_id=None):
    """Build a single condition dict for If / Switch nodes."""
    c = {
        "id": cond_id or uid(),
        "leftValue": left,
        "operator": {"type": op_type, "operation": operation},
    }
    if right is not None:
        c["rightValue"] = right
    return c


# -- System Prompt (full, from Gmail version + all fix scripts) -----------

SYSTEM_PROMPT = r"""You are the AI Email Manager for AnyVision Media, a digital media and technology agency. Your job is to analyze incoming business emails and return a structured JSON classification.

## Your Task
For every email you receive, analyze it and return ONLY a valid JSON object. No markdown formatting, no backticks, no explanation text -- just the raw JSON.

## Company Context
- Company: AnyVision Media (digital media, AI solutions, web development)
- Owner: Ian Immelman (ian@anyvisionmedia.com)
- Services: AI workflow automation, web development, social media management, real estate tech solutions
- Tone: Professional but approachable, tech-savvy

## JSON Output Format
Return exactly this structure:
{
  "sender": "<sender email address>",
  "sender_name": "<sender display name>",
  "subject": "<email subject line>",
  "intent": "<1 sentence: what the sender wants or needs>",
  "tone": "<one of: formal, informal, urgent, angry, friendly, neutral>",
  "urgency": "<one of: high, medium, low>",
  "action_required": true or false,
  "department": "<ONE of: Accounting_Finance, Customer_Support, Sales, Management, Spam_Irrelevant>",
  "tags": ["<applicable tags from the list below>"],
  "is_spam": true or false,
  "suggested_response": "<a professional draft reply if action_required is true, otherwise null>",
  "summary": "<1-2 sentence summary of the email>",
  "escalation_needed": true or false,
  "is_interested_reply": true or false,
  "is_opt_out": true or false
}

## Department Classification Rules
- **Accounting_Finance**: Invoices, payments, billing inquiries, refund requests, financial statements, tax documents
- **Customer_Support**: Service complaints, technical issues, bug reports, account help, feature requests
- **Sales**: New business enquiries, pricing requests, partnership proposals, lead generation, RFP responses
- **Management**: Strategic decisions, legal matters, contracts, legal threats, regulatory matters, NDAs, high-level partnerships, media/PR, executive communications, escalated complaints, documentation, compliance, vendor setup, office operations, admin tasks, team communications, internal updates, HR matters
- **Spam_Irrelevant**: Unsolicited marketing, phishing attempts, suspicious links, irrelevant promotions, newsletters not subscribed to

## Available Tags
Invoice, Payment, Refund, Complaint, New_Lead, Contract, Meeting_Request, Follow_Up, Escalation, Urgent

## Urgency Rules
Mark as HIGH if any of these apply:
- Subject contains "urgent", "ASAP", "immediate", "critical"
- Legal threats or regulatory deadlines
- Payment disputes or overdue invoices
- Escalated customer complaints
- Time-sensitive business opportunities

## Interested Reply Detection Rules
Set is_interested_reply to TRUE if ALL of these apply:
- The email appears to be a REPLY to a previous outreach/cold email from AnyVision Media
- The sender expresses positive interest (wants to learn more, schedule a call, get pricing, says 'interested', 'sounds good', 'tell me more', 'let's chat', etc.)
- The sender is NOT from AnyVision Media itself

Set is_interested_reply to FALSE for:
- First-time inbound emails (not replies to our outreach)
- Negative responses ('not interested', 'unsubscribe', 'remove me')
- Automated responses / out-of-office replies
- Spam or irrelevant emails

## Opt-Out / Unsubscribe Detection Rules
Set is_opt_out to TRUE if ANY of these apply:
- Sender explicitly says "unsubscribe", "remove me", "stop emailing", "not interested please stop", "take me off your list", "cease communication"
- Email is a bounce/delivery failure: "address not found", "delivery failed", "mailbox full", "user unknown", "mailer-daemon", "postmaster"

When is_opt_out is TRUE, you MUST also set:
- action_required: false
- suggested_response: null
- is_interested_reply: false

## Response Writing Rules (for suggested_response)
When action_required is true, write a professional, well-structured reply:

**FORMATTING REQUIREMENTS:**
- Use proper line breaks (\n\n between paragraphs)
- Start with a personalized greeting: "Hi [name]," or "Dear [name],"
- Keep paragraphs short (2-3 sentences max)
- End with a professional signature block

**STRUCTURE:**
1. Greeting - Personalized with sender's name
2. Acknowledgment - Thank them and acknowledge their specific concern
3. Response - Address their question or request (1-2 paragraphs)
4. Next Steps - What happens next (if applicable)
5. Closing - Professional sign-off
6. Signature - AnyVision Media Team contact info

**CONTENT GUIDELINES:**
- Acknowledge receipt of their email
- Address their specific concern or question
- Be professional, warm, and concise
- Never promise specific timelines without verification
- Never confirm financial or legal decisions
- Never reveal that this is an automated system
- Match their tone (formal vs casual) appropriately

When action_required is false or the email is spam, set suggested_response to null.

CRITICAL: Return ONLY the JSON object. No other text."""

# -- HTML Signature --------------------------------------------------------

SIGNATURE_HTML = (
    '<table cellpadding="0" cellspacing="0" border="0" '
    'style="font-family:\'Segoe UI\',\'Helvetica Neue\',Arial,sans-serif;'
    'font-size:14px;line-height:1.4;color:#333333;">'
    '<tr>'
    '<td style="vertical-align:top;padding-right:18px;">'
    '<a href="https://www.anyvisionmedia.com" target="_blank" style="text-decoration:none;">'
    '<img src="https://www.anyvisionmedia.com/logo-icon.png" alt="AnyVision Media" '
    'width="70" style="display:block;border:0;width:70px;height:70px;" />'
    '</a></td>'
    '<td style="vertical-align:top;padding-left:18px;border-left:3px solid #6C63FF;">'
    '<table cellpadding="0" cellspacing="0" border="0">'
    '<tr><td style="font-size:20px;font-weight:700;color:#0A0F1C;padding-bottom:2px;'
    'letter-spacing:-0.3px;">Ian</td></tr>'
    '<tr><td style="font-size:13px;font-weight:400;color:#6B7280;padding-bottom:10px;">'
    'Founder&nbsp;&nbsp;&#183;&nbsp;&nbsp;'
    '<span style="color:#6C63FF;font-weight:600;">AnyVision Media</span></td></tr>'
    '<tr><td style="padding-bottom:10px;">'
    '<table cellpadding="0" cellspacing="0" border="0" width="200">'
    '<tr><td width="100" style="height:2px;background-color:#6C63FF;font-size:0;'
    'line-height:0;">&nbsp;</td>'
    '<td width="100" style="height:2px;background-color:#00D4AA;font-size:0;'
    'line-height:0;">&nbsp;</td></tr></table></td></tr>'
    '<tr><td style="font-size:12px;color:#333333;padding-bottom:3px;">'
    '<a href="mailto:ian@anyvisionmedia.com" style="color:#6C63FF;text-decoration:none;'
    'font-weight:500;">ian@anyvisionmedia.com</a></td></tr>'
    '<tr><td style="font-size:12px;color:#333333;padding-bottom:3px;">'
    '<a href="https://www.anyvisionmedia.com" target="_blank" style="color:#6C63FF;'
    'text-decoration:none;font-weight:500;">www.anyvisionmedia.com</a></td></tr>'
    '<tr><td style="font-size:11px;color:#9CA3AF;padding-top:2px;">'
    'Johannesburg, South Africa</td></tr>'
    '</table></td></tr></table>'
)

THANK_YOU_HTML = (
    '<div style="font-family:\'Segoe UI\',\'Helvetica Neue\',Arial,sans-serif;'
    'font-size:14px;line-height:1.5;color:#333333;">'
    '<p style="margin:0 0 12px 0;">Hi {{ $json.sender_name }},</p>'
    '<p style="margin:0 0 12px 0;">Thank you so much for getting back to us! '
    'We really appreciate your interest.</p>'
    '<p style="margin:0 0 12px 0;">I\'ll be in touch shortly to discuss how '
    'AnyVision Media can help you further. In the meantime, if you have any '
    'questions, feel free to reply to this email.</p>'
    '<p style="margin:0 0 12px 0;">Looking forward to connecting!</p>'
    '<br>' + SIGNATURE_HTML + '</div>'
)

# -- JavaScript Code Blocks ------------------------------------------------

# Escape signature for embedding in JS template literal
_sig_js = SIGNATURE_HTML.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

PREPARE_EMAIL_DATA_JS = r"""const items = $input.all();
const results = [];

for (const item of items) {
  // Extract sender info from Outlook's Microsoft Graph API structure
  const senderAddress = item.json.sender?.emailAddress?.address
    || item.json.from?.emailAddress?.address || '';
  const senderName = item.json.sender?.emailAddress?.name
    || item.json.from?.emailAddress?.name || '';

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
    attachmentCount: item.json.hasAttachments ? 1 : 0,
    messageId: item.json.id || '',
    threadId: item.json.conversationId || ''
  };

  const classificationPrompt = `Analyze this business email. Return ONLY valid JSON, no markdown, no backticks.

From: ${emailData.from}
Subject: ${emailData.subject}
Date: ${emailData.date}
Body:
${emailData.body}
Has Attachments: ${emailData.hasAttachments ? 'Yes (' + emailData.attachmentCount + ')' : 'No'}`;

  results.push({
    json: {
      ...emailData,
      classificationPrompt
    }
  });
}

return results;"""

PARSE_AI_RESPONSE_JS = (
    r"""const items = $input.all();
const results = [];

for (const item of items) {
  const emailData = $('Prepare Email Data').first().json;

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
      department: 'Management',
      tags: ['Escalation'],
      is_spam: false,
      suggested_response: null,
      summary: 'Email could not be auto-classified. Manual review required.',
      escalation_needed: true,
      is_interested_reply: false,
      is_opt_out: false
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
      sender: parsed.sender || emailData.from || '',
      sender_name: parsed.sender_name || 'Unknown',
      subject: parsed.subject || emailData.subject || '',
      intent: parsed.intent || '',
      tone: parsed.tone || 'neutral',
      urgency: parsed.urgency || 'medium',
      action_required: parsed.action_required || false,
      department: parsed.department || 'Management',
      tags: parsed.tags || [],
      tags_string: (parsed.tags || []).join(', '),
      is_spam: parsed.is_spam || false,
      suggested_response: parsed.suggested_response || '',
      html_response: (() => {
        const text = parsed.suggested_response || '';
        if (!text) return '';
        const paragraphs = text.split(/\n\n+/);
        const htmlParagraphs = paragraphs
          .map(p => p.replace(/\n/g, '<br>'))
          .map(p => '<p style="margin:0 0 12px 0;font-family:Segoe UI,Helvetica Neue,Arial,sans-serif;font-size:14px;line-height:1.5;color:#333333;">' + p + '</p>')
          .join('');
        const signature = `"""
    + _sig_js
    + r"""`;
        return '<div style="font-family:Segoe UI,Helvetica Neue,Arial,sans-serif;">' + htmlParagraphs + '<br>' + signature + '</div>';
      })(),
      summary: parsed.summary || '',
      escalation_needed: parsed.escalation_needed || false,
      is_interested_reply: parsed.is_interested_reply || false,
      is_opt_out: parsed.is_opt_out || false,
      processed_at: new Date().toISOString(),
      ticket_number: 'TKT-' + Date.now()
    }
  });
}

return results;"""
)

CHECK_REFERENCE_NUMBER_JS = r"""const items = $input.all();

const TICKET_PATTERNS = [
  /\bTKT[-#]?\s*\d+/i,
  /\bTICKET\s*[#:]?\s*\d+/i,
  /\bTICKET\s+NUMBER\s*:?\s*\w+/i,
  /\bREF\s*[-:]\s*#?\s*[A-Z0-9]{3,}/i,
  /\bREFERENCE\s*(NUMBER|NO\.?|#)\s*:?\s*[A-Z0-9-]+/i,
  /\bENQ[-#]?\s*\d+/i,
  /\bENQUIRY\s*(NUMBER|NO\.?|#)\s*:?\s*\w+/i,
  /\bCASE\s*(ID|NUMBER|NO\.?|#)\s*:?\s*[A-Z0-9-]+/i,
  /\bINCIDENT\s*(ID|NUMBER|NO\.?|#)\s*:?\s*[A-Z0-9-]+/i,
  /\bSR[-#]\s*\d+/i,
  /\bINC[-#]\s*\d+/i,
  /\b[A-Z]{2,4}-\d{4,}\b/,
];

return items.map(item => {
  const subject = (item.json.original_subject || '').toUpperCase();
  const body = (item.json.original_body || '').substring(0, 2000).toUpperCase();
  const textToCheck = subject + ' ' + body;

  let has_reference_number = false;
  let matched_pattern = '';

  for (const pattern of TICKET_PATTERNS) {
    const match = textToCheck.match(pattern);
    if (match) {
      has_reference_number = true;
      matched_pattern = match[0];
      break;
    }
  }

  return {
    json: {
      ...item.json,
      has_reference_number,
      matched_reference_pattern: matched_pattern
    }
  };
});"""

CHECK_IF_LEAD_JS = r"""const item = $input.first();
const d = item.json;

if (d.department === 'Sales' && d.tags_string && d.tags_string.includes('New_Lead')) {
  return [{
    json: {
      date: d.processed_at,
      lead_name: d.sender_name,
      email: d.sender,
      subject: d.original_subject,
      interest: d.intent,
      summary: d.summary,
      urgency: d.urgency,
      status: 'New',
      follow_up_date: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000)
        .toISOString().split('T')[0],
      is_lead: true
    }
  }];
}

return [{ json: { is_lead: false } }];"""

FORMAT_ERROR_JS = r"""const error = $input.first().json;

const errorReport = {
  workflow_name: error.workflow?.name || 'Business Email Management - Outlook',
  workflow_id: error.workflow?.id || 'unknown',
  node_name: error.execution?.error?.node?.name || 'unknown',
  error_message: error.execution?.error?.message || 'Unknown error',
  timestamp: new Date().toISOString(),
  execution_id: error.execution?.id || 'unknown',
  severity: 'high',
};

return [{ json: errorReport }];"""


# ==================================================================
# BUILD NODES
# ==================================================================

def build_nodes():
    """Build all 50 nodes for the Outlook email management workflow."""
    nodes = []

    # ---- A. Triggers & Pre-Processing ----

    # 1. Manual Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "When clicking 'Test workflow'",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [208, 160],
    })

    # 2. Outlook Trigger
    nodes.append({
        "parameters": {
            "pollTimes": {"item": [{"mode": "everyMinute"}]},
            "filters": {},
        },
        "id": uid(),
        "name": "Outlook Trigger",
        "type": "n8n-nodes-base.microsoftOutlookTrigger",
        "typeVersion": 1,
        "position": [208, 432],
        "credentials": {"microsoftOutlookOAuth2Api": CRED_OUTLOOK},
    })

    # 3. Has DNT Category?
    nodes.append(if_node(
        "Has DNT Category?",
        [cond(
            "={{ ($json.categories || []).includes('DNT') }}",
            "boolean", "true", True, "dnt-category-check"
        )],
        "and", [340, 432],
        type_validation="loose",
    ))

    # 4. Skip - DNT
    nodes.append(noop_node("Skip - DNT", [340, 608]))

    # 5. Check Sender DNT (Google Sheets lookup)
    nodes.append({
        "parameters": {
            "operation": "read",
            "documentId": {"mode": "id", "value": LEADS_SHEET_ID},
            "sheetName": {"mode": "name", "value": "Leads"},
            "filtersUI": {
                "values": [{
                    "lookupColumn": "email",
                    "lookupValue": "={{ $json.sender?.emailAddress?.address || $json.from?.emailAddress?.address || '' }}",
                }]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Check Sender DNT",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "onError": "continueRegularOutput",
        "position": [420, 520],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "onError": "continueRegularOutput",
        "alwaysOutputData": True,
    })

    # 5b. Is Sender DNT?
    nodes.append(if_node(
        "Is Sender DNT?",
        [cond(
            "={{ ($json.status || '').toLowerCase().includes('do not') || ($json.status || '').toLowerCase().includes('converted') }}",
            "boolean", "true", True, "sender-dnt-check"
        )],
        "and", [560, 520],
        type_validation="loose",
    ))

    # 5c. Skip - Sender Blocked
    nodes.append(noop_node("Skip - Sender Blocked", [560, 680]))

    # ---- B. AI Classification ----

    # 6. Prepare Email Data
    nodes.append({
        "parameters": {"jsCode": PREPARE_EMAIL_DATA_JS},
        "id": uid(),
        "name": "Prepare Email Data",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [720, 432],
    })

    # 7. AI Agent
    nodes.append({
        "parameters": {
            "promptType": "define",
            "text": "={{ $json.classificationPrompt }}",
            "options": {
                "systemMessage": SYSTEM_PROMPT,
                "maxIterations": 1,
                "returnIntermediateSteps": False,
                "maxTokens": 2000,
            },
        },
        "type": "@n8n/n8n-nodes-langchain.agent",
        "typeVersion": 3.1,
        "position": [912, 432],
        "id": uid(),
        "name": "AI Agent",
    })

    # 8. OpenRouter Chat Model
    nodes.append({
        "parameters": {
            "model": "anthropic/claude-sonnet-4-20250514",
            "options": {},
        },
        "type": "@n8n/n8n-nodes-langchain.lmChatOpenRouter",
        "typeVersion": 1,
        "position": [816, 720],
        "id": uid(),
        "name": "OpenRouter Chat Model",
        "credentials": {"openRouterApi": CRED_OPENROUTER},
    })

    # 9. Simple Memory
    nodes.append({
        "parameters": {
            "sessionIdType": "customKey",
            "sessionKey": "={{ $('Outlook Trigger')?.item?.json?.id ?? 'manual-test-' + Date.now() }}",
        },
        "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
        "typeVersion": 1.3,
        "position": [928, 720],
        "id": uid(),
        "name": "Simple Memory",
    })

    # 10. Parse AI Response
    nodes.append({
        "parameters": {"jsCode": PARSE_AI_RESPONSE_JS},
        "id": uid(),
        "name": "Parse AI Response",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 432],
    })

    # ---- C. Reference Number Detection ----

    # 11. Check Reference Number
    nodes.append({
        "parameters": {"jsCode": CHECK_REFERENCE_NUMBER_JS},
        "id": uid(),
        "name": "Check Reference Number",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1300, 432],
    })

    # ---- D. Department Routing ----

    # 12. Route by Department (Switch v3)
    departments = [
        "Spam_Irrelevant", "Accounting_Finance", "Customer_Support",
        "Sales", "Management"
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
                                "={{ $json.department }}", "string", "equals",
                                dept, f"dept-{dept}"
                            )],
                            "combinator": "and",
                        }
                    }
                    for dept in departments
                ]
            },
            "options": {"fallbackOutput": "extra"},
        },
        "id": uid(),
        "name": "Route by Department",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3,
        "position": [1500, 432],
    })

    # 13-18. Category nodes
    cat_map = [
        ("Categorize Junk", "Junk", [1760, 112]),
        ("Categorize Finance", "Accounting_Finance", [1760, 288]),
        ("Categorize Support", "Customer_Support", [1760, 464]),
        ("Categorize Sales", "Sales", [1760, 640]),
        ("Categorize Management", "Management", [1760, 816]),
        ("Categorize General", "General", [1760, 992]),
    ]
    for name, cat, pos in cat_map:
        nodes.append(categorize_node(name, cat, pos))

    # ---- E. Spam ----

    # 19. Mark Spam Read
    nodes.append(mark_read_node(
        "Mark Spam Read",
        "={{ $('Check Reference Number').first().json.original_message_id }}",
        [2016, 112],
    ))

    # ---- F. Urgency ----

    # 20. Is Urgent?
    nodes.append(if_node(
        "Is Urgent?",
        [cond("={{ $json.urgency }}", "string", "equals", "high")],
        "and", [1500, 1200],
    ))

    # 21. Categorize Urgent
    nodes.append(categorize_node("Categorize Urgent", "Urgent", [1760, 1152]))

    # 22. Not Urgent
    nodes.append(noop_node("Not Urgent", [1760, 1312]))

    # ---- G. No-Reply Detection ----

    # 23. Is No-Reply?
    nodes.append(if_node(
        "Is No-Reply?",
        [
            cond("={{ $json.sender }}", "string", "contains", "noreply"),
            cond("={{ $json.sender }}", "string", "contains", "no-reply"),
            cond("={{ $json.sender }}", "string", "contains", "donotreply"),
        ],
        "or", [1500, 1808],
        type_validation="loose", case_sensitive=False,
    ))

    # 24. Mark No-Reply Read
    nodes.append(mark_read_node(
        "Mark No-Reply Read",
        "={{ $json.original_message_id }}",
        [1760, 1744],
    ))

    # 25. Not No-Reply
    nodes.append(noop_node("Not No-Reply", [1760, 1904]))

    # ---- H. Reply Decision ----

    # 26. Reply Needed? (9-condition AND gate)
    nodes.append(if_node(
        "Reply Needed?",
        [
            cond("={{ $json.action_required }}", "boolean", "true", True,
                 "rn-action"),
            cond("={{ $json.suggested_response }}", "string", "notEmpty",
                 cond_id="rn-response"),
            cond("={{ $json.is_spam }}", "boolean", "false", False,
                 "rn-not-spam"),
            cond("={{ $json.sender }}", "string", "notContains", "noreply",
                 "rn-no-noreply"),
            cond("={{ $json.sender }}", "string", "notContains", "no-reply",
                 "rn-no-noreply2"),
            cond("={{ $json.sender }}", "string", "notContains", "donotreply",
                 "rn-no-donotreply"),
            cond("={{ $json.sender }}", "string", "notContains",
                 "@eftcorp.atlassian.net", "rn-no-eftcorp"),
            cond("={{ $json.has_reference_number }}", "boolean", "false",
                 False, "rn-no-ticket"),
            cond("={{ $json.is_interested_reply }}", "boolean", "false",
                 False, "rn-not-interested"),
            cond("={{ $json.is_opt_out }}", "boolean", "false", False,
                 "rn-not-optout"),
            cond("={{ $json.original_body }}", "string", "notContains",
                 "AnyVision Media Team", "rn-no-sig1"),
        ],
        "and", [1500, 1520],
        type_validation="loose", case_sensitive=False,
    ))

    # 27. Create Draft Reply (Outlook draft with HTML)
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
        "onError": "continueRegularOutput",
        "position": [1760, 1472],
        "credentials": {"microsoftOutlookOAuth2Api": CRED_OUTLOOK},
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 1000,
    })

    # 28. Mark Replied Read
    nodes.append(mark_read_node(
        "Mark Replied Read",
        "={{ $('Check Reference Number').first().json.original_message_id }}",
        [2016, 1472],
    ))

    # 29. No Reply Needed
    nodes.append(noop_node("No Reply Needed", [1760, 1632]))

    # ---- I. Ticket Handling ----

    # 30. Has Reference Number?
    nodes.append(if_node(
        "Has Reference Number?",
        [cond("={{ $json.has_reference_number }}", "boolean", "true", True)],
        "and", [1500, 1680],
    ))

    # 31. Update Lead - Stop Follow Up (Airtable)
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {
                "__rl": True,
                "mode": "list",
                "value": AIRTABLE_BASE_ID,
                "cachedResultName": "Lead Scraper - Johannesburg CRM",
            },
            "table": {
                "__rl": True,
                "mode": "list",
                "value": AIRTABLE_LEADS_TABLE,
                "cachedResultName": "Leads",
            },
            "columns": {
                "value": {
                    "Email": "={{ $json.sender }}",
                    "Follow Up Stage": 0,
                    "Status": "Ticket Reply - Do Not Follow Up",
                },
                "schema": [
                    {"id": "Email", "type": "string", "display": True,
                     "displayName": "Email"},
                    {"id": "Follow Up Stage", "type": "number", "display": True,
                     "displayName": "Follow Up Stage"},
                    {"id": "Status", "type": "string", "display": True,
                     "displayName": "Status"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Email"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Lead - Stop Follow Up",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1760, 1648],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # 32. Skip - Not Ticket Reply
    nodes.append(noop_node("Skip - Not Ticket Reply", [1760, 1780]))

    # ---- J. Logging ----

    # 33. Log to Email Sheet
    nodes.append({
        "parameters": {
            "operation": "append",
            "documentId": {"mode": "id", "value": EMAIL_LOG_SHEET_ID},
            "sheetName": {"mode": "name", "value": "Email Log"},
            "columns": {"mappingMode": "defineBelow", "value": {}},
            "options": {},
        },
        "id": uid(),
        "name": "Log to Email Sheet",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "onError": "continueRegularOutput",
        "position": [1500, 1960],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
    })

    # ---- K. Lead Detection ----

    # 34. Check If Lead
    nodes.append({
        "parameters": {"jsCode": CHECK_IF_LEAD_JS},
        "id": uid(),
        "name": "Check If Lead",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1500, 2160],
    })

    # 35. Is New Lead?
    nodes.append(if_node(
        "Is New Lead?",
        [cond("={{ $json.is_lead }}", "boolean", "true", True)],
        "and", [1760, 2160],
    ))

    # 36. Log New Lead
    nodes.append({
        "parameters": {
            "operation": "append",
            "documentId": {"mode": "id", "value": LEADS_SHEET_ID},
            "sheetName": {"mode": "name", "value": "Leads"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "date": "={{ $json.date }}",
                    "lead_name": "={{ $json.lead_name }}",
                    "email": "={{ $json.email }}",
                    "subject": "={{ $json.subject }}",
                    "interest": "={{ $json.interest }}",
                    "summary": "={{ $json.summary }}",
                    "urgency": "={{ $json.urgency }}",
                    "status": "={{ $json.status }}",
                    "follow_up_date": "={{ $json.follow_up_date }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log New Lead",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "onError": "continueRegularOutput",
        "position": [2016, 2112],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
    })

    # 37. Create Follow-Up (Google Calendar)
    nodes.append({
        "parameters": {
            "calendar": "primary",
            "start": "={{ $json.follow_up_date + 'T09:00:00' }}",
            "end": "={{ $json.follow_up_date + 'T09:30:00' }}",
            "additionalFields": {
                "description": (
                    "=Auto-generated sales lead follow-up.\n\n"
                    "Lead: {{ $json.lead_name }} ({{ $json.email }})\n"
                    "Interest: {{ $json.interest }}\n"
                    "Summary: {{ $json.summary }}"
                ),
                "summary": "=Follow up: {{ $json.lead_name }}",
            },
        },
        "id": uid(),
        "name": "Create Follow-Up",
        "type": "n8n-nodes-base.googleCalendar",
        "typeVersion": 1,
        "onError": "continueRegularOutput",
        "position": [2272, 2112],
        "credentials": {"googleCalendarOAuth2Api": CRED_GOOGLE_CALENDAR},
    })

    # 38. Not a Lead
    nodes.append(noop_node("Not a Lead", [2016, 2240]))

    # ---- L. Interested Reply Handling ----

    # 39. Is Interested Reply?
    nodes.append(if_node(
        "Is Interested Reply?",
        [
            cond("={{ $json.is_interested_reply }}", "boolean", "true", True),
            cond("={{ $json.sender }}", "string", "notContains",
                 "@eftcorp.atlassian.net", "block-eftcorp-interested"),
            cond("={{ $json.is_opt_out }}", "boolean", "false", False,
                 "guard-optout-interested"),
        ],
        "and", [1500, 2400],
    ))

    # 40. Send Thank You (Outlook reply with HTML)
    nodes.append({
        "parameters": {
            "resource": "message",
            "operation": "reply",
            "messageId": "={{ $json.original_message_id }}",
            "additionalFields": {
                "bodyContent": THANK_YOU_HTML,
                "bodyContentType": "HTML",
            },
        },
        "id": uid(),
        "name": "Send Thank You",
        "type": "n8n-nodes-base.microsoftOutlook",
        "typeVersion": 2,
        "onError": "continueRegularOutput",
        "position": [1760, 2352],
        "credentials": {"microsoftOutlookOAuth2Api": CRED_OUTLOOK},
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 1000,
    })

    # 41. Apply DNT Category
    nodes.append(categorize_node(
        "Apply DNT Category", "DNT", [2016, 2352]
    ))
    # Fix: target original message, not the reply
    nodes[-1]["parameters"]["messageId"] = \
        "={{ $('Check Reference Number').first().json.original_message_id }}"

    # 42. Update Lead Status
    nodes.append({
        "parameters": {
            "operation": "update",
            "documentId": {"mode": "id", "value": LEADS_SHEET_ID},
            "sheetName": {"mode": "name", "value": "Leads"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "email": "={{ $('Check Reference Number').first().json.sender }}",
                    "status": "Converted - Do Not Follow Up",
                },
            },
            "options": {
                "cellFormat": "USER_ENTERED",
                "handlingExtraData": "ignoreIt",
            },
            "dataMode": "defineBelow",
        },
        "id": uid(),
        "name": "Update Lead Status",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "onError": "continueRegularOutput",
        "position": [2272, 2352],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
    })

    # 43. Not Interested Reply
    nodes.append(noop_node("Not Interested Reply", [1760, 2496]))

    # ---- M. Opt-Out Detection ----

    # 44. Is Opt-Out?
    nodes.append(if_node(
        "Is Opt-Out?",
        [cond("={{ $json.is_opt_out }}", "boolean", "true", True)],
        "and", [1500, 2640],
    ))

    # 45. Apply Opt-Out DNT
    nodes.append(categorize_node(
        "Apply Opt-Out DNT", "DNT", [1760, 2592]
    ))

    # 46. Mark Opt-Out Read
    nodes.append(mark_read_node(
        "Mark Opt-Out Read",
        "={{ $json.original_message_id }}",
        [2016, 2592],
    ))

    # 47. Not Opt-Out
    nodes.append(noop_node("Not Opt-Out", [1760, 2720]))

    # ---- N. Error Handling ----

    # 48. Error Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "typeVersion": 1,
        "position": [208, -200],
    })

    # 49. Format Error Alert
    nodes.append({
        "parameters": {"jsCode": FORMAT_ERROR_JS},
        "id": uid(),
        "name": "Format Error Alert",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [464, -200],
    })

    # 50. Log Error to Sheet
    nodes.append({
        "parameters": {
            "operation": "append",
            "documentId": {"mode": "id", "value": EMAIL_LOG_SHEET_ID},
            "sheetName": {"mode": "name", "value": "Error Log"},
            "columns": {"mappingMode": "defineBelow", "value": {}},
            "options": {},
        },
        "id": uid(),
        "name": "Log Error to Sheet",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "onError": "continueRegularOutput",
        "position": [720, -200],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
    })

    # ---- Sticky Notes ----
    nodes.append({
        "parameters": {
            "content": (
                "## Business Email Management - Outlook Edition\n\n"
                "**Full feature parity with Gmail version.**\n\n"
                "**Flow:**\n"
                "1. Outlook Trigger polls every minute\n"
                "2. DNT category check + sender-level DNT\n"
                "3. AI classifies via Claude Sonnet (OpenRouter)\n"
                "4. Department routing with Outlook categories\n"
                "5. Draft replies with branded HTML signature\n"
                "6. Lead detection + Google Calendar follow-ups\n"
                "7. Interested reply -> thank-you + DNT\n"
                "8. Opt-out / bounce -> DNT + mark read\n"
                "9. Ticket references -> Airtable update\n"
                "10. All emails logged to Google Sheets\n\n"
                "**Outlook Categories Required:**\n"
                "Junk, Accounting_Finance, Customer_Support,\n"
                "Sales, Management, General, Urgent, DNT"
            ),
            "height": 520,
            "width": 380,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [-16, 112],
    })

    return nodes


# ==================================================================
# BUILD CONNECTIONS
# ==================================================================

def build_connections():
    """Build the connection map for all nodes."""
    def conn(node, index=0):
        return {"node": node, "type": "main", "index": index}

    return {
        # Triggers
        "When clicking 'Test workflow'": {
            "main": [[conn("Prepare Email Data")]]
        },
        "Outlook Trigger": {
            "main": [[conn("Has DNT Category?")]]
        },

        # DNT checks
        "Has DNT Category?": {
            "main": [
                [conn("Skip - DNT")],        # TRUE -> skip
                [conn("Check Sender DNT")],   # FALSE -> check sender
            ]
        },
        "Check Sender DNT": {
            "main": [[conn("Is Sender DNT?")]]
        },
        "Is Sender DNT?": {
            "main": [
                [conn("Skip - Sender Blocked")],  # TRUE -> skip
                [conn("Prepare Email Data")],      # FALSE -> process
            ]
        },

        # AI pipeline
        "Prepare Email Data": {
            "main": [[conn("AI Agent")]]
        },
        "AI Agent": {
            "main": [[conn("Parse AI Response")]]
        },
        "OpenRouter Chat Model": {
            "ai_languageModel": [[conn("AI Agent")]]
        },
        "Simple Memory": {
            "ai_memory": [[conn("AI Agent")]]
        },

        # Parse -> Check Reference -> fan-out
        "Parse AI Response": {
            "main": [[conn("Check Reference Number")]]
        },
        "Check Reference Number": {
            "main": [[
                conn("Route by Department"),
                conn("Is Urgent?"),
                conn("Is No-Reply?"),
                conn("Reply Needed?"),
                conn("Has Reference Number?"),
                conn("Log to Email Sheet"),
                conn("Check If Lead"),
                conn("Is Interested Reply?"),
                conn("Is Opt-Out?"),
            ]]
        },

        # Department routing
        "Route by Department": {
            "main": [
                [conn("Categorize Junk")],       # 0: Spam
                [conn("Categorize Finance")],    # 1: Finance
                [conn("Categorize Support")],    # 2: Support
                [conn("Categorize Sales")],      # 3: Sales
                [conn("Categorize Management")], # 4: Management
                [conn("Categorize General")],    # 5: fallback
            ]
        },
        "Categorize Junk": {
            "main": [[conn("Mark Spam Read")]]
        },

        # Urgency
        "Is Urgent?": {
            "main": [
                [conn("Categorize Urgent")],  # TRUE
                [conn("Not Urgent")],         # FALSE
            ]
        },

        # No-Reply
        "Is No-Reply?": {
            "main": [
                [conn("Mark No-Reply Read")],  # TRUE
                [conn("Not No-Reply")],        # FALSE
            ]
        },

        # Reply decision
        "Reply Needed?": {
            "main": [
                [conn("Create Draft Reply")],  # TRUE
                [conn("No Reply Needed")],     # FALSE
            ]
        },
        "Create Draft Reply": {
            "main": [[conn("Mark Replied Read")]]
        },

        # Ticket handling
        "Has Reference Number?": {
            "main": [
                [conn("Update Lead - Stop Follow Up")],  # TRUE
                [conn("Skip - Not Ticket Reply")],       # FALSE
            ]
        },

        # Lead detection
        "Check If Lead": {
            "main": [[conn("Is New Lead?")]]
        },
        "Is New Lead?": {
            "main": [
                [conn("Log New Lead")],  # TRUE
                [conn("Not a Lead")],    # FALSE
            ]
        },
        "Log New Lead": {
            "main": [[conn("Create Follow-Up")]]
        },

        # Interested reply
        "Is Interested Reply?": {
            "main": [
                [conn("Send Thank You")],       # TRUE
                [conn("Not Interested Reply")],  # FALSE
            ]
        },
        "Send Thank You": {
            "main": [[conn("Apply DNT Category")]]
        },
        "Apply DNT Category": {
            "main": [[conn("Update Lead Status")]]
        },

        # Opt-out
        "Is Opt-Out?": {
            "main": [
                [conn("Apply Opt-Out DNT")],  # TRUE
                [conn("Not Opt-Out")],        # FALSE
            ]
        },
        "Apply Opt-Out DNT": {
            "main": [[conn("Mark Opt-Out Read")]]
        },

        # Error handling
        "Error Trigger": {
            "main": [[conn("Format Error Alert")]]
        },
        "Format Error Alert": {
            "main": [[conn("Log Error to Sheet")]]
        },
    }


# ==================================================================
# BUILD WORKFLOW
# ==================================================================

def build_workflow():
    """Build the complete workflow JSON."""
    return {
        "name": "Business Email Management - Outlook",
        "nodes": build_nodes(),
        "connections": build_connections(),
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "errorWorkflow": "",
        },
        "staticData": None,
        "tags": [],
    }


# ==================================================================
# CLI
# ==================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/deploy_outlook_email_mgmt.py [build|deploy|activate]")
        sys.exit(1)

    action = sys.argv[1].lower()
    output_dir = Path(__file__).parent.parent / "workflows" / "email-mgmt"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "business_email_mgmt_outlook.json"

    # Always build first
    print("Building Business Email Management - Outlook workflow...")
    wf = build_workflow()
    node_count = len([n for n in wf["nodes"]
                      if n["type"] != "n8n-nodes-base.stickyNote"])
    print(f"  {node_count} functional nodes built")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {output_path}")

    if action == "build":
        print("\nBuild complete. Review the JSON before deploying.")
        _print_setup_checklist()
        return

    # Deploy
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

        # Check if workflow already exists by name
        existing = None
        try:
            all_wfs = client.list_workflows()
            for existing_wf in all_wfs:
                if existing_wf["name"] == wf["name"]:
                    existing = existing_wf
                    break
        except Exception:
            pass

        if existing:
            print(f"\n  Updating existing workflow {existing['id']}...")
            update_payload = {
                "name": wf["name"],
                "nodes": wf["nodes"],
                "connections": wf["connections"],
                "settings": wf.get("settings", {}),
            }
            result = client.update_workflow(existing["id"], update_payload)
            wf_id = existing["id"]
            print(f"  Updated! Workflow ID: {wf_id}")
        else:
            print("\n  Creating new workflow...")
            result = client.create_workflow(wf)
            wf_id = result.get("id", "unknown")
            print(f"  Deployed! Workflow ID: {wf_id}")

        if action == "activate":
            print("\nActivating...")
            client.activate_workflow(wf_id)
            print(f"  Workflow {wf_id} is now ACTIVE")

    _print_setup_checklist()
    print(f"\n  Workflow ID: {wf_id}")


def _print_setup_checklist():
    """Print pre-activation setup requirements."""
    print("\n--- Setup Checklist ---")
    print("1. Create Azure App Registration:")
    print("   - Redirect URI: https://ianimmelman89.app.n8n.cloud/rest/oauth2-credential/callback")
    print("   - Permissions: Mail.ReadWrite, Mail.Send, MailboxSettings.ReadWrite")
    print("2. Create 'Microsoft Outlook OAuth2 API' credential in n8n")
    print("3. Set N8N_CRED_OUTLOOK in .env (or update YOUR_CREDENTIAL_ID in workflow)")
    print("4. Create 8 Outlook categories in target mailbox:")
    print("   Junk, Accounting_Finance, Customer_Support, Sales,")
    print("   Management, General, Urgent, DNT")
    print("5. Verify Google Sheets 'Email Log' and 'Leads' tabs exist")
    print("6. Test with manual trigger before activating")


if __name__ == "__main__":
    main()

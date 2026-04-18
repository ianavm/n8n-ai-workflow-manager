"""
Business Email Management Automation - Gmail Edition (v2)

AI-powered email triage, classification, and routing for AnyVision Media.

Improvements over v1:
    1. Gmail trigger: 5-minute polling (was every minute = 43,200 execs/month)
    2. Removed buffer memory (unnecessary for one-shot classification)
    3. Error handler logs to Google Sheets (was Gmail - circular failure risk)
    4. continueOnFail on non-critical nodes (logging, Airtable, Calendar)
    5. Opt-out phrase detection (22 phrases) -> suppression table + DNT label
    6. Reference number detection folded into Parse AI Response (removed extra node)
    7. Blocked domain list (configurable, not just eftcorp)
    8. is_opt_out + is_blocked_domain guards on Reply Needed? check
    9. Manual Trigger routes through DNT check (was bypassing it)
    10. Switch v3.2 compliant conditions (no id/combinator in rules)

Features:
    - Gmail trigger (5min polling, unread only)
    - DNT label check (skip already-handled emails)
    - AI classification via Claude Sonnet (OpenRouter)
    - Department routing + Gmail labels (6 departments + fallback)
    - Urgency detection + urgent label
    - Auto-draft replies (branded HTML signature, no-reply/blocked guards)
    - No-reply sender detection + auto mark-read
    - Reference number detection (13 regex patterns)
    - Lead detection + Google Sheets + Calendar follow-up
    - Interested reply handling (thank-you + DNT label + lead status update)
    - Opt-out detection -> Airtable suppression + DNT label
    - Email logging to Google Sheets
    - Error logging to Google Sheets (avoids circular Gmail failure)

Usage:
    python tools/deploy_business_email_mgmt.py build       # Save JSON to workflows/
    python tools/deploy_business_email_mgmt.py deploy      # Build + deploy to n8n (inactive)
    python tools/deploy_business_email_mgmt.py activate    # Build + deploy + activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from datetime import datetime

# -- Environment -----------------------------------------------------------

env_path = Path(__file__).parent.parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(env_path)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
try:
    from n8n_client import N8nClient
except ImportError:
    N8nClient = None

# -- Credential Constants --------------------------------------------------

CRED_GMAIL = {"id": "EC2l4faLSdgePOM6", "name": "Gmail AVM Tutorial"}
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GOOGLE_SHEETS = {"id": "OkpDXxwI8WcUJp4P", "name": "Google Sheets AVM Tutorial"}
CRED_GOOGLE_CALENDAR = {"id": "I5zIYf0UxlkUt3KG", "name": "Google Calendar AVM Tutorial"}
CRED_AIRTABLE = {"id": "7TtMl7ZnJFpC4RGk", "name": "Lead Scraper Airtable"}

# -- Sheet / Table IDs -----------------------------------------------------

EMAIL_LOG_SHEET_ID = os.getenv(
    "EMAIL_LOG_SHEET_ID", "1Adp3x0ler5H69Cih5tbMLqWEgZMziebhnOEWbMPTvaA"
)
LEADS_SHEET_ID = os.getenv(
    "LEADS_SHEET_ID", "1G2P9gYuPKtqhDkkJaTVLbuA_yxj_IqTI7vuCfhFLklM"
)
AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_LEADS_TABLE = "tblOsuh298hB9WWrA"
AIRTABLE_SUPPRESSION_TABLE = "tbl0LtepawDzFYg4I"

# Addresses n8n itself sends from. Any inbound message with a bare from-address
# in this list is blocked from auto-drafting to prevent reply-to-self loops.
AUTOMATION_SENDERS: list[str] = [
    s.strip().lower()
    for s in os.getenv("AUTOMATION_SENDERS", "ian@anyvisionmedia.com").split(",")
    if s.strip()
]

# -- Gmail Label Map --------------------------------------------------------

LABELS = {
    "Finance": "Label_1",
    "Support": "Label_2",
    "Sales": "Label_3",
    "Management": "Label_4",
    "General": "Label_5",
    "Urgent": "Label_7",
    "Junk": "Label_8",
    "DNT": "Label_9",
}

# -- Helpers ----------------------------------------------------------------


def uid() -> str:
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


def conn(node: str, index: int = 0, conn_type: str = "main") -> dict:
    """Build a connection target dict."""
    return {"node": node, "type": conn_type, "index": index}


def gmail_node(
    name: str,
    position: list[int],
    operation: str = "addLabels",
    params: dict | None = None,
    on_error: str | None = None,
) -> dict:
    """Build a Gmail v2.2 node."""
    node = {
        "parameters": params or {},
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.2,
        "onError": "continueRegularOutput",
        "position": position,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    }
    if on_error:
        node["onError"] = on_error
    return node


def if_node(
    name: str,
    conditions: list[dict],
    position: list[int],
    combinator: str = "and",
    case_sensitive: bool = True,
    type_validation: str = "strict",
) -> dict:
    """Build an If v2.3 node."""
    return {
        "parameters": {
            "conditions": {
                "options": {
                    "version": 2,
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
        "typeVersion": 2.3,
        "position": position,
    }


def noop_node(name: str, position: list[int]) -> dict:
    """Build a No Operation node."""
    return {
        "parameters": {},
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": position,
    }


def code_node(name: str, js_code: str, position: list[int], on_error: str | None = None) -> dict:
    """Build a Code v2 node."""
    node = {
        "parameters": {"jsCode": js_code},
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
    }
    if on_error:
        node["onError"] = on_error
    return node


def cond_str(left: str, operation: str, right: str) -> dict:
    """Build a binary string condition (equals, contains, notContains)."""
    return {
        "leftValue": left,
        "rightValue": right,
        "operator": {"type": "string", "operation": operation},
    }


def cond_str_unary(left: str, operation: str) -> dict:
    """Build a unary string condition (empty, notEmpty)."""
    return {
        "leftValue": left,
        "operator": {"type": "string", "operation": operation, "singleValue": True},
    }


def cond_bool(left: str, operation: str) -> dict:
    """Build a unary boolean condition (true, false). No rightValue."""
    return {
        "leftValue": left,
        "operator": {"type": "boolean", "operation": operation, "singleValue": True},
    }


# -- Email Signature HTML ---------------------------------------------------

AVM_SIGNATURE = (
    '<table cellpadding="0" cellspacing="0" border="0" '
    "style=\"font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif;"
    'font-size:14px;line-height:1.4;color:#333333;">'
    "<tr>"
    '<td style="vertical-align:top;padding-right:18px;">'
    '<a href="https://www.anyvisionmedia.com" target="_blank" style="text-decoration:none;">'
    '<img src="https://www.anyvisionmedia.com/logo-icon.png" alt="AnyVision Media" '
    'width="70" style="display:block;border:0;width:70px;height:70px;" />'
    "</a></td>"
    '<td style="vertical-align:top;padding-left:18px;border-left:3px solid #6C63FF;">'
    '<table cellpadding="0" cellspacing="0" border="0">'
    "<tr><td style=\"font-size:20px;font-weight:700;color:#0A0F1C;padding-bottom:2px;"
    'letter-spacing:-0.3px;">Ian</td></tr>'
    '<tr><td style="font-size:13px;font-weight:400;color:#6B7280;padding-bottom:10px;">'
    "Founder&nbsp;&nbsp;&#183;&nbsp;&nbsp;"
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
    "Johannesburg, South Africa</td></tr>"
    "</table></td></tr></table>"
)

# -- JavaScript Code Strings ------------------------------------------------

PREPARE_EMAIL_JS = r"""const items = $input.all();
const results = [];

// Blocked domains - emails from these are classified but never auto-replied
const BLOCKED_DOMAINS = [
  '@eftcorp.atlassian.net',
  '@noreply.github.com',
  '@notifications.google.com',
  '@mailer-daemon.',
  // n8n platform alerts (execution reports, workflow failures, billing)
  '@n8n.io',
  '@app.n8n.cloud',
  '@ianimmelman89.app.n8n.cloud'
];

// Subject patterns for n8n-generated reports/updates - no drafts needed
// Catches self-sent workflow reports even when 'from' is ian@anyvisionmedia.com
const N8N_REPORT_SUBJECT_PATTERNS = [
  /\bworkflow\s+execution/i,
  /\bexecution\s+(report|failed|error)/i,
  /\[n8n\]/i,
  /\bn8n\s+(alert|report|notification|update)/i,
  /\b(daily|weekly|monthly)\s+report\b/i,
  /\baudit\s+report\b/i,
  /\bbudget\s+enforcer/i,
  /\[ADS-\d+\]/i,
  /\[SHM\]/i,
  /\[ERR\]/i,
  /\[LI-\d+\]/i,
  /\bSHM\s+health\s+check/i,
  /\bworkflow\s+(update|summary)/i
];

for (const item of items) {
  const emailData = {
    from: item.json.from || item.json.sender || '',
    to: item.json.to || '',
    subject: item.json.subject || '',
    date: item.json.date || new Date().toISOString(),
    body: (item.json.textPlain || item.json.snippet || item.json.text || '').substring(0, 3000),
    hasAttachments: item.json.attachments ? item.json.attachments.length > 0 : false,
    attachmentCount: item.json.attachments ? item.json.attachments.length : 0,
    messageId: item.json.id || item.json.messageId || '',
    threadId: item.json.threadId || '',
    labelIds: item.json.labelIds || []
  };

  const fromLower = emailData.from.toLowerCase();
  const isBlockedDomain = BLOCKED_DOMAINS.some(d => fromLower.includes(d));
  const isN8nReport = N8N_REPORT_SUBJECT_PATTERNS.some(rx => rx.test(emailData.subject || ''));

  const classificationPrompt = `Analyze this business email. Return ONLY valid JSON, no markdown, no backticks.

From: ${emailData.from}
Subject: ${emailData.subject}
Date: ${emailData.date}
Body:
${emailData.body}
Has Attachments: ${emailData.hasAttachments ? 'Yes (' + emailData.attachmentCount + ')' : 'No'}

Return this exact JSON:
{
  "sender": "<email>",
  "sender_name": "<name>",
  "subject": "<subject>",
  "intent": "<what sender wants>",
  "tone": "<formal|informal|urgent|angry|friendly|neutral>",
  "urgency": "<high|medium|low>",
  "action_required": true or false,
  "department": "<ONE of: Accounting_Finance|Customer_Support|Sales|Management|Admin|Legal|Internal|Spam_Irrelevant>",
  "tags": ["<from: Invoice,Payment,Refund,Complaint,New_Lead,Contract,Meeting_Request,Follow_Up,Escalation,Urgent>"],
  "is_spam": true or false,
  "suggested_response": "<professional reply if action_required, else null>",
  "summary": "<1-2 sentence summary>",
  "escalation_needed": true or false,
  "is_interested_reply": true or false
}

Rules:
- Accounting_Finance: invoices, payments, billing, refunds
- Customer_Support: complaints, technical issues, service support
- Sales: new enquiries, pricing, leads
- Management: strategy, legal, partnerships, high-level complaints
- Spam_Irrelevant: suspicious links, phishing, irrelevant promos
- Mark urgency HIGH if: urgent/ASAP in subject, legal threats, payment issues
- Responses must be professional and concise`;

  results.push({
    json: {
      ...emailData,
      classificationPrompt,
      is_blocked_domain: isBlockedDomain,
      is_n8n_report: isN8nReport
    }
  });
}

return results;"""

def build_parse_ai_response_js(automation_senders: list[str]) -> str:
    """Build the Parse AI Response Code node body, with the automation-sender
    blocklist injected as a JS array literal. Serialize via json.dumps so the
    JS syntax is guaranteed valid regardless of the Python list contents.
    """
    return (
        r"""const items = $input.all();
const results = [];

// Addresses n8n itself sends from — inbound messages from these are never
// auto-drafted (prevents reply-to-self loops when a workflow-sent email
// lands back in the inbox via Cc, auto-forward, or send-as alias).
const AUTOMATION_SENDERS = """
        + json.dumps(automation_senders)
        + r""";

// Opt-out phrases (case-insensitive)
const OPT_OUT_PHRASES = [
  'unsubscribe', 'opt out', 'opt-out', 'remove me', 'stop emailing',
  'not interested', 'no thanks', 'no thank you', "i'll pass", 'take me off',
  'remove from list', 'stop sending', 'do not contact', "don't contact",
  'leave me alone', 'stop messaging', 'reported as spam', 'block sender',
  'cease and desist', 'gdpr removal', 'popia removal', 'remove my data'
];

// Ticket / reference number patterns
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
  /\b[A-Z]{2,4}-\d{4,}\b/
];

const SIGNATURE = `"""
        + AVM_SIGNATURE.replace("`", "\\`")
        + r"""`;

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
      department: 'Admin',
      tags: ['Escalation'],
      is_spam: false,
      suggested_response: null,
      summary: 'Email could not be auto-classified. Manual review required.',
      escalation_needed: true,
      is_interested_reply: false
    };
  }

  // Reference number detection
  const subject = (emailData.subject || '').toUpperCase();
  const body = (emailData.body || '').substring(0, 2000).toUpperCase();
  const textToCheck = subject + ' ' + body;

  let has_reference_number = false;
  let matched_reference_pattern = '';
  for (const pattern of TICKET_PATTERNS) {
    const match = textToCheck.match(pattern);
    if (match) {
      has_reference_number = true;
      matched_reference_pattern = match[0];
      break;
    }
  }

  // Opt-out detection
  const bodyLower = (emailData.body || '').toLowerCase();
  const subjectLower = (emailData.subject || '').toLowerCase();
  const is_opt_out = OPT_OUT_PHRASES.some(phrase =>
    bodyLower.includes(phrase) || subjectLower.includes(phrase)
  );

  // Automation-sender detection — extract the bare email address from the
  // "From" header (which may be "Display Name <addr@host>") and check against
  // the AUTOMATION_SENDERS blocklist. Equality match on the bare address so a
  // legitimate client like iansomething@example.com is not blocked by a
  // substring check.
  const fromRaw = emailData.from || '';
  const bracketMatch = fromRaw.match(/<([^>]+)>/);
  const original_from_address = (bracketMatch ? bracketMatch[1] : fromRaw)
    .trim()
    .toLowerCase();
  const is_automation_sender = AUTOMATION_SENDERS.includes(original_from_address);

  // Build HTML response from suggested_response
  const html_response = (() => {
    const text = parsed.suggested_response || '';
    if (!text) return '';
    const paragraphs = text.split(/\n\n+/);
    const htmlParagraphs = paragraphs
      .map(p => p.replace(/\n/g, '<br>'))
      .map(p => '<p style="margin:0 0 12px 0;font-family:Segoe UI,Helvetica Neue,Arial,' +
        'sans-serif;font-size:14px;line-height:1.5;color:#333333;">' + p + '</p>')
      .join('');
    return '<div style="font-family:Segoe UI,Helvetica Neue,Arial,sans-serif;">' +
      htmlParagraphs + '<br>' + SIGNATURE + '</div>';
  })();

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
      department: parsed.department || 'Admin',
      tags: parsed.tags || [],
      tags_string: (parsed.tags || []).join(', '),
      is_spam: parsed.is_spam || false,
      suggested_response: parsed.suggested_response || '',
      html_response,
      summary: parsed.summary || '',
      escalation_needed: parsed.escalation_needed || false,
      is_interested_reply: parsed.is_interested_reply || false,
      has_reference_number,
      matched_reference_pattern,
      is_opt_out,
      original_from_address,
      is_automation_sender,
      is_blocked_domain: emailData.is_blocked_domain || false,
      is_n8n_report: emailData.is_n8n_report || false,
      processed_at: new Date().toISOString(),
      ticket_number: 'TKT-' + Date.now()
    }
  });
}

return results;"""
)

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

# -- AI System Message ------------------------------------------------------

AI_SYSTEM_MESSAGE = (
    "You are the AI Email Manager for AnyVision Media, a digital media and "
    "technology agency. Your job is to analyze incoming business emails and "
    "return a structured JSON classification.\n\n"
    "## Your Task\n"
    "For every email you receive, analyze it and return ONLY a valid JSON "
    "object. No markdown formatting, no backticks, no explanation text - "
    "just the raw JSON.\n\n"
    "## Company Context\n"
    "- Company: AnyVision Media (digital media, AI solutions, web development)\n"
    "- Owner: Ian Immelman (ian@anyvisionmedia.com)\n"
    "- Services: AI workflow automation, web development, social media "
    "management, real estate tech solutions\n"
    "- Tone: Professional but approachable, tech-savvy\n\n"
    "## JSON Output Format\n"
    "Return exactly this structure:\n"
    "{\n"
    '  "sender": "<sender email address>",\n'
    '  "sender_name": "<sender display name>",\n'
    '  "subject": "<email subject line>",\n'
    '  "intent": "<1 sentence: what the sender wants or needs>",\n'
    '  "tone": "<one of: formal, informal, urgent, angry, friendly, neutral>",\n'
    '  "urgency": "<one of: high, medium, low>",\n'
    '  "action_required": true or false,\n'
    '  "department": "<ONE of: Accounting_Finance, Customer_Support, Sales, '
    'Management, Admin, Legal, Internal, Spam_Irrelevant>",\n'
    '  "tags": ["<applicable tags from the list below>"],\n'
    '  "is_spam": true or false,\n'
    '  "suggested_response": "<a professional draft reply if action_required '
    'is true, otherwise null>",\n'
    '  "summary": "<1-2 sentence summary of the email>",\n'
    '  "escalation_needed": true or false,\n'
    '  "is_interested_reply": true or false\n'
    "}\n\n"
    "## Department Classification Rules\n"
    "- **Accounting_Finance**: Invoices, payments, billing inquiries, refund "
    "requests, financial statements, tax documents\n"
    "- **Customer_Support**: Service complaints, technical issues, bug reports, "
    "account help, feature requests\n"
    "- **Sales**: New business enquiries, pricing requests, partnership "
    "proposals, lead generation, RFP responses\n"
    "- **Management**: Strategic decisions, legal matters, high-level "
    "partnerships, media/PR, executive communications, escalated complaints\n"
    "- **Admin**: Documentation, compliance, vendor setup, office operations\n"
    "- **Legal**: Contracts, legal threats, regulatory matters, NDAs\n"
    "- **Internal**: Team communications, internal updates, HR matters\n"
    "- **Spam_Irrelevant**: Unsolicited marketing, phishing attempts, "
    "suspicious links, irrelevant promotions\n\n"
    "## Available Tags\n"
    "Invoice, Payment, Refund, Complaint, New_Lead, Contract, Meeting_Request, "
    "Follow_Up, Escalation, Urgent\n\n"
    "## Urgency Rules\n"
    "Mark as HIGH if any of these apply:\n"
    '- Subject contains "urgent", "ASAP", "immediate", "critical"\n'
    "- Legal threats or regulatory deadlines\n"
    "- Payment disputes or overdue invoices\n"
    "- Escalated customer complaints\n"
    "- Time-sensitive business opportunities\n\n"
    "## Response Writing Rules (for suggested_response)\n"
    "When action_required is true, write a professional, well-structured reply:\n\n"
    "**STRUCTURE:**\n"
    "1. Greeting - Personalized with sender's name\n"
    "2. Acknowledgment - Thank them and acknowledge their specific concern\n"
    "3. Response - Address their question or request (1-2 paragraphs)\n"
    "4. Next Steps - What happens next (if applicable)\n"
    "5. Closing - Professional sign-off\n\n"
    "**CONTENT GUIDELINES:**\n"
    "- Acknowledge receipt of their email\n"
    "- Be professional, warm, and concise\n"
    "- Never promise specific timelines without verification\n"
    "- Never confirm financial or legal decisions\n"
    "- Never reveal that this is an automated system\n"
    "- Match their tone (formal vs casual) appropriately\n"
    "- Use proper line breaks (\\n\\n between paragraphs)\n\n"
    "When action_required is false or the email is spam, set "
    "suggested_response to null.\n\n"
    "## Interested Reply Detection Rules\n"
    "Set is_interested_reply to TRUE if ALL of these apply:\n"
    "- The email appears to be a REPLY to a previous outreach from "
    "AnyVision Media\n"
    "- The sender expresses positive interest (wants to learn more, schedule "
    "a call, get pricing, says 'interested', 'sounds good', 'tell me more')\n"
    "- The sender is NOT from AnyVision Media itself\n\n"
    "Set is_interested_reply to FALSE for:\n"
    "- First-time inbound emails (not replies to our outreach)\n"
    "- Negative responses ('not interested', 'unsubscribe', 'remove me')\n"
    "- Automated responses / out-of-office replies\n"
    "- Spam or irrelevant emails\n\n"
    "CRITICAL: Return ONLY the JSON object. No other text."
)

# -- Thank You Reply HTML ---------------------------------------------------

THANK_YOU_HTML = (
    '<div style="font-family:\'Segoe UI\',\'Helvetica Neue\',Arial,sans-serif;'
    'font-size:14px;line-height:1.5;color:#333333;">'
    '<p style="margin:0 0 12px 0;">Hi {{ $json.sender_name }},</p>'
    '<p style="margin:0 0 12px 0;">Thank you so much for getting back to us! '
    "We really appreciate your interest.</p>"
    '<p style="margin:0 0 12px 0;">I\'ll be in touch shortly to discuss how '
    "AnyVision Media can help you further. In the meantime, if you have any "
    "questions, feel free to reply to this email.</p>"
    '<p style="margin:0 0 12px 0;">Looking forward to connecting!</p>'
    "<br>" + AVM_SIGNATURE + "</div>"
)


# ==========================================================================
#  BUILD NODES
# ==========================================================================


def build_nodes() -> list[dict]:
    """Build all workflow nodes."""
    nodes: list[dict] = []

    # ── Triggers ──────────────────────────────────────────────────────

    # 1. Manual Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "When clicking 'Test workflow'",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [200, 160],
    })

    # 2. Gmail Trigger v1.3 - polling is automatic in v1.3 (no pollTimes param)
    # n8n Cloud controls the polling interval via workflow settings.
    # Default is ~2min for active workflows; unread filter keeps volume low.
    nodes.append({
        "parameters": {
            "filters": {"readStatus": "unread"},
            "options": {},
        },
        "id": uid(),
        "name": "Gmail Trigger",
        "type": "n8n-nodes-base.gmailTrigger",
        "typeVersion": 1.3,
        "position": [200, 432],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # 3. Error Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "typeVersion": 1,
        "position": [-200, 600],
    })

    # ── Pre-filter ────────────────────────────────────────────────────

    # 4. Has DNT Label? (both Manual + Gmail route through this)
    nodes.append(if_node(
        "Has DNT Label?",
        [cond_bool("={{ ($json.labelIds || []).includes('" + LABELS["DNT"] + "') }}", "true")],
        [340, 432],
    ))

    # 5. Skip - DNT
    nodes.append(noop_node("Skip - DNT", [340, 608]))

    # ── Classification ────────────────────────────────────────────────

    # 6. Prepare Email Data
    nodes.append(code_node("Prepare Email Data", PREPARE_EMAIL_JS, [460, 432]))

    # 7. AI Agent (no buffer memory - one-shot classification)
    nodes.append({
        "parameters": {
            "promptType": "define",
            "text": "={{ $json.classificationPrompt }}",
            "options": {
                "systemMessage": AI_SYSTEM_MESSAGE,
                "maxIterations": 1,
                "returnIntermediateSteps": False,
            },
        },
        "type": "@n8n/n8n-nodes-langchain.agent",
        "typeVersion": 3.1,
        "position": [660, 432],
        "id": uid(),
        "name": "AI Agent",
    })

    # 8. OpenRouter Chat Model (Claude Sonnet)
    nodes.append({
        "parameters": {
            "model": "anthropic/claude-sonnet-4",
            "options": {},
        },
        "type": "@n8n/n8n-nodes-langchain.lmChatOpenRouter",
        "typeVersion": 1,
        "position": [660, 680],
        "id": uid(),
        "name": "OpenRouter Chat Model",
        "credentials": {"openRouterApi": CRED_OPENROUTER},
    })

    # 9. Parse AI Response (includes reference number + opt-out + automation-sender detection)
    nodes.append(code_node(
        "Parse AI Response",
        build_parse_ai_response_js(AUTOMATION_SENDERS),
        [990, 432],
    ))

    # ── Department Routing ────────────────────────────────────────────

    # 10. Switch - Route by Department (v3.4 with outputKey per rule)
    dept_labels = [
        ("Spam_Irrelevant", "Spam"),
        ("Accounting_Finance", "Finance"),
        ("Customer_Support", "Support"),
        ("Sales", "Sales"),
        ("Management", "Management"),
    ]
    dept_rules = []
    for dept, output_key in dept_labels:
        dept_rules.append({
            "outputKey": output_key,
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                },
                "conditions": [
                    cond_str("={{ $json.department }}", "equals", dept),
                ],
            },
        })

    nodes.append({
        "parameters": {
            "rules": {"values": dept_rules},
            "options": {"fallbackOutput": "extra"},
        },
        "id": uid(),
        "name": "Route by Department",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.4,
        "position": [1250, 432],
    })

    # 11-16. Gmail Label nodes for each department
    label_defs = [
        ("Label Junk", LABELS["Junk"], [1500, 112]),
        ("Label Finance", LABELS["Finance"], [1500, 288]),
        ("Label Support", LABELS["Support"], [1500, 464]),
        ("Label Sales", LABELS["Sales"], [1500, 640]),
        ("Label Management", LABELS["Management"], [1500, 832]),
        ("Label General", LABELS["General"], [1500, 1008]),
    ]
    for name, label_id, pos in label_defs:
        nodes.append(gmail_node(name, pos, params={
            "operation": "addLabels",
            "messageId": "={{ $json.original_message_id }}",
            "labelIds": [label_id],
        }))

    # 17. Mark Spam Read
    nodes.append(gmail_node("Mark Spam Read", [1760, 112], params={
        "operation": "markAsRead",
        "messageId": "={{ $('Parse AI Response').first().json.original_message_id }}",
    }))

    # ── Urgency Check ─────────────────────────────────────────────────

    # 18. Is Urgent?
    nodes.append(if_node(
        "Is Urgent?",
        [cond_str("={{ $json.urgency }}", "equals", "high")],
        [1250, 1200],
    ))

    # 19. Label Urgent
    nodes.append(gmail_node("Label Urgent", [1500, 1152], params={
        "operation": "addLabels",
        "messageId": "={{ $json.original_message_id }}",
        "labelIds": [LABELS["Urgent"]],
    }))

    # 20. Not Urgent
    nodes.append(noop_node("Not Urgent", [1500, 1312]))

    # ── No-Reply Detection ────────────────────────────────────────────

    # 21. Is No-Reply?
    nodes.append(if_node(
        "Is No-Reply?",
        [
            cond_str("={{ $json.sender }}", "contains", "noreply"),
            cond_str("={{ $json.sender }}", "contains", "no-reply"),
            cond_str("={{ $json.sender }}", "contains", "donotreply"),
        ],
        [1250, 1808],
        combinator="or",
        case_sensitive=False,
        type_validation="loose",
    ))

    # 22. Mark No-Reply Read
    nodes.append(gmail_node("Mark No-Reply Read", [1500, 1744], params={
        "operation": "markAsRead",
        "messageId": "={{ $json.original_message_id }}",
    }))

    # 23. Not No-Reply
    nodes.append(noop_node("Not No-Reply", [1500, 1904]))

    # ── Reply Logic ───────────────────────────────────────────────────

    # 24. Reply Needed? (guards: action required + not spam + not no-reply
    #     + not blocked domain + not opt-out + no reference number
    #     + not an n8n report/update + sender is not one of our own automation
    #     addresses — read-only, never draft)
    nodes.append(if_node(
        "Reply Needed?",
        [
            cond_bool("={{ $json.action_required }}", "true"),
            cond_str_unary("={{ $json.suggested_response }}", "notEmpty"),
            cond_bool("={{ $json.is_spam }}", "false"),
            cond_str("={{ $json.sender }}", "notContains", "noreply"),
            cond_str("={{ $json.sender }}", "notContains", "no-reply"),
            cond_str("={{ $json.sender }}", "notContains", "donotreply"),
            cond_str("={{ $json.original_body }}", "notContains", "no reply"),
            cond_bool("={{ $json.has_reference_number }}", "false"),
            cond_bool("={{ $json.is_opt_out }}", "false"),
            cond_bool("={{ $json.is_blocked_domain }}", "false"),
            cond_bool("={{ $json.is_n8n_report }}", "false"),
            cond_bool("={{ $json.is_automation_sender }}", "false"),
        ],
        [1250, 1520],
        case_sensitive=False,
        type_validation="loose",
    ))

    # 25. Create Reply (draft via resource=draft, operation=create)
    nodes.append(gmail_node("Create Reply", [1500, 1472], params={
        "resource": "draft",
        "operation": "create",
        "subject": "={{ 'Re: ' + $json.original_subject }}",
        "message": "={{ $json.html_response }}",
        "emailType": "html",
        "options": {
            "threadId": "={{ $json.original_thread_id }}",
            "sendTo": "={{ $json.sender }}",
        },
    }))

    # 26. No Reply Needed
    nodes.append(noop_node("No Reply Needed", [1500, 1632]))

    # ── Reference Number Check ────────────────────────────────────────

    # 27. Has Reference Number?
    nodes.append(if_node(
        "Has Reference Number?",
        [cond_bool("={{ $json.has_reference_number }}", "true")],
        [1250, 1680],
    ))

    # 28. Update Lead - Stop Follow Up (Airtable)
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
        "typeVersion": 2.2,
        "onError": "continueRegularOutput",
        "position": [1500, 1648],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # 29. Skip - Not Ticket Reply
    nodes.append(noop_node("Skip - Not Ticket Reply", [1500, 1780]))

    # ── Email Logging ─────────────────────────────────────────────────

    # 30. Log to Email Sheet
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
        "typeVersion": 4.7,
        "onError": "continueRegularOutput",
        "position": [1250, 1950],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "onError": "continueRegularOutput",
    })

    # ── Lead Detection ────────────────────────────────────────────────

    # 31. Check If Lead
    nodes.append(code_node("Check If Lead", CHECK_IF_LEAD_JS, [1250, 2080]))

    # 32. Is New Lead?
    nodes.append(if_node(
        "Is New Lead?",
        [cond_bool("={{ $json.is_lead }}", "true")],
        [1500, 2080],
    ))

    # 33. Log New Lead
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
        "typeVersion": 4.7,
        "onError": "continueRegularOutput",
        "position": [1760, 2032],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "onError": "continueRegularOutput",
    })

    # 34. Create Follow-Up (Calendar v1 — plain string calendar, default create)
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
        "position": [2030, 2032],
        "credentials": {"googleCalendarOAuth2Api": CRED_GOOGLE_CALENDAR},
        "onError": "continueRegularOutput",
    })

    # 35. Not a Lead
    nodes.append(noop_node("Not a Lead", [1760, 2160]))

    # ── Interested Reply Handling ─────────────────────────────────────

    # 36. Is Interested Reply?
    nodes.append(if_node(
        "Is Interested Reply?",
        [
            cond_bool("={{ $json.is_interested_reply }}", "true"),
            cond_str("={{ $json.sender }}", "notContains", "@eftcorp.atlassian.net"),
        ],
        [1250, 2340],
    ))

    # 37. Send Thank You (= prefix for expression in HTML)
    nodes.append(gmail_node("Send Thank You", [1500, 2288], params={
        "operation": "reply",
        "messageId": "={{ $json.original_message_id }}",
        "message": "=" + THANK_YOU_HTML,
        "options": {},
    }))

    # 38. Apply DNT Label
    nodes.append(gmail_node("Apply DNT Label", [1760, 2288], params={
        "operation": "addLabels",
        "messageId": (
            "={{ $('Send Thank You').first().json.id || "
            "$json.original_message_id }}"
        ),
        "labelIds": [LABELS["DNT"]],
    }))

    # 39. Update Lead Status (Sheets v4.7 with resourceMapper)
    nodes.append({
        "parameters": {
            "operation": "update",
            "documentId": {"mode": "id", "value": LEADS_SHEET_ID},
            "sheetName": {"mode": "name", "value": "Leads"},
            "columns": {
                "mappingMode": "defineBelow",
                "matchingColumns": ["email"],
                "value": {
                    "email": "={{ $json.sender }}",
                    "status": "Converted - Do Not Follow Up",
                },
            },
            "options": {
                "cellFormat": "USER_ENTERED",
            },
        },
        "id": uid(),
        "name": "Update Lead Status",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.7,
        "onError": "continueRegularOutput",
        "position": [2030, 2288],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "onError": "continueRegularOutput",
    })

    # 40. Not Interested Reply
    nodes.append(noop_node("Not Interested Reply", [1500, 2432]))

    # ── Opt-Out Detection (NEW) ───────────────────────────────────────

    # 41. Is Opt-Out?
    nodes.append(if_node(
        "Is Opt-Out?",
        [cond_bool("={{ $json.is_opt_out }}", "true")],
        [1250, 2600],
    ))

    # 42. Mark Opt-Out in Suppression Table (Airtable)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {
                "__rl": True,
                "mode": "list",
                "value": AIRTABLE_BASE_ID,
                "cachedResultName": "Lead Scraper - Johannesburg CRM",
            },
            "table": {
                "__rl": True,
                "mode": "list",
                "value": AIRTABLE_SUPPRESSION_TABLE,
                "cachedResultName": "Email Suppression",
            },
            "columns": {
                "value": {
                    "Email": "={{ $json.sender }}",
                    "Status": "Opted Out",
                    "Source": "Email Management - Auto Detected",
                    "Date Added": "={{ $json.processed_at }}",
                },
                "schema": [
                    {"id": "Email", "type": "string", "display": True,
                     "displayName": "Email"},
                    {"id": "Status", "type": "string", "display": True,
                     "displayName": "Status"},
                    {"id": "Source", "type": "string", "display": True,
                     "displayName": "Source"},
                    {"id": "Date Added", "type": "string", "display": True,
                     "displayName": "Date Added"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Mark Opt-Out Suppression",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.2,
        "onError": "continueRegularOutput",
        "position": [1500, 2560],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # 43. Apply Opt-Out DNT Label
    nodes.append(gmail_node("Apply Opt-Out DNT", [1760, 2560], params={
        "operation": "addLabels",
        "messageId": "={{ $('Parse AI Response').first().json.original_message_id }}",
        "labelIds": [LABELS["DNT"]],
    }))

    # 44. Not Opt-Out
    nodes.append(noop_node("Not Opt-Out", [1500, 2700]))

    # ── Error Handler ─────────────────────────────────────────────────

    # 45. Log Error to Sheets (NOT Gmail - prevents circular failure)
    nodes.append({
        "parameters": {
            "operation": "append",
            "documentId": {"mode": "id", "value": EMAIL_LOG_SHEET_ID},
            "sheetName": {"mode": "name", "value": "Error Log"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "timestamp": "={{ new Date().toISOString() }}",
                    "workflow": "={{ $json.workflow.name }}",
                    "error": "={{ $json.execution.error.message }}",
                    "node": "={{ $json.execution.lastNodeExecuted }}",
                    "execution_url": "={{ $json.execution.url }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Error to Sheets",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.7,
        "onError": "continueRegularOutput",
        "position": [56, 600],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "onError": "continueRegularOutput",
    })

    return nodes


# ==========================================================================
#  BUILD CONNECTIONS
# ==========================================================================


def build_connections() -> dict:
    """Build the workflow connection map."""
    return {
        # Triggers -> DNT check (both Manual and Gmail route through it)
        "When clicking 'Test workflow'": {
            "main": [[conn("Has DNT Label?")]],
        },
        "Gmail Trigger": {
            "main": [[conn("Has DNT Label?")]],
        },
        # DNT check: TRUE (has DNT) -> Skip, FALSE (no DNT) -> Prepare
        "Has DNT Label?": {
            "main": [
                [conn("Skip - DNT")],       # output 0 = TRUE
                [conn("Prepare Email Data")],  # output 1 = FALSE
            ],
        },
        # Classification pipeline
        "Prepare Email Data": {
            "main": [[conn("AI Agent")]],
        },
        "AI Agent": {
            "main": [[conn("Parse AI Response")]],
        },
        # LLM -> AI Agent
        "OpenRouter Chat Model": {
            "ai_languageModel": [[conn("AI Agent", conn_type="ai_languageModel")]],
        },
        # Parse AI Response fans out to 9 parallel branches
        "Parse AI Response": {
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
            ]],
        },
        # Department routing (Switch outputs 0-4 + fallback)
        "Route by Department": {
            "main": [
                [conn("Label Junk")],        # 0 = Spam_Irrelevant
                [conn("Label Finance")],     # 1 = Accounting_Finance
                [conn("Label Support")],     # 2 = Customer_Support
                [conn("Label Sales")],       # 3 = Sales
                [conn("Label Management")],  # 4 = Management
                [conn("Label General")],     # 5 = fallback (extra)
            ],
        },
        "Label Junk": {
            "main": [[conn("Mark Spam Read")]],
        },
        # Urgency
        "Is Urgent?": {
            "main": [
                [conn("Label Urgent")],  # TRUE
                [conn("Not Urgent")],    # FALSE
            ],
        },
        # No-reply
        "Is No-Reply?": {
            "main": [
                [conn("Mark No-Reply Read")],  # TRUE
                [conn("Not No-Reply")],         # FALSE
            ],
        },
        # Reply logic
        "Reply Needed?": {
            "main": [
                [conn("Create Reply")],      # TRUE
                [conn("No Reply Needed")],   # FALSE
            ],
        },
        # Reference number
        "Has Reference Number?": {
            "main": [
                [conn("Update Lead - Stop Follow Up")],  # TRUE
                [conn("Skip - Not Ticket Reply")],       # FALSE
            ],
        },
        # Lead detection
        "Check If Lead": {
            "main": [[conn("Is New Lead?")]],
        },
        "Is New Lead?": {
            "main": [
                [conn("Log New Lead")],   # TRUE
                [conn("Not a Lead")],     # FALSE
            ],
        },
        "Log New Lead": {
            "main": [[conn("Create Follow-Up")]],
        },
        # Interested reply
        "Is Interested Reply?": {
            "main": [
                [conn("Send Thank You")],         # TRUE
                [conn("Not Interested Reply")],    # FALSE
            ],
        },
        "Send Thank You": {
            "main": [[conn("Apply DNT Label")]],
        },
        "Apply DNT Label": {
            "main": [[conn("Update Lead Status")]],
        },
        # Opt-out (NEW)
        "Is Opt-Out?": {
            "main": [
                [conn("Mark Opt-Out Suppression")],  # TRUE
                [conn("Not Opt-Out")],                # FALSE
            ],
        },
        "Mark Opt-Out Suppression": {
            "main": [[conn("Apply Opt-Out DNT")]],
        },
        # Error handler
        "Error Trigger": {
            "main": [[conn("Log Error to Sheets")]],
        },
    }


# ==========================================================================
#  BUILD WORKFLOW
# ==========================================================================


def build_workflow() -> dict:
    """Assemble the complete workflow JSON."""
    return {
        "name": "Business Email Management Automation",
        "nodes": build_nodes(),
        "connections": build_connections(),
        "settings": {
            "executionOrder": "v1",
        },
        "pinData": {},
        "meta": {"templateCredsSetupCompleted": True},
    }


# ==========================================================================
#  CLI
# ==========================================================================


def save_json(workflow: dict) -> Path:
    """Save workflow JSON to workflows/ directory."""
    out_dir = Path(__file__).parent.parent / "workflows"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "business_email_mgmt_automation_v2.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Saved: {out_path}")
    return out_path


def _get_client() -> "N8nClient | None":
    """Create an N8nClient from environment variables."""
    if N8nClient is None:
        print("ERROR: n8n_client.py not found")
        return None
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY", "")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        return None
    return N8nClient(base_url=base_url, api_key=api_key)


def deploy(workflow: dict) -> str | None:
    """Deploy workflow to n8n Cloud.

    If BUSINESS_EMAIL_MGMT_WORKFLOW_ID is set in .env, updates the existing
    workflow in place (preserves active state). Otherwise creates a new one.
    """
    client = _get_client()
    if client is None:
        return None
    existing_id = os.getenv("BUSINESS_EMAIL_MGMT_WORKFLOW_ID", "").strip()
    if existing_id:
        # n8n PUT /workflows/:id only accepts name/nodes/connections/settings.
        payload = {
            "name": workflow["name"],
            "nodes": workflow["nodes"],
            "connections": workflow["connections"],
            "settings": workflow.get("settings", {"executionOrder": "v1"}),
        }
        client.update_workflow(existing_id, payload)
        print(f"Updated: {existing_id}")
        return existing_id
    resp = client.create_workflow(workflow)
    wf_id = resp.get("id", "unknown")
    print(f"Deployed: {wf_id} (inactive)")
    return wf_id


def activate(wf_id: str) -> None:
    """Activate a deployed workflow."""
    client = _get_client()
    if client is None:
        return
    client.activate_workflow(wf_id)
    print(f"Activated: {wf_id}")


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python deploy_business_email_mgmt.py <build|deploy|activate>")
        sys.exit(1)

    command = sys.argv[1].lower()
    workflow = build_workflow()

    if command == "build":
        save_json(workflow)

    elif command == "deploy":
        save_json(workflow)
        deploy(workflow)

    elif command == "activate":
        save_json(workflow)
        wf_id = deploy(workflow)
        if wf_id:
            activate(wf_id)

    else:
        print(f"Unknown command: {command}")
        print("Usage: python deploy_business_email_mgmt.py <build|deploy|activate>")
        sys.exit(1)


if __name__ == "__main__":
    main()

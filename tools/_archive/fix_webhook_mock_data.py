"""
Fix all webhook-triggered workflows to handle Manual Trigger gracefully.
Adds test/mock data fallback when no webhook body is present.
"""
import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

API_KEY = os.getenv('N8N_API_KEY')
BASE_URL = os.getenv('N8N_BASE_URL', 'https://ianimmelman89.app.n8n.cloud')
HEADERS = {'X-N8N-API-KEY': API_KEY, 'Content-Type': 'application/json'}


def patch_code_node(wf_id, node_name, new_code):
    """Fetch workflow, replace Code node's jsCode, PUT back."""
    r = httpx.get(f'{BASE_URL}/api/v1/workflows/{wf_id}', headers=HEADERS)
    if r.status_code != 200:
        print(f"  ERROR fetching {wf_id}: {r.status_code}")
        return False
    wf = r.json()
    found = False
    for n in wf['nodes']:
        if n['name'] == node_name:
            n['parameters']['jsCode'] = new_code
            found = True
            break
    if not found:
        print(f"  ERROR: Node '{node_name}' not found in {wf_id}")
        return False

    # Strip to only fields the n8n PUT API accepts
    allowed = ['name', 'nodes', 'connections', 'settings']
    body = {k: wf[k] for k in allowed if k in wf}

    put_r = httpx.put(
        f'{BASE_URL}/api/v1/workflows/{wf_id}',
        headers=HEADERS,
        json=body,
        timeout=30
    )
    if put_r.status_code == 200:
        print(f"  OK: Patched '{node_name}'")
        return True
    else:
        print(f"  ERROR {put_r.status_code}: {put_r.text[:300]}")
        return False


# ─── CR-03: Extract Client Data ───────────────────────────────────────
CR03_CODE = r"""// Extract client data from webhook body (with test data fallback)
const body = $json.body || $json;
const isManualTrigger = !body.email && !body.client_email && !body.name && !body.client_name;

const testData = {
  email: 'test@anyvisionmedia.com',
  name: 'Test Client',
  company: 'Test Company (Pty) Ltd',
  plan: 'professional',
  phone: '+27 11 000 0000',
  source: 'manual_test',
};

const src = isManualTrigger ? testData : body;
const client = {
  email: (src.email || src.client_email || '').toLowerCase().trim(),
  name: src.name || src.client_name || src.full_name || '',
  company: src.company || src.organization || '',
  plan: src.plan || src.subscription_plan || 'starter',
  phone: src.phone || '',
  source: src.source || src.utm_source || 'direct',
  is_test: isManualTrigger,
};

if (!client.email) {
  throw new Error('Client email is required for onboarding');
}

return { json: { client } };
"""

# ─── CONTENT-02: Parse Input ──────────────────────────────────────────
CONTENT02_CODE = r"""// Parse webhook input: content ID + target formats (with test data fallback)
const input = $input.first().json;
const body = input.body || input;

const contentId = body.contentId || body.content_id || body.id || '';
const isManualTrigger = !contentId;

if (isManualTrigger) {
  return {
    json: {
      contentId: 'TEST_RECORD',
      targetFormats: ['blog', 'social', 'newsletter', 'video-script'],
      tone: 'professional',
      audience: 'business owners',
      is_test: true,
    }
  };
}

const targetFormats = body.formats || body.targetFormats
  || ['blog', 'social', 'newsletter', 'video-script'];
const tone = body.tone || 'professional';
const audience = body.audience || 'business owners';

return {
  json: {
    contentId,
    targetFormats,
    tone,
    audience,
    is_test: false,
  }
};
"""

# ─── ORCH-02: Route Event ─────────────────────────────────────────────
ORCH02_CODE = r"""// Parse incoming webhook event and determine routing (with test data fallback)
const input = $input.first().json;

const eventType = input.event_type || input.eventType || '';
const isManualTrigger = !eventType;

const testEvent = {
  event_type: 'health_check',
  source_agent: 'manual_test',
  payload: { message: 'Manual trigger test', timestamp: new Date().toISOString() },
  priority: 'Low',
};

const src = isManualTrigger ? testEvent : input;
const srcEventType = src.event_type || src.eventType || 'unknown';
const sourceAgent = src.source_agent || src.sourceAgent || 'unknown';
const payload = src.payload || src;
const priority = src.priority || 'Medium';

// Route based on event type
let targetAgent = 'agent_orchestrator';
let action = 'log';

switch (srcEventType) {
  case 'lead_qualified':
    targetAgent = 'agent_client_relations';
    action = 'create_client';
    break;
  case 'invoice_created':
    targetAgent = 'agent_finance';
    action = 'track_revenue';
    break;
  case 'content_published':
    targetAgent = 'agent_marketing';
    action = 'track_content';
    break;
  case 'support_ticket':
    targetAgent = 'agent_support';
    action = 'create_ticket';
    break;
  case 'health_check':
    targetAgent = 'agent_orchestrator';
    action = 'log';
    break;
  default:
    action = 'log';
}

return {
  json: {
    event_type: srcEventType,
    source_agent: sourceAgent,
    target_agent: targetAgent,
    action,
    priority,
    payload,
    received_at: new Date().toISOString(),
    is_test: isManualTrigger,
  }
};
"""

# ─── OPT-01: Validate Config ──────────────────────────────────────────
OPT01_CODE = r"""// Validate A/B test configuration (with test data fallback)
const body = $json.body || $json;

const hasData = body.test_name || body.variable || body.variant_a;
const isManualTrigger = !hasData;

const testConfig = {
  test_name: 'Manual Test - Email Subject A/B',
  variable: 'email_subject',
  variant_a: 'Original: Your Weekly SEO Report',
  variant_b: 'Test: SEO Insights That Drive Revenue',
  metric: 'open_rate',
  sample_size_target: 100,
  department: 'marketing',
  is_test: true,
};

const src = isManualTrigger ? testConfig : body;
const required = ['test_name', 'variable', 'variant_a', 'variant_b', 'metric', 'sample_size_target'];
const missing = required.filter(f => !src[f]);

if (missing.length > 0) {
  return [{
    json: {
      valid: false,
      error: 'Missing required fields: ' + missing.join(', '),
      required_fields: required,
    }
  }];
}

return [{
  json: {
    valid: true,
    test_name: src.test_name,
    variable: src.variable,
    variant_a: src.variant_a,
    variant_b: src.variant_b,
    metric: src.metric,
    sample_size_target: parseInt(src.sample_size_target) || 100,
    department: src.department || 'general',
    start_date: new Date().toISOString(),
    status: 'running',
    is_test: isManualTrigger,
  }
}];
"""


# ─── SUP-01: Extract Ticket Data ──────────────────────────────────────
SUP01_CODE = r"""// Extract ticket data from webhook body (with test data fallback)
const body = $json.body || $json;
const isManualTrigger = !body.email && !body.client_email && !body.subject && !body.title;

const testData = {
  email: 'test@anyvisionmedia.com',
  subject: 'Test Support Ticket - Manual Trigger',
  body: 'This is a test support ticket created via Manual Trigger for workflow testing.',
  client_id: 'test_client_001',
  source: 'manual_test',
};

const src = isManualTrigger ? testData : body;
const ticket = {
  email: (src.email || src.client_email || '').toLowerCase().trim(),
  subject: src.subject || src.title || 'No subject',
  body: src.body || src.message || src.description || '',
  client_id: src.client_id || src.clientId || '',
  source: src.source || 'webhook',
  is_test: isManualTrigger,
};

if (!ticket.email) {
  throw new Error('Client email is required for ticket creation');
}

return { json: { ticket } };
"""

# ─── WA-03: Scan Urgency ─────────────────────────────────────────────
WA03_CODE = r"""// Scan incoming message for complaint/urgency keywords (with test data fallback)
const input = $input.first().json;
const hasMessage = input.body || input.message || input.text;
const isManualTrigger = !hasMessage;

const testMessage = {
  body: 'This is an urgent test message. The client is frustrated and needs help ASAP with a refund request.',
  from: '+27110000000',
  contact_name: 'Test Contact',
  timestamp: new Date().toISOString(),
  is_test: true,
};

const src = isManualTrigger ? testMessage : input;
const text = ((src.body || src.message || src.text || '') + '').toLowerCase();

const urgencyKeywords = [
  { word: 'urgent', weight: 0.9 },
  { word: 'broken', weight: 0.7 },
  { word: 'refund', weight: 0.8 },
  { word: 'cancel', weight: 0.8 },
  { word: 'frustrated', weight: 0.7 },
  { word: 'help', weight: 0.4 },
  { word: 'angry', weight: 0.8 },
  { word: 'deadline', weight: 0.7 },
  { word: 'asap', weight: 0.9 },
  { word: 'escalate', weight: 1.0 },
  { word: 'complaint', weight: 0.8 },
  { word: 'unacceptable', weight: 0.7 },
  { word: 'immediately', weight: 0.8 },
  { word: 'critical', weight: 0.9 },
  { word: 'emergency', weight: 1.0 },
];

let score = 0;
const matched = [];
for (const kw of urgencyKeywords) {
  if (text.includes(kw.word)) {
    score += kw.weight;
    matched.push(kw.word);
  }
}

const normalizedScore = Math.min(score / 3, 1.0);
const isUrgent = normalizedScore >= 0.5;

return {
  json: {
    urgency_score: normalizedScore,
    is_urgent: isUrgent,
    matched_keywords: matched,
    original_text: (src.body || src.message || src.text || '').substring(0, 500),
    from: src.from || src.phone || '',
    contact_name: src.contact_name || src.name || '',
    is_test: isManualTrigger,
  }
};
"""


def main():
    patches = [
        ('CR-03', 'e1ufCH2KvuvrBQPm', 'Extract Client Data', CR03_CODE),
        ('CONTENT-02', 'dSAt6zYsfLy1e6tH', 'Parse Input', CONTENT02_CODE),
        ('ORCH-02', '47CJmRKTh9kPZ7u5', 'Route Event', ORCH02_CODE),
        ('OPT-01', 'Rsyz1BHai3q94wPI', 'Validate Config', OPT01_CODE),
        ('SUP-01', 'Pk0B97gW8xtcgHBf', 'Extract Ticket Data', SUP01_CODE),
        ('WA-03', '6C9PPWe4IWoUhjq2', 'Scan Urgency', WA03_CODE),
    ]

    success = 0
    for label, wf_id, node_name, code in patches:
        print(f"\n=== {label} ({wf_id}) ===")
        if patch_code_node(wf_id, node_name, code):
            success += 1

    print(f"\n--- Done: {success}/{len(patches)} patched successfully ---")


if __name__ == '__main__':
    main()

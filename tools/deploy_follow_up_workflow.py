"""
Deploy the Lead Follow-Up Sequence workflow to n8n.

Creates a new workflow that runs daily at 10AM, checks Airtable for leads
due for follow-up, generates stage-appropriate AI emails, and sends them.

Follow-up schedule:
  - FU1: 2 days after initial email
  - FU2: 3 days after FU1 (Day 5)
  - FU3: 7 days after FU2 (Day 12)
  - FU4: 14 days after FU3 (Day 26)

Usage:
    python tools/deploy_follow_up_workflow.py
"""

import sys
import json
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx


# ── Constants ─────────────────────────────────────────────────
AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_TABLE_ID = "tblOsuh298hB9WWrA"

CRED_AIRTABLE = {"id": "7TtMl7ZnJFpC4RGk", "name": "Lead Scraper Airtable"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}


def uid():
    return str(uuid.uuid4())


# ── AI Prompt Templates ──────────────────────────────────────

PREPARE_CONTEXT_CODE = r"""
const items = $input.all();

return items.map(item => {
  const fields = item.json.fields || item.json;
  const recordId = item.json.id || '';

  const stage = parseInt(fields['Follow Up Stage'] || 1);
  const businessName = fields['Business Name'] || '';
  const email = fields['Email'] || '';
  const website = fields['Website'] || '';
  const industry = fields['Industry'] || '';
  const location = fields['Location'] || '';
  const initialSubject = fields['Notes'] || '';

  if (!email) return null;

  const stageConfig = {
    1: { fuNumber: 1, label: 'Follow-Up 1', daysUntilNext: 3, nextStage: 2 },
    2: { fuNumber: 2, label: 'Follow-Up 2', daysUntilNext: 7, nextStage: 3 },
    3: { fuNumber: 3, label: 'Follow-Up 3', daysUntilNext: 14, nextStage: 4 },
    4: { fuNumber: 4, label: 'Follow-Up 4', daysUntilNext: 0, nextStage: 5 }
  };

  const cfg = stageConfig[stage];
  if (!cfg) return null;

  let nextFollowUpDate = '';
  if (cfg.nextStage < 5) {
    const d = new Date();
    d.setDate(d.getDate() + cfg.daysUntilNext);
    nextFollowUpDate = d.toISOString().split('T')[0];
  }

  const prompts = {
    1: `You are a professional business development writer crafting a follow-up email.
This is Follow-Up #1 (sent 2 days after the initial outreach).

CONTEXT:
- Business: ${businessName}
- Industry: ${industry}
- Location: ${location}
- Website: ${website}
- Original email subject: ${initialSubject}

INSTRUCTIONS:
- Reference that you sent an email a couple of days ago about "${initialSubject}"
- Add one specific value point relevant to their ${industry} industry
- Keep it brief - 3-4 sentences max in the body
- Friendly and curious tone, not pushy
- Low-commitment CTA: ask if they had a chance to see the previous email
- Subject line: short Re: style referencing original subject

OUTPUT FORMAT (JSON only, no markdown):
{"subject": "...", "body": "...", "cta_text": "..."}`,

    2: `You are a professional business development writer crafting a follow-up email.
This is Follow-Up #2 (sent 5 days after initial outreach). Use a pattern-interrupt approach.

CONTEXT:
- Business: ${businessName}
- Industry: ${industry}
- Location: ${location}
- Website: ${website}

INSTRUCTIONS:
- Do NOT reference previous emails - fresh approach
- Lead with a brief case study: "One of our ${industry} clients recently..."
- Share a specific, believable outcome (bookings, revenue, or time saved)
- Position their business as having a similar opportunity
- CTA: offer to share the full case study, no commitment required
- Subject: curiosity-driven, not salesy (max 55 chars)

OUTPUT FORMAT (JSON only, no markdown):
{"subject": "...", "body": "...", "cta_text": "..."}`,

    3: `You are a professional business development writer crafting a follow-up email.
This is Follow-Up #3 (sent 12 days after initial outreach). Time to create mild urgency.

CONTEXT:
- Business: ${businessName}
- Industry: ${industry}
- Location: ${location}
- Website: ${website}

INSTRUCTIONS:
- Open with a different angle - a trend or insight about the ${industry} market in ${location}
- Mention you're only taking on a couple of new clients in ${location} this quarter
- Make it feel like insider information, not a pitch
- CTA: ask for a specific 10-minute discovery call this week
- Subject: market-trend or insight framing (max 55 chars)

OUTPUT FORMAT (JSON only, no markdown):
{"subject": "...", "body": "...", "cta_text": "..."}`,

    4: `You are a professional business development writer crafting a final "breakup" email.
This is Follow-Up #4 and FINAL email (sent 26 days after initial outreach).

CONTEXT:
- Business: ${businessName}
- Industry: ${industry}
- Location: ${location}

INSTRUCTIONS:
- Acknowledge you've reached out a few times and don't want to be a nuisance
- Leave the door completely open - "if timing changes, we're here"
- No hard CTA - just a warm, human close
- One final soft value mention but keep it brief
- Subject: something honest like "Closing the loop" or "Last note from me"
- Tone: gracious, genuine, not passive-aggressive

OUTPUT FORMAT (JSON only, no markdown):
{"subject": "...", "body": "...", "cta_text": "..."}`
  };

  return {
    json: {
      recordId,
      email,
      businessName,
      industry,
      location,
      website,
      stage,
      fuNumber: cfg.fuNumber,
      fuLabel: cfg.label,
      nextStage: cfg.nextStage,
      nextFollowUpDate,
      chatInput: prompts[stage]
    }
  };
}).filter(item => item !== null);
"""


FORMAT_EMAIL_CODE = r"""
const items = $input.all();
const allLeads = $('Prepare Follow-Up Context').all();

return items.map((item, index) => {
  const input = item.json;
  const ctx = allLeads[index]?.json || {};

  const SENDER_NAME = 'Ian Immelman';
  const SENDER_TITLE = 'Director';
  const SENDER_COMPANY = 'AnyVision Media';

  let emailContent;
  try {
    const rawText = input.text || input.response || JSON.stringify(input);
    const jsonMatch = rawText.match(/\{[\s\S]*\}/);
    emailContent = JSON.parse(jsonMatch[0]);
  } catch (e) {
    emailContent = {
      subject: `Following up - ${ctx.businessName || 'your business'}`,
      body: `Hi there,\n\nI wanted to follow up on my earlier message about how we help ${ctx.industry || 'businesses'} automate their workflows.\n\nWe've been seeing great results with similar businesses in ${ctx.location || 'the area'}.`,
      cta_text: 'Would a brief 10-minute call work to explore this?'
    };
  }

  const htmlBody = '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">' +
    '<div style="padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;">' +
    '<h1 style="margin:0;font-size:22px;color:#1A1A2E;">' + SENDER_COMPANY + '</h1>' +
    '<p style="margin:8px 0 0;font-size:13px;color:#666;">Business Automation & Lead Generation</p></div>' +
    '<div style="padding:30px 40px;">' +
    '<p style="font-size:15px;line-height:1.6;color:#333;">' + emailContent.body + '</p>' +
    '<p style="font-size:15px;line-height:1.6;color:#333;">' + emailContent.cta_text + '</p>' +
    '<p style="font-size:15px;line-height:1.6;color:#333;margin-top:24px;">Best regards,<br>' +
    '<strong>' + SENDER_NAME + '</strong><br>' +
    '<span style="color:#666;">' + SENDER_TITLE + '</span><br>' +
    '<span style="color:#666;">' + SENDER_COMPANY + '</span></p></div>' +
    '<div style="padding:20px 40px;background:#f8f8f8;border-top:1px solid #eee;">' +
    '<p style="font-size:11px;color:#999;">You received this because your business was listed on Google Maps. Reply &quot;unsubscribe&quot; to be removed.</p></div></div>';

  return {
    json: {
      to: ctx.email,
      subject: emailContent.subject,
      htmlBody: htmlBody,
      recordId: ctx.recordId,
      email: ctx.email,
      businessName: ctx.businessName,
      nextStage: ctx.nextStage,
      nextFollowUpDate: ctx.nextFollowUpDate,
      fuLabel: ctx.fuLabel
    }
  };
});
"""


AGGREGATE_CODE = r"""
const items = $('Update Follow-Up Stage').all();
const now = new Date().toLocaleString('en-ZA', { timeZone: 'Africa/Johannesburg' });

if (items.length === 0) {
  return { json: { subject: 'Follow-Up Run: No emails sent today', body: '<p>No follow-ups were due today.</p>' } };
}

const byStage = {};
for (const item of items) {
  const label = item.json.fuLabel || 'Unknown';
  byStage[label] = (byStage[label] || 0) + 1;
}

const lines = Object.entries(byStage).map(([k, v]) => '<li>' + k + ': ' + v + ' sent</li>');

return {
  json: {
    subject: 'Follow-Up Run: ' + items.length + ' emails sent',
    body: '<h2>Daily Follow-Up Sequence Report</h2>' +
      '<p><strong>Date:</strong> ' + now + '</p>' +
      '<p><strong>Total emails:</strong> ' + items.length + '</p>' +
      '<ul>' + lines.join('') + '</ul>' +
      '<p>Check <a href="https://airtable.com/app2ALQUP7CKEkHOz">Airtable CRM</a> for details.</p>'
  }
};
"""


def build_nodes():
    """Build all workflow nodes."""
    nodes = []

    # 1. Schedule Trigger - daily at 10AM
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "days", "triggerAtHour": 10}]
            }
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 300],
        "typeVersion": 1.2
    })

    # 2. Manual Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 500],
        "typeVersion": 1
    })

    # 3. Fetch Due Follow-Ups from Airtable
    nodes.append({
        "parameters": {
            "operation": "list",
            "base": {
                "__rl": True, "mode": "list",
                "value": AIRTABLE_BASE_ID,
                "cachedResultName": "Lead Scraper - Johannesburg CRM"
            },
            "table": {
                "__rl": True, "mode": "list",
                "value": AIRTABLE_TABLE_ID,
                "cachedResultName": "Leads"
            },
            "returnAll": True,
            "options": {
                "filterByFormula": (
                    "AND("
                    "IS_BEFORE({Next Follow Up Date}, DATEADD(TODAY(), 1, 'days')), "
                    "{Follow Up Stage} >= 1, "
                    "{Follow Up Stage} <= 4"
                    ")"
                )
            }
        },
        "id": uid(),
        "name": "Fetch Due Follow-Ups",
        "type": "n8n-nodes-base.airtable",
        "position": [460, 300],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE}
    })

    # 4. Has Leads? (IF node)
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"version": 2, "typeValidation": "strict", "caseSensitive": True},
                "combinator": "and",
                "conditions": [{
                    "id": uid(),
                    "operator": {"type": "string", "operation": "exists", "singleValue": True},
                    "leftValue": "={{ $json.fields.Email }}",
                    "rightValue": ""
                }]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Has Leads?",
        "type": "n8n-nodes-base.if",
        "position": [700, 300],
        "typeVersion": 2.2
    })

    # 5. No Leads Today
    nodes.append({
        "parameters": {
            "mode": "manual",
            "assignments": {"assignments": [{
                "id": uid(),
                "name": "subject",
                "value": "Follow-Up Run: No emails due today",
                "type": "string"
            }, {
                "id": uid(),
                "name": "body",
                "value": "<p>No follow-ups were due today. The sequence is on track.</p>",
                "type": "string"
            }]}
        },
        "id": uid(),
        "name": "No Leads Today",
        "type": "n8n-nodes-base.set",
        "position": [700, 540],
        "typeVersion": 3.4
    })

    # 6. Prepare Follow-Up Context (Code node - selects prompt by stage)
    nodes.append({
        "parameters": {"jsCode": PREPARE_CONTEXT_CODE},
        "id": uid(),
        "name": "Prepare Follow-Up Context",
        "type": "n8n-nodes-base.code",
        "position": [960, 300],
        "typeVersion": 2,
        "onError": "continueRegularOutput"
    })

    # 7. Rate Limit (30s between emails)
    nodes.append({
        "parameters": {"amount": 30},
        "id": uid(),
        "name": "Rate Limit Follow-Ups",
        "type": "n8n-nodes-base.wait",
        "position": [1200, 300],
        "typeVersion": 1.1,
        "webhookId": uid()
    })

    # 8. AI Generate Follow-Up Email (chainLlm)
    nodes.append({
        "parameters": {
            "promptType": "auto",
            "text": "={{ $json.chatInput }}",
            "hasOutputParser": False,
            "options": {}
        },
        "id": uid(),
        "name": "AI Generate Follow-Up",
        "type": "@n8n/n8n-nodes-langchain.chainLlm",
        "position": [1440, 300],
        "typeVersion": 1.4
    })

    # 9. OpenRouter Model (sub-node for chainLlm)
    nodes.append({
        "parameters": {
            "model": "anthropic/claude-sonnet-4.5",
            "options": {
                "maxTokens": 500,
                "temperature": 0.7
            }
        },
        "id": uid(),
        "name": "OpenRouter Model",
        "type": "@n8n/n8n-nodes-langchain.lmChatOpenRouter",
        "position": [1460, 520],
        "typeVersion": 1,
        "credentials": {"openRouterApi": CRED_OPENROUTER}
    })

    # 10. Format Follow-Up Email
    nodes.append({
        "parameters": {"jsCode": FORMAT_EMAIL_CODE},
        "id": uid(),
        "name": "Format Follow-Up Email",
        "type": "n8n-nodes-base.code",
        "position": [1680, 300],
        "typeVersion": 2,
        "onError": "continueRegularOutput"
    })

    # 11. Send Follow-Up Email
    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.to }}",
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.htmlBody }}",
            "options": {}
        },
        "id": uid(),
        "name": "Send Follow-Up Email",
        "type": "n8n-nodes-base.gmail",
        "position": [1920, 300],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput"
    })

    # 12. Update Follow-Up Stage in Airtable
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {
                "__rl": True, "mode": "list",
                "value": AIRTABLE_BASE_ID,
                "cachedResultName": "Lead Scraper - Johannesburg CRM"
            },
            "table": {
                "__rl": True, "mode": "list",
                "value": AIRTABLE_TABLE_ID,
                "cachedResultName": "Leads"
            },
            "columns": {
                "value": {
                    "Follow Up Stage": "={{ $('Format Follow-Up Email').item.json.nextStage }}",
                    "Next Follow Up Date": "={{ $('Format Follow-Up Email').item.json.nextFollowUpDate }}",
                    "Status": "Followed Up",
                    "Email": "={{ $('Format Follow-Up Email').item.json.email }}"
                },
                "schema": [
                    {"id": "Follow Up Stage", "type": "number", "display": True, "displayName": "Follow Up Stage"},
                    {"id": "Next Follow Up Date", "type": "string", "display": True, "displayName": "Next Follow Up Date"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Email", "type": "string", "display": True, "displayName": "Email"}
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Email"]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Update Follow-Up Stage",
        "type": "n8n-nodes-base.airtable",
        "position": [2160, 300],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput"
    })

    # 13. Aggregate Follow-Up Results
    nodes.append({
        "parameters": {"jsCode": AGGREGATE_CODE},
        "id": uid(),
        "name": "Aggregate Follow-Up Results",
        "type": "n8n-nodes-base.code",
        "position": [2400, 300],
        "typeVersion": 2,
        "alwaysOutputData": True
    })

    # 14. Send Summary Email
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.body }}",
            "options": {}
        },
        "id": uid(),
        "name": "Send Follow-Up Summary",
        "type": "n8n-nodes-base.gmail",
        "position": [2640, 400],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput"
    })

    # 15. Error Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 740],
        "typeVersion": 1
    })

    # 16. Error Notification
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=Follow-Up Workflow ERROR - {{ $json.workflow.name }}",
            "emailType": "html",
            "message": (
                "=<h2>Follow-Up Workflow Error</h2>"
                "<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>"
                "<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>"
                "<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>"
            ),
            "options": {}
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [460, 740],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"gmailOAuth2": CRED_GMAIL}
    })

    # Sticky notes for documentation
    nodes.append({
        "parameters": {
            "width": 400, "height": 200,
            "content": (
                "## Lead Follow-Up Sequence\n\n"
                "Runs daily at 10AM. Checks Airtable for leads due for follow-up.\n\n"
                "**Schedule:** FU1 (Day 2) -> FU2 (Day 5) -> FU3 (Day 12) -> FU4 (Day 26)\n\n"
                "**To stop follow-ups for a lead:** Set Follow Up Stage to 0 in Airtable"
            )
        },
        "id": uid(),
        "name": "Note 1",
        "type": "n8n-nodes-base.stickyNote",
        "position": [160, 60],
        "typeVersion": 1
    })

    nodes.append({
        "parameters": {
            "width": 350, "height": 160,
            "content": (
                "## Follow-Up Stages\n\n"
                "| Stage | Meaning |\n"
                "|---|---|\n"
                "| 0 | Inactive/Unsubscribed |\n"
                "| 1 | Initial sent, FU1 pending |\n"
                "| 2 | FU1 sent, FU2 pending |\n"
                "| 3 | FU2 sent, FU3 pending |\n"
                "| 4 | FU3 sent, FU4 pending |\n"
                "| 5 | Sequence complete |"
            )
        },
        "id": uid(),
        "name": "Note 2",
        "type": "n8n-nodes-base.stickyNote",
        "position": [580, 60],
        "typeVersion": 1
    })

    return nodes


def build_connections():
    """Build workflow connections."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Fetch Due Follow-Ups", "type": "main", "index": 0}]]
        },
        "Manual Trigger": {
            "main": [[{"node": "Fetch Due Follow-Ups", "type": "main", "index": 0}]]
        },
        "Fetch Due Follow-Ups": {
            "main": [[{"node": "Has Leads?", "type": "main", "index": 0}]]
        },
        "Has Leads?": {
            "main": [
                [{"node": "Prepare Follow-Up Context", "type": "main", "index": 0}],
                [{"node": "No Leads Today", "type": "main", "index": 0}]
            ]
        },
        "No Leads Today": {
            "main": [[{"node": "Send Follow-Up Summary", "type": "main", "index": 0}]]
        },
        "Prepare Follow-Up Context": {
            "main": [[{"node": "Rate Limit Follow-Ups", "type": "main", "index": 0}]]
        },
        "Rate Limit Follow-Ups": {
            "main": [[{"node": "AI Generate Follow-Up", "type": "main", "index": 0}]]
        },
        "AI Generate Follow-Up": {
            "main": [[{"node": "Format Follow-Up Email", "type": "main", "index": 0}]]
        },
        "OpenRouter Model": {
            "ai_languageModel": [[{"node": "AI Generate Follow-Up", "type": "ai_languageModel", "index": 0}]]
        },
        "Format Follow-Up Email": {
            "main": [[{"node": "Send Follow-Up Email", "type": "main", "index": 0}]]
        },
        "Send Follow-Up Email": {
            "main": [[{"node": "Update Follow-Up Stage", "type": "main", "index": 0}]]
        },
        "Update Follow-Up Stage": {
            "main": [[{"node": "Aggregate Follow-Up Results", "type": "main", "index": 0}]]
        },
        "Aggregate Follow-Up Results": {
            "main": [[{"node": "Send Follow-Up Summary", "type": "main", "index": 0}]]
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]]
        }
    }


def build_workflow():
    """Build the complete workflow payload."""
    return {
        "name": "Lead Follow-Up Sequence",
        "nodes": build_nodes(),
        "connections": build_connections(),
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner"
        }
    }


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    workflow = build_workflow()

    # Save locally
    output_dir = Path(__file__).parent.parent / ".tmp"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "follow_up_workflow.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2)
    print(f"Saved workflow JSON to {output_path}")

    node_count = len([n for n in workflow["nodes"] if "stickyNote" not in n["type"]])
    print(f"Nodes: {node_count} functional + {len(workflow['nodes']) - node_count} sticky notes")

    with httpx.Client(timeout=60) as client:
        # Create the workflow
        print("\nDeploying to n8n...")
        resp = client.post(
            f"{base_url}/api/v1/workflows",
            headers=headers,
            json=workflow
        )
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {resp.text[:500]}")
            sys.exit(1)
        result = resp.json()
        workflow_id = result["id"]
        print(f"Created workflow: {result['name']} (ID: {workflow_id})")

        # Activate
        resp = client.post(
            f"{base_url}/api/v1/workflows/{workflow_id}/activate",
            headers=headers
        )
        resp.raise_for_status()
        print(f"Activated! Schedule: daily at 10AM")

        # Verify
        resp = client.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers)
        final = resp.json()
        print(f"\nVerification:")
        print(f"  Name: {final['name']}")
        print(f"  ID: {final['id']}")
        print(f"  Active: {final.get('active')}")
        print(f"  Nodes: {len(final['nodes'])}")

        # Save workflow ID for reference
        id_path = output_dir / "follow_up_workflow_id.txt"
        id_path.write_text(workflow_id)
        print(f"\nWorkflow ID saved to {id_path}")


if __name__ == "__main__":
    main()

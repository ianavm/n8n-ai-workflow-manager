"""
Add agent status toggle features to WhatsApp Multi-Agent v2 (Cloud API).

Features:
1. Business hours auto-toggle — AI steps back during business hours, takes over after hours
2. ONLINE/OFFLINE keyword override — agent sends keyword from their personal number
3. Manual override with expiry — resets to business hours schedule automatically
4. Confirmation message sent back to agent on toggle

Patches workflow OnyparfRHiiCeRXM in place.

Usage:
    python tools/fix_whatsapp_v2_agent_status.py preview
    python tools/fix_whatsapp_v2_agent_status.py deploy
"""

import sys
import json
import uuid

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx

WORKFLOW_ID = "OnyparfRHiiCeRXM"


def uid():
    return str(uuid.uuid4())


def update_merge_agent_data(node):
    """Update Merge Agent Data to include new fields."""
    node["parameters"]["jsCode"] = r"""// Merge message data with agent profile
const message = $('Parse Message').first().json;
const agentRecord = $input.first().json;
const fields = agentRecord.fields || agentRecord;

const agent = {
  recordId: agentRecord.id,
  id: fields.agent_id || agentRecord.id,
  agentName: fields.agent_name || 'Assistant',
  email: fields.email || '',
  companyName: fields.company_name || 'AnyVision Media',
  region: fields.region || 'South Africa',
  language: fields.language || 'en',
  timezone: fields.timezone || 'Africa/Johannesburg',
  isActive: fields.is_active !== false,
  autoReply: fields.auto_reply !== false,
  isOnline: fields.is_online === true,
  lastSeen: fields.last_seen || null,
  onlineThresholdMinutes: parseInt(fields.online_threshold_minutes || '5'),
  botType: fields.bot_type || 'business',
  customSystemPrompt: fields.custom_system_prompt || '',
  aiModel: fields.openrouter_model || fields.ai_model || 'anthropic/claude-sonnet-4-20250514',
  aiTemperature: parseFloat(fields.ai_temperature || '0.7'),
  maxResponseLength: parseInt(fields.max_response_length || '500'),
  airtableBaseId: fields.airtable_base_id || 'appzcZpiIZ6QPtJXT',
  whatsappPhoneNumberId: message.phoneNumberId,
  // New fields for business hours & agent toggle
  businessHoursStart: fields.business_hours_start || '08:00',
  businessHoursEnd: fields.business_hours_end || '17:00',
  agentPersonalNumber: (fields.agent_personal_number || '').replace(/\D/g, ''),
  manualOverride: fields.manual_override || null,
  manualOverrideExpiry: fields.manual_override_expiry || null,
};

// Build conversation ID for history lookup
const conversationId = `${agent.id}_${message.from}`;

const _out = {
  ...message,
  agent: agent,
  agentId: agent.id,
  agentName: agent.agentName,
  agentRecordId: agent.recordId,
  conversationId: conversationId,
};
return [{ json: _out }];
"""
    return True


def update_build_ai_context(node):
    """Update Build AI Context with business hours + manual override logic."""
    node["parameters"]["jsCode"] = r"""// Build AI context: business hours check + manual override + conversation history
const message = $('Merge Agent Data').first().json;
const historyRaw = $input.all();
const agent = message.agent;

// --- DETERMINE IF AI SHOULD RESPOND ---
let shouldBlock = false;
let blockReason = null;

// 1. Check manual override first (takes priority)
if (agent.manualOverride) {
  // Check if override has expired
  const expiry = agent.manualOverrideExpiry ? new Date(agent.manualOverrideExpiry).getTime() : 0;
  const overrideValid = !agent.manualOverrideExpiry || expiry > Date.now();

  if (overrideValid) {
    if (agent.manualOverride === 'online') {
      // Agent manually set ONLINE — block AI
      shouldBlock = true;
      blockReason = 'agent_online_manual';
    }
    // If manual override is 'offline', AI takes over (shouldBlock stays false)
  }
  // If expired, fall through to business hours check
}

// 2. If no valid manual override, check business hours
if (!shouldBlock && !blockReason) {
  const tz = agent.timezone || 'Africa/Johannesburg';
  const now = new Date();

  // Get current time in agent's timezone
  const timeStr = now.toLocaleTimeString('en-GB', { timeZone: tz, hour12: false, hour: '2-digit', minute: '2-digit' });
  const [nowH, nowM] = timeStr.split(':').map(Number);
  const nowMinutes = nowH * 60 + nowM;

  const [startH, startM] = (agent.businessHoursStart || '08:00').split(':').map(Number);
  const startMinutes = startH * 60 + startM;

  const [endH, endM] = (agent.businessHoursEnd || '17:00').split(':').map(Number);
  const endMinutes = endH * 60 + endM;

  // Check if current time is within business hours
  const withinBusinessHours = nowMinutes >= startMinutes && nowMinutes < endMinutes;

  // Also check day of week (Mon-Fri = business days, Sat-Sun = AI takes over)
  const dayStr = now.toLocaleDateString('en-GB', { timeZone: tz, weekday: 'short' });
  const isWeekday = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'].includes(dayStr);

  if (withinBusinessHours && isWeekday) {
    // During business hours on weekdays — agent is "available", block AI
    shouldBlock = true;
    blockReason = 'business_hours';
  }
  // Outside business hours or weekends — AI takes over
}

// 3. Rate limiting: count inbound messages in last 5 minutes
const records = historyRaw
  .map(item => item.json)
  .filter(r => r && (r.fields || r.message_body))
  .reverse();

const fiveMinAgo = Date.now() - 300000;
const recentInbound = records.filter(r => {
  const f = r.fields || r;
  return f.direction === 'inbound' && new Date(f.timestamp).getTime() > fiveMinAgo;
}).length;

if (recentInbound > 10 && !shouldBlock) {
  shouldBlock = true;
  blockReason = 'rate_limited';
}

// --- BUILD CONVERSATION HISTORY ---
const conversationMessages = [];

for (const record of records) {
  const f = record.fields || record;
  const body = f.message_body || '';
  if (!body) continue;

  if (f.direction === 'inbound') {
    conversationMessages.push({ role: 'user', content: body });
  } else if (f.direction === 'outbound') {
    conversationMessages.push({ role: 'assistant', content: body });
  }
}

// Remove the last inbound message from history (it's the current one)
if (conversationMessages.length > 0 &&
    conversationMessages[conversationMessages.length - 1].role === 'user') {
  conversationMessages.pop();
}

const _out = {
  ...message,
  shouldBlock: shouldBlock,
  blockReason: blockReason,
  sessionExpired: false,
  conversationHistory: conversationMessages,
  historyCount: conversationMessages.length,
  processingStartTime: Date.now(),
};
return [{ json: _out }];
"""
    return True


def add_agent_command_nodes(wf):
    """Add nodes to detect ONLINE/OFFLINE commands from the agent's own number."""
    nodes = wf["nodes"]
    connections = wf["connections"]
    node_map = {n["name"]: n for n in nodes}

    # Skip if already added
    if "Agent Command?" in node_map:
        print("  Agent Command nodes already exist, skipping")
        return

    # The flow we need to insert AFTER "Not Opted Out?" true output → before "Find Agent"
    # Current: Not Opted Out? → [true] → Find Agent
    # New:     Not Opted Out? → [true] → Find Agent → Agent Found? → [true] → Merge Agent Data → Agent Command? → [yes: Toggle Status] → [no: continue normal flow]

    # Actually, better to insert AFTER Merge Agent Data, because we need agent data to check personal number.
    # Current: Merge Agent Data → Log Incoming + Fetch History
    # New: Merge Agent Data → Agent Command? → [yes: Toggle Status → Send Toggle Confirmation] → [no: Log Incoming + Fetch History]

    merge_node = node_map.get("Merge Agent Data")
    if not merge_node:
        print("  WARNING: Merge Agent Data not found")
        return

    merge_pos = merge_node["position"]

    # Create "Agent Command?" If node
    agent_cmd_node = {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": False},
                "conditions": [
                    {
                        "leftValue": "={{ $json.isAgentCommand }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "equals"
                        }
                    }
                ],
                "combinator": "and"
            }
        },
        "id": uid(),
        "name": "Agent Command?",
        "type": "n8n-nodes-base.if",
        "position": [merge_pos[0] + 220, merge_pos[1]],
        "typeVersion": 2.2
    }
    nodes.append(agent_cmd_node)

    # Create "Detect Agent Command" Code node (inserted into Merge Agent Data output)
    detect_cmd_node = {
        "parameters": {
            "jsCode": r"""// Detect if this message is an ONLINE/OFFLINE command from the agent
const data = $input.first().json;
const agent = data.agent;
const from = data.from || '';
const body = (data.body || '').trim().toUpperCase();

let isAgentCommand = false;
let commandType = null;

// Check if sender is the agent's personal number
if (agent.agentPersonalNumber && from === agent.agentPersonalNumber) {
  if (body === 'ONLINE' || body === 'GO ONLINE' || body === 'AI OFF') {
    isAgentCommand = true;
    commandType = 'online';
  } else if (body === 'OFFLINE' || body === 'GO OFFLINE' || body === 'AI ON') {
    isAgentCommand = true;
    commandType = 'offline';
  } else if (body === 'STATUS') {
    isAgentCommand = true;
    commandType = 'status';
  }
}

const _out = {
  ...data,
  isAgentCommand: isAgentCommand,
  commandType: commandType,
};
return [{ json: _out }];
"""
        },
        "id": uid(),
        "name": "Detect Agent Command",
        "type": "n8n-nodes-base.code",
        "position": [merge_pos[0] + 220, merge_pos[1] - 140],
        "typeVersion": 2
    }
    nodes.append(detect_cmd_node)

    # Create "Toggle Agent Status" Code node
    toggle_node = {
        "parameters": {
            "jsCode": r"""// Prepare the status toggle update for Airtable
const data = $input.first().json;
const command = data.commandType;
const agent = data.agent;

let newOverride = null;
let confirmMsg = '';

// Set override expiry to end of current business day (or 12 hours from now)
const now = new Date();
const expiryHours = 12;
const expiry = new Date(now.getTime() + expiryHours * 3600000).toISOString();

if (command === 'online') {
  newOverride = 'online';
  confirmMsg = `You are now ONLINE. The AI assistant has stepped back.\n\nYou will handle messages directly until you send OFFLINE or until ${agent.businessHoursEnd || '17:00'} today.\n\nSend OFFLINE when you want the AI to take over again.`;
} else if (command === 'offline') {
  newOverride = 'offline';
  confirmMsg = `You are now OFFLINE. The AI assistant is handling messages.\n\nCustomers will receive AI-powered responses. Send ONLINE when you want to take over.`;
} else if (command === 'status') {
  const isBusinessHours = true; // simplified — actual check is in Build AI Context
  const status = agent.manualOverride || 'auto (business hours)';
  confirmMsg = `Current status: ${status}\nBusiness hours: ${agent.businessHoursStart || '08:00'} - ${agent.businessHoursEnd || '17:00'}\n\nSend ONLINE or OFFLINE to change.`;
  // For status check, don't change anything
  const _out = {
    ...data,
    toggleConfirmation: confirmMsg,
    skipToggle: true,
  };
  return [{ json: _out }];
}

const _out = {
  ...data,
  newOverride: newOverride,
  overrideExpiry: expiry,
  toggleConfirmation: confirmMsg,
  skipToggle: false,
};
return [{ json: _out }];
"""
        },
        "id": uid(),
        "name": "Toggle Agent Status",
        "type": "n8n-nodes-base.code",
        "position": [merge_pos[0] + 660, merge_pos[1] - 140],
        "typeVersion": 2
    }
    nodes.append(toggle_node)

    # Create "Update Override" Airtable node
    update_override_node = {
        "parameters": {
            "operation": "update",
            "base": {
                "__rl": True,
                "value": "appzcZpiIZ6QPtJXT",
                "mode": "id"
            },
            "table": {
                "__rl": True,
                "value": "tblHCkr9weKQAHZoB",
                "mode": "id"
            },
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "manual_override": "={{ $json.newOverride }}",
                    "manual_override_expiry": "={{ $json.overrideExpiry }}",
                    "is_online": "={{ $json.newOverride === 'online' }}"
                }
            },
            "options": {}
        },
        "id": uid(),
        "name": "Update Override",
        "type": "n8n-nodes-base.airtable",
        "position": [merge_pos[0] + 880, merge_pos[1] - 140],
        "typeVersion": 2.1,
        "credentials": {
            "airtableTokenApi": {
                "id": "ZyBrcAO6fps7YB3u",
                "name": "Whatsapp Multi Agent"
            }
        }
    }
    nodes.append(update_override_node)

    # Create "Send Toggle Confirmation" HTTP Request node
    send_confirm_node = {
        "parameters": {
            "method": "POST",
            "url": "=https://graph.facebook.com/v21.0/{{ $json.phoneNumberId }}/messages",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "whatsAppApi",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={\n  "messaging_product": "whatsapp",\n  "to": "{{ $json.from }}",\n  "type": "text",\n  "text": {\n    "body": {{ JSON.stringify($json.toggleConfirmation) }}\n  }\n}',
            "options": {"timeout": 10000}
        },
        "id": uid(),
        "name": "Send Toggle Confirmation",
        "type": "n8n-nodes-base.httpRequest",
        "position": [merge_pos[0] + 1100, merge_pos[1] - 140],
        "typeVersion": 4.2,
        "credentials": {
            "whatsAppApi": {
                "id": "dCAz6MBXpOXvMJrq",
                "name": "WhatsApp account AVM Multi Agent"
            }
        },
        "onError": "continueRegularOutput"
    }
    nodes.append(send_confirm_node)

    # Now rewire connections:
    # 1. Merge Agent Data → Detect Agent Command (instead of Log Incoming + Fetch History)
    # 2. Detect Agent Command → Agent Command?
    # 3. Agent Command? [true/yes] → Toggle Agent Status → Update Override → Send Toggle Confirmation
    # 4. Agent Command? [false/no] → Log Incoming + Fetch History (original flow)

    # Save original Merge Agent Data connections
    original_merge_targets = connections.get("Merge Agent Data", {}).get("main", [[]])[0]

    # Rewire Merge Agent Data → Detect Agent Command
    connections["Merge Agent Data"] = {
        "main": [[{"node": "Detect Agent Command", "type": "main", "index": 0}]]
    }

    # Detect Agent Command → Agent Command?
    connections["Detect Agent Command"] = {
        "main": [[{"node": "Agent Command?", "type": "main", "index": 0}]]
    }

    # Agent Command? true → Toggle Agent Status, false → original targets
    connections["Agent Command?"] = {
        "main": [
            # true (index 0) → Toggle Agent Status
            [{"node": "Toggle Agent Status", "type": "main", "index": 0}],
            # false (index 1) → original Merge Agent Data targets
            original_merge_targets
        ]
    }

    # Toggle Agent Status → Update Override
    connections["Toggle Agent Status"] = {
        "main": [[{"node": "Update Override", "type": "main", "index": 0}]]
    }

    # Update Override → Send Toggle Confirmation
    connections["Update Override"] = {
        "main": [[{"node": "Send Toggle Confirmation", "type": "main", "index": 0}]]
    }

    # Send Toggle Confirmation → nothing (end of command flow)
    connections["Send Toggle Confirmation"] = {"main": [[]]}

    print("  Added: Detect Agent Command, Agent Command?, Toggle Agent Status, Update Override, Send Toggle Confirmation")
    print(f"  Rewired: Merge Agent Data -> Detect Agent Command -> Agent Command? -> [cmd: toggle flow] / [normal: {[t['node'] for t in original_merge_targets]}]")


def fix_workflow(wf):
    """Apply agent status toggle features."""
    node_map = {n["name"]: n for n in wf["nodes"]}

    # 1. Update Merge Agent Data to include new fields
    print("\n[1] Updating Merge Agent Data with new fields...")
    merge = node_map.get("Merge Agent Data")
    if merge:
        update_merge_agent_data(merge)
        print("  Updated Merge Agent Data")

    # 2. Update Build AI Context with business hours logic
    print("\n[2] Updating Build AI Context with business hours + manual override...")
    ctx = node_map.get("Build AI Context")
    if ctx:
        update_build_ai_context(ctx)
        print("  Updated Build AI Context")

    # 3. Add agent command detection nodes
    print("\n[3] Adding agent command detection flow...")
    add_agent_command_nodes(wf)

    print(f"\n  Final node count: {len(wf['nodes'])}")
    return wf


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    action = sys.argv[1] if len(sys.argv) > 1 else "preview"

    print("=" * 60)
    print("WhatsApp v2 Cloud API — Agent Status Toggle Features")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:
        print(f"\n[FETCH] Getting workflow {WORKFLOW_ID}...")
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

        wf = fix_workflow(wf)

        if action == "preview":
            print("\nPreview mode - no changes pushed.")
            out_path = "workflows/whatsapp-v2/whatsapp_v2_cloudapi_agent_status.json"
            import os
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(wf, f, indent=2)
            print(f"Saved preview to {out_path}")

        elif action == "deploy":
            print("\n[DEPLOY] Pushing to n8n...")
            update_payload = {
                "name": wf["name"],
                "nodes": wf["nodes"],
                "connections": wf["connections"],
                "settings": wf.get("settings", {"executionOrder": "v1"})
            }
            put_resp = client.put(
                f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
                headers=headers,
                json=update_payload
            )
            if put_resp.status_code != 200:
                print(f"  Error {put_resp.status_code}: {put_resp.text[:500]}")
                sys.exit(1)
            print("  Deployed successfully!")

            out_path = "workflows/whatsapp-v2/whatsapp_v2_cloudapi_agent_status.json"
            import os
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(wf, f, indent=2)
            print(f"  Also saved to {out_path}")


if __name__ == "__main__":
    main()

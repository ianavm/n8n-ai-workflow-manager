"""
Enable self-message toggle for WhatsApp Multi-Agent v2 (Cloud API).

Modifies Parse Message to allow ONLINE/OFFLINE/STATUS commands through
loop prevention when sent from the business number itself (self-message).
Modifies Detect Agent Command to check isSelfCommand flag in addition
to agentPersonalNumber match.

No second phone number needed — agent messages their own WhatsApp number.

Patches workflow OnyparfRHiiCeRXM in place.

Usage:
    python tools/fix_whatsapp_v2_self_toggle.py preview
    python tools/fix_whatsapp_v2_self_toggle.py deploy
"""

import sys
import json

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx

WORKFLOW_ID = "OnyparfRHiiCeRXM"


PARSE_MESSAGE_CODE = r"""// Parse WhatsApp Cloud API message
try {
  const data = $input.first().json;
  const now = Date.now();

  // Cloud API format
  const entry = data.entry?.[0];
  const change = entry?.changes?.[0];
  const value = change?.value;
  const message = value?.messages?.[0];
  const contact = value?.contacts?.[0];
  const metadata = value?.metadata;

  if (!message) {
    const _out = {
      parseSuccess: false,
      error: true,
      errorType: 'not_a_message',
      errorMessage: 'Not a message event (status update or other)',
      timestamp: new Date().toISOString()
    };
    return [{ json: _out }];
  }

  const phoneNumberId = metadata?.phone_number_id || '';
  const displayPhone = (metadata?.display_phone_number || '').replace(/\D/g, '');
  const from = (message.from || '').replace(/\D/g, '');
  const waId = contact?.wa_id || from;
  const profileName = contact?.profile?.name || '';
  const cloudApiMessageId = message.id || '';
  const msgType = message.type || 'text';

  let body = '';
  let hasMedia = false;
  let mediaUrl = null;
  let mediaType = null;

  if (msgType === 'text') {
    body = message.text?.body || '';
  } else if (['image', 'video', 'audio', 'document'].includes(msgType)) {
    body = message[msgType]?.caption || '';
    hasMedia = true;
    mediaUrl = message[msgType]?.id || null;
    mediaType = message[msgType]?.mime_type || msgType;
  } else if (msgType === 'location') {
    body = `Location: ${message.location?.latitude}, ${message.location?.longitude}`;
  } else if (msgType === 'contacts') {
    body = `Shared contact: ${message.contacts?.[0]?.name?.formatted_name || 'Unknown'}`;
  }

  // Sanitize
  body = (body || '').trim().replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '');
  if (body.length > 2000) body = body.substring(0, 2000);

  if (!phoneNumberId || !from) {
    throw new Error('Missing phoneNumberId or from');
  }

  // Self-message detection: check if sender IS the business number
  // Uses display_phone_number (actual phone number) not phone_number_id (Meta internal ID)
  const isSelfMessage = displayPhone && from === displayPhone;
  let isSelfCommand = false;

  if (isSelfMessage) {
    const upperBody = (body || '').trim().toUpperCase();
    const commandKeywords = ['ONLINE', 'OFFLINE', 'GO ONLINE', 'GO OFFLINE', 'AI ON', 'AI OFF', 'STATUS'];

    if (commandKeywords.includes(upperBody)) {
      // Allow through as agent self-command
      isSelfCommand = true;
    } else {
      // Block non-command self-messages (loop prevention)
      const _out = {
        parseSuccess: false,
        error: true,
        errorType: 'self_message',
        errorMessage: 'Ignoring own message (loop prevention)',
        timestamp: new Date().toISOString()
      };
      return [{ json: _out }];
    }
  }

  // Deduplication: reject recently-seen message IDs
  const staticData = $getWorkflowStaticData('global');
  if (!staticData.recentMsgIds) staticData.recentMsgIds = {};
  const dedupNow = Date.now();
  for (const [mid, ts] of Object.entries(staticData.recentMsgIds)) {
    if (dedupNow - ts > 60000) delete staticData.recentMsgIds[mid];
  }
  if (cloudApiMessageId && staticData.recentMsgIds[cloudApiMessageId]) {
    const _out = {
      parseSuccess: false,
      error: true,
      errorType: 'duplicate',
      errorMessage: 'Duplicate message (already processed)',
      timestamp: new Date().toISOString()
    };
    return [{ json: _out }];
  }
  if (cloudApiMessageId) staticData.recentMsgIds[cloudApiMessageId] = dedupNow;

  const _out = {
    messageId: `msg_${now}`,
    cloudApiMessageId: cloudApiMessageId,
    phoneNumberId: phoneNumberId,
    from: from,
    waId: waId,
    body: body,
    type: msgType,
    isGroup: false,
    isSelfCommand: isSelfCommand,
    hasMedia: hasMedia,
    mediaUrl: mediaUrl,
    mediaType: mediaType,
    profileName: profileName,
    timestamp: new Date().toISOString(),
    processingStartTime: now,
    parseSuccess: true
  };
  return [{ json: _out }];

} catch (error) {
  const _out = {
    parseSuccess: false,
    error: true,
    errorType: 'parse_error',
    errorMessage: error.message,
    timestamp: new Date().toISOString()
  };
  return [{ json: _out }];
}
"""


DETECT_AGENT_COMMAND_CODE = r"""// Detect if this message is an ONLINE/OFFLINE command from the agent
// Supports two methods:
// 1. Self-message: agent sends command to their own business number (isSelfCommand flag)
// 2. Personal number: agent sends from a separate personal number (agentPersonalNumber match)
const data = $input.first().json;
const agent = data.agent;
const from = data.from || '';
const body = (data.body || '').trim().toUpperCase();

let isAgentCommand = false;
let commandType = null;

// Check either method
const isSelfCmd = data.isSelfCommand === true;
const isPersonalNum = agent.agentPersonalNumber && from === agent.agentPersonalNumber;

if (isSelfCmd || isPersonalNum) {
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


def fix_workflow(wf):
    """Apply self-message toggle modifications."""
    node_map = {n["name"]: n for n in wf["nodes"]}

    # 1. Update Parse Message
    print("\n[1] Updating Parse Message with self-message detection...")
    parse = node_map.get("Parse Message")
    if parse:
        parse["parameters"]["jsCode"] = PARSE_MESSAGE_CODE
        print("  Updated Parse Message (self-message commands pass through loop prevention)")
    else:
        print("  WARNING: Parse Message node not found")

    # 2. Update Detect Agent Command
    print("\n[2] Updating Detect Agent Command with isSelfCommand support...")
    detect = node_map.get("Detect Agent Command")
    if detect:
        detect["parameters"]["jsCode"] = DETECT_AGENT_COMMAND_CODE
        print("  Updated Detect Agent Command (checks isSelfCommand OR agentPersonalNumber)")
    else:
        print("  WARNING: Detect Agent Command node not found")

    print(f"\n  Final node count: {len(wf['nodes'])}")
    return wf


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    action = sys.argv[1] if len(sys.argv) > 1 else "preview"

    print("=" * 60)
    print("WhatsApp v2 Cloud API -- Self-Message Toggle")
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
            out_path = "workflows/whatsapp-v2/whatsapp_v2_cloudapi_self_toggle.json"
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

            out_path = "workflows/whatsapp-v2/whatsapp_v2_cloudapi_self_toggle.json"
            import os
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(wf, f, indent=2)
            print(f"  Also saved to {out_path}")


if __name__ == "__main__":
    main()

"""
Add manual testing nodes to both WhatsApp workflows.

Adds a "Test WhatsApp Payload" Code node that generates a realistic
sample Cloud API webhook payload, wired to a Manual Trigger so you
can test the full pipeline from the n8n UI without a real WhatsApp message.

Targets:
  - OnyparfRHiiCeRXM  (Cloud API)        — already has Manual Trigger
  - Hfr5mvET000uxoVx  (v2.0 copy)        — needs Manual Trigger added

Usage:
    python tools/add_test_nodes_whatsapp.py
"""

import sys
import json
import uuid

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx

CLOUD_API_WF = "OnyparfRHiiCeRXM"
V2_COPY_WF = "Hfr5mvET000uxoVx"

# Sample WhatsApp Cloud API webhook payload
TEST_PAYLOAD_CODE = r'''// Generate a realistic WhatsApp Cloud API test payload
const now = Date.now();
const testMsgId = 'wamid_TEST_' + now;

const _out = {
  object: 'whatsapp_business_account',
  entry: [{
    id: '000000000000000',
    changes: [{
      value: {
        messaging_product: 'whatsapp',
        metadata: {
          display_phone_number: '27000000000',
          phone_number_id: '000000000000000'
        },
        contacts: [{
          profile: { name: 'Test User' },
          wa_id: '27821234567'
        }],
        messages: [{
          from: '27821234567',
          id: testMsgId,
          timestamp: String(Math.floor(now / 1000)),
          text: { body: 'Hi, I am looking for a 3 bedroom house in Sandton under R2.5 million' },
          type: 'text'
        }]
      },
      field: 'messages'
    }]
  }]
};
return [{ json: _out }];
'''


def uid():
    return str(uuid.uuid4())


def patch_workflow(client, base_url, headers, wf_id, wf_label):
    """Add test nodes to a workflow."""
    print(f"\n{'='*50}")
    print(f"Patching: {wf_label} ({wf_id})")
    print('='*50)

    resp = client.get(f"{base_url}/api/v1/workflows/{wf_id}", headers=headers)
    resp.raise_for_status()
    wf = resp.json()
    nodes = wf["nodes"]
    connections = wf["connections"]
    node_map = {n["name"]: n for n in nodes}

    # Check if test payload node already exists
    if "Test WhatsApp Payload" in node_map:
        print("  Test WhatsApp Payload node already exists, skipping")
        return

    # Find the parse message node (entry point)
    parse_name = None
    for name in ["Parse Message", "1 Parse Message"]:
        if name in node_map:
            parse_name = name
            break
    if not parse_name:
        print("  ERROR: Could not find Parse Message node")
        return

    parse_node = node_map[parse_name]
    parse_pos = parse_node["position"]

    # Find or create Manual Trigger
    manual_trigger = node_map.get("Manual Trigger")
    if manual_trigger:
        print(f"  Manual Trigger already exists at {manual_trigger['position']}")
        test_pos = [manual_trigger["position"][0] + 240, manual_trigger["position"][1]]

        # Disconnect Manual Trigger from Parse Message (we'll rewire through test node)
        if "Manual Trigger" in connections:
            del connections["Manual Trigger"]
            print("  Disconnected Manual Trigger -> Parse Message (will rewire)")
    else:
        # Create Manual Trigger to the left of parse node
        manual_trigger = {
            "parameters": {},
            "id": uid(),
            "name": "Manual Trigger",
            "type": "n8n-nodes-base.manualTrigger",
            "position": [parse_pos[0] - 480, parse_pos[1] - 200],
            "typeVersion": 1
        }
        nodes.append(manual_trigger)
        print(f"  Created Manual Trigger at {manual_trigger['position']}")
        test_pos = [manual_trigger["position"][0] + 240, manual_trigger["position"][1]]

    # Create Test WhatsApp Payload Code node
    test_node = {
        "parameters": {
            "jsCode": TEST_PAYLOAD_CODE
        },
        "id": uid(),
        "name": "Test WhatsApp Payload",
        "type": "n8n-nodes-base.code",
        "position": test_pos,
        "typeVersion": 2
    }
    nodes.append(test_node)
    print(f"  Created Test WhatsApp Payload at {test_pos}")

    # Wire: Manual Trigger -> Test WhatsApp Payload -> Parse Message
    connections["Manual Trigger"] = {
        "main": [[{"node": "Test WhatsApp Payload", "type": "main", "index": 0}]]
    }
    connections["Test WhatsApp Payload"] = {
        "main": [[{"node": parse_name, "type": "main", "index": 0}]]
    }
    print(f"  Wired: Manual Trigger -> Test WhatsApp Payload -> {parse_name}")

    # Push
    update_payload = {
        "name": wf["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": wf.get("settings", {"executionOrder": "v1"})
    }
    put_resp = client.put(
        f"{base_url}/api/v1/workflows/{wf_id}",
        headers=headers,
        json=update_payload
    )
    if put_resp.status_code != 200:
        print(f"  ERROR {put_resp.status_code}: {put_resp.text[:500]}")
        return
    print(f"  Deployed successfully! ({len(nodes)} nodes)")


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    with httpx.Client(timeout=60) as client:
        patch_workflow(client, base_url, headers, CLOUD_API_WF, "WhatsApp Multi-Agent v2 (Cloud API)")
        patch_workflow(client, base_url, headers, V2_COPY_WF, "Whatsapp Multi Agent System optimized copy 2.0")

    print("\nDone! Click 'Test workflow' in n8n UI to run with sample payload.")


if __name__ == "__main__":
    main()

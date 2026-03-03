"""
WhatsApp Single Business Bot - Credential Assigner & Deployer

Discovers credentials by scanning all workflows on the n8n instance,
assigns them to the WhatsApp Single Business Bot workflow, and updates it.

Usage:
    python tools/deploy_whatsapp_bot.py discover   # List all credentials (read-only)
    python tools/deploy_whatsapp_bot.py build      # Fetch + assign creds + save locally
    python tools/deploy_whatsapp_bot.py deploy     # Fetch + assign creds + push to n8n
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


# ── Configuration ──────────────────────────────────────────────

WORKFLOW_NAME = "WhatsApp Multi-Agent (Security Patched)"

# WhatsApp Business Cloud API phone number ID (from .env WHATSAPP_PHONE_NUMBER_ID)
WHATSAPP_PHONE_NUMBER_ID = "956186580917374"

# Known good credential IDs from working workflows on the n8n instance.
# These are used directly (no API discovery needed for known types).
KNOWN_CREDENTIALS = {
    "airtableTokenApi": {"id": "CTVAhYlNsJFMX2lE", "name": "Whatsapp Multi Agent"},
    "httpHeaderAuth": {"id": "xymp9Nho08mRW2Wz", "name": "Header Auth account 2"},
    "openAiApi": {"id": "mNXmJ6IgruQfWkPq", "name": "OpenAi account 10"},
    "gmailOAuth2": {"id": "EC2l4faLSdgePOM6", "name": "Gmail AVM Tutorial"},
    "googleCalendarOAuth2Api": {"id": "I5zIYf0UxlkUt3KG", "name": "Google Calendar AVM Tutorial"},
    # WhatsApp Business Cloud API credentials (AVM Multi Agent)
    "whatsAppApi": {"id": "dCAz6MBXpOXvMJrq", "name": "WhatsApp account AVM Multi Agent"},
    "whatsAppTriggerApi": {"id": "rUyqIX1gaBs3ae6Q", "name": "WhatsApp OAuth AVM Multi Agent"},
}

# n8n node types that require credentials
NODE_TYPE_TO_CRED_TYPE = {
    "n8n-nodes-base.twilio": "twilioApi",
    "n8n-nodes-base.whatsApp": "whatsAppApi",
    "n8n-nodes-base.whatsAppTrigger": "whatsAppTriggerApi",
    "n8n-nodes-base.googleCalendar": "googleCalendarOAuth2Api",
    "n8n-nodes-base.gmail": "gmailOAuth2",
    "n8n-nodes-base.airtable": "airtableTokenApi",
}

# Node types that never need credentials
SKIP_NODE_TYPES = {
    "n8n-nodes-base.stickyNote", "n8n-nodes-base.code",
    "n8n-nodes-base.if", "n8n-nodes-base.switch",
    "n8n-nodes-base.set", "n8n-nodes-base.webhook",
    "n8n-nodes-base.manualTrigger", "n8n-nodes-base.respondToWebhook",
    "n8n-nodes-base.noOp", "n8n-nodes-base.errorTrigger",
}


# ── Credential Discovery (by scanning workflows) ──────────────

def discover_credentials_from_workflows(client) -> Dict[str, List[Dict]]:
    """
    Since n8n cloud doesn't expose GET /credentials, discover all credentials
    by scanning every workflow's nodes for credential references.
    """
    print("\nDiscovering credentials by scanning all workflows...")
    workflows = client.list_workflows(use_cache=False)
    print(f"  Scanning {len(workflows)} workflows...")

    creds_by_type: Dict[str, List[Dict]] = {}
    seen_ids = set()

    for wf in workflows:
        try:
            full_wf = client.get_workflow(wf["id"])
            for node in full_wf.get("nodes", []):
                for ctype, cval in node.get("credentials", {}).items():
                    cid = cval.get("id", "")
                    cname = cval.get("name", "")
                    if not cid or cid.startswith("YOUR_") or cid in seen_ids:
                        continue
                    seen_ids.add(cid)
                    if ctype not in creds_by_type:
                        creds_by_type[ctype] = []
                    creds_by_type[ctype].append({
                        "id": cid,
                        "name": cname,
                        "type": ctype,
                    })
        except Exception:
            pass

    total = sum(len(v) for v in creds_by_type.values())
    print(f"  Found {total} unique credentials across {len(creds_by_type)} types\n")
    for ctype, creds in sorted(creds_by_type.items()):
        print(f"  {ctype}:")
        for c in creds:
            print(f"    - {c['name']} ({c['id']})")

    return creds_by_type


def find_whatsapp_credentials(creds_by_type: Dict) -> Dict[str, Dict]:
    """
    Find WhatsApp Business Cloud API credentials.
    Returns dict with keys 'send' (whatsAppApi) and 'trigger' (whatsAppTriggerApi).
    Prefers credentials with 'AVM Multi Agent' in name.
    """
    result = {"send": None, "trigger": None}

    # Find send credential (whatsAppApi)
    for cred in creds_by_type.get("whatsAppApi", []):
        if "avm multi agent" in cred["name"].lower():
            result["send"] = cred
            break
    if not result["send"]:
        creds = creds_by_type.get("whatsAppApi", [])
        if creds:
            result["send"] = creds[0]

    # Find trigger credential (whatsAppTriggerApi)
    for cred in creds_by_type.get("whatsAppTriggerApi", []):
        if "avm multi agent" in cred["name"].lower():
            result["trigger"] = cred
            break
    if not result["trigger"]:
        creds = creds_by_type.get("whatsAppTriggerApi", [])
        if creds:
            result["trigger"] = creds[0]

    print(f"\n  WhatsApp Send:    {result['send']['name'] + ' (' + result['send']['id'] + ')' if result['send'] else 'NOT FOUND'}")
    print(f"  WhatsApp Trigger: {result['trigger']['name'] + ' (' + result['trigger']['id'] + ')' if result['trigger'] else 'NOT FOUND'}")

    return result


# ── Node Conversion ────────────────────────────────────────────

def convert_twilio_to_whatsapp(node: Dict, wa_cred: Dict) -> Dict:
    """
    Convert a Twilio Send WhatsApp node to WhatsApp Business Cloud API node.
    Based on the real node structure from the working 'Whatsapp Agent' workflow.
    """
    print(f"  Converting '{node['name']}' from Twilio -> WhatsApp Business Cloud API")

    node["type"] = "n8n-nodes-base.whatsApp"
    node["typeVersion"] = 1.1
    node["parameters"] = {
        "operation": "send",
        "phoneNumberId": WHATSAPP_PHONE_NUMBER_ID,
        "recipientPhoneNumber": "={{ $json.to }}",
        "textBody": "={{ $json.body }}",
        "additionalFields": {},
    }
    node["credentials"] = {
        "whatsAppApi": wa_cred
    }
    # Remove Twilio-specific properties
    for key in ("retryOnFail", "maxTries", "waitBetween"):
        node.pop(key, None)

    return node


# ── Credential Assignment ─────────────────────────────────────

def assign_credentials(
    workflow: Dict,
    cred_map: Dict,
    wa_creds: Dict,
) -> Tuple[Dict, List[str]]:
    """Walk all nodes and assign credentials. Returns (workflow, changes)."""
    changes = []

    for node in workflow.get("nodes", []):
        node_name = node.get("name", "unnamed")
        node_type = node.get("type", "")

        if node_type in SKIP_NODE_TYPES:
            continue

        # Special case: Twilio node -> convert to WhatsApp Business Cloud
        if node_type == "n8n-nodes-base.twilio":
            if wa_creds.get("send"):
                convert_twilio_to_whatsapp(node, wa_creds["send"])
                changes.append(f"  {node_name}: CONVERTED Twilio -> WhatsApp -> {wa_creds['send']['name']}")
            else:
                changes.append(f"  {node_name}: SKIPPED - no whatsAppApi credential found")
            continue

        # httpRequest nodes - use nodeCredentialType or genericAuthType
        if node_type == "n8n-nodes-base.httpRequest":
            params = node.get("parameters", {})
            cred_type_key = params.get("nodeCredentialType") or params.get("genericAuthType")
            if not cred_type_key:
                continue

            existing_creds = node.get("credentials", {})
            if cred_type_key in existing_creds:
                current_id = existing_creds[cred_type_key].get("id", "")
                if current_id.startswith("YOUR_") or not current_id:
                    if cred_type_key in cred_map and cred_map[cred_type_key]:
                        existing_creds[cred_type_key] = cred_map[cred_type_key]
                        changes.append(f"  {node_name}: {cred_type_key} -> {cred_map[cred_type_key]['name']}")
                else:
                    changes.append(f"  {node_name}: {cred_type_key} KEPT ({current_id})")
            continue

        # Standard node types
        expected_cred_type = NODE_TYPE_TO_CRED_TYPE.get(node_type)
        if not expected_cred_type:
            continue

        if expected_cred_type not in cred_map or cred_map[expected_cred_type] is None:
            changes.append(f"  {node_name}: SKIPPED - no {expected_cred_type} credential available")
            continue

        resolved = cred_map[expected_cred_type]
        existing_creds = node.get("credentials", {})

        if existing_creds:
            if expected_cred_type in existing_creds:
                current_id = existing_creds[expected_cred_type].get("id", "")
                if current_id == resolved["id"]:
                    changes.append(f"  {node_name}: {expected_cred_type} KEPT ({current_id})")
                elif current_id.startswith("YOUR_") or not current_id:
                    existing_creds[expected_cred_type] = resolved
                    changes.append(f"  {node_name}: {expected_cred_type} -> {resolved['name']} (replaced placeholder)")
                else:
                    # Replace with the target credential even if current is real
                    existing_creds[expected_cred_type] = resolved
                    changes.append(f"  {node_name}: {expected_cred_type} -> {resolved['name']} (replaced {current_id})")
            else:
                node["credentials"][expected_cred_type] = resolved
                changes.append(f"  {node_name}: {expected_cred_type} -> {resolved['name']} (added)")
        else:
            node["credentials"] = {expected_cred_type: resolved}
            changes.append(f"  {node_name}: {expected_cred_type} -> {resolved['name']} (injected)")

    return workflow, changes


# ── Workflow Operations ────────────────────────────────────────

def find_workflow_by_name(client, name: str) -> Optional[str]:
    """Find a workflow ID by name."""
    workflows = client.list_workflows(use_cache=False)
    for wf in workflows:
        if wf.get("name") == name:
            return wf.get("id")
    return None


def print_summary(cred_map: Dict, changes: List[str], result: Dict, wa_creds: Dict):
    """Print deployment summary."""
    print("\n" + "=" * 60)
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    print(f"\nWorkflow: {result.get('name')}")
    print(f"ID: {result.get('id')}")
    print(f"Active: {result.get('active', False)}")

    print(f"\nWhatsApp Credentials:")
    print(f"  Send:    {wa_creds.get('send', {}).get('name', 'NONE')} ({wa_creds.get('send', {}).get('id', '')})")
    print(f"  Trigger: {wa_creds.get('trigger', {}).get('name', 'NONE')} ({wa_creds.get('trigger', {}).get('id', '')})")

    print(f"\nCredential Assignments ({len(changes)}):")
    for change in changes:
        print(change)

    print(f"\nFull Credential Map:")
    for ctype, cred in cred_map.items():
        if cred:
            print(f"  {ctype}: {cred['name']} ({cred['id']})")
        else:
            print(f"  {ctype}: NOT ASSIGNED")

    missing = [t for t, c in cred_map.items() if c is None]
    if missing:
        print(f"\nWARNING: {len(missing)} credential type(s) unresolved:")
        for m in missing:
            print(f"  - {m}")

    print(f"\nNext steps:")
    print(f"  1. Open workflow in n8n UI to verify credential bindings")
    print(f"  2. Update Business Config node with real phone numbers & API keys")
    print(f"  3. Test with Manual Trigger before activating the webhook")


# ── Main ───────────────────────────────────────────────────────

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "build"
    if action not in ("discover", "build", "deploy"):
        print(f"Unknown action: {action}")
        print("Usage: python tools/deploy_whatsapp_bot.py [discover|build|deploy]")
        sys.exit(1)

    sys.path.insert(0, str(Path(__file__).parent))
    from config_loader import load_config
    from n8n_client import N8nClient

    print("=" * 60)
    print("WHATSAPP SINGLE BUSINESS BOT - CREDENTIAL DEPLOYER")
    print("=" * 60)

    config = load_config()
    api_key = config["api_keys"]["n8n"]
    if not api_key:
        print("Error: N8N_API_KEY not found in .env")
        sys.exit(1)

    base_url = config["n8n"]["base_url"]

    with N8nClient(base_url, api_key,
                   timeout=config["n8n"].get("timeout_seconds", 30),
                   max_retries=config["n8n"].get("max_retries", 3),
                   cache_dir=config["paths"]["cache_dir"]) as client:

        health = client.health_check()
        if not health["connected"]:
            print(f"ERROR: Cannot connect to n8n: {health.get('error')}")
            sys.exit(1)
        print(f"Connected to {base_url}")

        # Step 1: Discover credentials by scanning all workflows
        creds_by_type = discover_credentials_from_workflows(client)

        if action == "discover":
            print("\nDiscovery complete.")
            return

        # Step 2: Find WhatsApp credentials
        wa_creds = find_whatsapp_credentials(creds_by_type)

        # Step 3: Build credential map for all node types
        print("\nResolving credentials...")
        cred_map = {}
        for cred_type, known in KNOWN_CREDENTIALS.items():
            if known["id"] == "PLACEHOLDER":
                # Look up from discovered credentials
                live = creds_by_type.get(cred_type, [])
                if live:
                    cred_map[cred_type] = {"id": live[0]["id"], "name": live[0]["name"]}
                else:
                    cred_map[cred_type] = None
            else:
                cred_map[cred_type] = known

        # Only use discovered WhatsApp creds if KNOWN ones are still PLACEHOLDER
        if KNOWN_CREDENTIALS["whatsAppApi"]["id"] == "PLACEHOLDER" and wa_creds.get("send"):
            cred_map["whatsAppApi"] = {
                "id": wa_creds["send"]["id"],
                "name": wa_creds["send"]["name"],
            }

        for ctype, cred in cred_map.items():
            status = f"{cred['name']} ({cred['id']})" if cred else "NOT FOUND"
            print(f"  {ctype}: {status}")

        # Step 4: Fetch live workflow from n8n
        print(f"\nSearching for workflow: {WORKFLOW_NAME}")
        workflow_id = find_workflow_by_name(client, WORKFLOW_NAME)

        if workflow_id:
            print(f"  Found existing workflow: {workflow_id}")
            workflow = client.get_workflow(workflow_id)
        else:
            print("  Workflow not found on n8n. Loading from local template...")
            template_path = (
                Path(__file__).parent.parent.parent
                / "n8n Agentic Workflows"
                / "whatsapp_single_business_bot.json"
            )
            if not template_path.exists():
                print(f"  ERROR: Template not found at {template_path}")
                sys.exit(1)
            with open(template_path, "r", encoding="utf-8") as f:
                workflow = json.load(f)
            workflow_id = None

        node_count = len([n for n in workflow.get("nodes", [])
                         if n.get("type") != "n8n-nodes-base.stickyNote"])
        print(f"  Loaded: {workflow.get('name')} ({node_count} functional nodes)")

        # Step 5: Assign credentials to all nodes
        print("\nAssigning credentials to nodes...")
        workflow, changes = assign_credentials(workflow, cred_map, wa_creds)
        for change in changes:
            print(change)

        # Step 6: Save locally
        output_dir = Path(config["paths"]["tmp_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "whatsapp_bot_with_creds.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(workflow, f, indent=2, ensure_ascii=False)
        print(f"\nSaved modified workflow to: {output_path}")

        if action == "build":
            print("\nBuild complete. Run with 'deploy' to push to n8n.")
            return

        # Step 7: Deploy to n8n
        # Strip extra properties that the n8n cloud API doesn't accept
        ALLOWED_NODE_KEYS = {
            "parameters", "id", "name", "type", "typeVersion", "position",
            "credentials", "continueOnFail", "alwaysOutputData", "notes",
            "webhookId", "disabled", "retryOnFail", "maxTries", "waitBetween",
        }
        clean_nodes = []
        for node in workflow["nodes"]:
            clean_node = {k: v for k, v in node.items() if k in ALLOWED_NODE_KEYS}
            clean_nodes.append(clean_node)

        payload = {
            "name": workflow.get("name", WORKFLOW_NAME),
            "nodes": clean_nodes,
            "connections": workflow["connections"],
            "settings": {"executionOrder": "v1"},
        }

        if workflow_id:
            print(f"\nUpdating workflow {workflow_id}...")
            result = client.update_workflow(workflow_id, payload)
        else:
            print("\nCreating new workflow...")
            result = client.create_workflow(payload)

        print_summary(cred_map, changes, result, wa_creds)


if __name__ == "__main__":
    main()

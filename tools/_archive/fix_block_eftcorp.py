"""
Block all outreach to @eftcorp.atlassian.net addresses.

Patches the live Business Email Management Automation workflow to add
sender blocking conditions on both outreach gates:
  - "Reply Needed?" (controls "Create Reply" node)
  - "Is Interested Reply?" (controls "Send Thank You" node)
"""

import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from n8n_client import N8nClient

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

WORKFLOW_ID = "g2uPmEBbAEtz9YP4L8utG"
BLOCK_DOMAIN = "@eftcorp.atlassian.net"


def main():
    client = N8nClient(
        base_url=os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud"),
        api_key=os.getenv("N8N_API_KEY"),
    )

    print(f"Fetching workflow {WORKFLOW_ID}...")
    wf = client.get_workflow(WORKFLOW_ID)
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}

    patched = []

    # --- Patch "Reply Needed?" node ---
    rn = node_map.get("Reply Needed?")
    if not rn:
        print("ERROR: 'Reply Needed?' node not found")
        return

    conditions = rn["parameters"]["conditions"]["conditions"]
    already_blocked = any(
        c.get("rightValue") == BLOCK_DOMAIN
        for c in conditions
    )
    if already_blocked:
        print(f"'Reply Needed?' already blocks {BLOCK_DOMAIN}")
    else:
        conditions.append({
            "id": "block-eftcorp-reply",
            "leftValue": "={{ $json.sender }}",
            "rightValue": BLOCK_DOMAIN,
            "operator": {
                "type": "string",
                "operation": "notContains"
            }
        })
        patched.append("Reply Needed?")
        print(f"Added {BLOCK_DOMAIN} block to 'Reply Needed?'")

    # --- Patch "Is Interested Reply?" node ---
    ir = node_map.get("Is Interested Reply?")
    if not ir:
        print("ERROR: 'Is Interested Reply?' node not found")
        return

    ir_conditions = ir["parameters"]["conditions"]["conditions"]
    already_blocked_ir = any(
        c.get("rightValue") == BLOCK_DOMAIN
        for c in ir_conditions
    )
    if already_blocked_ir:
        print(f"'Is Interested Reply?' already blocks {BLOCK_DOMAIN}")
    else:
        # Change combinator from just "is_interested_reply = true" to also require sender not containing the domain
        # Need to ensure combinator is "and"
        ir["parameters"]["conditions"]["combinator"] = "and"
        ir_conditions.append({
            "id": "block-eftcorp-interested",
            "leftValue": "={{ $json.sender }}",
            "rightValue": BLOCK_DOMAIN,
            "operator": {
                "type": "string",
                "operation": "notContains"
            }
        })
        patched.append("Is Interested Reply?")
        print(f"Added {BLOCK_DOMAIN} block to 'Is Interested Reply?'")

    if not patched:
        print("Nothing to patch - blocks already in place.")
        return

    print(f"\nPushing patched workflow ({', '.join(patched)})...")
    # Only include API-allowed settings keys
    raw_settings = wf.get("settings", {})
    allowed_settings_keys = {
        "executionOrder", "errorWorkflow", "saveManualExecutions",
        "saveExecutionProgress", "callerPolicy", "timezone"
    }
    clean_settings = {k: v for k, v in raw_settings.items() if k in allowed_settings_keys}
    update_payload = {
        "name": wf["name"],
        "nodes": nodes,
        "connections": wf["connections"],
        "settings": clean_settings,
    }
    try:
        client.update_workflow(WORKFLOW_ID, update_payload)
    except Exception as e:
        if hasattr(e, 'response'):
            print(f"Response body: {e.response.text}")
        raise
    print("Done! All outreach to @eftcorp.atlassian.net is now blocked.")


if __name__ == "__main__":
    main()

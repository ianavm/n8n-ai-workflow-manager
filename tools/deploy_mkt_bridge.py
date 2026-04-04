"""
MKT-BRIDGE: Marketing Portal Action Bridge — Builder & Deployer

Receives portal campaign actions (pause, resume, duplicate, archive) via
webhook and relays them to the appropriate ad platform APIs (Google Ads,
Meta Ads, TikTok Ads, LinkedIn Ads).

Workflow flow:
  1. Webhook receives action from portal API route
  2. Validate payload (client_id, action, entity_type, entity_id)
  3. Look up campaign in Supabase (mkt_campaigns) to get platform + platform_campaign_id
  4. Switch on platform -> call appropriate platform API
  5. Log result to mkt_audit_log
  6. Respond with success/failure

Usage:
    python tools/deploy_mkt_bridge.py build
    python tools/deploy_mkt_bridge.py deploy
    python tools/deploy_mkt_bridge.py activate
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))

from acct_helpers import (
    SUPABASE_KEY,
    SUPABASE_URL,
    build_workflow_json,
    code_node,
    conn,
    noop_node,
    respond_webhook,
    switch_node,
    uid,
    webhook_trigger,
)


# ══════════════════════════════════════════════════════════════
# NODE BUILDERS
# ══════════════════════════════════════════════════════════════


def build_nodes() -> list[dict]:
    """Build all nodes for the MKT-BRIDGE workflow."""
    nodes: list[dict] = []

    # ── 1. Portal Action Webhook ──
    nodes.append(
        webhook_trigger(
            name="Portal Action Webhook",
            path="mkt/portal-action",
            position=[200, 400],
            method="POST",
            response_mode="responseNode",
        )
    )

    # ── 2. Validate Payload ──
    nodes.append(
        code_node(
            name="Validate Payload",
            js_code=(
                "const body = $input.first().json.body || $input.first().json;\n"
                "const { client_id, action, entity_type, entity_id } = body;\n"
                "\n"
                "if (!client_id || !action || !entity_type || !entity_id) {\n"
                "  return [{\n"
                "    json: {\n"
                "      valid: false,\n"
                "      error: 'Missing required fields: client_id, action, entity_type, entity_id',\n"
                "    }\n"
                "  }];\n"
                "}\n"
                "\n"
                "const validActions = ['pause_campaign', 'resume_campaign'];\n"
                "if (!validActions.includes(action)) {\n"
                "  return [{\n"
                "    json: {\n"
                "      valid: false,\n"
                "      error: `Unsupported action: ${action}. Valid: ${validActions.join(', ')}`,\n"
                "    }\n"
                "  }];\n"
                "}\n"
                "\n"
                "return [{\n"
                "  json: {\n"
                "    valid: true,\n"
                "    client_id,\n"
                "    action,\n"
                "    entity_type,\n"
                "    entity_id,\n"
                "    received_at: new Date().toISOString(),\n"
                "  }\n"
                "}];\n"
            ),
            position=[440, 400],
        )
    )

    # ── 3. Is Valid? ──
    nodes.append(
        {
            "parameters": {
                "conditions": {
                    "options": {
                        "caseSensitive": True,
                        "leftValue": "",
                        "typeValidation": "strict",
                    },
                    "conditions": [
                        {
                            "id": uid(),
                            "leftValue": "={{ $json.valid }}",
                            "operator": {
                                "type": "boolean",
                                "operation": "true",
                                "singleValue": True,
                            },
                        }
                    ],
                    "combinator": "and",
                },
            },
            "id": uid(),
            "name": "Is Valid?",
            "type": "n8n-nodes-base.if",
            "position": [680, 400],
            "typeVersion": 2,
        }
    )

    # ── 4. Respond Error (invalid payload) ──
    nodes.append(
        code_node(
            name="Prepare Error Response",
            js_code=(
                "const input = $input.first().json;\n"
                "return [{\n"
                "  json: {\n"
                "    success: false,\n"
                "    error: input.error || 'Validation failed',\n"
                "  }\n"
                "}];\n"
            ),
            position=[920, 600],
        )
    )

    nodes.append(
        respond_webhook(
            name="Respond Error",
            position=[1160, 600],
        )
    )

    # ── 5. Fetch Campaign from Supabase ──
    campaign_url = (
        f"={SUPABASE_URL}/rest/v1/mkt_campaigns"
        "?select=id,name,platform,platform_campaign_id,status,client_id"
        "&id=eq.{{ $json.entity_id }}"
        "&client_id=eq.{{ $json.client_id }}"
        "&limit=1"
    )
    nodes.append(
        {
            "parameters": {
                "method": "GET",
                "url": campaign_url,
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "apikey", "value": SUPABASE_KEY},
                        {"name": "Authorization", "value": f"Bearer {SUPABASE_KEY}"},
                        {
                            "name": "Accept",
                            "value": "application/vnd.pgrst.object+json",
                        },
                    ]
                },
                "options": {
                    "response": {"response": {"responseFormat": "json"}}
                },
            },
            "id": uid(),
            "name": "Fetch Campaign",
            "type": "n8n-nodes-base.httpRequest",
            "position": [920, 300],
            "typeVersion": 4.2,
            "alwaysOutputData": True,
        }
    )

    # ── 6. Merge action context with campaign data ──
    nodes.append(
        code_node(
            name="Prepare Platform Action",
            js_code=(
                "const campaign = $input.first().json;\n"
                "const actionCtx = $('Validate Payload').first().json;\n"
                "\n"
                "if (!campaign || !campaign.id) {\n"
                "  return [{\n"
                "    json: {\n"
                "      platform: 'none',\n"
                "      error: 'Campaign not found',\n"
                "      ...actionCtx,\n"
                "    }\n"
                "  }];\n"
                "}\n"
                "\n"
                "// Map portal action to platform-specific operation\n"
                "const platformAction = actionCtx.action === 'pause_campaign'\n"
                "  ? 'PAUSED'\n"
                "  : 'ENABLED';\n"
                "\n"
                "return [{\n"
                "  json: {\n"
                "    ...actionCtx,\n"
                "    platform: campaign.platform || 'none',\n"
                "    platform_campaign_id: campaign.platform_campaign_id,\n"
                "    campaign_name: campaign.name,\n"
                "    campaign_status: campaign.status,\n"
                "    platform_action: platformAction,\n"
                "  }\n"
                "}];\n"
            ),
            position=[1160, 300],
        )
    )

    # ── 7. Platform Switch ──
    nodes.append(
        switch_node(
            name="Platform Switch",
            rules=[
                {
                    "leftValue": "={{ $json.platform }}",
                    "rightValue": "google_ads",
                    "output": "google",
                },
                {
                    "leftValue": "={{ $json.platform }}",
                    "rightValue": "meta_ads",
                    "output": "meta",
                },
                {
                    "leftValue": "={{ $json.platform }}",
                    "rightValue": "tiktok_ads",
                    "output": "tiktok",
                },
                {
                    "leftValue": "={{ $json.platform }}",
                    "rightValue": "linkedin_ads",
                    "output": "linkedin",
                },
            ],
            position=[1400, 300],
        )
    )

    # ── 8a. Google Ads API (placeholder — requires OAuth) ──
    nodes.append(
        code_node(
            name="Google Ads Action",
            js_code=(
                "// TODO: Replace with real Google Ads API call once OAuth is configured\n"
                "// POST https://googleads.googleapis.com/v17/customers/{customer_id}/campaigns:mutate\n"
                "const input = $input.first().json;\n"
                "return [{\n"
                "  json: {\n"
                "    ...input,\n"
                "    platform_result: 'pending',\n"
                "    platform_message: `Google Ads: ${input.platform_action} for campaign ${input.platform_campaign_id} (manual action required until OAuth configured)`,\n"
                "  }\n"
                "}];\n"
            ),
            position=[1700, 100],
        )
    )

    # ── 8b. Meta Ads API (placeholder — requires Marketing API tier) ──
    nodes.append(
        code_node(
            name="Meta Ads Action",
            js_code=(
                "// TODO: Replace with real Meta Marketing API call\n"
                "// POST https://graph.facebook.com/v21.0/{campaign_id}\n"
                "const input = $input.first().json;\n"
                "const metaStatus = input.platform_action === 'PAUSED' ? 'PAUSED' : 'ACTIVE';\n"
                "return [{\n"
                "  json: {\n"
                "    ...input,\n"
                "    platform_result: 'pending',\n"
                "    platform_message: `Meta Ads: set status=${metaStatus} for campaign ${input.platform_campaign_id} (manual action required until API tier approved)`,\n"
                "  }\n"
                "}];\n"
            ),
            position=[1700, 300],
        )
    )

    # ── 8c. TikTok Ads API (placeholder) ──
    nodes.append(
        code_node(
            name="TikTok Ads Action",
            js_code=(
                "// TODO: Replace with real TikTok Ads API call\n"
                "// POST https://business-api.tiktok.com/open_api/v1.3/campaign/status/update/\n"
                "const input = $input.first().json;\n"
                "return [{\n"
                "  json: {\n"
                "    ...input,\n"
                "    platform_result: 'pending',\n"
                "    platform_message: `TikTok Ads: ${input.platform_action} for campaign ${input.platform_campaign_id}`,\n"
                "  }\n"
                "}];\n"
            ),
            position=[1700, 500],
        )
    )

    # ── 8d. LinkedIn Ads API (placeholder) ──
    nodes.append(
        code_node(
            name="LinkedIn Ads Action",
            js_code=(
                "// TODO: Replace with real LinkedIn Marketing API call\n"
                "// POST https://api.linkedin.com/rest/adCampaigns/{id}\n"
                "const input = $input.first().json;\n"
                "return [{\n"
                "  json: {\n"
                "    ...input,\n"
                "    platform_result: 'pending',\n"
                "    platform_message: `LinkedIn Ads: ${input.platform_action} for campaign ${input.platform_campaign_id}`,\n"
                "  }\n"
                "}];\n"
            ),
            position=[1700, 700],
        )
    )

    # ── 8e. No platform / multi-platform fallback ──
    nodes.append(
        code_node(
            name="No Platform Action",
            js_code=(
                "const input = $input.first().json;\n"
                "return [{\n"
                "  json: {\n"
                "    ...input,\n"
                "    platform_result: 'skipped',\n"
                "    platform_message: `No platform-specific action for platform: ${input.platform}`,\n"
                "  }\n"
                "}];\n"
            ),
            position=[1700, 900],
        )
    )

    # ── 9. Log to Supabase (mkt_audit_log) ──
    audit_url = f"{SUPABASE_URL}/rest/v1/mkt_audit_log"
    nodes.append(
        code_node(
            name="Prepare Audit Entry",
            js_code=(
                "const input = $input.first().json;\n"
                "return [{\n"
                "  json: {\n"
                "    client_id: input.client_id,\n"
                "    entity_type: input.entity_type || 'campaign',\n"
                "    entity_id: input.entity_id,\n"
                "    action: input.action,\n"
                "    result: input.platform_result || 'unknown',\n"
                "    metadata: {\n"
                "      platform: input.platform,\n"
                "      platform_campaign_id: input.platform_campaign_id,\n"
                "      platform_message: input.platform_message,\n"
                "      received_at: input.received_at,\n"
                "    },\n"
                "    created_at: new Date().toISOString(),\n"
                "  }\n"
                "}];\n"
            ),
            position=[2000, 400],
        )
    )

    nodes.append(
        {
            "parameters": {
                "method": "POST",
                "url": audit_url,
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "apikey", "value": SUPABASE_KEY},
                        {
                            "name": "Authorization",
                            "value": f"Bearer {SUPABASE_KEY}",
                        },
                        {"name": "Content-Type", "value": "application/json"},
                        {"name": "Prefer", "value": "return=minimal"},
                    ]
                },
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify($json) }}",
                "options": {
                    "response": {"response": {"responseFormat": "json"}}
                },
            },
            "id": uid(),
            "name": "Write Audit Log",
            "type": "n8n-nodes-base.httpRequest",
            "position": [2240, 400],
            "typeVersion": 4.2,
            "onError": "continueRegularOutput",
        }
    )

    # ── 10. Prepare Success Response ──
    nodes.append(
        code_node(
            name="Prepare Success Response",
            js_code=(
                "const ctx = $('Prepare Audit Entry').first().json;\n"
                "return [{\n"
                "  json: {\n"
                "    success: true,\n"
                "    action: ctx.action,\n"
                "    entity_id: ctx.entity_id,\n"
                "    result: ctx.result,\n"
                "    message: ctx.metadata.platform_message || 'Action processed',\n"
                "  }\n"
                "}];\n"
            ),
            position=[2480, 400],
        )
    )

    # ── 11. Respond Success ──
    nodes.append(
        respond_webhook(
            name="Respond Success",
            position=[2720, 400],
        )
    )

    return nodes


# ══════════════════════════════════════════════════════════════
# CONNECTIONS
# ══════════════════════════════════════════════════════════════


def build_connections() -> dict:
    """Build connections for the MKT-BRIDGE workflow."""
    return {
        "Portal Action Webhook": {
            "main": [[conn("Validate Payload")]],
        },
        "Validate Payload": {
            "main": [[conn("Is Valid?")]],
        },
        # Is Valid: true -> Fetch Campaign, false -> Error Response
        "Is Valid?": {
            "main": [
                [conn("Fetch Campaign")],
                [conn("Prepare Error Response")],
            ],
        },
        "Prepare Error Response": {
            "main": [[conn("Respond Error")]],
        },
        "Fetch Campaign": {
            "main": [[conn("Prepare Platform Action")]],
        },
        "Prepare Platform Action": {
            "main": [[conn("Platform Switch")]],
        },
        # Switch outputs: 0=google, 1=meta, 2=tiktok, 3=linkedin, 4=fallback
        "Platform Switch": {
            "main": [
                [conn("Google Ads Action")],
                [conn("Meta Ads Action")],
                [conn("TikTok Ads Action")],
                [conn("LinkedIn Ads Action")],
                [conn("No Platform Action")],
            ],
        },
        # All platform outputs -> audit
        "Google Ads Action": {
            "main": [[conn("Prepare Audit Entry")]],
        },
        "Meta Ads Action": {
            "main": [[conn("Prepare Audit Entry")]],
        },
        "TikTok Ads Action": {
            "main": [[conn("Prepare Audit Entry")]],
        },
        "LinkedIn Ads Action": {
            "main": [[conn("Prepare Audit Entry")]],
        },
        "No Platform Action": {
            "main": [[conn("Prepare Audit Entry")]],
        },
        # Audit -> Respond
        "Prepare Audit Entry": {
            "main": [[conn("Write Audit Log")]],
        },
        "Write Audit Log": {
            "main": [[conn("Prepare Success Response")]],
        },
        "Prepare Success Response": {
            "main": [[conn("Respond Success")]],
        },
    }


# ══════════════════════════════════════════════════════════════
# WORKFLOW ASSEMBLY
# ══════════════════════════════════════════════════════════════

WORKFLOW_NAME = "MKT-BRIDGE Portal Action Handler"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "marketing-bridge"
OUTPUT_FILENAME = "mkt_bridge_portal_action.json"


def build_workflow() -> dict:
    """Assemble the complete workflow JSON."""
    return build_workflow_json(
        name=WORKFLOW_NAME,
        nodes=build_nodes(),
        connections=build_connections(),
    )


def save_workflow(workflow: dict) -> Path:
    """Save workflow JSON to file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILENAME

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    return output_path


def print_workflow_stats(workflow: dict) -> None:
    """Print workflow statistics."""
    all_nodes = workflow["nodes"]
    func_nodes = [n for n in all_nodes if n["type"] != "n8n-nodes-base.stickyNote"]
    note_nodes = [n for n in all_nodes if n["type"] == "n8n-nodes-base.stickyNote"]
    conn_count = len(workflow["connections"])

    print(f"  Name: {workflow['name']}")
    print(f"  Nodes: {len(func_nodes)} functional + {len(note_nodes)} sticky notes")
    print(f"  Connections: {conn_count}")


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MKT-BRIDGE Portal Action Handler"
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="build",
        choices=["build", "deploy", "activate"],
    )
    parsed = parser.parse_args()
    action = parsed.action

    print("=" * 60)
    print("MKT-BRIDGE: PORTAL ACTION HANDLER")
    print("=" * 60)

    # Build
    print("\nBuilding workflow...")
    workflow = build_workflow()
    output_path = save_workflow(workflow)
    print_workflow_stats(workflow)
    print(f"  Saved to: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    # Deploy / Activate
    if action in ("deploy", "activate"):
        from config_loader import load_config
        from n8n_client import N8nClient

        config = load_config()
        api_key = config["api_keys"]["n8n"]
        base_url = config["n8n"]["base_url"]

        print(f"\nConnecting to {base_url}...")

        with N8nClient(
            base_url,
            api_key,
            timeout=config["n8n"].get("timeout_seconds", 30),
            cache_dir=config["paths"]["cache_dir"],
        ) as client:
            health = client.health_check()
            if not health["connected"]:
                print(f"  ERROR: Cannot connect to n8n: {health.get('error')}")
                sys.exit(1)
            print("  Connected!")

            # Check if workflow already exists (by name)
            existing = None
            try:
                all_wfs = client.list_workflows()
                for wf in all_wfs:
                    if wf["name"] == workflow["name"]:
                        existing = wf
                        break
            except Exception:
                pass

            if existing:
                update_payload = {
                    "name": workflow["name"],
                    "nodes": workflow["nodes"],
                    "connections": workflow["connections"],
                    "settings": workflow["settings"],
                }
                result = client.update_workflow(existing["id"], update_payload)
                wf_id = result.get("id")
                print(f"  Updated: {result.get('name')} (ID: {wf_id})")
            else:
                create_payload = {
                    "name": workflow["name"],
                    "nodes": workflow["nodes"],
                    "connections": workflow["connections"],
                    "settings": workflow["settings"],
                }
                result = client.create_workflow(create_payload)
                wf_id = result.get("id")
                print(f"  Created: {result.get('name')} (ID: {wf_id})")

            if action == "activate" and wf_id:
                print("  Activating...")
                client.activate_workflow(wf_id)
                print("  Activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Open the workflow in n8n UI to verify node connections")
    print("  2. Ensure N8N_BASE_URL is set in portal .env")
    print("  3. Test: POST to /webhook/mkt/portal-action with sample payload")
    print("  4. Create mkt_audit_log table in Supabase (if not exists)")
    print("  5. Replace platform Code nodes with real HTTP API calls as")
    print("     platform OAuth credentials become available")
    print("  6. Once verified, activate the webhook trigger")


if __name__ == "__main__":
    main()

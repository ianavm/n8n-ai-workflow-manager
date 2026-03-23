"""
ADS Workflow Revision -- 2026-03-23

Fixes 6 issues found during full audit:

CRITICAL:
  1. ADS-04: Meta Insights query params malformed (fields/date_preset/level concatenated)
  2. ADS-03: Create Meta Campaign sends empty POST body (missing campaign data)

MEDIUM:
  3. ADS-07: Write Attribution targets wrong table (Budget_Allocations instead of Events)
  4. ADS-01: AI prompt gets incomplete context after Merge (only last item)
  5. ADS-05: Same AI prompt context issue as ADS-01

LOW:
  6. ADS-07: Organic Performance reads Distribution Log (wrong fields) - add alwaysOutputData

Usage:
    python tools/fix_ads_revision_2026_03_23.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from config_loader import load_config
from n8n_client import N8nClient

# Workflow IDs
WF_ADS_01 = "LZ2ZXwra1ep3IEQH"
WF_ADS_03 = "KAkjBo273HOMbVEP"
WF_ADS_04 = "3U4ZXsWW7255zoFm"
WF_ADS_05 = "cwdYl8T8GRSmrWjp"
WF_ADS_07 = "h3YGMAPAcCx3Y51G"

# Operations Control Events table (for attribution logs)
ORCH_BASE_ID = "appTCh0EeXQp0XqzW"
EVENTS_TABLE_ID = "tbl6PqkxZy0Md2Ocf"


def build_client(config):
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def deploy(client, wf_id, wf):
    """Push updated workflow to n8n."""
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    return client.update_workflow(wf_id, payload)


# ─────────────────────────────────────────────────────────────
# FIX 1: ADS-04 Meta Insights query parameters
# ─────────────────────────────────────────────────────────────

def fix_ads04_query_params(client):
    """Split concatenated fields/date_preset/level into separate query params."""
    print("\n" + "=" * 60)
    print("FIX 1: ADS-04 Meta Insights query parameters (CRITICAL)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_04)
    node_map = {n["name"]: n for n in wf["nodes"]}

    meta_node = node_map.get("Meta Ads Get Insights")
    if not meta_node:
        print("  ERROR: 'Meta Ads Get Insights' node not found")
        return False

    old_params = meta_node["parameters"]["options"].get("queryParameters", {})
    old_value = ""
    if old_params.get("parameter"):
        old_value = old_params["parameter"][0].get("value", "")
    print(f"  Old fields value: {old_value[:80]}...")

    # Fix: split into 3 separate query parameters
    meta_node["parameters"]["options"]["queryParameters"] = {
        "parameter": [
            {
                "name": "fields",
                "value": "campaign_id,campaign_name,impressions,clicks,spend,actions,cpc,cpm,ctr,reach,video_views"
            },
            {
                "name": "date_preset",
                "value": "today"
            },
            {
                "name": "level",
                "value": "campaign"
            }
        ]
    }
    print("  Fixed: split into fields + date_preset + level params")

    deploy(client, WF_ADS_04, wf)
    print("  Deployed ADS-04")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 2: ADS-03 Create Meta Campaign POST body
# ─────────────────────────────────────────────────────────────

def fix_ads03_campaign_body(client):
    """Add campaign data as query parameters to the Facebook Graph API POST."""
    print("\n" + "=" * 60)
    print("FIX 2: ADS-03 Create Meta Campaign POST body (CRITICAL)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_03)
    node_map = {n["name"]: n for n in wf["nodes"]}

    meta_node = node_map.get("Create Meta Campaign")
    if not meta_node:
        print("  ERROR: 'Create Meta Campaign' node not found")
        return False

    old_options = meta_node["parameters"].get("options", {})
    print(f"  Old options: {json.dumps(old_options)}")

    # Facebook Marketing API accepts campaign params as query/body params
    meta_node["parameters"]["options"] = {
        "queryParameters": {
            "parameter": [
                {"name": "name", "value": "={{$json.name}}"},
                {"name": "objective", "value": "={{$json.objective}}"},
                {"name": "status", "value": "={{$json.status}}"},
                {"name": "daily_budget", "value": "={{$json.daily_budget}}"},
                {"name": "special_ad_categories", "value": "={{JSON.stringify($json.special_ad_categories || [])}}"},
            ]
        }
    }
    print("  Fixed: added name, objective, status, daily_budget, special_ad_categories params")

    deploy(client, WF_ADS_03, wf)
    print("  Deployed ADS-03")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 3: ADS-07 Write Attribution wrong table
# ─────────────────────────────────────────────────────────────

def fix_ads07_attribution_table(client):
    """Change Write Attribution from Budget_Allocations to Operations Events table."""
    print("\n" + "=" * 60)
    print("FIX 3: ADS-07 Write Attribution wrong table (MEDIUM)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_07)
    node_map = {n["name"]: n for n in wf["nodes"]}

    write_node = node_map.get("Write Attribution")
    if not write_node:
        print("  ERROR: 'Write Attribution' node not found")
        return False

    old_base = write_node["parameters"]["base"]["value"]
    old_table = write_node["parameters"]["table"]["value"]
    print(f"  Old target: base={old_base}, table={old_table}")

    # Change to Operations Control Events table
    write_node["parameters"]["base"]["value"] = ORCH_BASE_ID
    write_node["parameters"]["table"]["value"] = EVENTS_TABLE_ID
    print(f"  New target: base={ORCH_BASE_ID}, table={EVENTS_TABLE_ID} (Events)")

    # Also fix: Read Organic Performance - add alwaysOutputData
    # so it doesn't break the chain when Distribution Log has no matching records
    org_node = node_map.get("Read Organic Performance")
    if org_node:
        org_node["alwaysOutputData"] = True
        print("  Added alwaysOutputData to Read Organic Performance")

    # Also add alwaysOutputData to Read Ad Performance for safety
    ad_node = node_map.get("Read Ad Performance")
    if ad_node:
        ad_node["alwaysOutputData"] = True
        print("  Added alwaysOutputData to Read Ad Performance")

    deploy(client, WF_ADS_07, wf)
    print("  Deployed ADS-07")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 4: ADS-01 AI prompt incomplete context
# ─────────────────────────────────────────────────────────────

def fix_ads01_ai_context(client):
    """Add aggregation Code node between Merge and AI to collect all context."""
    print("\n" + "=" * 60)
    print("FIX 4: ADS-01 AI prompt incomplete context (MEDIUM)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_01)
    node_map = {n["name"]: n for n in wf["nodes"]}

    merge_node = node_map.get("Merge Context")
    ai_node = node_map.get("AI Strategy Generator")
    if not merge_node or not ai_node:
        print("  ERROR: Required nodes not found")
        return False

    # Insert a Code node between Merge and AI to aggregate all items
    import uuid
    agg_node = {
        "id": str(uuid.uuid4()),
        "name": "Aggregate Context",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [875, 300],
        "parameters": {
            "jsCode": (
                "// Collect all merged items into structured context\n"
                "const items = $input.all();\n"
                "const research = [];\n"
                "const campaigns = [];\n"
                "const budgets = [];\n\n"
                "for (const item of items) {\n"
                "  const d = item.json;\n"
                "  if (d['Campaign Name'] && (d.Status === 'Active' || d.Status === 'Launched' || d.Status === 'Planned')) {\n"
                "    campaigns.push(d);\n"
                "  } else if (d['Allocation Name'] || d['Daily Budget ZAR'] !== undefined) {\n"
                "    budgets.push(d);\n"
                "  } else {\n"
                "    research.push(d);\n"
                "  }\n"
                "}\n\n"
                "return [{json: {\n"
                "  research_insights: research,\n"
                "  current_campaigns: campaigns,\n"
                "  budget_allocation: budgets,\n"
                "  timestamp: new Date().toISOString(),\n"
                "}}];\n"
            )
        },
    }
    wf["nodes"].append(agg_node)

    # Rewire: Merge -> Aggregate -> AI
    wf["connections"]["Merge Context"]["main"][0] = [
        {"node": "Aggregate Context", "type": "main", "index": 0}
    ]
    wf["connections"]["Aggregate Context"] = {
        "main": [[{"node": "AI Strategy Generator", "type": "main", "index": 0}]]
    }

    # Update AI prompt to use structured fields
    ai_params = ai_node["parameters"]
    old_body = ai_params["jsonBody"]

    # Replace the three identical $json references with structured fields
    new_body = old_body.replace(
        "ORGANIC CONTENT PERFORMANCE (last 7 days):\\n{{JSON.stringify($json)}}\\n\\nCURRENT PAID CAMPAIGNS:\\n{{JSON.stringify($json)}}\\n\\nBUDGET ALLOCATION:\\n{{JSON.stringify($json)}}",
        "ORGANIC CONTENT PERFORMANCE (last 7 days):\\n{{JSON.stringify($json.research_insights)}}\\n\\nCURRENT PAID CAMPAIGNS:\\n{{JSON.stringify($json.current_campaigns)}}\\n\\nBUDGET ALLOCATION:\\n{{JSON.stringify($json.budget_allocation)}}"
    )

    if new_body != old_body:
        ai_params["jsonBody"] = new_body
        print("  Fixed AI prompt to reference structured fields")
    else:
        print("  WARNING: Could not find prompt pattern to replace")

    # Move AI node right to make room for aggregate
    ai_node["position"] = [1100, 300]

    deploy(client, WF_ADS_01, wf)
    print("  Deployed ADS-01 with new Aggregate Context node")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 5: ADS-05 AI prompt incomplete context
# ─────────────────────────────────────────────────────────────

def fix_ads05_ai_context(client):
    """Add aggregation Code node between Merge and AI in Optimization Engine."""
    print("\n" + "=" * 60)
    print("FIX 5: ADS-05 AI prompt incomplete context (MEDIUM)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_05)
    node_map = {n["name"]: n for n in wf["nodes"]}

    merge_node = node_map.get("Merge Data")
    ai_node = node_map.get("AI Optimizer")
    if not merge_node or not ai_node:
        print("  ERROR: Required nodes not found")
        return False

    # Insert aggregation Code node
    import uuid
    agg_node = {
        "id": str(uuid.uuid4()),
        "name": "Aggregate Data",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1125, 300],
        "parameters": {
            "jsCode": (
                "// Collect performance signals and budgets into one payload\n"
                "const items = $input.all();\n"
                "const performance = [];\n"
                "const budgets = [];\n\n"
                "for (const item of items) {\n"
                "  const d = item.json;\n"
                "  if (d.campaign || d.avgCTR !== undefined || d.roas !== undefined) {\n"
                "    performance.push(d);\n"
                "  } else {\n"
                "    budgets.push(d);\n"
                "  }\n"
                "}\n\n"
                "return [{json: {\n"
                "  performance_signals: performance,\n"
                "  budget_allocation: budgets,\n"
                "  timestamp: new Date().toISOString(),\n"
                "}}];\n"
            )
        },
    }
    wf["nodes"].append(agg_node)

    # Rewire: Merge -> Aggregate -> AI
    wf["connections"]["Merge Data"]["main"][0] = [
        {"node": "Aggregate Data", "type": "main", "index": 0}
    ]
    wf["connections"]["Aggregate Data"] = {
        "main": [[{"node": "AI Optimizer", "type": "main", "index": 0}]]
    }

    # Update AI prompt
    ai_params = ai_node["parameters"]
    old_body = ai_params["jsonBody"]

    new_body = old_body.replace(
        "7-DAY PERFORMANCE DATA:\\n{{JSON.stringify($json)}}\\n\\nCURRENT BUDGET ALLOCATION:\\n{{JSON.stringify($json)}}",
        "7-DAY PERFORMANCE DATA:\\n{{JSON.stringify($json.performance_signals)}}\\n\\nCURRENT BUDGET ALLOCATION:\\n{{JSON.stringify($json.budget_allocation)}}"
    )

    if new_body != old_body:
        ai_params["jsonBody"] = new_body
        print("  Fixed AI prompt to reference structured fields")
    else:
        print("  WARNING: Could not find prompt pattern to replace")

    # Shift AI node right
    ai_node["position"] = [1375, 300]

    deploy(client, WF_ADS_05, wf)
    print("  Deployed ADS-05 with new Aggregate Data node")
    return True


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    config = load_config()

    print("=" * 60)
    print("ADS WORKFLOW REVISION -- 2026-03-23")
    print("=" * 60)

    results = {}

    with build_client(config) as client:
        # CRITICAL
        try:
            results["ads04_query_params"] = fix_ads04_query_params(client)
        except Exception as e:
            print(f"  ERROR: {e}")
            results["ads04_query_params"] = False

        try:
            results["ads03_campaign_body"] = fix_ads03_campaign_body(client)
        except Exception as e:
            print(f"  ERROR: {e}")
            results["ads03_campaign_body"] = False

        # MEDIUM
        try:
            results["ads07_attribution_table"] = fix_ads07_attribution_table(client)
        except Exception as e:
            print(f"  ERROR: {e}")
            results["ads07_attribution_table"] = False

        try:
            results["ads01_ai_context"] = fix_ads01_ai_context(client)
        except Exception as e:
            print(f"  ERROR: {e}")
            results["ads01_ai_context"] = False

        try:
            results["ads05_ai_context"] = fix_ads05_ai_context(client)
        except Exception as e:
            print(f"  ERROR: {e}")
            results["ads05_ai_context"] = False

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  {name}: {status}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"\n  {len(failed)} fix(es) failed.")
    else:
        print("\n  All 5 fixes applied successfully!")


if __name__ == "__main__":
    main()

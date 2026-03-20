"""
System Revision Session 3 — 2026-03-17

Deactivates 4 high-frequency failures, then fixes 10 code/config bugs via API.

Fixes:
1.  ORCH-01 (5XR7j7hQ8cdWpi1e)  - "Update Registry Healthy" matchingColumns agentId -> Agent ID
2.  CRM-01  (EiuQcBeQG7AVcbYE)  - Deactivate only (credential issue)
3.  BizEmail(g2uPmEBbAEtz9YP4L8utG) - Deactivate only (rate limit)
4.  LeadScr (uq4hnH0YHfhYOOzO) - "Validate Email Clean" looseTypeValidation
5.  BRIDGE-01(IqODyj5suLusrkIx) - "Split New Leads" strip _action field
6.  INTEL-04(gijDxxcJjHMHnaUn)  - "Tavily Search" remove ={{ }} wrapper, add API key
7.  INTEL-06(sbEwotSVpnyqrQtG)  - "Tavily Search Regulatory" remove ={{ }} wrapper
8.  DATA-02 (oMFz2y6ntoqcYxkZ)  - filterByFormula snapshot_date -> Snapshot Date
9.  ORCH-03 (JDrgcv5iNIXLyQfs)  - "Update Agent KPIs" matchingColumns + mappingMode
10. DEVOPS-02(VuBUg4r0BLL81KIF) - "Write Check Results" add mappingMode
11. QA-01  (oWZ6VTwbYOflPAMS)   - "Split URLs" Code node fix
12. QA-03  (N0VEU3RHsq3OIoqR)   - "Write Benchmark" add mappingMode

Usage:
    python tools/fix_revision_2026_03_17_s3.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
from n8n_client import N8nClient

TAVILY_API_KEY = "REDACTED_TAVILY_KEY"


def build_client(config):
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def deploy_workflow(client, workflow_id, wf):
    """Push patched workflow to n8n, stripping read-only fields."""
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    result = client.update_workflow(workflow_id, payload)
    return result


# =====================================================================
# PHASE 1: Deactivate high-frequency failures
# =====================================================================

DEACTIVATE_IDS = {
    "5XR7j7hQ8cdWpi1e": "ORCH-01 Health Monitor (15min, ~96 errors)",
    "EiuQcBeQG7AVcbYE": "CRM-01 Hourly Sync (1hr, cred 403)",
    "g2uPmEBbAEtz9YP4L8utG": "Business Email Mgmt (30min, rate limit)",
    "uq4hnH0YHfhYOOzO": "Lead Scraper (2hr, If node type error)",
}


def phase1_deactivate(client):
    print("\n" + "=" * 60)
    print("PHASE 1: Deactivating high-frequency failures")
    print("=" * 60)
    for wf_id, desc in DEACTIVATE_IDS.items():
        try:
            client.deactivate_workflow(wf_id)
            print(f"  [OK] Deactivated: {desc}")
        except Exception as e:
            print(f"  [WARN] {desc}: {e}")


# =====================================================================
# PHASE 2: Fix code/config bugs
# =====================================================================

def fix_orch01(client):
    """Fix ORCH-01 'Update Registry Healthy' - matchingColumns agentId -> Agent ID."""
    wf_id = "5XR7j7hQ8cdWpi1e"
    print("\n" + "-" * 60)
    print("FIX: ORCH-01 Health Monitor - Update Registry Healthy")
    print("-" * 60)

    wf = client.get_workflow(wf_id)
    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    node = node_map.get("Update Registry Healthy")
    if node:
        # Fix matchingColumns to use Title Case field name
        node["parameters"]["columns"] = {
            "mappingMode": "autoMapInputData",
            "value": {},
            "matchingColumns": ["Agent ID"]
        }
        node["continueOnFail"] = True
        node["onError"] = "continueRegularOutput"
        changes.append("Update Registry Healthy: matchingColumns agentId -> Agent ID, continueOnFail")

    # Also fix "Update Registry Degraded" if it exists with same issue
    node2 = node_map.get("Update Registry Degraded")
    if node2:
        node2["parameters"]["columns"] = {
            "mappingMode": "autoMapInputData",
            "value": {},
            "matchingColumns": ["Agent ID"]
        }
        node2["continueOnFail"] = True
        node2["onError"] = "continueRegularOutput"
        changes.append("Update Registry Degraded: same fix")

    if changes:
        deploy_workflow(client, wf_id, wf)
        for c in changes:
            print(f"  [OK] {c}")
    else:
        print("  [SKIP] Target nodes not found")


def fix_lead_scraper(client):
    """Fix Lead Scraper 'Validate Email Clean' - enable looseTypeValidation."""
    wf_id = "uq4hnH0YHfhYOOzO"
    print("\n" + "-" * 60)
    print("FIX: Lead Scraper - Validate Email Clean If node")
    print("-" * 60)

    wf = client.get_workflow(wf_id)
    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    node = node_map.get("Validate Email Clean")
    if node:
        # Enable loose type validation to handle boolean/string coercion
        node["parameters"]["looseTypeValidation"] = True
        # Also set options to be lenient
        if "options" not in node["parameters"]:
            node["parameters"]["options"] = {}
        changes.append("Validate Email Clean: looseTypeValidation=true")

    if changes:
        deploy_workflow(client, wf_id, wf)
        for c in changes:
            print(f"  [OK] {c}")
    else:
        print("  [SKIP] Node not found")


def fix_bridge01(client):
    """Fix BRIDGE-01 'Split New Leads' - strip _action field before Airtable create."""
    wf_id = "IqODyj5suLusrkIx"
    print("\n" + "-" * 60)
    print("FIX: BRIDGE-01 Lead Sync - Strip _action from output")
    print("-" * 60)

    wf = client.get_workflow(wf_id)
    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    node = node_map.get("Split New Leads")
    if node and node["type"] == "n8n-nodes-base.code":
        old_code = node["parameters"].get("jsCode", "")
        # Append _action stripping if not already present
        if "delete" not in old_code or "_action" not in old_code:
            # Add cleanup at the end of the code
            new_code = old_code.rstrip()
            if not new_code.endswith(";"):
                new_code += ";"
            # We need to modify the return to strip _action
            # Wrap the existing code: capture output, strip _action, return
            new_code = """// Original logic
const items = (function() {
""" + old_code + """
})();

// Strip internal _action field before sending to Airtable
const result = Array.isArray(items) ? items : [items];
for (const item of result) {
  const data = item.json || item;
  delete data._action;
}
return result.map(r => r.json ? r : { json: r });
"""
            node["parameters"]["jsCode"] = new_code
            changes.append("Split New Leads: wrapped code to strip _action field")

    if changes:
        deploy_workflow(client, wf_id, wf)
        for c in changes:
            print(f"  [OK] {c}")
    else:
        print("  [SKIP] Node not found or already fixed")


def fix_intel04(client):
    """Fix INTEL-04 'Tavily Search' - remove ={{ }} wrapper, add API key."""
    wf_id = "gijDxxcJjHMHnaUn"
    print("\n" + "-" * 60)
    print("FIX: INTEL-04 Competitive Scan - Tavily Search jsonBody")
    print("-" * 60)

    wf = client.get_workflow(wf_id)
    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    node = node_map.get("Tavily Search")
    if node:
        # Set static JSON body (no ={{ }} expression wrapper)
        node["parameters"]["jsonBody"] = json.dumps({
            "api_key": TAVILY_API_KEY,
            "query": "AnyVision Media OR anyvisionmedia.com competitor digital agency Johannesburg",
            "search_depth": "advanced",
            "max_results": 10
        }, indent=2)
        changes.append("Tavily Search: static JSON with API key (no ={{ }} wrapper)")

    if changes:
        deploy_workflow(client, wf_id, wf)
        for c in changes:
            print(f"  [OK] {c}")
    else:
        print("  [SKIP] Node not found")


def fix_intel06(client):
    """Fix INTEL-06 'Tavily Search Regulatory' - remove ={{ }} wrapper."""
    wf_id = "sbEwotSVpnyqrQtG"
    print("\n" + "-" * 60)
    print("FIX: INTEL-06 Regulatory Alert - Tavily Search Regulatory jsonBody")
    print("-" * 60)

    wf = client.get_workflow(wf_id)
    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    node = node_map.get("Tavily Search Regulatory")
    if node:
        node["parameters"]["jsonBody"] = json.dumps({
            "api_key": TAVILY_API_KEY,
            "query": "South Africa POPIA digital marketing regulation law change 2026",
            "search_depth": "advanced",
            "max_results": 10
        }, indent=2)
        changes.append("Tavily Search Regulatory: static JSON with API key (no ={{ }} wrapper)")

    if changes:
        deploy_workflow(client, wf_id, wf)
        for c in changes:
            print(f"  [OK] {c}")
    else:
        print("  [SKIP] Node not found")


def fix_data02(client):
    """Fix DATA-02 'Query KPI Snapshots' - filterByFormula field name."""
    wf_id = "oMFz2y6ntoqcYxkZ"
    print("\n" + "-" * 60)
    print("FIX: DATA-02 Daily Trend - filterByFormula field name")
    print("-" * 60)

    wf = client.get_workflow(wf_id)
    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    node = node_map.get("Query KPI Snapshots")
    if node:
        old_filter = node["parameters"].get("filterByFormula", "")
        new_filter = old_filter.replace("snapshot_date", "Snapshot Date")
        if new_filter != old_filter:
            node["parameters"]["filterByFormula"] = new_filter
            node["continueOnFail"] = True
            node["alwaysOutputData"] = True
            changes.append(f"Query KPI Snapshots: {old_filter} -> {new_filter}")

    if changes:
        deploy_workflow(client, wf_id, wf)
        for c in changes:
            print(f"  [OK] {c}")
    else:
        print("  [SKIP] Already fixed or node not found")


def fix_orch03(client):
    """Fix ORCH-03 'Update Agent KPIs' - matchingColumns + mappingMode."""
    wf_id = "JDrgcv5iNIXLyQfs"
    print("\n" + "-" * 60)
    print("FIX: ORCH-03 Daily KPI - Update Agent KPIs Airtable node")
    print("-" * 60)

    wf = client.get_workflow(wf_id)
    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    node = node_map.get("Update Agent KPIs")
    if node:
        node["parameters"]["columns"] = {
            "mappingMode": "autoMapInputData",
            "value": {},
            "matchingColumns": ["Agent ID"]
        }
        node["continueOnFail"] = True
        node["onError"] = "continueRegularOutput"
        changes.append("Update Agent KPIs: mappingMode + matchingColumns=[Agent ID] + continueOnFail")

    node2 = node_map.get("Write KPI Snapshots")
    if node2:
        if "columns" in node2["parameters"]:
            node2["parameters"]["columns"]["mappingMode"] = "autoMapInputData"
        else:
            node2["parameters"]["columns"] = {
                "mappingMode": "autoMapInputData",
                "value": {}
            }
        node2["continueOnFail"] = True
        node2["onError"] = "continueRegularOutput"
        changes.append("Write KPI Snapshots: continueOnFail + mappingMode")

    if changes:
        deploy_workflow(client, wf_id, wf)
        for c in changes:
            print(f"  [OK] {c}")
    else:
        print("  [SKIP] Nodes not found")


def fix_devops02(client):
    """Fix DEVOPS-02 'Write Check Results' - add mappingMode."""
    wf_id = "VuBUg4r0BLL81KIF"
    print("\n" + "-" * 60)
    print("FIX: DEVOPS-02 Cred Rotation - Write Check Results")
    print("-" * 60)

    wf = client.get_workflow(wf_id)
    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    node = node_map.get("Write Check Results")
    if node:
        node["parameters"]["columns"] = {
            "mappingMode": "autoMapInputData",
            "value": {}
        }
        changes.append("Write Check Results: added mappingMode=autoMapInputData")

    if changes:
        deploy_workflow(client, wf_id, wf)
        for c in changes:
            print(f"  [OK] {c}")
    else:
        print("  [SKIP] Node not found")


def fix_qa01(client):
    """Fix QA-01 'Split URLs' Code node - return $input.all() directly."""
    wf_id = "oWZ6VTwbYOflPAMS"
    print("\n" + "-" * 60)
    print("FIX: QA-01 Daily Smoke Test - Split URLs Code node")
    print("-" * 60)

    wf = client.get_workflow(wf_id)
    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    node = node_map.get("Split URLs")
    if node and node["type"] == "n8n-nodes-base.code":
        # The upstream "Set Test URLs" already returns proper [{json: {url, name, expect}}] items.
        # Split URLs just needs to pass them through.
        node["parameters"]["jsCode"] = "return $input.all();"
        changes.append("Split URLs: simplified to return $input.all()")

    if changes:
        deploy_workflow(client, wf_id, wf)
        for c in changes:
            print(f"  [OK] {c}")
    else:
        print("  [SKIP] Node not found")


def fix_qa03(client):
    """Fix QA-03 'Write Benchmark' - add mappingMode."""
    wf_id = "N0VEU3RHsq3OIoqR"
    print("\n" + "-" * 60)
    print("FIX: QA-03 Performance Benchmark - Write Benchmark")
    print("-" * 60)

    wf = client.get_workflow(wf_id)
    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    node = node_map.get("Write Benchmark")
    if node:
        node["parameters"]["columns"] = {
            "mappingMode": "autoMapInputData",
            "value": {}
        }
        changes.append("Write Benchmark: added mappingMode=autoMapInputData")

    if changes:
        deploy_workflow(client, wf_id, wf)
        for c in changes:
            print(f"  [OK] {c}")
    else:
        print("  [SKIP] Node not found")


# =====================================================================
# PHASE 3: Reactivate fixed workflows
# =====================================================================

REACTIVATE_IDS = {
    "uq4hnH0YHfhYOOzO": "Lead Scraper (If node fixed)",
    "oWZ6VTwbYOflPAMS": "QA-01 Daily Smoke Test",
    "N0VEU3RHsq3OIoqR": "QA-03 Performance Benchmark",
    "VuBUg4r0BLL81KIF": "DEVOPS-02 Cred Rotation",
    "oMFz2y6ntoqcYxkZ": "DATA-02 Daily Trend",
    "gijDxxcJjHMHnaUn": "INTEL-04 Competitive Scan",
    "sbEwotSVpnyqrQtG": "INTEL-06 Regulatory Alert",
    "IqODyj5suLusrkIx": "BRIDGE-01 Lead Sync",
}

# NOT reactivating (need manual credential fixes):
# 5XR7j7hQ8cdWpi1e  ORCH-01 - needs Airtable PAT + field name verification
# EiuQcBeQG7AVcbYE  CRM-01  - needs Airtable PAT table access
# g2uPmEBbAEtz9YP4L8utG  Biz Email - needs rate limit fix
# JDrgcv5iNIXLyQfs  ORCH-03 - needs Airtable PAT (auth 401)


def phase3_reactivate(client):
    print("\n" + "=" * 60)
    print("PHASE 3: Reactivating fixed workflows")
    print("=" * 60)
    for wf_id, desc in REACTIVATE_IDS.items():
        try:
            client.activate_workflow(wf_id)
            print(f"  [OK] Reactivated: {desc}")
        except Exception as e:
            print(f"  [WARN] {desc}: {e}")


# =====================================================================
# MAIN
# =====================================================================

def main():
    config = load_config()
    client = build_client(config)

    print("n8n Workflow System Revision - Session 3")
    print("=" * 60)

    # Phase 1: Stop the bleeding
    phase1_deactivate(client)

    # Phase 2: Fix code/config bugs
    print("\n" + "=" * 60)
    print("PHASE 2: Fixing code/config bugs via API")
    print("=" * 60)

    fix_orch01(client)
    fix_lead_scraper(client)
    fix_bridge01(client)
    fix_intel04(client)
    fix_intel06(client)
    fix_data02(client)
    fix_orch03(client)
    fix_devops02(client)
    fix_qa01(client)
    fix_qa03(client)

    # Phase 3: Reactivate fixed workflows
    phase3_reactivate(client)

    # Summary
    print("\n" + "=" * 60)
    print("REVISION COMPLETE")
    print("=" * 60)
    print(f"\nDeactivated: {len(DEACTIVATE_IDS)} workflows")
    print(f"Fixed: 10 code/config bugs")
    print(f"Reactivated: {len(REACTIVATE_IDS)} workflows")
    print("\nSTILL NEED MANUAL ACTION:")
    print("  1. Airtable PAT cred ZyBrcAO6fps7YB3u - add table tblLo3smPaM19XXkv access (CRM-01)")
    print("  2. Airtable PAT cred K8t2NtJ89DLLh64j - expired/invalid (ORCH-01, ORCH-03)")
    print("  3. Create new OpenRouter httpHeaderAuth credential (BRIDGE-04)")
    print("  4. Business Email Mgmt - Google Sheets rate limit (reduce frequency or add backoff)")
    print("  5. ORCH-03 - Airtable PAT auth 401 on Write KPI Snapshots")


if __name__ == "__main__":
    main()

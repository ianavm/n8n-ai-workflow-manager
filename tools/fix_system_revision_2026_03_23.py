"""
System Revision -- 2026-03-23

Addresses execution quota crisis + workflow cleanup + hardening.

Phase 1: Deactivate ~40 mock/broken workflows, stretch 3 high-frequency schedules
Phase 2: Deactivate remaining REMAX-tagged workflows
Phase 3: Harden active workflows (alwaysOutputData, continueOnFail, credential sweep)

Usage:
    python tools/fix_system_revision_2026_03_23.py              # all phases
    python tools/fix_system_revision_2026_03_23.py phase1       # execution reduction only
    python tools/fix_system_revision_2026_03_23.py phase2       # cleanup only
    python tools/fix_system_revision_2026_03_23.py phase3       # harden only
    python tools/fix_system_revision_2026_03_23.py --reactivate # restore from manifest
    python tools/fix_system_revision_2026_03_23.py --verify     # post-run verification
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from n8n_client import N8nClient
from config_loader import load_config

MANIFEST_PATH = Path(__file__).parent.parent / ".tmp" / "revision_2026_03_23_manifest.json"

# ─────────────────────────────────────────────────────────────
# PHASE 1A: Mock/broken agent workflows to deactivate
# ─────────────────────────────────────────────────────────────
DEACTIVATE_MOCK = {
    # Knowledge Management -- mock Supabase HTTP
    "yl6JUOIkQstPhGQp": ("KM-01: Document Indexer", "Mock Supabase HTTP endpoints"),
    "Nw5LtlkQZGc3tDJF": ("KM-02: Contradiction Detector", "Mock Supabase HTTP endpoints"),
    "85BvMeuhsc7jCMlw": ("KM-03: FAQ Generator", "Mock Supabase HTTP endpoints"),
    # Data Curation -- mock Supabase HTTP
    "mYMT5IxJUl9TPMcV": ("CURE-01: Nightly Dedup Scan", "Mock Supabase + paired item error"),
    "pbEVUg4fMNmFtaUZ": ("CURE-02: Weekly Quality Report", "Mock Supabase HTTP endpoints"),
    "qortQbQC3sEz7YeN": ("CURE-03: Monthly Schema Audit", "Mock Supabase HTTP endpoints"),
    # QA Testing -- mock Playwright URLs
    "oWZ6VTwbYOflPAMS": ("QA-01: Daily Smoke Test", "Mock Playwright/portal URLs"),
    "0LdRipyCFSBe4k0k": ("QA-02: Weekly Regression Suite", "Mock Playwright/portal URLs"),
    "N0VEU3RHsq3OIoqR": ("QA-03: Performance Benchmark", "Mock portal URLs"),
    # Brand Guard -- mock Blotato/competitor
    "50nJrGBGaqgmT7pr": ("BRAND-01: Pre-Publish Gate", "Webhook, no real publishers"),
    "aLyEUA8r08NvSRUk": ("BRAND-02: Weekly Brand Audit", "Mock Blotato endpoints"),
    "f3TES6QXLW5VQNHA": ("BRAND-03: Competitor Differentiation", "Mock competitor URLs"),
    # Compliance -- mock Supabase HTTP
    "LUu04DSW25dOmWIY": ("COMPLY-01: Monthly Compliance Scan", "Mock Supabase HTTP"),
    "EXnkfN49D36P9LFE": ("COMPLY-02: Ad Policy Check", "Mock ad platform calls"),
    "wNUidyYs4cslPT0W": ("COMPLY-03: POPIA Audit", "Mock Supabase calls"),
    # DevOps -- mock n8n/GitHub API
    "4Aqa5MYibl3sJufj": ("DEVOPS-01: Auto-Deploy Monitor", "Mock n8n API calls"),
    "VuBUg4r0BLL81KIF": ("DEVOPS-02: Credential Rotation Alert", "Mock n8n API calls"),
    "sCx9folUZZHBjT9K": ("DEVOPS-03: Release Notes Generator", "Mock GitHub API calls"),
    # Booking -- mock Google Calendar
    "OnO0pefXoNWWtp7L": ("BOOK-01: Meeting Scheduler", "Mock Google Calendar API"),
    "yIQe9s8RVdMs91oo": ("BOOK-02: Follow-Up Nudge", "Mock Google Calendar API"),
    "TKhl6Oyn7Nx4L9kr": ("BOOK-03: Calendar Optimizer", "Mock Google Calendar API"),
    # Intelligence -- mock Tavily/Supabase/n8n
    "gijDxxcJjHMHnaUn": ("INTEL-04: Daily Competitive Scan", "Mock Tavily API"),
    "S7sUARwMIijtPeRf": ("INTEL-05: Weekly Market Digest", "Mock Tavily API"),
    "sbEwotSVpnyqrQtG": ("INTEL-06: Regulatory Alert", "Mock Tavily API"),
    "P9NgW8csqbCh817f": ("INTEL-01: Cross-Dept Correlator", "Mock Supabase/n8n API"),
    "Fmut5pJ4fVXIfxke": ("INTEL-02: Executive Report", "Mock endpoints"),
    "hSiIZJu5bgDIOCDO": ("INTEL-03: Prompt Performance Tracker", "Needs n8n API cred"),
    # Optimization -- mock Supabase HTTP
    "Rsyz1BHai3q94wPI": ("OPT-01: A/B Test Manager", "Mock Supabase HTTP"),
    "I37U9l1kOcsr8fpP": ("OPT-02: A/B Test Analyzer", "Mock Supabase HTTP"),
    "TPp402GuDxnruRd2": ("OPT-03: Churn Predictor", "Mock Supabase HTTP"),
    # Data Intelligence -- mock Supabase HTTP
    "6gzRYYhAIv08cvIK": ("DATA-01: On-Demand Query Agent", "Webhook, mock Supabase"),
    "oMFz2y6ntoqcYxkZ": ("DATA-02: Daily Trend Dashboard", "Mock Supabase HTTP"),
    "U1PM6yCbbEE8I6YH": ("DATA-03: Monthly Report Automation", "Mock Supabase HTTP"),
    # Broken credentials
    "5XR7j7hQ8cdWpi1e": ("ORCH-01: Health Monitor", "Airtable PAT expired + n8n API cred missing"),
    "EiuQcBeQG7AVcbYE": ("CRM-01: Hourly Sync", "Airtable PAT expired on cred K8t2"),
    # WhatsApp small agents -- mock HTTP
    "YBxMfFdFb7BCUxzi": ("WA-01: Conversation Analyzer", "Mock HTTP endpoints"),
    "twe45qwa4Kwalzdx": ("WA-02: CRM Sync", "Mock HTTP endpoints"),
    "6C9PPWe4IWoUhjq2": ("WA-03: Issue Detector", "Mock HTTP endpoints"),
}

# ─────────────────────────────────────────────────────────────
# PHASE 1A continued: Duplicate/old workflow versions
# ─────────────────────────────────────────────────────────────
DEACTIVATE_DUPLICATES = {
    "rbHj5pTI10wNtBHp": ("INTEL-03 Prompt Tracker (old)", "Duplicate of hSiIZJu5bgDIOCDO"),
    "jOUhPTYMBCf5z4PW": ("OPT-02 A/B Test Analyzer (old)", "Duplicate of I37U9l1kOcsr8fpP"),
    "yYTjNyTIvgaD7Qwa": ("OPT-03 Churn Predictor (old)", "Duplicate of TPp402GuDxnruRd2"),
    "nbNcnixOO7njPA7w": ("CR-01 Health Scorer (old)", "Duplicate of 5Qzbyar2VTIbAuEo"),
    "nOTNEIxTRJKYskCq": ("SUP-01 Ticket Creator (old)", "Duplicate of Pk0B97gW8xtcgHBf"),
    "xFnBYVNwObY9bR7k": ("WA-03 Issue Detector (old)", "Duplicate of 6C9PPWe4IWoUhjq2"),
}

# ─────────────────────────────────────────────────────────────
# PHASE 1B: Schedule stretches
# ─────────────────────────────────────────────────────────────
SCHEDULE_STRETCHES = {
    "tOT9DtpE8DspXSjm": {
        "name": "BRIDGE-02: Email Reply Matcher",
        "old": "every 5 min",
        "new_interval": [{"field": "minutes", "minutesInterval": 30}],
        "saved_per_day": 240,
    },
    "EmpOzaaDGqsLvg5j": {
        "name": "WF-07: Exception Handler",
        "old": "every 15 min",
        "new_interval": [{"field": "hours", "hoursInterval": 1}],
        "saved_per_day": 72,
    },
    "M67NBeAEHfDIJ9wz": {
        "name": "SEO-WF08: Engagement & Community",
        "old": "every 30 min",
        "new_interval": [{"field": "hours", "hoursInterval": 2}],
        "saved_per_day": 36,
    },
}

# ─────────────────────────────────────────────────────────────
# PHASE 3C: Previous ADS fix verification
# ─────────────────────────────────────────────────────────────
ADS_VERIFICATIONS = {
    "3U4ZXsWW7255zoFm": {
        "name": "ADS-04",
        "check": "meta_query_params_separated",
        "node": "Meta Ads Get Insights",
    },
    "KAkjBo273HOMbVEP": {
        "name": "ADS-03",
        "check": "meta_post_body_present",
        "node": "Create Meta Campaign",
    },
    "LZ2ZXwra1ep3IEQH": {
        "name": "ADS-01",
        "check": "aggregate_context_node_exists",
        "node": "Aggregate Context",
    },
    "cwdYl8T8GRSmrWjp": {
        "name": "ADS-05",
        "check": "aggregate_data_node_exists",
        "node": "Aggregate Data",
    },
    "h3YGMAPAcCx3Y51G": {
        "name": "ADS-07",
        "check": "writes_to_events_table",
        "node": "Write Attribution",
    },
}

OLD_OPENROUTER_CRED = "87T4lIBmU8si87Ms"
CORRECT_OPENROUTER_CRED = "9ZgHenDBrFuyboov"


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


def save_manifest(results, purpose):
    """Save deactivation manifest for reactivation."""
    manifest = {
        "created_at": datetime.now().isoformat(),
        "purpose": purpose,
        "workflows": results,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Merge with existing manifest if present
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        existing_ids = {w["id"] for w in existing.get("workflows", [])}
        for r in results:
            if r["id"] not in existing_ids:
                existing["workflows"].append(r)
        existing["updated_at"] = datetime.now().isoformat()
        manifest = existing

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  Manifest saved: {MANIFEST_PATH}")


# ═════════════════════════════════════════════════════════════
# PHASE 1
# ═════════════════════════════════════════════════════════════

def phase1(client):
    print("\n" + "=" * 60)
    print("PHASE 1: EXECUTION REDUCTION")
    print("=" * 60)

    all_targets = {}
    all_targets.update(DEACTIVATE_MOCK)
    all_targets.update(DEACTIVATE_DUPLICATES)

    # 1A: Deactivate mock/broken/duplicate workflows
    print(f"\n--- 1A: Deactivating {len(all_targets)} non-essential workflows ---")
    results = []
    deactivated = 0
    skipped = 0

    for wf_id, (name, reason) in all_targets.items():
        try:
            wf_info = client.get_workflow(wf_id)
            if not wf_info.get("active", False):
                print(f"  SKIP {name} -- already inactive")
                skipped += 1
                continue

            client.deactivate_workflow(wf_id)
            results.append({
                "id": wf_id,
                "name": name,
                "reason": reason,
                "status": "deactivated",
                "deactivated_at": datetime.now().isoformat(),
            })
            deactivated += 1
            print(f"  OFF  {name}")
        except Exception as e:
            results.append({
                "id": wf_id,
                "name": name,
                "reason": reason,
                "status": "error",
                "error": str(e),
                "deactivated_at": datetime.now().isoformat(),
            })
            print(f"  ERR  {name}: {e}")

    save_manifest(results, "System revision 2026-03-23: deactivate mock/broken workflows")
    print(f"\n  Phase 1A: {deactivated} deactivated, {skipped} already inactive")

    # 1B: Stretch high-frequency schedules
    print(f"\n--- 1B: Stretching {len(SCHEDULE_STRETCHES)} high-frequency schedules ---")
    total_saved = 0

    for wf_id, info in SCHEDULE_STRETCHES.items():
        try:
            wf = client.get_workflow(wf_id)
            node_map = {n["name"]: n for n in wf["nodes"]}

            # Find the schedule trigger node
            trigger_node = None
            for node in wf["nodes"]:
                if node.get("type") == "n8n-nodes-base.scheduleTrigger":
                    trigger_node = node
                    break

            if not trigger_node:
                print(f"  SKIP {info['name']} -- no scheduleTrigger found")
                continue

            old_interval = trigger_node["parameters"]["rule"]["interval"]
            trigger_node["parameters"]["rule"]["interval"] = info["new_interval"]

            deploy(client, wf_id, wf)
            total_saved += info["saved_per_day"]
            print(f"  OK   {info['name']}: {info['old']} -> saves {info['saved_per_day']}/day")

        except Exception as e:
            print(f"  ERR  {info['name']}: {e}")

    print(f"\n  Phase 1B: ~{total_saved} executions/day saved from schedule stretches")
    print(f"\n  PHASE 1 TOTAL: ~{deactivated * 2 + total_saved} est. executions/day saved")


# ═════════════════════════════════════════════════════════════
# PHASE 2
# ═════════════════════════════════════════════════════════════

def phase2(client):
    print("\n" + "=" * 60)
    print("PHASE 2: REMAX CLEANUP")
    print("=" * 60)

    all_workflows = client.list_workflows(use_cache=False)
    remax_active = []

    for wf in all_workflows:
        name = wf.get("name", "")
        if not wf.get("active", False):
            continue
        name_lower = name.lower()
        if "remax" in name_lower or "re/max" in name_lower:
            remax_active.append(wf)

    if not remax_active:
        print("  No active REMAX-tagged workflows found.")
        return

    print(f"  Found {len(remax_active)} active REMAX workflow(s):")
    results = []
    for wf in remax_active:
        wf_id = wf["id"]
        name = wf["name"]
        try:
            client.deactivate_workflow(wf_id)
            results.append({
                "id": wf_id,
                "name": name,
                "reason": "REMAX legacy workflow",
                "status": "deactivated",
                "deactivated_at": datetime.now().isoformat(),
            })
            print(f"  OFF  {name} ({wf_id})")
        except Exception as e:
            print(f"  ERR  {name}: {e}")

    if results:
        save_manifest(results, "System revision 2026-03-23: REMAX cleanup")


# ═════════════════════════════════════════════════════════════
# PHASE 3
# ═════════════════════════════════════════════════════════════

def phase3(client):
    print("\n" + "=" * 60)
    print("PHASE 3: HARDEN ACTIVE WORKFLOWS")
    print("=" * 60)

    all_workflows = client.list_workflows(use_cache=False)
    active_workflows = [w for w in all_workflows if w.get("active")]
    print(f"\n  Active workflows to scan: {len(active_workflows)}")

    # 3A: Add alwaysOutputData to Airtable search nodes
    print(f"\n--- 3A: Adding alwaysOutputData to Airtable search nodes ---")
    airtable_fixes = 0
    workflows_fixed = 0

    for wf_summary in active_workflows:
        wf_id = wf_summary["id"]
        try:
            wf = client.get_workflow(wf_id)
        except Exception:
            continue

        changed = False
        for node in wf.get("nodes", []):
            if (node.get("type") == "n8n-nodes-base.airtable"
                    and node.get("parameters", {}).get("operation") == "search"
                    and not node.get("alwaysOutputData")):
                node["alwaysOutputData"] = True
                changed = True
                airtable_fixes += 1

        if changed:
            try:
                deploy(client, wf_id, wf)
                workflows_fixed += 1
            except Exception as e:
                print(f"  ERR deploying {wf_summary.get('name', wf_id)}: {e}")

    print(f"  Fixed {airtable_fixes} Airtable search nodes across {workflows_fixed} workflows")

    # 3B: Add continueOnFail to placeholder HTTP nodes
    print(f"\n--- 3B: Adding continueOnFail to placeholder HTTP nodes ---")
    http_fixes = 0
    PLACEHOLDER_PATTERNS = ["REPLACE", "example.com", "localhost", "placeholder", "your-", "TODO"]

    for wf_summary in active_workflows:
        wf_id = wf_summary["id"]
        try:
            wf = client.get_workflow(wf_id)
        except Exception:
            continue

        changed = False
        for node in wf.get("nodes", []):
            if node.get("type") != "n8n-nodes-base.httpRequest":
                continue
            url = node.get("parameters", {}).get("url", "")
            if any(p.lower() in url.lower() for p in PLACEHOLDER_PATTERNS):
                if node.get("onError") != "continueRegularOutput":
                    node["onError"] = "continueRegularOutput"
                    changed = True
                    http_fixes += 1

        if changed:
            try:
                deploy(client, wf_id, wf)
            except Exception as e:
                print(f"  ERR deploying {wf_summary.get('name', wf_id)}: {e}")

    print(f"  Fixed {http_fixes} placeholder HTTP nodes")

    # 3C: Verify previous ADS fixes
    print(f"\n--- 3C: Verifying previous ADS fixes ---")
    for wf_id, info in ADS_VERIFICATIONS.items():
        try:
            wf = client.get_workflow(wf_id)
            node_map = {n["name"]: n for n in wf["nodes"]}
            node = node_map.get(info["node"])

            if info["check"] == "meta_query_params_separated":
                params = node["parameters"]["options"]["queryParameters"]["parameter"]
                param_names = [p["name"] for p in params]
                ok = "fields" in param_names and "date_preset" in param_names and "level" in param_names
                print(f"  {'OK  ' if ok else 'FAIL'} {info['name']}: query params separated = {ok}")

            elif info["check"] == "meta_post_body_present":
                params = node["parameters"].get("options", {}).get("queryParameters", {}).get("parameter", [])
                param_names = [p["name"] for p in params]
                ok = "name" in param_names and "objective" in param_names
                print(f"  {'OK  ' if ok else 'FAIL'} {info['name']}: POST body present = {ok}")

            elif info["check"] in ("aggregate_context_node_exists", "aggregate_data_node_exists"):
                ok = node is not None
                print(f"  {'OK  ' if ok else 'FAIL'} {info['name']}: {info['node']} exists = {ok}")

            elif info["check"] == "writes_to_events_table":
                table_id = node["parameters"]["table"]["value"]
                ok = table_id == "tbl6PqkxZy0Md2Ocf"
                print(f"  {'OK  ' if ok else 'FAIL'} {info['name']}: writes to Events = {ok}")

        except Exception as e:
            print(f"  ERR  {info['name']}: {e}")

    # 3D: OpenRouter credential sweep
    print(f"\n--- 3D: OpenRouter credential sweep ---")
    old_cred_found = 0

    for wf_summary in active_workflows:
        wf_id = wf_summary["id"]
        try:
            wf = client.get_workflow(wf_id)
        except Exception:
            continue

        changed = False
        for node in wf.get("nodes", []):
            creds = node.get("credentials", {})
            for cred_type, cred_info in creds.items():
                if cred_info.get("id") == OLD_OPENROUTER_CRED:
                    cred_info["id"] = CORRECT_OPENROUTER_CRED
                    cred_info["name"] = "OpenRouter 2WC"
                    changed = True
                    old_cred_found += 1
                    print(f"  SWAP {wf_summary.get('name', wf_id)} / {node['name']}")

        if changed:
            try:
                deploy(client, wf_id, wf)
            except Exception as e:
                print(f"  ERR deploying {wf_summary.get('name', wf_id)}: {e}")

    if old_cred_found == 0:
        print("  No old OpenRouter credentials found -- all clean")
    else:
        print(f"  Swapped {old_cred_found} old OpenRouter credential references")


# ═════════════════════════════════════════════════════════════
# VERIFY
# ═════════════════════════════════════════════════════════════

def verify(client):
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    all_workflows = client.list_workflows(use_cache=False)
    active = [w for w in all_workflows if w.get("active")]
    inactive = [w for w in all_workflows if not w.get("active")]

    print(f"\n  Total workflows: {len(all_workflows)}")
    print(f"  Active: {len(active)}")
    print(f"  Inactive: {len(inactive)}")

    # Check for REPLACE credentials in active workflows
    print(f"\n  Scanning {len(active)} active workflows for issues...")
    replace_creds = 0
    old_openrouter = 0

    for wf_summary in active:
        wf_id = wf_summary["id"]
        try:
            wf = client.get_workflow(wf_id)
        except Exception:
            continue

        for node in wf.get("nodes", []):
            creds = node.get("credentials", {})
            for cred_type, cred_info in creds.items():
                cred_id = cred_info.get("id", "")
                if "REPLACE" in cred_id or "PLACEHOLDER" in cred_id:
                    replace_creds += 1
                    print(f"    REPLACE cred: {wf_summary.get('name')} / {node['name']} / {cred_type}")
                if cred_id == OLD_OPENROUTER_CRED:
                    old_openrouter += 1
                    print(f"    OLD OpenRouter: {wf_summary.get('name')} / {node['name']}")

    print(f"\n  Results:")
    print(f"    Active workflows: {len(active)}")
    print(f"    REPLACE credentials: {replace_creds}")
    print(f"    Old OpenRouter refs: {old_openrouter}")

    target_ok = len(active) <= 60
    creds_ok = replace_creds == 0 and old_openrouter == 0
    print(f"\n    Active count <= 60: {'PASS' if target_ok else 'FAIL'} ({len(active)})")
    print(f"    No stale credentials: {'PASS' if creds_ok else 'FAIL'}")

    # Manifest check
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        deactivated_count = sum(1 for w in manifest.get("workflows", []) if w.get("status") == "deactivated")
        print(f"    Manifest: {deactivated_count} workflows can be reactivated with --reactivate")


# ═════════════════════════════════════════════════════════════
# REACTIVATE
# ═════════════════════════════════════════════════════════════

def reactivate(client):
    print("\n" + "=" * 60)
    print("REACTIVATING FROM MANIFEST")
    print("=" * 60)

    if not MANIFEST_PATH.exists():
        print(f"  No manifest at {MANIFEST_PATH}")
        return

    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    workflows = [w for w in manifest.get("workflows", []) if w.get("status") == "deactivated"]
    print(f"  Found {len(workflows)} workflows to reactivate")

    success = 0
    for wf in workflows:
        try:
            client.activate_workflow(wf["id"])
            print(f"  ON   {wf['name']}")
            success += 1
        except Exception as e:
            print(f"  ERR  {wf['name']}: {e}")

    print(f"\n  Reactivated: {success}/{len(workflows)}")
    if success == len(workflows):
        MANIFEST_PATH.unlink()
        print(f"  Manifest removed.")


# ═════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════

def main():
    config = load_config()
    args = sys.argv[1:]

    print("=" * 60)
    print("SYSTEM REVISION -- 2026-03-23")
    print("=" * 60)

    with build_client(config) as client:
        if "--reactivate" in args:
            reactivate(client)
        elif "--verify" in args:
            verify(client)
        elif "phase1" in args:
            phase1(client)
        elif "phase2" in args:
            phase2(client)
        elif "phase3" in args:
            phase3(client)
        else:
            # Run all phases
            phase1(client)
            phase2(client)
            phase3(client)
            verify(client)


if __name__ == "__main__":
    main()

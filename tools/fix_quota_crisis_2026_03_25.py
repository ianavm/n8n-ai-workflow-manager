"""
Quota Crisis Fix -- 2026-03-25

All 55 active workflows failing with "Execution limit reached" since March 20.
Root cause: n8n Cloud execution quota exhausted (~75,000+ execs/month against plan cap).

Phase 0: EMERGENCY -- Deactivate Self-Healing Error Monitor (breaks cascading error loop)
Phase 1: DEACTIVATE -- 30 shell/mock/credential-less workflows
Phase 2: STRETCH -- 7 high-frequency schedule changes
Phase 3: VERIFY -- Count active workflows, estimate monthly execs

Usage:
    python tools/fix_quota_crisis_2026_03_25.py              # all phases
    python tools/fix_quota_crisis_2026_03_25.py phase0       # kill Self-Healing cascade
    python tools/fix_quota_crisis_2026_03_25.py phase1       # deactivate 30 non-essential
    python tools/fix_quota_crisis_2026_03_25.py phase2       # stretch 7 high-frequency
    python tools/fix_quota_crisis_2026_03_25.py --verify     # post-run verification
    python tools/fix_quota_crisis_2026_03_25.py --reactivate # restore from manifest
    python tools/fix_quota_crisis_2026_03_25.py --dry-run    # preview without executing
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

MANIFEST_PATH = Path(__file__).parent.parent / ".tmp" / "revision_2026_03_25_manifest.json"

DRY_RUN = False

# =================================================================
# PHASE 0: EMERGENCY -- Self-Healing Error Monitor
# =================================================================
EMERGENCY_DEACTIVATE = {
    "EyLZIilcnAidOv7R": ("Self-Healing Error Monitor", "Cascading error loop -- triggers on every failure, doubling exec count"),
}

# =================================================================
# PHASE 1: DEACTIVATE -- Non-essential workflows
# =================================================================
DEACTIVATE = {
    # ADS Dept (8) -- no real ad platform credentials
    "LZ2ZXwra1ep3IEQH": ("ADS-01 Strategy Generator", "No ad platform credentials"),
    "Ygvv6yGVqqOGDYgV": ("ADS-02 Copy & Creative Generator", "No ad platform credentials"),
    "KAkjBo273HOMbVEP": ("ADS-03 Campaign Builder", "No ad platform credentials"),
    "3U4ZXsWW7255zoFm": ("ADS-04 Performance Monitor", "No ad platform credentials"),
    "cwdYl8T8GRSmrWjp": ("ADS-05 Optimization Engine", "No ad platform credentials"),
    "uU3OLLP5vtLpD5uM": ("ADS-06 Creative Recycler", "No ad platform credentials"),
    "h3YGMAPAcCx3Y51G": ("ADS-07 Attribution Engine", "No ad platform credentials"),
    "6cDCfVjuAcZQKStK": ("ADS-08 Reporting Dashboard", "No ad platform credentials"),

    # Support Dept (3) -- mock Supabase/portal endpoints
    "Pk0B97gW8xtcgHBf": ("SUP-01 Ticket Creator", "Mock Supabase/portal endpoints"),
    "EnnsJg43EazmEHJl": ("SUP-02 SLA Monitor", "Mock endpoints, was burning ~2,880 execs/month"),
    "3CQqDNDtgLJi2ZUu": ("SUP-04 KB Builder", "Mock Supabase endpoints"),

    # Client Relations (4) -- mock Supabase HTTP calls
    "5Qzbyar2VTIbAuEo": ("CR-01 Health Scorer", "Mock Supabase HTTP calls"),
    "3ZzWEUmgVNIxNmx3": ("CR-02 Renewal Manager", "Mock Supabase HTTP calls"),
    "e1ufCH2KvuvrBQPm": ("CR-03 Onboarding Automation", "Mock Supabase HTTP calls"),
    "fOygygjEdwAyf5of": ("CR-04 Satisfaction Pulse", "Mock Supabase HTTP calls"),

    # Orchestrator (3) -- mock n8n API / Supabase calls
    "47CJmRKTh9kPZ7u5": ("ORCH-02 Cross-Dept Router", "Mock n8n API / Supabase calls"),
    "JDrgcv5iNIXLyQfs": ("ORCH-03 Daily KPI Aggregation", "Mock Supabase / Airtable calls"),
    "2gXlFqBtOoReQfaT": ("ORCH-04 Weekly Report Generator", "Mock endpoints"),

    # Finance Agent (2) -- no QBO OAuth2 credential
    "3Gb4pWJhsf2aHhsW": ("FIN-08 Cash Flow Forecast", "No QuickBooks OAuth2 credential"),
    "6bo7BSssN6SQeodg": ("FIN-09 Anomaly Detector", "No QuickBooks OAuth2 credential"),

    # Marketing Agent (2) -- mock data analysis endpoints
    "Ns8pI1OowMbNDfUV": ("MKT-05 Campaign ROI Tracker", "Mock data analysis endpoints"),
    "UKIxkygJgJQ245pM": ("MKT-06 Budget Optimizer", "Mock data analysis endpoints"),

    # Content Agent (2) -- mock performance endpoints
    "330wVSlaVBtoKwV1": ("CONTENT-01 Performance Feedback Loop", "Mock performance data endpoints"),
    "dSAt6zYsfLy1e6tH": ("CONTENT-02 Multi-Format Generator", "Mock content processing endpoints"),

    # Financial Intel (3) -- no QBO OAuth2 credential
    "mywOowwRhK3ovV8R": ("FINTEL-01 Monthly Payroll Run", "No QuickBooks OAuth2 credential"),
    "OgLBLCZyQuV1wgEG": ("FINTEL-02 Quarterly VAT Prep", "No QuickBooks OAuth2 credential"),
    "wEXsboGxGfRlEDEH": ("FINTEL-03 Cash Flow Scenarios", "No QuickBooks OAuth2 credential"),

    # CRM Sync (2) -- Airtable PAT expired/scoped out
    "Up3ROwbRMHVjZhvc": ("CRM-02 Nightly Dedup", "Airtable PAT expired or scoped out"),
    "BtOSWQwrhGweBDK9": ("CRM-03 Weekly Enrichment", "Airtable PAT expired or scoped out"),

    # WhatsApp (1) -- pending Meta verification
    "H3Uzy1kmHKLbTVQu_YR82": ("WhatsApp Multi-Agent v2", "Pending Meta/360dialog verification"),
}

# =================================================================
# PHASE 2: STRETCH -- High-frequency triggers
# =================================================================
SCHEDULE_STRETCHES = {
    "gwMuSElYqDTRGFKa": {
        "name": "WF-06 Master Data & Audit",
        "old": "every 1 hour",
        "new_interval": [{"field": "hours", "hoursInterval": 6}],
        "old_monthly": 720,
        "new_monthly": 120,
    },
    "EmpOzaaDGqsLvg5j": {
        "name": "WF-07 Exception Handler",
        "old": "every 1 hour",
        "new_interval": [{"field": "hours", "hoursInterval": 4}],
        "old_monthly": 720,
        "new_monthly": 180,
    },
    "M67NBeAEHfDIJ9wz": {
        "name": "SEO-WF08 Engagement & Community",
        "old": "every 2 hours",
        "new_interval": [{"field": "hours", "hoursInterval": 4}],
        "old_monthly": 360,
        "new_monthly": 180,
    },
    "IqODyj5suLusrkIx": {
        "name": "BRIDGE-01 Lead Sync",
        "old": "every 2 hours",
        "new_interval": [{"field": "hours", "hoursInterval": 6}],
        "old_monthly": 360,
        "new_monthly": 120,
    },
    "tOT9DtpE8DspXSjm": {
        "name": "BRIDGE-02 Email Reply Matcher",
        "old": "every 30 min",
        "new_interval": [{"field": "hours", "hoursInterval": 2}],
        "old_monthly": 1440,
        "new_monthly": 360,
    },
    "uq4hnH0YHfhYOOzO": {
        "name": "Lead Scraper",
        "old": "every 2 hours",
        "new_interval": [{"field": "hours", "hoursInterval": 6}],
        "old_monthly": 360,
        "new_monthly": 120,
    },
    "2extQxrmWCoGgXCp": {
        "name": "Marketing Dept All Workflows",
        "old": "every 2 hours",
        "new_interval": [{"field": "hours", "hoursInterval": 6}],
        "old_monthly": 360,
        "new_monthly": 120,
    },
}

# =================================================================
# Expected active workflows after fix (24 total)
# =================================================================
EXPECTED_ACTIVE = {
    "twSg4SfNdlmdITHj": ("WF-01 Invoicing", 300),
    "CWQ9zjCTaf56RBe6": ("WF-02 Collections", 30),
    "ygwBtSysINRWHJxB": ("WF-03 Payments", 30),
    "ZEcxIC9M5ehQvsbg": ("WF-04 Supplier Bills", 300),
    "f0Wh4SOxbODbs4TE": ("WF-05 Month-End", 1),
    "gwMuSElYqDTRGFKa": ("WF-06 Master Data Audit", 120),
    "EmpOzaaDGqsLvg5j": ("WF-07 Exception Handler", 180),
    "0US5H9smGsrCUsv7": ("SEO-SCORE Scoring Engine", 50),
    "5XZFaoQxfyJOlqje": ("SEO-WF05 Trend Discovery", 8),
    "ipsnBC5Xox4DWgBg": ("SEO-WF06 Content Production", 30),
    "u7LSuq6zmAY8P7fU": ("SEO-WF07 Publishing", 30),
    "M67NBeAEHfDIJ9wz": ("SEO-WF08 Engagement", 180),
    "BpZ4LkxKjHoGfjUq": ("SEO-WF09 Lead Capture", 30),
    "Xlu3tGHgM5DDXnkl": ("SEO-WF10 Maintenance", 4),
    "Y80dDSmWQfUlfvib": ("SEO-WF11 Analytics", 5),
    "IqODyj5suLusrkIx": ("BRIDGE-01 Lead Sync", 120),
    "tOT9DtpE8DspXSjm": ("BRIDGE-02 Email Reply", 360),
    "0ynfcpEwHrPaghTl": ("BRIDGE-03 Scoring", 30),
    "OlHyOU8mHxJ1uZuc": ("BRIDGE-04 Nurture", 30),
    "g2uPmEBbAEtz9YP4L8utG": ("Business Email Mgmt", 600),
    "uq4hnH0YHfhYOOzO": ("Lead Scraper", 120),
    "2extQxrmWCoGgXCp": ("Marketing All", 120),
    "foWQmkUEt79vGZXO": ("Email Suppression Check", 30),
    "Q5XUQfhZO83I948P": ("Contact Form -> Pipeline", 10),
}


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


def deactivate_batch(client, targets, label):
    """Deactivate a batch of workflows and return results."""
    results = []
    deactivated = 0
    skipped = 0
    errors = 0

    for wf_id, (name, reason) in targets.items():
        if DRY_RUN:
            print(f"  [DRY] Would deactivate: {name} ({wf_id})")
            deactivated += 1
            continue

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
            errors += 1
            print(f"  ERR  {name}: {e}")

    print(f"\n  {label}: {deactivated} deactivated, {skipped} already inactive, {errors} errors")
    return results


# =================================================================
# PHASE 0: EMERGENCY
# =================================================================

def phase0(client):
    print("\n" + "=" * 60)
    print("PHASE 0: EMERGENCY -- Kill Self-Healing Cascade")
    print("=" * 60)

    results = deactivate_batch(client, EMERGENCY_DEACTIVATE, "Phase 0")
    if results and not DRY_RUN:
        save_manifest(results, "Quota crisis 2026-03-25: emergency self-healing deactivation")
    return results


# =================================================================
# PHASE 1: DEACTIVATE
# =================================================================

def phase1(client):
    print("\n" + "=" * 60)
    print(f"PHASE 1: DEACTIVATE {len(DEACTIVATE)} non-essential workflows")
    print("=" * 60)

    # Group for display
    groups = {}
    for wf_id, (name, reason) in DEACTIVATE.items():
        prefix = name.split("-")[0].split(" ")[0] if "-" in name else reason.split(" ")[0]
        groups.setdefault(prefix, []).append((wf_id, name, reason))

    results = deactivate_batch(client, DEACTIVATE, "Phase 1")
    if results and not DRY_RUN:
        save_manifest(results, "Quota crisis 2026-03-25: deactivate non-essential workflows")
    return results


# =================================================================
# PHASE 2: STRETCH
# =================================================================

def phase2(client):
    print("\n" + "=" * 60)
    print(f"PHASE 2: STRETCH {len(SCHEDULE_STRETCHES)} high-frequency triggers")
    print("=" * 60)

    total_old = 0
    total_new = 0

    for wf_id, info in SCHEDULE_STRETCHES.items():
        total_old += info["old_monthly"]
        total_new += info["new_monthly"]

        if DRY_RUN:
            saved = info["old_monthly"] - info["new_monthly"]
            print(f"  [DRY] {info['name']}: {info['old']} -> saves {saved}/month")
            continue

        try:
            wf = client.get_workflow(wf_id)

            # Find the schedule trigger node
            trigger_node = None
            for node in wf["nodes"]:
                if node.get("type") == "n8n-nodes-base.scheduleTrigger":
                    trigger_node = node
                    break

            if not trigger_node:
                print(f"  SKIP {info['name']} -- no scheduleTrigger found")
                continue

            trigger_node["parameters"]["rule"]["interval"] = info["new_interval"]
            deploy(client, wf_id, wf)
            saved = info["old_monthly"] - info["new_monthly"]
            print(f"  OK   {info['name']}: {info['old']} -> saves {saved}/month")

        except Exception as e:
            print(f"  ERR  {info['name']}: {e}")

    print(f"\n  Schedule stretch savings: {total_old} -> {total_new} execs/month ({total_old - total_new} saved)")


# =================================================================
# VERIFY
# =================================================================

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

    # Check active vs expected
    active_ids = {w["id"] for w in active}
    expected_ids = set(EXPECTED_ACTIVE.keys())

    unexpected_active = active_ids - expected_ids
    missing_active = expected_ids - active_ids

    print(f"\n--- Active Workflow Check ---")
    if unexpected_active:
        print(f"  UNEXPECTED active ({len(unexpected_active)}):")
        for wf in active:
            if wf["id"] in unexpected_active:
                print(f"    ? {wf.get('name', 'Unknown')} ({wf['id']})")
    else:
        print(f"  No unexpected active workflows -- PASS")

    if missing_active:
        print(f"  MISSING (should be active, {len(missing_active)}):")
        for wf_id in missing_active:
            name, _ = EXPECTED_ACTIVE[wf_id]
            print(f"    ! {name} ({wf_id})")
    else:
        print(f"  All expected workflows active -- PASS")

    # Estimate monthly executions
    print(f"\n--- Execution Budget Estimate ---")
    total_monthly = 0
    for wf in active:
        wf_id = wf["id"]
        if wf_id in EXPECTED_ACTIVE:
            name, est = EXPECTED_ACTIVE[wf_id]
            total_monthly += est
        else:
            total_monthly += 30  # assume daily for unknown

    print(f"  Estimated monthly executions: ~{total_monthly:,}")
    print(f"  Starter plan (2,500):  {'FITS' if total_monthly <= 2500 else 'OVER by ' + str(total_monthly - 2500)}")
    print(f"  Pro plan (10,000):     {'FITS (' + str(round(total_monthly/100)) + '% utilization)' if total_monthly <= 10000 else 'OVER'}")

    # Check deactivated workflows are actually off
    print(f"\n--- Deactivation Verification ---")
    all_deactivate_ids = set(DEACTIVATE.keys()) | set(EMERGENCY_DEACTIVATE.keys())
    still_active = all_deactivate_ids & active_ids
    if still_active:
        print(f"  FAIL: {len(still_active)} workflows still active that should be deactivated:")
        for wf in active:
            if wf["id"] in still_active:
                print(f"    ! {wf.get('name', 'Unknown')} ({wf['id']})")
    else:
        print(f"  All {len(all_deactivate_ids)} target workflows confirmed deactivated -- PASS")

    # Target check
    target_count = len(EXPECTED_ACTIVE)
    count_ok = len(active) <= target_count + 2  # allow small margin
    print(f"\n--- Summary ---")
    print(f"  Active count target: {target_count}")
    print(f"  Actual active: {len(active)}")
    print(f"  Status: {'PASS' if count_ok else 'FAIL -- too many active'}")

    # Manifest info
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        deactivated_count = sum(1 for w in manifest.get("workflows", []) if w.get("status") == "deactivated")
        print(f"\n  Manifest: {deactivated_count} workflows can be reactivated with --reactivate")

    print(f"\n  RECOMMENDATION: Upgrade n8n Cloud to Pro plan (EUR 60/month, 10,000 execs)")


# =================================================================
# REACTIVATE
# =================================================================

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
    print(f"  WARNING: Reactivating all will increase monthly execs significantly!")
    print(f"  Consider reactivating selectively.\n")

    success = 0
    for wf in workflows:
        if DRY_RUN:
            print(f"  [DRY] Would reactivate: {wf['name']} ({wf['id']})")
            success += 1
            continue

        try:
            client.activate_workflow(wf["id"])
            print(f"  ON   {wf['name']}")
            success += 1
        except Exception as e:
            print(f"  ERR  {wf['name']}: {e}")

    print(f"\n  Reactivated: {success}/{len(workflows)}")
    if success == len(workflows) and not DRY_RUN:
        MANIFEST_PATH.unlink()
        print(f"  Manifest removed.")


# =================================================================
# MAIN
# =================================================================

def main():
    global DRY_RUN
    config = load_config()
    args = sys.argv[1:]

    DRY_RUN = "--dry-run" in args

    print("=" * 60)
    print("QUOTA CRISIS FIX -- 2026-03-25")
    if DRY_RUN:
        print("*** DRY RUN -- No changes will be made ***")
    print("=" * 60)
    print(f"  Target: 55 active -> 24 active")
    print(f"  Target: ~75,000 execs/month -> ~2,718 execs/month")

    with build_client(config) as client:
        if "--reactivate" in args:
            reactivate(client)
        elif "--verify" in args:
            verify(client)
        elif "phase0" in args:
            phase0(client)
        elif "phase1" in args:
            phase1(client)
        elif "phase2" in args:
            phase2(client)
        else:
            # Run all phases
            phase0(client)
            phase1(client)
            phase2(client)
            verify(client)


if __name__ == "__main__":
    main()

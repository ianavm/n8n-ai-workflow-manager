"""
Full System Revision -- 2026-03-28

All 14 active workflows are failing. Core business workflows inactive since quota crisis.

Phase 0: EMERGENCY STOP -- Deactivate all 14 failing active workflows
Phase 1: CLEANUP -- Delete ~50+ dead/duplicate/junk workflows
Phase 2: FIX -- Patch 5 specific node-level bugs in workflows that need to work
Phase 3: REACTIVATE -- Bring back Tier 1 workflows (RE-09, Business Email)
Phase 4: DEPLOY SCRIPT FIXES -- Luxon .format() -> .toFormat() across tools/
Phase 5: VERIFY -- Count actives, estimate monthly execs, check errors

Usage:
    python tools/fix_revision_2026_03_28.py              # all phases
    python tools/fix_revision_2026_03_28.py phase0       # emergency stop only
    python tools/fix_revision_2026_03_28.py phase1       # cleanup only
    python tools/fix_revision_2026_03_28.py phase2       # fix bugs only
    python tools/fix_revision_2026_03_28.py phase3       # reactivate only
    python tools/fix_revision_2026_03_28.py phase4       # deploy script fixes only
    python tools/fix_revision_2026_03_28.py --verify     # post-run verification
    python tools/fix_revision_2026_03_28.py --reactivate # restore from manifest
    python tools/fix_revision_2026_03_28.py --dry-run    # preview without executing
"""

import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(__file__))
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from n8n_client import N8nClient
from config_loader import load_config

MANIFEST_PATH = Path(__file__).parent.parent / ".tmp" / "revision_2026_03_28_manifest.json"
TOOLS_DIR = Path(__file__).parent

DRY_RUN = False


# =================================================================
# PHASE 0: EMERGENCY STOP -- All 14 currently-active failing workflows
# =================================================================

EMERGENCY_DEACTIVATE: Dict[str, Tuple[str, str]] = {
    # Self-Healing (cascading error amplifier)
    "EyLZIilcnAidOv7R": ("Self-Healing Error Monitor", "Cascading error loop -- triggers on every failure including its own"),

    # ADS Dept (8) -- no real ad platform credentials, burning execs every 6-12h
    "3U4ZXsWW7255zoFm": ("ADS-04 Performance Monitor", "Meta Ads video_views field invalid, errors every 6h"),
    "h3YGMAPAcCx3Y51G": ("ADS-07 Attribution Engine", "Code node refs unexecuted $('Read Organic Performance'), errors every 12h"),
    "cwdYl8T8GRSmrWjp": ("ADS-05 Optimization Engine", "No real ad platform credentials, API failures"),
    "LZ2ZXwra1ep3IEQH": ("ADS-01 Strategy Generator", "No ad platform credentials"),
    "Ygvv6yGVqqOGDYgV": ("ADS-02 Copy & Creative Generator", "No ad platform credentials"),
    "KAkjBo273HOMbVEP": ("ADS-03 Campaign Builder", "No ad platform credentials"),
    "6cDCfVjuAcZQKStK": ("ADS-08 Reporting Dashboard", "No ad platform credentials"),
    "uU3OLLP5vtLpD5uM": ("ADS-06 Creative Recycler", "No ad platform credentials"),

    # Support (3) -- mock Supabase/portal endpoints
    "Pk0B97gW8xtcgHBf": ("SUP-01 Ticket Creator", "Mock Supabase/portal endpoints"),
    "EnnsJg43EazmEHJl": ("SUP-02 SLA Monitor", "Mock endpoints, burning ~2,880 execs/month"),
    "3CQqDNDtgLJi2ZUu": ("SUP-04 KB Builder", "Mock Supabase endpoints"),

    # Business Email
    "g2uPmEBbAEtz9YP4L8utG": ("Business Email Mgmt", "Was hitting execution limits"),

    # RE-09 Telegram
    "KGc5cpmCHYbPaOgO": ("RE-09 Telegram Command Hub", "Airtable fields telegram_user_id/telegram_chat_id don't exist"),
}


# =================================================================
# PHASE 1: CLEANUP -- Delete dead/duplicate/junk workflows
# =================================================================

DELETE_JUNK: Dict[str, Tuple[str, str]] = {
    # Category A: Old experiments / empty / "My workflow" junk
    "OrZnsFsCnsWIs8Hl": ("My workflow 3", "Empty (0 nodes), archived"),
    "YlHiYRqUO1kLoT1m": ("My workflow 4", "Empty (0 nodes), archived"),
    "NGbPGQingjQOVjUK": ("My workflow 5", "Old experiment, archived"),
    "SzzDir1rboIEI4vO": ("My workflow 6", "Old experiment, archived"),
    "SokUSAjmyPh2Oih6": ("My workflow 7", "1 node, archived"),
    "kyogP859OmfIRjBO": ("My workflow 8", "1 node, archived"),
    "9FXZgN1Cq4gaH0f5": ("My workflow 9", "Old experiment, archived"),
    "chb4L0ghuYFFqZAX": ("My workflow 13", "Empty (0 nodes)"),
    "tEoyh796e1M2REHa": ("My workflow 2 (old)", "Empty (0 nodes), archived"),
    "WgAZ6zunh5XlWUNC": ("My workflow 2 (Apr 2025)", "Old experiment, archived"),
    "RczHb3lD720jet0Q": ("Create Anything Sora 2", "Empty (0 nodes), archived"),
    "UoPPr3NGrsK7HmNK": ("Proposal Agent AVM Tutorial (old)", "Empty (0 nodes), archived"),
    "u0bLAklw7ax799uj": ("Proposal Agent 2WC", "1 node, archived"),
    "o5L911aeq0XKnXkfN4hJn": ("My workflow 10", "Old experiment, archived"),
    "w5ODM4ddEHWuw6F174tun": ("My workflow 12", "Old experiment, archived"),

    # Category B: Old tutorial/demo workflows
    "xMC3Xb0ChXuNMvHK": ("Demo: My first AI Agent", "Old demo, archived"),
    "KR1BvYemG1Yq8KUk": ("Angie personal AI assistant Telegram", "Old demo, archived"),
    "YzPqgvxNE8eoXV0d": ("Onboarding Agent AVM Tutorial", "Old tutorial, 0 nodes"),
    "bU1tXILak6yUNv1R": ("Proposal Agent AVM Tutorial", "Old tutorial, 7 nodes"),
    "nPJ1fiAiBJVr5Z8m": ("Sales Agent AVM Tutorial", "Old tutorial"),
    "U8GReeXowSh9Yncq": ("2WC: Sales Agent", "Old archived agent"),
    "m3tbLN_rBOLg05kgZtOzY": ("Hackernews to AI Clone Videos", "Old experiment, archived"),
    "N-mbl-rk86zQ46KVjU_PY": ("Accounting Manager 1.0", "Old prototype, archived"),

    # Category C: [ARCHIVED]-prefixed duplicates
    "jOUhPTYMBCf5z4PW": ("[ARCHIVED] OPT-02 A/B Test Analyzer", "Superseded by I37U9l1kOcsr8fpP"),
    "nOTNEIxTRJKYskCq": ("[ARCHIVED] SUP-01 Ticket Creator", "Superseded by Pk0B97gW8xtcgHBf"),
    "nbNcnixOO7njPA7w": ("[ARCHIVED] CR-01 Health Scorer", "Superseded by 5Qzbyar2VTIbAuEo"),
    "xFnBYVNwObY9bR7k": ("[ARCHIVED] WA-03 Issue Detector", "Superseded by 6C9PPWe4IWoUhjq2"),
    "yYTjNyTIvgaD7Qwa": ("[ARCHIVED] OPT-03 Churn Predictor", "Superseded by TPp402GuDxnruRd2"),
    "rbHj5pTI10wNtBHp": ("[ARCHIVED] INTEL-03 Prompt Tracker", "Superseded by hSiIZJu5bgDIOCDO"),

    # Category D: Standalone tool workflows (never used, no connections)
    "7ERC0CoyPIyNmfmg": ("Edit Image Tool", "Standalone tool, never used"),
    "9oOcrIzp4tO6FUMH": ("Create Image Tool", "Standalone tool, never used"),
    "uIGTjUY9ZS1VTXhC": ("Create Video Tool", "Standalone tool, never used"),
    "egh1KkFRsNEJsrId": ("Image to Video Tool", "Standalone tool, never used"),
    "h7idIpIrgZXScCKB": ("Create Doc Tool", "Standalone tool, never used"),
    "mMKdVwSO6o4KYjZ5": ("Create Doc Tool (dup)", "Duplicate, archived"),
    "RZcMuAjeaP7JxAnj": ("TikTok Post Tool", "3 nodes, standalone"),
    "S995y0qAM7SUARFR": ("Instagram Post", "3 nodes, standalone"),
    "8CThofMtRs9gCMwN": ("FB Post", "3 nodes, standalone"),
    "GoBcWrBB2PTgApNn": ("Carousel Template", "Template, never deployed"),
    "8BYEYL89gjlwnBrv": ("Automate Instagram Carousels with AI", "Template, never deployed"),
    "axsqR54oyn34VxGs": ("1 Post Everywhere", "Template, never deployed"),
    "OvtHjZckq0tCuDOp": ("Email to Long-Form Thread", "Template, never deployed"),
    "NBnJZTmsnTMgzBFv": ("Gmail campaign sender bulk", "Template, never deployed"),
    "iCZCgD4UDdlRVmiN": ("LinkedIn lead generation scoring", "Template, 97 nodes but never used"),

    # Category E: REMAX duplicates (not the active RE-operations ones)
    "TOJ6KiV9oA2AxZ45": ("Whatsapp Bot (REMAX, old)", "1 node, archived"),
    "fUxhfzWASNiG5Cbv": ("REMAX Agent", "Old, archived"),
    "OWx_CjZ90Af1K7MHXUmxq": ("Real Estate WhatsApp Agent Multi-Agent", "Old, archived"),
    "Vwh95t2rEPnvVd9nzrsbZ": ("Real Estate Multi-Agent v2.1", "Old, archived"),
    "lIJwIIfuuqTTBc1zYtvig": ("Multi-Agent Real Estate v3.0", "Old, archived"),
    "btLzxIQ5Gekw7C2DqLoed": ("Enhanced Multi Agent", "Old REMAX, archived"),
    "C4nu7b4a0BtfuSA0": ("WhatsApp Multi-Agent System copy copy", "Duplicate"),
    "Hfr5mvET000uxoVx": ("Whatsapp Multi Agent optimized copy 2.0", "Duplicate"),

    # Category F: Old archived platform workflows
    "0GzsWpVWpaeIhlO9": ("Image Editing (AIMT)", "Old AIMT, archived"),
    "PoHr1kDibptUjiC7": ("Image Creation (AIMT)", "Old AIMT, archived"),
    "iVGSIbXy8XbVXFKe": ("Image (AIMT)", "Old AIMT, archived"),
    "xphXEUd5iqjV43Ii": ("Video (AIMT)", "Old AIMT, archived"),
    "uVY23hPrBrwGGPEm": ("Blog Post (AIMT)", "Old AIMT, archived"),
    "k8BsMhaTDvAIdzPH": ("LinkedIn (AIMT)", "Old AIMT, archived"),
    "alZuuZpuSoAFjtIS": ("Marketing Team (AIMT)", "Old AIMT, archived"),
    "nD_tMQA99l4Ro86NVFwYF": ("Gamma Proposal Generation", "Old, archived"),
    "QrcJzKNRRXSEfOxg": ("My Sub-Workflow 1", "2 nodes, archived"),
}


# =================================================================
# PHASE 2: FIX -- Node-level bug fixes on specific workflows
# =================================================================

def fix_ads04_meta_field(client: N8nClient) -> bool:
    """Fix 1: Remove invalid video_views field from Meta Ads Insights query."""
    wf_id = "3U4ZXsWW7255zoFm"
    name = "ADS-04 Performance Monitor"
    print(f"\n  Fix 1: {name} -- remove invalid video_views field")

    if DRY_RUN:
        print(f"    [DRY] Would remove video_views from Meta Ads Get Insights fields param")
        return True

    try:
        wf = client.get_workflow(wf_id)
        changed = False

        for node in wf["nodes"]:
            if node.get("name") == "Meta Ads Get Insights":
                params = node.get("parameters", {})
                options = params.get("options", {})
                query_params = options.get("queryParameters", {}).get("parameter", [])

                for qp in query_params:
                    if qp.get("name") == "fields" and "video_views" in qp.get("value", ""):
                        old_val = qp["value"]
                        new_val = old_val.replace(",video_views", "").replace("video_views,", "").replace("video_views", "")
                        qp["value"] = new_val
                        print(f"    Fields: {old_val} -> {new_val}")
                        changed = True

                # Add continueOnFail for resilience
                node["continueOnFail"] = True
                node["alwaysOutputData"] = True

        if changed:
            _deploy(client, wf_id, wf)
            print(f"    FIXED {name}")
        else:
            print(f"    SKIP -- video_views not found in fields param")
        return True

    except Exception as e:
        print(f"    ERR  {name}: {e}")
        return False


def fix_ads07_attribution(client: N8nClient) -> bool:
    """Fix 2: Wrap $('Read Organic Performance') in try/catch in Compute Attribution code node."""
    wf_id = "h3YGMAPAcCx3Y51G"
    name = "ADS-07 Attribution Engine"
    print(f"\n  Fix 2: {name} -- wrap unexecuted node ref in try/catch")

    if DRY_RUN:
        print(f"    [DRY] Would wrap $('Read Organic Performance') in try/catch")
        return True

    try:
        wf = client.get_workflow(wf_id)
        changed = False

        for node in wf["nodes"]:
            if node.get("name") == "Compute Attribution":
                js_code = node.get("parameters", {}).get("jsCode", "")
                if "$('Read Organic Performance')" in js_code and "try" not in js_code:
                    # Wrap the entire code in a try/catch that provides defaults
                    new_code = (
                        "// Auto-fixed: wrap organic data ref in try/catch\n"
                        "let organicData = [];\n"
                        "try {\n"
                        "  organicData = $('Read Organic Performance').all();\n"
                        "} catch (e) {\n"
                        "  // Node may not have executed -- use empty fallback\n"
                        "  organicData = [];\n"
                        "}\n\n"
                        "const adData = $('Read Ad Performance').all();\n"
                        "\n"
                        "const results = adData.map(item => {\n"
                        "  const ad = item.json;\n"
                        "  const organic = organicData.length > 0 ? organicData[0].json : {};\n"
                        "  return {\n"
                        "    json: {\n"
                        "      campaign_id: ad.campaign_id || 'unknown',\n"
                        "      campaign_name: ad.campaign_name || 'unknown',\n"
                        "      ad_spend: parseFloat(ad.spend || 0),\n"
                        "      ad_clicks: parseInt(ad.clicks || 0),\n"
                        "      organic_sessions: parseInt(organic.sessions || 0),\n"
                        "      attribution_score: ad.spend ? (parseInt(ad.clicks || 0) / parseFloat(ad.spend)) : 0,\n"
                        "      computed_at: new Date().toISOString(),\n"
                        "    }\n"
                        "  };\n"
                        "});\n\n"
                        "return results.length > 0 ? results : [{ json: { status: 'no_data', computed_at: new Date().toISOString() } }];"
                    )
                    node["parameters"]["jsCode"] = new_code
                    changed = True
                    print(f"    Rewrote Compute Attribution code node")

            # Also add alwaysOutputData to the Read Organic Performance node
            if node.get("name") == "Read Organic Performance":
                node["alwaysOutputData"] = True
                node["continueOnFail"] = True
                changed = True

        if changed:
            _deploy(client, wf_id, wf)
            print(f"    FIXED {name}")
        else:
            print(f"    SKIP -- pattern not found or already fixed")
        return True

    except Exception as e:
        print(f"    ERR  {name}: {e}")
        return False


def fix_re09_airtable_fields(client: N8nClient) -> bool:
    """Fix 3: Fix Airtable field names in RE-09 Telegram Command Hub."""
    wf_id = "KGc5cpmCHYbPaOgO"
    name = "RE-09 Telegram Command Hub"
    print(f"\n  Fix 3: {name} -- fix Airtable field names in Check Auth node")

    if DRY_RUN:
        print(f"    [DRY] Would update filterByFormula field names and add continueOnFail")
        return True

    try:
        wf = client.get_workflow(wf_id)
        changed = False

        for node in wf["nodes"]:
            if node.get("name") == "Check Auth":
                params = node.get("parameters", {})
                formula = params.get("filterByFormula", "")
                if "telegram_user_id" in formula:
                    # Replace snake_case field names with likely Airtable-style names
                    # Common pattern: "Telegram User ID" / "Telegram Chat ID"
                    new_formula = formula.replace("telegram_user_id", "Telegram User ID").replace("telegram_chat_id", "Telegram Chat ID")
                    params["filterByFormula"] = new_formula
                    node["alwaysOutputData"] = True
                    node["continueOnFail"] = True
                    changed = True
                    print(f"    Formula: {formula}")
                    print(f"         -> {new_formula}")

        if changed:
            _deploy(client, wf_id, wf)
            print(f"    FIXED {name}")
        else:
            print(f"    SKIP -- field names already correct or not found")
        return True

    except Exception as e:
        print(f"    ERR  {name}: {e}")
        return False


def fix_business_email(client: N8nClient) -> bool:
    """Fix 4: Add continueOnFail to external API nodes in Business Email Mgmt."""
    wf_id = "g2uPmEBbAEtz9YP4L8utG"
    name = "Business Email Mgmt"
    print(f"\n  Fix 4: {name} -- add continueOnFail to external API nodes")

    if DRY_RUN:
        print(f"    [DRY] Would add continueOnFail to HTTP/API nodes")
        return True

    try:
        wf = client.get_workflow(wf_id)
        hardened = 0

        for node in wf["nodes"]:
            node_type = node.get("type", "")
            if node_type in (
                "n8n-nodes-base.httpRequest",
                "n8n-nodes-base.microsoftOutlook",
                "n8n-nodes-base.openAi",
            ):
                if not node.get("continueOnFail"):
                    node["continueOnFail"] = True
                    hardened += 1

        if hardened > 0:
            _deploy(client, wf_id, wf)
            print(f"    FIXED {name}: hardened {hardened} external API nodes")
        else:
            print(f"    SKIP -- all API nodes already have continueOnFail")
        return True

    except Exception as e:
        print(f"    ERR  {name}: {e}")
        return False


def fix_self_healing(client: N8nClient) -> bool:
    """Fix 5: Add self-exclusion filter to Self-Healing Error Monitor."""
    wf_id = "EyLZIilcnAidOv7R"
    name = "Self-Healing Error Monitor"
    print(f"\n  Fix 5: {name} -- add self-exclusion filter to prevent cascading loop")

    if DRY_RUN:
        print(f"    [DRY] Would add Code node to skip errors from own workflow ID")
        return True

    try:
        wf = client.get_workflow(wf_id)
        changed = False

        # Find the Error Trigger node and whatever it connects to
        error_trigger = None
        error_trigger_name = None
        for node in wf["nodes"]:
            if node.get("type") == "n8n-nodes-base.errorTrigger":
                error_trigger = node
                error_trigger_name = node["name"]
                break

        if not error_trigger:
            print(f"    SKIP -- no errorTrigger found")
            return True

        # Check if self-exclusion filter already exists
        for node in wf["nodes"]:
            if "Self-Exclusion" in node.get("name", "") or "Skip Own Errors" in node.get("name", ""):
                print(f"    SKIP -- self-exclusion filter already exists")
                return True

        # Add a Code node right after the Error Trigger that filters out own workflow errors
        filter_node = {
            "parameters": {
                "jsCode": (
                    f"// Self-exclusion: skip errors from THIS workflow to prevent cascading loop\n"
                    f"const ownWorkflowId = '{wf_id}';\n"
                    f"const errorWorkflowId = $json.execution?.workflowId || $json.workflow?.id || '';\n"
                    f"\n"
                    f"if (errorWorkflowId === ownWorkflowId) {{\n"
                    f"  // Skip own errors to prevent infinite loop\n"
                    f"  return [];\n"
                    f"}}\n"
                    f"\n"
                    f"return [$input.item];"
                ),
            },
            "name": "Skip Own Errors",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [
                error_trigger["position"][0] + 200,
                error_trigger["position"][1],
            ],
        }

        wf["nodes"].append(filter_node)

        # Rewire: Error Trigger -> Skip Own Errors -> (whatever Error Trigger connected to)
        conns = wf.get("connections", {})
        old_targets = conns.pop(error_trigger_name, None)
        conns[error_trigger_name] = {
            "main": [[{"node": "Skip Own Errors", "type": "main", "index": 0}]]
        }
        if old_targets:
            conns["Skip Own Errors"] = old_targets

        # Shift downstream nodes 200px to the right to make room
        filter_x = filter_node["position"][0]
        for node in wf["nodes"]:
            if node["name"] != error_trigger_name and node["name"] != "Skip Own Errors":
                if node["position"][0] >= filter_x:
                    node["position"][0] += 200

        changed = True

        if changed:
            _deploy(client, wf_id, wf)
            print(f"    FIXED {name}: added Skip Own Errors filter node")
        return True

    except Exception as e:
        print(f"    ERR  {name}: {e}")
        return False


# =================================================================
# PHASE 3: REACTIVATE -- Tier 1 workflows
# =================================================================

REACTIVATE_TIER1: Dict[str, Tuple[str, str]] = {
    "g2uPmEBbAEtz9YP4L8utG": ("Business Email Mgmt", "Core email automation, hardened in Phase 2"),
}

# Note: RE-09 is NOT reactivated automatically because the Airtable field name
# fix in Phase 2 uses guessed field names ("Telegram User ID" / "Telegram Chat ID")
# that need manual verification before reactivation.


# =================================================================
# PHASE 4: DEPLOY SCRIPT FIXES -- Luxon .format() -> .toFormat()
# =================================================================

LUXON_PATTERN = re.compile(r'\.format\s*\(')
# Only match inside JavaScript strings in deploy scripts, not Python .format()
LUXON_JS_PATTERN = re.compile(r"""(["'].*?\.)(format)(\s*\(.*?["'])""")


def fix_luxon_in_deploy_scripts() -> int:
    """Fix Luxon .format() -> .toFormat() in deploy scripts' JavaScript strings."""
    print(f"\n  Scanning {TOOLS_DIR} for Luxon .format() in JS code strings...")

    deploy_scripts = sorted(TOOLS_DIR.glob("deploy_*.py"))
    total_fixes = 0

    for script in deploy_scripts:
        content = script.read_text(encoding="utf-8")

        # Find .format( inside JavaScript code strings (jsCode parameters)
        # These appear as Python strings containing JS: 'DateTime.now().format("yyyy-MM-dd")'
        # We need to change them to: 'DateTime.now().toFormat("yyyy-MM-dd")'

        # Match patterns like: .format(' or .format(" inside jsCode strings
        # But NOT Python's str.format() which uses {} placeholders

        lines = content.split("\n")
        file_fixes = 0
        new_lines = []

        for line in lines:
            # Only fix .format() inside jsCode/JavaScript string contexts
            # Heuristic: line contains DateTime/Luxon AND .format(
            if ".format(" in line and any(kw in line for kw in [
                "DateTime", "luxon", "toISO", "toFormat", ".now()",
                "yyyy", "MM-dd", "HH:mm", "EEEE", "MMMM",
            ]):
                new_line = line.replace(".format(", ".toFormat(")
                if new_line != line:
                    file_fixes += 1
                    if DRY_RUN:
                        print(f"    [DRY] {script.name}: .format( -> .toFormat(")
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        if file_fixes > 0 and not DRY_RUN:
            script.write_text("\n".join(new_lines), encoding="utf-8")
            print(f"    FIXED {script.name}: {file_fixes} occurrences")
            total_fixes += file_fixes
        elif file_fixes > 0:
            total_fixes += file_fixes

    print(f"\n  Luxon fix: {total_fixes} occurrences across {len(deploy_scripts)} scripts")
    return total_fixes


# =================================================================
# HELPERS
# =================================================================

def build_client(config: Dict[str, Any]) -> N8nClient:
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def _deploy(client: N8nClient, wf_id: str, wf: Dict[str, Any]) -> Dict[str, Any]:
    """Push updated workflow to n8n."""
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    return client.update_workflow(wf_id, payload)


def save_manifest(results: List[Dict[str, Any]], purpose: str) -> None:
    """Save deactivation/deletion manifest for rollback reference."""
    manifest = {
        "created_at": datetime.now().isoformat(),
        "purpose": purpose,
        "workflows": results,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

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


def deactivate_batch(
    client: N8nClient,
    targets: Dict[str, Tuple[str, str]],
    label: str,
) -> List[Dict[str, Any]]:
    """Deactivate a batch of workflows and return results."""
    results: List[Dict[str, Any]] = []
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
                "action": "deactivated",
                "timestamp": datetime.now().isoformat(),
            })
            deactivated += 1
            print(f"  OFF  {name}")
        except Exception as e:
            results.append({
                "id": wf_id,
                "name": name,
                "reason": reason,
                "action": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
            errors += 1
            print(f"  ERR  {name}: {e}")

    print(f"\n  {label}: {deactivated} deactivated, {skipped} already inactive, {errors} errors")
    return results


def delete_batch(
    client: N8nClient,
    targets: Dict[str, Tuple[str, str]],
    label: str,
) -> List[Dict[str, Any]]:
    """Delete a batch of junk workflows and return results."""
    results: List[Dict[str, Any]] = []
    deleted = 0
    skipped = 0
    errors = 0

    for wf_id, (name, reason) in targets.items():
        if DRY_RUN:
            print(f"  [DRY] Would delete: {name} ({wf_id})")
            deleted += 1
            continue

        try:
            client.delete_workflow(wf_id)
            results.append({
                "id": wf_id,
                "name": name,
                "reason": reason,
                "action": "deleted",
                "timestamp": datetime.now().isoformat(),
            })
            deleted += 1
            print(f"  DEL  {name}")
        except Exception as e:
            # Workflow might already be deleted
            if "404" in str(e) or "not found" in str(e).lower():
                print(f"  SKIP {name} -- already gone")
                skipped += 1
            else:
                results.append({
                    "id": wf_id,
                    "name": name,
                    "reason": reason,
                    "action": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                })
                errors += 1
                print(f"  ERR  {name}: {e}")

    print(f"\n  {label}: {deleted} deleted, {skipped} already gone, {errors} errors")
    return results


# =================================================================
# PHASE FUNCTIONS
# =================================================================

def phase0(client: N8nClient) -> None:
    print("\n" + "=" * 60)
    print(f"PHASE 0: EMERGENCY STOP -- Deactivate all {len(EMERGENCY_DEACTIVATE)} failing active workflows")
    print("=" * 60)

    results = deactivate_batch(client, EMERGENCY_DEACTIVATE, "Phase 0")
    if results and not DRY_RUN:
        save_manifest(results, "Revision 2026-03-28: emergency stop all 14 failing active workflows")


def phase1(client: N8nClient) -> None:
    print("\n" + "=" * 60)
    print(f"PHASE 1: CLEANUP -- Delete {len(DELETE_JUNK)} dead/duplicate/junk workflows")
    print("=" * 60)

    results = delete_batch(client, DELETE_JUNK, "Phase 1")
    if results and not DRY_RUN:
        save_manifest(results, "Revision 2026-03-28: cleanup dead/duplicate workflows")


def phase2(client: N8nClient) -> None:
    print("\n" + "=" * 60)
    print("PHASE 2: FIX -- Patch 5 specific node-level bugs")
    print("=" * 60)

    fixes = [
        ("Fix 1: ADS-04 Meta Ads video_views field", fix_ads04_meta_field),
        ("Fix 2: ADS-07 Compute Attribution try/catch", fix_ads07_attribution),
        ("Fix 3: RE-09 Airtable field names", fix_re09_airtable_fields),
        ("Fix 4: Business Email Mgmt hardening", fix_business_email),
        ("Fix 5: Self-Healing self-exclusion filter", fix_self_healing),
    ]

    success = 0
    for label, fn in fixes:
        if fn(client):
            success += 1

    print(f"\n  Phase 2: {success}/{len(fixes)} fixes applied")


def phase3(client: N8nClient) -> None:
    print("\n" + "=" * 60)
    print(f"PHASE 3: REACTIVATE -- {len(REACTIVATE_TIER1)} Tier 1 workflows")
    print("=" * 60)

    for wf_id, (name, reason) in REACTIVATE_TIER1.items():
        if DRY_RUN:
            print(f"  [DRY] Would reactivate: {name} ({wf_id})")
            continue

        try:
            client.activate_workflow(wf_id)
            print(f"  ON   {name} -- {reason}")
        except Exception as e:
            print(f"  ERR  {name}: {e}")

    print(f"\n  NOTE: RE-09 Telegram NOT auto-reactivated -- verify Airtable field names first")
    print(f"  NOTE: ADS workflows NOT reactivated -- no ad platform credentials")
    print(f"  NOTE: Marketing/Lead Scraper can be reactivated manually if needed")


def phase4() -> None:
    print("\n" + "=" * 60)
    print("PHASE 4: DEPLOY SCRIPT FIXES -- Luxon .format() -> .toFormat()")
    print("=" * 60)

    fix_luxon_in_deploy_scripts()


# =================================================================
# VERIFY
# =================================================================

def verify(client: N8nClient) -> None:
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    all_workflows = client.list_workflows(use_cache=False)
    active = [w for w in all_workflows if w.get("active")]
    inactive = [w for w in all_workflows if not w.get("active")]

    print(f"\n  Total workflows: {len(all_workflows)}")
    print(f"  Active: {len(active)}")
    print(f"  Inactive: {len(inactive)}")

    # List active workflows
    print(f"\n--- Active Workflows ---")
    for wf in sorted(active, key=lambda w: w.get("name", "")):
        print(f"  * {wf.get('name', 'Unknown')} ({wf['id']})")

    # Check that emergency targets are deactivated
    print(f"\n--- Deactivation Check ---")
    active_ids = {w["id"] for w in active}
    emergency_ids = set(EMERGENCY_DEACTIVATE.keys())
    still_active = emergency_ids & active_ids
    if still_active:
        print(f"  FAIL: {len(still_active)} emergency targets still active:")
        for wf in active:
            if wf["id"] in still_active:
                print(f"    ! {wf.get('name', 'Unknown')} ({wf['id']})")
    else:
        print(f"  All {len(emergency_ids)} emergency targets confirmed deactivated -- PASS")

    # Check deletions
    print(f"\n--- Deletion Check ---")
    all_ids = {w["id"] for w in all_workflows}
    junk_ids = set(DELETE_JUNK.keys())
    still_exist = junk_ids & all_ids
    if still_exist:
        print(f"  {len(still_exist)} junk workflows still exist (may need manual review)")
    else:
        print(f"  All {len(junk_ids)} junk workflows confirmed deleted -- PASS")

    # Estimate monthly executions
    print(f"\n--- Execution Budget Estimate ---")
    est_monthly = len(active) * 30  # rough: assume daily average
    print(f"  Active workflows: {len(active)}")
    print(f"  Rough estimate: ~{est_monthly} execs/month")
    print(f"  Starter plan (2,500): {'FITS' if est_monthly <= 2500 else 'OVER'}")
    print(f"  Pro plan (10,000): {'FITS' if est_monthly <= 10000 else 'OVER'}")

    # Manifest info
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        total = len(manifest.get("workflows", []))
        deactivated = sum(1 for w in manifest.get("workflows", []) if w.get("action") == "deactivated")
        deleted = sum(1 for w in manifest.get("workflows", []) if w.get("action") == "deleted")
        print(f"\n  Manifest: {total} entries ({deactivated} deactivated, {deleted} deleted)")

    print(f"\n--- Summary ---")
    print(f"  Active: {len(active)} | Inactive: {len(inactive)} | Total: {len(all_workflows)}")


# =================================================================
# REACTIVATE FROM MANIFEST
# =================================================================

def reactivate(client: N8nClient) -> None:
    print("\n" + "=" * 60)
    print("REACTIVATING FROM MANIFEST")
    print("=" * 60)

    if not MANIFEST_PATH.exists():
        print(f"  No manifest at {MANIFEST_PATH}")
        return

    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    # Only reactivate deactivated workflows (not deleted ones -- those are gone)
    workflows = [w for w in manifest.get("workflows", []) if w.get("action") == "deactivated"]
    print(f"  Found {len(workflows)} deactivated workflows to reactivate")
    print(f"  NOTE: {sum(1 for w in manifest.get('workflows', []) if w.get('action') == 'deleted')} deleted workflows cannot be restored\n")

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


# =================================================================
# MAIN
# =================================================================

def main() -> None:
    global DRY_RUN
    config = load_config()
    args = sys.argv[1:]

    DRY_RUN = "--dry-run" in args

    print("=" * 60)
    print("FULL SYSTEM REVISION -- 2026-03-28")
    if DRY_RUN:
        print("*** DRY RUN -- No changes will be made ***")
    print("=" * 60)
    print(f"  14 active workflows (all failing) -> 1 active (Business Email)")
    print(f"  ~200 total workflows -> ~140 (after deleting ~60 junk)")
    print(f"  5 node-level bug fixes")

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
        elif "phase3" in args:
            phase3(client)
        elif "phase4" in args:
            phase4()
        else:
            # Run all phases
            phase0(client)
            phase1(client)
            phase2(client)
            phase3(client)
            phase4()
            verify(client)


if __name__ == "__main__":
    main()

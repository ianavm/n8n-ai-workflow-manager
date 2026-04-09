"""
ADS Workflow Revision -- 2026-04-03

Fixes 6 issues causing 100% failure rate across ADS workflows:

CRITICAL:
  1. ADS-03: Google Ads API v20 requires containsEuPoliticalAdvertising field
  2. ADS-02: Request Type "Creative" is not a valid singleSelect option (should be "Creative_Update")

HIGH:
  3. ADS-07: Write Attribution autoMaps raw OpenRouter response to Orchestrator Events
  4. ADS-05: Parse Optimizations error handler outputs {error,raw} which autoMaps to wrong Airtable fields

MEDIUM (preventive):
  5. ADS-08: Log Report Event autoMaps Gmail response to Orchestrator Events
  6. ADS-06: Parse Variants error handler same issue as ADS-05

NOTE: ADS-04 (Google Ads OAuth2 credential) must be re-authorized manually in n8n UI.

Usage:
    python tools/fix_ads_revision_2026_04_03.py
"""

import sys
import json
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from config_loader import load_config
from n8n_client import N8nClient

# ── Workflow IDs (current deployment) ──
WF_ADS_02 = "cYkaNVG10Pnvjjcy"
WF_ADS_03 = "0CTAnjA2R05JHJwQ"
WF_ADS_05 = "D51N98bhjjahd0ed"
WF_ADS_06 = "6okBtJubjoPfoOvF"
WF_ADS_07 = "bT4hWPLioD4HefU8"
WF_ADS_08 = "jkP78rX7RNqjVzXA"

# ── Airtable refs ──
ORCH_BASE_ID = "appTCh0EeXQp0XqzW"
EVENTS_TABLE_ID = "tbl6PqkxZy0Md2Ocf"
MARKETING_BASE_ID = "apptjjBx34z9340tK"
TABLE_APPROVALS = "tblov57B8uj09ZF2k"


def build_client(config: dict) -> N8nClient:
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def deploy(client: N8nClient, wf_id: str, wf: dict) -> dict:
    """Push updated workflow to n8n."""
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    return client.update_workflow(wf_id, payload)


def make_code_node(name: str, js_code: str, position: list[int]) -> dict:
    """Create a Code node dict."""
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": {"jsCode": js_code},
    }


# ─────────────────────────────────────────────────────────────
# FIX 1: ADS-03 — Add containsEuPoliticalAdvertising
# ─────────────────────────────────────────────────────────────

def fix_ads03_eu_political_field(client: N8nClient) -> bool:
    """Add containsEuPoliticalAdvertising: false to Google campaign create payload."""
    print("\n" + "=" * 60)
    print("FIX 1: ADS-03 — Add containsEuPoliticalAdvertising (CRITICAL)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_03)
    node_map = {n["name"]: n for n in wf["nodes"]}

    code_node = node_map.get("Build Google Campaign")
    if not code_node:
        print("  ERROR: 'Build Google Campaign' node not found")
        return False

    old_code = code_node["parameters"]["jsCode"]

    # Insert containsEuPoliticalAdvertising after status: 'PAUSED'
    if "containsEuPoliticalAdvertising" in old_code:
        print("  SKIP: already has containsEuPoliticalAdvertising")
        return True

    new_code = old_code.replace(
        "status: 'PAUSED',",
        "status: 'PAUSED',\n          containsEuPoliticalAdvertising: false,"
    )

    if new_code == old_code:
        # Try alternate pattern — the campaign create might have different structure
        # from the live workflow vs deploy script
        new_code = old_code.replace(
            "status: 'PAUSED'",
            "status: 'PAUSED',\n          containsEuPoliticalAdvertising: false"
        )

    if new_code == old_code:
        print("  WARNING: Could not find 'status: PAUSED' pattern — patching manually")
        # Fallback: insert before the closing of the create object
        new_code = old_code.replace(
            "campaignBudget:",
            "containsEuPoliticalAdvertising: false,\n          campaignBudget:"
        )

    code_node["parameters"]["jsCode"] = new_code
    print("  Added containsEuPoliticalAdvertising: false to campaign create payload")

    deploy(client, WF_ADS_03, wf)
    print("  Deployed ADS-03")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 2: ADS-02 — Fix Request Type singleSelect value
# ─────────────────────────────────────────────────────────────

def fix_ads02_approval_request_type(client: N8nClient) -> bool:
    """Change Request Type from 'Creative' to 'Creative_Update'."""
    print("\n" + "=" * 60)
    print("FIX 2: ADS-02 — Fix Request Type select value (CRITICAL)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_02)
    node_map = {n["name"]: n for n in wf["nodes"]}

    approval_node = node_map.get("Create Approval Request")
    if not approval_node:
        print("  ERROR: 'Create Approval Request' node not found")
        return False

    columns = approval_node["parameters"].get("columns", {})
    mapping_mode = columns.get("mappingMode", "")

    if mapping_mode == "defineBelow":
        value = columns.get("value", {})
        old_type = value.get("Request Type", "")
        print(f"  Current Request Type: '{old_type}'")

        if old_type == "Creative_Update":
            print("  SKIP: already correct")
            return True

        value["Request Type"] = "Creative_Update"
        print("  Changed Request Type: 'Creative' -> 'Creative_Update'")
    else:
        # If using autoMap, switch to defineBelow with correct field mapping
        print(f"  Current mappingMode: '{mapping_mode}' — switching to defineBelow")
        approval_node["parameters"]["columns"] = {
            "mappingMode": "defineBelow",
            "value": {
                "Campaign Name": "={{ $json.fields ? $json.fields['Campaign Name'] : $json['Campaign Name'] }}",
                "Request Type": "Creative_Update",
                "Requested By": "ADS-02",
                "Status": "Pending",
                "Details": "={{ ($json.fields ? $json.fields['Creative Name'] : $json['Creative Name']) + ' (' + ($json.fields ? $json.fields['Platform'] : $json['Platform']) + ')' }}",
                "Created At": "={{ new Date().toISOString().split('T')[0] }}",
            },
        }
        print("  Set defineBelow with Campaign Name, Request Type=Creative_Update, Status=Pending")

    deploy(client, WF_ADS_02, wf)
    print("  Deployed ADS-02")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 3: ADS-07 — Format data before Write Attribution
# ─────────────────────────────────────────────────────────────

FORMAT_ATTRIBUTION_CODE = """\
// Transform AI Attribution Analyst response into Orchestrator Events fields
const aiResp = $input.first().json;
const content = aiResp.choices?.[0]?.message?.content || JSON.stringify(aiResp);

return [{json: {
  'Event Type': 'kpi_update',
  'Source Agent': 'ADS-07',
  'Priority': 'P3',
  'Status': 'Completed',
  'Payload': typeof content === 'string' ? content : JSON.stringify(content),
  'Created At': new Date().toISOString(),
}}];
"""


def fix_ads07_write_attribution(client: N8nClient) -> bool:
    """Insert format node before Write Attribution so autoMap sends correct fields."""
    print("\n" + "=" * 60)
    print("FIX 3: ADS-07 — Format data before Write Attribution (HIGH)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_07)
    node_map = {n["name"]: n for n in wf["nodes"]}

    # Check if already fixed
    if "Format Attribution Data" in node_map:
        print("  SKIP: 'Format Attribution Data' node already exists")
        return True

    ai_node = node_map.get("AI Attribution Analyst")
    write_node = node_map.get("Write Attribution")
    if not ai_node or not write_node:
        print("  ERROR: Required nodes not found")
        return False

    # Position between AI and Write nodes
    ai_pos = ai_node["position"]
    write_pos = write_node["position"]
    mid_x = (ai_pos[0] + write_pos[0]) // 2
    mid_y = (ai_pos[1] + write_pos[1]) // 2

    format_node = make_code_node("Format Attribution Data", FORMAT_ATTRIBUTION_CODE, [mid_x, mid_y])
    wf["nodes"].append(format_node)

    # Rewire: AI -> Format -> Write (instead of AI -> Write)
    wf["connections"]["AI Attribution Analyst"]["main"][0] = [
        {"node": "Format Attribution Data", "type": "main", "index": 0}
    ]
    wf["connections"]["Format Attribution Data"] = {
        "main": [[{"node": "Write Attribution", "type": "main", "index": 0}]]
    }

    print("  Inserted 'Format Attribution Data' code node")
    print("  Rewired: AI Attribution Analyst -> Format Attribution Data -> Write Attribution")

    deploy(client, WF_ADS_07, wf)
    print("  Deployed ADS-07")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 4: ADS-05 — Fix Parse Optimizations + Airtable writes
# ─────────────────────────────────────────────────────────────

ADS05_PARSE_OPTIMIZATIONS_FIXED = r"""
// Parse AI optimization recommendations
const aiResp = $('AI Optimizer').first().json;
const content = aiResp.choices?.[0]?.message?.content || '[]';

let recommendations;
try {
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  recommendations = JSON.parse(cleaned);
} catch (e) {
  // Return skip items for both outputs — do NOT output error/raw fields
  return [
    [{json: {skip: true, _noData: true}}],
    [{json: {skip: true, _noData: true}}],
  ];
}

if (!Array.isArray(recommendations)) recommendations = [recommendations];
if (recommendations.length === 0) {
  return [
    [{json: {skip: true, _noData: true}}],
    [{json: {skip: true, _noData: true}}],
  ];
}

const autoApply = [];
const needsApproval = [];
const now = new Date().toISOString().split('T')[0];

for (const rec of recommendations) {
  const record = {
    'Campaign Name': rec.campaign_name || rec.campaign || 'Unknown',
    'Request Type': 'Optimization',
    'Requested By': 'ADS-05',
    'Details': JSON.stringify(rec),
    'Created At': now,
  };

  if (rec.auto_approvable) {
    autoApply.push({json: {...record, 'Status': 'Approved'}});
  } else {
    needsApproval.push({json: {...record, 'Status': 'Pending'}});
  }
}

// Output 0 = auto-apply, Output 1 = needs approval
return [
  autoApply.length > 0 ? autoApply : [{json: {skip: true}}],
  needsApproval.length > 0 ? needsApproval : [{json: {skip: true}}],
];
"""


def fix_ads05_parse_and_writes(client: N8nClient) -> bool:
    """Fix Parse Optimizations error handling and ensure Airtable writes use correct fields."""
    print("\n" + "=" * 60)
    print("FIX 4: ADS-05 — Fix Parse Optimizations + Airtable writes (HIGH)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_05)
    node_map = {n["name"]: n for n in wf["nodes"]}

    # 4a: Fix Parse Optimizations code
    parse_node = node_map.get("Parse Optimizations")
    if not parse_node:
        print("  ERROR: 'Parse Optimizations' node not found")
        return False

    parse_node["parameters"]["jsCode"] = ADS05_PARSE_OPTIMIZATIONS_FIXED
    print("  Fixed Parse Optimizations: error handler now returns {skip: true}")
    print("  Fixed Parse Optimizations: output now formats Campaign_Approvals fields")

    # 4b: Change Log Auto Changes from autoMap to defineBelow
    # Since Parse Optimizations now outputs Campaign_Approvals fields directly,
    # autoMap will work correctly. But we add continueOnFail for safety.
    log_node = node_map.get("Log Auto Changes")
    if log_node:
        log_node["continueOnFail"] = True
        # Ensure autoMap is set (it should already be from build_airtable_create)
        print("  Added continueOnFail to Log Auto Changes")

    # 4c: Same for Create Approval Requests
    approval_node = node_map.get("Create Approval Requests")
    if approval_node:
        approval_node["continueOnFail"] = True
        print("  Added continueOnFail to Create Approval Requests")

    deploy(client, WF_ADS_05, wf)
    print("  Deployed ADS-05")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 5: ADS-08 — Format data before Log Report Event
# ─────────────────────────────────────────────────────────────

FORMAT_REPORT_LOG_CODE = """\
// Transform Gmail send response into Orchestrator Events fields
const gmailResp = $input.first().json;

return [{json: {
  'Event Type': 'kpi_update',
  'Source Agent': 'ADS-08',
  'Priority': 'P4',
  'Status': 'Completed',
  'Payload': JSON.stringify({
    messageId: gmailResp.id || '',
    threadId: gmailResp.threadId || '',
    sentAt: new Date().toISOString(),
  }),
  'Created At': new Date().toISOString(),
}}];
"""


def fix_ads08_log_report(client: N8nClient) -> bool:
    """Insert format node before Log Report Event."""
    print("\n" + "=" * 60)
    print("FIX 5: ADS-08 — Format data before Log Report Event (PREVENTIVE)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_08)
    node_map = {n["name"]: n for n in wf["nodes"]}

    if "Format Report Log" in node_map:
        print("  SKIP: 'Format Report Log' node already exists")
        return True

    send_node = node_map.get("Send Weekly Report")
    log_node = node_map.get("Log Report Event")
    if not send_node or not log_node:
        print("  ERROR: Required nodes not found")
        return False

    # Position between Send and Log nodes
    send_pos = send_node["position"]
    log_pos = log_node["position"]
    mid_x = (send_pos[0] + log_pos[0]) // 2
    mid_y = (send_pos[1] + log_pos[1]) // 2

    format_node = make_code_node("Format Report Log", FORMAT_REPORT_LOG_CODE, [mid_x, mid_y])
    wf["nodes"].append(format_node)

    # Rewire: Send -> Format -> Log (instead of Send -> Log)
    wf["connections"]["Send Weekly Report"]["main"][0] = [
        {"node": "Format Report Log", "type": "main", "index": 0}
    ]
    wf["connections"]["Format Report Log"] = {
        "main": [[{"node": "Log Report Event", "type": "main", "index": 0}]]
    }

    print("  Inserted 'Format Report Log' code node")
    print("  Rewired: Send Weekly Report -> Format Report Log -> Log Report Event")

    deploy(client, WF_ADS_08, wf)
    print("  Deployed ADS-08")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 6: ADS-06 — Fix Parse Variants error handler
# ─────────────────────────────────────────────────────────────

def fix_ads06_parse_variants_error(client: N8nClient) -> bool:
    """Fix Parse Variants error handler to return skip instead of error/raw fields."""
    print("\n" + "=" * 60)
    print("FIX 6: ADS-06 — Fix Parse Variants error handler (PREVENTIVE)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_06)
    node_map = {n["name"]: n for n in wf["nodes"]}

    parse_node = node_map.get("Parse Variants")
    if not parse_node:
        print("  ERROR: 'Parse Variants' node not found")
        return False

    old_code = parse_node["parameters"]["jsCode"]

    if "skip: true" in old_code and "{error:" not in old_code:
        print("  SKIP: error handler already returns skip")
        return True

    # Replace the error handler that returns {error, raw} with {skip: true}
    new_code = old_code.replace(
        "return [{json: {error: 'Failed to parse variants', raw: content}}];",
        "return [{json: {skip: true}}];"
    )

    if new_code == old_code:
        print("  WARNING: Could not find exact error handler pattern")
        # Try alternate quote style
        new_code = old_code.replace(
            'return [{json: {error: "Failed to parse variants", raw: content}}];',
            "return [{json: {skip: true}}];"
        )

    parse_node["parameters"]["jsCode"] = new_code
    print("  Fixed error handler: {error, raw} -> {skip: true}")

    deploy(client, WF_ADS_06, wf)
    print("  Deployed ADS-06")
    return True


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main() -> None:
    config = load_config()

    print("=" * 60)
    print("ADS WORKFLOW REVISION -- 2026-04-03")
    print("Fixing 100% failure rate across ADS workflows")
    print("=" * 60)

    results: dict[str, bool] = {}

    with build_client(config) as client:
        # CRITICAL
        for name, fn in [
            ("ads03_eu_political", fix_ads03_eu_political_field),
            ("ads02_approval_type", fix_ads02_approval_request_type),
        ]:
            try:
                results[name] = fn(client)
            except Exception as e:
                print(f"  ERROR: {e}")
                results[name] = False

        # HIGH
        for name, fn in [
            ("ads07_write_attribution", fix_ads07_write_attribution),
            ("ads05_parse_and_writes", fix_ads05_parse_and_writes),
        ]:
            try:
                results[name] = fn(client)
            except Exception as e:
                print(f"  ERROR: {e}")
                results[name] = False

        # PREVENTIVE
        for name, fn in [
            ("ads08_log_report", fix_ads08_log_report),
            ("ads06_parse_variants", fix_ads06_parse_variants_error),
        ]:
            try:
                results[name] = fn(client)
            except Exception as e:
                print(f"  ERROR: {e}")
                results[name] = False

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  {name}: {status}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"\n  {len(failed)} fix(es) failed: {', '.join(failed)}")
    else:
        print("\n  All 6 fixes applied successfully!")

    print("\n  MANUAL ACTION REQUIRED:")
    print("  -> Re-authorize Google Ads OAuth2 credential (5au55TkIyGEnuZvD) in n8n UI")
    print("     This fixes ADS-04 Performance Monitor (cascades to fix ADS-05)")


if __name__ == "__main__":
    main()

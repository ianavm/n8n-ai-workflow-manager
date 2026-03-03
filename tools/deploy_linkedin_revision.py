"""
LinkedIn Lead Gen Workflow Revision - Builder & Deployer

Fetches workflow iCZCgD4UDdlRVmiN from n8n, applies all fixes, and pushes back.

Fixes applied:
  Phase 0: HDW Community Node Replacement
  0.1  Replace 10 HDW community nodes with standard HTTP Request nodes
       (eliminates dependency on uninstallable n8n-nodes-hdw package)

  Phase 1: Blockers
  1.2  Google Sheets17 broken reference (Google Sheets16 -> Google Sheets21)

  Phase 2: Functional Correctness
  2.1  Company Score Analysis prompt (Hotels -> AI Automation)
  2.2  If2 lead score threshold (>= 8)
  2.3  Basic LLM Chain removal (wasteful passthrough)
  2.4  Schedule Trigger staggering (7/8/9 AM)

  Phase 3: Robustness
  3.1  5s wait node fix (set amount: 5)
  3.2  Connection request rate limiting (new Wait node)
  3.3  Error resilience on API nodes (onError: continueRegularOutput)
  3.4  Merge empty tracks (alwaysOutputData on enrichment loops)

Usage:
    python tools/deploy_linkedin_revision.py check     # Verify connectivity & workflow
    python tools/deploy_linkedin_revision.py build     # Fetch + apply fixes + save to .tmp/
    python tools/deploy_linkedin_revision.py deploy    # build + push to n8n (stays inactive)
    python tools/deploy_linkedin_revision.py activate  # deploy + activate workflow

HDW API Key:
    Add HDW_API_KEY and HDW_ACCOUNT_ID to your .env file after signing up at hdw.app.
    If not set, placeholders are used and you can update them in the n8n UI later.
"""

import json
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

# ── Configuration ──────────────────────────────────────────────

WORKFLOW_ID = "iCZCgD4UDdlRVmiN"
WORKFLOW_NAME = "Automated LinkedIn lead generation, scoring & communication with AI-Agent"

HDW_API_BASE = "https://api.horizondatawave.ai"
HDW_KEY_PLACEHOLDER = "YOUR_HDW_API_KEY"
HDW_ACCT_PLACEHOLDER = "YOUR_HDW_ACCOUNT_ID"

# Original HDW node types (for identification during replacement)
HDW_NODE_TYPES = [
    "n8n-nodes-hdw.hdwLinkedin",
    "n8n-nodes-hdw.hdwLinkedinManagement",
    "n8n-nodes-hdw.hdwWebParserTool",
]

# AI Automation scoring prompt (replaces Hotels-focused prompt)
SCORE_SYSTEM_PROMPT = (
    "You are an expert in evaluating lead potential for AI automation and "
    "digital transformation services.\n"
    "Analyze the company's and lead's profile content, assessing their "
    "likelihood of interest in AI automation services on a scale from 1 to 10 "
    "(where 1 indicates minimal potential, and 10 indicates maximum potential).\n\n"
    "Key evaluation criteria:\n"
    "  \u2022 Signs of manual/repetitive business processes that could benefit from automation\n"
    "  \u2022 Mentions of digital transformation, AI adoption, workflow optimization, or efficiency improvements\n"
    "  \u2022 Business size and operational complexity suggesting automation ROI\n"
    "  \u2022 Technology awareness or existing tech stack usage\n"
    "  \u2022 Growth indicators suggesting a need for scalable solutions\n"
    "  \u2022 Industry sectors known to benefit from AI automation "
    "(professional services, e-commerce, real estate, healthcare admin, logistics, finance)\n\n"
    "Evaluation scale:\n"
    "  \u2022 8\u201310 points: Clear indicators of automation need, active interest in "
    "technology, business processes ripe for AI, and decision-maker engagement.\n"
    "  \u2022 5\u20137 points: Some indicators of automation potential, moderate technology "
    "engagement, or indirect signals of operational pain points.\n"
    "  \u2022 1\u20134 points: No clear automation needs, very small scale, or heavily "
    "manual-labor industries with low automation fit.\n\n"
    "Your answer must ONLY be a single number from 1 to 10, without any additional text."
)

LEAD_SCORE_THRESHOLD = 8


def uid():
    return str(uuid.uuid4())


def find_node(nodes, name):
    """Find a node by name."""
    for node in nodes:
        if node.get("name") == name:
            return node
    return None


# ── Phase 0: HDW Node Replacement ─────────────────────────────

def _http_params(url, body, api_key):
    """Build n8n HTTP Request v4.2 node parameters."""
    return {
        "method": "POST",
        "url": url,
        "authentication": "none",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "access-token", "value": api_key}
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": body,
        "options": {}
    }


def _tool_http_params(url, description, body, placeholders, api_key):
    """Build n8n Tool HTTP Request v1.1 node parameters (for AI agent tools)."""
    return {
        "method": "POST",
        "url": url,
        "authentication": "none",
        "toolDescription": description,
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "access-token", "value": api_key},
            {"name": "Content-Type", "value": "application/json"}
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": body,
        "placeholderDefinitions": {"values": placeholders}
    }


def replace_hdw_with_http_nodes(nodes, api_key=None, account_id=None):
    """Phase 0: Replace all 10 HDW community nodes with standard HTTP Request nodes."""
    key = api_key or HDW_KEY_PLACEHOLDER
    acct = account_id or HDW_ACCT_PLACEHOLDER
    changes = []

    for node in nodes:
        old_type = node.get("type", "")
        if old_type not in HDW_NODE_TYPES:
            continue

        name = node.get("name", "")

        # --- LinkedIn Scraping Nodes (hdwLinkedin) ---

        if name == "HDW LinkedIn SN":
            # Sales Navigator search - receives ICP criteria from Split Out
            node["type"] = "n8n-nodes-base.httpRequest"
            node["typeVersion"] = 4.2
            node["parameters"] = _http_params(
                HDW_API_BASE + "/api/linkedin/sn_search/users",
                '={{ JSON.stringify({'
                'keyword: $json.keywords || "", '
                'current_titles: String($json.current_titles || "").split(",").map(s => s.trim()).filter(Boolean), '
                'current_companies: String($json.current_companies || "").split(",").map(s => s.trim()).filter(Boolean), '
                'location: String($json.location || "").split(",").map(s => s.trim()).filter(Boolean), '
                'industry: String($json.industry || "").split(",").map(s => s.trim()).filter(Boolean), '
                'company_sizes: String($json.company_sizes || "").split(",").map(s => s.trim()).filter(Boolean), '
                'limit: parseInt($json.count) || 25'
                '}) }}',
                key
            )

        elif name == "HDW Get Company Website":
            # Get company info from LinkedIn - receives leads with empty Website field
            node["type"] = "n8n-nodes-base.httpRequest"
            node["typeVersion"] = 4.2
            node["parameters"] = _http_params(
                HDW_API_BASE + "/api/linkedin/company",
                '={{ JSON.stringify({'
                'url: "https://www.linkedin.com/company/" + '
                'String($json["Company URN"] || "").split(":").pop()'
                '}) }}',
                key
            )

        elif name == "HDW Get User Posts":
            # Get LinkedIn user posts - receives leads from Loop Over Items2
            node["type"] = "n8n-nodes-base.httpRequest"
            node["typeVersion"] = 4.2
            node["parameters"] = _http_params(
                HDW_API_BASE + "/api/linkedin/user/posts",
                '={{ JSON.stringify({url: $json.URL}) }}',
                key
            )

        elif name == "HDW Get Company News":
            # Google search for company news - receives leads from Loop Over Items3
            node["type"] = "n8n-nodes-base.httpRequest"
            node["typeVersion"] = 4.2
            node["parameters"] = _http_params(
                HDW_API_BASE + "/api/google/search",
                '={{ JSON.stringify({query: ($json["Current company"] || $json.Name || "") + " company news"}) }}',
                key
            )

        elif name == "HDW Get Company Posts":
            # Get LinkedIn company posts - receives leads from Loop Over Items4
            node["type"] = "n8n-nodes-base.httpRequest"
            node["typeVersion"] = 4.2
            node["parameters"] = _http_params(
                HDW_API_BASE + "/api/linkedin/company/posts",
                '={{ JSON.stringify({'
                'url: "https://www.linkedin.com/company/" + '
                'String($json["Company URN"] || "").split(":").pop()'
                '}) }}',
                key
            )

        # --- AI Tool Nodes (hdwWebParserTool) ---

        elif name == "HDW Site-map":
            # Website sitemap tool - used by "Summarise company website" AI agent
            node["type"] = "@n8n/n8n-nodes-langchain.toolHttpRequest"
            node["typeVersion"] = 1.1
            node["parameters"] = _tool_http_params(
                HDW_API_BASE + "/api/website/map",
                "Get the sitemap/structure of a website to discover all available pages and links.",
                '{"url": "{url}"}',
                [{"name": "url", "description": "The full website URL (e.g. https://example.com)"}],
                key
            )

        elif name == "HDW Parser":
            # Website content scraper - used by "Summarise company website" AI agent
            node["type"] = "@n8n/n8n-nodes-langchain.toolHttpRequest"
            node["typeVersion"] = 1.1
            node["parameters"] = _tool_http_params(
                HDW_API_BASE + "/api/website/scrape",
                "Scrape and extract the text content of a specific web page.",
                '{"url": "{url}"}',
                [{"name": "url", "description": "The web page URL to scrape content from"}],
                key
            )

        # --- Management Nodes (hdwLinkedinManagement) ---

        elif name == "HDW Send LinkedIn Connection":
            # Send connection request - receives leads from Loop Over Items7
            node["type"] = "n8n-nodes-base.httpRequest"
            node["typeVersion"] = 4.2
            node["parameters"] = _http_params(
                HDW_API_BASE + "/api/linkedin/management/user/connection",
                '={{ JSON.stringify({url: $json.URL, message: "", account_id: "' + acct + '"}) }}',
                key
            )

        elif name == "HDW Get LinkedIn Profile Connections":
            # Get accepted connections - triggered by Schedule Trigger1
            node["type"] = "n8n-nodes-base.httpRequest"
            node["typeVersion"] = 4.2
            node["parameters"] = _http_params(
                HDW_API_BASE + "/api/linkedin/management/user/connections",
                '{"account_id": "' + acct + '"}',
                key
            )

        elif name == "HDW LinkedIn Send Message":
            # Send message to connected lead - receives data from 5s wait
            node["type"] = "n8n-nodes-base.httpRequest"
            node["typeVersion"] = 4.2
            node["parameters"] = _http_params(
                HDW_API_BASE + "/api/linkedin/management/chat/message",
                '={{ JSON.stringify({'
                'url: $json.URL || $json.url, '
                'message: $json.Message || $json.message || $json.text || "", '
                'account_id: "' + acct + '"'
                '}) }}',
                key
            )

        else:
            changes.append(f"WARNING: Unknown HDW node '{name}' ({old_type}) - skipped")
            continue

        # Common post-replacement settings
        node["credentials"] = {}
        node["onError"] = "continueRegularOutput"
        changes.append(f"Replaced '{name}' ({old_type}) -> {node['type']}")

    return changes


# ── Phase 1: Blockers ──────────────────────────────────────────

def fix_sheets17_reference(nodes):
    """Fix 1.2: Fix Google Sheets17 URN reference from Google Sheets16 -> Google Sheets21."""
    changes = []
    node = find_node(nodes, "Google Sheets17")
    if node:
        columns = node.get("parameters", {}).get("columns", {}).get("value", {})
        old_urn = columns.get("URN", "")
        if "Google Sheets16" in old_urn:
            columns["URN"] = "={{ $('Google Sheets21').item.json.URN }}"
            changes.append("Fixed Google Sheets17 URN: Google Sheets16 -> Google Sheets21")
        else:
            changes.append(f"Google Sheets17 URN already OK")
    else:
        changes.append("WARNING: Google Sheets17 node not found")
    return changes


# ── Phase 2: Functional Correctness ───────────────────────────

def fix_score_analysis_prompt(nodes):
    """Fix 2.1: Replace Hotels-focused scoring prompt with AI Automation prompt."""
    changes = []
    node = find_node(nodes, "Company Score Analysis")
    if node:
        messages = node.get("parameters", {}).get("messages", {})
        values = messages.get("values", [])
        if values:
            for val in values:
                if val.get("role") == "system":
                    val["content"] = SCORE_SYSTEM_PROMPT
                    changes.append("Replaced Company Score Analysis prompt: Hotels -> AI Automation")
                    break
            else:
                values[0]["content"] = SCORE_SYSTEM_PROMPT
                changes.append("Replaced Company Score Analysis prompt (no system role found)")
        else:
            changes.append("WARNING: Company Score Analysis has no message values")
    else:
        changes.append("WARNING: Company Score Analysis node not found")
    return changes


def fix_if2_threshold(nodes):
    """Fix 2.2: Add Lead Score >= 8 threshold to If2 conditions."""
    changes = []
    node = find_node(nodes, "If2")
    if node:
        params = node.get("parameters", {})
        conditions = params.get("conditions", {})
        existing_conditions = conditions.get("conditions", [])

        has_score = any("Lead Score" in str(c.get("leftValue", "")) for c in existing_conditions)
        if not has_score:
            existing_conditions.append({
                "id": uid(),
                "operator": {"type": "number", "operation": "gte"},
                "leftValue": "={{ $json[\"Lead Score\"] }}",
                "rightValue": str(LEAD_SCORE_THRESHOLD)
            })
            conditions["combinator"] = "and"
            changes.append(f"Added Lead Score >= {LEAD_SCORE_THRESHOLD} condition to If2")
        else:
            changes.append("If2 already has Lead Score condition")
    else:
        changes.append("WARNING: If2 node not found")
    return changes


def disable_basic_llm_chain(nodes, connections):
    """Fix 2.3: Disable Basic LLM Chain and clean up connections."""
    changes = []
    node = find_node(nodes, "Basic LLM Chain")
    if node:
        node["disabled"] = True
        changes.append("Disabled Basic LLM Chain node")
    else:
        changes.append("Basic LLM Chain not found (already removed?)")
        return changes

    # Remove connection from If false branch -> Basic LLM Chain
    if_conns = connections.get("If", {})
    main_conns = if_conns.get("main", [])
    if len(main_conns) > 1:
        false_branch = main_conns[1]
        original_count = len(false_branch)
        main_conns[1] = [c for c in false_branch if c.get("node") != "Basic LLM Chain"]
        removed = original_count - len(main_conns[1])
        if removed:
            changes.append(f"Removed {removed} connection(s) from If false -> Basic LLM Chain")

    # Remove OpenAI Chat Model2 -> Basic LLM Chain connection
    model2_conns = connections.get("OpenAI Chat Model2", {})
    for conn_type, targets_list in model2_conns.items():
        for i, targets in enumerate(targets_list):
            original_count = len(targets)
            targets_list[i] = [c for c in targets if c.get("node") != "Basic LLM Chain"]
            removed = original_count - len(targets_list[i])
            if removed:
                changes.append(f"Removed OpenAI Chat Model2 -> Basic LLM Chain ({conn_type})")

    return changes


def stagger_schedule_triggers(nodes):
    """Fix 2.4: Stagger Schedule Triggers to 7/8/9 AM."""
    changes = []
    for name, hour, label in [
        ("Schedule Trigger1", 7, "check connections"),
        ("Schedule Trigger", 8, "connection requests"),
        ("Schedule Trigger3", 9, "send messages"),
    ]:
        node = find_node(nodes, name)
        if node:
            rule = node.get("parameters", {}).get("rule", {})
            intervals = rule.get("interval", [{}])
            intervals[0]["triggerAtHour"] = hour
            changes.append(f"{name} ({label}): set to {hour} AM")
    return changes


# ── Phase 3: Robustness ───────────────────────────────────────

def fix_wait_5s(nodes):
    """Fix 3.1: Set 5s wait node to actually wait 5 seconds."""
    changes = []
    node = find_node(nodes, "5s")
    if node:
        params = node.get("parameters", {})
        if not params.get("amount"):
            params["amount"] = 5
            node["parameters"] = params
            changes.append("Fixed 5s wait node: set amount=5")
        else:
            changes.append(f"5s wait node already has amount={params['amount']}")
    else:
        changes.append("WARNING: 5s wait node not found")
    return changes


def add_connection_rate_limit(nodes, connections):
    """Fix 3.2: Add Wait node between Google Sheets14 and Loop Over Items7."""
    changes = []
    gs14 = find_node(nodes, "Google Sheets14")
    loop7 = find_node(nodes, "Loop Over Items7")

    if not gs14 or not loop7:
        changes.append("WARNING: Could not find Google Sheets14 or Loop Over Items7")
        return changes

    if find_node(nodes, "Wait Between Connections"):
        changes.append("Wait Between Connections already exists")
        return changes

    gs14_pos = gs14.get("position", [0, 0])
    loop7_pos = loop7.get("position", [0, 0])
    new_pos = [(gs14_pos[0] + loop7_pos[0]) // 2, gs14_pos[1] + 100]

    wait_node = {
        "parameters": {"amount": 5},
        "id": uid(),
        "name": "Wait Between Connections",
        "type": "n8n-nodes-base.wait",
        "position": new_pos,
        "typeVersion": 1.1,
        "webhookId": uid()
    }
    nodes.append(wait_node)
    changes.append("Added 'Wait Between Connections' node (5s delay)")

    # Rewire: Google Sheets14 -> Wait -> Loop Over Items7
    gs14_conns = connections.get("Google Sheets14", {})
    main_conns = gs14_conns.get("main", [[]])
    for i, targets in enumerate(main_conns):
        new_targets = []
        for t in targets:
            if t.get("node") == "Loop Over Items7":
                new_targets.append({"node": "Wait Between Connections", "type": "main", "index": 0})
                changes.append("Rewired: Google Sheets14 -> Wait Between Connections")
            else:
                new_targets.append(t)
        main_conns[i] = new_targets

    connections["Wait Between Connections"] = {
        "main": [[{"node": "Loop Over Items7", "type": "main", "index": 0}]]
    }
    changes.append("Added connection: Wait Between Connections -> Loop Over Items7")
    return changes


def add_error_resilience(nodes):
    """Fix 3.3: Add onError: continueRegularOutput to API-calling nodes."""
    api_node_names = [
        "HDW LinkedIn SN", "HDW Get Company Website", "HDW Get User Posts",
        "HDW Get Company News", "HDW Get Company Posts",
        "HDW Send LinkedIn Connection", "HDW Get LinkedIn Profile Connections",
        "HDW LinkedIn Send Message"
    ]
    changes = []
    for node in nodes:
        if node["name"] in api_node_names:
            if node.get("onError") != "continueRegularOutput":
                node["onError"] = "continueRegularOutput"
                changes.append(f"Added error resilience to: {node['name']}")
    return changes


def fix_merge_empty_tracks(nodes):
    """Fix 3.4: Set alwaysOutputData on enrichment loops so Merge fires."""
    changes = []
    for name in ["Loop Over Items1", "Loop Over Items2", "Loop Over Items3", "Loop Over Items4"]:
        node = find_node(nodes, name)
        if node:
            if not node.get("alwaysOutputData"):
                node["alwaysOutputData"] = True
                changes.append(f"Set alwaysOutputData=true on {name}")
        else:
            changes.append(f"WARNING: {name} not found")
    return changes


# ── Verification ───────────────────────────────────────────────

def verify_all_fixes(nodes, connections):
    """Run post-fix verification checks. Returns (passed, failed) lists."""
    passed = []
    failed = []

    # 1. No HDW-typed nodes remain
    hdw_remaining = [n["name"] for n in nodes if n.get("type", "") in HDW_NODE_TYPES]
    if hdw_remaining:
        failed.append(f"HDW nodes still present: {hdw_remaining}")
    else:
        passed.append("All HDW nodes replaced with HTTP Request")

    # 2. Replacement nodes have HDW API URLs
    hdw_names = [
        "HDW LinkedIn SN", "HDW Get Company Website", "HDW Get User Posts",
        "HDW Get Company News", "HDW Get Company Posts", "HDW Site-map", "HDW Parser",
        "HDW Send LinkedIn Connection", "HDW Get LinkedIn Profile Connections",
        "HDW LinkedIn Send Message"
    ]
    for name in hdw_names:
        node = find_node(nodes, name)
        if node:
            url = node.get("parameters", {}).get("url", "")
            if "horizondatawave" in url:
                passed.append(f"'{name}' has correct HDW API URL")
            else:
                failed.append(f"'{name}' missing HDW API URL: {url[:60]}")
        else:
            failed.append(f"'{name}' node not found")

    # 3. Google Sheets17 references Google Sheets21
    gs17 = find_node(nodes, "Google Sheets17")
    if gs17:
        urn = gs17.get("parameters", {}).get("columns", {}).get("value", {}).get("URN", "")
        if "Google Sheets21" in urn:
            passed.append("Google Sheets17 URN references Google Sheets21")
        else:
            failed.append(f"Google Sheets17 URN still broken: {urn[:80]}")

    # 4. Score prompt contains "AI automation"
    score_node = find_node(nodes, "Company Score Analysis")
    if score_node:
        messages = score_node.get("parameters", {}).get("messages", {}).get("values", [])
        prompt_text = " ".join(v.get("content", "") for v in messages)
        if "AI automation" in prompt_text or "ai automation" in prompt_text.lower():
            passed.append("Score prompt mentions AI automation")
        else:
            failed.append("Score prompt does NOT mention AI automation")
        if "hotel" in prompt_text.lower():
            failed.append("Score prompt still mentions Hotels")
        else:
            passed.append("Score prompt does not mention Hotels")

    # 5. If2 has lead score condition
    if2 = find_node(nodes, "If2")
    if if2:
        conditions = if2.get("parameters", {}).get("conditions", {})
        cond_list = conditions.get("conditions", [])
        has_score = any("Lead Score" in str(c.get("leftValue", "")) for c in cond_list)
        combinator = conditions.get("combinator", "")
        if has_score and combinator == "and":
            passed.append("If2 has Lead Score condition with AND combinator")
        else:
            failed.append(f"If2 missing Lead Score condition")

    # 6. Basic LLM Chain is disabled
    blc = find_node(nodes, "Basic LLM Chain")
    if blc and blc.get("disabled"):
        passed.append("Basic LLM Chain is disabled")
    elif blc:
        failed.append("Basic LLM Chain is NOT disabled")

    # 7. Schedule Triggers have different hours
    hours = set()
    for name in ["Schedule Trigger", "Schedule Trigger1", "Schedule Trigger3"]:
        node = find_node(nodes, name)
        if node:
            h = node.get("parameters", {}).get("rule", {}).get("interval", [{}])[0].get("triggerAtHour", -1)
            hours.add(h)
    if len(hours) == 3:
        passed.append(f"Schedule Triggers have unique hours: {sorted(hours)}")
    else:
        failed.append(f"Schedule Triggers NOT unique: {hours}")

    # 8. 5s wait has amount
    wait5 = find_node(nodes, "5s")
    if wait5:
        amt = wait5.get("parameters", {}).get("amount")
        if amt == 5:
            passed.append("5s wait node has amount=5")
        else:
            failed.append(f"5s wait node amount={amt} (expected 5)")

    # 9. Wait Between Connections exists
    if find_node(nodes, "Wait Between Connections"):
        passed.append("Wait Between Connections node exists")
    else:
        failed.append("Wait Between Connections node NOT found")

    # 10. API nodes have error resilience
    api_names = [
        "HDW LinkedIn SN", "HDW Get Company Website", "HDW Get User Posts",
        "HDW Get Company News", "HDW Get Company Posts",
        "HDW Send LinkedIn Connection", "HDW Get LinkedIn Profile Connections",
        "HDW LinkedIn Send Message"
    ]
    resilient_count = 0
    for name in api_names:
        node = find_node(nodes, name)
        if node and node.get("onError") == "continueRegularOutput":
            resilient_count += 1
    if resilient_count == len(api_names):
        passed.append(f"All {resilient_count} API nodes have error resilience")
    else:
        failed.append(f"Only {resilient_count}/{len(api_names)} API nodes have error resilience")

    return passed, failed


# ── Main ───────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1].lower()
    if action not in ("check", "build", "deploy", "activate"):
        print(f"Unknown action: {action}")
        print("Valid actions: check, build, deploy, activate")
        sys.exit(1)

    # Load configuration
    from config_loader import load_config
    from n8n_client import N8nClient

    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = config["n8n"]["base_url"]
    timeout = config["n8n"].get("timeout_seconds", 30)
    max_retries = config["n8n"].get("max_retries", 3)
    tmp_dir = Path(config["paths"]["tmp_dir"])
    tmp_dir.mkdir(parents=True, exist_ok=True)

    if not api_key:
        print("ERROR: N8N_API_KEY not found. Add it to .env file.")
        sys.exit(1)

    # Load HDW credentials from .env (optional)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    hdw_api_key = os.getenv("HDW_API_KEY")
    hdw_account_id = os.getenv("HDW_ACCOUNT_ID")

    print("=" * 60)
    print("LINKEDIN LEAD GEN WORKFLOW REVISION")
    print(f"Workflow: {WORKFLOW_NAME}")
    print(f"ID: {WORKFLOW_ID}")
    print(f"Instance: {base_url}")
    print(f"Action: {action}")
    print(f"HDW API Key: {'SET' if hdw_api_key else 'NOT SET (will use placeholder)'}")
    print(f"HDW Account ID: {'SET' if hdw_account_id else 'NOT SET (will use placeholder)'}")
    print("=" * 60)

    with N8nClient(base_url, api_key, timeout=timeout,
                   max_retries=max_retries,
                   cache_dir=str(tmp_dir / "cache")) as client:

        # ── CHECK ──
        if action == "check":
            print("\n--- Pre-flight Checks ---")

            health = client.health_check()
            if health["connected"]:
                print(f"  [OK] Connected to {health['base_url']}")
            else:
                print(f"  [FAIL] Cannot connect: {health.get('error')}")
                sys.exit(1)

            try:
                wf = client.get_workflow(WORKFLOW_ID)
                node_count = len(wf.get("nodes", []))
                active = wf.get("active", False)
                print(f"  [OK] Workflow found: {wf.get('name')} ({node_count} nodes, {'ACTIVE' if active else 'INACTIVE'})")
            except Exception as e:
                print(f"  [FAIL] Workflow {WORKFLOW_ID} not found: {e}")
                sys.exit(1)

            # Check HDW node status
            hdw_count = sum(1 for n in wf["nodes"] if n.get("type", "") in HDW_NODE_TYPES)
            http_count = sum(1 for n in wf["nodes"]
                          if n.get("name", "").startswith("HDW ")
                          and "httpRequest" in n.get("type", ""))
            if hdw_count > 0:
                print(f"  [INFO] {hdw_count} HDW community nodes found (will be replaced on build)")
            elif http_count > 0:
                print(f"  [OK] {http_count} HDW nodes already replaced with HTTP Request")

            if not hdw_api_key:
                print("\n  [INFO] HDW_API_KEY not set in .env")
                print("  To set up:")
                print("    1. Sign up at https://hdw.app (redirects to anysite.io)")
                print("    2. Get your API key and account ID")
                print("    3. Add to .env:")
                print("       HDW_API_KEY=your_key_here")
                print("       HDW_ACCOUNT_ID=your_account_id_here")
                print("    4. Re-run this script")
                print("\n  NOTE: You can build/deploy without HDW keys.")
                print("        Placeholders will be used; update them in n8n UI later.")

            print("\n  Pre-flight checks complete!")
            return

        # ── BUILD / DEPLOY / ACTIVATE ──

        # Step 1: Fetch current workflow
        print("\n--- Fetching workflow from n8n ---")
        wf = client.get_workflow(WORKFLOW_ID)
        node_count = len(wf.get("nodes", []))
        print(f"  Fetched: {wf.get('name')} ({node_count} nodes)")

        # Step 2: Backup original
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = tmp_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"linkedin_backup_{timestamp}.json"
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"  Backup saved: {backup_path}")

        # Step 3: Apply all fixes
        print("\n--- Applying Fixes ---")
        nodes = wf["nodes"]
        connections = wf["connections"]
        all_changes = []

        print("\n  Phase 0: HDW Node Replacement")
        all_changes += replace_hdw_with_http_nodes(nodes, hdw_api_key, hdw_account_id)

        print("  Phase 1: Blockers")
        all_changes += fix_sheets17_reference(nodes)

        print("  Phase 2: Functional Correctness")
        all_changes += fix_score_analysis_prompt(nodes)
        all_changes += fix_if2_threshold(nodes)
        all_changes += disable_basic_llm_chain(nodes, connections)
        all_changes += stagger_schedule_triggers(nodes)

        print("  Phase 3: Robustness")
        all_changes += fix_wait_5s(nodes)
        all_changes += add_connection_rate_limit(nodes, connections)
        all_changes += add_error_resilience(nodes)
        all_changes += fix_merge_empty_tracks(nodes)

        print()
        for change in all_changes:
            prefix = "  [WARN]" if "WARNING" in change else "  [FIX] "
            print(f"{prefix} {change}")
        print(f"\n  Total changes: {len(all_changes)}")

        # Step 4: Verify
        print("\n--- Verification ---")
        passed, failed = verify_all_fixes(nodes, connections)
        for p in passed:
            print(f"  [PASS] {p}")
        for f_msg in failed:
            print(f"  [FAIL] {f_msg}")

        if failed:
            print(f"\n  {len(failed)} verification(s) FAILED.")
            if action in ("deploy", "activate"):
                print("  Aborting deployment due to verification failures.")
                sys.exit(1)

        # Step 5: Save revised JSON
        revised_path = tmp_dir / "linkedin_revised.json"
        with open(revised_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"\n  Revised workflow saved: {revised_path}")
        print(f"  Node count: {len(nodes)} (was {node_count})")

        if action == "build":
            print("\n  Build complete. Review the JSON then run 'deploy'.")
            return

        # Step 6: Deploy to n8n
        print("\n--- Deploying to n8n ---")
        update_payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        result = client.update_workflow(WORKFLOW_ID, update_payload)
        print(f"  Deployed successfully!")
        print(f"  Updated: {result.get('updatedAt', 'unknown')}")

        if action == "deploy":
            print("\n  Workflow deployed (INACTIVE). Run 'activate' when ready.")
            return

        # Step 7: Activate
        print("\n--- Activating workflow ---")
        try:
            client.activate_workflow(WORKFLOW_ID)
            print("  Workflow is now ACTIVE!")
            wf_status = "ACTIVE"
        except Exception as e:
            resp_body = ""
            if hasattr(e, "response") and e.response is not None:
                try:
                    resp_body = e.response.text
                except Exception:
                    pass
            print(f"  Activation failed: {resp_body or str(e)}")
            wf_status = "INACTIVE"

        print("\n" + "=" * 60)
        print("DEPLOYMENT COMPLETE")
        print("=" * 60)
        print(f"  Workflow: {WORKFLOW_NAME}")
        print(f"  Status: {wf_status}")
        print(f"  Fixes Applied: {len(all_changes)}")
        print(f"  Verification: {len(passed)} passed, {len(failed)} failed")
        if not hdw_api_key:
            print(f"\n  IMPORTANT: HDW API key not configured.")
            print(f"  Add HDW_API_KEY and HDW_ACCOUNT_ID to .env, then re-run,")
            print(f"  or update the placeholder values directly in the n8n UI.")
        print(f"\n  Next steps:")
        print(f"    1. Sign up at https://hdw.app and get API key + account ID")
        print(f"    2. Add to .env: HDW_API_KEY=... and HDW_ACCOUNT_ID=...")
        print(f"    3. Re-run: python tools/deploy_linkedin_revision.py activate")
        print(f"    4. Test the ICP Chat Trigger in the n8n UI")


if __name__ == "__main__":
    main()

"""Convert ALL Airtable nodes in AVM standalone workflows to mock Code nodes.

continueOnFail doesn't catch "Could not get parameter" errors because those happen
during parameter resolution before the node executes. The only fix is to replace
Airtable nodes with Code nodes that return mock data.
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from n8n_client import N8nClient

AVM_WORKFLOWS = {
    "5XR7j7hQ8cdWpi1e": "ORCH-01 Health Monitor",
    "47CJmRKTh9kPZ7u5": "ORCH-02 Cross-Dept Router",
    "JDrgcv5iNIXLyQfs": "ORCH-03 Daily KPI Aggregation",
    "2gXlFqBtOoReQfaT": "ORCH-04 Weekly Report Generator",
    "Ns8pI1OowMbNDfUV": "MKT-05 Campaign ROI Tracker",
    "UKIxkygJgJQ245pM": "MKT-06 Budget Optimizer",
    "3Gb4pWJhsf2aHhsW": "FIN-08 Cash Flow Forecast",
    "6bo7BSssN6SQeodg": "FIN-09 Anomaly Detector",
    "330wVSlaVBtoKwV1": "CONTENT-01 Performance Feedback Loop",
    "dSAt6zYsfLy1e6tH": "CONTENT-02 Multi-Format Generator",
    "5Qzbyar2VTIbAuEo": "CR-01 Health Scorer (new)",
    "nbNcnixOO7njPA7w": "CR-01 Health Scorer (old)",
    "3ZzWEUmgVNIxNmx3": "CR-02 Renewal Manager",
    "e1ufCH2KvuvrBQPm": "CR-03 Onboarding Automation",
    "fOygygjEdwAyf5of": "CR-04 Satisfaction Pulse",
    "Pk0B97gW8xtcgHBf": "SUP-01 Ticket Creator (new)",
    "nOTNEIxTRJKYskCq": "SUP-01 Ticket Creator (old)",
    "EnnsJg43EazmEHJl": "SUP-02 SLA Monitor",
    "HnmuFSsdx7hasPcI": "SUP-03 Auto-Resolver",
    "3CQqDNDtgLJi2ZUu": "SUP-04 KB Builder",
    "YBxMfFdFb7BCUxzi": "WA-01 Conversation Analyzer",
    "twe45qwa4Kwalzdx": "WA-02 CRM Sync",
    "6C9PPWe4IWoUhjq2": "WA-03 Issue Detector (new)",
    "xFnBYVNwObY9bR7k": "WA-03 Issue Detector (old)",
    "P9NgW8csqbCh817f": "INTEL-01 Cross-Dept Correlator",
    "Fmut5pJ4fVXIfxke": "INTEL-02 Executive Report",
    "hSiIZJu5bgDIOCDO": "INTEL-03 Prompt Performance (new)",
    "rbHj5pTI10wNtBHp": "INTEL-03 Prompt Performance (old)",
    "Rsyz1BHai3q94wPI": "OPT-01 A/B Test Manager",
    "jOUhPTYMBCf5z4PW": "OPT-02 A/B Test Analyzer (old)",
    "I37U9l1kOcsr8fpP": "OPT-02 A/B Test Analyzer (new)",
    "TPp402GuDxnruRd2": "OPT-03 Churn Predictor (new)",
    "yYTjNyTIvgaD7Qwa": "OPT-03 Churn Predictor (old)",
}


def classify_node(name):
    lower = name.lower()
    if any(k in lower for k in ['read ', 'fetch ', 'search ', 'get ']):
        return "read"
    if any(k in lower for k in ['write ', 'create ', 'log ', 'save ', 'update ', 'escalate ']):
        return "write"
    return "read"  # default to read (returns array)


MOCK_TEMPLATES = {
    "read": """// Mock: {name} (Airtable table not yet provisioned)
// TODO: Reconnect to Airtable once tables are created via setup scripts
const items = $input.all();
return items.length > 0 ? items : [{{ json: {{ id: 'rec_mock', _mock: true, _source: '{name}' }} }}];""",

    "write": """// Mock: {name} (Airtable table not yet provisioned)
// TODO: Reconnect to Airtable once tables are created via setup scripts
const data = $input.first().json;
return {{ json: {{ id: 'rec_mock', ...data, _mock: true, _source: '{name}' }} }};""",
}


def convert_airtable_to_code(node):
    """Convert an Airtable node to a mock Code node."""
    category = classify_node(node["name"])
    mock_code = MOCK_TEMPLATES[category].format(name=node["name"])

    node["type"] = "n8n-nodes-base.code"
    node["typeVersion"] = 2
    node["parameters"] = {"jsCode": mock_code}

    # Remove Airtable-specific properties
    if "credentials" in node:
        creds = node["credentials"]
        if "airtableTokenApi" in creds or "airtableOAuth2Api" in creds:
            del node["credentials"]

    # Remove continueOnFail (Code nodes don't need it for mock data)
    node.pop("onError", None)
    node.pop("continueOnFail", None)
    node.pop("alwaysOutputData", None)


def main():
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        sys.exit(1)
    client = N8nClient(base_url=base_url, api_key=api_key)

    total_converted = 0
    workflows_modified = 0

    for wf_id, wf_label in AVM_WORKFLOWS.items():
        try:
            wf = client.get_workflow(wf_id)
        except Exception as e:
            print(f"SKIP {wf_label}: {e}")
            continue

        nodes = wf["nodes"]
        converted = 0

        for node in nodes:
            if node.get("type") == "n8n-nodes-base.airtable":
                convert_airtable_to_code(node)
                converted += 1

        if converted > 0:
            try:
                result = client.update_workflow(wf_id, {
                    "name": wf["name"],
                    "nodes": nodes,
                    "connections": wf["connections"],
                    "settings": wf.get("settings", {}),
                    "staticData": wf.get("staticData"),
                })
                print(f"  {wf_label}: converted {converted} Airtable nodes -> Code")
                total_converted += converted
                workflows_modified += 1
            except Exception as e:
                print(f"  ERROR {wf_label}: {e}")
        else:
            print(f"  {wf_label}: no Airtable nodes")

    print(f"\nDONE: {total_converted} Airtable nodes converted across {workflows_modified} workflows")


if __name__ == "__main__":
    main()

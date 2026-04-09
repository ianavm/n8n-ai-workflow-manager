"""
AVM Brain Writer — Sub-workflow for Postgres Brain Event Logging

A reusable sub-workflow that any n8n workflow can call via Execute Workflow
to write events to the brain_events and brain_state tables in Supabase.

Input parameters (via Execute Workflow):
    source:      str  — 'n8n:ADS-SHM', 'n8n:LI-01', etc.
    source_type: str  — 'workflow' | 'agent' | 'claude' | 'portal' | 'cron'
    event_type:  str  — 'execution_success' | 'execution_failure' | 'decision_made' |
                         'fix_applied' | 'client_action' | 'alert' | 'milestone' | 'deploy'
    severity:    str  — 'info' | 'warning' | 'error' | 'critical'
    department:  str  — 'accounting' | 'marketing' | 'ads' | 'linkedin' | 'fa' | 'seo' | 're' | 'infra'
    summary:     str  — Human-readable summary
    details:     str  — JSON string of structured payload (optional)
    entity_id:   str  — n8n workflow ID for brain_state upsert (optional)
    entity_name: str  — Display name for brain_state (optional)

Usage:
    python tools/deploy_brain_writer.py build      # Build JSON
    python tools/deploy_brain_writer.py deploy      # Build + Deploy (inactive)
    python tools/deploy_brain_writer.py activate    # Build + Deploy + Activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# ── Supabase Config ────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://qfvsqjsrlnxjplqefhon.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# ── n8n Config ─────────────────────────────────────────────────
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")

WORKFLOW_NAME = "AVM: Brain Writer"


def uid() -> str:
    return str(uuid.uuid4())


# ======================================================================
# CODE NODE SCRIPTS
# ======================================================================

SCRIPT_FORMAT_EVENT = """
// Format incoming data for Supabase brain_events insert
const input = $input.first().json;

// Safe JSON parse for details field
let parsedDetails = {};
if (input.details) {
  if (typeof input.details === 'string') {
    try { parsedDetails = JSON.parse(input.details); }
    catch (e) { parsedDetails = { raw: input.details, parseError: e.message }; }
  } else {
    parsedDetails = input.details;
  }
}

const event = {
  source: input.source || 'unknown',
  source_type: input.source_type || 'workflow',
  event_type: input.event_type || 'execution_success',
  severity: input.severity || 'info',
  department: input.department || null,
  summary: input.summary || 'No summary provided',
  details: parsedDetails,
  resolved: false
};

// Build brain_state upsert if entity_id provided
let stateUpsert = null;
if (input.entity_id) {
  const isFailure = ['execution_failure', 'alert'].includes(event.event_type);
  const isCritical = ['error', 'critical'].includes(event.severity);

  stateUpsert = {
    entity_type: 'workflow',
    entity_id: input.entity_id,
    entity_name: input.entity_name || input.source,
    status: isCritical ? 'failing' : (isFailure ? 'degraded' : 'healthy'),
    last_seen: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    notes: event.summary
  };

  if (isFailure) {
    stateUpsert.last_failure = new Date().toISOString();
  } else {
    stateUpsert.last_success = new Date().toISOString();
    stateUpsert.failure_count = 0;
  }
}

return [{ json: { event, stateUpsert, hasStateUpsert: !!stateUpsert } }];
"""

SCRIPT_INCREMENT_FAILURES = """
// For failures, increment failure_count via RPC or raw SQL
// Supabase REST API doesn't support atomic increment, so we use a simple approach:
// Set failure_count in the upsert body (the trigger/view handles incrementing)
const input = $input.first().json;
if (input.stateUpsert && input.stateUpsert.status !== 'healthy') {
  // We'll handle this via the on_conflict resolution
  input.stateUpsert.failure_count = 1;  // Will be overridden by Supabase function if exists
}
return [{ json: input }];
"""


# ======================================================================
# NODE BUILDERS
# ======================================================================

def build_nodes() -> list:
    nodes = []

    # 1. Execute Workflow Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Execute Workflow Trigger",
        "type": "n8n-nodes-base.executeWorkflowTrigger",
        "position": [200, 400],
        "typeVersion": 1,
    })

    # 2. Format Event Data
    nodes.append({
        "parameters": {"jsCode": SCRIPT_FORMAT_EVENT},
        "id": uid(),
        "name": "Format Event",
        "type": "n8n-nodes-base.code",
        "position": [420, 400],
        "typeVersion": 2,
    })

    # 3. Insert brain_events (Supabase REST API)
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": f"{SUPABASE_URL}/rest/v1/brain_events",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": SUPABASE_ANON_KEY},
                    {"name": "Prefer", "value": "return=minimal"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json.event) }}",
            "options": {"timeout": 10000},
        },
        "id": uid(),
        "name": "Insert brain_events",
        "type": "n8n-nodes-base.httpRequest",
        "position": [640, 300],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "credentials": {
            "httpHeaderAuth": {
                "id": "mlYOg9wSp9IFlm4k",
                "name": "Supabase Service Role"
            }
        },
    })

    # 4. Check if state upsert needed
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [{
                    "leftValue": "={{ $('Format Event').first().json.hasStateUpsert }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "true"},
                }],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Has State Update?",
        "type": "n8n-nodes-base.if",
        "position": [640, 500],
        "typeVersion": 2.2,
    })

    # 5. Upsert brain_state (Supabase REST API with ON CONFLICT)
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": f"{SUPABASE_URL}/rest/v1/brain_state?on_conflict=entity_type,entity_id",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": SUPABASE_ANON_KEY},
                    {"name": "Prefer", "value": "resolution=merge-duplicates,return=minimal"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($('Format Event').first().json.stateUpsert) }}",
            "options": {"timeout": 10000},
        },
        "id": uid(),
        "name": "Upsert brain_state",
        "type": "n8n-nodes-base.httpRequest",
        "position": [880, 440],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "credentials": {
            "httpHeaderAuth": {
                "id": "mlYOg9wSp9IFlm4k",
                "name": "Supabase Service Role"
            }
        },
    })

    return nodes


def build_connections(nodes: list) -> dict:
    node_map = {n["name"]: n for n in nodes}

    return {
        "Execute Workflow Trigger": {
            "main": [[{"node": "Format Event", "type": "main", "index": 0}]]
        },
        "Format Event": {
            "main": [
                [
                    {"node": "Insert brain_events", "type": "main", "index": 0},
                    {"node": "Has State Update?", "type": "main", "index": 0},
                ]
            ]
        },
        "Has State Update?": {
            "main": [
                [{"node": "Upsert brain_state", "type": "main", "index": 0}],
                [],
            ]
        },
    }


# ======================================================================
# BUILD / DEPLOY / ACTIVATE
# ======================================================================

def build() -> dict:
    nodes = build_nodes()
    connections = build_connections(nodes)
    return {
        "name": WORKFLOW_NAME,
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
    }


def save_json(workflow: dict) -> str:
    out_dir = Path(__file__).parent.parent / "workflows" / "brain"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "brain_writer.json"
    with open(path, "w") as f:
        json.dump(workflow, f, indent=2)
    print(f"  Saved: {path}")
    return str(path)


def deploy(workflow: dict) -> str:
    import httpx
    headers = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}

    # Check if workflow exists by name
    resp = httpx.get(
        f"{N8N_BASE_URL}/api/v1/workflows",
        headers=headers,
        params={"limit": 100},
    )
    resp.raise_for_status()
    existing = [w for w in resp.json()["data"] if w["name"] == WORKFLOW_NAME]

    if existing:
        wf_id = existing[0]["id"]
        print(f"  Updating existing workflow {wf_id}...")
        resp = httpx.put(
            f"{N8N_BASE_URL}/api/v1/workflows/{wf_id}",
            headers=headers,
            json=workflow,
        )
    else:
        print("  Creating new workflow...")
        resp = httpx.post(
            f"{N8N_BASE_URL}/api/v1/workflows",
            headers=headers,
            json=workflow,
        )

    resp.raise_for_status()
    wf_id = resp.json()["id"]
    print(f"  Deployed: {WORKFLOW_NAME} ({wf_id})")
    return wf_id


def activate(wf_id: str) -> None:
    import httpx
    headers = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}
    resp = httpx.post(f"{N8N_BASE_URL}/api/v1/workflows/{wf_id}/activate", headers=headers)
    resp.raise_for_status()
    print(f"  Activated: {wf_id}")


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "build"

    print(f"\n{'='*60}")
    print(f"  AVM Brain Writer — {action.upper()}")
    print(f"{'='*60}\n")

    # Validate Supabase config
    if not SUPABASE_SERVICE_ROLE_KEY:
        print("  WARNING: SUPABASE_SERVICE_ROLE_KEY not set in .env")
        print("  The workflow will need a Supabase httpHeaderAuth credential in n8n")

    workflow = build()
    save_json(workflow)

    if action in ("deploy", "activate"):
        wf_id = deploy(workflow)
        if action == "activate":
            activate(wf_id)

        print(f"\n  IMPORTANT: Create httpHeaderAuth credential in n8n UI:")
        print(f"    Name: 'Supabase Service Role'")
        print(f"    Header Name: Authorization")
        print(f"    Header Value: Bearer <SUPABASE_SERVICE_ROLE_KEY>")
        print(f"    Then update credential ID 'BRAIN_SUPABASE_CRED' in the workflow\n")

    print("  Done.\n")


if __name__ == "__main__":
    main()

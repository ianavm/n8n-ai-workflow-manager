"""
Plug-and-Play Accounting — WF01 Customer & Supplier Master Data

Handles create/update of customers and suppliers via webhook,
with dedup by email+client_id, accounting-software sync adapter,
audit logging, and bank-details hashing.

Usage:
    python tools/deploy_acct_v2_wf01.py build
    python tools/deploy_acct_v2_wf01.py deploy
    python tools/deploy_acct_v2_wf01.py activate
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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
    if_node,
    manual_trigger,
    noop_node,
    portal_status_webhook,
    respond_webhook,
    supabase_insert,
    supabase_select,
    supabase_update,
    switch_node,
    uid,
    webhook_trigger,
)

# ── Constants ────────────────────────────────────────────────

WORKFLOW_NAME = "ACCT-01 Customer & Supplier Master Data"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "accounting-v2"
OUTPUT_FILENAME = "wf01_master_data.json"


# ══════════════════════════════════════════════════════════════
# NODE BUILDERS
# ══════════════════════════════════════════════════════════════

def build_nodes() -> list[dict[str, Any]]:
    """Build all ~18 nodes for the Customer & Supplier Master Data workflow."""
    nodes: list[dict[str, Any]] = []

    # ── 1. Manual Trigger ──────────────────────────────────────
    nodes.append(manual_trigger(position=[200, 600]))

    # ── 2. Customer Webhook ────────────────────────────────────
    nodes.append(webhook_trigger(
        name="Customer Webhook",
        path="accounting/customer",
        position=[200, 300],
    ))

    # ── 3. Supplier Webhook ────────────────────────────────────
    nodes.append(webhook_trigger(
        name="Supplier Webhook",
        path="accounting/supplier",
        position=[200, 900],
    ))

    # ── 4. Validate Customer Fields ────────────────────────────
    nodes.append(code_node(
        name="Validate Customer Fields",
        js_code=(
            "const body = $input.first().json.body || $input.first().json;\n"
            "const errors = [];\n"
            "\n"
            "if (!body.legal_name || !body.legal_name.trim()) {\n"
            "  errors.push('legal_name is required');\n"
            "}\n"
            "if (!body.client_id) {\n"
            "  errors.push('client_id is required');\n"
            "}\n"
            "\n"
            "if (errors.length > 0) {\n"
            "  throw new Error('Validation failed: ' + errors.join(', '));\n"
            "}\n"
            "\n"
            "return [{\n"
            "  json: {\n"
            "    legal_name: body.legal_name.trim(),\n"
            "    email: (body.email || '').trim().toLowerCase(),\n"
            "    phone: body.phone || null,\n"
            "    billing_address: body.billing_address || null,\n"
            "    vat_number: body.vat_number || null,\n"
            "    payment_terms: body.payment_terms || 'net_30',\n"
            "    credit_limit: body.credit_limit || 0,\n"
            "    client_id: body.client_id,\n"
            "    entity_type: 'customer',\n"
            "  }\n"
            "}];\n"
        ),
        position=[460, 300],
    ))

    # ── 5. Check Customer Exists ───────────────────────────────
    nodes.append(supabase_select(
        name="Check Customer Exists",
        table="acct_customers",
        select="*",
        filters="={{  'email=eq.' + $json.email + '&client_id=eq.' + $json.client_id }}",
        position=[720, 300],
    ))

    # ── 6. Customer Exists? ────────────────────────────────────
    nodes.append(if_node(
        name="Customer Exists?",
        left_value="={{ $json.length }}",
        operator_type="number",
        operation="gt",
        right_value="0",
        position=[960, 300],
    ))

    # ── 7. Prepare Customer Update ─────────────────────────────
    nodes.append(code_node(
        name="Prepare Customer Update",
        js_code=(
            "const existing = $input.first().json[0] || $input.first().json;\n"
            "const upstream = $('Validate Customer Fields').first().json;\n"
            "\n"
            "return [{\n"
            "  json: {\n"
            "    id: existing.id,\n"
            "    updatePayload: {\n"
            "      legal_name: upstream.legal_name,\n"
            "      phone: upstream.phone,\n"
            "      billing_address: upstream.billing_address,\n"
            "      vat_number: upstream.vat_number,\n"
            "      payment_terms: upstream.payment_terms,\n"
            "      credit_limit: upstream.credit_limit,\n"
            "      updated_at: new Date().toISOString(),\n"
            "    },\n"
            "    client_id: upstream.client_id,\n"
            "    event_type: 'CUSTOMER_UPDATED',\n"
            "    entity_type: 'customer',\n"
            "  }\n"
            "}];\n"
        ),
        position=[1200, 200],
    ))

    # ── 8. Update Customer ─────────────────────────────────────
    nodes.append(supabase_update(
        name="Update Customer",
        table="acct_customers",
        match_col="id",
        position=[1440, 200],
    ))

    # ── 9. Insert Customer ─────────────────────────────────────
    nodes.append(supabase_insert(
        name="Insert Customer",
        table="acct_customers",
        position=[1200, 400],
    ))

    # ── 10. Acct Software Switch (Customer) ────────────────────
    nodes.append(switch_node(
        name="Acct Software Switch (Customer)",
        rules=[
            {"leftValue": "={{ $json.accounting_software || 'none' }}", "rightValue": "quickbooks", "output": "quickbooks"},
            {"leftValue": "={{ $json.accounting_software || 'none' }}", "rightValue": "xero", "output": "xero"},
            {"leftValue": "={{ $json.accounting_software || 'none' }}", "rightValue": "sage", "output": "sage"},
        ],
        position=[1680, 300],
    ))

    # ── 11. Sync Customer to QB (placeholder) ──────────────────
    nodes.append(code_node(
        name="Sync Customer to QB",
        js_code=(
            "// Placeholder: POST customer to QuickBooks / Xero / Sage\n"
            "// Replace with HTTP Request to accounting software API\n"
            "const record = $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    ...record,\n"
            "    external_id: 'placeholder_' + Date.now(),\n"
            "    sync_status: 'pending_implementation',\n"
            "  }\n"
            "}];\n"
        ),
        position=[1940, 100],
    ))

    # ── 12. Skip Sync (Customer) ───────────────────────────────
    nodes.append(noop_node(
        name="Skip Sync (Customer)",
        position=[1940, 500],
    ))

    # ── 13. Audit Log Customer ─────────────────────────────────
    nodes.append(portal_status_webhook(
        name="Audit Log Customer",
        action="audit_log",
        position=[2200, 300],
    ))

    # ── 14. Respond Customer Webhook ───────────────────────────
    nodes.append(respond_webhook(
        name="Respond Customer Webhook",
        position=[2440, 300],
    ))

    # ── 15. Validate Supplier Fields ───────────────────────────
    nodes.append(code_node(
        name="Validate Supplier Fields",
        js_code=(
            "const body = $input.first().json.body || $input.first().json;\n"
            "const errors = [];\n"
            "\n"
            "if (!body.legal_name || !body.legal_name.trim()) {\n"
            "  errors.push('legal_name is required');\n"
            "}\n"
            "if (!body.client_id) {\n"
            "  errors.push('client_id is required');\n"
            "}\n"
            "\n"
            "if (errors.length > 0) {\n"
            "  throw new Error('Validation failed: ' + errors.join(', '));\n"
            "}\n"
            "\n"
            "// Hash bank details if provided — never store raw\n"
            "let bankDetailsHash = null;\n"
            "if (body.bank_details) {\n"
            "  const raw = JSON.stringify(body.bank_details);\n"
            "  let hash = 0;\n"
            "  for (let i = 0; i < raw.length; i++) {\n"
            "    const chr = raw.charCodeAt(i);\n"
            "    hash = ((hash << 5) - hash) + chr;\n"
            "    hash |= 0;\n"
            "  }\n"
            "  bankDetailsHash = 'hash_' + Math.abs(hash).toString(16);\n"
            "}\n"
            "\n"
            "return [{\n"
            "  json: {\n"
            "    legal_name: body.legal_name.trim(),\n"
            "    email: (body.email || '').trim().toLowerCase(),\n"
            "    phone: body.phone || null,\n"
            "    billing_address: body.billing_address || null,\n"
            "    vat_number: body.vat_number || null,\n"
            "    payment_terms: body.payment_terms || 'net_30',\n"
            "    bank_details_hash: bankDetailsHash,\n"
            "    client_id: body.client_id,\n"
            "    entity_type: 'supplier',\n"
            "  }\n"
            "}];\n"
        ),
        position=[460, 900],
    ))

    # ── 16. Check Supplier Exists ──────────────────────────────
    nodes.append(supabase_select(
        name="Check Supplier Exists",
        table="acct_suppliers",
        select="*",
        filters="={{ 'email=eq.' + $json.email + '&client_id=eq.' + $json.client_id }}",
        position=[720, 900],
    ))

    # ── 17. Supplier Exists? ───────────────────────────────────
    nodes.append(if_node(
        name="Supplier Exists?",
        left_value="={{ $json.length }}",
        operator_type="number",
        operation="gt",
        right_value="0",
        position=[960, 900],
    ))

    # ── 18. Prepare Supplier Update ────────────────────────────
    nodes.append(code_node(
        name="Prepare Supplier Update",
        js_code=(
            "const existing = $input.first().json[0] || $input.first().json;\n"
            "const upstream = $('Validate Supplier Fields').first().json;\n"
            "\n"
            "return [{\n"
            "  json: {\n"
            "    id: existing.id,\n"
            "    updatePayload: {\n"
            "      legal_name: upstream.legal_name,\n"
            "      phone: upstream.phone,\n"
            "      billing_address: upstream.billing_address,\n"
            "      vat_number: upstream.vat_number,\n"
            "      payment_terms: upstream.payment_terms,\n"
            "      bank_details_hash: upstream.bank_details_hash,\n"
            "      updated_at: new Date().toISOString(),\n"
            "    },\n"
            "    client_id: upstream.client_id,\n"
            "    event_type: 'SUPPLIER_UPDATED',\n"
            "    entity_type: 'supplier',\n"
            "  }\n"
            "}];\n"
        ),
        position=[1200, 800],
    ))

    # ── 19. Update Supplier ────────────────────────────────────
    nodes.append(supabase_update(
        name="Update Supplier",
        table="acct_suppliers",
        match_col="id",
        position=[1440, 800],
    ))

    # ── 20. Insert Supplier ────────────────────────────────────
    nodes.append(supabase_insert(
        name="Insert Supplier",
        table="acct_suppliers",
        position=[1200, 1000],
    ))

    # ── 21. Acct Software Switch (Supplier) ────────────────────
    nodes.append(switch_node(
        name="Acct Software Switch (Supplier)",
        rules=[
            {"leftValue": "={{ $json.accounting_software || 'none' }}", "rightValue": "quickbooks", "output": "quickbooks"},
            {"leftValue": "={{ $json.accounting_software || 'none' }}", "rightValue": "xero", "output": "xero"},
            {"leftValue": "={{ $json.accounting_software || 'none' }}", "rightValue": "sage", "output": "sage"},
        ],
        position=[1680, 900],
    ))

    # ── 22. Sync Supplier to QB (placeholder) ──────────────────
    nodes.append(code_node(
        name="Sync Supplier to QB",
        js_code=(
            "// Placeholder: POST supplier to QuickBooks / Xero / Sage\n"
            "// Replace with HTTP Request to accounting software API\n"
            "const record = $input.first().json;\n"
            "return [{\n"
            "  json: {\n"
            "    ...record,\n"
            "    external_id: 'placeholder_' + Date.now(),\n"
            "    sync_status: 'pending_implementation',\n"
            "  }\n"
            "}];\n"
        ),
        position=[1940, 700],
    ))

    # ── 23. Skip Sync (Supplier) ───────────────────────────────
    nodes.append(noop_node(
        name="Skip Sync (Supplier)",
        position=[1940, 1100],
    ))

    # ── 24. Audit Log Supplier ─────────────────────────────────
    nodes.append(portal_status_webhook(
        name="Audit Log Supplier",
        action="audit_log",
        position=[2200, 900],
    ))

    # ── 25. Respond Supplier Webhook ───────────────────────────
    nodes.append(respond_webhook(
        name="Respond Supplier Webhook",
        position=[2440, 900],
    ))

    return nodes


# ══════════════════════════════════════════════════════════════
# CONNECTIONS
# ══════════════════════════════════════════════════════════════

def build_connections() -> dict[str, Any]:
    """Build connections for the Customer & Supplier Master Data workflow."""
    return {
        # ── Customer path ──────────────────────────────────────
        "Customer Webhook": {
            "main": [[conn("Validate Customer Fields")]],
        },
        "Manual Trigger": {
            "main": [[conn("Validate Customer Fields")]],
        },
        "Validate Customer Fields": {
            "main": [[conn("Check Customer Exists")]],
        },
        "Check Customer Exists": {
            "main": [[conn("Customer Exists?")]],
        },
        "Customer Exists?": {
            "main": [
                # true  -> update
                [conn("Prepare Customer Update")],
                # false -> insert
                [conn("Insert Customer")],
            ],
        },
        "Prepare Customer Update": {
            "main": [[conn("Update Customer")]],
        },
        "Update Customer": {
            "main": [[conn("Acct Software Switch (Customer)")]],
        },
        "Insert Customer": {
            "main": [[conn("Acct Software Switch (Customer)")]],
        },
        "Acct Software Switch (Customer)": {
            "main": [
                # output 0 = quickbooks
                [conn("Sync Customer to QB")],
                # output 1 = xero (reuse same placeholder)
                [conn("Sync Customer to QB")],
                # output 2 = sage (reuse same placeholder)
                [conn("Sync Customer to QB")],
                # output 3 = fallback (none)
                [conn("Skip Sync (Customer)")],
            ],
        },
        "Sync Customer to QB": {
            "main": [[conn("Audit Log Customer")]],
        },
        "Skip Sync (Customer)": {
            "main": [[conn("Audit Log Customer")]],
        },
        "Audit Log Customer": {
            "main": [[conn("Respond Customer Webhook")]],
        },

        # ── Supplier path ──────────────────────────────────────
        "Supplier Webhook": {
            "main": [[conn("Validate Supplier Fields")]],
        },
        "Validate Supplier Fields": {
            "main": [[conn("Check Supplier Exists")]],
        },
        "Check Supplier Exists": {
            "main": [[conn("Supplier Exists?")]],
        },
        "Supplier Exists?": {
            "main": [
                # true  -> update
                [conn("Prepare Supplier Update")],
                # false -> insert
                [conn("Insert Supplier")],
            ],
        },
        "Prepare Supplier Update": {
            "main": [[conn("Update Supplier")]],
        },
        "Update Supplier": {
            "main": [[conn("Acct Software Switch (Supplier)")]],
        },
        "Insert Supplier": {
            "main": [[conn("Acct Software Switch (Supplier)")]],
        },
        "Acct Software Switch (Supplier)": {
            "main": [
                # output 0 = quickbooks
                [conn("Sync Supplier to QB")],
                # output 1 = xero
                [conn("Sync Supplier to QB")],
                # output 2 = sage
                [conn("Sync Supplier to QB")],
                # output 3 = fallback (none)
                [conn("Skip Sync (Supplier)")],
            ],
        },
        "Sync Supplier to QB": {
            "main": [[conn("Audit Log Supplier")]],
        },
        "Skip Sync (Supplier)": {
            "main": [[conn("Audit Log Supplier")]],
        },
        "Audit Log Supplier": {
            "main": [[conn("Respond Supplier Webhook")]],
        },
    }


# ══════════════════════════════════════════════════════════════
# WORKFLOW ASSEMBLY
# ══════════════════════════════════════════════════════════════

def build_workflow() -> dict[str, Any]:
    """Assemble the complete workflow JSON."""
    return build_workflow_json(
        name=WORKFLOW_NAME,
        nodes=build_nodes(),
        connections=build_connections(),
    )


def save_workflow(workflow: dict[str, Any]) -> Path:
    """Save workflow JSON to file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILENAME

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    return output_path


def print_workflow_stats(workflow: dict[str, Any]) -> None:
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
        description="ACCT-01 Customer & Supplier Master Data — Builder & Deployer",
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
    print("ACCT-01  CUSTOMER & SUPPLIER MASTER DATA")
    print("=" * 60)

    # ── Build ──────────────────────────────────────────────────
    print("\nBuilding workflow...")
    workflow = build_workflow()
    output_path = save_workflow(workflow)
    print_workflow_stats(workflow)
    print(f"  Saved to: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    # ── Deploy / Activate ──────────────────────────────────────
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

        # Check if workflow already exists by name
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
            print(f"  Activating...")
            client.activate_workflow(wf_id)
            print(f"  Activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Webhooks:")
    print("  POST /accounting/customer  — create/update customer")
    print("  POST /accounting/supplier  — create/update supplier")
    print()
    print("Next steps:")
    print("  1. Open the workflow in n8n UI to verify node connections")
    print("  2. Ensure Supabase tables exist: acct_customers, acct_suppliers")
    print("  3. Configure portal webhook secret (N8N_WEBHOOK_SECRET)")
    print("  4. Test: POST to /accounting/customer with {legal_name, client_id, email}")
    print("  5. Test: POST to /accounting/supplier with {legal_name, client_id, email}")
    print("  6. Replace placeholder accounting-software sync nodes when ready")


if __name__ == "__main__":
    main()

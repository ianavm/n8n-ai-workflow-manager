"""
Document Intake - Master Workflow Builder & Deployer

Real Estate Document Intake & Organization System.
Automates document capture from Outlook, AI classification,
Google Drive folder organization, and admin review queue.

Workflows:
    WF-DI-01: Email Intake + Raw Storage
    WF-DI-02: Document Processing (sub-workflow)
    WF-DI-03: Admin Review (polls Google Sheets)
    WF-DI-04: Notifications & Monitoring

Usage:
    python tools/deploy_document_intake.py build              # Build all JSONs
    python tools/deploy_document_intake.py build di01         # Build WF-DI-01 only
    python tools/deploy_document_intake.py deploy             # Build + Deploy (inactive)
    python tools/deploy_document_intake.py activate           # Build + Deploy + Activate
"""

import json
import sys
import uuid
import os
import importlib
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Add tools dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# -- Credential Constants ------------------------------------------------
# Existing credentials (already in n8n)
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GOOGLE_SHEETS = {"id": "OkpDXxwI8WcUJp4P", "name": "Google Sheets AVM Tutorial"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}

# New credentials (must create in n8n UI before deploy)
CRED_OUTLOOK = {
    "id": os.getenv("N8N_CRED_OUTLOOK", "PLACEHOLDER_OUTLOOK"),
    "name": "Microsoft Outlook OAuth2",
}
CRED_GOOGLE_DRIVE = {
    "id": os.getenv("N8N_CRED_GDRIVE", "PLACEHOLDER_GDRIVE"),
    "name": "Google Drive OAuth2",
}

# -- Google Sheets DB ----------------------------------------------------
DI_SHEETS_ID = os.getenv("DI_SHEETS_ID", "REPLACE_WITH_SHEETS_ID")

# -- Google Drive Folders ------------------------------------------------
DI_INCOMING_FOLDER_ID = os.getenv("DI_GDRIVE_INCOMING_FOLDER_ID", "REPLACE_INCOMING")
DI_PROPERTIES_FOLDER_ID = os.getenv("DI_GDRIVE_PROPERTIES_FOLDER_ID", "REPLACE_PROPERTIES")

# -- Google Document AI (OCR) -------------------------------------------
DI_DOCAI_PROJECT_ID = os.getenv("DI_DOCAI_PROJECT_ID", "REPLACE_DOCAI_PROJECT")
DI_DOCAI_LOCATION = os.getenv("DI_DOCAI_LOCATION", "us")
DI_DOCAI_PROCESSOR_ID = os.getenv("DI_DOCAI_PROCESSOR_ID", "REPLACE_DOCAI_PROCESSOR")

# -- Sub-workflow IDs (set after first deploy) ---------------------------
WF_DI_02_ID = os.getenv("WF_DI_02_ID", "REPLACE_AFTER_DEPLOY")

# -- Sheet Tab Names -----------------------------------------------------
TAB_DOCUMENT_LOG = "Document_Log"
TAB_PROPERTY_REGISTRY = "Property_Registry"
TAB_REVIEW_QUEUE = "Review_Queue"
TAB_AUDIT_LOG = "Audit_Log"
TAB_ADMIN_CONFIG = "Admin_Config"
TAB_DUPLICATE_LOG = "Duplicate_Log"

# -- Document Type -> Folder Mapping -------------------------------------
DOC_TYPE_FOLDER_MAP = {
    "FICA": "01_FICA",
    "Offer_to_Purchase": "02_OTP",
    "Mandate": "03_Mandate",
    "Title_Deed": "04_Title_Deed",
    "Municipal_Document": "05_Municipal",
    "Bond_Finance": "06_Bond_Finance",
    "Compliance_Certificate": "07_Compliance",
    "Sectional_Scheme": "08_Sectional_Scheme",
    "Entity_Document": "09_Entity_Docs",
    "Other": "10_Other",
}

# -- AI Config -----------------------------------------------------------
AI_MODEL = "anthropic/claude-sonnet-4-20250514"
AI_CONFIDENCE_THRESHOLD = 0.75

# -- Config bundle (passed to per-workflow modules) ----------------------
CONFIG = {
    "cred_outlook": CRED_OUTLOOK,
    "cred_google_drive": CRED_GOOGLE_DRIVE,
    "cred_openrouter": CRED_OPENROUTER,
    "cred_google_sheets": CRED_GOOGLE_SHEETS,
    "cred_gmail": CRED_GMAIL,
    "di_sheets_id": DI_SHEETS_ID,
    "di_incoming_folder_id": DI_INCOMING_FOLDER_ID,
    "di_properties_folder_id": DI_PROPERTIES_FOLDER_ID,
    "di_docai_project_id": DI_DOCAI_PROJECT_ID,
    "di_docai_location": DI_DOCAI_LOCATION,
    "di_docai_processor_id": DI_DOCAI_PROCESSOR_ID,
    "wf_di_02_id": WF_DI_02_ID,
    "tab_document_log": TAB_DOCUMENT_LOG,
    "tab_property_registry": TAB_PROPERTY_REGISTRY,
    "tab_review_queue": TAB_REVIEW_QUEUE,
    "tab_audit_log": TAB_AUDIT_LOG,
    "tab_admin_config": TAB_ADMIN_CONFIG,
    "tab_duplicate_log": TAB_DUPLICATE_LOG,
    "doc_type_folder_map": DOC_TYPE_FOLDER_MAP,
    "ai_model": AI_MODEL,
    "ai_confidence_threshold": AI_CONFIDENCE_THRESHOLD,
}


# -- Helpers --------------------------------------------------------------

def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# -- Workflow Registry ----------------------------------------------------

WORKFLOW_REGISTRY = {
    "di01": {
        "module": "deploy_di_wf01",
        "name": "Document Intake - Email Intake & Raw Storage (WF-DI-01)",
        "filename": "wf01_email_intake.json",
        "description": "Outlook email trigger, attachment download, Drive upload, dupe detection",
    },
    "di02": {
        "module": "deploy_di_wf02",
        "name": "Document Intake - Document Processing (WF-DI-02)",
        "filename": "wf02_doc_processing.json",
        "description": "PDF text extraction, OCR fallback, AI classification, folder filing",
    },
    "di03": {
        "module": "deploy_di_wf03",
        "name": "Document Intake - Admin Review (WF-DI-03)",
        "filename": "wf03_admin_review.json",
        "description": "Polls Review_Queue sheet for admin decisions, processes approvals",
    },
    "di04": {
        "module": "deploy_di_wf04",
        "name": "Document Intake - Notifications & Monitoring (WF-DI-04)",
        "filename": "wf04_notifications.json",
        "description": "Daily summary, review alerts, error handling, audit logging",
    },
}


# ================================================================
# COMBINED WORKFLOW BUILDER
# ================================================================

def build_combined_nodes_and_connections():
    """
    Build a single combined workflow containing all 4 sub-workflows
    on one canvas. Each workflow section is offset vertically so they
    don't overlap, with colored section sticky notes for visual clarity.

    This is for client presentation / overview only - not for production
    deployment (duplicate triggers would conflict).
    """
    all_nodes = []
    all_connections = {}

    # Canvas layout: stack workflows vertically with generous spacing
    y_offsets = {
        "di01": 0,       # Email Intake (top)
        "di02": 1400,    # Document Processing
        "di03": 3200,    # Admin Review
        "di04": 4400,    # Notifications
    }

    section_colors = {
        "di01": 4,  # Blue
        "di02": 2,  # Green
        "di03": 3,  # Yellow
        "di04": 5,  # Red
    }

    section_labels = {
        "di01": "PHASE 1: EMAIL INTAKE & RAW STORAGE",
        "di02": "PHASE 2: DOCUMENT PROCESSING & AI CLASSIFICATION",
        "di03": "PHASE 3: ADMIN REVIEW QUEUE",
        "di04": "MONITORING & NOTIFICATIONS",
    }

    for wf_id, reg in WORKFLOW_REGISTRY.items():
        y_offset = y_offsets[wf_id]

        # Add large section sticky note as a visual divider
        all_nodes.append({
            "parameters": {
                "content": f"## {section_labels[wf_id]}\n{reg['description']}",
                "width": 1800,
                "height": 200,
                "color": section_colors.get(wf_id, 1),
            },
            "id": uid(),
            "name": f"Section - {wf_id.upper()}",
            "type": "n8n-nodes-base.stickyNote",
            "position": [100, y_offset - 120],
            "typeVersion": 1,
        })

        # Import module and build nodes
        mod = importlib.import_module(reg["module"])
        nodes = mod.build_nodes(CONFIG)
        connections = mod.build_connections(CONFIG)

        # Offset node Y positions
        for node in nodes:
            if "position" in node:
                node["position"] = [
                    node["position"][0],
                    node["position"][1] + y_offset,
                ]

        all_nodes.extend(nodes)
        all_connections.update(connections)

    return all_nodes, all_connections


# ================================================================
# WORKFLOW ASSEMBLY
# ================================================================

def build_workflow(wf_id):
    """Assemble a complete workflow JSON."""
    if wf_id == "combined":
        nodes, connections = build_combined_nodes_and_connections()
        name = "Document Intake - Complete System (All Workflows)"
    elif wf_id in WORKFLOW_REGISTRY:
        mod = importlib.import_module(WORKFLOW_REGISTRY[wf_id]["module"])
        nodes = mod.build_nodes(CONFIG)
        connections = mod.build_connections(CONFIG)
        name = WORKFLOW_REGISTRY[wf_id]["name"]
    else:
        valid = list(WORKFLOW_REGISTRY.keys()) + ["combined"]
        raise ValueError(f"Unknown workflow: {wf_id}. Valid: {', '.join(valid)}")

    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def save_workflow(wf_id, workflow):
    """Save workflow JSON to file."""
    if wf_id == "combined":
        filename = "combined_all_workflows.json"
    else:
        filename = WORKFLOW_REGISTRY[wf_id]["filename"]

    output_dir = Path(__file__).parent.parent / "workflows" / "document-intake"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    return output_path


def print_workflow_stats(wf_id, workflow):
    """Print workflow statistics."""
    all_nodes = workflow["nodes"]
    func_nodes = [n for n in all_nodes if n["type"] != "n8n-nodes-base.stickyNote"]
    note_nodes = [n for n in all_nodes if n["type"] == "n8n-nodes-base.stickyNote"]
    conn_count = len(workflow["connections"])
    print(f"  Name: {workflow['name']}")
    print(f"  Nodes: {len(func_nodes)} functional + {len(note_nodes)} sticky notes")
    print(f"  Connections: {conn_count}")


def check_credentials(action):
    """Pre-flight credential validation."""
    missing = []
    if "PLACEHOLDER" in CRED_OUTLOOK["id"]:
        missing.append("N8N_CRED_OUTLOOK - Create Microsoft Outlook OAuth2 in n8n UI")
    if "PLACEHOLDER" in CRED_GOOGLE_DRIVE["id"]:
        missing.append("N8N_CRED_GDRIVE - Create Google Drive OAuth2 in n8n UI")
    if "REPLACE" in DI_SHEETS_ID:
        missing.append("DI_SHEETS_ID - Create tracking Google Sheet and set its ID")
    if "REPLACE" in DI_INCOMING_FOLDER_ID:
        missing.append("DI_GDRIVE_INCOMING_FOLDER_ID - Create Incoming_Documents folder in Drive")
    if "REPLACE" in DI_PROPERTIES_FOLDER_ID:
        missing.append("DI_GDRIVE_PROPERTIES_FOLDER_ID - Create Properties folder in Drive")

    if missing:
        print()
        print("WARNING: Missing configuration:")
        for m in missing:
            print(f"  - {m}")
        print()
        if action in ("deploy", "activate"):
            print("Deploying with placeholder IDs (skeleton / visual preview only).")
            print("Workflows will NOT be activated until real credentials are set.")
            print()
        else:
            print("Continuing build with placeholder IDs (for preview only)...")
            print()


# ================================================================
# CLI
# ================================================================

def main():
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    print("=" * 60)
    print("DOCUMENT INTAKE - WORKFLOW BUILDER")
    print("=" * 60)

    # Determine targets
    valid_wfs = list(WORKFLOW_REGISTRY.keys()) + ["combined"]
    if target == "all":
        # Build all individual + combined
        workflow_ids = list(WORKFLOW_REGISTRY.keys()) + ["combined"]
    elif target in valid_wfs:
        workflow_ids = [target]
    else:
        print(f"ERROR: Unknown target '{target}'. Use: all, {', '.join(valid_wfs)}")
        sys.exit(1)

    # Pre-flight checks
    check_credentials(action)

    # Build workflows
    workflows = {}
    for wf_id in workflow_ids:
        print(f"\nBuilding {wf_id}...")
        try:
            workflow = build_workflow(wf_id)
            output_path = save_workflow(wf_id, workflow)
            workflows[wf_id] = workflow
            print_workflow_stats(wf_id, workflow)
            print(f"  Saved to: {output_path}")
        except Exception as e:
            print(f"  ERROR building {wf_id}: {e}")
            import traceback
            traceback.print_exc()
            if action in ("deploy", "activate"):
                print("  Aborting deployment due to build error.")
                sys.exit(1)

    if action == "build":
        print("\n" + "=" * 60)
        print("BUILD COMPLETE")
        print("=" * 60)
        print(f"\nBuilt {len(workflows)} workflow(s):")
        for wf_id in workflows:
            if wf_id == "combined":
                print(f"  combined: Document Intake - Complete System (All Workflows)")
            else:
                print(f"  {wf_id}: {WORKFLOW_REGISTRY[wf_id]['name']}")
        print("\nRun with 'deploy' to push to n8n.")
        return

    # Deploy to n8n
    if action in ("deploy", "activate"):
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

            deployed_ids = {}

            for wf_id, workflow in workflows.items():
                print(f"\nDeploying {wf_id}...")

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
                    deployed_ids[wf_id] = result.get("id")
                    print(f"  Updated: {result.get('name')} (ID: {result.get('id')})")
                else:
                    create_payload = {
                        "name": workflow["name"],
                        "nodes": workflow["nodes"],
                        "connections": workflow["connections"],
                        "settings": workflow["settings"],
                    }
                    result = client.create_workflow(create_payload)
                    deployed_ids[wf_id] = result.get("id")
                    print(f"  Created: {result.get('name')} (ID: {result.get('id')})")

                if action == "activate" and deployed_ids.get(wf_id):
                    has_placeholders = any("PLACEHOLDER" in v["id"] if isinstance(v, dict) and "id" in v else False for v in [CRED_OUTLOOK, CRED_GOOGLE_DRIVE])
                    if wf_id == "combined":
                        print(f"  Skipping activation for combined (presentation only - duplicate triggers)")
                    elif has_placeholders:
                        print(f"  Skipping activation for {wf_id} (placeholder credentials - skeleton only)")
                    else:
                        print(f"  Activating {wf_id}...")
                        client.activate_workflow(deployed_ids[wf_id])
                        print(f"  Activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Deployed workflow IDs:")
    for wf_id, wid in deployed_ids.items():
        print(f"  {wf_id}: {wid}")
    print()
    print("IMPORTANT: Set WF_DI_02_ID in .env after deploying WF-DI-02:")
    print(f"  WF_DI_02_ID={deployed_ids.get('di02', 'CHECK_N8N_UI')}")
    print()
    print("Next steps:")
    print("  1. Open each workflow in n8n UI to verify node connections")
    print("  2. Verify credential bindings (Outlook, Google Drive, Sheets, Gmail)")
    print("  3. Set WF_DI_02_ID in .env -> rebuild + redeploy WF-DI-01")
    print("  4. Send a test email with PDF attachment to the monitored mailbox")
    print("  5. Verify document appears in Google Drive Incoming_Documents/")
    print("  6. Check Document_Log sheet for the new row")


if __name__ == "__main__":
    main()

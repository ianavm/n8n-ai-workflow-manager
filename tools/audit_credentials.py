"""Audit n8n credentials used by active workflows.

Identifies which credentials are referenced by active workflows,
lists all available credentials, and flags potential sharing issues.
Outputs a checklist for manual credential sharing in the n8n UI.
"""
import json
import os
import sys
import io
from collections import defaultdict

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from config_loader import load_config
from n8n_client import N8nClient


def extract_credentials_from_workflow(workflow):
    """Extract all credential references from a workflow's nodes."""
    creds = []
    for node in workflow.get("nodes", []):
        node_creds = node.get("credentials", {})
        for cred_type, cred_info in node_creds.items():
            creds.append({
                "cred_type": cred_type,
                "cred_id": cred_info.get("id", "unknown"),
                "cred_name": cred_info.get("name", "unknown"),
                "node_name": node.get("name", "unknown"),
                "node_type": node.get("type", "unknown"),
            })
    return creds


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    if not api_key:
        print("Error: N8N_API_KEY not found.")
        sys.exit(1)

    base_url = config["n8n"]["base_url"]

    print("=" * 70)
    print("CREDENTIAL AUDIT - Active Workflows")
    print("=" * 70)

    with N8nClient(base_url, api_key) as client:
        # 1. Get all active workflows
        print("\n[1/3] Fetching active workflows...")
        all_workflows = client.list_workflows(use_cache=False)
        active_wfs = [w for w in all_workflows if w.get("active")]
        print(f"  Active workflows: {len(active_wfs)}")

        # 2. Get available credentials
        print("\n[2/3] Fetching credentials...")
        all_creds = client.list_credentials()
        cred_by_id = {c.get("id"): c for c in all_creds}
        print(f"  Available credentials: {len(all_creds)}")

        # 3. Extract credential usage from each active workflow
        print("\n[3/3] Analyzing credential usage...")
        cred_usage = defaultdict(list)  # cred_id -> list of (workflow_name, node_name)
        missing_creds = []
        workflow_cred_details = []

        for wf_summary in active_wfs:
            wf_id = wf_summary.get("id")
            wf_name = wf_summary.get("name", "Unknown")

            # Fetch full workflow to get node credential refs
            try:
                wf_full = client.get_workflow(wf_id)
            except Exception as e:
                print(f"  Warning: Could not fetch {wf_name} ({wf_id}): {e}")
                continue

            creds = extract_credentials_from_workflow(wf_full)
            for cred in creds:
                cred_id = cred["cred_id"]
                cred_usage[cred_id].append({
                    "workflow": wf_name,
                    "workflow_id": wf_id,
                    "node": cred["node_name"],
                })

                # Check if credential exists
                if cred_id not in cred_by_id and cred_id != "unknown":
                    missing_creds.append({
                        **cred,
                        "workflow": wf_name,
                        "workflow_id": wf_id,
                    })

                workflow_cred_details.append({
                    "workflow": wf_name,
                    "workflow_id": wf_id,
                    **cred,
                })

        # --- Report ---
        print("\n" + "=" * 70)
        print("CREDENTIAL USAGE REPORT")
        print("=" * 70)

        # Unique credentials in use
        unique_creds = set()
        for detail in workflow_cred_details:
            unique_creds.add((detail["cred_id"], detail["cred_name"], detail["cred_type"]))

        print(f"\nUnique credentials referenced by active workflows: {len(unique_creds)}")
        print(f"Total credentials in n8n: {len(all_creds)}")

        # Print each credential and which workflows use it
        print(f"\n{'='*70}")
        print("CREDENTIALS IN USE")
        print(f"{'='*70}")
        for cred_id, cred_name, cred_type in sorted(unique_creds, key=lambda x: x[1]):
            users = cred_usage.get(cred_id, [])
            exists = "OK" if cred_id in cred_by_id else "MISSING"
            print(f"\n  [{exists}] {cred_name} ({cred_type})")
            print(f"         ID: {cred_id}")
            print(f"         Used by {len(users)} workflow(s):")
            for u in users[:5]:  # Show max 5
                print(f"           - {u['workflow']} -> {u['node']}")
            if len(users) > 5:
                print(f"           ... and {len(users)-5} more")

        # Credentials that exist but aren't used by any active workflow
        used_ids = set(d["cred_id"] for d in workflow_cred_details)
        unused = [c for c in all_creds if c.get("id") not in used_ids]
        if unused:
            print(f"\n{'='*70}")
            print(f"UNUSED CREDENTIALS ({len(unused)} not referenced by any active workflow)")
            print(f"{'='*70}")
            for c in sorted(unused, key=lambda x: x.get("name", "")):
                print(f"  - {c.get('name', 'Unknown')} ({c.get('type', '?')}) [ID: {c.get('id')}]")

        # Missing / problematic credentials
        if missing_creds:
            print(f"\n{'='*70}")
            print(f"MISSING/INACCESSIBLE CREDENTIALS ({len(missing_creds)})")
            print(f"{'='*70}")
            for mc in missing_creds:
                print(f"  PROBLEM: {mc['cred_name']} ({mc['cred_type']})")
                print(f"    Workflow: {mc['workflow']}")
                print(f"    Node: {mc.get('node_name', mc.get('node', 'unknown'))}")
                print(f"    Cred ID: {mc['cred_id']}")
                print()

        # Manual action checklist
        print(f"\n{'='*70}")
        print("MANUAL ACTION CHECKLIST")
        print(f"{'='*70}")
        print("""
The following workflows are DEACTIVATED due to credential sharing issues.
To fix them, share the credential with the "AVM" project in n8n UI:

  n8n UI -> Settings -> Credentials -> [credential name] -> Sharing -> Add "AVM"

1. Business Email Management (g2uPmEBbAEtz9YP4L8utG)
   -> Share: "Gmail AVM Tutorial" (gmailOAuth2, ID: EC2l4faLSdgePOM6)

2. Marketing All Workflows Combined (2extQxrmWCoGgXCp)
   -> Share: "Whatsapp Multi Agent" (airtableTokenApi, ID: CTVAhYlNsJFMX2lE)

3. CRM-01 Hourly Sync (EiuQcBeQG7AVcbYE)
   -> Update Airtable PAT to include table tblLo3smPaM19XXkv (Leads)
   -> Credential: "Whatsapp Multi Agent" (airtableTokenApi, ID: ZyBrcAO6fps7YB3u)

After sharing, reactivate with:
   python tools/deactivate_broken.py --reactivate
""")

        # Save full report
        report = {
            "active_workflows": len(active_wfs),
            "total_credentials": len(all_creds),
            "credentials_in_use": len(unique_creds),
            "unused_credentials": len(unused),
            "missing_credentials": len(missing_creds),
            "details": workflow_cred_details,
        }
        report_path = os.path.join(
            os.path.dirname(__file__), '..', '.tmp', 'credential_audit.json'
        )
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Full report saved to: {report_path}")


if __name__ == "__main__":
    main()

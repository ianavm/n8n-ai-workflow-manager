"""
Transfer a workflow between n8n projects.

Moves a workflow from one project to another while preserving all
credential bindings. Uses PUT /workflows/{id}/transfer endpoint.

Usage:
    python tools/transfer_workflow.py              # Transfer with defaults
    python tools/transfer_workflow.py --dry-run    # Preview only
    python tools/transfer_workflow.py --workflow-id <id> --dest-project "Personal"
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

WORKFLOW_ID = "g2uPmEBbAEtz9YP4L8utG"
DEST_PROJECT_NAME = "Ian Immelman <ian@anyvisionmedia.com>"


def main():
    parser = argparse.ArgumentParser(description="Transfer workflow between n8n projects")
    parser.add_argument("--workflow-id", default=WORKFLOW_ID,
                        help="Workflow ID to transfer")
    parser.add_argument("--dest-project", default=DEST_PROJECT_NAME,
                        help="Destination project name (case-insensitive)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List projects and workflow info without transferring")
    args = parser.parse_args()

    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = config["n8n"]["base_url"].rstrip("/")

    if not api_key:
        print("Error: N8N_API_KEY not found. Add it to .env")
        sys.exit(1)

    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    print("=" * 60)
    print("WORKFLOW PROJECT TRANSFER")
    print("=" * 60)

    with httpx.Client(timeout=30) as client:
        # Step 1: List projects
        print("\n[1/5] Listing projects...")
        resp = client.get(f"{base_url}/api/v1/projects", headers=headers)
        resp.raise_for_status()
        projects_data = resp.json()
        projects = projects_data.get("data", projects_data)
        if not isinstance(projects, list):
            projects = [projects] if projects else []

        for p in projects:
            print(f"  {p['id']:30s}  {p.get('name', 'N/A')!r:30s}  ({p.get('type', 'unknown')})")

        # Find destination project (case-insensitive)
        dest = None
        for p in projects:
            if p.get("name", "").lower() == args.dest_project.lower():
                dest = p
                break

        if not dest:
            print(f"\nError: Project '{args.dest_project}' not found.")
            print("Available projects listed above. Use --dest-project with the correct name.")
            sys.exit(1)

        print(f"\n  Destination: {dest['name']} ({dest['id']})")

        # Step 2: Verify workflow
        print(f"\n[2/5] Fetching workflow {args.workflow_id}...")
        resp = client.get(f"{base_url}/api/v1/workflows/{args.workflow_id}", headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        was_active = wf.get("active", False)
        print(f"  Name: {wf.get('name', 'Unknown')}")
        print(f"  Active: {was_active}")
        print(f"  Nodes: {len(wf.get('nodes', []))}")

        if args.dry_run:
            print("\n[DRY RUN] Would transfer:")
            print(f"  Workflow: {wf.get('name')} ({args.workflow_id})")
            print(f"  To: {dest['name']} ({dest['id']})")
            print("  No changes made.")
            return

        # Step 3: Transfer
        print(f"\n[3/5] Transferring to '{dest['name']}'...")
        resp = client.put(
            f"{base_url}/api/v1/workflows/{args.workflow_id}/transfer",
            headers=headers,
            json={"destinationProjectId": dest["id"]}
        )
        resp.raise_for_status()
        print("  Transfer successful!")

        # Step 4: Verify post-transfer
        print(f"\n[4/5] Verifying transfer...")
        resp = client.get(f"{base_url}/api/v1/workflows/{args.workflow_id}", headers=headers)
        resp.raise_for_status()
        wf_after = resp.json()
        is_active = wf_after.get("active", False)
        print(f"  Active after transfer: {is_active}")

        # Step 5: Reactivate if needed
        if was_active and not is_active:
            print(f"\n[5/5] Reactivating workflow...")
            resp = client.post(
                f"{base_url}/api/v1/workflows/{args.workflow_id}/activate",
                headers=headers
            )
            resp.raise_for_status()
            is_active = True
            print("  Reactivated!")
        else:
            print(f"\n[5/5] No reactivation needed.")

        print("\n" + "=" * 60)
        print("TRANSFER COMPLETE")
        print("=" * 60)
        print(f"  Workflow: {wf.get('name')}")
        print(f"  Destination: {dest['name']}")
        print(f"  Active: {is_active}")
        print(f"  Credentials: Preserved (no changes)")


if __name__ == "__main__":
    main()

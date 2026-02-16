"""
Update workflow to use new Airtable base.

Usage:
    python tools/update_airtable_base.py <base_id> <table_id>

Example:
    python tools/update_airtable_base.py appAbc123Def456 tblXyz789Ghi012
"""

import sys
import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config


def main():
    if len(sys.argv) < 3:
        print("Usage: python tools/update_airtable_base.py <base_id> <table_id>")
        print()
        print("Example:")
        print("  python tools/update_airtable_base.py appAbc123Def456 tblXyz789Ghi012")
        sys.exit(1)

    new_base_id = sys.argv[1]
    new_table_id = sys.argv[2]

    if not new_base_id.startswith('app'):
        print("ERROR: Base ID must start with 'app'")
        sys.exit(1)

    if not new_table_id.startswith('tbl'):
        print("ERROR: Table ID must start with 'tbl'")
        sys.exit(1)

    print("=" * 60)
    print("UPDATING WORKFLOW TO NEW AIRTABLE BASE")
    print("=" * 60)
    print()
    print(f"New Base ID:  {new_base_id}")
    print(f"New Table ID: {new_table_id}")
    print()

    config = load_config()
    client = httpx.Client(
        base_url=config['n8n']['base_url'] + '/api/v1',
        headers={'X-N8N-API-KEY': config['api_keys']['n8n'], 'Content-Type': 'application/json'},
        timeout=30
    )

    # Fetch current workflow
    print("Fetching workflow...")
    resp = client.get('/workflows/uq4hnH0YHfhYOOzO')
    wf = resp.json()
    nodes = wf['nodes']

    # Update all Airtable nodes
    print("Updating Airtable nodes...")
    updated_count = 0

    for n in nodes:
        if n['type'] == 'n8n-nodes-base.airtable':
            # Update base reference
            if 'base' in n['parameters']:
                n['parameters']['base']['value'] = new_base_id
                n['parameters']['base']['cachedResultName'] = 'Lead Scraper - Fourways CRM'

            # Update table reference
            if 'table' in n['parameters']:
                n['parameters']['table']['value'] = new_table_id
                n['parameters']['table']['cachedResultName'] = 'Leads'

            updated_count += 1
            print(f"  ✓ {n['name']}")

    print(f"\nUpdated {updated_count} Airtable nodes")

    # Deploy
    print("\nDeploying updated workflow...")
    payload = {
        "name": wf['name'],
        "nodes": nodes,
        "connections": wf['connections'],
        "settings": {"executionOrder": "v1"}
    }

    resp = client.put('/workflows/uq4hnH0YHfhYOOzO', json=payload)

    if resp.status_code == 200:
        print("✓ Deployment successful!")
        print()
        print("=" * 60)
        print("UPDATE COMPLETE")
        print("=" * 60)
        print()
        print("Your workflow now uses the new dedicated Airtable base:")
        print(f"  Base: https://airtable.com/{new_base_id}")
        print(f"  Table: {new_table_id}")
        print()
        print("Next steps:")
        print("  1. Open n8n workflow and verify Airtable nodes show correct base")
        print("  2. Run a test (set maxResults to 5, click 'Test workflow')")
        print("  3. Check your new Airtable base for data")
    else:
        print(f"✗ Deployment failed: {resp.status_code}")
        print(resp.text[:500])

    client.close()


if __name__ == "__main__":
    main()

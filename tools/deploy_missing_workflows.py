"""Deploy the 7 missing workflows to n8n and transfer to AVM project."""
import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

API_KEY = os.getenv('N8N_API_KEY')
BASE_URL = os.getenv('N8N_BASE_URL', 'https://ianimmelman89.app.n8n.cloud')
HEADERS = {'X-N8N-API-KEY': API_KEY, 'Content-Type': 'application/json'}
AVM_PROJECT_ID = 'X8YS2aPAoXgAHLmS'

WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__), '..', 'workflows')

MISSING = [
    ('client-relations', 'cr01_client_health_scorer.json'),
    ('support-agent', 'sup01_ticket_creator.json'),
    ('whatsapp-agent', 'wa02_crm_sync.json'),
    ('whatsapp-agent', 'wa03_issue_detector.json'),
    ('intelligence', 'intel03_prompt_tracker.json'),
    ('optimization', 'opt02_ab_test_analyzer.json'),
    ('optimization', 'opt03_churn_predictor.json'),
]


def deploy_workflow(dept, filename):
    filepath = os.path.join(WORKFLOWS_DIR, dept, filename)
    with open(filepath) as f:
        wf_data = json.load(f)

    # Create workflow
    body = {
        'name': wf_data.get('name', filename.replace('.json', '')),
        'nodes': wf_data.get('nodes', []),
        'connections': wf_data.get('connections', {}),
        'settings': wf_data.get('settings', {}),
    }

    r = httpx.post(f'{BASE_URL}/api/v1/workflows', headers=HEADERS, json=body, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  ERROR creating: {r.status_code} - {r.text[:200]}")
        return None

    wf_id = r.json()['id']
    print(f"  Created: {wf_id}")

    # Transfer to AVM project
    tr = httpx.put(
        f'{BASE_URL}/api/v1/workflows/{wf_id}/transfer',
        headers=HEADERS,
        json={'destinationProjectId': AVM_PROJECT_ID},
        timeout=30
    )
    if tr.status_code == 200:
        print(f"  Transferred to AVM project")
    else:
        print(f"  Transfer failed: {tr.status_code} - {tr.text[:200]}")

    return wf_id


def main():
    deployed = []
    for dept, filename in MISSING:
        label = filename.replace('.json', '')
        print(f"\n=== {label} ({dept}) ===")
        wf_id = deploy_workflow(dept, filename)
        if wf_id:
            deployed.append((label, wf_id))

    print(f"\n--- Deployed {len(deployed)}/{len(MISSING)} workflows ---")
    for label, wf_id in deployed:
        print(f"  {label}: {wf_id}")


if __name__ == '__main__':
    main()

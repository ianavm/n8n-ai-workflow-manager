"""Reconnect mock Code nodes back to real Airtable nodes.

Now that Operations Control and Support tables are provisioned,
convert the mock Code nodes back to proper Airtable nodes.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from n8n_client import N8nClient

ORCH_BASE = os.getenv('ORCH_AIRTABLE_BASE_ID')
SUPPORT_BASE = os.getenv('SUPPORT_AIRTABLE_BASE_ID')
CRED_AIRTABLE = 'K8t2NtJ89DLLh64j'

# Node name pattern -> (base_id, table_id, operation)
NODE_TABLE_MAP = {
    # Orchestrator - Agent Registry
    'Update Registry': (ORCH_BASE, os.getenv('ORCH_TABLE_AGENT_REGISTRY'), 'update'),
    'Update Agent KPIs': (ORCH_BASE, os.getenv('ORCH_TABLE_AGENT_REGISTRY'), 'update'),
    'Read Agent Registry': (ORCH_BASE, os.getenv('ORCH_TABLE_AGENT_REGISTRY'), 'search'),
    # Orchestrator - Events
    'Log Event': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Log OK Status': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Log to Orchestrator': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Log KPI Event': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Log Clean Scan': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Log Health Score Event': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Log Renewal Event': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Log Onboarding Event': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Log Pulse Event': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Log Ticket Event': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Log KB Build Event': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Create Churn Event': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    'Create AB Test': (ORCH_BASE, os.getenv('ORCH_TABLE_EVENTS'), 'create'),
    # Orchestrator - Decision Log
    'Log Auto Fix': (ORCH_BASE, os.getenv('ORCH_TABLE_DECISION_LOG'), 'create'),
    'Log Decision': (ORCH_BASE, os.getenv('ORCH_TABLE_DECISION_LOG'), 'create'),
    'Read Decisions': (ORCH_BASE, os.getenv('ORCH_TABLE_DECISION_LOG'), 'search'),
    'Read Decision Log': (ORCH_BASE, os.getenv('ORCH_TABLE_DECISION_LOG'), 'search'),
    # Orchestrator - Escalation Queue
    'Create Escalation': (ORCH_BASE, os.getenv('ORCH_TABLE_ESCALATION_QUEUE'), 'create'),
    'Escalate At-Risk': (ORCH_BASE, os.getenv('ORCH_TABLE_ESCALATION_QUEUE'), 'create'),
    'Escalate SLA Breach': (ORCH_BASE, os.getenv('ORCH_TABLE_ESCALATION_QUEUE'), 'create'),
    'Read Escalations': (ORCH_BASE, os.getenv('ORCH_TABLE_ESCALATION_QUEUE'), 'search'),
    'Read Escalation Queue': (ORCH_BASE, os.getenv('ORCH_TABLE_ESCALATION_QUEUE'), 'search'),
    # Orchestrator - KPI Snapshots
    'Write KPI Snapshots': (ORCH_BASE, os.getenv('ORCH_TABLE_KPI_SNAPSHOTS'), 'create'),
    'Read KPI History': (ORCH_BASE, os.getenv('ORCH_TABLE_KPI_SNAPSHOTS'), 'search'),
    'Read KPI Snapshots': (ORCH_BASE, os.getenv('ORCH_TABLE_KPI_SNAPSHOTS'), 'search'),
    # Support - Tickets
    'Create Ticket': (SUPPORT_BASE, os.getenv('SUPPORT_TABLE_TICKETS'), 'create'),
    'Create Support Ticket': (SUPPORT_BASE, os.getenv('SUPPORT_TABLE_TICKETS'), 'create'),
    'Read Open Tickets': (SUPPORT_BASE, os.getenv('SUPPORT_TABLE_TICKETS'), 'search'),
    'Update Ticket Resolved': (SUPPORT_BASE, os.getenv('SUPPORT_TABLE_TICKETS'), 'update'),
    'Update Ticket Draft': (SUPPORT_BASE, os.getenv('SUPPORT_TABLE_TICKETS'), 'update'),
    'Read Resolved Tickets': (SUPPORT_BASE, os.getenv('SUPPORT_TABLE_TICKETS'), 'search'),
    # Support - Knowledge Base
    'Create KB Articles': (SUPPORT_BASE, os.getenv('SUPPORT_TABLE_KNOWLEDGE_BASE'), 'create'),
    'Search Knowledge Base': (SUPPORT_BASE, os.getenv('SUPPORT_TABLE_KNOWLEDGE_BASE'), 'search'),
    # Support - SLA Config
    'Read SLA Config': (SUPPORT_BASE, os.getenv('SUPPORT_TABLE_SLA_CONFIG'), 'search'),
}

AVM_IDS = {
    '5XR7j7hQ8cdWpi1e': 'ORCH-01', '47CJmRKTh9kPZ7u5': 'ORCH-02',
    'JDrgcv5iNIXLyQfs': 'ORCH-03', '2gXlFqBtOoReQfaT': 'ORCH-04',
    'Ns8pI1OowMbNDfUV': 'MKT-05', 'UKIxkygJgJQ245pM': 'MKT-06',
    '3Gb4pWJhsf2aHhsW': 'FIN-08', '6bo7BSssN6SQeodg': 'FIN-09',
    '330wVSlaVBtoKwV1': 'CONTENT-01', 'dSAt6zYsfLy1e6tH': 'CONTENT-02',
    '5Qzbyar2VTIbAuEo': 'CR-01', '3ZzWEUmgVNIxNmx3': 'CR-02',
    'e1ufCH2KvuvrBQPm': 'CR-03', 'fOygygjEdwAyf5of': 'CR-04',
    'Pk0B97gW8xtcgHBf': 'SUP-01', 'EnnsJg43EazmEHJl': 'SUP-02',
    'HnmuFSsdx7hasPcI': 'SUP-03', '3CQqDNDtgLJi2ZUu': 'SUP-04',
    'YBxMfFdFb7BCUxzi': 'WA-01', 'twe45qwa4Kwalzdx': 'WA-02',
    '6C9PPWe4IWoUhjq2': 'WA-03',
    'P9NgW8csqbCh817f': 'INTEL-01', 'Fmut5pJ4fVXIfxke': 'INTEL-02',
    'hSiIZJu5bgDIOCDO': 'INTEL-03',
    'Rsyz1BHai3q94wPI': 'OPT-01', 'I37U9l1kOcsr8fpP': 'OPT-02',
    'TPp402GuDxnruRd2': 'OPT-03',
}


def convert_to_airtable(node, base_id, table_id, operation):
    """Convert a mock Code node back to a real Airtable node."""
    node['type'] = 'n8n-nodes-base.airtable'
    node['typeVersion'] = 2.1

    if operation == 'create':
        node['parameters'] = {
            'operation': 'create',
            'base': {'__rl': True, 'value': base_id, 'mode': 'id'},
            'table': {'__rl': True, 'value': table_id, 'mode': 'id'},
            'columns': {
                'mappingMode': 'autoMapInputData',
                'value': {}
            },
            'options': {}
        }
    elif operation == 'search':
        node['parameters'] = {
            'operation': 'search',
            'base': {'__rl': True, 'value': base_id, 'mode': 'id'},
            'table': {'__rl': True, 'value': table_id, 'mode': 'id'},
            'options': {}
        }
        node['alwaysOutputData'] = True
    elif operation == 'update':
        node['parameters'] = {
            'operation': 'update',
            'base': {'__rl': True, 'value': base_id, 'mode': 'id'},
            'table': {'__rl': True, 'value': table_id, 'mode': 'id'},
            'columns': {
                'mappingMode': 'autoMapInputData',
                'value': {}
            },
            'options': {}
        }

    node['credentials'] = {
        'airtableTokenApi': {
            'id': CRED_AIRTABLE,
            'name': 'Airtable Personal Access Token account'
        }
    }
    node['onError'] = 'continueRegularOutput'
    node['continueOnFail'] = True


def main():
    base_url = os.getenv('N8N_BASE_URL', 'https://ianimmelman89.app.n8n.cloud')
    api_key = os.getenv('N8N_API_KEY')
    if not api_key:
        print('ERROR: N8N_API_KEY not set')
        sys.exit(1)
    client = N8nClient(base_url=base_url, api_key=api_key)

    total_reconnected = 0
    wf_count = 0

    for wf_id, label in AVM_IDS.items():
        try:
            wf = client.get_workflow(wf_id)
        except Exception as e:
            print(f'SKIP {label}: {e}')
            continue

        nodes = wf['nodes']
        reconnected = 0

        for node in nodes:
            if node.get('type') != 'n8n-nodes-base.code':
                continue
            js = node.get('parameters', {}).get('jsCode', '')
            if '_mock' not in js:
                continue

            name = node['name']
            matched_key = None
            for pattern in NODE_TABLE_MAP:
                if pattern in name:
                    matched_key = pattern
                    break

            if not matched_key:
                continue

            base_id, table_id, operation = NODE_TABLE_MAP[matched_key]
            if not table_id:
                continue

            convert_to_airtable(node, base_id, table_id, operation)
            reconnected += 1

        if reconnected > 0:
            try:
                result = client.update_workflow(wf_id, {
                    'name': wf['name'],
                    'nodes': nodes,
                    'connections': wf['connections'],
                    'settings': wf.get('settings', {}),
                    'staticData': wf.get('staticData'),
                })
                print(f'{label}: {reconnected} nodes reconnected')
                total_reconnected += reconnected
                wf_count += 1
            except Exception as e:
                print(f'ERROR {label}: {e}')

    print(f'\nDONE: {total_reconnected} nodes reconnected across {wf_count} workflows')


if __name__ == '__main__':
    main()

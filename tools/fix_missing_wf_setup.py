"""Fix placeholders and add manual triggers in newly deployed workflows."""
import httpx
import os
import json
import uuid
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

API_KEY = os.getenv('N8N_API_KEY')
BASE_URL = os.getenv('N8N_BASE_URL', 'https://ianimmelman89.app.n8n.cloud')
HEADERS = {'X-N8N-API-KEY': API_KEY, 'Content-Type': 'application/json'}

# Airtable IDs from .env
ORCH_BASE = os.getenv('ORCH_AIRTABLE_BASE_ID', 'appTCh0EeXQp0XqzW')
ORCH_TABLES = {
    'Agent_Registry': os.getenv('ORCH_TABLE_AGENT_REGISTRY', 'tblPeQM1c3DBIIzAO'),
    'Events': os.getenv('ORCH_TABLE_EVENTS', 'tblgHAw52EyUcIkWR'),
    'KPI_Snapshots': os.getenv('ORCH_TABLE_KPI_SNAPSHOTS', 'tblwCC1ERhxI44pqI'),
    'Escalation_Queue': os.getenv('ORCH_TABLE_ESCALATION_QUEUE', 'tblGXY0wS2Z5lwq1K'),
    'Decision_Log': os.getenv('ORCH_TABLE_DECISION_LOG', 'tblbhoiCQQDAs6igp'),
}

# Support Airtable - check if we have these
SUPPORT_BASE = os.getenv('SUPPORT_AIRTABLE_BASE_ID', '')
SUPPORT_TABLES = {
    'Tickets': os.getenv('SUPPORT_TABLE_TICKETS', ''),
    'Knowledge_Base': os.getenv('SUPPORT_TABLE_KB', ''),
    'SLA_Config': os.getenv('SUPPORT_TABLE_SLA', ''),
}


def get_workflow(wf_id):
    r = httpx.get(f'{BASE_URL}/api/v1/workflows/{wf_id}', headers=HEADERS)
    return r.json()


def put_workflow(wf_id, wf):
    body = {k: wf[k] for k in ['name', 'nodes', 'connections', 'settings'] if k in wf}
    r = httpx.put(f'{BASE_URL}/api/v1/workflows/{wf_id}', headers=HEADERS, json=body, timeout=30)
    return r.status_code == 200


def fix_placeholders(wf):
    """Replace REPLACE_AFTER_SETUP with real Airtable IDs based on node context."""
    wf_str = json.dumps(wf)
    if 'REPLACE_AFTER_SETUP' not in wf_str:
        return wf, 0

    count = 0
    for node in wf['nodes']:
        params = node.get('parameters', {})

        # Fix base ID
        if params.get('base') == 'REPLACE_AFTER_SETUP':
            # Determine which base based on workflow name
            wf_name = wf.get('name', '').lower()
            if 'support' in wf_name or 'sup' in wf_name or 'ticket' in wf_name:
                params['base'] = SUPPORT_BASE or ORCH_BASE  # Fallback to Orch base
            elif 'wa-' in wf_name or 'whatsapp' in wf_name:
                params['base'] = ORCH_BASE  # WhatsApp agents use Operations Control
            else:
                params['base'] = ORCH_BASE
            count += 1

        # Fix table ID
        if params.get('table') == 'REPLACE_AFTER_SETUP':
            node_name = node.get('name', '').lower()
            if 'ticket' in node_name:
                params['table'] = SUPPORT_TABLES.get('Tickets') or ORCH_TABLES['Events']
            elif 'knowledge' in node_name or 'kb' in node_name:
                params['table'] = SUPPORT_TABLES.get('Knowledge_Base') or ORCH_TABLES['Decision_Log']
            elif 'sla' in node_name:
                params['table'] = SUPPORT_TABLES.get('SLA_Config') or ORCH_TABLES['Agent_Registry']
            elif 'escalat' in node_name:
                params['table'] = ORCH_TABLES['Escalation_Queue']
            elif 'event' in node_name or 'log' in node_name:
                params['table'] = ORCH_TABLES['Events']
            elif 'decision' in node_name:
                params['table'] = ORCH_TABLES['Decision_Log']
            elif 'agent' in node_name or 'registry' in node_name:
                params['table'] = ORCH_TABLES['Agent_Registry']
            elif 'kpi' in node_name or 'snapshot' in node_name:
                params['table'] = ORCH_TABLES['KPI_Snapshots']
            else:
                params['table'] = ORCH_TABLES['Events']
            count += 1

    # Also check for REPLACE in HTTP request headers/URLs (like WA-02 Supabase)
    wf_str2 = json.dumps(wf)
    if 'REPLACE_AFTER_SETUP' in wf_str2:
        supabase_url = os.getenv('SUPABASE_URL', 'https://your-project.supabase.co')
        supabase_key = os.getenv('SUPABASE_ANON_KEY', os.getenv('SUPABASE_KEY', ''))
        wf_str2 = wf_str2.replace('REPLACE_AFTER_SETUP_SUPABASE_URL', supabase_url)
        wf_str2 = wf_str2.replace('REPLACE_AFTER_SETUP_SUPABASE_KEY', supabase_key)
        wf_str2 = wf_str2.replace('REPLACE_AFTER_SETUP', ORCH_BASE)
        wf = json.loads(wf_str2)
        count += 1

    return wf, count


def add_manual_trigger(wf):
    """Add a Manual Trigger node connected to the first downstream node."""
    nodes = wf['nodes']
    connections = wf['connections']

    # Find existing trigger nodes
    triggers = [n for n in nodes if 'trigger' in n['type'].lower() or 'webhook' in n['type'].lower()]
    schedule_triggers = [t for t in triggers if 'schedule' in t['type'].lower()]
    webhook_triggers = [t for t in triggers if 'webhook' == t['type'].split('.')[-1]]

    # Check if manual trigger already exists
    if any('manual' in t['type'].lower() for t in triggers):
        return wf, False

    # Find what the primary trigger connects to
    primary_trigger = schedule_triggers[0] if schedule_triggers else (webhook_triggers[0] if webhook_triggers else None)
    if not primary_trigger:
        print("    No trigger found to wire manual trigger to")
        return wf, False

    trigger_name = primary_trigger['name']
    trigger_conns = connections.get(trigger_name, {})
    if not trigger_conns:
        # Find first non-trigger, non-error node
        non_triggers = [n for n in nodes if 'trigger' not in n['type'].lower()
                       and 'webhook' not in n['type'].lower()
                       and 'error' not in n['type'].lower()
                       and 'respondToWebhook' not in n['type']]
        if non_triggers:
            target_name = non_triggers[0]['name']
        else:
            print("    No target node found")
            return wf, False
    else:
        # Get the first connected node
        main_output = trigger_conns.get('main', [[]])
        if main_output and main_output[0]:
            target_name = main_output[0][0].get('node', '')
        else:
            print("    Trigger has no connections")
            return wf, False

    # Position manual trigger above the primary trigger
    pos = primary_trigger['position']
    manual_pos = [pos[0], pos[1] - 160]

    manual_node = {
        'parameters': {},
        'id': str(uuid.uuid4()),
        'name': 'Manual Trigger',
        'type': 'n8n-nodes-base.manualTrigger',
        'typeVersion': 1,
        'position': manual_pos,
    }

    nodes.append(manual_node)
    connections['Manual Trigger'] = {
        'main': [[{'node': target_name, 'type': 'main', 'index': 0}]]
    }

    return wf, True


def main():
    workflows = {
        'SUP-01': 'Pk0B97gW8xtcgHBf',
        'WA-02': 'phF5vteIF4y6Tevt',
        'WA-03': '6C9PPWe4IWoUhjq2',
        'INTEL-03': 'hSiIZJu5bgDIOCDO',
        'OPT-02': 'I37U9l1kOcsr8fpP',
        'OPT-03': 'TPp402GuDxnruRd2',
    }

    for name, wf_id in workflows.items():
        print(f"\n=== {name} ({wf_id}) ===")
        wf = get_workflow(wf_id)

        # Fix placeholders
        wf, placeholder_fixes = fix_placeholders(wf)
        if placeholder_fixes:
            print(f"  Fixed {placeholder_fixes} placeholder(s)")

        # Add manual trigger
        wf, added = add_manual_trigger(wf)
        if added:
            print(f"  Added Manual Trigger")
        else:
            print(f"  Manual trigger: skipped (already exists or no target)")

        # Save
        if placeholder_fixes or added:
            ok = put_workflow(wf_id, wf)
            print(f"  Save: {'OK' if ok else 'FAILED'}")
        else:
            print(f"  No changes needed")


if __name__ == '__main__':
    main()

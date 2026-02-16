"""
AI node manager for n8n workflows.

Scans, analyzes, and optimizes AI-specific nodes across n8n workflows.
Provides prompt analysis, cost estimation, model recommendations,
and security auditing for AI components.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

AI_NODE_TYPES = {
    '@n8n/n8n-nodes-langchain.openAi',
    '@n8n/n8n-nodes-langchain.lmChatOpenAi',
    '@n8n/n8n-nodes-langchain.lmChatAnthropic',
    '@n8n/n8n-nodes-langchain.agent',
    '@n8n/n8n-nodes-langchain.chainLlm',
    '@n8n/n8n-nodes-langchain.chainSummarization',
    '@n8n/n8n-nodes-langchain.memoryBufferWindow',
    '@n8n/n8n-nodes-langchain.vectorStoreInMemory',
    '@n8n/n8n-nodes-langchain.vectorStorePinecone',
    'n8n-nodes-base.openAi',
    'n8n-nodes-base.httpRequest',
}


class AINodeManager:
    """Manages and optimizes AI nodes in n8n workflows."""

    def __init__(self, n8n_client):
        self.client = n8n_client

    def scan_ai_nodes(self, workflow_id=None):
        print("\nScanning for AI nodes...")

        if workflow_id:
            workflows = [self.client.get_workflow(workflow_id)]
        else:
            workflows = self.client.list_workflows(use_cache=False)

        ai_nodes = []
        for wf in workflows:
            wf_id = wf.get('id', '')
            wf_name = wf.get('name', 'Unknown')
            nodes = wf.get('nodes', [])

            for node in nodes:
                node_type = node.get('type', '')
                is_ai_node = node_type in AI_NODE_TYPES

                if node_type == 'n8n-nodes-base.httpRequest':
                    url = str(node.get('parameters', {}).get('url', ''))
                    if any(api in url.lower() for api in ['openai', 'anthropic', 'openrouter', 'cohere']):
                        is_ai_node = True

                if node_type == 'n8n-nodes-base.code':
                    code = str(node.get('parameters', {}).get('jsCode', ''))
                    code += str(node.get('parameters', {}).get('pythonCode', ''))
                    if any(p in code.lower() for p in ['openai', 'anthropic', 'gpt-', 'claude', 'chat/completions']):
                        is_ai_node = True

                if is_ai_node:
                    ai_nodes.append({
                        'workflow_id': wf_id, 'workflow_name': wf_name,
                        'node_name': node.get('name', 'Unknown'),
                        'node_type': node_type,
                        'parameters': node.get('parameters', {}),
                    })

        print(f"  Found {len(ai_nodes)} AI nodes across {len(workflows)} workflows")
        return ai_nodes

    def analyze_prompt_quality(self, ai_nodes):
        results = []
        for node in ai_nodes:
            params = node.get('parameters', {})
            for key in ['systemMessage', 'instructions', 'text', 'prompt', 'systemPrompt']:
                value = params.get(key, '')
                if isinstance(value, str) and len(value) > 10:
                    analysis = {
                        'workflow_name': node['workflow_name'],
                        'node_name': node['node_name'],
                        'prompt_field': key,
                        'char_count': len(value),
                        'has_persona': any(w in value.lower() for w in ['you are', 'act as', 'your role']),
                        'has_output_format': any(w in value.lower() for w in ['json', 'format', 'output']),
                        'has_examples': any(w in value.lower() for w in ['example', 'e.g.']),
                        'has_constraints': any(w in value.lower() for w in ['do not', 'never', 'always', 'must']),
                    }
                    score = sum(25 for k in ['has_persona', 'has_output_format', 'has_examples', 'has_constraints'] if analysis[k])
                    analysis['quality_score'] = score
                    results.append(analysis)
        return results

    def estimate_ai_costs(self, ai_nodes, executions_per_day=100):
        model_costs = {
            'gpt-4o': {'input': 0.005, 'output': 0.015},
            'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
            'claude-3-sonnet': {'input': 0.003, 'output': 0.015},
            'claude-3-haiku': {'input': 0.00025, 'output': 0.00125},
            'default': {'input': 0.003, 'output': 0.015},
        }

        total_daily = 0
        breakdown = []
        for node in ai_nodes:
            params = node.get('parameters', {})
            model = str(params.get('model', params.get('modelId', 'default')))
            cost_tier = model_costs.get('default')
            for key, costs in model_costs.items():
                if key in model.lower():
                    cost_tier = costs
                    break

            prompt_text = str(params.get('systemMessage', '')) + str(params.get('text', ''))
            est_input = len(prompt_text.split()) * 1.3
            cost = (est_input / 1000) * cost_tier['input'] + 0.5 * cost_tier['output']
            daily = cost * executions_per_day
            total_daily += daily

            breakdown.append({
                'workflow_name': node['workflow_name'], 'node_name': node['node_name'],
                'model': model, 'est_daily_cost': round(daily, 2),
            })

        return {
            'total_daily_estimate': round(total_daily, 2),
            'total_monthly_estimate': round(total_daily * 30, 2),
            'executions_per_day': executions_per_day,
            'node_breakdown': sorted(breakdown, key=lambda x: x['est_daily_cost'], reverse=True),
        }

    def audit_ai_security(self, ai_nodes):
        findings = []
        for node in ai_nodes:
            params = node.get('parameters', {})
            if not params.get('maxTokens') and not params.get('max_tokens'):
                findings.append({
                    'workflow_name': node['workflow_name'], 'node_name': node['node_name'],
                    'severity': 'low', 'issue': 'No max token limit set',
                })
        return findings

    def save_audit_results(self, data, output_path):
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n  AI audit saved to: {output_file}")


def main():
    from config_loader import load_config
    from n8n_client import N8nClient

    try:
        config = load_config()
        api_key = config['api_keys']['n8n']
        if not api_key:
            print("Error: N8N_API_KEY not found.")
            sys.exit(1)

        with N8nClient(config['n8n']['base_url'], api_key,
                       timeout=config['n8n'].get('timeout_seconds', 30),
                       cache_dir=config['paths']['cache_dir']) as client:

            manager = AINodeManager(client)
            ai_nodes = manager.scan_ai_nodes()

            if not ai_nodes:
                print("\nNo AI nodes found.")
                return

            prompts = manager.analyze_prompt_quality(ai_nodes)
            costs = manager.estimate_ai_costs(ai_nodes)
            security = manager.audit_ai_security(ai_nodes)

            print(f"\n{'=' * 50}")
            print("AI NODE AUDIT REPORT")
            print(f"{'=' * 50}")
            print(f"AI Nodes: {len(ai_nodes)}")
            print(f"Workflows with AI: {len(set(n['workflow_name'] for n in ai_nodes))}")

            print(f"\nCost Estimate ({costs['executions_per_day']} exec/day):")
            print(f"  Daily:   ${costs['total_daily_estimate']:.2f}")
            print(f"  Monthly: ${costs['total_monthly_estimate']:.2f}")

            if security:
                print(f"\nSecurity Findings: {len(security)}")

            tmp_dir = Path(config['paths']['tmp_dir'])
            manager.save_audit_results({
                'generated_at': datetime.now().isoformat(),
                'ai_nodes': ai_nodes, 'prompt_analysis': prompts,
                'cost_estimate': costs, 'security_findings': security,
            }, str(tmp_dir / "ai_audit_results.json"))

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

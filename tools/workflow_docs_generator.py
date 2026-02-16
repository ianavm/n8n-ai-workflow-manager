"""
n8n workflow documentation generator.

Auto-generates markdown documentation from n8n workflow JSON definitions.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


class WorkflowDocsGenerator:
    """Auto-generates documentation from n8n workflow JSON definitions."""

    def __init__(self, n8n_client):
        self.client = n8n_client

    def generate_workflow_doc(self, workflow):
        name = workflow.get('name', 'Unknown Workflow')
        wf_id = workflow.get('id', 'N/A')
        active = workflow.get('active', False)
        nodes = workflow.get('nodes', [])
        connections = workflow.get('connections', {})
        created = workflow.get('createdAt', '')
        updated = workflow.get('updatedAt', '')

        triggers = [n for n in nodes if 'trigger' in n.get('type', '').lower()]
        ai_nodes = [n for n in nodes if 'langchain' in n.get('type', '').lower() or 'openai' in n.get('type', '').lower()]

        doc = f"# {name}\n\n"
        doc += f"**ID:** {wf_id} | **Status:** {'Active' if active else 'Inactive'} | **Nodes:** {len(nodes)}\n"
        doc += f"**Created:** {created[:10] if created else 'N/A'} | **Updated:** {updated[:10] if updated else 'N/A'}\n\n"

        doc += "## Triggers\n\n"
        for t in (triggers or [{'name': 'Manual', 'type': 'manual'}]):
            doc += f"- **{t.get('name', 'Unknown')}** (`{t.get('type', '')}`)\n"

        doc += "\n## Node Inventory\n\n| # | Node | Type |\n|---|------|------|\n"
        for i, node in enumerate(nodes, 1):
            doc += f"| {i} | {node.get('name', '?')} | {node.get('type', '').split('.')[-1]} |\n"

        if ai_nodes:
            doc += "\n## AI Components\n\n"
            for node in ai_nodes:
                params = node.get('parameters', {})
                doc += f"- **{node.get('name')}**: model=`{params.get('model', 'N/A')}`\n"

        doc += "\n## Data Flow\n\n```mermaid\ngraph LR\n"
        for src, targets in connections.items():
            for conn_type, conn_list in targets.items():
                for arr in conn_list:
                    for conn in arr:
                        doc += f"    {src.replace(' ', '_')} --> {conn.get('node', '?').replace(' ', '_')}\n"
        doc += "```\n"

        doc += f"\n---\n*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
        return doc

    def generate_full_catalog(self, workflows=None):
        if workflows is None:
            workflows = self.client.list_workflows(use_cache=False)

        active = [w for w in workflows if w.get('active')]
        inactive = [w for w in workflows if not w.get('active')]

        doc = f"# n8n Workflow Catalog\n\n"
        doc += f"**Generated:** {datetime.now().strftime('%Y-%m-%d')} | "
        doc += f"**Total:** {len(workflows)} | **Active:** {len(active)} | **Inactive:** {len(inactive)}\n\n"

        doc += "## Active Workflows\n\n| # | Name | ID | Nodes |\n|---|------|----|-------|\n"
        for i, wf in enumerate(active, 1):
            doc += f"| {i} | {wf.get('name', '?')[:50]} | {wf.get('id', '')} | {len(wf.get('nodes', []))} |\n"

        doc += "\n## Inactive Workflows\n\n| # | Name | ID | Nodes |\n|---|------|----|-------|\n"
        for i, wf in enumerate(inactive, 1):
            doc += f"| {i} | {wf.get('name', '?')[:50]} | {wf.get('id', '')} | {len(wf.get('nodes', []))} |\n"

        return doc

    def save_documentation(self, doc_content, output_path):
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(doc_content)
        print(f"  Saved: {output_file}")


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

            gen = WorkflowDocsGenerator(client)
            workflows = client.list_workflows(use_cache=False)

            # Catalog
            print("\nGenerating catalog...")
            catalog = gen.generate_full_catalog(workflows)
            tmp_dir = Path(config['paths']['tmp_dir'])
            gen.save_documentation(catalog, str(tmp_dir / "workflow_catalog.md"))

            # Individual docs
            active = [w for w in workflows if w.get('active')]
            print(f"Documenting {len(active)} active workflows...")
            docs_dir = tmp_dir / "workflow_docs"

            for wf in active:
                try:
                    full_wf = client.get_workflow(wf['id'])
                    doc = gen.generate_workflow_doc(full_wf)
                    safe_name = wf.get('name', 'unnamed').replace(' ', '_').replace('/', '_')[:50]
                    gen.save_documentation(doc, str(docs_dir / f"{safe_name}.md"))
                except Exception as e:
                    print(f"  Failed: {wf.get('name')}: {e}")

            print(f"\n  Documentation complete! ({len(active)} workflows)")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

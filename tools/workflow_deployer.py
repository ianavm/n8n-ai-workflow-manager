"""
n8n workflow deployer.

Deploys, exports, activates, deactivates, and manages
n8n workflow lifecycle. Handles import from JSON files,
batch operations, and version comparison.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


class WorkflowDeployer:
    """Deploys and manages n8n workflow lifecycle."""

    def __init__(self, n8n_client):
        """
        Initialize workflow deployer.

        Args:
            n8n_client: Initialized N8nClient instance
        """
        self.client = n8n_client

    def deploy_from_file(self, json_path: str, activate: bool = False) -> Dict[str, Any]:
        """
        Deploy a workflow from a local JSON file.

        Args:
            json_path: Path to workflow JSON file
            activate: Whether to activate after deployment

        Returns:
            Created workflow dictionary
        """
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {json_path}")

        print(f"\nDeploying workflow from: {path.name}")

        with open(path, 'r', encoding='utf-8') as f:
            workflow_data = json.load(f)

        # Remove ID to create as new
        workflow_data.pop('id', None)

        result = self.client.create_workflow(workflow_data)

        if activate and result.get('id'):
            self.client.activate_workflow(result['id'])

        print(f"  Deployed: {result.get('name', 'Unknown')} (ID: {result.get('id')})")
        return result

    def export_workflow(self, workflow_id: str, output_path: str) -> str:
        """
        Export a workflow from n8n to a local JSON file.

        Args:
            workflow_id: Workflow ID to export
            output_path: Path to save JSON file

        Returns:
            Output file path
        """
        workflow = self.client.get_workflow(workflow_id)

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(workflow, f, indent=2, ensure_ascii=False)

        name = workflow.get('name', 'Unknown')
        print(f"  Exported: {name} -> {output_file}")
        return str(output_file)

    def export_all_workflows(self, output_dir: str) -> List[str]:
        """
        Export all workflows to a directory.

        Args:
            output_dir: Directory to save workflow JSON files

        Returns:
            List of exported file paths
        """
        workflows = self.client.list_workflows(use_cache=False)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        exported = []
        for wf in workflows:
            wf_id = wf.get('id')
            wf_name = wf.get('name', 'unnamed').replace(' ', '_').replace('/', '_')[:50]
            filename = f"{wf_id}_{wf_name}.json"

            try:
                path = self.export_workflow(wf_id, str(output_path / filename))
                exported.append(path)
            except Exception as e:
                print(f"  Failed to export {wf_name}: {e}")

        print(f"\n  Exported {len(exported)}/{len(workflows)} workflows")
        return exported

    def batch_activate(self, workflow_ids: List[str]) -> Dict[str, Any]:
        """
        Activate multiple workflows.

        Args:
            workflow_ids: List of workflow IDs

        Returns:
            Results dictionary
        """
        results = {'activated': [], 'failed': []}

        for wf_id in workflow_ids:
            try:
                self.client.activate_workflow(wf_id)
                results['activated'].append(wf_id)
            except Exception as e:
                results['failed'].append({'id': wf_id, 'error': str(e)})

        print(f"\n  Activated: {len(results['activated'])}, Failed: {len(results['failed'])}")
        return results

    def batch_deactivate(self, workflow_ids: List[str]) -> Dict[str, Any]:
        """
        Deactivate multiple workflows.

        Args:
            workflow_ids: List of workflow IDs

        Returns:
            Results dictionary
        """
        results = {'deactivated': [], 'failed': []}

        for wf_id in workflow_ids:
            try:
                self.client.deactivate_workflow(wf_id)
                results['deactivated'].append(wf_id)
            except Exception as e:
                results['failed'].append({'id': wf_id, 'error': str(e)})

        print(f"\n  Deactivated: {len(results['deactivated'])}, Failed: {len(results['failed'])}")
        return results

    def compare_versions(self, workflow_id: str, local_path: str) -> Dict[str, Any]:
        """
        Compare a deployed workflow with a local JSON file.

        Args:
            workflow_id: Deployed workflow ID
            local_path: Path to local workflow JSON

        Returns:
            Comparison results
        """
        try:
            from deepdiff import DeepDiff
        except ImportError:
            return {'error': 'deepdiff not installed. Run: pip install deepdiff'}

        deployed = self.client.get_workflow(workflow_id)

        with open(local_path, 'r', encoding='utf-8') as f:
            local = json.load(f)

        # Exclude metadata fields from comparison
        exclude_keys = {'id', 'createdAt', 'updatedAt', 'versionId', 'active'}
        for key in exclude_keys:
            deployed.pop(key, None)
            local.pop(key, None)

        diff = DeepDiff(local, deployed, ignore_order=True)

        has_changes = bool(diff)
        return {
            'workflow_id': workflow_id,
            'has_changes': has_changes,
            'diff': diff.to_dict() if has_changes else {},
            'compared_at': datetime.now().isoformat()
        }


def main():
    """Main function for command-line usage."""
    from config_loader import load_config
    from n8n_client import N8nClient

    try:
        config = load_config()

        api_key = config['api_keys']['n8n']
        if not api_key:
            print("Error: N8N_API_KEY not found.")
            sys.exit(1)

        base_url = config['n8n']['base_url']

        with N8nClient(base_url, api_key,
                       timeout=config['n8n'].get('timeout_seconds', 30),
                       cache_dir=config['paths']['cache_dir']) as client:

            deployer = WorkflowDeployer(client)

            # Default action: export all workflows as backup
            action = sys.argv[1] if len(sys.argv) > 1 else 'export-all'

            if action == 'export-all':
                print("Exporting all workflows as backup...")
                tmp_dir = Path(config['paths']['tmp_dir'])
                export_dir = tmp_dir / "workflow_backups" / datetime.now().strftime('%Y%m%d_%H%M%S')
                deployer.export_all_workflows(str(export_dir))

            elif action == 'deploy' and len(sys.argv) > 2:
                json_path = sys.argv[2]
                activate_flag = '--activate' in sys.argv
                deployer.deploy_from_file(json_path, activate=activate_flag)

            elif action == 'compare' and len(sys.argv) > 3:
                workflow_id = sys.argv[2]
                local_path = sys.argv[3]
                result = deployer.compare_versions(workflow_id, local_path)
                if result.get('has_changes'):
                    print("  Differences found!")
                    print(json.dumps(result['diff'], indent=2))
                else:
                    print("  No differences - workflow is in sync")

            else:
                print("Usage:")
                print("  python workflow_deployer.py export-all")
                print("  python workflow_deployer.py deploy <path.json> [--activate]")
                print("  python workflow_deployer.py compare <workflow_id> <local.json>")

            print(f"\n  Deployment operations complete!")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

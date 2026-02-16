"""
n8n execution monitor.

Monitors workflow executions, detects failures, tracks patterns,
and generates health dashboard data.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter


class ExecutionMonitor:
    """Monitors n8n workflow executions and detects issues."""

    def __init__(self, n8n_client, alert_threshold: int = 3):
        """
        Initialize execution monitor.

        Args:
            n8n_client: Initialized N8nClient instance
            alert_threshold: Number of consecutive errors before alerting
        """
        self.client = n8n_client
        self.alert_threshold = alert_threshold

    def fetch_recent_executions(self, hours: int = 24,
                                 workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch recent executions across all or specific workflows.

        Args:
            hours: How many hours of history to fetch
            workflow_id: Optional workflow filter

        Returns:
            List of execution dictionaries
        """
        print(f"\nFetching executions from the last {hours} hours...")

        all_executions = []

        # Fetch successful executions
        success = self.client.list_executions(
            workflow_id=workflow_id, status='success', limit=250
        )
        all_executions.extend(success)

        # Fetch failed executions
        errors = self.client.list_executions(
            workflow_id=workflow_id, status='error', limit=250
        )
        all_executions.extend(errors)

        # Fetch waiting executions
        waiting = self.client.list_executions(
            workflow_id=workflow_id, status='waiting', limit=100
        )
        all_executions.extend(waiting)

        # Filter by time window
        cutoff = datetime.now() - timedelta(hours=hours)
        filtered = []
        for ex in all_executions:
            started = ex.get('startedAt') or ex.get('createdAt', '')
            if started:
                try:
                    ex_time = datetime.fromisoformat(started.replace('Z', '+00:00'))
                    if ex_time.replace(tzinfo=None) >= cutoff:
                        filtered.append(ex)
                except (ValueError, TypeError):
                    filtered.append(ex)
            else:
                filtered.append(ex)

        print(f"  Found {len(filtered)} executions in the last {hours}h")
        return filtered

    def get_execution_stats(self, executions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate execution statistics.

        Args:
            executions: List of execution records

        Returns:
            Statistics dictionary
        """
        if not executions:
            return {'total': 0, 'success': 0, 'error': 0, 'waiting': 0, 'success_rate': 0}

        total = len(executions)
        success = sum(1 for ex in executions if ex.get('status') == 'success')
        error = sum(1 for ex in executions if ex.get('status') == 'error')
        waiting = sum(1 for ex in executions if ex.get('status') == 'waiting')

        # Calculate average duration for completed executions
        durations = []
        for ex in executions:
            started = ex.get('startedAt')
            stopped = ex.get('stoppedAt')
            if started and stopped:
                try:
                    start_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
                    stop_dt = datetime.fromisoformat(stopped.replace('Z', '+00:00'))
                    duration = (stop_dt - start_dt).total_seconds()
                    if duration >= 0:
                        durations.append(duration)
                except (ValueError, TypeError):
                    pass

        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            'total': total,
            'success': success,
            'error': error,
            'waiting': waiting,
            'success_rate': round(success / total * 100, 1) if total > 0 else 0,
            'avg_duration_seconds': round(avg_duration, 2),
        }

    def detect_failing_workflows(self, executions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify workflows with error rate above threshold.

        Args:
            executions: List of execution records

        Returns:
            List of failing workflow summaries
        """
        # Group executions by workflow
        workflow_executions = {}
        for ex in executions:
            wf_id = ex.get('workflowId') or ex.get('workflowData', {}).get('id', 'unknown')
            wf_name = ex.get('workflowData', {}).get('name', 'Unknown')
            if wf_id not in workflow_executions:
                workflow_executions[wf_id] = {'name': wf_name, 'executions': []}
            workflow_executions[wf_id]['executions'].append(ex)

        failing = []
        for wf_id, data in workflow_executions.items():
            exs = data['executions']
            errors = sum(1 for ex in exs if ex.get('status') == 'error')
            total = len(exs)

            if errors >= self.alert_threshold:
                error_rate = errors / total * 100 if total > 0 else 0
                failing.append({
                    'workflow_id': wf_id,
                    'workflow_name': data['name'],
                    'total_executions': total,
                    'errors': errors,
                    'error_rate': round(error_rate, 1),
                })

        failing.sort(key=lambda x: x['errors'], reverse=True)
        return failing

    def check_stale_workflows(self, workflows: List[Dict[str, Any]],
                               executions: List[Dict[str, Any]],
                               days_inactive: int = 30) -> List[Dict[str, Any]]:
        """
        Identify active workflows that haven't executed recently.

        Args:
            workflows: List of all workflows
            executions: List of recent executions
            days_inactive: Days threshold for stale detection

        Returns:
            List of stale workflow summaries
        """
        executed_ids = set()
        for ex in executions:
            wf_id = ex.get('workflowId') or ex.get('workflowData', {}).get('id')
            if wf_id:
                executed_ids.add(str(wf_id))

        stale = []
        for wf in workflows:
            wf_id = str(wf.get('id', ''))
            if wf.get('active') and wf_id not in executed_ids:
                stale.append({
                    'workflow_id': wf_id,
                    'workflow_name': wf.get('name', 'Unknown'),
                    'active': True,
                    'last_execution': 'None in monitored period'
                })

        return stale

    def generate_health_dashboard(self, executions: List[Dict[str, Any]],
                                   workflows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate overall system health dashboard data.

        Args:
            executions: List of execution records
            workflows: List of all workflows

        Returns:
            Dashboard data dictionary
        """
        stats = self.get_execution_stats(executions)
        failing = self.detect_failing_workflows(executions)
        stale = self.check_stale_workflows(workflows, executions)

        # Count by workflow
        workflow_counts = Counter()
        for ex in executions:
            wf_name = ex.get('workflowData', {}).get('name', 'Unknown')
            workflow_counts[wf_name] += 1

        dashboard = {
            'generated_at': datetime.now().isoformat(),
            'overall_stats': stats,
            'total_workflows': len(workflows),
            'active_workflows': sum(1 for w in workflows if w.get('active')),
            'failing_workflows': failing,
            'stale_workflows': stale,
            'top_executed_workflows': workflow_counts.most_common(10),
            'health_status': 'healthy' if stats['success_rate'] >= 90 else
                           'warning' if stats['success_rate'] >= 70 else 'critical'
        }

        return dashboard

    def save_monitoring_results(self, data: Dict[str, Any], output_path: str):
        """Save monitoring snapshot to JSON."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n  Monitoring results saved to: {output_file}")


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
        threshold = config['monitoring'].get('error_alert_threshold', 3)
        history_days = config['monitoring'].get('execution_history_days', 30)

        with N8nClient(base_url, api_key,
                       timeout=config['n8n'].get('timeout_seconds', 30),
                       cache_dir=config['paths']['cache_dir']) as client:

            monitor = ExecutionMonitor(client, alert_threshold=threshold)

            # Fetch data
            workflows = client.list_workflows(use_cache=False)
            executions = monitor.fetch_recent_executions(hours=history_days * 24)

            # Generate dashboard
            dashboard = monitor.generate_health_dashboard(executions, workflows)

            # Print dashboard
            stats = dashboard['overall_stats']
            print(f"\n{'=' * 50}")
            print("EXECUTION HEALTH DASHBOARD")
            print(f"{'=' * 50}")
            print(f"System Status: {dashboard['health_status'].upper()}")
            print(f"Total Workflows: {dashboard['total_workflows']}")
            print(f"Active Workflows: {dashboard['active_workflows']}")
            print(f"\nExecution Stats (last {history_days} days):")
            print(f"  Total Executions: {stats['total']}")
            print(f"  Successful: {stats['success']}")
            print(f"  Failed: {stats['error']}")
            print(f"  Success Rate: {stats['success_rate']}%")
            print(f"  Avg Duration: {stats['avg_duration_seconds']:.1f}s")

            if dashboard['failing_workflows']:
                print(f"\nFailing Workflows ({len(dashboard['failing_workflows'])}):")
                for wf in dashboard['failing_workflows']:
                    print(f"  [{wf['error_rate']}% errors] {wf['workflow_name']} "
                          f"({wf['errors']}/{wf['total_executions']})")

            if dashboard['stale_workflows']:
                print(f"\nStale Workflows ({len(dashboard['stale_workflows'])}):")
                for wf in dashboard['stale_workflows'][:5]:
                    print(f"  {wf['workflow_name']} (active but no recent executions)")

            # Save results
            tmp_dir = Path(config['paths']['tmp_dir'])
            monitor.save_monitoring_results(dashboard, str(tmp_dir / "monitoring_results.json"))

            # Also save raw execution data for the analyzer
            monitor.save_monitoring_results(
                {'executions': executions, 'workflows': workflows},
                str(tmp_dir / "execution_data.json")
            )

            print(f"\n  Monitoring complete!")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

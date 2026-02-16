"""
n8n workflow performance analyzer.

Calculates success rates, throughput, error patterns, and generates
optimization recommendations using pandas.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from collections import Counter
import pandas as pd
import numpy as np


class WorkflowAnalyzer:
    """Analyzes n8n workflow performance and generates optimization insights."""

    def __init__(self, min_executions_threshold: int = 5):
        """
        Initialize workflow analyzer.

        Args:
            min_executions_threshold: Minimum executions to include in analysis
        """
        self.min_executions_threshold = min_executions_threshold
        self.df = None
        self.insights = {}

    def load_execution_data(self, execution_data_path: str):
        """
        Load execution data into pandas DataFrame.

        Args:
            execution_data_path: Path to execution_data.json
        """
        with open(execution_data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        executions = data.get('executions', [])
        if not executions:
            raise ValueError("No executions found in input file")

        # Flatten execution data into records
        records = []
        for ex in executions:
            wf_data = ex.get('workflowData', {})
            started = ex.get('startedAt') or ex.get('createdAt', '')
            stopped = ex.get('stoppedAt', '')

            duration = 0
            if started and stopped:
                try:
                    start_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
                    stop_dt = datetime.fromisoformat(stopped.replace('Z', '+00:00'))
                    duration = (stop_dt - start_dt).total_seconds()
                except (ValueError, TypeError):
                    pass

            records.append({
                'execution_id': ex.get('id', ''),
                'workflow_id': ex.get('workflowId') or wf_data.get('id', 'unknown'),
                'workflow_name': wf_data.get('name', 'Unknown'),
                'status': ex.get('status', 'unknown'),
                'started_at': started,
                'stopped_at': stopped,
                'duration_seconds': max(0, duration),
                'finished': ex.get('finished', False),
                'mode': ex.get('mode', 'unknown'),
            })

        self.df = pd.DataFrame(records)

        # Parse dates
        self.df['started_at'] = pd.to_datetime(self.df['started_at'], errors='coerce', utc=True)
        self.df['execution_date'] = self.df['started_at'].dt.date

        print(f"Loaded {len(self.df)} executions across {self.df['workflow_id'].nunique()} workflows")

    def analyze(self) -> Dict[str, Any]:
        """
        Perform complete analysis and generate insights.

        Returns:
            Dictionary containing all analysis results
        """
        self.calculate_metrics()

        analysis = {
            'summary': self._generate_summary(),
            'top_performers': self._identify_top_performers(),
            'workflow_comparison': self._compare_workflows(),
            'time_series': self._analyze_time_series(),
            'error_analysis': self._analyze_errors(),
            'recommendations': self._generate_recommendations()
        }

        self.insights = analysis
        return analysis

    def calculate_metrics(self):
        """Calculate per-workflow performance metrics."""
        print("\nCalculating metrics...")

        # Per-workflow aggregation
        wf_stats = self.df.groupby('workflow_id').agg(
            workflow_name=('workflow_name', 'first'),
            total_executions=('execution_id', 'count'),
            successes=('status', lambda x: (x == 'success').sum()),
            errors=('status', lambda x: (x == 'error').sum()),
            avg_duration=('duration_seconds', 'mean'),
            max_duration=('duration_seconds', 'max'),
            min_duration=('duration_seconds', 'min'),
        ).reset_index()

        wf_stats['success_rate'] = (wf_stats['successes'] / wf_stats['total_executions'] * 100).round(1)
        wf_stats['error_rate'] = (wf_stats['errors'] / wf_stats['total_executions'] * 100).round(1)
        wf_stats['avg_duration'] = wf_stats['avg_duration'].round(2)

        self.wf_stats = wf_stats
        print("  Metrics calculated")

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate overall summary statistics."""
        total_executions = len(self.df)
        successes = (self.df['status'] == 'success').sum()
        errors = (self.df['status'] == 'error').sum()

        return {
            'total_workflows': int(self.df['workflow_id'].nunique()),
            'total_executions': int(total_executions),
            'total_successes': int(successes),
            'total_errors': int(errors),
            'overall_success_rate': round(successes / total_executions * 100, 1) if total_executions > 0 else 0,
            'avg_duration_seconds': round(self.df['duration_seconds'].mean(), 2),
            'active_workflows': int(self.wf_stats[self.wf_stats['total_executions'] >= self.min_executions_threshold].shape[0]),
        }

    def _identify_top_performers(self, top_n: int = 10) -> Dict[str, Any]:
        """Identify top performing workflows by different metrics."""
        qualified = self.wf_stats[self.wf_stats['total_executions'] >= self.min_executions_threshold]

        return {
            'by_success_rate': qualified.nlargest(top_n, 'success_rate')[
                ['workflow_id', 'workflow_name', 'success_rate', 'total_executions', 'avg_duration']
            ].to_dict('records'),
            'by_throughput': qualified.nlargest(top_n, 'total_executions')[
                ['workflow_id', 'workflow_name', 'total_executions', 'success_rate', 'avg_duration']
            ].to_dict('records'),
            'by_efficiency': qualified.nsmallest(top_n, 'avg_duration')[
                ['workflow_id', 'workflow_name', 'avg_duration', 'success_rate', 'total_executions']
            ].to_dict('records'),
        }

    def _compare_workflows(self) -> List[Dict[str, Any]]:
        """Compare all workflows side-by-side."""
        return self.wf_stats.sort_values('total_executions', ascending=False).to_dict('records')

    def _analyze_time_series(self) -> Dict[str, Any]:
        """Analyze execution volume and error rate over time."""
        if self.df['execution_date'].isna().all():
            return {'daily_stats': [], 'trends': {'note': 'No date data available'}}

        daily = self.df.groupby('execution_date').agg(
            total_executions=('execution_id', 'count'),
            successes=('status', lambda x: (x == 'success').sum()),
            errors=('status', lambda x: (x == 'error').sum()),
            avg_duration=('duration_seconds', 'mean'),
        ).reset_index()

        daily['success_rate'] = (daily['successes'] / daily['total_executions'] * 100).round(1)
        daily['avg_duration'] = daily['avg_duration'].round(2)

        # Convert dates to strings
        records = daily.tail(30).to_dict('records')
        for rec in records:
            if 'execution_date' in rec and hasattr(rec['execution_date'], 'strftime'):
                rec['execution_date'] = rec['execution_date'].strftime('%Y-%m-%d')

        return {
            'daily_stats': records,
            'trends': self._identify_trends()
        }

    def _identify_trends(self) -> Dict[str, str]:
        """Identify upward or downward trends."""
        if len(self.df) < 20:
            return {'note': 'Insufficient data for trend analysis'}

        df_sorted = self.df.sort_values('started_at')
        mid = len(df_sorted) // 2
        first_half = df_sorted.iloc[:mid]
        second_half = df_sorted.iloc[mid:]

        trends = {}

        first_success = (first_half['status'] == 'success').mean() * 100
        second_success = (second_half['status'] == 'success').mean() * 100
        if first_success > 0:
            change = second_success - first_success
            trends['success_rate_trend'] = f"{'UP' if change > 0 else 'DOWN'} {abs(change):.1f}pp"

        first_dur = first_half['duration_seconds'].mean()
        second_dur = second_half['duration_seconds'].mean()
        if first_dur > 0:
            dur_change = ((second_dur - first_dur) / first_dur * 100)
            trends['duration_trend'] = f"{'UP' if dur_change > 0 else 'DOWN'} {abs(dur_change):.1f}%"

        return trends

    def _analyze_errors(self) -> Dict[str, Any]:
        """Analyze error patterns across workflows."""
        error_df = self.df[self.df['status'] == 'error']

        if error_df.empty:
            return {'total_errors': 0, 'error_prone_workflows': []}

        error_by_workflow = error_df.groupby('workflow_name').size().reset_index(name='error_count')
        error_by_workflow = error_by_workflow.sort_values('error_count', ascending=False)

        return {
            'total_errors': len(error_df),
            'error_prone_workflows': error_by_workflow.head(10).to_dict('records'),
            'errors_by_mode': error_df['mode'].value_counts().to_dict(),
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on analysis."""
        recommendations = []

        # Success rate recommendations
        summary = self.insights.get('summary', self._generate_summary())
        if summary['overall_success_rate'] < 90:
            recommendations.append(
                f"Overall success rate is {summary['overall_success_rate']}% - "
                "review failing workflows and implement retry logic or error handling"
            )

        # Identify problematic workflows
        low_success = self.wf_stats[
            (self.wf_stats['success_rate'] < 80) &
            (self.wf_stats['total_executions'] >= self.min_executions_threshold)
        ]
        if not low_success.empty:
            worst = low_success.nsmallest(1, 'success_rate').iloc[0]
            recommendations.append(
                f"'{worst['workflow_name']}' has {worst['success_rate']}% success rate "
                f"across {worst['total_executions']} executions - prioritize debugging"
            )

        # Duration recommendations
        slow_workflows = self.wf_stats[
            (self.wf_stats['avg_duration'] > 60) &
            (self.wf_stats['total_executions'] >= self.min_executions_threshold)
        ]
        if not slow_workflows.empty:
            slowest = slow_workflows.nlargest(1, 'avg_duration').iloc[0]
            recommendations.append(
                f"'{slowest['workflow_name']}' averages {slowest['avg_duration']:.0f}s per execution - "
                "consider optimizing node chains or adding parallel execution"
            )

        # Throughput recommendations
        high_volume = self.wf_stats.nlargest(1, 'total_executions')
        if not high_volume.empty:
            top = high_volume.iloc[0]
            recommendations.append(
                f"'{top['workflow_name']}' has the highest volume ({top['total_executions']} executions) - "
                "ensure it has robust error handling and monitoring"
            )

        # Stale workflow recommendation
        zero_exec = self.wf_stats[self.wf_stats['total_executions'] < 2]
        if len(zero_exec) > 3:
            recommendations.append(
                f"{len(zero_exec)} workflows have very few executions - "
                "consider archiving unused workflows to reduce clutter"
            )

        return recommendations[:5]

    def save_analysis(self, output_path: str):
        """Save analysis results to JSON file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.insights, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n  Analysis saved to: {output_file}")


def main():
    """Main function for command-line usage."""
    from config_loader import load_config

    try:
        config = load_config()

        tmp_dir = Path(config['paths']['tmp_dir'])
        input_file = tmp_dir / "execution_data.json"

        if not input_file.exists():
            print("Error: execution_data.json not found.")
            print("Please run tools/execution_monitor.py first.")
            sys.exit(1)

        analyzer = WorkflowAnalyzer(min_executions_threshold=5)
        analyzer.load_execution_data(str(input_file))
        analysis = analyzer.analyze()

        # Print summary
        print(f"\n{'=' * 50}")
        print("WORKFLOW PERFORMANCE SUMMARY")
        print(f"{'=' * 50}")

        summary = analysis['summary']
        print(f"Total Workflows: {summary['total_workflows']}")
        print(f"Total Executions: {summary['total_executions']}")
        print(f"Overall Success Rate: {summary['overall_success_rate']}%")
        print(f"Average Duration: {summary['avg_duration_seconds']:.1f}s")

        print(f"\n{'=' * 50}")
        print("RECOMMENDATIONS")
        print(f"{'=' * 50}")
        for i, rec in enumerate(analysis['recommendations'], 1):
            print(f"{i}. {rec}")

        # Save results
        output_file = tmp_dir / "analysis_results.json"
        analyzer.save_analysis(str(output_file))

        print(f"\n  Analysis complete!")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Chart generation tool.

Creates professional visualizations using Plotly for n8n workflow performance.
Exports charts as PNG images for inclusion in Google Slides reports.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any
import plotly.graph_objects as go
from datetime import datetime


class ChartGenerator:
    """Generates professional charts for n8n workflow performance."""

    def __init__(self, brand_color: str = "#FF6D5A"):
        """
        Initialize chart generator.

        Args:
            brand_color: Primary color for charts (n8n orange-red)
        """
        self.brand_color = brand_color
        self.color_scheme = {
            'primary': brand_color,
            'secondary': '#1A1A2E',
            'accent': '#00C9A7',
            'warning': '#FFB800',
            'error': '#E74C3C',
            'background': '#FFFFFF'
        }
        self.analysis_data = None

    def load_analysis_data(self, analysis_file: str):
        """Load analysis results from JSON file."""
        with open(analysis_file, 'r', encoding='utf-8') as f:
            self.analysis_data = json.load(f)
        print(f"  Loaded analysis data from {Path(analysis_file).name}")

    def generate_all_charts(self, output_dir: str):
        """
        Generate all charts for the performance report.

        Args:
            output_dir: Directory to save PNG chart files
        """
        if not self.analysis_data:
            raise ValueError("No analysis data loaded. Call load_analysis_data() first.")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print("\nGenerating charts...")

        # 1. Success rates bar chart
        self._generate_success_rates_chart(output_path / "workflow_success_rates.png")

        # 2. Category performance chart
        self._generate_category_chart(output_path / "category_performance.png")

        # 3. Throughput comparison chart
        self._generate_throughput_chart(output_path / "workflow_comparison.png")

        # 4. Execution trend chart
        self._generate_execution_trend_chart(output_path / "execution_trend.png")

        # 5. Duration scatter plot
        self._generate_duration_scatter_chart(output_path / "duration_scatter.png")

        print(f"\n  All charts saved to: {output_path}")

    def _generate_success_rates_chart(self, output_file: Path):
        """Generate horizontal bar chart of workflow success rates."""
        top_performers = self.analysis_data.get('top_performers', {}).get('by_success_rate', [])

        if not top_performers:
            print("  Skipping success rates chart - no data")
            return

        names = [w['workflow_name'][:40] + "..." if len(w['workflow_name']) > 40 else w['workflow_name']
                 for w in top_performers]
        rates = [w['success_rate'] for w in top_performers]

        names = names[::-1]
        rates = rates[::-1]

        colors = [self.color_scheme['accent'] if r >= 95 else
                  self.brand_color if r >= 80 else
                  self.color_scheme['warning'] if r >= 60 else
                  self.color_scheme['error'] for r in rates]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=names, x=rates, orientation='h',
            marker=dict(color=colors, line=dict(color='#FFFFFF', width=2)),
            text=[f"{r:.1f}%" for r in rates],
            textposition='auto',
        ))

        fig.update_layout(
            title="Top Workflows by Success Rate",
            xaxis_title="Success Rate (%)", xaxis_range=[0, 105],
            font=dict(size=12, family="Arial"),
            height=600, width=1200,
            plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(l=300, r=50, t=80, b=50)
        )

        fig.write_image(str(output_file))
        print(f"  Success rates chart: {output_file.name}")

    def _generate_category_chart(self, output_file: Path):
        """Generate bar chart of workflow execution volumes."""
        comparison = self.analysis_data.get('workflow_comparison', [])

        if not comparison or len(comparison) < 2:
            print("  Skipping category chart - insufficient data")
            return

        top = comparison[:10]
        names = [w['workflow_name'][:30] for w in top]
        executions = [w['total_executions'] for w in top]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=names, y=executions, name='Executions',
            marker=dict(color=self.brand_color),
            text=[f"{e}" for e in executions],
            textposition='outside'
        ))

        fig.update_layout(
            title="Workflow Execution Volume (Top 10)",
            xaxis_title="Workflow", yaxis_title="Executions",
            font=dict(size=12, family="Arial"),
            height=500, width=1200,
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis_tickangle=-30
        )

        fig.write_image(str(output_file))
        print(f"  Category performance chart: {output_file.name}")

    def _generate_throughput_chart(self, output_file: Path):
        """Generate horizontal bar chart comparing workflow throughput."""
        top_throughput = self.analysis_data.get('top_performers', {}).get('by_throughput', [])

        if not top_throughput or len(top_throughput) < 2:
            print("  Skipping throughput chart - insufficient data")
            return

        names = [w['workflow_name'][:30] + "..." if len(w['workflow_name']) > 30
                 else w['workflow_name'] for w in top_throughput]
        counts = [w['total_executions'] for w in top_throughput]

        names = names[::-1]
        counts = counts[::-1]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=names, x=counts, orientation='h',
            marker=dict(color=self.brand_color),
            text=[f"{c:,}" for c in counts],
            textposition='auto'
        ))

        fig.update_layout(
            title="Workflow Throughput Comparison",
            xaxis_title="Total Executions",
            font=dict(size=12, family="Arial"),
            height=600, width=1200,
            plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(l=250, r=50, t=80, b=50)
        )

        fig.write_image(str(output_file))
        print(f"  Throughput comparison chart: {output_file.name}")

    def _generate_execution_trend_chart(self, output_file: Path):
        """Generate line chart of daily executions and success rate over time."""
        time_series = self.analysis_data.get('time_series', {}).get('daily_stats', [])

        if not time_series or len(time_series) < 3:
            print("  Skipping execution trend chart - insufficient data")
            return

        dates = [entry['execution_date'] for entry in time_series]
        executions = [entry['total_executions'] for entry in time_series]
        success_rates = [entry['success_rate'] for entry in time_series]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=dates, y=executions, name='Executions',
            marker=dict(color=self.brand_color, opacity=0.6),
            yaxis='y'
        ))

        fig.add_trace(go.Scatter(
            x=dates, y=success_rates, name='Success Rate',
            mode='lines+markers',
            line=dict(color=self.color_scheme['accent'], width=3),
            marker=dict(size=6),
            yaxis='y2'
        ))

        fig.update_layout(
            title="Execution Volume & Success Rate Over Time",
            xaxis_title="Date",
            yaxis=dict(title="Executions", side='left'),
            yaxis2=dict(title="Success Rate (%)", side='right', overlaying='y', range=[0, 105]),
            font=dict(size=14, family="Arial"),
            height=500, width=1200,
            plot_bgcolor='white', paper_bgcolor='white',
            legend=dict(x=0.01, y=0.99),
            hovermode='x unified'
        )

        fig.write_image(str(output_file))
        print(f"  Execution trend chart: {output_file.name}")

    def _generate_duration_scatter_chart(self, output_file: Path):
        """Generate scatter plot of executions vs avg duration, colored by success rate."""
        comparison = self.analysis_data.get('workflow_comparison', [])

        if not comparison or len(comparison) < 5:
            print("  Skipping duration scatter chart - insufficient data")
            return

        top = [w for w in comparison if w['total_executions'] >= 2][:30]
        if len(top) < 3:
            print("  Skipping duration scatter chart - insufficient qualified data")
            return

        executions = [w['total_executions'] for w in top]
        durations = [w['avg_duration'] for w in top]
        success_rates = [w['success_rate'] for w in top]
        names = [w['workflow_name'][:30] for w in top]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=executions, y=durations, mode='markers',
            marker=dict(
                size=12, color=success_rates,
                colorscale='RdYlGn', showscale=True,
                colorbar=dict(title="Success %"),
                cmin=0, cmax=100,
                line=dict(width=1, color='white')
            ),
            text=names,
            hovertemplate='<b>%{text}</b><br>Executions: %{x}<br>Avg Duration: %{y:.1f}s<br>Success: %{marker.color:.1f}%<extra></extra>'
        ))

        fig.update_layout(
            title="Executions vs Duration (colored by Success Rate)",
            xaxis_title="Total Executions",
            yaxis_title="Average Duration (seconds)",
            font=dict(size=14, family="Arial"),
            height=600, width=1200,
            plot_bgcolor='white', paper_bgcolor='white'
        )

        fig.write_image(str(output_file))
        print(f"  Duration scatter chart: {output_file.name}")


def main():
    """Main function for command-line usage."""
    from config_loader import load_config

    try:
        config = load_config()

        tmp_dir = Path(config['paths']['tmp_dir'])
        analysis_file = tmp_dir / "analysis_results.json"
        charts_dir = Path(config['paths']['charts_dir'])

        if not analysis_file.exists():
            print("Error: analysis_results.json not found.")
            print("Please run tools/workflow_analyzer.py first.")
            sys.exit(1)

        brand_color = config['reporting'].get('brand_color', '#FF6D5A')

        generator = ChartGenerator(brand_color=brand_color)
        generator.load_analysis_data(str(analysis_file))
        generator.generate_all_charts(str(charts_dir))

        print("\n  Chart generation complete!")

    except ImportError as e:
        if 'kaleido' in str(e).lower():
            print("\nError: Kaleido not installed.")
            print("  pip install kaleido")
        else:
            print(f"\nImport Error: {e}")
            print("  pip install -r requirements.txt")
        sys.exit(1)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

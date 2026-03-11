"""
Intelligence Engine - Cross-Department Analytics & Forecasting

Connects to all Airtable bases, computes correlations between department
metrics, identifies bottlenecks, generates trend forecasts, and detects
cross-department anomalies.

Usage:
    python tools/intelligence_engine.py correlations              # Cross-dept correlations
    python tools/intelligence_engine.py bottlenecks               # Identify bottlenecks
    python tools/intelligence_engine.py forecast <agent> <metric> # Trend forecast
    python tools/intelligence_engine.py anomalies                 # Cross-dept anomaly detection
"""

import json
import math
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import httpx
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# -- Airtable Config ---------------------------------------------------------

AIRTABLE_API_URL = "https://api.airtable.com/v0"
AIRTABLE_TOKEN = os.getenv("AIRTABLE_API_TOKEN", "")

# Orchestrator base
ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")
ORCH_TABLE_KPI = os.getenv("ORCH_TABLE_KPI_SNAPSHOTS", "REPLACE_WITH_TABLE_ID")
ORCH_TABLE_ESCALATION = os.getenv("ORCH_TABLE_ESCALATION_QUEUE", "REPLACE_WITH_TABLE_ID")
ORCH_TABLE_DECISION = os.getenv("ORCH_TABLE_DECISION_LOG", "REPLACE_WITH_TABLE_ID")
ORCH_TABLE_EVENTS = os.getenv("ORCH_TABLE_EVENTS", "REPLACE_WITH_TABLE_ID")

# Marketing base
MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TABLE_CONTENT_CALENDAR = os.getenv("MARKETING_TABLE_CONTENT_CALENDAR", "REPLACE_WITH_TABLE_ID")
TABLE_ENGAGEMENT_LOG = os.getenv("SEO_TABLE_ENGAGEMENT_LOG", "REPLACE_WITH_TABLE_ID")
TABLE_LEADS = os.getenv("SEO_TABLE_LEADS", "REPLACE_WITH_TABLE_ID")

# Lead scraper base
SCRAPER_BASE_ID = os.getenv("LEAD_SCRAPER_AIRTABLE_BASE_ID", "app2ALQUP7CKEkHOz")
SCRAPER_TABLE_LEADS = os.getenv("LEAD_SCRAPER_TABLE_LEADS", "REPLACE_WITH_TABLE_ID")

# -- Metrics we track across agents ------------------------------------------

AGENT_METRICS = [
    "content_published",
    "leads_generated",
    "emails_sent",
    "revenue_zar",
    "messages_handled",
    "tickets_resolved",
    "success_rate",
    "token_usage",
]

# Input -> Output metric pairs (for bottleneck detection)
INPUT_OUTPUT_PAIRS = [
    ("content_published", "leads_generated", "Marketing Funnel"),
    ("leads_generated", "emails_sent", "Lead Outreach"),
    ("emails_sent", "revenue_zar", "Email -> Revenue"),
    ("content_published", "messages_handled", "Content Engagement"),
    ("leads_generated", "revenue_zar", "Lead -> Revenue"),
]


class IntelligenceEngine:
    """Cross-department analytics and forecasting engine."""

    def __init__(self):
        if not AIRTABLE_TOKEN:
            raise ValueError("AIRTABLE_API_TOKEN not set in .env")
        self.headers = {
            "Authorization": f"Bearer {AIRTABLE_TOKEN}",
            "Content-Type": "application/json",
        }
        self.client = httpx.Client(timeout=30)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # -- Airtable Helpers -----------------------------------------------------

    def _fetch_records(
        self, base_id: str, table_id: str,
        formula: str = "", fields: Optional[List[str]] = None,
        max_records: int = 1000,
    ) -> List[Dict]:
        """Fetch records from Airtable with pagination."""
        url = f"{AIRTABLE_API_URL}/{base_id}/{table_id}"
        all_records = []
        offset = None

        while True:
            params: Dict[str, Any] = {"pageSize": min(100, max_records - len(all_records))}
            if formula:
                params["filterByFormula"] = formula
            if fields:
                for i, f in enumerate(fields):
                    params[f"fields[{i}]"] = f
            if offset:
                params["offset"] = offset

            resp = self.client.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            data = resp.json()

            records = data.get("records", [])
            all_records.extend(records)

            offset = data.get("offset")
            if not offset or len(all_records) >= max_records:
                break

        return all_records

    def _get_kpi_snapshots(self, days: int = 28) -> List[Dict]:
        """Fetch KPI snapshots for the last N days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        formula = f"IS_AFTER({{Snapshot Date}}, '{cutoff}')"
        records = self._fetch_records(ORCH_BASE_ID, ORCH_TABLE_KPI, formula=formula)
        return [r["fields"] for r in records if "fields" in r]

    def _get_kpi_by_agent(self, days: int = 28) -> Dict[str, List[Dict]]:
        """Group KPI snapshots by agent_id."""
        snapshots = self._get_kpi_snapshots(days)
        by_agent: Dict[str, List[Dict]] = {}
        for snap in snapshots:
            agent = snap.get("Agent ID", snap.get("agent_id", "unknown"))
            by_agent.setdefault(agent, []).append(snap)

        # Sort each agent's data by date
        for agent in by_agent:
            by_agent[agent].sort(
                key=lambda s: s.get("Snapshot Date", s.get("snapshot_date", ""))
            )
        return by_agent

    # -- Statistical Helpers --------------------------------------------------

    @staticmethod
    def _pearson_correlation(x: List[float], y: List[float]) -> Optional[float]:
        """Compute Pearson correlation coefficient between two series."""
        n = min(len(x), len(y))
        if n < 3:
            return None

        x, y = x[:n], y[:n]
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        den_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
        den_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

        if den_x == 0 or den_y == 0:
            return None
        return num / (den_x * den_y)

    @staticmethod
    def _linear_regression(values: List[float]) -> Tuple[float, float]:
        """Simple linear regression (y = mx + b). Returns (slope, intercept)."""
        n = len(values)
        if n < 2:
            return 0.0, values[0] if values else 0.0

        x = list(range(n))
        mean_x = sum(x) / n
        mean_y = sum(values) / n

        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, values))
        den = sum((xi - mean_x) ** 2 for xi in x)

        if den == 0:
            return 0.0, mean_y

        slope = num / den
        intercept = mean_y - slope * mean_x
        return slope, intercept

    @staticmethod
    def _extract_metric(snapshot: Dict, metric: str) -> float:
        """Extract a numeric metric from a KPI snapshot (handles field name variants)."""
        # Try camelCase, Title Case, and snake_case
        variants = [
            metric,
            metric.replace("_", " ").title(),
            metric.replace("_", " ").title().replace(" ", ""),
            # Common Airtable field name mappings
            {
                "content_published": "Content Published",
                "leads_generated": "Leads Generated",
                "emails_sent": "Emails Sent",
                "revenue_zar": "Revenue ZAR",
                "messages_handled": "Messages Handled",
                "tickets_resolved": "Tickets Resolved",
                "success_rate": "Success Rate",
                "token_usage": "Token Usage",
            }.get(metric, metric),
        ]

        for v in variants:
            val = snapshot.get(v)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
        return 0.0

    # -- Core Analysis Methods ------------------------------------------------

    def compute_cross_dept_correlations(self, days: int = 28) -> Dict:
        """
        Compute Pearson correlations between all metric pairs across all agents.
        Returns top 5 positive and top 5 negative correlations.
        """
        by_agent = self._get_kpi_by_agent(days)

        # Aggregate all snapshots by date (sum across agents)
        by_date: Dict[str, Dict[str, float]] = {}
        for agent, snaps in by_agent.items():
            for snap in snaps:
                date = snap.get("Snapshot Date", snap.get("snapshot_date", "unknown"))
                if date not in by_date:
                    by_date[date] = {m: 0.0 for m in AGENT_METRICS}
                for metric in AGENT_METRICS:
                    by_date[date][metric] += self._extract_metric(snap, metric)

        dates_sorted = sorted(by_date.keys())
        if len(dates_sorted) < 5:
            return {
                "error": f"Insufficient data: only {len(dates_sorted)} days of snapshots",
                "positive": [],
                "negative": [],
            }

        # Build time series for each metric
        series: Dict[str, List[float]] = {}
        for metric in AGENT_METRICS:
            series[metric] = [by_date[d][metric] for d in dates_sorted]

        # Compute all pairwise correlations
        correlations = []
        for i, m1 in enumerate(AGENT_METRICS):
            for m2 in AGENT_METRICS[i + 1:]:
                r = self._pearson_correlation(series[m1], series[m2])
                if r is not None:
                    correlations.append({
                        "metric_a": m1,
                        "metric_b": m2,
                        "correlation": round(r, 4),
                        "strength": (
                            "strong" if abs(r) > 0.7
                            else "moderate" if abs(r) > 0.4
                            else "weak"
                        ),
                        "data_points": len(dates_sorted),
                    })

        correlations.sort(key=lambda c: c["correlation"], reverse=True)

        return {
            "period_days": days,
            "data_points": len(dates_sorted),
            "agents_included": list(by_agent.keys()),
            "positive": correlations[:5],
            "negative": correlations[-5:][::-1],
        }

    def identify_bottlenecks(self) -> List[Dict]:
        """
        Identify agents where input metrics are high but output metrics are low.
        Returns a list of bottleneck descriptions with severity.
        """
        by_agent = self._get_kpi_by_agent(days=14)
        bottlenecks = []

        for agent, snaps in by_agent.items():
            if len(snaps) < 3:
                continue

            # Average metrics over the period
            avg: Dict[str, float] = {}
            for metric in AGENT_METRICS:
                vals = [self._extract_metric(s, metric) for s in snaps]
                avg[metric] = sum(vals) / len(vals) if vals else 0.0

            # Check each input -> output pair
            for input_metric, output_metric, label in INPUT_OUTPUT_PAIRS:
                input_val = avg.get(input_metric, 0)
                output_val = avg.get(output_metric, 0)

                if input_val <= 0:
                    continue

                # Compute conversion rate
                ratio = output_val / input_val if input_val > 0 else 0

                # Flag if input is above median but output is below median
                # Use a simple threshold: ratio < 0.1 is a bottleneck
                if input_val > 1 and ratio < 0.1:
                    severity = "high" if ratio < 0.02 else "medium" if ratio < 0.05 else "low"
                    bottlenecks.append({
                        "agent": agent,
                        "funnel_stage": label,
                        "input_metric": input_metric,
                        "input_avg": round(input_val, 2),
                        "output_metric": output_metric,
                        "output_avg": round(output_val, 2),
                        "conversion_rate": round(ratio * 100, 2),
                        "severity": severity,
                        "recommendation": (
                            f"{agent}: {label} conversion is only "
                            f"{round(ratio * 100, 1)}%. "
                            f"Avg {input_metric}={round(input_val, 1)} but "
                            f"{output_metric}={round(output_val, 1)}. "
                            f"Investigate pipeline between these stages."
                        ),
                    })

        # Sort by severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        bottlenecks.sort(key=lambda b: severity_order.get(b["severity"], 3))

        return bottlenecks

    def generate_trend_forecast(
        self, agent_id: str, metric: str, days: int = 30
    ) -> Dict:
        """
        Simple linear regression on historical KPI data.
        Projects next 7 days.
        """
        by_agent = self._get_kpi_by_agent(days)

        if agent_id not in by_agent:
            available = list(by_agent.keys())
            return {
                "error": f"Agent '{agent_id}' not found. Available: {available}",
            }

        snaps = by_agent[agent_id]
        values = [self._extract_metric(s, metric) for s in snaps]

        if len(values) < 3:
            return {
                "error": f"Insufficient data for {agent_id}/{metric}: only {len(values)} points",
            }

        slope, intercept = self._linear_regression(values)
        current_value = values[-1]
        projected_value = slope * (len(values) + 7 - 1) + intercept

        # Determine trend direction
        if abs(slope) < 0.01 * (max(values) - min(values) + 1):
            direction = "flat"
        elif slope > 0:
            direction = "up"
        else:
            direction = "down"

        # Confidence based on R-squared
        mean_y = sum(values) / len(values)
        ss_tot = sum((y - mean_y) ** 2 for y in values)
        ss_res = sum(
            (y - (slope * i + intercept)) ** 2
            for i, y in enumerate(values)
        )
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "agent_id": agent_id,
            "metric": metric,
            "data_points": len(values),
            "period_days": days,
            "current_value": round(current_value, 2),
            "slope_per_day": round(slope, 4),
            "projected_7d": round(projected_value, 2),
            "trend_direction": direction,
            "r_squared": round(r_squared, 4),
            "confidence": (
                "high" if r_squared > 0.7
                else "moderate" if r_squared > 0.4
                else "low"
            ),
            "recent_values": [round(v, 2) for v in values[-7:]],
        }

    def detect_cross_dept_anomalies(self, days: int = 14) -> List[Dict]:
        """
        Look for mismatches across departments.
        E.g., marketing leads up 50% but finance invoices flat = conversion problem.
        """
        by_agent = self._get_kpi_by_agent(days)
        anomalies = []

        # Compute week-over-week change for each agent/metric
        changes: Dict[str, Dict[str, float]] = {}
        for agent, snaps in by_agent.items():
            if len(snaps) < 4:
                continue

            mid = len(snaps) // 2
            first_half = snaps[:mid]
            second_half = snaps[mid:]

            changes[agent] = {}
            for metric in AGENT_METRICS:
                avg_first = sum(
                    self._extract_metric(s, metric) for s in first_half
                ) / len(first_half)
                avg_second = sum(
                    self._extract_metric(s, metric) for s in second_half
                ) / len(second_half)

                if avg_first > 0:
                    pct_change = ((avg_second - avg_first) / avg_first) * 100
                elif avg_second > 0:
                    pct_change = 100.0
                else:
                    pct_change = 0.0
                changes[agent][metric] = round(pct_change, 1)

        # Cross-department anomaly rules
        anomaly_rules = [
            {
                "name": "Marketing leads up but revenue flat",
                "check": lambda c: (
                    c.get("agent_marketing", {}).get("leads_generated", 0) > 30
                    and abs(c.get("agent_finance", {}).get("revenue_zar", 0)) < 10
                ),
                "description": "Lead generation increased significantly but revenue hasn't followed - possible conversion bottleneck",
                "severity": "P2",
            },
            {
                "name": "Content up but engagement flat",
                "check": lambda c: (
                    c.get("agent_content", {}).get("content_published", 0) > 30
                    and abs(c.get("agent_marketing", {}).get("messages_handled", 0)) < 10
                ),
                "description": "Content output increased but engagement hasn't - content quality or distribution issue",
                "severity": "P3",
            },
            {
                "name": "Emails up but leads flat",
                "check": lambda c: (
                    c.get("agent_marketing", {}).get("emails_sent", 0) > 40
                    and abs(c.get("agent_marketing", {}).get("leads_generated", 0)) < 10
                ),
                "description": "Email volume increased significantly but lead generation hasn't - email targeting or quality issue",
                "severity": "P2",
            },
            {
                "name": "Success rate declining while volume increases",
                "check": lambda c: any(
                    agent_data.get("success_rate", 0) < -15
                    and (
                        agent_data.get("emails_sent", 0) > 20
                        or agent_data.get("content_published", 0) > 20
                    )
                    for agent_data in c.values()
                ),
                "description": "An agent's success rate is declining while output volume increases - quality vs quantity tradeoff",
                "severity": "P2",
            },
            {
                "name": "Token usage spike without output increase",
                "check": lambda c: any(
                    agent_data.get("token_usage", 0) > 50
                    and max(
                        agent_data.get("content_published", 0),
                        agent_data.get("emails_sent", 0),
                        agent_data.get("leads_generated", 0),
                    ) < 10
                    for agent_data in c.values()
                ),
                "description": "AI token consumption increased significantly without corresponding output increase - possible prompt inefficiency or retry loops",
                "severity": "P3",
            },
        ]

        for rule in anomaly_rules:
            try:
                if rule["check"](changes):
                    # Find the agents involved
                    involved_agents = []
                    for agent, metrics in changes.items():
                        for m, v in metrics.items():
                            if abs(v) > 20:
                                involved_agents.append(
                                    f"{agent}: {m} {'+' if v > 0 else ''}{v}%"
                                )

                    anomalies.append({
                        "anomaly": rule["name"],
                        "severity": rule["severity"],
                        "description": rule["description"],
                        "involved": involved_agents[:5],
                        "changes": {
                            agent: {m: v for m, v in metrics.items() if abs(v) > 5}
                            for agent, metrics in changes.items()
                            if any(abs(v) > 5 for v in metrics.values())
                        },
                    })
            except Exception:
                continue

        return anomalies


# -- CLI ----------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    if not args:
        print("AVM Intelligence Engine")
        print("=" * 50)
        print()
        print("Usage:")
        print("  python tools/intelligence_engine.py correlations")
        print("  python tools/intelligence_engine.py bottlenecks")
        print("  python tools/intelligence_engine.py forecast <agent_id> <metric>")
        print("  python tools/intelligence_engine.py anomalies")
        print()
        print("Available metrics:", ", ".join(AGENT_METRICS))
        sys.exit(0)

    command = args[0]

    with IntelligenceEngine() as engine:
        if command == "correlations":
            days = int(args[1]) if len(args) > 1 else 28
            print(f"Computing cross-department correlations ({days} days)...")
            result = engine.compute_cross_dept_correlations(days)
            print()
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Period: {result['period_days']} days, {result['data_points']} data points")
                print(f"Agents: {', '.join(result['agents_included'])}")
                print()
                print("Top 5 Positive Correlations:")
                for c in result["positive"]:
                    print(f"  {c['metric_a']} <-> {c['metric_b']}: r={c['correlation']} ({c['strength']})")
                print()
                print("Top 5 Negative Correlations:")
                for c in result["negative"]:
                    print(f"  {c['metric_a']} <-> {c['metric_b']}: r={c['correlation']} ({c['strength']})")

        elif command == "bottlenecks":
            print("Identifying bottlenecks...")
            result = engine.identify_bottlenecks()
            print()
            if not result:
                print("No bottlenecks detected.")
            else:
                print(f"Found {len(result)} bottleneck(s):")
                for b in result:
                    print(f"\n  [{b['severity'].upper()}] {b['agent']} - {b['funnel_stage']}")
                    print(f"    {b['input_metric']}: {b['input_avg']} -> {b['output_metric']}: {b['output_avg']}")
                    print(f"    Conversion: {b['conversion_rate']}%")
                    print(f"    Recommendation: {b['recommendation']}")

        elif command == "forecast":
            if len(args) < 3:
                print("Usage: python tools/intelligence_engine.py forecast <agent_id> <metric>")
                print(f"  Metrics: {', '.join(AGENT_METRICS)}")
                sys.exit(1)
            agent_id = args[1]
            metric = args[2]
            days = int(args[3]) if len(args) > 3 else 30
            print(f"Generating trend forecast for {agent_id}/{metric} ({days} days)...")
            result = engine.generate_trend_forecast(agent_id, metric, days)
            print()
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Agent: {result['agent_id']}")
                print(f"Metric: {result['metric']}")
                print(f"Data points: {result['data_points']}")
                print(f"Current value: {result['current_value']}")
                print(f"Trend: {result['trend_direction']} (slope: {result['slope_per_day']}/day)")
                print(f"Projected (7 days): {result['projected_7d']}")
                print(f"R-squared: {result['r_squared']} ({result['confidence']} confidence)")
                print(f"Recent values: {result['recent_values']}")

        elif command == "anomalies":
            days = int(args[1]) if len(args) > 1 else 14
            print(f"Detecting cross-department anomalies ({days} days)...")
            result = engine.detect_cross_dept_anomalies(days)
            print()
            if not result:
                print("No cross-department anomalies detected.")
            else:
                print(f"Found {len(result)} anomaly/anomalies:")
                for a in result:
                    print(f"\n  [{a['severity']}] {a['anomaly']}")
                    print(f"    {a['description']}")
                    if a.get("involved"):
                        print(f"    Involved: {', '.join(a['involved'][:3])}")

        else:
            print(f"Unknown command: {command}")
            print("Use: correlations, bottlenecks, forecast, anomalies")
            sys.exit(1)


if __name__ == "__main__":
    main()

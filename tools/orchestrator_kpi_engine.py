"""
AVM Autonomous Operations - KPI Computation Engine

Connects to all Airtable bases, Supabase, and n8n API to compute per-agent
health scores, detect anomalies, and generate structured KPI data.

Used by:
    - ORCH-03 (Daily KPI Aggregation) via n8n Code node calling this as a module
    - deploy_orchestrator.py for embedding KPI logic
    - run_manager.py for CLI status checks

Classes:
    KPIEngine - Main engine for cross-department KPI computation

Usage:
    from orchestrator_kpi_engine import KPIEngine

    engine = KPIEngine()
    scores = engine.compute_all_agent_scores()
    anomalies = engine.detect_anomalies()
    snapshot = engine.generate_daily_snapshot()
"""

import os
import json
import math
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class KPIEngine:
    """Cross-department KPI computation and anomaly detection engine."""

    def __init__(self):
        self.airtable_token = os.getenv("AIRTABLE_API_TOKEN", "")
        self.n8n_base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
        self.n8n_api_key = os.getenv("N8N_API_KEY", "")
        self.supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

        # Airtable base IDs
        self.marketing_base = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
        self.accounting_base = os.getenv("ACCOUNTING_AIRTABLE_BASE_ID", "")
        self.whatsapp_base = os.getenv("WHATSAPP_AIRTABLE_BASE_ID", "appzcZpiIZ6QPtJXT")
        self.orch_base = os.getenv("ORCH_AIRTABLE_BASE_ID", "")
        self.support_base = os.getenv("SUPPORT_AIRTABLE_BASE_ID", "")

        # Agent -> Workflow ID mappings
        self.agent_workflows = {
            "agent_marketing": [
                "twSg4SfNdlmdITHj", "CWQ9zjCTaf56RBe6",
                "ygwBtSysINRWHJxB", "ZEcxIC9M5ehQvsbg",
                "5XZFaoQxfyJOlqje", "ipsnBC5Xox4DWgBg",
                "u7LSuq6zmAY8P7fU", "M67NBeAEHfDIJ9wz",
                "BpZ4LkxKjHoGfjUq", "Xlu3tGHgM5DDXnkl",
                "Y80dDSmWQfUlfvib", "0US5H9smGsrCUsv7",
                "IqODyj5suLusrkIx", "tOT9DtpE8DspXSjm",
                "0ynfcpEwHrPaghTl", "OlHyOU8mHxJ1uZuc",
            ],
            "agent_content": [
                "ygwBtSysINRWHJxB", "ipsnBC5Xox4DWgBg", "u7LSuq6zmAY8P7fU",
            ],
            "agent_finance": [
                "twSg4SfNdlmdITHj", "CWQ9zjCTaf56RBe6",
                "ygwBtSysINRWHJxB", "ZEcxIC9M5ehQvsbg",
                "f0Wh4SOxbODbs4TE", "gwMuSElYqDTRGFKa", "EmpOzaaDGqsLvg5j",
            ],
            "agent_client_relations": [],
            "agent_support": [],
            "agent_whatsapp": [],
            "agent_orchestrator": [],
        }

        self.client = httpx.Client(timeout=30)

    def close(self):
        """Close HTTP client."""
        self.client.close()

    # -- n8n API Methods --

    def get_workflow_executions(self, workflow_id, hours=24):
        """Fetch recent executions for a workflow from n8n API."""
        if not self.n8n_api_key:
            return []

        try:
            resp = self.client.get(
                f"{self.n8n_base_url}/api/v1/executions",
                headers={"X-N8N-API-KEY": self.n8n_api_key},
                params={
                    "workflowId": workflow_id,
                    "limit": 50,
                    "status": "error,success,waiting",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                executions = data.get("data", [])
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                return [
                    e for e in executions
                    if datetime.fromisoformat(e.get("startedAt", "2000-01-01T00:00:00").replace("Z", "+00:00")).replace(tzinfo=None) > cutoff
                ]
            return []
        except Exception:
            return []

    def compute_workflow_health(self, workflow_id, hours=24):
        """Compute health score (0-100) for a single workflow based on recent executions."""
        executions = self.get_workflow_executions(workflow_id, hours)

        if not executions:
            return {"score": 50, "total": 0, "success": 0, "errors": 0, "status": "no_data"}

        total = len(executions)
        success = sum(1 for e in executions if e.get("status") == "success")
        errors = sum(1 for e in executions if e.get("status") == "error")

        success_rate = (success / total * 100) if total > 0 else 0

        # Score: 100 if all success, penalize errors heavily
        score = int(success_rate)
        if errors > 3:
            score = max(0, score - 20)  # Extra penalty for many errors

        status = "healthy"
        if score < 60:
            status = "degraded"
        if score < 30:
            status = "critical"

        return {
            "score": score,
            "total": total,
            "success": success,
            "errors": errors,
            "success_rate": round(success_rate, 1),
            "status": status,
        }

    def compute_agent_health(self, agent_id, hours=24):
        """Compute aggregate health score for an agent across all its workflows."""
        workflow_ids = self.agent_workflows.get(agent_id, [])

        if not workflow_ids:
            return {
                "agent_id": agent_id,
                "health_score": 100,
                "status": "Active",
                "workflows_checked": 0,
                "details": [],
            }

        workflow_scores = []
        for wf_id in workflow_ids:
            health = self.compute_workflow_health(wf_id, hours)
            health["workflow_id"] = wf_id
            workflow_scores.append(health)

        # Aggregate: weighted average (lower scores pull down more)
        scores = [ws["score"] for ws in workflow_scores if ws["total"] > 0]
        if not scores:
            avg_score = 50  # No data
        else:
            avg_score = int(sum(scores) / len(scores))

        # Determine status
        if avg_score >= 80:
            status = "Active"
        elif avg_score >= 50:
            status = "Degraded"
        else:
            status = "Down"

        return {
            "agent_id": agent_id,
            "health_score": avg_score,
            "status": status,
            "workflows_checked": len(workflow_ids),
            "workflows_with_data": len(scores),
            "details": workflow_scores,
        }

    def compute_all_agent_scores(self, hours=24):
        """Compute health scores for all agents."""
        results = {}
        for agent_id in self.agent_workflows:
            results[agent_id] = self.compute_agent_health(agent_id, hours)
        return results

    # -- Airtable Methods --

    def airtable_count(self, base_id, table_id, formula=None):
        """Count records in an Airtable table, optionally filtered."""
        if not self.airtable_token or not base_id or not table_id:
            return 0

        try:
            params = {"pageSize": 100}
            if formula:
                params["filterByFormula"] = formula
            params["fields[]"] = []  # Don't fetch field data, just count

            resp = self.client.get(
                f"https://api.airtable.com/v0/{base_id}/{table_id}",
                headers={"Authorization": f"Bearer {self.airtable_token}"},
                params=params,
            )
            if resp.status_code == 200:
                data = resp.json()
                return len(data.get("records", []))
            return 0
        except Exception:
            return 0

    # -- KPI Computation --

    def compute_marketing_kpis(self):
        """Compute KPIs for the Marketing AI Agent."""
        content_table = os.getenv("MARKETING_TABLE_CONTENT", "")
        distribution_table = os.getenv("MARKETING_TABLE_DISTRIBUTION_LOG", "")
        leads_table = os.getenv("SEO_TABLE_LEADS", "")
        today = datetime.now().strftime("%Y-%m-%d")

        content_published = self.airtable_count(
            self.marketing_base, content_table,
            f"=IS_SAME({{Published Date}}, '{today}', 'day')"
        ) if content_table else 0

        emails_sent = self.airtable_count(
            self.marketing_base, distribution_table,
            f"=IS_SAME({{Sent Date}}, '{today}', 'day')"
        ) if distribution_table else 0

        leads_today = self.airtable_count(
            self.marketing_base, leads_table,
            f"=IS_SAME({{Created At}}, '{today}', 'day')"
        ) if leads_table else 0

        return {
            "content_published": content_published,
            "emails_sent": emails_sent,
            "leads_generated": leads_today,
        }

    def compute_finance_kpis(self):
        """Compute KPIs for the Finance & Accounting Agent."""
        invoices_table = os.getenv("ACCOUNTING_TABLE_INVOICES", "")
        payments_table = os.getenv("ACCOUNTING_TABLE_PAYMENTS", "")

        # Count today's invoices and payments
        today = datetime.now().strftime("%Y-%m-%d")

        invoices_today = self.airtable_count(
            self.accounting_base, invoices_table,
            f"=IS_SAME({{Invoice Date}}, '{today}', 'day')"
        ) if invoices_table else 0

        payments_today = self.airtable_count(
            self.accounting_base, payments_table,
            f"=IS_SAME({{Payment Date}}, '{today}', 'day')"
        ) if payments_table else 0

        return {
            "invoices_created": invoices_today,
            "payments_processed": payments_today,
        }

    def compute_support_kpis(self):
        """Compute KPIs for the Customer Support Agent."""
        tickets_table = os.getenv("SUPPORT_TABLE_TICKETS", "")

        open_tickets = self.airtable_count(
            self.support_base, tickets_table,
            "={Status} = 'Open'"
        ) if tickets_table else 0

        resolved_today = self.airtable_count(
            self.support_base, tickets_table,
            f"=AND({{Status}} = 'Resolved', IS_SAME({{Resolved At}}, '{datetime.now().strftime('%Y-%m-%d')}', 'day'))"
        ) if tickets_table else 0

        return {
            "open_tickets": open_tickets,
            "tickets_resolved": resolved_today,
        }

    # -- Anomaly Detection --

    def detect_anomalies(self, kpi_history, current_kpis):
        """
        Detect anomalies using z-score on a 7-day rolling window.

        Args:
            kpi_history: List of dicts with past daily KPI values
            current_kpis: Dict of today's KPI values

        Returns:
            List of anomaly descriptions
        """
        anomalies = []

        if len(kpi_history) < 3:
            return anomalies  # Not enough data

        for metric_name, current_value in current_kpis.items():
            if not isinstance(current_value, (int, float)):
                continue

            # Get historical values for this metric
            historical = [
                h.get(metric_name, 0) for h in kpi_history
                if isinstance(h.get(metric_name, 0), (int, float))
            ]

            if len(historical) < 3:
                continue

            # Compute mean and std dev
            mean = sum(historical) / len(historical)
            variance = sum((x - mean) ** 2 for x in historical) / len(historical)
            std_dev = math.sqrt(variance) if variance > 0 else 0

            if std_dev == 0:
                continue

            z_score = (current_value - mean) / std_dev

            if abs(z_score) > 2.5:
                direction = "above" if z_score > 0 else "below"
                anomalies.append({
                    "metric": metric_name,
                    "current": current_value,
                    "mean": round(mean, 2),
                    "std_dev": round(std_dev, 2),
                    "z_score": round(z_score, 2),
                    "direction": direction,
                    "description": f"{metric_name} is {abs(round(z_score, 1))} std devs {direction} average ({current_value} vs avg {round(mean, 1)})",
                })

        return anomalies

    # -- Snapshot Generation --

    def generate_daily_snapshot(self):
        """Generate a complete daily KPI snapshot for all agents."""
        today = datetime.now().strftime("%Y-%m-%d")
        agent_scores = self.compute_all_agent_scores()
        marketing_kpis = self.compute_marketing_kpis()
        finance_kpis = self.compute_finance_kpis()
        support_kpis = self.compute_support_kpis()

        snapshots = []

        for agent_id, health in agent_scores.items():
            snapshot = {
                "Snapshot ID": f"{agent_id}_{today}",
                "Snapshot Date": today,
                "Agent ID": agent_id,
                "Success Rate": health.get("details", [{}])[0].get("success_rate", 0) if health.get("details") else 0,
            }

            # Merge department-specific KPIs
            if agent_id == "agent_marketing":
                snapshot.update({
                    "Content Published": marketing_kpis.get("content_published", 0),
                    "Emails Sent": marketing_kpis.get("emails_sent", 0),
                    "Leads Generated": marketing_kpis.get("leads_generated", 0),
                })
            elif agent_id == "agent_finance":
                snapshot.update({
                    "Revenue ZAR": 0,  # Populated from QuickBooks via workflow
                })
            elif agent_id == "agent_support":
                snapshot.update({
                    "Tickets Resolved": support_kpis.get("tickets_resolved", 0),
                })

            snapshots.append(snapshot)

        return {
            "date": today,
            "agent_scores": agent_scores,
            "snapshots": snapshots,
            "marketing_kpis": marketing_kpis,
            "finance_kpis": finance_kpis,
            "support_kpis": support_kpis,
        }


# -- CLI Interface --

def main():
    """Run KPI engine from command line for testing."""
    import sys

    engine = KPIEngine()

    if len(sys.argv) > 1 and sys.argv[1] == "health":
        print("Computing agent health scores...")
        print("-" * 50)
        scores = engine.compute_all_agent_scores()
        for agent_id, health in scores.items():
            print(f"  {agent_id:<30} Score: {health['health_score']:>3}  Status: {health['status']}")
        print()

    elif len(sys.argv) > 1 and sys.argv[1] == "snapshot":
        print("Generating daily snapshot...")
        print("-" * 50)
        snapshot = engine.generate_daily_snapshot()
        print(json.dumps(snapshot, indent=2, default=str))

    else:
        print("AVM KPI Engine")
        print()
        print("Usage:")
        print("  python tools/orchestrator_kpi_engine.py health     # Show agent health scores")
        print("  python tools/orchestrator_kpi_engine.py snapshot   # Generate daily KPI snapshot")

    engine.close()


if __name__ == "__main__":
    main()

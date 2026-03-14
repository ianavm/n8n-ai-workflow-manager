"""
AVM Agent Registry - Central registry for the 22-agent system.

Provides agent metadata, routing, escalation rules, and health tracking.
This is the operational backbone that maps agents to their workflows,
tools, and communication channels.

Usage:
    from agent_registry import AGENTS, get_agent, get_agents_by_tier

    agent = get_agent("chief")
    tier2 = get_agents_by_tier(2)
    escalation = get_escalation_chain("finance")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AgentConfig:
    """Configuration for a single agent in the AVM system."""
    name: str
    display_name: str
    tier: int
    mission: str
    parent_agent: Optional[str]
    workflows: List[str]
    airtable_tables: Dict[str, str]
    communicates_with: List[str]
    escalates_to: str
    kpis: Dict[str, float]
    token_budget_daily: int
    model: str
    enabled: bool
    schedule: Dict[str, str] = field(default_factory=dict)
    safety_caps: Dict[str, float] = field(default_factory=dict)


# ============================================================
# Agent Definitions
# ============================================================

AGENTS: Dict[str, AgentConfig] = {

    # ── Tier 1: Executive ────────────────────────────────────
    "chief": AgentConfig(
        name="chief",
        display_name="CHIEF (Executive Intelligence)",
        tier=1,
        mission="Strategic synthesis, cross-department decisions, budget arbitration",
        parent_agent=None,
        workflows=["ORCH_03", "ORCH_04", "INTEL_02"],
        airtable_tables={
            "kpi_snapshots": "tblUsdtPRFN7UchgK",
            "decision_log": "tblHViYF9sEUOFdNO",
            "escalation_queue": "tbl2kDx0EqczOU3ib",
        },
        communicates_with=["all"],
        escalates_to="ian@anyvisionmedia.com",
        kpis={"decision_turnaround_hours": 2.0, "report_accuracy_pct": 95.0},
        token_budget_daily=20000,
        model="opus",
        enabled=True,
    ),

    # ── Tier 2: Revenue & Growth ─────────────────────────────
    "finance": AgentConfig(
        name="finance",
        display_name="FINANCE (Revenue Operations)",
        tier=2,
        mission="AP/AR, invoicing, collections, reconciliation",
        parent_agent="chief",
        workflows=[
            "ACC_WF01", "ACC_WF02", "ACC_WF03", "ACC_WF04",
            "ACC_WF05", "ACC_WF06", "ACC_WF07", "FIN_08", "FIN_09",
        ],
        airtable_tables={},
        communicates_with=["chief", "client_success", "intelligence"],
        escalates_to="chief",
        kpis={
            "processing_time_min": 5.0,
            "collection_rate_pct": 85.0,
            "reconciliation_accuracy_pct": 99.0,
        },
        token_budget_daily=10000,
        model="sonnet",
        enabled=True,
        safety_caps={
            "auto_approve_zar": 10000,
            "escalate_zar": 50000,
        },
    ),

    "growth_organic": AgentConfig(
        name="growth_organic",
        display_name="GROWTH_ORGANIC (Content & SEO)",
        tier=2,
        mission="Content, SEO, social media, organic leads",
        parent_agent="chief",
        workflows=[
            "SEO_WF05", "SEO_WF06", "SEO_WF07", "SEO_WF08",
            "SEO_WF09", "SEO_WF10", "SEO_WF11", "SEO_SCORE",
        ],
        airtable_tables={},
        communicates_with=["pipeline", "growth_paid", "intelligence"],
        escalates_to="chief",
        kpis={
            "content_per_week": 15.0,
            "engagement_rate_pct": 3.0,
            "organic_leads_monthly": 50.0,
            "seo_audit_score": 70.0,
        },
        token_budget_daily=50000,
        model="sonnet",
        enabled=True,
    ),

    "growth_paid": AgentConfig(
        name="growth_paid",
        display_name="GROWTH_PAID (Advertising)",
        tier=2,
        mission="Google/Meta/TikTok ads, campaign strategy, bid optimization",
        parent_agent="chief",
        workflows=[
            "ADS_01", "ADS_02", "ADS_03", "ADS_04",
            "ADS_05", "ADS_06", "ADS_07", "ADS_08",
        ],
        airtable_tables={},
        communicates_with=["growth_organic", "finance", "chief", "intelligence"],
        escalates_to="chief",
        kpis={"roas": 3.0, "budget_utilization_pct": 85.0},
        token_budget_daily=30000,
        model="sonnet",
        enabled=True,
        safety_caps={
            "daily_zar": 2000,
            "weekly_zar": 10000,
            "monthly_zar": 35000,
            "max_bid_change_pct": 20,
            "max_budget_increase_zar": 200,
        },
    ),

    "pipeline": AgentConfig(
        name="pipeline",
        display_name="PIPELINE (Lead Pipeline)",
        tier=2,
        mission="Lead generation, qualification, nurturing, conversion",
        parent_agent="chief",
        workflows=["BRIDGE_01", "BRIDGE_02", "BRIDGE_03", "BRIDGE_04"],
        airtable_tables={},
        communicates_with=["growth_organic", "client_success", "intelligence"],
        escalates_to="chief",
        kpis={
            "qualification_rate_pct": 30.0,
            "deliverability_pct": 95.0,
            "reply_rate_pct": 5.0,
            "nurture_conversion_pct": 10.0,
        },
        token_budget_daily=15000,
        model="sonnet",
        enabled=True,
    ),

    # ── Tier 3: Client-Facing ────────────────────────────────
    "client_success": AgentConfig(
        name="client_success",
        display_name="CLIENT_SUCCESS (Client Relations)",
        tier=3,
        mission="Retention, health scoring, renewals, onboarding",
        parent_agent="chief",
        workflows=["CR_01", "CR_02", "CR_03", "CR_04", "OPT_03"],
        airtable_tables={},
        communicates_with=["finance", "pipeline", "support", "chief"],
        escalates_to="chief",
        kpis={
            "health_avg": 70.0,
            "churn_rate_pct": 10.0,
            "renewal_rate_pct": 85.0,
            "nps": 40.0,
        },
        token_budget_daily=10000,
        model="sonnet",
        enabled=True,
    ),

    "support": AgentConfig(
        name="support",
        display_name="SUPPORT (Operations & Support)",
        tier=3,
        mission="Tickets, SLA, auto-resolve, KB, document processing",
        parent_agent="chief",
        workflows=[
            "SUP_01", "SUP_02", "SUP_03", "SUP_04",
            "DI_WF01", "DI_WF02", "DI_WF03", "DI_WF04", "DI_COMBINED",
        ],
        airtable_tables={
            "tickets": "tbldPadf19Ky0JIez",
            "knowledge_base": "tblPQFlV6Y5qDjiKT",
            "sla_config": "tblJ7wayh08MflQGN",
        },
        communicates_with=["client_success", "chief", "intelligence"],
        escalates_to="chief",
        kpis={
            "sla_compliance_pct": 95.0,
            "auto_resolution_pct": 40.0,
        },
        token_budget_daily=10000,
        model="sonnet",
        enabled=True,
    ),

    "messenger": AgentConfig(
        name="messenger",
        display_name="MESSENGER (Conversational Intelligence)",
        tier=3,
        mission="WhatsApp intelligence, CRM sync, issue detection",
        parent_agent="chief",
        workflows=["WA_01", "WA_02", "WA_03"],
        airtable_tables={},
        communicates_with=["pipeline", "support", "intelligence"],
        escalates_to="chief",
        kpis={
            "response_time_min": 2.0,
            "crm_sync_accuracy_pct": 99.0,
        },
        token_budget_daily=15000,
        model="sonnet",
        enabled=False,  # Pending WhatsApp Business API verification
    ),

    # ── Tier 4: Infrastructure ───────────────────────────────
    "sentinel": AgentConfig(
        name="sentinel",
        display_name="SENTINEL (Systems Health)",
        tier=4,
        mission="Monitoring, self-healing, error classification",
        parent_agent="chief",
        workflows=["ORCH_01", "ORCH_02", "SELF_HEALING"],
        airtable_tables={
            "agent_registry": "tblsees8vFGZaNLqZ",
            "events": "tbl6PqkxZy0Md2Ocf",
        },
        communicates_with=["all"],
        escalates_to="chief",
        kpis={
            "uptime_pct": 99.5,
            "auto_fix_success_pct": 80.0,
            "mttd_min": 15.0,
            "mttr_min": 30.0,
        },
        token_budget_daily=5000,
        model="sonnet",
        enabled=True,
    ),

    "engineer": AgentConfig(
        name="engineer",
        display_name="ENGINEER (Platform Engineering)",
        tier=4,
        mission="Deploy, patch, migrations, portal development",
        parent_agent="chief",
        workflows=[],
        airtable_tables={},
        communicates_with=["all"],
        escalates_to="chief",
        kpis={"deployment_success_pct": 95.0},
        token_budget_daily=0,
        model="sonnet",
        enabled=True,
    ),

    "intelligence": AgentConfig(
        name="intelligence",
        display_name="INTELLIGENCE (Analytics & Optimization)",
        tier=4,
        mission="Cross-dept analytics, A/B testing, optimization",
        parent_agent="chief",
        workflows=["INTEL_01", "INTEL_02", "INTEL_03", "OPT_01", "OPT_02"],
        airtable_tables={
            "kpi_snapshots": "tblUsdtPRFN7UchgK",
            "decision_log": "tblHViYF9sEUOFdNO",
        },
        communicates_with=["all"],
        escalates_to="chief",
        kpis={
            "forecast_accuracy_pct": 85.0,
            "optimization_adoption_pct": 50.0,
        },
        token_budget_daily=10000,
        model="sonnet",
        enabled=True,
    ),

    "devops_coordinator": AgentConfig(
        name="devops_coordinator",
        display_name="DEVOPS_COORDINATOR (DevOps & Deployment)",
        tier=4,
        mission="CI/CD, releases, credential rotation, rollback",
        parent_agent="engineer",
        workflows=["DEVOPS_01", "DEVOPS_02", "DEVOPS_03"],
        airtable_tables={},
        communicates_with=["engineer", "sentinel", "chief"],
        escalates_to="engineer",
        kpis={"deployment_success_pct": 99.0, "rollback_time_min": 5.0},
        token_budget_daily=5000,
        model="sonnet",
        enabled=True,
    ),

    # ── Tier 5: Intelligence Layer ───────────────────────────
    "market_intel": AgentConfig(
        name="market_intel",
        display_name="MARKET_INTEL (Market Intelligence)",
        tier=5,
        mission="Competitive monitoring, market research, regulatory alerts",
        parent_agent="intelligence",
        workflows=["INTEL_04", "INTEL_05", "INTEL_06"],
        airtable_tables={},
        communicates_with=["chief", "growth_organic", "growth_paid", "pipeline"],
        escalates_to="intelligence",
        kpis={},
        token_budget_daily=5000,
        model="sonnet",
        enabled=True,
    ),

    "knowledge_manager": AgentConfig(
        name="knowledge_manager",
        display_name="KNOWLEDGE_MANAGER (Knowledge Management)",
        tier=5,
        mission="Document indexing, semantic search, FAQ generation",
        parent_agent="support",
        workflows=["KM_01", "KM_02", "KM_03"],
        airtable_tables={"knowledge_base": "tblPQFlV6Y5qDjiKT"},
        communicates_with=["support", "client_success", "finance", "chief"],
        escalates_to="support",
        kpis={},
        token_budget_daily=5000,
        model="sonnet",
        enabled=True,
    ),

    "data_analyst": AgentConfig(
        name="data_analyst",
        display_name="DATA_ANALYST (Data Intelligence)",
        tier=5,
        mission="Natural language SQL, spreadsheet analysis, auto-reporting",
        parent_agent="intelligence",
        workflows=["DATA_01", "DATA_02", "DATA_03"],
        airtable_tables={},
        communicates_with=["chief", "intelligence", "finance"],
        escalates_to="intelligence",
        kpis={"query_accuracy_pct": 95.0},
        token_budget_daily=5000,
        model="sonnet",
        enabled=True,
    ),

    # ── Tier 6: Quality & Compliance ─────────────────────────
    "qa_agent": AgentConfig(
        name="qa_agent",
        display_name="QA_AGENT (Quality Assurance)",
        tier=6,
        mission="Smoke tests, visual regression, performance monitoring",
        parent_agent="sentinel",
        workflows=["QA_01", "QA_02", "QA_03"],
        airtable_tables={},
        communicates_with=["sentinel", "engineer", "chief"],
        escalates_to="sentinel",
        kpis={"test_pass_rate_pct": 99.0, "page_load_ms": 3000.0},
        token_budget_daily=2000,
        model="sonnet",
        enabled=True,
    ),

    "brand_guardian": AgentConfig(
        name="brand_guardian",
        display_name="BRAND_GUARDIAN (Brand Consistency)",
        tier=6,
        mission="Brand compliance, content gate, style enforcement",
        parent_agent="growth_organic",
        workflows=["BRAND_01", "BRAND_02", "BRAND_03"],
        airtable_tables={},
        communicates_with=["growth_organic", "growth_paid", "support"],
        escalates_to="growth_organic",
        kpis={"brand_compliance_pct": 90.0},
        token_budget_daily=3000,
        model="sonnet",
        enabled=True,
    ),

    "compliance_auditor": AgentConfig(
        name="compliance_auditor",
        display_name="COMPLIANCE_AUDITOR (Legal & Compliance)",
        tier=6,
        mission="POPIA, BBBEE, tax deadlines, ad policy, contract scanning",
        parent_agent="chief",
        workflows=["COMPLY_01", "COMPLY_02", "COMPLY_03"],
        airtable_tables={},
        communicates_with=["chief", "finance", "growth_paid", "support"],
        escalates_to="chief",
        kpis={"compliance_score_pct": 95.0},
        token_budget_daily=3000,
        model="sonnet",
        enabled=True,
    ),

    # ── Tier 7: Operations ───────────────────────────────────
    "financial_intel": AgentConfig(
        name="financial_intel",
        display_name="FINANCIAL_INTEL (Financial Intelligence)",
        tier=7,
        mission="Payroll, VAT, cash flow scenarios, smart payments",
        parent_agent="finance",
        workflows=["FINTEL_01", "FINTEL_02", "FINTEL_03", "FINTEL_04"],
        airtable_tables={},
        communicates_with=["finance", "chief", "client_success"],
        escalates_to="finance",
        kpis={"payroll_accuracy_pct": 100.0, "cash_flow_forecast_accuracy_pct": 90.0},
        token_budget_daily=5000,
        model="sonnet",
        enabled=True,
    ),

    "crm_sync": AgentConfig(
        name="crm_sync",
        display_name="CRM_SYNC (CRM Unification)",
        tier=7,
        mission="Unified contacts, dedup, activity timelines",
        parent_agent="pipeline",
        workflows=["CRM_01", "CRM_02", "CRM_03"],
        airtable_tables={},
        communicates_with=["pipeline", "client_success", "finance", "growth_organic"],
        escalates_to="pipeline",
        kpis={"sync_lag_hours": 1.0, "dedup_accuracy_pct": 98.0},
        token_budget_daily=3000,
        model="sonnet",
        enabled=True,
    ),

    "booking_assistant": AgentConfig(
        name="booking_assistant",
        display_name="BOOKING_ASSISTANT (Scheduling & Calendar)",
        tier=7,
        mission="Calendar management, meeting scheduling",
        parent_agent="client_success",
        workflows=["BOOK_01", "BOOK_02", "BOOK_03"],
        airtable_tables={},
        communicates_with=["pipeline", "client_success", "chief"],
        escalates_to="client_success",
        kpis={"no_show_rate_pct": 10.0},
        token_budget_daily=2000,
        model="haiku",
        enabled=True,
    ),

    "data_curator": AgentConfig(
        name="data_curator",
        display_name="DATA_CURATOR (Data Quality)",
        tier=7,
        mission="Deduplication, validation, schema drift detection",
        parent_agent="sentinel",
        workflows=["CURE_01", "CURE_02", "CURE_03"],
        airtable_tables={},
        communicates_with=["all"],
        escalates_to="sentinel",
        kpis={"duplicate_rate_pct": 1.0, "validation_pass_pct": 99.0},
        token_budget_daily=2000,
        model="haiku",
        enabled=True,
    ),
}


# ============================================================
# Helper Functions
# ============================================================

def get_agent(name: str) -> Optional[AgentConfig]:
    """Get agent configuration by name."""
    return AGENTS.get(name)


def get_agents_by_tier(tier: int) -> Dict[str, AgentConfig]:
    """Get all agents in a specific tier."""
    return {k: v for k, v in AGENTS.items() if v.tier == tier}


def get_enabled_agents() -> Dict[str, AgentConfig]:
    """Get all enabled agents."""
    return {k: v for k, v in AGENTS.items() if v.enabled}


def get_escalation_chain(agent_name: str) -> List[str]:
    """Get the escalation chain from agent up to CHIEF/Ian.

    Returns list of agent names in escalation order.
    """
    chain = [agent_name]
    current = AGENTS.get(agent_name)
    while current and current.escalates_to != "ian@anyvisionmedia.com":
        next_agent = current.escalates_to
        if next_agent in AGENTS:
            chain.append(next_agent)
            current = AGENTS[next_agent]
        else:
            break
    chain.append("ian@anyvisionmedia.com")
    return chain


def get_total_token_budget() -> int:
    """Get total daily token budget across all enabled agents."""
    return sum(
        a.token_budget_daily
        for a in AGENTS.values()
        if a.enabled
    )


def get_agent_workflows(agent_name: str) -> List[str]:
    """Get all workflow registry keys for an agent."""
    agent = AGENTS.get(agent_name)
    return agent.workflows if agent else []


def print_roster():
    """Print the full agent roster organized by tier."""
    tiers = {}
    for name, agent in AGENTS.items():
        tiers.setdefault(agent.tier, []).append(agent)

    tier_names = {
        1: "Executive",
        2: "Revenue & Growth",
        3: "Client-Facing",
        4: "Infrastructure",
        5: "Intelligence Layer",
        6: "Quality & Compliance",
        7: "Operations",
    }

    for tier_num in sorted(tiers.keys()):
        print(f"\n{'='*60}")
        print(f"  Tier {tier_num}: {tier_names.get(tier_num, 'Unknown')}")
        print(f"{'='*60}")
        for agent in tiers[tier_num]:
            status = "ACTIVE" if agent.enabled else "INACTIVE"
            print(f"  [{status:8s}] {agent.display_name}")
            print(f"             Mission: {agent.mission}")
            print(f"             Model: {agent.model} | Tokens: {agent.token_budget_daily:,}/day")
            print(f"             Workflows: {len(agent.workflows)}")
            print(f"             Escalates to: {agent.escalates_to}")
            print()

    total_budget = get_total_token_budget()
    enabled = len(get_enabled_agents())
    print(f"{'='*60}")
    print(f"  TOTAL: {len(AGENTS)} agents ({enabled} enabled)")
    print(f"  Daily token budget: {total_budget:,} tokens")
    print(f"{'='*60}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "roster":
            print_roster()
        elif cmd == "escalation" and len(sys.argv) > 2:
            chain = get_escalation_chain(sys.argv[2])
            print(f"Escalation chain: {' -> '.join(chain)}")
        elif cmd == "budget":
            print(f"Total daily token budget: {get_total_token_budget():,}")
        elif cmd in AGENTS:
            agent = AGENTS[cmd]
            print(f"Agent: {agent.display_name}")
            print(f"Tier: {agent.tier}")
            print(f"Mission: {agent.mission}")
            print(f"Model: {agent.model}")
            print(f"Enabled: {agent.enabled}")
            print(f"Workflows: {agent.workflows}")
            print(f"Escalates to: {agent.escalates_to}")
            print(f"Token budget: {agent.token_budget_daily:,}/day")
        else:
            print(f"Unknown command or agent: {cmd}")
            print("Usage: python agent_registry.py [roster|escalation <name>|budget|<agent_name>]")
    else:
        print_roster()

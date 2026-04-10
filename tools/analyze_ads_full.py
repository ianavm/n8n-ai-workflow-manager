"""Full ADS Department Diagnostic — read-only.

Fetches live state from Airtable + n8n and produces a markdown report covering:
1. Executive summary
2. Operational health (n8n executions for ADS-01..08 + SHM)
3. Platform status (Google Ads / Meta / TikTok)
4. Spend & budget vs caps
5. Campaign performance (CTR/CPC/CPA/ROAS)
6. Creative performance + A/B tests
7. Pending approvals queue
8. Rule-based recommendations

No mutations. Output: .tmp/ads_analysis_<YYYY-MM-DD>.md
"""
from __future__ import annotations

import logging
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# ── Setup ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Force UTF-8 stdout on Windows so emoji health icons render
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("analyze_ads")

# ── Config ──────────────────────────────────────────────────────────────
AIRTABLE_TOKEN = os.environ["AIRTABLE_API_TOKEN"]
ADS_BASE = os.getenv("ADS_AIRTABLE_BASE_ID") or os.getenv(
    "MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK"
)

TBL_CAMPAIGNS = os.getenv("ADS_TABLE_CAMPAIGNS", "tblon2FDqfifeF1Iv")
TBL_PERFORMANCE = os.getenv("ADS_TABLE_PERFORMANCE", "tblH1ztufqk5Kkkln")
TBL_BUDGET = os.getenv("ADS_TABLE_BUDGET_ALLOCATIONS", "tblhYDUzyzNxnQQXw")
TBL_CREATIVES = os.getenv("ADS_TABLE_CREATIVES", "tblF1FwoZEQlMG6X9")
TBL_AB_TESTS = os.getenv("ADS_TABLE_AB_TESTS", "tblTUyvpzb7aV6P6Y")
TBL_APPROVALS = os.getenv("ADS_TABLE_APPROVALS", "tblov57B8uj09ZF2k")

N8N_BASE_URL = os.environ["N8N_BASE_URL"]
N8N_API_KEY = os.environ["N8N_API_KEY"]

LAUNCH_DATE = datetime(2026, 4, 8, tzinfo=timezone.utc)
DAILY_CAP = 666.0
WEEKLY_CAP = 5000.0
MONTHLY_CAP = 20000.0

GOOGLE_ADS_CRED_ID = "abkg9bL66BFOj2F3"
GOOGLE_ADS_CUSTOMER_ID = "5876156009"
META_ACCOUNT_ID = "26395704183451218"

OUT_PATH = ROOT / ".tmp" / f"ads_analysis_{datetime.now().strftime('%Y-%m-%d')}.md"

at_headers = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json",
}
n8n_headers = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}


# ── Data classes ────────────────────────────────────────────────────────
@dataclass
class WorkflowHealth:
    name: str
    workflow_id: str
    active: bool
    total_runs: int = 0
    success: int = 0
    error: int = 0
    last_run: str | None = None
    last_status: str | None = None

    @property
    def failure_rate(self) -> float:
        return self.error / self.total_runs if self.total_runs else 0.0

    @property
    def health_label(self) -> str:
        if not self.active:
            return "INACTIVE"
        if self.total_runs == 0:
            return "NO RUNS"
        if self.failure_rate > 0.20:
            return "DEGRADED"
        if self.failure_rate > 0:
            return "WARNING"
        return "HEALTHY"


@dataclass
class CampaignMetrics:
    name: str
    platform: str
    status: str
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: int = 0

    @property
    def ctr(self) -> float:
        return (self.clicks / self.impressions * 100) if self.impressions else 0.0

    @property
    def cpc(self) -> float:
        return (self.spend / self.clicks) if self.clicks else 0.0

    @property
    def cpa(self) -> float:
        return (self.spend / self.conversions) if self.conversions else 0.0


@dataclass
class Diagnostic:
    workflows: list[WorkflowHealth] = field(default_factory=list)
    campaigns: list[CampaignMetrics] = field(default_factory=list)
    perf_records: list[dict[str, Any]] = field(default_factory=list)
    budgets: list[dict[str, Any]] = field(default_factory=list)
    creatives: list[dict[str, Any]] = field(default_factory=list)
    ab_tests: list[dict[str, Any]] = field(default_factory=list)
    approvals: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ── Fetchers ────────────────────────────────────────────────────────────
def fetch_airtable(table_id: str, formula: str = "") -> list[dict[str, Any]]:
    """Fetch all records from an Airtable table (handles pagination)."""
    records: list[dict[str, Any]] = []
    url = f"https://api.airtable.com/v0/{ADS_BASE}/{table_id}"
    offset: str | None = None
    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if formula:
            params["filterByFormula"] = formula
        if offset:
            params["offset"] = offset
        try:
            resp = httpx.get(url, headers=at_headers, params=params, timeout=30)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("Airtable fetch failed for %s: %s", table_id, e)
            return records
        data = resp.json()
        for rec in data.get("records", []):
            fields = rec.get("fields", {})
            fields["_id"] = rec.get("id")
            fields["_createdTime"] = rec.get("createdTime")
            records.append(fields)
        offset = data.get("offset")
        if not offset:
            break
    return records


def fetch_n8n_workflows() -> list[dict[str, Any]]:
    """List all workflows from n8n (paginated, lenient timeouts)."""
    workflows: list[dict[str, Any]] = []
    cursor: str | None = None
    base = f"{N8N_BASE_URL.rstrip('/')}/api/v1"
    max_pages = 10
    for page in range(max_pages):
        params: dict[str, Any] = {"limit": 50}
        if cursor:
            params["cursor"] = cursor
        try:
            resp = httpx.get(
                f"{base}/workflows", headers=n8n_headers, params=params, timeout=90
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("n8n list_workflows page %d failed: %s", page, e)
            break
        data = resp.json()
        batch = data.get("data", [])
        workflows.extend(batch)
        cursor = data.get("nextCursor")
        if not cursor or not batch:
            break
    return workflows


def fetch_n8n_executions(workflow_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch recent executions for a workflow."""
    base = f"{N8N_BASE_URL.rstrip('/')}/api/v1"
    try:
        resp = httpx.get(
            f"{base}/executions",
            headers=n8n_headers,
            params={"workflowId": workflow_id, "limit": limit},
            timeout=30,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("n8n executions fetch failed for %s: %s", workflow_id, e)
        return []
    return resp.json().get("data", [])


# ── Diagnostics ─────────────────────────────────────────────────────────
def collect_workflow_health() -> list[WorkflowHealth]:
    """Find all ADS-* workflows and pull execution stats."""
    log.info("Fetching n8n workflows...")
    all_wfs = fetch_n8n_workflows()
    ads_wfs = [
        wf for wf in all_wfs
        if "AVM ADS" in wf.get("name", "").upper()
        or wf.get("name", "").upper().startswith(("ADS-", "ADS "))
    ]
    log.info("Found %d ADS workflows", len(ads_wfs))

    health: list[WorkflowHealth] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for wf in sorted(ads_wfs, key=lambda w: w.get("name", "")):
        wf_id = wf.get("id", "")
        h = WorkflowHealth(
            name=wf.get("name", "?"),
            workflow_id=wf_id,
            active=bool(wf.get("active", False)),
        )
        execs = fetch_n8n_executions(wf_id, limit=50)
        for ex in execs:
            started = ex.get("startedAt")
            if not started:
                continue
            try:
                started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            except ValueError:
                continue
            if started_dt < cutoff:
                continue
            h.total_runs += 1
            status = "error" if ex.get("status") == "error" or ex.get("stoppedAt") and ex.get("finished") is False else "success"
            if ex.get("status") == "error":
                h.error += 1
            else:
                h.success += 1
            if h.last_run is None or started > h.last_run:
                h.last_run = started
                h.last_status = ex.get("status", "unknown")
        health.append(h)
    return health


def aggregate_campaigns(
    campaigns: list[dict[str, Any]], perf: list[dict[str, Any]]
) -> list[CampaignMetrics]:
    """Roll perf records up to per-campaign metrics with platform-correct semantics.

    CRITICAL: Ad_Performance snapshots have DIFFERENT semantics per platform:
      - Google Ads (n8n googleAds node): each row is LIFETIME CUMULATIVE since
        campaign launch. To get totals, take the LATEST snapshot per campaign.
      - Meta Ads (facebookGraphApi date_preset=today): each row is CUMULATIVE
        SINCE MIDNIGHT — resets daily. To get totals, take MAX per (campaign,
        date) and SUM those daily values.

    Group by (Campaign Name, Platform) — same campaign name can exist on
    multiple platforms with different external IDs.
    """
    by_key: dict[tuple[str, str], CampaignMetrics] = {}
    # seed from Ad_Campaigns
    for c in campaigns:
        name = c.get("Campaign Name") or c.get("Name") or "(unnamed)"
        platform = c.get("Platform", "?")
        by_key[(name, platform)] = CampaignMetrics(
            name=name,
            platform=platform,
            status=c.get("Status", "?"),
        )

    # Step 1: bucket perf records by platform-correct key
    google_latest: dict[tuple[str, str], dict[str, Any]] = {}
    meta_daily_max: dict[tuple[str, str, str], dict[str, Any]] = {}

    for p in perf:
        name = p.get("Campaign Name") or "(orphan)"
        platform = p.get("Platform", "?")
        date = (p.get("Date") or "")[:10]
        hour = p.get("Snapshot Hour", "") or ""
        spend = float(p.get("Spend ZAR") or 0)

        if platform == "google_ads":
            # Take the snapshot with the highest (date, hour) — lifetime cumulative
            key = (name, platform)
            cur = google_latest.get(key)
            if cur is None or (date, hour) > (cur.get("_date", ""), cur.get("_hour", "")):
                google_latest[key] = {**p, "_date": date, "_hour": hour}
        elif platform == "meta_ads":
            # Take max spend per (campaign, date) — cumulative within day
            key3 = (name, platform, date)
            cur = meta_daily_max.get(key3)
            if cur is None or spend > float(cur.get("Spend ZAR") or 0):
                meta_daily_max[key3] = p

    # Step 2: apply Google (latest = lifetime totals)
    for (name, platform), p in google_latest.items():
        if (name, platform) not in by_key:
            by_key[(name, platform)] = CampaignMetrics(
                name=name, platform=platform, status="unknown"
            )
        m = by_key[(name, platform)]
        m.impressions = int(p.get("Impressions") or 0)
        m.clicks = int(p.get("Clicks") or 0)
        m.spend = float(p.get("Spend ZAR") or 0)
        m.conversions = int(p.get("Conversions") or 0)

    # Step 3: apply Meta (sum of daily-max)
    for (name, platform, _date), p in meta_daily_max.items():
        if (name, platform) not in by_key:
            by_key[(name, platform)] = CampaignMetrics(
                name=name, platform=platform, status="unknown"
            )
        m = by_key[(name, platform)]
        m.impressions += int(p.get("Impressions") or 0)
        m.clicks += int(p.get("Clicks") or 0)
        m.spend += float(p.get("Spend ZAR") or 0)
        m.conversions += int(p.get("Conversions") or 0)

    return list(by_key.values())


def compute_spend_summary(
    perf: list[dict[str, Any]],
    campaigns_aggregated: list[CampaignMetrics],
) -> dict[str, Any]:
    """Compute totals + daily breakdown using platform-correct semantics.

    Totals come from already-aggregated campaign metrics (so Google = lifetime
    cumulative, Meta = sum of daily-max). Daily breakdown is recomputed from
    raw perf with the same per-platform logic so the per-day trend is accurate.
    """
    total_spend = sum(c.spend for c in campaigns_aggregated)
    total_impressions = sum(c.impressions for c in campaigns_aggregated)
    total_clicks = sum(c.clicks for c in campaigns_aggregated)
    total_conversions = sum(c.conversions for c in campaigns_aggregated)

    by_day: dict[str, float] = defaultdict(float)
    by_platform: dict[str, float] = defaultdict(float)

    # ── Google: per-day spend = (latest cumulative on date D) - (latest on D-1)
    google_cum: dict[tuple[str, str], float] = {}  # (campaign, date) -> latest cum
    for p in perf:
        if p.get("Platform") != "google_ads":
            continue
        name = p.get("Campaign Name") or "?"
        date = (p.get("Date") or "")[:10]
        if not date:
            continue
        spend = float(p.get("Spend ZAR") or 0)
        cur = google_cum.get((name, date), 0.0)
        if spend > cur:
            google_cum[(name, date)] = spend

    by_camp_dates: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (name, date), cum in google_cum.items():
        by_camp_dates[name].append((date, cum))
    for name, pairs in by_camp_dates.items():
        pairs.sort()
        prev = 0.0
        for date, cum in pairs:
            delta = max(0.0, cum - prev)
            by_day[date] += delta
            prev = cum
        # Lifetime contribution to platform total = highest cumulative ever seen
        if pairs:
            by_platform["google_ads"] += pairs[-1][1]

    # ── Meta: per-day spend = max snapshot per (campaign, date)
    meta_daily: dict[tuple[str, str], float] = {}
    for p in perf:
        if p.get("Platform") != "meta_ads":
            continue
        name = p.get("Campaign Name") or "?"
        date = (p.get("Date") or "")[:10]
        if not date:
            continue
        spend = float(p.get("Spend ZAR") or 0)
        cur = meta_daily.get((name, date), 0.0)
        if spend > cur:
            meta_daily[(name, date)] = spend
    for (_name, date), spend in meta_daily.items():
        by_day[date] += spend
        by_platform["meta_ads"] += spend

    days_since_launch = max(1, (datetime.now(timezone.utc) - LAUNCH_DATE).days)
    avg_daily = total_spend / days_since_launch
    projected_monthly = avg_daily * 30

    return {
        "total_spend": total_spend,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_conversions": total_conversions,
        "by_day": dict(by_day),
        "by_platform": dict(by_platform),
        "days_since_launch": days_since_launch,
        "avg_daily": avg_daily,
        "projected_monthly": projected_monthly,
        "daily_cap_pct": (avg_daily / DAILY_CAP * 100) if DAILY_CAP else 0,
        "monthly_cap_pct": (total_spend / MONTHLY_CAP * 100) if MONTHLY_CAP else 0,
    }


def generate_recommendations(
    diag: Diagnostic, spend: dict[str, Any], camps: list[CampaignMetrics]
) -> list[tuple[str, str]]:
    """Rule-based recommendations: (severity, message)."""
    recs: list[tuple[str, str]] = []

    # Critical platform blockers
    google_active = any(
        c.platform.lower().startswith("google") and c.spend > 0 for c in camps
    )
    if not google_active:
        recs.append((
            "CRITICAL",
            f"Google Ads is not delivering. Re-authorize OAuth2 credential "
            f"`{GOOGLE_ADS_CRED_ID}` in n8n UI (customer {GOOGLE_ADS_CUSTOMER_ID}). "
            f"ADS-03 build pipeline is blocked until this is fixed.",
        ))

    tiktok_active = any(c.platform.lower().startswith("tiktok") for c in camps)
    if not tiktok_active:
        recs.append((
            "CRITICAL",
            "TikTok Ads credential never configured (TIKTOK_ADS_ADVERTISER_ID env "
            "var unset). Either create the credential in n8n or remove TikTok branches "
            "from ADS-04 to silence noise.",
        ))

    # Workflow health
    for w in diag.workflows:
        if not w.active:
            recs.append(("HIGH", f"Workflow {w.name} is INACTIVE — activate or archive."))
        elif w.failure_rate > 0.20:
            recs.append((
                "HIGH",
                f"{w.name} failure rate {w.failure_rate*100:.0f}% "
                f"({w.error}/{w.total_runs} runs in 7d) — investigate.",
            ))

    # Spend caps
    if spend["avg_daily"] > 0.8 * DAILY_CAP:
        recs.append((
            "HIGH",
            f"Daily burn R{spend['avg_daily']:.0f} is {spend['daily_cap_pct']:.0f}% "
            f"of R{DAILY_CAP:.0f} cap — review before more campaigns spin up.",
        ))
    if spend["total_spend"] > 0.8 * MONTHLY_CAP:
        recs.append((
            "HIGH",
            f"Monthly spend R{spend['total_spend']:.0f} is {spend['monthly_cap_pct']:.0f}% "
            f"of R{MONTHLY_CAP:.0f} cap.",
        ))

    # Campaign-level
    for c in camps:
        if c.spend > 500 and c.conversions == 0:
            recs.append((
                "HIGH",
                f"Campaign '{c.name}' ({c.platform}): R{c.spend:.0f} spent, "
                f"0 conversions. Recommend pause or creative refresh.",
            ))
        elif c.spend > 200 and c.ctr < 0.5 and c.impressions > 1000:
            recs.append((
                "MEDIUM",
                f"Campaign '{c.name}': CTR {c.ctr:.2f}% below 0.5% threshold "
                f"after {c.impressions:,} impressions.",
            ))

    # Approvals queue
    now = datetime.now(timezone.utc)
    for a in diag.approvals:
        created = a.get("_createdTime") or a.get("Created At")
        if not created:
            continue
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        age_h = (now - created_dt).total_seconds() / 3600
        if age_h > 48:
            recs.append((
                "MEDIUM",
                f"Approval '{a.get('Campaign Name', '?')}' pending {age_h:.0f}h — "
                f"requested by {a.get('Requested By', '?')}.",
            ))

    if not recs:
        recs.append(("INFO", "No critical issues detected."))
    return recs


# ── Rendering ───────────────────────────────────────────────────────────
def fmt_currency(amount: float) -> str:
    return f"R{amount:,.0f}"


def render_report(diag: Diagnostic) -> str:
    """Build full markdown report."""
    camps = sorted(diag.campaigns, key=lambda c: c.spend, reverse=True)
    spend = compute_spend_summary(diag.perf_records, diag.campaigns)
    recs = generate_recommendations(diag, spend, camps)

    lines: list[str] = []
    now = datetime.now()
    lines.append(f"# AVM Paid Advertising — Full Diagnostic")
    lines.append(f"_Generated {now.strftime('%Y-%m-%d %H:%M')} SAST_")
    lines.append("")

    # ── 1. Executive Summary ──
    health_count = sum(1 for w in diag.workflows if w.health_label == "HEALTHY")
    degraded = sum(1 for w in diag.workflows if w.health_label in ("DEGRADED", "INACTIVE"))
    critical_recs = sum(1 for s, _ in recs if s == "CRITICAL")
    if critical_recs >= 2 or degraded >= 3:
        overall = "🔴 RED"
    elif critical_recs == 1 or degraded >= 1:
        overall = "🟡 YELLOW"
    else:
        overall = "🟢 GREEN"

    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append(f"- **Overall health:** {overall}")
    lines.append(f"- **Days since launch:** {spend['days_since_launch']} (launch 2026-04-08)")
    lines.append(f"- **Total spend:** {fmt_currency(spend['total_spend'])} "
                 f"({spend['monthly_cap_pct']:.1f}% of R{MONTHLY_CAP:,.0f} monthly cap)")
    lines.append(f"- **Avg daily burn:** {fmt_currency(spend['avg_daily'])} "
                 f"({spend['daily_cap_pct']:.0f}% of R{DAILY_CAP:.0f} cap)")
    lines.append(f"- **Projected monthly:** {fmt_currency(spend['projected_monthly'])}")
    lines.append(f"- **Impressions:** {spend['total_impressions']:,} | "
                 f"**Clicks:** {spend['total_clicks']:,} | "
                 f"**Conversions:** {spend['total_conversions']:,}")
    lines.append(f"- **Workflows healthy:** {health_count}/{len(diag.workflows)}")
    lines.append(f"- **Campaigns tracked:** {len(camps)}")
    lines.append(f"- **Pending approvals:** {len(diag.approvals)}")
    lines.append("")

    # ── 2. Operational Health ──
    lines.append("## 2. Operational Health (n8n, last 7 days)")
    lines.append("")
    if not diag.workflows:
        lines.append("_No ADS workflows found in n8n._")
    else:
        lines.append("| Workflow | Status | Active | Runs | Success | Errors | Last Run | Health |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for w in diag.workflows:
            last = (w.last_run or "")[:19].replace("T", " ")
            lines.append(
                f"| {w.name} | `{w.workflow_id}` | {'✅' if w.active else '❌'} | "
                f"{w.total_runs} | {w.success} | {w.error} | {last or '—'} | {w.health_label} |"
            )
    lines.append("")

    # ── 3. Platform Status ──
    lines.append("## 3. Platform Status")
    lines.append("")
    lines.append("| Platform | Status | Account | Spend | Notes |")
    lines.append("|---|---|---|---|---|")
    google_spend = spend["by_platform"].get("google_ads", 0) + spend["by_platform"].get("Google Ads", 0)
    meta_spend = (
        spend["by_platform"].get("meta_ads", 0)
        + spend["by_platform"].get("Meta Ads", 0)
        + spend["by_platform"].get("facebook", 0)
    )
    tiktok_spend = spend["by_platform"].get("tiktok_ads", 0) + spend["by_platform"].get("TikTok Ads", 0)

    google_status = "🟢 Delivering" if google_spend > 0 else "🔴 Blocked (OAuth2 re-auth)"
    meta_status = "🟢 Delivering" if meta_spend > 0 else "🟡 No spend yet"
    tiktok_status = "🔴 Not configured"

    lines.append(
        f"| Google Ads | {google_status} | {GOOGLE_ADS_CUSTOMER_ID} | "
        f"{fmt_currency(google_spend)} | Cred `{GOOGLE_ADS_CRED_ID}` |"
    )
    lines.append(
        f"| Meta Ads | {meta_status} | {META_ACCOUNT_ID} | "
        f"{fmt_currency(meta_spend)} | — |"
    )
    lines.append(
        f"| TikTok Ads | {tiktok_status} | — | "
        f"{fmt_currency(tiktok_spend)} | TIKTOK_ADS_ADVERTISER_ID env unset |"
    )
    lines.append("")

    # ── 4. Spend & Budget ──
    lines.append("## 4. Spend & Budget Analysis")
    lines.append("")
    lines.append(f"- **Total spend (since launch):** {fmt_currency(spend['total_spend'])}")
    lines.append(f"- **Daily cap:** R{DAILY_CAP:.0f} (currently at "
                 f"{spend['daily_cap_pct']:.0f}% avg)")
    lines.append(f"- **Weekly cap:** {fmt_currency(WEEKLY_CAP)}")
    lines.append(f"- **Monthly cap:** {fmt_currency(MONTHLY_CAP)} "
                 f"({spend['monthly_cap_pct']:.1f}% used)")
    lines.append("")
    if spend["by_day"]:
        lines.append("### Daily breakdown")
        lines.append("| Date | Spend | % of cap |")
        lines.append("|---|---|---|")
        for date in sorted(spend["by_day"].keys()):
            amt = spend["by_day"][date]
            pct = amt / DAILY_CAP * 100
            lines.append(f"| {date} | {fmt_currency(amt)} | {pct:.0f}% |")
        lines.append("")
    if spend["by_platform"]:
        lines.append("### By platform")
        for plat, amt in sorted(spend["by_platform"].items(), key=lambda x: -x[1]):
            lines.append(f"- {plat}: {fmt_currency(amt)}")
        lines.append("")
    if diag.budgets:
        lines.append(f"### Budget Allocations ({len(diag.budgets)} records)")
        for b in diag.budgets[:5]:
            name = b.get("Allocation Name", "?")
            planned = float(b.get("Total Budget ZAR") or 0)
            actual = float(b.get("Actual Spend ZAR") or 0)
            variance = actual - planned
            lines.append(
                f"- **{name}**: planned {fmt_currency(planned)} / "
                f"actual {fmt_currency(actual)} / variance {fmt_currency(variance)}"
            )
        lines.append("")

    # ── 5. Campaign Performance ──
    lines.append("## 5. Campaign Performance")
    lines.append("")
    if not camps:
        lines.append("_No campaigns recorded yet._")
    else:
        lines.append("| Campaign | Platform | Status | Spend | Impr | Clicks | CTR | CPC | Conv | CPA |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for c in camps[:20]:
            lines.append(
                f"| {c.name[:40]} | {c.platform} | {c.status} | "
                f"{fmt_currency(c.spend)} | {c.impressions:,} | {c.clicks:,} | "
                f"{c.ctr:.2f}% | R{c.cpc:.2f} | {c.conversions} | "
                f"{'R' + format(c.cpa, '.0f') if c.cpa else '—'} |"
            )
        if len(camps) > 20:
            lines.append(f"_({len(camps) - 20} more campaigns)_")
    lines.append("")

    # ── 6. Creative Performance ──
    lines.append("## 6. Creative Performance & A/B Tests")
    lines.append("")
    lines.append(f"- **Total creatives:** {len(diag.creatives)}")
    if diag.creatives:
        by_format: dict[str, int] = defaultdict(int)
        quality_scores: list[float] = []
        for cr in diag.creatives:
            by_format[cr.get("Ad Format", "?")] += 1
            qs = cr.get("Quality Score")
            if qs is not None:
                try:
                    quality_scores.append(float(qs))
                except (TypeError, ValueError):
                    pass
        lines.append(f"- **By format:** {dict(by_format)}")
        if quality_scores:
            avg_q = sum(quality_scores) / len(quality_scores)
            lines.append(f"- **Avg AI quality score:** {avg_q:.1f}/10 "
                         f"(n={len(quality_scores)})")
    lines.append(f"- **A/B tests:** {len(diag.ab_tests)}")
    running_tests = [t for t in diag.ab_tests if t.get("Status") == "Running"]
    if running_tests:
        lines.append("")
        lines.append("### Running A/B tests")
        for t in running_tests:
            lines.append(
                f"- **{t.get('Test Name', '?')}** "
                f"({t.get('Metric', '?')}, conf {t.get('Confidence', 0)}%)"
            )
    lines.append("")

    # ── 7. Approvals Queue ──
    lines.append("## 7. Pending Approvals")
    lines.append("")
    if not diag.approvals:
        lines.append("_Queue empty._")
    else:
        lines.append("| Campaign | Type | Budget Impact | Requested By | Created |")
        lines.append("|---|---|---|---|---|")
        for a in diag.approvals[:15]:
            created = (a.get("_createdTime") or "")[:10]
            lines.append(
                f"| {a.get('Campaign Name', '?')} | "
                f"{a.get('Request Type', '?')} | "
                f"{fmt_currency(float(a.get('Budget Impact ZAR') or 0))} | "
                f"{a.get('Requested By', '?')} | {created} |"
            )
    lines.append("")

    # ── 8. Recommendations ──
    lines.append("## 8. Recommendations")
    lines.append("")
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    recs.sort(key=lambda r: severity_order.get(r[0], 5))
    icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "ℹ️"}
    for sev, msg in recs:
        lines.append(f"- {icons.get(sev, '•')} **{sev}** — {msg}")
    lines.append("")

    # ── Errors ──
    if diag.errors:
        lines.append("## Diagnostic Errors")
        for e in diag.errors:
            lines.append(f"- {e}")
        lines.append("")

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────
def run() -> Diagnostic:
    diag = Diagnostic()

    log.info("Fetching Airtable data...")
    diag.perf_records = fetch_airtable(TBL_PERFORMANCE)
    log.info("  perf records: %d", len(diag.perf_records))
    campaigns_raw = fetch_airtable(TBL_CAMPAIGNS)
    log.info("  campaigns: %d", len(campaigns_raw))
    diag.budgets = fetch_airtable(TBL_BUDGET)
    log.info("  budgets: %d", len(diag.budgets))
    diag.creatives = fetch_airtable(TBL_CREATIVES)
    log.info("  creatives: %d", len(diag.creatives))
    diag.ab_tests = fetch_airtable(TBL_AB_TESTS)
    log.info("  ab tests: %d", len(diag.ab_tests))
    diag.approvals = fetch_airtable(TBL_APPROVALS, "{Status}='Pending'")
    log.info("  pending approvals: %d", len(diag.approvals))

    diag.campaigns = aggregate_campaigns(campaigns_raw, diag.perf_records)

    log.info("Fetching n8n workflow health...")
    diag.workflows = collect_workflow_health()

    return diag


def main() -> int:
    try:
        diag = run()
    except KeyError as e:
        log.error("Missing required env var: %s", e)
        return 1
    except Exception as e:
        log.exception("Diagnostic run failed: %s", e)
        return 1

    report = render_report(diag)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(report, encoding="utf-8")

    # Console preview: first 60 lines
    preview = "\n".join(report.splitlines()[:60])
    print()
    print(preview)
    print()
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Full report saved to: {OUT_PATH.relative_to(ROOT)}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return 0


if __name__ == "__main__":
    sys.exit(main())

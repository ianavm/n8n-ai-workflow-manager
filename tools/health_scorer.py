"""
Client Health Scorer — Daily health score calculation for AnyVision Media portal.

Calculates composite health scores across four dimensions:
  - Usage (30%): Platform login/event frequency
  - Payment (25%): Subscription status
  - Engagement (25%): Activity growth rate
  - Support (20%): Ticket resolution (placeholder)

Usage:
  python tools/health_scorer.py               # Score all clients
  python tools/health_scorer.py --client-id UUID  # Score one client
"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("health_scorer")

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# Dimension weights
USAGE_WEIGHT = 0.30
PAYMENT_WEIGHT = 0.25
ENGAGEMENT_WEIGHT = 0.25
SUPPORT_WEIGHT = 0.20


@dataclass(frozen=True)
class HealthScore:
    """Immutable health score result for a single client."""
    client_id: str
    usage_score: int
    payment_score: int
    engagement_score: int
    support_score: int
    composite_score: int
    risk_level: str
    trend: str
    days_at_risk: int
    score_details: dict[str, Any]


def supabase_get(path: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """GET request to Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=HEADERS, params=params or {})
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()


def supabase_upsert(table: str, rows: list[dict[str, Any]]) -> None:
    """Upsert rows into a Supabase table (merge-duplicates on conflict)."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    upsert_headers = {
        **HEADERS,
        "Prefer": "resolution=merge-duplicates",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, headers=upsert_headers, json=rows)
        resp.raise_for_status()


def supabase_insert(table: str, row: dict[str, Any]) -> None:
    """Insert a single row into a Supabase table."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, headers=HEADERS, json=row)
        resp.raise_for_status()


def get_all_client_ids() -> list[str]:
    """Fetch all client IDs from the clients table."""
    data = supabase_get("clients", {"select": "id"})
    return [row["id"] for row in data]


def calc_usage_score(client_id: str) -> tuple[int, str]:
    """
    Usage score (30%): based on stat_events in last 30 days.
    >=20 events = 100, >=10 = 70, >=4 = 40, 0 = 10.
    """
    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
    try:
        data = supabase_get("stat_events", {
            "select": "id",
            "client_id": f"eq.{client_id}",
            "created_at": f"gte.{cutoff}",
        })
        count = len(data)
    except httpx.HTTPStatusError:
        # Table may not exist
        count = 0

    if count >= 20:
        score = 100
    elif count >= 10:
        score = 70
    elif count >= 4:
        score = 40
    else:
        score = 10

    detail = f"{count} events in 30d"
    return score, detail


def calc_payment_score(client_id: str) -> tuple[int, str]:
    """
    Payment score (25%): subscription status.
    active=100, past_due=40, canceled=0. +10 bonus if payment_methods exist (capped at 100).
    """
    try:
        subs = supabase_get("subscriptions", {
            "select": "status",
            "client_id": f"eq.{client_id}",
            "order": "created_at.desc",
            "limit": "1",
        })
    except httpx.HTTPStatusError:
        subs = []

    if not subs:
        return 50, "no subscription found"

    status = subs[0].get("status", "unknown")
    base_score = {"active": 100, "trialing": 90, "past_due": 40, "canceled": 0}.get(
        status, 50
    )

    # Bonus for having payment methods
    try:
        methods = supabase_get("payment_methods", {
            "select": "id",
            "client_id": f"eq.{client_id}",
            "limit": "1",
        })
        bonus = 10 if methods else 0
    except httpx.HTTPStatusError:
        bonus = 0

    score = min(base_score + bonus, 100)
    detail = f"status={status}, methods={'yes' if bonus else 'no'}"
    return score, detail


def calc_engagement_score(client_id: str) -> tuple[int, str]:
    """
    Engagement score (25%): compare stat_events in current 30d vs previous 30d.
    >10% increase = 100, stable (within 10%) = 70, declining = 30.
    """
    now = datetime.utcnow()
    current_start = (now - timedelta(days=30)).isoformat()
    prior_start = (now - timedelta(days=60)).isoformat()
    prior_end = (now - timedelta(days=30)).isoformat()

    try:
        current_data = supabase_get("stat_events", {
            "select": "id",
            "client_id": f"eq.{client_id}",
            "created_at": f"gte.{current_start}",
        })
        current_count = len(current_data)
    except httpx.HTTPStatusError:
        current_count = 0

    try:
        prior_data = supabase_get("stat_events", {
            "select": "id",
            "client_id": f"eq.{client_id}",
            "created_at": f"gte.{prior_start}",
            "and": f"(created_at.lt.{prior_end})",
        })
        prior_count = len(prior_data)
    except httpx.HTTPStatusError:
        prior_count = 0

    if prior_count == 0 and current_count == 0:
        score = 50
        growth = "no data"
    elif prior_count == 0:
        score = 100
        growth = "new activity"
    else:
        change_pct = ((current_count - prior_count) / prior_count) * 100
        if change_pct > 10:
            score = 100
        elif change_pct >= -10:
            score = 70
        else:
            score = 30
        growth = f"{change_pct:+.0f}%"

    detail = f"current={current_count}, prior={prior_count}, growth={growth}"
    return score, detail


def calc_support_score() -> tuple[int, str]:
    """
    Support score (20%): placeholder until support ticket table is fully integrated.
    Default: 80.
    """
    return 80, "default (no ticket data yet)"


def determine_risk_level(composite: int) -> str:
    """Map composite score to risk level."""
    if composite < 30:
        return "critical"
    if composite < 50:
        return "high"
    if composite <= 70:
        return "medium"
    return "low"


def determine_trend(client_id: str, current_composite: int) -> str:
    """
    Compare to 7-day-ago score.
    +5 or more = improving, -5 or more = declining, else stable.
    """
    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        prev_scores = supabase_get("client_health_scores", {
            "select": "composite_score",
            "client_id": f"eq.{client_id}",
            "score_date": f"eq.{week_ago}",
            "limit": "1",
        })
    except httpx.HTTPStatusError:
        return "stable"

    if not prev_scores:
        return "stable"

    prev_composite = prev_scores[0].get("composite_score", current_composite)
    diff = current_composite - prev_composite

    if diff >= 5:
        return "improving"
    if diff <= -5:
        return "declining"
    return "stable"


def count_days_at_risk(client_id: str) -> int:
    """Count consecutive days where composite < 70, looking back up to 90 days."""
    try:
        rows = supabase_get("client_health_scores", {
            "select": "composite_score,score_date",
            "client_id": f"eq.{client_id}",
            "order": "score_date.desc",
            "limit": "90",
        })
    except httpx.HTTPStatusError:
        return 0

    consecutive = 0
    for row in rows:
        if row.get("composite_score", 100) < 70:
            consecutive += 1
        else:
            break
    return consecutive


def check_score_drop_alert(client_id: str, current_composite: int) -> None:
    """Create a health_alert if composite dropped >10 points in 7 days."""
    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        prev = supabase_get("client_health_scores", {
            "select": "composite_score",
            "client_id": f"eq.{client_id}",
            "score_date": f"eq.{week_ago}",
            "limit": "1",
        })
    except httpx.HTTPStatusError:
        return

    if not prev:
        return

    prev_score = prev[0].get("composite_score", current_composite)
    drop = prev_score - current_composite

    if drop > 10:
        severity = "critical" if drop > 25 else "high" if drop > 15 else "medium"
        alert_row = {
            "client_id": client_id,
            "alert_type": "score_drop",
            "severity": severity,
            "message": f"Health score dropped {drop} points in 7 days (from {prev_score} to {current_composite})",
            "metadata": {
                "previous_score": prev_score,
                "current_score": current_composite,
                "drop_amount": drop,
            },
            "created_at": datetime.utcnow().isoformat(),
        }
        try:
            supabase_insert("health_alerts", alert_row)
            logger.warning(
                "ALERT: %s — score dropped %d points (%d -> %d)",
                client_id[:8],
                drop,
                prev_score,
                current_composite,
            )
        except httpx.HTTPStatusError as exc:
            logger.error("Failed to create alert for %s: %s", client_id[:8], exc)


def score_client(client_id: str) -> HealthScore:
    """Calculate all health dimensions and produce a composite score for one client."""
    usage_score, usage_detail = calc_usage_score(client_id)
    payment_score, payment_detail = calc_payment_score(client_id)
    engagement_score, engagement_detail = calc_engagement_score(client_id)
    support_score, support_detail = calc_support_score()

    composite = round(
        usage_score * USAGE_WEIGHT
        + payment_score * PAYMENT_WEIGHT
        + engagement_score * ENGAGEMENT_WEIGHT
        + support_score * SUPPORT_WEIGHT
    )

    risk_level = determine_risk_level(composite)
    trend = determine_trend(client_id, composite)
    days_at_risk = count_days_at_risk(client_id)

    return HealthScore(
        client_id=client_id,
        usage_score=usage_score,
        payment_score=payment_score,
        engagement_score=engagement_score,
        support_score=support_score,
        composite_score=composite,
        risk_level=risk_level,
        trend=trend,
        days_at_risk=days_at_risk,
        score_details={
            "usage": usage_detail,
            "payment": payment_detail,
            "engagement": engagement_detail,
            "support": support_detail,
        },
    )


def persist_score(score: HealthScore) -> None:
    """Upsert the score into client_health_scores and check for alerts."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    row = {
        "client_id": score.client_id,
        "score_date": today,
        "usage_score": score.usage_score,
        "payment_score": score.payment_score,
        "engagement_score": score.engagement_score,
        "support_score": score.support_score,
        "composite_score": score.composite_score,
        "risk_level": score.risk_level,
        "trend": score.trend,
        "days_at_risk": score.days_at_risk,
        "score_details": score.score_details,
    }

    supabase_upsert("client_health_scores", [row])
    check_score_drop_alert(score.client_id, score.composite_score)


def print_summary(scores: list[HealthScore]) -> None:
    """Print a human-readable summary of all scored clients."""
    if not scores:
        logger.info("No clients to score.")
        return

    logger.info("=" * 70)
    logger.info("HEALTH SCORE SUMMARY — %s", datetime.utcnow().strftime("%Y-%m-%d"))
    logger.info("=" * 70)
    logger.info(
        "%-10s  %5s  %5s  %5s  %5s  %5s  %-8s  %-10s  %s",
        "Client", "Usage", "Pay", "Eng", "Supp", "Total", "Risk", "Trend", "At Risk",
    )
    logger.info("-" * 70)

    for s in sorted(scores, key=lambda x: x.composite_score):
        logger.info(
            "%-10s  %5d  %5d  %5d  %5d  %5d  %-8s  %-10s  %dd",
            s.client_id[:10],
            s.usage_score,
            s.payment_score,
            s.engagement_score,
            s.support_score,
            s.composite_score,
            s.risk_level,
            s.trend,
            s.days_at_risk,
        )

    critical = [s for s in scores if s.risk_level == "critical"]
    high = [s for s in scores if s.risk_level == "high"]
    declining = [s for s in scores if s.trend == "declining"]

    logger.info("-" * 70)
    logger.info(
        "Totals: %d scored | %d critical | %d high risk | %d declining",
        len(scores),
        len(critical),
        len(high),
        len(declining),
    )
    logger.info("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate client health scores")
    parser.add_argument("--client-id", type=str, help="Score a specific client by UUID")
    args = parser.parse_args()

    if args.client_id:
        client_ids = [args.client_id]
        logger.info("Scoring single client: %s", args.client_id)
    else:
        client_ids = get_all_client_ids()
        logger.info("Found %d clients to score", len(client_ids))

    results: list[HealthScore] = []
    for cid in client_ids:
        try:
            score = score_client(cid)
            persist_score(score)
            results.append(score)
            logger.info(
                "Scored %s: composite=%d risk=%s trend=%s",
                cid[:10],
                score.composite_score,
                score.risk_level,
                score.trend,
            )
        except Exception as exc:
            logger.error("Failed to score client %s: %s", cid[:10], exc)

    print_summary(results)


if __name__ == "__main__":
    main()

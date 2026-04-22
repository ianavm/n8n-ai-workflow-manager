"""Idempotent setup for the CRM module Supabase schema (migration 031).

Usage
-----
    python tools/setup_crm_supabase.py --check          # Verify tables exist, report counts
    python tools/setup_crm_supabase.py --client-id <uuid> --seed-demo
                                                        # Seed demo companies/contacts/leads for one client

Requires:
    SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) and SUPABASE_SERVICE_ROLE_KEY in .env.

The DDL itself lives in ``client-portal/supabase/migrations/031_crm_module.sql``
and is applied via ``supabase db push`` (or the Supabase Studio SQL editor).
This script does NOT execute DDL — it only verifies and seeds sample data.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("ERROR: httpx not installed. Run: pip install httpx")

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("setup_crm_supabase")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


SUPABASE_URL: str = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    sys.exit("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")


CRM_TABLES: tuple[str, ...] = (
    "crm_config",
    "crm_stages",
    "crm_companies",
    "crm_contacts",
    "crm_leads",
    "crm_activities",
    "crm_email_templates",
    "crm_email_messages",
    "crm_research_reports",
    "crm_imports",
)


# ---------------------------------------------------------------------------
# Supabase REST helpers
# ---------------------------------------------------------------------------


def _headers(prefer: str | None = None) -> dict[str, str]:
    h: dict[str, str] = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def supabase_get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    try:
        resp = httpx.get(url, params=params, headers=_headers(), timeout=30)
    except httpx.RequestError as exc:
        logger.error("GET %s failed: %s", table, exc)
        return []
    if resp.status_code != 200:
        logger.error("GET %s -> %s %s", table, resp.status_code, resp.text[:200])
        return []
    return resp.json()


def supabase_count(table: str, filters: dict[str, str] | None = None) -> int:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {"select": "id"}
    if filters:
        params.update(filters)
    try:
        resp = httpx.get(
            url,
            params=params,
            headers={**_headers(), "Prefer": "count=exact", "Range": "0-0"},
            timeout=30,
        )
    except httpx.RequestError as exc:
        logger.error("COUNT %s failed: %s", table, exc)
        return -1
    if resp.status_code not in (200, 206):
        logger.error("COUNT %s -> %s %s", table, resp.status_code, resp.text[:200])
        return -1
    content_range = resp.headers.get("content-range", "*/0")
    total = content_range.split("/")[-1]
    return int(total) if total.isdigit() else -1


def supabase_post(table: str, data: dict[str, Any]) -> dict[str, Any]:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    try:
        resp = httpx.post(
            url,
            json=data,
            headers=_headers("return=representation"),
            timeout=30,
        )
    except httpx.RequestError as exc:
        logger.error("POST %s failed: %s", table, exc)
        return {}
    if resp.status_code not in (200, 201):
        logger.error("POST %s -> %s %s", table, resp.status_code, resp.text[:300])
        return {}
    body = resp.json()
    return body[0] if isinstance(body, list) else body


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TableReport:
    table: str
    rows: int


def verify_schema() -> list[TableReport]:
    reports: list[TableReport] = []
    for t in CRM_TABLES:
        reports.append(TableReport(table=t, rows=supabase_count(t)))
    return reports


def print_report(reports: list[TableReport]) -> None:
    logger.info("%s", "=" * 56)
    logger.info("CRM module schema check")
    logger.info("%s", "=" * 56)
    for r in reports:
        mark = "OK" if r.rows >= 0 else "MISSING"
        logger.info("  %-26s %6s rows   [%s]", r.table, r.rows if r.rows >= 0 else "—", mark)


# ---------------------------------------------------------------------------
# Demo seed
# ---------------------------------------------------------------------------


DEMO_COMPANIES: tuple[dict[str, Any], ...] = (
    {"name": "Aurora Logistics", "domain": "auroralogistics.co.za", "industry": "Logistics", "country": "South Africa", "size_band": "51-200", "hq_city": "Johannesburg"},
    {"name": "Kopano Health", "domain": "kopanohealth.co.za", "industry": "Healthcare", "country": "South Africa", "size_band": "11-50", "hq_city": "Cape Town"},
    {"name": "Veldt Financial", "domain": "veldtfinancial.co.za", "industry": "Financial Services", "country": "South Africa", "size_band": "201-500", "hq_city": "Sandton"},
    {"name": "Baobab Media", "domain": "baobabmedia.co.za", "industry": "Media", "country": "South Africa", "size_band": "11-50", "hq_city": "Durban"},
    {"name": "Safari E-commerce", "domain": "safari-ec.com", "industry": "E-commerce", "country": "South Africa", "size_band": "1-10", "hq_city": "Pretoria"},
)

DEMO_CONTACTS: tuple[tuple[int, dict[str, Any]], ...] = (
    (0, {"first_name": "Nomusa", "last_name": "Dlamini", "title": "COO", "email": "nomusa@auroralogistics.co.za"}),
    (1, {"first_name": "Sipho", "last_name": "Nkosi", "title": "CEO", "email": "sipho@kopanohealth.co.za"}),
    (2, {"first_name": "Lerato", "last_name": "Mbeki", "title": "Head of Growth", "email": "lerato@veldtfinancial.co.za"}),
    (3, {"first_name": "Riaan", "last_name": "Kruger", "title": "Founder", "email": "riaan@baobabmedia.co.za"}),
    (4, {"first_name": "Ayesha", "last_name": "Patel", "title": "Marketing Lead", "email": "ayesha@safari-ec.com"}),
)

DEMO_LEAD_STAGES: tuple[str, ...] = (
    "new",
    "enriched",
    "researched",
    "outreach_sent",
    "replied",
)


def seed_demo_for_client(client_id: str) -> None:
    logger.info("Seeding demo CRM data for client %s", client_id)

    company_ids: list[str] = []
    for company in DEMO_COMPANIES:
        payload = {**company, "client_id": client_id}
        result = supabase_post("crm_companies", payload)
        if result:
            company_ids.append(result["id"])
            logger.info("  + company %s", company["name"])

    contact_ids: list[str] = []
    for idx, contact in DEMO_CONTACTS:
        payload = {**contact, "client_id": client_id, "company_id": company_ids[idx]}
        result = supabase_post("crm_contacts", payload)
        if result:
            contact_ids.append(result["id"])
            logger.info("  + contact %s %s", contact["first_name"], contact["last_name"])

    for idx in range(len(company_ids)):
        lead_payload = {
            "client_id": client_id,
            "company_id": company_ids[idx],
            "contact_id": contact_ids[idx],
            "stage_key": DEMO_LEAD_STAGES[idx % len(DEMO_LEAD_STAGES)],
            "score": 50 + idx * 8,
            "source": "demo_seed",
            "deal_value_zar": 15000 * (idx + 1),
            "deal_probability": 20 + idx * 10,
        }
        result = supabase_post("crm_leads", lead_payload)
        if result:
            logger.info("  + lead for %s (stage=%s)", DEMO_COMPANIES[idx]["name"], lead_payload["stage_key"])

    logger.info("Demo seed complete.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="CRM Supabase setup helper")
    parser.add_argument("--check", action="store_true", help="Verify schema + row counts")
    parser.add_argument("--client-id", help="Target client UUID for --seed-demo")
    parser.add_argument("--seed-demo", action="store_true", help="Insert demo companies / contacts / leads")
    args = parser.parse_args()

    if args.check:
        print_report(verify_schema())

    if args.seed_demo:
        if not args.client_id:
            sys.exit("ERROR: --seed-demo requires --client-id <uuid>")
        seed_demo_for_client(args.client_id)


if __name__ == "__main__":
    main()

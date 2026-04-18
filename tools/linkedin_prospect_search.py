"""LinkedIn prospect search via Apify Google Search Scraper.

Finds public LinkedIn profiles matching AnyVision Media's SA ICP, then writes
deduplicated prospects to Airtable LI_Leads for the LI-03..LI-09 pipeline.

Usage:
    python tools/linkedin_prospect_search.py --count 30
    python tools/linkedin_prospect_search.py --count 30 --dry-run
    python tools/linkedin_prospect_search.py --count 30 --campaign "CAMP-001"
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


APIFY_ACTOR = "apify~google-search-scraper"
APIFY_RUN_SYNC_URL = (
    f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items"
)
AIRTABLE_BASE_URL = "https://api.airtable.com/v0"
AIRTABLE_BATCH_LIMIT = 10

ICP_TITLES: tuple[str, ...] = (
    "Operations Director",
    "COO",
    "Managing Director",
    "CEO",
    "Marketing Director",
)
ICP_LOCATIONS: tuple[str, ...] = (
    "Johannesburg",
    "Gauteng",
    "Cape Town",
    "South Africa",
)


@dataclass(frozen=True)
class Prospect:
    full_name: str
    first_name: str
    last_name: str
    title: str
    company_name: str
    location: str
    linkedin_url: str


def _require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        sys.stderr.write(f"ERROR: {key} not set in .env\n")
        sys.exit(2)
    return value


def build_queries(titles: Iterable[str], locations: Iterable[str]) -> list[str]:
    return [f'site:linkedin.com/in "{t}" "{loc}"' for t in titles for loc in locations]


def call_apify(token: str, queries: list[str], timeout: float = 180.0) -> list[dict]:
    payload = {
        "queries": "\n".join(queries),
        "resultsPerPage": 30,
        "maxPagesPerQuery": 1,
        "countryCode": "za",
        "languageCode": "en",
        "mobileResults": False,
        "saveHtml": False,
        "saveHtmlToKeyValueStore": False,
    }
    params = {"token": token}
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(APIFY_RUN_SYNC_URL, params=params, json=payload)
        resp.raise_for_status()
        return resp.json()


def _normalize_linkedin_url(url: str) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").rstrip("/")
    if "linkedin.com" not in host:
        return None
    if not path.lower().startswith("/in/"):
        return None
    slug = path.split("/in/", 1)[1].split("/")[0]
    if not slug:
        return None
    return f"https://www.linkedin.com/in/{slug.lower()}"


_SEP = re.compile(r"\s+[-–|·]\s+|\s+\|\s+")


def _strip_linkedin_suffix(text: str) -> str:
    return re.sub(r"\s*\|\s*LinkedIn.*$", "", text, flags=re.IGNORECASE).strip()


def parse_search_result(item: dict) -> Prospect | None:
    url = item.get("url") or ""
    canonical = _normalize_linkedin_url(url)
    if not canonical:
        return None

    raw_title = _strip_linkedin_suffix(item.get("title") or "")
    description = (item.get("description") or "").strip()

    segments = [s.strip() for s in _SEP.split(raw_title) if s.strip()]
    if len(segments) < 2:
        return None

    full_name = segments[0]
    title = segments[1]
    company = segments[2] if len(segments) >= 3 else ""

    if not company and " at " in title:
        t_part, c_part = title.rsplit(" at ", 1)
        title = t_part.strip()
        company = c_part.strip()

    if not company and description:
        m = re.search(r"\bat\s+([A-Z][\w &().,'-]+)", description)
        if m:
            company = m.group(1).strip(" .,")

    location = ""
    if description:
        for loc in ICP_LOCATIONS:
            if loc.lower() in description.lower():
                location = loc
                break

    name_parts = full_name.split()
    first_name = name_parts[0] if name_parts else ""
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    return Prospect(
        full_name=full_name,
        first_name=first_name,
        last_name=last_name,
        title=title,
        company_name=company,
        location=location,
        linkedin_url=canonical,
    )


def extract_prospects(results: list[dict]) -> list[Prospect]:
    prospects: list[Prospect] = []
    seen: set[str] = set()
    for group in results:
        items = group.get("organicResults") or group.get("results") or []
        if isinstance(group, dict) and not items and group.get("url"):
            items = [group]
        for item in items:
            prospect = parse_search_result(item)
            if prospect is None:
                continue
            if prospect.linkedin_url in seen:
                continue
            seen.add(prospect.linkedin_url)
            prospects.append(prospect)
    return prospects


def fetch_existing_urls(
    urls: list[str], token: str, base_id: str, table_id: str
) -> set[str]:
    if not urls:
        return set()
    existing: set[str] = set()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{AIRTABLE_BASE_URL}/{base_id}/{table_id}"
    with httpx.Client(timeout=60.0, headers=headers) as client:
        for i in range(0, len(urls), 20):
            chunk = urls[i : i + 20]
            conditions = ",".join(f"{{LinkedIn URL}}='{u}'" for u in chunk)
            params = {
                "filterByFormula": f"OR({conditions})",
                "fields[]": "LinkedIn URL",
                "pageSize": 100,
            }
            resp = client.get(url, params=params)
            resp.raise_for_status()
            for rec in resp.json().get("records", []):
                lurl = (rec.get("fields") or {}).get("LinkedIn URL")
                if lurl:
                    existing.add(_normalize_linkedin_url(lurl) or lurl)
    return existing


def insert_prospects(
    prospects: list[Prospect],
    token: str,
    base_id: str,
    table_id: str,
    campaign: str,
) -> int:
    if not prospects:
        return 0
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"{AIRTABLE_BASE_URL}/{base_id}/{table_id}"
    inserted = 0
    with httpx.Client(timeout=60.0, headers=headers) as client:
        for i in range(0, len(prospects), AIRTABLE_BATCH_LIMIT):
            batch = prospects[i : i + AIRTABLE_BATCH_LIMIT]
            records = []
            for p in batch:
                fields = {
                    "Full Name": p.full_name,
                    "First Name": p.first_name,
                    "Last Name": p.last_name,
                    "Title": p.title,
                    "Company Name": p.company_name,
                    "Location": p.location,
                    "LinkedIn URL": p.linkedin_url,
                    "Source": "Apify",
                    "Status": "New",
                }
                if campaign:
                    fields["Campaign ID"] = campaign
                records.append({"fields": {k: v for k, v in fields.items() if v}})
            resp = client.post(url, json={"records": records, "typecast": True})
            resp.raise_for_status()
            inserted += len(resp.json().get("records", []))
            time.sleep(0.25)
    return inserted


def write_csv(prospects: list[Prospect], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(prospects[0]).keys()) if prospects else ["linkedin_url"])
        writer.writeheader()
        for p in prospects:
            writer.writerow(asdict(p))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search LinkedIn via Apify and write to Airtable.")
    parser.add_argument("--count", type=int, default=30, help="Target number of prospects (default 30).")
    parser.add_argument("--dry-run", action="store_true", help="Print CSV only; no Airtable write.")
    parser.add_argument("--campaign", default="", help="Campaign ID to attach to each lead.")
    parser.add_argument(
        "--csv-out",
        default=str(REPO_ROOT / ".tmp" / "linkedin_prospects.csv"),
        help="CSV output path (written on every run).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    apify_token = _require_env("APIFY_API_TOKEN")
    base_id = os.environ.get("MARKETING_AIRTABLE_BASE_ID") or "apptjjBx34z9340tK"
    table_id = _require_env("LI_TABLE_LEADS")
    airtable_token = _require_env("AIRTABLE_API_TOKEN") if not args.dry_run else ""

    queries = build_queries(ICP_TITLES, ICP_LOCATIONS)
    print(f"[search] {len(queries)} Google queries against Apify {APIFY_ACTOR}")

    raw = call_apify(apify_token, queries)
    candidates = extract_prospects(raw)
    filtered_out = sum(
        len(g.get("organicResults") or g.get("results") or []) for g in raw
    ) - len(candidates)
    print(f"[parse]  {len(candidates)} unique LinkedIn /in/ profiles (filtered {filtered_out})")

    csv_path = Path(args.csv_out)
    write_csv(candidates, csv_path)
    print(f"[csv]    wrote {csv_path}")

    if args.dry_run:
        print(f"[dry-run] would insert up to {args.count} prospects; exiting without Airtable writes.")
        return 0

    existing = fetch_existing_urls([p.linkedin_url for p in candidates], airtable_token, base_id, table_id)
    new_prospects = [p for p in candidates if p.linkedin_url not in existing][: args.count]
    print(f"[dedupe] {len(existing)} already in Airtable; {len(new_prospects)} new to insert")

    inserted = insert_prospects(new_prospects, airtable_token, base_id, table_id, args.campaign)
    print(f"[done]   Inserted {inserted}, Skipped-duplicate {len(existing)}, Filtered-out {filtered_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

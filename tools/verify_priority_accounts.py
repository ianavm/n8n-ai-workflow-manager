"""Re-verify priority LI_Leads accounts before outreach.

Priority accounts are LI_Leads records whose Source Metadata JSON contains
`"priority": true`. They were seeded manually from research (see
`.claude/plans/happy-finding-eagle.md`) and need periodic liveness checks so
stale hiring hooks, dead websites, or wound-down companies don't end up in
outbound sequences.

What it checks per account:
  - Company Website reachable (HEAD, follows redirects, 200-399 = OK)
  - LinkedIn URL reachable (best-effort; LinkedIn returns 999/403 for bot
    traffic, so those codes are treated as "manual verify needed", not fail)
  - `hook_url` in Source Metadata (e.g. Himalayas job post) — the freshness of
    this URL is the single most important signal for outreach hooks

Outputs a human-readable report to stdout. With `--update`, also writes
`last_verified` timestamp and per-URL results back into each record's
Source Metadata.

Usage:
    python tools/verify_priority_accounts.py            # report only
    python tools/verify_priority_accounts.py --update   # write back to Airtable
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("verify_priority")

AIRTABLE_TOKEN = os.getenv("AIRTABLE_API_TOKEN")
MARKETING_BASE_ID = "apptjjBx34z9340tK"
LEADS_TABLE = "LI_Leads"

AIRTABLE_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json",
}

HTTP_TIMEOUT = 15.0
USER_AGENT = (
    "Mozilla/5.0 (compatible; AVMVerifyBot/1.0; "
    "+https://anyvisionmedia.com)"
)


@dataclass(frozen=True)
class PriorityAccount:
    record_id: str
    lead_id: str
    company_name: str
    company_website: str
    linkedin_url: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class CheckResult:
    url: str
    status: int | None
    ok: bool
    note: str = ""
    skipped: bool = False  # True when URL was empty/missing — not a failure


@dataclass(frozen=True)
class AccountReport:
    account: PriorityAccount
    website: CheckResult
    linkedin: CheckResult
    hook: CheckResult | None


def fetch_priority_accounts() -> list[PriorityAccount]:
    """Return every LI_Leads record with priority=true in Source Metadata."""
    accounts: list[PriorityAccount] = []
    offset: str | None = None

    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if offset:
            params["offset"] = offset

        r = httpx.get(
            f"https://api.airtable.com/v0/{MARKETING_BASE_ID}/{LEADS_TABLE}",
            headers=AIRTABLE_HEADERS,
            params=params,
            timeout=30.0,
        )
        r.raise_for_status()
        data = r.json()

        for rec in data.get("records", []):
            fields = rec.get("fields", {})
            metadata_raw = fields.get("Source Metadata") or ""
            if not metadata_raw:
                continue
            try:
                metadata = json.loads(metadata_raw)
            except json.JSONDecodeError:
                continue
            if not metadata.get("priority"):
                continue

            accounts.append(
                PriorityAccount(
                    record_id=rec["id"],
                    lead_id=fields.get("Lead ID", ""),
                    company_name=fields.get("Company Name", ""),
                    company_website=fields.get("Company Website", ""),
                    linkedin_url=fields.get("LinkedIn URL", ""),
                    metadata=metadata,
                )
            )

        offset = data.get("offset")
        if not offset:
            break

    return accounts


def check_url(url: str, *, tolerate_bot_block: bool = False) -> CheckResult:
    """HEAD-check a URL (follows redirects). Falls back to GET on 405."""
    if not url:
        return CheckResult(
            url=url,
            status=None,
            ok=True,
            note="not set (TBD)",
            skipped=True,
        )

    headers = {"User-Agent": USER_AGENT}
    try:
        r = httpx.head(
            url,
            headers=headers,
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
        )
        if r.status_code == 405:
            r = httpx.get(
                url,
                headers=headers,
                timeout=HTTP_TIMEOUT,
                follow_redirects=True,
            )
        status = r.status_code
    except httpx.RequestError as exc:
        return CheckResult(url=url, status=None, ok=False, note=f"network: {exc}")

    if tolerate_bot_block and status in (999, 403, 429):
        return CheckResult(
            url=url,
            status=status,
            ok=True,
            note="bot-block; manual verify",
        )

    ok = 200 <= status < 400
    return CheckResult(
        url=url,
        status=status,
        ok=ok,
        note="" if ok else f"http {status}",
    )


def verify_account(account: PriorityAccount) -> AccountReport:
    website = check_url(account.company_website, tolerate_bot_block=True)
    linkedin = check_url(account.linkedin_url, tolerate_bot_block=True)

    hook: CheckResult | None = None
    hook_url = account.metadata.get("hook_url")
    if isinstance(hook_url, str) and hook_url:
        hook = check_url(hook_url, tolerate_bot_block=True)

    return AccountReport(
        account=account,
        website=website,
        linkedin=linkedin,
        hook=hook,
    )


def update_record(report: AccountReport) -> None:
    """Append last_verified + per-URL results to Source Metadata."""
    metadata: dict[str, Any] = dict(report.account.metadata)
    metadata["last_verified"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    metadata["verification_results"] = {
        "website": {
            "status": report.website.status,
            "ok": report.website.ok,
            "note": report.website.note,
        },
        "linkedin": {
            "status": report.linkedin.status,
            "ok": report.linkedin.ok,
            "note": report.linkedin.note,
        },
        "hook": (
            {
                "status": report.hook.status,
                "ok": report.hook.ok,
                "note": report.hook.note,
            }
            if report.hook
            else None
        ),
    }

    r = httpx.patch(
        f"https://api.airtable.com/v0/{MARKETING_BASE_ID}/{LEADS_TABLE}/{report.account.record_id}",
        headers=AIRTABLE_HEADERS,
        json={"fields": {"Source Metadata": json.dumps(metadata)}},
        timeout=30.0,
    )
    r.raise_for_status()


def _format_line(label: str, result: CheckResult) -> str:
    if result.skipped:
        icon = "[SKIP]"
    elif result.ok:
        icon = "[OK]  "
    else:
        icon = "[FAIL]"
    status = str(result.status) if result.status is not None else "---"
    extra = f"  ({result.note})" if result.note else ""
    url_display = result.url or "(none)"
    return f"    {icon} {label:<9} {status:<5}  {url_display}{extra}"


def print_report(reports: list[AccountReport]) -> None:
    print()
    print("=" * 88)
    print(f"  PRIORITY ACCOUNT VERIFICATION  ({len(reports)} accounts)")
    print("=" * 88)

    for rep in reports:
        a = rep.account
        motion = a.metadata.get("motion", "n/a")
        urgency = a.metadata.get("urgency", "n/a")
        print()
        print(f"  [{a.lead_id}]  {a.company_name}")
        print(f"    motion={motion}  urgency={urgency}")
        print(_format_line("website", rep.website))
        print(_format_line("linkedin", rep.linkedin))
        if rep.hook is not None:
            print(_format_line("hook", rep.hook))
        else:
            print("    [----] hook      ---    (no hook_url in metadata)")

    print()
    print("-" * 88)
    total = len(reports)
    website_ok = sum(1 for r in reports if r.website.ok and not r.website.skipped)
    linkedin_set = [r for r in reports if not r.linkedin.skipped]
    linkedin_ok = sum(1 for r in linkedin_set if r.linkedin.ok)
    hook_reports = [r for r in reports if r.hook is not None]
    hook_ok = sum(1 for r in hook_reports if r.hook is not None and r.hook.ok)

    stale_sites = [
        r.account.lead_id
        for r in reports
        if not r.website.skipped and not r.website.ok
    ]
    broken_linkedin = [
        r.account.lead_id
        for r in linkedin_set
        if not r.linkedin.ok
    ]
    tbd_linkedin = [
        r.account.lead_id
        for r in reports
        if r.linkedin.skipped
    ]
    dead_hooks = [
        r.account.lead_id
        for r in hook_reports
        if r.hook is not None and not r.hook.ok
    ]

    print(f"  Websites reachable : {website_ok}/{total}")
    print(f"  LinkedIn reachable : {linkedin_ok}/{len(linkedin_set)}  (999/403/429 tolerated; {len(tbd_linkedin)} not set)")
    print(f"  Hook URLs live     : {hook_ok}/{len(hook_reports)}")
    if stale_sites:
        print(f"  WARN stale sites      : {', '.join(stale_sites)}")
    if broken_linkedin:
        print(f"  WARN broken linkedin  : {', '.join(broken_linkedin)}  (fix slug or blank it)")
    if tbd_linkedin:
        print(f"  INFO linkedin TBD     : {', '.join(tbd_linkedin)}  (manual lookup needed)")
    if dead_hooks:
        print(f"  WARN dead hooks       : {', '.join(dead_hooks)}  (rewrite outreach angle)")
    if not stale_sites and not broken_linkedin and not dead_hooks:
        print("  All set URLs verified clean.")
    print("=" * 88)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify priority LI_Leads accounts before outreach."
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Write verification results back to Source Metadata in Airtable",
    )
    args = parser.parse_args()

    if not AIRTABLE_TOKEN:
        log.error("AIRTABLE_API_TOKEN missing from .env")
        return 1

    log.info(
        "Fetching priority accounts from base=%s table=%s",
        MARKETING_BASE_ID,
        LEADS_TABLE,
    )
    try:
        accounts = fetch_priority_accounts()
    except httpx.HTTPError as exc:
        log.error("Airtable fetch failed: %s", exc)
        return 2

    if not accounts:
        log.info("No priority accounts found (nothing to verify).")
        return 0

    log.info("Verifying %d priority accounts...", len(accounts))
    reports = [verify_account(a) for a in accounts]

    print_report(reports)

    if args.update:
        log.info("Writing verification results back to Airtable...")
        for rep in reports:
            try:
                update_record(rep)
            except httpx.HTTPError as exc:
                log.warning("Failed to update %s: %s", rep.account.lead_id, exc)
        log.info("Airtable update complete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

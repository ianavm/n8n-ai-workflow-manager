"""Strip the AVM client portal down to a curated demo-only set.

One-shot cleanup. Hard-deletes every client not in KEEP_EMAILS from the Supabase
`clients` table (cascades to workflows/stats/subs/etc.) and removes their
auth.users record. Prints a dry-run preview and requires typing 'DELETE' to
proceed.

Usage:
    python tools/cleanup_portal_demo_only.py            # dry-run + prompt
    python tools/cleanup_portal_demo_only.py --execute  # same flow (explicit)

`admin_users` table is intentionally untouched (internal staff access).
"""
from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client
from tabulate import tabulate

load_dotenv()

KEEP_EMAILS: frozenset[str] = frozenset(
    {
        "test@testemail.com",
        "client@testemail.com",
        "ian@anyvisionmedia.com",
    }
)

DEPENDENT_TABLES: tuple[str, ...] = (
    "workflows",
    "stat_events",
    "workflow_executions",
    "client_notes",
    "subscriptions",
    "invoices",
    "payment_methods",
    "usage_records",
)


def build_client() -> Client:
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        sys.exit("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    return create_client(url, key)


def fetch_all_clients(sb: Client) -> list[dict[str, Any]]:
    res = (
        sb.table("clients")
        .select("id,auth_user_id,email,full_name,company_name,status,created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def fetch_subscription(sb: Client, client_id: str) -> dict[str, Any] | None:
    res = (
        sb.table("subscriptions")
        .select("status,trial_end,plan_id")
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def count_dependents(sb: Client, client_ids: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for tbl in DEPENDENT_TABLES:
        res = (
            sb.table(tbl)
            .select("id", count="exact")
            .in_("client_id", client_ids)
            .limit(1)
            .execute()
        )
        counts[tbl] = res.count or 0
    return counts


def partition(clients: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    keep, delete = [], []
    for c in clients:
        (keep if c["email"] in KEEP_EMAILS else delete).append(c)
    return keep, delete


def render_clients_table(rows: list[dict[str, Any]], sb: Client) -> str:
    if not rows:
        return "(none)"
    out = []
    for c in rows:
        sub = fetch_subscription(sb, c["id"])
        out.append(
            [
                c["email"],
                (c.get("full_name") or "")[:30],
                (c.get("company_name") or "")[:30],
                c.get("status") or "",
                (sub or {}).get("status") or "—",
                (sub or {}).get("trial_end") or "—",
            ]
        )
    return tabulate(
        out,
        headers=["email", "name", "company", "status", "sub", "trial_end"],
        tablefmt="simple",
    )


def assert_keep_list_present(keep: list[dict[str, Any]]) -> None:
    found = {c["email"] for c in keep}
    missing = KEEP_EMAILS - found
    if missing:
        sys.exit(
            f"ERROR: keep-list emails missing from live clients: {sorted(missing)}. "
            "Aborting — would not preserve the intended demo set."
        )


def delete_one(sb: Client, client: dict[str, Any]) -> tuple[bool, bool, str]:
    """Returns (db_ok, auth_ok, message)."""
    cid, auth_uid, email = client["id"], client["auth_user_id"], client["email"]
    try:
        sb.table("clients").delete().eq("id", cid).execute()
        db_ok = True
    except Exception as e:
        return False, False, f"{email}: DB delete failed: {e}"
    try:
        sb.auth.admin.delete_user(auth_uid)
        auth_ok = True
        return db_ok, auth_ok, f"{email}: removed (db + auth)"
    except Exception as e:
        return db_ok, False, (
            f"{email}: DB row removed but auth delete FAILED "
            f"(orphan auth_user_id={auth_uid}): {e}"
        )


def main() -> int:
    sb = build_client()

    print("Fetching live clients...")
    clients = fetch_all_clients(sb)
    print(f"Found {len(clients)} client records.\n")

    keep, delete = partition(clients)
    assert_keep_list_present(keep)

    print("=" * 70)
    print(f"KEEP ({len(keep)}):")
    print("=" * 70)
    print(render_clients_table(keep, sb))
    print()
    print("=" * 70)
    print(f"DELETE ({len(delete)}):")
    print("=" * 70)
    print(render_clients_table(delete, sb))
    print()

    if not delete:
        print("Nothing to delete. Exiting.")
        return 0

    delete_ids = [c["id"] for c in delete]
    print("Cascade row counts that will be removed:")
    counts = count_dependents(sb, delete_ids)
    print(tabulate(counts.items(), headers=["table", "rows"], tablefmt="simple"))

    activity_res = (
        sb.table("activity_log")
        .select("id", count="exact")
        .in_("actor_id", delete_ids)
        .limit(1)
        .execute()
    )
    print(
        f"  activity_log (actor_id, no FK, cleaned explicitly): {activity_res.count or 0}"
    )
    print()

    print(
        "Hard delete is IRREVERSIBLE. Type 'DELETE' (uppercase, no quotes) to proceed, "
        "anything else aborts."
    )
    try:
        confirm = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return 1
    if confirm != "DELETE":
        print("Aborted — confirmation phrase not matched.")
        return 1

    print("\nExecuting deletes...")
    all_ok = True
    for c in delete:
        db_ok, auth_ok, msg = delete_one(sb, c)
        marker = "OK " if (db_ok and auth_ok) else "WARN"
        print(f"  [{marker}] {msg}")
        if not (db_ok and auth_ok):
            all_ok = False

    try:
        activity_del = (
            sb.table("activity_log").delete().in_("actor_id", delete_ids).execute()
        )
        print(f"  [OK ] activity_log: removed {len(activity_del.data or [])} orphan rows")
    except Exception as e:
        print(f"  [WARN] activity_log cleanup failed: {e}")
        all_ok = False

    print("\nPost-verification:")
    remaining = fetch_all_clients(sb)
    remaining_emails = sorted(c["email"] for c in remaining)
    print(f"  clients remaining: {len(remaining)}")
    for e in remaining_emails:
        print(f"    - {e}")

    expected = sorted(KEEP_EMAILS)
    if remaining_emails != expected:
        print(
            f"\nWARN: remaining emails {remaining_emails} != expected {expected}."
        )
        all_ok = False

    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())

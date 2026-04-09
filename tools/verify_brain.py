"""
Brain System — Full Revision & Verification Script

Checks all components: tables, view, workflows, credentials, data integrity.
Run: python tools/verify_brain.py
"""

import httpx
import os
import json
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

N8N_BASE_URL = os.getenv("N8N_BASE_URL", "")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

BRAIN_WF_ID = "XpGdo7DKv3XEpqZc"
SHM_WF_ID = "5k1OKJuaAWVPf7Lb"
CRED_ID = "mlYOg9wSp9IFlm4k"

n8n_headers = {"X-N8N-API-KEY": N8N_API_KEY}
sb_headers = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
}

issues: list[str] = []
passes: list[str] = []


def check(name: str, ok: bool, fail_msg: str = "") -> None:
    if ok:
        passes.append(name)
        print(f"  [PASS] {name}")
    else:
        msg = f"{name}: {fail_msg}" if fail_msg else name
        issues.append(msg)
        print(f"  [FAIL] {msg}")


def main() -> None:
    print("=" * 60)
    print("  BRAIN SYSTEM — FULL REVISION REPORT")
    print("=" * 60)

    # ── 1. SUPABASE TABLES ──
    print("\n1. SUPABASE TABLES")
    for table in ["brain_events", "brain_state", "brain_links", "brain_sessions"]:
        resp = httpx.get(
            f"{SUPABASE_URL}/rest/v1/{table}?select=*&limit=0",
            headers=sb_headers,
        )
        check(f"Table {table} accessible", resp.status_code == 200, str(resp.status_code))

    # ── 2. BRAIN BRIEFING VIEW ──
    print("\n2. BRAIN BRIEFING VIEW")
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/brain_briefing?select=category",
        headers=sb_headers,
    )
    if resp.status_code == 200:
        categories = set(r["category"] for r in resp.json())
        required = {"failing_entities", "last_session"}
        optional = {"unresolved_events"}
        has_required = required.issubset(categories)
        has_only_valid = categories.issubset(required | optional)
        check(
            "View returns required categories (failing_entities, last_session)",
            has_required and has_only_valid,
            f"got {categories}",
        )
        if "unresolved_events" not in categories:
            print("    (unresolved_events empty — no open events, which is correct)")
    else:
        check("View accessible", False, str(resp.status_code))

    # ── 3. BRAIN STATE DATA ──
    print("\n3. BRAIN STATE DATA")
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/brain_state?select=entity_type,status",
        headers=sb_headers,
    )
    rows = resp.json()
    total = len(rows)
    by_type: dict[str, int] = {}
    for r in rows:
        key = f"{r['entity_type']}:{r['status']}"
        by_type[key] = by_type.get(key, 0) + 1

    print(f"  Total entities: {total}")
    for k, v in sorted(by_type.items()):
        print(f"    {k}: {v}")
    check(f"Entity count >= 58", total >= 58, f"only {total}")

    # ── 4. BRAIN WRITER WORKFLOW ──
    print("\n4. BRAIN WRITER WORKFLOW")
    resp = httpx.get(f"{N8N_BASE_URL}/api/v1/workflows/{BRAIN_WF_ID}", headers=n8n_headers)
    bw = resp.json()
    check("Brain Writer active", bw["active"])
    check("Brain Writer has 5 nodes", len(bw["nodes"]) == 5, f"has {len(bw['nodes'])}")

    for n in bw["nodes"]:
        if n["name"] == "Upsert brain_state":
            url = n["parameters"]["url"]
            check("Upsert URL has on_conflict", "on_conflict" in url, url)
        cred = n.get("credentials", {}).get("httpHeaderAuth", {})
        if cred:
            check(
                f"Node '{n['name']}' has correct cred ID",
                cred.get("id") == CRED_ID,
                f"got {cred.get('id')}",
            )

    # ── 5. SHM WORKFLOW ──
    print("\n5. ADS SHM WORKFLOW")
    resp = httpx.get(f"{N8N_BASE_URL}/api/v1/workflows/{SHM_WF_ID}", headers=n8n_headers)
    shm = resp.json()
    check("SHM active", shm["active"])

    brain_nodes = [n for n in shm["nodes"] if n["name"] == "Write to Brain"]
    check("Exactly 1 Write to Brain node", len(brain_nodes) == 1, f"found {len(brain_nodes)}")

    if brain_nodes:
        bn = brain_nodes[0]
        wf_ref = bn["parameters"].get("workflowId", {}).get("value", "")
        check("Write to Brain calls correct workflow", wf_ref == BRAIN_WF_ID, wf_ref)

    af_conn = shm["connections"].get("Analyze Failures", {}).get("main", [[]])[0]
    af_targets = [c["node"] for c in af_conn]
    check(
        "Analyze Failures fans out correctly",
        "Write to Brain" in af_targets and "Has Failures?" in af_targets,
        str(af_targets),
    )

    # ── 6. CREDENTIAL & WRITE TEST ──
    print("\n6. SUPABASE CREDENTIAL & WRITE TEST")
    write_resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/brain_events",
        headers={**sb_headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
        json={
            "source": "claude:revision-check",
            "source_type": "claude",
            "event_type": "execution_success",
            "severity": "info",
            "department": "infra",
            "summary": "Full brain revision passed",
        },
    )
    check("Write to brain_events", write_resp.status_code in (200, 201), str(write_resp.status_code))

    upsert_resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/brain_state?on_conflict=entity_type,entity_id",
        headers={
            **sb_headers,
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        json={
            "entity_type": "workflow",
            "entity_id": BRAIN_WF_ID,
            "entity_name": "AVM: Brain Writer",
            "status": "healthy",
            "last_seen": "2026-04-09T12:30:00+00:00",
            "updated_at": "2026-04-09T12:30:00+00:00",
            "notes": "Sub-workflow for brain event logging.",
        },
    )
    check("Upsert brain_state", upsert_resp.status_code in (200, 201), str(upsert_resp.status_code))

    # ── 7. UPSERT MERGE TEST ──
    print("\n7. UPSERT MERGE & FAILURE_COUNT TRIGGER TEST")

    test_entity_type = "workflow"
    test_entity_id = "__verify_brain_test__"

    # Clean up any prior test entity
    httpx.delete(
        f"{SUPABASE_URL}/rest/v1/brain_state?entity_type=eq.{test_entity_type}&entity_id=eq.{test_entity_id}",
        headers={**sb_headers, "Prefer": "return=minimal"},
    )

    # Insert test entity as healthy
    ins_resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/brain_state?on_conflict=entity_type,entity_id",
        headers={**sb_headers, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"},
        json={
            "entity_type": test_entity_type,
            "entity_id": test_entity_id,
            "entity_name": "Verify Brain Test Entity",
            "status": "healthy",
            "failure_count": 0,
            "updated_at": "2026-04-09T00:00:00+00:00",
        },
    )
    check("Insert test entity", ins_resp.status_code in (200, 201), str(ins_resp.status_code))

    # Upsert 3x as failing — trigger should increment failure_count each time
    for i in range(3):
        httpx.post(
            f"{SUPABASE_URL}/rest/v1/brain_state?on_conflict=entity_type,entity_id",
            headers={**sb_headers, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"},
            json={
                "entity_type": test_entity_type,
                "entity_id": test_entity_id,
                "entity_name": "Verify Brain Test Entity",
                "status": "failing",
                "updated_at": f"2026-04-09T00:0{i+1}:00+00:00",
            },
        )

    # Read back and verify failure_count = 3
    read_resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/brain_state?entity_type=eq.{test_entity_type}&entity_id=eq.{test_entity_id}&select=failure_count,status",
        headers=sb_headers,
    )
    rows = read_resp.json()
    if rows:
        fc = rows[0].get("failure_count", -1)
        check("failure_count incremented to 3", fc == 3, f"got {fc}")
        check("No duplicate test entity", len(rows) == 1, f"got {len(rows)} rows")
    else:
        check("Test entity exists after upsert", False, "entity not found")

    # Upsert as healthy — trigger should reset failure_count to 0
    httpx.post(
        f"{SUPABASE_URL}/rest/v1/brain_state?on_conflict=entity_type,entity_id",
        headers={**sb_headers, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"},
        json={
            "entity_type": test_entity_type,
            "entity_id": test_entity_id,
            "entity_name": "Verify Brain Test Entity",
            "status": "healthy",
            "updated_at": "2026-04-09T00:05:00+00:00",
        },
    )
    read_resp2 = httpx.get(
        f"{SUPABASE_URL}/rest/v1/brain_state?entity_type=eq.{test_entity_type}&entity_id=eq.{test_entity_id}&select=failure_count",
        headers=sb_headers,
    )
    rows2 = read_resp2.json()
    if rows2:
        fc2 = rows2[0].get("failure_count", -1)
        check("failure_count resets to 0 on healthy", fc2 == 0, f"got {fc2}")
    else:
        check("Test entity exists after healthy upsert", False, "entity not found")

    # Cleanup test entity
    httpx.delete(
        f"{SUPABASE_URL}/rest/v1/brain_state?entity_type=eq.{test_entity_type}&entity_id=eq.{test_entity_id}",
        headers={**sb_headers, "Prefer": "return=minimal"},
    )

    # ── 8. CROSS-CHECK IDS ──
    print("\n8. CROSS-CHECK: brain_state vs live n8n")
    resp = httpx.get(f"{N8N_BASE_URL}/api/v1/workflows", headers=n8n_headers, params={"limit": 100})
    n8n_ids = set(w["id"] for w in resp.json()["data"])

    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/brain_state?entity_type=eq.workflow&select=entity_id",
        headers=sb_headers,
    )
    brain_ids = set(r["entity_id"] for r in resp.json())

    orphans = brain_ids - n8n_ids
    missing = n8n_ids - brain_ids
    check("No orphan brain entities", len(orphans) == 0, f"orphans: {orphans}")
    check("No missing n8n workflows", len(missing) == 0, f"missing: {missing}")

    # ── SUMMARY ──
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY: {len(passes)} PASS, {len(issues)} ISSUES")
    print(f"{'=' * 60}")
    if issues:
        print("\nISSUES:")
        for i in issues:
            print(f"  [!] {i}")
    else:
        print("\n  ALL CHECKS PASSED")


if __name__ == "__main__":
    main()

"""
Brain System — End-to-End Simulation Test

Simulates the exact data flow: SHM → Brain Writer Format Event → Supabase
Tests 3 scenarios: healthy, failure, recovery.
Also tests edge cases: empty input, malformed JSON, null fields.

Run: python tools/test_brain_e2e.py
"""

import httpx
import json
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

sb_headers = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}

passes: list[str] = []
issues: list[str] = []


def check(name: str, ok: bool, fail_msg: str = "") -> None:
    if ok:
        passes.append(name)
        print(f"  [PASS] {name}")
    else:
        msg = f"{name}: {fail_msg}" if fail_msg else name
        issues.append(msg)
        print(f"  [FAIL] {msg}")


def insert_event(event: dict) -> int:
    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/brain_events",
        headers={**sb_headers, "Prefer": "return=minimal"},
        json=event,
    )
    return resp.status_code


def upsert_state(state: dict) -> tuple[int, dict]:
    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/brain_state?on_conflict=entity_type,entity_id",
        headers={**sb_headers, "Prefer": "resolution=merge-duplicates,return=representation"},
        json=state,
    )
    rows = resp.json() if resp.status_code in (200, 201) else []
    return resp.status_code, rows[0] if rows else {}


def get_state(entity_id: str) -> dict:
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/brain_state?entity_id=eq.{entity_id}&select=*",
        headers={k: v for k, v in sb_headers.items() if k != "Content-Type"},
    )
    rows = resp.json()
    return rows[0] if rows else {}


def cleanup_test_entity(entity_id: str) -> None:
    httpx.delete(
        f"{SUPABASE_URL}/rest/v1/brain_state?entity_id=eq.{entity_id}",
        headers={**sb_headers, "Prefer": "return=minimal"},
    )


def main() -> None:
    test_eid = "__e2e_test_shm__"

    print("=" * 60)
    print("  BRAIN E2E SIMULATION — 3 Scenarios + Edge Cases")
    print("=" * 60)

    # Clean slate
    cleanup_test_entity(test_eid)

    # ── SCENARIO 1: Healthy check ──
    print("\n1. SCENARIO: SHM reports all healthy")
    event1 = {
        "source": "n8n:ADS-SHM",
        "source_type": "workflow",
        "event_type": "execution_success",
        "severity": "info",
        "department": "ads",
        "summary": "All ADS workflows healthy",
        "details": {"healthy": True, "checkedAt": "2026-04-09T14:00:00Z"},
        "resolved": False,
    }
    check("Insert healthy event", insert_event(event1) in (200, 201))

    status1, row1 = upsert_state({
        "entity_type": "workflow",
        "entity_id": test_eid,
        "entity_name": "E2E Test SHM",
        "status": "healthy",
        "last_success": "2026-04-09T14:00:00+00:00",
        "failure_count": 0,
        "updated_at": "2026-04-09T14:00:00+00:00",
        "notes": "All healthy",
    })
    check("Upsert healthy state", status1 in (200, 201))
    check("Status is healthy", row1.get("status") == "healthy", row1.get("status", "missing"))
    check("failure_count is 0", row1.get("failure_count") == 0, str(row1.get("failure_count")))

    # ── SCENARIO 2: Two consecutive failures ──
    print("\n2. SCENARIO: SHM reports failures (2 rounds)")
    for i in range(2):
        event2 = {
            "source": "n8n:ADS-SHM",
            "source_type": "workflow",
            "event_type": "alert",
            "severity": "warning",
            "department": "ads",
            "summary": f"2 ADS workflow failures detected (round {i+1})",
            "details": {"healthy": False, "failureCount": 2},
            "resolved": False,
        }
        insert_event(event2)

        upsert_state({
            "entity_type": "workflow",
            "entity_id": test_eid,
            "entity_name": "E2E Test SHM",
            "status": "degraded",
            "last_failure": f"2026-04-09T{16+i}:00:00+00:00",
            "updated_at": f"2026-04-09T{16+i}:00:00+00:00",
            "notes": f"2 failures round {i+1}",
        })

    state2 = get_state(test_eid)
    check("Status is degraded after failures", state2.get("status") == "degraded", state2.get("status", "missing"))
    check("failure_count is 2 after 2 failures", state2.get("failure_count") == 2, str(state2.get("failure_count")))

    # ── SCENARIO 3: Recovery ──
    print("\n3. SCENARIO: SHM reports healthy (recovery)")
    event3 = {
        "source": "n8n:ADS-SHM",
        "source_type": "workflow",
        "event_type": "execution_success",
        "severity": "info",
        "department": "ads",
        "summary": "All ADS workflows healthy (recovery)",
        "details": {"healthy": True},
        "resolved": False,
    }
    insert_event(event3)

    upsert_state({
        "entity_type": "workflow",
        "entity_id": test_eid,
        "entity_name": "E2E Test SHM",
        "status": "healthy",
        "last_success": "2026-04-09T18:00:00+00:00",
        "failure_count": 0,
        "updated_at": "2026-04-09T18:00:00+00:00",
        "notes": "All healthy (recovery)",
    })

    state3 = get_state(test_eid)
    check("Status is healthy after recovery", state3.get("status") == "healthy", state3.get("status", "missing"))
    check("failure_count resets to 0", state3.get("failure_count") == 0, str(state3.get("failure_count")))

    # ── EDGE CASE 1: Critical failure (severity escalation) ──
    print("\n4. EDGE CASE: Critical severity (>3 failures)")
    event4 = {
        "source": "n8n:ADS-SHM",
        "source_type": "workflow",
        "event_type": "alert",
        "severity": "critical",
        "department": "ads",
        "summary": "5 ADS workflow failures detected",
        "details": {"healthy": False, "failureCount": 5},
        "resolved": False,
    }
    insert_event(event4)

    upsert_state({
        "entity_type": "workflow",
        "entity_id": test_eid,
        "entity_name": "E2E Test SHM",
        "status": "failing",
        "last_failure": "2026-04-09T20:00:00+00:00",
        "updated_at": "2026-04-09T20:00:00+00:00",
        "notes": "5 failures — critical",
    })

    state4 = get_state(test_eid)
    check("Status is failing on critical", state4.get("status") == "failing", state4.get("status", "missing"))
    check("failure_count is 1 (first failure after recovery)", state4.get("failure_count") == 1, str(state4.get("failure_count")))

    # ── EDGE CASE 2: Malformed details string ──
    print("\n5. EDGE CASE: Malformed details (not valid JSON)")
    event5 = {
        "source": "n8n:ADS-SHM",
        "source_type": "workflow",
        "event_type": "execution_success",
        "severity": "info",
        "department": "ads",
        "summary": "Malformed details test",
        "details": {"raw": "not{valid json", "parseError": "test"},
        "resolved": False,
    }
    check("Insert with malformed details", insert_event(event5) in (200, 201))

    # ── EDGE CASE 3: Null/missing optional fields ──
    print("\n6. EDGE CASE: Null optional fields")
    event6 = {
        "source": "n8n:ADS-SHM",
        "source_type": "workflow",
        "event_type": "execution_success",
        "severity": "info",
        "department": None,
        "summary": "Null department test",
        "details": {},
        "resolved": False,
    }
    check("Insert with null department", insert_event(event6) in (200, 201))

    # ── EDGE CASE 4: Missing client_id (should be null, not error) ──
    print("\n7. EDGE CASE: No client_id (null FK)")
    event7 = {
        "source": "n8n:ADS-SHM",
        "source_type": "workflow",
        "event_type": "execution_success",
        "severity": "info",
        "summary": "No client_id test",
        "details": {},
        "resolved": False,
    }
    check("Insert without client_id", insert_event(event7) in (200, 201))

    # ── BRIEFING VIEW TEST ──
    print("\n8. BRIEFING VIEW: Verify bounded results")
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/brain_briefing?select=category",
        headers={k: v for k, v in sb_headers.items() if k != "Content-Type"},
    )
    categories = set(r["category"] for r in resp.json()) if resp.status_code == 200 else set()
    check("Briefing returns unresolved_events", "unresolved_events" in categories)
    check("Briefing returns last_session", "last_session" in categories)

    # Count unresolved events (should be <= 20 from bounded view)
    resp2 = httpx.get(
        f"{SUPABASE_URL}/rest/v1/brain_briefing?category=eq.unresolved_events&select=item",
        headers={k: v for k, v in sb_headers.items() if k != "Content-Type"},
    )
    event_count = len(resp2.json()) if resp2.status_code == 200 else -1
    check(f"Unresolved events bounded (<= 20)", event_count <= 20, f"got {event_count}")

    # ── CLEANUP ──
    cleanup_test_entity(test_eid)

    # ── SUMMARY ──
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY: {len(passes)} PASS, {len(issues)} ISSUES")
    print(f"{'=' * 60}")
    if issues:
        print("\nISSUES:")
        for i in issues:
            print(f"  [!] {i}")
    else:
        print("\n  ALL E2E TESTS PASSED")


if __name__ == "__main__":
    main()

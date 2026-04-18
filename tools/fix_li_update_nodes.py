"""Patch broken LI-03..LI-09 Google Sheets Update nodes.

Bug: `columns.matchingColumns` references a Lead ID column that has no entry
in `columns.value`, so the node errors with
"The 'Column to Match On' parameter is required".

Fix: For every Update node in LI-03, LI-04, LI-08, LI-09, add a Lead ID
expression to `columns.value`. Also remove the stray root-level
`matchingColumns` (tolerated but misleading).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")

N8N_BASE = os.environ["N8N_BASE_URL"].rstrip("/")
N8N_KEY = os.environ["N8N_API_KEY"]
HEADERS = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}

TARGETS = {
    "LI-03": "ZNA5Un9kDSGGCYhZ",
    "LI-04": "GhOqQITx3rfWWswM",
    "LI-08": "2ZbzAI9YLL6OiSrT",
    "LI-09": "iVDt9KZZs1jmRaJq",
}

LEAD_ID_EXPR = "={{ $json.lead_id || $json['Lead ID'] || '' }}"


def fetch(wf_id: str) -> dict:
    r = httpx.get(f"{N8N_BASE}/api/v1/workflows/{wf_id}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def push(wf_id: str, wf: dict) -> None:
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {}),
    }
    r = httpx.put(
        f"{N8N_BASE}/api/v1/workflows/{wf_id}",
        headers=HEADERS,
        json=payload,
        timeout=60,
    )
    r.raise_for_status()


def patch_node(n: dict) -> bool:
    p = n.get("parameters", {}) or {}
    if p.get("operation") not in ("update", "upsert"):
        return False
    cols = p.get("columns") or {}
    match = cols.get("matchingColumns") or []
    value = dict(cols.get("value") or {})
    changed = False
    for m in match:
        if m not in value:
            value[m] = LEAD_ID_EXPR if m == "Lead ID" else f"={{{{ $json['{m.lower().replace(' ', '_')}'] || $json['{m}'] || '' }}}}"
            changed = True
    if changed:
        cols["value"] = value
        p["columns"] = cols
    # Remove stray root-level matchingColumns
    if "matchingColumns" in p:
        p.pop("matchingColumns", None)
        changed = True
    if changed:
        n["parameters"] = p
    return changed


def main() -> int:
    any_err = False
    for label, wf_id in TARGETS.items():
        try:
            wf = fetch(wf_id)
            patched = 0
            for n in wf["nodes"]:
                if patch_node(n):
                    patched += 1
                    print(f"  [{label}] patched node: {n['name']}")
            if patched:
                push(wf_id, wf)
                print(f"  [{label}] pushed {patched} node fix(es)")
            else:
                print(f"  [{label}] no changes needed")
        except Exception as e:
            any_err = True
            print(f"  [{label}] ERROR: {e}", file=sys.stderr)
    return 1 if any_err else 0


if __name__ == "__main__":
    sys.exit(main())

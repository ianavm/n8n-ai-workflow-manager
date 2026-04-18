"""Audit LI-03..LI-10 live workflows for broken Google Sheets Update nodes.

For each Update node: report matchingColumns, columns.value keys, and
whether any matching column is missing from columns.value (the bug).
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

LI_WORKFLOWS = {
    "LI-03": "ZNA5Un9kDSGGCYhZ",
    "LI-04": "GhOqQITx3rfWWswM",
    "LI-05": "KZqZ0AnjneUQGNvU",
    "LI-06": "6BhjrUM1UB0w8iXO",
    "LI-07": "qLWY6xKkPP5s9DbB",
    "LI-08": "2ZbzAI9YLL6OiSrT",
    "LI-09": "iVDt9KZZs1jmRaJq",
    "LI-10": "XLyM6yRIBDb3pzgJ",
}


def fetch(wf_id: str) -> dict:
    r = httpx.get(
        f"{N8N_BASE}/api/v1/workflows/{wf_id}",
        headers={"X-N8N-API-KEY": N8N_KEY},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def audit(label: str, wf_id: str) -> None:
    wf = fetch(wf_id)
    print(f"\n==== {label} ({wf['name']}) ====")
    for n in wf["nodes"]:
        p = n.get("parameters", {}) or {}
        if p.get("operation") != "update" and p.get("operation") != "upsert":
            continue
        cols = p.get("columns", {}) or {}
        match = cols.get("matchingColumns") or p.get("matchingColumns") or []
        value_keys = list((cols.get("value") or {}).keys())
        missing = [m for m in match if m not in value_keys]
        stray_root = "matchingColumns" in p
        status = "BROKEN" if missing else "ok"
        print(f"  [{status}] {n['name']:30s} | match={match} | value_keys={value_keys} | missing={missing} | stray_root={stray_root}")


if __name__ == "__main__":
    for label, wf_id in LI_WORKFLOWS.items():
        try:
            audit(label, wf_id)
        except Exception as e:
            print(f"\n==== {label} ERROR: {e}")

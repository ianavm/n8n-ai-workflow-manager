"""
Decision Logger — Audit trail for AWLM autonomous decisions.

Logs every detection, classification, action, and outcome to:
    1. Airtable Decision_Log table (tblHViYF9sEUOFdNO in Operations Control)
    2. Local JSON files in .tmp/decisions/

Usage:
    from decision_logger import DecisionLogger
    logger = DecisionLogger(config)
    logger.log_decision(loop_type="repair", workflow_id="abc", ...)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


# ── Airtable IDs (Operations Control base) ─────────────────
_OPS_BASE_ID = "appTCh0EeXQp0XqzW"
_DECISION_LOG_TABLE = "tblHViYF9sEUOFdNO"
_ESCALATION_TABLE = "tbl2kDx0EqczOU3ib"
_AIRTABLE_URL = "https://api.airtable.com/v0"


class DecisionLogger:
    """Log autonomous decisions to Airtable and local JSON."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._api_key = os.getenv("AIRTABLE_API_TOKEN", "")
        self._base_id = _OPS_BASE_ID
        self._decision_table = _DECISION_LOG_TABLE
        self._escalation_table = _ESCALATION_TABLE
        self._local_dir = Path(
            self._config.get("lifecycle", {}).get(
                "decisions_dir",
                str(Path(__file__).parent.parent / ".tmp" / "decisions"),
            )
        )
        self._local_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ──────────────────────────────────────────

    def log_decision(
        self,
        loop_type: str,
        workflow_id: str,
        agent_owner: str = "",
        issue_detected: str = "",
        classification: str = "",
        confidence_score: float = 0.0,
        risk_level: str = "",
        action_taken: str = "",
        changes_made: str = "",
        outcome: str = "pending",
        backup_path: str = "",
    ) -> str:
        """Log a single autonomous decision.  Returns the decision ID."""
        now = datetime.now(tz=None).isoformat() + "Z"
        decision_id = f"DEC-{datetime.now(tz=None).strftime('%Y%m%d%H%M%S')}-{workflow_id[:8]}"

        record: Dict[str, Any] = {
            "Decision_ID": decision_id,
            "Timestamp": now,
            "Loop_Type": loop_type,
            "Workflow_ID": workflow_id,
            "Agent_Owner": agent_owner,
            "Issue_Detected": issue_detected,
            "Classification": classification,
            "Confidence_Score": round(confidence_score, 3),
            "Risk_Level": risk_level,
            "Action_Taken": action_taken,
            "Changes_Made": changes_made,
            "Outcome": outcome,
            "Backup_Path": backup_path,
        }

        # Write locally (always succeeds)
        self._write_local(decision_id, record)

        # Write to Airtable (best-effort)
        self._write_airtable(self._decision_table, record)

        return decision_id

    def log_detection(self, issues: List[Dict[str, Any]]) -> None:
        """Log a batch of detected issues (informational, local only)."""
        now = datetime.now(tz=None).strftime("%Y%m%d%H%M%S")
        path = self._local_dir / f"detection_{now}.json"
        self._save_json(path, {"timestamp": now, "issues": issues})

    def log_escalation(
        self,
        workflow_id: str,
        severity: str,
        category: str,
        description: str,
        recommended_action: str = "",
    ) -> None:
        """Write an escalation record to Airtable Escalation_Queue."""
        record = {
            "Workflow_ID": workflow_id,
            "Severity": severity,
            "Category": category,
            "Description": description,
            "Recommended_Action": recommended_action,
            "Status": "Open",
            "Created_At": datetime.now(tz=None).isoformat() + "Z",
        }
        self._write_airtable(self._escalation_table, record)
        self._write_local(
            f"ESC-{datetime.now(tz=None).strftime('%Y%m%d%H%M%S')}-{workflow_id[:8]}",
            record,
        )

    def get_recent_decisions(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Read recent decision records from local JSON files."""
        decisions: List[Dict[str, Any]] = []
        cutoff = datetime.now(tz=None).timestamp() - hours * 3600
        for path in sorted(self._local_dir.glob("DEC-*.json"), reverse=True):
            if path.stat().st_mtime < cutoff:
                break
            try:
                with open(path, "r", encoding="utf-8") as f:
                    decisions.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                continue
        return decisions

    def get_decisions_for_workflow(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Read all decision records for a specific workflow."""
        decisions: List[Dict[str, Any]] = []
        for path in sorted(self._local_dir.glob("DEC-*.json"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("Workflow_ID") == workflow_id:
                    decisions.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return decisions

    # ── Internal ────────────────────────────────────────────

    def _write_local(self, decision_id: str, record: Dict[str, Any]) -> None:
        path = self._local_dir / f"{decision_id}.json"
        self._save_json(path, record)

    def _write_airtable(self, table_id: str, record: Dict[str, Any]) -> None:
        if not self._api_key:
            return
        url = f"{_AIRTABLE_URL}/{self._base_id}/{table_id}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {"records": [{"fields": record}]}
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    print(f"  [DecisionLogger] Airtable write failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as exc:
            print(f"  [DecisionLogger] Airtable write error: {exc}")

    @staticmethod
    def _save_json(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

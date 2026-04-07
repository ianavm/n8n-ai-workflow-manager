"""
Repair Pattern Store — Persistent pattern registry with learning.

Stores repair patterns, their historical success/failure rates, and
per-workflow performance baselines in JSON files under .tmp/repair_patterns/.

File layout:
    .tmp/repair_patterns/
        patterns.json      — Pattern definitions (serialisable subset)
        outcomes.json      — {pattern_id: {success: N, failure: N, history: [...]}}
        baselines.json     — {workflow_id: {success_rate, avg_duration, ...}}

Usage:
    from repair_pattern_store import RepairPatternStore
    store = RepairPatternStore()
    store.record_outcome("airtable_token_expired", "abc123", success=True, details={...})
    rate = store.get_success_rate("airtable_token_expired")
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class RepairPatternStore:
    """JSON-backed persistent store for repair patterns and baselines."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self._dir = Path(store_dir) if store_dir else (
            Path(__file__).parent.parent / ".tmp" / "repair_patterns"
        )
        self._dir.mkdir(parents=True, exist_ok=True)
        self._patterns_path = self._dir / "patterns.json"
        self._outcomes_path = self._dir / "outcomes.json"
        self._baselines_path = self._dir / "baselines.json"

    # ── Pattern CRUD ────────────────────────────────────────

    def save_pattern(self, pattern_data: Dict[str, Any]) -> None:
        """Upsert a pattern definition keyed by pattern_id."""
        patterns = self._load_json(self._patterns_path, default={})
        pid = pattern_data["pattern_id"]
        patterns[pid] = {
            "pattern_id": pid,
            "name": pattern_data.get("name", pid),
            "error_signatures": pattern_data.get("error_signatures", []),
            "node_types_affected": pattern_data.get("node_types_affected", []),
            "confidence": pattern_data.get("confidence", 0.5),
            "risk_level": pattern_data.get("risk_level", "MEDIUM"),
            "requires_deploy_script_update": pattern_data.get(
                "requires_deploy_script_update", False
            ),
            "updated_at": datetime.now(tz=None).isoformat() + "Z",
        }
        self._save_json(self._patterns_path, patterns)

    def load_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Return all stored pattern definitions."""
        return self._load_json(self._patterns_path, default={})

    def get_pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        patterns = self.load_patterns()
        return patterns.get(pattern_id)

    def delete_pattern(self, pattern_id: str) -> bool:
        patterns = self.load_patterns()
        if pattern_id in patterns:
            del patterns[pattern_id]
            self._save_json(self._patterns_path, patterns)
            return True
        return False

    # ── Outcome tracking ────────────────────────────────────

    def record_outcome(
        self,
        pattern_id: str,
        workflow_id: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record the result of applying a repair pattern."""
        outcomes = self._load_json(self._outcomes_path, default={})
        if pattern_id not in outcomes:
            outcomes[pattern_id] = {"success": 0, "failure": 0, "history": []}

        entry = outcomes[pattern_id]
        if success:
            entry["success"] += 1
        else:
            entry["failure"] += 1

        entry["history"].append({
            "workflow_id": workflow_id,
            "success": success,
            "timestamp": datetime.now(tz=None).isoformat() + "Z",
            "details": details or {},
        })

        # Keep last 100 history entries per pattern
        entry["history"] = entry["history"][-100:]

        self._save_json(self._outcomes_path, outcomes)

        # Auto-update pattern confidence based on observed rate
        self._update_pattern_confidence(pattern_id)

    def get_success_rate(self, pattern_id: str) -> float:
        """Return the historical success rate for a pattern (0.0–1.0)."""
        outcomes = self._load_json(self._outcomes_path, default={})
        entry = outcomes.get(pattern_id)
        if not entry:
            return 0.5  # Unknown pattern → neutral
        total = entry["success"] + entry["failure"]
        if total == 0:
            return 0.5
        return round(entry["success"] / total, 3)

    def get_outcome_counts(self, pattern_id: str) -> Dict[str, int]:
        outcomes = self._load_json(self._outcomes_path, default={})
        entry = outcomes.get(pattern_id, {"success": 0, "failure": 0})
        return {"success": entry["success"], "failure": entry["failure"]}

    def get_fix_history(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Return all fix outcomes for a specific workflow across all patterns."""
        outcomes = self._load_json(self._outcomes_path, default={})
        results: List[Dict[str, Any]] = []
        for pid, entry in outcomes.items():
            for h in entry.get("history", []):
                if h.get("workflow_id") == workflow_id:
                    results.append({"pattern_id": pid, **h})
        results.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        return results

    # ── Baselines ───────────────────────────────────────────

    def save_baseline(self, workflow_id: str, metrics: Dict[str, Any]) -> None:
        """Save/overwrite the performance baseline for a workflow."""
        baselines = self._load_json(self._baselines_path, default={})
        baselines[workflow_id] = {
            **metrics,
            "updated_at": datetime.now(tz=None).isoformat() + "Z",
        }
        self._save_json(self._baselines_path, baselines)

    def get_baseline(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        baselines = self._load_json(self._baselines_path, default={})
        return baselines.get(workflow_id)

    def list_baselines(self) -> Dict[str, Dict[str, Any]]:
        return self._load_json(self._baselines_path, default={})

    # ── Internal helpers ────────────────────────────────────

    def _update_pattern_confidence(self, pattern_id: str) -> None:
        """Sync the stored pattern confidence with observed success rate."""
        patterns = self._load_json(self._patterns_path, default={})
        if pattern_id in patterns:
            new_conf = self.get_success_rate(pattern_id)
            patterns[pattern_id]["confidence"] = new_conf
            self._save_json(self._patterns_path, patterns)

    @staticmethod
    def _load_json(path: Path, default: Any = None) -> Any:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return default if default is not None else {}

    @staticmethod
    def _save_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

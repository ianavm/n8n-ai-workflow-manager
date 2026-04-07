"""Seed the RepairPatternStore with known patterns.

Sources:
    1. BUILTIN_PATTERNS from tools/repair_engine.py (12 patterns)
    2. Additional n8n gotchas from CLAUDE.md knowledge
    3. Categories derived from existing tools/fix_*.py scripts

Usage:
    python -m autonomous.scripts.seed_patterns [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add tools/ to path so we can import repair_engine and pattern store
_TOOLS_DIR = str(Path(__file__).parent.parent.parent / "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from repair_engine import BUILTIN_PATTERNS
from repair_pattern_store import RepairPatternStore


# Additional patterns from CLAUDE.md n8n Node Rules and common issues
ADDITIONAL_PATTERNS = [
    {
        "pattern_id": "webhook_auth_missing",
        "name": "Webhook missing authentication",
        "error_signatures": [
            r"(?i)webhook.*auth",
            r"(?i)unauthorized.*webhook",
            r"(?i)unauthenticated.*webhook",
        ],
        "node_types_affected": ["n8n-nodes-base.webhook"],
        "confidence": 0.85,
        "risk_level": "HIGH",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "respond_to_webhook_text",
        "name": "respondToWebhook with invalid respondWith: text",
        "error_signatures": [
            r"(?i)respondWith.*text",
            r"(?i)respond.*webhook.*invalid",
        ],
        "node_types_affected": ["n8n-nodes-base.respondToWebhook"],
        "confidence": 0.90,
        "risk_level": "MEDIUM",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "respond_to_webhook_headers",
        "name": "respondToWebhook responseHeaders with JSON mode",
        "error_signatures": [
            r"(?i)responseHeaders.*json",
            r"(?i)options\.responseHeaders",
        ],
        "node_types_affected": ["n8n-nodes-base.respondToWebhook"],
        "confidence": 0.90,
        "risk_level": "MEDIUM",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "merge_v3_wrong_param",
        "name": "Merge v3 uses combinationMode instead of combineBy",
        "error_signatures": [
            r"(?i)combinationMode.*mergeByPosition",
            r"(?i)merge.*position.*error",
        ],
        "node_types_affected": ["n8n-nodes-base.merge"],
        "confidence": 0.90,
        "risk_level": "MEDIUM",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "if_node_strict_type",
        "name": "If node strict mode numeric comparison needs integer",
        "error_signatures": [
            r"(?i)if.*rightValue.*string",
            r"(?i)numeric.*comparison.*string",
        ],
        "node_types_affected": ["n8n-nodes-base.if"],
        "confidence": 0.85,
        "risk_level": "LOW",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "airtable_create_matching_columns",
        "name": "Airtable create with matchingColumns causes invalid request",
        "error_signatures": [
            r"(?i)airtable.*create.*matchingColumns",
            r"(?i)invalid.*request.*matchingColumns",
        ],
        "node_types_affected": ["n8n-nodes-base.airtable"],
        "confidence": 0.90,
        "risk_level": "MEDIUM",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "airtable_filter_dynamic_prefix",
        "name": "Airtable filterByFormula dynamic expression missing = prefix",
        "error_signatures": [
            r"(?i)filterByFormula.*expression",
            r"(?i)INVALID_FILTER_BY_FORMULA",
        ],
        "node_types_affected": ["n8n-nodes-base.airtable"],
        "confidence": 0.85,
        "risk_level": "MEDIUM",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "chain_breaking_expression",
        "name": "Expression references broken after chain-breaking node",
        "error_signatures": [
            r"\$json\.",
            r"(?i)cannot read.*json",
            r"(?i)\.item\.json",
        ],
        "node_types_affected": ["*"],
        "confidence": 0.70,
        "risk_level": "MEDIUM",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "switch_combinator_crash",
        "name": "Switch node combinator without options.caseSensitive",
        "error_signatures": [
            r"(?i)combinator.*caseSensitive",
            r"(?i)switch.*combinator.*crash",
        ],
        "node_types_affected": ["n8n-nodes-base.switch"],
        "confidence": 0.90,
        "risk_level": "MEDIUM",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "switch_condition_id_field",
        "name": "Switch v3 conditions with id field causes crash",
        "error_signatures": [
            r"(?i)switch.*condition.*id",
            r"(?i)could not find property",
        ],
        "node_types_affected": ["n8n-nodes-base.switch"],
        "confidence": 0.85,
        "risk_level": "MEDIUM",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "gsheets_define_below_missing",
        "name": "Google Sheets update missing defineBelow mapping",
        "error_signatures": [
            r"(?i)google.*sheets.*mapping",
            r"(?i)defineBelow",
        ],
        "node_types_affected": ["n8n-nodes-base.googleSheets"],
        "confidence": 0.85,
        "risk_level": "MEDIUM",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "split_in_batches_v3_reversed",
        "name": "SplitInBatches v3 outputs are reversed (done=0, loop=1)",
        "error_signatures": [
            r"(?i)splitInBatches.*output",
            r"(?i)batch.*reversed",
        ],
        "node_types_affected": ["n8n-nodes-base.splitInBatches"],
        "confidence": 0.80,
        "risk_level": "MEDIUM",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "credential_rotation_needed",
        "name": "Generic credential rotation (PAT expired / revoked)",
        "error_signatures": [
            r"(?i)401.*unauthorized",
            r"(?i)403.*forbidden",
            r"(?i)credential.*expired",
            r"(?i)token.*invalid",
        ],
        "node_types_affected": ["*"],
        "confidence": 0.80,
        "risk_level": "CRITICAL",
        "requires_deploy_script_update": False,
    },
    {
        "pattern_id": "openrouter_model_invalid",
        "name": "OpenRouter model ID invalid or deprecated",
        "error_signatures": [
            r"(?i)model.*not.*found",
            r"(?i)invalid.*model",
            r"(?i)openrouter.*model",
        ],
        "node_types_affected": ["n8n-nodes-base.httpRequest"],
        "confidence": 0.85,
        "risk_level": "MEDIUM",
        "requires_deploy_script_update": True,
    },
    {
        "pattern_id": "luxon_format_error",
        "name": "Luxon DateTime format error (toFormat vs format)",
        "error_signatures": [
            r"(?i)luxon.*format",
            r"(?i)toFormat.*not.*function",
            r"(?i)\.format\(",
        ],
        "node_types_affected": ["n8n-nodes-base.code", "n8n-nodes-base.set"],
        "confidence": 0.90,
        "risk_level": "LOW",
        "requires_deploy_script_update": True,
    },
]


def seed_patterns(force: bool = False) -> dict[str, int]:
    """Seed the RepairPatternStore with known patterns.

    Args:
        force: Re-seed even if patterns already exist.

    Returns:
        Dict with counts: {"builtin": N, "additional": N, "skipped": N}
    """
    store = RepairPatternStore()
    existing = store.load_patterns()
    counts = {"builtin": 0, "additional": 0, "skipped": 0}

    # 1. Seed from BUILTIN_PATTERNS
    for pattern in BUILTIN_PATTERNS:
        pid = pattern.pattern_id
        if pid in existing and not force:
            counts["skipped"] += 1
            continue
        store.save_pattern({
            "pattern_id": pid,
            "name": pattern.name,
            "error_signatures": pattern.error_signatures,
            "node_types_affected": pattern.node_types_affected,
            "confidence": pattern.confidence,
            "risk_level": pattern.risk_level.name,
            "requires_deploy_script_update": pattern.requires_deploy_script_update,
        })
        counts["builtin"] += 1

    # 2. Seed additional patterns from CLAUDE.md knowledge
    for pattern_data in ADDITIONAL_PATTERNS:
        pid = pattern_data["pattern_id"]
        if pid in existing and not force:
            counts["skipped"] += 1
            continue
        store.save_pattern(pattern_data)
        counts["additional"] += 1

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed AWE repair patterns")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-seed existing patterns (overwrite)",
    )
    args = parser.parse_args()

    counts = seed_patterns(force=args.force)
    total = counts["builtin"] + counts["additional"]
    print(f"AWE pattern seeding complete:")
    print(f"  Builtin patterns:    {counts['builtin']}")
    print(f"  Additional patterns: {counts['additional']}")
    print(f"  Skipped (existing):  {counts['skipped']}")
    print(f"  Total seeded:        {total}")


if __name__ == "__main__":
    main()

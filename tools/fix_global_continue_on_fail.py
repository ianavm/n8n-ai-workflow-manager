"""
Global continueOnFail Injector for Deploy Scripts

Scans all tools/deploy_*.py files and adds "onError": "continueRegularOutput"
to every API node definition that lacks it. This prevents entire workflow
crashes when a single API call times out, hits a rate limit, or returns
an error response.

Targets node types that make external API calls:
    httpRequest, googleSheets, airtable, gmail, telegram, executeWorkflow,
    microsoftOutlook, googleDrive, googleCalendar, googleAds, facebookGraphApi

Skips node types that are logic/control-flow only:
    code, if, switch, set, noOp, scheduleTrigger, webhookTrigger, stickyNote,
    merge, splitInBatches, manualTrigger, errorTrigger, webhook, respondToWebhook,
    wait, filter, splitOut, removeDuplicates, executeWorkflowTrigger, whatsAppTrigger,
    microsoftOutlookTrigger, gmailTrigger, telegramTrigger, extractFromFile

Usage:
    python tools/fix_global_continue_on_fail.py preview   # Show what would change
    python tools/fix_global_continue_on_fail.py apply      # Apply changes to deploy scripts
"""

from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Configuration ────────────────────────────────────────────────

TOOLS_DIR = Path(__file__).parent
PROJECT_ROOT = TOOLS_DIR.parent
BACKUP_DIR = PROJECT_ROOT / ".tmp" / "backups" / "continue_on_fail"

# Node types that make external API calls and need error handling
API_NODE_TYPES: frozenset[str] = frozenset({
    "httpRequest",
    "googleSheets",
    "airtable",
    "gmail",
    "telegram",
    "executeWorkflow",
    "microsoftOutlook",
    "googleDrive",
    "googleCalendar",
    "googleAds",
    "facebookGraphApi",
})

# Node types that are internal logic -- never add onError to these
SKIP_NODE_TYPES: frozenset[str] = frozenset({
    "code",
    "if",
    "switch",
    "set",
    "noOp",
    "scheduleTrigger",
    "webhookTrigger",
    "stickyNote",
    "merge",
    "splitInBatches",
    "manualTrigger",
    "errorTrigger",
    "webhook",
    "respondToWebhook",
    "wait",
    "filter",
    "splitOut",
    "removeDuplicates",
    "executeWorkflowTrigger",
    "whatsAppTrigger",
    "microsoftOutlookTrigger",
    "gmailTrigger",
    "telegramTrigger",
    "extractFromFile",
})

# Marker strings indicating existing error handling
ALREADY_HANDLED_MARKERS: tuple[str, ...] = (
    '"onError"',
    "'onError'",
    '"continueOnFail"',
    "'continueOnFail'",
    "continueRegularOutput",
)

# Files known to use make_resilient() wrapper -- skip entirely
RESILIENT_WRAPPER_FILES: frozenset[str] = frozenset({
    "deploy_ads_dept.py",
})


# ── Data Classes ─────────────────────────────────────────────────

@dataclass(frozen=True)
class NodeMatch:
    """Represents a single API node that needs onError injection."""
    line_number: int
    node_name: str
    node_type: str
    type_version_line: int


@dataclass
class FileReport:
    """Results for a single deploy script file."""
    filename: str
    filepath: Path
    total_api_nodes: int = 0
    already_handled: int = 0
    needs_fix: int = 0
    matches: list[NodeMatch] = field(default_factory=list)
    type_counts: dict[str, int] = field(default_factory=dict)
    skipped_reason: Optional[str] = None
    modified: bool = False


# ── Regex Patterns ───────────────────────────────────────────────

# Match: "type": "n8n-nodes-base.{nodeType}"
# Captures the node type name (e.g., "httpRequest", "airtable")
RE_NODE_TYPE = re.compile(
    r'"type"\s*:\s*"n8n-nodes-base\.(\w+)"'
)

# Match: "typeVersion": <number> anywhere on a line
# Used to locate the injection point
RE_TYPE_VERSION = re.compile(
    r'"typeVersion"\s*:\s*[\d.]+'
)

# Match: "name": "Some Node Name"
RE_NODE_NAME = re.compile(
    r'"name"\s*:\s*"([^"]*)"'
)


# ── Core Logic ───────────────────────────────────────────────────

def _find_node_region(
    lines: list[str],
    type_line_idx: int,
    max_search: int = 40,
) -> tuple[int, int]:
    """Find the region belonging to this node, bounded by other nodes.

    Searches backward and forward from the type line. Stops at the
    next/previous n8n-nodes-base type declaration or function def boundary.
    Returns (start_line, end_line) -- inclusive range.
    """
    # Search backward -- stop at previous node type or function def
    start = type_line_idx
    for i in range(type_line_idx - 1, max(0, type_line_idx - max_search), -1):
        line = lines[i]
        # Stop at another node type declaration
        if RE_NODE_TYPE.search(line) and i != type_line_idx:
            start = i + 1
            break
        # Stop at function definition (helper functions return single node dicts)
        if line.strip().startswith("def ") and line.strip().endswith(":"):
            start = i + 1
            break
    else:
        start = max(0, type_line_idx - max_search)

    # Search forward -- stop at next node type declaration
    end = type_line_idx
    for i in range(type_line_idx + 1, min(len(lines), type_line_idx + max_search)):
        line = lines[i]
        # Stop at another node type declaration
        if RE_NODE_TYPE.search(line):
            end = i - 1
            break
        # Stop at function definition
        if line.strip().startswith("def ") and line.strip().endswith(":"):
            end = i - 1
            break
    else:
        end = min(len(lines) - 1, type_line_idx + max_search)

    return start, end


def node_already_has_error_handling(
    lines: list[str],
    type_line_idx: int,
) -> bool:
    """Check if the node dict already contains onError/continueOnFail.

    Uses node region detection (bounded by adjacent node type declarations)
    to avoid false positives from nearby nodes.
    """
    start, end = _find_node_region(lines, type_line_idx)
    window_text = "\n".join(lines[start:end + 1])

    for marker in ALREADY_HANDLED_MARKERS:
        if marker in window_text:
            return True

    # Also check if the node is wrapped in make_resilient()
    for i in range(type_line_idx, max(0, type_line_idx - 10), -1):
        if "make_resilient" in lines[i]:
            return True

    return False


def find_node_name(lines: list[str], type_line_idx: int) -> str:
    """Extract the node name from nearby lines."""
    start = max(0, type_line_idx - 15)
    end = min(len(lines), type_line_idx + 15)

    for i in range(start, end):
        match = RE_NODE_NAME.search(lines[i])
        if match:
            return match.group(1)

    return "<unknown>"


def find_type_version_line(
    lines: list[str],
    type_line_idx: int,
    search_range: int = 10,
) -> Optional[int]:
    """Find the typeVersion line near the type line.

    Searches forward first (most common pattern), then backward.
    Handles both standalone typeVersion lines and inline cases where
    typeVersion is on the same line as type.
    Returns line index or None.
    """
    # Search forward first (type usually appears before typeVersion)
    # Note: typeVersion can be on the SAME line as type (compact formatting)
    for i in range(type_line_idx, min(len(lines), type_line_idx + search_range)):
        if RE_TYPE_VERSION.search(lines[i]):
            return i

    # Search backward (less common)
    for i in range(type_line_idx - 1, max(0, type_line_idx - search_range), -1):
        if RE_TYPE_VERSION.search(lines[i]):
            return i

    return None


def scan_file(filepath: Path) -> FileReport:
    """Scan a single deploy script for API nodes missing onError."""
    report = FileReport(
        filename=filepath.name,
        filepath=filepath,
    )

    # Check if file uses make_resilient wrapper
    if filepath.name in RESILIENT_WRAPPER_FILES:
        report.skipped_reason = "uses make_resilient() wrapper"
        return report

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        report.skipped_reason = f"read error: {exc}"
        return report

    lines = content.splitlines()

    # Find all node type declarations
    for line_idx, line in enumerate(lines):
        type_match = RE_NODE_TYPE.search(line)
        if not type_match:
            continue

        node_type = type_match.group(1)

        # Skip non-API node types
        if node_type not in API_NODE_TYPES:
            continue

        report.total_api_nodes += 1

        # Check if already handled
        if node_already_has_error_handling(lines, line_idx):
            report.already_handled += 1
            continue

        # Find the typeVersion line for injection
        tv_line = find_type_version_line(lines, line_idx)
        if tv_line is None:
            # No typeVersion found -- unusual, skip this node
            continue

        node_name = find_node_name(lines, line_idx)

        match = NodeMatch(
            line_number=line_idx + 1,
            node_name=node_name,
            node_type=node_type,
            type_version_line=tv_line,
        )
        report.matches.append(match)
        report.needs_fix += 1

        # Track by type
        short_type = node_type
        report.type_counts[short_type] = report.type_counts.get(short_type, 0) + 1

    return report


def _detect_indent(line: str) -> str:
    """Extract the leading whitespace from a line."""
    indent = ""
    for ch in line:
        if ch in (" ", "\t"):
            indent += ch
        else:
            break
    return indent


def inject_on_error(filepath: Path, matches: list[NodeMatch]) -> bool:
    """Inject onError into a deploy script file.

    Adds '"onError": "continueRegularOutput",' after each typeVersion line
    identified in the matches. Processes from bottom to top to preserve
    line numbers.

    Returns True if file was modified.
    """
    if not matches:
        return False

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    lines = content.splitlines()

    # Sort matches by typeVersion line number, descending (bottom-up injection)
    sorted_matches = sorted(matches, key=lambda m: m.type_version_line, reverse=True)

    for match in sorted_matches:
        tv_idx = match.type_version_line
        if tv_idx >= len(lines):
            continue

        tv_line = lines[tv_idx]
        if not RE_TYPE_VERSION.search(tv_line):
            continue

        # Detect indentation for the new onError line.
        # Strategy: Use the indentation of the typeVersion line itself.
        # For inline/compact dicts (e.g. '"type": ..., "typeVersion": 4.2,')
        # we detect indent from the line and use it consistently.
        indent = _detect_indent(tv_line)

        # If the typeVersion line is very compact (inline with type + position),
        # look at surrounding lines for better indent reference.
        if indent == "" or (len(indent) < 4 and '"type"' in tv_line):
            # Try the next few lines for indent reference
            for lookahead in range(tv_idx + 1, min(len(lines), tv_idx + 5)):
                candidate_indent = _detect_indent(lines[lookahead])
                if len(candidate_indent) > len(indent) and '"' in lines[lookahead]:
                    indent = candidate_indent
                    break
            # If still no luck, try lines before
            if indent == "" or len(indent) < 4:
                for lookback in range(tv_idx - 1, max(0, tv_idx - 10), -1):
                    candidate_indent = _detect_indent(lines[lookback])
                    if len(candidate_indent) >= 4 and '"' in lines[lookback]:
                        indent = candidate_indent
                        break

        # Ensure the typeVersion line ends with a comma
        stripped = tv_line.rstrip()
        if not stripped.endswith(",") and not stripped.endswith("})"):
            lines[tv_idx] = stripped + ","

        # Build the onError line with matching indentation
        on_error_line = f'{indent}"onError": "continueRegularOutput",'

        # Insert after the typeVersion line
        lines.insert(tv_idx + 1, on_error_line)

    # Write back
    new_content = "\n".join(lines)
    # Preserve trailing newline if original had one
    if content.endswith("\n"):
        new_content += "\n"

    try:
        filepath.write_text(new_content, encoding="utf-8")
        return True
    except OSError:
        return False


def backup_file(filepath: Path) -> Optional[Path]:
    """Create a backup of a file before modification.

    Returns the backup path or None on failure.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / filepath.name
    try:
        shutil.copy2(filepath, backup_path)
        return backup_path
    except OSError:
        return None


# ── CLI ──────────────────────────────────────────────────────────

def format_type_counts(counts: dict[str, int]) -> str:
    """Format type counts for display: '12 httpRequest, 2 googleSheets'."""
    parts = []
    for node_type, count in sorted(counts.items(), key=lambda x: -x[1]):
        parts.append(f"{count} {node_type}")
    return ", ".join(parts)


def run_preview() -> tuple[int, int, int]:
    """Preview mode: scan and report, don't modify files.

    Returns (total_nodes_needing_fix, total_files_affected, total_scripts).
    """
    deploy_scripts = sorted(TOOLS_DIR.glob("deploy_*.py"))
    total_scripts = len(deploy_scripts)

    print(f"=== Global continueOnFail Injector ===")
    print(f"Processing {total_scripts} deploy scripts...\n")

    total_need_fix = 0
    files_affected = 0
    files_already_ok = 0
    files_skipped = 0

    for script_path in deploy_scripts:
        report = scan_file(script_path)

        if report.skipped_reason:
            files_skipped += 1
            print(f"  {report.filename}: SKIPPED ({report.skipped_reason})")
            continue

        if report.needs_fix == 0:
            if report.total_api_nodes > 0:
                files_already_ok += 1
            continue

        files_affected += 1
        total_need_fix += report.needs_fix

        type_detail = format_type_counts(report.type_counts)
        print(f"  {report.filename}: {report.needs_fix} nodes need onError ({type_detail})")

        # Show individual nodes
        for match in report.matches:
            print(f"    L{match.line_number}: {match.node_name} [{match.node_type}]")

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {total_need_fix} nodes across {files_affected} scripts need onError")
    print(f"  Scripts scanned:    {total_scripts}")
    print(f"  Scripts to modify:  {files_affected}")
    print(f"  Scripts already OK: {files_already_ok}")
    print(f"  Scripts skipped:    {files_skipped}")
    print(f"{'=' * 60}")

    return total_need_fix, files_affected, total_scripts


def run_apply() -> None:
    """Apply mode: inject onError into all deploy scripts that need it."""
    deploy_scripts = sorted(TOOLS_DIR.glob("deploy_*.py"))
    total_scripts = len(deploy_scripts)

    print(f"=== Global continueOnFail Injector (APPLY MODE) ===")
    print(f"Processing {total_scripts} deploy scripts...\n")

    total_fixed = 0
    files_modified = 0
    files_skipped = 0
    backup_count = 0
    errors: list[str] = []

    for script_path in deploy_scripts:
        report = scan_file(script_path)

        if report.skipped_reason:
            files_skipped += 1
            continue

        if report.needs_fix == 0:
            continue

        # Back up the file first
        backup_path = backup_file(script_path)
        if backup_path is None:
            err_msg = f"  ERROR: Could not back up {report.filename} -- skipping"
            errors.append(err_msg)
            print(err_msg)
            continue
        backup_count += 1

        # Apply the injection
        success = inject_on_error(script_path, report.matches)
        if not success:
            err_msg = f"  ERROR: Failed to modify {report.filename}"
            errors.append(err_msg)
            print(err_msg)
            continue

        files_modified += 1
        total_fixed += report.needs_fix

        type_detail = format_type_counts(report.type_counts)
        print(f"  FIXED {report.filename}: {report.needs_fix} nodes ({type_detail})")

    print(f"\n{'=' * 60}")
    print(f"APPLIED: {total_fixed} onError injections across {files_modified} scripts")
    print(f"  Backups created:  {backup_count} (in .tmp/backups/continue_on_fail/)")
    print(f"  Scripts skipped:  {files_skipped}")
    if errors:
        print(f"  Errors:           {len(errors)}")
        for err in errors:
            print(f"    {err}")
    print(f"{'=' * 60}")

    # Verification pass: re-scan to confirm injection worked
    print(f"\n--- Verification Pass ---")
    remaining = 0
    for script_path in deploy_scripts:
        report = scan_file(script_path)
        if report.needs_fix > 0:
            remaining += report.needs_fix
            print(f"  WARNING: {report.filename} still has {report.needs_fix} unhandled nodes")

    if remaining == 0:
        print("  All API nodes now have onError handling.")
    else:
        print(f"  WARNING: {remaining} nodes still missing onError -- manual review needed")


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python tools/fix_global_continue_on_fail.py preview   # Show what would change")
        print("  python tools/fix_global_continue_on_fail.py apply     # Apply changes")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "preview":
        run_preview()
    elif command == "apply":
        run_apply()
    else:
        print(f"Unknown command: {command}")
        print("Use 'preview' or 'apply'")
        sys.exit(1)


if __name__ == "__main__":
    main()

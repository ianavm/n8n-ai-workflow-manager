"""
Deploy Script Audit Scanner
Scans all deploy_*.py files for 8 known anti-patterns that cause production failures.

Anti-patterns detected:
    AP-01: $env references in Code/expression nodes (CRITICAL)
    AP-02: autoMapInputData on Airtable nodes (CRITICAL)
    AP-03: Placeholder URLs and IDs (HIGH)
    AP-04: jsonBody/url with '=' prefix (HIGH)
    AP-05: Missing continueOnFail on API nodes (HIGH)
    AP-06: Missing numberOfOutputs on multi-output Code nodes (MEDIUM)
    AP-07: Stale workflow IDs (HIGH)
    AP-08: Expression corruption risk (MEDIUM)

Usage:
    python tools/audit_deploy_scripts.py              # Scan all deploy scripts (default)
    python tools/audit_deploy_scripts.py --all        # Same as above
    python tools/audit_deploy_scripts.py --file FILE  # Scan a single file
    python tools/audit_deploy_scripts.py --json-only  # Output JSON only (for CI)
"""

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
TOOLS_DIR = Path(__file__).parent
PROJECT_ROOT = TOOLS_DIR.parent
TMP_DIR = PROJECT_ROOT / ".tmp"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Issue:
    """Single anti-pattern occurrence found in a deploy script."""
    pattern_id: str
    severity: str
    line: int
    column: int
    match: str
    message: str
    fix: str

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "severity": self.severity,
            "line": self.line,
            "column": self.column,
            "match": self.match,
            "message": self.message,
            "fix": self.fix,
        }


@dataclass
class ScriptReport:
    """All issues found in a single deploy script."""
    filepath: str
    issues: list[Issue] = field(default_factory=list)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def severities(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts

    def to_dict(self) -> dict:
        return {
            "issues": [i.to_dict() for i in self.issues],
            "issue_count": self.issue_count,
            "severities": self.severities,
        }


# ---------------------------------------------------------------------------
# AP-01: $env references in Code/expression nodes
# ---------------------------------------------------------------------------

_RE_ENV_REF = re.compile(r'\$env\.\w+')


def check_ap01_env_refs(filepath: str, content: str) -> list[Issue]:
    """Check for $env references that will fail on n8n Cloud."""
    issues: list[Issue] = []
    for i, line in enumerate(content.splitlines(), 1):
        for m in _RE_ENV_REF.finditer(line):
            issues.append(Issue(
                pattern_id="AP-01",
                severity="CRITICAL",
                line=i,
                column=m.start() + 1,
                match=m.group(),
                message=f"$env reference '{m.group()}' will fail on n8n Cloud",
                fix="Replace with hardcoded value or upstream Set node parameter",
            ))
    return issues


# ---------------------------------------------------------------------------
# AP-02: autoMapInputData on Airtable nodes
# ---------------------------------------------------------------------------

_RE_AUTOMAP = re.compile(r'autoMapInputData')


def check_ap02_automap(filepath: str, content: str) -> list[Issue]:
    """Check for autoMapInputData usage on Airtable create/update nodes."""
    issues: list[Issue] = []
    for i, line in enumerate(content.splitlines(), 1):
        for m in _RE_AUTOMAP.finditer(line):
            issues.append(Issue(
                pattern_id="AP-02",
                severity="CRITICAL",
                line=i,
                column=m.start() + 1,
                match=m.group(),
                message="autoMapInputData sends ALL fields; singleSelect fields reject unknown options",
                fix="Use 'defineBelow' mappingMode with explicit column definitions",
            ))
    return issues


# ---------------------------------------------------------------------------
# AP-03: Placeholder URLs and IDs
# ---------------------------------------------------------------------------

_PLACEHOLDER_PATTERNS = [
    (re.compile(r'REPLACE_AFTER_SETUP', re.IGNORECASE), "REPLACE_AFTER_SETUP placeholder"),
    (re.compile(r'REPLACE_AFTER_DEPLOY', re.IGNORECASE), "REPLACE_AFTER_DEPLOY placeholder"),
    (re.compile(r'REPLACE_WITH_\w+', re.IGNORECASE), "REPLACE_WITH_* placeholder"),
    # Standalone REPLACE (but not REPLACE_AFTER_* or REPLACE_WITH_* already caught)
    (re.compile(r'(?<![A-Z_])REPLACE(?![A-Z_])'), "REPLACE placeholder"),
    (re.compile(r'example\.com'), "example.com placeholder URL"),
    (re.compile(r'localhost[:\d]*'), "localhost reference"),
    (re.compile(r'REPLACE_CHAT_ID|REPLACE_CHANNEL_ID', re.IGNORECASE), "Placeholder chat/channel ID"),
]


def check_ap03_placeholders(filepath: str, content: str) -> list[Issue]:
    """Check for placeholder URLs and IDs that will fail when activated."""
    issues: list[Issue] = []
    seen: set[tuple[int, str]] = set()  # (line, pattern_text) to avoid duplicate matches

    for i, line in enumerate(content.splitlines(), 1):
        # Skip comment-only lines (pure documentation)
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        for pattern, description in _PLACEHOLDER_PATTERNS:
            for m in pattern.finditer(line):
                key = (i, m.group())
                if key in seen:
                    continue
                seen.add(key)

                # Downgrade to INFO if inside os.getenv default (resolved at build time)
                is_getenv_default = bool(re.search(
                    r'os\.getenv\s*\([^,]+,\s*["\'].*' + re.escape(m.group()),
                    line,
                ))
                severity = "INFO" if is_getenv_default else "HIGH"

                issues.append(Issue(
                    pattern_id="AP-03",
                    severity=severity,
                    line=i,
                    column=m.start() + 1,
                    match=m.group(),
                    message=f"Placeholder found: {description}"
                            + (" (os.getenv default -- OK if .env has value)" if is_getenv_default else ""),
                    fix="Replace with actual value or set the corresponding env var",
                ))
    return issues


# ---------------------------------------------------------------------------
# AP-04: jsonBody/url with '=' prefix
# ---------------------------------------------------------------------------

_RE_JSON_BODY_EQ = re.compile(r'"jsonBody"\s*:\s*"=\{')
_RE_JSON_BODY_EQ_TRIPLE = re.compile(r'"jsonBody"\s*:\s*"""=\{', re.MULTILINE)
_RE_URL_EQ = re.compile(r'"url"\s*:\s*"=https?://')


def check_ap04_eq_prefix(filepath: str, content: str) -> list[Issue]:
    """Check for jsonBody/url with '=' prefix that breaks valid JSON."""
    issues: list[Issue] = []
    for i, line in enumerate(content.splitlines(), 1):
        for m in _RE_JSON_BODY_EQ.finditer(line):
            issues.append(Issue(
                pattern_id="AP-04",
                severity="HIGH",
                line=i,
                column=m.start() + 1,
                match=m.group()[:40],
                message="jsonBody starts with '=' prefix -- n8n treats this as expression, not literal JSON",
                fix="Remove the '=' prefix or use expression syntax correctly",
            ))
        for m in _RE_URL_EQ.finditer(line):
            issues.append(Issue(
                pattern_id="AP-04",
                severity="HIGH",
                line=i,
                column=m.start() + 1,
                match=m.group()[:40],
                message="URL starts with '=' prefix -- n8n treats this as expression, not literal URL",
                fix="Remove the '=' prefix or use expression syntax correctly",
            ))

    # Also check for triple-quoted jsonBody with '=' (multiline strings)
    for m in _RE_JSON_BODY_EQ_TRIPLE.finditer(content):
        line_num = content[:m.start()].count('\n') + 1
        issues.append(Issue(
            pattern_id="AP-04",
            severity="HIGH",
            line=line_num,
            column=1,
            match=m.group()[:40],
            message="Triple-quoted jsonBody starts with '=' prefix -- n8n expression in multiline string",
            fix="Remove the '=' prefix or use expression syntax correctly",
        ))

    return issues


# ---------------------------------------------------------------------------
# AP-05: Missing continueOnFail on API nodes
# ---------------------------------------------------------------------------

# Node types that make external API calls and should have error handling
_API_NODE_TYPES = [
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.googleSheets",
    "n8n-nodes-base.airtable",
    "n8n-nodes-base.gmail",
    "n8n-nodes-base.microsoftOutlook",
    "n8n-nodes-base.slack",
    "n8n-nodes-base.telegram",
    "n8n-nodes-base.googleAds",
    "n8n-nodes-base.facebookGraphApi",
]

_RE_NODE_TYPE = re.compile(r'"type"\s*:\s*"(n8n-nodes-base\.\w+)"')
_RE_ON_ERROR = re.compile(r'"onError"\s*:')
_RE_CONTINUE_ON_FAIL = re.compile(r'"continueOnFail"\s*:\s*true')


def check_ap05_missing_error_handling(filepath: str, content: str) -> list[Issue]:
    """Check coverage of continueOnFail/onError on API nodes."""
    issues: list[Issue] = []
    lines = content.splitlines()

    api_node_lines: list[tuple[int, str]] = []
    has_error_handling = False
    total_api_nodes = 0
    protected_api_nodes = 0

    # Check if file uses make_resilient wrapper (adds continueOnFail programmatically)
    has_make_resilient = "def make_resilient" in content

    # Simple heuristic: for each line that declares an API node type,
    # look within the surrounding context (50 lines) for onError or continueOnFail
    for i, line in enumerate(lines):
        for m in _RE_NODE_TYPE.finditer(line):
            node_type = m.group(1)
            if node_type not in _API_NODE_TYPES:
                continue

            total_api_nodes += 1
            # Look in surrounding 50 lines for error handling
            context_start = max(0, i - 10)
            context_end = min(len(lines), i + 50)
            context_block = "\n".join(lines[context_start:context_end])

            if (_RE_ON_ERROR.search(context_block)
                    or _RE_CONTINUE_ON_FAIL.search(context_block)
                    or (has_make_resilient and "make_resilient" in context_block)):
                protected_api_nodes += 1
            else:
                api_node_lines.append((i + 1, node_type))

    if total_api_nodes > 0 and api_node_lines:
        coverage = (protected_api_nodes / total_api_nodes * 100) if total_api_nodes > 0 else 0
        for line_num, node_type in api_node_lines:
            short_type = node_type.replace("n8n-nodes-base.", "")
            issues.append(Issue(
                pattern_id="AP-05",
                severity="HIGH",
                line=line_num,
                column=1,
                match=node_type,
                message=(
                    f"{short_type} node has no onError/continueOnFail "
                    f"(coverage: {protected_api_nodes}/{total_api_nodes} = {coverage:.0f}%)"
                ),
                fix="Add 'onError': 'continueRegularOutput' to node settings",
            ))

    return issues


# ---------------------------------------------------------------------------
# AP-06: Missing numberOfOutputs on multi-output Code nodes
# ---------------------------------------------------------------------------

_RE_CODE_NODE = re.compile(r'"type"\s*:\s*"n8n-nodes-base\.code"')
_RE_NUM_OUTPUTS = re.compile(r'"numberOfOutputs"\s*:\s*\d+')
_RE_RETURN_ARRAY = re.compile(r'return\s*\[')


def check_ap06_missing_num_outputs(filepath: str, content: str) -> list[Issue]:
    """Check for Code nodes that may return multiple outputs but lack numberOfOutputs."""
    issues: list[Issue] = []
    lines = content.splitlines()

    for i, line in enumerate(lines):
        if not _RE_CODE_NODE.search(line):
            continue

        # Look ahead in the node definition (next 100 lines) for numberOfOutputs
        context_start = i
        context_end = min(len(lines), i + 100)
        context_block = "\n".join(lines[context_start:context_end])

        has_num_outputs = _RE_NUM_OUTPUTS.search(context_block) is not None

        if has_num_outputs:
            continue

        # Check for patterns suggesting multiple return values
        # Look for `return [` in associated code strings
        # Also check for jsCode strings with array-of-array returns
        code_region_end = min(len(lines), i + 200)
        code_block = "\n".join(lines[i:code_region_end])

        # Detect patterns like return [items1, items2] (multi-output)
        multi_return = re.search(r'return\s*\[\s*\[', code_block)
        if multi_return:
            issues.append(Issue(
                pattern_id="AP-06",
                severity="MEDIUM",
                line=i + 1,
                column=1,
                match="Code node without numberOfOutputs",
                message="Code node appears to return multiple output arrays but has no numberOfOutputs parameter",
                fix="Add 'numberOfOutputs': N to the Code node parameters",
            ))

    return issues


# ---------------------------------------------------------------------------
# AP-07: Stale workflow IDs (hardcoded n8n IDs)
# ---------------------------------------------------------------------------

# n8n workflow/credential IDs are typically 16-char alphanumeric strings
_RE_N8N_ID = re.compile(r'"([a-zA-Z0-9]{16})"')

# Known credential IDs that are expected (not stale workflow refs)
_KNOWN_CRED_PATTERNS = {
    "id", "name", "credentials", "CRED_", "cred_",
}


def check_ap07_stale_ids(filepath: str, content: str) -> list[Issue]:
    """Extract hardcoded n8n workflow IDs for cross-reference validation."""
    issues: list[Issue] = []
    lines = content.splitlines()
    seen_ids: set[str] = set()

    for i, line in enumerate(lines, 1):
        # Skip credential definitions (those are expected)
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        for m in _RE_N8N_ID.finditer(line):
            n8n_id = m.group(1)

            # Skip if already reported
            if n8n_id in seen_ids:
                continue

            # Check if this looks like it's used as a workflow ID reference
            # (execute workflow, sub-workflow call, etc.)
            context_before = line[:m.start()].lower()
            is_workflow_ref = any(kw in context_before for kw in [
                "workflowid", "workflow_id", "workflow",
                "executeworkflow", "execute_workflow",
                "callee", "target",
            ])

            # Also flag IDs that appear in "id" fields (credential or node IDs)
            is_id_field = '"id"' in line[:m.start() + 10]

            if is_workflow_ref:
                seen_ids.add(n8n_id)
                issues.append(Issue(
                    pattern_id="AP-07",
                    severity="HIGH",
                    line=i,
                    column=m.start() + 1,
                    match=n8n_id,
                    message=f"Hardcoded workflow ID '{n8n_id}' -- verify it exists in n8n",
                    fix="Cross-reference with live n8n instance or use env var",
                ))

    return issues


# ---------------------------------------------------------------------------
# AP-08: Expression corruption risk
# ---------------------------------------------------------------------------

# Note: AP-08 uses inline regex matching inside the check function rather than
# pre-compiled lookbehinds, because variable-width lookbehinds are not supported.


def check_ap08_expression_corruption(filepath: str, content: str) -> list[Issue]:
    """Check for .all()/.first().json without proper $input/$() prefix in Code strings."""
    issues: list[Issue] = []
    lines = content.splitlines()

    # Only check inside string literals that look like n8n Code node content
    # Look for lines containing JavaScript patterns within Python strings
    in_code_block = False
    code_block_start = 0

    for i, line in enumerate(lines, 1):
        # Heuristic: detect lines that are inside Code node jsCode content
        # These typically appear as string literals with JS code
        has_js_pattern = any(kw in line for kw in [
            '$input.', '$json.', '$node.', "items[", "const ",
            ".all()", ".first()", "$('",
        ])

        if not has_js_pattern:
            continue

        # Check for .all() without proper prefix
        # Pattern: something.all() where "something" is not $input or $('NodeName')
        # Look for bare .all() that might have lost its $input prefix
        bare_all_matches = re.finditer(r'(?<!\w)(\w+)\.all\(\)', line)
        for m in bare_all_matches:
            prefix = m.group(1)
            # Valid prefixes: $input, items (JS variable), results, etc.
            if prefix in ('$input', 'items', 'results', 'data', 'allItems', 'JSON'):
                continue
            # Check if preceded by $(' which indicates proper expression
            pre_context = line[:m.start()]
            if "$(" in pre_context[-30:]:
                continue
            issues.append(Issue(
                pattern_id="AP-08",
                severity="MEDIUM",
                line=i,
                column=m.start() + 1,
                match=m.group(),
                message=f"Possible expression corruption: '{m.group()}' may be missing $input or $() prefix",
                fix="Ensure expressions use $input.all() or $('NodeName').all()",
            ))

    return issues


# ---------------------------------------------------------------------------
# Runner: execute all checks against a single file
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_ap01_env_refs,
    check_ap02_automap,
    check_ap03_placeholders,
    check_ap04_eq_prefix,
    check_ap05_missing_error_handling,
    check_ap06_missing_num_outputs,
    check_ap07_stale_ids,
    check_ap08_expression_corruption,
]


def audit_file(filepath: Path) -> ScriptReport:
    """Run all anti-pattern checks against a single deploy script."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    report = ScriptReport(filepath=filepath.name)

    for check_fn in ALL_CHECKS:
        found = check_fn(filepath.name, content)
        report.issues.extend(found)

    # Sort issues by line number for readability
    report.issues = sorted(report.issues, key=lambda x: (x.line, x.pattern_id))
    return report


# ---------------------------------------------------------------------------
# Discovery: find all deploy scripts
# ---------------------------------------------------------------------------

def find_deploy_scripts(tools_dir: Optional[Path] = None) -> list[Path]:
    """Find all deploy_*.py scripts in the tools directory."""
    search_dir = tools_dir or TOOLS_DIR
    scripts = sorted(search_dir.glob("deploy_*.py"))
    # Exclude this audit script itself
    scripts = [s for s in scripts if s.name != "audit_deploy_scripts.py"]
    return scripts


# ---------------------------------------------------------------------------
# Report: build full audit report
# ---------------------------------------------------------------------------

def build_report(scripts: list[Path]) -> dict:
    """Build the complete JSON audit report."""
    timestamp = datetime.now(timezone.utc).isoformat()
    script_reports: dict[str, dict] = {}
    all_issues: list[Issue] = []

    for script_path in scripts:
        report = audit_file(script_path)
        if report.issues:
            script_reports[report.filepath] = report.to_dict()
        all_issues.extend(report.issues)

    # Exclude INFO-level issues from actionable counts (they are resolved/informational)
    actionable_issues = [i for i in all_issues if i.severity != "INFO"]
    severity_counts = Counter(i.severity for i in actionable_issues)
    pattern_counts = Counter(i.pattern_id for i in actionable_issues)
    info_count = sum(1 for i in all_issues if i.severity == "INFO")

    # Count unique scripts per pattern (excluding INFO)
    pattern_script_counts: dict[str, int] = {}
    for pid in sorted(pattern_counts.keys()):
        scripts_with_pattern = len({
            name for name, data in script_reports.items()
            if any(
                issue["pattern_id"] == pid and issue.get("severity") != "INFO"
                for issue in data["issues"]
            )
        })
        pattern_script_counts[pid] = scripts_with_pattern

    return {
        "timestamp": timestamp,
        "total_scripts": len(scripts),
        "scripts_with_issues": len(script_reports),
        "total_issues": len(actionable_issues),
        "info_issues": info_count,
        "by_severity": dict(sorted(severity_counts.items())),
        "by_pattern": {
            pid: {"count": cnt, "scripts_affected": pattern_script_counts.get(pid, 0)}
            for pid, cnt in sorted(pattern_counts.items())
        },
        "scripts": dict(sorted(
            script_reports.items(),
            key=lambda kv: kv[1]["issue_count"],
            reverse=True,
        )),
    }


# ---------------------------------------------------------------------------
# Console output: formatted + colored
# ---------------------------------------------------------------------------

# ANSI color codes (work on most terminals, including Windows Terminal)
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_GREEN = "\033[92m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"

_SEVERITY_COLORS = {
    "CRITICAL": _RED,
    "HIGH": _YELLOW,
    "MEDIUM": _CYAN,
}

PATTERN_DESCRIPTIONS = {
    "AP-01": "$env references (blocked on n8n Cloud)",
    "AP-02": "autoMapInputData (breaks singleSelect fields)",
    "AP-03": "Placeholder URLs/IDs (will fail when activated)",
    "AP-04": "jsonBody/url '=' prefix (expression vs literal)",
    "AP-05": "Missing error handling on API nodes",
    "AP-06": "Missing numberOfOutputs on Code nodes",
    "AP-07": "Stale hardcoded workflow IDs",
    "AP-08": "Expression corruption risk",
}


def print_report(report: dict) -> None:
    """Print a formatted, colored summary to the console."""
    total = report["total_scripts"]
    with_issues = report["scripts_with_issues"]
    total_issues = report["total_issues"]

    print()
    print(f"{_BOLD}{'=' * 55}")
    print(f"  Deploy Script Audit Report")
    print(f"{'=' * 55}{_RESET}")
    print(f"  Scanned {_BOLD}{total}{_RESET} deploy scripts")
    print(f"  Found {_BOLD}{total_issues}{_RESET} issues in {_BOLD}{with_issues}{_RESET} scripts")
    print(f"  {_DIM}{report['timestamp']}{_RESET}")
    print()

    if total_issues == 0:
        print(f"  {_GREEN}{_BOLD}All clear -- no anti-patterns detected.{_RESET}")
        print()
        return

    # Group by severity
    severity_order = ["CRITICAL", "HIGH", "MEDIUM"]
    for severity in severity_order:
        count = report["by_severity"].get(severity, 0)
        if count == 0:
            continue

        color = _SEVERITY_COLORS.get(severity, _RESET)
        print(f"  {color}{_BOLD}{severity} ({count} issues):{_RESET}")

        # Show patterns at this severity
        for pid, pdata in sorted(report["by_pattern"].items()):
            # Determine severity from the issues
            pattern_severity = _get_pattern_severity(pid)
            if pattern_severity != severity:
                continue

            desc = PATTERN_DESCRIPTIONS.get(pid, pid)
            pcount = pdata["count"]
            pscripts = pdata["scripts_affected"]
            print(f"    {color}{pid}{_RESET} {desc}: "
                  f"{_BOLD}{pcount}{_RESET} in {pscripts} script{'s' if pscripts != 1 else ''}")

        print()

    # Top problematic scripts
    scripts = report.get("scripts", {})
    if scripts:
        sorted_scripts = sorted(
            scripts.items(),
            key=lambda kv: kv[1]["issue_count"],
            reverse=True,
        )
        top_n = min(10, len(sorted_scripts))
        print(f"  {_BOLD}Top {top_n} most problematic scripts:{_RESET}")
        for rank, (name, data) in enumerate(sorted_scripts[:top_n], 1):
            sev_parts = []
            for s in severity_order:
                c = data["severities"].get(s, 0)
                if c > 0:
                    color = _SEVERITY_COLORS.get(s, _RESET)
                    sev_parts.append(f"{color}{c} {s}{_RESET}")
            sev_str = ", ".join(sev_parts)
            print(f"    {rank:>2}. {name} ({data['issue_count']} issues: {sev_str})")

        print()

    # Clean scripts
    clean_count = total - with_issues
    if clean_count > 0:
        print(f"  {_GREEN}{clean_count} scripts passed with no issues.{_RESET}")
        print()


def _get_pattern_severity(pattern_id: str) -> str:
    """Map pattern ID to its primary severity."""
    severity_map = {
        "AP-01": "CRITICAL",
        "AP-02": "CRITICAL",
        "AP-03": "HIGH",
        "AP-04": "HIGH",
        "AP-05": "HIGH",
        "AP-06": "MEDIUM",
        "AP-07": "HIGH",
        "AP-08": "MEDIUM",
    }
    return severity_map.get(pattern_id, "MEDIUM")


# ---------------------------------------------------------------------------
# Save JSON report
# ---------------------------------------------------------------------------

def save_report(report: dict) -> Path:
    """Save report as JSON to .tmp/ directory."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_path = TMP_DIR / f"audit_report_{date_str}.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> dict:
    """Parse command-line arguments."""
    args = {
        "mode": "all",        # "all" | "file"
        "file": None,         # path when mode == "file"
        "json_only": False,   # suppress console output, print JSON
    }

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--all":
            args["mode"] = "all"
        elif arg == "--file":
            if i + 1 >= len(argv):
                print("Error: --file requires a path argument", file=sys.stderr)
                sys.exit(1)
            args["mode"] = "file"
            args["file"] = argv[i + 1]
            i += 1
        elif arg == "--json-only":
            args["json_only"] = True
        elif arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        else:
            print(f"Error: unknown argument '{arg}'", file=sys.stderr)
            print("Usage: python tools/audit_deploy_scripts.py [--all|--file FILE|--json-only]",
                  file=sys.stderr)
            sys.exit(1)
        i += 1

    return args


def main() -> int:
    """Entry point."""
    args = parse_args(sys.argv[1:])

    # Discover scripts
    if args["mode"] == "file":
        target = Path(args["file"])
        if not target.exists():
            print(f"Error: file not found: {target}", file=sys.stderr)
            return 1
        scripts = [target]
    else:
        scripts = find_deploy_scripts()
        if not scripts:
            print("No deploy_*.py scripts found in tools/", file=sys.stderr)
            return 1

    # Build report
    report = build_report(scripts)

    # Output
    if args["json_only"]:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report)
        report_path = save_report(report)
        print(f"  {_DIM}JSON report saved to: {report_path}{_RESET}")
        print()

    # Exit code: 1 if any CRITICAL issues found
    has_critical = report["by_severity"].get("CRITICAL", 0) > 0
    return 1 if has_critical else 0


if __name__ == "__main__":
    sys.exit(main())

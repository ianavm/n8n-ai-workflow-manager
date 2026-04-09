"""
Fix $env references in ALL deploy scripts.

n8n Cloud blocks $env access in Code nodes and expressions.
This script scans all deploy_*.py files for n8n-runtime $env.VARNAME
patterns and replaces them with values resolved at Python build time.

Strategy per pattern type:
  A. Standalone n8n expression ("={{ $env.VAR }}") as entire value
     -> replace string with os.getenv("VAR", "fallback") Python call
  B. Embedded n8n expression in larger string ("...{{ $env.VAR }}...")
     -> inline the resolved value directly into the string
  C. Bare $env.VAR in jsCode strings (Code nodes)
     -> replace with JS string literal of resolved value
  D. Secrets (API keys, tokens, passphrases)
     -> use os.getenv() call to resolve at build time, never hardcode

Usage:
    python tools/fix_env_refs_all_scripts.py preview   # Show what would change
    python tools/fix_env_refs_all_scripts.py apply      # Apply changes with backups
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Load .env so we can resolve values at script runtime
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)
except ImportError:
    # Manual fallback: parse .env line-by-line
    if ENV_PATH.exists():
        for _line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#"):
                continue
            if "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

TOOLS_DIR = PROJECT_ROOT / "tools"
BACKUP_DIR = PROJECT_ROOT / ".tmp" / "backups" / "env_refs"

# ---------------------------------------------------------------------------
# Variable name aliases: n8n $env name -> actual .env name
# Some deploy scripts use different names than what's in .env
# ---------------------------------------------------------------------------

VAR_ALIASES: dict[str, str] = {
    "WHATSAPP_PHONE_ID": "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_ACCESS_TOKEN": "FA_WHATSAPP_ACCESS_TOKEN",
}

# ---------------------------------------------------------------------------
# Secret detection: these should NEVER be hardcoded in source.
# They get resolved via os.getenv() at Python build time.
# ---------------------------------------------------------------------------

SECRET_VARS: frozenset[str] = frozenset({
    "N8N_API_KEY",
    "WEBHOOK_AUTH_TOKEN",
    "STRIPE_WEBHOOK_SECRET",
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_APP_SECRET",
    "OPENROUTER_API_KEY",
    "AIRTABLE_API_TOKEN",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ACCESS_TOKEN",
    "FA_WHATSAPP_ACCESS_TOKEN",
    "PAYFAST_PASSPHRASE",
    "PAYFAST_MERCHANT_KEY",
    "PORTAL_ADMIN_KEY",
    "GITHUB_PAT",
    "XERO_CLIENT_SECRET",
    "TELEGRAM_BOT_TOKEN",
    "LI_TELEGRAM_BOT_TOKEN",
    "APIFY_API_TOKEN",
    "N8N_CLOUD_MCP_JWT",
})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Replacement:
    """A single $env replacement within a file."""

    file: str
    line_num: int
    env_var: str
    old_text: str
    new_text: str
    category: str  # "expression", "code_node", "secret", "standalone"
    resolved: bool = True  # False if env var is missing and no fallback


@dataclass
class FileReport:
    """All replacements planned/made for one file."""

    path: Path
    replacements: list[Replacement] = field(default_factory=list)
    backed_up: bool = False
    applied: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_env_var(var_name: str) -> Optional[str]:
    """Look up an environment variable, checking aliases too."""
    val = os.environ.get(var_name)
    if val is not None:
        return val
    # Check alias
    alias = VAR_ALIASES.get(var_name)
    if alias:
        return os.environ.get(alias)
    return None


def canonical_var_name(var_name: str) -> str:
    """Return the canonical .env variable name (resolving aliases)."""
    return VAR_ALIASES.get(var_name, var_name)


def is_secret(var_name: str) -> bool:
    """Check if a variable is a secret that should not be hardcoded."""
    canonical = canonical_var_name(var_name)
    if var_name in SECRET_VARS or canonical in SECRET_VARS:
        return True
    upper = var_name.upper()
    for keyword in ("_KEY", "_SECRET", "_TOKEN", "_PASSWORD", "_PASSPHRASE"):
        if keyword in upper:
            return True
    return False


def extract_fallback(text: str) -> str:
    """Extract fallback from '|| "default"' or "|| 'default'" expressions."""
    m = re.search(r"\|\|\s*['\"]([^'\"]*)['\"]", text)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Regex patterns for $env references in Python string literals
# ---------------------------------------------------------------------------

# Pattern 1: Full n8n mustache expression {{ $env.VAR }} or {{ $env.VAR || 'fb' }}
RE_MUSTACHE = re.compile(
    r"\{\{\s*\$env\.([A-Z][A-Z0-9_]*)"
    r"(\s*\|\|\s*(?:'[^']*'|\"[^\"]*\"))?"
    r"\s*\}\}"
)

# Pattern 2: Bare $env.VAR || 'fallback' in JS code strings
RE_BARE_WITH_FB = re.compile(
    r"\$env\.([A-Z][A-Z0-9_]*)\s*\|\|\s*('[^']*'|\"[^\"]*\")"
)

# Pattern 3: Bare $env.VAR in JS code strings (no fallback)
RE_BARE = re.compile(
    r"\$env\.([A-Z][A-Z0-9_]*)"
)

# Pattern for detecting if the entire Python string is just an n8n expression
# e.g., "={{ $env.VAR || '' }}" or "={{ $env.VAR }}"
RE_STANDALONE_EXPR = re.compile(
    r'^"=\{\{\s*\$env\.([A-Z][A-Z0-9_]*)'
    r'(\s*\|\|\s*(?:\'[^\']*\'|"[^"]*"))?\s*\}\}"'
)


# ---------------------------------------------------------------------------
# Line-by-line replacement engine
# ---------------------------------------------------------------------------

def process_line(
    line: str,
    line_num: int,
    file_path: str,
) -> tuple[str, list[Replacement]]:
    """Process one source line. Replace all $env references.

    Returns (modified_line, list_of_replacements).
    """
    replacements: list[Replacement] = []
    result = line

    # Collect all match spans to process right-to-left (preserving offsets).
    # Each entry: (start, end, var_name, full_match, category)
    hits: list[tuple[int, int, str, str, str]] = []

    # 1. Mustache {{ $env.VAR ... }}
    for m in RE_MUSTACHE.finditer(result):
        hits.append((m.start(), m.end(), m.group(1), m.group(0), "expression"))

    # 2. Bare $env.VAR || 'fallback'
    for m in RE_BARE_WITH_FB.finditer(result):
        if not _covered(m.start(), m.end(), hits):
            hits.append((m.start(), m.end(), m.group(1), m.group(0), "code_node"))

    # 3. Bare $env.VAR
    for m in RE_BARE.finditer(result):
        if not _covered(m.start(), m.end(), hits):
            hits.append((m.start(), m.end(), m.group(1), m.group(0), "code_node"))

    # Process right-to-left
    hits.sort(key=lambda h: h[0], reverse=True)

    for start, end, var_name, full_match, category in hits:
        env_val = resolve_env_var(var_name)
        fallback = extract_fallback(full_match)
        secret = is_secret(var_name)
        resolved_val = env_val if env_val is not None else fallback
        was_resolved = env_val is not None or bool(fallback)
        cat = "secret" if secret else category

        if category == "expression":
            # Inside a string: "...{{ $env.VAR || 'fb' }}..."
            # Replace mustache with the resolved value inline.
            result = result[:start] + resolved_val + result[end:]

        elif category == "code_node":
            # Inside jsCode: $env.VAR || 'fb' or bare $env.VAR
            if "||" in full_match:
                # Replace entire  $env.VAR || 'fb'  with  'resolved_val'
                result = result[:start] + f"'{resolved_val}'" + result[end:]
            else:
                # Replace bare  $env.VAR  with  'resolved_val'
                result = result[:start] + f"'{resolved_val}'" + result[end:]

        # Mask secrets in preview output
        if secret and resolved_val:
            preview = resolved_val[:4] + "***" + resolved_val[-4:] if len(resolved_val) > 12 else "***"
        else:
            preview = (resolved_val[:40] + "...") if len(resolved_val) > 40 else resolved_val

        replacements.append(Replacement(
            file=file_path,
            line_num=line_num,
            env_var=var_name,
            old_text=full_match,
            new_text=preview,
            category=cat,
            resolved=was_resolved,
        ))

    return result, replacements


def _covered(start: int, end: int, existing: list[tuple[int, int, str, str, str]]) -> bool:
    """Check if a span is already covered by an existing match."""
    return any(s <= start and end <= e for s, e, *_ in existing)


# ---------------------------------------------------------------------------
# Phase 0: Python string concatenation patterns
# ---------------------------------------------------------------------------

def fix_concat_env_patterns(content: str, file_path: str) -> tuple[str, list[Replacement]]:
    """Fix patterns where $env fallback uses Python string concatenation.

    Handles deploy_self_healing.py style patterns like:
        n8n_url_expr = "={{ $env.N8N_BASE_URL || '" + N8N_BASE_URL + "' }}"
        "url": "={{ ... ($env.N8N_BASE_URL || '" + N8N_BASE_URL + "') + '/path' ... }}",
        "url": "={{ $env.N8N_BASE_URL || '" + N8N_BASE_URL + "' }}/api/v1/...",

    These are n8n expressions where the fallback is injected via Python
    concatenation at build time. Since $env is blocked on Cloud, we remove
    the $env reference and keep only the Python-injected value.
    """
    replacements: list[Replacement] = []
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []

    # Pattern A: Simple assignment
    # VAR = "={{ $env.X || '" + PYVAR + "' }}"
    pat_simple = re.compile(
        r"""^(\s*\w+\s*=\s*)"=\{\{\s*\$env\.([A-Z][A-Z0-9_]*)\s*\|\|\s*'"\s*\+\s*([A-Z][A-Z0-9_]*)\s*\+\s*"'\s*\}\}"(.*)$"""
    )

    # Pattern B: Parenthesized in larger expression
    # ($env.VAR || '" + PYVAR + "')
    pat_paren = re.compile(
        r"""\(\$env\.([A-Z][A-Z0-9_]*)\s*\|\|\s*'"\s*\+\s*([A-Z][A-Z0-9_]*)\s*\+\s*"'\)"""
    )

    # Pattern C: Non-parenthesized with URL suffix
    # "={{ $env.VAR || '" + PYVAR + "' }}/suffix..."
    # Captures: opening quote through closing quote+suffix
    # Use non-raw string so \" works for literal double quotes
    pat_url_suffix = re.compile(
        "\"=\\{\\{\\s*\\$env\\.([A-Z][A-Z0-9_]*)\\s*\\|\\|\\s*'\"\\s*\\+\\s*"
        "([A-Z][A-Z0-9_]*)\\s*\\+\\s*\"'\\s*\\}\\}([^\"]*)\"",
    )

    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            new_lines.append(line)
            continue

        new_line = line
        matched = False

        # Try Pattern A: simple assignment
        m = pat_simple.match(new_line)
        if m:
            prefix, var_name, py_var, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
            new_line = f"{prefix}{py_var}{suffix}\n"
            replacements.append(Replacement(
                file=file_path, line_num=i, env_var=var_name,
                old_text=f"$env.{var_name} || ... + {py_var} + ...",
                new_text=py_var,
                category="concat_simplify", resolved=True,
            ))
            matched = True

        # Try Pattern B: parenthesized
        if not matched:
            paren_matches = list(pat_paren.finditer(new_line))
            for pm in reversed(paren_matches):
                var_name, py_var = pm.group(1), pm.group(2)
                replacement = "'\" + " + py_var + " + \"'"
                new_line = new_line[:pm.start()] + replacement + new_line[pm.end():]
                replacements.append(Replacement(
                    file=file_path, line_num=i, env_var=var_name,
                    old_text=pm.group(0),
                    new_text=f"'\" + {py_var} + \"'",
                    category="concat_simplify", resolved=True,
                ))
                matched = True

        # Try Pattern C: URL suffix (no parens)
        if not matched:
            url_matches = list(pat_url_suffix.finditer(new_line))
            for um in reversed(url_matches):
                var_name, py_var, suffix = um.group(1), um.group(2), um.group(3)
                replacement = f'"=" + {py_var} + "{suffix}"'
                new_line = new_line[:um.start()] + replacement + new_line[um.end():]
                replacements.append(Replacement(
                    file=file_path, line_num=i, env_var=var_name,
                    old_text=f"$env.{var_name} || ... + {py_var} + ...",
                    new_text=f'{py_var} + "{suffix}"',
                    category="concat_simplify", resolved=True,
                ))
                matched = True

        new_lines.append(new_line)

    return "".join(new_lines), replacements


# ---------------------------------------------------------------------------
# Phase 1: Standalone expression refactoring
# ---------------------------------------------------------------------------

def refactor_standalone_expressions(content: str, file_path: str) -> tuple[str, list[Replacement]]:
    """Find lines where the ENTIRE string value is an n8n expression
    like "={{ $env.VAR || '' }}" and refactor to os.getenv().

    This handles cases like:
        "Call RE-15 Scoring", "={{ $env.RE_WF_RE15_ID || '' }}",
    becomes:
        "Call RE-15 Scoring", os.getenv("RE_WF_RE15_ID", ""),
    """
    replacements: list[Replacement] = []
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []

    # Pattern: captures a quoted n8n expression that is the entire value
    # Matches: "={{ $env.VAR || 'fallback' }}"  or  "={{ $env.VAR }}"
    pat = re.compile(
        r'"=\{\{\s*\$env\.([A-Z][A-Z0-9_]*)'
        r'(?:\s*\|\|\s*\'([^\']*)\')?\s*\}\}"'
    )

    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            new_lines.append(line)
            continue

        new_line = line
        # Process all standalone expressions on this line (right to left)
        matches = list(pat.finditer(new_line))
        for m in reversed(matches):
            var_name = m.group(1)
            fallback = m.group(2) or ""
            canonical = canonical_var_name(var_name)
            secret = is_secret(var_name)

            # Build the os.getenv replacement
            escaped_fb = fallback.replace('"', '\\"')
            replacement = f'os.getenv("{canonical}", "{escaped_fb}")'

            new_line = new_line[:m.start()] + replacement + new_line[m.end():]

            if secret:
                preview = f'os.getenv("{canonical}", "***")'
            else:
                preview = replacement

            replacements.append(Replacement(
                file=file_path,
                line_num=i,
                env_var=var_name,
                old_text=m.group(0),
                new_text=preview,
                category="standalone",
                resolved=True,
            ))

        new_lines.append(new_line)

    return "".join(new_lines), replacements


# ---------------------------------------------------------------------------
# File-level processing
# ---------------------------------------------------------------------------

def _run_phases(content: str, file_path: str) -> tuple[str, list[Replacement]]:
    """Run all replacement phases on file content.

    Returns (modified_content, all_replacements).
    """
    all_reps: list[Replacement] = []

    # Phase 0: Fix Python string concatenation patterns ($env.VAR || '" + PYVAR + "')
    content, p0_reps = fix_concat_env_patterns(content, file_path)
    all_reps.extend(p0_reps)

    # Phase 1: Refactor standalone n8n expressions to os.getenv()
    content, p1_reps = refactor_standalone_expressions(content, file_path)
    all_reps.extend(p1_reps)

    # Phase 2: Inline remaining $env references (embedded in larger strings / jsCode)
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            new_lines.append(line)
            continue
        new_line, line_reps = process_line(line, i, file_path)
        new_lines.append(new_line)
        all_reps.extend(line_reps)

    return "".join(new_lines), all_reps


def process_file(file_path: Path) -> FileReport:
    """Scan a deploy script and compute all replacements (preview mode)."""
    report = FileReport(path=file_path)

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        report.error = f"Read error: {exc}"
        return report

    _, all_reps = _run_phases(content, str(file_path))
    report.replacements = _dedup(all_reps)
    return report


def apply_file(file_path: Path) -> FileReport:
    """Apply all $env replacements to a deploy script, with backup."""
    report = FileReport(path=file_path)

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        report.error = f"Read error: {exc}"
        return report

    # Backup
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / file_path.name
    try:
        shutil.copy2(file_path, backup_path)
        report.backed_up = True
    except Exception as exc:
        report.error = f"Backup error: {exc}"
        return report

    new_content, all_reps = _run_phases(content, str(file_path))
    report.replacements = _dedup(all_reps)

    if report.replacements:
        try:
            file_path.write_text(new_content, encoding="utf-8")
            report.applied = True
        except Exception as exc:
            report.error = f"Write error: {exc}"
            try:
                shutil.copy2(backup_path, file_path)
            except Exception:
                pass
    else:
        # No changes, remove unneeded backup
        try:
            backup_path.unlink()
        except Exception:
            pass

    return report


def _dedup(reps: list[Replacement]) -> list[Replacement]:
    """Remove duplicate replacements (same line + var + old text)."""
    seen: set[tuple[int, str, str]] = set()
    unique: list[Replacement] = []
    for r in reps:
        key = (r.line_num, r.env_var, r.old_text)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(reports: list[FileReport], mode: str) -> None:
    """Print a human-readable summary."""
    total_files = 0
    total_replacements = 0
    total_secrets = 0
    total_unresolved = 0
    total_standalone = 0
    total_concat = 0
    total_errors = 0

    for report in reports:
        if not report.replacements and not report.error:
            continue

        total_files += 1
        name = report.path.name

        if report.error:
            total_errors += 1
            print(f"\n  ERROR in {name}: {report.error}")
            continue

        count = len(report.replacements)
        total_replacements += count
        status = ""
        if mode == "apply":
            status = " [APPLIED]" if report.applied else " [BACKUP ONLY]"

        print(f"\n  {name} ({count} replacement{'s' if count != 1 else ''}){status}")

        if report.backed_up and mode == "apply":
            print(f"    Backup: .tmp/backups/env_refs/{name}")

        for r in report.replacements:
            tags: list[str] = []
            if r.category == "secret":
                tags.append("SECRET")
                total_secrets += 1
            if r.category == "standalone":
                tags.append("os.getenv")
                total_standalone += 1
            if r.category == "concat_simplify":
                tags.append("CONCAT")
                total_concat += 1
            if not r.resolved:
                tags.append("UNRESOLVED")
                total_unresolved += 1
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            print(f"    L{r.line_num}: $env.{r.env_var} -> {r.new_text}{tag_str}")

    print(f"\n{'=' * 64}")
    print(f"  Total: {total_replacements} replacements across {total_files} files")
    if total_standalone > 0:
        print(f"  Standalone -> os.getenv(): {total_standalone}")
    if total_concat > 0:
        print(f"  Concat patterns simplified: {total_concat}")
    if total_secrets > 0:
        print(f"  Secrets: {total_secrets} (masked in preview, resolved from .env)")
    if total_unresolved > 0:
        print(f"  UNRESOLVED: {total_unresolved} (env var missing, using fallback)")
    if total_errors > 0:
        print(f"  Errors: {total_errors}")
    if mode == "preview":
        print("  Run with 'apply' to modify deploy script source files.")
    elif mode == "apply":
        print(f"  Backups: .tmp/backups/env_refs/")
    print(f"{'=' * 64}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def find_deploy_scripts() -> list[Path]:
    """Find all deploy_*.py in tools/."""
    return sorted(TOOLS_DIR.glob("deploy_*.py"))


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("preview", "apply"):
        print("Usage: python tools/fix_env_refs_all_scripts.py <preview|apply>")
        print()
        print("  preview  - Scan all deploy scripts, show what would change")
        print("  apply    - Apply changes (backups to .tmp/backups/env_refs/)")
        sys.exit(1)

    mode = sys.argv[1]

    # Verify .env loaded
    if not os.environ.get("N8N_BASE_URL"):
        print("WARNING: .env may not be loaded properly.")
        print(f"  Expected at: {ENV_PATH}")
        if not ENV_PATH.exists():
            print("  File does not exist!")
            sys.exit(1)

    scripts = find_deploy_scripts()
    print(f"{'=' * 64}")
    print(f"  fix_env_refs_all_scripts.py - {mode.upper()}")
    print(f"  Scanning {len(scripts)} deploy scripts for $env references")
    print(f"{'=' * 64}")

    # Quick filter: only scripts containing "$env."
    affected: list[Path] = []
    for s in scripts:
        try:
            if "$env." in s.read_text(encoding="utf-8"):
                affected.append(s)
        except Exception:
            affected.append(s)

    if not affected:
        print("\n  No $env references found in any deploy script.")
        print(f"{'=' * 64}")
        return

    print(f"  Found {len(affected)} scripts with $env references\n")

    reports: list[FileReport] = []
    for script in affected:
        if mode == "preview":
            reports.append(process_file(script))
        else:
            reports.append(apply_file(script))

    print_report(reports, mode)


if __name__ == "__main__":
    main()

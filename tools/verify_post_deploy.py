"""
Post-Deployment Verification Harness

Fetches live workflows from n8n and validates against 9 integrity checks.
Catches deployment corruption: stripped expressions, broken auth configs,
dangling connections, missing error handling, and more.

Usage:
    python tools/verify_post_deploy.py --all              # Check all active workflows
    python tools/verify_post_deploy.py --id <workflow_id>  # Check a single workflow
    python tools/verify_post_deploy.py --json-only         # Machine-readable output only
    python tools/verify_post_deploy.py --no-cache          # Skip workflow list cache
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(str(Path(__file__).parent.parent / ".env"))

from n8n_client import N8nClient
from config_loader import load_config


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Airtable tables known to contain singleSelect fields (autoMap is dangerous)
SINGLE_SELECT_TABLES: Dict[str, str] = {
    "tblgHAw52EyUcIkWR": "Orchestrator_Events",
    "tblov57B8uj09ZF2k": "Campaign_Approvals",
}

# Node types considered "API nodes" for error-handling coverage (Check 5)
API_NODE_TYPES: set = {
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.googleSheets",
    "n8n-nodes-base.airtable",
    "n8n-nodes-base.gmail",
}

# Patterns that indicate placeholder / mock URLs
PLACEHOLDER_URL_PATTERNS: List[re.Pattern] = [
    re.compile(r"https?://example\.com", re.IGNORECASE),
    re.compile(r"https?://localhost", re.IGNORECASE),
    re.compile(r"https?://127\.0\.0\.1", re.IGNORECASE),
    re.compile(r"https?://your[-_]?domain", re.IGNORECASE),
    re.compile(r"https?://placeholder", re.IGNORECASE),
    re.compile(r"https?://todo", re.IGNORECASE),
    re.compile(r"REPLACE_ME", re.IGNORECASE),
]

# Warn threshold for error-handling coverage (%)
ERROR_HANDLING_WARN_THRESHOLD: int = 80


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    """Single verification issue."""
    check: int
    severity: str  # "error" | "warn"
    message: str


@dataclass
class WorkflowResult:
    """Result of verifying one workflow."""
    workflow_id: str
    workflow_name: str
    active: bool
    issues: List[Issue] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(i.severity == "error" for i in self.issues):
            return "FAIL"
        if self.issues:
            return "WARN"
        return "PASS"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "active": self.active,
            "status": self.status,
            "issue_count": len(self.issues),
            "issues": [
                {"check": i.check, "severity": i.severity, "message": i.message}
                for i in self.issues
            ],
        }


# ---------------------------------------------------------------------------
# Recursive parameter scanner
# ---------------------------------------------------------------------------

def _scan_params(obj: Any, pattern: re.Pattern, path: str = "") -> List[str]:
    """Recursively scan a JSON-like object for regex matches. Returns match strings."""
    matches: List[str] = []
    if isinstance(obj, str):
        for m in pattern.finditer(obj):
            matches.append(m.group(0))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            matches.extend(_scan_params(v, pattern, f"{path}.{k}"))
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            matches.extend(_scan_params(v, pattern, f"{path}[{idx}]"))
    return matches


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_1_no_env_refs(nodes: List[Dict], **_kw: Any) -> List[Issue]:
    """Check 1: No $env references remain in any node parameters."""
    issues: List[Issue] = []
    env_pattern = re.compile(r"\$env\.\w+")
    for node in nodes:
        name = node.get("name", "<unnamed>")
        params = node.get("parameters", {})
        matches = _scan_params(params, env_pattern)
        for match in matches:
            issues.append(Issue(
                check=1,
                severity="error",
                message=f"Node '{name}' has $env reference: {match}",
            ))
    return issues


def _has_broken_all_call(js_code: str) -> bool:
    """Detect .all().<method> calls that lack a $input or $('...') prefix."""
    # Find every .all().<method> occurrence and check what precedes it
    for m in re.finditer(r"\.all\(\)\s*\.(map|filter|forEach|reduce)\b", js_code):
        start = m.start()
        preceding = js_code[max(0, start - 30):start]
        # Valid prefixes end with $input or $('SomeName')
        if re.search(r"\$input\s*$", preceding):
            continue
        if re.search(r"\$\('[^']*'\)\s*$", preceding):
            continue
        return True
    return False


def _has_broken_first_call(js_code: str) -> bool:
    """Detect .first().json calls that lack a $input or $('...') prefix."""
    for m in re.finditer(r"\.first\(\)\.json\b", js_code):
        start = m.start()
        preceding = js_code[max(0, start - 30):start]
        if re.search(r"\$input\s*$", preceding):
            continue
        if re.search(r"\$\('[^']*'\)\s*$", preceding):
            continue
        return True
    return False


def check_2_stripped_expressions(nodes: List[Dict], **_kw: Any) -> List[Issue]:
    """Check 2: No stripped $input/$json prefixes in Code nodes."""
    issues: List[Issue] = []
    for node in nodes:
        ntype = node.get("type", "")
        if ntype != "n8n-nodes-base.code":
            continue
        name = node.get("name", "<unnamed>")
        js_code = node.get("parameters", {}).get("jsCode", "")
        if not js_code:
            continue
        if _has_broken_all_call(js_code):
            issues.append(Issue(
                check=2,
                severity="error",
                message=f"Node '{name}' has broken expression: .all().method without $input prefix",
            ))
        if _has_broken_first_call(js_code):
            issues.append(Issue(
                check=2,
                severity="error",
                message=f"Node '{name}' has broken expression: .first().json without $input or $('...') prefix",
            ))
    return issues


def check_3_jsonbody_equals_prefix(nodes: List[Dict], **_kw: Any) -> List[Issue]:
    """Check 3: No jsonBody with '=' prefix on httpRequest nodes."""
    issues: List[Issue] = []
    for node in nodes:
        ntype = node.get("type", "")
        if ntype != "n8n-nodes-base.httpRequest":
            continue
        name = node.get("name", "<unnamed>")
        params = node.get("parameters", {})
        json_body = params.get("jsonBody", "")
        if isinstance(json_body, str) and json_body.startswith("={"):
            issues.append(Issue(
                check=3,
                severity="error",
                message=f"Node '{name}' has invalid jsonBody prefix '='",
            ))
    return issues


def check_4_airtable_single_select(nodes: List[Dict], **_kw: Any) -> List[Issue]:
    """Check 4: Airtable create/update nodes using autoMapInputData on singleSelect tables."""
    issues: List[Issue] = []
    for node in nodes:
        ntype = node.get("type", "")
        if ntype != "n8n-nodes-base.airtable":
            continue
        name = node.get("name", "<unnamed>")
        params = node.get("parameters", {})
        operation = params.get("operation", "")
        if operation not in ("create", "update", "upsert"):
            continue
        # Check for autoMapInputData
        columns = params.get("columns", {})
        if isinstance(columns, dict):
            mapping_mode = columns.get("mappingMode", "")
            if mapping_mode == "autoMapInputData":
                # Check if table is in the known singleSelect set
                table_param = params.get("table", {})
                table_id = ""
                if isinstance(table_param, dict):
                    table_id = table_param.get("value", "")
                elif isinstance(table_param, str):
                    table_id = table_param
                if table_id in SINGLE_SELECT_TABLES:
                    issues.append(Issue(
                        check=4,
                        severity="error",
                        message=(
                            f"Node '{name}' uses autoMapInputData on singleSelect "
                            f"table {SINGLE_SELECT_TABLES[table_id]} ({table_id})"
                        ),
                    ))
    return issues


def check_5_api_error_handling(
    nodes: List[Dict], workflow_name: str = "", **_kw: Any
) -> List[Issue]:
    """Check 5: API nodes have error handling. Reports coverage %."""
    issues: List[Issue] = []
    api_nodes_total = 0
    api_nodes_handled = 0
    for node in nodes:
        ntype = node.get("type", "")
        if ntype not in API_NODE_TYPES:
            continue
        api_nodes_total += 1
        has_handling = (
            node.get("continueOnFail", False)
            or node.get("onError") is not None
        )
        if has_handling:
            api_nodes_handled += 1
    if api_nodes_total > 0:
        coverage = int((api_nodes_handled / api_nodes_total) * 100)
        if coverage < ERROR_HANDLING_WARN_THRESHOLD:
            issues.append(Issue(
                check=5,
                severity="warn",
                message=(
                    f"{coverage}% error handling coverage "
                    f"({api_nodes_handled}/{api_nodes_total} API nodes)"
                ),
            ))
    return issues


def check_6_connection_integrity(
    nodes: List[Dict], connections: Dict[str, Any], **_kw: Any
) -> List[Issue]:
    """Check 6: All connection endpoints reference existing nodes."""
    issues: List[Issue] = []
    node_names = {n.get("name", "") for n in nodes}
    for source_name, conn_map in connections.items():
        if source_name not in node_names:
            issues.append(Issue(
                check=6,
                severity="error",
                message=f"Connection from '{source_name}' references non-existent node",
            ))
        if not isinstance(conn_map, dict):
            continue
        for _conn_type, outputs in conn_map.items():
            if not isinstance(outputs, list):
                continue
            for output_group in outputs:
                if not isinstance(output_group, list):
                    continue
                for target in output_group:
                    target_name = target.get("node", "")
                    if target_name and target_name not in node_names:
                        issues.append(Issue(
                            check=6,
                            severity="error",
                            message=(
                                f"Connection from '{source_name}' to '{target_name}' "
                                f"references non-existent node"
                            ),
                        ))
    return issues


def check_7_execute_workflow_ids(
    nodes: List[Dict], existing_workflow_ids: set, **_kw: Any
) -> List[Issue]:
    """Check 7: Execute Workflow nodes reference IDs that exist on n8n."""
    issues: List[Issue] = []
    for node in nodes:
        ntype = node.get("type", "")
        if ntype != "n8n-nodes-base.executeWorkflow":
            continue
        name = node.get("name", "<unnamed>")
        params = node.get("parameters", {})
        # workflowId can be in params directly or under source=database
        wf_id = params.get("workflowId", "")
        if isinstance(wf_id, dict):
            wf_id = wf_id.get("value", "")
        if not wf_id:
            continue
        # Skip expression-based IDs (dynamic)
        if isinstance(wf_id, str) and wf_id.startswith("="):
            continue
        if wf_id not in existing_workflow_ids:
            issues.append(Issue(
                check=7,
                severity="error",
                message=f"Node '{name}' references non-existent workflow ID: {wf_id}",
            ))
    return issues


def check_8_code_multi_output(
    nodes: List[Dict], connections: Dict[str, Any], **_kw: Any
) -> List[Issue]:
    """Check 8: Code nodes with multiple output branches have numberOfOutputs parameter."""
    issues: List[Issue] = []
    for node in nodes:
        ntype = node.get("type", "")
        if ntype != "n8n-nodes-base.code":
            continue
        name = node.get("name", "<unnamed>")
        params = node.get("parameters", {})
        # Count output branches from connections
        node_conns = connections.get(name, {})
        main_outputs = node_conns.get("main", [])
        output_branch_count = len(main_outputs) if isinstance(main_outputs, list) else 0
        if output_branch_count > 1:
            num_outputs = params.get("numberOfOutputs")
            if num_outputs is None:
                issues.append(Issue(
                    check=8,
                    severity="error",
                    message=(
                        f"Code node '{name}' has {output_branch_count} output "
                        f"branches but no numberOfOutputs parameter"
                    ),
                ))
    return issues


def check_9_placeholder_urls_active(
    nodes: List[Dict], is_active: bool = False, **_kw: Any
) -> List[Issue]:
    """Check 9: Active workflows must not contain placeholder URLs."""
    if not is_active:
        return []
    issues: List[Issue] = []
    for node in nodes:
        ntype = node.get("type", "")
        if ntype != "n8n-nodes-base.httpRequest":
            continue
        name = node.get("name", "<unnamed>")
        params = node.get("parameters", {})
        url = str(params.get("url", ""))
        for pattern in PLACEHOLDER_URL_PATTERNS:
            if pattern.search(url):
                issues.append(Issue(
                    check=9,
                    severity="error",
                    message=f"Active workflow has placeholder URL in node '{name}': {url}",
                ))
                break  # one match per node is enough
    return issues


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_1_no_env_refs,
    check_2_stripped_expressions,
    check_3_jsonbody_equals_prefix,
    check_4_airtable_single_select,
    check_5_api_error_handling,
    check_6_connection_integrity,
    check_7_execute_workflow_ids,
    check_8_code_multi_output,
    check_9_placeholder_urls_active,
]


def verify_workflow(
    workflow_data: Dict[str, Any],
    existing_workflow_ids: set,
) -> WorkflowResult:
    """Run all 9 checks against a single workflow's full JSON."""
    wf_id = str(workflow_data.get("id", ""))
    wf_name = workflow_data.get("name", "<unnamed>")
    is_active = bool(workflow_data.get("active", False))
    nodes = workflow_data.get("nodes", [])
    connections = workflow_data.get("connections", {})

    result = WorkflowResult(
        workflow_id=wf_id,
        workflow_name=wf_name,
        active=is_active,
    )

    kwargs = {
        "nodes": nodes,
        "connections": connections,
        "workflow_name": wf_name,
        "is_active": is_active,
        "existing_workflow_ids": existing_workflow_ids,
    }

    for check_fn in ALL_CHECKS:
        result.issues.extend(check_fn(**kwargs))

    return result


def fetch_full_workflows(
    client: N8nClient,
    workflow_ids: Optional[List[str]] = None,
    active_only: bool = False,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """
    Fetch full workflow JSON for the requested set.

    If workflow_ids is provided, fetches those specific workflows.
    Otherwise lists all (or active-only) and fetches each one.
    """
    if workflow_ids:
        results: List[Dict[str, Any]] = []
        for wf_id in workflow_ids:
            try:
                results.append(client.get_workflow(wf_id))
            except Exception as exc:
                print(f"  WARNING: Could not fetch workflow {wf_id}: {exc}")
        return results

    # List workflows to get IDs, then fetch full details
    summaries = client.list_workflows(active_only=active_only, use_cache=use_cache)
    full_workflows: List[Dict[str, Any]] = []
    total = len(summaries)
    for idx, summary in enumerate(summaries, 1):
        wf_id = str(summary.get("id", ""))
        if not wf_id:
            continue
        try:
            full_wf = client.get_workflow(wf_id)
            full_workflows.append(full_wf)
        except Exception as exc:
            print(f"  WARNING: Could not fetch workflow {wf_id}: {exc}")
        if idx % 10 == 0 or idx == total:
            print(f"  Fetched {idx}/{total} workflows...")
    return full_workflows


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(results: List[WorkflowResult]) -> None:
    """Print human-readable verification report to stdout."""
    pass_count = sum(1 for r in results if r.status == "PASS")
    warn_count = sum(1 for r in results if r.status == "WARN")
    fail_count = sum(1 for r in results if r.status == "FAIL")

    print("")
    print("=== Post-Deploy Verification ===")
    print(f"Checked {len(results)} workflows...")
    print("")

    for result in sorted(results, key=lambda r: (r.status != "FAIL", r.status != "WARN", r.workflow_name)):
        tag = result.status
        issue_count = len(result.issues)
        line = f"  [{tag}] {result.workflow_name} ({issue_count} issue{'s' if issue_count != 1 else ''})"
        if tag == "WARN" and issue_count == 1:
            line += f": {result.issues[0].message}"
        print(line)
        if tag == "FAIL":
            for issue in result.issues:
                print(f"    - Check {issue.check}: {issue.message}")
        elif tag == "WARN" and issue_count > 1:
            for issue in result.issues:
                print(f"    - Check {issue.check}: {issue.message}")

    print("")
    print(f"SUMMARY: {pass_count} PASS, {warn_count} WARN, {fail_count} FAIL")


def save_json_report(results: List[WorkflowResult], output_path: Path) -> None:
    """Save machine-readable JSON report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_workflows": len(results),
        "pass": sum(1 for r in results if r.status == "PASS"),
        "warn": sum(1 for r in results if r.status == "WARN"),
        "fail": sum(1 for r in results if r.status == "FAIL"),
        "results": [r.to_dict() for r in results],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=True)
    print(f"\nJSON report saved to: {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post-deployment verification for n8n workflows.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Check all active workflows",
    )
    group.add_argument(
        "--id",
        dest="workflow_ids",
        nargs="+",
        help="Check specific workflow ID(s)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        default=False,
        help="Output JSON only (no human-readable report)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Skip workflow list cache",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        default=False,
        help="Also check inactive workflows (only with --all)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load configuration
    try:
        config = load_config()
    except Exception as exc:
        print(f"ERROR: Failed to load config: {exc}")
        sys.exit(1)

    api_key = config["api_keys"]["n8n"]
    if not api_key:
        print("ERROR: N8N_API_KEY not found in environment variables.")
        print("Please add it to your .env file.")
        sys.exit(1)

    base_url = config["n8n"]["base_url"]
    timeout = config["n8n"].get("timeout_seconds", 30)
    max_retries = config["n8n"].get("max_retries", 3)
    cache_dir = config["paths"]["cache_dir"]
    tmp_dir = config["paths"]["tmp_dir"]

    with N8nClient(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        max_retries=max_retries,
        cache_dir=cache_dir,
    ) as client:
        # Determine which workflows to check
        active_only = args.all and not args.include_inactive
        use_cache = not args.no_cache

        if not args.json_only:
            print("=== Post-Deploy Verification ===")
            scope = "active" if active_only else "all"
            if args.workflow_ids:
                print(f"Fetching {len(args.workflow_ids)} workflow(s)...")
            else:
                print(f"Fetching {scope} workflows...")

        # Fetch full workflow data
        workflows = fetch_full_workflows(
            client,
            workflow_ids=args.workflow_ids,
            active_only=active_only,
            use_cache=use_cache,
        )

        if not workflows:
            print("No workflows found to verify.")
            sys.exit(0)

        # Build set of all known workflow IDs for Check 7
        all_wf_ids: set = set()
        if args.workflow_ids:
            # When checking specific IDs, we still need the full list
            # to validate Execute Workflow references
            summaries = client.list_workflows(use_cache=use_cache)
            all_wf_ids = {str(s.get("id", "")) for s in summaries}
        else:
            all_wf_ids = {str(w.get("id", "")) for w in workflows}
            # If only checking active, also include inactive IDs for ref checking
            if active_only:
                summaries = client.list_workflows(active_only=False, use_cache=use_cache)
                all_wf_ids = {str(s.get("id", "")) for s in summaries}

        if not args.json_only:
            print(f"Checking {len(workflows)} workflow(s)...")

        # Run verification
        results: List[WorkflowResult] = []
        for wf_data in workflows:
            result = verify_workflow(wf_data, all_wf_ids)
            results.append(result)

        # Output
        today = datetime.now().strftime("%Y-%m-%d")
        json_path = Path(tmp_dir) / f"verify_report_{today}.json"
        save_json_report(results, json_path)

        if not args.json_only:
            print_report(results)

        # Exit code: 1 if any FAIL, 0 otherwise
        has_failures = any(r.status == "FAIL" for r in results)
        sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()

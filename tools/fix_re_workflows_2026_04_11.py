"""Fix RE-14 + RE-17 workflows (2026-04-11).

Problems:
1. RE-14 Create Exception + RE-17 Create Health Exception have stale schema —
   the live Exceptions sheet has 14 columns now, nodes still point at 8/9.
   Failure: "Column names were updated after the node's setup".
2. Both RE-14 Call RE-18 Alert and RE-17 Call RE-18 Health Alert reference
   RE-18 (BHxuBeVNOH0ecuyI) which is unpublished AND has broken config
   (placeholder chat_id, empty trigger params). n8n refuses to publish any
   workflow that references an unpublished sub-workflow. The pragmatic fix
   is to remove those Call nodes and re-wire past them so exceptions still
   land in the sheet — just without a Telegram notification (which wasn't
   working anyway).

Live Exceptions sheet columns (1J3zHyyRnIX2AaGQZZj9vn362XQQm5sqlhOAhNKe0b7I):
    Exception ID, Exception Type, Severity, Entity Type, Entity ID,
    Description, Recommended Action, Status, Resolved By, Resolved At,
    Resolution Notes, Escalated To, Created At, Last Notified
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from n8n_client import N8nClient

load_dotenv()

WF_RE14 = "AZHnQmu1bY9d67xG"
WF_RE17 = "CsNZ0pHR28MMU00I"
WF_RE18 = "BHxuBeVNOH0ecuyI"

EXCEPTIONS_SCHEMA: list[dict[str, Any]] = [
    {"id": col, "type": "string", "display": True, "displayName": col}
    for col in (
        "Exception ID",
        "Exception Type",
        "Severity",
        "Entity Type",
        "Entity ID",
        "Description",
        "Recommended Action",
        "Status",
        "Resolved By",
        "Resolved At",
        "Resolution Notes",
        "Escalated To",
        "Created At",
        "Last Notified",
    )
]


def re14_exception_values() -> dict[str, str]:
    return {
        "Exception ID": "={{ $json.exception_id }}",
        "Exception Type": "={{ $json.exception_type }}",
        "Severity": "={{ $json.severity }}",
        "Entity Type": "={{ $json.entity_type }}",
        "Entity ID": "={{ $json.entity_id }}",
        "Description": "={{ $json.description }}",
        "Recommended Action": "={{ $json.recommended_action || '' }}",
        "Status": "={{ $json.status }}",
        "Resolved By": "",
        "Resolved At": "",
        "Resolution Notes": "",
        "Escalated To": "={{ $json.assigned_agent || '' }}",
        "Created At": "={{ $json.created_at }}",
        "Last Notified": "={{ $json.created_at }}",
    }


def re17_exception_values() -> dict[str, str]:
    return {
        "Exception ID": "=HEALTH-{{ $now.toFormat('yyyyMMddHHmmss') }}",
        "Exception Type": "System Health",
        "Severity": "={{ $json.severity }}",
        "Entity Type": "System",
        "Entity ID": "=n8n-health-{{ $now.toFormat('yyyyMMddHHmm') }}",
        "Description": "={{ $json.message }}",
        "Recommended Action": "Review failed executions in n8n dashboard",
        "Status": "Open",
        "Resolved By": "",
        "Resolved At": "",
        "Resolution Notes": "",
        "Escalated To": "",
        "Created At": "={{ $json.checked_at }}",
        "Last Notified": "={{ $json.checked_at }}",
    }


def patch_exception_node(node: dict[str, Any], values: dict[str, str]) -> None:
    """Rewrite the columns block on a Google Sheets append node."""
    node["parameters"]["columns"] = {
        "mappingMode": "defineBelow",
        "value": values,
        "matchingColumns": [],
        "schema": EXCEPTIONS_SCHEMA,
    }


def remove_node_and_rewire(
    wf: dict[str, Any], node_name: str
) -> None:
    """Delete a node and splice its upstream connections directly to its
    downstream nodes. Assumes single-output, main-branch wiring.
    """
    # Find upstream nodes pointing at this node.
    upstream_edges: list[tuple[str, int]] = []  # (source_name, branch_index)
    downstream: list[dict[str, Any]] = []  # list of {"node": ..., "type": ..., "index": ...}

    for src, connspec in wf["connections"].items():
        for branch_idx, branch in enumerate(connspec.get("main", [])):
            # branch is a list of edges
            keep = []
            for edge in branch:
                if edge.get("node") == node_name:
                    upstream_edges.append((src, branch_idx))
                else:
                    keep.append(edge)
            connspec["main"][branch_idx] = keep

    # Capture downstream (what the node pointed TO).
    node_conn = wf["connections"].pop(node_name, None)
    if node_conn is not None:
        for branch in node_conn.get("main", []):
            downstream.extend(branch)

    # Reattach each upstream edge to the downstream targets.
    for src, branch_idx in upstream_edges:
        wf["connections"][src]["main"][branch_idx].extend(downstream)

    # Remove the node from the nodes array.
    wf["nodes"] = [n for n in wf["nodes"] if n.get("name") != node_name]


def update_workflow(client: N8nClient, wf_id: str, wf: dict[str, Any]) -> None:
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    client.update_workflow(wf_id, payload)


def fix_re14(client: N8nClient) -> None:
    print("RE-14: fetching...")
    wf = client.get_workflow(WF_RE14)
    nodes = {n["name"]: n for n in wf["nodes"]}

    create_exc = nodes.get("Create Exception")
    if create_exc is None:
        raise RuntimeError("RE-14 'Create Exception' node not found")
    patch_exception_node(create_exc, re14_exception_values())
    print("  Patched 'Create Exception' columns (14 fields)")

    if "Call RE-18 Alert" in nodes:
        remove_node_and_rewire(wf, "Call RE-18 Alert")
        print("  Removed 'Call RE-18 Alert' and rewired to Log Escalation")

    update_workflow(client, WF_RE14, wf)
    print("  RE-14 saved")


def fix_re17(client: N8nClient) -> None:
    print("RE-17: fetching...")
    wf = client.get_workflow(WF_RE17)
    nodes = {n["name"]: n for n in wf["nodes"]}

    create_exc = nodes.get("Create Health Exception")
    if create_exc is None:
        raise RuntimeError("RE-17 'Create Health Exception' node not found")
    patch_exception_node(create_exc, re17_exception_values())
    print("  Patched 'Create Health Exception' columns (14 fields)")

    if "Call RE-18 Health Alert" in nodes:
        remove_node_and_rewire(wf, "Call RE-18 Health Alert")
        print("  Removed 'Call RE-18 Health Alert' and rewired to Log Health Check")

    update_workflow(client, WF_RE17, wf)
    print("  RE-17 saved")


def main() -> None:
    client = N8nClient(
        base_url=os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud"),
        api_key=os.getenv("N8N_API_KEY", ""),
    )
    fix_re14(client)
    fix_re17(client)
    print("Done.")


if __name__ == "__main__":
    main()

"""
SOP skeleton generator — create baseline Markdown SOPs from n8n workflow JSON.

Used in Phase B4 of the Full Revision to close the 22-department documentation
gap. Generates a consistent SOP skeleton that lists triggers, node types,
integrations, AI nodes, credentials, and error-handling coverage.

The output is intentionally a skeleton: it states what the workflow IS based on
JSON evidence and flags sections that need human context (business rationale,
escalation contacts, troubleshooting runbook).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


# Node-type prefix → display category
_INTEGRATION_PREFIXES: dict[str, str] = {
    "n8n-nodes-base.airtable": "Airtable",
    "n8n-nodes-base.googleSheets": "Google Sheets",
    "n8n-nodes-base.gmail": "Gmail",
    "n8n-nodes-base.googleDrive": "Google Drive",
    "n8n-nodes-base.googleCalendar": "Google Calendar",
    "n8n-nodes-base.googleSlides": "Google Slides",
    "n8n-nodes-base.googleDocs": "Google Docs",
    "n8n-nodes-base.microsoftOutlook": "Outlook",
    "n8n-nodes-base.microsoftGraphSecurity": "Microsoft Graph",
    "n8n-nodes-base.httpRequest": "HTTP Request",
    "n8n-nodes-base.webhook": "Webhook",
    "n8n-nodes-base.telegram": "Telegram",
    "n8n-nodes-base.slack": "Slack",
    "n8n-nodes-base.quickbooks": "QuickBooks",
    "n8n-nodes-base.supabase": "Supabase",
    "n8n-nodes-base.postgres": "Postgres",
}

_TRIGGER_TYPES: frozenset[str] = frozenset({
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.cron",
    "n8n-nodes-base.emailReadImap",
    "n8n-nodes-base.errorTrigger",
    "n8n-nodes-base.workflowTrigger",
    "n8n-nodes-base.executeWorkflowTrigger",
    "n8n-nodes-base.telegramTrigger",
    "n8n-nodes-base.whatsAppTrigger",
    "n8n-nodes-base.microsoftOutlookTrigger",
    "n8n-nodes-base.gmailTrigger",
    "n8n-nodes-base.slackTrigger",
    "@n8n/n8n-nodes-langchain.chatTrigger",
})

_AI_NODE_TYPES: frozenset[str] = frozenset({
    "@n8n/n8n-nodes-langchain.agent",
    "@n8n/n8n-nodes-langchain.chainLlm",
    "@n8n/n8n-nodes-langchain.lmChatOpenAi",
    "@n8n/n8n-nodes-langchain.lmChatAnthropic",
    "@n8n/n8n-nodes-langchain.openAi",
    "n8n-nodes-base.openAi",
})


@dataclass(frozen=True)
class WorkflowSummary:
    """Extracted high-signal facts about an n8n workflow."""
    name: str
    workflow_id: str
    node_count: int
    triggers: list[str]
    integrations: list[str]
    ai_node_count: int
    credentials: list[str]
    error_handling_nodes: list[str]
    schedule_hint: str
    has_http_request: bool


def summarize(workflow_json: dict[str, Any]) -> WorkflowSummary:
    """Extract summary facts from one workflow JSON object."""
    nodes: list[dict[str, Any]] = workflow_json.get("nodes", []) or []

    triggers: list[str] = []
    schedule_hint: str = ""
    integration_counter: Counter[str] = Counter()
    ai_count: int = 0
    credentials: set[str] = set()
    error_nodes: list[str] = []
    has_http: bool = False

    for node in nodes:
        ntype = node.get("type", "")
        nname = node.get("name", "<unnamed>")

        if ntype in _TRIGGER_TYPES:
            triggers.append(f"{nname} ({ntype.split('.')[-1]})")
            if ntype == "n8n-nodes-base.scheduleTrigger":
                schedule_hint = _describe_schedule(node)

        label = _INTEGRATION_PREFIXES.get(ntype)
        if label:
            integration_counter[label] += 1

        if ntype == "n8n-nodes-base.httpRequest":
            has_http = True

        if ntype in _AI_NODE_TYPES or ntype.startswith("@n8n/n8n-nodes-langchain."):
            ai_count += 1

        params = node.get("parameters", {}) or {}
        if params.get("continueOnFail") or params.get("onError"):
            error_nodes.append(nname)

        creds = node.get("credentials", {}) or {}
        for cred_type, cred_info in creds.items():
            if isinstance(cred_info, dict):
                name = cred_info.get("name") or cred_type
            else:
                name = str(cred_info)
            credentials.add(f"{cred_type}: {name}")

    integrations = [f"{label} ({count})" for label, count in integration_counter.most_common()]

    return WorkflowSummary(
        name=workflow_json.get("name", "<unnamed>"),
        workflow_id=workflow_json.get("id", ""),
        node_count=len(nodes),
        triggers=triggers,
        integrations=integrations,
        ai_node_count=ai_count,
        credentials=sorted(credentials),
        error_handling_nodes=error_nodes,
        schedule_hint=schedule_hint,
        has_http_request=has_http,
    )


def _describe_schedule(trigger_node: dict[str, Any]) -> str:
    """Turn a scheduleTrigger node's rule into a short human string."""
    rule = (trigger_node.get("parameters", {}) or {}).get("rule", {}) or {}
    intervals = rule.get("interval", []) or []
    parts: list[str] = []
    for entry in intervals:
        if not isinstance(entry, dict):
            continue
        field = entry.get("field", "")
        if field == "hours":
            parts.append(f"every {entry.get('hoursInterval', 1)} hour(s)")
        elif field == "minutes":
            parts.append(f"every {entry.get('minutesInterval', 1)} minute(s)")
        elif field == "days":
            parts.append(f"every {entry.get('daysInterval', 1)} day(s)")
        elif field == "weeks":
            days = entry.get("weekday", [])
            parts.append(f"weekly ({days})")
        elif field == "cronExpression":
            parts.append(f"cron: {entry.get('expression', '')}")
    return ", ".join(parts) if parts else "trigger configured"


def render_sop(summary: WorkflowSummary, dept: str) -> str:
    """Render a Markdown SOP skeleton from *summary*."""
    bullet_list = lambda items: "\n".join(f"- {i}" for i in items) if items else "- (none detected)"

    schedule_line = summary.schedule_hint or "on-demand / triggered"

    return f"""# SOP: {summary.name}

> Auto-generated skeleton from workflow JSON. Review and enrich with business context, escalation runbook, and troubleshooting tips. Live active/inactive state is not captured here — check n8n for runtime status.

| Field | Value |
|---|---|
| Department | `{dept}` |
| Workflow ID | `{summary.workflow_id or '<local-only>'}` |
| Node count | {summary.node_count} |
| Schedule | {schedule_line} |
| AI nodes | {summary.ai_node_count} |

## Triggers
{bullet_list(summary.triggers)}

## Integrations
{bullet_list(summary.integrations)}

## Credentials referenced
{bullet_list(summary.credentials)}

## Error handling
{bullet_list(summary.error_handling_nodes)}

## Business context
<!-- TODO: What business outcome does this workflow drive? Who owns it? Why does it exist? -->

## Escalation
<!-- TODO: Where does a failure show up? Telegram channel, Gmail, Airtable table? Who gets paged? -->

## Troubleshooting
<!-- TODO: Common failure modes and their fixes. Populate as incidents occur. -->

## Change log
- Skeleton generated by `revision_sop_generator.py` as part of Full Revision.
"""


def generate_sop_from_file(workflow_path: Path, dept: str) -> str:
    """Read a workflow JSON file and render its SOP skeleton."""
    with workflow_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return render_sop(summarize(data), dept)


def sop_filename(workflow_path: Path) -> str:
    """Derive the conventional SOP filename from a workflow JSON path."""
    return f"SOP_{workflow_path.stem}.md"

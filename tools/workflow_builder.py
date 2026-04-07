"""
Workflow Builder — Generate n8n workflows from structured specifications.

Generates workflow JSON and corresponding deploy scripts using
the existing deploy pattern (build_nodes → build_connections → CLI).

Extracts node templates from existing deploy_*.py scripts to ensure
consistent node construction across the system.

Usage:
    from workflow_builder import WorkflowBuilder, WorkflowSpec
    builder = WorkflowBuilder(config)
    result = builder.build_from_spec(spec)
    # result = {"workflow_json": {...}, "deploy_script": "..."}
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class WorkflowSpec:
    """Structured specification for a new workflow."""
    name: str
    department: str
    description: str
    trigger_type: str               # "schedule", "webhook", "manual", "error_trigger"
    trigger_config: Dict[str, Any] = field(default_factory=dict)
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    connections: List[Dict[str, Any]] = field(default_factory=list)
    credentials_needed: List[str] = field(default_factory=list)
    airtable_tables: Dict[str, str] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    test_data: Optional[Dict[str, Any]] = None
    risk_class: str = "medium"      # "low", "medium", "high", "critical"
    retry_policy: Dict[str, Any] = field(default_factory=lambda: {"maxRetries": 3})


# ── Node templates ──────────────────────────────────────────

def _make_node(
    name: str,
    node_type: str,
    position: List[int],
    parameters: Optional[Dict[str, Any]] = None,
    type_version: int = 1,
    credentials: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a standard n8n node dict."""
    node: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "name": name,
        "type": node_type,
        "typeVersion": type_version,
        "position": position,
        "parameters": parameters or {},
    }
    if credentials:
        node["credentials"] = credentials
    return node


# Common trigger templates
TRIGGER_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "schedule": {
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "0 7 * * 1"}]
            }
        },
    },
    "webhook": {
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "parameters": {
            "path": "default-webhook",
            "httpMethod": "POST",
            "responseMode": "lastNode",
        },
    },
    "manual": {
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "parameters": {},
    },
    "error_trigger": {
        "type": "n8n-nodes-base.errorTrigger",
        "typeVersion": 1,
        "parameters": {},
    },
}


class WorkflowBuilder:
    """Generate workflow JSON and deploy scripts from specifications."""

    # Node spacing for auto-positioning
    X_START = 250
    Y_START = 300
    X_STEP = 300
    Y_STEP = 200

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}

    def build_from_spec(self, spec: WorkflowSpec) -> Dict[str, Any]:
        """Generate workflow JSON from a WorkflowSpec.

        Returns:
            {
                "workflow_json": Dict (n8n workflow),
                "deploy_script": str (Python source code),
                "spec": Dict (original spec as dict),
            }
        """
        nodes: List[Dict[str, Any]] = []
        connections: Dict[str, Any] = {}

        # 1. Build trigger node
        trigger = self._build_trigger(spec)
        nodes.append(trigger)

        # 2. Build user-specified nodes
        prev_name = trigger["name"]
        for i, node_spec in enumerate(spec.nodes):
            pos = [self.X_START + (i + 1) * self.X_STEP, self.Y_START]
            node = _make_node(
                name=node_spec.get("name", f"Node {i+1}"),
                node_type=node_spec.get("type", "n8n-nodes-base.noOp"),
                position=pos,
                parameters=node_spec.get("parameters", {}),
                type_version=node_spec.get("typeVersion", 1),
                credentials=node_spec.get("credentials"),
            )
            nodes.append(node)

            # Auto-connect sequential nodes (linear pipeline)
            if prev_name:
                connections.setdefault(prev_name, {"main": [[]]})
                connections[prev_name]["main"][0].append({
                    "node": node["name"],
                    "type": "main",
                    "index": 0,
                })
            prev_name = node["name"]

        # 3. Override connections if explicitly specified
        for conn in spec.connections:
            from_node = conn.get("from_node", "")
            to_node = conn.get("to_node", "")
            from_output = conn.get("from_output", 0)
            to_input = conn.get("to_input", 0)
            connections.setdefault(from_node, {"main": [[]]})
            # Extend main outputs to the required index
            main = connections[from_node]["main"]
            while len(main) <= from_output:
                main.append([])
            main[from_output].append({
                "node": to_node,
                "type": "main",
                "index": to_input,
            })

        # 4. Assemble workflow JSON
        settings = {
            "executionOrder": "v1",
            **spec.settings,
        }
        workflow_json = {
            "name": spec.name,
            "nodes": nodes,
            "connections": connections,
            "settings": settings,
        }

        # 5. Generate deploy script
        deploy_script = self._generate_deploy_script(spec, workflow_json)

        return {
            "workflow_json": workflow_json,
            "deploy_script": deploy_script,
            "spec": {
                "name": spec.name,
                "department": spec.department,
                "description": spec.description,
                "risk_class": spec.risk_class,
                "generated_at": datetime.now(tz=None).isoformat() + "Z",
            },
        }

    def save_workflow(
        self,
        result: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> Dict[str, str]:
        """Save generated workflow JSON and deploy script to disk."""
        out = Path(output_dir) if output_dir else Path(__file__).parent.parent / "workflows"
        out.mkdir(parents=True, exist_ok=True)

        name_slug = result["spec"]["name"].lower().replace(" ", "_").replace("-", "_")

        wf_path = out / f"{name_slug}.json"
        with open(wf_path, "w", encoding="utf-8") as f:
            json.dump(result["workflow_json"], f, indent=2, ensure_ascii=False)

        script_path = Path(__file__).parent / f"deploy_{name_slug}.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(result["deploy_script"])

        return {
            "workflow_json_path": str(wf_path),
            "deploy_script_path": str(script_path),
        }

    # ── Internal ────────────────────────────────────────────

    def _build_trigger(self, spec: WorkflowSpec) -> Dict[str, Any]:
        """Build the trigger node from spec."""
        template = TRIGGER_TEMPLATES.get(spec.trigger_type, TRIGGER_TEMPLATES["manual"])
        params = {**template.get("parameters", {}), **spec.trigger_config}

        return _make_node(
            name=f"{spec.name} Trigger",
            node_type=template["type"],
            position=[self.X_START, self.Y_START],
            parameters=params,
            type_version=template.get("typeVersion", 1),
        )

    def _generate_deploy_script(
        self, spec: WorkflowSpec, workflow_json: Dict[str, Any]
    ) -> str:
        """Generate a deploy_*.py script following the project pattern."""
        name_slug = spec.name.lower().replace(" ", "_").replace("-", "_")
        # Sanitize for safe embedding in Python source
        safe_name = json.dumps(spec.name)
        safe_dept = json.dumps(spec.department)
        safe_desc = json.dumps(spec.description)
        nodes_repr = json.dumps(workflow_json["nodes"], indent=4, ensure_ascii=False)
        conns_repr = json.dumps(workflow_json["connections"], indent=4, ensure_ascii=False)
        safe_slug = json.dumps(name_slug)

        return f'''"""
Deploy script for {spec.name}.

Auto-generated by AWLM WorkflowBuilder on {datetime.now(tz=None).isoformat()}Z.
Department: {spec.department}
Description: {spec.description}

Usage:
    python tools/deploy_{name_slug}.py build    # Save JSON
    python tools/deploy_{name_slug}.py deploy   # Deploy to n8n
    python tools/deploy_{name_slug}.py activate # Activate
"""

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
from n8n_client import N8nClient


WORKFLOW_NAME = {safe_name}


def build_nodes():
    """Return the node list for this workflow."""
    return {nodes_repr}


def build_connections():
    """Return the connection map for this workflow."""
    return {conns_repr}


def build_workflow():
    """Assemble the complete workflow JSON."""
    return {{
        "name": WORKFLOW_NAME,
        "nodes": build_nodes(),
        "connections": build_connections(),
        "settings": {json.dumps(workflow_json.get("settings", {}))},
    }}


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {{Path(__file__).name}} build|deploy|activate")
        sys.exit(1)

    action = sys.argv[1]
    config = load_config()
    wf = build_workflow()

    if action == "build":
        out_dir = Path(__file__).parent.parent / "workflows" / {safe_dept}
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / ({safe_slug} + ".json")
        with open(out_path, "w") as f:
            json.dump(wf, f, indent=2)
        print(f"Saved to {{out_path}}")

    elif action == "deploy":
        client = N8nClient(
            base_url=config["n8n"]["base_url"],
            api_key=config["api_keys"]["n8n"],
        )
        result = client.create_workflow(wf)
        print(f"Deployed: {{result.get('name')}} (ID: {{result.get('id')}})")
        client.close()

    elif action == "activate":
        wf_id = sys.argv[2] if len(sys.argv) > 2 else input("Workflow ID: ")
        client = N8nClient(
            base_url=config["n8n"]["base_url"],
            api_key=config["api_keys"]["n8n"],
        )
        result = client.activate_workflow(wf_id)
        print(f"Activated: {{result.get('name')}}")
        client.close()

    else:
        print(f"Unknown action: {{action}}")
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

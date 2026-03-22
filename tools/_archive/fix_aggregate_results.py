"""Fix duplicate 'const config' in Aggregate Results node."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

WORKFLOW_ID = "uq4hnH0YHfhYOOzO"


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    with httpx.Client(timeout=60) as client:
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        wf = resp.json()

        for node in wf["nodes"]:
            if node["name"] == "Aggregate Results":
                code = node["parameters"]["jsCode"]

                # The area rotation code has its own 'const config = $('Search Config')...'
                # which conflicts with the one already at the top.
                # Fix: replace the second declaration with a reference to the existing one.

                # Split into lines and find the duplicate
                lines = code.split("\n")
                first_config_found = False
                fixed_lines = []
                for line in lines:
                    if "const config = $('Search Config')" in line:
                        if first_config_found:
                            # Skip the duplicate
                            fixed_lines.append("// config already declared above")
                            continue
                        first_config_found = True
                    fixed_lines.append(line)

                new_code = "\n".join(fixed_lines)
                node["parameters"]["jsCode"] = new_code

                # Count config declarations
                count = new_code.count("const config")
                print(f"Fixed Aggregate Results: {count} 'const config' declaration(s) remaining")
                break

        # Deploy
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/deactivate", headers=headers)
        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate", headers=headers)
        print("Deployed and activated")


if __name__ == "__main__":
    main()

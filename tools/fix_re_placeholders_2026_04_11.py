"""Fix placeholder/auth issues in RE operations workflows (2026-04-11).

1. RE-11 Daily Summary 'Send Daily Summary': chatId REPLACE_AFTER_SETUP -> real.
2. RE-12 Agent Performance 'Send Performance Report': chatId REPLACE_AFTER_SETUP -> real.
3. RE-13 Stale Lead Follow-up 'AI Generate Follow-up': authentication was set to
   "none" despite an httpHeaderAuth credential being attached, producing 401 on
   OpenRouter. Flip to genericCredentialType/httpHeaderAuth so the credential
   actually gets used.

The owner Telegram chat ID is sourced from CLAUDE.md project notes.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from n8n_client import N8nClient

load_dotenv()

WF_RE11 = "RMfnjJLTYJqrbNfx"
WF_RE12 = "m8SCmtv4RTyay036"
WF_RE13 = "QzfuUFjAKhOFfMyb"

# From CLAUDE.md / memory: @AVMCRMBot, chat 6311361442
OWNER_CHAT_ID = "6311361442"


def update_workflow(client: N8nClient, wf_id: str, wf: dict[str, Any]) -> None:
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    client.update_workflow(wf_id, payload)


def fix_telegram_chat(
    client: N8nClient, wf_id: str, node_name: str
) -> None:
    wf = client.get_workflow(wf_id)
    node = next((n for n in wf["nodes"] if n.get("name") == node_name), None)
    if node is None:
        raise RuntimeError(f"{wf_id}: node {node_name!r} not found")
    current = node["parameters"].get("chatId")
    if current != "REPLACE_AFTER_SETUP":
        print(f"  {node_name}: chatId already set ({current!r}), skipping")
        return
    node["parameters"]["chatId"] = OWNER_CHAT_ID
    update_workflow(client, wf_id, wf)
    print(f"  {wf['name']} / {node_name}: chatId -> {OWNER_CHAT_ID}")


def fix_re13_openrouter_auth(client: N8nClient) -> None:
    wf = client.get_workflow(WF_RE13)
    node = next(
        (n for n in wf["nodes"] if n.get("name") == "AI Generate Follow-up"),
        None,
    )
    if node is None:
        raise RuntimeError("RE-13: 'AI Generate Follow-up' node not found")
    params = node["parameters"]
    if params.get("authentication") == "genericCredentialType":
        print("  RE-13 AI Generate Follow-up: auth already fixed, skipping")
        return
    params["authentication"] = "genericCredentialType"
    params["genericAuthType"] = "httpHeaderAuth"
    update_workflow(client, WF_RE13, wf)
    print("  RE-13 / AI Generate Follow-up: authentication -> httpHeaderAuth")


def main() -> None:
    client = N8nClient(
        base_url=os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud"),
        api_key=os.getenv("N8N_API_KEY", ""),
    )
    print("Fixing Telegram placeholders...")
    fix_telegram_chat(client, WF_RE11, "Send Daily Summary")
    fix_telegram_chat(client, WF_RE12, "Send Performance Report")
    print("Fixing RE-13 OpenRouter auth...")
    fix_re13_openrouter_auth(client)
    print("Done.")


if __name__ == "__main__":
    main()

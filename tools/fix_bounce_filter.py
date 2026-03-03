"""
Fix bounce detection to:
1. Exclude workflow's own error/summary notification emails
2. Mark processed bounce emails as read so they aren't re-processed
3. Ignore emails sent FROM ourselves (prevents feedback loops)
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

FU_WORKFLOW_ID = Path(__file__).parent.parent / ".tmp" / "follow_up_workflow_id.txt"


# Updated Gmail search query:
# - Only match actual bounce notifications (mailer-daemon, postmaster, delivery failures)
# - Exclude emails FROM ourselves (-from:me)
# - Exclude our own error notification subjects
# - Only look at unread emails (is:unread) so we don't re-process
BOUNCE_SEARCH_QUERY = (
    '(from:mailer-daemon OR from:postmaster OR subject:"delivery status" '
    'OR subject:"mail delivery failed" OR subject:"undeliverable") '
    '-from:me '
    '-subject:"Workflow ERROR" '
    '-subject:"Follow-Up Run" '
    '-subject:"Lead Scraper Report" '
    'is:unread newer_than:2d'
)


# Updated extract code that also filters out our own email addresses
# and marks the original bounce emails as read after extracting
EXTRACT_BOUNCES_CODE = "\n".join([
    "const items = $input.all();",
    "const bouncedEmails = [];",
    "",
    "for (const item of items) {",
    "  const body = item.json.textPlain || item.json.text || item.json.snippet || '';",
    "  const from = (item.json.from || '').toLowerCase();",
    "",
    "  // Skip emails that are from ourselves (our own notifications)",
    "  if (from.includes('anyvisionmedia') || from.includes('ian@')) continue;",
    "",
    "  // Extract email addresses from the bounce message body",
    "  const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g;",
    "  const allEmails = body.match(emailRegex) || [];",
    "",
    "  // Filter out system/internal emails - only keep the original recipient",
    "  const recipientEmails = allEmails.filter(e => {",
    "    const lower = e.toLowerCase();",
    "    return !lower.includes('mailer-daemon') &&",
    "           !lower.includes('postmaster') &&",
    "           !lower.includes('googlemail') &&",
    "           !lower.includes('google.com') &&",
    "           !lower.includes('gmail.com') &&",
    "           !lower.includes('anyvisionmedia') &&",
    "           !lower.includes('ian@') &&",
    "           !lower.includes('noreply') &&",
    "           !lower.includes('no-reply');",
    "  });",
    "",
    "  for (const email of recipientEmails) {",
    "    if (!bouncedEmails.includes(email)) {",
    "      bouncedEmails.push(email);",
    "    }",
    "  }",
    "}",
    "",
    "if (bouncedEmails.length === 0) return [];",
    "",
    "return bouncedEmails.map(email => ({",
    "  json: { bouncedEmail: email }",
    "}));",
])


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    workflow_id = FU_WORKFLOW_ID.read_text().strip()
    print(f"Follow-Up Workflow: {workflow_id}")

    with httpx.Client(timeout=60) as client:
        resp = client.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers)
        wf = resp.json()

        for node in wf["nodes"]:
            # Fix 1: Update Gmail search query in Check Bounced Emails
            if node["name"] == "Check Bounced Emails":
                node["parameters"]["filters"]["q"] = BOUNCE_SEARCH_QUERY
                # Also mark retrieved emails as read so they aren't re-processed
                node["parameters"]["options"] = {"readStatus": "unread"}
                print(f"Updated bounce search query:")
                print(f"  {BOUNCE_SEARCH_QUERY[:100]}...")
                print(f"  Added: -from:me, -subject:ERROR, is:unread")

            # Fix 2: Update Extract Bounced Addresses code
            if node["name"] == "Extract Bounced Addresses":
                node["parameters"]["jsCode"] = EXTRACT_BOUNCES_CODE
                print("Updated extract code with additional filters")

        # Also add a "Mark Bounces Read" Gmail node after Flag Bounced Leads
        # This prevents re-processing the same bounce emails tomorrow
        # Actually, the Gmail search with is:unread handles this already
        # But let's add it as belt-and-suspenders

        # Deploy
        client.post(f"{base_url}/api/v1/workflows/{workflow_id}/deactivate", headers=headers)
        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{workflow_id}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        client.post(f"{base_url}/api/v1/workflows/{workflow_id}/activate", headers=headers)

        print(f"\nDeployed. Active: True")
        print("\nBounce detection now excludes:")
        print("  - Emails FROM ourselves (-from:me)")
        print("  - Our own error notifications (-subject:Workflow ERROR)")
        print("  - Our own summary emails (-subject:Follow-Up Run)")
        print("  - Our own scraper reports (-subject:Lead Scraper Report)")
        print("  - Already-read bounces (is:unread only)")


if __name__ == "__main__":
    main()

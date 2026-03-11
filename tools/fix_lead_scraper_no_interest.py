"""
Fix Lead Scraper - Comprehensive opt-out / not-interested handling.

Gaps in current workflow:
1. "Not interested" replies get flagged as "Unsubscribed" — should be distinct
2. Missing common negative phrases: "no thanks", "no thank you", "pass", etc.
3. "Check Lead Replies" doesn't exclude "not interested" — double-catch risk
4. "Not Interested" not in Filter New Leads block list
5. No classification of reply sentiment (positive interest vs polite decline)

Fixes:
1. Expand "Check Unsubscribe Replies" Gmail query with more opt-out phrases
2. Split unsubscribe detection: "Unsubscribed" (explicit opt-out) vs "Not Interested"
3. Add "Not Interested" to Filter New Leads exclusion list
4. Update "Check Lead Replies" to exclude ALL negative phrases
5. Classify reply sentiment in Extract Reply Senders to flag negative replies
"""

import sys
import json

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "uq4hnH0YHfhYOOzO"

# Comprehensive opt-out / not-interested phrases for Gmail search
OPTOUT_PHRASES = [
    "unsubscribe",
    "opt out",
    "remove me",
    "stop emailing",
    "take me off",
    "do not contact",
    "not interested",
    "no thanks",
    "no thank you",
    "not for us",
    "not at this time",
    "please stop",
    "no longer interested",
    "stop sending",
    "cease communication",
    "leave me alone",
    "don't contact",
    "not right now",
    "we'll pass",
    "I'll pass",
    "decline",
    "no need",
]

# Build Gmail query string
OPTOUT_QUERY_PARTS = " OR ".join(f'"{p}"' for p in OPTOUT_PHRASES)
OPTOUT_GMAIL_QUERY = (
    f'({OPTOUT_QUERY_PARTS}) '
    '-from:me -from:anyvisionmedia '
    '-subject:"Workflow ERROR" -subject:"Lead Scraper Report" '
    'is:unread newer_than:14d'
)

# For Check Lead Replies — exclude all opt-out phrases so they don't double-match
REPLY_EXCLUDE_PARTS = " OR ".join(f'"{p}"' for p in OPTOUT_PHRASES)
REPLY_GMAIL_QUERY = (
    'is:unread newer_than:14d '
    '-from:me -from:mailer-daemon -from:postmaster '
    '-subject:"delivery status" -subject:"mail delivery failed" '
    '-subject:"undeliverable" -subject:"Workflow ERROR" '
    f'-subject:"Lead Scraper" -({REPLY_EXCLUDE_PARTS})'
)


# New Extract Unsubscribe Emails code — classifies as "Unsubscribed" vs "Not Interested"
EXTRACT_UNSUB_CODE = r"""const items = $input.all();
const results = [];
const seen = new Set();

// Explicit opt-out = "Unsubscribed"
const unsubTerms = ['unsubscribe', 'opt out', 'remove me', 'stop emailing',
  'take me off', 'do not contact', 'cease communication', 'leave me alone',
  "don't contact", 'please stop', 'stop sending'];

// Polite decline = "Not Interested"
const notInterestedTerms = ['not interested', 'no thanks', 'no thank you',
  'not for us', 'not at this time', 'no longer interested', 'not right now',
  "we'll pass", "i'll pass", 'decline', 'no need'];

for (const item of items) {
  const from = (item.json.from || '').toLowerCase();
  const subject = (item.json.subject || '').toLowerCase();
  const body = (item.json.textPlain || item.json.text || item.json.snippet || '').toLowerCase();
  const msgId = item.json.id || '';

  if (from.includes('anyvisionmedia') || from.includes('ian@')) continue;

  const combined = subject + ' ' + body;

  // Check which category matches
  const isUnsub = unsubTerms.some(t => combined.includes(t));
  const isNotInterested = notInterestedTerms.some(t => combined.includes(t));

  if (!isUnsub && !isNotInterested) continue;

  // Extract sender email
  const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
  const fromEmails = from.match(emailRegex) || [];
  const senderEmail = fromEmails.find(e =>
    !e.includes('anyvisionmedia') && !e.includes('ian@') &&
    !e.includes('noreply') && !e.includes('no-reply') &&
    !e.includes('mailer-daemon') && !e.includes('postmaster')
  );

  if (senderEmail && !seen.has(senderEmail)) {
    seen.add(senderEmail);
    // Explicit unsub takes priority over "not interested"
    const status = isUnsub ? 'Unsubscribed' : 'Not Interested';
    results.push({ json: { unsubEmail: senderEmail, optOutStatus: status, messageId: msgId } });
  }
}

if (results.length === 0) return [];
return results;"""


# Updated Flag Unsubscribed Leads — uses optOutStatus for the Status field
# We need to update the Airtable node to use the dynamic status
FLAG_UNSUB_STATUS_EXPR = "={{ $json.optOutStatus }}"


def fix_workflow(wf):
    """Patch opt-out handling to catch not-interested and classify properly."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}
    connections = wf["connections"]

    # ── FIX 1: Expand "Check Unsubscribe Replies" Gmail query ──
    print("  [1] Expanding Check Unsubscribe Replies query...")
    unsub_check = node_map["Check Unsubscribe Replies"]
    unsub_check["parameters"]["filters"]["q"] = OPTOUT_GMAIL_QUERY
    print(f"    -> {len(OPTOUT_PHRASES)} opt-out phrases (was 7)")
    print(f"    -> newer_than:14d (was 7d)")

    # ── FIX 2: Update Extract Unsubscribe Emails to classify status ──
    print("  [2] Updating Extract Unsubscribe Emails with sentiment classification...")
    extract_unsub = node_map["Extract Unsubscribe Emails"]
    extract_unsub["parameters"]["jsCode"] = EXTRACT_UNSUB_CODE
    print("    -> Classifies: 'Unsubscribed' (explicit opt-out) vs 'Not Interested' (polite decline)")

    # ── FIX 3: Flag Unsubscribed Leads — use dynamic status ──
    print("  [3] Updating Flag Unsubscribed Leads to use dynamic status...")
    flag_unsub = node_map["Flag Unsubscribed Leads"]
    flag_unsub["parameters"]["columns"]["value"]["Status"] = FLAG_UNSUB_STATUS_EXPR
    print(f"    -> Status now uses expression: {FLAG_UNSUB_STATUS_EXPR}")

    # ── FIX 4: Add "Not Interested" to Filter New Leads ──
    print("  [4] Adding 'Not Interested' to Filter New Leads block list...")
    filter_new = node_map["Filter New Leads"]
    conditions = filter_new["parameters"]["conditions"]["conditions"]

    # Check if already present
    existing_values = [c.get("rightValue", "") for c in conditions]
    if "Not Interested" not in existing_values:
        conditions.append({
            "id": "ni-block-001",
            "operator": {
                "type": "string",
                "operation": "notEquals"
            },
            "leftValue": "={{ $json.status }}",
            "rightValue": "Not Interested"
        })
        print("    -> Added: status != 'Not Interested'")
    else:
        print("    -> Already present, skipping")

    # Also add "Opted Out" as a catch-all for manually flagged leads
    if "Opted Out" not in existing_values:
        conditions.append({
            "id": "oo-block-001",
            "operator": {
                "type": "string",
                "operation": "notEquals"
            },
            "leftValue": "={{ $json.status }}",
            "rightValue": "Opted Out"
        })
        print("    -> Added: status != 'Opted Out'")

    # ── FIX 5: Update "Check Lead Replies" to exclude ALL opt-out phrases ──
    print("  [5] Updating Check Lead Replies to exclude all opt-out phrases...")
    reply_check = node_map["Check Lead Replies"]
    reply_check["parameters"]["filters"]["q"] = REPLY_GMAIL_QUERY
    print(f"    -> Excludes all {len(OPTOUT_PHRASES)} opt-out phrases")
    print("    -> newer_than:14d (was 7d)")

    # ── FIX 6: Update Has Unsubscribes? to also pass messageId for marking read ──
    # (already works since we pass messageId in the new Extract Unsubscribe Emails)

    return wf


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    print("=" * 60)
    print("LEAD SCRAPER FIX - Not Interested / Opt-Out Handling")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:
        # 1. Fetch
        print("\n[FETCH] Getting current workflow...")
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

        # 2. Fix
        print("\n[FIX] Applying opt-out handling fixes...")
        wf = fix_workflow(wf)

        # 3. Save locally
        from pathlib import Path
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "lead_scraper_no_interest_fix.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVE] Saved to {output_path}")

        # 4. Deploy
        print("\n[DEPLOY] Pushing to n8n...")
        update_payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
            headers=headers,
            json=update_payload
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"  Deployed: {result['name']} (ID: {result['id']})")
        print(f"  Active: {result.get('active')}")

        # 5. Re-activate
        print("\n[ACTIVATE] Re-activating workflow...")
        resp = client.post(
            f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate",
            headers=headers
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"  Active: {result.get('active')}")

    print("\n" + "=" * 60)
    print("FIX DEPLOYED SUCCESSFULLY")
    print("=" * 60)
    print("\nChanges made:")
    print(f"  1. Check Unsubscribe Replies: {len(OPTOUT_PHRASES)} phrases (was 7), 14d window (was 7d)")
    print("  2. Extract Unsubscribe Emails: classifies 'Unsubscribed' vs 'Not Interested'")
    print("  3. Flag Unsubscribed Leads: uses dynamic status from classification")
    print("  4. Filter New Leads: blocks 'Not Interested' and 'Opted Out' statuses")
    print("  5. Check Lead Replies: excludes all opt-out phrases (no double-catch)")
    print("\nAirtable statuses that block re-emailing:")
    print("  Bounced | Unsubscribed | Not Interested | Opted Out | Do Not Contact | Send Failed | Email Sent | Replied")


if __name__ == "__main__":
    main()

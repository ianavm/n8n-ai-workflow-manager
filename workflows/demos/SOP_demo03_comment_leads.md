# DEMO-03 — Comment Lead Miner

Social comments → AI intent scoring → Slack alert + CRM for the hot ones.

## Business use case

Every post you put out generates comments like "how much?", "link?",
"DM me", "need this". Today those die in the comment section. This
workflow polls comments, scores each for buying intent (0-100), tiers
them high/medium/low, routes high-intent to Slack with a drafted reply,
and writes everything to Airtable. Sales team opens Slack → sees the
5 hottest leads of the hour with a ready-to-paste reply.

## Demo scenario (3 minutes)

1. Tell the prospect: "You posted about your product yesterday and you got
   47 comments. How many of those are actual leads? I don't know either
   — let's find out."
2. Fire the webhook (or screenshare Airtable and trigger manually).
   `Demo Mode = 1` loads 12 realistic comments inline — no live API needed.
3. ~10 seconds later show Airtable `DEMO_Comment_Leads` filtered by
   `Tier = high` → prospect sees 4 hot leads pop up with intent scores,
   categories, and AI-drafted replies.
4. Open Slack in a second tab → four alert cards appear with the hottest
   comment, the username, and a ready-to-send reply.
5. Show the "low" tier — filters out the spammer and the random fan. Prove
   that it's not just keyword matching.

Key stat to sell: **in a typical 50-comment post, 20-30% are qualified
leads that today get lost.**

## Node-by-node

| # | Node | Purpose |
|---|------|---------|
| 1a | Webhook Trigger | On-demand demo firing |
| 1b | Every 5 Minutes | Production polling |
| 2 | Demo Config | Normalises input, stamps runId, embeds fixtures |
| 3 | DEMO_MODE Switch | Route demo vs live |
| 4a | Load Fixture Comments | 12 seeded realistic comments (code) |
| 4b | Apify Comment Scrape | Live IG comment scrape via Apify actor |
| 4b' | Normalise Apify | Flatten Apify response into canonical shape |
| 5 | Merge Comments | Join both paths |
| 6 | Build Classification Prompt | Assemble batch prompt with brand context |
| 7 | AI Classify Intent | OpenRouter → Claude Haiku 4.5 (fast, cheap) |
| 8 | Merge & Fan Out | JSON.parse + heuristic fallback per comment |
| 9 | Log Lead to Airtable | Write row per comment with score + reply |
| 10 | Tier Router | Switch on `tier` (high / medium / low) |
| 11 | Slack Alert — High Intent | POST to SLACK_WEBHOOK_URL |
| 12-13 | Pass-through + Merge Tiers | Rejoin paths for summary |
| 14 | Summarise Run | Aggregate stats: counts per tier + top leads |
| 15 | Respond | Return JSON |

## Inputs

Webhook POST body (all optional — all default):
```json
{
  "demoMode": "1",
  "postUrl": "https://instagram.com/p/DEMO",
  "platform": "instagram"
}
```

## Outputs

```json
{
  "runId": "CL-20260420-142135",
  "total": 12,
  "breakdown": { "high": 4, "medium": 5, "low": 3 },
  "highIntentLeads": [
    {
      "username": "@startup_wayne",
      "score": 88,
      "text": "Can we jump on a demo call this week? Running 12 person team...",
      "category": "demo-request",
      "suggestedReply": "Wayne, happy to — sent you a DM with a Friday slot."
    }
  ],
  "status": "complete"
}
```

## Required creds / env

- `N8N_API_KEY`, `N8N_BASE_URL`
- `AIRTABLE_API_TOKEN` + `MARKETING_AIRTABLE_BASE_ID`
- `DEMO_TABLE_COMMENT_LEADS` — created by `tools/setup_demo_airtable.py`
- OpenRouter credential (wired)
- `SLACK_WEBHOOK_URL` — optional; workflow completes without it (alert
  node posts to `/DISABLED` and fails soft)
- `APIFY_API_TOKEN` — only for live mode

Demo mode requires only: n8n + OpenRouter + Airtable. Nothing else.

## Data schema — `DEMO_Comment_Leads` (Airtable)

| Field | Type | Notes |
|-------|------|-------|
| Comment ID | singleLineText | dedupe key |
| Run ID | singleLineText | `CL-YYYYMMDD-HHMMSS` |
| Platform | singleSelect | instagram / tiktok / linkedin / facebook |
| Post URL | url | |
| Username | singleLineText | `@handle` |
| Comment Text | multilineText | raw comment |
| Intent Score | number | 0-100 |
| Category | singleSelect | pricing / demo-request / objection / endorsement / support / spam / generic |
| Tier | singleSelect | high / medium / low |
| Reasoning | multilineText | 1-sentence AI explainer |
| Suggested Reply | multilineText | AI-drafted (high+medium only) |
| Likes | number | |
| Source | singleSelect | fixture / apify / webhook |
| Commented At | dateTime | from platform |
| Created At | dateTime | log timestamp |

## Error handling

- AI call fails → fallback heuristic regex keyword match classifies comments
  so the run still produces triaged leads.
- Slack webhook missing → points at `/DISABLED` and `onError: continueRegularOutput`
- Airtable log mismatch → `onError: continueRegularOutput`
- Apify errors in live mode → Normalise returns `_empty:true` placeholder;
  run still completes with 0 leads.

## Cost

Per 50-comment run:
- Claude Haiku classification — ~$0.002
- Airtable — free
- Apify IG comment actor — ~$0.04 per 50 comments (live mode)

So the **live mode costs < 10c per poll**. At 288 polls/day (every 5min),
that's about $11/day if running continuously — sell it as a flat R800/mo
per client.

Demo mode = $0.

## Security / compliance

- POPIA: comment text is public by nature; usernames are public handles.
  We don't persist anything that isn't already on the live platform.
- Store Slack webhook in `.env`, never hardcoded.
- IG scraping: Apify handles TOS, but in production prefer IG Graph API
  once the prospect has business verification.

## Demo polish notes

- Pre-create Slack channel `#demo-leads` with a fresh webhook URL so it's
  clean for every prospect.
- In Airtable, use a Kanban view grouped by Tier. Hot leads pop up in the
  first column like a notification feed.
- If the prospect asks about reply quality, read one of the AI drafts out
  loud — they never expect it to be that natural.

## Productise to SaaS

- Per-client Airtable or Postgres with per-brand prompt template.
- Auto-reply option (from R5k/mo tier) — posts the suggested reply
  automatically instead of drafting it.
- CRM integrations: HubSpot, Pipedrive, Zoho push. Deliver as a Zap-like
  selector in a small dashboard.
- Monthly "lead harvest" report: "Last month I found you 347 qualified
  leads you never replied to. 22 are now customers. Here's what you
  missed."

## Run it

```
python tools/setup_demo_airtable.py        # creates DEMO_Comment_Leads
# Add DEMO_TABLE_COMMENT_LEADS=tblXXX to .env
python tools/deploy_demo_comment_leads.py deploy
python tools/deploy_demo_comment_leads.py activate
```

Test it:
```
curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/demo03-comment-leads \
  -H 'Content-Type: application/json' \
  -d '{"demoMode":"1"}'
```

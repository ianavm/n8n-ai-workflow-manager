# DEMO-04 — Hook Lab

One idea → 5 hook variations per platform → AI picks the winner.

## Business use case

Kill "what should my caption be?" forever. Marketers waste 30-60 min per post
writing hooks from scratch. Hook Lab produces 5 high-quality variations per
platform in one click, logs them, simulates engagement (or measures real
engagement if wired to Blotato), and writes the winning hook back with an
AI-generated rationale. Winners become reusable templates.

## Demo scenario (3 minutes)

1. Open the form URL (or the webhook if pitching via API).
2. Paste one idea, e.g. "We just launched a 5-tool AI stack for SA SMEs under
   R2k/mo". Pick platforms (IG, LinkedIn, TikTok, Twitter). Leave Demo Mode
   on `1`.
3. Submit. In ~15 seconds the workflow returns JSON showing:
   - 20 hook variations (5 × 4 platforms), each tagged with an emotional
     angle (curiosity / contrarian / FOMO / social-proof / transformation).
   - The winning hook + a 2-sentence rationale from Claude explaining why
     it will outperform.
   - Top 3 variations as the "safe bets".
4. Pop open Airtable → `DEMO_Hook_Experiments` → show the prospect every
   variation is logged, the winner is flagged, and the experiment ID ties
   back to the form submission.

## Node-by-node

| # | Node | Purpose |
|---|------|---------|
| 1a | Form Trigger | Public URL for demos — one form, five fields |
| 1b | Webhook Trigger | Programmatic path for API pitches |
| 2 | Demo Config | Normalises input + stamps experimentId + brand voice |
| 3 | Build Variation Prompt | Templated Claude prompt per platform |
| 4 | AI Generate Variations | OpenRouter → Claude Sonnet 4 → JSON of 5×N variations |
| 5 | Parse & Fan Out | JSON.parse + fallback + fan-out (1 item per variation) |
| 6 | Log Variation to Airtable | Write each variation as a row |
| 7 | DEMO_MODE Switch | Route `1` → simulate, `0` → live |
| 8a | Simulate Engagement | Deterministic synthetic scores per (hook × platform × angle) |
| 8b | Live Path Placeholder | Production hook for Blotato + 24h wait + metrics fetch |
| 9 | Merge Paths | Fan paths back in |
| 10 | Aggregate Results | Sort by score, pick winner |
| 11 | AI Explain Winner | Claude Haiku → 2-sentence rationale |
| 12 | Finalize Payload | Shape final response |
| 13 | Log Winner to Airtable | Write winner row with Is_Winner=true |
| 14 | Respond | Return JSON to form / webhook caller |

## Inputs

```json
{
  "Core Idea": "We just launched a 5-tool AI stack for SA SMEs under R2k/mo",
  "Platforms": "instagram,linkedin,tiktok,twitter",
  "Target Audience": "SA SME owners, 30-55, hands-on",
  "Demo Mode": "1"
}
```

## Outputs

```json
{
  "experimentId": "HL-20260420-141203",
  "idea": "We just launched a 5-tool AI stack for SA SMEs under R2k/mo",
  "winner": {
    "platform": "linkedin",
    "angle": "contrarian",
    "hook": "Most SA SMEs think AI costs R50k/mo. Ours runs on R2k.",
    "cta": "Comment STACK and I'll DM the list.",
    "score24h": 0.91,
    "impressions": 8420,
    "engagementRate": 10.9
  },
  "winnerRationale": "The contrarian frame triggers pattern-break in a feed of...",
  "topThree": [ /* ... */ ],
  "totalVariations": 20,
  "status": "complete"
}
```

## Required creds / env

- `N8N_API_KEY`, `N8N_BASE_URL` — n8n Cloud
- `AIRTABLE_API_TOKEN` + `MARKETING_AIRTABLE_BASE_ID`
- `DEMO_TABLE_HOOK_EXPERIMENTS` — created by `tools/setup_demo_airtable.py`
- n8n credential `OpenRouter 2WC` (id `9ZgHenDBrFuyboov`) already wired
- n8n credential `Airtable account` (id `ZyBrcAO6fps7YB3u`) already wired

Live mode (optional): Blotato account + Slack webhook. Not required for
demo mode.

## Data schema — `DEMO_Hook_Experiments` (Airtable)

| Field | Type | Notes |
|-------|------|-------|
| Experiment ID | singleLineText | `HL-YYYYMMDD-HHMMSS` or `*-WINNER` |
| Variation Idx | number | 0 for winner row, 1..N for individual variations |
| Platform | singleSelect | instagram / linkedin / tiktok / twitter / facebook / youtube |
| Angle | singleSelect | curiosity / contrarian / fomo / social-proof / transformation |
| Hook | multilineText | The generated hook |
| CTA | singleLineText | Call to action |
| Idea | multilineText | Original prompt |
| Is Winner | checkbox | True on winner rows only |
| Winner Rationale | multilineText | AI-generated explainer (winner rows) |
| Score 24h | number | Synthetic (demo) or real engagement score |
| Impressions | number | Synthetic (demo) or real |
| Engagement Rate | number | Synthetic (demo) or real % |
| Created At | dateTime | ISO |

## Error handling

- AI call fails → `Parse & Fan Out` uses deterministic fallback variations
  so the demo still completes.
- Airtable logging uses `onError: continueRegularOutput` so a table-schema
  mismatch never blocks the response.
- AI Explain Winner also degrades gracefully to a static rationale.

## Cost

Per run (20 variations + rationale):
- Claude Sonnet 4 — ~2.2k output tokens — ~$0.033
- Claude Haiku 4.5 — ~400 tokens — ~$0.0008
- n8n execution — free on self-hosted / $0.01-ish on Cloud

Roughly **$0.035 per run**. Viable at scale.

## Security / compliance

- No PII handled — only content ideas and hooks.
- POPIA: N/A unless prospects use it for audience-specific content with real
  customer data.
- Never log API keys — prompts go out over HTTPS via n8n creds only.

## Demo polish notes

- Pre-seed one killer example in the form default text so it looks clean
  on first load.
- Keep Airtable view open in a second tab set to `Grid — Sorted by
  Created At desc, Is Winner first` — prospects see the winner row pop to
  the top in real time.
- If the prospect is non-technical, skip the JSON response and screenshare
  Airtable only.

## Productise to SaaS

- Multi-tenant by adding a `tenantId` field and an Airtable or Postgres
  lookup per tenant.
- Tier on volume: Free = 10 experiments/mo, Pro = unlimited + real
  engagement via Blotato, Agency = white-label + client workspaces.
- Monthly recurring training: feed winners back into the prompt as
  few-shot examples per tenant so each account's brand voice improves
  over time.

## Run it

```
# 1. Create the Airtable table (first time only):
python tools/setup_demo_airtable.py

# 2. Add the table ID it prints to .env:
#    DEMO_TABLE_HOOK_EXPERIMENTS=tblXXXXXXXXXXXXXX

# 3. Build + deploy:
python tools/deploy_demo_hook_lab.py deploy

# 4. Activate when ready for prospect demos:
python tools/deploy_demo_hook_lab.py activate
```

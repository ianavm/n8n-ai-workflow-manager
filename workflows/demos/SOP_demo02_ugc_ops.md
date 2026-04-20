# DEMO-02 — UGC Ops Autopilot

"I need 10 UGC videos" → creators found + scored + briefed + contacted,
all logged, in under a minute.

## Business use case

UGC is a $7.1B market growing to $64B by 2034 (Archive.com). 87% of
brands use UGC, only 16% have systematic ops — most still hunt creators
manually on Instagram DMs. This workflow collapses discovery → scoring →
personalised brief drafting → outreach → CRM into one n8n flow.
Ecommerce, CPG, and performance agencies all buy this.

## Demo scenario (3 minutes)

1. Open the form. Fill in:
   - Brand: VitalityCo
   - Product: Morning Stack Supplement
   - Brief: "Locally-sourced daily stack, no caffeine, no crash"
   - Niche: "wellness, supplements, SA moms"
   - Deliverables: "1 × 30s TikTok + 1 × IG reel"
   - Budget per creator: R1200
   - Quantity: 5
   - Demo Mode: 1
2. Submit. In ~45 seconds the workflow:
   - Creates a campaign record in Airtable
   - "Finds" 10 creators (fixtures in demo, Apify TikTok scrape in live)
   - Scores each for fit and drafts a personalised outreach DM
   - Filters qualified creators (fitScore ≥ 7)
   - Simulates sending outreach (or sends via Gmail in live mode)
   - Logs everything: campaign + qualified creators + outreach messages
3. Flip to Airtable, open `DEMO_UGC_Campaigns` → one row shows the
   campaign. `DEMO_UGC_Creators` filtered by CampaignID shows qualified
   creators with fit scores. `DEMO_UGC_Outreach` shows the exact
   personalised message drafted per creator.
4. Read one out loud — the prospect sees the AI referenced the creator's
   actual sample post by content. That's the "holy shit" moment.

## Node-by-node

| # | Node | Purpose |
|---|------|---------|
| 1a | Form Trigger | Prospect-facing campaign launcher |
| 1b | Webhook Trigger | Programmatic pitch path |
| 2 | Demo Config | Stamp campaignId, load fixtures, normalise |
| 3 | Create Campaign Record | Airtable row (status = Sourcing) |
| 4 | DEMO_MODE Switch | Route fixture vs Apify |
| 5a | Load Fixture Creators | 10 hand-crafted creators (incl. 2 mismatches) |
| 5b | Apify TikTok Scrape | `clockworks/tiktok-scraper` hashtag search |
| 5b' | Normalise Apify Creators | Canonicalise into creator shape |
| 6 | Merge Creators | Fan paths back in |
| 7 | Build Scoring Prompt | Per-creator templated Claude prompt |
| 8 | AI Score + Brief | Claude Sonnet returns fitScore + subject + body |
| 9 | Parse Score | JSON.parse + heuristic niche-overlap fallback |
| 10 | Filter Qualified | Drop creators below fitScore 7 |
| 11 | Log Creator | Airtable row per qualified creator |
| 12 | Send Mode Switch | demo=simulate, live=Gmail |
| 13a | Simulate Send | Stamp status=simulated_sent |
| 13b | Send Gmail Outreach | Real email via Gmail OAuth |
| 14 | Merge Send Paths | Fan paths back in |
| 15 | Log Outreach | `DEMO_UGC_Outreach` row per message |
| 16 | Aggregate Campaign | Roll up for response |
| 17 | Respond | Return JSON |

## Inputs

```json
{
  "Brand": "VitalityCo",
  "Product Name": "Morning Stack Supplement",
  "Product Brief": "Locally-sourced daily stack for busy professionals — no caffeine, no crash.",
  "Niche Keywords": "wellness, supplements, SA moms",
  "Deliverables": "1 × 30s TikTok + 1 × IG reel",
  "Budget Per Creator (ZAR)": 1200,
  "Quantity": 5,
  "Demo Mode": "1"
}
```

## Outputs

```json
{
  "campaignId": "UGC-20260420-145030",
  "brand": "VitalityCo",
  "productName": "Morning Stack Supplement",
  "quantityRequested": 5,
  "creatorsReached": 7,
  "creators": [
    {
      "handle": "@busy_mom_van",
      "platform": "tiktok",
      "fitScore": 9,
      "outreachStatus": "simulated_sent",
      "subject": "Quick collab on your 2pm-crash story — R1200 TikTok"
    }
  ],
  "status": "outreach_complete"
}
```

## Required creds / env

Demo mode:
- `N8N_API_KEY`, `N8N_BASE_URL`
- `AIRTABLE_API_TOKEN` + `MARKETING_AIRTABLE_BASE_ID`
- `DEMO_TABLE_UGC_CAMPAIGNS`, `DEMO_TABLE_UGC_CREATORS`, `DEMO_TABLE_UGC_OUTREACH`
- OpenRouter credential (wired)

Live mode (additional):
- `APIFY_API_TOKEN` — TikTok creator scraping (~$0.05 per 20 results)
- Gmail OAuth credential (wired as `Gmail AVM Tutorial`)
- Consider IG Graph API for cross-platform creator search once
  business verification is live

## Data schemas

### `DEMO_UGC_Campaigns`
Campaign ID · Brand · Product Name · Product Brief · Niche · Deliverables
· Budget Per Creator · Quantity · Status · Created At

### `DEMO_UGC_Creators`
Campaign ID · Handle · Platform · Followers · Avg Views · Engagement Rate
· Niche · Sample Post · Email · Rate Card · Fit Score · Fit Reasoning
· Outreach Subject · Outreach Body · Status · Source · Created At

### `DEMO_UGC_Outreach`
Campaign ID · Handle · Email · Subject · Body · Status · Message ID
· Sent At

## Error handling

- AI scoring fails → heuristic niche-overlap fallback so each creator
  still gets a score and a generic outreach draft.
- Apify failure in live mode → normaliser produces `_empty:true` item
  that the Filter node drops.
- Gmail send failure → `onError: continueRegularOutput` so the outreach
  log still captures the attempt.

## Cost per campaign

Demo mode: < $0.05 (10 AI score calls).

Live mode for 20 creators:
- Apify TikTok scrape — $0.10
- 20 × Claude Sonnet score+brief — ~$0.50
- Gmail — free
- **~$0.60 per campaign** for qualified creators.

Sell at R3500 per campaign to ecommerce brands.

## Security / compliance

- POPIA: creator emails are usually publicly listed in IG/TikTok bios.
  Store only what's public. Offer creators an opt-out per outreach (add
  `unsubscribe_link` variable to the prompt for full compliance).
- Gmail sending rate limits: keep sends to ≤ 50/day per Google account
  on free tier, or use Workspace.
- Don't store creator addresses or phone numbers — email is enough.

## Demo polish notes

- Pre-create a Kanban Airtable view on `DEMO_UGC_Creators` grouped by
  `Status` — it feels like a Trello board for UGC.
- Show 2 of the 10 fixture creators have wrong niches (crypto guy, car
  guy). Prove the filter works by pointing out they're not in the
  qualified list.
- If the prospect asks "how accurate is Apify?", show the
  `Normalise Apify Creators` node — it canonicalises into the same
  shape as fixtures, so fit-scoring is platform-agnostic.

## Productise to SaaS

- Per-tenant creator CRM with their own rate-card field.
- Campaign templates: Supplements / Beauty / B2B SaaS / DTC Apparel,
  each with niche taxonomy + prompt baked in.
- Upsell: auto-followups on non-response (3-touch sequence).
- Upsell: deliverable tracking tab — creators upload to a Drive folder
  via a unique link, triggers payment via PayFast on approval.

## Run it

```
python tools/setup_demo_airtable.py        # creates the 3 UGC tables
# Add these to .env:
#   DEMO_TABLE_UGC_CAMPAIGNS=tblXXX
#   DEMO_TABLE_UGC_CREATORS=tblXXX
#   DEMO_TABLE_UGC_OUTREACH=tblXXX
python tools/deploy_demo_ugc_ops.py deploy
python tools/deploy_demo_ugc_ops.py activate
```

Test it:
```
curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/demo02-ugc-ops \
  -H 'Content-Type: application/json' \
  -d '{"demoMode":"1","brand":"VitalityCo","productName":"Morning Stack","niche":"wellness, SA moms","deliverables":"1×TikTok","budgetPerCreator":1200,"quantity":5}'
```

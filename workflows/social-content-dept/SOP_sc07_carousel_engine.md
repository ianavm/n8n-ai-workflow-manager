# SOP — SC-07 Carousel Engine

Sheet-driven Blotato carousel posting. Replaces the manual-edit SC-06 pattern.

## What it does

Every 5 minutes, SC-07 scans the **`AVM Carousel Engine`** Google Sheet for rows where:

- `Status = Approved`
- `Posted At` is empty
- `Scheduled At` is within the next 10 minutes (or already passed)
- `Retry Count < 3`

It picks the earliest eligible row, locks it (`Status = Posting`), uploads the slide images to Blotato, and schedules the carousel on Instagram, LinkedIn, and Facebook. Results are logged per platform, the row is updated (`Status = Posted` or `Failed`), and a summary email is sent to `ian@anyvisionmedia.com`.

Key files:

- Deploy: [tools/deploy_sc07_carousel_engine.py](../../tools/deploy_sc07_carousel_engine.py)
- Sheet bootstrap: [tools/setup_carousel_gsheet.py](../../tools/setup_carousel_gsheet.py)
- Image generator (per-carousel): e.g. [tools/generate_ai_pain_points_carousel.py](../../tools/generate_ai_pain_points_carousel.py)
- Supabase uploader (reused): [tools/upload_to_supabase_storage.py](../../tools/upload_to_supabase_storage.py)
- Blotato admin / cancellation: [tools/deploy_blotato_admin.py](../../tools/deploy_blotato_admin.py) (workflow `60WDevpigvaNgavo`)

## One-time setup

```bash
# 1. Create the Google Sheet (idempotent; safe to re-run)
python tools/setup_carousel_gsheet.py

# 2. Paste the printed CAROUSEL_GSHEET_ID= line into .env

# 3. Deploy the workflow
python tools/deploy_sc07_carousel_engine.py activate
```

Prerequisites:

- `GOOGLE_APPLICATION_CREDENTIALS` points at a service-account JSON with Sheets + Drive scopes.
- `N8N_API_KEY` set in `.env`.
- Blotato credential (`N8N_CRED_BLOTATO` or the default `hhRiqZrWNlqvmYZR`) connected in n8n.
- Google Sheets credential (`OkpDXxwI8WcUJp4P`) connected in n8n.
- Gmail credential (`2IuycrTIgWJZEjBE`) connected in n8n for the notify step.

## How to ship a new carousel (3 steps)

1. **Generate images.** Write a one-off script modelled on [tools/generate_ai_pain_points_carousel.py](../../tools/generate_ai_pain_points_carousel.py) — copy it, rename the `CAROUSEL_ID` constant, swap the `SLIDES` list, and run with `--render` to produce PNGs.

2. **Upload to Supabase.** The existing uploader produces public URLs:

   ```bash
   python tools/upload_to_supabase_storage.py \
     --bucket avm-public \
     --prefix carousels/<carousel-id> \
     .tmp/carousels/<carousel-id>/*.png
   ```

   Copy the printed URLs (one per line).

3. **Fill a row in the `Carousels` tab.** Paste the URLs (comma or newline separated) into `Image URLs`. Fill in captions, hashtags, and `Scheduled At` (ISO 8601 UTC, e.g. `2026-04-22T07:00:00Z`). Leave `Status = Draft` while you review. When ready, flip `Status` to `Approved` and set `Approved By` to your name.

Within 5 minutes the workflow picks up the row and posts. Watch `Status` cycle `Approved → Posting → Posted`.

## Sheet schema

### `Carousels` tab

| Column | Required | Notes |
|---|---|---|
| `Carousel ID` | yes | unique, lowercase-kebab, e.g. `ai-pain-points-2026-04-21` |
| `Title` | yes | human-friendly label |
| `Status` | yes | dropdown: `Draft` / `Approved` / `Posting` / `Posted` / `Failed` / `Paused` |
| `Scheduled At` | yes | ISO 8601 UTC. Example: `2026-04-22T07:00:00Z` |
| `Image URLs` | yes | comma or newline separated public image URLs |
| `IG Caption` | yes | LinkedIn caption if reused |
| `LI Caption` | yes | — |
| `FB Caption` | yes | can reuse IG copy if unsure |
| `Hashtags IG` | optional | space or comma separated, with or without `#`. **Capped at 5** per Blotato / IG |
| `Hashtags LI` | optional | no cap |
| `Approved By` | yes | your name — set when flipping Status |
| `Approved At` | auto | written by workflow on first read of `Approved` |
| `Posted At` | auto | written when all 3 platforms succeed |
| `Blotato Schedule IDs` | auto | JSON `{instagram, linkedin, facebook}` — use for cancellation |
| `Last Error` | auto | cleared on success; populated on failure |
| `Retry Count` | auto | 0, capped at 3. Row is skipped once it hits 3 |

### `Post Log` tab (append-only history)

One row per platform per carousel. Use this for per-platform analytics (IG vs LI success rate, typical failure modes, etc).

## Running ad-hoc

- **Manual trigger (n8n UI):** open SC-07 and click "Execute Workflow". It will process whatever the filter finds — same rules apply.
- **Webhook:** `POST https://ianimmelman89.app.n8n.cloud/webhook/sc07-carousel-trigger` with an empty body.

## Cancelling a scheduled carousel

Once a row has a `Blotato Schedule IDs` JSON, you can cancel via the Blotato Admin Proxy:

```bash
curl -X POST https://ianimmelman89.app.n8n.cloud/webhook/blotato-admin-proxy \
  -H "Content-Type: application/json" \
  -d '{"method": "DELETE", "path": "/schedules/<id>"}'
```

Do this once per platform using the IDs stored in the sheet. Then update the row: `Status = Paused`, clear `Posted At`.

## Failure modes & troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Row stays `Posting`, never moves | Upload to Blotato step timed out | Check the last n8n execution. If the HTTP POST to `/v2/posts` succeeded for any platform, check the Blotato dashboard before re-flipping Status — you may have half-posted and a retry would duplicate. |
| `Status = Failed`, `Retry Count = 3` | Three consecutive failures | Read `Last Error`. Common: bad image URL (404 from Supabase), caption exceeded platform limit, Blotato account disconnected. Fix + reset: clear `Retry Count`, flip `Status` back to `Approved`. |
| IG succeeded but LI failed | Per-platform issue | Successful platform is already scheduled. Don't retry the whole row — fix manually. Re-flipping `Approved` will attempt all 3 again and duplicate the successful one. Instead: cancel successful platform via Admin Proxy, then re-approve. |
| No rows being picked up | Schedule trigger not firing OR filter logic rejecting | Check the workflow is `active`. Inspect the `Read Carousels Sheet` -> `Filter Eligible Rows` node output in the last execution. Verify `Scheduled At` is valid ISO 8601 UTC. |
| "`blotato-api-key` not set" | Blotato credential not configured in n8n | Re-link the `Blotato AVM` credential (id `hhRiqZrWNlqvmYZR`) on each HTTP Request + Blotato media node. |
| IG post rejected with "too many hashtags" | Hashtag cap not applied | Caption node caps IG at 5 tags. If you embedded hashtags directly in `IG Caption` (not in `Hashtags IG`), they bypass the cap. Move them into `Hashtags IG`. |

## Scaling beyond v1 (roadmap, not live)

- **Caption autodraft**: Claude sub-workflow reads a `Content Ideas` tab, writes `Draft` rows into `Carousels`.
- **Image autogen**: extend the per-carousel generator into a template tool that reads one row and produces 8 PNGs without code edits.
- **Analytics**: weekly Blotato `GET /posts/{id}/stats` -> `Analytics` tab.
- **Slack approval button**: `Status = Draft` notification with Approve / Reject buttons via Slack Interactive webhook.

## Gotchas baked into the workflow (don't regress)

- HTTP Request node to `/v2/posts` has **no retries** — Blotato creates duplicate schedules on retry. Per-row `Retry Count` handles this safely.
- Code nodes use `runOnceForAllItems` — never `executeOnce: true` (drops items after the first).
- FB `target.pageId` is mandatory. Hardcoded to `972448295960293` (Any Vision Media).
- IG hashtag cap of 5 is enforced in the `Carousel Config` code node by slicing `Hashtags IG` list.
- All Google Sheets nodes use `mappingMode: defineBelow` with explicit `schema: []`. `autoMapInputData` breaks updates (see `feedback-n8n-node-issues.md` in memory).
- `ScheduledAt` stored in UTC. Blotato accepts ISO 8601 UTC only.

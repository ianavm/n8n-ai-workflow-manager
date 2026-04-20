# DEMO-01 — Video Clip Factory

Long-form video in → 5 short-form clips with captions & hooks out.

## Business use case

Creators, podcasters, agencies, course sellers, and B2B founders all
produce long-form content (podcasts, webinars, sales calls, YouTube
uploads) and all struggle to cut it down into 30+ short-form posts per
week. Manual editing = 2-3 hours per clip. Opus Clip, Vizard, and
Submagic have proven 70-91% time savings with AI-driven selection +
caption burn.

This workflow productises that for clients: drop a URL, get 5 ready-to-
publish clips per platform with AI-generated captions, logged to
Airtable and optionally pushed to Blotato.

## Demo scenario (3 minutes)

1. Open the form. Paste the fixture URL (or any YouTube/Drive link).
   Leave Demo Mode = 1.
2. Submit. In ~10 seconds the response shows 5 clips with:
   - Hook line (burned into the video)
   - Start/end seconds on the source
   - Retention score (why the AI picked it)
   - Pre-rendered clip URL (demo) or live Remotion render (live mode)
   - Four platform-specific captions (TikTok / IG / YouTube / LinkedIn)
3. Flip to Airtable `DEMO_Video_Clips` — prospect sees 5 rows, one per
   clip, ready to schedule.
4. Hit play on one of the fixture clip URLs to show the caption-burn style.
5. Close with: "Production mode replaces the fixtures with real
   AssemblyAI transcription + our Remotion render server — same flow,
   same outputs, 15 minutes per 60-min source."

## Node-by-node

| # | Node | Purpose |
|---|------|---------|
| 1a | Form Trigger | Prospect-friendly URL to submit a video |
| 1b | Webhook Trigger | Programmatic path |
| 2 | Demo Config | Normalises input, stamps videoId, loads fixtures |
| 3 | DEMO_MODE Switch | Route demo vs live |
| 4a | Load Fixture Segments | 5 hand-crafted segments with pre-rendered clip URLs |
| 4b | Submit Transcription | AssemblyAI /transcript (live) |
| 4b' | Poll Transcription | Fetch completed transcript |
| 4b'' | AI Segment Picker | Claude Sonnet picks 5 best 20-40s windows |
| 4b''' | Remotion Render (Live) | `ClipWithBurnedCaptions` composition |
| 5 | Merge Paths | Re-join demo and live paths |
| 6 | Build Platform Copy Prompt | Per-clip templated prompt |
| 7 | AI Platform Copy | Claude Haiku → TikTok/IG/YT/LI captions |
| 8 | Parse Copy | JSON.parse with deterministic fallback |
| 9 | Log Clip to Airtable | 1 row per clip |
| 10 | Aggregate Clips | Roll up for response payload |
| 11 | Respond | JSON back to form/webhook caller |

## Inputs

```json
{
  "Video URL": "https://example.com/demos/avm-podcast-ep12.mp4",
  "Title": "AI for SMEs — 5 Tools That Run Our Agency (Ep. 12)",
  "Demo Mode": "1"
}
```

## Outputs

```json
{
  "videoId": "VID-20260420-143012",
  "title": "AI for SMEs — 5 Tools That Run Our Agency (Ep. 12)",
  "sourceUrl": "https://example.com/demos/avm-podcast-ep12.mp4",
  "clipsProduced": 5,
  "clips": [
    {
      "segmentIdx": 1,
      "hook": "Most SMEs think AI costs R50k a month. Ours runs on R2k.",
      "clipUrl": "https://social-render.up.railway.app/demo-clips/avm-ep12-clip1.mp4",
      "durationSec": 36,
      "retentionScore": 94,
      "copy": {
        "tiktok":    { "caption": "The R2k AI stack that runs our agency 🧠", "hashtags": ["#ai","#sme","#startups"] },
        "instagram": { "caption": "...", "hashtags": ["...","...","..."] },
        "youtube":   { "caption": "..." },
        "linkedin":  { "caption": "..." }
      }
    }
  ],
  "status": "complete"
}
```

## Required creds / env

Demo mode (minimum):
- `N8N_API_KEY`, `N8N_BASE_URL`
- `AIRTABLE_API_TOKEN` + `MARKETING_AIRTABLE_BASE_ID`
- `DEMO_TABLE_VIDEO_CLIPS`
- OpenRouter credential (wired)

Live mode (full):
- `ASSEMBLYAI_API_KEY` — transcription ($0.65/hr of audio)
- `REMOTION_RENDER_URL` — already at `https://social-render.up.railway.app`
- Remotion server must expose a `ClipWithBurnedCaptions` composition
- Optional: Blotato creds (for auto-schedule) + Slack webhook

## Data schema — `DEMO_Video_Clips` (Airtable)

| Field | Type |
|-------|------|
| Video ID | singleLineText |
| Title | singleLineText |
| Source URL | url |
| Segment Idx | number |
| Start Sec | number |
| End Sec | number |
| Duration Sec | number |
| Hook | multilineText |
| Summary | multilineText |
| Retention Score | number |
| Clip URL | url |
| Caption TikTok | multilineText |
| Caption Instagram | multilineText |
| Caption YouTube | multilineText |
| Caption LinkedIn | multilineText |
| Source | singleSelect (fixture / live) |
| Created At | dateTime |

## Error handling

- Transcription failure → Live path produces empty segments → Merge Paths
  still fires, just with no data on the live branch.
- AI Platform Copy failure → `Parse Copy` uses deterministic fallback
  copy based on clip hook/summary.
- Airtable `onError: continueRegularOutput` on all writes.

## Cost per run

Demo mode: < $0.01 (just AI copy generation).

Live mode for a 60-minute source:
- AssemblyAI transcription — $0.65
- Claude Sonnet segment pick — $0.02
- Remotion render × 5 clips — ~$0.25 (Railway compute)
- Claude Haiku copy × 5 — $0.01
- **Total: ~$0.93 per 60-min source**

Sell at R800/mo for 10 sources ≈ R80 per source = ~R30 profit per source
at current FX, scales well.

## Security / compliance

- POPIA: if the source contains personal data (sales calls), store only
  the clip URLs + captions, not the full transcript.
- AssemblyAI retains transcripts for 14 days by default — set
  `keep_for` param to 0 for privacy-sensitive prospects.
- Never log raw API keys. Pass via n8n credentials only.

## Demo polish notes

- Pre-host the 5 fixture clip URLs on your Remotion server before the
  first prospect demo. If they 404, the demo dies.
- Pin the sample video in the form description so prospects don't need
  to have their own on hand.
- Keep Airtable view set to Gallery layout — the clip thumbnails make
  it feel like a real content library.

## Productise to SaaS

- Tier by volume: Free = 2 sources/mo, Pro R1k/mo = 20, Agency R5k/mo = 100.
- White-label the Remotion server per agency so their brand colors
  appear on every clip out of the box.
- Add a "Style" dropdown (TikTok native / Podcast captions / News ticker)
  that swaps Remotion compositions.
- Auto-scheduling upsell via Blotato (add R500/mo).

## Run it

```
python tools/setup_demo_airtable.py        # creates DEMO_Video_Clips
# Add DEMO_TABLE_VIDEO_CLIPS=tblXXX to .env
python tools/deploy_demo_video_clips.py deploy
python tools/deploy_demo_video_clips.py activate
```

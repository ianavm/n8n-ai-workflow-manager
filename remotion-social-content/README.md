# AVM Social Content — Remotion Render Server

Programmatic video renderer for the Social Content Trend Replication Pipeline.
Called by SC-04 (n8n workflow) to render AVM-branded videos from adapted scripts.

## Compositions

All 9:16 (1080x1920), 30fps, MP4 output:

- **TextOnScreen** — kinetic typography, numbered points, brand CTA card
- **QuoteCard** — single quote with typewriter effect
- **StatGraphic** — animated number counters + bar charts
- **TalkingHeadOverlay** — lower thirds + bullet overlays (for manual recordings)

## Local development

```bash
# Install
npm install

# Studio (visual editor)
npm run studio

# Run server locally
npm run server

# Test render (server must be running)
curl -X POST http://localhost:3000/render \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev-key" \
  -d '{
    "compositionId": "TextOnScreen",
    "props": {
      "title": "Stop wasting hours on marketing",
      "script": ["Point 1", "Point 2", "Point 3"],
      "cta": "Follow for more",
      "brandColor": "#FF6D5A",
      "brandName": "AnyVision Media"
    },
    "outputFormat": "mp4"
  }'
```

## Deployment

### Option A: Railway (recommended — simplest)

1. Install Railway CLI: `npm i -g @railway/cli`
2. `cd remotion-social-content && railway login && railway init`
3. Set env vars in Railway dashboard:
   - `SUPABASE_URL` — your Supabase project URL
   - `SUPABASE_SERVICE_ROLE_KEY` — service role key (not anon!)
   - `SUPABASE_BUCKET` — `social-content` (create it first, public)
   - `RENDER_API_KEY` — generate a random string for n8n auth
4. `railway up` — builds Dockerfile, deploys
5. Copy the generated URL (e.g., `https://avm-render-production.up.railway.app`)
6. Set `REMOTION_RENDER_URL` in `.env` and redeploy SC-04

### Option B: Render.com

1. Push repo to GitHub (this directory)
2. Create new Web Service on Render.com, point to repo
3. Uses `render.yaml` config automatically
4. Set env vars in Render dashboard (same as Railway)

### Option C: Fly.io

```bash
flyctl launch --dockerfile Dockerfile
flyctl secrets set SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... RENDER_API_KEY=...
flyctl deploy
```

## Supabase Storage setup

1. Go to Supabase dashboard → Storage
2. Create bucket `social-content` as **public**
3. Create folders: `videos/` and `thumbnails/`
4. Copy Service Role Key from Project Settings → API

## API Reference

### POST /render

Render a new video. Returns immediately with job ID.

```json
Request:
{
  "compositionId": "TextOnScreen",
  "props": { ... },
  "outputFormat": "mp4"
}

Response:
{
  "jobId": "uuid",
  "status": "queued"
}
```

### GET /render/:jobId

Check render status.

```json
Response when complete:
{
  "status": "complete",
  "videoUrl": "https://...supabase.co/storage/v1/object/public/social-content/videos/uuid.mp4",
  "thumbnailUrl": "https://..."
}

Response when still rendering:
{
  "status": "rendering"
}

Response on error:
{
  "status": "error",
  "error": "error message"
}
```

### GET /health

Health check.

## Memory requirements

Remotion rendering needs ~2GB RAM minimum. Railway Hobby plan (512MB) may OOM
for long/complex videos. Use Railway Pro ($5/mo) or Render Starter ($7/mo).

## Cost estimate

- 5-10 videos/day × 30-60 seconds each
- Railway Pro: $5/mo flat
- Supabase Storage: ~$0.021/GB/mo (5 videos/day × 10MB = 1.5GB/mo = $0.03)
- **Total: ~$5/mo**

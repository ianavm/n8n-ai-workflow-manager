/**
 * AnyVision Media — Remotion Render Server
 *
 * Express server that renders Remotion videos on demand and uploads to Supabase Storage.
 * Designed to be called from n8n workflow SC-04 (Social Content Video Production).
 *
 * Endpoints:
 *   POST /render   -> accepts {compositionId, props, outputFormat} -> returns {jobId, status}
 *   GET  /render/:jobId -> returns {status, videoUrl, thumbnailUrl}
 *   GET  /health   -> returns {status: "ok"}
 *
 * Deployment: Railway, Render.com, Fly.io, or any Node.js host with 2GB+ RAM.
 *
 * Env vars required:
 *   PORT                      - server port (default 3000)
 *   SUPABASE_URL              - e.g. https://xyz.supabase.co
 *   SUPABASE_SERVICE_ROLE_KEY - for uploading to public bucket
 *   SUPABASE_BUCKET           - public bucket name (default "social-content")
 *   RENDER_API_KEY            - shared secret to auth n8n requests
 */

import "dotenv/config";
import express from "express";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { createClient } from "@supabase/supabase-js";
import { randomUUID } from "crypto";
import path from "path";
import { fileURLToPath } from "url";
import fs from "fs/promises";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = process.env.PORT || 3000;
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const SUPABASE_BUCKET = process.env.SUPABASE_BUCKET || "social-content";
const RENDER_API_KEY = process.env.RENDER_API_KEY || "dev-key";

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required");
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
const app = express();
app.use(express.json({ limit: "10mb" }));

// In-memory job store (reset on restart). For production, use Redis.
const jobs = new Map();

// Bundle the Remotion project asynchronously (takes 20-40s)
// Server must start listening immediately for Railway healthchecks
let bundleLocation = null;
let bundleError = null;
function initBundle() {
  console.log("Bundling Remotion project (async)...");
  const entryPoint = path.resolve(__dirname, "src/index.ts");
  bundle({
    entryPoint,
    webpackOverride: (config) => config,
  })
    .then((loc) => {
      bundleLocation = loc;
      console.log(`Bundle ready: ${bundleLocation}`);
    })
    .catch((err) => {
      bundleError = err.message;
      console.error("Bundle failed:", err);
    });
}

// Auth middleware
function requireAuth(req, res, next) {
  const key = req.headers["x-api-key"];
  if (key !== RENDER_API_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
}

app.get("/health", (req, res) => {
  // Return ok even if bundle isn't ready yet — Railway healthcheck passes
  // bundleReady flag tells clients if /render will actually work
  res.json({
    status: "ok",
    bundleReady: bundleLocation !== null,
    bundleError: bundleError,
  });
});

/**
 * POST /render
 * Body: {compositionId: "TextOnScreen", props: {...}, outputFormat: "mp4"}
 * Returns: {jobId, status: "queued"}
 */
app.post("/render", requireAuth, async (req, res) => {
  const { compositionId, props = {}, outputFormat = "mp4" } = req.body;

  if (!compositionId) {
    return res.status(400).json({ error: "compositionId required" });
  }

  if (!bundleLocation) {
    return res.status(503).json({ error: "Bundle not ready" });
  }

  const jobId = randomUUID();
  jobs.set(jobId, { status: "queued", startedAt: Date.now() });

  res.json({ jobId, status: "queued" });

  // Fire and forget — render asynchronously
  renderJob(jobId, compositionId, props, outputFormat).catch((err) => {
    console.error(`Job ${jobId} failed:`, err);
    jobs.set(jobId, { status: "error", error: err.message });
  });
});

/**
 * GET /render/:jobId
 * Returns: {status, videoUrl?, thumbnailUrl?, error?}
 */
app.get("/render/:jobId", requireAuth, (req, res) => {
  const job = jobs.get(req.params.jobId);
  if (!job) {
    return res.status(404).json({ error: "Job not found" });
  }
  res.json(job);
});

async function renderJob(jobId, compositionId, props, outputFormat) {
  jobs.set(jobId, { status: "rendering" });

  // Select the composition
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: compositionId,
    inputProps: props,
  });

  // Render video
  const videoPath = path.join("/tmp", `${jobId}.${outputFormat}`);
  const codec = outputFormat === "webm" ? "vp8" : "h264";

  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec,
    outputLocation: videoPath,
    inputProps: props,
  });

  // Render still (frame 0) as thumbnail
  const thumbPath = path.join("/tmp", `${jobId}-thumb.png`);
  await renderStill({
    composition,
    serveUrl: bundleLocation,
    output: thumbPath,
    inputProps: props,
    frame: 0,
  });

  // Upload both to Supabase
  const videoBuffer = await fs.readFile(videoPath);
  const thumbBuffer = await fs.readFile(thumbPath);

  const videoKey = `videos/${jobId}.${outputFormat}`;
  const thumbKey = `thumbnails/${jobId}.png`;

  const [videoUpload, thumbUpload] = await Promise.all([
    supabase.storage.from(SUPABASE_BUCKET).upload(videoKey, videoBuffer, {
      contentType: outputFormat === "webm" ? "video/webm" : "video/mp4",
      upsert: true,
    }),
    supabase.storage.from(SUPABASE_BUCKET).upload(thumbKey, thumbBuffer, {
      contentType: "image/png",
      upsert: true,
    }),
  ]);

  if (videoUpload.error) throw new Error(`Video upload: ${videoUpload.error.message}`);
  if (thumbUpload.error) throw new Error(`Thumbnail upload: ${thumbUpload.error.message}`);

  const videoUrl = supabase.storage.from(SUPABASE_BUCKET).getPublicUrl(videoKey).data.publicUrl;
  const thumbnailUrl = supabase.storage.from(SUPABASE_BUCKET).getPublicUrl(thumbKey).data.publicUrl;

  // Cleanup temp files
  await Promise.all([
    fs.unlink(videoPath).catch(() => {}),
    fs.unlink(thumbPath).catch(() => {}),
  ]);

  jobs.set(jobId, {
    status: "complete",
    videoUrl,
    thumbnailUrl,
    completedAt: Date.now(),
  });

  console.log(`Job ${jobId} complete: ${videoUrl}`);
}

// Start listening IMMEDIATELY (Railway healthcheck needs this)
app.listen(PORT, "0.0.0.0", () => {
  console.log(`Remotion render server listening on :${PORT}`);
  // Kick off bundle in background — /health returns 200 even while bundling
  initBundle();
});

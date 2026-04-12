---
name: rendering-guide
description: Remotion rendering options — CLI flags, Node.js API, output formats
---

# Rendering Guide

## CLI Rendering

### Video
```bash
npx remotion render <composition-id> --output <path>

# Common flags
--codec h264|h265|vp8|vp9|prores|gif
--crf 18                    # Quality (lower = better, 0-51 for h264)
--width 1920 --height 1080
--fps 30
--props '{"key": "value"}'  # Pass input props as JSON
--concurrency 50%           # Use 50% of CPU cores
--every-nth-frame 2         # Skip frames (faster draft)
--frames 0-89               # Render specific frame range
--muted                     # No audio
--audio-codec aac|mp3|opus
--audio-bitrate 320k
```

### Still Image
```bash
npx remotion still <composition-id> --output <path>

--frame 0                   # Which frame to capture (default: 0)
--image-format png|jpeg|webp
--quality 80                # JPEG/WebP quality (0-100)
```

### Preview
```bash
npx remotion studio         # Interactive preview at localhost:3000
npx remotion studio --port 3001  # Custom port
```

## Node.js API

```typescript
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition, getCompositions } from "@remotion/renderer";

// Bundle project
const bundleLocation = await bundle({ entryPoint: "./src/index.ts" });

// List compositions
const compositions = await getCompositions(bundleLocation);

// Select specific composition
const composition = await selectComposition({
  serveUrl: bundleLocation,
  id: "MyVideo",
  inputProps: { title: "Hello" },
});

// Render video
await renderMedia({
  composition,
  serveUrl: bundleLocation,
  codec: "h264",
  outputLocation: "./out/video.mp4",
  inputProps: { title: "Hello" },
  onProgress: ({ progress }) => console.log(`${Math.round(progress * 100)}%`),
});

// Render still
await renderStill({
  composition,
  serveUrl: bundleLocation,
  output: "./out/thumbnail.png",
  frame: 0,
  imageFormat: "png",
});
```

## Output Format Reference

| Format | Codec | Extension | Best For |
|--------|-------|-----------|----------|
| MP4 (H.264) | `h264` | .mp4 | Universal playback, social media |
| MP4 (H.265) | `h265` | .mp4 | Smaller files, modern devices |
| WebM (VP8) | `vp8` | .webm | Web, transparency support |
| WebM (VP9) | `vp9` | .webm | Better quality web video |
| ProRes | `prores` | .mov | Professional editing |
| GIF | `gif` | .gif | Short loops, email |
| PNG Sequence | via `renderStill` loop | .png | Frame-by-frame compositing |

## Quality Settings (CRF)

| CRF | Quality | File Size | Use Case |
|-----|---------|-----------|----------|
| 0 | Lossless | Very large | Archival |
| 15-18 | Excellent | Large | Final delivery |
| 23 | Good (default) | Medium | General use |
| 28-35 | Acceptable | Small | Draft, web preview |

## Cloud Rendering

### AWS Lambda (`@remotion/lambda`)
- Distributed rendering across multiple Lambda functions
- Best for: high-volume rendering, parallel jobs
- Requires AWS account setup

### GCP Cloud Run (`@remotion/cloudrun`)
- Single-machine rendering on Cloud Run
- Best for: moderate volume, simpler setup

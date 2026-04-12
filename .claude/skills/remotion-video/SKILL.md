---
name: remotion-video
description: "Programmatic video creation with Remotion (React). Create videos from code, render MP4/WebM/GIF, compose animations, overlay text/graphics. Use when user says: create video, render video, video from code, animation, remotion, motion graphics, video composition, programmatic video, social media video, product demo video."
argument-hint: "[create|render|still|preview] <description or composition-id>"
metadata:
  version: "1.0.0"
  reference-repo: "Github Access/remotion-main"
---

# Remotion Video — Programmatic Video Creation

## What is Remotion

Remotion is a React framework for creating videos programmatically. Each frame is a React component. Your video is code — version-controlled, testable, automatable.

**Reference repo:** `Github Access/remotion-main/` (80+ packages, full source + docs)
**Docs:** `Github Access/remotion-main/packages/docs/docs/`

## When to Use

- Social media video content (reels, shorts, posts)
- Product demo / walkthrough videos
- Motion graphics intros/outros
- Data visualization animations
- Personalized video at scale
- Compositing AI-generated content (HeyGen avatars, Banana images) into video

## Quick Start — Scaffold a New Project

```bash
npx create-video@latest      # Interactive setup
# OR
npx create-video@latest --template blank   # Minimal
```

This creates a project with:
- `src/Root.tsx` — Register compositions
- `src/Composition.tsx` — Your video components
- `remotion.config.ts` — Build config

## Core Concepts

### Composition = React Component + Video Metadata

```tsx
import { Composition } from "remotion";
import { MyVideo } from "./MyVideo";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="MyVideo"
    component={MyVideo}
    durationInFrames={150}    // 5 seconds at 30fps
    fps={30}
    width={1920}
    height={1080}
  />
);
```

### Frame-Based Animation

```tsx
import { useCurrentFrame, useVideoConfig, interpolate, spring, AbsoluteFill } from "remotion";

export const MyVideo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: "clamp" });
  const scale = spring({ frame, fps, config: { damping: 200 } });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ opacity, transform: `scale(${scale})`, fontSize: 80 }}>
        Hello World
      </div>
    </AbsoluteFill>
  );
};
```

### Key Primitives

| Component/Hook | Purpose |
|----------------|---------|
| `AbsoluteFill` | Full-frame container (position absolute, covers entire canvas) |
| `Sequence` | Time-offset a section: `<Sequence from={30}>...</Sequence>` |
| `useCurrentFrame()` | Returns current frame number (starts at 0) |
| `useVideoConfig()` | Returns `{ fps, durationInFrames, width, height }` |
| `interpolate()` | Map frame ranges to value ranges (opacity, position, etc.) |
| `spring()` | Physics-based animation (damping, stiffness, mass) |
| `OffthreadVideo` | **ALWAYS use instead of `Video`** — frame-accurate via FFmpeg |
| `Audio` | Add audio tracks with volume control |
| `Img` | Load images (supports `staticFile()` for local assets) |
| `staticFile()` | Reference files in `public/` directory |

### CRITICAL RULES

1. **ALWAYS use `OffthreadVideo`, NEVER `Video`** — `Video` uses browser decoder (causes jitter)
2. **First frame is 0**, last frame is `durationInFrames - 1`
3. **`staticFile()`** references files from `public/` directory
4. **Multiple compositions** in Root.tsx: wrap in `<>...</>` fragment
5. **`calculateMetadata`** for dynamic duration (e.g., from video length)

## CLI Commands

```bash
# Development — interactive preview
npx remotion studio

# Render video
npx remotion render <composition-id> --output out/video.mp4
npx remotion render MyVideo --codec h264 --output out/video.mp4

# Render still image (single frame)
npx remotion still <composition-id> --output out/frame.png
npx remotion still MyVideo --frame 30 --output out/frame.png

# List available compositions
npx remotion compositions

# Render with options
npx remotion render MyVideo \
  --output out/video.mp4 \
  --codec h264 \
  --width 1920 --height 1080 \
  --fps 30 \
  --crf 18 \
  --props '{"title": "Hello"}'
```

### Output Formats

| Codec | Flag | Use Case |
|-------|------|----------|
| H.264 | `--codec h264` | Default, best compatibility (MP4) |
| H.265 | `--codec h265` | Smaller files, newer devices |
| VP8 | `--codec vp8` | WebM, web playback |
| VP9 | `--codec vp9` | WebM, better quality |
| ProRes | `--codec prores` | Professional editing |
| GIF | `--codec gif` | Animated GIF |

## Node.js Rendering API

For programmatic rendering (scripts, automation, n8n integration):

```typescript
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

async function renderVideo(compositionId: string, outputPath: string, props: Record<string, unknown> = {}) {
  // 1. Bundle the project
  const bundleLocation = await bundle({ entryPoint: "./src/index.ts" });

  // 2. Select composition
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: compositionId,
    inputProps: props,
  });

  // 3. Render
  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outputPath,
    inputProps: props,
  });
}
```

## Integration with Other Skills

### Banana (AI Images) + Remotion

Generate images with `/banana generate`, then use in Remotion:

```tsx
import { Img, staticFile } from "remotion";

// After banana generates to public/hero.png
<Img src={staticFile("hero.png")} style={{ width: "100%", height: "100%" }} />
```

### HeyGen (AI Avatars) + Remotion

See `references/heygen-integration.md` for full guide. Key pattern:

```tsx
import { OffthreadVideo, AbsoluteFill, Sequence } from "remotion";

export const AvatarPresentation: React.FC<{ avatarUrl: string }> = ({ avatarUrl }) => (
  <AbsoluteFill>
    <OffthreadVideo src={avatarUrl} style={{ width: "100%", height: "100%" }} />
    <Sequence from={30}>
      <AnimatedTitle text="Welcome to AnyVision Media" />
    </Sequence>
  </AbsoluteFill>
);
```

### Stitch (UI Designs) + Remotion

Capture Stitch-generated screens as images, use as video frames:

```tsx
<Img src={staticFile("stitch-dashboard.png")} />
```

## Common Patterns

### Social Media Dimensions

```typescript
const PRESETS = {
  instagram_reel:  { width: 1080, height: 1920, fps: 30 },  // 9:16
  youtube:         { width: 1920, height: 1080, fps: 30 },  // 16:9
  tiktok:          { width: 1080, height: 1920, fps: 30 },  // 9:16
  instagram_post:  { width: 1080, height: 1080, fps: 30 },  // 1:1
  twitter_video:   { width: 1280, height: 720,  fps: 30 },  // 16:9
  linkedin:        { width: 1920, height: 1080, fps: 30 },  // 16:9
};
```

### Text Animation

```tsx
const TextReveal: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const chars = text.split("");

  return (
    <div style={{ display: "flex" }}>
      {chars.map((char, i) => {
        const delay = i * 2;
        const opacity = interpolate(frame, [delay, delay + 10], [0, 1], { extrapolateRight: "clamp" });
        return <span key={i} style={{ opacity }}>{char}</span>;
      })}
    </div>
  );
};
```

### Slide Deck

```tsx
const slides = ["Slide 1", "Slide 2", "Slide 3"];
const SLIDE_DURATION = 90; // 3 seconds each

export const SlideDeck: React.FC = () => (
  <AbsoluteFill>
    {slides.map((slide, i) => (
      <Sequence key={i} from={i * SLIDE_DURATION} durationInFrames={SLIDE_DURATION}>
        <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", fontSize: 60 }}>
          {slide}
        </AbsoluteFill>
      </Sequence>
    ))}
  </AbsoluteFill>
);
```

## Dependencies

- **Node.js 18+** (already present)
- **FFmpeg** (auto-installed by Remotion, or `choco install ffmpeg`)
- **Chrome/Chromium** (present on Windows 11)
- No API keys required

## Reference Documentation

Load on-demand from `references/`:
- `composition-patterns.md` — Layout, layering, transitions
- `rendering-guide.md` — CLI flags, Node.js API, cloud rendering
- `animation-reference.md` — spring(), interpolate(), easing functions
- `media-handling.md` — Video, audio, images, fonts
- `template-catalog.md` — Available starter templates
- `heygen-integration.md` — HeyGen avatar + Remotion workflows

## Error Handling

| Error | Fix |
|-------|-----|
| "Cannot find module remotion" | Run `npm install remotion @remotion/cli` |
| "Already running on port 3000" | Kill existing process or use `--port 3001` |
| Video jitter in render | Use `OffthreadVideo` instead of `Video` |
| "No composition found" | Check `id` matches in `Root.tsx` |
| FFmpeg not found | `choco install ffmpeg` or let Remotion auto-install |

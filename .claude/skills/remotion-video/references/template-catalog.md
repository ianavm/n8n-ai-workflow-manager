---
name: template-catalog
description: Available Remotion starter templates for common video types
---

# Remotion Template Catalog

Scaffold with: `npx create-video@latest --template <name>`

## Available Templates

| Template | Use Case | Key Features |
|----------|----------|--------------|
| `blank` | Minimal starting point | Just the essentials |
| `helloworld` | Learning Remotion | Basic animation examples |
| `javascript` | JS (no TypeScript) | For JS-only projects |
| `audiogram` | Audio visualization | Waveform + captions from audio |
| `music-visualization` | Music videos | Frequency bars, visualizer |

## Custom Project Templates (AnyVision Media)

### Social Media Reel (9:16)
```tsx
// Vertical format for TikTok/Reels/Shorts
<Composition
  id="SocialReel"
  component={SocialReel}
  durationInFrames={450}  // 15 seconds
  fps={30}
  width={1080}
  height={1920}
/>
```

### Product Demo (16:9)
```tsx
// Landscape for YouTube/LinkedIn
<Composition
  id="ProductDemo"
  component={ProductDemo}
  durationInFrames={900}  // 30 seconds
  fps={30}
  width={1920}
  height={1080}
/>
```

### Instagram Post (1:1)
```tsx
<Composition
  id="InstaPost"
  component={InstaPost}
  durationInFrames={300}  // 10 seconds
  fps={30}
  width={1080}
  height={1080}
/>
```

### Thumbnail / OG Image (Still)
```tsx
<Composition
  id="Thumbnail"
  component={Thumbnail}
  durationInFrames={1}
  fps={30}
  width={1280}
  height={720}
/>
// Render with: npx remotion still Thumbnail --output thumb.png
```

## Additional Packages

| Package | What it adds |
|---------|-------------|
| `@remotion/three` | 3D scenes (React Three Fiber) |
| `@remotion/lottie` | Lottie animation files |
| `@remotion/gif` | GIF playback in compositions |
| `@remotion/shapes` | SVG shapes (circle, rect, triangle, etc.) |
| `@remotion/paths` | SVG path manipulation and animation |
| `@remotion/noise` | Perlin/simplex noise for generative art |
| `@remotion/transitions` | Scene transition presets |
| `@remotion/tailwind` | Tailwind CSS support |
| `@remotion/captions` | Caption/subtitle rendering |
| `@remotion/elevenlabs` | Text-to-speech integration |
| `@remotion/skia` | Low-level 2D graphics (React Native Skia) |

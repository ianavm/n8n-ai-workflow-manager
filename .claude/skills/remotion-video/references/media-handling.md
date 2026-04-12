---
name: media-handling
description: Using video, audio, images, and fonts in Remotion
---

# Media Handling

## Video

### OffthreadVideo (ALWAYS USE THIS)

```tsx
import { OffthreadVideo } from "remotion";

// Basic usage
<OffthreadVideo src={videoUrl} />

// With transparency (WebM)
<OffthreadVideo src={webmUrl} transparent />

// Local file (from public/ directory)
import { staticFile } from "remotion";
<OffthreadVideo src={staticFile("background.mp4")} />

// With styling
<OffthreadVideo
  src={videoUrl}
  style={{ width: "100%", height: "100%", objectFit: "cover" }}
/>

// Playback rate
<OffthreadVideo src={videoUrl} playbackRate={0.5} />  // Half speed
<OffthreadVideo src={videoUrl} playbackRate={2} />    // Double speed

// Start from specific time
<OffthreadVideo src={videoUrl} startFrom={60} />  // Start from frame 60

// End at specific time
<OffthreadVideo src={videoUrl} endAt={120} />  // End at frame 120

// Muted
<OffthreadVideo src={videoUrl} muted />
```

**NEVER use `Video` component** — it uses browser decoder (causes jitter in renders).

## Audio

```tsx
import { Audio, staticFile } from "remotion";

// Background music
<Audio src={staticFile("music.mp3")} />

// With volume control
<Audio src={staticFile("music.mp3")} volume={0.5} />

// Fade in/out
const frame = useCurrentFrame();
const volume = interpolate(frame, [0, 30, 270, 300], [0, 0.8, 0.8, 0], {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
});
<Audio src={staticFile("music.mp3")} volume={volume} />

// Start from specific time
<Audio src={staticFile("music.mp3")} startFrom={60} />

// Play only during a Sequence
<Sequence from={30} durationInFrames={120}>
  <Audio src={staticFile("sfx.mp3")} />
</Sequence>
```

## Images

```tsx
import { Img, staticFile } from "remotion";

// Local image
<Img src={staticFile("hero.png")} />

// Remote image
<Img src="https://example.com/photo.jpg" />

// With styling
<Img
  src={staticFile("hero.png")}
  style={{
    width: "100%",
    height: "100%",
    objectFit: "cover",
  }}
/>
```

## Static Files

Place files in `public/` directory, reference with `staticFile()`:

```
public/
  background.mp4
  music.mp3
  logo.png
  font.woff2
```

```tsx
import { staticFile } from "remotion";

staticFile("background.mp4")  // → /public/background.mp4
staticFile("logo.png")        // → /public/logo.png
```

## Fonts

### Google Fonts (via @remotion/google-fonts)

```tsx
import { loadFont } from "@remotion/google-fonts/Inter";
const { fontFamily } = loadFont();

<div style={{ fontFamily }}>Text with Inter font</div>
```

### Local Fonts

```tsx
// In your component
const fontFace = new FontFace("MyFont", `url(${staticFile("font.woff2")})`);
document.fonts.add(fontFace);
await fontFace.load();
```

## Preloading (for Player)

```tsx
import { preloadVideo, preloadAudio, preloadImage } from "@remotion/preload";

// Preload before rendering
preloadVideo(videoUrl);
preloadAudio(audioUrl);
preloadImage(imageUrl);
```

## Media Duration Detection

```tsx
import { getVideoMetadata, getAudioDurationInSeconds } from "@remotion/media-utils";

// Get video info
const { durationInSeconds, width, height } = await getVideoMetadata(videoUrl);
const durationInFrames = Math.ceil(durationInSeconds * 30);

// Get audio duration
const audioDuration = await getAudioDurationInSeconds(audioUrl);
```

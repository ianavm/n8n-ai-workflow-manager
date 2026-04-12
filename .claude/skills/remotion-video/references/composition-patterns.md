---
name: composition-patterns
description: Common Remotion composition patterns for layout, layering, and transitions
---

# Composition Patterns

## Layout Patterns

### AbsoluteFill (Full Frame)
```tsx
import { AbsoluteFill } from "remotion";

<AbsoluteFill style={{ backgroundColor: "#1a1a2e", justifyContent: "center", alignItems: "center" }}>
  <h1 style={{ color: "white", fontSize: 80 }}>Title</h1>
</AbsoluteFill>
```

### Split Screen
```tsx
<AbsoluteFill style={{ flexDirection: "row" }}>
  <div style={{ flex: 1, backgroundColor: "#1a1a2e" }}>Left</div>
  <div style={{ flex: 1, backgroundColor: "#2a2a3e" }}>Right</div>
</AbsoluteFill>
```

### Grid Layout
```tsx
<AbsoluteFill style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gridTemplateRows: "1fr 1fr" }}>
  <div>Top Left</div>
  <div>Top Right</div>
  <div>Bottom Left</div>
  <div>Bottom Right</div>
</AbsoluteFill>
```

## Layering with Sequences

```tsx
import { AbsoluteFill, Sequence } from "remotion";

<AbsoluteFill>
  {/* Background - always visible */}
  <AbsoluteFill style={{ backgroundColor: "#1a1a2e" }} />

  {/* Title appears at frame 0, lasts 60 frames */}
  <Sequence durationInFrames={60}>
    <Title text="Welcome" />
  </Sequence>

  {/* Content appears at frame 30, lasts 90 frames */}
  <Sequence from={30} durationInFrames={90}>
    <Content />
  </Sequence>

  {/* CTA appears at frame 90, stays until end */}
  <Sequence from={90}>
    <CallToAction />
  </Sequence>
</AbsoluteFill>
```

## Transitions

### Fade In/Out
```tsx
const frame = useCurrentFrame();
const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
```

### Slide In
```tsx
const translateX = interpolate(frame, [0, 20], [-1920, 0], { extrapolateRight: "clamp" });
style={{ transform: `translateX(${translateX}px)` }}
```

### Scale Up
```tsx
const scale = spring({ frame, fps, config: { damping: 200, stiffness: 100 } });
style={{ transform: `scale(${scale})` }}
```

### Wipe Transition Between Scenes
```tsx
const progress = interpolate(frame, [0, 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

<AbsoluteFill>
  <AbsoluteFill style={{ clipPath: `inset(0 ${(1 - progress) * 100}% 0 0)` }}>
    <NewScene />
  </AbsoluteFill>
  <AbsoluteFill style={{ clipPath: `inset(0 0 0 ${progress * 100}%)` }}>
    <OldScene />
  </AbsoluteFill>
</AbsoluteFill>
```

## Multiple Compositions

Register multiple videos in one project:

```tsx
// src/Root.tsx
export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Intro" component={Intro} durationInFrames={90} fps={30} width={1920} height={1080} />
    <Composition id="Main" component={Main} durationInFrames={300} fps={30} width={1920} height={1080} />
    <Composition id="Outro" component={Outro} durationInFrames={60} fps={30} width={1920} height={1080} />
    <Composition id="Thumbnail" component={Thumbnail} durationInFrames={1} fps={30} width={1280} height={720} />
  </>
);
```

## Dynamic Props with calculateMetadata

```tsx
import { CalculateMetadataFunction } from "remotion";

export const calculateMetadata: CalculateMetadataFunction<MyProps> = async ({ props }) => {
  const duration = await fetchVideoDuration(props.videoUrl);
  return {
    durationInFrames: Math.ceil(duration * 30),
    fps: 30,
    width: 1920,
    height: 1080,
  };
};
```

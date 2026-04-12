---
name: animation-reference
description: Remotion animation primitives — interpolate, spring, easing
---

# Animation Reference

## interpolate()

Maps a value from one range to another. Primary animation tool.

```tsx
import { interpolate, useCurrentFrame } from "remotion";

const frame = useCurrentFrame();

// Fade in over 30 frames
const opacity = interpolate(frame, [0, 30], [0, 1]);

// Move from left to center
const x = interpolate(frame, [0, 60], [-500, 0]);

// With clamping (prevent overshoot)
const clamped = interpolate(frame, [0, 30], [0, 1], {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
});

// With easing
import { Easing } from "remotion";
const eased = interpolate(frame, [0, 30], [0, 1], {
  easing: Easing.bezier(0.25, 0.1, 0.25, 1),
  extrapolateRight: "clamp",
});
```

### Common Easing Functions

```tsx
import { Easing } from "remotion";

Easing.linear           // No easing
Easing.ease             // Default CSS ease
Easing.in(Easing.ease)  // Ease in
Easing.out(Easing.ease) // Ease out
Easing.inOut(Easing.ease) // Ease in-out
Easing.bezier(0.25, 0.1, 0.25, 1)  // Custom cubic bezier
Easing.bounce           // Bounce effect
Easing.elastic(1)       // Elastic effect
```

## spring()

Physics-based animation. Returns 0 → 1 with natural motion.

```tsx
import { spring, useCurrentFrame, useVideoConfig } from "remotion";

const frame = useCurrentFrame();
const { fps } = useVideoConfig();

// Basic spring (smooth entrance)
const scale = spring({ frame, fps });

// Custom config
const bouncy = spring({
  frame,
  fps,
  config: {
    damping: 10,      // Lower = more bouncy (default: 10)
    stiffness: 100,   // Higher = faster (default: 100)
    mass: 1,           // Higher = slower (default: 1)
    overshootClamping: false, // Allow overshoot (default: false)
  },
});

// Delayed spring
const delayed = spring({ frame: frame - 30, fps }); // Starts at frame 30

// Spring with duration
const timed = spring({
  frame,
  fps,
  durationInFrames: 30,
  config: { damping: 200 },
});
```

## Sequence Timing

```tsx
import { Sequence } from "remotion";

// Show from frame 0 to 60
<Sequence durationInFrames={60}>
  <Component />
</Sequence>

// Show from frame 30 onwards
<Sequence from={30}>
  <Component />
</Sequence>

// Show from frame 30 to 90
<Sequence from={30} durationInFrames={60}>
  <Component />
</Sequence>

// Named sequence (shows in timeline)
<Sequence from={30} name="Title Animation">
  <Component />
</Sequence>
```

## Common Animation Recipes

### Fade In + Scale Up
```tsx
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
const opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
const scale = spring({ frame, fps, config: { damping: 200 } });

<div style={{ opacity, transform: `scale(${scale})` }}>Content</div>
```

### Typewriter Effect
```tsx
const text = "Hello World";
const frame = useCurrentFrame();
const charsToShow = Math.min(Math.floor(frame / 3), text.length);
<span>{text.slice(0, charsToShow)}</span>
```

### Counter / Number Animation
```tsx
const frame = useCurrentFrame();
const value = Math.round(interpolate(frame, [0, 60], [0, 1000], { extrapolateRight: "clamp" }));
<span>{value.toLocaleString()}</span>
```

### Stagger (Sequential Elements)
```tsx
const items = ["A", "B", "C", "D"];
const frame = useCurrentFrame();
const { fps } = useVideoConfig();

{items.map((item, i) => {
  const delay = i * 5; // 5 frame delay between each
  const scale = spring({ frame: frame - delay, fps, config: { damping: 200 } });
  return <div key={i} style={{ transform: `scale(${Math.max(0, scale)})` }}>{item}</div>;
})}
```

### Looping Animation
```tsx
const frame = useCurrentFrame();
const loopedFrame = frame % 60; // Loop every 60 frames
const rotation = interpolate(loopedFrame, [0, 60], [0, 360]);
<div style={{ transform: `rotate(${rotation}deg)` }}>Spinning</div>
```

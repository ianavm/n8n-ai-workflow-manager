---
name: integration-guide
description: How Stitch outputs integrate with Remotion, Banana, and frontend development
---

# Stitch Integration Guide

## Stitch + Remotion (Video from Designs)

### Use Case: Product Demo Video
1. Design each "screen" of the demo in Stitch
2. Download images with `get_screen_image`
3. Save to Remotion `public/` directory
4. Create a slide-deck composition:

```tsx
import { Img, staticFile, Sequence, AbsoluteFill } from "remotion";

const screens = ["screen-dashboard.png", "screen-settings.png", "screen-analytics.png"];
const SLIDE_DURATION = 90; // 3 seconds each

export const ProductDemo: React.FC = () => (
  <AbsoluteFill>
    {screens.map((screen, i) => (
      <Sequence key={i} from={i * SLIDE_DURATION} durationInFrames={SLIDE_DURATION}>
        <Img src={staticFile(screen)} style={{ width: "100%", height: "100%" }} />
      </Sequence>
    ))}
  </AbsoluteFill>
);
```

### Use Case: App Walkthrough with Transitions
1. Generate screens for each step
2. Add slide/fade transitions between screens in Remotion
3. Overlay annotations, arrows, highlights with animation

## Stitch + Banana (Enhanced Visuals)

### Use Case: Landing Page with Custom Hero Image
1. Design the page layout in Stitch (with placeholder hero area)
2. Generate a hero image with Banana: `/banana generate "startup team collaborating in modern office, warm lighting, editorial style"`
3. Download both assets
4. Composite in HTML/CSS or Remotion

### Use Case: Marketing Materials
1. Generate multiple page layouts with Stitch
2. Generate product photos and illustrations with Banana
3. Combine into cohesive marketing assets

## Stitch + Frontend (Design to Code)

### Workflow
1. Generate UI with Stitch
2. Download HTML with `get_screen_code`
3. Analyze the HTML structure
4. Rebuild as React/Next.js components with proper:
   - Component decomposition
   - Tailwind classes (replacing inline styles)
   - State management
   - API integration
   - Responsive breakpoints

### Tips
- Use Stitch HTML as visual reference, not production code
- Extract the design tokens (colors, spacing, typography)
- The generated HTML is a starting point, not the final implementation
- Cross-reference with ui-ux-pro-max-skill for design patterns

## Content Creation Pipeline

```
         Text Prompt
              |
     [Stitch: Design UI]
         /          \
  HTML/Code      Screenshot
     |                |
  Frontend Dev    [Banana: Hero Images]
                      |
              [Remotion: Compose Video]
                      |
              MP4 / WebM / GIF / Stills
```

1. Start with Stitch for layout and structure
2. Enhance with Banana for custom imagery
3. Animate with Remotion for video content
4. Output to social media, website, presentations

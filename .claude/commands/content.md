---
description: Content creation pipeline using Stitch (design), Banana (images), and Remotion (video). Orchestrates AI-generated visuals into production content.
---

# Content Creation Pipeline

This command orchestrates the three content creation skills:

## Available Skills

| Skill | What it does | Invoke with |
|-------|-------------|-------------|
| **Stitch** | AI UI/UX screen generation | `/stitch-design` or natural language |
| **Banana** | AI image generation (9 creative modes) | `/banana generate <idea>` |
| **Remotion** | Programmatic video from React code | `/video` or natural language |
| **HeyGen** | AI avatar video generation | HeyGen skill (re-enabled) |

## Pipeline

```
[Stitch] Design UI screens/mockups
    |
    v
[Banana] Generate hero images, product photos, OG images
    |
    v
[Remotion] Compose into video: UI demos + images + motion graphics + avatars
    |
    v
Output: MP4/WebM for social, GIF for email, stills for blog
```

## Content Types

### Social Media Video
1. Generate key frames with Stitch or Banana
2. Create Remotion composition (1080x1920 for reels, 1920x1080 for YouTube)
3. Add animations, text overlays, transitions
4. Render to MP4

### Product Demo
1. Design UI screens with Stitch
2. Add product photos with Banana
3. Compose walkthrough video with Remotion
4. Optional: add HeyGen avatar presenter

### Marketing Assets
1. Design landing page with Stitch
2. Generate hero image with Banana
3. Create animated banner with Remotion
4. Export stills for social media

### Presentation Video
1. Design slide layouts with Stitch
2. Generate supporting visuals with Banana
3. Animate slide deck with Remotion
4. Optional: add HeyGen avatar narration
5. Render to MP4

## Quick Start

Tell me what content you need and I'll route to the right skill(s):
- "I need a product demo video" → Stitch + Remotion
- "Generate a hero image for our landing page" → Banana
- "Design a new dashboard mockup" → Stitch
- "Create a social media reel" → Banana + Remotion
- "Make an animated logo intro" → Remotion

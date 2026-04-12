---
description: Create, preview, and render videos using Remotion. Scaffolds projects, builds compositions, and handles rendering.
---

Load the remotion-video skill and help the user with video creation.

## Workflow

1. If no Remotion project exists, scaffold one with `npx create-video@latest`
2. Design compositions based on the user's requirements
3. Preview with `npx remotion studio`
4. Render with `npx remotion render` or the Node.js API

## Common tasks

- `create` — Scaffold a new Remotion project for the specified video type
- `render <composition-id>` — Render a composition to MP4
- `still <composition-id>` — Render a single frame as PNG
- `preview` — Start Remotion Studio for interactive preview
- `list` — List available compositions

## Integration

- Use Banana-generated images as video assets
- Use HeyGen avatar videos with OffthreadVideo
- Use Stitch-generated UI screens as video frames

Read the full skill at `.claude/skills/remotion-video/SKILL.md` and its references for patterns.

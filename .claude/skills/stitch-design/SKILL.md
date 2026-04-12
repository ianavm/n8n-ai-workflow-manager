---
name: stitch-design
description: "AI UI/UX design generation using Google Stitch. Generate UI screens from text prompts, download HTML/images, build sites from designs. Use when user says: design UI, create screen, generate mockup, UI design, stitch, design page, landing page design, app screen, wireframe, prototype, generate layout."
argument-hint: "[generate|list|download|build] <description or project-id>"
metadata:
  version: "1.0.0"
  mcp-endpoint: "https://stitch.googleapis.com/mcp"
  reference-repo: "Github Access/stitch-main"
---

# Stitch Design — AI UI/UX Screen Generation

## What is Stitch

Stitch is Google's AI-powered UI/UX design and code generation tool. It generates
full UI screens from text descriptions using Gemini models, and exports both
images and HTML code. Access via MCP server at `https://stitch.googleapis.com/mcp`.

**Free to use.** No per-generation charges.

## MCP Tools Available

| Tool | Purpose |
|------|---------|
| `list_projects` | List all Stitch projects |
| `get_project_details` | Get details about a specific project |
| `list_screens` | Get all screens in a project |
| `get_screen_code` | Download HTML code for a screen |
| `get_screen_image` | Download screenshot/image of a screen |
| `generate_screen` | Generate a new UI screen from text prompt |
| `enhance_prompt` | Improve a design prompt before generation |
| `build_site` | Build an Astro site from project screens |

## Workflow

### Generate a UI Screen

1. **Craft a detailed prompt** describing the screen:
   - Layout structure (sidebar, grid, cards)
   - Content type (dashboard, login, pricing, settings)
   - Style (dark mode, minimal, corporate, playful)
   - Platform (mobile, desktop, tablet)

2. **Optionally enhance the prompt** for better results:
   - Use `enhance_prompt` to have AI improve your description

3. **Generate the screen**:
   - Use `generate_screen` with your prompt
   - Choose model: Gemini 3 Pro (higher quality) or Gemini 3 Flash (faster, default)

4. **Review and iterate**:
   - Use `get_screen_image` to preview the result
   - Regenerate with refined prompt if needed

5. **Export**:
   - `get_screen_code` — HTML/CSS for development
   - `get_screen_image` — PNG for presentations, Remotion videos, mockups

### Build a Full Site

1. Generate multiple screens (landing, dashboard, settings, etc.)
2. Use `build_site` to map screens to routes
3. Get an Astro-based site with proper navigation

## Prompting Best Practices

### Be Specific About Layout
```
GOOD: "A SaaS dashboard with a dark sidebar navigation on the left,
       main content area showing 4 KPI cards in a row at the top,
       a line chart below, and a data table at the bottom"

BAD:  "A dashboard"
```

### Include Content Context
```
GOOD: "A pricing page for a digital marketing agency with 3 tiers:
       Starter (R1,999/mo), Growth (R4,999/mo), Enterprise (R29,999/mo).
       Dark theme with orange (#FF6D5A) accent color."

BAD:  "A pricing page"
```

### Reference Design Patterns
```
"Material Design 3 style settings page"
"Stripe-inspired checkout flow"
"Linear-style project board"
"Notion-like document editor"
```

### Specify Platform
```
"Mobile-first login screen for iOS"
"Desktop admin dashboard, 1440px wide"
"Responsive landing page, mobile and desktop"
```

## Integration with Other Skills

### Stitch + Banana (Images)
Generate hero images with `/banana generate` for Stitch-designed pages:
1. Design the page layout with Stitch
2. Generate a hero image with Banana matching the design style
3. Export both and combine in frontend code

### Stitch + Remotion (Video)
Use Stitch screens as video frames:
1. Generate UI screens with Stitch
2. Download as images
3. Use in Remotion composition as `<Img>` components
4. Add animations and transitions

### Stitch + Frontend Development
Use Stitch as a starting point:
1. Generate UI screen with Stitch
2. Download HTML with `get_screen_code`
3. Adapt to React/Next.js components
4. Apply your design system (Tailwind, etc.)

## Authentication

Requires a Stitch API key configured in `.mcp.json`:
- Get API key at https://stitch.withgoogle.com/ → Settings → API Keys → Create Key
- Configured as `X-Goog-Api-Key` header in the MCP server config

## Error Handling

| Error | Resolution |
|-------|-----------|
| Authentication failed | Check API key in `.mcp.json` |
| Rate limited | Wait and retry (free tier has generous limits) |
| Generation failed | Simplify prompt, try Gemini 3 Flash instead of Pro |
| Screen not found | Use `list_screens` to verify screen ID |

---
name: stitch-tools
description: MCP tool reference for Google Stitch design generation
---

# Stitch MCP Tool Reference

## Endpoint

HTTP MCP server at `https://stitch.googleapis.com/mcp`

Authentication: `X-Goog-Api-Key` header with Stitch API key

## Tools

### list_projects
Lists all Stitch projects for the authenticated user.
- No parameters required
- Returns: Array of project objects with IDs and names

### get_project_details
Get comprehensive information about a specific project.
- Parameter: `project_id` (string) — The project ID
- Returns: Project metadata, settings, screen count

### list_screens
Get all screens within a project.
- Parameter: `project_id` (string) — The project ID
- Returns: Array of screen objects with IDs, names, thumbnails

### get_screen_code
Download the HTML/CSS code for a specific screen.
- Parameter: `screen_id` (string) — The screen ID
- Returns: Full HTML with inline CSS

### get_screen_image
Download a screenshot/image of a specific screen.
- Parameter: `screen_id` (string) — The screen ID
- Returns: Base64-encoded PNG image

### generate_screen
Generate a new UI screen from a text description.
- Parameter: `prompt` (string) — Description of the desired screen
- Parameter: `model` (string, optional) — "gemini-3-pro" or "gemini-3-flash" (default)
- Returns: Generated screen with ID, image, and code

### enhance_prompt
Improve a design prompt for better generation results.
- Parameter: `prompt` (string) — The original prompt to enhance
- Returns: Enhanced, more detailed prompt

### build_site
Build a static Astro site from project screens.
- Parameter: `project_id` (string) — The project ID
- Parameter: `route_mapping` (object, optional) — Map screen IDs to URL routes
- Returns: Astro project structure with routes

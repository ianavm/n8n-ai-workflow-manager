---
type: governance
tags: [meta, governance]
last_reviewed: 2026-04-12
---

# Plugin Allowlist

Last reviewed: 2026-04-12
Next review: 2026-07-12 (quarterly)

## Approved Plugins (all users)

| Plugin | ID | Purpose | Status |
|---|---|---|---|
| Templater | templater-obsidian | Template engine with variables | Active, maintained |
| QuickAdd | quickadd | Macro engine, pairs with Templater | Active |
| Tasks | obsidian-tasks-plugin | Cross-vault task queries | Active |
| Advanced Tables | table-editor-obsidian | Table editing shortcuts | Active |
| Excalidraw | obsidian-excalidraw-plugin | Diagrams with note linking | Very active |
| Obsidian Git | obsidian-git | Git sync, auto-commit | Active |
| Homepage | homepage | Landing page on vault open | Active |
| Style Settings | obsidian-style-settings | Theme customization | Maintenance mode |
| Iconize | obsidian-icon-folder | Folder/file icons | Active |

## Approved AI Plugins (Ian only)

| Plugin | ID | Purpose | Status |
|---|---|---|---|
| Smart Connections | smart-connections | Local RAG + semantic search | Active, 786K downloads |
| Claude Code MCP | obsidian-claude-code-mcp | MCP server for Claude Code/Cursor | Active |
| AI Prompt Manager | ai-prompt-manager | Prompt library with versioning | Niche, active |

## Banned / Avoided

- **Projects** (marcusolsson) - Discontinued May 2025. Use Bases instead.
- **Dataview** - Legacy. Use Bases for new structured views. Install only if a specific DQL query is needed that Bases cannot express.
- **Text Generator** - Overtaken by Smart Connections / Copilot.
- Any plugin that embeds MCP servers without code review.
- Any plugin requesting network access that is not on the approved list.

## Policy

1. All plugin installations must be approved by Ian.
2. Community plugins run unsandboxed with full Node.js access. One compromised plugin = full vault exfiltration.
3. Do NOT install experimental AI plugins in any vault containing sensitive data.
4. Review this list quarterly. Remove any abandoned or suspicious plugins.
5. Pin plugin versions where possible. Test updates before applying to the shared vault.

## How to Request a Plugin

1. Open a note in `62 Incidents/` or discuss with Ian.
2. Include: plugin name, GitHub repo, what it does, why you need it.
3. Ian reviews the source, checks maintenance status, and decides.

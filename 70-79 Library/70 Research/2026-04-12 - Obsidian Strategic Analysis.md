---
type: research
date: 2026-04-12
topic: Obsidian.md adoption decision
status: decided
decision: Adopt (limited scope — founder + technical team)
tags: [research, decision, tools]
---

# Obsidian.md — Strategic Analysis for AVM

> Research conducted 2026-04-12. Decision: **Adopt as technical knowledge backbone** (Option B — founder + small technical team, git-backed, hybrid with Google Workspace).

## Executive Summary

Obsidian is a free, local-first Markdown editor that turns any folder of `.md` files into a linked, graphable, queryable knowledge vault. AVM adopted it because our knowledge is already 80% Markdown, and Obsidian makes it linkable, queryable (Bases), embeddable (Smart Connections / LlamaIndex), and directly callable from Claude Code / Cursor / MCP.

**Confidence: 8.5/10**

## Verdict by Use Case

| Use | Score | Notes |
|---|---|---|
| Founder second brain | 10/10 | Perfect fit, near-zero migration |
| Workflow/agent/prompt documentation | 9-10/10 | Best-in-class for technical docs |
| SOP documentation | 8/10 | Strong, but no approval workflows |
| Meeting notes | 7/10 | Good async; use Google Docs for live co-editing |
| Client-facing docs | 5/10 | Internal only; export via Quartz or Drive |
| Sales playbooks | 6/10 | Non-technical staff prefer Docs/Notion |
| Project management | 4/10 | Use a real PM tool (ClickUp/Linear) |
| Onboarding non-technical staff | 4/10 | Expect 50% never to adopt it |

## Key Strengths

- **Data ownership** — notes are files on disk, zero lock-in
- **AI compatibility** — Claude Code, Cursor, LlamaIndex, LangChain all treat Markdown as first-class
- **Bases (2025+)** — native database views over frontmatter, replacing Dataview
- **Speed** — 5,000-note vault opens in under a second
- **Free** — commercial license became optional Feb 2026

## Key Risks

- **No native real-time collaboration** at Google-Docs quality
- **No SSO, audit logs, SOC 2, or enterprise controls**
- **Plugin supply chain** — unsandboxed, full Node.js access
- **Failure mode: "only the founder uses it"** — most common exit story
- **Plugin abandonment** — Projects discontinued, Kanban maintenance-only

## Competitive Position

- **Beats Notion** on: data ownership, speed, AI compatibility, lock-in risk
- **Loses to Notion** on: collaboration, onboarding, client-facing docs
- **Beats Confluence** for our size (overkill for <20 people)
- **Logseq has stalled** — DB version still beta after 2+ years
- **Google Docs** is the "do nothing" baseline — Obsidian must prove it adds value beyond Docs

## AI Company Killer Use Case

**Vault -> LlamaIndex ObsidianReader -> Postgres Brain -> RAG endpoint -> n8n workflows -> AI agents -> clients.** One substrate, many retrieval surfaces. Our Postgres Brain already does half of this.

## Recommended Hybrid Stack

| Tool | Role |
|---|---|
| **Obsidian** | Technical knowledge backbone (SOPs, workflows, agents, prompts, research) |
| **Git** | Version control + sync + backup |
| **Google Workspace** | Collaborative editing, client deliverables, anything non-technical staff touch |
| **Airtable/Supabase** | Structured business data, production data, client portal |
| **Claude Code MCP** | AI reads/writes the vault directly |
| **Quartz 4** | Publish selected notes as static site (free, self-hosted) |

## Implementation (completed 2026-04-12)

- Vault at repo root with Johnny.Decimal structure (00-09 through 90-99)
- 9 approved plugins (Templater, QuickAdd, Tasks, Advanced Tables, Excalidraw, Obsidian Git, Homepage, Style Settings, Iconize)
- 9 templates (Workflow, Agent, Prompt, Meeting, SOP, Decision, Experiment, Client Onboarding, Bug Pattern)
- 3 Bases views (Workflow Registry, Agent Library, Prompt Library)
- 10 starter workflow notes with real data
- Governance docs (Plugin Allowlist, Vault Conventions, Backup Policy)
- Selective gitignore (commit core config, ignore workspace + plugin data)

## Non-Negotiables

1. Git-backed, not Obsidian-Sync-alone
2. Plugin allowlist enforced (Ian approves all installs)
3. Two vaults when sensitive data is involved (ops + sensitive)
4. Templates + frontmatter schemas required for every new note
5. Nightly off-site backup
6. Quarterly plugin + schema audit

## Success Metrics (30-day check)

- [ ] 20+ notes/week written in Obsidian
- [ ] 2+ active users opening the vault weekly
- [ ] 80% of workflow notes have complete frontmatter
- [ ] 5+ Claude Code sessions/week using vault context
- [ ] <2 sync conflicts requiring manual resolution

## Sources

Official: obsidian.md/pricing, /sync, /publish, /privacy, /roadmap, help.obsidian.md/bases, /plugin-security
Comparisons: tech-insider.org, productivetemply.com, eesel.ai, clonepartner.com, androidpolice.com
AI integrations: github.com/iansinnott/obsidian-claude-code-mcp, github.com/brianpetro/obsidian-smart-connections, docs.llamaindex.ai/obsidian, github.com/Ar9av/obsidian-wiki
Plugin ecosystem: obsidian.rocks, obsidianstats.com, dsebastien.net, systemsculpt.com

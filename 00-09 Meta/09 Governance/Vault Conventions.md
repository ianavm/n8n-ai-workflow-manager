---
type: governance
tags: [meta, governance]
last_reviewed: 2026-04-12
---

# Vault Conventions

## Folder Structure

This vault uses **Johnny.Decimal** — numbered areas alongside existing code folders.

| Area | Purpose |
|---|---|
| 00-09 Meta | Dashboard, templates, governance |
| 10-19 Company | Strategy, brand, legal |
| 20-29 Departments | Per-department notes |
| 30-39 Systems | Workflows, agents, tools, prompts, architecture |
| 40-49 Clients | Active and closed client folders |
| 50-59 R&D | Experiments, model comparisons, bug patterns |
| 60-69 Ops | Meeting notes, decisions, incidents |
| 70-79 Library | Research, reference docs |
| 80-89 People | Team notes |
| 90-99 Archive | Anything older than 6 months without recent references |

**Important:** The `templates/` folder at repo root contains **HTML email templates for n8n workflows** (accounting, lead outreach). It is NOT the Obsidian template folder. Obsidian templates live in `00-09 Meta/01 Templates/`.

## Naming Conventions

| Type | Pattern | Example |
|---|---|---|
| Workflow notes | `WF-## - Name` or `ADS-## - Name` or `LI-## - Name` | `WF-01 - Invoice Generator` |
| Agent notes | `AGENT-## - Name` | `AGENT-LI-03 - Enrichment` |
| SOP notes | `SOP-## - Name` | `SOP-01 - Deployment Checklist` |
| Client folders | `ClientName` (stable slug) | `Acme Corp` |
| Meeting notes | `YYYY-MM-DD - Topic` | `2026-04-12 - Sprint Review` |
| Decision notes | `YYYY-MM-DD - Decision - Topic` | `2026-04-12 - Decision - Obsidian Adoption` |
| Experiments | `EXP-## - Name` | `EXP-01 - Claude vs GPT on ICP Scoring` |

## Required Frontmatter

Every note MUST have a `type` field. Additional required fields depend on the type:

| Type | Required Fields |
|---|---|
| workflow | type, wf_id, department, active, owner, tags |
| agent | type, agent_id, department, status, tags |
| prompt | type, prompt_id, model, version, tags |
| meeting | type, date, tags |
| sop | type, sop_id, department, version, owner, tags |
| decision | type, date, status, tags |
| experiment | type, date, model, status, tags |
| client | type, client_name, status, tags |
| bug-pattern | type, date, severity, tags |

Use templates from `01 Templates/` to create new notes — they enforce the schema automatically.

## Linking Conventions

- Use **wikilinks** (`[[Note Name]]`), not markdown links.
- Link workflows to their SOPs, agents, and prompts.
- Link agents to their prompts and tools.
- Link meeting notes to the project they concern.
- When referencing a deploy script or tool, use backtick code format: `` `tools/deploy_ads_dept.py` ``.

## Tagging Rules

Use tags sparingly — prefer links and frontmatter properties for organization. Tags are for cross-cutting categories:

| Tag | When to use |
|---|---|
| `#workflow` | All workflow notes |
| `#agent` | All agent notes |
| `#prompt` | All prompt notes |
| `#meeting` | All meeting notes |
| `#decision` | All decision notes |
| `#sop` | All SOP notes |
| `#client` | All client notes |
| `#experiment` | All experiment notes |
| `#bug-pattern` | All bug pattern notes |
| `#urgent` | Anything requiring immediate attention |
| `#stale` | Notes that need review or updating |

## File Location Rules

- New quick notes default to `60-69 Ops/60 Meeting Notes/` (configured in app.json).
- Attachments go to `00-09 Meta/Attachments/`.
- When in doubt, check this guide or ask Ian.

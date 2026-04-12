---
type: workflow
wf_id: LI-03
department: linkedin
n8n_id: 
schedule: "Called by LI-01"
active: true
dependencies: ["OpenRouter (Claude Sonnet 4)", "Google Sheets"]
owner: ian
last_audit: 2026-04-12
tags: [workflow, linkedin, leads, agent, ai]
---

# LI-03 - Enrichment Agent

## Purpose
Enriches discovered LinkedIn leads with AI-generated analysis. Uses Claude Sonnet 4 via OpenRouter to analyze profile data, identify company context, and score relevance.

## Trigger
Called by [[LI-01 - Orchestrator]] (sub-workflow, after LI-02)

## Key Nodes
- Google Sheets read (Discovery tab)
- Claude Sonnet 4 enrichment via OpenRouter
- Google Sheets write (Enrichment tab)

## Dependencies
- OpenRouter API key (model: `anthropic/claude-sonnet-4-20250514`)
- Google Sheets (shared sheet)

## Related
- Deploy script: `tools/deploy_linkedin_dept.py`
- Department: [[24 LinkedIn Intelligence/]]
- Previous: [[LI-02 - Discovery Agent]]
- Next: LI-04 (ICP Scoring)

## Notes
- One of 6 AI nodes across the pipeline (LI-03 through LI-07 + LI-10)
- Token budget managed at the OpenRouter level

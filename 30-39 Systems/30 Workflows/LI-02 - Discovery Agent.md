---
type: workflow
wf_id: LI-02
department: linkedin
n8n_id: 
schedule: "Called by LI-01"
active: true
dependencies: ["Apify", "Google Sheets"]
owner: ian
last_audit: 2026-04-12
tags: [workflow, linkedin, leads, agent]
---

# LI-02 - Discovery Agent

## Purpose
Discovers potential LinkedIn leads matching ICP criteria. Scrapes profiles via Apify and stores raw data in Google Sheets.

## Trigger
Called by [[LI-01 - Orchestrator]] (sub-workflow)

## Key Nodes
- Apify LinkedIn scraper
- Google Sheets write (Discovery tab)
- Deduplication logic

## Dependencies
- Apify credential
- Google Sheets (shared sheet with 10 tabs)

## Related
- Deploy script: `tools/deploy_linkedin_dept.py`
- Department: [[24 LinkedIn Intelligence/]]
- Previous: [[LI-01 - Orchestrator]]
- Next: [[LI-03 - Enrichment Agent]]

## Notes
- Part of the 10-workflow LinkedIn Intelligence pipeline

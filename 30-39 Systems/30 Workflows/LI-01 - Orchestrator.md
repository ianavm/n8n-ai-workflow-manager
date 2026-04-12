---
type: workflow
wf_id: LI-01
department: linkedin
n8n_id: 
schedule: "Mon 07:00 SAST"
active: true
dependencies: ["Google Sheets", "Apify", "OpenRouter"]
owner: ian
last_audit: 2026-04-12
tags: [workflow, linkedin, leads]
---

# LI-01 - Orchestrator

## Purpose
Main orchestrator for the LinkedIn Lead Intelligence pipeline. Calls LI-02 through LI-09 sequentially every Monday.

## Trigger
Scheduled: Monday at 07:00 SAST

## Key Nodes
- Sequential workflow calls (LI-02 -> LI-09)
- Google Sheets status tracking
- Telegram summary notification

## Dependencies
- Google Sheets (`133K-AiWyvCaeD8Y_SCzDT7Huxz-TrBY6CXn10jY81uE`) with 10 tabs
- Apify (LinkedIn scraping)
- OpenRouter (Claude Sonnet 4 for AI nodes in LI-03 to LI-07)
- Telegram (@AVMCRMBot, chat 6311361442)
- Gmail (summary email)

## Related
- Deploy script: `tools/deploy_linkedin_dept.py`
- Department: [[24 LinkedIn Intelligence/]]
- Pipeline: LI-01 -> [[LI-02 - Discovery Agent]] -> [[LI-03 - Enrichment Agent]] -> LI-04 through LI-09
- Feedback loop: LI-10 (runs independently)

## Notes
- 10-workflow multi-agent AI pipeline: discovery -> enrichment -> ICP scoring -> pain detection -> opportunity mapping -> outreach -> prioritization -> CRM sync
- 6 AI nodes across LI-03 to LI-07 + LI-10

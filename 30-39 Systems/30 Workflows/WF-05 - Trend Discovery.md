---
type: workflow
wf_id: WF-05
department: seo-social
n8n_id: 
schedule: "Mon/Thu 06:00 SAST"
active: true
dependencies: ["SerpAPI", "Airtable (Keywords table)", "OpenRouter"]
owner: ian
last_audit: 2026-04-12
tags: [workflow, seo, social]
---

# WF-05 - Trend Discovery

## Purpose
Discovers trending topics and keywords relevant to AVM's content strategy. Feeds into the SEO content production pipeline.

## Trigger
Scheduled: Monday and Thursday at 06:00 SAST

## Key Nodes
- SerpAPI keyword research
- Claude AI topic analysis via OpenRouter
- Airtable Keywords table update

## Dependencies
- SerpAPI credential (httpHeaderAuth)
- Airtable marketing base (`apptjjBx34z9340tK`)
- OpenRouter API key

## Related
- SOP: [[workflows/seo-social-dept/airtable_schema|SEO Social Airtable Schema]]
- Deploy script: `tools/deploy_seo_social_dept.py`
- Department: [[22 SEO & Social/]]
- Next in pipeline: [[WF-06 - SEO Content Production]]
- Scoring engine: WF-SCORE (engagement/lead/SEO/composite scores 0-100)

## Notes
- Part of 8-workflow SEO + Social Growth Engine
- Pipeline: trend discovery -> content production -> publishing -> engagement monitoring

---
type: workflow
wf_id: WF-06
department: seo-social
n8n_id: 
schedule: "Daily 09:30 SAST"
active: true
dependencies: ["OpenRouter", "Airtable (Content Topics table)", "Blotato"]
owner: ian
last_audit: 2026-04-12
tags: [workflow, seo, social, content]
---

# WF-06 - SEO Content Production

## Purpose
Produces SEO-optimized content based on trends discovered by WF-05. Generates articles, social posts, and distributes via Blotato.

## Trigger
Scheduled: Daily at 09:30 SAST

## Key Nodes
- Airtable Content Topics read
- Claude AI content generation via OpenRouter
- Blotato publishing (9 platforms: TikTok, Instagram, Facebook, etc.)

## Dependencies
- OpenRouter API (Claude Sonnet, 50k daily token budget)
- Airtable marketing base (`apptjjBx34z9340tK`)
- Blotato account

## Related
- Deploy script: `tools/deploy_seo_social_dept.py`
- Department: [[22 SEO & Social/]]
- Previous: [[WF-05 - Trend Discovery]]
- Publishing follows at 10:30 SAST

## Notes
- Engagement monitoring runs every 30 min after publishing
- Lead capture via webhook
- SEO maintenance runs Sunday 02:00 SAST
- Analytics & reporting runs Monday 06:00 SAST

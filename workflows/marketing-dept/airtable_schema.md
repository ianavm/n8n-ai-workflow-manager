# Marketing Department — Airtable Schema Reference

**Base Name:** Marketing Department
**Base ID:** `apptjjBx34z9340tK`

---

## Tables

### 1. Content Calendar

Tracks daily content plan — what to create, for which platforms, and current status.

| Field | Type | Options |
|-------|------|---------|
| Title (primary) | Single Line Text | — |
| Date | Date | ISO format |
| Content Type | Single Select | social_post, blog_post, email_campaign, video_script, carousel |
| Topic | Single Line Text | — |
| Platform | Multiple Select | TikTok, Instagram, Facebook |
| Status | Single Select | Planned, In Production, Draft, Ready, Published, Failed |
| Brief | Long Text | Content brief / context for AI |
| Campaign | Single Line Text | Campaign name |

### 2. Content

Stores AI-generated content pieces with quality scores and hook variations.

| Field | Type | Options |
|-------|------|---------|
| Title (primary) | Single Line Text | Hook / headline |
| Calendar Entry ID | Single Line Text | Reference to Content Calendar record |
| Content Type | Single Select | social_post, blog_post, email_campaign, video_script, carousel |
| Body | Long Text | Full generated content |
| Hashtags | Long Text | Platform hashtags |
| Hook Variations | Long Text | JSON array of 3 hook alternatives |
| Selected Hook | Number | Index of chosen hook (0-2) |
| Status | Single Select | Draft, Ready, Published, Rejected |
| Quality Score | Number | AI self-assessment 1-10 |
| Platform | Single Line Text | Target platform(s) |
| Created At | Date | ISO format |

### 3. Publish Queue

Distribution queue — content waiting to be published to platforms.

| Field | Type | Options |
|-------|------|---------|
| Queue ID (primary) | Single Line Text | Auto-generated ID |
| Content ID | Single Line Text | Reference to Content record |
| Channel | Single Select | blotato_social, gmail_campaign, blog |
| Scheduled For | Date | When to publish |
| Status | Single Select | Queued, Publishing, Published, Failed |
| Published At | Date | Timestamp after publishing |
| Platform Results | Long Text | JSON: per-platform success/failure |

### 4. Distribution Log

Per-platform publishing results for analytics tracking.

| Field | Type | Options |
|-------|------|---------|
| Log ID (primary) | Single Line Text | Auto-generated ID |
| Content ID | Single Line Text | — |
| Platform | Single Line Text | Specific platform name |
| Published At | Date | ISO format |
| Status | Single Select | Success, Failed |
| Response | Long Text | API response or error message |

### 5. System State

Key-value store for orchestrator state and configuration tracking.

| Field | Type | Options |
|-------|------|---------|
| Key (primary) | Single Line Text | State key |
| Value | Long Text | JSON string value |
| Updated At | Date | ISO format |
| Updated By | Single Line Text | Which workflow updated it |

### 6. Research Config

Competitor URLs, RSS feeds, and keywords for intelligence monitoring.

| Field | Type | Options |
|-------|------|---------|
| Key (primary) | Single Line Text | Config key (e.g., `competitor_zapier`) |
| Type | Single Select | competitor, rss_feed, keyword |
| URL | Single Line Text | Target URL or feed URL |
| Label | Single Line Text | Human-readable name |
| Active | Checkbox | Enable/disable monitoring |
| Last Checked | Date | ISO format |
| Notes | Long Text | Additional context |

### 7. Research Insights

AI-analyzed intelligence findings from weekly research runs.

| Field | Type | Options |
|-------|------|---------|
| Title (primary) | Single Line Text | Insight headline |
| Source Type | Single Select | competitor, rss, trend |
| Source | Single Line Text | URL or feed name |
| Summary | Long Text | AI-generated summary |
| Key Themes | Long Text | JSON array of themes |
| Content Opportunities | Long Text | JSON array of suggested topics |
| Relevance Score | Number | 1-10 |
| Week | Single Line Text | ISO week (e.g., "2026-W08") |
| Created At | Date | ISO format |

---

## Table IDs

| Table | ID |
|-------|----|
| Content Calendar | `tblq3SGdZtvbFcfkw` |
| Content | `tblf3QGxX9K1y2h2H` |
| Publish Queue | `tblkS0va5Dw4yPSuq` |
| Distribution Log | `tblLI70ZD0DkJKXvI` |
| System State | `tblMNOdQPXRqQ4ZsY` |
| Research Config | `tblZymxNBj7KPfuqz` |
| Research Insights | `tblPHMyQMedBvcGQz` |

---

## Status Lifecycle

### Content Calendar
```
Planned → In Production → Draft (if quality < 6)
                        → Ready → Published
                        → Failed (on error)
```

### Content
```
Draft → Ready (if quality >= 6) → Published
      → Rejected (manual)
```

### Publish Queue
```
Queued → Publishing → Published
                    → Failed
```

---

## Setup Instructions

1. Create a new Airtable base called "Marketing Department"
2. Copy the base ID from the URL (starts with `app...`)
3. Add to `.env`: `MARKETING_AIRTABLE_BASE_ID=appXXXXXXXXXX`
4. Run: `python tools/setup_marketing_airtable.py --seed`
5. Update `.env` with the table IDs printed by the setup tool
6. Run: `python tools/deploy_marketing_dept.py build`

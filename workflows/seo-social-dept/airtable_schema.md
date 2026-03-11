# SEO + Social Growth Engine — Airtable Schema

> **Base:** Marketing Department (`apptjjBx34z9340tK`)
> **Tables:** 8 new tables added to existing marketing base
> **Created by:** `tools/setup_seo_social_airtable.py`

## Table Overview

| # | Table | Env Var | Used By | Purpose |
|---|-------|---------|---------|---------|
| 8 | Keywords | `SEO_TABLE_KEYWORDS` | WF-05, WF-06 | Keyword database with rankings and scores |
| 9 | SERP Snapshots | `SEO_TABLE_SERP_SNAPSHOTS` | WF-05 | Historical SERP position tracking |
| 10 | Engagement Log | `SEO_TABLE_ENGAGEMENT_LOG` | WF-08 | Social engagement metrics per post |
| 11 | Leads | `SEO_TABLE_LEADS` | WF-09 | Lead database with UTM attribution |
| 12 | SEO Audits | `SEO_TABLE_SEO_AUDITS` | WF-10 | On-page SEO audit results |
| 13 | Analytics Snapshots | `SEO_TABLE_ANALYTICS_SNAPSHOTS` | WF-11 | Performance metrics over time |
| 14 | Scoring Log | `SEO_TABLE_SCORING_LOG` | WF-SCORE | Score history for all entity types |
| 15 | Content Topics | `SEO_TABLE_CONTENT_TOPICS` | WF-05, WF-06, WF-10 | Topic clusters with pillar pages |

> Tables 1-7 are the existing Marketing Department tables (Content Calendar, Content, Publish Queue, Distribution Log, System State, Research Config, Research Insights).

---

## Table 8: Keywords

**Purpose:** Central keyword database tracking search volume, difficulty, rankings, and SEO scores.

| Field | Type | Options | Description |
|-------|------|---------|-------------|
| **Keyword** (primary) | Single Line Text | — | The target keyword |
| Cluster | Single Line Text | — | Topic cluster name |
| Search Volume | Number (int) | — | Monthly search volume |
| Difficulty | Number (int) | 0-100 | Keyword difficulty score |
| Current Rank | Number (int) | — | Current SERP position |
| Previous Rank | Number (int) | — | Last check position |
| Rank Change | Number (int) | — | Delta (positive = improvement) |
| Target URL | URL | — | Page targeting this keyword |
| SEO Score | Number (int) | 0-100 | From scoring engine |
| Status | Single Select | Discovery, Targeting, Ranked, Lost | Keyword lifecycle stage |
| Source | Single Select | GSC, SerpAPI, AI_Generated, Manual | How keyword was discovered |
| Last Checked | Date (ISO) | — | Last SERP check date |
| Created At | Date (ISO) | — | Record creation date |

**Workflows:** WF-05 creates/upserts (matchingColumns: Keyword), WF-06 reads for content briefs.

---

## Table 9: SERP Snapshots

**Purpose:** Historical record of SERP positions per keyword per check.

| Field | Type | Options | Description |
|-------|------|---------|-------------|
| **Snapshot ID** (primary) | Single Line Text | — | Auto-generated UUID |
| Keyword | Single Line Text | — | FK to Keywords table |
| Check Date | Date (ISO) | — | When the check was performed |
| Position | Number (int) | — | SERP rank position |
| URL | URL | — | The URL that ranked |
| Featured Snippet | Checkbox | — | Whether in featured snippet |
| SERP Features | Long Text | — | JSON array of features (PAA, Images, etc.) |
| Competitor URLs | Long Text | — | JSON array of top 10 competitor URLs |
| Device | Single Select | Desktop, Mobile | Device type for check |

**Workflows:** WF-05 creates snapshots after each SERP check.

---

## Table 10: Engagement Log

**Purpose:** Per-post, per-platform engagement metrics for tracking social performance.

| Field | Type | Options | Description |
|-------|------|---------|-------------|
| **Log ID** (primary) | Single Line Text | — | Auto-generated UUID |
| Platform | Single Select | TikTok, Instagram, Facebook, LinkedIn, Twitter, YouTube, Threads, Bluesky, Pinterest | Social platform |
| Post ID | Single Line Text | — | Platform-specific post identifier |
| Content ID | Single Line Text | — | FK to Content table |
| Metric Type | Single Select | like, comment, share, save, reply, mention | Engagement type |
| Count | Number (int) | — | Metric count |
| Engagement Score | Number (int) | 0-100 | From scoring engine |
| Captured At | Date (ISO) | — | When metrics were captured |

**Workflows:** WF-08 creates entries every 30 minutes for published posts.

---

## Table 11: Leads

**Purpose:** Lead database tracking source attribution via UTM parameters and lead scoring.

| Field | Type | Options | Description |
|-------|------|---------|-------------|
| **Lead ID** (primary) | Single Line Text | — | Auto-generated UUID |
| Name | Single Line Text | — | Lead name |
| Email | Email | — | Lead email (used for dedup) |
| Phone | Phone Number | — | Contact phone |
| Company | Single Line Text | — | Company name |
| Source Channel | Single Select | Organic, Social_TikTok, Social_IG, Social_LinkedIn, Social_Twitter, Social_Facebook, Referral, Direct, Paid | Acquisition channel |
| Source URL | URL | — | Landing page with UTM params |
| UTM Campaign | Single Line Text | — | Campaign identifier |
| UTM Medium | Single Line Text | — | Traffic medium |
| UTM Source | Single Line Text | — | Traffic source |
| First Touch Content | Single Line Text | — | FK to Content table |
| Lead Score | Number (int) | 0-100 | From scoring engine |
| Status | Single Select | New, Contacted, Qualified, Converted, Lost | Lead lifecycle stage |
| Notes | Long Text | — | Free-form notes |
| Created At | Date (ISO) | — | Record creation date |

**Workflows:** WF-09 creates (webhook) or updates (batch) leads. Score >= 80 triggers hot lead alert.

---

## Table 12: SEO Audits

**Purpose:** Technical SEO audit results per URL with deterministic scoring.

| Field | Type | Options | Description |
|-------|------|---------|-------------|
| **Audit ID** (primary) | Single Line Text | — | Auto-generated UUID |
| URL | URL | — | Audited page URL |
| Audit Date | Date (ISO) | — | When audit was performed |
| Title Tag | Single Line Text | — | Page title tag content |
| Meta Description | Long Text | — | Meta description content |
| H1 Count | Number (int) | — | Number of H1 tags |
| Word Count | Number (int) | — | Total word count |
| Internal Links | Number (int) | — | Count of internal links |
| External Links | Number (int) | — | Count of external links |
| Broken Links | Long Text | — | JSON array of broken URLs |
| Image Alt Missing | Number (int) | — | Images missing alt text |
| Page Speed Score | Number (int) | 0-100 | Google PageSpeed score |
| Mobile Friendly | Checkbox | — | Mobile responsiveness |
| Schema Markup | Checkbox | — | Has structured data |
| SEO Score | Number (int) | 0-100 | Deterministic score |
| Issues | Long Text | — | JSON array of issues found |
| Recommendations | Long Text | — | AI-generated fix suggestions |

**SEO Score Formula (deterministic, 100 points):**
- Title tag contains primary keyword: 15 pts
- Meta description 120-160 chars: 10 pts
- Exactly 1 H1 tag: 10 pts
- Word count > 1000: 10 pts
- Internal links > 3: 10 pts
- No broken links: 15 pts
- All images have alt text: 10 pts
- Page speed > 90: 10 pts
- Mobile friendly: 5 pts
- Schema markup present: 5 pts

**Workflows:** WF-10 creates audit records weekly.

---

## Table 13: Analytics Snapshots

**Purpose:** Performance metrics snapshots aggregated by period (daily/weekly/monthly).

| Field | Type | Options | Description |
|-------|------|---------|-------------|
| **Snapshot ID** (primary) | Single Line Text | — | Auto-generated UUID |
| Period | Single Select | Daily, Weekly, Monthly | Aggregation period |
| Date | Date (ISO) | — | Snapshot date |
| Platform | Single Line Text | — | Platform or "all" |
| Followers | Number (int) | — | Follower count |
| Posts Published | Number (int) | — | Posts in period |
| Total Engagement | Number (int) | — | Sum of all engagement |
| Engagement Rate | Number (decimal) | — | Percentage |
| Top Post ID | Single Line Text | — | Best performing post |
| Impressions | Number (int) | — | Total impressions |
| Clicks | Number (int) | — | Total clicks |
| Conversions | Number (int) | — | Lead conversions |
| Revenue Attribution | Number (decimal) | — | ZAR revenue attributed |

**Workflows:** WF-11 creates weekly/monthly snapshots.

---

## Table 14: Scoring Log

**Purpose:** Audit trail of all scores computed by the Scoring Engine (WF-SCORE).

| Field | Type | Options | Description |
|-------|------|---------|-------------|
| **Score ID** (primary) | Single Line Text | — | Auto-generated UUID |
| Entity Type | Single Select | Content, Lead, Keyword, Page | What was scored |
| Entity ID | Single Line Text | — | FK to source table |
| Engagement Score | Number (int) | 0-100 | Engagement potential |
| Lead Score | Number (int) | 0-100 | Lead quality |
| SEO Score | Number (int) | 0-100 | SEO health |
| Composite Score | Number (int) | 0-100 | Weighted average |
| Scoring Date | Date (ISO) | — | When scored |
| Reasoning | Long Text | — | AI-generated explanation |

**Scoring Weights:**
- **Content:** likes(0.2) + comments(0.3) + shares(0.3) + saves(0.2)
- **Lead:** source_quality(0.3) + engagement_depth(0.2) + company_fit(0.2) + recency(0.15) + completeness(0.15)
- **Keyword:** volume(0.3) + difficulty_inverse(0.2) + current_rank(0.25) + trend(0.25)
- **Page:** deterministic from SEO audit formula

**Workflows:** WF-SCORE creates entries when called by any other workflow.

---

## Table 15: Content Topics

**Purpose:** Topic cluster management linking pillar pages to target keywords.

| Field | Type | Options | Description |
|-------|------|---------|-------------|
| **Topic** (primary) | Single Line Text | — | Topic cluster name |
| Cluster | Single Line Text | — | Parent cluster |
| Pillar Page URL | URL | — | Main content page URL |
| Target Keywords | Long Text | — | JSON array of keyword strings |
| Content Pieces | Number (int) | — | Count of related content |
| Avg SEO Score | Number (int) | 0-100 | Average across related pages |
| Status | Single Select | Planning, Active, Saturated | Cluster lifecycle |
| Last Updated | Date (ISO) | — | Last modification date |

**Workflows:** WF-05 reads for context, WF-06 reads for briefs, WF-10 updates avg scores.

---

## Cross-Table Relationships

```
Content Topics  --[target keywords]--> Keywords
Keywords        --[snapshots]---------> SERP Snapshots
Content Calendar --[produces]---------> Content --[published via]--> Distribution Log
Distribution Log --[engagement]-------> Engagement Log
Content         --[first touch]-------> Leads
All entities    --[scored by]---------> Scoring Log
Weekly rollups  ----------------------> Analytics Snapshots
Pages           --[audited]-----------> SEO Audits
```

## Setup Instructions

1. Ensure `AIRTABLE_API_TOKEN` and `MARKETING_AIRTABLE_BASE_ID` are set in `.env`
2. Run: `python tools/setup_seo_social_airtable.py --seed`
3. Copy the output table IDs to `.env` (8 `SEO_TABLE_*` variables)
4. Verify tables in Airtable UI
5. Run: `python tools/deploy_seo_social_dept.py build`

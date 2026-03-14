# Paid Advertising Department - Airtable Schema

**Base:** AVM Marketing (`apptjjBx34z9340tK`) in "AVM Only" workspace
**Setup script:** `tools/setup_ads_airtable.py`
**Tables:** 8 (colocated with existing organic marketing tables)

## Table: Ad_Campaigns

Campaign plans and active campaigns across all ad platforms.

| Field | Type | Options |
|-------|------|---------|
| Campaign Name (primary) | singleLineText | |
| Platform | singleSelect | google_ads, meta_ads, tiktok_ads, youtube_ads |
| Objective | singleSelect | Traffic, Conversions, Lead_Gen, Awareness, Video_Views, App_Install |
| Status | singleSelect | Planned, Approved, Launched, Active, Paused, Completed, Rejected |
| Target Audience | multilineText | AI-generated audience description |
| Daily Budget ZAR | number (2dp) | |
| Lifetime Budget ZAR | number (2dp) | |
| Start Date | date (iso) | |
| End Date | date (iso) | |
| External Campaign ID | singleLineText | Platform-specific ID |
| Key Messages | multilineText | JSON array of messaging angles |
| Priority | singleSelect | High, Medium, Low |
| ROAS | number (2dp) | Computed by ADS-07 |
| Total Spend ZAR | number (2dp) | Updated by ADS-04 |
| Total Conversions | number | Updated by ADS-04 |
| Created At | date (iso) | |
| Created By | singleLineText | Workflow name or "manual" |

**Written by:** ADS-01 (Strategy Generator), ADS-03 (Campaign Builder)
**Read by:** ADS-02, ADS-04, ADS-05, ADS-07

---

## Table: Ad_Sets

Ad set / ad group level configuration per campaign.

| Field | Type | Options |
|-------|------|---------|
| Ad Set Name (primary) | singleLineText | |
| Campaign Name | singleLineText | Reference to Ad_Campaigns |
| Platform | singleSelect | google_ads, meta_ads, tiktok_ads |
| Status | singleSelect | Active, Paused, Completed |
| Targeting | multilineText | JSON: age, geo, interests, audiences |
| Daily Budget ZAR | number (2dp) | |
| Bid Strategy | singleSelect | Lowest_Cost, Cost_Cap, Bid_Cap, Target_CPA, Target_ROAS |
| Bid Amount ZAR | number (2dp) | |
| External AdSet ID | singleLineText | Platform-specific ID |
| Placement | singleSelect | Automatic, Feed, Stories, Reels, Search, Display |
| Created At | date (iso) | |

**Written by:** ADS-03 (Campaign Builder)
**Read by:** ADS-04, ADS-05

---

## Table: Ad_Creatives

Ad creative variations with copy, headlines, and quality scores.

| Field | Type | Options |
|-------|------|---------|
| Creative Name (primary) | singleLineText | |
| Campaign Name | singleLineText | Reference to Ad_Campaigns |
| Platform | singleSelect | google_ads, meta_ads, tiktok_ads |
| Ad Format | singleSelect | RSA, Image, Video, Carousel, Collection |
| Status | singleSelect | Draft, Approved, Active, Paused, Retired |
| Headlines | multilineText | JSON array (Google RSA: up to 15 x 30 chars) |
| Descriptions | multilineText | JSON array (Google RSA: up to 4 x 90 chars) |
| Primary Text | multilineText | Main ad copy body |
| CTA | singleSelect | Learn_More, Sign_Up, Contact_Us, Get_Quote, Book_Now |
| Quality Score | number (1dp) | AI-rated 1-10 |
| External Ad ID | singleLineText | Platform-specific ID |
| Parent Creative ID | singleLineText | For recycled variants (ref to original) |
| AB Test Group | singleLineText | e.g., "test_001_A" |
| Created At | date (iso) | |

**Written by:** ADS-02 (Copy Generator), ADS-06 (Creative Recycler)
**Read by:** ADS-03 (Campaign Builder)

---

## Table: Ad_Performance

Daily performance metrics per campaign per platform.

| Field | Type | Options |
|-------|------|---------|
| Performance ID (primary) | singleLineText | Auto-generated |
| Campaign Name | singleLineText | Reference to Ad_Campaigns |
| Platform | singleSelect | google_ads, meta_ads, tiktok_ads |
| Date | date (iso) | |
| Impressions | number | |
| Clicks | number | |
| CTR | number (4dp) | Percentage as decimal |
| Spend ZAR | number (2dp) | |
| Conversions | number | |
| CPA ZAR | number (2dp) | Cost per acquisition |
| ROAS | number (2dp) | Return on ad spend |
| CPM ZAR | number (2dp) | Cost per 1000 impressions |
| CPC ZAR | number (2dp) | Cost per click |
| Video Views | number | |
| Engagement Rate | number (4dp) | |
| Attribution Source | singleSelect | Direct, Assisted, First_Touch, Last_Touch |
| Snapshot Hour | singleLineText | "06:00", "12:00", "18:00", "00:00" |

**Written by:** ADS-04 (Performance Monitor)
**Read by:** ADS-05, ADS-06, ADS-07, ADS-08

---

## Table: Budget_Allocations

Weekly/monthly budget allocation plans and actuals across platforms.

| Field | Type | Options |
|-------|------|---------|
| Allocation Name (primary) | singleLineText | e.g., "Week 12 - 2026" |
| Period Start | date (iso) | |
| Period End | date (iso) | |
| Total Budget ZAR | number (2dp) | |
| Google Ads ZAR | number (2dp) | |
| Meta Ads ZAR | number (2dp) | |
| TikTok Ads ZAR | number (2dp) | |
| Organic Buffer ZAR | number (2dp) | AI token costs etc. |
| Actual Spend ZAR | number (2dp) | Updated by ADS-04 |
| Variance ZAR | number (2dp) | Budget - Actual |
| Status | singleSelect | Planned, Active, Completed |
| AI Recommendation | multilineText | From ADS-05 optimization engine |

**Written by:** ADS-05 (Optimization Engine), ADS-07 (Attribution)
**Read by:** ADS-01, ADS-03, ADS-08

---

## Table: Audience_Segments

Target audience definitions per platform.

| Field | Type | Options |
|-------|------|---------|
| Segment Name (primary) | singleLineText | |
| Platform | singleSelect | google_ads, meta_ads, tiktok_ads, all |
| Type | singleSelect | Interest, Lookalike, Retargeting, Custom, CRM |
| Definition | multilineText | JSON targeting specification |
| Size Estimate | number | |
| Performance Notes | multilineText | |
| External Audience ID | singleLineText | Platform-specific ID |
| Created At | date (iso) | |

**Written by:** ADS-01 (Strategy Generator)
**Read by:** ADS-03 (Campaign Builder)

---

## Table: AB_Tests

A/B test tracking with statistical significance.

| Field | Type | Options |
|-------|------|---------|
| Test Name (primary) | singleLineText | |
| Campaign Name | singleLineText | Reference to Ad_Campaigns |
| Variant A ID | singleLineText | Creative ID |
| Variant B ID | singleLineText | Creative ID |
| Metric | singleSelect | CTR, CPA, ROAS, Conversion_Rate |
| Status | singleSelect | Running, Concluded, Cancelled |
| Winner | singleSelect | A, B, Inconclusive |
| Confidence | number (1dp) | Statistical confidence 0-100% |
| Start Date | date (iso) | |
| End Date | date (iso) | |
| Results | multilineText | JSON with per-variant metrics |

**Written by:** ADS-02 (Copy Generator)
**Read by:** ADS-05, ADS-06

---

## Table: Campaign_Approvals

Human approval queue for campaigns, budgets, and optimizations.

| Field | Type | Options |
|-------|------|---------|
| Approval ID (primary) | singleLineText | Auto-generated |
| Campaign Name | singleLineText | Reference to Ad_Campaigns |
| Request Type | singleSelect | New_Campaign, Budget_Change, Creative_Update, Optimization |
| Requested By | singleLineText | Workflow name |
| Status | singleSelect | Pending, Approved, Rejected |
| Details | multilineText | What needs approval |
| Budget Impact ZAR | number (2dp) | |
| Approval URL | url | Webhook URL for one-click approve |
| Approved By | singleLineText | |
| Approved At | date (iso) | |
| Notes | multilineText | |
| Created At | date (iso) | |

**Written by:** ADS-02, ADS-03, ADS-05
**Read by:** ADS-03 (Campaign Builder)

---

## Safety Thresholds (from config.json)

| Threshold | Value | Enforcement |
|-----------|-------|-------------|
| Daily hard cap | R2,000 | ADS-03 + ADS-05 Code nodes |
| Weekly hard cap | R10,000 | ADS-03 + ADS-05 Code nodes |
| Monthly hard cap | R35,000 | ADS-03 + ADS-05 Code nodes |
| Auto-approve bid change | < 20% | ADS-05 auto-apply threshold |
| Auto-approve budget increase | < R200/day | ADS-05 auto-apply threshold |
| Anomaly Z-score | > 2.0 | ADS-04 triggers alert |

# AnyVision Media — Paid Advertising Strategy

**Date:** 2026-03-04
**Approach:** Start small on Google, scale up, add LinkedIn then Meta
**Starting Budget:** R10,000-R15,000/mo (Google only)

---

## Executive Summary

AnyVision Media has a significant first-mover advantage: **no local SA AI consulting firm is running aggressive paid ads**. The space is dominated by directory sites (Clutch, DesignRush) and global firms with generic messaging. Localized, intent-based campaigns will capture high-quality leads at R500-R1,500 CPL on Google before competitors react.

The existing infrastructure (13 landing pages with UTM capture, WF-09 webhook, BRIDGE scoring/nurture) means leads from paid ads flow directly into the same automated pipeline as organic leads — no extra CRM setup needed.

---

## Phase Plan & Budget Scaling

| Phase | Timeline | Platforms | Monthly Budget | Expected Leads |
|-------|----------|-----------|---------------|----------------|
| **Phase 1** | Month 1-2 | Google Ads | R10,000-R15,000 | 7-15 |
| **Phase 2** | Month 3-4 | Google + LinkedIn | R20,000-R30,000 | 15-25 |
| **Phase 3** | Month 5-6 | Google + LinkedIn + Meta retargeting | R30,000-R45,000 | 25-40 |
| **Phase 4** | Month 7+ | Scale winners, kill losers | Based on ROAS | 40+ |

**Scale-up triggers** (move to next phase when):
- Google CPA is below R1,500 for 2 consecutive weeks
- At least 3 leads converted to booked calls
- Landing page conversion rate > 3%

**Kill triggers** (pause campaign if):
- CPA exceeds 3x target for 14+ days (3x Kill Rule)
- CTR below 2% after 1,000 impressions
- Zero conversions after R5,000 spend

---

## Platform Strategy

### 1. Google Ads (Phase 1 — Primary)

**Why first:** Highest intent. People searching "AI consulting Johannesburg" are actively looking to buy. SA CPC for professional services is R6-R15 (much cheaper than US/UK). Low competition from local AI firms.

**Account structure:**

```
AnyVision Media Google Ads
|
+-- [BRAND] AnyVision Media
|   +-- Brand terms (anyvision media, anyvision, anyvision ai)
|   +-- Budget: R1,000/mo (protect brand, cheap clicks)
|
+-- [SEARCH] AI Consulting - Geo
|   +-- Ad Group: Johannesburg
|   |   Keywords: "ai consulting johannesburg", "ai solutions johannesburg"
|   +-- Ad Group: Cape Town
|   |   Keywords: "ai consulting cape town", "ai solutions cape town"
|   +-- Ad Group: Durban
|   |   Keywords: "ai consulting durban"
|   +-- Ad Group: Pretoria
|   |   Keywords: "ai consulting pretoria"
|   +-- Ad Group: National
|   |   Keywords: "ai consulting south africa", "ai consulting company sa"
|   +-- Budget: R5,000-R7,000/mo
|   +-- Landing pages: City-specific pages (ai-consulting-johannesburg.html, etc.)
|
+-- [SEARCH] AI Services - Intent
|   +-- Ad Group: AI Automation
|   |   Keywords: "ai automation for business", "automate business processes ai"
|   +-- Ad Group: Custom AI
|   |   Keywords: "custom ai solutions", "ai development company"
|   +-- Ad Group: AI Strategy
|   |   Keywords: "ai strategy consulting", "ai readiness assessment"
|   +-- Budget: R3,000-R5,000/mo
|   +-- Landing page: free-ai-assessment.html (lead magnet)
|
+-- [SEARCH] Industry-Specific
|   +-- Ad Group: Accounting + AI
|   |   Keywords: "ai for accounting firms", "automate bookkeeping"
|   +-- Ad Group: Law + AI
|   |   Keywords: "ai for law firms south africa", "legal document automation"
|   +-- Ad Group: Real Estate + AI
|   |   Keywords: "ai for real estate", "property management automation"
|   +-- Budget: R1,000-R3,000/mo (test, scale winners)
|   +-- Landing pages: Service pages or free-ai-assessment.html
|
+-- [RETARGETING] Display
|   +-- Website visitors (7-30 days)
|   +-- Budget: R500-R1,000/mo (add in month 2)
|   +-- Creative: Case study + "Book your free assessment"
```

**Keyword strategy:**

| Priority | Keywords | Match Type | Est. CPC (ZAR) | Landing Page |
|----------|----------|------------|-----------------|-------------|
| P1 | ai consulting johannesburg | Phrase | R10-R25 | /ai-consulting-johannesburg |
| P1 | ai consulting south africa | Phrase | R15-R35 | /index.html |
| P1 | ai consulting cape town | Phrase | R10-R25 | /ai-consulting-cape-town |
| P2 | custom ai solutions south africa | Phrase | R12-R30 | /services/custom-ai-solutions |
| P2 | ai automation for business | Phrase | R8-R20 | /free-ai-assessment |
| P2 | artificial intelligence consulting | Broad | R15-R40 | /index.html |
| P3 | ai for accounting firms | Phrase | R5-R15 | /free-ai-assessment |
| P3 | automate business processes | Broad | R8-R15 | /free-ai-assessment |

**Negative keywords:** jobs, courses, free, internship, salary, tutorial, download, PDF, how to, what is, training (except "ai training for business")

**Bidding:** Start with Maximize Clicks (R20 max CPC cap) for first 2 weeks to gather data, then switch to Maximize Conversions once 15+ conversions tracked.

**Ad extensions:**
- Sitelinks: Free AI Assessment, Our Services, Case Studies, About Us
- Callout: 15 Hours/Week Saved, Free Assessment, SA-Based Team, Custom Solutions
- Structured snippets: Services: AI Strategy, Computer Vision, NLP, Automation
- Location: Johannesburg (primary)
- Call: +27-10-500-0000

---

### 2. LinkedIn Ads (Phase 2 — Add Month 3)

**Why second:** Highest lead quality (20-35% lead-to-SQL rate), but expensive (R1,500-R2,500 CPL). Add once Google proves ROI and you have case study content for social proof.

**Account structure:**

```
AnyVision Media LinkedIn
|
+-- [LEAD GEN] Free AI Assessment
|   +-- Audience: C-suite + IT Directors in SA
|   |   Titles: CEO, CTO, CIO, COO, Managing Director, IT Director, Head of IT
|   |   Company size: 11-500 employees
|   |   Industries: Accounting, Legal, Real Estate, Healthcare, Financial Services
|   |   Geography: South Africa
|   +-- Format: Lead Gen Form (no landing page needed)
|   +-- Offer: "Free 15-Minute AI Readiness Assessment"
|   +-- Budget: R5,000-R8,000/mo
|
+-- [SPONSORED CONTENT] Thought Leadership
|   +-- Audience: Same as above + broader "AI interested" professionals
|   +-- Format: Single image + Thought Leader Ads (from Ian's profile)
|   +-- Content: Case study highlights, AI trends in SA, proof points
|   +-- Budget: R3,000-R5,000/mo
|   +-- Goal: Engagement -> build retargeting audience
|
+-- [RETARGETING] Website Visitors
|   +-- Audience: LinkedIn Matched Audiences (website visitors via Insight Tag)
|   +-- Format: Sponsored Content
|   +-- Content: "See how we helped a JHB firm save 15 hrs/week"
|   +-- Budget: R2,000-R3,000/mo
```

**LinkedIn Lead Gen Form fields:**
- First Name (pre-filled)
- Last Name (pre-filled)
- Email (pre-filled)
- Company Name (pre-filled)
- Job Title (pre-filled)
- "What's your biggest operational bottleneck?" (custom, single-line)

**n8n integration:** LinkedIn Lead Gen Forms can POST to a webhook via Zapier/Make, OR use LinkedIn's API. Build a new n8n workflow (BRIDGE-05?) to:
1. Poll LinkedIn Lead Gen API every 30 minutes
2. Create lead in Airtable SEO Leads table with source=linkedin_ads
3. Trigger BRIDGE-03 scoring
4. Hot leads get immediate alert to Ian

---

### 3. Meta Ads (Phase 3 — Add Month 5)

**Why third:** Lowest lead quality for B2B, but excellent for retargeting and awareness. Very cheap CPMs in SA. Use primarily to retarget warm audiences, not cold prospecting.

**Account structure:**

```
AnyVision Media Meta Ads
|
+-- [RETARGETING] Website Visitors
|   +-- Audience: Pixel-based custom audience (visited any landing page, 30 days)
|   +-- Exclude: Already submitted form (via pixel event)
|   +-- Format: Single image + Carousel (case studies)
|   +-- Budget: R2,000-R3,000/mo
|
+-- [RETARGETING] Video Viewers
|   +-- Audience: Watched 50%+ of any video content
|   +-- Format: Lead form ad -> free assessment
|   +-- Budget: R1,000-R2,000/mo
|
+-- [LOOKALIKE] Top Clients
|   +-- Source: Email list of existing leads/clients (upload to Meta)
|   +-- Audience: 1% lookalike, South Africa
|   +-- Format: Lead form or traffic to free-ai-assessment.html
|   +-- Budget: R2,000-R3,000/mo (test)
```

**Meta is a supporting channel, not primary lead gen.** Its role is:
- Keep AnyVision Media visible to people who already visited the website
- Retarget LinkedIn engagers across Facebook/Instagram
- Build brand awareness cheaply

---

## Creative Strategy

### Google Ads Copy

**Ad 1 — Geo (Johannesburg):**
```
Headline 1: AI Consulting in Johannesburg
Headline 2: Free 15-Min AI Assessment
Headline 3: Custom AI Solutions for SA Business
Description 1: We helped a JHB accounting firm automate 15 hrs/week of manual work. Get your free AI readiness assessment today.
Description 2: Strategy, computer vision, NLP & automation. Local SA team. Book a free call.
```

**Ad 2 — Service (Automation):**
```
Headline 1: Automate Your Business With AI
Headline 2: Save 15+ Hours Per Week
Headline 3: Free AI Assessment — No Obligation
Description 1: AnyVision Media helps SA businesses automate repetitive tasks with custom AI solutions. Real results, not hype.
Description 2: Invoice processing, lead follow-up, document review & more. Get your free 15-min assessment.
```

**Ad 3 — Industry (Accounting):**
```
Headline 1: AI for Accounting Firms in SA
Headline 2: Automate 15 Hrs/Week of Data Entry
Headline 3: Free AI Assessment for Your Firm
Description 1: We helped a Johannesburg accounting firm eliminate manual data entry. See how AI can transform your practice.
Description 2: Invoice processing, reconciliation, collections — all automated. Book your free assessment.
```

### LinkedIn Ad Copy

**Sponsored Content (Thought Leadership):**
```
We helped a Johannesburg accounting firm automate 15 hours/week of manual data entry.

Here's what most SA businesses get wrong about AI:
They think they need a massive budget and a data science team.

Reality? The highest-ROI AI implementations start with the boring stuff — invoice processing, lead follow-up, appointment reminders.

If you're spending more than 10 hours/week on repetitive admin, AI can help.

Reply "ASSESS" or DM me for a free 15-minute AI readiness check.

#AIConsulting #SouthAfrica #BusinessAutomation
```

**Lead Gen Form Ad:**
```
Headline: Is Your Business Ready for AI?
Intro: Most SA businesses waste 10-20 hours/week on tasks AI can handle. Take 15 minutes to find out where AI fits in your operations — completely free.
CTA: Get Free Assessment
```

### Meta Retargeting Creative

**Format:** Carousel (3 cards)
- Card 1: "15 hours/week saved" — accounting case study
- Card 2: "Your free AI assessment" — what's included
- Card 3: "Book now" — CTA to free-ai-assessment.html

---

## Conversion Tracking Setup

### Landing Page Pixels (add to ALL pages)

| Pixel | Code Location | Fires On |
|-------|--------------|----------|
| **Google Ads gtag.js** | `<head>` of all pages | Page load (pageview) |
| **Google Ads conversion** | Form success callback | Form submission |
| **Meta Pixel** | `<head>` of all pages | Page load (PageView) |
| **Meta Lead event** | Form success callback | Form submission |
| **LinkedIn Insight Tag** | `<head>` of all pages | Page load |
| **LinkedIn conversion** | Form success callback | Form submission |

### Server-Side Conversion API (n8n Workflow)

**New workflow: WF-12 — Ad Platform Conversion Sync**

Trigger: Airtable record update in SEO Leads table
When lead status changes to "Responded" or "Booked":

1. Read UTM params from lead record
2. If utm_source = google: POST offline conversion to Google Ads API
3. If utm_source = linkedin: POST conversion to LinkedIn Conversions API
4. If utm_source = facebook/instagram: POST to Meta CAPI
5. Log conversion sync in Airtable

This gives ad platforms **downstream conversion signals** — they learn to optimize for leads that actually convert, not just form fills. Most competitors only track the form submission.

### Event Deduplication

Both client-side pixel AND server-side CAPI will fire on form submission. Use `event_id` parameter (set in JavaScript, passed through webhook to n8n) to deduplicate.

```
Form submit -> fires Meta Pixel Lead event (event_id: "lead_<timestamp>_<email_hash>")
Form submit -> fires webhook to WF-09 (includes event_id in payload)
WF-09 -> stores event_id in Airtable
WF-12 -> sends CAPI event with same event_id
Meta deduplicates: only counts 1 conversion
```

---

## n8n Integration Architecture

```
                         +-----------------+
    Google Ads --------->|                 |
    LinkedIn Ads ------->|  Landing Pages  |---> UTM params captured
    Meta Ads ----------->|  (13 pages)     |
                         +-----------------+
                                |
                    Form submit + pixel fires
                                |
                    +-----------v-----------+
                    |   WF-09 Webhook       |
                    |   (Lead Capture)      |
                    +-----------+-----------+
                                |
                    +-----------v-----------+
                    |   Airtable            |
                    |   SEO Leads table     |
                    +-----------+-----------+
                                |
              +-----------------+------------------+
              |                 |                   |
    +---------v------+  +------v--------+  +-------v--------+
    | BRIDGE-03      |  | BRIDGE-04     |  | WF-12 (NEW)    |
    | Lead Scoring   |  | Nurture       |  | CAPI Sync      |
    | Hot/Warm/Cold  |  | Email drip    |  | Google/Meta/LI  |
    +---------+------+  +---------------+  +-------+--------+
              |                                     |
    +---------v------+                    +---------v--------+
    | Hot Lead Alert |                    | Offline          |
    | -> Ian (1 hr)  |                    | Conversions      |
    | + Calendar     |                    | -> Optimize bids |
    +----------------+                    +------------------+
```

**No new CRM needed.** Paid leads flow into the exact same pipeline as scraper and organic leads. The only additions are:
1. Pixel code on landing pages (JavaScript)
2. WF-12 workflow for server-side conversion sync

---

## KPI Targets

| Metric | Month 1 (Baseline) | Month 3 | Month 6 |
|--------|-------------------|---------|---------|
| **Google CPC** | R10-R25 | R8-R20 | R6-R15 |
| **Google CTR** | 5%+ | 7%+ | 9%+ |
| **Google CPL** | R1,000-R1,500 | R700-R1,000 | R500-R800 |
| **LinkedIn CPL** | — | R1,500-R2,500 | R1,200-R2,000 |
| **Meta CPL** | — | — | R400-R800 |
| **Blended CPL** | R1,000-R1,500 | R900-R1,200 | R600-R900 |
| **Lead-to-Booked Call %** | 10% | 15% | 20% |
| **Booked-to-Client %** | 20% | 25% | 30% |
| **Monthly leads (paid)** | 7-15 | 15-25 | 25-40 |
| **Monthly spend** | R10,000-R15,000 | R20,000-R30,000 | R30,000-R45,000 |

---

## Implementation Roadmap

### Week 1-2: Foundation
- [ ] Create Google Ads account
- [ ] Install Google gtag.js on all 13 landing pages
- [ ] Install Meta Pixel on all 13 landing pages
- [ ] Install LinkedIn Insight Tag on all 13 landing pages
- [ ] Set up conversion events (form submission) on all platforms
- [ ] Build Google Ads campaigns (Brand + Geo + Services)
- [ ] Write ad copy (3 responsive search ads per ad group)
- [ ] Set up negative keyword list
- [ ] Configure Enhanced Conversions (Google)

### Week 3-4: Google Launch
- [ ] Launch Google Ads (Maximize Clicks, R20 max CPC)
- [ ] Monitor daily: search terms, CPC, CTR, conversions
- [ ] Add negative keywords from search term report
- [ ] Verify conversion tracking fires correctly
- [ ] Build WF-12 (CAPI sync workflow) in n8n

### Week 5-8: Optimize Google, Prep LinkedIn
- [ ] Switch to Maximize Conversions (once 15+ conversions)
- [ ] Kill ad groups with CPA > 3x target
- [ ] Scale ad groups with CPA < target (20% budget increase)
- [ ] Set up LinkedIn Campaign Manager
- [ ] Build LinkedIn audiences (C-suite, IT Directors in SA)
- [ ] Create Lead Gen Form
- [ ] Launch LinkedIn campaigns

### Week 9-12: Add Meta, Full Funnel
- [ ] Set up Meta Business Manager
- [ ] Build retargeting audience (website visitors from Google/LinkedIn)
- [ ] Launch Meta retargeting campaigns
- [ ] Upload client email list -> create Lookalike audience
- [ ] Full-funnel optimization: Google captures intent, LinkedIn targets decision-makers, Meta retargets
- [ ] Monthly performance review -> 70/20/10 budget rebalance

---

## Remaining Blocker

| # | Blocker | Action Required |
|---|---------|----------------|
| 1 | **Google Ads account** | Ian creates at ads.google.com |
| 2 | **Meta Business Manager** | Ian creates at business.facebook.com |
| 3 | **LinkedIn Campaign Manager** | Ian creates via linkedin.com/campaignmanager |
| 4 | **Phone number** | Confirm +27-10-500-0000 is correct for call extensions |
| 5 | **Billing** | Credit card linked to each ad platform |

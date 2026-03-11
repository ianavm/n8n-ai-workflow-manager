# 1,000 Leads in 27 Days — Full Execution Plan

> **Goal:** 1,000 qualified leads by March 31, 2026 -> 10 paying clients
> **Company:** AnyVision Media (AI consulting, South Africa)
> **Owner:** Ian Immelman

---

## EXECUTIVE SUMMARY

We have a fully automated lead generation pipeline already built but running at ~20% capacity with critical gaps. This plan fixes the gaps, scales the scraper, connects the landing pages, launches paid ads, and adds Cape Town + Durban + Pretoria coverage. Projected: **1,200-1,800 raw leads, 800-1,000 after dedup.**

---

## PHASE 1: FIX CRITICAL GAPS (Day 1-2)

### Task 1.1: Connect Landing Page Forms to n8n Webhook
**Problem:** The Netlify contact form on www.anyvisionmedia.com submits to Netlify Forms ONLY. Inbound leads never reach Airtable or trigger WF-09 lead capture.

**Action:** Add JavaScript to all landing pages that POSTs form data to the WF-09 webhook alongside Netlify's native handling.

```
Webhook URL: https://ianimmelman89.app.n8n.cloud/webhook/seo-social/lead-capture
Method: POST
Payload: { email, name, company, phone, message, page_url, utm_source, utm_medium, utm_campaign }
```

**Files to update:**
- `landing-pages/deploy/index.html`
- `landing-pages/deploy/ai-consulting-johannesburg.html`
- `landing-pages/deploy/ai-consulting-cape-town.html`
- `landing-pages/deploy/ai-consulting-durban.html`
- `landing-pages/deploy/services/ai-strategy-consulting.html`
- `landing-pages/deploy/services/ai-integration.html`
- `landing-pages/deploy/services/computer-vision.html`
- `landing-pages/deploy/services/custom-ai-solutions.html`
- `landing-pages/deploy/services/nlp-llm-solutions.html`
- `landing-pages/deploy/services/ai-training.html`

Also add UTM parameter capture from URL query string so paid ad clicks are attributed.

### Task 1.2: Enable Scraper Pagination (Page 2)
**Problem:** The "Places Page 2" node in the lead scraper workflow is disabled. Each run only gets 20 results instead of 40.

**Action:** Enable the pagination node in the live workflow. This doubles throughput immediately.

```
Workflow ID: uq4hnH0YHfhYOOzO
Node to enable: "Places Page 2"
```

### Task 1.3: Add Cold Lead Re-engagement
**Problem:** BRIDGE-03 scores leads as Cold (<50) but never contacts them again. These are wasted leads.

**Action:** Modify BRIDGE-04 nurture workflow to include a single "cold reactivation" email for Cold leads that are at least 7 days old. One touch — if no response, mark as "Exhausted".

### Task 1.4: Fix WF-09 Stale Lead Path
**Problem:** The daily batch in WF-09 counts stale leads (New status, older than 1 day) but takes no action.

**Action:** Route stale inbound leads to BRIDGE-03 for scoring so they enter the nurture pipeline.

---

## PHASE 2: SCALE THE SCRAPER (Day 2-4)

### Task 2.1: Expand Geographic Coverage
**Current:** 24 Gauteng areas only.

**Add these cities/areas (60+ new locations):**

**Cape Town Metro (15 areas):**
Cape Town CBD, Sea Point, Green Point, Camps Bay, Claremont, Constantia, Bellville, Durbanville, Stellenbosch, Paarl, Somerset West, Milnerton, Century City, Woodstock, Observatory

**Durban Metro (12 areas):**
Durban CBD, Umhlanga, Ballito, Pinetown, Westville, Hillcrest, Kloof, Durban North, Berea, Musgrave, La Lucia, Gateway

**Pretoria/Tshwane (8 areas, some already covered):**
Pretoria East, Lynnwood, Waterkloof, Montana, Silverton, Arcadia, Sunnyside, Irene

**Other metros (10 areas):**
Bloemfontein, Port Elizabeth/Gqeberha, East London, Nelspruit/Mbombela, Polokwane, Rustenburg, Pietermaritzburg, Richards Bay, George, Stellenbosch

**New total:** 24 existing + ~45 new = ~69 areas
**New combinations:** 20 industries x 69 areas = 1,380 unique searches

### Task 2.2: Increase Scraper Frequency
**Current:** Every 6 hours (4 runs/day)

**Change to:** Every 2 hours (12 runs/day) for the first 2 weeks, then back to every 6 hours.

**Daily capacity with changes:**
- 40 results/run (page 2 enabled) x 12 runs/day = 480 raw leads/day
- After dedup (~60% unique): ~288 unique leads/day
- Over 14 days at this rate: ~4,032 raw, ~2,400 unique
- Conservative estimate after email validation: **1,200-1,500 usable leads**

### Task 2.3: Add High-Value Industry Categories
**Add these 10 categories to the rotation:**
```
engineering firm, architecture firm, IT company, software development,
event management, travel agency, private school, freight forwarding,
manufacturing company, food processing
```

**New total:** 30 industries x 69 areas = 2,070 unique combinations

### Task 2.4: Deploy Updated Scraper
Use `tools/fix_lead_scraper_gauteng.py` as template to build a new fix script that:
1. Expands the area list to all 69 locations
2. Adds 10 new industry categories
3. Enables page 2 pagination
4. Sets schedule to every 2 hours

---

## PHASE 3: LANDING PAGE + SEO OPTIMIZATION (Day 3-5)

### Task 3.1: SEO Audit All Landing Pages
Run `/seo audit https://www.anyvisionmedia.com` and fix critical issues:
- Meta titles/descriptions optimized for "AI consulting South Africa"
- Schema markup (LocalBusiness + Service) on all pages
- Internal linking between city pages and service pages
- Core Web Vitals fixes

### Task 3.2: Add More Geo Landing Pages
Create landing pages for:
- `ai-consulting-pretoria.html`
- `ai-consulting-bloemfontein.html`
- `ai-consulting-port-elizabeth.html`

These pages will be ad campaign destinations AND organic SEO targets.

### Task 3.3: Create a Lead Magnet Page
Build `landing-pages/deploy/free-ai-assessment.html`:
- "Free AI Readiness Assessment for Your Business"
- Simple form: Name, Email, Company, Industry, Biggest Pain Point
- Form POSTs to WF-09 webhook with utm_campaign="lead-magnet"
- This becomes the primary CTA for paid ads

---

## PHASE 4: PAID ADS CAMPAIGN (Day 4-10)

### Task 4.1: Google Ads Campaign Plan
Run `/ads plan local-service` to generate a full campaign architecture.

**Recommended structure:**
- **Campaign 1: Search — AI Consulting (Johannesburg)**
  - Keywords: "AI consulting Johannesburg", "business automation South Africa", "AI solutions for business"
  - Landing page: `/ai-consulting-johannesburg.html`
  - Budget: R200/day (~$11/day)

- **Campaign 2: Search — AI Consulting (Cape Town)**
  - Keywords: "AI consulting Cape Town", "automation Cape Town"
  - Landing page: `/ai-consulting-cape-town.html`
  - Budget: R150/day

- **Campaign 3: Search — AI Services (National)**
  - Keywords: "custom AI solutions", "workflow automation South Africa", "AI integration services"
  - Landing page: `/free-ai-assessment.html`
  - Budget: R150/day

**Total Google Ads budget:** ~R500/day (~R15,000/month, ~$830/month)
**Expected:** 50-100 clicks/day at R5-10 CPC = 5-15 leads/day = **150-450 leads/month**

### Task 4.2: Meta Ads Campaign (Optional, Budget Permitting)
- **Campaign:** Lead Gen form ad targeting SA business owners
- Audience: Business owners, 25-55, Johannesburg/Cape Town/Durban, interested in technology/business software
- Creative: Carousel showing AI automation benefits with case study stats
- Budget: R200/day
- Expected: 10-20 leads/day = **300-600 leads/month**

### Task 4.3: LinkedIn Ads Campaign (Optional, Higher Quality)
- **Campaign:** Sponsored content targeting SA decision-makers
- Targeting: Job titles (CEO, CTO, COO, MD), Company size 10-500, South Africa
- Creative: "How SA businesses are saving 10+ hours/week with AI automation"
- Budget: R300/day (LinkedIn is expensive but high-quality B2B leads)
- Expected: 3-8 leads/day = **90-240 leads/month**

---

## PHASE 5: OUTREACH OPTIMIZATION (Day 5-10)

### Task 5.1: Improve Cold Email Copy
Update `templates/lead_email_prompt.txt` to:
- Reference specific industry pain points (not generic)
- Include a concrete stat: "We helped a Johannesburg accounting firm automate 15 hours/week of manual data entry"
- CTA: "Reply YES for a free 15-minute AI assessment" (low friction)
- A/B test: version with case study vs version with question hook

### Task 5.2: Add Follow-Up Email Sequence
Current: 1 cold email, then Bridge-04 nurture (3 emails over 7 days) for Warm only.

**Add:** A 2nd follow-up email for ALL leads who don't respond to the initial cold email after 4 days. Use the existing `add_followup_fields.py` script as reference.

### Task 5.3: Deploy Email Warm-Up (If New Domain/Gmail)
If using a new sending domain, ensure:
- SPF, DKIM, DMARC records configured
- Start with 20 emails/day, ramp to 100 over 2 weeks
- Monitor bounce rate — pause if >5%

---

## PHASE 6: ACTIVATE SEO + SOCIAL ENGINE (Day 5-15)

### Task 6.1: Activate SEO-Social Workflows
Ensure all 8 SEO-Social workflows are active:
- WF-05: Trend Discovery (Mon/Thu 6:00)
- WF-06: SEO Content Production (daily 9:30)
- WF-07: Publishing (daily 10:30)
- WF-08: Engagement Monitoring (every 30min)
- WF-09: Lead Capture (webhook — must be active)
- WF-10: SEO Maintenance (Sun 2:00)
- WF-11: Analytics & Reporting (Mon 6:00)
- WF-SCORE: Scoring sub-workflow

### Task 6.2: Content Topics for Lead Gen
Seed content calendar with high-intent topics:
- "5 Ways AI Automation Saves SA Businesses R50,000/month"
- "Why Johannesburg Companies Are Switching to AI Workflows"
- "AI for Accounting Firms: Automate Invoicing, Collections, and Reconciliation"
- "The SME Guide to AI Integration in South Africa (2026)"

### Task 6.3: Social Publishing via Blotato
Ensure Blotato connections are active for content distribution across 9 platforms.

---

## PROJECTED RESULTS

| Channel | Raw Leads | After Dedup | Timeline |
|---------|-----------|-------------|----------|
| **Scraper (expanded)** | 4,000+ | 1,200-1,500 | Days 3-27 |
| **Google Ads** | 150-450 | 120-400 | Days 7-27 |
| **Landing page inbound (organic)** | 20-50 | 20-50 | Days 3-27 |
| **Social/content** | 10-30 | 10-30 | Days 10-27 |
| **Meta Ads (optional)** | 300-600 | 250-500 | Days 10-27 |
| **LinkedIn Ads (optional)** | 90-240 | 80-200 | Days 10-27 |
| **TOTAL (without paid)** | 4,180+ | **1,350-1,980** | |
| **TOTAL (with Google Ads)** | 4,330+ | **1,470-2,380** | |

### Conversion Funnel (Conservative)
```
1,000 qualified leads
  -> 5% reply rate (cold email + nurture) = 50 conversations
  -> 3% inbound conversion (ads + organic) = 15-30 conversations
  -> Total conversations: 65-80
  -> 15% close rate = 10-12 clients
```

---

## EXECUTION CHECKLIST

### Day 1-2 (Fix Gaps)
- [ ] Connect all landing page forms to WF-09 webhook
- [ ] Enable scraper pagination (Page 2 node)
- [ ] Add cold lead re-engagement to BRIDGE-04
- [ ] Fix WF-09 stale lead routing

### Day 2-4 (Scale Scraper)
- [ ] Build fix script to expand scraper to 69 areas + 30 industries
- [ ] Deploy updated scraper with 2-hour schedule
- [ ] Verify Airtable dedup is working with higher volume
- [ ] Monitor Google Places API quota usage

### Day 3-5 (Landing Pages + SEO)
- [ ] Run /seo audit on www.anyvisionmedia.com
- [ ] Fix critical SEO issues (meta, schema, CWV)
- [ ] Create free-ai-assessment lead magnet page
- [ ] Create Pretoria geo landing page
- [ ] Deploy to Netlify

### Day 4-10 (Paid Ads)
- [ ] Run /ads plan local-service for campaign architecture
- [ ] Set up Google Ads account (if not exists)
- [ ] Create 3 search campaigns with geo-targeting
- [ ] Set up conversion tracking (form submissions -> Google Ads)
- [ ] Launch with R500/day budget
- [ ] Monitor CPC, CTR, conversion rate daily

### Day 5-10 (Outreach Optimization)
- [ ] Update cold email prompt template with industry-specific hooks
- [ ] Add 2nd follow-up email to scraper workflow (4 days after initial)
- [ ] Verify email deliverability (SPF, DKIM, DMARC)
- [ ] Monitor bounce rate and adjust sending volume

### Day 5-15 (SEO + Social)
- [ ] Verify all 8 SEO-Social workflows are active
- [ ] Seed 10 content topics in Content Calendar Airtable
- [ ] Verify Blotato connections for social publishing
- [ ] Monitor engagement metrics in WF-08

### Day 15-27 (Monitor + Optimize)
- [ ] Daily: Check lead counts in Airtable, respond to Hot leads within 1 hour
- [ ] Daily: Monitor ad spend vs leads, pause underperforming keywords
- [ ] Weekly: Review nurture email open/reply rates
- [ ] Weekly: A/B test cold email subject lines
- [ ] Day 20: Assess progress, double down on best-performing channel

---

## BUDGET SUMMARY

| Item | Monthly Cost |
|------|-------------|
| Google Places API | ~R50 (~$3) |
| Google Ads (required) | R15,000 (~$830) |
| Meta Ads (optional) | R6,000 (~$330) |
| LinkedIn Ads (optional) | R9,000 (~$500) |
| OpenRouter AI (email gen) | ~R500 (~$28) |
| **Minimum (scraper + Google Ads)** | **~R15,550** |
| **Full stack (all channels)** | **~R30,550** |

---

## WHAT I NEED FROM YOU (IAN)

1. **Google Ads account access** — do you have one? If not, I'll help set it up
2. **Ad budget approval** — minimum R15,000/month for Google Ads
3. **Airtable PAT update** — both credentials (`ZyBrcAO6fps7YB3u` and `K8t2NtJ89DLLh64j`) need SEO Leads table access added in n8n UI
4. **Email sending limits** — what's the daily Gmail sending limit on ian@anyvisionmedia.com? (Free Gmail = 500/day, Workspace = 2,000/day)
5. **Response commitment** — Hot leads need a reply within 1 hour during business hours. Can you commit to this, or should we set up auto-booking (Calendly/Cal.com link)?
6. **Meta/LinkedIn decision** — want to run these too, or start with Google Ads only?

---

## HOW TO EXECUTE THIS PLAN

Paste this entire plan into a new Claude Code session with the instruction:

```
Execute the 1,000 Leads plan from LEAD_GEN_1000_PLAN.md. Start with Phase 1 (fix critical gaps). Work through each phase sequentially. Ask me for decisions where marked. Let's go.
```

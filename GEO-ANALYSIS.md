# GEO Analysis — AnyVision Media
**Date:** 2026-03-04
**URL:** https://www.anyvisionmedia.com

---

## GEO Readiness Score: 76/100

| Dimension | Score | Notes |
|-----------|-------|-------|
| Citability | 72/100 | Passages too brief (28-54 words vs 134-167 optimal) |
| Structural Readability | 80/100 | Good heading hierarchy, needs question-based H2s |
| Multi-Modal Content | 65/100 | Missing video, infographics, interactive tools |
| Authority & Brand Signals | 85/100 | 47 brand mentions, strong entity clarity |
| Technical Accessibility | 95/100 | Excellent SSR, all content pre-rendered |
| Schema & Structured Data | 90/100 | Comprehensive JSON-LD, now with telephone + founder fixes |
| AI Crawler Access | 70/100 | Permissive robots.txt but no explicit AI crawler directives |

---

## Platform Breakdown

| Platform | Score | Expected Citation Likelihood |
|----------|-------|------------------------------|
| Google Gemini/AIO | 82/100 | 75% |
| ChatGPT/OpenAI | 74/100 | 72% |
| Perplexity | 72/100 | 68% |
| Claude AI | 73/100 | 70% |

---

## AI Crawler Access Status

**Current robots.txt:** Permissive (no explicit blocks)
- GPTBot: Allowed (no directive)
- ClaudeBot: Allowed (no directive)
- PerplexityBot: Allowed (no directive)
- OAI-SearchBot: Allowed (no directive)

**Recommendation:** Add explicit `User-agent` entries for all AI crawlers to signal intent.

---

## llms.txt Status

**Status:** NOW IMPLEMENTED (deployed to `/llms.txt`)
- Covers all services, locations, key facts
- Links to all city and service pages
- Includes founder name, proof point, free assessment CTA

---

## Brand Mention Analysis: 85/100

- 47 explicit brand mentions on homepage
- Entity clarity: EXCELLENT (95/100) — consistent "AnyVision Media" naming
- Context richness: EXCELLENT (92/100) — AI consulting + South Africa + specific services
- sameAs: LinkedIn (now added to schema)
- **Gap:** No Wikipedia, Reddit, or YouTube presence yet

---

## Passage-Level Citability: 72/100

Current service descriptions average 28-54 words per passage — well below the 134-167 word optimal range for AI citation.

**Best candidates for citation:** FAQ answers (already well-structured Q&A format)

**Action needed:** Expand 6 service descriptions to 150-167 word self-contained passages with specific statistics and outcomes.

---

## Server-Side Rendering: 95/100

- Full HTML pre-rendering confirmed (static HTML on Netlify)
- All structured data pre-rendered in `<script type="application/ld+json">`
- All meta tags server-rendered
- No JavaScript required for content access
- AI crawlers can fully parse all content

---

## Top 5 Highest-Impact Changes

| # | Change | Impact | Effort | GEO Improvement |
|---|--------|--------|--------|-----------------|
| 1 | ~~Deploy llms.txt~~ DONE | 9/10 | 1/10 | +8-12 pts |
| 2 | Add explicit robots.txt AI crawler directives | 7/10 | 1/10 | +5-8 pts |
| 3 | Expand service passages to 150-167 words | 8/10 | 5/10 | +6-10 pts |
| 4 | ~~Fix schema: telephone, founder, sameAs~~ DONE | 6/10 | 2/10 | +4-7 pts |
| 5 | Create AI-optimized case study pages | 6/10 | 5/10 | +3-6 pts |

---

## Schema Recommendations

1. **BreadcrumbList** — Already implemented on new city pages
2. **LocalBusiness** — Now includes telephone on all 6 city pages
3. **Organization** — Founder fixed to `Person` type, sameAs added
4. **AggregateRating** — Present on homepage (4.9/5, 50 reviews)
5. **Service** — Present on service pages
6. **FAQPage** — Should be added to city pages with local Q&A

---

## Content Reformatting Suggestions

1. **Service descriptions** — Expand from ~50 words to 150-167 words each
2. **Case studies** — Create dedicated pages with CreativeWork schema
3. **AI concepts glossary** — Add definition blocks ("What is [topic]?") for AI citation
4. **Question-based headings** — Convert H2s to "How does AI help [industry]?" format
5. **Comparison tables** — Add data tables for AI ROI by industry

---

## Implementation Status

| Task | Status |
|------|--------|
| llms.txt deployed | DONE |
| Schema telephone fixes (6 pages) | DONE |
| Founder schema fix (index.html) | DONE |
| sameAs links added | DONE |
| Explicit robots.txt AI directives | TODO |
| Expand service passages | TODO |
| Case study pages | TODO |
| FAQ schema on city pages | TODO |

**30-Day Target:** 88-92/100
**90-Day Target:** 92-96/100

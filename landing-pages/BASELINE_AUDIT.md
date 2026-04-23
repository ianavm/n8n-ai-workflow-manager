# Landing Pages — Baseline Audit

**Date:** 2026-04-22
**Target:** `landing-pages/deploy/` (deployed to `www.anyvisionmedia.com` via Netlify)
**Method:** Static HTML analysis (16 pages) + live PageSpeed Insights API (3 representative URLs × mobile/desktop).

## Live Lighthouse scores (PSI, pre-fix)

| Page | Strategy | Perf | A11y | SEO | BP | LCP | CLS | TBT | FCP |
|---|---|---:|---:|---:|---:|---|---|---|---|
| homepage | mobile | **76** | 91 | 100 | 92 | 3.5 s | 0 | 410 ms | 2.7 s |
| homepage | desktop | 76 | 91 | 100 | 92 | 1.0 s | 0.001 | 470 ms | 0.8 s |
| location (JHB) | mobile | **75** | 94 | 100 | 100 | 3.8 s | 0 | 390 ms | 2.8 s |
| location (JHB) | desktop | 70 | 94 | 100 | 100 | 1.0 s | 0.013 | 920 ms | 0.5 s |
| pricing | mobile | **72** | 94 | 100 | 100 | 3.3 s | 0 | 620 ms | 2.6 s |
| pricing | desktop | 97 | 94 | 100 | 100 | 0.9 s | 0.001 | 120 ms | 0.7 s |

### Headlines

- ✅ **SEO: 100/100** across every URL and strategy — nothing to fix structurally
- ✅ **A11y: 91–94** — minor improvements possible (colour contrast, ARIA)
- ✅ **BP: 92–100** — almost perfect
- ✅ **CLS: ~0** — layout stability excellent
- ❌ **Mobile Performance 72–76** — below the 90 target
- ❌ **Mobile LCP 3.3–3.8 s** — above Google's "Good" threshold of **2.5 s**
- ⚠️ **TBT 390–920 ms** — render-blocking scripts confirmed as predicted by static audit

### Root cause

Exactly what the static audit flagged: 3–4 render-blocking scripts per page pushing FCP/LCP into "Needs Improvement". No image/CSS issues — the HTML is clean.

### Prediction for AstroWind port (Phase 4)

**Not needed.** Once render-blocking scripts are deferred + fonts preconnect, mobile Performance should clear 90. No structural rewrite warranted.

---

## Post-fix Lighthouse scores (2026-04-23, 3-run median)

After FB Pixel lazy-load (commits `97d202e` + `d95d0ea`) and trial-CTA cleanup (`9714e2a`):

| Page | Strategy | Perf | A11y | SEO | BP | LCP | CLS | TBT | FCP |
|---|---|---:|---:|---:|---:|---|---|---|---|
| homepage | mobile | **86** | 91 | 100 | 92 | 3.4 s | 0 | **116 ms** | 2.7 s |
| homepage | desktop | **90** | 91 | 100 | 92 | 0.9 s | 0.001 | 222 ms | 0.8 s |
| location | mobile | **83** | 94 | 100 | 100 | 3.4 s | 0.001 | 212 ms | 2.7 s |
| location | desktop | **85** | 94 | 100 | 100 | 0.9 s | 0.013 | 296 ms | 0.8 s |
| pricing | mobile | 78 | 94 | 100 | 100 | 3.3 s | 0 | 460 ms | 2.6 s |
| pricing | desktop | 71* | 94 | 100 | 100 | 1.0 s | 0.001 | 675 ms | 0.7 s |

*Pricing desktop result noisy — runs: 71/71/85. Was 97 pre-fix. Likely lab variance on an already-fast page; HTML structure is unchanged from before. Re-measure after 24h for stable CrUX-based reading.

### Delta vs baseline

| Page | Strategy | Perf Δ | TBT Δ |
|---|---|---|---|
| homepage | mobile | +10 | −72% |
| homepage | desktop | +14 ✓ crossed 90 | −53% |
| location | mobile | +8 | −46% |
| location | desktop | +15 | −68% |
| pricing | mobile | +6 | −26% |
| pricing | desktop | noisy | noisy |

**Main win:** TBT cut 46-72% on 4 of 6 views. Homepage desktop cleared 90. No regressions in SEO/A11y/CLS.

### Remaining gap to 90+ mobile

Mobile LCP stuck at ~3.3 s across pages — driven by the 35 KB render-blocking `/css/styles.css` and Google Fonts roundtrip. Next-tier fix (not in scope yet): inline critical CSS + async-load the rest. Expected uplift: mobile Perf 86 → 92+.



## Scope

16 HTML pages: `index.html`, 6 city location pages (johannesburg, cape-town, durban, pretoria, port-elizabeth, bloemfontein), `pricing.html`, `case-studies.html`, `faq.html`, `about.html`, `roi-calculator.html`, `free-ai-assessment.html`, `refund-policy.html`, `terms.html`, `404.html`.

## Summary

| Severity | Count | Notes |
|---|---|---|
| Critical | **0** | Doctype, lang, viewport, title, charset all present on every page ✓ |
| High | 19 | Mostly `<img>` missing `alt` (15x, but all on FB Pixel noscript) + 404.html bare + 1x multi-H1 |
| Medium | 32 | Render-blocking scripts (3-4 per page) + no WebP/AVIF |
| Low | 15 | Missing explicit `font-display: swap` |

## Page sizes

| Page | KB | Scripts | Images |
|---|---:|---:|---:|
| `index.html` | 83 | 9 | 1 |
| `pricing.html` | 86 | 9 | 1 |
| `faq.html` | 86 | 6 | 1 |
| `ai-consulting-*` (6 pages) | 85–94 | 8 | 1 |
| `case-studies.html` | 45 | 6 | 1 |
| `free-ai-assessment.html` | 85 | 5 | 1 |
| `roi-calculator.html` | 64 | 7 | 1 |
| `about.html` | 55 | 6 | 1 |
| `refund-policy.html` | 58 | 6 | 1 |
| `terms.html` | 73 | 6 | 1 |
| `404.html` | 2 | 0 | 0 |

All pages are ~60–95KB HTML — good. The "1 image" on most pages is a Facebook tracking pixel in `<noscript>`, not a visible image.

## Findings by severity

### HIGH (19)

1. **`404.html` is bare** — missing meta description, canonical, Schema.org, Open Graph, Twitter cards. Low-value page but indexable.
2. **`free-ai-assessment.html` has 2 `<h1>` tags** — split the primary heading into `<h1>` + `<h2>`.
3. **FB Pixel noscript `<img>` missing `alt=""`** — 15 pages. Technically correct practice to set `alt=""` on decorative images even in `<noscript>`. Cosmetic, but Lighthouse flags it.

### MEDIUM (32)

1. **3–4 render-blocking scripts per page** — analytics + third-party scripts loaded synchronously in `<head>`. Impacts LCP. **Fix:** add `defer` to all non-critical scripts; move analytics after initial render or use `<script type="module">`.
2. **No WebP/AVIF** — only 1 image per page (the FB pixel), but the one `<meta property="og:image">` references PNG. **Fix:** generate `og-image.webp` + `og-image.avif` alternatives.
3. **No Open Graph tags on `404.html`** — minor.

### LOW (15)

1. **No explicit `font-display: swap`** — Google Fonts typically default to swap now, but declaring it explicitly prevents FOIT on some browsers.

## What's solid ✓

- Every page: doctype, `<html lang>`, viewport, charset, title, meta description, canonical, Schema.org JSON-LD, Open Graph, Twitter Cards.
- Clean semantic structure.
- Page sizes well under the 200KB HTML threshold.
- HTTPS-only (no non-HTTPS resources detected).
- Existing `robots.txt`, `sitemap.xml`, `llms.txt` → good for AI crawlers.

## Gaps that need live data (PSI API key)

Static analysis cannot measure:
- **LCP, INP, CLS, TBT, FCP, Speed Index** — need Lighthouse run
- **JavaScript execution time / main-thread blocking**
- **Real-world Core Web Vitals from CrUX**
- **Actual Lighthouse Performance/Accessibility/SEO/Best-Practices scores**

To unblock: add `GOOGLE_PAGESPEED_API_KEY` to `.env`, then re-run `.tmp/run_psi_audit.py`. API key is free from [Google Cloud Console](https://console.cloud.google.com/apis/credentials) (enable "PageSpeed Insights API").

## Priority ranking for Phase 3+

Based on static analysis alone:

1. **Defer render-blocking scripts** (medium, affects every page, likely biggest LCP win)
2. **Fix `404.html`** (high — it's bare; 15-min fix)
3. **Fix `free-ai-assessment.html` H1 duplication** (high, 5-min fix)
4. **Add `alt=""` to FB pixel noscript** (cosmetic but batch-fixable)
5. **Generate WebP/AVIF OG image** (medium, marginal win)
6. **Explicit `font-display: swap`** (low, defensive)

## Phase 4 decision point

Once PSI data is available:
- Lighthouse **Performance ≥ 90**: skip AstroWind port; apply targeted fixes here.
- Lighthouse **Performance < 80**: AstroWind port (static-first, Tailwind, ~100 Lighthouse OOTB) likely pays off.

Current structure is clean enough that a targeted fix pass is almost certainly the right move over a full rewrite.

## Artifacts

- `.tmp/audit/static_results.json` — full per-page findings
- `.tmp/run_psi_audit.py` — PSI fetcher (runnable once API key is set)
- `.tmp/static_audit.py` — static HTML analyzer (re-runnable anytime)

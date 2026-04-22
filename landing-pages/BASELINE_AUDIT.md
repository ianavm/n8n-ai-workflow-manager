# Landing Pages — Baseline Audit

**Date:** 2026-04-22
**Target:** `landing-pages/deploy/` (deployed to `www.anyvisionmedia.com` via Netlify)
**Method:** Static HTML analysis across all 16 pages. Live PageSpeed Insights API blocked (unauthenticated rate limit; needs `GOOGLE_PAGESPEED_API_KEY`).

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

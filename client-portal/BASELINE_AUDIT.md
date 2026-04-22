# Client Portal — Baseline Audit

**Date:** 2026-04-22
**Target:** `client-portal/` (deployed to `portal.anyvisionmedia.com` via Vercel)
**Method:** Static code + build-output analysis. Live Lighthouse against the production portal is blocked by auth — would need a Lighthouse run against a demo session or a PSI API key + public demo route.

## Stack

| Layer | Version |
|---|---|
| Next.js | **16.2.4** |
| React | **19.2.3** |
| TypeScript | 5.9.3 |
| Tailwind CSS | **4.1.18** (+ `@tailwindcss/postcss`) |
| Supabase | `@supabase/ssr 0.8.0`, `supabase-js 2.96.0` |
| Rate limiting | `@upstash/ratelimit 2.0.8` + `@upstash/redis 1.37.0` |
| Stripe | 20.4.1 |
| Framer Motion | **12.38.0** ✓ (Phase 3.4 already satisfied) |
| Charts | `recharts 3.7.0` |
| Icons | `lucide-react 0.576.0` |
| Toasts | `sonner 2.0.7` |
| Validation | `zod 4.3.6` |
| Forms data | `papaparse 5.5.3`, `jspdf 4.2.1`, `jspdf-autotable 5.0.7` |

**Stack is current.** Everything is modern (Next 16, React 19, Tailwind 4). Nothing flagged as outdated.

**Missing for shadcn:** `class-variance-authority`, `tailwind-merge`, `clsx`, `@radix-ui/*`. Phase 3 installs these.

## Codebase size

| Metric | Count |
|---|---|
| TS/TSX files | **293** |
| Pages (`page.tsx`) | **88** |
| API routes (`route.ts`) | **98** |
| `src/` size | 2.3 MB |
| Component domains | 11 |

### Component domains
`accounting/`, `admin/`, `billing/`, `charts/`, `connections/`, `crm/`, `dashboard/`, `marketing/`, `onboarding/`, `portal/`, `ui/`

### UI primitives (hand-rolled, in `src/components/ui/`)
`Badge.tsx`, `Button.tsx`, `Card.tsx`, `DateRangePicker.tsx`, `EmptyState.tsx`, `Input.tsx`, `Modal.tsx`, `RiskBadge.tsx`, `Skeleton.tsx`, `Table.tsx`

**Gap:** no shadcn/Radix primitives. Phase 3 adds them under `src/components/ui-shadcn/`, non-breaking.

## Build output

| Metric | Value |
|---|---|
| `.next/static/chunks/` total | **4.7 MB** |
| Largest single chunk | 418 KB |
| Next-largest (×3, same hash repeated) | 367 KB each |
| 5th largest | 232 KB |

The three identical 367 KB chunks suggest bundle duplication — likely `framer-motion` + `recharts` being bundled on multiple routes rather than shared. Worth investigating in a later performance pass.

## What's solid ✓

- Modern stack, current versions
- `framer-motion` already installed → Phase 3.4 doesn't need an install
- Upstash rate limiting in place (security hygiene)
- Supabase SSR used correctly
- Zod for validation
- Clear domain separation in `src/components/`

## Gaps identified

### Code architecture

1. **No shadcn foundation** — each UI primitive is hand-rolled. Makes consistency, theming, and future component additions harder. **Phase 3 fix.**
2. **No `cn()` utility / `clsx` + `tailwind-merge`** — class merging is brittle in custom components. **Phase 3 adds `src/lib/utils.ts`.**
3. **No design tokens file** — brand color `#FF6D5A` likely repeated across files. **Phase 3 centralises into `globals.css` CSS variables via tweakcn.**

### Bundle

1. **Three identical 367 KB chunks** — possible deduplication opportunity (likely recharts/framer-motion repeated across routes). Defer to post-Phase-3 performance pass.

### Blocked (needs live Lighthouse)

- LCP / INP / CLS / TBT numbers on actual dashboard views
- Authenticated route performance
- Runtime JS execution time
- Actual CWV real-user data (CrUX)

To unblock: either (a) add PSI API key + audit a public portal route, or (b) run local Lighthouse against the dev server with a fixture session.

## Priority ranking for Phase 3+

1. **Bootstrap shadcn + `cn()` util under `ui-shadcn/`** — unlocks fast, themed component additions (Phase 3.1–3.3)
2. **Bake `#FF6D5A` brand theme via tweakcn** (Phase 3.2)
3. **Drop one MagicUI animated block as smoke test** (Phase 3.4 — `framer-motion` already installed)
4. **Audit bundle after Phase 3 to see if shadcn/Radix additions change chunk dedup picture**
5. **Set up PSI key → run Lighthouse against a public demo route** (post-Phase 3)

## Artifacts

- `.tmp/audit/static_results.json` — per-page landing page audit (shared artifact)
- This doc — portal baseline

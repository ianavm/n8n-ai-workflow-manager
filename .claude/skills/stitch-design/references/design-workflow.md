---
name: design-workflow
description: End-to-end design workflows using Stitch for different project types
---

# Design Workflows

## Landing Page Design

1. **Generate hero section**: "A modern SaaS landing page hero with headline, subtext, CTA button, and product screenshot"
2. **Generate features section**: "Features grid with 6 cards, each with icon, title, description"
3. **Generate pricing section**: "3-tier pricing table with feature comparison"
4. **Generate footer**: "Footer with company links, social media, newsletter signup"
5. **Build site**: Map screens to a single-page layout

## Dashboard Design

1. **Generate main dashboard**: "Analytics dashboard with KPI cards, charts, and activity feed"
2. **Generate settings page**: "User settings with profile, notifications, billing tabs"
3. **Generate list/table view**: "Data table with filters, search, pagination, bulk actions"
4. **Build site**: Map to /dashboard, /settings, /data routes

## Mobile App Design

1. **Generate onboarding**: "Mobile onboarding with swipeable cards and skip button"
2. **Generate login**: "Mobile login with email/password, Google sign-in, biometric option"
3. **Generate home**: "Mobile home screen with bottom tab navigation, feed layout"
4. **Generate profile**: "Mobile profile with avatar, stats, settings gear icon"

## E-commerce Design

1. **Generate product grid**: "Product listing with filters sidebar, sort dropdown, card grid"
2. **Generate product detail**: "Product page with gallery, description, reviews, add-to-cart"
3. **Generate cart**: "Shopping cart with item list, quantity controls, order summary"
4. **Generate checkout**: "Multi-step checkout: shipping, payment, review, confirmation"

## Design System Extraction

After generating screens:
1. Download HTML with `get_screen_code`
2. Extract color palette, typography, spacing from generated CSS
3. Map to Tailwind config or design tokens
4. Use as foundation for component library

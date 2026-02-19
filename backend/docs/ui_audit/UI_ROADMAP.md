# UI Roadmap (Frontend-Only)
Prioritized steps that do not require backend changes and avoid Claude’s touch areas.

## P0 (Stability & Transparency)
- Add skeletons/loaders + error banners on tenders, EPazar, products, chat, admin; keep layout stable during hydration.
- Clarify data gaps: badges for missing price/CPV/contact info; tooltips for procedure_type/CPV codes; language consistency on each page.
- Gate obvious premium actions client-side: exports, chat send, saved-search count; surface usage from `getSubscriptionStatus`.
- Fix hardcoded filters: load procedure/status/category options from APIs; add “reset filters” CTA on empty states.

## P1 (Discovery & Trust)
- Wire `PriceHistoryChart` with placeholder message and toggle; show “data coming soon” instead of empty chart.
- Build CPV browser widget using `getCpvCodes` and embed on tenders/products/epazar pages.
- Add comparison drawer (client-only) for tenders/products/suppliers; allow side-by-side fields already returned in list payloads.
- Show bidders/lots/offers tables where data is already fetched (tender and epazar detail); add empty-state messaging when absent.
- Add route-level breadcrumbs and back-to-results links for `/products`, `/tenders/[id]`, `/epazar/[id]`.

## P2 (Guided Flows)
- Add product discovery CTA from landing/dashboard to `/products`; zero-state cards linking across datasets (tenders/epazar).
- Integrate saved searches with visible limits and upgrade CTA; sync to localStorage only but label clearly.
- Add “Ask AI about this” chips (CPV, entity, value) to prefill chat prompts; show sources/confidence badges in chat bubbles.
- Add soft rate-limits UI (cooldowns) to chat/search pagination to deter spam.

## P3 (Polish)
- Localize consistently (MK vs EN); centralize strings.
- Add light watermark on free-tier detail pages to reduce screenshot resale.
- Theme refresh for analytics cards and admin tables to match dashboard.

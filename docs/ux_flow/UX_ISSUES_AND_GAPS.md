# UX Issues & Gaps (Client-Side)
Read-only assessment of the Next.js app UX. Focused on states, missing surfaces, and mismatches with available APIs.

## High-Impact Gaps vs Available APIs
- **Price history:** `components/charts/PriceHistoryChart` exists but no route uses it; no API call for time-series values (tenders, suppliers, or products).
- **Comparison:** No side-by-side view for tenders/suppliers/products despite rich detail pages; no shared selection state.
- **Analytics:** Admin-only analytics screen exists; no user-facing analytics dashboard (status trends, CPV mix, top entities).
- **CPV browser:** `api.getCpvCodes` exists but no UI tree/search to navigate CPV hierarchy or filter by CPV across datasets.
- **Saved searches:** Component stores to localStorage only; ignores `saved_searches` API concept and tier limits; no alerts.
- **Fraud/tier limits:** `getTierLimits`/`validateEmail` not used; chat and search run without throttles or visual limits.
- **AI grounding:** Chat and tender/epazar pages call `queryRAG` without showing token usage, tier gating, or citation details.
- **Bidders/lots coverage:** Tenders detail fetches bidders/lots but UI renders bidders only; lots are fetched but unused.
- **EPazar offers/awards:** Detail page hits offers/awarded-items but prioritizes summary/chat; no offers table, no contract values.
- **Product discovery:** Aggregations fetched on first search only; no CPV/category facets; quantity/price sorting is client-side only.

## Inconsistent or Missing UI States
- **Loading/error coverage:** Several pages early-return on `!isHydrated` but lack per-section spinners (e.g., EPazar items tab); errors are logged but not surfaced (e.g., `getTenderStats`, product stats, EPazar stats).
- **Hardcoded filters:** Tenders quick filters use Macedonian labels that may not match API procedure_type/status values → likely zero-results; no dynamic options from `/api/tenders/categories` or `/api/tenders/cpv-codes`.
- **Filter reset vs dataset:** Tenders dataset tabs force `status=open` on “active”; switching to “awarded/cancelled” does not reset stale filters leading to empty states without guidance.
- **Pagination & search coupling:** Product search paginates but does not persist sort/filters across pages when query changes; EPazar products paginates without empty-state CTA.
- **Auth feedback:** Login/register use toast errors but no field-level validation; verify-email/resend lack success/failure states.
- **Admin guard:** `AdminRoute` checks role on client only; no loader for `/admin/*` while auth fetches; failure falls back to toast.
- **AI chat:** No loader for streaming; errors show toast but conversation lacks retry/“regenerate” controls; no context chips (tender/doc/CPV).
- **Saved searches:** No indication of persistence scope or tier; toggling “alerts” is local only (misleading).
- **Bidders/lots toggle:** Data fetched but hidden; users cannot see empty-state reason.

## Broken/Weak Flows (Examples)
- **Finding a product (“surgical drape set”):** User goes to `/products` → search suggestions appear, but underlying dataset lacks prices/CPV; aggregations only refresh on first page, and price history/comparison tabs are absent. If zero results, no alternate path (no link to tenders search or EPazar items).
- **Tenders detail exploration:** Lots fetched but unseen; bidders shown without clarity on winners vs participants; documents shown without content snippets; AI section lacks sources or confidence, so users cannot verify.
- **EPazar detail:** Offers/awarded-items endpoints available but not rendered, so contract award context is missing; AI summary fills the gap but unverifiable.

## Tier Gating Opportunities (UI-only)
- Chat/RAG button and product exports should check `getSubscriptionStatus.tier` before enabling; currently always enabled.
- Saved searches/alerts: enforce Free=1, Pro=10, Premium=unlimited; show counters and upgrade CTA.
- Exports: `ExportButton` available on tenders/products without tier check; add disabled state + upgrade modal.
- Competitors and personalized dashboard: show upgrade banner when personalization endpoints fail or user is Free.
- Admin access: add loader + redirect on failure instead of rendering partial layout.

## Design/Content Debt
- Mixed languages (Macedonian labels, English headers) within the same page (e.g., products/tenders).
- Missing empty-state guidance and recovery links (e.g., “Try EPazar items” when tenders empty).
- No tooltips or info badges for CPV, procedure_type, or value fields; users can’t interpret domain terms.
- Lack of skeletons for cards and tables → perceived slowness.

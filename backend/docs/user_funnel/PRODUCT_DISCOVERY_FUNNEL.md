# Product Discovery Funnel (UI-Only)
Walkthrough for a user searching “surgical drape set” and where the UI breaks. No backend actions required.

## Expected Funnel
1) Landing → click “Product Research” CTA (missing; currently only tenders/chat CTAs).
2) `/products` search bar → type “surgical drape set”.
3) Suggestions dropdown (`getProductSuggestions`) → pick best match.
4) Results grid/list with price/quantity, CPV/category facets, and comparison/price history.
5) Drill into tender or supplier; bookmark or export.

## Actual UI Behavior
- **Entry:** No CTA from landing/dashboard to `/products`; users must discover via sidebar only.
- **Search:** Suggestions load after 300ms debounce; if dataset is empty, dropdown hides silently—no hint to try tenders/epazar.
- **Results:** `searchProducts` returns but quantities/prices are often null; client-side sort falls back to 0 → misleading ordering.
- **Aggregations:** Fetched only on first page; changing pages or filters leaves stale aggregates; no CPV/category facets.
- **Price history:** `PriceHistoryChart` exists but unused—no time series for items.
- **Comparison:** No selection or compare mode; user cannot contrast suppliers or tenders for the product.
- **Exports:** Enabled without tier check; CSV may include null pricing, confusing users.
- **Drill-through:** Links go to tender detail, but AI products and bidders are separate flows; no breadcrumb back to products.

## Breakpoints in the Flow
- Empty dataset → user sees zero results without guidance; no “try EPazar items” or “search tenders by keyword”.
- Missing CPV facets → user can’t narrow down medical category; must rely on free-text.
- No price visibility → even when unit_price is missing, UI doesn’t explain why.
- No saved searches → localStorage only; cannot follow up later or set alerts.
- No multi-compare → cannot select multiple tenders for side-by-side view.

## UI-Only Remediations (no backend)
- Add CTA buttons from landing/dashboard to `/products`.
- Add helper banners on zero results linking to `/tenders?search=surgical drape set` and `/epazar?tab=products`.
- Surface “data incomplete” badge when price/CPV missing; grey out sort options that rely on missing fields.
- Keep aggregations in sync per page/filter and show skeletons while loading.
- Add client-side compare drawer (select up to 3 products/tenders) using existing result data.
- Wire `PriceHistoryChart` to placeholder data with note “waiting for values”; hide until real series available.
- Persist saved searches to localStorage with a visible count and upgrade CTA when exceeding tier caps (UI-only guard).

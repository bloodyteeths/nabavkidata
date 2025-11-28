# Frontend Route & Component Map (Next.js App Router)
Static map of all `frontend/app` routes, their primary components, and API callers (`@/lib/api`). No backend changes implied.

## Route Inventory (App Router)
- `/` (landing): `frontend/app/page.tsx` with landing sections (hero, features, pricing, trust, navbar, comparison).
- `/auth/*`: login, register, verify-email, forgot/reset password, callback; uses auth API but minimal loading/error states.
- `/dashboard`: summary cards from `api.getPersonalizedDashboard`, `api.searchTenders` fallback; uses `DashboardLayout`.
- `/tenders`: list view with filters (`TenderFilters`), stats (`TenderStats`), saved searches (localStorage), export; API: `getTenders`, `getTenderStats`. Quick filters hardcode procedure/status labels.
- `/tenders/[id]`: detail view; API: `getTender`, `getTenderDocuments`, `getTenderBidders`, `getTenderLots`, `getAIExtractedProducts`, `queryRAG`, `logBehavior`. RAG + AI products shown without tier gating.
- `/epazar`: dual tab (tenders/products); API: `getEPazarStats`, `getEPazarTenders`, `searchEPazarItems`, `getEPazarItemsAggregations`. Items tab hides aggregations until searched; no bidders/offers view.
- `/epazar/[id]`: detail; API: `getEPazarTender`, `queryRAG`, `summarizeEPazarTender`, `getEPazarItems`, `getEPazarOffers`, `getEPazarAwardedItems`, `getEPazarDocuments`. Missing price history and bidder analytics surfaces.
- `/products`: product search; API: `getProductStats`, `getProductSuggestions`, `searchProducts`, `getProductAggregations`. No CPV browser, comparison, or price history overlays.
- `/suppliers`: list; API: `getSuppliers`. Basic filters only; no comparison or price history.
- `/suppliers/[id]`: detail; API: `getSupplier`. Shows participations; no CPV mix or value trends.
- `/competitors`: combines personalization + known winners; API: `getPersonalizedDashboard`, `getKnownWinners`, `getPreferences/savePreferences`. No competitive comparison UI.
- `/chat`: AI assistant; API: `getSubscriptionStatus`, `queryRAG`. Free-text entry, unlimited client-side loop; no usage gating or captcha.
- `/inbox`: digests; API: `getDigests`, `getDigestDetail`. Read-only; no filtering.
- `/settings`: preferences builder; API: `getPreferences/savePreferences`, `searchEntities`, `searchTenders`, `getSuppliers`, `getEPazarSuppliers`, billing checkout/portal. No validation for tier limits on alert counts.
- `/billing` + `/billing/plans` + success/cancelled: plan display and Stripe actions; API: `getPlans`, `getCurrentSubscription`, `createCheckoutSession`, `getInvoices`, `getUsage`, `createPortalSession`, `cancelSubscription`.
- `/admin/*`: dashboard/users/tenders/scraper/monitor/logs/broadcast/analytics; API: `getDashboardStats`, `getUsers`, `updateUser/ban/unban/delete`, `approveTender/deleteTender`, `getScraperStatus/triggerScraper`, `getLogs`, `getAnalytics`, `sendBroadcast`. Guarded by `AdminRoute` but relies on client role only.
- `/privacy`, `/terms`, `/403`, `/billing/plans`, `/billing/success`, `/billing/cancelled`, `/competitors`, `/settings`, `/inbox`, `/chat`, `/products`, `/suppliers`, `/dashboard`, `/admin/*`, `/epazar/*`, `/tenders/*`.

## Component Catalog (frontend/components)
- **UI primitives:** `ui/*` (button, input, select, dialog, table, tabs, card, badge, dropdown-menu, textarea, checkbox, label, avatar).
- **Layout:** `layout/DashboardLayout` (shell for many pages).
- **Navigation:** `landing/Navbar`; `admin/sidebar-layout`.
- **Tenders:** `tenders/TenderCard`, `TenderFilters`, `TenderStats`.
- **EPazar:** (embedded in page; no standalone components).
- **Chat:** `chat/ChatInput`, `ChatMessage`.
- **Dashboard:** `dashboard/TendersByCategory`, `TenderTimeline`.
- **Charts:** `charts/PriceHistoryChart` (currently unused, no data feed).
- **Billing:** `billing/PlanCard`.
- **Admin:** `admin/AdminRoute`, `UserTable`, `StatCard`.
- **Auth:** `auth/ProtectedRoute`.
- **Saved searches/export:** `SavedSearches` (localStorage only), `ExportButton`.

## Client-Side API Callers
All API calls flow through `frontend/lib/api.ts` (single client with token refresh). Route usage highlights:
- **Tenders:** `getTenders`, `getTender`, `getTenderStats`, `getTenderDocuments`, `getTenderBidders`, `getTenderLots`, `getAIExtractedProducts`, `queryRAG`, `logBehavior`.
- **Products:** `getProductStats`, `getProductSuggestions`, `searchProducts`, `getProductAggregations`, `getProductsByTender`, `getProductStats`.
- **EPazar:** `getEPazarStats`, `getEPazarTenders`, `searchEPazarItems`, `getEPazarItemsAggregations`, `getEPazarTender`, `summarizeEPazarTender`, `getEPazarItems`, `getEPazarOffers`, `getEPazarAwardedItems`, `getEPazarDocuments`, `analyzeEPazarSupplier`, `getEPazarSuppliers`.
- **Suppliers/entities:** `getSuppliers`, `getSupplier`, `searchSuppliers`, `getEntities`, `searchEntities`.
- **Personalization/behavior:** `getPersonalizedDashboard`, `getPreferences/savePreferences`, `getSearchHistory`, `logSearch`, `logBehavior`, `getPopularSearches`.
- **RAG/AI:** `queryRAG`, `semanticSearch` (unused in UI).
- **Billing:** `getPlans`, `getCurrentSubscription`, `createCheckoutSession`, `createPortalSession`, `getSubscriptionStatus`, `cancelSubscription`, `getInvoices`, `getUsage`.
- **Fraud endpoints:** `getTierLimits`, `validateEmail` (not used in UI).
- **Admin:** `getDashboardStats`, `getUsers/getUser/updateUser/deleteUser/ban/unban`, `approveTender/deleteTender`, `getAnalytics`, `getLogs`, `getScraperStatus/triggerScraper`, `sendBroadcast`.
- **Digests:** `getDigests`, `getDigestDetail`.

## Route Diagram (text)
```
Landing
 └─ Auth (login/register/verify/forgot/reset/callback)
Dashboard
 ├─ Tenders (list -> detail)
 │    ├─ Documents
 │    ├─ Bidders/Lots
 │    ├─ AI products
 │    └─ Chat about tender
 ├─ EPazar (tenders tab, products tab -> detail)
 ├─ Products (cross-tender product search)
 ├─ Suppliers (list -> detail)
 ├─ Competitors
 ├─ Inbox (digests)
 ├─ Chat (AI)
 ├─ Settings (preferences + billing shortcuts)
 ├─ Billing (plans, portal, success/cancelled)
 └─ Admin (dashboard, users, tenders, scraper, monitor, logs, broadcast, analytics)
```

## Immediate Mapping Gaps
- CPV browser absent despite `api.getCpvCodes`.
- Comparison flows missing (no component to compare tenders/suppliers/products).
- Price history chart component exists but unused (no data feed).
- Analytics/dashboard views in admin lack user-facing analytics route.
- Saved searches are local-only (no API sync, no tier limits, no alerts).
- Fraud endpoints not wired (no tier-limits UI, no email validation UX).

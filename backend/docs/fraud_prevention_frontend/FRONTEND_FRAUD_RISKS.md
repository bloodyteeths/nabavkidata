# Frontend Fraud/Abuse Surfaces
UI-only view of abuse vectors and mitigations that do not require backend changes (though backend enforcement is still needed).

## Surfaces
- **AI chat spam:** `/chat` and tender/epazar detail chat boxes allow unthrottled free-text calls to `queryRAG`; no client cooldown, character limit, or captcha; no usage meter.
- **Search scraping:** Tenders, EPazar, products, suppliers, competitors pages allow rapid pagination/export without visible rate limits; `ExportButton` not gated by tier.
- **Saved searches:** Local-only storage; toggling “alerts” implies server-backed notifications but actually does nothing, leading to confusion and potential expectation abuse.
- **Admin panels:** Client-only role check; if token is reused, UI will render admin controls before a 401; no obfuscation or delayed load.
- **Email abuse:** Register/forgot-password forms lack email validation or per-session throttle UI; no inline hints about disposable domains though `validateEmail` API exists.
- **Screenshot scraping:** High-value data (contact info, bidders) shown as plain text with no friction; copy buttons absent but screens are easily captured; no watermarking or masked numbers for free tier.

## UI-Only Mitigations (safe alongside Claude’s backend work)
- Add visible usage meters and “cooldown” timers in chat; disable send button for a few seconds after each call; show tier-based daily/ monthly quota pulled from `getSubscriptionStatus`.
- Add client-side request debounce and minimal delay between pagination actions; show “rate limited” toast when user exceeds soft threshold.
- Gate exports behind tier check; for free tier, disable and show upgrade modal instead of downloading CSV.
- Use `getTierLimits` and `validateEmail` to pre-screen emails in auth flows; block submission with clear error if not allowed.
- Clarify saved-search behavior: label as “Local only” until backend alerts exist; limit count per tier client-side.
- Mask sensitive values on free tier in UI (e.g., hide contact emails/phones until upgraded) and add watermark overlay on detail pages to deter screenshot resale.

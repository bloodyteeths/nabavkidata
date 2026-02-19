# AI UI Implementation (Frontend-Only)
Scope: UI/UX improvements for AI flows and raw JSON visibility in `frontend/` only. No backend, scraper, or API contract changes.

## What Changed
- **AI experience cleanup** (chat page and tender detail):
  - Removed placeholders, developer toggles, and fake panels; chat now shows only real answers.
  - Kept minimal loading state and error messaging; free tier upsell disables input.
- **Tender detail:** removed raw JSON drawer and AI placeholder tabs; AI summary shows only real text.
- **Products:** CPV Browser renders only when real `cpv_codes` are returned; no placeholder state is shown.

## Files Touched (Frontend Only)
- `frontend/app/chat/page.tsx`: streamlined chat, real data only, free-tier upsell.
- `frontend/app/tenders/[id]/page.tsx`: AI summary + chat without placeholders or raw JSON drawer.
- `frontend/app/products/page.tsx`: CPV Browser only when data exists.

## How to Use (UI Behavior)
- **Chat (/chat):** Free tier sees upsell and disabled input; paid tiers can chat; loading shows simple typing state.
- **Tender detail:** AI summary uses only `queryRAG` answer; chat returns answers without extra panels.
- **Products:** CPV card appears only when backend returns codes; otherwise hidden.

## Deferred to Backend (placeholders)
- Source attribution, confidence, CPV suggestions, and richer AI panels depend on future backend payloads and are intentionally omitted for now.

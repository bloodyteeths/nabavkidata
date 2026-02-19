# UX Gaps and Missing Screens
Reference checklist of UI work that is not yet implemented. No code changes here—design and scope only.

## Price History
- **Purpose:** show historical estimated/awarded values per tender or supplier to spot trends.
- **Needed UI:** chart component on tender detail with MKD/EUR toggle; timeline of amendments; badge for variance vs. estimated.
- **Data dependencies:** awarded/estimated values (currently partial/empty), currency conversion, tender_amendments once populated.
- **Interactions:** filter by CPV/category, export CSV/PDF, compare periods (last 6/12/24 months).

## Comparison Tool
- **Purpose:** side-by-side view of multiple tenders or suppliers.
- **Needed UI:** multi-select on list pages → comparison drawer/page; columns for values, dates, CPV, procedure_type, bidder count, documents list.
- **Data dependencies:** consistent tender_id links, bidder counts, CPV, contract_duration; epazar financials must be backfilled.
- **Interactions:** save comparison sets, share link (admin/pro tiers), quick diff highlighting mismatched fields.

## CPV Browser
- **Purpose:** navigable CPV hierarchy to improve discovery and AI grounding.
- **Needed UI:** tree view (level 1–5), search-as-you-type with fuzzy matching, detail pane with descriptions and related tenders count.
- **Data dependencies:** `cpv_codes` table, per-tender CPV coverage (67% today, 0% on epazar_items), enrichment suggestions from AI.
- **Interactions:** click to filter lists, subscribe to CPV for alerts, expose to AI chat as selectable context.

## Analytics Dashboard
- **Purpose:** executive overview of pipeline health and market activity.
- **Needed UI:** KPIs (open/awarded counts, total estimated value, extraction success), charts for status over time, top procuring entities, CPV mix, scraper health widget.
- **Data dependencies:** tender status/time series, scrape_history, document extraction stats, subscription usage, bidder stats (currently winner-only).
- **Interactions:** date range picker, drill-through to lists, export to CSV; admin-only controls for resync/reindex.

## Saved Search Manager
- **Purpose:** let users create, edit, and delete saved filters/alerts.
- **Needed UI:** dashboard section listing saved searches with CPV/category/keyword filters; toggle email cadence; usage counter per tier.
- **Data dependencies:** saved_searches table (currently empty), alerts/notifications plumbing, tier limits (free=1, pro=10, premium=unlimited).
- **Interactions:** create from current filters, duplicate/edit, test alert preview, pause/resume, delete.

## AI Assistant Flow
- **Purpose:** guided chat experience with transparent sourcing.
- **Needed UI:** prompt library (CPV lookup, bid preparation, doc summary), source citations per message, confidence pill (High/Medium/Low), feedback buttons.
- **Data dependencies:** RAG health, embeddings coverage, query_history for auditing; tender/doc metadata for citations.
- **Interactions:** attach context (tender/doc/CPV), ask follow-ups, export conversation, escalate to web fallback when local recall is low (with explanation).

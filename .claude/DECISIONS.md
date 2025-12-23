# Architecture & Technical Decisions Log

Track important decisions to maintain context across Claude sessions.

---

## 2025-12-23: Risk Analysis Page Performance Fix
**Decision**: Use PostgreSQL materialized views for corruption flags aggregation
**Rationale**: Stats endpoint took 10s, flagged-tenders took 2.5s due to complex CTEs
**Result**: Stats 0.26s (40x faster), flagged-tenders 0.45s (5.5x faster)
**Views Created**: `mv_flagged_tenders`, `mv_corruption_stats`
**Cron**: Daily refresh at 5 AM via `/home/ubuntu/nabavkidata/scraper/cron/refresh_corruption_views.sh`

## 2025-12-23: Risk Flagging Accuracy Audit
**Decision**: Mark 838 flags as false positives (724 short_deadline, 114 single_bidder)
**Rationale**: 88% of short_deadline flags were due to bad date data in database
**Status**: Applied to database
**SQL**: `UPDATE corruption_flags SET false_positive = TRUE WHERE ...`

## 2025-12-23: Bilingual Search Implementation
**Decision**: Implement Latin-to-Cyrillic transliteration for all search fields
**Rationale**: Users type Latin characters but data is in Macedonian Cyrillic
**Files**: `backend/api/corruption.py` - `latin_to_cyrillic()`, `build_bilingual_search_condition()`

## 2025-12-22: E-Pazar Integration
**Decision**: Separate tables for e-pazar data (epazar_tenders, epazar_items, epazar_offers)
**Rationale**: Different data structure than e-nabavki; keep normalized for price intelligence
**Status**: Implemented with dedicated spider and API endpoints

## 2025-12-20: Two-Track Data Import Strategy
**Decision**: Import OpenTender OCDS + parallel scrape e-nabavki
**Rationale**: Historical data takes weeks to scrape; OpenTender has 260,901 validated records
**Scripts**: `scraper/import_opentender.py`, `scraper/run_parallel_scrape.sh`

## 2025-12-18: Archive vs Year Filter Parameters
**Decision**: Use `year` param for 2008-2021, `year_filter` for 2022+
**Rationale**: Archive uses Playwright modal selector; default view uses server-side filter
**Result**: Fixed 2022-2024 scraping gap
**Commands**:
```bash
# Archive (modal selection)
scrapy crawl nabavki -a category=awarded -a year=2019

# Recent (server-side filter)
scrapy crawl nabavki -a category=awarded -a year_filter=2024
```

## 2025-12-15: Document Processing Pipeline
**Decision**: Two-step pipeline: Chandra OCR extraction -> Gemini embeddings
**Rationale**: Chandra handles scanned PDFs better; Gemini provides quality embeddings
**Scripts**: `scraper/process_documents.py`, `ai/embeddings/pipeline.py`

---

## Decision Template
```
## YYYY-MM-DD: [Short Title]
**Decision**: [What was decided]
**Rationale**: [Why this approach]
**Status**: [Implemented/In Progress/Planned]
**Files**: [Affected files]
**Commands**: [Relevant commands if any]
```

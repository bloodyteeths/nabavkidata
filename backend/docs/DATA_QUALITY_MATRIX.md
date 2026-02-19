# Data Quality Matrix
Cross-reference of fill rates, fitness for AI, and business priority. Numbers come from the latest DB audit (tenders=1,778 rows; epazar_tenders=745; epazar_items=10,135; documents=2,298; product_items=1,399; tender_bidders=1,003).

## Legend
- **Good:** >95% populated
- **Partial:** 50–95% populated
- **Trash:** <50% populated or systematically empty
- **AI-ready fields:** usable today for retrieval/LLM prompts
- **Raw JSON needed:** should be captured in `raw_data_json` (currently empty) for fallback parsing
- **Business-critical:** required for customer-facing analytics, alerts, and billing promises

## Table-Level Matrix
| Table | Fill Rate Snapshot | Field Classification | AI-Ready Fields | Raw JSON Needed Fields | Business-Critical Fields |
|-------|--------------------|----------------------|-----------------|------------------------|--------------------------|
| **tenders** | Core IDs/title/status 100%; publication_date 99.9%; cpv_code/description ~66%; closing_date 16.7%; values_mkd ~50%; EUR/guarantees 0% | **Good:** tender_id, title, status, source_url, procuring_entity, procedure_type. **Partial:** cpv_code, description, opening/closing_date, evaluation_method, contract_duration, contact_phone/email/person. **Trash:** estimated_value_eur, actual_value_eur, security_deposit_mkd, performance_guarantee_mkd, award_criteria (0%). | cpv_code, category, description, estimated_value_mkd, winner, contact info, publication/closing dates. | award_criteria, guarantees, amendment text, bidder list (full), bureau_delivery_date; untouched `raw_data_json` should store full scraped payload for CPV derivation and evaluation rules. | closing_date, opening_date, estimated_value_mkd, cpv_code, procedure_type, winner, contact_email/phone, source_url, publication_date. |
| **epazar_tenders** | Core fields 100%; description 98.5%; publication_date 99.5%; closing_date 98.5%; award_date/contract_date 0–30%; financials/CPV 0% | **Good:** tender_id, title, source_url, category, procedure_type, status, publication/closing dates. **Partial:** description, award_date, contract_date, contract_duration. **Trash:** cpv_code, estimated/awarded values (all 0%). | title, description, procedure_type, category, publication/closing dates. | cpv_code, estimated_value_mkd/eur, awarded_value_mkd/eur, contracting_authority_id details. | closing_date, publication_date, contract_number, procedure_type, category, contracting_authority. |
| **epazar_items** | line_number/item_name/item_id/quantity/unit 100%; item_description 25%; all price fields 0% | **Good:** IDs and quantities. **Partial:** item_description. **Trash:** cpv_code, estimated/unit/total prices, delivery/specs fields (all 0%). | item_name, quantity, item_description (when present). | unit_price/total_price, cpv_code, delivery dates/locations, specs; raw BOQ JSON should be preserved for reconstruction. | quantity, item_name, item_description, tender_id linkage, unit. |
| **documents** | doc_id/tender_id/file_name/doc_type 100%; file_url 86%; file_size 77%; page_count 84%; content_text 85%; specifications_json 57% | **Good:** identifiers, file metadata, content_text presence. **Partial:** mime_type, file_url, file_size_bytes, page_count, specifications_json. **Trash:** none, but extraction_status pending for 15% files. | content_text, doc_type, file_url, page_count, file_size_bytes, mime_type. | specifications_json enrichment (parsed tables/clauses), doc_category/version, extracted structured clauses for conditions and CPV hints. | file_url, content_text, doc_type, tender_id, file_size_bytes, extraction_status. |
| **product_items** | name/specifications 100%; quantity 11.6%; unit_price 0.07%; all other metadata 0% | **Good:** name, freeform specifications. **Partial:** quantity. **Trash:** manufacturer, supplier, category, cpv_code, model, unit_price, source_document_url. | specifications text for embedding; name; quantity (when present). | normalized manufacturer/supplier, pricing, CPV/category; source document references; extraction_method for auditability. | quantity, unit_price, supplier, category/cpv_code, source_document_url. |
| **tender_bidders** | 1,003 rows; bid_amount 100%; bidder identity 100%; winner flag 100% (all true) | **Good:** bid amounts and winner marking. **Partial:** bidder metadata beyond name/tax_id. **Trash:** lacks non-winning bids (coverage bias). | bid_amount_mkd, bidder names/tax_ids. | non-winning bids, scoring notes, evaluation criteria, bid timestamps. | bidder name/tax_id, bid_amount_mkd, award status, tender_id linkage. |

## AI Readiness Notes
- **Strengths:** high integrity, strong population of titles/categories/status; documents have usable text for embeddings; cpv_code available for ~67% of tenders; epazar descriptions are rich.
- **Weaknesses:** price data in epazar_items/product_items is effectively missing; EUR conversions absent; award criteria and guarantees are absent; raw_data_json is empty so long-tail attributes are lost.
- **Immediate wins:** expose contact fields and winner info to AI prompts; embed content_text for all extracted docs; backfill CPV from descriptions using ML; derive contract_duration/payment_terms from documents into tender_conditions.

## Raw JSON Capture Targets
- Full scraped payloads per tender (all web fields, even if not mapped).
- BOQ line items with unit/total pricing and delivery specs.
- Evaluation and eligibility clauses for auditability.
- Currency context (original currency, exchange rate, VAT flags).
- Document-level metadata (issuer, revision, signatures) to aid provenance checks.

## Business-Critical Coverage Risks
- **Financial analytics blocked:** missing estimated/awarded values (EUR) and item pricing prevent revenue models and alerts.
- **Competitive intelligence weak:** tender_bidders only stores winners; lost insight on competition and price ranges.
- **Search/filters limited:** missing CPV on epazar records and product_items categories reduces discovery.
- **AI fallback missing:** empty `raw_data_json` limits the AI assistant when structured fields are null.

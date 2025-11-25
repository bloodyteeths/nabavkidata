"""
Scrapy Item definitions for tenders and documents
"""
import scrapy

class TenderItem(scrapy.Item):
    """Tender data structure"""
    tender_id = scrapy.Field()
    title = scrapy.Field()
    description = scrapy.Field()
    category = scrapy.Field()
    procuring_entity = scrapy.Field()
    opening_date = scrapy.Field()
    closing_date = scrapy.Field()
    publication_date = scrapy.Field()
    estimated_value_mkd = scrapy.Field()
    estimated_value_eur = scrapy.Field()
    actual_value_mkd = scrapy.Field()  # Database column name (was: awarded_value_mkd)
    actual_value_eur = scrapy.Field()  # Database column name (was: awarded_value_eur)
    cpv_code = scrapy.Field()
    status = scrapy.Field()
    winner = scrapy.Field()
    source_url = scrapy.Field()
    language = scrapy.Field()
    scraped_at = scrapy.Field()
    source_category = scrapy.Field()  # PHASE 4: Track which category listing the tender came from
    content_hash = scrapy.Field()  # PHASE 5: SHA-256 hash for change detection

    # NEW FIELDS: Added 6 missing fields
    procedure_type = scrapy.Field()
    contract_signing_date = scrapy.Field()
    contract_duration = scrapy.Field()
    contracting_entity_category = scrapy.Field()
    procurement_holder = scrapy.Field()
    bureau_delivery_date = scrapy.Field()

    # PHASE 3 FIELDS: Contact & Financial Data
    contact_person = scrapy.Field()
    contact_email = scrapy.Field()
    contact_phone = scrapy.Field()
    num_bidders = scrapy.Field()
    security_deposit_mkd = scrapy.Field()
    performance_guarantee_mkd = scrapy.Field()
    payment_terms = scrapy.Field()
    evaluation_method = scrapy.Field()
    award_criteria = scrapy.Field()  # JSON string
    has_lots = scrapy.Field()
    num_lots = scrapy.Field()
    amendment_count = scrapy.Field()
    last_amendment_date = scrapy.Field()

    # PHASE 3: Related data (as JSON strings, parsed in pipeline)
    lots_data = scrapy.Field()  # JSON array of lot objects
    bidders_data = scrapy.Field()  # JSON array of bidder objects
    amendments_data = scrapy.Field()  # JSON array of amendment objects
    clarifications_data = scrapy.Field()  # JSON array of Q&A objects
    documents_data = scrapy.Field()  # Collected document links/metadata

class DocumentItem(scrapy.Item):
    """Document data structure"""
    tender_id = scrapy.Field()
    doc_type = scrapy.Field()
    file_name = scrapy.Field()
    file_path = scrapy.Field()
    file_url = scrapy.Field()
    content_text = scrapy.Field()
    extraction_status = scrapy.Field()
    file_size_bytes = scrapy.Field()
    page_count = scrapy.Field()
    mime_type = scrapy.Field()

    # PHASE 3: Enhanced document metadata
    doc_category = scrapy.Field()  # technical_specs, financial_docs, award_decision, contract, etc.
    doc_version = scrapy.Field()
    upload_date = scrapy.Field()
    file_hash = scrapy.Field()  # SHA-256 for duplicate detection

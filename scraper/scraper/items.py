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
    actual_value_mkd = scrapy.Field()
    actual_value_eur = scrapy.Field()
    cpv_code = scrapy.Field()
    status = scrapy.Field()
    winner = scrapy.Field()
    source_url = scrapy.Field()
    language = scrapy.Field()
    scraped_at = scrapy.Field()

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

#!/usr/bin/env python3
"""
Test script to scrape a single tender detail page directly
Bypasses listing page pagination to quickly test extraction
"""

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scraper.spiders.nabavki_spider import NabavkiSpider
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

class SingleTenderSpider(NabavkiSpider):
    """Modified spider that scrapes specific tender URLs only"""
    name = 'test_single'

    # Test with a few specific tender URLs (from active notices)
    test_urls = [
        'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/99b6f70f-e4b0-4001-86be-b31b5e062d01',
        'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/d7c9fae4-e68b-4e38-bdde-6e0aed49b876',
        'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/0c8f3d97-fc9a-40da-9f16-aed34b9be5da',
    ]

    def start_requests(self):
        """Override to scrape specific test URLs only"""
        for url in self.test_urls[:3]:  # Limit to 3 tenders
            print(f"Testing tender: {url}")
            yield scrapy.Request(
                url=url,
                callback=self.parse_tender_detail,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'networkidle',
                        'timeout': 60000,
                    },
                    'source_category': 'active',
                },
                errback=self.errback_playwright,
                dont_filter=True
            )

if __name__ == '__main__':
    # Get project settings
    settings = get_project_settings()
    settings.set('FEEDS', {
        'test_output.json': {
            'format': 'json',
            'encoding': 'utf-8',
            'overwrite': True,
        }
    })
    settings.set('LOG_LEVEL', 'INFO')

    # Run the spider
    process = CrawlerProcess(settings)
    process.crawl(SingleTenderSpider)
    process.start()

    # Print results
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)

    try:
        with open('test_output.json', 'r') as f:
            items = json.load(f)

        print(f"\nItems scraped: {len(items)}\n")

        for i, item in enumerate(items, 1):
            print(f"Item {i}:")
            print(f"  Tender ID: {item.get('tender_id', 'N/A')}")
            print(f"  Title: {item.get('title', 'N/A')[:70]}")
            print(f"  Closing Date: {item.get('closing_date', 'N/A')}")
            print(f"  Estimated Value: {item.get('estimated_value_mkd', 'N/A')} MKD")
            print(f"  CPV Code: {item.get('cpv_code', 'N/A')}")
            print(f"  Procuring Entity: {item.get('procuring_entity', 'N/A')[:50]}")
            print(f"  Contact Person: {item.get('contact_person', 'N/A')}")
            print(f"  Contact Email: {item.get('contact_email', 'N/A')}")
            print(f"  Contact Phone: {item.get('contact_phone', 'N/A')}")
            print(f"  Documents: {len(item.get('documents', []))} files")
            print()

    except FileNotFoundError:
        print("No output file created")
    except Exception as e:
        print(f"Error reading results: {e}")

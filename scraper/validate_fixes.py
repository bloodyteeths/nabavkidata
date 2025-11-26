#!/usr/bin/env python3
"""
Validation script to verify all scraper fixes are in place
Run this to confirm Agent C's work is complete
"""

import os
import sys
from pathlib import Path

def check_file_content(filepath, checks):
    """Check if file contains expected content"""
    with open(filepath, 'r') as f:
        content = f.read()

    results = []
    for check_name, search_string in checks.items():
        found = search_string in content
        results.append((check_name, found, search_string))

    return results

def main():
    print("=" * 70)
    print("SCRAPER FIXES VALIDATION")
    print("=" * 70)

    base_path = Path(__file__).parent / "scraper"

    all_passed = True

    # CHECK 1: items.py
    print("\n1. Checking items.py...")
    items_checks = {
        "awarded_value_mkd field": "awarded_value_mkd = scrapy.Field()",
        "awarded_value_eur field": "awarded_value_eur = scrapy.Field()",
        "procedure_type field": "procedure_type = scrapy.Field()",
        "contract_signing_date field": "contract_signing_date = scrapy.Field()",
        "contract_duration field": "contract_duration = scrapy.Field()",
        "contracting_entity_category field": "contracting_entity_category = scrapy.Field()",
        "procurement_holder field": "procurement_holder = scrapy.Field()",
        "bureau_delivery_date field": "bureau_delivery_date = scrapy.Field()",
        "NO actual_value_mkd": "actual_value_mkd" not in open(base_path / "items.py").read(),
    }

    results = check_file_content(base_path / "items.py",
                                 {k: v for k, v in items_checks.items() if k != "NO actual_value_mkd"})

    # Special check for absence
    with open(base_path / "items.py") as f:
        content = f.read()
        no_actual = "actual_value_mkd" not in content or "# FIXED" in content
        results.append(("NO actual_value_mkd", no_actual, "actual_value_mkd should not appear"))

    for check, passed, search in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    # CHECK 2: nabavki_spider.py
    print("\n2. Checking nabavki_spider.py...")
    spider_checks = {
        "Correct start URL": 'home.aspx#/notices',
        "start_requests method": "def start_requests(self):",
        "errback_playwright": "def errback_playwright(self, failure):",
        "async parse": "async def parse(self, response):",
        "async parse_tender_detail": "async def parse_tender_detail(self, response):",
        "playwright meta": "'playwright': True",
        "playwright_include_page": "'playwright_include_page': True",
        "awarded_value extraction": "tender['awarded_value_mkd']",
        "procedure_type extraction": "tender['procedure_type']",
        "contract_signing_date extraction": "tender['contract_signing_date']",
        "await page.wait_for_selector": "await page.wait_for_selector",
    }

    results = check_file_content(base_path / "spiders" / "nabavki_spider.py", spider_checks)
    for check, passed, search in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    # CHECK 3: pipelines.py
    print("\n3. Checking pipelines.py...")
    pipeline_checks = {
        "awarded_value_mkd in validation": "'awarded_value_mkd'",
        "awarded_value in INSERT": "awarded_value_mkd, awarded_value_eur,",
        "procedure_type in INSERT": "procedure_type, contract_signing_date",
        "awarded_value in UPDATE": "awarded_value_mkd = EXCLUDED.awarded_value_mkd",
        "procedure_type in UPDATE": "procedure_type = EXCLUDED.procedure_type",
    }

    results = check_file_content(base_path / "pipelines.py", pipeline_checks)
    for check, passed, search in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    # CHECK 4: settings.py
    print("\n4. Checking settings.py...")
    settings_checks = {
        "PLAYWRIGHT_BROWSER_TYPE": 'PLAYWRIGHT_BROWSER_TYPE = "chromium"',
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60000",
        "--no-sandbox arg": "'--no-sandbox'",
        "PLAYWRIGHT_CONTEXTS": "PLAYWRIGHT_CONTEXTS = {",
        "Macedonian locale": "'locale': 'mk-MK'",
        "DOWNLOAD_HANDLERS": '"http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler"',
    }

    results = check_file_content(base_path / "settings.py", settings_checks)
    for check, passed, search in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    # FINAL VERDICT
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL CHECKS PASSED - Scraper fixes complete!")
        print("=" * 70)
        return 0
    else:
        print("✗ SOME CHECKS FAILED - Review output above")
        print("=" * 70)
        return 1

if __name__ == "__main__":
    sys.exit(main())

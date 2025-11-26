#!/usr/bin/env python3
"""
Playwright-based selector extraction script for e-nabavki.gov.mk

This script:
1. Loads the tender listings page with Playwright
2. Extracts real CSS selectors by analyzing the DOM
3. Follows a sample tender detail page
4. Extracts field selectors from detail page
5. Outputs JSON with real selectors for spider
"""

import asyncio
import json
import re
from playwright.async_api import async_playwright

async def extract_selectors():
    results = {
        'listings_page': {
            'url': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices',
            'selectors': {},
            'sample_tender_urls': []
        },
        'detail_page': {
            'selectors': {},
            'sample_html': ''
        }
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='mk-MK',
            timezone_id='Europe/Skopje'
        )
        page = await context.new_page()

        print("=" * 80)
        print("STEP 1: Loading tender listings page...")
        print("=" * 80)

        # Navigate to listings page
        await page.goto('https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices',
                       wait_until='networkidle', timeout=60000)

        # Wait for Angular to render
        await page.wait_for_timeout(3000)

        # Try to find tender list container
        print("\nLooking for tender list container...")

        # Common container selectors
        container_candidates = [
            'div.tender-list',
            'div.tenders',
            'table.tender-table',
            'div[ng-repeat]',
            'tbody',
            'div.list-group',
            'div.results'
        ]

        for selector in container_candidates:
            try:
                element = await page.query_selector(selector)
                if element:
                    print(f"✓ Found container: {selector}")
                    results['listings_page']['selectors']['container'] = selector
                    break
            except:
                pass

        # Extract tender links
        print("\nExtracting tender links...")

        link_candidates = [
            'a[href*="Dossie"]',
            'a[href*="notice"]',
            'a[href*="tender"]',
            'a[href*="nabavka"]',
            'tbody tr a',
            'div.tender-item a',
            'a[ng-click*="view"]'
        ]

        found_links = []
        working_selector = None

        for selector in link_candidates:
            try:
                links = await page.query_selector_all(selector)
                if len(links) > 0:
                    print(f"✓ Found {len(links)} links with: {selector}")
                    working_selector = selector

                    # Get first 5 URLs
                    for link in links[:5]:
                        href = await link.get_attribute('href')
                        if href:
                            # Make absolute URL
                            if href.startswith('#'):
                                href = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx' + href
                            elif not href.startswith('http'):
                                href = 'https://e-nabavki.gov.mk' + href
                            found_links.append(href)
                    break
            except Exception as e:
                pass

        if working_selector:
            results['listings_page']['selectors']['tender_links'] = working_selector
            results['listings_page']['sample_tender_urls'] = found_links
            print(f"\nSample tender URLs:")
            for url in found_links[:3]:
                print(f"  - {url}")

        # Save listings page HTML for analysis
        print("\nSaving listings page HTML...")
        listings_html = await page.content()
        with open('/tmp/listings_page.html', 'w', encoding='utf-8') as f:
            f.write(listings_html)
        print("✓ Saved to /tmp/listings_page.html")

        # Follow first tender detail page
        if found_links:
            print("\n" + "=" * 80)
            print("STEP 2: Loading tender detail page...")
            print("=" * 80)

            detail_url = found_links[0]
            print(f"\nNavigating to: {detail_url}")

            await page.goto(detail_url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)

            # Save detail page HTML
            detail_html = await page.content()
            with open('/tmp/detail_page.html', 'w', encoding='utf-8') as f:
                f.write(detail_html)
            print("✓ Saved to /tmp/detail_page.html")

            results['detail_page']['sample_html'] = detail_html[:5000]  # First 5KB

            # Extract field selectors from detail page
            print("\nAnalyzing detail page structure...")

            # Look for ASP.NET control IDs (from open source project)
            aspnet_fields = {
                'procedure_type': 'lblProcedureType',
                'contract_duration': 'lblContractPeriod',
                'contract_signing_date': 'lblContractDate',
                'procurement_holder': 'lblNositel',
                'estimated_value': 'lblEstimatedContractValue',
                'awarded_value': 'lblAssignedContractValueVAT',
                'bureau_delivery_date': 'lblDeliveryDate',
                'contracting_entity_category': 'lblCategory',
                'title': 'lblName',
                'cpv_code': 'lblCPV',
                'closing_date': 'lblDeadline',
                'opening_date': 'lblOpeningDate',
                'publication_date': 'lblPublicationDate',
                'procuring_entity': 'lblName',
                'winner': 'lblWinner'
            }

            field_selectors = {}

            for field_name, control_id in aspnet_fields.items():
                # Try to find element with this ID
                try:
                    element = await page.query_selector(f'#{control_id}')
                    if element:
                        text_content = await element.text_content()
                        if text_content and text_content.strip():
                            field_selectors[field_name] = f'#{control_id}'
                            print(f"✓ {field_name}: #{control_id} = '{text_content.strip()[:50]}'")

                    # Also try with ASP.NET prefix
                    full_id = f'ctl00_ctl00_cphGlobal_cphPublicAccess_{control_id}'
                    element = await page.query_selector(f'#{full_id}')
                    if element:
                        text_content = await element.text_content()
                        if text_content and text_content.strip():
                            field_selectors[field_name] = f'#{full_id}'
                            print(f"✓ {field_name}: #{full_id} = '{text_content.strip()[:50]}'")
                except Exception as e:
                    pass

            results['detail_page']['selectors'] = field_selectors

            # Try to find documents section
            print("\nLooking for documents section...")
            doc_selectors = [
                'a[href*="Download"]',
                'a[href*=".pdf"]',
                'a[href*="File"]',
                'div.documents a',
                'table.attachments a'
            ]

            for selector in doc_selectors:
                try:
                    docs = await page.query_selector_all(selector)
                    if len(docs) > 0:
                        print(f"✓ Found {len(docs)} documents with: {selector}")
                        results['detail_page']['selectors']['documents'] = selector
                        break
                except:
                    pass

        await browser.close()

    return results

async def main():
    print("\n" + "=" * 80)
    print("E-NABAVKI.GOV.MK SELECTOR EXTRACTION")
    print("=" * 80)

    results = await extract_selectors()

    # Save results
    output_file = '/tmp/extracted_selectors.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"\nResults saved to: {output_file}")
    print("\nSummary:")
    print(f"  Listings selectors: {len(results['listings_page']['selectors'])}")
    print(f"  Sample tender URLs: {len(results['listings_page']['sample_tender_urls'])}")
    print(f"  Detail selectors: {len(results['detail_page']['selectors'])}")
    print("\nHTML files saved:")
    print("  - /tmp/listings_page.html")
    print("  - /tmp/detail_page.html")
    print("\nNext steps:")
    print("  1. Review extracted selectors in JSON file")
    print("  2. Update spider with real selectors")
    print("  3. Test scraping again")

if __name__ == '__main__':
    asyncio.run(main())

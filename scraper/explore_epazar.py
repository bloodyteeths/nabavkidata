#!/usr/bin/env python3
"""
E-Pazar Site Structure Explorer
Uses Playwright to manually analyze e-pazar.gov.mk
"""

import asyncio
import json
from playwright.async_api import async_playwright

BASE_URL = "https://e-pazar.gov.mk"

async def explore_site():
    """Explore e-pazar.gov.mk site structure"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='mk-MK'
        )
        page = await context.new_page()

        results = {
            'urls_tested': [],
            'api_calls': [],
            'navigation': [],
            'tender_selectors': [],
            'page_structure': {}
        }

        # Capture API calls
        async def capture_request(request):
            if '/api/' in request.url or 'notice' in request.url.lower():
                results['api_calls'].append({
                    'url': request.url,
                    'method': request.method
                })

        page.on('request', capture_request)

        print(f"\n{'='*60}")
        print("E-PAZAR SITE STRUCTURE EXPLORER")
        print(f"{'='*60}\n")

        # Test 1: Main page
        print("1. Testing main page...")
        await page.goto(BASE_URL, wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)  # Wait for React

        # Get navigation links
        nav_links = await page.query_selector_all('a')
        print(f"   Found {len(nav_links)} links on main page")

        for link in nav_links[:20]:
            try:
                href = await link.get_attribute('href')
                text = await link.inner_text()
                if href and text and len(text.strip()) > 0:
                    results['navigation'].append({
                        'text': text.strip()[:50],
                        'href': href
                    })
                    print(f"   - {text.strip()[:30]}: {href}")
            except:
                pass

        # Test 2: Check various URL patterns
        test_urls = [
            '/Notices',
            '/Notices/Search',
            '/Notices/Search?status=active',
            '/Notices/Search?status=awarded',
            '/PublicAuctions',
            '/ElectronicAuctions',
            '/MiniCompetitions',
            '/FrameworkAgreements',
        ]

        print("\n2. Testing URL patterns...")
        for url_path in test_urls:
            full_url = BASE_URL + url_path
            print(f"\n   Testing: {full_url}")
            results['urls_tested'].append(full_url)

            try:
                await page.goto(full_url, wait_until='networkidle', timeout=60000)
                await page.wait_for_timeout(5000)  # Wait for React to render

                # Check page title
                title = await page.title()
                print(f"   Title: {title}")

                # Look for tender/notice elements
                potential_selectors = [
                    'table tbody tr',
                    '.MuiTableRow-root',
                    '[class*="notice"]',
                    '[class*="tender"]',
                    '[class*="auction"]',
                    '.MuiCard-root',
                    '.MuiPaper-root',
                    '[data-testid]',
                    '.MuiListItem-root',
                    'table',
                ]

                for selector in potential_selectors:
                    elements = await page.query_selector_all(selector)
                    if elements and len(elements) > 0:
                        print(f"   Found {len(elements)} elements with selector: {selector}")

                        # Try to get more info
                        if len(elements) <= 10:
                            for i, elem in enumerate(elements[:3]):
                                try:
                                    text = await elem.inner_text()
                                    if text and len(text.strip()) > 0:
                                        print(f"      [{i}] {text.strip()[:100]}...")
                                except:
                                    pass

                        results['tender_selectors'].append({
                            'url': full_url,
                            'selector': selector,
                            'count': len(elements)
                        })

                # Get page HTML snippet
                content = await page.content()
                results['page_structure'][url_path] = {
                    'title': title,
                    'html_length': len(content),
                    'has_table': 'MuiTable' in content or '<table' in content,
                    'has_list': 'MuiList' in content,
                    'has_card': 'MuiCard' in content,
                }

            except Exception as e:
                print(f"   Error: {e}")
                results['page_structure'][url_path] = {'error': str(e)}

        # Test 3: Look for API endpoints in the page source
        print("\n3. Looking for API patterns in source...")
        await page.goto(BASE_URL + '/Notices/Search', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)

        content = await page.content()

        # Look for API URLs
        import re
        api_patterns = re.findall(r'["\']/(api/[^"\']+)["\']', content)
        if api_patterns:
            print("   Found API patterns:")
            for pattern in set(api_patterns)[:10]:
                print(f"   - {pattern}")
                results['api_calls'].append({'pattern': pattern})

        # Test 4: Network requests captured
        print("\n4. API calls captured during navigation:")
        for call in results['api_calls'][:20]:
            print(f"   {call}")

        # Save results
        output_path = '/home/ubuntu/nabavkidata/scraper/epazar_exploration.json'
        print(f"\n5. Saving results to: epazar_exploration.json")

        await browser.close()

        return results

if __name__ == '__main__':
    results = asyncio.run(explore_site())
    print("\n" + "="*60)
    print("EXPLORATION COMPLETE")
    print("="*60)
    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))

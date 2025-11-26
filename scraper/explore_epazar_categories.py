#!/usr/bin/env python3
"""
E-Pazar Categories Explorer
Explores each category to understand data structure and available fields
"""

import asyncio
import json
from playwright.async_api import async_playwright

BASE_URL = "https://e-pazar.gov.mk"

# Discovered categories from main page navigation
CATEGORIES = {
    'catalogue': '/catalogue',        # Е-Каталог
    'activeTenders': '/activeTenders', # Набавки од мала вредност (Active)
    'finishedTenders': '/finishedTenders',  # Одлуки (Decisions)
    'signedContracts': '/signedContracts',  # Склучени договори
}

async def explore_categories():
    """Explore each E-Pazar category"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='mk-MK'
        )
        page = await context.new_page()

        results = {
            'categories': {},
            'api_endpoints': [],
            'tender_fields': {},
        }

        # Track XHR/Fetch API calls
        async def capture_api(request):
            url = request.url
            if 'api' in url.lower() or 'graphql' in url.lower() or '.json' in url.lower():
                if 'google' not in url and 'analytics' not in url:
                    results['api_endpoints'].append({
                        'url': url,
                        'method': request.method
                    })

        page.on('request', capture_api)

        print(f"\n{'='*70}")
        print("E-PAZAR CATEGORIES DEEP EXPLORATION")
        print(f"{'='*70}\n")

        for cat_name, cat_path in CATEGORIES.items():
            full_url = BASE_URL + cat_path
            print(f"\n{'='*70}")
            print(f"EXPLORING: {cat_name} ({full_url})")
            print(f"{'='*70}")

            cat_result = {
                'url': full_url,
                'loaded': False,
                'elements_found': {},
                'table_structure': None,
                'sample_data': [],
                'pagination': None,
                'filters': [],
            }

            try:
                await page.goto(full_url, wait_until='networkidle', timeout=90000)
                await page.wait_for_timeout(8000)  # Wait extra for React to render

                cat_result['loaded'] = True

                # Get page content for inspection
                html = await page.content()
                cat_result['html_length'] = len(html)

                # Check for loading indicators
                loading = await page.query_selector('.loading, .spinner, [class*="loading"]')
                if loading:
                    print("  - Page still loading, waiting more...")
                    await page.wait_for_timeout(5000)

                # Look for main content containers
                containers = [
                    '.MuiContainer-root',
                    '.MuiPaper-root',
                    '.MuiCard-root',
                    '.MuiBox-root',
                    'main',
                    '#root > div',
                ]

                for selector in containers:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        cat_result['elements_found'][selector] = len(elements)
                        print(f"  Found {len(elements)} {selector} elements")

                # Look for tables (primary data structure)
                table_selectors = [
                    'table',
                    '.MuiTable-root',
                    '.MuiDataGrid-root',
                    '[role="grid"]',
                    '[role="table"]',
                ]

                for selector in table_selectors:
                    tables = await page.query_selector_all(selector)
                    if tables:
                        print(f"  Found {len(tables)} tables with: {selector}")

                        # Analyze first table structure
                        table = tables[0]

                        # Get headers
                        headers = await table.query_selector_all('th, .MuiTableCell-head, [role="columnheader"]')
                        header_texts = []
                        for h in headers:
                            text = await h.inner_text()
                            if text.strip():
                                header_texts.append(text.strip())

                        if header_texts:
                            cat_result['table_structure'] = header_texts
                            print(f"  Table headers: {header_texts}")

                        # Get sample data rows
                        rows = await table.query_selector_all('tbody tr, .MuiTableRow-root')
                        print(f"  Found {len(rows)} data rows")

                        for i, row in enumerate(rows[:3]):  # First 3 rows
                            cells = await row.query_selector_all('td, .MuiTableCell-body, [role="cell"]')
                            row_data = []
                            for cell in cells:
                                text = await cell.inner_text()
                                row_data.append(text.strip()[:100])  # Truncate long text
                            if row_data:
                                cat_result['sample_data'].append(row_data)
                                print(f"    Row {i+1}: {row_data[:5]}...")  # First 5 cells

                        break  # Found table, stop looking

                # Look for card-based listings
                card_selectors = [
                    '.MuiCard-root',
                    '[class*="tender-card"]',
                    '[class*="notice-card"]',
                    '[class*="item-card"]',
                ]

                for selector in card_selectors:
                    cards = await page.query_selector_all(selector)
                    if cards and len(cards) > 1:
                        print(f"  Found {len(cards)} cards with: {selector}")

                        # Analyze first card
                        card = cards[0]
                        card_text = await card.inner_text()
                        cat_result['sample_data'].append({'card_content': card_text[:500]})
                        print(f"    Card sample: {card_text[:200]}...")
                        break

                # Look for list items
                list_selectors = [
                    '.MuiList-root .MuiListItem-root',
                    '[class*="tender-list"] > div',
                    '[class*="notice-list"] > div',
                ]

                for selector in list_selectors:
                    items = await page.query_selector_all(selector)
                    if items and len(items) > 1:
                        print(f"  Found {len(items)} list items with: {selector}")
                        break

                # Look for pagination
                pagination_selectors = [
                    '.MuiPagination-root',
                    '.MuiTablePagination-root',
                    '[class*="pagination"]',
                    'nav[aria-label*="pagination"]',
                ]

                for selector in pagination_selectors:
                    pag = await page.query_selector(selector)
                    if pag:
                        pag_text = await pag.inner_text()
                        cat_result['pagination'] = pag_text.strip()[:100]
                        print(f"  Pagination found: {pag_text.strip()[:50]}...")
                        break

                # Look for filters/search
                filter_selectors = [
                    'input[type="text"]',
                    'input[type="search"]',
                    '.MuiSelect-root',
                    '.MuiAutocomplete-root',
                    '[class*="filter"]',
                    '[class*="search"]',
                ]

                for selector in filter_selectors:
                    filters = await page.query_selector_all(selector)
                    if filters:
                        for f in filters[:5]:
                            placeholder = await f.get_attribute('placeholder')
                            aria_label = await f.get_attribute('aria-label')
                            label = placeholder or aria_label or 'unknown'
                            cat_result['filters'].append(label)
                        print(f"  Filters found: {cat_result['filters']}")
                        break

                # Try to click on first item to see detail page structure
                clickable_selectors = [
                    'tbody tr:first-child',
                    '.MuiTableRow-root:not(.MuiTableRow-head)',
                    'a[href*="tender"]',
                    'a[href*="notice"]',
                    'a[href*="contract"]',
                    '[class*="item"] a',
                ]

                for selector in clickable_selectors:
                    clickable = await page.query_selector(selector)
                    if clickable:
                        # Get href if it's a link
                        href = await clickable.get_attribute('href')
                        if href:
                            cat_result['detail_link_pattern'] = href
                            print(f"  Detail link pattern: {href}")
                        break

            except Exception as e:
                print(f"  ERROR: {e}")
                cat_result['error'] = str(e)

            results['categories'][cat_name] = cat_result

        # Unique API endpoints discovered
        unique_apis = list(set([a['url'] for a in results['api_endpoints'] if 'google' not in a['url']]))
        print(f"\n{'='*70}")
        print("API ENDPOINTS DISCOVERED:")
        print(f"{'='*70}")
        for api in unique_apis[:20]:
            print(f"  {api}")

        await browser.close()

        return results

if __name__ == '__main__':
    results = asyncio.run(explore_categories())

    # Save detailed results
    with open('epazar_categories_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE - Saved to epazar_categories_analysis.json")
    print(f"{'='*70}")

    # Summary
    print("\nSUMMARY:")
    for cat_name, cat_data in results['categories'].items():
        print(f"\n{cat_name}:")
        print(f"  - URL: {cat_data.get('url')}")
        print(f"  - Loaded: {cat_data.get('loaded')}")
        if cat_data.get('table_structure'):
            print(f"  - Columns: {cat_data['table_structure']}")
        if cat_data.get('sample_data'):
            print(f"  - Sample rows: {len(cat_data['sample_data'])}")
        if cat_data.get('pagination'):
            print(f"  - Pagination: {cat_data['pagination']}")

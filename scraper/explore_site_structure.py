#!/usr/bin/env python3
"""
E-Nabavki Website Structure Explorer
Uses Playwright to discover all tender categories, URLs, and navigation paths.
This script runs with JavaScript execution to properly render the Angular SPA.
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = "https://e-nabavki.gov.mk"

async def explore_site_structure():
    """Explore e-nabavki.gov.mk to discover all tender categories and URLs."""

    results = {
        "exploration_date": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "categories_discovered": [],
        "navigation_links": [],
        "sample_tenders": {},
        "api_endpoints": [],
        "errors": []
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="mk-MK"
        )

        # Capture XHR/Fetch requests to discover API endpoints
        api_calls = []

        page = await context.new_page()

        # Intercept network requests to find API endpoints
        async def handle_request(request):
            if request.resource_type in ["xhr", "fetch"]:
                api_calls.append({
                    "url": request.url,
                    "method": request.method,
                    "resource_type": request.resource_type
                })

        page.on("request", handle_request)

        try:
            # 1. Navigate to homepage and wait for Angular to load
            print("Step 1: Loading homepage...")
            await page.goto(f"{BASE_URL}/PublicAccess/home.aspx#/home", wait_until="networkidle")
            await page.wait_for_timeout(3000)

            # 2. Get all navigation links
            print("Step 2: Extracting navigation links...")
            nav_links = await page.evaluate("""
                () => {
                    const links = [];
                    // Get all anchor tags
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.getAttribute('href');
                        const text = a.innerText.trim();
                        if (href && text && (href.includes('#/') || href.includes('PublicAccess'))) {
                            links.push({
                                text: text,
                                href: href,
                                fullUrl: a.href
                            });
                        }
                    });
                    // Get navigation menu items
                    document.querySelectorAll('nav a, .navbar a, .menu a, [ng-click]').forEach(el => {
                        const text = el.innerText.trim();
                        const ngClick = el.getAttribute('ng-click');
                        if (text || ngClick) {
                            links.push({
                                text: text,
                                ngClick: ngClick,
                                tagName: el.tagName
                            });
                        }
                    });
                    return links;
                }
            """)
            results["navigation_links"] = nav_links

            # 3. Try known category routes
            print("Step 3: Testing category routes...")
            routes_to_test = [
                "#/notices",      # Active tenders
                "#/awarded",      # Awarded tenders
                "#/cancelled",    # Cancelled tenders
                "#/archive",      # Historical/archive
                "#/completed",    # Completed contracts
                "#/planned",      # Planned tenders
                "#/contracts",    # Contracts
                "#/decisions",    # Decisions
                "#/home",         # Home
                "#/sitemap",      # Sitemap
            ]

            for route in routes_to_test:
                try:
                    url = f"{BASE_URL}/PublicAccess/home.aspx{route}"
                    print(f"  Testing: {url}")
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                    await page.wait_for_timeout(2000)

                    # Check if page has content
                    content = await page.content()
                    has_tenders = ".RowStyle" in content or ".AltRowStyle" in content or "tender" in content.lower()
                    title = await page.title()

                    # Count table rows
                    row_count = await page.evaluate("""
                        () => document.querySelectorAll('.RowStyle, .AltRowStyle, tr[ng-repeat]').length
                    """)

                    results["categories_discovered"].append({
                        "route": route,
                        "url": url,
                        "accessible": True,
                        "has_tenders": has_tenders,
                        "row_count": row_count,
                        "title": title
                    })
                except Exception as e:
                    results["categories_discovered"].append({
                        "route": route,
                        "url": url,
                        "accessible": False,
                        "error": str(e)
                    })

            # 4. Go to main notices page and explore filtering options
            print("Step 4: Exploring notices page filters...")
            await page.goto(f"{BASE_URL}/PublicAccess/home.aspx#/notices", wait_until="networkidle")
            await page.wait_for_timeout(3000)

            # Get all dropdown/filter options
            filters = await page.evaluate("""
                () => {
                    const filters = [];
                    document.querySelectorAll('select, [ng-model], .dropdown, .filter').forEach(el => {
                        const options = [];
                        el.querySelectorAll('option').forEach(opt => {
                            options.push({value: opt.value, text: opt.innerText.trim()});
                        });
                        filters.push({
                            id: el.id,
                            name: el.name,
                            ngModel: el.getAttribute('ng-model'),
                            options: options
                        });
                    });
                    return filters;
                }
            """)
            results["filters"] = filters

            # 5. Extract sample tender URLs from the listing
            print("Step 5: Extracting sample tender URLs...")
            tender_links = await page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('.RowStyle a[href], .AltRowStyle a[href]').forEach(a => {
                        links.push({
                            href: a.getAttribute('href'),
                            fullUrl: a.href,
                            text: a.innerText.trim().substring(0, 100)
                        });
                    });
                    return links.slice(0, 10);  // Get first 10
                }
            """)
            results["sample_tenders"]["active"] = tender_links

            # 6. Try to find status-based filtering
            print("Step 6: Looking for status filters...")
            status_elements = await page.evaluate("""
                () => {
                    const statuses = [];
                    // Look for tabs, buttons, or links that might filter by status
                    document.querySelectorAll('[class*="tab"], [class*="status"], [class*="filter"], button, .nav-item').forEach(el => {
                        const text = el.innerText.trim();
                        if (text && text.length < 50) {
                            statuses.push({
                                text: text,
                                className: el.className,
                                tagName: el.tagName
                            });
                        }
                    });
                    return statuses;
                }
            """)
            results["status_elements"] = status_elements

            # 7. Check for Angular routes in the page source
            print("Step 7: Extracting Angular routes...")
            angular_info = await page.evaluate("""
                () => {
                    const info = {
                        routes: [],
                        ngApp: null,
                        controllers: []
                    };
                    // Try to get Angular app info
                    if (window.angular) {
                        const injector = angular.element(document.body).injector();
                        if (injector) {
                            try {
                                const $route = injector.get('$route');
                                if ($route && $route.routes) {
                                    for (let path in $route.routes) {
                                        info.routes.push(path);
                                    }
                                }
                            } catch(e) {}
                        }
                    }
                    // Look for ng-app attribute
                    const ngApp = document.querySelector('[ng-app]');
                    if (ngApp) {
                        info.ngApp = ngApp.getAttribute('ng-app');
                    }
                    return info;
                }
            """)
            results["angular_info"] = angular_info

            # 8. Save API endpoints discovered
            results["api_endpoints"] = api_calls

            # 9. Take screenshots of key pages
            print("Step 8: Taking screenshots...")
            await page.goto(f"{BASE_URL}/PublicAccess/home.aspx#/notices", wait_until="networkidle")
            await page.wait_for_timeout(2000)
            await page.screenshot(path="/tmp/e_nabavki_notices.png", full_page=False)

        except Exception as e:
            results["errors"].append(str(e))
            print(f"Error during exploration: {e}")

        finally:
            await browser.close()

    return results

async def main():
    print("="*60)
    print("E-NABAVKI WEBSITE STRUCTURE EXPLORER")
    print("="*60)

    results = await explore_site_structure()

    # Save results to JSON
    output_file = "/tmp/e_nabavki_site_structure.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_file}")

    # Print summary
    print("\n" + "="*60)
    print("DISCOVERY SUMMARY")
    print("="*60)

    print(f"\nCategories tested: {len(results.get('categories_discovered', []))}")
    for cat in results.get('categories_discovered', []):
        status = "✓" if cat.get('accessible') and cat.get('has_tenders') else "✗"
        print(f"  {status} {cat['route']}: rows={cat.get('row_count', 'N/A')}")

    print(f"\nNavigation links found: {len(results.get('navigation_links', []))}")
    print(f"API endpoints captured: {len(results.get('api_endpoints', []))}")
    print(f"Sample tenders found: {len(results.get('sample_tenders', {}).get('active', []))}")

    if results.get('angular_info', {}).get('routes'):
        print(f"\nAngular routes discovered: {results['angular_info']['routes']}")

    # Print full JSON for inspection
    print("\n" + "="*60)
    print("FULL RESULTS (JSON)")
    print("="*60)
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())

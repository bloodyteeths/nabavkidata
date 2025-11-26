#!/usr/bin/env python3
"""
Comprehensive route discovery for e-nabavki.gov.mk
Discovers all available routes by analyzing navigation and Angular routes.
"""

import asyncio
from playwright.async_api import async_playwright
import json
import re

async def discover_all_routes():
    """Discover all available routes on e-nabavki.gov.mk"""

    results = {
        "menu_links": [],
        "angular_routes": [],
        "working_routes": [],
        "failed_routes": [],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="mk-MK"
        )

        page = await context.new_page()

        # Step 1: Load main page and extract all menu links
        print("Step 1: Loading main page to extract navigation links...")
        try:
            await page.goto(
                "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/home",
                wait_until="networkidle",
                timeout=60000
            )
            await page.wait_for_timeout(5000)

            # Extract all href links
            all_links = await page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.getAttribute('href');
                        const text = a.innerText.trim().substring(0, 100);
                        if (href && (href.includes('#/') || href.includes('home.aspx'))) {
                            links.push({
                                href: href,
                                text: text,
                                fullUrl: a.href
                            });
                        }
                    });
                    return links;
                }
            """)
            results["menu_links"] = all_links
            print(f"Found {len(all_links)} navigation links")

            # Extract Angular routes from page source
            content = await page.content()

            # Look for route definitions in JavaScript
            route_patterns = re.findall(r'#/([a-zA-Z0-9_/-]+)', content)
            results["angular_routes"] = list(set(route_patterns))
            print(f"Found {len(results['angular_routes'])} Angular routes in page source")

        except Exception as e:
            print(f"Error in step 1: {e}")

        # Step 2: Test all discovered routes
        print("\nStep 2: Testing discovered routes...")

        base_urls = [
            "https://e-nabavki.gov.mk/PublicAccess/home.aspx",
        ]

        # Combine routes from navigation and content analysis
        routes_to_test = set()

        # Add routes from navigation links
        for link in results["menu_links"]:
            if '#/' in link.get('href', ''):
                route = '#/' + link['href'].split('#/')[-1]
                routes_to_test.add(route)

        # Add routes from page source
        for route in results["angular_routes"]:
            routes_to_test.add(f"#/{route}")

        # Add additional candidate routes
        additional_routes = [
            "#/notices",
            "#/home",
            "#/awarded",
            "#/contracts",
            "#/concluded",
            "#/realized",
            "#/cancelled",
            "#/annulled",
            "#/archive",
            "#/historical",
            "#/planned",
            "#/sitemap",
            "#/askquestion",
            "#/realizacija",  # Macedonian "realization"
            "#/skluchen",     # Macedonian "concluded"
            "#/ponisten",     # Macedonian "cancelled"
            "#/odluka",       # Macedonian "decision"
            "#/dodeleni",     # Macedonian "awarded"
        ]
        routes_to_test.update(additional_routes)

        print(f"Testing {len(routes_to_test)} unique routes...")

        await page.close()

        for route in sorted(routes_to_test):
            page = await context.new_page()
            for base_url in base_urls:
                full_url = f"{base_url}{route}"
                try:
                    await page.goto(full_url, wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(2000)

                    # Check if route worked (didn't redirect to home)
                    current_url = page.url

                    # Check for content indicators
                    content = await page.content()
                    has_table = "table" in content.lower()
                    has_grid = "grid" in content.lower()
                    row_count = await page.evaluate("""
                        () => {
                            return document.querySelectorAll('table tbody tr, .RowStyle, .AltRowStyle, [ng-repeat*="item"]').length;
                        }
                    """)

                    route_info = {
                        "route": route,
                        "url": full_url,
                        "final_url": current_url,
                        "redirected": current_url != full_url,
                        "has_table": has_table,
                        "has_grid": has_grid,
                        "row_count": row_count
                    }

                    if route in current_url and row_count > 0:
                        results["working_routes"].append(route_info)
                        status = "✓ WORKING"
                    elif route in current_url:
                        results["working_routes"].append(route_info)
                        status = "~ ACCESSIBLE (no data)"
                    else:
                        results["failed_routes"].append(route_info)
                        status = "✗ REDIRECTED"

                    print(f"  {status}: {route} -> {row_count} rows")

                except Exception as e:
                    results["failed_routes"].append({
                        "route": route,
                        "url": full_url,
                        "error": str(e)
                    })
                    print(f"  ✗ ERROR: {route} - {str(e)[:50]}")

            await page.close()

        await browser.close()

    # Save results
    with open("/tmp/e_nabavki_all_routes.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Menu links found: {len(results['menu_links'])}")
    print(f"Angular routes found: {len(results['angular_routes'])}")
    print(f"Working routes: {len(results['working_routes'])}")
    print(f"Failed routes: {len(results['failed_routes'])}")

    print("\nWorking routes with data:")
    for route in results["working_routes"]:
        if route.get("row_count", 0) > 0:
            print(f"  {route['route']}: {route['row_count']} rows")

    print("\nResults saved to: /tmp/e_nabavki_all_routes.json")

if __name__ == "__main__":
    asyncio.run(discover_all_routes())

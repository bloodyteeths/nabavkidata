#!/usr/bin/env python3
"""
Discover routes on InstitutionGridData.aspx
This is where awarded contracts/concluded tenders might be.
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def discover_institution_routes():
    """Discover routes on InstitutionGridData.aspx"""

    results = {
        "menu_links": [],
        "working_routes": [],
        "failed_routes": [],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="mk-MK"
        )

        # Step 1: Load InstitutionGridData page and extract menu links
        print("Step 1: Loading InstitutionGridData page...")
        page = await context.new_page()

        try:
            await page.goto(
                "https://e-nabavki.gov.mk/InstitutionGridData.aspx#/home",
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
                        if (href) {
                            links.push({
                                href: href,
                                text: text
                            });
                        }
                    });
                    return links;
                }
            """)

            # Filter for hash routes
            hash_routes = [l for l in all_links if '#/' in l.get('href', '')]
            results["menu_links"] = hash_routes
            print(f"Found {len(hash_routes)} hash route links")

            for link in hash_routes[:30]:
                print(f"  {link['href']}: {link['text'][:50]}")

        except Exception as e:
            print(f"Error loading page: {e}")

        await page.close()

        # Step 2: Test routes found in the menu
        print("\nStep 2: Testing routes from menu...")

        base_url = "https://e-nabavki.gov.mk/InstitutionGridData.aspx"

        # Routes to test (from menu + guesses)
        routes_to_test = set()

        # Add from menu
        for link in results["menu_links"]:
            href = link.get('href', '')
            if '#/' in href:
                route = '#/' + href.split('#/')[-1]
                routes_to_test.add(route)

        # Add guessed routes
        guesses = [
            "#/home",
            "#/ciContractsGrid",  # Found earlier
            "#/ciNoticesGrid",
            "#/ciCancelledGrid",
            "#/ciArchiveGrid",
            "#/ciPlannedGrid",
            "#/contracts",
            "#/notices",
            "#/cancelled",
            "#/archive",
            "#/planned",
            "#/concluded",
            "#/realized",
            "#/dogovori",
            "#/oglasi",
            "#/realizirani",
        ]
        routes_to_test.update(guesses)

        print(f"Testing {len(routes_to_test)} routes...")

        for route in sorted(routes_to_test):
            page = await context.new_page()
            full_url = f"{base_url}{route}"

            try:
                await page.goto(full_url, wait_until="networkidle", timeout=45000)
                await page.wait_for_timeout(3000)

                current_url = page.url

                # Check for data
                row_count = await page.evaluate("""
                    () => {
                        return document.querySelectorAll('table tbody tr, .RowStyle, .AltRowStyle, [ng-repeat*="item"]').length;
                    }
                """)

                # Get page title or main heading
                title = await page.title()

                route_info = {
                    "route": route,
                    "url": full_url,
                    "final_url": current_url,
                    "redirected": route not in current_url,
                    "row_count": row_count,
                    "title": title
                }

                if route in current_url and row_count > 0:
                    results["working_routes"].append(route_info)
                    status = "✓ WORKING"
                elif route in current_url:
                    results["working_routes"].append(route_info)
                    status = "~ ACCESSIBLE"
                else:
                    results["failed_routes"].append(route_info)
                    status = "✗ REDIRECTED"

                print(f"  {status}: {route} -> {row_count} rows")

            except Exception as e:
                results["failed_routes"].append({
                    "route": route,
                    "url": full_url,
                    "error": str(e)[:100]
                })
                print(f"  ✗ ERROR: {route} - {str(e)[:50]}")

            await page.close()

        await browser.close()

    # Save results
    with open("/tmp/e_nabavki_institution_routes.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "="*60)
    print("SUMMARY - InstitutionGridData.aspx")
    print("="*60)
    print(f"Menu links found: {len(results['menu_links'])}")
    print(f"Working routes: {len(results['working_routes'])}")
    print(f"Failed routes: {len(results['failed_routes'])}")

    print("\nWorking routes:")
    for route in results["working_routes"]:
        print(f"  {route['route']}: {route['row_count']} rows")

    print("\nResults saved to: /tmp/e_nabavki_institution_routes.json")

if __name__ == "__main__":
    asyncio.run(discover_institution_routes())

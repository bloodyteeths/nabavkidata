#!/usr/bin/env python3
"""
Analyze a real tender detail page structure.
Checks for bidders, lots, documents, and all available data.
"""

import asyncio
from playwright.async_api import async_playwright
import json
import re

async def analyze_tender_page(tender_url: str):
    """Analyze a tender detail page for available data"""

    result = {
        "url": tender_url,
        "fields_found": {},
        "tables_found": [],
        "bidders_section": None,
        "lots_section": None,
        "documents_section": None,
        "raw_text_sample": "",
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="mk-MK"
        )

        page = await context.new_page()

        try:
            await page.goto(tender_url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(5000)

            # Get all label-value pairs
            labels_values = await page.evaluate("""
                () => {
                    const pairs = [];
                    // Pattern 1: label followed by value label
                    document.querySelectorAll('label.dosie-label').forEach(label => {
                        const key = label.innerText.trim();
                        const valueEl = label.nextElementSibling;
                        if (valueEl && valueEl.classList.contains('dosie-value')) {
                            const value = valueEl.innerText.trim();
                            if (key && value) {
                                pairs.push({key: key, value: value.substring(0, 200)});
                            }
                        }
                    });
                    // Pattern 2: th-td pairs
                    document.querySelectorAll('table tr').forEach(row => {
                        const th = row.querySelector('th');
                        const td = row.querySelector('td');
                        if (th && td) {
                            pairs.push({key: th.innerText.trim(), value: td.innerText.trim().substring(0, 200)});
                        }
                    });
                    return pairs;
                }
            """)
            result["fields_found"] = {p['key']: p['value'] for p in labels_values if p['key']}

            # Check for tables
            tables = await page.evaluate("""
                () => {
                    const tables = [];
                    document.querySelectorAll('table').forEach((table, idx) => {
                        const headers = [];
                        table.querySelectorAll('th').forEach(th => {
                            headers.push(th.innerText.trim());
                        });
                        const rowCount = table.querySelectorAll('tbody tr').length;
                        tables.push({
                            index: idx,
                            headers: headers,
                            rowCount: rowCount,
                            hasClass: table.className
                        });
                    });
                    return tables;
                }
            """)
            result["tables_found"] = tables

            # Check for bidder-related sections
            bidder_html = await page.evaluate("""
                () => {
                    const keywords = ['понудувач', 'bidder', 'учесник', 'participant', 'победник', 'winner', 'добитник'];
                    const sections = [];
                    document.body.querySelectorAll('*').forEach(el => {
                        const text = el.innerText?.toLowerCase() || '';
                        if (keywords.some(k => text.includes(k))) {
                            const html = el.outerHTML?.substring(0, 500);
                            if (html && !sections.some(s => s.includes(html.substring(0, 100)))) {
                                sections.push(html);
                            }
                        }
                    });
                    return sections.slice(0, 5);
                }
            """)
            result["bidders_section"] = bidder_html

            # Check for lot-related sections
            lot_html = await page.evaluate("""
                () => {
                    const keywords = ['лот', 'lot', 'делива', 'dividable', 'партија', 'part'];
                    const sections = [];
                    document.body.querySelectorAll('*').forEach(el => {
                        const text = el.innerText?.toLowerCase() || '';
                        if (keywords.some(k => text.includes(k))) {
                            const html = el.outerHTML?.substring(0, 500);
                            if (html && !sections.some(s => s.includes(html.substring(0, 100)))) {
                                sections.push(html);
                            }
                        }
                    });
                    return sections.slice(0, 5);
                }
            """)
            result["lots_section"] = lot_html

            # Check for document links
            doc_links = await page.evaluate("""
                () => {
                    const docs = [];
                    document.querySelectorAll('a[href*="download"], a[href*="document"], a[href*=".pdf"], a[href*=".doc"]').forEach(a => {
                        docs.push({
                            text: a.innerText?.trim().substring(0, 100),
                            href: a.getAttribute('href')
                        });
                    });
                    // Also check for document section
                    document.querySelectorAll('[class*="document"], [class*="attachment"], [ng-repeat*="document"]').forEach(el => {
                        docs.push({
                            text: el.innerText?.trim().substring(0, 100),
                            href: el.querySelector('a')?.getAttribute('href')
                        });
                    });
                    return docs.slice(0, 10);
                }
            """)
            result["documents_section"] = doc_links

            # Get key fields specifically
            key_fields_check = await page.evaluate("""
                () => {
                    const checks = {
                        has_winner: false,
                        has_bidders_table: false,
                        has_lots: false,
                        has_documents: false,
                        status: '',
                        dividable: ''
                    };

                    const text = document.body.innerText.toLowerCase();

                    // Check for winner
                    checks.has_winner = text.includes('победник') || text.includes('добитник') || text.includes('winner');

                    // Check for bidders table
                    document.querySelectorAll('table').forEach(t => {
                        const headers = t.innerText.toLowerCase();
                        if (headers.includes('понудувач') || headers.includes('bidder') || headers.includes('учесник')) {
                            checks.has_bidders_table = true;
                        }
                    });

                    // Check for lots
                    checks.has_lots = text.includes('делива набавка: да') || text.includes('dividable: yes');

                    // Check for documents
                    checks.has_documents = document.querySelectorAll('a[href*="download"], a[href*=".pdf"], a[href*=".doc"]').length > 0;

                    // Find status field
                    const statusLabel = document.querySelector('label:contains("Статус"), label:contains("Status")');
                    if (statusLabel) {
                        const valueEl = statusLabel.nextElementSibling;
                        if (valueEl) checks.status = valueEl.innerText?.trim();
                    }

                    // Find dividable field
                    const divLabel = Array.from(document.querySelectorAll('label')).find(l =>
                        l.innerText?.includes('Делива') || l.innerText?.includes('Dividable')
                    );
                    if (divLabel) {
                        const valueEl = divLabel.nextElementSibling;
                        if (valueEl) checks.dividable = valueEl.innerText?.trim();
                    }

                    return checks;
                }
            """)
            result["key_checks"] = key_fields_check

            # Screenshot
            await page.screenshot(path="/tmp/tender_analysis.png")

        except Exception as e:
            result["error"] = str(e)

        finally:
            await browser.close()

    return result

async def main():
    # Test with a real tender URL from our database
    tender_urls = [
        "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/68819af5-0ecf-419e-b32a-1e27f855f960",
        "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/f14f1e48-0a71-4b62-9b3d-1e27f855f960",
    ]

    for url in tender_urls:
        print(f"\n{'='*60}")
        print(f"Analyzing: {url}")
        print("="*60)

        result = await analyze_tender_page(url)

        print("\nKey Checks:")
        if "key_checks" in result:
            for k, v in result["key_checks"].items():
                print(f"  {k}: {v}")

        print(f"\nFields Found: {len(result.get('fields_found', {}))}")
        for k, v in list(result.get('fields_found', {}).items())[:15]:
            print(f"  {k}: {v[:80]}...")

        print(f"\nTables Found: {len(result.get('tables_found', []))}")
        for t in result.get('tables_found', []):
            print(f"  Table {t['index']}: {t['headers'][:5]} ({t['rowCount']} rows)")

        print(f"\nDocuments: {len(result.get('documents_section', []))}")
        for d in result.get('documents_section', [])[:5]:
            print(f"  {d.get('text', 'N/A')[:50]}: {d.get('href', 'N/A')[:50]}")

        # Save full result
        with open(f"/tmp/tender_analysis_{url.split('/')[-1][:20]}.json", "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Analyze tender detail page structure to understand field extraction.
"""
import asyncio
from playwright.async_api import async_playwright

async def analyze_tender_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Test with an awarded tender
        url = "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/53e296c7-fc8b-46e6-97d3-48f4ea309acf"
        print(f"Loading: {url}")

        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Wait for content
        try:
            await page.wait_for_selector("label.dosie-value", timeout=15000)
            print("Page loaded successfully")
        except:
            print("Timeout waiting for dosie-value")

        # Get all label-value pairs
        print("\n" + "="*60)
        print("ALL LABEL-FOR ATTRIBUTES AND VALUES")
        print("="*60)

        labels = await page.query_selector_all("label[label-for]")
        for label in labels[:50]:  # First 50 labels
            label_for = await label.get_attribute("label-for") or ""
            label_text = (await label.inner_text()).strip()

            # Try to find next sibling value
            value = await page.evaluate("""(el) => {
                let next = el.nextElementSibling;
                while(next) {
                    if(next.classList && next.classList.contains('dosie-value')) {
                        return next.innerText.trim();
                    }
                    next = next.nextElementSibling;
                }
                return null;
            }""", label)

            if value and len(value) > 0:
                display_value = value[:100] + "..." if len(value) > 100 else value
                print(f"  [{label_for}] {label_text} => {display_value}")

        # Get all dosie-value elements
        print("\n" + "="*60)
        print("ALL DOSIE-VALUE ELEMENTS WITH PRECEDING LABELS")
        print("="*60)

        dosie_values = await page.query_selector_all("label.dosie-value")
        for dv in dosie_values[:50]:
            value = (await dv.inner_text()).strip()
            if value:
                # Try to find preceding label
                prev_label = await page.evaluate("""(el) => {
                    let prev = el.previousElementSibling;
                    while(prev) {
                        if(prev.tagName === 'LABEL' && prev.getAttribute('label-for')) {
                            return prev.innerText.trim();
                        }
                        prev = prev.previousElementSibling;
                    }
                    return null;
                }""", dv)

                display_value = value[:80] + "..." if len(value) > 80 else value
                print(f"  {prev_label or '[UNKNOWN]'}: {display_value}")

        # Get tabs
        print("\n" + "="*60)
        print("NAVIGATION TABS")
        print("="*60)

        tabs = await page.query_selector_all(".nav-tabs li a, .nav-link, [role='tab']")
        for tab in tabs[:15]:
            text = (await tab.inner_text()).strip()
            if text:
                href = await tab.get_attribute("href") or ""
                print(f"  Tab: {text} [{href}]")

        # Save page HTML for inspection
        html = await page.content()
        with open("/tmp/tender_detail.html", "w") as f:
            f.write(html)
        print(f"\nHTML saved to /tmp/tender_detail.html ({len(html)} bytes)")

        # Extract specific sections
        print("\n" + "="*60)
        print("SEARCHING FOR KEY FIELDS")
        print("="*60)

        key_searches = [
            ("Subject/Description", ["Предмет на договорот", "Предмет на делот", "Опис"]),
            ("CPV Code", ["CPV", "ЦПВ"]),
            ("Winner/Operator", ["Добитник", "Избран понудувач", "Економски оператор"]),
            ("Contract Value", ["Вредност на договорот", "Цена", "Износ"]),
            ("Contracting Authority", ["Договорен орган", "Назив на договорниот орган"]),
        ]

        for section_name, keywords in key_searches:
            print(f"\n  {section_name}:")
            for keyword in keywords:
                try:
                    selector = f"*:has-text('{keyword}')"
                    elems = await page.query_selector_all(selector)
                    for elem in elems[:3]:
                        text = (await elem.inner_text()).strip()
                        if text and len(text) < 500:
                            print(f"    [{keyword}]: {text[:200]}...")
                            break
                except Exception as e:
                    pass

        await browser.close()

if __name__ == "__main__":
    asyncio.run(analyze_tender_page())

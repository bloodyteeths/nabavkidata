#!/usr/bin/env python3
"""
Research script to investigate where participant/bidder contact information
(emails, phones) is available on e-nabavki.gov.mk

This script will:
1. Check awarded tender pages for participant lists
2. Look for bidder/winner contact details
3. Check if login reveals more data
4. Document all fields with contact information
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright

# Login credentials
USERNAME = 'teknomed'
PASSWORD = '7Jb*Gr=2'

async def research_contact_data():
    """Research where contact data (emails, phones) is available"""

    results = {
        'timestamp': datetime.utcnow().isoformat(),
        'findings': [],
        'contact_fields_found': [],
        'pages_checked': [],
        'recommendations': []
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="mk-MK"
        )

        page = await context.new_page()

        # =====================================================
        # 1. CHECK PUBLIC ACCESS PAGES (NO LOGIN)
        # =====================================================
        print("\n" + "="*70)
        print("PHASE 1: CHECKING PUBLIC ACCESS PAGES (NO LOGIN)")
        print("="*70)

        public_urls = [
            ("https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0", "Awarded Contracts"),
            ("https://e-nabavki.gov.mk/PublicAccess/home.aspx#/tender-winners/0", "Tender Winners"),
            ("https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices", "Active Tenders"),
        ]

        for url, description in public_urls:
            print(f"\n--- Checking: {description} ---")
            print(f"URL: {url}")

            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(5000)

                # Look for table rows
                rows = await page.query_selector_all('table tbody tr')
                print(f"Found {len(rows)} table rows")

                # Get first tender link to check detail page
                tender_links = await page.query_selector_all("a[href*='dossie']")
                print(f"Found {len(tender_links)} tender detail links")

                if tender_links:
                    # Click first tender to see detail page
                    first_link = tender_links[0]
                    href = await first_link.get_attribute('href')
                    print(f"Checking first tender detail: {href}")

                    # Navigate to detail page
                    if href.startswith('#'):
                        detail_url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx' + href
                    else:
                        detail_url = href

                    await page.goto(detail_url, wait_until="networkidle", timeout=60000)
                    await page.wait_for_timeout(3000)

                    # Search for contact-related labels
                    contact_labels = [
                        'Е-пошта', 'E-mail', 'Email', 'email',
                        'Телефон', 'Phone', 'Тел',
                        'Контакт', 'Contact',
                        'Понудувач', 'Bidder', 'Учесник', 'Participant',
                        'Добитник', 'Winner',
                        'Економски оператор', 'Economic operator',
                    ]

                    content = await page.content()

                    print(f"\nSearching for contact-related fields in {description}:")
                    for label in contact_labels:
                        if label.lower() in content.lower():
                            count = content.lower().count(label.lower())
                            print(f"  ✓ Found '{label}': {count} occurrences")
                            results['contact_fields_found'].append({
                                'label': label,
                                'page': description,
                                'count': count,
                                'requires_login': False
                            })

                    # Look for specific XPath patterns for emails
                    email_patterns = await page.query_selector_all('label.dosie-value')
                    email_found = False
                    for elem in email_patterns:
                        text = await elem.inner_text()
                        if '@' in text:
                            print(f"  ✓✓ EMAIL FOUND: {text}")
                            email_found = True
                            results['findings'].append({
                                'type': 'email',
                                'value': text,
                                'page': description,
                                'requires_login': False
                            })

                    if not email_found:
                        print("  ✗ No email addresses found in public view")

                    # Save screenshot
                    await page.screenshot(path=f"/tmp/research_{description.replace(' ', '_')}_public.png")

                results['pages_checked'].append({
                    'url': url,
                    'description': description,
                    'public': True,
                    'tender_count': len(tender_links)
                })

            except Exception as e:
                print(f"  Error: {e}")

        # =====================================================
        # 2. LOGIN AND CHECK AUTHENTICATED PAGES
        # =====================================================
        print("\n" + "="*70)
        print("PHASE 2: CHECKING WITH AUTHENTICATION")
        print("="*70)

        # Navigate to login page
        await page.goto('https://e-nabavki.gov.mk/PublicAccess/home.aspx#/home', wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Try to login
        print("\nAttempting login...")

        # Look for login button
        login_clicked = False
        login_selectors = [
            'a:has-text("Најава")',
            'a:has-text("Login")',
            'button:has-text("Најава")',
            '.login-button',
        ]

        for selector in login_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(2000)
                    login_clicked = True
                    print(f"  Clicked login button: {selector}")
                    break
            except:
                continue

        if login_clicked:
            # Fill credentials
            try:
                # Username
                username_field = await page.query_selector('input[type="text"], input[name*="user"]')
                if username_field:
                    await username_field.fill(USERNAME)
                    print("  Filled username")

                # Password
                password_field = await page.query_selector('input[type="password"]')
                if password_field:
                    await password_field.fill(PASSWORD)
                    print("  Filled password")

                # Submit
                submit_btn = await page.query_selector('button[type="submit"], button:has-text("Најави")')
                if submit_btn:
                    await submit_btn.click()
                    await page.wait_for_timeout(5000)
                    print("  Submitted login form")

                # Check if logged in
                content = await page.content()
                if 'одјава' in content.lower() or 'logout' in content.lower():
                    print("  ✓ LOGIN SUCCESSFUL!")
                    results['findings'].append({
                        'type': 'login',
                        'status': 'success',
                        'username': USERNAME
                    })

                    # Now check authenticated pages
                    auth_urls = [
                        ("https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0", "Contracts (Auth)"),
                        ("https://e-nabavki.gov.mk/PublicAccess/home.aspx#/tender-winners/0", "Winners (Auth)"),
                    ]

                    for url, description in auth_urls:
                        print(f"\n--- Checking (Authenticated): {description} ---")

                        await page.goto(url, wait_until="networkidle", timeout=60000)
                        await page.wait_for_timeout(5000)

                        # Get tender links
                        tender_links = await page.query_selector_all("a[href*='dossie']")
                        print(f"Found {len(tender_links)} tender links")

                        if tender_links:
                            href = await tender_links[0].get_attribute('href')
                            if href.startswith('#'):
                                detail_url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx' + href
                            else:
                                detail_url = href

                            await page.goto(detail_url, wait_until="networkidle", timeout=60000)
                            await page.wait_for_timeout(3000)

                            content = await page.content()

                            # Search more thoroughly for contact info
                            print(f"\nSearching for contact data (authenticated):")

                            # Look for emails anywhere in content
                            import re
                            emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)
                            if emails:
                                print(f"  ✓✓ EMAILS FOUND: {list(set(emails))[:10]}")
                                for email in list(set(emails))[:10]:
                                    results['findings'].append({
                                        'type': 'email',
                                        'value': email,
                                        'page': description,
                                        'requires_login': True
                                    })

                            # Look for phone patterns
                            phones = re.findall(r'[\+]?[0-9]{2,3}[\s\-]?[0-9]{2,3}[\s\-]?[0-9]{3,4}[\s\-]?[0-9]{0,4}', content)
                            if phones:
                                print(f"  ✓✓ PHONES FOUND: {list(set(phones))[:10]}")

                            # Look for bidder/participant tables
                            bidder_tables = await page.query_selector_all('table')
                            for i, table in enumerate(bidder_tables):
                                table_html = await table.inner_html()
                                if any(kw in table_html.lower() for kw in ['понудувач', 'bidder', 'учесник', 'participant', 'оператор']):
                                    print(f"  ✓ Found bidder-related table #{i}")
                                    # Extract table content
                                    rows = await table.query_selector_all('tr')
                                    for row in rows[:5]:
                                        row_text = await row.inner_text()
                                        print(f"    Row: {row_text[:100]}...")

                            await page.screenshot(path=f"/tmp/research_{description.replace(' ', '_').replace('(', '').replace(')', '')}_auth.png")
                else:
                    print("  ✗ Login may have failed")

            except Exception as e:
                print(f"  Login error: {e}")

        # =====================================================
        # 3. CHECK SPECIFIC TENDER DETAIL STRUCTURE
        # =====================================================
        print("\n" + "="*70)
        print("PHASE 3: ANALYZING TENDER DETAIL PAGE STRUCTURE")
        print("="*70)

        # Go to a specific awarded tender
        await page.goto('https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0', wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        tender_links = await page.query_selector_all("a[href*='dossie-acpp']")
        if tender_links:
            href = await tender_links[0].get_attribute('href')
            print(f"\nAnalyzing tender detail: {href}")

            if href.startswith('#'):
                detail_url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx' + href
            else:
                detail_url = href

            await page.goto(detail_url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(5000)

            # Extract all label-value pairs
            print("\nAll label-for attributes found:")
            labels = await page.query_selector_all('label[label-for]')

            contact_related = []
            for label in labels:
                label_for = await label.get_attribute('label-for')
                label_text = await label.inner_text()

                # Get the value
                next_label = await label.evaluate_handle('el => el.nextElementSibling')
                value = ''
                try:
                    value = await next_label.inner_text()
                except:
                    pass

                # Check if contact-related
                contact_keywords = ['email', 'phone', 'contact', 'телефон', 'пошта', 'контакт', 'bidder', 'понудувач', 'winner', 'добитник', 'operator', 'оператор']
                if any(kw in (label_for or '').lower() or kw in label_text.lower() for kw in contact_keywords):
                    contact_related.append({
                        'label_for': label_for,
                        'label_text': label_text,
                        'value': value[:100] if value else ''
                    })
                    print(f"  {label_for}: {label_text} => {value[:50] if value else 'N/A'}")

            results['contact_fields_found'].extend(contact_related)

            # Save full page HTML for analysis
            content = await page.content()
            with open('/tmp/tender_detail_full.html', 'w') as f:
                f.write(content)
            print("\nFull HTML saved to /tmp/tender_detail_full.html")

            await page.screenshot(path="/tmp/research_tender_detail.png", full_page=True)

        # =====================================================
        # 4. GENERATE RECOMMENDATIONS
        # =====================================================
        print("\n" + "="*70)
        print("PHASE 4: GENERATING RECOMMENDATIONS")
        print("="*70)

        if results['findings']:
            print("\nKey findings:")
            for finding in results['findings']:
                print(f"  - {finding}")

        results['recommendations'] = [
            "1. Contact emails may be available in tender documents (PDFs)",
            "2. Winner company names are available - can be matched with company registry",
            "3. Procuring entity contact (email, phone) may be in tender detail pages",
            "4. Bidder lists appear after tender award in award decision documents",
            "5. Consider scraping award decision PDFs and extracting contact info via OCR",
        ]

        for rec in results['recommendations']:
            print(f"  {rec}")

        await browser.close()

    # Save results
    with open('/tmp/contact_research_results.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "="*70)
    print("RESEARCH COMPLETE")
    print("="*70)
    print(f"Results saved to: /tmp/contact_research_results.json")
    print(f"Screenshots saved to: /tmp/research_*.png")

    return results

if __name__ == "__main__":
    asyncio.run(research_contact_data())

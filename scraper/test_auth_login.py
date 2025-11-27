#!/usr/bin/env python3
"""
Test authenticated login to e-nabavki.gov.mk
Verifies credentials work and explores what data is available after login
"""
import asyncio
import os
from playwright.async_api import async_playwright

# Credentials
USERNAME = "teknomed"
PASSWORD = "7Jb*Gr=2"

async def test_login():
    """Test login to e-nabavki.gov.mk"""
    print("=" * 60)
    print("Testing e-nabavki.gov.mk Authentication")
    print("=" * 60)

    async with async_playwright() as p:
        # Launch browser (headless for server)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        try:
            # Navigate to login page
            print("\n1. Navigating to e-nabavki.gov.mk...")
            await page.goto('https://e-nabavki.gov.mk', wait_until='networkidle', timeout=30000)
            print(f"   Current URL: {page.url}")

            # Wait for Angular to load
            await page.wait_for_timeout(3000)

            # Look for login button/link
            print("\n2. Looking for login elements...")

            # Try to find and click login link
            login_selectors = [
                'a:has-text("Најава")',
                'a:has-text("Логирај")',
                'button:has-text("Најава")',
                '[href*="login"]',
                '.login-btn',
                '#loginBtn'
            ]

            login_clicked = False
            for selector in login_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.click()
                        login_clicked = True
                        print(f"   Clicked login element: {selector}")
                        await page.wait_for_timeout(2000)
                        break
                except:
                    continue

            if not login_clicked:
                print("   No login button found, checking if already on login form...")

            # Wait for login form
            await page.wait_for_timeout(2000)
            print(f"   Current URL after login click: {page.url}")

            # Try to find username field
            print("\n3. Looking for username field...")
            username_selectors = [
                'input[placeholder*="Корисничко"]',
                'input[ng-model*="userName"]',
                'input[name="username"]',
                'input[type="text"]',
                '#username',
                'input[formcontrolname="username"]'
            ]

            username_field = None
            for selector in username_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem and await elem.is_visible():
                        username_field = elem
                        print(f"   Found username field: {selector}")
                        break
                except:
                    continue

            if not username_field:
                # Take screenshot to debug
                await page.screenshot(path='/tmp/enabavki_login_debug.png')
                print("   Username field not found. Screenshot saved to /tmp/enabavki_login_debug.png")

                # Print page content for debugging
                html = await page.content()
                print(f"\n   Page HTML preview (first 2000 chars):")
                print(html[:2000])
                return

            # Find password field
            print("\n4. Looking for password field...")
            password_selectors = [
                'input[type="password"]',
                'input[placeholder*="Лозинка"]',
                'input[ng-model*="password"]',
                '#password'
            ]

            password_field = None
            for selector in password_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem and await elem.is_visible():
                        password_field = elem
                        print(f"   Found password field: {selector}")
                        break
                except:
                    continue

            if not password_field:
                print("   Password field not found")
                return

            # Enter credentials
            print("\n5. Entering credentials...")
            await username_field.fill(USERNAME)
            await password_field.fill(PASSWORD)
            print("   Credentials entered")

            # Find and click submit button
            print("\n6. Looking for submit button...")
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Најава")',
                'button:has-text("Логирај")',
                'input[type="submit"]',
                '.btn-primary'
            ]

            for selector in submit_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem and await elem.is_visible():
                        await elem.click()
                        print(f"   Clicked submit: {selector}")
                        break
                except:
                    continue

            # Wait for navigation
            await page.wait_for_timeout(5000)
            print(f"\n7. After login URL: {page.url}")

            # Check if logged in
            print("\n8. Checking login status...")

            # Look for user profile or logout button (indicators of successful login)
            logged_in_indicators = [
                'a:has-text("Одјава")',
                'a:has-text("Logout")',
                '.user-profile',
                '.user-name',
                '[ng-if*="isLoggedIn"]'
            ]

            logged_in = False
            for selector in logged_in_indicators:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        logged_in = True
                        print(f"   LOGIN SUCCESSFUL! Found: {selector}")
                        break
                except:
                    continue

            if not logged_in:
                # Check for error messages
                error_selectors = [
                    '.error-message',
                    '.alert-danger',
                    '[class*="error"]'
                ]
                for selector in error_selectors:
                    try:
                        elem = await page.query_selector(selector)
                        if elem:
                            text = await elem.inner_text()
                            print(f"   Login error: {text}")
                    except:
                        continue

                await page.screenshot(path='/tmp/enabavki_after_login.png')
                print("   Login status unclear. Screenshot saved to /tmp/enabavki_after_login.png")

            # If logged in, try to access a tender detail page
            if logged_in:
                print("\n9. Testing access to tender detail page...")
                # Try to access a tender detail
                test_tender_url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/21492/2025'
                await page.goto(test_tender_url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(3000)

                print(f"   Tender page URL: {page.url}")

                # Look for bidders section
                print("\n10. Looking for bidders/lots data...")

                bidder_indicators = [
                    'Понудувач',
                    'Учесник',
                    'Економски оператор',
                    'Понуди',
                    'Лот'
                ]

                html = await page.content()
                for indicator in bidder_indicators:
                    if indicator in html:
                        print(f"   Found '{indicator}' in page content!")

                # Take screenshot of tender detail
                await page.screenshot(path='/tmp/enabavki_tender_detail.png', full_page=True)
                print("\n   Full tender page screenshot saved to /tmp/enabavki_tender_detail.png")

                # Save HTML for analysis
                with open('/tmp/enabavki_tender_detail.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                print("   Tender page HTML saved to /tmp/enabavki_tender_detail.html")

            # Get cookies for future use
            cookies = await context.cookies()
            print(f"\n11. Captured {len(cookies)} cookies for session persistence")

        except Exception as e:
            print(f"\nError: {e}")
            await page.screenshot(path='/tmp/enabavki_error.png')
            print("Error screenshot saved to /tmp/enabavki_error.png")

        finally:
            await browser.close()

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_login())

"""
Screenshot capture script for nabavkidata.com brochure.
Uses Playwright (Firefox) with pre-generated JWT token injected into localStorage.
"""

import time
from playwright.sync_api import sync_playwright

# Pre-generated JWT token for admin@nabavkidata.com (enterprise tier)
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwNWFhZWY5Ni01ZTMxLTRmYTgtOTIxNS1mNGI0ZmUwY2RlN2IiLCJleHAiOjE3NzI1NjYwNDYsInR5cGUiOiJhY2Nlc3MifQ.2EiWdOWBKLO_vmT61MklA66FNqbfaLhoAs5RY38lsIc"
REFRESH_TOKEN = "dummy_refresh"  # Not needed for screenshots

SITE_URL = "https://nabavkidata.com"
OUTPUT_DIR = "/Users/tamsar/Downloads/nabavkidata/brochure"

VIEWPORT = {"width": 1280, "height": 800}


def inject_auth_tokens(page):
    """Inject JWT tokens into localStorage to simulate logged-in state."""
    page.evaluate(f"""() => {{
        localStorage.setItem('auth_token', '{ACCESS_TOKEN}');
        localStorage.setItem('refresh_token', '{REFRESH_TOKEN}');
        // Set token expiry 7 days from now
        const expiry = Date.now() + 7 * 24 * 60 * 60 * 1000;
        localStorage.setItem('token_expiry', expiry.toString());
        // Also set cookie for middleware auth
        const expires = new Date(expiry).toUTCString();
        document.cookie = 'auth_token=' + '{ACCESS_TOKEN}' + '; path=/; expires=' + expires + '; SameSite=Lax';
    }}""")


def wait_for_page_ready(page, timeout=15000):
    """Wait for the page to be fully loaded and rendered."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass
    # Extra wait for React hydration and data fetching
    time.sleep(2)


def capture_tenders_page(page):
    """Capture the tenders search/list page."""
    print("[1/5] Capturing /tenders page...")
    page.goto(f"{SITE_URL}/tenders", wait_until="domcontentloaded", timeout=30000)
    wait_for_page_ready(page)
    # Wait for tender list items to appear
    try:
        page.wait_for_selector("[class*='tender'], table, [class*='card']", timeout=10000)
    except Exception:
        print("  Warning: Could not find tender list elements, capturing anyway.")
    time.sleep(1)
    page.screenshot(path=f"{OUTPUT_DIR}/ss_tenders.png")
    print("  Saved ss_tenders.png")


def capture_tender_detail(page):
    """Capture a tender detail page by clicking the first tender."""
    print("[2/5] Capturing tender detail page...")
    # Try to click the first tender link/row
    clicked = False
    selectors_to_try = [
        "a[href*='/tenders/']",
        "tr[class*='cursor'] a",
        "table tbody tr a",
        "[class*='tender'] a",
        "a[href*='tender']",
    ]
    for selector in selectors_to_try:
        try:
            links = page.query_selector_all(selector)
            for link in links:
                href = link.get_attribute("href")
                if href and "/tenders/" in href and "/tenders/?" not in href:
                    link.click()
                    clicked = True
                    break
            if clicked:
                break
        except Exception:
            continue

    if not clicked:
        # Fallback: navigate to a known tender URL pattern
        print("  Could not click a tender, trying direct navigation...")
        page.goto(f"{SITE_URL}/tenders", wait_until="domcontentloaded", timeout=30000)
        wait_for_page_ready(page)
        # Try finding any link that looks like a tender detail
        try:
            link = page.query_selector("a[href*='/tenders/']")
            if link:
                link.click()
                clicked = True
        except Exception:
            pass

    if clicked:
        wait_for_page_ready(page)
        time.sleep(2)
    else:
        print("  Warning: Could not navigate to a tender detail page.")

    page.screenshot(path=f"{OUTPUT_DIR}/ss_tender_detail.png")
    print("  Saved ss_tender_detail.png")
    return clicked


def capture_ai_chat(page, on_tender_detail=False):
    """Capture the AI chat interface on a tender detail page."""
    print("[3/5] Capturing AI chat...")
    if not on_tender_detail:
        # Navigate to tenders and click into one
        page.goto(f"{SITE_URL}/tenders", wait_until="domcontentloaded", timeout=30000)
        wait_for_page_ready(page)
        try:
            link = page.query_selector("a[href*='/tenders/']")
            if link:
                link.click()
                wait_for_page_ready(page)
        except Exception:
            pass

    # Look for AI chat button/tab and click it
    chat_found = False
    chat_selectors = [
        "button:has-text('AI')",
        "button:has-text('Chat')",
        "button:has-text('Прашај')",
        "[class*='chat']",
        "button:has-text('Анализа')",
        "[role='tab']:has-text('AI')",
        "[role='tab']:has-text('Chat')",
        "a:has-text('AI Chat')",
        "button:has-text('Ask')",
    ]
    for selector in chat_selectors:
        try:
            el = page.query_selector(selector)
            if el and el.is_visible():
                el.click()
                time.sleep(2)
                chat_found = True
                print(f"  Found chat via selector: {selector}")
                break
        except Exception:
            continue

    if not chat_found:
        print("  Warning: Could not find AI chat button/tab. Capturing current page state.")

    page.screenshot(path=f"{OUTPUT_DIR}/ss_ai_chat.png")
    print("  Saved ss_ai_chat.png")


def capture_competitors_page(page):
    """Capture the competitors tracking page."""
    print("[4/5] Capturing /competitors page...")
    page.goto(f"{SITE_URL}/competitors", wait_until="domcontentloaded", timeout=30000)
    wait_for_page_ready(page)
    time.sleep(1)
    page.screenshot(path=f"{OUTPUT_DIR}/ss_competitors.png")
    print("  Saved ss_competitors.png")


def capture_products_page(page):
    """Capture the products/price intelligence page."""
    print("[5/5] Capturing /products page...")
    page.goto(f"{SITE_URL}/products", wait_until="domcontentloaded", timeout=30000)
    wait_for_page_ready(page)
    time.sleep(1)
    page.screenshot(path=f"{OUTPUT_DIR}/ss_products.png")
    print("  Saved ss_products.png")


def main():
    print("Starting screenshot capture for nabavkidata.com brochure...")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Viewport: {VIEWPORT['width']}x{VIEWPORT['height']}")
    print()

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            viewport=VIEWPORT,
            locale="mk-MK",
            color_scheme="light",
        )
        page = context.new_page()

        # Step 1: Navigate to site root to set up localStorage domain
        print("Injecting authentication tokens...")
        page.goto(SITE_URL, wait_until="domcontentloaded", timeout=30000)
        inject_auth_tokens(page)
        # Reload to pick up the injected tokens
        page.reload(wait_until="domcontentloaded", timeout=30000)
        wait_for_page_ready(page)

        # Verify we are logged in by checking if there is a user menu or dashboard link
        try:
            page.wait_for_selector(
                "a[href*='/dashboard'], [class*='avatar'], button:has-text('Излези'), a[href*='/profile']",
                timeout=8000
            )
            print("Authentication successful - logged in as admin@nabavkidata.com")
        except Exception:
            print("Warning: Could not verify login state, but continuing with screenshots...")

        print()

        # Capture screenshots
        capture_tenders_page(page)
        on_detail = capture_tender_detail(page)
        capture_ai_chat(page, on_tender_detail=on_detail)
        capture_competitors_page(page)
        capture_products_page(page)

        print()
        print("All screenshots captured successfully!")
        print(f"Files saved in: {OUTPUT_DIR}/")

        browser.close()


if __name__ == "__main__":
    main()

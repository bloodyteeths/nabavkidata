#!/usr/bin/env python3
"""Test archive year modal selection on e-nabavki."""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def main():
    options = Options()
    # Run visible to see the modal
    # options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1200')
    driver = webdriver.Chrome(options=options)

    try:
        # Navigate to awarded contracts page
        url = "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0"
        print(f"Navigating to: {url}")
        driver.get(url)
        time.sleep(4)

        # Wait for Angular
        try:
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script(
                    "return typeof angular !== 'undefined' && "
                    "angular.element(document).injector() && "
                    "angular.element(document).injector().get('$http').pendingRequests.length === 0"
                )
            )
        except:
            time.sleep(3)

        # Look for archive/year buttons or links
        print("\nLooking for archive/year selection elements...")

        # Check for year buttons or archive links
        selectors_to_try = [
            ("xpath", "//a[contains(@ng-click, 'archive')]"),
            ("xpath", "//button[contains(@ng-click, 'archive')]"),
            ("xpath", "//a[contains(text(), 'Архива')]"),
            ("xpath", "//button[contains(text(), 'Архива')]"),
            ("xpath", "//a[contains(@href, 'archive')]"),
            ("xpath", "//select[contains(@ng-model, 'year')]"),
            ("css", ".year-selector"),
            ("css", "select.year"),
            ("xpath", "//button[contains(text(), '2019')]"),
            ("xpath", "//a[contains(text(), '2019')]"),
            ("xpath", "//*[contains(@class, 'modal')]"),
            ("xpath", "//div[contains(@class, 'dropdown')]//a"),
        ]

        for method, selector in selectors_to_try:
            try:
                if method == "xpath":
                    elems = driver.find_elements(By.XPATH, selector)
                else:
                    elems = driver.find_elements(By.CSS_SELECTOR, selector)

                if elems:
                    print(f"\n  Found with '{selector}':")
                    for e in elems[:5]:
                        text = e.text.strip()[:60] if e.text else ""
                        tag = e.tag_name
                        onclick = e.get_attribute('ng-click') or e.get_attribute('onclick') or ''
                        print(f"    <{tag}> text='{text}' ng-click='{onclick[:50]}'")
            except Exception as ex:
                pass

        # Check page source for archive-related elements
        print("\n\nSearching page source for 'Архив' or 'archive'...")
        source = driver.page_source
        if 'Архив' in source:
            print("  Found 'Архив' in page source")
        if 'archive' in source.lower():
            print("  Found 'archive' in page source")

        # Check for date filter inputs
        print("\n\nLooking for date inputs...")
        date_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='date'], input[ng-model*='date'], input[placeholder*='Од'], input[placeholder*='датум']")
        for inp in date_inputs:
            print(f"  {inp.get_attribute('outerHTML')[:150]}")

        print("\n\nDone. Check browser window for UI elements.")
        input("Press Enter to close browser...")

    finally:
        driver.quit()


if __name__ == '__main__':
    main()

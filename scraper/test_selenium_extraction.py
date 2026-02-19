#!/usr/bin/env python3
"""
Quick test for Selenium spider extraction of actual_value.
Tests extraction on a few awarded tenders to verify the XPaths work.
"""
import re
import time
from decimal import Decimal

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Test URLs - awarded tenders that should have actual_value
TEST_URLS = [
    "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/d9c32b2e-7fff-4e64-b67f-9fc3e1c47c7a",
    "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/c5e7d8a9-2b3c-4a1d-9e8f-1a2b3c4d5e6f",
]


def setup_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1200')
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(90)
    driver.implicitly_wait(10)
    return driver


def wait_for_angular(driver, timeout=30):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script(
                "return typeof angular !== 'undefined' && "
                "angular.element(document).injector() && "
                "angular.element(document).injector().get('$http').pendingRequests.length === 0"
            )
        )
    except:
        time.sleep(2)


def extract_tender(driver, url):
    """Extract tender data including actual_value."""
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print('='*60)

    driver.get(url)
    time.sleep(3)
    wait_for_angular(driver)

    # Wait for content
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".panel, .card, table, h1, h2"))
    )

    tender = {}

    # Field patterns - same as in spider
    field_patterns = {
        'tender_id': [
            ("xpath", "//label[@label-for='PROCESS NUMBER FOR NOTIFICATION DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[@label-for='NUMBER ACPP']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[contains(text(),'Број на огласот')]/following-sibling::*"),
        ],
        'title': [
            ("xpath", "//label[@label-for='SUBJECT:']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[@label-for='DETAIL DESCRIPTION OF THE ITEM TO BE PROCURED DOSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[contains(text(),'Предмет на договорот')]/following-sibling::*"),
        ],
        'procuring_entity': [
            ("xpath", "//label[@label-for='CONTRACTING INSTITUTION NAME DOSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[contains(text(),'Назив на договорниот орган')]/following-sibling::*"),
        ],
        'estimated_value': [
            ("xpath", "//label[@label-for='ESTIMATED VALUE NEW']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[contains(text(),'Проценета вредност')]/following-sibling::*"),
        ],
        'actual_value': [
            ("xpath", "//label[@label-for='ASSIGNED CONTRACT VALUE WITHOUT VAT']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[@label-for='ASSIGNED CONTRACT VALUE DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[contains(@label-for, 'CONTRACT VALUE')]/following-sibling::label[contains(@class, 'dosie-value')]"),
        ],
        'winner': [
            ("xpath", "//label[@label-for='NAME OF CONTACT OF PROCUREMENT DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[@label-for='WINNER NAME DOSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[@label-for='SELECTED BIDDER DOSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[contains(text(),'економски оператор')]/following-sibling::*"),
        ],
        'num_bidders': [
            ("xpath", "//label[@label-for='NUMBER OF OFFERS DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
            ("xpath", "//label[contains(text(),'Број на понуди')]/following-sibling::*"),
        ],
    }

    for field, patterns in field_patterns.items():
        for method, selector in patterns:
            try:
                if method == "xpath":
                    elem = driver.find_element(By.XPATH, selector)
                else:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)

                text = elem.text.strip()
                if text and len(text) > 0:
                    tender[field] = text
                    print(f"  ✓ {field}: {text[:80]}")
                    break
            except:
                continue

        if field not in tender:
            print(f"  ✗ {field}: NOT FOUND")

    # Parse actual_value
    if 'actual_value' in tender:
        try:
            value_text = tender['actual_value']
            # Handle Macedonian format: 1.234.567,89
            value_clean = value_text.replace('.', '').replace(',', '.')
            value_clean = re.sub(r'[^\d.]', '', value_clean)
            if value_clean:
                tender['actual_value_mkd'] = Decimal(value_clean)
                print(f"  → Parsed actual_value_mkd: {tender['actual_value_mkd']}")
        except Exception as e:
            print(f"  ✗ Failed to parse actual_value: {e}")

    return tender


def main():
    print("Testing Selenium Extraction for actual_value")
    print("="*60)

    driver = setup_driver()

    try:
        # First get a list of awarded tenders
        listing_url = "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0"
        print(f"\nNavigating to listing: {listing_url}")
        driver.get(listing_url)
        time.sleep(4)
        wait_for_angular(driver)

        # Wait for table
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )

        # Get first 3 tender links
        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='dossie-acpp']")
        test_urls = []
        for link in links[:3]:
            href = link.get_attribute('href')
            if href and 'dossie-acpp' in href:
                test_urls.append(href)

        print(f"Found {len(test_urls)} tenders to test")

        success_count = 0
        for url in test_urls:
            result = extract_tender(driver, url)
            if result.get('actual_value_mkd'):
                success_count += 1

        print(f"\n{'='*60}")
        print(f"RESULTS: {success_count}/{len(test_urls)} tenders have actual_value")
        print("="*60)

    finally:
        driver.quit()


if __name__ == '__main__':
    main()

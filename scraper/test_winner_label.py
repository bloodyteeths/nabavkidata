#!/usr/bin/env python3
"""Find winner/supplier label on page."""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def main():
    options = Options()
    options.add_argument('--headless=new')
    driver = webdriver.Chrome(options=options)

    try:
        url = "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/bb29ce72-fc9b-44d6-83f4-39689b770947"
        driver.get(url)
        time.sleep(5)

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

        # Find ALL labels with label-for containing winner/supplier/contractor keywords
        all_labels = driver.find_elements(By.XPATH, "//label[@label-for]")
        print(f"All labels with label-for (checking for winner/supplier patterns):\n")
        for label in all_labels:
            label_for = label.get_attribute('label-for') or ''
            text = label.text.strip()[:60] if label.text else ""
            # Check if it mentions winner, supplier, contractor, etc.
            keywords = ['WINNER', 'SUPPLIER', 'CONTRACTOR', 'SELECTED', 'AWARDED', 'ECONOMIC', 'OPERATOR', 'ПОНУДУВАЧ']
            if any(k in label_for.upper() for k in keywords) or any(k.lower() in text.lower() for k in ['понудувач', 'добитник', 'оператор']):
                print(f"  label-for='{label_for}' | text='{text}'")

        # Also check for tables with bidder info
        print("\n\nLooking for tables with winner/bidder info:")
        tables = driver.find_elements(By.TAG_NAME, "table")
        for i, table in enumerate(tables):
            html = table.get_attribute('outerHTML')[:500]
            if any(k in html.lower() for k in ['понудувач', 'учесник', 'оператор', 'bidder']):
                print(f"Table {i}: {html[:200]}...")

    finally:
        driver.quit()

if __name__ == '__main__':
    main()

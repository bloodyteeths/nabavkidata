#!/usr/bin/env python3
"""Inspect page structure for label-for attributes."""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def main():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    driver = webdriver.Chrome(options=options)

    try:
        url = "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/bb29ce72-fc9b-44d6-83f4-39689b770947"
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

        # Find all labels with label-for
        labels = driver.find_elements(By.XPATH, "//label[@label-for]")
        print(f"Found {len(labels)} labels with label-for:")
        for label in labels[:30]:
            try:
                label_for = label.get_attribute('label-for')
                text = label.text.strip()[:50] if label.text else ""
                print(f"  label-for='{label_for}' | text='{text}'")
            except:
                pass

        # Try to find tender_id patterns
        print("\n\nLooking for tender number patterns:")
        patterns = [
            "//label[contains(text(),'Број')]",
            "//*[contains(text(),'Број на оглас')]",
            "//span[@ng-bind]",
            "//label[@label-for='NUMBER ACPP']",
            "//label[@label-for='TENDER ID']",
        ]
        for p in patterns:
            try:
                elems = driver.find_elements(By.XPATH, p)
                if elems:
                    for e in elems[:3]:
                        print(f"  {p}: '{e.text[:80]}'")
            except:
                pass

        # Check for h1, h2, h3 titles
        print("\n\nLooking for titles (h1,h2,h3):")
        for tag in ['h1', 'h2', 'h3', '.tender-title', '[ng-bind*="title"]']:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, tag)
                if elems:
                    for e in elems[:3]:
                        t = e.text.strip()[:100]
                        if t:
                            print(f"  {tag}: '{t}'")
            except:
                pass

    finally:
        driver.quit()

if __name__ == '__main__':
    main()

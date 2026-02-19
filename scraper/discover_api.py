#!/usr/bin/env python3
"""
Discover API endpoints on e-nabavki.gov.mk
If we find JSON APIs, we can skip browser rendering entirely = 100x faster
"""
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

def main():
    options = Options()
    options.add_argument('--headless=new')

    # Enable performance logging to capture network requests
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    driver = webdriver.Chrome(options=options)

    try:
        print("Navigating to e-nabavki and capturing network requests...")
        driver.get('https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0')
        time.sleep(10)  # Wait for all requests

        # Get performance logs
        logs = driver.get_log('performance')

        api_endpoints = set()
        json_endpoints = set()

        for entry in logs:
            try:
                message = json.loads(entry['message'])['message']
                if message['method'] == 'Network.requestWillBeSent':
                    url = message['params']['request']['url']

                    # Look for API/JSON endpoints
                    if any(x in url.lower() for x in ['api', 'json', '.asmx', 'handler', 'service', 'data']):
                        api_endpoints.add(url[:200])

                    # Look for XHR requests
                    if message['params'].get('type') == 'XHR':
                        json_endpoints.add(url[:200])

            except:
                continue

        print("\n=== POTENTIAL API ENDPOINTS ===")
        for url in sorted(api_endpoints):
            print(f"  {url}")

        print("\n=== XHR REQUESTS ===")
        for url in sorted(json_endpoints):
            print(f"  {url}")

        # Also check for Angular $http calls in the page source
        print("\n=== CHECKING PAGE SOURCE FOR API PATTERNS ===")
        source = driver.page_source

        import re
        # Look for API URLs in the source
        api_patterns = [
            r'https?://[^\s"\'<>]+/api/[^\s"\'<>]+',
            r'https?://[^\s"\'<>]+\.asmx[^\s"\'<>]*',
            r'https?://[^\s"\'<>]+/Handler[^\s"\'<>]+',
            r'\$http\.(get|post)\([\'"]([^\'"]+)[\'"]',
        ]

        for pattern in api_patterns:
            matches = re.findall(pattern, source)
            if matches:
                print(f"  Pattern '{pattern[:30]}...': {matches[:5]}")

        # Try to access Angular scope to find data sources
        print("\n=== CHECKING ANGULAR SCOPE ===")
        try:
            data = driver.execute_script("""
                var scope = angular.element(document.querySelector('[ng-controller]')).scope();
                if (scope) {
                    return {
                        hasData: !!scope.data,
                        hasContracts: !!scope.contracts,
                        keys: Object.keys(scope).filter(k => !k.startsWith('$')).slice(0, 20)
                    };
                }
                return null;
            """)
            if data:
                print(f"  Angular scope keys: {data.get('keys')}")
        except Exception as e:
            print(f"  Could not access Angular scope: {e}")

        # Check for DataTables API
        print("\n=== CHECKING DATATABLES CONFIG ===")
        try:
            dt_config = driver.execute_script("""
                var table = $('table').DataTable();
                if (table && table.ajax) {
                    return {
                        ajaxUrl: table.ajax.url(),
                        pageLength: table.page.len()
                    };
                }
                return null;
            """)
            if dt_config:
                print(f"  DataTables AJAX URL: {dt_config.get('ajaxUrl')}")
                print(f"  Page length: {dt_config.get('pageLength')}")
        except Exception as e:
            print(f"  Could not access DataTables config: {e}")

    finally:
        driver.quit()

if __name__ == '__main__':
    main()

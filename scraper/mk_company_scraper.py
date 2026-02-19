#!/usr/bin/env python3
"""
North Macedonia Company Registry Scraper
=========================================
Scrapes public company data from the Central Registry (crm.com.mk)
using the free "Основен профил" (Basic Profile) open data page.

This data is PUBLIC and FREE per North Macedonia's Open Government Partnership commitment.
URL: https://www.crm.com.mk/mk/otvoreni-podatotsi/osnoven-profil-na-registriran-subjekt

The scraper iterates through EMBS (ЕМБС) numbers — the unique company registration
numbers in North Macedonia. These are typically 7-digit sequential numbers.

Usage:
    pip install requests beautifulsoup4 lxml
    python mk_company_scraper.py

Output: companies_mk.csv with all scraped company data
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
import json
import re
import os
import sys
import random
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

# ============================================================
# CONFIGURATION — adjust these settings as needed
# ============================================================

# EMBS number range to scan
# North Macedonia companies typically have 7-digit EMBS numbers
# Active companies are roughly in the range 4000000-7600000
# Adjust these based on your needs
EMBS_START = 4000000
EMBS_END = 7600000

# How many EMBS numbers to try (set to None to scan the full range)
# Useful for testing — set to e.g. 1000 for a quick test run
MAX_TO_SCAN = None  # Set to e.g. 1000 for testing

# Delay between requests (seconds) — be respectful to the server
MIN_DELAY = 0.5
MAX_DELAY = 1.5

# Number of parallel threads (keep low to avoid being blocked)
NUM_THREADS = 3

# Output file
OUTPUT_FILE = "companies_mk.csv"
CHECKPOINT_FILE = "scraper_checkpoint.json"

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5

# Logging
LOG_FILE = "scraper.log"

# ============================================================
# SETUP
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Base URL for the basic profile search
BASE_URL = "https://www.crm.com.mk/mk/otvoreni-podatotsi/osnoven-profil-na-registriran-subjekt"

# Headers to mimic a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "mk,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# CSV columns
CSV_COLUMNS = [
    "embs",           # ЕМБС - Company Registration Number
    "edb",            # ЕДБ - Tax ID Number
    "full_name",      # Целосен назив - Full Name
    "short_name",     # Скратен назив - Short Name
    "founding_date",  # Датум на основање - Date of Establishment
    "legal_form",     # Правна форма - Legal Form (DOO, DOOEL, AD, etc.)
    "legal_status",   # Правен статус - Status (active/inactive/etc.)
    "address",        # Адреса - Address
    "additional_info", # Дополнителни информации - Additional Info (bankruptcy/liquidation)
    "activity_code",  # Дејност шифра - Activity Code
    "activity_desc",  # Дејност опис - Activity Description
    "size",           # Големина - Size
    "scraped_at",     # Timestamp of when this record was scraped
]

# ============================================================
# APPROACH 1: Direct page scraping (HTML parsing)
# ============================================================

class CRMScraper:
    """Scraper for crm.com.mk basic profile data."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.found_count = 0
        self.scanned_count = 0
        self.error_count = 0

    def fetch_company_by_embs(self, embs: int) -> dict | None:
        """
        Fetch company data by EMBS number.
        Returns dict with company data or None if not found.
        """
        params = {"embs": str(embs)}
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(
                    BASE_URL, 
                    params=params, 
                    timeout=15
                )
                
                if response.status_code == 200:
                    return self._parse_response(response.text, embs)
                elif response.status_code == 429:
                    # Rate limited — back off
                    wait = RETRY_DELAY * (attempt + 1) * 2
                    logger.warning(f"Rate limited on EMBS {embs}. Waiting {wait}s...")
                    time.sleep(wait)
                elif response.status_code >= 500:
                    logger.warning(f"Server error {response.status_code} for EMBS {embs}")
                    time.sleep(RETRY_DELAY)
                else:
                    return None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout for EMBS {embs} (attempt {attempt+1})")
                time.sleep(RETRY_DELAY)
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for EMBS {embs}: {e}")
                time.sleep(RETRY_DELAY)
        
        self.error_count += 1
        return None

    def _parse_response(self, html: str, embs: int) -> dict | None:
        """
        Parse the HTML response and extract company data.
        
        NOTE: The crm.com.mk page may load data dynamically via JavaScript/AJAX.
        If this is the case, this parser won't work and you'll need Approach 2 
        (Selenium) or Approach 3 (intercept the API calls).
        
        This parser tries multiple strategies to find the data.
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Strategy 1: Look for structured data in tables
        company = self._parse_table_data(soup, embs)
        if company:
            return company
        
        # Strategy 2: Look for data in definition lists (dl/dt/dd)
        company = self._parse_dl_data(soup, embs)
        if company:
            return company
        
        # Strategy 3: Look for data in divs with specific classes
        company = self._parse_div_data(soup, embs)
        if company:
            return company
        
        # Strategy 4: Look for JSON-LD or embedded JSON data
        company = self._parse_json_data(soup, embs)
        if company:
            return company
            
        return None

    def _parse_table_data(self, soup, embs) -> dict | None:
        """Try parsing data from HTML tables."""
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            data = {}
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    data[key] = value
            
            if data and any(k for k in data.keys() if 'ембс' in k or 'embs' in k.lower() or 'назив' in k):
                return self._normalize_data(data, embs)
        return None

    def _parse_dl_data(self, soup, embs) -> dict | None:
        """Try parsing from definition lists."""
        dls = soup.find_all('dl')
        for dl in dls:
            data = {}
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                key = dt.get_text(strip=True).lower()
                value = dd.get_text(strip=True)
                data[key] = value
            if data:
                return self._normalize_data(data, embs)
        return None

    def _parse_div_data(self, soup, embs) -> dict | None:
        """Try parsing from div elements with labels."""
        # Look for common patterns like label/value pairs in divs
        result = {}
        
        # Try finding elements with specific text content
        label_patterns = {
            'embs': ['ембс', 'embs', 'матичен број'],
            'edb': ['едб', 'edb', 'даночен'],
            'full_name': ['целосен назив', 'полн назив', 'full name'],
            'short_name': ['скратен назив', 'short name'],
            'founding_date': ['датум на основање', 'date of establishment'],
            'legal_form': ['правна форма', 'legal form'],
            'legal_status': ['правен статус', 'legal status', 'статус'],
            'address': ['адреса', 'address', 'седиште'],
            'activity_code': ['дејност', 'activity'],
            'size': ['големина', 'size'],
        }
        
        all_text_elements = soup.find_all(['span', 'div', 'p', 'label', 'strong', 'b'])
        
        for elem in all_text_elements:
            text = elem.get_text(strip=True).lower()
            for field, patterns in label_patterns.items():
                if any(p in text for p in patterns):
                    # Try to get the next sibling or parent's next element
                    value_elem = elem.find_next_sibling() or elem.find_next()
                    if value_elem:
                        value = value_elem.get_text(strip=True)
                        if value and value.lower() != text:
                            result[field] = value
        
        if result and ('full_name' in result or 'embs' in result):
            result.setdefault('embs', str(embs))
            return self._fill_missing(result)
        
        return None

    def _parse_json_data(self, soup, embs) -> dict | None:
        """Try to find embedded JSON data in script tags."""
        scripts = soup.find_all('script')
        for script in scripts:
            text = script.string or ''
            # Look for JSON objects that might contain company data
            json_patterns = [
                r'var\s+\w+\s*=\s*(\{.*?\});',
                r'data\s*:\s*(\{.*?\})',
                r'"embs"\s*:\s*"?\d+"?',
            ]
            for pattern in json_patterns:
                matches = re.findall(pattern, text, re.DOTALL)
                for match in matches:
                    try:
                        data = json.loads(match)
                        if isinstance(data, dict):
                            return self._normalize_data(data, embs)
                    except (json.JSONDecodeError, TypeError):
                        continue
        return None

    def _normalize_data(self, raw_data: dict, embs: int) -> dict:
        """Normalize raw scraped data into our standard format."""
        # Mapping of possible Macedonian/English field names to our column names
        field_map = {
            'embs': ['ембс', 'embs', 'матичен број', 'sin-b', 'sinb'],
            'edb': ['едб', 'edb', 'stn', 'даночен број'],
            'full_name': ['целосен назив', 'full name', 'полн назив', 'назив', 'име'],
            'short_name': ['скратен назив', 'short name', 'abbreviated name'],
            'founding_date': ['датум на основање', 'date of establishment', 'основање'],
            'legal_form': ['правна форма', 'legal form', 'организационен облик'],
            'legal_status': ['правен статус', 'legal status', 'статус', 'status'],
            'address': ['адреса', 'address', 'седиште'],
            'additional_info': ['дополнителни информации', 'additional information', 'дополнително'],
            'activity_code': ['дејност', 'activity', 'претежна дејност', 'шифра'],
            'activity_desc': ['опис на дејност', 'activity description'],
            'size': ['големина', 'size'],
        }
        
        result = {'embs': str(embs)}
        
        for our_field, possible_keys in field_map.items():
            for raw_key, raw_value in raw_data.items():
                raw_key_lower = raw_key.lower().strip().rstrip(':')
                if any(pk in raw_key_lower for pk in possible_keys):
                    result[our_field] = str(raw_value).strip()
                    break
        
        return self._fill_missing(result)

    def _fill_missing(self, data: dict) -> dict:
        """Fill in missing fields with empty strings."""
        for col in CSV_COLUMNS:
            if col not in data:
                data[col] = ''
        data['scraped_at'] = datetime.now().isoformat()
        return data


# ============================================================
# APPROACH 2: Selenium-based scraper (for JavaScript-rendered pages)
# ============================================================

class CRMSeleniumScraper:
    """
    Use this if the page loads data via JavaScript/AJAX.
    
    Install: pip install selenium webdriver-manager
    """
    
    def __init__(self):
        self.driver = None
        self.found_count = 0
        self.scanned_count = 0
        
    def setup(self):
        """Initialize Selenium WebDriver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument(f'--user-agent={HEADERS["User-Agent"]}')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            logger.info("Selenium WebDriver initialized")
            
        except ImportError:
            logger.error("Selenium not installed. Run: pip install selenium webdriver-manager")
            raise
    
    def fetch_company_by_embs(self, embs: int) -> dict | None:
        """Fetch company using Selenium for JS-rendered pages."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        url = f"{BASE_URL}?embs={embs}"
        
        try:
            self.driver.get(url)
            
            # Wait for page to load (adjust selector based on actual page structure)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table, .profile-data, .result"))
            )
            
            # Additional wait for AJAX
            time.sleep(1)
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'lxml')
            
            # Use the same parsing logic
            scraper = CRMScraper()
            result = scraper._parse_table_data(soup, embs)
            if not result:
                result = scraper._parse_dl_data(soup, embs)
            if not result:
                result = scraper._parse_div_data(soup, embs)
            if not result:
                result = scraper._parse_json_data(soup, embs)
            
            return result
            
        except Exception as e:
            logger.error(f"Selenium error for EMBS {embs}: {e}")
            return None
    
    def close(self):
        if self.driver:
            self.driver.quit()


# ============================================================
# APPROACH 3: Network interception (find the hidden API)
# ============================================================

def discover_api():
    """
    Instructions to discover the hidden API that crm.com.mk uses:
    
    1. Open Chrome DevTools (F12)
    2. Go to the Network tab
    3. Visit: https://www.crm.com.mk/mk/otvoreni-podatotsi/osnoven-profil-na-registriran-subjekt
    4. Search for a company by name or EMBS
    5. Look at the XHR/Fetch requests in the Network tab
    6. Find the API endpoint (usually something like /api/... or /search/...)
    7. Note the request method, headers, and parameters
    8. Update the API_URL and fetch_from_api() function below
    
    Common patterns to look for:
    - POST requests with JSON body
    - GET requests with query parameters
    - GraphQL endpoints
    """
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║           HOW TO FIND THE HIDDEN API                        ║
    ╠══════════════════════════════════════════════════════════════╣
    ║                                                              ║
    ║  1. Open Chrome → Go to crm.com.mk basic profile page       ║
    ║  2. Press F12 → Network tab → check "XHR" filter            ║
    ║  3. Search for any company by name or EMBS number            ║
    ║  4. Look at the API requests that appear                     ║
    ║  5. Right-click the request → Copy as cURL                   ║
    ║  6. Paste it below to update this script                     ║
    ║                                                              ║
    ║  The API will likely return JSON — much easier to parse!     ║
    ╚══════════════════════════════════════════════════════════════╝
    """)


# Example API scraper (update after discovering the real API)
def fetch_from_api(session, embs: int, api_url: str = None) -> dict | None:
    """
    Fetch from the API directly (fastest method).
    
    UPDATE THIS after you discover the real API endpoint using
    Chrome DevTools. The API URL and parameters will vary.
    """
    if not api_url:
        # Placeholder — replace with actual API URL from Chrome DevTools
        api_url = "https://www.crm.com.mk/api/search"  # EXAMPLE ONLY
    
    try:
        # Try common API patterns
        # Pattern 1: GET with query params
        response = session.get(api_url, params={"embs": embs}, timeout=10)
        if response.status_code == 200:
            try:
                data = response.json()
                if data:
                    return data
            except json.JSONDecodeError:
                pass
        
        # Pattern 2: POST with JSON body
        response = session.post(api_url, json={"embs": str(embs)}, timeout=10)
        if response.status_code == 200:
            try:
                data = response.json()
                if data:
                    return data
            except json.JSONDecodeError:
                pass
                
    except Exception as e:
        logger.debug(f"API fetch failed for EMBS {embs}: {e}")
    
    return None


# ============================================================
# MAIN SCRAPER RUNNER
# ============================================================

class ScraperRunner:
    """Orchestrates the scraping process with checkpointing and CSV output."""
    
    def __init__(self, scraper):
        self.scraper = scraper
        self.results = []
        self.last_embs = EMBS_START
        self._load_checkpoint()
    
    def _load_checkpoint(self):
        """Resume from last checkpoint if available."""
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, 'r') as f:
                    data = json.load(f)
                    self.last_embs = data.get('last_embs', EMBS_START)
                    logger.info(f"Resuming from EMBS {self.last_embs}")
            except (json.JSONDecodeError, IOError):
                pass
    
    def _save_checkpoint(self, embs: int):
        """Save progress checkpoint."""
        with open(CHECKPOINT_FILE, 'w') as f:
            json.dump({
                'last_embs': embs,
                'timestamp': datetime.now().isoformat(),
                'found': self.scraper.found_count,
                'scanned': self.scraper.scanned_count,
            }, f)
    
    def _init_csv(self):
        """Initialize CSV file with headers if it doesn't exist."""
        if not os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                writer.writeheader()
    
    def _append_to_csv(self, company: dict):
        """Append a single company record to the CSV."""
        with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writerow({k: company.get(k, '') for k in CSV_COLUMNS})
    
    def run(self):
        """Main scraping loop."""
        self._init_csv()
        
        start = self.last_embs
        end = EMBS_END
        total = end - start
        
        if MAX_TO_SCAN:
            end = min(start + MAX_TO_SCAN, EMBS_END)
            total = end - start
        
        logger.info(f"Starting scrape: EMBS {start} → {end} ({total:,} to scan)")
        logger.info(f"Output: {OUTPUT_FILE}")
        
        batch_size = 100  # Save checkpoint every N items
        
        for i, embs in enumerate(range(start, end)):
            try:
                company = self.scraper.fetch_company_by_embs(embs)
                self.scraper.scanned_count += 1
                
                if company and company.get('full_name'):
                    self.scraper.found_count += 1
                    self._append_to_csv(company)
                    logger.info(
                        f"[{self.scraper.found_count}] EMBS {embs}: "
                        f"{company.get('full_name', 'N/A')}"
                    )
                
                # Progress update
                if (i + 1) % batch_size == 0:
                    pct = ((i + 1) / total) * 100
                    logger.info(
                        f"Progress: {i+1:,}/{total:,} ({pct:.1f}%) | "
                        f"Found: {self.scraper.found_count:,} | "
                        f"Errors: {self.scraper.error_count}"
                    )
                    self._save_checkpoint(embs)
                
                # Respectful delay
                time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
                
            except KeyboardInterrupt:
                logger.info("Interrupted! Saving checkpoint...")
                self._save_checkpoint(embs)
                break
            except Exception as e:
                logger.error(f"Unexpected error at EMBS {embs}: {e}")
                continue
        
        self._save_checkpoint(end)
        logger.info(
            f"\nDone! Found {self.scraper.found_count:,} companies "
            f"out of {self.scraper.scanned_count:,} scanned. "
            f"Saved to {OUTPUT_FILE}"
        )


# ============================================================
# ALTERNATIVE: FOI Request Template
# ============================================================

FOI_REQUEST_TEMPLATE = """
Предмет: Барање за слободен пристап до информации од јавен карактер

До: Централен регистар на Република Северна Македонија
Адреса: ул. Кузман Јосифовски Питу бр. 1, 1000 Скопје
Email: e-registracija@crm.org.mk

Врз основа на член 4 од Законот за слободен пристап до информации од јавен карактер 
и обврските преземени со Акцискиот план за Отворено владино партнерство (OGP), 
ја поднесувам следната:

БАРАЊЕ

Ве молам да ми доставите целосна листа на сите регистрирани субјекти во 
Трговскиот регистар во машински читлив формат (CSV, Excel или JSON), 
вклучувајќи ги следните основни податоци:

- ЕМБС (матичен број)
- ЕДБ (даночен број)
- Целосен назив
- Скратен назив
- Датум на основање
- Правна форма
- Правен статус (активен/неактивен)
- Адреса
- Претежна дејност (шифра и опис)
- Големина

Напомена: Овие податоци се веќе јавно достапни преку услугата 
"Основен профил на регистриран субјект" на вашата веб страница, 
и се дел од обврските преземени со OGP Акцискиот план 2018-2020.

Со почит,
[ВАШЕТО ИМЕ]
[АДРЕСА]
[ТЕЛЕФОН]
[EMAIL]

Датум: {date}
""".format(date=datetime.now().strftime("%d.%m.%Y"))


# ============================================================
# ENTRY POINT
# ============================================================

def print_menu():
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║       North Macedonia Company Registry Scraper                  ║
    ║       Data source: crm.com.mk (Public Open Data)               ║
    ╠══════════════════════════════════════════════════════════════════╣
    ║                                                                  ║
    ║  Choose your approach:                                           ║
    ║                                                                  ║
    ║  1. HTML Scraper (requests + BeautifulSoup)                      ║
    ║     → Simple, works if page is server-rendered                   ║
    ║                                                                  ║
    ║  2. Selenium Scraper (browser automation)                        ║
    ║     → Works with JavaScript-rendered pages                       ║
    ║     → Requires: pip install selenium webdriver-manager           ║
    ║                                                                  ║
    ║  3. API Discovery Guide                                          ║
    ║     → Instructions to find the hidden API (fastest method)       ║
    ║                                                                  ║
    ║  4. Generate FOI Request Letter                                  ║
    ║     → Formal request to get the full dataset officially          ║
    ║                                                                  ║
    ║  5. Test single EMBS lookup                                      ║
    ║     → Quick test to see if scraping works                        ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)


def main():
    print_menu()
    
    choice = input("Enter choice (1-5): ").strip()
    
    if choice == '1':
        scraper = CRMScraper()
        runner = ScraperRunner(scraper)
        runner.run()
        
    elif choice == '2':
        scraper = CRMSeleniumScraper()
        scraper.setup()
        try:
            runner = ScraperRunner(scraper)
            runner.run()
        finally:
            scraper.close()
    
    elif choice == '3':
        discover_api()
    
    elif choice == '4':
        print("\n" + "="*60)
        print("FOI REQUEST LETTER (copy and send to crm.com.mk)")
        print("="*60)
        print(FOI_REQUEST_TEMPLATE)
        
        # Also save to file
        with open("foi_request_mk.txt", 'w', encoding='utf-8') as f:
            f.write(FOI_REQUEST_TEMPLATE)
        print("\n✓ Letter also saved to: foi_request_mk.txt")
    
    elif choice == '5':
        embs = input("Enter EMBS number to test (e.g. 7519958): ").strip()
        if not embs.isdigit():
            print("Invalid EMBS number")
            return
            
        print(f"\nTesting EMBS {embs}...")
        scraper = CRMScraper()
        
        # First, let's see what the raw HTML looks like
        response = scraper.session.get(BASE_URL, params={"embs": embs}, timeout=15)
        print(f"Status: {response.status_code}")
        print(f"Content length: {len(response.text)} bytes")
        
        # Save raw HTML for inspection
        with open(f"test_embs_{embs}.html", 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"Raw HTML saved to: test_embs_{embs}.html")
        
        # Try parsing
        result = scraper.fetch_company_by_embs(int(embs))
        if result:
            print("\n✓ Company found:")
            for k, v in result.items():
                if v:
                    print(f"  {k}: {v}")
        else:
            print("\n✗ No data parsed. The page likely uses JavaScript.")
            print("  → Try option 2 (Selenium) or option 3 (API discovery)")
            print(f"  → Inspect the HTML file: test_embs_{embs}.html")
    
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()

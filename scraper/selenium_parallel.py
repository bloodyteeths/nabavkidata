#!/usr/bin/env python3
"""
Parallel Selenium Scraper for E-Nabavki

Runs multiple browser instances in parallel to speed up scraping.
Each worker handles a separate page range.

Usage:
    python selenium_parallel.py --workers 4 --max-pages 500
    python selenium_parallel.py --workers 6 --category awarded
"""

import argparse
import asyncio
import logging
import os
import re
import sys
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from threading import Lock

import asyncpg
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv
load_dotenv()


# Configure logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'logs/parallel_scrape_{datetime.now().strftime("%Y%m%d_%H%M")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)

CATEGORY_URLS = {
    'active': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices',
    'awarded': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0',
    'cancelled': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/cancelations',
}

# Thread-safe stats
stats_lock = Lock()
global_stats = {
    'tenders_found': 0,
    'tenders_saved': 0,
    'tenders_updated': 0,
    'errors': 0,
}


def create_driver(headless: bool = True) -> webdriver.Chrome:
    """Create a Chrome WebDriver instance optimized for Angular SPA scraping."""
    options = Options()
    if headless:
        options.add_argument('--headless=new')

    # Core stability options
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # DISABLE GPU for stability (fixes rendering issues in headless)
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')

    # Memory/performance - keep these
    options.add_argument('--disable-extensions')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')

    # Reduce logging overhead
    options.add_argument('--log-level=3')
    options.add_argument('--silent')

    # DO NOT disable images - Angular SPA needs full rendering
    # DO NOT use 'eager' page load - Angular needs full DOM ready
    # Use default 'normal' page load strategy for full Angular rendering
    options.page_load_strategy = 'normal'

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(120)  # Match Playwright's 120s timeout
    driver.implicitly_wait(10)  # Longer implicit wait for Angular elements
    return driver


def wait_for_angular(driver, timeout: int = 20):
    """Wait for Angular to finish loading."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script(
                "return typeof angular !== 'undefined' && "
                "angular.element(document).injector() && "
                "angular.element(document).injector().get('$http').pendingRequests.length === 0"
            )
        )
    except TimeoutException:
        time.sleep(1)


def get_tender_links(driver) -> List[str]:
    """Extract tender links from current page."""
    links = []
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='dossie-acpp']")
        for elem in elements:
            try:
                href = elem.get_attribute('href')
                if href and 'dossie-acpp' in href:
                    links.append(href)
            except:
                continue
    except Exception as e:
        logger.error(f"Error getting links: {e}")
    return list(set(links))


def click_next_page(driver, retry_count: int = 3) -> bool:
    """Click next page by clicking the page number button directly (most reliable for Angular SPAs)."""
    from selenium.webdriver.common.action_chains import ActionChains

    for attempt in range(retry_count):
        try:
            # CAPTURE BEFORE STATE
            old_first_link = ""
            try:
                first_links = driver.find_elements(By.CSS_SELECTOR, "table tbody tr td a[href*='dossie']")
                if first_links:
                    old_first_link = first_links[0].get_attribute('href')
            except:
                pass

            # Get current page number from active button
            current_page = 1
            try:
                current_btn = driver.find_element(By.CSS_SELECTOR, ".paginate_button.current")
                current_page = int(current_btn.text.strip())
            except:
                pass

            next_page = current_page + 1
            logger.debug(f"Attempting to navigate from page {current_page} to {next_page}")

            # METHOD 1: Click directly on the next page number button
            # This is more reliable than clicking "Next" because it explicitly targets a page
            page_clicked = False
            try:
                # Find page number buttons
                page_buttons = driver.find_elements(By.CSS_SELECTOR, ".paginate_button")
                for btn in page_buttons:
                    try:
                        btn_text = btn.text.strip()
                        if btn_text == str(next_page):
                            # Found the target page button
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                            time.sleep(0.3)

                            # Click using JavaScript (most reliable for Angular)
                            driver.execute_script("arguments[0].click();", btn)
                            page_clicked = True
                            logger.debug(f"Clicked page number {next_page}")
                            break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Page number click error: {e}")

            # METHOD 2: If page number not found, click the Next button
            if not page_clicked:
                next_selectors = [
                    "a.paginate_button.next:not(.disabled)",
                    "#contracts-grid_next:not(.disabled)",
                    "#notices-grid_next:not(.disabled)",
                ]

                for selector in next_selectors:
                    try:
                        btn = driver.find_element(By.CSS_SELECTOR, selector)
                        if btn and 'disabled' not in (btn.get_attribute('class') or ''):
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                            time.sleep(0.3)
                            driver.execute_script("arguments[0].click();", btn)
                            page_clicked = True
                            logger.debug(f"Clicked Next button: {selector}")
                            break
                    except:
                        continue

            if not page_clicked:
                logger.debug("Could not find page button to click")
                return False

            # Wait for Angular/AJAX and verify content changed
            time.sleep(3)  # Longer wait for Angular SPA
            wait_for_angular(driver, timeout=25)

            # VERIFY page changed by checking first link is different
            verified = False
            for verify_attempt in range(8):  # More retries
                try:
                    first_links = driver.find_elements(By.CSS_SELECTOR, "table tbody tr td a[href*='dossie']")
                    if first_links:
                        new_first_link = first_links[0].get_attribute('href')
                        if new_first_link and old_first_link and new_first_link != old_first_link:
                            logger.debug(f"Page verified: link changed")
                            verified = True
                            break

                    # Also check if current page button changed
                    try:
                        new_current_btn = driver.find_element(By.CSS_SELECTOR, ".paginate_button.current")
                        new_page = int(new_current_btn.text.strip())
                        if new_page != current_page:
                            logger.debug(f"Page verified: page number changed to {new_page}")
                            verified = True
                            break
                    except:
                        pass
                except:
                    pass
                time.sleep(0.5)

            if verified:
                return True

            logger.debug(f"Page click attempt {attempt+1} - content did not change")

            if attempt < retry_count - 1:
                # Try refreshing the page and waiting
                time.sleep(2)
                continue

            return False

        except Exception as e:
            logger.debug(f"Next page error (attempt {attempt+1}): {e}")
            if attempt < retry_count - 1:
                time.sleep(2)
                continue
            return False

    return False


def navigate_to_page(driver, url: str, target_page: int) -> bool:
    """Navigate to a specific page number."""
    driver.get(url)
    time.sleep(2)
    wait_for_angular(driver)

    # Wait for table
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
    except TimeoutException:
        return False

    # Navigate to target page
    for _ in range(target_page - 1):
        if not click_next_page(driver):
            return False

    return True


def extract_tender(driver, url: str) -> Optional[Dict[str, Any]]:
    """Extract ALL available tender data from detail page with comprehensive 40+ field extraction."""
    try:
        driver.get(url)
        time.sleep(3)  # Longer wait for Angular
        wait_for_angular(driver, timeout=25)

        # Wait for content with multiple selectors
        content_loaded = False
        content_selectors = [
            ".panel", ".card", "table", ".tab-content",
            "label.dosie-value", "[ng-bind]", ".dossie-container"
        ]
        for selector in content_selectors:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                content_loaded = True
                break
            except TimeoutException:
                continue

        if not content_loaded:
            logger.warning(f"Content not fully loaded for {url}")

        time.sleep(1.5)  # Extra wait for Angular to render all data

        tender = {'source_url': url, 'language': 'mk'}

        # Extract IDs from URL
        id_match = re.search(r'/dossie-acpp/([a-f0-9-]+)', url)
        if id_match:
            tender['internal_id'] = id_match.group(1)
            tender['dossier_id'] = id_match.group(1)
            tender['tender_uuid'] = id_match.group(1)

        # Get page source for comprehensive extraction
        page_source = driver.page_source
        page_text = driver.find_element(By.TAG_NAME, "body").text if driver.find_elements(By.TAG_NAME, "body") else ""

        # === TENDER NUMBER (CRITICAL) ===
        # Use the same patterns as the working Playwright spider
        tender_id_patterns = [
            # Primary: label-for based patterns (from Playwright spider)
            (By.XPATH, "//label[@label-for='PROCESS NUMBER FOR NOTIFICATION DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')][1]"),
            (By.XPATH, "//label[@label-for='ANNOUNCEMENT NUMBER DOSIE']/following-sibling::label[contains(@class, 'dosie-value')][1]"),
            (By.XPATH, "//label[@label-for='NUMBER OF NOTICE DOSIE']/following-sibling::label[contains(@class, 'dosie-value')][1]"),
            # Pattern match in dosie-value labels
            (By.XPATH, "//label[contains(@class, 'dosie-value')][contains(text(), '/202')]"),
            (By.XPATH, "//label[contains(@class, 'dosie-value')][contains(text(), '/201')]"),
            # ng-bind patterns
            (By.XPATH, "//span[contains(@ng-bind, 'numberAcpp')]"),
            (By.XPATH, "//span[contains(@ng-bind, 'processNumber')]"),
            # Text-based patterns
            (By.XPATH, "//td[contains(text(),'Број на оглас')]/following-sibling::td"),
            (By.XPATH, "//td[contains(text(),'Број на постапка')]/following-sibling::td"),
        ]
        for method, selector in tender_id_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip()
                # Validate tender_id format: should contain / and year
                if text and '/' in text and re.search(r'/20[0-2][0-9]', text):
                    tender['tender_id'] = text
                    logger.debug(f"Found tender_id via XPath: {text}")
                    break
            except:
                continue

        # Fallback 1: Search page text for tender ID pattern
        if not tender.get('tender_id'):
            # Look for pattern like 12345/2025 in page text
            id_regex = re.search(r'\b(\d{1,6}/20[0-2][0-9])\b', page_text)
            if id_regex:
                tender['tender_id'] = id_regex.group(1)
                logger.debug(f"Found tender_id via page text: {tender['tender_id']}")

        # Fallback 2: Search page source
        if not tender.get('tender_id'):
            id_regex = re.search(r'\b(\d{1,6}/20[0-2][0-9])\b', page_source)
            if id_regex:
                tender['tender_id'] = id_regex.group(1)
                logger.debug(f"Found tender_id via page source: {tender['tender_id']}")

        # Last resort: use dossier UUID
        if not tender.get('tender_id'):
            tender['tender_id'] = f"SEL-{tender.get('internal_id', 'UNK')[:8]}"

        # === TITLE (CRITICAL) ===
        # Use label-for patterns from Playwright spider
        title_patterns = [
            (By.XPATH, "//label[@label-for='SUBJECT:']/following-sibling::label[contains(@class, 'dosie-value')][1]"),
            (By.XPATH, "//label[contains(@label-for, 'SUBJECT')]/following-sibling::label[contains(@class, 'dosie-value')][1]"),
            (By.XPATH, "//label[@label-for='DETAIL DESCRIPTION OF THE ITEM TO BE PROCURED DOSIE']/following-sibling::label[contains(@class, 'dosie-value')][1]"),
            (By.XPATH, "//span[contains(@ng-bind, 'subject')]"),
            (By.XPATH, "//td[contains(text(),'Предмет')]/following-sibling::td"),
        ]
        for method, selector in title_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip()
                if text and len(text) > 10 and text not in ['ЕСЈН', 'Тип на договор']:
                    tender['title'] = text[:500]
                    break
            except:
                continue
        if not tender.get('title'):
            tender['title'] = 'Наслов не е пронајден'

        # === PROCURING ENTITY (CRITICAL) ===
        # Use label-for patterns from Playwright spider
        entity_patterns = [
            (By.XPATH, "//label[@label-for='CONTRACTING INSTITUTION NAME DOSIE']/following-sibling::label[contains(@class, 'dosie-value')][1]"),
            (By.XPATH, "//label[@label-for='CONTRACTING AUTHORITY NAME DOSIE']/following-sibling::label[contains(@class, 'dosie-value')][1]"),
            (By.XPATH, "//span[contains(@ng-bind, 'contractingAuthorityName')]"),
            (By.XPATH, "//span[contains(@ng-bind, 'institutionName')]"),
            (By.XPATH, "//td[contains(text(),'Договорен орган')]/following-sibling::td"),
            (By.XPATH, "//label[contains(text(),'Договорен орган')]/following-sibling::label"),
        ]
        for method, selector in entity_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip()
                if text and len(text) > 3:
                    tender['procuring_entity'] = text[:500]
                    break
            except:
                continue

        # === WINNER (IMPORTANT) ===
        winner_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'winnerName')]"),
            (By.XPATH, "//span[contains(@ng-bind, 'selectedOperator')]"),
            (By.XPATH, "//td[contains(text(),'Избран понудувач')]/following-sibling::td"),
            (By.XPATH, "//td[contains(text(),'Добитник')]/following-sibling::td"),
            (By.XPATH, "//label[contains(text(),'Понудувач')]/following-sibling::span"),
        ]
        for method, selector in winner_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip()
                if text and len(text) > 2 and text != '-':
                    tender['winner'] = text[:500]
                    break
            except:
                continue

        # === ESTIMATED VALUE ===
        value_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'estimatedValue')]"),
            (By.XPATH, "//span[contains(@ng-bind, 'contractValue')]"),
            (By.XPATH, "//td[contains(text(),'Проценета вредност')]/following-sibling::td"),
            (By.XPATH, "//td[contains(text(),'Вредност')]/following-sibling::td"),
        ]
        for method, selector in value_patterns:
            try:
                elem = driver.find_element(method, selector)
                value_text = elem.text.strip()
                value_clean = re.sub(r'[^\d.,]', '', value_text).replace(',', '').replace('.', '', value_text.count('.') - 1)
                if value_clean and float(value_clean) > 0:
                    tender['estimated_value_mkd'] = Decimal(value_clean)
                    break
            except:
                continue

        # === CPV CODE ===
        cpv_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'cpvCode')]"),
            (By.XPATH, "//td[contains(text(),'CPV')]/following-sibling::td"),
        ]
        for method, selector in cpv_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip()
                cpv_match = re.search(r'\d{8}', text)
                if cpv_match:
                    tender['cpv_code'] = cpv_match.group()
                    break
            except:
                continue

        # === PUBLICATION DATE ===
        date_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'publicationDate')]"),
            (By.XPATH, "//span[contains(@ng-bind, 'datePublished')]"),
            (By.XPATH, "//td[contains(text(),'Датум на објава')]/following-sibling::td"),
        ]
        for method, selector in date_patterns:
            try:
                elem = driver.find_element(method, selector)
                date_text = elem.text.strip()
                # Try parsing date
                for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y %H:%M']:
                    try:
                        tender['publication_date'] = datetime.strptime(date_text.split()[0], fmt.split()[0]).date()
                        break
                    except:
                        continue
                if tender.get('publication_date'):
                    break
            except:
                continue

        # === PROCEDURE TYPE ===
        procedure_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'procedureType')]"),
            (By.XPATH, "//td[contains(text(),'Вид на постапка')]/following-sibling::td"),
        ]
        for method, selector in procedure_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip()
                if text and len(text) > 2:
                    tender['procedure_type'] = text[:200]
                    break
            except:
                continue

        # === CATEGORY (GOODS/SERVICES/WORKS) ===
        category_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'contractType')]"),
            (By.XPATH, "//td[contains(text(),'Тип на договор')]/following-sibling::td"),
            (By.XPATH, "//span[contains(text(),'Стоки') or contains(text(),'Услуги') or contains(text(),'Работи')]"),
        ]
        for method, selector in category_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip().lower()
                if 'стоки' in text or 'goods' in text:
                    tender['category'] = 'goods'
                elif 'услуги' in text or 'services' in text:
                    tender['category'] = 'services'
                elif 'работи' in text or 'works' in text:
                    tender['category'] = 'works'
                break
            except:
                continue

        # === CLOSING DATE ===
        closing_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'deadlineDate')]"),
            (By.XPATH, "//td[contains(text(),'Рок за понуди')]/following-sibling::td"),
            (By.XPATH, "//td[contains(text(),'Краен рок')]/following-sibling::td"),
        ]
        for method, selector in closing_patterns:
            try:
                elem = driver.find_element(method, selector)
                date_text = elem.text.strip()
                for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y %H:%M']:
                    try:
                        tender['closing_date'] = datetime.strptime(date_text.split()[0], fmt.split()[0]).date()
                        break
                    except:
                        continue
                if tender.get('closing_date'):
                    break
            except:
                continue

        # === ACTUAL CONTRACT VALUE ===
        actual_value_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'contractValue')]"),
            (By.XPATH, "//span[contains(@ng-bind, 'awardedValue')]"),
            (By.XPATH, "//td[contains(text(),'Договорена вредност')]/following-sibling::td"),
        ]
        for method, selector in actual_value_patterns:
            try:
                elem = driver.find_element(method, selector)
                value_text = elem.text.strip()
                value_clean = re.sub(r'[^\d.,]', '', value_text).replace(',', '')
                if value_clean and float(value_clean) > 0:
                    tender['actual_value_mkd'] = Decimal(value_clean)
                    break
            except:
                continue

        # === NUM BIDDERS ===
        try:
            bidder_elems = driver.find_elements(By.XPATH, "//span[contains(@ng-bind, 'numberOfOffers')] | //td[contains(text(),'Број на понуди')]/following-sibling::td")
            for elem in bidder_elems:
                text = elem.text.strip()
                num_match = re.search(r'\d+', text)
                if num_match:
                    tender['num_bidders'] = int(num_match.group())
                    break
        except:
            pass

        # === CONTRACT SIGNING DATE ===
        signing_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'signingDate')]"),
            (By.XPATH, "//td[contains(text(),'Датум на потпишување')]/following-sibling::td"),
        ]
        for method, selector in signing_patterns:
            try:
                elem = driver.find_element(method, selector)
                date_text = elem.text.strip()
                for fmt in ['%d.%m.%Y', '%Y-%m-%d']:
                    try:
                        tender['contract_signing_date'] = datetime.strptime(date_text, fmt).date()
                        break
                    except:
                        continue
                if tender.get('contract_signing_date'):
                    break
            except:
                continue

        # === CONTACT INFO ===
        # Use label-for patterns from Playwright spider
        contact_patterns = {
            'contact_person': [
                "//label[@label-for='CONTRACTING INSTITUTION CONTACT PERSON DOSIE']/following-sibling::label[contains(@class, 'dosie-value')][1]",
                "//span[contains(@ng-bind, 'contactPerson')]",
                "//td[contains(text(),'Лице за контакт')]/following-sibling::td"
            ],
            'contact_email': [
                "//label[@label-for='CONTRACTING INSTITUTION EMAIL DOSIE']/following-sibling::label[contains(@class, 'dosie-value')][1]",
                "//span[contains(@ng-bind, 'email')]",
                "//a[contains(@href, 'mailto:')]"
            ],
            'contact_phone': [
                "//label[@label-for='CONTRACTING INSTITUTION PHONE DOSIE']/following-sibling::label[contains(@class, 'dosie-value')][1]",
                "//span[contains(@ng-bind, 'phone')]",
                "//td[contains(text(),'Телефон')]/following-sibling::td"
            ],
        }
        for field, selectors in contact_patterns.items():
            for selector in selectors:
                try:
                    elem = driver.find_element(By.XPATH, selector)
                    text = elem.text.strip() if 'mailto' not in selector else elem.get_attribute('href').replace('mailto:', '')
                    if text and len(text) > 2:
                        tender[field] = text[:255]
                        break
                except:
                    continue

        # === DELIVERY LOCATION ===
        location_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'deliveryLocation')]"),
            (By.XPATH, "//td[contains(text(),'Место на испорака')]/following-sibling::td"),
        ]
        for method, selector in location_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip()
                if text and len(text) > 2:
                    tender['delivery_location'] = text[:500]
                    break
            except:
                continue

        # === EVALUATION METHOD ===
        eval_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'evaluationMethod')]"),
            (By.XPATH, "//td[contains(text(),'Метод на оценување')]/following-sibling::td"),
        ]
        for method, selector in eval_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip()
                if text and len(text) > 2:
                    tender['evaluation_method'] = text[:200]
                    break
            except:
                continue

        # === ALL BIDDERS (JSON) ===
        try:
            bidder_rows = driver.find_elements(By.XPATH, "//table[contains(@class,'bidders')]//tr | //div[contains(@ng-repeat,'bidder')]")
            bidders = []
            for row in bidder_rows[:20]:  # Limit to 20 bidders
                try:
                    text = row.text.strip()
                    if text and len(text) > 5:
                        bidders.append({'name': text[:200]})
                except:
                    continue
            if bidders:
                tender['all_bidders_json'] = bidders
        except:
            pass

        # === OPENING DATE ===
        opening_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'openingDate')]"),
            (By.XPATH, "//td[contains(text(),'Датум на отворање')]/following-sibling::td"),
            (By.XPATH, "//label[@label-for='OPENING DATE']/following-sibling::label"),
        ]
        for method, selector in opening_patterns:
            try:
                elem = driver.find_element(method, selector)
                date_text = elem.text.strip()
                for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y']:
                    try:
                        tender['opening_date'] = datetime.strptime(date_text.split()[0], fmt).date()
                        break
                    except:
                        continue
                if tender.get('opening_date'):
                    break
            except:
                continue

        # === EUR VALUES (convert from MKD if needed) ===
        MKD_TO_EUR = Decimal('61.5')  # Approximate exchange rate
        if tender.get('estimated_value_mkd') and not tender.get('estimated_value_eur'):
            tender['estimated_value_eur'] = tender['estimated_value_mkd'] / MKD_TO_EUR
        if tender.get('actual_value_mkd') and not tender.get('actual_value_eur'):
            tender['actual_value_eur'] = tender['actual_value_mkd'] / MKD_TO_EUR

        # === SECURITY DEPOSIT ===
        deposit_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'securityDeposit')]"),
            (By.XPATH, "//td[contains(text(),'Гаранција за понуда')]/following-sibling::td"),
            (By.XPATH, "//label[contains(text(),'депозит')]/following-sibling::label"),
        ]
        for method, selector in deposit_patterns:
            try:
                elem = driver.find_element(method, selector)
                value_text = elem.text.strip()
                value_clean = re.sub(r'[^\d.,]', '', value_text).replace(',', '')
                if value_clean and float(value_clean) > 0:
                    tender['security_deposit_mkd'] = Decimal(value_clean)
                    break
            except:
                continue

        # === PERFORMANCE GUARANTEE ===
        guarantee_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'performanceGuarantee')]"),
            (By.XPATH, "//td[contains(text(),'Гаранција за извршување')]/following-sibling::td"),
        ]
        for method, selector in guarantee_patterns:
            try:
                elem = driver.find_element(method, selector)
                value_text = elem.text.strip()
                value_clean = re.sub(r'[^\d.,]', '', value_text).replace(',', '')
                if value_clean and float(value_clean) > 0:
                    tender['performance_guarantee_mkd'] = Decimal(value_clean)
                    break
            except:
                continue

        # === PAYMENT TERMS ===
        payment_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'paymentTerms')]"),
            (By.XPATH, "//td[contains(text(),'Услови за плаќање')]/following-sibling::td"),
            (By.XPATH, "//label[contains(text(),'плаќање')]/following-sibling::label"),
        ]
        for method, selector in payment_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip()
                if text and len(text) > 2:
                    tender['payment_terms'] = text[:500]
                    break
            except:
                continue

        # === CONTRACT DURATION ===
        duration_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'contractDuration')]"),
            (By.XPATH, "//td[contains(text(),'Времетраење')]/following-sibling::td"),
            (By.XPATH, "//label[contains(text(),'траење')]/following-sibling::label"),
        ]
        for method, selector in duration_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip()
                if text and len(text) > 1:
                    tender['contract_duration'] = text[:200]
                    break
            except:
                continue

        # === HIGHEST/LOWEST BID ===
        try:
            bid_patterns = [
                ("highest_bid_mkd", ["//span[contains(@ng-bind, 'highestBid')]", "//td[contains(text(),'Највисока понуда')]/following-sibling::td"]),
                ("lowest_bid_mkd", ["//span[contains(@ng-bind, 'lowestBid')]", "//td[contains(text(),'Најниска понуда')]/following-sibling::td"]),
            ]
            for field, selectors in bid_patterns:
                for selector in selectors:
                    try:
                        elem = driver.find_element(By.XPATH, selector)
                        value_text = elem.text.strip()
                        value_clean = re.sub(r'[^\d.,]', '', value_text).replace(',', '')
                        if value_clean and float(value_clean) > 0:
                            tender[field] = Decimal(value_clean)
                            break
                    except:
                        continue
        except:
            pass

        # === HAS LOTS / NUM LOTS ===
        try:
            lot_patterns = [
                (By.XPATH, "//span[contains(@ng-bind, 'hasLots')]"),
                (By.XPATH, "//td[contains(text(),'Поделено во делови')]/following-sibling::td"),
            ]
            for method, selector in lot_patterns:
                try:
                    elem = driver.find_element(method, selector)
                    text = elem.text.strip().lower()
                    tender['has_lots'] = 'да' in text or 'yes' in text or 'true' in text
                    break
                except:
                    continue

            # Count lots if present
            lot_rows = driver.find_elements(By.XPATH, "//div[contains(@ng-repeat,'lot')] | //tr[contains(@ng-repeat,'lot')]")
            tender['num_lots'] = len(lot_rows) if lot_rows else 0
        except:
            pass

        # === CONTRACTING ENTITY CATEGORY ===
        entity_cat_patterns = [
            (By.XPATH, "//span[contains(@ng-bind, 'entityCategory')]"),
            (By.XPATH, "//label[@label-for='CATEGORY OF CONTRACTING INSTITUTION']/following-sibling::label"),
            (By.XPATH, "//td[contains(text(),'Категорија')]/following-sibling::td"),
        ]
        for method, selector in entity_cat_patterns:
            try:
                elem = driver.find_element(method, selector)
                text = elem.text.strip()
                if text and len(text) > 2:
                    tender['contracting_entity_category'] = text[:200]
                    break
            except:
                continue

        # === RAW CONTENT FOR EMBEDDINGS (COMPREHENSIVE) ===
        try:
            # Get all visible text from the page for embedding
            body_elem = driver.find_element(By.TAG_NAME, "body")
            raw_text = body_elem.text

            # Clean up and limit size
            raw_text = re.sub(r'\s+', ' ', raw_text).strip()
            if len(raw_text) > 100:  # Only if meaningful content
                tender['description'] = raw_text[:10000]  # Limit for DB

            # Store COMPREHENSIVE raw data as JSON for LLM/embeddings
            tender['raw_json'] = {
                # Core identifiers
                'tender_id': tender.get('tender_id'),
                'dossier_id': tender.get('dossier_id'),
                'source_url': url,

                # Main content
                'title': tender.get('title'),
                'description': tender.get('description'),
                'procuring_entity': tender.get('procuring_entity'),
                'winner': tender.get('winner'),
                'category': tender.get('category'),

                # Codes and types
                'cpv_code': tender.get('cpv_code'),
                'procedure_type': tender.get('procedure_type'),
                'contracting_entity_category': tender.get('contracting_entity_category'),

                # Dates
                'publication_date': str(tender.get('publication_date')) if tender.get('publication_date') else None,
                'opening_date': str(tender.get('opening_date')) if tender.get('opening_date') else None,
                'closing_date': str(tender.get('closing_date')) if tender.get('closing_date') else None,
                'contract_signing_date': str(tender.get('contract_signing_date')) if tender.get('contract_signing_date') else None,

                # Values
                'estimated_value_mkd': str(tender.get('estimated_value_mkd')) if tender.get('estimated_value_mkd') else None,
                'actual_value_mkd': str(tender.get('actual_value_mkd')) if tender.get('actual_value_mkd') else None,
                'security_deposit_mkd': str(tender.get('security_deposit_mkd')) if tender.get('security_deposit_mkd') else None,

                # Contact info
                'contact_person': tender.get('contact_person'),
                'contact_email': tender.get('contact_email'),
                'contact_phone': tender.get('contact_phone'),

                # Bidding info
                'num_bidders': tender.get('num_bidders'),
                'evaluation_method': tender.get('evaluation_method'),
                'delivery_location': tender.get('delivery_location'),
                'payment_terms': tender.get('payment_terms'),
                'contract_duration': tender.get('contract_duration'),

                # Lots
                'has_lots': tender.get('has_lots'),
                'num_lots': tender.get('num_lots'),

                # Metadata
                'scraped_at': datetime.now().isoformat(),
                'language': 'mk',

                # Full page text for embedding/RAG
                'full_text': raw_text[:100000] if raw_text else None,  # Full text for embeddings
                'page_html_length': len(page_source) if page_source else 0,
            }

            # Also store as raw_data_json for the AI fallback column
            tender['raw_data_json'] = tender['raw_json']

        except Exception as e:
            logger.debug(f"Could not extract raw content: {e}")

        # Validate extracted data
        if not tender.get('tender_id') or tender['tender_id'].startswith('SEL-'):
            logger.warning(f"Could not extract proper tender_id from {url}")

        return tender

    except Exception as e:
        logger.error(f"Extract error for {url}: {e}")
        return None


def save_tender_sync(tender: Dict[str, Any]) -> bool:
    """Save ALL 40+ tender fields to database (synchronous version)."""
    import psycopg2
    import json

    if not tender.get('tender_id'):
        return False

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Check if exists
        cur.execute("SELECT tender_id, winner, procuring_entity FROM tenders WHERE tender_id = %s", (tender['tender_id'],))
        existing = cur.fetchone()

        # Convert JSON fields
        raw_json_str = json.dumps(tender.get('raw_json'), ensure_ascii=False, default=str) if tender.get('raw_json') else None
        raw_data_json_str = json.dumps(tender.get('raw_data_json'), ensure_ascii=False, default=str) if tender.get('raw_data_json') else None
        all_bidders_str = json.dumps(tender.get('all_bidders_json'), ensure_ascii=False) if tender.get('all_bidders_json') else None

        if existing:
            # Update - comprehensive update of all NULL fields (40+ fields)
            cur.execute("""
                UPDATE tenders SET
                    title = CASE WHEN title IS NULL OR title = 'Unknown' OR title = 'Наслов не е пронајден'
                                 THEN COALESCE(%s, title) ELSE title END,
                    description = CASE WHEN description IS NULL OR LENGTH(description) < 100
                                       THEN COALESCE(%s, description) ELSE description END,
                    category = COALESCE(category, %s),
                    procuring_entity = COALESCE(procuring_entity, %s),
                    closing_date = COALESCE(closing_date, %s),
                    opening_date = COALESCE(opening_date, %s),
                    publication_date = COALESCE(publication_date, %s),
                    estimated_value_mkd = COALESCE(estimated_value_mkd, %s),
                    estimated_value_eur = COALESCE(estimated_value_eur, %s),
                    actual_value_mkd = COALESCE(actual_value_mkd, %s),
                    actual_value_eur = COALESCE(actual_value_eur, %s),
                    cpv_code = COALESCE(cpv_code, %s),
                    winner = COALESCE(winner, %s),
                    procedure_type = COALESCE(procedure_type, %s),
                    contract_signing_date = COALESCE(contract_signing_date, %s),
                    contact_person = COALESCE(contact_person, %s),
                    contact_email = COALESCE(contact_email, %s),
                    contact_phone = COALESCE(contact_phone, %s),
                    num_bidders = COALESCE(num_bidders, %s),
                    evaluation_method = COALESCE(evaluation_method, %s),
                    delivery_location = COALESCE(delivery_location, %s),
                    tender_uuid = COALESCE(tender_uuid, %s),
                    dossier_id = COALESCE(dossier_id, %s),
                    source_url = COALESCE(%s, source_url),
                    security_deposit_mkd = COALESCE(security_deposit_mkd, %s),
                    performance_guarantee_mkd = COALESCE(performance_guarantee_mkd, %s),
                    payment_terms = COALESCE(payment_terms, %s),
                    contract_duration = COALESCE(contract_duration, %s),
                    has_lots = COALESCE(has_lots, %s),
                    num_lots = COALESCE(num_lots, %s),
                    contracting_entity_category = COALESCE(contracting_entity_category, %s),
                    raw_json = CASE WHEN raw_json IS NULL THEN %s::jsonb ELSE raw_json END,
                    raw_data_json = CASE WHEN raw_data_json IS NULL THEN %s::jsonb ELSE raw_data_json END,
                    all_bidders_json = CASE WHEN all_bidders_json IS NULL THEN %s::jsonb ELSE all_bidders_json END,
                    scraped_at = NOW(),
                    updated_at = NOW(),
                    scrape_count = COALESCE(scrape_count, 0) + 1
                WHERE tender_id = %s
            """, (
                tender.get('title'),
                tender.get('description'),
                tender.get('category'),
                tender.get('procuring_entity'),
                tender.get('closing_date'),
                tender.get('opening_date'),
                tender.get('publication_date'),
                tender.get('estimated_value_mkd'),
                tender.get('estimated_value_eur'),
                tender.get('actual_value_mkd'),
                tender.get('actual_value_eur'),
                tender.get('cpv_code'),
                tender.get('winner'),
                tender.get('procedure_type'),
                tender.get('contract_signing_date'),
                tender.get('contact_person'),
                tender.get('contact_email'),
                tender.get('contact_phone'),
                tender.get('num_bidders'),
                tender.get('evaluation_method'),
                tender.get('delivery_location'),
                tender.get('tender_uuid'),
                tender.get('dossier_id'),
                tender.get('source_url'),
                tender.get('security_deposit_mkd'),
                tender.get('performance_guarantee_mkd'),
                tender.get('payment_terms'),
                tender.get('contract_duration'),
                tender.get('has_lots'),
                tender.get('num_lots'),
                tender.get('contracting_entity_category'),
                raw_json_str,
                raw_data_json_str,
                all_bidders_str,
                tender['tender_id'],
            ))
            with stats_lock:
                global_stats['tenders_updated'] += 1
            action = "updated"
        else:
            # Insert new tender with ALL 40+ fields
            cur.execute("""
                INSERT INTO tenders (
                    tender_id, title, description, category, procuring_entity,
                    closing_date, opening_date, publication_date,
                    estimated_value_mkd, estimated_value_eur, actual_value_mkd, actual_value_eur,
                    cpv_code, winner, procedure_type, contract_signing_date,
                    contact_person, contact_email, contact_phone, num_bidders,
                    evaluation_method, delivery_location, tender_uuid, dossier_id,
                    source_url, security_deposit_mkd, performance_guarantee_mkd,
                    payment_terms, contract_duration, has_lots, num_lots,
                    contracting_entity_category, raw_json, raw_data_json, all_bidders_json,
                    language, status, scraped_at, created_at, updated_at, scrape_count, first_scraped_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                    'mk', 'awarded', NOW(), NOW(), NOW(), 1, NOW()
                )
            """, (
                tender['tender_id'],
                tender.get('title', 'Unknown'),
                tender.get('description'),
                tender.get('category'),
                tender.get('procuring_entity'),
                tender.get('closing_date'),
                tender.get('opening_date'),
                tender.get('publication_date'),
                tender.get('estimated_value_mkd'),
                tender.get('estimated_value_eur'),
                tender.get('actual_value_mkd'),
                tender.get('actual_value_eur'),
                tender.get('cpv_code'),
                tender.get('winner'),
                tender.get('procedure_type'),
                tender.get('contract_signing_date'),
                tender.get('contact_person'),
                tender.get('contact_email'),
                tender.get('contact_phone'),
                tender.get('num_bidders'),
                tender.get('evaluation_method'),
                tender.get('delivery_location'),
                tender.get('tender_uuid'),
                tender.get('dossier_id'),
                tender.get('source_url'),
                tender.get('security_deposit_mkd'),
                tender.get('performance_guarantee_mkd'),
                tender.get('payment_terms'),
                tender.get('contract_duration'),
                tender.get('has_lots'),
                tender.get('num_lots'),
                tender.get('contracting_entity_category'),
                raw_json_str,
                raw_data_json_str,
                all_bidders_str,
            ))
            with stats_lock:
                global_stats['tenders_saved'] += 1
            action = "saved"

        conn.commit()
        cur.close()
        conn.close()

        # Log with quality indicators
        quality = []
        if tender.get('winner'):
            quality.append('W')
        if tender.get('procuring_entity'):
            quality.append('E')
        if tender.get('estimated_value_mkd'):
            quality.append('V')
        if tender.get('raw_data_json'):
            quality.append('R')
        quality_str = ''.join(quality) if quality else 'minimal'

        logger.debug(f"{action}: {tender['tender_id']} [{quality_str}]")
        return True

    except Exception as e:
        logger.error(f"DB error saving {tender.get('tender_id')}: {e}")
        with stats_lock:
            global_stats['errors'] += 1
        return False


def collect_all_links(category: str, max_pages: int, headless: bool = True) -> List[str]:
    """Collect all tender links by navigating through listing pages."""
    logger.info(f"Collecting links from {max_pages} pages for category: {category}")

    driver = create_driver(headless)
    all_links = []
    consecutive_empty = 0
    consecutive_failures = 0

    try:
        url = CATEGORY_URLS.get(category, CATEGORY_URLS['awarded'])
        logger.info(f"Loading: {url}")
        driver.get(url)
        time.sleep(5)  # Longer initial wait for Angular SPA
        wait_for_angular(driver, timeout=30)

        # Wait for table with multiple selectors
        table_loaded = False
        table_selectors = [
            "table tbody tr",
            "table.dataTable tbody tr",
            "#contracts-grid tbody tr",
            "#notices-grid tbody tr",
        ]

        for selector in table_selectors:
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                table_loaded = True
                logger.info(f"Table loaded with selector: {selector}")
                break
            except TimeoutException:
                continue

        if not table_loaded:
            logger.error("Could not find table on listing page")
            driver.quit()
            return []

        # Get page info
        try:
            info = driver.find_element(By.CSS_SELECTOR, ".dataTables_info").text
            logger.info(f"DataTable info: {info}")
        except:
            pass

        page = 0
        while page < max_pages:
            page += 1

            # Get links from current page
            links = get_tender_links(driver)

            if links:
                new_count = len([l for l in links if l not in all_links])
                all_links.extend(links)
                consecutive_empty = 0
                logger.info(f"Page {page}: Found {len(links)} links ({new_count} new), total: {len(set(all_links))}")
            else:
                consecutive_empty += 1
                logger.warning(f"Page {page}: No links found (consecutive empty: {consecutive_empty})")
                if consecutive_empty >= 3:
                    logger.warning("Too many consecutive empty pages, stopping")
                    break

            # Log progress every 10 pages
            if page % 10 == 0:
                unique_count = len(set(all_links))
                logger.info(f"Progress: {page} pages, {unique_count} unique links")

            # Try to go to next page
            if not click_next_page(driver):
                consecutive_failures += 1
                logger.warning(f"Next page click failed (attempt {consecutive_failures})")

                if consecutive_failures >= 3:
                    logger.info(f"Reached last page at {page} (3 consecutive failures)")
                    break

                # Try refreshing and navigating again
                time.sleep(2)
                continue
            else:
                consecutive_failures = 0

            # Small delay between pages
            time.sleep(0.5)

    except Exception as e:
        logger.error(f"Error collecting links: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

    unique_links = list(set(all_links))
    logger.info(f"Collection complete: {len(unique_links)} unique links from {page} pages")
    return unique_links


def worker_process_links(worker_id: int, links: List[str], headless: bool):
    """Worker function to process a batch of tender links."""
    logger.info(f"Worker {worker_id} starting: {len(links)} tenders to process")

    driver = None
    processed = 0

    try:
        driver = create_driver(headless)

        for link in links:
            try:
                tender = extract_tender(driver, link)
                if tender:
                    save_tender_sync(tender)
                    processed += 1

                    if processed % 10 == 0:
                        logger.info(f"Worker {worker_id}: Processed {processed}/{len(links)}")

                # Small delay
                time.sleep(0.2)

            except Exception as e:
                logger.error(f"Worker {worker_id} error on {link}: {e}")
                with stats_lock:
                    global_stats['errors'] += 1

    except Exception as e:
        logger.error(f"Worker {worker_id} fatal error: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    logger.info(f"Worker {worker_id} finished: {processed}/{len(links)} processed")


def main():
    parser = argparse.ArgumentParser(description='Parallel Selenium Scraper')
    parser.add_argument('--workers', type=int, default=6, help='Number of parallel workers')
    parser.add_argument('--max-pages', type=int, default=100, help='Maximum pages to scrape')
    parser.add_argument('--category', default='awarded', help='Category to scrape')
    parser.add_argument('--no-headless', action='store_true', help='Run with visible browsers')

    args = parser.parse_args()

    headless = not args.no_headless
    num_workers = args.workers

    logger.info(f"Starting parallel scrape: {num_workers} workers, {args.max_pages} pages")

    start_time = time.time()

    # Phase 1: Collect all links from listing pages (single browser)
    logger.info("=" * 60)
    logger.info("PHASE 1: Collecting tender links...")
    logger.info("=" * 60)

    all_links = collect_all_links(args.category, args.max_pages, headless)

    if not all_links:
        logger.error("No links collected!")
        return

    with stats_lock:
        global_stats['tenders_found'] = len(all_links)

    collect_time = time.time() - start_time
    logger.info(f"Collection took {collect_time:.1f}s")

    # Phase 2: Process links in parallel
    logger.info("=" * 60)
    logger.info(f"PHASE 2: Processing {len(all_links)} tenders with {num_workers} workers...")
    logger.info("=" * 60)

    # Split links among workers
    links_per_worker = len(all_links) // num_workers
    link_batches = []
    for i in range(num_workers):
        start_idx = i * links_per_worker
        if i == num_workers - 1:
            batch = all_links[start_idx:]
        else:
            batch = all_links[start_idx:start_idx + links_per_worker]
        link_batches.append(batch)

    process_start = time.time()

    # Process in parallel
    with ThreadPoolExecutor(max_workers=num_workers, thread_name_prefix='Worker') as executor:
        futures = []
        for i, batch in enumerate(link_batches):
            future = executor.submit(worker_process_links, i + 1, batch, headless)
            futures.append(future)

        # Wait for all workers
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Worker failed: {e}")

    process_time = time.time() - process_start
    total_time = time.time() - start_time

    logger.info("=" * 60)
    logger.info("PARALLEL SCRAPE COMPLETE")
    logger.info(f"Workers: {num_workers}")
    logger.info(f"Pages scraped: {args.max_pages}")
    logger.info(f"Collection time: {collect_time:.1f}s")
    logger.info(f"Processing time: {process_time:.1f}s ({process_time/60:.1f} min)")
    logger.info(f"Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    logger.info(f"Tenders found: {global_stats['tenders_found']}")
    logger.info(f"Tenders saved (new): {global_stats['tenders_saved']}")
    logger.info(f"Tenders updated: {global_stats['tenders_updated']}")
    logger.info(f"Errors: {global_stats['errors']}")
    if process_time > 0 and global_stats['tenders_found'] > 0:
        rate = (global_stats['tenders_saved'] + global_stats['tenders_updated']) / (process_time / 60)
        logger.info(f"Rate: {rate:.1f} tenders/min")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()

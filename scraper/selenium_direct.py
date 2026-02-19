#!/usr/bin/env python3
"""
Direct URL Selenium Scraper for E-Nabavki

Bypasses pagination entirely by directly scraping tender detail pages using
existing GUIDs from the database. This is more reliable than trying to
navigate the Angular SPA pagination.

Usage:
    # Scrape tenders missing key data (winner, value, etc.)
    python selenium_direct.py --workers 4 --limit 1000

    # Scrape all tenders from a specific year
    python selenium_direct.py --workers 6 --year 2024

    # Scrape specific tender IDs
    python selenium_direct.py --tender-ids "123/2024,456/2024"
"""

import argparse
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from threading import Lock
import json

import psycopg2
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
        logging.FileHandler(f'logs/direct_scrape_{datetime.now().strftime("%Y%m%d_%H%M")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)

# Thread-safe stats
stats_lock = Lock()
global_stats = {
    'tenders_processed': 0,
    'tenders_updated': 0,
    'tenders_skipped': 0,
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

    # DISABLE GPU for stability in headless mode
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')

    # Memory/performance
    options.add_argument('--disable-extensions')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')

    # Reduce logging
    options.add_argument('--log-level=3')
    options.add_argument('--silent')

    # Use normal page load for full Angular rendering
    options.page_load_strategy = 'normal'

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(120)
    driver.implicitly_wait(10)
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


def get_tenders_to_scrape(limit: int = 1000, year: Optional[int] = None,
                          missing_fields: bool = True, tender_ids: Optional[List[str]] = None) -> List[Dict]:
    """Get list of tenders that need scraping from database."""
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=30)
    cur = conn.cursor()

    if tender_ids:
        # Specific tender IDs requested
        placeholders = ','.join(['%s'] * len(tender_ids))
        cur.execute(f"""
            SELECT tender_id, dossier_id, source_url
            FROM tenders
            WHERE tender_id IN ({placeholders})
        """, tender_ids)
    elif missing_fields:
        # Get tenders missing important data that we CAN scrape (have URL)
        year_filter = ""
        if year:
            year_filter = f"AND tender_id LIKE '%%/{year}'"

        cur.execute(f"""
            SELECT tender_id, dossier_id, source_url
            FROM tenders
            WHERE (
                raw_data_json IS NULL
                OR winner IS NULL
                OR procuring_entity IS NULL
            )
            AND (
                dossier_id IS NOT NULL
                OR source_url LIKE '%%e-nabavki.gov.mk%%dossie%%'
            )
            {year_filter}
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
    else:
        # Get all scrapeable tenders from specified year
        year_filter = "AND tender_id LIKE '%%/" + str(year) + "'" if year else ""

        cur.execute(f"""
            SELECT tender_id, dossier_id, source_url
            FROM tenders
            WHERE (
                dossier_id IS NOT NULL
                OR source_url LIKE '%%e-nabavki.gov.mk%%dossie%%'
            )
            {year_filter}
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))

    results = []
    for row in cur.fetchall():
        tender_id, dossier_id, source_url = row

        # Extract dossier_id from URL if not directly available
        if not dossier_id and source_url:
            import re
            match = re.search(r'/dossie-acpp/([a-f0-9-]+)', source_url)
            if match:
                dossier_id = match.group(1)

        # Build URL if we have dossier_id
        if dossier_id:
            url = f"https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/{dossier_id}"
        elif source_url and 'e-nabavki' in source_url:
            url = source_url
        else:
            continue  # Skip if no way to access

        results.append({
            'tender_id': tender_id,
            'dossier_id': dossier_id,
            'url': url
        })

    cur.close()
    conn.close()

    logger.info(f"Found {len(results)} scrapeable tenders")
    return results


def parse_date(text: str):
    """Parse date from various formats."""
    if not text:
        return None
    text = text.strip()
    for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
        try:
            return datetime.strptime(text, fmt).date()
        except:
            continue
    # Try regex
    match = re.search(r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})', text)
    if match:
        try:
            return datetime(int(match.group(3)), int(match.group(2)), int(match.group(1))).date()
        except:
            pass
    return None


def parse_value(text: str):
    """Parse currency value."""
    if not text:
        return None
    text = re.sub(r'[^\d.,]', '', text).replace(',', '')
    try:
        val = float(text)
        return Decimal(str(val)) if val > 0 else None
    except:
        return None


def extract_tender(driver, url: str, expected_tender_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Extract ALL available tender data from detail page - COMPREHENSIVE VERSION."""
    try:
        driver.get(url)
        time.sleep(1)
        wait_for_angular(driver, timeout=10)

        # Wait for content
        for selector in ["label.dosie-value", ".panel", "table"]:
            try:
                WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                break
            except TimeoutException:
                continue

        time.sleep(0.5)
        tender = {'source_url': url, 'language': 'mk'}

        # Extract dossier ID from URL
        id_match = re.search(r'/dossie(?:-acpp)?/([a-f0-9-]+)', url)
        if id_match:
            tender['dossier_id'] = id_match.group(1)
            tender['tender_uuid'] = id_match.group(1)

        page_text = driver.find_element(By.TAG_NAME, "body").text if driver.find_elements(By.TAG_NAME, "body") else ""
        page_source = driver.page_source

        # Helper to extract by label-for pattern
        def get_by_label(label_for_values, max_len=500):
            for lf in label_for_values:
                try:
                    elem = driver.find_element(By.XPATH, f"//label[@label-for='{lf}']/following-sibling::label[contains(@class, 'dosie-value')][1]")
                    text = elem.text.strip()
                    if text and len(text) > 1 and text != '-':
                        return text[:max_len]
                except:
                    continue
            return None

        # === TENDER ID ===
        tender['tender_id'] = get_by_label([
            'PROCESS NUMBER FOR NOTIFICATION DOSSIE',
            'ANNOUNCEMENT NUMBER DOSIE',
            'NUMBER OF NOTICE DOSIE'
        ], 50)
        if not tender.get('tender_id'):
            match = re.search(r'\b(\d{1,6}/20[0-2][0-9])\b', page_text)
            tender['tender_id'] = match.group(1) if match else expected_tender_id

        # === TITLE ===
        tender['title'] = get_by_label(['SUBJECT:', 'SUBJECT', 'DETAIL DESCRIPTION OF THE ITEM TO BE PROCURED DOSIE'])

        # === PROCURING ENTITY ===
        tender['procuring_entity'] = get_by_label(['CONTRACTING INSTITUTION NAME DOSIE', 'CONTRACTING AUTHORITY NAME DOSIE'])

        # === CATEGORY ===
        tender['category'] = get_by_label(['TYPE OF PROCUREMENT DOSIE', 'PROCUREMENT TYPE DOSIE'])

        # === PROCEDURE TYPE ===
        tender['procedure_type'] = get_by_label(['PROCUREMENT PROCEDURE DOSIE', 'TYPE OF PROCEDURE DOSIE', 'PROCEDURE TYPE DOSIE'])

        # === CONTRACTING ENTITY CATEGORY ===
        tender['contracting_entity_category'] = get_by_label(['CONTRACTING AUTHORITY TYPE DOSIE', 'CONTRACTING ENTITY TYPE DOSIE'])

        # === DATES ===
        pub_date = get_by_label(['PUBLICATION DATE DOSIE', 'DATE OF PUBLICATION DOSIE'])
        tender['publication_date'] = parse_date(pub_date)

        open_date = get_by_label(['OPENING DATE DOSIE', 'OFFER OPENING DATE DOSIE', 'BID OPENING DATE DOSIE'])
        tender['opening_date'] = parse_date(open_date)

        close_date = get_by_label(['DEADLINE DOSIE', 'CLOSING DATE DOSIE', 'OFFER DEADLINE DOSIE', 'SUBMISSION DEADLINE DOSIE'])
        tender['closing_date'] = parse_date(close_date)

        contract_date = get_by_label(['CONTRACT SIGNING DATE DOSIE', 'DATE OF CONTRACT DOSIE'])
        tender['contract_signing_date'] = parse_date(contract_date)

        bureau_date = get_by_label(['BUREAU DELIVERY DATE DOSIE', 'DELIVERY TO BUREAU DATE DOSIE'])
        tender['bureau_delivery_date'] = parse_date(bureau_date)

        # === VALUES ===
        est_val = get_by_label(['ESTIMATED VALUE DOSIE', 'ESTIMATED CONTRACT VALUE DOSIE'])
        tender['estimated_value_mkd'] = parse_value(est_val)

        act_val = get_by_label(['CONTRACT VALUE DOSIE', 'ACTUAL VALUE DOSIE', 'FINAL VALUE DOSIE'])
        tender['actual_value_mkd'] = parse_value(act_val)

        sec_dep = get_by_label(['SECURITY DEPOSIT DOSIE', 'BID SECURITY DOSIE', 'GUARANTEE AMOUNT DOSIE'])
        tender['security_deposit_mkd'] = parse_value(sec_dep)

        perf_guar = get_by_label(['PERFORMANCE GUARANTEE DOSIE', 'PERFORMANCE SECURITY DOSIE'])
        tender['performance_guarantee_mkd'] = parse_value(perf_guar)

        # === CONTRACT DURATION ===
        tender['contract_duration'] = get_by_label(['CONTRACT DURATION DOSIE', 'DURATION DOSIE', 'CONTRACT PERIOD DOSIE'], 100)

        # === WINNER ===
        winner = None
        for sel in ["//span[contains(@ng-bind, 'winnerName')]", "//span[contains(@ng-bind, 'selectedOperator')]"]:
            try:
                elem = driver.find_element(By.XPATH, sel)
                if elem.text.strip() and elem.text.strip() != '-':
                    winner = elem.text.strip()[:500]
                    break
            except:
                continue
        tender['winner'] = winner or get_by_label(['SELECTED OPERATOR DOSIE', 'WINNER DOSIE'])

        # === CPV CODE ===
        cpv = None
        try:
            for elem in driver.find_elements(By.XPATH, "//span[contains(@ng-bind, 'cpvCode')] | //*[contains(text(), 'CPV')]"):
                match = re.search(r'\d{8}', elem.text)
                if match:
                    cpv = match.group()
                    break
        except:
            pass
        tender['cpv_code'] = cpv

        # === CONTACT INFO ===
        tender['contact_person'] = get_by_label(['CONTRACTING INSTITUTION CONTACT PERSON DOSIE', 'CONTACT PERSON DOSIE'], 255)
        tender['contact_email'] = get_by_label(['CONTRACTING INSTITUTION EMAIL DOSIE', 'EMAIL DOSIE'], 255)
        tender['contact_phone'] = get_by_label(['CONTRACTING INSTITUTION PHONE DOSIE', 'PHONE DOSIE'], 100)

        # === EVALUATION METHOD ===
        tender['evaluation_method'] = get_by_label(['EVALUATION CRITERIA DOSIE', 'AWARD CRITERIA DOSIE', 'EVALUATION METHOD DOSIE'])

        # === PAYMENT TERMS ===
        tender['payment_terms'] = get_by_label(['PAYMENT TERMS DOSIE', 'PAYMENT CONDITIONS DOSIE'])

        # === DELIVERY LOCATION ===
        tender['delivery_location'] = get_by_label(['DELIVERY LOCATION DOSIE', 'PLACE OF DELIVERY DOSIE', 'DELIVERY ADDRESS DOSIE'])

        # === LOTS ===
        has_lots = get_by_label(['HAS LOTS DOSIE', 'DIVIDED INTO LOTS DOSIE'])
        tender['has_lots'] = has_lots.lower() in ('да', 'yes', 'true') if has_lots else False

        # Count lots from page
        lots_data = []
        try:
            lot_rows = driver.find_elements(By.XPATH, "//tr[contains(@ng-repeat, 'lot')]")
            for row in lot_rows[:50]:  # Max 50 lots
                lot_text = row.text.strip()
                if lot_text:
                    lots_data.append({'text': lot_text[:500]})
        except:
            pass
        tender['num_lots'] = len(lots_data) if lots_data else (1 if tender['has_lots'] else 0)
        tender['lots_data'] = json.dumps(lots_data, ensure_ascii=False) if lots_data else None

        # === BIDDERS ===
        bidders = []
        try:
            bidder_rows = driver.find_elements(By.XPATH, "//tr[contains(@ng-repeat, 'offer')] | //tr[contains(@ng-repeat, 'bid')]")
            for row in bidder_rows[:100]:
                cells = row.find_elements(By.TAG_NAME, 'td')
                if len(cells) >= 2:
                    bidders.append({
                        'name': cells[0].text.strip()[:500] if cells[0].text else None,
                        'value': cells[1].text.strip() if len(cells) > 1 else None
                    })
        except:
            pass
        tender['num_bidders'] = len(bidders) if bidders else None
        tender['all_bidders_json'] = json.dumps(bidders, ensure_ascii=False) if bidders else None

        # Extract highest/lowest bids
        if bidders:
            values = []
            for b in bidders:
                v = parse_value(b.get('value', ''))
                if v:
                    values.append(v)
            if values:
                tender['highest_bid_mkd'] = max(values)
                tender['lowest_bid_mkd'] = min(values)

        # === DOCUMENTS ===
        documents = []
        try:
            doc_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf') or contains(@href, 'download') or contains(@href, 'document')]")
            for link in doc_links[:50]:
                href = link.get_attribute('href')
                if href and 'e-nabavki.gov.mk' in href:
                    documents.append({
                        'url': href,
                        'name': link.text.strip()[:200] if link.text else 'document'
                    })
        except:
            pass

        # === RAW CONTENT ===
        raw_text = re.sub(r'\s+', ' ', page_text).strip()
        tender['description'] = raw_text[:10000] if len(raw_text) > 100 else None

        # Store comprehensive raw data
        tender['raw_json'] = {
            'tender_id': tender.get('tender_id'),
            'dossier_id': tender.get('dossier_id'),
            'source_url': url,
            'title': tender.get('title'),
            'procuring_entity': tender.get('procuring_entity'),
            'category': tender.get('category'),
            'procedure_type': tender.get('procedure_type'),
            'publication_date': str(tender.get('publication_date')) if tender.get('publication_date') else None,
            'opening_date': str(tender.get('opening_date')) if tender.get('opening_date') else None,
            'closing_date': str(tender.get('closing_date')) if tender.get('closing_date') else None,
            'estimated_value_mkd': str(tender.get('estimated_value_mkd')) if tender.get('estimated_value_mkd') else None,
            'actual_value_mkd': str(tender.get('actual_value_mkd')) if tender.get('actual_value_mkd') else None,
            'winner': tender.get('winner'),
            'cpv_code': tender.get('cpv_code'),
            'contact_person': tender.get('contact_person'),
            'contact_email': tender.get('contact_email'),
            'contact_phone': tender.get('contact_phone'),
            'num_bidders': tender.get('num_bidders'),
            'num_lots': tender.get('num_lots'),
            'documents': documents,
            'scraped_at': datetime.now().isoformat(),
            'full_text': raw_text[:100000] if raw_text else None,
        }
        tender['raw_data_json'] = tender['raw_json']

        return tender

    except Exception as e:
        logger.error(f"Extract error for {url}: {e}")
        return None


def update_tender(tender: Dict[str, Any]) -> bool:
    """Update existing tender with ALL new data fields."""
    if not tender.get('tender_id'):
        return False

    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=30)
        cur = conn.cursor()

        raw_json_str = json.dumps(tender.get('raw_json'), ensure_ascii=False, default=str) if tender.get('raw_json') else None
        raw_data_json_str = json.dumps(tender.get('raw_data_json'), ensure_ascii=False, default=str) if tender.get('raw_data_json') else None
        all_bidders_str = tender.get('all_bidders_json')
        lots_data_str = tender.get('lots_data')

        # Update ALL fields - COALESCE keeps existing values if new is NULL
        cur.execute("""
            UPDATE tenders SET
                title = CASE WHEN title IS NULL OR title = 'Unknown' THEN COALESCE(%s, title) ELSE title END,
                description = COALESCE(%s, description),
                procuring_entity = COALESCE(%s, procuring_entity),
                category = COALESCE(%s, category),
                procedure_type = COALESCE(%s, procedure_type),
                contracting_entity_category = COALESCE(%s, contracting_entity_category),
                publication_date = COALESCE(%s, publication_date),
                opening_date = COALESCE(%s, opening_date),
                closing_date = COALESCE(%s, closing_date),
                contract_signing_date = COALESCE(%s, contract_signing_date),
                bureau_delivery_date = COALESCE(%s, bureau_delivery_date),
                estimated_value_mkd = COALESCE(%s, estimated_value_mkd),
                actual_value_mkd = COALESCE(%s, actual_value_mkd),
                security_deposit_mkd = COALESCE(%s, security_deposit_mkd),
                performance_guarantee_mkd = COALESCE(%s, performance_guarantee_mkd),
                contract_duration = COALESCE(%s, contract_duration),
                winner = COALESCE(%s, winner),
                cpv_code = COALESCE(%s, cpv_code),
                contact_person = COALESCE(%s, contact_person),
                contact_email = COALESCE(%s, contact_email),
                contact_phone = COALESCE(%s, contact_phone),
                evaluation_method = COALESCE(%s, evaluation_method),
                payment_terms = COALESCE(%s, payment_terms),
                delivery_location = COALESCE(%s, delivery_location),
                has_lots = COALESCE(%s, has_lots),
                num_lots = COALESCE(%s, num_lots),
                num_bidders = COALESCE(%s, num_bidders),
                highest_bid_mkd = COALESCE(%s, highest_bid_mkd),
                lowest_bid_mkd = COALESCE(%s, lowest_bid_mkd),
                dossier_id = COALESCE(%s, dossier_id),
                tender_uuid = COALESCE(%s, tender_uuid),
                source_url = COALESCE(%s, source_url),
                all_bidders_json = COALESCE(%s::jsonb, all_bidders_json),
                lots_data = COALESCE(%s::jsonb, lots_data),
                raw_json = COALESCE(%s::jsonb, raw_json),
                raw_data_json = COALESCE(%s::jsonb, raw_data_json),
                scraped_at = NOW(),
                updated_at = NOW()
            WHERE tender_id = %s
            RETURNING tender_id
        """, (
            tender.get('title'),
            tender.get('description'),
            tender.get('procuring_entity'),
            tender.get('category'),
            tender.get('procedure_type'),
            tender.get('contracting_entity_category'),
            tender.get('publication_date'),
            tender.get('opening_date'),
            tender.get('closing_date'),
            tender.get('contract_signing_date'),
            tender.get('bureau_delivery_date'),
            tender.get('estimated_value_mkd'),
            tender.get('actual_value_mkd'),
            tender.get('security_deposit_mkd'),
            tender.get('performance_guarantee_mkd'),
            tender.get('contract_duration'),
            tender.get('winner'),
            tender.get('cpv_code'),
            tender.get('contact_person'),
            tender.get('contact_email'),
            tender.get('contact_phone'),
            tender.get('evaluation_method'),
            tender.get('payment_terms'),
            tender.get('delivery_location'),
            tender.get('has_lots'),
            tender.get('num_lots'),
            tender.get('num_bidders'),
            tender.get('highest_bid_mkd'),
            tender.get('lowest_bid_mkd'),
            tender.get('dossier_id'),
            tender.get('tender_uuid'),
            tender.get('source_url'),
            all_bidders_str,
            lots_data_str,
            raw_json_str,
            raw_data_json_str,
            tender['tender_id'],
        ))

        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        if result:
            with stats_lock:
                global_stats['tenders_updated'] += 1
            return True
        return False

    except Exception as e:
        logger.error(f"DB error updating {tender.get('tender_id')}: {e}")
        with stats_lock:
            global_stats['errors'] += 1
        return False


def worker_process_tenders(worker_id: int, tenders: List[Dict], headless: bool):
    """Worker function to process a batch of tenders."""
    logger.info(f"Worker {worker_id} starting: {len(tenders)} tenders to process")

    driver = None
    processed = 0

    try:
        driver = create_driver(headless)

        for i, tender_info in enumerate(tenders):
            try:
                url = tender_info['url']
                expected_id = tender_info.get('tender_id')

                logger.debug(f"Worker {worker_id}: Processing {i+1}/{len(tenders)} - {expected_id}")

                tender = extract_tender(driver, url, expected_id)
                if tender:
                    tid = tender.get('tender_id', 'UNKNOWN')
                    logger.info(f"Worker {worker_id}: Extracted {tid}")
                    if update_tender(tender):
                        processed += 1
                        logger.info(f"Worker {worker_id}: Updated {tid}")
                    else:
                        logger.warning(f"Worker {worker_id}: Update failed for {tid}")
                else:
                    logger.warning(f"Worker {worker_id}: Extraction failed for {expected_id} at {url[:60]}...")

                with stats_lock:
                    global_stats['tenders_processed'] += 1

                # Log every tender for debugging
                logger.info(f"Worker {worker_id}: Progress {i+1}/{len(tenders)} - updated {processed}")

                time.sleep(0.3)  # Small delay

            except Exception as e:
                logger.error(f"Worker {worker_id} error on {tender_info.get('url')}: {e}")
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

    logger.info(f"Worker {worker_id} finished: {processed}/{len(tenders)} updated")


def main():
    parser = argparse.ArgumentParser(description='Direct URL Selenium Scraper')
    parser.add_argument('--workers', type=int, default=50, help='Number of parallel workers (default: 50)')
    parser.add_argument('--stagger', type=float, default=10, help='Seconds between worker launches (default: 10)')
    parser.add_argument('--limit', type=int, default=1000, help='Maximum tenders to scrape')
    parser.add_argument('--year', type=int, help='Filter by tender year')
    parser.add_argument('--tender-ids', help='Comma-separated list of tender IDs')
    parser.add_argument('--all', action='store_true', help='Scrape all tenders, not just missing fields')
    parser.add_argument('--no-headless', action='store_true', help='Run with visible browsers')

    args = parser.parse_args()

    headless = not args.no_headless
    num_workers = args.workers

    logger.info(f"Starting direct URL scrape: {num_workers} workers")
    logger.info(f"Headless: {headless}, Limit: {args.limit}, Year: {args.year}")

    start_time = time.time()

    # Get tenders to scrape
    tender_ids = args.tender_ids.split(',') if args.tender_ids else None
    tenders = get_tenders_to_scrape(
        limit=args.limit,
        year=args.year,
        missing_fields=not args.all,
        tender_ids=tender_ids
    )

    if not tenders:
        logger.info("No tenders to scrape!")
        return

    # Split among workers - use min of workers and tenders
    actual_workers = min(num_workers, len(tenders))
    tenders_per_worker = max(1, len(tenders) // actual_workers)
    batches = []
    for i in range(actual_workers):
        start_idx = i * tenders_per_worker
        if i == actual_workers - 1:
            batch = tenders[start_idx:]  # Last worker gets remainder
        else:
            batch = tenders[start_idx:start_idx + tenders_per_worker]
        if batch:
            batches.append(batch)

    logger.info(f"Processing {len(tenders)} tenders with {actual_workers} workers...")
    logger.info(f"Staggered launch: {args.stagger}s delay between workers")

    # Process in parallel with staggered launch
    with ThreadPoolExecutor(max_workers=actual_workers, thread_name_prefix='Worker') as executor:
        futures = []
        for i, batch in enumerate(batches):
            if batch:
                # Stagger worker launches to avoid overwhelming the system
                if i > 0 and args.stagger > 0:
                    time.sleep(args.stagger)
                logger.info(f"Launching worker {i+1}/{len(batches)} with {len(batch)} tenders")
                future = executor.submit(worker_process_tenders, i + 1, batch, headless)
                futures.append(future)

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Worker failed: {e}")

    total_time = time.time() - start_time

    logger.info("=" * 60)
    logger.info("DIRECT SCRAPE COMPLETE")
    logger.info(f"Workers: {num_workers}")
    logger.info(f"Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    logger.info(f"Tenders processed: {global_stats['tenders_processed']}")
    logger.info(f"Tenders updated: {global_stats['tenders_updated']}")
    logger.info(f"Errors: {global_stats['errors']}")
    if total_time > 0 and global_stats['tenders_updated'] > 0:
        rate = global_stats['tenders_updated'] / (total_time / 60)
        logger.info(f"Rate: {rate:.1f} tenders/min")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()

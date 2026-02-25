#!/usr/bin/env python3
"""
Simple Authenticated Document Downloader using Selenium

This script:
1. Authenticates using Selenium (more reliable than Playwright in some environments)
2. Saves cookies
3. Downloads documents using requests with saved cookies
"""

import os
import sys
import json
import hashlib
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
COOKIE_FILE = Path('/tmp/nabavki_auth_cookies.json')
SESSION_FILE = Path('/tmp/nabavki_auth_session.json')
FILES_STORE = Path(os.environ.get('FILES_STORE', '/Users/tamsar/Downloads/nabavkidata/scraper/downloads/files'))
FILES_STORE.mkdir(parents=True, exist_ok=True)

# Load credentials from .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

NABAVKI_USERNAME = os.environ.get('NABAVKI_USERNAME')
NABAVKI_PASSWORD = os.environ.get('NABAVKI_PASSWORD')

# Database connection
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'user': os.environ.get('DB_USER', 'nabavki_user'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'dbname': os.environ.get('DB_NAME', 'nabavkidata'),
}


def load_saved_cookies() -> dict:
    """Load saved cookies if they exist and are not expired"""
    try:
        if COOKIE_FILE.exists() and SESSION_FILE.exists():
            with open(SESSION_FILE, 'r') as f:
                session_data = json.load(f)

            login_time = datetime.fromisoformat(session_data.get('login_time', '2000-01-01'))
            expiry_time = login_time + timedelta(hours=4)

            if datetime.utcnow() < expiry_time:
                with open(COOKIE_FILE, 'r') as f:
                    cookies = json.load(f)
                logger.info(f"Loaded {len(cookies)} cookies (valid until {expiry_time})")
                return {c['name']: c['value'] for c in cookies}
            else:
                logger.info("Saved cookies expired")
    except Exception as e:
        logger.warning(f"Could not load cookies: {e}")
    return {}


def save_cookies(cookies: list):
    """Save cookies to file"""
    try:
        login_time = datetime.utcnow()

        with open(COOKIE_FILE, 'w') as f:
            json.dump(cookies, f, indent=2)

        session_data = {
            'login_time': login_time.isoformat(),
            'username': NABAVKI_USERNAME,
            'cookie_count': len(cookies),
        }
        with open(SESSION_FILE, 'w') as f:
            json.dump(session_data, f, indent=2)

        logger.info(f"Saved {len(cookies)} cookies")
    except Exception as e:
        logger.error(f"Could not save cookies: {e}")


def authenticate_with_selenium() -> dict:
    """Authenticate using Selenium and return cookies"""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.action_chains import ActionChains
    except ImportError:
        logger.error("Selenium not installed. Run: pip install selenium")
        return {}

    logger.info("Authenticating with Selenium...")

    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 30)

        logger.info("Navigating to e-nabavki.gov.mk...")
        driver.get('https://e-nabavki.gov.mk/PublicAccess/home.aspx#/home')

        # Wait for Angular app to load
        time.sleep(8)

        # Wait for login form to be visible
        logger.info("Waiting for login form...")

        # Try multiple selectors for username field
        username_selectors = [
            (By.CSS_SELECTOR, 'input[placeholder*="Корисничко"]'),
            (By.CSS_SELECTOR, 'input[ng-model*="userName"]'),
            (By.CSS_SELECTOR, 'input.form-control[type="text"]'),
            (By.XPATH, '//input[@type="text"]'),
        ]

        username_field = None
        for selector_type, selector in username_selectors:
            try:
                elements = driver.find_elements(selector_type, selector)
                for elem in elements:
                    if elem.is_displayed() and elem.is_enabled():
                        username_field = elem
                        logger.info(f"Found username field: {selector}")
                        break
                if username_field:
                    break
            except:
                continue

        if not username_field:
            # Try scrolling and waiting more
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(3)

            # Last resort - find any text input
            inputs = driver.find_elements(By.CSS_SELECTOR, 'input')
            for inp in inputs:
                try:
                    if inp.is_displayed() and inp.get_attribute('type') in ['text', '']:
                        username_field = inp
                        logger.info("Found username field via generic search")
                        break
                except:
                    continue

        if not username_field:
            logger.error("Could not find username field")
            # Save page source for debugging
            with open('/tmp/nabavki_page.html', 'w') as f:
                f.write(driver.page_source)
            logger.info("Saved page source to /tmp/nabavki_page.html for debugging")
            if driver:
                driver.quit()
            return {}

        # Clear and fill username
        username_field.clear()
        time.sleep(0.5)
        username_field.send_keys(NABAVKI_USERNAME)
        logger.info("Filled username")

        # Find password field
        try:
            password_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="password"]')))
            password_field.clear()
            time.sleep(0.5)
            password_field.send_keys(NABAVKI_PASSWORD)
            logger.info("Filled password")
        except Exception as e:
            logger.error(f"Could not find password field: {e}")
            if driver:
                driver.quit()
            return {}

        time.sleep(1)

        # Find and click login button
        button_selectors = [
            (By.XPATH, '//button[contains(text(), "Влез")]'),
            (By.XPATH, '//button[contains(text(), "Login")]'),
            (By.CSS_SELECTOR, 'button[type="submit"]'),
            (By.CSS_SELECTOR, 'input[type="submit"]'),
            (By.CSS_SELECTOR, 'button.btn-primary'),
        ]

        login_button = None
        for selector_type, selector in button_selectors:
            try:
                elements = driver.find_elements(selector_type, selector)
                for elem in elements:
                    if elem.is_displayed() and elem.is_enabled():
                        login_button = elem
                        logger.info(f"Found login button: {selector}")
                        break
                if login_button:
                    break
            except:
                continue

        if login_button:
            login_button.click()
            logger.info("Clicked login button")
        else:
            logger.error("Could not find login button")
            if driver:
                driver.quit()
            return {}

        # Wait for login to complete
        time.sleep(8)

        # Check if logged in
        page_source = driver.page_source.lower()
        if 'одјава' in page_source or 'logout' in page_source or NABAVKI_USERNAME.lower() in page_source:
            logger.info("✅ LOGIN SUCCESSFUL")

            # Get cookies
            selenium_cookies = driver.get_cookies()
            save_cookies(selenium_cookies)

            cookies_dict = {c['name']: c['value'] for c in selenium_cookies}
            driver.quit()
            return cookies_dict
        else:
            logger.error("❌ LOGIN FAILED - Could not verify login success")
            # Save page for debugging
            with open('/tmp/nabavki_after_login.html', 'w') as f:
                f.write(driver.page_source)
            logger.info("Saved post-login page to /tmp/nabavki_after_login.html")
            driver.quit()
            return {}

    except Exception as e:
        logger.error(f"Selenium error: {e}")
        import traceback
        traceback.print_exc()
        if driver:
            try:
                driver.quit()
            except:
                pass
        return {}


def is_html_content(content: bytes) -> bool:
    """Check if content is HTML (login page) instead of actual file"""
    if len(content) < 100:
        return True

    content_start = content[:500].lower()
    html_indicators = [b'<!doctype html', b'<html', b'<!doctype', b'<head', b'<body']

    if any(ind in content_start for ind in html_indicators):
        return True

    # Check for Macedonian login page text
    if b'\xd0\x9d\xd0\xb0\xd1\x98\xd0\xb0\xd0\xb2\xd0\xb8' in content:  # "Најави"
        return True

    return False


def get_pending_documents(conn, file_types=None, limit=None, redownload=False):
    """Get documents that need downloading"""
    conditions = ["file_url LIKE 'https://e-nabavki%'"]
    conditions.append("file_url NOT LIKE '%ohridskabanka%'")

    if redownload:
        # Include documents that may have been saved as HTML instead of real files
        # Files < 50KB are suspicious for Office docs
        conditions.append("""
            (extraction_status IN ('pending', 'download_failed', 'auth_required')
             OR (extraction_status = 'success' AND (file_size_bytes IS NULL OR file_size_bytes < 50000)))
        """)
    else:
        conditions.append("extraction_status IN ('pending', 'download_failed', 'auth_required')")

    if file_types:
        type_conditions = []
        for ft in file_types:
            type_conditions.append(f"LOWER(file_name) LIKE '%.{ft.lower()}'")
        conditions.append(f"({' OR '.join(type_conditions)})")

    query = f"""
        SELECT doc_id, tender_id, file_url, file_name, file_path
        FROM documents
        WHERE {' AND '.join(conditions)}
        ORDER BY
            CASE
                WHEN LOWER(file_name) LIKE '%.xlsx' THEN 1
                WHEN LOWER(file_name) LIKE '%.xls' THEN 2
                WHEN LOWER(file_name) LIKE '%.docx' THEN 3
                WHEN LOWER(file_name) LIKE '%.doc' THEN 4
                ELSE 5
            END
        {f'LIMIT {limit}' if limit else ''}
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        rows = cur.fetchall()

    logger.info(f"Found {len(rows)} documents to download")
    return rows


def download_document(session, doc, conn):
    """Download a single document"""
    doc_id = doc['doc_id']
    url = doc['file_url']
    file_name = doc['file_name']
    tender_id = doc['tender_id']

    # Generate local filename
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    ext = Path(file_name).suffix.lower() or '.pdf'
    safe_tender_id = str(tender_id).replace('/', '_').replace('\\', '_')
    local_filename = f"{safe_tender_id}_{url_hash}{ext}"
    local_path = FILES_STORE / local_filename

    try:
        response = session.get(url, timeout=300, stream=True)

        if response.status_code != 200:
            logger.warning(f"HTTP {response.status_code} for {file_name}")
            update_doc_status(conn, doc_id, 'download_failed')
            return False

        content = response.content

        # Check if we got HTML instead of file
        if is_html_content(content):
            logger.warning(f"Got HTML instead of file: {file_name}")
            update_doc_status(conn, doc_id, 'auth_required')
            return False

        # Save file
        with open(local_path, 'wb') as f:
            f.write(content)

        # Calculate hash
        file_hash = hashlib.sha256(content).hexdigest()

        # Update database
        update_doc_success(conn, doc_id, str(local_path), len(content), file_hash)

        logger.info(f"✅ Downloaded: {file_name} ({len(content):,} bytes)")
        return True

    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        update_doc_status(conn, doc_id, 'download_failed')
        return False


def update_doc_status(conn, doc_id, status):
    """Update document status"""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE documents
            SET extraction_status = %s
            WHERE doc_id = %s
        """, (status, doc_id))
    conn.commit()


def update_doc_success(conn, doc_id, file_path, file_size, file_hash):
    """Update document after successful download"""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE documents
            SET file_path = %s,
                file_size_bytes = %s,
                file_hash = %s,
                extraction_status = 'pending'
            WHERE doc_id = %s
        """, (file_path, file_size, file_hash, doc_id))
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description='Download documents with authentication')
    parser.add_argument('--file-type', '-t', action='append', dest='file_types',
                       help='File types to download (xlsx, docx, pdf). Can be used multiple times.')
    parser.add_argument('--limit', '-l', type=int, default=None,
                       help='Maximum documents to download')
    parser.add_argument('--redownload', '-r', action='store_true',
                       help='Re-download failed/HTML documents')

    args = parser.parse_args()

    # Load or get cookies
    cookies = load_saved_cookies()
    if not cookies:
        cookies = authenticate_with_selenium()
        if not cookies:
            logger.error("Authentication failed. Cannot proceed.")
            return

    # Create session with cookies
    session = requests.Session()
    for name, value in cookies.items():
        session.cookies.set(name, value, domain='e-nabavki.gov.mk')

    logger.info(f"Session initialized with {len(cookies)} cookies")

    # Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    logger.info("Database connected")

    try:
        # Get documents
        documents = get_pending_documents(
            conn,
            file_types=args.file_types,
            limit=args.limit,
            redownload=args.redownload
        )

        if not documents:
            logger.info("No documents to download")
            return

        # Download documents
        stats = {'downloaded': 0, 'failed': 0}

        for i, doc in enumerate(documents):
            if download_document(session, doc, conn):
                stats['downloaded'] += 1
            else:
                stats['failed'] += 1

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i+1}/{len(documents)} "
                           f"(Downloaded: {stats['downloaded']}, Failed: {stats['failed']})")

        # Summary
        logger.info("=" * 60)
        logger.info("DOWNLOAD COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total: {len(documents)}")
        logger.info(f"Downloaded: {stats['downloaded']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info("=" * 60)

    finally:
        conn.close()


if __name__ == '__main__':
    main()

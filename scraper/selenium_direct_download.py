#!/usr/bin/env python3
"""
Direct Selenium Download - Downloads files by navigating to URLs in the browser

This approach keeps the full session context instead of trying to transfer cookies to requests.
"""

import os
import sys
import json
import hashlib
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import shutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
FILES_STORE = Path(os.environ.get('FILES_STORE', '/Users/tamsar/Downloads/nabavkidata/scraper/downloads/files'))
FILES_STORE.mkdir(parents=True, exist_ok=True)

DOWNLOAD_DIR = Path('/tmp/nabavki_selenium_downloads')
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Load credentials from .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

NABAVKI_USERNAME = os.environ.get('NABAVKI_USERNAME')
NABAVKI_PASSWORD = os.environ.get('NABAVKI_PASSWORD')

# Database connection
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'user': os.environ.get('DB_USER', 'nabavki_user'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'dbname': os.environ.get('DB_NAME', 'nabavkidata'),
}


def clear_downloads():
    """Clear the downloads directory"""
    for f in DOWNLOAD_DIR.glob('*'):
        try:
            f.unlink()
        except:
            pass


def wait_for_download(timeout=120):
    """Wait for a download to complete and return the file path"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check for .crdownload files (Chrome downloading)
        downloading = list(DOWNLOAD_DIR.glob('*.crdownload'))

        # Check for completed files
        files = list(DOWNLOAD_DIR.glob('*'))
        completed_files = [f for f in files if not f.name.endswith('.crdownload')]

        if completed_files and not downloading:
            return completed_files[0]

        time.sleep(0.5)
    return None


def get_authenticated_driver():
    """Create and authenticate a Selenium driver with download settings"""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        logger.error("Selenium not installed. Run: pip install selenium")
        return None

    logger.info("Starting Selenium browser...")

    options = Options()
    # NOT headless - download works better in headed mode
    # But we can try headless with special settings
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')

    # Configure download settings
    prefs = {
        'download.default_directory': str(DOWNLOAD_DIR),
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
        'safebrowsing.enabled': False,
        'plugins.always_open_pdf_externally': True,
        'profile.default_content_settings.popups': 0,
        'profile.default_content_setting_values.automatic_downloads': 1,
    }
    options.add_experimental_option('prefs', prefs)

    driver = webdriver.Chrome(options=options)

    # Enable download in headless mode
    driver.execute_cdp_cmd('Page.setDownloadBehavior', {
        'behavior': 'allow',
        'downloadPath': str(DOWNLOAD_DIR)
    })

    wait = WebDriverWait(driver, 30)

    try:
        logger.info("Navigating to e-nabavki.gov.mk...")
        driver.get('https://e-nabavki.gov.mk/PublicAccess/home.aspx#/home')
        time.sleep(8)

        # Find and fill login form
        logger.info("Logging in...")

        username_selectors = [
            (By.CSS_SELECTOR, 'input[placeholder*="Корисничко"]'),
            (By.CSS_SELECTOR, 'input[ng-model*="userName"]'),
            (By.CSS_SELECTOR, 'input.form-control[type="text"]'),
        ]

        username_field = None
        for selector_type, selector in username_selectors:
            try:
                elements = driver.find_elements(selector_type, selector)
                for elem in elements:
                    if elem.is_displayed() and elem.is_enabled():
                        username_field = elem
                        break
                if username_field:
                    break
            except:
                continue

        if not username_field:
            logger.error("Could not find username field")
            return None

        username_field.clear()
        time.sleep(0.5)
        username_field.send_keys(NABAVKI_USERNAME)

        # Password
        password_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="password"]')))
        password_field.clear()
        time.sleep(0.5)
        password_field.send_keys(NABAVKI_PASSWORD)

        time.sleep(1)

        # Click login
        button_selectors = [
            (By.XPATH, '//button[contains(text(), "Влез")]'),
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
            return None

        time.sleep(8)

        # Verify login
        page_source = driver.page_source.lower()
        if 'одјава' in page_source or 'logout' in page_source:
            logger.info("✅ LOGIN SUCCESSFUL")
            return driver
        else:
            logger.error("❌ LOGIN FAILED")
            return None

    except Exception as e:
        logger.error(f"Error during authentication: {e}")
        import traceback
        traceback.print_exc()
        if driver:
            driver.quit()
        return None


def is_html_content(content: bytes) -> bool:
    """Check if content is HTML (login page)"""
    if len(content) < 100:
        return True

    # Try brotli decompression
    try:
        import brotli
        content = brotli.decompress(content)
    except:
        pass

    content_start = content[:500].lower()
    html_indicators = [b'<!doctype html', b'<html', b'<!doctype', b'<head', b'<body']

    if any(ind in content_start for ind in html_indicators):
        return True

    return False


def download_with_selenium(driver, doc, conn):
    """Download a document using Selenium directly"""
    doc_id = doc['doc_id']
    url = doc['file_url']
    file_name = doc['file_name']
    tender_id = doc['tender_id']

    clear_downloads()

    try:
        logger.info(f"Downloading: {file_name}")

        # Use JavaScript to trigger download
        # This keeps the session context
        driver.execute_script(f'window.location.href = "{url}";')

        # Wait for download
        time.sleep(3)
        downloaded_file = wait_for_download(timeout=120)

        if not downloaded_file:
            logger.warning(f"Download timeout: {file_name}")
            update_doc_status(conn, doc_id, 'download_timeout')
            return False

        # Read file content
        content = downloaded_file.read_bytes()

        # Check if it's HTML
        if is_html_content(content):
            logger.warning(f"Got HTML instead of file: {file_name}")
            update_doc_status(conn, doc_id, 'auth_required')
            downloaded_file.unlink()
            return False

        # Generate local filename
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        ext = Path(file_name).suffix.lower() or downloaded_file.suffix.lower() or '.bin'
        safe_tender_id = str(tender_id).replace('/', '_').replace('\\', '_')
        local_filename = f"{safe_tender_id}_{url_hash}{ext}"
        local_path = FILES_STORE / local_filename

        # Move file to final location
        shutil.move(str(downloaded_file), str(local_path))

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


def get_pending_documents(conn, file_types=None, limit=None):
    """Get documents that need downloading"""
    conditions = ["file_url LIKE 'https://e-nabavki%'"]
    conditions.append("file_url NOT LIKE '%ohridskabanka%'")
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
    parser = argparse.ArgumentParser(description='Download documents with Selenium directly')
    parser.add_argument('--file-type', '-t', action='append', dest='file_types',
                       help='File types to download (xlsx, docx, pdf). Can be used multiple times.')
    parser.add_argument('--limit', '-l', type=int, default=None,
                       help='Maximum documents to download')

    args = parser.parse_args()

    # Get authenticated driver
    driver = get_authenticated_driver()
    if not driver:
        logger.error("Could not authenticate. Exiting.")
        return

    # Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    logger.info("Database connected")

    try:
        # Get documents
        documents = get_pending_documents(
            conn,
            file_types=args.file_types,
            limit=args.limit
        )

        if not documents:
            logger.info("No documents to download")
            return

        # Download documents
        stats = {'downloaded': 0, 'failed': 0}

        for i, doc in enumerate(documents):
            if download_with_selenium(driver, doc, conn):
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
        driver.quit()
        conn.close()


if __name__ == '__main__':
    main()

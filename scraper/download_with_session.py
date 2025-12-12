#!/usr/bin/env python3
"""
Download documents using Selenium-extracted session with requests

This script extracts the full session state from Selenium (cookies + headers)
and uses them with requests for faster downloads.
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
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
FILES_STORE = Path(os.environ.get('FILES_STORE', '/Users/tamsar/Downloads/nabavkidata/scraper/downloads/files'))
FILES_STORE.mkdir(parents=True, exist_ok=True)

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
    'password': os.environ.get('DB_PASSWORD', '9fagrPSDfQqBjrKZZLVrJY2Am'),
    'dbname': os.environ.get('DB_NAME', 'nabavkidata'),
}


def get_session_from_selenium():
    """Authenticate with Selenium and extract full session state"""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        logger.error("Selenium not installed. Run: pip install selenium")
        return None

    logger.info("Starting Selenium authentication...")

    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')

    driver = webdriver.Chrome(options=options)
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
        else:
            logger.error("❌ LOGIN FAILED")
            return None

        # Create requests session with Selenium cookies
        session = requests.Session()

        # Copy cookies
        for cookie in driver.get_cookies():
            session.cookies.set(
                cookie['name'],
                cookie['value'],
                domain=cookie.get('domain', 'e-nabavki.gov.mk'),
                path=cookie.get('path', '/')
            )
            logger.debug(f"Added cookie: {cookie['name']}")

        # Set headers to match browser
        session.headers.update({
            'User-Agent': driver.execute_script("return navigator.userAgent"),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,mk;q=0.8',
            'Accept-Encoding': 'gzip, deflate',  # Avoid brotli to get uncompressed files
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
        })

        # Now make a request to a protected page to verify session works
        logger.info("Verifying session with requests...")
        test_url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx'
        test_response = session.get(test_url, timeout=30)

        if test_response.status_code == 200 and 'одјава' in test_response.text.lower():
            logger.info("✅ Session verified with requests")
        else:
            logger.warning("Session may not be fully authenticated")

        return session

    except Exception as e:
        logger.error(f"Error during authentication: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        driver.quit()


def decompress_if_needed(content: bytes) -> bytes:
    """Try to decompress content if it's brotli/gzip compressed"""
    # Try brotli first (common for web)
    try:
        import brotli
        decompressed = brotli.decompress(content)
        return decompressed
    except:
        pass

    # Try gzip
    try:
        import gzip
        decompressed = gzip.decompress(content)
        return decompressed
    except:
        pass

    # Try deflate
    try:
        import zlib
        decompressed = zlib.decompress(content, -zlib.MAX_WBITS)
        return decompressed
    except:
        pass

    return content


def is_html_content(content: bytes) -> bool:
    """Check if content is HTML (login page) instead of actual file"""
    if len(content) < 100:
        return True

    # First decompress if needed
    decompressed = decompress_if_needed(content)

    content_start = decompressed[:500].lower()
    html_indicators = [b'<!doctype html', b'<html', b'<!doctype', b'<head', b'<body']

    if any(ind in content_start for ind in html_indicators):
        return True

    return False


def get_pending_documents(conn, file_types=None, limit=None, redownload=False):
    """Get documents that need downloading"""
    conditions = ["file_url LIKE 'https://e-nabavki%'"]
    conditions.append("file_url NOT LIKE '%ohridskabanka%'")

    if redownload:
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
        # Set referer for this specific request
        headers = {
            'Referer': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx',
        }

        response = session.get(url, timeout=300, headers=headers, allow_redirects=True)

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
    parser = argparse.ArgumentParser(description='Download documents with authenticated session')
    parser.add_argument('--file-type', '-t', action='append', dest='file_types',
                       help='File types to download (xlsx, docx, pdf). Can be used multiple times.')
    parser.add_argument('--limit', '-l', type=int, default=None,
                       help='Maximum documents to download')
    parser.add_argument('--redownload', '-r', action='store_true',
                       help='Re-download failed/HTML documents')

    args = parser.parse_args()

    # Get authenticated session
    session = get_session_from_selenium()
    if not session:
        logger.error("Could not get authenticated session. Exiting.")
        return

    logger.info(f"Session has {len(session.cookies)} cookies")

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

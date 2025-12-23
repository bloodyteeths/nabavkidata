#!/usr/bin/env python3
"""
E-Pazar Evaluation Report PDF Extractor

Extracts structured data from e-pazar evaluationReport.pdf files using PyMuPDF.
Falls back to Gemini AI for failed extractions.

Usage:
    python epazar_evaluation_extractor.py --limit 10
    python epazar_evaluation_extractor.py --tender-id EPAZAR-982
    python epazar_evaluation_extractor.py --retry-failed
"""

import argparse
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import hashlib

import fitz  # PyMuPDF
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com'),
    'database': os.getenv('DB_NAME', 'nabavkidata'),
    'user': os.getenv('DB_USER', 'nabavki_user'),
    'password': os.getenv('DB_PASSWORD', '9fagrPSDfQqBjrKZZLVrJY2Am'),
    'port': os.getenv('DB_PORT', '5432')
}

# E-Pazar base URL
EPAZAR_BASE_URL = "https://e-pazar.gov.mk"


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def download_pdf(url: str, timeout: int = 30) -> Optional[bytes]:
    """Download PDF from URL."""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Failed to download PDF from {url}: {e}")
        return None


def parse_european_number(value: str) -> Optional[float]:
    """Parse European-style numbers like 2.100,00 or 2100.00"""
    if not value:
        return None
    s = str(value).strip()
    # Remove currency symbols and whitespace
    s = re.sub(r'[МКД€$\s]', '', s)
    if not s:
        return None
    # European format: 2.100,00 -> 2100.00
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    # Just comma as decimal: 2100,00 -> 2100.00
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return None


def parse_brands(brands_text: str) -> List[str]:
    """Parse brands from text like 'Fairy,Gloss' or 'Ariel, Persil'."""
    if not brands_text:
        return []
    # Split by comma, clean each brand
    brands = [b.strip() for b in brands_text.split(',')]
    return [b for b in brands if b and b != '/']


def extract_text_from_pdf(pdf_content: bytes) -> Tuple[str, int]:
    """Extract all text from PDF and return (text, page_count)."""
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        page_count = len(doc)
        doc.close()
        return "\n".join(text_parts), page_count
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        return "", 0


def extract_tables_from_pdf(pdf_content: bytes) -> List[List[List[str]]]:
    """Extract tables from PDF using PyMuPDF."""
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        all_tables = []
        for page in doc:
            tables = page.find_tables()
            for table in tables:
                extracted = table.extract()
                if extracted:
                    all_tables.append(extracted)
        doc.close()
        return all_tables
    except Exception as e:
        logger.error(f"Failed to extract tables from PDF: {e}")
        return []


def parse_evaluation_report(pdf_content: bytes) -> Dict[str, Any]:
    """
    Parse evaluation report PDF and extract all structured data.

    Returns dict with:
    - header: tender info
    - bidders: list of all bidders
    - items: list of per-item evaluation data
    - rejected: rejected offers info
    - signatures: commission/responsible person
    - raw_text: full text
    """
    result = {
        'header': {},
        'bidders': [],
        'items': [],
        'rejected_offers': [],
        'rejected_bidders': [],
        'cancelled_parts': [],
        'parts_without_offers': [],
        'signatures': {},
        'raw_text': '',
        'extraction_method': 'pymupdf',
        'extraction_status': 'pending',
        'extraction_confidence': 0.0
    }

    # Extract full text
    raw_text, page_count = extract_text_from_pdf(pdf_content)
    result['raw_text'] = raw_text
    result['page_count'] = page_count

    if not raw_text:
        result['extraction_status'] = 'failed'
        result['extraction_error'] = 'Could not extract text from PDF'
        return result

    # Extract tables
    tables = extract_tables_from_pdf(pdf_content)

    # Parse header info
    result['header'] = parse_header(raw_text)

    # Parse bidders list
    result['bidders'] = parse_bidders(raw_text)

    # Parse main items table
    result['items'] = parse_items_table(tables, raw_text)

    # Parse rejected/cancelled sections
    result['rejected_offers'] = parse_section(raw_text, 'Отфрлени понуди')
    result['rejected_bidders'] = parse_section(raw_text, 'Одбиени понудувачи')
    result['cancelled_parts'] = parse_section(raw_text, 'Поништени делови')
    result['parts_without_offers'] = parse_section(raw_text, 'Делови за кои нема понуда')

    # Parse signatures
    result['signatures'] = parse_signatures(raw_text)

    # Calculate confidence
    if result['items']:
        # Check completeness of items
        complete_items = sum(1 for item in result['items']
                          if item.get('unit_price') and item.get('winner_name'))
        result['extraction_confidence'] = complete_items / len(result['items'])
        result['extraction_status'] = 'success' if result['extraction_confidence'] > 0.5 else 'partial'
    else:
        result['extraction_status'] = 'failed'
        result['extraction_error'] = 'No items extracted from table'

    return result


def parse_header(text: str) -> Dict[str, Any]:
    """Extract header information from text."""
    header = {}

    # Tender number pattern: M00425/2025
    tender_match = re.search(r'([A-Z]?\d{4,6}/\d{4})', text)
    if tender_match:
        header['tender_number'] = tender_match.group(1)

    # Publication date
    date_match = re.search(r'објавена на (\d{1,2}\.\d{1,2}\.\d{4})', text)
    if date_match:
        header['publication_date'] = date_match.group(1)

    # Contracting authority - usually after "од страна на"
    authority_match = re.search(r'од страна на ([^,]+)', text)
    if authority_match:
        header['contracting_authority'] = authority_match.group(1).strip()

    # Tender type
    if 'Стоки' in text:
        header['tender_type'] = 'Стоки'
    elif 'Услуги' in text:
        header['tender_type'] = 'Услуги'
    elif 'Работи' in text:
        header['tender_type'] = 'Работи'

    # Subject - after "предмет:"
    subject_match = re.search(r'предмет:\s*([^\n]+)', text, re.IGNORECASE)
    if subject_match:
        header['tender_subject'] = subject_match.group(1).strip()

    return header


def parse_bidders(text: str) -> List[str]:
    """Extract list of bidders from text."""
    bidders = []

    # Pattern: "понуди доставија следните понудувачи:" followed by list
    bidders_section = re.search(
        r'понуди доставија[\s\S]*?следните понудувачи:\s*([\s\S]*?)(?=Комисија|Избрани понуди|$)',
        text, re.IGNORECASE
    )

    if bidders_section:
        section_text = bidders_section.group(1)
        # Find lines starting with "-" or "•"
        lines = re.findall(r'[-•]\s*(.+?)(?=\n|$)', section_text)
        for line in lines:
            bidder = line.strip()
            if bidder and len(bidder) > 5:  # Filter out short noise
                bidders.append(bidder)

    return bidders


def parse_items_table(tables: List[List[List[str]]], raw_text: str) -> List[Dict[str, Any]]:
    """Parse the main items evaluation table."""
    # PyMuPDF table extraction often fails with complex e-pazar PDFs
    # Use text-based parsing which is more reliable for this format
    return parse_items_from_text(raw_text)


def parse_table_row(row: List[str]) -> Optional[Dict[str, Any]]:
    """Parse a single table row into item data."""
    if not row or len(row) < 5:
        return None

    # Clean cells
    cells = [str(cell).strip() if cell else '' for cell in row]

    item = {}

    # Try to identify columns by content
    for i, cell in enumerate(cells):
        if not cell:
            continue

        # Line number (first numeric cell)
        if not item.get('line_number') and cell.isdigit():
            item['line_number'] = int(cell)

        # Unit price (numeric with decimal)
        if re.match(r'^[\d.,]+$', cell) and (',' in cell or '.' in cell):
            value = parse_european_number(cell)
            if value:
                if not item.get('unit_price'):
                    item['unit_price'] = value
                elif not item.get('total_price'):
                    item['total_price'] = value

        # Quantity (integer in specific position)
        if cell.isdigit() and int(cell) < 10000:
            if not item.get('quantity') and item.get('line_number'):
                item['quantity'] = int(cell)

        # Unit (known units)
        if cell.lower() in ['парче', 'литар', 'килограм', 'пакување', 'метар', 'сет', 'кутија']:
            item['unit'] = cell

        # Brand detection (short text without spaces, not a number)
        if len(cell) > 2 and len(cell) < 50 and not cell.isdigit():
            if ',' in cell:
                # Multiple brands
                if not item.get('required_brands_raw'):
                    item['required_brands_raw'] = cell
                    item['required_brands'] = parse_brands(cell)
            elif not item.get('offered_brand') and item.get('required_brands'):
                # Single brand after required brands = offered brand
                item['offered_brand'] = cell

    # Try to get item name and winner from longer text cells
    for cell in cells:
        if len(cell) > 50:
            if 'ДООЕЛ' in cell or 'ДОО' in cell or 'АД' in cell:
                item['winner_name'] = cell
            elif not item.get('item_subject'):
                item['item_subject'] = cell

    return item if item.get('line_number') else None


def parse_items_from_text(text: str) -> List[Dict[str, Any]]:
    """Parse items from raw text - handles line-by-line PDF extraction."""
    items = []
    lines = text.split('\n')

    # Known units
    UNITS = ['литар', 'литри', 'парче', 'килограм', 'пакување', 'метар', 'сет', 'кутија', 'kg', 'л.', 'м.']

    # Company suffixes that indicate winner name
    COMPANY_SUFFIXES = ['ДООЕЛ', 'ДОО', 'АД', 'ДООЕЛ увоз-извоз', 'експорт импорт']

    current_item = None
    item_text_buffer = []
    found_line_numbers = set()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Check if this is a line number (start of new item)
        if line.isdigit() and int(line) < 100:
            line_num = int(line)

            # Save previous item if exists
            if current_item and current_item.get('line_number'):
                items.append(current_item)

            # Check if this is a new item (not already processed)
            if line_num not in found_line_numbers:
                found_line_numbers.add(line_num)
                current_item = {'line_number': line_num}
                item_text_buffer = []
            i += 1
            continue

        # If we're in an item, collect data
        if current_item is not None:
            # Check for brands (comma-separated, short text)
            if ',' in line and len(line) < 100 and not any(c.isdigit() for c in line.replace(',', '')):
                brands = parse_brands(line)
                if brands:
                    if not current_item.get('required_brands'):
                        current_item['required_brands'] = brands
                        current_item['required_brands_raw'] = line
                    i += 1
                    continue

            # Check for unit (known unit words)
            line_lower = line.lower()
            for unit in UNITS:
                if line_lower == unit or line_lower.startswith(unit):
                    current_item['unit'] = line
                    i += 1
                    continue

            # Check for quantity (pure integer, reasonable range)
            if line.isdigit() and 1 <= int(line) <= 10000:
                if not current_item.get('quantity'):
                    current_item['quantity'] = int(line)
                i += 1
                continue

            # Check for prices (decimal numbers like 74,98 or 4.498,80)
            price_match = re.match(r'^([\d.,]+)(?:\s+(.+))?$', line)
            if price_match:
                price_str = price_match.group(1)
                rest = price_match.group(2)

                # Check if it's a valid price format
                if ',' in price_str or (price_str.replace('.', '').replace(',', '').isdigit()):
                    price = parse_european_number(price_str)
                    if price and price > 0:
                        if not current_item.get('unit_price'):
                            current_item['unit_price'] = price
                        elif not current_item.get('total_price'):
                            current_item['total_price'] = price
                            # Rest might be winner name start
                            if rest:
                                current_item['winner_name'] = rest

            # Check for winner name (company suffixes)
            for suffix in COMPANY_SUFFIXES:
                if suffix in line:
                    # This line contains winner name - collect it
                    if current_item.get('winner_name'):
                        current_item['winner_name'] += ' ' + line
                    else:
                        current_item['winner_name'] = line
                    i += 1
                    continue

            # Check for offered brand (single word after required brands, before prices)
            if (current_item.get('required_brands') and
                not current_item.get('offered_brand') and
                not current_item.get('unit_price') and
                len(line) < 50 and
                not line.startswith('Опис') and
                not line.startswith('Карактеристики') and
                '/' not in line):
                # Could be offered brand
                if not any(c.isdigit() for c in line):
                    current_item['offered_brand'] = line

            # Collect text for item description
            if not current_item.get('item_subject') and len(line) > 3:
                item_text_buffer.append(line)
                if len(item_text_buffer) <= 4:
                    current_item['item_subject'] = ' '.join(item_text_buffer)

        i += 1

    # Don't forget last item
    if current_item and current_item.get('line_number'):
        items.append(current_item)

    # Clean up winner names (remove line breaks, extra spaces)
    for item in items:
        if item.get('winner_name'):
            item['winner_name'] = ' '.join(item['winner_name'].split())

    return items


def parse_section(text: str, section_name: str) -> List[str]:
    """Parse a specific section (rejected offers, etc.)."""
    results = []

    # Find section
    pattern = rf'{section_name}[\s\S]*?(?:/|$)'
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        section_text = match.group(0)
        if section_text.strip() == '/' or section_text.strip() == section_name:
            return []
        results.append(section_text.strip())

    return results


def parse_signatures(text: str) -> Dict[str, Any]:
    """Extract signature information."""
    signatures = {
        'commission': [],
        'responsible_person': None
    }

    # Digital signature pattern
    sig_pattern = re.compile(
        r'Digitally signed by ([^\n]+)\s*Date: ([\d.:\s+]+)',
        re.IGNORECASE
    )

    for match in sig_pattern.finditer(text):
        sig = {
            'name': match.group(1).strip(),
            'signed_at': match.group(2).strip()
        }
        signatures['commission'].append(sig)

    # Responsible person
    resp_match = re.search(r'Одговорно лице[:\s]*([^\n]+)', text)
    if resp_match:
        signatures['responsible_person'] = resp_match.group(1).strip()

    return signatures


def find_evaluation_report_url(tender_id: str, conn) -> Optional[str]:
    """Find or construct evaluation report URL for a tender."""
    # Extract numeric ID from EPAZAR-XXX format
    match = re.search(r'EPAZAR-(\d+)', tender_id)
    if not match:
        return None

    numeric_id = match.group(1)

    # Try to find in documents table first
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT file_url FROM epazar_documents
            WHERE tender_id = %s AND doc_type = 'evaluation_report'
            LIMIT 1
        """, (tender_id,))
        row = cur.fetchone()
        if row and row['file_url']:
            return row['file_url']

    # Construct URL pattern - need to discover the actual URL
    # Pattern: https://e-pazar.gov.mk/Files/{something}/2/{date}_evaluationReport.pdf
    # We'll need to scrape the tender page to find the actual URL

    return None


def discover_evaluation_urls(conn, limit: int = 100) -> List[Dict[str, str]]:
    """
    Discover evaluation report URLs from finished tenders.
    Scrapes e-pazar.gov.mk/finishedTenders to find PDF links.
    """
    discovered = []

    # Get finished tenders from our database
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT t.tender_id, t.source_url, t.status
            FROM epazar_tenders t
            LEFT JOIN epazar_evaluation_reports r ON t.tender_id = r.tender_id
            WHERE t.status IN ('signed', 'completed', 'awarded')
            AND r.report_id IS NULL
            AND t.evaluation_report_extracted IS NOT TRUE
            ORDER BY t.updated_at DESC
            LIMIT %s
        """, (limit,))
        tenders = cur.fetchall()

    for tender in tenders:
        tender_id = tender['tender_id']
        source_url = tender['source_url']

        if not source_url:
            continue

        # Try to fetch tender page and find evaluation report link
        try:
            response = requests.get(source_url, timeout=15)
            if response.status_code == 200:
                # Look for evaluationReport.pdf link
                pdf_match = re.search(
                    r'href=["\']([^"\']*evaluationReport\.pdf)["\']',
                    response.text,
                    re.IGNORECASE
                )
                if pdf_match:
                    pdf_url = pdf_match.group(1)
                    if not pdf_url.startswith('http'):
                        pdf_url = EPAZAR_BASE_URL + pdf_url
                    discovered.append({
                        'tender_id': tender_id,
                        'pdf_url': pdf_url
                    })
                    logger.info(f"Found evaluation report for {tender_id}: {pdf_url}")
        except Exception as e:
            logger.warning(f"Failed to check {tender_id}: {e}")

    return discovered


def save_extraction_results(conn, tender_id: str, pdf_url: str,
                           extraction: Dict[str, Any]) -> bool:
    """Save extraction results to database."""
    try:
        with conn.cursor() as cur:
            # 1. Insert into epazar_evaluation_reports
            report_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO epazar_evaluation_reports (
                    report_id, tender_id, pdf_url, pdf_filename,
                    tender_number, contracting_authority, tender_type, tender_subject,
                    bidders_list, rejected_offers, rejected_bidders,
                    cancelled_parts, parts_without_offers,
                    commission_members, responsible_person,
                    raw_text, raw_json,
                    extraction_method, extraction_status, extraction_error,
                    extraction_confidence, page_count
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (tender_id) DO UPDATE SET
                    pdf_url = EXCLUDED.pdf_url,
                    raw_text = EXCLUDED.raw_text,
                    raw_json = EXCLUDED.raw_json,
                    extraction_method = EXCLUDED.extraction_method,
                    extraction_status = EXCLUDED.extraction_status,
                    extraction_error = EXCLUDED.extraction_error,
                    extraction_confidence = EXCLUDED.extraction_confidence,
                    updated_at = NOW()
            """, (
                report_id, tender_id, pdf_url,
                pdf_url.split('/')[-1] if pdf_url else None,
                extraction['header'].get('tender_number'),
                extraction['header'].get('contracting_authority'),
                extraction['header'].get('tender_type'),
                extraction['header'].get('tender_subject'),
                extraction.get('bidders', []),
                Json(extraction.get('rejected_offers', [])),
                Json(extraction.get('rejected_bidders', [])),
                Json(extraction.get('cancelled_parts', [])),
                Json(extraction.get('parts_without_offers', [])),
                Json(extraction['signatures'].get('commission', [])),
                Json({'name': extraction['signatures'].get('responsible_person')}),
                extraction.get('raw_text', ''),
                Json(extraction),
                extraction.get('extraction_method', 'pymupdf'),
                extraction.get('extraction_status', 'pending'),
                extraction.get('extraction_error'),
                extraction.get('extraction_confidence', 0),
                extraction.get('page_count', 0)
            ))

            # 2. Insert item evaluations
            for item in extraction.get('items', []):
                cur.execute("""
                    INSERT INTO epazar_item_evaluations (
                        report_id, tender_id, line_number,
                        item_subject, product_name,
                        required_brands, required_brands_raw, required_specs_raw,
                        offered_brand, offered_specs_raw,
                        unit, quantity, unit_price_without_vat, total_without_vat,
                        winner_name, raw_row_data
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (tender_id, line_number) DO UPDATE SET
                        offered_brand = EXCLUDED.offered_brand,
                        unit_price_without_vat = EXCLUDED.unit_price_without_vat,
                        winner_name = EXCLUDED.winner_name,
                        raw_row_data = EXCLUDED.raw_row_data
                """, (
                    report_id, tender_id, item.get('line_number'),
                    item.get('item_subject'), item.get('product_name'),
                    item.get('required_brands', []), item.get('required_brands_raw'),
                    item.get('required_specs_raw'),
                    item.get('offered_brand'), item.get('offered_specs_raw'),
                    item.get('unit'), item.get('quantity'),
                    item.get('unit_price'), item.get('total_price'),
                    item.get('winner_name'),
                    Json(item)
                ))

            # 3. Insert bidders
            for bidder in extraction.get('bidders', []):
                cur.execute("""
                    INSERT INTO epazar_bidders (tender_id, bidder_name)
                    VALUES (%s, %s)
                    ON CONFLICT (tender_id, bidder_name) DO NOTHING
                """, (tender_id, bidder))

            # 4. Update tender status
            cur.execute("""
                UPDATE epazar_tenders SET
                    has_evaluation_report = TRUE,
                    evaluation_report_url = %s,
                    evaluation_report_extracted = TRUE,
                    evaluation_extraction_status = %s
                WHERE tender_id = %s
            """, (pdf_url, extraction.get('extraction_status'), tender_id))

            conn.commit()
            return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to save extraction for {tender_id}: {e}")
        return False


def process_tender(conn, tender_id: str, pdf_url: str) -> Dict[str, Any]:
    """Process a single tender's evaluation report."""
    result = {
        'tender_id': tender_id,
        'status': 'pending',
        'items_extracted': 0,
        'error': None
    }

    # Download PDF
    logger.info(f"Downloading PDF for {tender_id}: {pdf_url}")
    pdf_content = download_pdf(pdf_url)

    if not pdf_content:
        result['status'] = 'download_failed'
        result['error'] = 'Failed to download PDF'
        # Mark as failed in database
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE epazar_tenders SET
                    evaluation_extraction_status = 'download_failed',
                    evaluation_extraction_error = %s
                WHERE tender_id = %s
            """, (result['error'], tender_id))
            conn.commit()
        return result

    # Parse PDF
    logger.info(f"Parsing PDF for {tender_id}")
    extraction = parse_evaluation_report(pdf_content)

    # Save results
    if save_extraction_results(conn, tender_id, pdf_url, extraction):
        result['status'] = extraction.get('extraction_status', 'unknown')
        result['items_extracted'] = len(extraction.get('items', []))
        result['confidence'] = extraction.get('extraction_confidence', 0)
    else:
        result['status'] = 'save_failed'
        result['error'] = 'Failed to save to database'

    return result


def main():
    parser = argparse.ArgumentParser(description='Extract e-pazar evaluation reports')
    parser.add_argument('--limit', type=int, default=10, help='Max tenders to process')
    parser.add_argument('--tender-id', type=str, help='Process specific tender')
    parser.add_argument('--pdf-url', type=str, help='Direct PDF URL to process')
    parser.add_argument('--retry-failed', action='store_true', help='Retry failed extractions')
    parser.add_argument('--discover', action='store_true', help='Discover evaluation URLs first')
    args = parser.parse_args()

    conn = get_db_connection()

    try:
        results = {
            'processed': 0,
            'success': 0,
            'partial': 0,
            'failed': 0,
            'items_total': 0
        }

        if args.tender_id and args.pdf_url:
            # Process single tender with known URL
            result = process_tender(conn, args.tender_id, args.pdf_url)
            logger.info(f"Result: {result}")
            results['processed'] = 1
            if result['status'] == 'success':
                results['success'] = 1
            elif result['status'] == 'partial':
                results['partial'] = 1
            else:
                results['failed'] = 1
            results['items_total'] = result.get('items_extracted', 0)

        elif args.discover:
            # Discover and process evaluation URLs
            logger.info("Discovering evaluation report URLs...")
            discovered = discover_evaluation_urls(conn, args.limit)
            logger.info(f"Found {len(discovered)} evaluation reports")

            for item in discovered:
                result = process_tender(conn, item['tender_id'], item['pdf_url'])
                results['processed'] += 1
                if result['status'] == 'success':
                    results['success'] += 1
                elif result['status'] == 'partial':
                    results['partial'] += 1
                else:
                    results['failed'] += 1
                results['items_total'] += result.get('items_extracted', 0)

        else:
            logger.error("Please specify --tender-id with --pdf-url, or use --discover")
            sys.exit(1)

        # Print summary
        logger.info("=" * 50)
        logger.info(f"EXTRACTION COMPLETE")
        logger.info(f"Processed: {results['processed']}")
        logger.info(f"Success: {results['success']}")
        logger.info(f"Partial: {results['partial']}")
        logger.info(f"Failed: {results['failed']}")
        logger.info(f"Total items extracted: {results['items_total']}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()

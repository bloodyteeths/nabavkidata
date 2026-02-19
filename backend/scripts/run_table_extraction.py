#!/usr/bin/env python3
"""
Run table extraction on all real PDFs in the database.

This script:
1. Queries database for PDFs > 50KB (real files, not HTML)
2. Validates each file is a real PDF
3. Extracts tables using multi-engine approach
4. Stores results in extracted_tables table
5. Extracts items from tables into product_items
"""

import os
import sys
import json
import asyncio
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, '/Users/tamsar/Downloads/nabavkidata')
sys.path.insert(0, '/Users/tamsar/Downloads/nabavkidata/ai')

import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com',
    'port': 5432,
    'user': 'nabavki_user',
    'password': os.getenv('DB_PASSWORD', ''),
    'database': 'nabavkidata',
}


def is_real_pdf(file_path: str) -> bool:
    """Check if file is a real PDF (not HTML/ZIP masquerading)"""
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, 'rb') as f:
            header = f.read(10)
            return header.startswith(b'%PDF')
    except:
        return False


LOCAL_FILES_DIR = '/Users/tamsar/Downloads/nabavkidata/scraper/downloads/files'


def get_pending_pdfs(conn, limit: int = None) -> List[Dict]:
    """Get PDFs that haven't been processed for tables yet"""
    # First, find PDFs that exist locally
    import os
    local_pdfs = {}
    for f in os.listdir(LOCAL_FILES_DIR):
        if f.endswith('.pdf'):
            path = os.path.join(LOCAL_FILES_DIR, f)
            size = os.path.getsize(path)
            if size > 50000:  # Real PDFs
                local_pdfs[f] = {'path': path, 'size': size}

    if not local_pdfs:
        return []

    # Get document IDs for these files
    file_names = list(local_pdfs.keys())
    placeholders = ','.join(['%s'] * len(file_names))

    query = f"""
        SELECT d.doc_id, d.tender_id, d.file_path, d.file_name, d.file_size_bytes
        FROM documents d
        LEFT JOIN extracted_tables et ON d.doc_id = et.doc_id
        WHERE d.file_name IN ({placeholders})
          AND et.table_id IS NULL
        ORDER BY d.file_size_bytes DESC
    """
    if limit:
        query += f" LIMIT {limit}"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, file_names)
        rows = cur.fetchall()

    # Map local paths
    result = []
    for row in rows:
        if row['file_name'] in local_pdfs:
            row['file_path'] = local_pdfs[row['file_name']]['path']
            result.append(row)

    return result


def store_tables(conn, tables: List[Dict], tender_id: str, doc_id: str):
    """Store extracted tables in database"""
    if not tables:
        return 0

    stored = 0
    with conn.cursor() as cur:
        for table in tables:
            try:
                # Convert data to JSON
                raw_data = json.dumps({
                    'columns': table.get('columns', []),
                    'data': table.get('data', [])
                })

                cur.execute("""
                    INSERT INTO extracted_tables (
                        doc_id, tender_id, page_number, table_index,
                        extraction_engine, table_type, confidence_score,
                        row_count, col_count, raw_data, header_row
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    doc_id,
                    tender_id,
                    table.get('page_number', 1),
                    table.get('table_index', 0),
                    table.get('engine_used', 'pdfplumber'),
                    table.get('table_type', 'unknown'),
                    table.get('confidence', 0.5),
                    table.get('row_count', 0),
                    table.get('col_count', 0),
                    raw_data,
                    json.dumps(table.get('columns', []))
                ))
                stored += 1
            except Exception as e:
                logger.warning(f"Failed to store table: {e}")
    conn.commit()
    return stored


def extract_items_from_table(table_data: Dict, tender_id: str) -> List[Dict]:
    """Extract item records from table data"""
    items = []
    columns = table_data.get('columns', [])
    data = table_data.get('data', [])

    # Map column names to standard fields (Macedonian patterns)
    # Order matters: more specific patterns first
    col_map = {}
    for i, col in enumerate(columns):
        col_lower = col.lower().replace('\n', ' ').strip()
        # Item name - most important
        if any(p in col_lower for p in ['назив', 'опис', 'име']) and 'name' not in col_map:
            col_map['name'] = col
        # Quantity
        elif any(p in col_lower for p in ['количина', 'кол.', 'qty']) and 'quantity' not in col_map:
            col_map['quantity'] = col
        # Unit of measure
        elif any(p in col_lower for p in ['мерна', 'единица мера', 'unit']) and 'unit' not in col_map:
            col_map['unit'] = col
        # Total price (check before unit price to avoid conflict)
        elif any(p in col_lower for p in ['вкупна', 'вкупно', 'total', 'износ']) and 'total_price' not in col_map:
            col_map['total_price'] = col
        # Unit price - check for единечна specifically
        elif any(p in col_lower for p in ['единечна', 'unit price', 'цена по']) and 'unit_price' not in col_map:
            col_map['unit_price'] = col
        # CPV/Item code
        elif any(p in col_lower for p in ['шифра', 'код', 'cpv', 'code']) and 'code' not in col_map:
            col_map['code'] = col

    logger.info(f"    Column mapping: {list(col_map.keys())}")

    if 'name' not in col_map:
        logger.info(f"    Skipping table - no name column found. Columns: {columns}")
        return items  # Can't extract without item name

    for row in data:
        try:
            item = {
                'tender_id': tender_id,
                'item_name': row.get(col_map.get('name', ''), ''),
                'quantity': parse_number(row.get(col_map.get('quantity', ''), '')),
                'unit_of_measure': row.get(col_map.get('unit', ''), ''),
                'unit_price': parse_number(row.get(col_map.get('unit_price', ''), '')),
                'total_price': parse_number(row.get(col_map.get('total_price', ''), '')),
                'item_code': row.get(col_map.get('code', ''), ''),
                'extraction_source': 'table_extraction',
                'raw_json': json.dumps(row, ensure_ascii=False)  # Store original row data
            }
            if item['item_name'] and len(item['item_name']) > 2:
                items.append(item)
                logger.info(f"    Extracted item: {item['item_name'][:50]}... price={item['unit_price']}")
        except Exception as e:
            logger.warning(f"    Error extracting row: {e}")
            continue

    logger.info(f"    Total items from table: {len(items)}")
    return items


def parse_number(value) -> Optional[float]:
    """Parse numeric value from string"""
    if value is None or value == '':
        return None
    try:
        # Handle Macedonian number format (1.234,56 or 1,234.56)
        s = str(value).strip()
        s = s.replace(' ', '').replace('\xa0', '')
        # Remove currency symbols
        for c in ['ден', 'MKD', 'EUR', '€', '$']:
            s = s.replace(c, '')
        s = s.strip()
        if not s:
            return None
        # Handle comma as decimal
        if ',' in s and '.' in s:
            if s.index(',') > s.index('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            s = s.replace(',', '.')
        return float(s)
    except:
        return None


def store_items(conn, items: List[Dict], tender_id: str, doc_id: str = None):
    """Store extracted items in product_items table"""
    if not items:
        return 0

    stored = 0
    with conn.cursor() as cur:
        for item in items:
            try:
                item_name = item.get('item_name', '').strip()
                if not item_name or len(item_name) < 2:
                    continue

                # Check for duplicate
                cur.execute("""
                    SELECT id FROM product_items
                    WHERE tender_id = %s AND name = %s
                    LIMIT 1
                """, (tender_id, item_name))

                if cur.fetchone():
                    # Update existing
                    cur.execute("""
                        UPDATE product_items
                        SET unit_price = COALESCE(%s, unit_price),
                            quantity = COALESCE(%s, quantity),
                            unit = COALESCE(NULLIF(%s, ''), unit),
                            extraction_method = %s,
                            cpv_code = COALESCE(NULLIF(%s, ''), cpv_code)
                        WHERE tender_id = %s AND name = %s
                    """, (
                        item.get('unit_price'), item.get('quantity'),
                        item.get('unit_of_measure'), item.get('extraction_source', 'table_extraction'),
                        item.get('item_code'),
                        tender_id, item_name
                    ))
                else:
                    # Insert new with raw JSON data
                    cur.execute("""
                        INSERT INTO product_items (tender_id, document_id, name, quantity,
                            unit, unit_price, cpv_code, extraction_method, raw_text)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        tender_id, doc_id, item_name, item.get('quantity'),
                        item.get('unit_of_measure'), item.get('unit_price'),
                        item.get('item_code'), item.get('extraction_source', 'table_extraction'),
                        item.get('raw_json')  # Store raw JSON for provenance
                    ))
                stored += 1
            except Exception as e:
                logger.warning(f"Failed to store item: {e}")
    conn.commit()
    return stored


def process_pdf(conn, doc: Dict) -> Dict:
    """Process a single PDF"""
    from table_extraction import extract_tables_from_pdf

    file_path = doc['file_path']
    doc_id = str(doc['doc_id'])
    tender_id = doc['tender_id']

    result = {
        'doc_id': doc_id,
        'file_name': doc['file_name'],
        'tables': 0,
        'items': 0,
        'success': False,
        'error': None
    }

    # Validate real PDF
    if not is_real_pdf(file_path):
        result['error'] = 'Not a valid PDF'
        return result

    try:
        # Extract tables
        tables = extract_tables_from_pdf(file_path)
        logger.info(f"  Extracted {len(tables)} tables from {doc['file_name']}")

        if tables:
            # Convert to storable format
            table_dicts = []
            all_items = []

            for t in tables:
                td = {
                    'columns': list(t.data.columns),
                    'data': t.data.fillna('').to_dict(orient='records'),
                    'page_number': t.page_number,
                    'table_index': t.table_index,
                    'engine_used': t.engine_used,
                    'table_type': t.table_type.value,
                    'confidence': t.confidence,
                    'row_count': len(t.data),
                    'col_count': len(t.data.columns)
                }
                table_dicts.append(td)

                # Extract items from this table
                if t.table_type.value == 'items':
                    items = extract_items_from_table(td, tender_id)
                    all_items.extend(items)

            # Store tables
            stored_tables = store_tables(conn, table_dicts, tender_id, doc_id)
            result['tables'] = stored_tables

            # Store items
            if all_items:
                stored_items = store_items(conn, all_items, tender_id, doc_id)
                result['items'] = stored_items
                logger.info(f"  Stored {stored_items} items")

        result['success'] = True

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"  Error: {e}")

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None, help='Max PDFs to process')
    parser.add_argument('--dry-run', action='store_true', help='Only show what would be processed')
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)
    logger.info("Database connected")

    try:
        # Get pending PDFs
        pdfs = get_pending_pdfs(conn, limit=args.limit)
        logger.info(f"Found {len(pdfs)} PDFs to process")

        if args.dry_run:
            for doc in pdfs[:10]:
                print(f"Would process: {doc['file_name']} ({doc['file_size_bytes']/1024:.1f}KB)")
            return

        # Process each PDF
        stats = {'processed': 0, 'success': 0, 'tables': 0, 'items': 0}

        for i, doc in enumerate(pdfs):
            logger.info(f"[{i+1}/{len(pdfs)}] Processing: {doc['file_name']}")
            result = process_pdf(conn, doc)

            stats['processed'] += 1
            if result['success']:
                stats['success'] += 1
                stats['tables'] += result['tables']
                stats['items'] += result['items']

            if (i + 1) % 20 == 0:
                logger.info(f"Progress: {i+1}/{len(pdfs)} - Tables: {stats['tables']}, Items: {stats['items']}")

        # Summary
        print("\n" + "=" * 60)
        print("TABLE EXTRACTION COMPLETE")
        print("=" * 60)
        print(f"Processed: {stats['processed']}")
        print(f"Successful: {stats['success']}")
        print(f"Tables extracted: {stats['tables']}")
        print(f"Items extracted: {stats['items']}")
        print("=" * 60)

    finally:
        conn.close()


if __name__ == '__main__':
    main()

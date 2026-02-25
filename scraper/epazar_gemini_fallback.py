#!/usr/bin/env python3
"""
Gemini Fallback for Failed E-Pazar Evaluation Extractions

Uses Google Gemini API to re-extract data from evaluation reports
that failed or had low confidence with PyMuPDF text parsing.

Usage:
    python epazar_gemini_fallback.py --limit 10
    python epazar_gemini_fallback.py --tender-id EPAZAR-935
    python epazar_gemini_fallback.py --retry-failed
"""

import argparse
import json
import logging
import os
import re
import sys
from typing import Dict, List, Optional, Any
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor, Json
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'nabavkidata'),
    'user': os.getenv('DB_USER', 'nabavki_user'),
    'password': os.getenv('DB_PASSWORD', ''),
    'port': os.getenv('DB_PORT', '5432')
}

# Gemini API configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Extraction prompt for Gemini
EXTRACTION_PROMPT = """Extract structured data from this Macedonian e-pazar evaluation report PDF text.

Return a JSON object with:
{
  "header": {
    "tender_number": "M00XXX/2025",
    "contracting_authority": "Name of institution",
    "tender_type": "Стоки/Услуги/Работи",
    "tender_subject": "Subject description",
    "publication_date": "DD.MM.YYYY",
    "evaluation_date": "DD.MM.YYYY"
  },
  "bidders": ["Company 1", "Company 2"],
  "items": [
    {
      "line_number": 1,
      "item_subject": "Product name/description",
      "required_brands": ["Brand1", "Brand2"],
      "offered_brand": "Winning brand",
      "unit": "парче/литар/etc",
      "quantity": 100,
      "unit_price": 150.50,
      "total_price": 15050.00,
      "winner_name": "Winning company ДООЕЛ"
    }
  ],
  "rejected_offers": [],
  "cancelled_parts": []
}

Important:
- Prices use European format (1.234,56 = 1234.56)
- Extract ALL items from the table
- Winner names often contain ДООЕЛ, ДОО, or АД
- If data is unclear, use null

PDF Text:
"""


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def configure_gemini():
    """Configure Gemini API."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel('gemini-2.0-flash-lite')


def extract_with_gemini(model, raw_text: str) -> Optional[Dict[str, Any]]:
    """Extract structured data using Gemini API."""
    try:
        # Truncate if too long (Gemini has context limits)
        if len(raw_text) > 50000:
            raw_text = raw_text[:50000] + "\n... [truncated]"

        prompt = EXTRACTION_PROMPT + raw_text

        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 8192,
            }
        )

        # Parse JSON from response
        text = response.text

        # Find JSON in response (might have markdown code blocks)
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())

        return None

    except Exception as e:
        logger.error(f"Gemini extraction failed: {e}")
        return None


def update_extraction_results(conn, tender_id: str, report_id: str,
                              extraction: Dict[str, Any]) -> bool:
    """Update database with Gemini extraction results."""
    try:
        with conn.cursor() as cur:
            # Update evaluation report
            cur.execute("""
                UPDATE epazar_evaluation_reports SET
                    tender_number = COALESCE(%s, tender_number),
                    contracting_authority = COALESCE(%s, contracting_authority),
                    tender_type = COALESCE(%s, tender_type),
                    tender_subject = COALESCE(%s, tender_subject),
                    bidders_list = COALESCE(%s, bidders_list),
                    raw_json = %s,
                    extraction_method = 'gemini',
                    extraction_status = 'success',
                    extraction_confidence = 0.95,
                    updated_at = NOW()
                WHERE report_id = %s
            """, (
                extraction.get('header', {}).get('tender_number'),
                extraction.get('header', {}).get('contracting_authority'),
                extraction.get('header', {}).get('tender_type'),
                extraction.get('header', {}).get('tender_subject'),
                extraction.get('bidders', []),
                Json(extraction),
                report_id
            ))

            # Delete old items and insert new ones
            cur.execute("""
                DELETE FROM epazar_item_evaluations
                WHERE tender_id = %s AND report_id = %s
            """, (tender_id, report_id))

            for item in extraction.get('items', []):
                cur.execute("""
                    INSERT INTO epazar_item_evaluations (
                        report_id, tender_id, line_number,
                        item_subject, required_brands, required_brands_raw,
                        offered_brand, unit, quantity,
                        unit_price_without_vat, total_without_vat,
                        winner_name, raw_row_data
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (tender_id, line_number) DO UPDATE SET
                        offered_brand = EXCLUDED.offered_brand,
                        unit_price_without_vat = EXCLUDED.unit_price_without_vat,
                        winner_name = EXCLUDED.winner_name,
                        raw_row_data = EXCLUDED.raw_row_data
                """, (
                    report_id, tender_id, item.get('line_number'),
                    item.get('item_subject'),
                    item.get('required_brands', []),
                    ', '.join(item.get('required_brands', [])) if item.get('required_brands') else None,
                    item.get('offered_brand'),
                    item.get('unit'),
                    item.get('quantity'),
                    item.get('unit_price'),
                    item.get('total_price'),
                    item.get('winner_name'),
                    Json(item)
                ))

            # Update bidders
            for bidder in extraction.get('bidders', []):
                cur.execute("""
                    INSERT INTO epazar_bidders (tender_id, bidder_name, source)
                    VALUES (%s, %s, 'gemini')
                    ON CONFLICT (tender_id, bidder_name) DO NOTHING
                """, (tender_id, bidder))

            conn.commit()
            return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update extraction for {tender_id}: {e}")
        return False


def process_failed_extractions(conn, model, limit: int = 10) -> Dict[str, int]:
    """Process failed/partial extractions with Gemini."""
    results = {
        'processed': 0,
        'success': 0,
        'failed': 0,
        'items_extracted': 0
    }

    # Get failed/partial extractions
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT report_id, tender_id, raw_text, extraction_status, extraction_confidence
            FROM epazar_evaluation_reports
            WHERE extraction_status IN ('failed', 'partial')
               OR extraction_confidence < 0.6
            ORDER BY extraction_confidence ASC NULLS FIRST
            LIMIT %s
        """, (limit,))
        reports = cur.fetchall()

    logger.info(f"Found {len(reports)} reports to retry with Gemini")

    for report in reports:
        tender_id = report['tender_id']
        report_id = report['report_id']
        raw_text = report['raw_text']

        if not raw_text:
            logger.warning(f"No raw_text for {tender_id}, skipping")
            continue

        logger.info(f"Processing {tender_id} (was: {report['extraction_status']}, conf: {report['extraction_confidence']})")

        # Extract with Gemini
        extraction = extract_with_gemini(model, raw_text)

        if extraction and extraction.get('items'):
            if update_extraction_results(conn, tender_id, report_id, extraction):
                results['success'] += 1
                results['items_extracted'] += len(extraction.get('items', []))
                logger.info(f"✓ {tender_id}: Extracted {len(extraction.get('items', []))} items")
            else:
                results['failed'] += 1
        else:
            results['failed'] += 1
            logger.warning(f"✗ {tender_id}: Gemini extraction failed or no items")

            # Mark as gemini_failed
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE epazar_evaluation_reports SET
                        extraction_status = 'gemini_failed',
                        extraction_method = 'gemini',
                        updated_at = NOW()
                    WHERE report_id = %s
                """, (report_id,))
                conn.commit()

        results['processed'] += 1

    return results


def main():
    parser = argparse.ArgumentParser(description='Gemini fallback for failed extractions')
    parser.add_argument('--limit', type=int, default=10, help='Max reports to process')
    parser.add_argument('--tender-id', type=str, help='Process specific tender')
    parser.add_argument('--retry-failed', action='store_true', help='Retry failed extractions')
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY environment variable not set")
        sys.exit(1)

    conn = get_db_connection()
    model = configure_gemini()

    try:
        if args.tender_id:
            # Process specific tender
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT report_id, tender_id, raw_text
                    FROM epazar_evaluation_reports
                    WHERE tender_id = %s
                """, (args.tender_id,))
                report = cur.fetchone()

            if report:
                extraction = extract_with_gemini(model, report['raw_text'])
                if extraction:
                    update_extraction_results(conn, report['tender_id'], report['report_id'], extraction)
                    logger.info(f"Processed {args.tender_id}: {len(extraction.get('items', []))} items")
            else:
                logger.error(f"Tender {args.tender_id} not found")
        else:
            # Process failed extractions
            results = process_failed_extractions(conn, model, args.limit)

            logger.info("=" * 50)
            logger.info("GEMINI FALLBACK COMPLETE")
            logger.info(f"Processed: {results['processed']}")
            logger.info(f"Success: {results['success']}")
            logger.info(f"Failed: {results['failed']}")
            logger.info(f"Items extracted: {results['items_extracted']}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()

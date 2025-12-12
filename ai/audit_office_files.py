#!/usr/bin/env python3
"""
Audit Office Files - Distinguish real Office files from HTML disguised as Office files

Usage:
    python ai/audit_office_files.py --directory scraper/downloads/files/
    python ai/audit_office_files.py --db-audit  # Audit files in database
"""

import os
import sys
import argparse
import asyncio
import asyncpg
from pathlib import Path
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_real_office_file(file_path: str) -> tuple[bool, str]:
    """
    Check if a file is a real Office document or HTML disguised as one

    Returns:
        (is_real, file_type) where file_type is 'office', 'html', 'pdf', 'unknown'
    """
    if not os.path.exists(file_path):
        return False, 'missing'

    # Read first 512 bytes
    try:
        with open(file_path, 'rb') as f:
            header = f.read(512)

        # Check for Office Open XML (DOCX, XLSX) - ZIP signature
        if header[:4] == b'PK\x03\x04':
            return True, 'office_openxml'

        # Check for old Office binary format (DOC, XLS) - OLE signature
        if header[:8] == b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1':
            return True, 'office_binary'

        # Check for HTML
        html_markers = [
            b'<!DOCTYPE html',
            b'<html',
            b'<!doctype html',
            b'<HTML'
        ]
        for marker in html_markers:
            if marker in header:
                return False, 'html'

        # Check for PDF
        if header[:4] == b'%PDF':
            return False, 'pdf'

        # Check for plain text
        if header[:1] == b'<':
            return False, 'html_or_xml'

        return False, 'unknown'

    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return False, 'error'


def audit_directory(directory: str, extensions: List[str] = None) -> Dict:
    """
    Audit all Office files in a directory

    Args:
        directory: Directory to scan
        extensions: List of extensions to check (e.g., ['.docx', '.xlsx'])

    Returns:
        Statistics dictionary
    """
    if extensions is None:
        extensions = ['.docx', '.doc', '.xlsx', '.xls']

    stats = {
        'total_files': 0,
        'real_office': 0,
        'fake_html': 0,
        'other': 0,
        'missing': 0,
        'by_extension': {},
        'fake_files': []  # List of fake files for reporting
    }

    # Initialize per-extension stats
    for ext in extensions:
        stats['by_extension'][ext] = {
            'total': 0,
            'real': 0,
            'fake': 0,
            'other': 0
        }

    logger.info(f"Scanning directory: {directory}")

    # Find all files
    all_files = []
    for ext in extensions:
        files = list(Path(directory).glob(f'**/*{ext}'))
        all_files.extend(files)

    logger.info(f"Found {len(all_files)} files with Office extensions")

    # Check each file
    for file_path in all_files:
        stats['total_files'] += 1
        ext = file_path.suffix.lower()

        is_real, file_type = is_real_office_file(str(file_path))

        stats['by_extension'][ext]['total'] += 1

        if is_real:
            stats['real_office'] += 1
            stats['by_extension'][ext]['real'] += 1
        elif file_type == 'html' or file_type == 'html_or_xml':
            stats['fake_html'] += 1
            stats['by_extension'][ext]['fake'] += 1
            stats['fake_files'].append({
                'path': str(file_path),
                'extension': ext,
                'actual_type': file_type
            })
        elif file_type == 'missing':
            stats['missing'] += 1
        else:
            stats['other'] += 1
            stats['by_extension'][ext]['other'] += 1

    return stats


async def audit_database_files(db_pool: asyncpg.Pool) -> Dict:
    """
    Audit Office files registered in database

    Returns:
        Statistics dictionary
    """
    logger.info("Fetching Office files from database...")

    # Get all Office documents from database
    docs = await db_pool.fetch("""
        SELECT doc_id, tender_id, file_path, file_name, extraction_status
        FROM documents
        WHERE LOWER(file_name) LIKE '%.docx'
           OR LOWER(file_name) LIKE '%.doc'
           OR LOWER(file_name) LIKE '%.xlsx'
           OR LOWER(file_name) LIKE '%.xls'
        ORDER BY doc_id
    """)

    logger.info(f"Found {len(docs)} Office documents in database")

    stats = {
        'total_files': len(docs),
        'real_office': 0,
        'fake_html': 0,
        'other': 0,
        'missing': 0,
        'by_extension': {
            '.docx': {'total': 0, 'real': 0, 'fake': 0, 'other': 0, 'missing': 0},
            '.doc': {'total': 0, 'real': 0, 'fake': 0, 'other': 0, 'missing': 0},
            '.xlsx': {'total': 0, 'real': 0, 'fake': 0, 'other': 0, 'missing': 0},
            '.xls': {'total': 0, 'real': 0, 'fake': 0, 'other': 0, 'missing': 0},
        },
        'by_status': {
            'pending': {'total': 0, 'real': 0, 'fake': 0},
            'success': {'total': 0, 'real': 0, 'fake': 0},
            'failed': {'total': 0, 'real': 0, 'fake': 0},
        },
        'fake_files': [],
        'missing_files': []
    }

    for doc in docs:
        file_name = doc['file_name']
        file_path = doc['file_path']
        status = doc['extraction_status'] or 'unknown'

        # Get extension
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in stats['by_extension']:
            continue

        stats['by_extension'][ext]['total'] += 1

        # Check if file is real
        is_real, file_type = is_real_office_file(file_path)

        # Update status stats
        if status not in stats['by_status']:
            stats['by_status'][status] = {'total': 0, 'real': 0, 'fake': 0}

        stats['by_status'][status]['total'] += 1

        if is_real:
            stats['real_office'] += 1
            stats['by_extension'][ext]['real'] += 1
            stats['by_status'][status]['real'] += 1
        elif file_type == 'html' or file_type == 'html_or_xml':
            stats['fake_html'] += 1
            stats['by_extension'][ext]['fake'] += 1
            stats['by_status'][status]['fake'] += 1
            stats['fake_files'].append({
                'doc_id': doc['doc_id'],
                'tender_id': doc['tender_id'],
                'file_name': file_name,
                'path': file_path,
                'status': status,
                'actual_type': file_type
            })
        elif file_type == 'missing':
            stats['missing'] += 1
            stats['by_extension'][ext]['missing'] += 1
            stats['missing_files'].append({
                'doc_id': doc['doc_id'],
                'tender_id': doc['tender_id'],
                'file_name': file_name,
                'path': file_path
            })
        else:
            stats['other'] += 1
            stats['by_extension'][ext]['other'] += 1

    return stats


def print_audit_report(stats: Dict, mode: str = 'directory'):
    """Print audit report"""
    print(f"\n{'='*70}")
    print(f"OFFICE FILE AUDIT REPORT ({mode.upper()})")
    print(f"{'='*70}\n")

    print(f"Total Files Scanned: {stats['total_files']}")
    print(f"Real Office Files: {stats['real_office']} ({stats['real_office']/stats['total_files']*100:.1f}%)")
    print(f"Fake (HTML) Files: {stats['fake_html']} ({stats['fake_html']/stats['total_files']*100:.1f}%)")
    print(f"Missing Files: {stats['missing']} ({stats['missing']/stats['total_files']*100:.1f}%)")
    print(f"Other Types: {stats['other']} ({stats['other']/stats['total_files']*100:.1f}%)")

    print(f"\n{'='*70}")
    print("BY FILE EXTENSION")
    print(f"{'='*70}")

    for ext, data in sorted(stats['by_extension'].items()):
        if data['total'] > 0:
            print(f"\n{ext.upper()}:")
            print(f"  Total: {data['total']}")
            print(f"  Real: {data['real']} ({data['real']/data['total']*100:.1f}%)")
            print(f"  Fake: {data['fake']} ({data['fake']/data['total']*100:.1f}%)")
            if 'missing' in data:
                print(f"  Missing: {data['missing']}")
            if data['other'] > 0:
                print(f"  Other: {data['other']}")

    if 'by_status' in stats:
        print(f"\n{'='*70}")
        print("BY EXTRACTION STATUS")
        print(f"{'='*70}")

        for status, data in sorted(stats['by_status'].items()):
            if data['total'] > 0:
                print(f"\n{status.upper()}:")
                print(f"  Total: {data['total']}")
                print(f"  Real: {data['real']} ({data['real']/data['total']*100:.1f}%)")
                print(f"  Fake: {data['fake']} ({data['fake']/data['total']*100:.1f}%)")

    # Show sample fake files
    if stats['fake_files']:
        print(f"\n{'='*70}")
        print(f"SAMPLE FAKE FILES (showing first 10)")
        print(f"{'='*70}")
        for fake in stats['fake_files'][:10]:
            if mode == 'database':
                print(f"\n  Doc ID: {fake['doc_id']}")
                print(f"  Tender: {fake['tender_id']}")
                print(f"  File: {fake['file_name']}")
                print(f"  Status: {fake['status']}")
                print(f"  Actual Type: {fake['actual_type']}")
            else:
                print(f"\n  File: {os.path.basename(fake['path'])}")
                print(f"  Extension: {fake['extension']}")
                print(f"  Actual Type: {fake['actual_type']}")

        if len(stats['fake_files']) > 10:
            print(f"\n  ... and {len(stats['fake_files']) - 10} more fake files")

    # Show missing files
    if stats.get('missing_files'):
        print(f"\n{'='*70}")
        print(f"MISSING FILES (showing first 5)")
        print(f"{'='*70}")
        for missing in stats['missing_files'][:5]:
            print(f"\n  Doc ID: {missing['doc_id']}")
            print(f"  Tender: {missing['tender_id']}")
            print(f"  File: {missing['file_name']}")
            print(f"  Path: {missing['path']}")

        if len(stats['missing_files']) > 5:
            print(f"\n  ... and {len(stats['missing_files']) - 5} more missing files")

    print(f"\n{'='*70}")
    print("RECOMMENDATION")
    print(f"{'='*70}")

    real_pct = stats['real_office'] / stats['total_files'] * 100 if stats['total_files'] > 0 else 0
    fake_pct = stats['fake_html'] / stats['total_files'] * 100 if stats['total_files'] > 0 else 0

    print(f"\nProcessable Office Files: {stats['real_office']} ({real_pct:.1f}%)")

    if fake_pct > 20:
        print(f"\nWARNING: {fake_pct:.1f}% of files are HTML disguised as Office files!")
        print("These should be:")
        print("  1. Marked as 'failed' in database")
        print("  2. Removed from downloads or moved to separate folder")
        print("  3. Re-downloaded if possible")

    if stats['missing'] > 0:
        print(f"\nWARNING: {stats['missing']} files are missing from disk!")
        print("Update database records or re-download these files.")

    print(f"\n{'='*70}\n")


async def main():
    parser = argparse.ArgumentParser(description='Audit Office files')
    parser.add_argument('--directory', help='Directory to audit')
    parser.add_argument('--db-audit', action='store_true', help='Audit files in database')
    parser.add_argument('--db-host', default='localhost')
    parser.add_argument('--db-name', default='nabavkidata')
    parser.add_argument('--db-user', default='postgres')
    parser.add_argument('--db-password', default='postgres')

    args = parser.parse_args()

    if args.directory:
        # Directory audit
        stats = audit_directory(args.directory)
        print_audit_report(stats, mode='directory')

    elif args.db_audit:
        # Database audit
        pool = await asyncpg.create_pool(
            host=args.db_host,
            database=args.db_name,
            user=args.db_user,
            password=args.db_password,
            min_size=1,
            max_size=3
        )

        try:
            stats = await audit_database_files(pool)
            print_audit_report(stats, mode='database')
        finally:
            await pool.close()

    else:
        parser.print_help()


if __name__ == '__main__':
    asyncio.run(main())

#!/usr/bin/env python3
"""
Local Chandra OCR with remote database storage.
Run on Mac M1/M2 with GPU, save results to EC2 PostgreSQL.

Usage:
    source chandra_venv/bin/activate
    python local_chandra_ocr.py --limit 100 --type contract
"""
import os
import sys
import json
import asyncio
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import asyncpg
import aiohttp

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')

# Chandra output directory
CHANDRA_OUTPUT = Path('/tmp/chandra_batch')
CHANDRA_OUTPUT.mkdir(exist_ok=True)

# Download directory
DOWNLOAD_DIR = Path('/tmp/chandra_downloads')
DOWNLOAD_DIR.mkdir(exist_ok=True)

class LocalChandraProcessor:
    def __init__(self):
        self.conn = None
        self.session = None
        self.processed = 0
        self.failed = 0

    async def connect(self):
        """Connect to remote database."""
        db_url = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        self.conn = await asyncpg.connect(db_url)
        self.session = aiohttp.ClientSession()
        print(f"✓ Connected to database")

    async def close(self):
        if self.session:
            await self.session.close()
        if self.conn:
            await self.conn.close()

    async def get_pending_scanned_docs(self, limit: int = 100, doc_type: str = None) -> List[Dict]:
        """Get scanned documents (where Tesseract would be slow)."""
        query = """
            SELECT d.doc_id, d.tender_id, d.file_url, d.file_name, d.category,
                   t.tender_id as tender_number
            FROM documents d
            JOIN tenders t ON d.tender_id = t.id
            WHERE d.extraction_status = 'pending'
            AND d.file_url IS NOT NULL
            AND d.file_name LIKE '%.pdf'
        """
        if doc_type:
            query += f" AND d.category = '{doc_type}'"
        query += f" ORDER BY d.created_at DESC LIMIT {limit}"

        rows = await self.conn.fetch(query)
        return [dict(r) for r in rows]

    async def download_document(self, file_url: str, tender_number: str) -> Optional[Path]:
        """Download document from e-nabavki.gov.mk."""
        safe_name = f"{tender_number.replace('/', '_')}_{hash(file_url) & 0xFFFFFFFF:08x}.pdf"
        local_path = DOWNLOAD_DIR / safe_name

        if local_path.exists():
            return local_path

        try:
            async with self.session.get(file_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    local_path.write_bytes(content)
                    print(f"  ↓ Downloaded: {safe_name} ({len(content)/1024:.1f} KB)")
                    return local_path
                else:
                    print(f"  ✗ Download failed: HTTP {resp.status}")
                    return None
        except Exception as e:
            print(f"  ✗ Download error: {e}")
            return None

    def run_chandra_ocr(self, pdf_path: Path) -> Optional[str]:
        """Run Chandra OCR on a PDF file using M1 GPU."""
        output_dir = CHANDRA_OUTPUT / pdf_path.stem
        output_dir.mkdir(exist_ok=True)

        try:
            # Run chandra CLI
            result = subprocess.run(
                ['chandra', str(pdf_path), str(output_dir), '--method', 'hf', '--batch-size', '1'],
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout per document
                env={**os.environ, 'PYTORCH_ENABLE_MPS_FALLBACK': '1'}
            )

            # Read markdown output
            md_files = list(output_dir.glob('**/*.md'))
            if md_files:
                text = md_files[0].read_text()
                print(f"  ✓ Chandra extracted {len(text)} chars")
                return text
            else:
                # Check for errors
                if result.returncode != 0:
                    print(f"  ✗ Chandra error: {result.stderr[:200]}")
                return None

        except subprocess.TimeoutExpired:
            print(f"  ✗ Chandra timeout (>5 min)")
            return None
        except Exception as e:
            print(f"  ✗ Chandra error: {e}")
            return None

    async def update_document(self, doc_id: str, content_text: str):
        """Update document in remote database with OCR results."""
        await self.conn.execute("""
            UPDATE documents SET
                content_text = $2,
                extraction_status = 'success',
                extraction_method = 'chandra',
                extracted_at = NOW()
            WHERE doc_id = $1
        """, doc_id, content_text)

    async def mark_failed(self, doc_id: str, error: str):
        """Mark document as failed."""
        await self.conn.execute("""
            UPDATE documents SET
                extraction_status = 'failed',
                extraction_method = 'chandra',
                extracted_at = NOW()
            WHERE doc_id = $1
        """, doc_id)

    async def process_batch(self, limit: int = 10, doc_type: str = None):
        """Process a batch of documents with Chandra OCR."""
        await self.connect()

        try:
            docs = await self.get_pending_scanned_docs(limit, doc_type)
            print(f"Found {len(docs)} pending PDF documents\n")

            for i, doc in enumerate(docs):
                print(f"[{i+1}/{len(docs)}] {doc['file_name'][:50]} (tender {doc['tender_number']})")

                # Download
                pdf_path = await self.download_document(doc['file_url'], doc['tender_number'])
                if not pdf_path:
                    self.failed += 1
                    await self.mark_failed(doc['doc_id'], 'download_failed')
                    continue

                # OCR with Chandra
                text = self.run_chandra_ocr(pdf_path)
                if text and len(text) > 100:
                    await self.update_document(doc['doc_id'], text)
                    self.processed += 1
                else:
                    self.failed += 1
                    await self.mark_failed(doc['doc_id'], 'ocr_failed')

                # Cleanup to save disk space
                pdf_path.unlink(missing_ok=True)

                # Clean chandra output
                output_dir = CHANDRA_OUTPUT / pdf_path.stem
                if output_dir.exists():
                    import shutil
                    shutil.rmtree(output_dir, ignore_errors=True)

                print()

            print(f"\n{'='*50}")
            print(f"Completed: {self.processed} success, {self.failed} failed")

        finally:
            await self.close()

async def main():
    import argparse
    parser = argparse.ArgumentParser(description='Local Chandra OCR with remote storage')
    parser.add_argument('--limit', type=int, default=10, help='Number of documents to process')
    parser.add_argument('--type', choices=['contract', 'bid', 'technical_specs', 'tender_docs', 'other'],
                       help='Filter by document type')
    args = parser.parse_args()

    print("="*50)
    print("Chandra OCR - Local Processing with Remote Storage")
    print("="*50)
    print(f"Processing up to {args.limit} documents")
    if args.type:
        print(f"Document type: {args.type}")
    print()

    processor = LocalChandraProcessor()
    await processor.process_batch(args.limit, args.type)

if __name__ == '__main__':
    asyncio.run(main())

#!/usr/bin/env python3
"""
Chandra Batch OCR - Uses CLI but processes multiple files efficiently.
Keeps model loaded by processing multiple pages in one CLI call.
"""
import os
import sys
import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional
import asyncpg
import aiohttp
import time
from dotenv import load_dotenv
load_dotenv()


DATABASE_URL = os.getenv('DATABASE_URL')
WORK_DIR = Path('/tmp/chandra_work')
WORK_DIR.mkdir(exist_ok=True)


async def get_pending_docs(conn, limit: int = 50) -> List[Dict]:
    """Get pending PDF documents."""
    rows = await conn.fetch("""
        SELECT doc_id::text, tender_id, file_url, file_name,
               COALESCE(doc_type, 'other') as category
        FROM documents
        WHERE extraction_status = 'pending'
        AND file_url IS NOT NULL
        AND (file_name LIKE '%.pdf' OR file_name LIKE '%.PDF')
        ORDER BY uploaded_at DESC
        LIMIT $1
    """, limit)
    return [dict(r) for r in rows]


async def download_docs(session, docs: List[Dict]) -> List[Dict]:
    """Download documents in parallel."""
    async def download_one(doc):
        safe_name = f"{doc['tender_id'].replace('/', '_')}_{hash(doc['file_url']) & 0xFFFFFFFF:08x}.pdf"
        local_path = WORK_DIR / safe_name

        if local_path.exists() and local_path.stat().st_size > 0:
            doc['local_path'] = str(local_path)
            return doc

        try:
            async with session.get(doc['file_url'], timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    local_path.write_bytes(content)
                    doc['local_path'] = str(local_path)
                    print(f"  ↓ {safe_name} ({len(content)//1024}KB)")
        except Exception as e:
            doc['error'] = str(e)[:50]
        return doc

    return await asyncio.gather(*[download_one(d) for d in docs])


def run_chandra_on_dir(input_dir: Path, output_dir: Path) -> Dict[str, str]:
    """Run Chandra on all PDFs in directory - model loads once!"""
    output_dir.mkdir(exist_ok=True)

    print(f"  🔄 Running Chandra on {input_dir}...")
    start = time.time()

    result = subprocess.run(
        ['chandra', str(input_dir), str(output_dir), '--method', 'hf', '--batch-size', '1'],
        capture_output=True,
        text=True,
        timeout=600  # 10 min for batch
    )

    elapsed = time.time() - start
    print(f"  ⏱ Chandra completed in {elapsed:.1f}s")

    # Collect results
    results = {}
    for md_file in output_dir.glob('**/*.md'):
        # Match output file to input PDF
        pdf_name = md_file.parent.name  # Folder name = PDF stem
        results[pdf_name] = md_file.read_text()

    return results


async def update_docs(conn, results: List[Dict]):
    """Update documents in database."""
    success = [d for d in results if d.get('text')]
    failed = [d for d in results if not d.get('text')]

    for doc in success:
        await conn.execute("""
            UPDATE documents SET
                content_text = $2,
                extraction_status = 'success',
                extraction_method = 'chandra'
            WHERE doc_id = $1::uuid
        """, doc['doc_id'], doc['text'])

    for doc in failed:
        await conn.execute("""
            UPDATE documents SET
                extraction_status = 'failed',
                extraction_method = 'chandra_failed'
            WHERE doc_id = $1::uuid
        """, doc['doc_id'])

    print(f"  ↑ Updated {len(success)} success, {len(failed)} failed")


async def process_batch(limit: int = 20):
    """Process a batch of documents."""
    print("="*50)
    print("Chandra Batch OCR")
    print("="*50)

    conn = await asyncpg.connect(DATABASE_URL)
    session = aiohttp.ClientSession()

    try:
        # Get documents
        docs = await get_pending_docs(conn, limit)
        print(f"\n📄 Found {len(docs)} pending documents\n")

        if not docs:
            return

        # Download all
        print("Downloading...")
        docs = await download_docs(session, docs)
        downloaded = [d for d in docs if d.get('local_path')]
        print(f"  ✓ Downloaded {len(downloaded)}/{len(docs)}\n")

        if not downloaded:
            return

        # Create input directory with downloaded PDFs
        batch_input = WORK_DIR / 'batch_input'
        batch_output = WORK_DIR / 'batch_output'

        # Clean previous
        if batch_input.exists():
            shutil.rmtree(batch_input)
        if batch_output.exists():
            shutil.rmtree(batch_output)
        batch_input.mkdir()

        # Copy/link files to batch input
        for doc in downloaded:
            src = Path(doc['local_path'])
            dst = batch_input / f"{doc['doc_id']}.pdf"
            shutil.copy(src, dst)

        # Run Chandra on batch
        ocr_results = run_chandra_on_dir(batch_input, batch_output)

        # Match results to documents
        for doc in downloaded:
            pdf_stem = doc['doc_id']
            if pdf_stem in ocr_results:
                doc['text'] = ocr_results[pdf_stem]

        # Update database
        await update_docs(conn, downloaded)

        # Cleanup
        for doc in downloaded:
            if doc.get('local_path'):
                Path(doc['local_path']).unlink(missing_ok=True)

        # Stats
        with_text = len([d for d in downloaded if d.get('text')])
        print(f"\n✓ Processed {with_text}/{len(downloaded)} successfully")

    finally:
        await session.close()
        await conn.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()

    asyncio.run(process_batch(args.limit))

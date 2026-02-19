#!/usr/bin/env python3
"""
FAST Chandra OCR Pipeline - Optimized for M1 Max GPU

Key optimizations:
1. Load model ONCE, process many documents (no CLI overhead)
2. Async parallel downloads (GPU never waits for network)
3. Batch database updates (reduce round-trips)
4. Pipeline: Download → GPU → Upload runs concurrently

Usage:
    source chandra_venv/bin/activate
    python chandra_fast.py --limit 100
"""
import os
import sys
import asyncio
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import asyncpg
import aiohttp
import aiofiles
from PIL import Image
import io

# Database
DATABASE_URL = os.getenv('DATABASE_URL')

# Directories
DOWNLOAD_DIR = Path('/tmp/chandra_fast')
DOWNLOAD_DIR.mkdir(exist_ok=True)

@dataclass
class Document:
    doc_id: str
    tender_id: str
    tender_number: str
    file_url: str
    file_name: str
    category: str
    local_path: Optional[Path] = None
    text: Optional[str] = None
    error: Optional[str] = None


class ChandraFastProcessor:
    def __init__(self):
        self.conn = None
        self.session = None
        self.model = None
        self.processor = None
        self.device = None
        self.stats = {'downloaded': 0, 'processed': 0, 'uploaded': 0, 'failed': 0}
        self.start_time = None

    async def connect_db(self):
        """Connect to database."""
        self.conn = await asyncpg.connect(DATABASE_URL)
        self.session = aiohttp.ClientSession()
        print("✓ Connected to database")

    async def close(self):
        if self.session:
            await self.session.close()
        if self.conn:
            await self.conn.close()

    def load_model(self):
        """Load Chandra model ONCE - this is the key optimization."""
        print("Loading Chandra model (one-time)...")
        import torch
        from transformers import Qwen3VLForConditionalGeneration, Qwen3VLProcessor

        # Detect device
        if torch.backends.mps.is_available():
            self.device = "mps"
            dtype = torch.bfloat16
        elif torch.cuda.is_available():
            self.device = "cuda"
            dtype = torch.float16
        else:
            self.device = "cpu"
            dtype = torch.float32

        print(f"  Device: {self.device}")

        # Load model
        model_name = "datalab-to/chandra"
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
        )

        if self.device == "mps":
            self.model = self.model.to("mps")

        self.model = self.model.eval()
        self.processor = Qwen3VLProcessor.from_pretrained(model_name)

        print(f"✓ Model loaded on {self.device}")

    async def get_pending_docs(self, limit: int = 100) -> List[Document]:
        """Get pending PDF documents."""
        rows = await self.conn.fetch("""
            SELECT d.doc_id, d.tender_id, d.file_url, d.file_name,
                   COALESCE(d.doc_type, 'other') as category,
                   d.tender_id as tender_number
            FROM documents d
            WHERE d.extraction_status = 'pending'
            AND d.file_url IS NOT NULL
            AND (d.file_name LIKE '%.pdf' OR d.file_name LIKE '%.PDF')
            ORDER BY d.uploaded_at DESC
            LIMIT $1
        """, limit)

        return [Document(
            doc_id=str(r['doc_id']),
            tender_id=r['tender_id'],
            tender_number=r['tender_number'],
            file_url=r['file_url'],
            file_name=r['file_name'],
            category=r['category']
        ) for r in rows]

    async def download_doc(self, doc: Document) -> Document:
        """Download a single document."""
        safe_name = f"{doc.tender_number.replace('/', '_')}_{hash(doc.file_url) & 0xFFFFFFFF:08x}.pdf"
        local_path = DOWNLOAD_DIR / safe_name

        if local_path.exists() and local_path.stat().st_size > 0:
            doc.local_path = local_path
            return doc

        try:
            async with self.session.get(doc.file_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    async with aiofiles.open(local_path, 'wb') as f:
                        await f.write(content)
                    doc.local_path = local_path
                    self.stats['downloaded'] += 1
                else:
                    doc.error = f"HTTP {resp.status}"
        except Exception as e:
            doc.error = str(e)[:100]

        return doc

    async def download_batch(self, docs: List[Document], concurrency: int = 5) -> List[Document]:
        """Download multiple documents in parallel."""
        semaphore = asyncio.Semaphore(concurrency)

        async def download_with_limit(doc):
            async with semaphore:
                return await self.download_doc(doc)

        return await asyncio.gather(*[download_with_limit(d) for d in docs])

    def pdf_to_images(self, pdf_path: Path) -> List[Image.Image]:
        """Convert PDF pages to images for Chandra."""
        import pypdfium2 as pdfium

        try:
            pdf = pdfium.PdfDocument(str(pdf_path))
            images = []
            for i in range(min(len(pdf), 20)):  # Max 20 pages
                page = pdf[i]
                # Render at 150 DPI for good quality without being too large
                bitmap = page.render(scale=150/72)
                pil_image = bitmap.to_pil()
                images.append(pil_image)
            return images
        except Exception as e:
            print(f"  PDF error: {e}")
            return []

    def process_single_doc(self, doc: Document) -> Document:
        """Process a single document with Chandra (runs on GPU)."""
        import torch
        from qwen_vl_utils import process_vision_info

        if not doc.local_path or doc.error:
            return doc

        try:
            # Convert PDF to images
            images = self.pdf_to_images(doc.local_path)
            if not images:
                doc.error = "No pages extracted"
                return doc

            all_text = []

            for i, image in enumerate(images):
                # Prepare prompt
                prompt = """Extract all text from this document image.
Output the text in markdown format, preserving:
- Headers and sections
- Tables (as markdown tables)
- Lists (numbered and bulleted)
- All text content

Focus on accuracy for Cyrillic/Macedonian text."""

                messages = [{
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt}
                    ]
                }]

                text = self.processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )

                image_inputs, _ = process_vision_info(messages)
                inputs = self.processor(
                    text=text,
                    images=image_inputs,
                    padding=True,
                    return_tensors="pt",
                )
                inputs = inputs.to(self.device)

                # Generate
                with torch.no_grad():
                    generated_ids = self.model.generate(
                        **inputs,
                        max_new_tokens=4096,
                        do_sample=False,
                    )

                generated_ids_trimmed = generated_ids[0][len(inputs.input_ids[0]):]
                page_text = self.processor.decode(
                    generated_ids_trimmed,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,
                )

                all_text.append(f"## Page {i+1}\n\n{page_text}")

            doc.text = "\n\n---\n\n".join(all_text)
            self.stats['processed'] += 1

        except Exception as e:
            doc.error = str(e)[:200]
            self.stats['failed'] += 1

        # Cleanup
        if doc.local_path and doc.local_path.exists():
            doc.local_path.unlink(missing_ok=True)

        return doc

    async def upload_results(self, docs: List[Document]):
        """Batch upload results to database."""
        success_docs = [d for d in docs if d.text and len(d.text) > 50]
        failed_docs = [d for d in docs if d.error or (not d.text)]

        if success_docs:
            await self.conn.executemany("""
                UPDATE documents SET
                    content_text = $2,
                    extraction_status = 'success',
                    extraction_method = 'chandra',
                    extracted_at = NOW()
                WHERE doc_id = $1
            """, [(d.doc_id, d.text) for d in success_docs])
            self.stats['uploaded'] += len(success_docs)

        if failed_docs:
            await self.conn.executemany("""
                UPDATE documents SET
                    extraction_status = 'failed',
                    extraction_method = 'chandra_failed',
                    extracted_at = NOW()
                WHERE doc_id = $1
            """, [(d.doc_id,) for d in failed_docs])

    def print_stats(self):
        """Print progress stats."""
        elapsed = time.time() - self.start_time
        rate = self.stats['processed'] / elapsed * 60 if elapsed > 0 else 0
        print(f"\r⏱ {elapsed:.0f}s | ↓{self.stats['downloaded']} | 🔄{self.stats['processed']} | ↑{self.stats['uploaded']} | ❌{self.stats['failed']} | {rate:.1f}/min", end='', flush=True)

    async def run(self, limit: int = 100, batch_size: int = 5):
        """Main processing loop with pipelining."""
        self.start_time = time.time()

        await self.connect_db()
        self.load_model()

        docs = await self.get_pending_docs(limit)
        print(f"\nFound {len(docs)} pending documents\n")

        if not docs:
            print("No documents to process")
            await self.close()
            return

        # Process in batches
        for i in range(0, len(docs), batch_size):
            batch = docs[i:i + batch_size]

            # 1. Download batch in parallel
            batch = await self.download_batch(batch)

            # 2. Process each doc (GPU-bound, sequential)
            for doc in batch:
                if doc.local_path and not doc.error:
                    print(f"\n[{i + batch.index(doc) + 1}/{len(docs)}] {doc.file_name[:40]}...", end=' ')
                    doc = self.process_single_doc(doc)
                    if doc.text:
                        print(f"✓ {len(doc.text)} chars")
                    else:
                        print(f"✗ {doc.error[:30] if doc.error else 'failed'}")

            # 3. Upload batch results
            await self.upload_results(batch)

            self.print_stats()

        print(f"\n\n{'='*50}")
        print(f"Completed in {time.time() - self.start_time:.1f}s")
        print(f"Processed: {self.stats['processed']}, Uploaded: {self.stats['uploaded']}, Failed: {self.stats['failed']}")

        await self.close()


async def main():
    import argparse
    parser = argparse.ArgumentParser(description='Fast Chandra OCR')
    parser.add_argument('--limit', type=int, default=50, help='Documents to process')
    parser.add_argument('--batch', type=int, default=5, help='Batch size for downloads')
    args = parser.parse_args()

    print("="*50)
    print("FAST Chandra OCR Pipeline")
    print("="*50)

    processor = ChandraFastProcessor()
    await processor.run(args.limit, args.batch)


if __name__ == '__main__':
    asyncio.run(main())

#!/usr/bin/env python3
"""
Re-embed all tender documents with Gemini embeddings
Replaces old 1536-dim OpenAI embeddings with 768-dim Gemini embeddings
"""
import os
import sys
import asyncio
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'ai'))
sys.path.insert(0, str(project_root / 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
import asyncpg

print("=" * 80)
print("RE-EMBEDDING DOCUMENTS WITH GEMINI")
print("=" * 80)

# Load environment
from dotenv import load_dotenv
load_dotenv('.env.prod')

DATABASE_URL = os.getenv('DATABASE_URL')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not DATABASE_URL:
    print("❌ DATABASE_URL not set")
    sys.exit(1)

if not GEMINI_API_KEY or GEMINI_API_KEY == 'CHANGE_THIS_TO_YOUR_GEMINI_API_KEY':
    print("❌ GEMINI_API_KEY not set or invalid")
    print("Please update GEMINI_API_KEY in .env.prod")
    sys.exit(1)

print(f"✅ Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else '(local)'}")
print(f"✅ Gemini API Key: {'*' * 20}{GEMINI_API_KEY[-8:]}")

from embeddings import EmbeddingsPipeline

async def reembed_all_documents():
    """Re-embed all tender documents"""

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL.replace('postgresql+asyncpg', 'postgresql'))

    try:
        # Get all documents
        print("\n1. Fetching documents from database...")
        documents = await conn.fetch("""
            SELECT
                d.doc_id,
                d.tender_id,
                d.content_text,
                t.title,
                t.description
            FROM documents d
            LEFT JOIN tenders t ON d.tender_id = t.tender_id
            WHERE d.content_text IS NOT NULL
            ORDER BY d.created_at DESC
        """)

        print(f"   Found {len(documents)} documents")

        if len(documents) == 0:
            print("   No documents to embed")
            return

        # Initialize pipeline
        print("\n2. Initializing Gemini embeddings pipeline...")
        pipeline = EmbeddingsPipeline()

        # Process documents
        print("\n3. Generating embeddings...")
        success_count = 0
        error_count = 0

        for i, doc in enumerate(documents, 1):
            try:
                # Combine title + description + content
                text_parts = []
                if doc['title']:
                    text_parts.append(doc['title'])
                if doc['description']:
                    text_parts.append(doc['description'])
                if doc['content_text']:
                    text_parts.append(doc['content_text'])

                full_text = '\n\n'.join(text_parts)

                if not full_text.strip():
                    print(f"   [{i}/{len(documents)}] Skipping empty document {doc['doc_id']}")
                    continue

                # Generate embeddings
                embed_ids = await pipeline.process_document(
                    text=full_text,
                    tender_id=doc['tender_id'],
                    doc_id=str(doc['doc_id']),
                    metadata={
                        'title': doc['title'],
                        'source': 'reembedding'
                    }
                )

                success_count += 1
                print(f"   [{i}/{len(documents)}] ✅ {doc['doc_id']}: {len(embed_ids)} chunks")

            except Exception as e:
                error_count += 1
                print(f"   [{i}/{len(documents)}] ❌ {doc['doc_id']}: {e}")

        print("\n" + "=" * 80)
        print("RE-EMBEDDING COMPLETE")
        print("=" * 80)
        print(f"✅ Success: {success_count} documents")
        print(f"❌ Errors: {error_count} documents")
        print(f"📊 Total embeddings generated: (check database)")

    finally:
        await conn.close()

async def verify_embeddings():
    """Verify embeddings were created correctly"""
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)

    conn = await asyncpg.connect(DATABASE_URL.replace('postgresql+asyncpg', 'postgresql'))

    try:
        # Check embedding count
        count = await conn.fetchval("SELECT COUNT(*) FROM embeddings")
        print(f"✅ Total embeddings in database: {count}")

        # Check vector dimensions
        sample = await conn.fetchrow("""
            SELECT
                embed_id,
                array_length(vector::float[], 1) as dimension,
                embedding_model
            FROM embeddings
            LIMIT 1
        """)

        if sample:
            print(f"✅ Sample embedding dimension: {sample['dimension']}")
            print(f"✅ Embedding model: {sample['embedding_model']}")

            if sample['dimension'] != 768:
                print(f"❌ ERROR: Expected 768 dimensions, got {sample['dimension']}")
        else:
            print("⚠️  No embeddings found")

    finally:
        await conn.close()

async def main():
    print("\nThis will re-embed all documents with Gemini (768-dim vectors)")
    print("Old embeddings have been truncated during migration")
    print("")

    confirm = input("Continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Aborted")
        return

    await reembed_all_documents()
    await verify_embeddings()

    print("\n✅ Re-embedding complete!")
    print("\nNext: Test RAG queries with:")
    print("  python3 scripts/verify_gemini.py")

if __name__ == '__main__':
    asyncio.run(main())

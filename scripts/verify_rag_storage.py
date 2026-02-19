#!/usr/bin/env python3
"""
RAG Storage Verification Script

This script verifies that all raw data for RAG enrichment is being properly stored:
1. Documents table: content_text, specifications_json
2. Tenders table: raw_data_json
3. Product items: Extraction statistics

Usage:
    python verify_rag_storage.py
"""

import asyncio
import os
import asyncpg
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


DATABASE_URL = os.getenv('DATABASE_URL')

# Strip SQLAlchemy prefix if present
if DATABASE_URL.startswith('postgresql+asyncpg://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')


async def verify_storage():
    """Verify RAG storage across all tables"""

    print("=" * 80)
    print("RAG STORAGE VERIFICATION REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # =====================================================================
        # 1. DOCUMENTS TABLE - Content Text & Specifications
        # =====================================================================
        print("1. DOCUMENTS TABLE - Raw Content Storage")
        print("-" * 80)

        # Total documents
        total_docs = await conn.fetchval("SELECT COUNT(*) FROM documents")
        print(f"Total documents: {total_docs:,}")

        # Documents with content_text
        docs_with_content = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE content_text IS NOT NULL AND LENGTH(content_text) > 100"
        )
        print(f"Documents with content_text (>100 chars): {docs_with_content:,} ({docs_with_content/total_docs*100:.1f}%)")

        # Documents with specifications_json
        docs_with_specs = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE specifications_json IS NOT NULL"
        )
        print(f"Documents with specifications_json: {docs_with_specs:,} ({docs_with_specs/total_docs*100:.1f}%)")

        # Extraction status breakdown
        print("\nExtraction Status Breakdown:")
        status_rows = await conn.fetch("""
            SELECT extraction_status, COUNT(*) as count
            FROM documents
            GROUP BY extraction_status
            ORDER BY count DESC
        """)
        for row in status_rows:
            print(f"  - {row['extraction_status'] or 'NULL'}: {row['count']:,}")

        # Average content length
        avg_content_length = await conn.fetchval("""
            SELECT AVG(LENGTH(content_text))::INTEGER
            FROM documents
            WHERE content_text IS NOT NULL
        """)
        print(f"\nAverage content_text length: {avg_content_length:,} characters")

        # Sample document with content
        sample_doc = await conn.fetchrow("""
            SELECT doc_id, tender_id, file_name,
                   LENGTH(content_text) as content_length,
                   LEFT(content_text, 100) as content_preview,
                   specifications_json IS NOT NULL as has_specs
            FROM documents
            WHERE content_text IS NOT NULL
            ORDER BY RANDOM()
            LIMIT 1
        """)
        if sample_doc:
            print(f"\nSample document with content:")
            print(f"  - doc_id: {sample_doc['doc_id']}")
            print(f"  - tender_id: {sample_doc['tender_id']}")
            print(f"  - file_name: {sample_doc['file_name']}")
            print(f"  - content_length: {sample_doc['content_length']:,} chars")
            print(f"  - has_specs: {sample_doc['has_specs']}")
            print(f"  - preview: {sample_doc['content_preview'][:80]}...")

        print()

        # =====================================================================
        # 2. TENDERS TABLE - Raw JSON Storage
        # =====================================================================
        print("2. TENDERS TABLE - Raw JSON Storage")
        print("-" * 80)

        # Total tenders
        total_tenders = await conn.fetchval("SELECT COUNT(*) FROM tenders")
        print(f"Total tenders: {total_tenders:,}")

        # Tenders with raw_data_json
        tenders_with_raw = await conn.fetchval(
            "SELECT COUNT(*) FROM tenders WHERE raw_data_json IS NOT NULL"
        )
        print(f"Tenders with raw_data_json: {tenders_with_raw:,} ({tenders_with_raw/total_tenders*100:.1f}%)")

        # Sample tender with raw_data_json
        sample_tender = await conn.fetchrow("""
            SELECT tender_id, title,
                   jsonb_object_keys(raw_data_json) as keys_sample
            FROM tenders
            WHERE raw_data_json IS NOT NULL
            ORDER BY RANDOM()
            LIMIT 1
        """)
        if sample_tender:
            print(f"\nSample tender with raw_data_json:")
            print(f"  - tender_id: {sample_tender['tender_id']}")
            print(f"  - title: {sample_tender['title'][:60]}...")

            # Get all keys in raw_data_json
            keys = await conn.fetch("""
                SELECT DISTINCT jsonb_object_keys(raw_data_json) as key
                FROM tenders
                WHERE raw_data_json IS NOT NULL
                LIMIT 10
            """)
            print(f"  - raw_data_json keys (sample): {', '.join([k['key'] for k in keys[:10]])}")

        print()

        # =====================================================================
        # 3. PRODUCT ITEMS - Extracted Data
        # =====================================================================
        print("3. PRODUCT ITEMS - Extracted Product Data")
        print("-" * 80)

        # Total product items
        total_items = await conn.fetchval("SELECT COUNT(*) FROM product_items")
        print(f"Total product items extracted: {total_items:,}")

        # Items by extraction method
        print("\nExtraction Method Breakdown:")
        method_rows = await conn.fetch("""
            SELECT extraction_method, COUNT(*) as count
            FROM product_items
            GROUP BY extraction_method
            ORDER BY count DESC
        """)
        for row in method_rows:
            print(f"  - {row['extraction_method'] or 'NULL'}: {row['count']:,}")

        # Items with specifications
        items_with_specs = await conn.fetchval("""
            SELECT COUNT(*)
            FROM product_items
            WHERE specifications IS NOT NULL AND specifications::text != '{}'
        """)
        print(f"\nItems with specifications: {items_with_specs:,} ({items_with_specs/total_items*100:.1f}% if total_items else 0)")

        # Average extraction confidence
        avg_confidence = await conn.fetchval("""
            SELECT AVG(extraction_confidence)::NUMERIC(3,2)
            FROM product_items
            WHERE extraction_confidence IS NOT NULL
        """)
        print(f"Average extraction confidence: {avg_confidence or 'N/A'}")

        # Sample product item
        sample_item = await conn.fetchrow("""
            SELECT name, quantity, unit, unit_price,
                   tender_id, extraction_method,
                   specifications IS NOT NULL as has_specs
            FROM product_items
            ORDER BY RANDOM()
            LIMIT 1
        """)
        if sample_item:
            print(f"\nSample product item:")
            print(f"  - name: {sample_item['name'][:60]}")
            print(f"  - quantity: {sample_item['quantity']} {sample_item['unit']}")
            print(f"  - unit_price: {sample_item['unit_price']}")
            print(f"  - tender_id: {sample_item['tender_id']}")
            print(f"  - extraction_method: {sample_item['extraction_method']}")
            print(f"  - has_specs: {sample_item['has_specs']}")

        print()

        # =====================================================================
        # 4. EMBEDDINGS - Vector Search Readiness
        # =====================================================================
        print("4. EMBEDDINGS - Vector Search Readiness")
        print("-" * 80)

        # Total embeddings
        total_embeddings = await conn.fetchval("SELECT COUNT(*) FROM embeddings")
        print(f"Total embeddings: {total_embeddings:,}")

        # Embeddings by model
        model_rows = await conn.fetch("""
            SELECT embedding_model, COUNT(*) as count
            FROM embeddings
            GROUP BY embedding_model
            ORDER BY count DESC
        """)
        if model_rows:
            print("\nEmbedding Model Breakdown:")
            for row in model_rows:
                print(f"  - {row['embedding_model']}: {row['count']:,}")

        # Tenders with embeddings
        tenders_with_embeddings = await conn.fetchval("""
            SELECT COUNT(DISTINCT tender_id) FROM embeddings
        """)
        print(f"\nTenders with embeddings: {tenders_with_embeddings:,} ({tenders_with_embeddings/total_tenders*100:.1f}%)")

        # Documents with embeddings
        docs_with_embeddings = await conn.fetchval("""
            SELECT COUNT(DISTINCT doc_id) FROM embeddings WHERE doc_id IS NOT NULL
        """)
        print(f"Documents with embeddings: {docs_with_embeddings:,} ({docs_with_embeddings/total_docs*100:.1f}%)")

        print()

        # =====================================================================
        # 5. SUMMARY & RECOMMENDATIONS
        # =====================================================================
        print("5. SUMMARY & RECOMMENDATIONS")
        print("-" * 80)

        issues = []
        recommendations = []

        # Check for missing content_text
        if docs_with_content / total_docs < 0.5:
            issues.append(f"Low content_text coverage: {docs_with_content/total_docs*100:.1f}%")
            recommendations.append("Run process_documents.py to extract text from pending documents")

        # Check for missing raw_data_json
        if tenders_with_raw / total_tenders < 0.8:
            issues.append(f"Low raw_data_json coverage: {tenders_with_raw/total_tenders*100:.1f}%")
            recommendations.append("Update scraper to ensure raw_data_json is saved for all tenders")

        # Check for missing embeddings
        if tenders_with_embeddings / total_tenders < 0.3:
            issues.append(f"Low embedding coverage: {tenders_with_embeddings/total_tenders*100:.1f}%")
            recommendations.append("Run embedding generation script to create vectors for RAG")

        if issues:
            print("ISSUES FOUND:")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            print()
            print("RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
        else:
            print("ALL CHECKS PASSED!")
            print("RAG storage is properly configured and populated.")

        print()
        print("=" * 80)
        print("VERIFICATION COMPLETE")
        print("=" * 80)

    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(verify_storage())

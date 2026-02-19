#!/usr/bin/env python3
"""
Test script for semantic_search_documents tool
"""
import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.embeddings import EmbeddingGenerator, VectorStore
from db_pool import get_pool

async def test_semantic_search():
    """Test semantic search functionality"""

    print("="*70)
    print("Testing Semantic Search with pgvector")
    print("="*70)

    # Check environment
    if not os.getenv('GEMINI_API_KEY'):
        print("ERROR: GEMINI_API_KEY not set")
        return

    if not os.getenv('DATABASE_URL'):
        print("ERROR: DATABASE_URL not set")
        return

    try:
        # Initialize components
        print("\n1. Initializing embedding generator...")
        embedder = EmbeddingGenerator(api_key=os.getenv('GEMINI_API_KEY'))

        print("2. Connecting to database...")
        pool = await get_pool()

        # Test query
        test_query = "медицинска опрема за хируршки интервенции"
        print(f"\n3. Test query: '{test_query}'")

        # Generate embedding
        print("4. Generating query embedding...")
        query_vector = await embedder.generate_embedding(test_query)
        print(f"   ✓ Generated {len(query_vector)}-dimensional vector")

        # Perform similarity search
        print("\n5. Performing vector similarity search...")
        vector_str = '[' + ','.join(map(str, query_vector)) + ']'

        async with pool.acquire() as conn:
            # Check if embeddings table exists and has data
            count_result = await conn.fetchval("SELECT COUNT(*) FROM embeddings")
            print(f"   ℹ Database contains {count_result} embeddings")

            if count_result == 0:
                print("   ⚠ WARNING: No embeddings found in database!")
                print("   Run the embeddings pipeline first to generate embeddings.")
                return

            # Search with similarity threshold
            query = """
                SELECT
                    e.embed_id,
                    e.chunk_text,
                    e.tender_id,
                    e.doc_id,
                    1 - (e.embedding <=> $1::vector) as similarity,
                    t.title as tender_title,
                    t.procuring_entity
                FROM embeddings e
                LEFT JOIN tenders t ON e.tender_id = t.tender_id
                WHERE 1 - (e.embedding <=> $1::vector) >= 0.5
                ORDER BY e.embedding <=> $1::vector
                LIMIT 5
            """

            rows = await conn.fetch(query, vector_str)

            print(f"\n6. Results: Found {len(rows)} semantically similar documents\n")

            if rows:
                for i, row in enumerate(rows, 1):
                    similarity_pct = row['similarity'] * 100
                    print(f"Result #{i} - Similarity: {similarity_pct:.1f}%")
                    print(f"  Tender: {row['tender_title'][:80] if row['tender_title'] else 'N/A'}...")
                    print(f"  Entity: {row['procuring_entity'][:60] if row['procuring_entity'] else 'N/A'}")
                    print(f"  Preview: {row['chunk_text'][:150]}...")
                    print()
            else:
                print("  ⚠ No results found with similarity >= 50%")
                print("  Try lowering the threshold or use different search terms")

        print("="*70)
        print("✓ Semantic search test completed successfully!")
        print("="*70)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_semantic_search())

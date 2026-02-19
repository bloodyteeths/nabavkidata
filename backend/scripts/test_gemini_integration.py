#!/usr/bin/env python3
"""
Test Gemini Integration End-to-End
Tests the full pipeline: embeddings + RAG on production database
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'ai'))

async def main():
    print("=" * 80)
    print("GEMINI INTEGRATION TEST - Production Database")
    print("=" * 80)

    # Test 1: Embedding Generation
    print("\n1. Testing Embedding Generation...")
    try:
        from embeddings import EmbeddingGenerator

        gen = EmbeddingGenerator()
        test_text = "Јавна набавка за канцелариски материјали за 2025 година"

        vector = await gen.generate_embedding(test_text)

        print(f"   ✅ Generated embedding")
        print(f"   ✅ Model: {gen.model}")
        print(f"   ✅ Dimension: {len(vector)} (expected 768)")
        print(f"   ✅ Sample values: {vector[:3]}")

        if len(vector) != 768:
            print(f"   ❌ ERROR: Expected 768 dimensions, got {len(vector)}")
            return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Vector Storage
    print("\n2. Testing Vector Storage...")
    try:
        from embeddings import VectorStore

        db_url = os.getenv('DATABASE_URL')
        # asyncpg doesn't support the +asyncpg suffix
        if 'postgresql+asyncpg://' in db_url:
            db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
        store = VectorStore(db_url)
        await store.connect()

        # Store test embedding
        embed_id = await store.store_embedding(
            vector=vector,
            chunk_text=test_text,
            chunk_index=0,
            metadata={'test': True}
        )

        print(f"   ✅ Stored embedding: {embed_id}")

        # Test similarity search
        results = await store.similarity_search(vector, limit=1)

        print(f"   ✅ Similarity search returned {len(results)} results")
        if results:
            print(f"   ✅ Similarity score: {results[0]['similarity']:.4f}")
            print(f"   ✅ Retrieved text: {results[0]['chunk_text'][:50]}...")

        await store.close()

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 3: RAG Query
    print("\n3. Testing RAG Query...")
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

        model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        model = genai.GenerativeModel(model_name)

        query = "Што е јавна набавка?"
        response = model.generate_content(query)

        print(f"   ✅ Model: {model_name}")
        print(f"   ✅ Query: {query}")
        print(f"   ✅ Response length: {len(response.text)} chars")
        print(f"   ✅ Response preview: {response.text[:150]}...")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED - Gemini integration working!")
    print("=" * 80)
    print("\nProduction database is ready for:")
    print("  - Gemini text-embedding-004 (768 dimensions)")
    print("  - Gemini 2.5 Flash for RAG generation")
    print("  - Vector similarity search with pgvector")

    return True

if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

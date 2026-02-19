#!/usr/bin/env python3
"""
Gemini API Verification Script
Tests Gemini embeddings and generation
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'ai'))
sys.path.insert(0, str(project_root / 'backend'))

print("=" * 80)
print("GEMINI API VERIFICATION")
print("=" * 80)

# Check environment variables
print("\n1. Checking Environment Variables...")
gemini_key = os.getenv('GEMINI_API_KEY')
if gemini_key:
    print(f"   ✅ GEMINI_API_KEY: {'*' * 20}{gemini_key[-8:]}")
else:
    print("   ❌ GEMINI_API_KEY: Not set")
    print("\n   Please set GEMINI_API_KEY in your .env file")
    sys.exit(1)

database_url = os.getenv('DATABASE_URL')
if database_url:
    # Mask password
    masked_url = database_url.split('@')[0].split(':')[0] + ':***@' + database_url.split('@')[1] if '@' in database_url else database_url
    print(f"   ✅ DATABASE_URL: {masked_url}")
else:
    print("   ⚠️  DATABASE_URL: Not set (database tests will be skipped)")

print(f"   ✅ GEMINI_MODEL: {os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')}")
print(f"   ✅ EMBEDDING_MODEL: {os.getenv('EMBEDDING_MODEL', 'text-embedding-004')}")
print(f"   ✅ VECTOR_DIMENSION: {os.getenv('VECTOR_DIMENSION', '768')}")

# Test imports
print("\n2. Testing Imports...")
try:
    import google.generativeai as genai
    print("   ✅ google.generativeai imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import google.generativeai: {e}")
    print("   Run: pip3 install google-generativeai")
    sys.exit(1)

try:
    from embeddings import EmbeddingGenerator
    print("   ✅ EmbeddingGenerator imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import EmbeddingGenerator: {e}")
    sys.exit(1)

try:
    from rag_query import RAGQueryPipeline
    print("   ✅ RAGQueryPipeline imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import RAGQueryPipeline: {e}")
    sys.exit(1)

# Test Gemini API connection
print("\n3. Testing Gemini API Connection...")
async def test_embeddings():
    try:
        generator = EmbeddingGenerator()
        print(f"   ✅ EmbeddingGenerator initialized")
        print(f"   ✅ Model: {generator.model}")
        print(f"   ✅ Dimensions: {generator.dimensions}")

        # Test single embedding
        print("\n   Testing embedding generation...")
        test_text = "Public procurement tender for office supplies"
        embedding = await generator.generate_embedding(test_text)

        print(f"   ✅ Generated embedding")
        print(f"   ✅ Vector dimension: {len(embedding)}")
        print(f"   ✅ Sample values: {embedding[:5]}")

        if len(embedding) != 768:
            print(f"   ❌ ERROR: Expected 768 dimensions, got {len(embedding)}")
            return False

        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

# Test RAG generation
async def test_rag():
    try:
        print("\n4. Testing RAG Generation...")
        genai.configure(api_key=gemini_key)

        model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        model = genai.GenerativeModel(model_name)
        print(f"   ✅ GenerativeModel initialized ({model_name})")

        test_prompt = "What is a public procurement tender?"
        response = model.generate_content(test_prompt)

        print(f"   ✅ Generated response")
        print(f"   ✅ Response length: {len(response.text)} chars")
        print(f"   ✅ Sample: {response.text[:100]}...")

        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

# Run tests
async def main():
    embeddings_ok = await test_embeddings()
    rag_ok = await test_rag()

    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    if embeddings_ok and rag_ok:
        print("✅ All tests passed!")
        print("\nNext steps:")
        print("1. Run database migration: psql < db/migrations/migrate_to_gemini_768.sql")
        print("2. Re-embed documents: python scripts/reembed_documents.py")
        print("3. Start backend: cd backend && uvicorn main:app --reload")
        return 0
    else:
        print("❌ Some tests failed")
        print("\nPlease check:")
        print("- GEMINI_API_KEY is valid")
        print("- google-generativeai is installed")
        print("- API quota is not exceeded")
        return 1

if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

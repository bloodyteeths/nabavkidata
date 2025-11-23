"""
Tests for Google Gemini embeddings module

Tests embedding generation, chunking, and vector storage with Gemini API
"""
import pytest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock
import google.generativeai as genai

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from embeddings import (
    TextChunker,
    EmbeddingGenerator,
    VectorStore,
    EmbeddingsPipeline,
    TextChunk
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_text():
    """Sample tender document text"""
    return """
    Јавен повик за набавка на канцелариски материјал.
    Постапката се спроведува согласно Законот за јавни набавки.

    Предмет на набавка: Канцелариски материјал за 2024 година.
    Проценета вредност: 500,000 МКД.
    Рок за достава: 30 дена од склучување договор.

    Критериум за избор: Најниска цена.
    Рок за поднесување понуди: 15.02.2024.
    """


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API embedding response (768 dimensions)"""
    return {
        'embedding': [0.1] * 768
    }


@pytest.fixture
def mock_gemini_batch_response():
    """Mock Gemini API batch embedding response"""
    return {
        'embedding': [
            [0.1] * 768,
            [0.2] * 768,
            [0.3] * 768
        ]
    }


# ============================================================================
# TEXT CHUNKER TESTS
# ============================================================================

class TestTextChunker:
    """Test text chunking functionality"""

    def test_chunk_short_text(self):
        """Short text should be single chunk"""
        chunker = TextChunker(chunk_size=500)
        text = "Short text that fits in one chunk"

        chunks = chunker.chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_index == 0

    def test_chunk_long_text(self, sample_text):
        """Long text should be split into multiple chunks"""
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)

        chunks = chunker.chunk_text(sample_text)

        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert len(chunk.text) > 0

    def test_chunk_with_metadata(self):
        """Chunks should preserve metadata"""
        chunker = TextChunker()
        text = "Test text"
        metadata = {"source": "test"}

        chunks = chunker.chunk_text(text, metadata)

        assert chunks[0].metadata == metadata

    def test_chunk_document_with_ids(self, sample_text):
        """Chunks should have tender and doc IDs"""
        chunker = TextChunker()

        chunks = chunker.chunk_document(
            text=sample_text,
            tender_id="TENDER-123",
            doc_id="DOC-456"
        )

        for chunk in chunks:
            assert chunk.tender_id == "TENDER-123"
            assert chunk.doc_id == "DOC-456"

    def test_empty_text(self):
        """Empty text should return no chunks"""
        chunker = TextChunker()

        chunks = chunker.chunk_text("")

        assert len(chunks) == 0


# ============================================================================
# EMBEDDING GENERATOR TESTS
# ============================================================================

class TestEmbeddingGenerator:
    """Test Gemini embedding generation"""

    @pytest.mark.asyncio
    async def test_generate_single_embedding(self, mock_gemini_response):
        """Test single embedding generation with Gemini"""
        with patch.object(genai, 'embed_content', return_value=mock_gemini_response):
            generator = EmbeddingGenerator(api_key="test-key")

            embedding = await generator.generate_embedding("Test text")

            assert len(embedding) == 768  # Gemini text-embedding-004
            assert all(isinstance(x, (int, float)) for x in embedding)

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings(self, mock_gemini_batch_response):
        """Test batch embedding generation"""
        with patch.object(genai, 'embed_content', return_value=mock_gemini_batch_response):
            generator = EmbeddingGenerator(api_key="test-key")

            texts = ["Text 1", "Text 2", "Text 3"]
            embeddings = await generator.generate_embeddings_batch(texts)

            assert len(embeddings) == 3
            assert all(len(emb) == 768 for emb in embeddings)

    @pytest.mark.asyncio
    async def test_embed_chunks(self, mock_gemini_batch_response):
        """Test embedding chunk objects"""
        with patch.object(genai, 'embed_content', return_value=mock_gemini_batch_response):
            generator = EmbeddingGenerator(api_key="test-key")

            chunks = [
                TextChunk(text="Chunk 1", chunk_index=0),
                TextChunk(text="Chunk 2", chunk_index=1),
                TextChunk(text="Chunk 3", chunk_index=2)
            ]

            results = await generator.embed_chunks(chunks)

            assert len(results) == 3
            for chunk, vector in results:
                assert isinstance(chunk, TextChunk)
                assert len(vector) == 768

    def test_missing_api_key(self):
        """Should raise error if API key missing"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                EmbeddingGenerator(api_key=None)

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Should handle API errors gracefully"""
        with patch.object(genai, 'embed_content', side_effect=Exception("API Error")):
            generator = EmbeddingGenerator(api_key="test-key")

            with pytest.raises(Exception):
                await generator.generate_embedding("Test")

    def test_default_model(self):
        """Should use text-embedding-004 by default"""
        generator = EmbeddingGenerator(api_key="test-key")
        assert generator.model == "models/text-embedding-004"
        assert generator.dimensions == 768


# ============================================================================
# VECTOR STORE TESTS
# ============================================================================

class TestVectorStore:
    """Test vector database operations"""

    @pytest.fixture
    def mock_db_conn(self):
        """Mock database connection"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={'embed_id': 'test-id'})
        conn.fetch = AsyncMock(return_value=[
            {
                'embed_id': 'id-1',
                'chunk_text': 'Test chunk',
                'chunk_index': 0,
                'tender_id': 'TENDER-123',
                'doc_id': 'DOC-456',
                'metadata': {},
                'similarity': 0.95
            }
        ])
        return conn

    @pytest.mark.asyncio
    async def test_store_embedding(self, mock_db_conn):
        """Test storing 768-dimensional embedding"""
        store = VectorStore("postgresql://test")
        store.conn = mock_db_conn

        vector = [0.1] * 768  # Gemini 768-dim vector
        embed_id = await store.store_embedding(
            vector=vector,
            chunk_text="Test chunk",
            chunk_index=0,
            tender_id="TENDER-123"
        )

        assert embed_id == "test-id"
        mock_db_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_similarity_search(self, mock_db_conn):
        """Test vector similarity search"""
        store = VectorStore("postgresql://test")
        store.conn = mock_db_conn

        query_vector = [0.1] * 768
        results = await store.similarity_search(query_vector, limit=5)

        assert len(results) == 1
        assert results[0]['similarity'] == 0.95
        assert results[0]['tender_id'] == 'TENDER-123'

    @pytest.mark.asyncio
    async def test_similarity_search_with_filter(self, mock_db_conn):
        """Test filtered similarity search"""
        store = VectorStore("postgresql://test")
        store.conn = mock_db_conn

        query_vector = [0.1] * 768
        results = await store.similarity_search(
            query_vector,
            limit=5,
            tender_id="TENDER-123"
        )

        assert mock_db_conn.fetch.called


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestEmbeddingsPipeline:
    """Test complete embeddings pipeline"""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, sample_text, mock_gemini_batch_response):
        """Test complete document processing pipeline with Gemini"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'embed_id': 'test-id'})
        mock_conn.transaction = Mock()
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock()
        mock_transaction.__aexit__ = AsyncMock()
        mock_conn.transaction.return_value = mock_transaction

        with patch('asyncpg.connect', return_value=mock_conn):
            with patch.object(genai, 'embed_content', return_value=mock_gemini_batch_response):
                pipeline = EmbeddingsPipeline(
                    database_url="postgresql://test",
                    gemini_api_key="test-key"
                )

                embed_ids = await pipeline.process_document(
                    text=sample_text,
                    tender_id="TENDER-123",
                    doc_id="DOC-456"
                )

                assert len(embed_ids) > 0


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])

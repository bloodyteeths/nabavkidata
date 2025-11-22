"""
Tests for embeddings pipeline

Tests text chunking, embedding generation, and vector storage
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from embeddings import (
    TextChunk,
    EmbeddingResult,
    TextChunker,
    EmbeddingGenerator,
    VectorStore,
    EmbeddingsPipeline
)


# Test Data

SAMPLE_TEXT_SHORT = """
Јавен повик за набавка на канцелариски материјали.
Референтен број: 2024-001-КАНЦ
Нарачател: Општина Скопје
"""

SAMPLE_TEXT_LONG = """
Јавен повик за избор на најповолна понуда за набавка на канцелариски материјали.

Референтен број: 2024-001-КАНЦ
Датум на објавување: 15.11.2024

Нарачател: Општина Скопје
Адреса: бул. Илинден 82, Скопје
Телефон: +389 2 3289 999

Предмет на набавка: Канцелариски материјали за потребите на општинската администрација
за период од 12 месеци. Набавката вклучува хартија, пишувачки прибор, фасцикли,
регистратори, коверти и друг канцелариски материјал.

CPV код: 30190000-7 (Разни опрема и производи)

Рок за доставување понуди: 30.11.2024 до 16:00 часот

Критериум за избор: Економски најповолна понуда

Проценета вредност: 500.000,00 МКД без ДДВ
"""

MACEDONIAN_TEXT_WITH_SENTENCES = """
Првата реченица е кратка. Втората реченица содржи малку повеќе информации за тестирање.
Третата реченица е најдолга од сите и содржи детални информации за целите на тестирањето
на функционалноста на системот за препознавање на граници меѓу реченици во македонски јазик.
"""


class TestTextChunker:
    """Test TextChunker class"""

    def test_initialization(self):
        """Test chunker initialization"""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        assert chunker.chunk_size == 100
        assert chunker.chunk_overlap == 20
        assert chunker.encoding is not None

    def test_chunk_short_text(self):
        """Test chunking text that fits in single chunk"""
        chunker = TextChunker(chunk_size=500)
        chunks = chunker.chunk_text(SAMPLE_TEXT_SHORT)

        assert len(chunks) == 1
        assert chunks[0].text == SAMPLE_TEXT_SHORT
        assert chunks[0].chunk_index == 0

    def test_chunk_long_text(self):
        """Test chunking text that requires multiple chunks"""
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        chunks = chunker.chunk_text(SAMPLE_TEXT_LONG)

        assert len(chunks) > 1
        # Verify chunk indices
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
        # Verify all chunks have content
        for chunk in chunks:
            assert len(chunk.text.strip()) > 0

    def test_chunk_empty_text(self):
        """Test chunking empty or whitespace text"""
        chunker = TextChunker()

        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   ") == []
        assert chunker.chunk_text("\n\n") == []

    def test_chunk_with_metadata(self):
        """Test chunking with metadata attachment"""
        chunker = TextChunker()
        metadata = {'source': 'test', 'tender_id': 'T-001'}
        chunks = chunker.chunk_text(SAMPLE_TEXT_SHORT, metadata=metadata)

        assert len(chunks) == 1
        assert chunks[0].metadata == metadata

    def test_sentence_boundary_breaking(self):
        """Test that chunks prefer sentence boundaries"""
        chunker = TextChunker(chunk_size=20, chunk_overlap=5)
        chunks = chunker.chunk_text(MACEDONIAN_TEXT_WITH_SENTENCES)

        # At least one chunk should end with sentence punctuation
        sentence_endings = ['.', '!', '?']
        has_sentence_break = any(
            chunk.text.strip()[-1] in sentence_endings
            for chunk in chunks
        )
        assert has_sentence_break

    def test_chunk_document(self):
        """Test chunk_document with IDs"""
        chunker = TextChunker()
        chunks = chunker.chunk_document(
            text=SAMPLE_TEXT_SHORT,
            tender_id='TENDER-123',
            doc_id='DOC-456',
            metadata={'type': 'tender_notice'}
        )

        assert len(chunks) == 1
        assert chunks[0].tender_id == 'TENDER-123'
        assert chunks[0].doc_id == 'DOC-456'
        assert chunks[0].metadata == {'type': 'tender_notice'}


class TestEmbeddingGenerator:
    """Test EmbeddingGenerator class"""

    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI API response"""
        return {
            'data': [
                {'embedding': [0.1] * 1536}
            ]
        }

    @pytest.fixture
    def mock_openai_batch_response(self):
        """Mock OpenAI batch API response"""
        return {
            'data': [
                {'embedding': [0.1] * 1536},
                {'embedding': [0.2] * 1536},
                {'embedding': [0.3] * 1536}
            ]
        }

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_initialization(self):
        """Test generator initialization"""
        generator = EmbeddingGenerator()
        assert generator.model == "text-embedding-ada-002"
        assert generator.dimensions == 1536
        assert generator.batch_size == 100

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('openai.Embedding.create')
    @pytest.mark.asyncio
    async def test_generate_embedding(self, mock_create):
        """Test single embedding generation"""
        mock_create.return_value = {
            'data': [{'embedding': [0.1] * 1536}]
        }

        generator = EmbeddingGenerator()
        vector = await generator.generate_embedding("Test text")

        assert len(vector) == 1536
        assert vector[0] == 0.1
        mock_create.assert_called_once()

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('openai.Embedding.create')
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self, mock_create):
        """Test batch embedding generation"""
        mock_create.return_value = {
            'data': [
                {'embedding': [0.1] * 1536},
                {'embedding': [0.2] * 1536}
            ]
        }

        generator = EmbeddingGenerator()
        texts = ["Text 1", "Text 2"]
        vectors = await generator.generate_embeddings_batch(texts)

        assert len(vectors) == 2
        assert len(vectors[0]) == 1536
        assert vectors[0][0] == 0.1
        assert vectors[1][0] == 0.2

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('openai.Embedding.create')
    @pytest.mark.asyncio
    async def test_embed_chunks(self, mock_create):
        """Test embedding TextChunk objects"""
        mock_create.return_value = {
            'data': [
                {'embedding': [0.1] * 1536},
                {'embedding': [0.2] * 1536}
            ]
        }

        generator = EmbeddingGenerator()
        chunks = [
            TextChunk(text="Chunk 1", chunk_index=0),
            TextChunk(text="Chunk 2", chunk_index=1)
        ]

        results = await generator.embed_chunks(chunks)

        assert len(results) == 2
        assert results[0][0].text == "Chunk 1"
        assert len(results[0][1]) == 1536
        assert results[1][0].text == "Chunk 2"
        assert len(results[1][1]) == 1536


class TestVectorStore:
    """Test VectorStore class"""

    @pytest.fixture
    def mock_conn(self):
        """Mock asyncpg connection"""
        conn = AsyncMock()
        return conn

    @patch.dict('os.environ', {'DATABASE_URL': 'postgresql://localhost/test'})
    def test_initialization(self):
        """Test vector store initialization"""
        store = VectorStore('postgresql://localhost/test')
        assert store.database_url == 'postgresql://localhost/test'
        assert store.conn is None

    @pytest.mark.asyncio
    async def test_store_embedding(self, mock_conn):
        """Test storing single embedding"""
        mock_conn.fetchrow.return_value = {'embed_id': 'test-uuid'}

        store = VectorStore('postgresql://localhost/test')
        store.conn = mock_conn

        vector = [0.1] * 1536
        embed_id = await store.store_embedding(
            vector=vector,
            chunk_text="Test chunk",
            chunk_index=0,
            tender_id="TENDER-123",
            doc_id="DOC-456",
            metadata={'test': 'data'}
        )

        assert embed_id == 'test-uuid'
        mock_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_similarity_search(self, mock_conn):
        """Test similarity search"""
        mock_conn.fetch.return_value = [
            {
                'embed_id': 'uuid-1',
                'chunk_text': 'Result 1',
                'chunk_index': 0,
                'tender_id': 'T-001',
                'doc_id': 'D-001',
                'metadata': {},
                'similarity': 0.95
            },
            {
                'embed_id': 'uuid-2',
                'chunk_text': 'Result 2',
                'chunk_index': 1,
                'tender_id': 'T-002',
                'doc_id': 'D-002',
                'metadata': {},
                'similarity': 0.85
            }
        ]

        store = VectorStore('postgresql://localhost/test')
        store.conn = mock_conn

        query_vector = [0.1] * 1536
        results = await store.similarity_search(query_vector, limit=5)

        assert len(results) == 2
        assert results[0]['similarity'] == 0.95
        assert results[1]['similarity'] == 0.85
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_similarity_search_with_tender_filter(self, mock_conn):
        """Test similarity search filtered by tender_id"""
        mock_conn.fetch.return_value = [
            {
                'embed_id': 'uuid-1',
                'chunk_text': 'Result 1',
                'chunk_index': 0,
                'tender_id': 'T-001',
                'doc_id': 'D-001',
                'metadata': {},
                'similarity': 0.95
            }
        ]

        store = VectorStore('postgresql://localhost/test')
        store.conn = mock_conn

        query_vector = [0.1] * 1536
        results = await store.similarity_search(
            query_vector,
            limit=5,
            tender_id='T-001'
        )

        assert len(results) == 1
        # Verify tender_id was passed to query
        call_args = mock_conn.fetch.call_args
        assert 'T-001' in call_args[0]


class TestEmbeddingsPipeline:
    """Test EmbeddingsPipeline class"""

    @patch.dict('os.environ', {
        'DATABASE_URL': 'postgresql://localhost/test',
        'OPENAI_API_KEY': 'test-key'
    })
    def test_initialization(self):
        """Test pipeline initialization"""
        pipeline = EmbeddingsPipeline()
        assert pipeline.chunker is not None
        assert pipeline.embedder is not None
        assert pipeline.vector_store is not None

    @patch.dict('os.environ', {
        'DATABASE_URL': 'postgresql://localhost/test',
        'OPENAI_API_KEY': 'test-key'
    })
    @patch('openai.Embedding.create')
    @pytest.mark.asyncio
    async def test_process_document(self, mock_create):
        """Test complete document processing pipeline"""
        # Mock OpenAI response
        mock_create.return_value = {
            'data': [{'embedding': [0.1] * 1536}]
        }

        # Mock vector store
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {'embed_id': 'test-uuid'}

        pipeline = EmbeddingsPipeline(chunk_size=500)
        pipeline.vector_store.conn = mock_conn

        # Process short text (single chunk)
        embed_ids = await pipeline.process_document(
            text=SAMPLE_TEXT_SHORT,
            tender_id='TENDER-123',
            doc_id='DOC-456',
            metadata={'test': 'data'}
        )

        assert len(embed_ids) == 1
        assert embed_ids[0] == 'test-uuid'

    @patch.dict('os.environ', {
        'DATABASE_URL': 'postgresql://localhost/test',
        'OPENAI_API_KEY': 'test-key'
    })
    @pytest.mark.asyncio
    async def test_process_empty_document(self):
        """Test processing empty document"""
        pipeline = EmbeddingsPipeline()

        # Mock vector store connection
        mock_conn = AsyncMock()
        pipeline.vector_store.conn = mock_conn

        embed_ids = await pipeline.process_document(
            text="",
            tender_id='TENDER-123'
        )

        assert embed_ids == []


# Integration-style tests (would require actual database)

@pytest.mark.integration
class TestEmbeddingsIntegration:
    """
    Integration tests for embeddings pipeline

    NOTE: These tests require:
    - PostgreSQL with pgvector extension
    - Valid DATABASE_URL
    - Valid OPENAI_API_KEY
    - embeddings table created
    """

    @pytest.mark.asyncio
    async def test_full_pipeline_integration(self):
        """Test complete pipeline with real database"""
        # This test would run against a real database
        # Skipped in unit tests
        pytest.skip("Requires database setup")

    @pytest.mark.asyncio
    async def test_macedonian_text_embedding(self):
        """Test embedding Macedonian text"""
        # This test would verify Cyrillic handling
        pytest.skip("Requires OpenAI API key")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

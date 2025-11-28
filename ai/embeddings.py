"""
AI Embeddings Generator - Vector embeddings for RAG

Features:
- Google Gemini text-embedding-004 (768 dimensions)
- Semantic text chunking (Cyrillic-aware)
- Batch processing for efficiency
- pgvector storage integration
- Macedonian language support
"""
import os
import sys
import logging
import asyncio
import asyncpg
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import google.generativeai as genai

# Import shared connection pool
from db_pool import get_pool, get_connection

# Import optimized chunker
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'embeddings'))
try:
    from embeddings.chunker import SemanticChunker, ChunkStrategy, TextChunk as OptimizedTextChunk
    OPTIMIZED_CHUNKER_AVAILABLE = True
except ImportError:
    OPTIMIZED_CHUNKER_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """Represents a text chunk ready for embedding"""
    text: str
    chunk_index: int
    tender_id: Optional[str] = None
    doc_id: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class EmbeddingResult:
    """Result of embedding generation"""
    embed_id: str
    vector: List[float]
    text: str
    chunk_index: int
    tender_id: Optional[str] = None
    doc_id: Optional[str] = None
    chunk_metadata: Optional[Dict] = None


class TextChunker:
    """
    Semantic text chunking with Cyrillic support

    Chunks text into semantic segments suitable for embeddings.
    Handles Macedonian language properly.

    NOTE: This class now uses the optimized chunker if available.
    """

    def __init__(
        self,
        chunk_size: int = 500,  # approximate tokens
        chunk_overlap: int = 50  # approximate tokens
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Use optimized chunker if available
        if OPTIMIZED_CHUNKER_AVAILABLE:
            self.semantic_chunker = SemanticChunker(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                strategy=ChunkStrategy.SEMANTIC
            )
            logger.info("Using optimized semantic chunker")
        else:
            self.semantic_chunker = None
            logger.info("Using legacy chunker (optimized chunker not available)")

    def _approximate_tokens(self, text: str) -> int:
        """
        Approximate token count for text
        Using simple heuristic: ~4 chars per token
        """
        return len(text) // 4

    def chunk_text(self, text: str, metadata: Optional[Dict] = None) -> List[TextChunk]:
        """
        Split text into chunks with overlap

        Args:
            text: Full document text
            metadata: Optional metadata to attach to chunks

        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []

        # Use optimized chunker if available
        if self.semantic_chunker:
            optimized_chunks = self.semantic_chunker.chunk_text(
                text=text,
                metadata=metadata
            )

            # Convert to legacy format
            chunks = [
                TextChunk(
                    text=chunk.text,
                    chunk_index=chunk.chunk_index,
                    metadata=chunk.metadata or {}
                )
                for chunk in optimized_chunks
            ]

            logger.info(f"Split text into {len(chunks)} chunks (optimized)")
            return chunks

        # Legacy chunker (fallback)
        # Split into sentences first
        sentences = self._split_sentences(text)

        if not sentences:
            return []

        chunks = []
        chunk_index = 0
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence_tokens = self._approximate_tokens(sentence)

            if current_size + sentence_tokens > self.chunk_size and current_chunk:
                # Create chunk from accumulated sentences
                chunk_text = ' '.join(current_chunk)
                chunks.append(TextChunk(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    metadata=metadata or {}
                ))
                chunk_index += 1

                # Start new chunk with overlap
                overlap_sentences = current_chunk[-2:] if len(current_chunk) >= 2 else current_chunk
                current_chunk = overlap_sentences
                current_size = sum(self._approximate_tokens(s) for s in current_chunk)

            current_chunk.append(sentence)
            current_size += sentence_tokens

        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(TextChunk(
                text=chunk_text,
                chunk_index=chunk_index,
                metadata=metadata or {}
            ))

        logger.info(f"Split text into {len(chunks)} chunks (legacy)")
        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences
        Works with both English and Macedonian punctuation
        """
        import re

        # Sentence boundaries (English + Macedonian)
        pattern = r'[.!?]+[\s\n]+'
        sentences = re.split(pattern, text)

        # Clean and filter empty
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    def chunk_document(
        self,
        text: str,
        tender_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[TextChunk]:
        """
        Chunk document and attach IDs

        Args:
            text: Document text
            tender_id: Associated tender ID
            doc_id: Document ID
            metadata: Additional metadata

        Returns:
            List of TextChunk with IDs attached
        """
        chunks = self.chunk_text(text, metadata)

        # Attach IDs
        for chunk in chunks:
            chunk.tender_id = tender_id
            chunk.doc_id = doc_id

        return chunks


class EmbeddingGenerator:
    """
    Generate embeddings using Google Gemini text-embedding-004

    Handles batching, rate limiting, and error recovery
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "models/text-embedding-004",
        batch_size: int = 100
    ):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")

        genai.configure(api_key=self.api_key)
        self.model = model
        self.batch_size = batch_size
        self.dimensions = 768  # text-embedding-004 dimensions

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for single text

        Args:
            text: Text to embed

        Returns:
            768-dimensional vector
        """
        try:
            # Gemini API call (synchronous, so run in thread)
            result = await asyncio.to_thread(
                genai.embed_content,
                model=self.model,
                content=text,
                task_type="retrieval_document"
            )

            vector = result['embedding']
            return vector

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    async def generate_embeddings_batch(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """
        Generate embeddings for batch of texts

        Args:
            texts: List of texts to embed

        Returns:
            List of vectors (one per text)
        """
        if not texts:
            return []

        try:
            # Ensure genai is configured with the current API key
            genai.configure(api_key=self.api_key)

            # Gemini batch embedding with retry for rate limits
            max_retries = 3
            retry_delay = 5

            for attempt in range(max_retries):
                try:
                    result = await asyncio.to_thread(
                        genai.embed_content,
                        model=self.model,
                        content=texts,
                        task_type="retrieval_document"
                    )
                    break  # Success
                except Exception as api_error:
                    error_str = str(api_error).lower()
                    if "rate" in error_str or "quota" in error_str or "429" in error_str:
                        if attempt < max_retries - 1:
                            logger.warning(f"Rate limit hit, waiting {retry_delay}s before retry {attempt + 2}/{max_retries}")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            raise
                    else:
                        raise

            # Extract vectors
            if isinstance(result['embedding'][0], list):
                vectors = result['embedding']
            else:
                # Single embedding returned as flat list
                vectors = [result['embedding']]

            logger.info(f"Generated {len(vectors)} embeddings")
            return vectors

        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise

    async def embed_chunks(
        self,
        chunks: List[TextChunk]
    ) -> List[Tuple[TextChunk, List[float]]]:
        """
        Generate embeddings for list of chunks

        Args:
            chunks: List of TextChunk objects

        Returns:
            List of (chunk, vector) tuples
        """
        if not chunks:
            return []

        results = []

        # Process in batches
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            texts = [chunk.text for chunk in batch]

            # Generate embeddings
            vectors = await self.generate_embeddings_batch(texts)

            # Pair chunks with vectors
            for chunk, vector in zip(batch, vectors):
                results.append((chunk, vector))

            logger.info(
                f"Embedded batch {i // self.batch_size + 1} "
                f"({len(batch)} chunks)"
            )

        return results


class VectorStore:
    """
    Store and retrieve vectors using pgvector

    Handles database operations for embeddings.
    Uses shared connection pool to prevent connection exhaustion.
    """

    def __init__(self, database_url: str):
        # database_url kept for compatibility but we use shared pool
        self.database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        self._pool = None

    async def connect(self):
        """Get reference to shared connection pool"""
        if not self._pool:
            self._pool = await get_pool()

    async def close(self):
        """
        Release reference to pool (does not close the shared pool).
        The shared pool is managed by db_pool module.
        """
        self._pool = None

    async def store_embedding(
        self,
        vector: List[float],
        chunk_text: str,
        chunk_index: int,
        tender_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Store single embedding in database

        Returns:
            embed_id (UUID)
        """
        # Convert vector list to pgvector format
        vector_str = '[' + ','.join(map(str, vector)) + ']'

        # Convert metadata dict to JSON string
        metadata_json = json.dumps(metadata or {})

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO embeddings (
                    vector, chunk_text, chunk_index,
                    tender_id, doc_id, metadata
                ) VALUES ($1::vector, $2, $3, $4, $5, $6::jsonb)
                RETURNING embed_id
            """,
                vector_str,
                chunk_text,
                chunk_index,
                tender_id,
                doc_id,
                metadata_json
            )

        return str(result['embed_id'])

    async def store_embeddings_batch(
        self,
        embeddings: List[Tuple[TextChunk, List[float]]]
    ) -> List[str]:
        """
        Store multiple embeddings efficiently

        Args:
            embeddings: List of (chunk, vector) tuples

        Returns:
            List of embed_ids
        """
        embed_ids = []

        # Use transaction for batch insert
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for chunk, vector in embeddings:
                    # Convert vector list to pgvector format
                    vector_str = '[' + ','.join(map(str, vector)) + ']'
                    metadata_json = json.dumps(chunk.metadata or {})

                    result = await conn.fetchrow("""
                        INSERT INTO embeddings (
                            vector, chunk_text, chunk_index,
                            tender_id, doc_id, metadata
                        ) VALUES ($1::vector, $2, $3, $4, $5, $6::jsonb)
                        RETURNING embed_id
                    """,
                        vector_str,
                        chunk.text,
                        chunk.chunk_index,
                        chunk.tender_id,
                        chunk.doc_id,
                        metadata_json
                    )
                    embed_ids.append(str(result['embed_id']))

        logger.info(f"Stored {len(embed_ids)} embeddings")
        return embed_ids

    async def similarity_search(
        self,
        query_vector: List[float],
        limit: int = 5,
        tender_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Find similar vectors using cosine similarity

        Args:
            query_vector: Query embedding
            limit: Number of results
            tender_id: Optional filter by tender

        Returns:
            List of results with similarity scores
        """
        # Convert vector list to pgvector format
        vector_str = '[' + ','.join(map(str, query_vector)) + ']'

        async with self._pool.acquire() as conn:
            if tender_id:
                # Filter by tender
                query = """
                    SELECT
                        embed_id,
                        chunk_text,
                        chunk_index,
                        tender_id,
                        doc_id,
                        metadata,
                        1 - (vector <=> $1::vector) as similarity
                    FROM embeddings
                    WHERE tender_id = $2
                    ORDER BY vector <=> $1::vector
                    LIMIT $3
                """
                rows = await conn.fetch(query, vector_str, tender_id, limit)
            else:
                # Search all embeddings
                query = """
                    SELECT
                        embed_id,
                        chunk_text,
                        chunk_index,
                        tender_id,
                        doc_id,
                        metadata,
                        1 - (vector <=> $1::vector) as similarity
                    FROM embeddings
                    ORDER BY vector <=> $1::vector
                    LIMIT $2
                """
                rows = await conn.fetch(query, vector_str, limit)

        results = [dict(row) for row in rows]
        logger.info(f"Found {len(results)} similar vectors")
        return results


class EmbeddingsPipeline:
    """
    Complete embeddings pipeline: chunk → embed → store

    Orchestrates the full workflow
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        chunk_size: int = 500,
        batch_size: int = 100
    ):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL not set")

        self.chunker = TextChunker(chunk_size=chunk_size)
        self.embedder = EmbeddingGenerator(
            api_key=gemini_api_key,
            batch_size=batch_size
        )
        self.vector_store = VectorStore(self.database_url)

    async def process_document(
        self,
        text: str,
        tender_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[str]:
        """
        Process document: chunk → embed → store

        Args:
            text: Document text
            tender_id: Associated tender
            doc_id: Document ID
            metadata: Additional metadata

        Returns:
            List of embed_ids created
        """
        logger.info(
            f"Processing document: tender={tender_id}, doc={doc_id}, "
            f"length={len(text)} chars"
        )

        # Connect to database
        await self.vector_store.connect()

        try:
            # 1. Chunk text
            chunks = self.chunker.chunk_document(
                text=text,
                tender_id=tender_id,
                doc_id=doc_id,
                metadata=metadata
            )

            if not chunks:
                logger.warning("No chunks generated from text")
                return []

            # 2. Generate embeddings
            embeddings = await self.embedder.embed_chunks(chunks)

            # 3. Store in database
            embed_ids = await self.vector_store.store_embeddings_batch(embeddings)

            logger.info(
                f"✓ Processed document: {len(chunks)} chunks, "
                f"{len(embed_ids)} embeddings stored"
            )

            return embed_ids

        finally:
            await self.vector_store.close()

    async def process_documents_batch(
        self,
        documents: List[Dict]
    ) -> Dict[str, List[str]]:
        """
        Process multiple documents

        Args:
            documents: List of dicts with keys: text, tender_id, doc_id, metadata

        Returns:
            Dict mapping doc_id → embed_ids
        """
        results = {}

        for doc in documents:
            embed_ids = await self.process_document(
                text=doc['text'],
                tender_id=doc.get('tender_id'),
                doc_id=doc.get('doc_id'),
                metadata=doc.get('metadata')
            )
            results[doc.get('doc_id', 'unknown')] = embed_ids

        return results


# Convenience function
async def embed_tender_document(
    text: str,
    tender_id: str,
    doc_id: Optional[str] = None
) -> List[str]:
    """
    Quick function to embed a tender document

    Usage:
        embed_ids = await embed_tender_document(text, 'TENDER-123', 'DOC-456')
    """
    pipeline = EmbeddingsPipeline()
    return await pipeline.process_document(text, tender_id, doc_id)

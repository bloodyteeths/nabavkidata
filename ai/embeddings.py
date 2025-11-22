"""
AI Embeddings Generator - Vector embeddings for RAG

Features:
- OpenAI ada-002 embeddings (1536 dimensions)
- Semantic text chunking (Cyrillic-aware)
- Batch processing for efficiency
- pgvector storage integration
- Macedonian language support
"""
import os
import logging
import asyncio
import asyncpg
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import tiktoken
import openai

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
    """

    def __init__(
        self,
        chunk_size: int = 500,  # tokens
        chunk_overlap: int = 50,  # tokens
        model: str = "gpt-3.5-turbo"
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.encoding_for_model(model)

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

        # Tokenize text
        tokens = self.encoding.encode(text)
        total_tokens = len(tokens)

        if total_tokens <= self.chunk_size:
            # Entire text fits in one chunk
            return [TextChunk(
                text=text,
                chunk_index=0,
                metadata=metadata or {}
            )]

        chunks = []
        chunk_index = 0
        start = 0

        while start < total_tokens:
            # Get chunk
            end = min(start + self.chunk_size, total_tokens)
            chunk_tokens = tokens[start:end]

            # Decode back to text
            chunk_text = self.encoding.decode(chunk_tokens)

            # Try to break at sentence boundary for last chunk
            if end == total_tokens or (end - start) < self.chunk_size:
                # Last chunk or short chunk - use as is
                pass
            else:
                # Try to find good break point
                chunk_text = self._break_at_sentence(chunk_text)

            chunks.append(TextChunk(
                text=chunk_text,
                chunk_index=chunk_index,
                metadata=metadata or {}
            ))

            chunk_index += 1
            start = end - self.chunk_overlap

        logger.info(f"Split text into {len(chunks)} chunks ({total_tokens} tokens)")
        return chunks

    def _break_at_sentence(self, text: str) -> str:
        """
        Try to break text at sentence boundary

        Works with both English and Macedonian punctuation
        """
        # Sentence endings (English + Macedonian)
        sentence_endings = ['. ', '! ', '? ', '.\n', '!\n', '?\n']

        # Try to find last sentence ending
        last_pos = -1
        for ending in sentence_endings:
            pos = text.rfind(ending)
            if pos > last_pos and pos > len(text) * 0.5:  # At least 50% through
                last_pos = pos

        if last_pos > 0:
            # Break at sentence
            return text[:last_pos + 1].strip()

        # No good break point found - return as is
        return text

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
    Generate embeddings using OpenAI ada-002

    Handles batching, rate limiting, and error recovery
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-ada-002",
        batch_size: int = 100
    ):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

        openai.api_key = self.api_key
        self.model = model
        self.batch_size = batch_size
        self.dimensions = 1536  # ada-002 dimensions

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for single text

        Args:
            text: Text to embed

        Returns:
            1536-dimensional vector
        """
        try:
            # OpenAI API call
            response = await asyncio.to_thread(
                openai.Embedding.create,
                input=text,
                model=self.model
            )

            vector = response['data'][0]['embedding']
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
            # OpenAI batch API call
            response = await asyncio.to_thread(
                openai.Embedding.create,
                input=texts,
                model=self.model
            )

            # Extract vectors in original order
            vectors = [item['embedding'] for item in response['data']]

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

    Handles database operations for embeddings
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None

    async def connect(self):
        """Establish database connection"""
        if not self.conn:
            self.conn = await asyncpg.connect(self.database_url)

    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()
            self.conn = None

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
        result = await self.conn.fetchrow("""
            INSERT INTO embeddings (
                vector, chunk_text, chunk_index,
                tender_id, doc_id, chunk_metadata
            ) VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING embed_id
        """,
            vector,
            chunk_text,
            chunk_index,
            tender_id,
            doc_id,
            metadata or {}
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
        async with self.conn.transaction():
            for chunk, vector in embeddings:
                embed_id = await self.store_embedding(
                    vector=vector,
                    chunk_text=chunk.text,
                    chunk_index=chunk.chunk_index,
                    tender_id=chunk.tender_id,
                    doc_id=chunk.doc_id,
                    metadata=chunk.metadata
                )
                embed_ids.append(embed_id)

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
        if tender_id:
            # Filter by tender
            query = """
                SELECT
                    embed_id,
                    chunk_text,
                    chunk_index,
                    tender_id,
                    doc_id,
                    chunk_metadata as metadata,
                    1 - (vector <=> $1::vector) as similarity
                FROM embeddings
                WHERE tender_id = $2
                ORDER BY vector <=> $1::vector
                LIMIT $3
            """
            rows = await self.conn.fetch(query, query_vector, tender_id, limit)
        else:
            # Search all embeddings
            query = """
                SELECT
                    embed_id,
                    chunk_text,
                    chunk_index,
                    tender_id,
                    doc_id,
                    chunk_metadata as metadata,
                    1 - (vector <=> $1::vector) as similarity
                FROM embeddings
                ORDER BY vector <=> $1::vector
                LIMIT $2
            """
            rows = await self.conn.fetch(query, query_vector, limit)

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
        openai_api_key: Optional[str] = None,
        chunk_size: int = 500,
        batch_size: int = 100
    ):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL not set")

        self.chunker = TextChunker(chunk_size=chunk_size)
        self.embedder = EmbeddingGenerator(
            api_key=openai_api_key,
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

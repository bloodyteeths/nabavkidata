"""
RAG/AI API endpoints
Question answering and semantic search
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
import time
import sys
import os

# Add AI module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../ai'))

from database import get_db
from models import QueryHistory, User
from schemas import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSource,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResult
)

# Import RAG components
try:
    from rag_query import RAGQueryPipeline, search_tenders as rag_search_tenders
    from embeddings import EmbeddingsPipeline
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("Warning: RAG modules not available. Install ai/ dependencies.")

router = APIRouter(prefix="/rag", tags=["rag"])


# ============================================================================
# RAG QUERY ENDPOINTS
# ============================================================================

@router.post("/query", response_model=RAGQueryResponse)
async def query_rag(
    request: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
    # current_user: User = Depends(get_current_user)  # TODO: Add auth
):
    """
    Ask question using RAG

    Request body:
    - question: User question
    - tender_id: Optional filter by specific tender
    - top_k: Number of chunks to retrieve (1-20)
    - conversation_history: Optional previous Q&A pairs

    Returns:
    - answer: Generated answer
    - sources: List of source documents
    - confidence: high/medium/low
    - query_time_ms: Query execution time
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="RAG service not available. Check configuration."
        )

    start_time = time.time()

    try:
        # Initialize RAG pipeline
        pipeline = RAGQueryPipeline(top_k=request.top_k)

        # Generate answer
        answer = await pipeline.generate_answer(
            question=request.question,
            tender_id=request.tender_id,
            conversation_history=request.conversation_history
        )

        # Calculate query time
        query_time_ms = int((time.time() - start_time) * 1000)

        # Save to query history
        # TODO: Add user_id from auth
        # query_history = QueryHistory(
        #     user_id=current_user.user_id,
        #     question=request.question,
        #     answer=answer.answer,
        #     sources=[...],
        #     confidence=answer.confidence,
        #     query_time_ms=query_time_ms
        # )
        # db.add(query_history)
        # await db.commit()

        # Convert sources to response format
        sources_response = [
            RAGSource(
                tender_id=source.tender_id,
                doc_id=source.doc_id,
                chunk_text=source.chunk_text,
                similarity=source.similarity,
                chunk_metadata=source.chunk_metadata
            )
            for source in answer.sources
        ]

        return RAGQueryResponse(
            question=answer.question,
            answer=answer.answer,
            sources=sources_response,
            confidence=answer.confidence,
            query_time_ms=query_time_ms,
            generated_at=answer.generated_at
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG query failed: {str(e)}"
        )


@router.post("/search", response_model=SemanticSearchResponse)
async def semantic_search(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Semantic search without answer generation

    Request body:
    - query: Search query
    - tender_id: Optional filter by tender
    - top_k: Number of results (1-50)

    Returns:
    - results: List of matching document chunks
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="RAG service not available. Check configuration."
        )

    try:
        # Perform semantic search
        results = await rag_search_tenders(
            query=request.query,
            top_k=request.top_k
        )

        # Filter by tender_id if specified
        if request.tender_id:
            results = [r for r in results if r.tender_id == request.tender_id]

        # Convert to response format
        search_results = [
            SemanticSearchResult(
                tender_id=result.tender_id,
                doc_id=result.doc_id,
                chunk_text=result.chunk_text,
                chunk_index=result.chunk_index,
                similarity=result.similarity,
                chunk_metadata=result.chunk_metadata
            )
            for result in results
        ]

        return SemanticSearchResponse(
            query=request.query,
            total_results=len(search_results),
            results=search_results
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Semantic search failed: {str(e)}"
        )


# ============================================================================
# EMBEDDING ENDPOINTS
# ============================================================================

@router.post("/embed/document")
async def embed_document(
    tender_id: str,
    doc_id: str,
    text: str,
    metadata: Optional[dict] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Embed document text

    Parameters:
    - tender_id: Tender ID
    - doc_id: Document ID
    - text: Document text to embed
    - metadata: Optional metadata

    Returns:
    - embed_ids: List of created embedding IDs
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Embedding service not available. Check configuration."
        )

    try:
        # Initialize pipeline
        pipeline = EmbeddingsPipeline()

        # Process document
        embed_ids = await pipeline.process_document(
            text=text,
            tender_id=tender_id,
            doc_id=doc_id,
            metadata=metadata
        )

        return {
            "success": True,
            "tender_id": tender_id,
            "doc_id": doc_id,
            "embed_count": len(embed_ids),
            "embed_ids": embed_ids
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Embedding failed: {str(e)}"
        )


@router.post("/embed/batch")
async def embed_documents_batch(
    documents: list,
    db: AsyncSession = Depends(get_db)
):
    """
    Embed multiple documents in batch

    Request body: List of documents with text, tender_id, doc_id

    Returns:
    - results: Dict mapping doc_id to embed_ids
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Embedding service not available. Check configuration."
        )

    try:
        # Initialize pipeline
        pipeline = EmbeddingsPipeline()

        # Process batch
        results = await pipeline.process_documents_batch(documents)

        return {
            "success": True,
            "total_documents": len(documents),
            "results": results
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch embedding failed: {str(e)}"
        )


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def rag_health_check():
    """
    Check RAG service health

    Returns RAG service status and configuration
    """
    return {
        "status": "healthy" if RAG_AVAILABLE else "unavailable",
        "rag_enabled": RAG_AVAILABLE,
        "gemini_configured": bool(os.getenv('GEMINI_API_KEY')),
        "database_configured": bool(os.getenv('DATABASE_URL')),
        "service": "rag-api",
        "model": "gemini-1.5-flash"
    }

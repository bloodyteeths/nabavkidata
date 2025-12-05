"""
RAG/AI API endpoints
Question answering and semantic search
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, AsyncGenerator
from datetime import datetime
import time
import sys
import os
import json
import asyncio

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
    SemanticSearchResult,
    EmbeddingResponse,
    BatchEmbeddingResponse
)
from api.auth import get_current_user

# Import fraud prevention for tier enforcement
try:
    from services.fraud_prevention import check_rate_limit, increment_query_count, TIER_LIMITS
    FRAUD_PREVENTION_AVAILABLE = True
except ImportError:
    FRAUD_PREVENTION_AVAILABLE = False
    print("Warning: Fraud prevention not available. Tier limits not enforced.")

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
    current_user: User = Depends(get_current_user)
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

    # PHASE 4: Check tier-based rate limits before processing query
    if FRAUD_PREVENTION_AVAILABLE:
        is_allowed, reason, info = await check_rate_limit(db, current_user.user_id, current_user)
        if not is_allowed:
            tier = getattr(current_user, 'subscription_tier', 'free').lower()
            tier_config = TIER_LIMITS.get(tier, TIER_LIMITS['free'])
            raise HTTPException(
                status_code=429,
                detail={
                    "message": reason,
                    "tier": tier,
                    "daily_limit": tier_config['daily_queries'],
                    "monthly_limit": tier_config['monthly_queries'],
                    "upgrade_url": "/pricing"
                }
            )

    start_time = time.time()

    try:
        # Initialize RAG pipeline
        pipeline = RAGQueryPipeline(top_k=request.top_k)

        # Generate answer
        answer = await pipeline.generate_answer(
            question=request.question,
            tender_id=request.tender_id,
            conversation_history=request.conversation_history,
            user_id=str(current_user.user_id)
        )

        # Calculate query time
        query_time_ms = int((time.time() - start_time) * 1000)

        # Save to query history
        try:
            query_history = QueryHistory(
                user_id=current_user.user_id,
                question=request.question,
                answer=answer.answer,
                confidence=answer.confidence,
                query_time_ms=query_time_ms,
                created_at=datetime.utcnow()
            )
            db.add(query_history)
            await db.commit()
        except Exception as db_error:
            # Log but don't fail the request if history save fails
            print(f"Warning: Failed to save query history: {db_error}")

        # PHASE 4: Increment query count for tier tracking
        if FRAUD_PREVENTION_AVAILABLE:
            try:
                await increment_query_count(db, current_user.user_id)
            except Exception as e:
                print(f"Warning: Failed to increment query count: {e}")

        # Convert sources to response format
        sources_response = []
        for source in answer.sources:
            # Convert doc_id to string if it's a UUID
            doc_id_str = str(source.doc_id) if source.doc_id else None

            # Parse chunk_metadata if it's a JSON string
            chunk_meta = source.chunk_metadata
            if isinstance(chunk_meta, str):
                try:
                    chunk_meta = json.loads(chunk_meta)
                except (json.JSONDecodeError, TypeError):
                    chunk_meta = {}
            elif chunk_meta is None:
                chunk_meta = {}

            sources_response.append(RAGSource(
                tender_id=source.tender_id,
                doc_id=doc_id_str,
                chunk_text=source.chunk_text,
                similarity=source.similarity,
                chunk_metadata=chunk_meta
            ))

        return RAGQueryResponse(
            question=answer.question,
            answer=answer.answer,
            sources=sources_response,
            confidence=answer.confidence,
            query_time_ms=query_time_ms,
            generated_at=answer.generated_at
        )

    except Exception as e:
        # Log the full error for debugging
        import traceback
        print(f"RAG query error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"RAG query failed: {str(e)}"
        )


@router.post("/query/stream")
async def query_rag_stream(
    request: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Ask question using RAG with streaming response

    Request body:
    - question: User question
    - tender_id: Optional filter by specific tender
    - top_k: Number of chunks to retrieve (1-20)
    - conversation_history: Optional previous Q&A pairs

    Returns:
    - Server-Sent Events (SSE) stream with:
      - sources: Source documents (sent first)
      - tokens: Answer tokens as they're generated
      - metadata: Confidence and timing info (sent last)
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="RAG service not available. Check configuration."
        )

    # PHASE 4: Check tier-based rate limits before processing query
    if FRAUD_PREVENTION_AVAILABLE:
        is_allowed, reason, info = await check_rate_limit(db, current_user.user_id, current_user)
        if not is_allowed:
            tier = getattr(current_user, 'subscription_tier', 'free').lower()
            tier_config = TIER_LIMITS.get(tier, TIER_LIMITS['free'])
            raise HTTPException(
                status_code=429,
                detail={
                    "message": reason,
                    "tier": tier,
                    "daily_limit": tier_config['daily_queries'],
                    "monthly_limit": tier_config['monthly_queries'],
                    "upgrade_url": "/pricing"
                }
            )

    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate SSE stream for RAG response"""
        start_time = time.time()

        try:
            # Initialize RAG pipeline
            pipeline = RAGQueryPipeline(top_k=request.top_k)

            # Import here to access streaming generation
            import google.generativeai as genai
            from rag_query import ContextAssembler, PromptBuilder

            # 1. Get query embedding and search
            yield f"data: {json.dumps({'type': 'status', 'message': 'Searching documents...'})}\n\n"

            from embeddings import EmbeddingGenerator, VectorStore
            embedder = EmbeddingGenerator()
            vector_store = VectorStore(pipeline.database_url)
            await vector_store.connect()

            try:
                # Generate query embedding
                query_vector = await embedder.generate_embedding(request.question)

                # Search for similar chunks
                raw_results = await vector_store.similarity_search(
                    query_vector=query_vector,
                    limit=request.top_k,
                    tender_id=request.tender_id
                )

                # Convert to SearchResult objects
                from rag_query import SearchResult
                search_results = [
                    SearchResult(
                        embed_id=str(r['embed_id']),
                        chunk_text=r['chunk_text'],
                        chunk_index=r['chunk_index'],
                        tender_id=r.get('tender_id'),
                        doc_id=r.get('doc_id'),
                        chunk_metadata=r.get('metadata', {}),
                        similarity=r['similarity']
                    )
                    for r in raw_results
                ]

                # Send sources
                sources_data = [
                    {
                        'tender_id': s.tender_id,
                        'doc_id': s.doc_id,
                        'chunk_text': s.chunk_text[:200] + '...' if len(s.chunk_text) > 200 else s.chunk_text,
                        'similarity': s.similarity,
                        'chunk_metadata': s.chunk_metadata
                    }
                    for s in search_results
                ]
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources_data})}\n\n"

                # 2. Assemble context and build prompt
                yield f"data: {json.dumps({'type': 'status', 'message': 'Generating answer...'})}\n\n"

                context_assembler = ContextAssembler()
                prompt_builder = PromptBuilder()

                context, sources_used = context_assembler.assemble_context(
                    search_results,
                    max_tokens=pipeline.max_context_tokens
                )

                prompt = prompt_builder.build_query_prompt(
                    question=request.question,
                    context=context,
                    conversation_history=request.conversation_history
                )

                # 3. Generate answer with streaming
                # Relaxed safety settings for business content
                model_obj = genai.GenerativeModel(pipeline.model)

                # Stream response
                full_answer = []
                response = model_obj.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=1000
                    ),
                    
                    stream=True
                )

                for chunk in response:
                    if chunk.text:
                        full_answer.append(chunk.text)
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.text})}\n\n"
                        await asyncio.sleep(0)  # Allow other tasks to run

                # 4. Send metadata
                answer_text = ''.join(full_answer)
                confidence = context_assembler.determine_confidence(sources_used)
                query_time_ms = int((time.time() - start_time) * 1000)

                yield f"data: {json.dumps({'type': 'metadata', 'confidence': confidence, 'query_time_ms': query_time_ms, 'model': pipeline.model})}\n\n"

                # 5. Send completion signal
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

                # Save to query history (async, non-blocking)
                try:
                    query_history = QueryHistory(
                        user_id=current_user.user_id,
                        question=request.question,
                        answer=answer_text,
                        confidence=confidence,
                        query_time_ms=query_time_ms,
                        created_at=datetime.utcnow()
                    )
                    db.add(query_history)
                    await db.commit()
                except Exception as e:
                    # Log but don't fail the stream
                    print(f"Warning: Failed to save query history: {e}")

            finally:
                await vector_store.close()

        except Exception as e:
            error_message = f"RAG streaming query failed: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post("/search", response_model=SemanticSearchResponse)
async def semantic_search(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        search_results = []
        for result in results:
            # Convert doc_id to string if it's a UUID
            doc_id_str = str(result.doc_id) if result.doc_id else None

            # Parse chunk_metadata if it's a JSON string
            chunk_meta = result.chunk_metadata
            if isinstance(chunk_meta, str):
                try:
                    chunk_meta = json.loads(chunk_meta)
                except (json.JSONDecodeError, TypeError):
                    chunk_meta = {}
            elif chunk_meta is None:
                chunk_meta = {}

            search_results.append(SemanticSearchResult(
                tender_id=result.tender_id,
                doc_id=doc_id_str,
                chunk_text=result.chunk_text,
                chunk_index=result.chunk_index,
                similarity=result.similarity,
                chunk_metadata=chunk_meta
            ))

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

@router.post("/embed/document", response_model=EmbeddingResponse)
async def embed_document(
    tender_id: str,
    doc_id: str,
    text: str,
    metadata: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
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


@router.post("/embed/batch", response_model=BatchEmbeddingResponse)
async def embed_documents_batch(
    documents: list,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Embed multiple documents in batch

    Request body: List of documents with text, tender_id, doc_id

    Returns:
    - results: Dict mapping doc_id to embed_ids

    Rate limits:
    - Free tier: 10 documents per request, 50 per day
    - Starter: 50 documents per request, 200 per day
    - Professional: 200 documents per request, 1000 per day
    - Enterprise: Unlimited
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Embedding service not available. Check configuration."
        )

    # Rate limiting based on user tier
    tier = getattr(current_user, 'plan_tier', 'free')
    tier_limits = {
        'free': {'per_request': 10, 'daily': 50},
        'starter': {'per_request': 50, 'daily': 200},
        'professional': {'per_request': 200, 'daily': 1000},
        'enterprise': {'per_request': 10000, 'daily': 100000},
    }

    limits = tier_limits.get(tier, tier_limits['free'])

    # Check per-request limit
    if len(documents) > limits['per_request']:
        raise HTTPException(
            status_code=429,
            detail=f"Too many documents. Your {tier} tier allows {limits['per_request']} documents per request. Upgrade for higher limits."
        )

    # Check daily limit (query usage tracking)
    try:
        from sqlalchemy import text
        daily_count_result = await db.execute(
            text("""
                SELECT COALESCE(SUM(JSONB_ARRAY_LENGTH(COALESCE(embed_ids::jsonb, '[]'::jsonb))), 0) as count
                FROM query_history
                WHERE user_id = :user_id
                  AND created_at > NOW() - INTERVAL '24 hours'
                  AND embed_ids IS NOT NULL
            """),
            {"user_id": str(current_user.user_id)}
        )
        daily_count = daily_count_result.scalar() or 0

        if daily_count + len(documents) > limits['daily']:
            raise HTTPException(
                status_code=429,
                detail=f"Daily embedding limit exceeded. Your {tier} tier allows {limits['daily']} embeddings per day. Used: {daily_count}."
            )
    except HTTPException:
        raise
    except Exception as e:
        # Log but don't fail if rate limit check fails
        print(f"Warning: Rate limit check failed: {e}")

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
        "model": os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
    }

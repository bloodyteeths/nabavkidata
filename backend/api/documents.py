"""
Document API endpoints
Document retrieval and management

Security:
- List/view documents: Requires authentication
- Create/delete documents: Requires admin role
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional, Dict, List, Any
from uuid import UUID
import os
import json
import hashlib
import asyncio
from datetime import datetime
import re

from database import get_db
from models import Document, Tender, User
from schemas import DocumentResponse, DocumentListResponse, DocumentCreate, MessageResponse, DocumentContentResponse
from middleware.rbac import get_current_user, require_admin

router = APIRouter(prefix="/documents", tags=["documents"])

# Import Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = bool(os.getenv('GEMINI_API_KEY'))
    if GEMINI_AVAILABLE:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
except ImportError:
    GEMINI_AVAILABLE = False


# ============================================================================
# AI DOCUMENT SUMMARIZATION
# ============================================================================

async def summarize_document_with_ai(content_text: str) -> Dict[str, Any]:
    """
    Use Gemini AI to summarize document content and extract key information.

    Args:
        content_text: The extracted text from the document

    Returns:
        Dictionary with:
        - summary: Brief summary in Macedonian (2-3 sentences)
        - key_requirements: List of extracted requirements
        - items_mentioned: List of products/items with quantities

    Raises:
        Exception: If AI service fails
    """
    if not GEMINI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI service not configured. Set GEMINI_API_KEY environment variable."
        )

    if not content_text or len(content_text.strip()) < 50:
        return {
            "summary": "Документот е премал или празен за анализа.",
            "key_requirements": [],
            "items_mentioned": []
        }

    # Truncate content to fit context window (keep first 8000 chars for summary)
    content_preview = content_text[:8000]

    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

    prompt = f"""Анализирај го следниот документ од јавна набавка и обезбеди:

1. Кратко резиме (2-3 реченици на македонски јазик) што опишува главната цел и содржина на документот
2. Список на клучни барања/услови (максимум 10 најважни барања)
3. Список на производи/услуги споменати во документот (со количини ако се достапни)

ДОКУМЕНТ:
{content_preview}

Врати резултат во JSON формат:
{{
  "summary": "Кратко резиме на 2-3 реченици...",
  "key_requirements": [
    "Барање 1",
    "Барање 2",
    "Барање 3"
  ],
  "items_mentioned": [
    {{
      "name": "Име на производ/услуга",
      "quantity": "100",
      "unit": "парчиња",
      "notes": "Дополнителни белешки ако има"
    }}
  ]
}}

Важно:
- Резимето да биде на македонски јазик
- Барањата да бидат јасни и конкретни
- Производите да се реални ставки од документот
- Ако нема податоци, врати празни низи

JSON:"""

    try:
        def _sync_generate():
            # No safety settings to avoid blocks
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.2,  # Low temperature for consistent extraction
                    max_output_tokens=2000
                )
            )
            try:
                return response.text
            except ValueError:
                return "{}"

        response_text = await asyncio.to_thread(_sync_generate)

        # Clean up response - extract JSON from markdown if needed
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        # Parse JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise ValueError("Could not parse AI response as JSON")

        # Validate structure
        return {
            "summary": result.get("summary", "Нема достапно резиме."),
            "key_requirements": result.get("key_requirements", [])[:10],  # Limit to 10
            "items_mentioned": result.get("items_mentioned", [])[:20]  # Limit to 20
        }

    except Exception as e:
        print(f"AI document summarization failed: {e}")
        # Return fallback
        return {
            "summary": "Автоматско резиме не е достапно за овој документ.",
            "key_requirements": [],
            "items_mentioned": []
        }


def compute_content_hash(content_text: str) -> str:
    """Compute SHA-256 hash of content for cache invalidation"""
    if not content_text:
        return ""
    return hashlib.sha256(content_text.encode('utf-8')).hexdigest()


# ============================================================================
# DOCUMENT ENDPOINTS
# ============================================================================


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    tender_id: Optional[str] = None,
    extraction_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List documents with optional filtering. Requires authentication."""
    query = select(Document)
    filters = []

    if tender_id:
        filters.append(Document.tender_id == tender_id)
    if extraction_status:
        filters.append(Document.extraction_status == extraction_status)

    if filters:
        query = query.where(and_(*filters))

    # Count total
    count_query = select(func.count()).select_from(Document)
    if filters:
        count_query = count_query.where(and_(*filters))
    total = await db.scalar(count_query)

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentListResponse(
        total=total,
        items=[DocumentResponse.from_orm(d) for d in documents]
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get document by ID. Requires authentication."""
    query = select(Document).where(Document.doc_id == doc_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse.from_orm(document)


@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(
    document: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create new document. Requires admin role."""
    # Verify tender exists
    tender_query = select(Tender).where(Tender.tender_id == document.tender_id)
    tender_result = await db.execute(tender_query)
    if not tender_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Tender not found")

    db_document = Document(**document.dict())
    db.add(db_document)
    await db.commit()
    await db.refresh(db_document)

    return DocumentResponse.from_orm(db_document)


@router.delete("/{doc_id}", response_model=MessageResponse)
async def delete_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete document. Requires admin role."""
    query = select(Document).where(Document.doc_id == doc_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.delete(document)
    await db.commit()

    return MessageResponse(message="Document deleted successfully")


@router.get("/{doc_id}/content", response_model=DocumentContentResponse)
async def get_document_content(
    doc_id: UUID,
    generate_ai_summary: bool = Query(True, description="Generate AI summary if not cached"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get document content with full extracted text, metadata, and AI summary.
    Requires authentication.

    Returns:
    - Full content_text from document
    - Content preview (first 500 chars)
    - Word count
    - Table detection (checks for table-like patterns)
    - File metadata and download URL
    - AI-generated summary (cached)
    - Key requirements extracted
    - Items mentioned in document

    Query Parameters:
    - generate_ai_summary: If True (default), generates AI summary if not cached
    """
    query = select(Document).where(Document.doc_id == doc_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Extract content text
    content_text = document.content_text or ""

    # Generate content preview (first 500 chars)
    content_preview = content_text[:500] if content_text else None

    # Calculate word count
    word_count = len(content_text.split()) if content_text else 0

    # Detect tables - look for table-like patterns in content
    has_tables = False
    if content_text:
        # Check for common table indicators: multiple rows with consistent separators
        # Look for patterns like: pipe-separated (|), tab-separated, or multiple consecutive lines with numbers
        table_patterns = [
            r'\|.*\|.*\|',  # Pipe-separated tables
            r'\t.*\t.*\t',  # Tab-separated tables
            r'^\s*\d+\.?\s+.*\s+\d+',  # Numbered rows with numbers in columns
        ]
        for pattern in table_patterns:
            if re.search(pattern, content_text, re.MULTILINE):
                has_tables = True
                break

    # Determine file type from file_name or mime_type
    file_type = None
    if document.file_name:
        if document.file_name.lower().endswith('.pdf'):
            file_type = 'pdf'
        elif document.file_name.lower().endswith(('.doc', '.docx')):
            file_type = 'word'
        elif document.file_name.lower().endswith(('.xls', '.xlsx')):
            file_type = 'excel'
        else:
            file_type = 'other'
    elif document.mime_type:
        if 'pdf' in document.mime_type.lower():
            file_type = 'pdf'
        elif 'word' in document.mime_type.lower() or 'msword' in document.mime_type.lower():
            file_type = 'word'
        elif 'excel' in document.mime_type.lower() or 'spreadsheet' in document.mime_type.lower():
            file_type = 'excel'
        else:
            file_type = 'other'

    # AI Summary generation (with caching)
    ai_summary = document.ai_summary
    key_requirements = document.key_requirements or []
    items_mentioned = document.items_mentioned or []

    # Check if we need to generate AI summary
    should_generate = (
        generate_ai_summary and
        GEMINI_AVAILABLE and
        content_text and
        len(content_text) >= 50 and
        (
            not document.ai_summary or  # No summary exists
            document.content_hash != compute_content_hash(content_text)  # Content changed
        )
    )

    if should_generate:
        try:
            # Generate AI summary
            ai_result = await summarize_document_with_ai(content_text)

            # Update document with AI summary
            document.ai_summary = ai_result["summary"]
            document.key_requirements = ai_result["key_requirements"]
            document.items_mentioned = ai_result["items_mentioned"]
            document.content_hash = compute_content_hash(content_text)
            document.ai_extracted_at = datetime.utcnow()

            # Save to database
            await db.commit()
            await db.refresh(document)

            # Update response values
            ai_summary = document.ai_summary
            key_requirements = document.key_requirements
            items_mentioned = document.items_mentioned

        except Exception as e:
            print(f"Failed to generate AI summary: {e}")
            # Continue without AI summary (graceful degradation)

    return DocumentContentResponse(
        doc_id=document.doc_id,
        file_name=document.file_name,
        file_type=file_type,
        content_text=content_text,
        content_preview=content_preview,
        word_count=word_count,
        has_tables=has_tables,
        extraction_status=document.extraction_status,
        file_url=document.file_url,
        tender_id=document.tender_id,
        created_at=document.uploaded_at,
        ai_summary=ai_summary,
        key_requirements=key_requirements,
        items_mentioned=items_mentioned
    )

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
import httpx
from datetime import datetime
import re

from database import get_db
from models import Document, Tender, User
from schemas import DocumentResponse, DocumentListResponse, DocumentCreate, MessageResponse, DocumentContentResponse
from middleware.rbac import get_current_user, require_admin
from middleware.entitlements import require_module
from config.plans import ModuleName

router = APIRouter(prefix="/documents", tags=["documents"])

# Import Gemini
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = bool(os.getenv('GEMINI_API_KEY'))
    if GEMINI_AVAILABLE:
        _genai_client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
except ImportError:
    GEMINI_AVAILABLE = False
    _genai_client = None


# ============================================================================
# AI DOCUMENT SUMMARIZATION
# ============================================================================

def _clean_ocr_text(text: str) -> str:
    """Clean OCR-extracted text: remove junk lines, normalize whitespace."""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip lines that are mostly non-alphanumeric (OCR noise)
        alnum = sum(1 for c in line if c.isalnum() or c in ' .,;:!?()-/')
        if len(line) > 0 and alnum / len(line) < 0.4:
            continue
        # Skip very short lines (1-3 chars) that are likely OCR fragments
        if len(line) <= 3 and not line[-1].isdigit():
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)


def _is_gibberish(text: str) -> bool:
    """Detect if OCR text is gibberish (unreadable)."""
    if not text or len(text.strip()) < 50:
        return True

    # Sample the first 2000 chars for quality check
    sample = text[:2000]

    # Count Cyrillic + Latin alphabetic characters vs total
    alpha_chars = sum(1 for c in sample if c.isalpha())
    total_chars = len(sample.replace('\n', '').replace(' ', ''))
    if total_chars == 0:
        return True

    alpha_ratio = alpha_chars / total_chars
    # Good text is >50% alphabetic; gibberish is mostly symbols
    if alpha_ratio < 0.35:
        return True

    # Check for recognizable Macedonian/Latin words (at least some should appear)
    words = re.findall(r'[а-яА-ЯёЁa-zA-Z]{3,}', sample)
    if len(words) < 5:
        return True

    # Average word length check — gibberish has very short "words"
    if words:
        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len < 2.5:
            return True

    return False


def _parse_json_response(response_text: str) -> dict:
    """Parse JSON from Gemini response, handling markdown wrappers and nested JSON."""
    text = response_text.strip()
    # Strip markdown code fences
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e1:
        print(f"Direct JSON parse failed: {e1}")
        print(f"Response repr (first 200): {repr(text[:200])}")
        # Try to find JSON object in response
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError as e2:
                print(f"Regex JSON parse also failed: {e2}")
        # Last resort: try to extract summary field from truncated JSON
        summary_match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if summary_match:
            print(f"Recovered summary from truncated JSON")
            reqs_matches = re.findall(r'"key_requirements"\s*:\s*\[(.*?)\]', text, re.DOTALL)
            reqs = []
            if reqs_matches:
                reqs = re.findall(r'"((?:[^"\\]|\\.)*)"', reqs_matches[0])
            return {"summary": summary_match.group(1), "key_requirements": reqs, "items_mentioned": []}

        print(f"Failed to parse Gemini response (first 500 chars): {text[:500]}")
        raise ValueError("Could not parse AI response as JSON")


async def summarize_pdf_with_vision(file_url: str) -> Dict[str, Any]:
    """
    Download PDF from URL and use Gemini vision to analyze it directly.
    Fallback for documents where OCR text is gibberish.
    """
    if not GEMINI_AVAILABLE:
        raise Exception("Gemini not available")

    # Download the PDF
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(file_url)
        resp.raise_for_status()
        pdf_bytes = resp.content

    if len(pdf_bytes) < 100:
        raise Exception("PDF too small or empty")

    # Limit to 20MB for Gemini
    if len(pdf_bytes) > 20 * 1024 * 1024:
        raise Exception("PDF too large for vision analysis")

    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

    prompt = """Анализирај го овој PDF документ од јавна набавка и обезбеди:

1. Кратко резиме (2-3 реченици на македонски јазик) што опишува главната цел и содржина на документот
2. Список на клучни барања/услови (максимум 10 најважни барања)
3. Список на производи/услуги споменати во документот (со количини ако се достапни)

Врати резултат во JSON формат:
{
  "summary": "Кратко резиме на 2-3 реченици...",
  "key_requirements": [
    "Барање 1",
    "Барање 2"
  ],
  "items_mentioned": [
    {
      "name": "Име на производ/услуга",
      "quantity": "100",
      "unit": "парчиња",
      "notes": "Дополнителни белешки ако има"
    }
  ]
}

Важно:
- Резимето да биде на македонски јазик
- Барањата да бидат јасни и конкретни
- Производите да се реални ставки од документот
- Ако нема податоци, врати празни низи

JSON:"""

    def _sync_vision():
        # Determine mime type from URL or default to PDF
        mime = 'application/pdf'
        lower_url = file_url.lower()
        if lower_url.endswith('.doc') or ('fname=' in lower_url and '.doc' in lower_url and '.docx' not in lower_url):
            mime = 'application/msword'
        elif lower_url.endswith('.docx') or ('fname=' in lower_url and '.docx' in lower_url):
            mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif lower_url.endswith('.xls') or ('fname=' in lower_url and '.xls' in lower_url and '.xlsx' not in lower_url):
            mime = 'application/vnd.ms-excel'
        elif lower_url.endswith('.xlsx') or ('fname=' in lower_url and '.xlsx' in lower_url):
            mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        doc_part = genai_types.Part.from_bytes(data=pdf_bytes, mime_type=mime)
        response = _genai_client.models.generate_content(
            model=model_name,
            contents=[doc_part, prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=2000,
                response_mime_type="application/json"
            )
        )
        try:
            return response.text
        except ValueError:
            return "{}"

    response_text = await asyncio.to_thread(_sync_vision)
    result = _parse_json_response(response_text)

    return {
        "summary": result.get("summary", "Нема достапно резиме."),
        "key_requirements": result.get("key_requirements", [])[:10],
        "items_mentioned": result.get("items_mentioned", [])[:20]
    }


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

    # Check text quality — gibberish OCR text can't be summarized from text alone
    if _is_gibberish(content_text):
        return {
            "summary": "Документот не може да се анализира — текстот е нечитлив (лош OCR квалитет). Отворете го оригиналниот документ за детали.",
            "key_requirements": [],
            "items_mentioned": []
        }

    # Clean OCR noise before sending to AI
    cleaned_text = _clean_ocr_text(content_text)

    # Truncate content to fit context window (keep first 8000 chars for summary)
    content_preview = cleaned_text[:8000]

    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

    prompt = f"""Анализирај го следниот документ од јавна набавка и обезбеди:

1. Кратко резиме (2-3 реченици на македонски јазик) што опишува главната цел и содржина на документот
2. Список на клучни барања/услови (максимум 10 најважни барања)
3. Список на производи/услуги споменати во документот (со количини ако се достапни)

ВАЖНО: Текстот е извлечен преку OCR и може да содржи мали грешки. Игнорирај ги нечитливите делови и фокусирај се на читливиот текст. Ако документот е претежно нечитлив, наведи го тоа во резимето.

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
            response = _genai_client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=4000,
                    response_mime_type="application/json"
                )
            )
            try:
                return response.text
            except ValueError:
                return "{}"

        response_text = await asyncio.to_thread(_sync_generate)
        result = _parse_json_response(response_text)

        return {
            "summary": result.get("summary", "Нема достапно резиме."),
            "key_requirements": result.get("key_requirements", [])[:10],
            "items_mentioned": result.get("items_mentioned", [])[:20]
        }

    except Exception as e:
        print(f"AI document summarization failed: {e}")
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


@router.get("/{doc_id}/content", response_model=DocumentContentResponse, dependencies=[Depends(require_module(ModuleName.DOCUMENT_EXTRACTION))])
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

    # If source text is gibberish, return a clear message instead of AI analysis
    text_is_gibberish = _is_gibberish(content_text) if content_text else False

    # Detect if cached summary is a failed/fallback placeholder
    _fallback_prefixes = ("Автоматско резиме не е достапно", "Документот не може да се анализира", "Документот е премал")
    has_real_summary = document.ai_summary and not document.ai_summary.startswith(_fallback_prefixes)

    # Check if we need to generate AI summary
    should_generate = (
        generate_ai_summary and
        GEMINI_AVAILABLE and
        content_text and
        len(content_text) >= 50 and
        not text_is_gibberish and
        (
            not has_real_summary or  # No real summary exists (or has fallback)
            document.content_hash != compute_content_hash(content_text)  # Content changed
        )
    )

    # Vision fallback: when OCR text is gibberish/empty but we have a file URL, use Gemini vision
    should_use_vision = (
        generate_ai_summary and
        GEMINI_AVAILABLE and
        document.file_url and
        (text_is_gibberish or not content_text) and
        not has_real_summary
    )

    if should_use_vision:
        try:
            print(f"Using Gemini vision for gibberish doc {doc_id} — URL: {document.file_url}")
            ai_result = await summarize_pdf_with_vision(document.file_url)

            document.ai_summary = ai_result["summary"]
            document.key_requirements = ai_result["key_requirements"]
            document.items_mentioned = ai_result["items_mentioned"]
            document.content_hash = compute_content_hash(content_text or "vision")
            document.ai_extracted_at = datetime.utcnow()

            await db.commit()
            await db.refresh(document)

            ai_summary = document.ai_summary
            key_requirements = document.key_requirements
            items_mentioned = document.items_mentioned
        except Exception as e:
            print(f"Vision PDF analysis failed for {doc_id}: {e}")
            ai_summary = "Документот не може да се анализира — текстот е нечитлив (лош OCR квалитет). Отворете го оригиналниот документ за детали."
            key_requirements = []
            items_mentioned = []
    elif text_is_gibberish and content_text and not document.ai_summary:
        # No file_url or Gemini unavailable — show warning
        ai_summary = "Документот не може да се анализира — текстот е нечитлив (лош OCR квалитет). Отворете го оригиналниот документ за детали."
        key_requirements = []
        items_mentioned = []

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

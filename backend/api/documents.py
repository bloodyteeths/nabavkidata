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
from typing import Optional
from uuid import UUID

from database import get_db
from models import Document, Tender, User
from schemas import DocumentResponse, DocumentListResponse, DocumentCreate, MessageResponse
from middleware.rbac import get_current_user, require_admin

router = APIRouter(prefix="/documents", tags=["documents"])


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

"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID


# ============================================================================
# TENDER SCHEMAS
# ============================================================================

class TenderBase(BaseModel):
    """Base tender schema"""
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    procuring_entity: Optional[str] = None
    opening_date: Optional[date] = None
    closing_date: Optional[date] = None
    publication_date: Optional[date] = None
    estimated_value_mkd: Optional[Decimal] = None
    estimated_value_eur: Optional[Decimal] = None
    actual_value_mkd: Optional[Decimal] = None
    actual_value_eur: Optional[Decimal] = None
    cpv_code: Optional[str] = None
    status: Optional[str] = "open"
    winner: Optional[str] = None
    source_url: Optional[str] = None
    language: str = "mk"


class TenderCreate(TenderBase):
    """Schema for creating tender"""
    tender_id: str


class TenderUpdate(BaseModel):
    """Schema for updating tender (all fields optional)"""
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    procuring_entity: Optional[str] = None
    opening_date: Optional[date] = None
    closing_date: Optional[date] = None
    publication_date: Optional[date] = None
    estimated_value_mkd: Optional[Decimal] = None
    estimated_value_eur: Optional[Decimal] = None
    actual_value_mkd: Optional[Decimal] = None
    actual_value_eur: Optional[Decimal] = None
    cpv_code: Optional[str] = None
    status: Optional[str] = None
    winner: Optional[str] = None
    source_url: Optional[str] = None
    language: Optional[str] = None


class TenderResponse(TenderBase):
    """Schema for tender response"""
    tender_id: str
    scraped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TenderListResponse(BaseModel):
    """Schema for paginated tender list"""
    total: int
    page: int
    page_size: int
    items: List[TenderResponse]


# ============================================================================
# DOCUMENT SCHEMAS
# ============================================================================

class DocumentBase(BaseModel):
    """Base document schema"""
    doc_type: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    content_text: Optional[str] = None
    extraction_status: str = "pending"
    file_size_bytes: Optional[int] = None
    page_count: Optional[int] = None
    mime_type: Optional[str] = None


class DocumentCreate(DocumentBase):
    """Schema for creating document"""
    tender_id: str


class DocumentResponse(DocumentBase):
    """Schema for document response"""
    doc_id: UUID
    tender_id: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema for document list"""
    total: int
    items: List[DocumentResponse]


# ============================================================================
# RAG/AI SCHEMAS
# ============================================================================

class RAGQueryRequest(BaseModel):
    """Request schema for RAG queries"""
    question: str = Field(..., min_length=1, max_length=1000, description="User question")
    tender_id: Optional[str] = Field(None, description="Filter by specific tender")
    top_k: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Previous Q&A pairs for context"
    )


class RAGSource(BaseModel):
    """Source document for RAG answer"""
    tender_id: Optional[str]
    doc_id: Optional[str]
    chunk_text: str
    similarity: float
    chunk_metadata: Optional[Dict[str, Any]] = None


class RAGQueryResponse(BaseModel):
    """Response schema for RAG queries"""
    question: str
    answer: str
    sources: List[RAGSource]
    confidence: str  # 'high', 'medium', 'low'
    query_time_ms: int
    generated_at: datetime


class SemanticSearchRequest(BaseModel):
    """Request schema for semantic search"""
    query: str = Field(..., min_length=1, max_length=500)
    tender_id: Optional[str] = None
    top_k: int = Field(10, ge=1, le=50)


class SemanticSearchResult(BaseModel):
    """Single search result"""
    tender_id: Optional[str]
    doc_id: Optional[str]
    chunk_text: str
    chunk_index: int
    similarity: float
    chunk_metadata: Optional[Dict[str, Any]] = None


class SemanticSearchResponse(BaseModel):
    """Response schema for semantic search"""
    query: str
    total_results: int
    results: List[SemanticSearchResult]


class EmbeddingResponse(BaseModel):
    """Response schema for document embedding"""
    success: bool
    tender_id: str
    doc_id: str
    embed_count: int
    embed_ids: List[str]


class BatchEmbeddingResponse(BaseModel):
    """Response schema for batch document embedding"""
    success: bool
    total_documents: int
    results: Dict[str, Any]


# ============================================================================
# USER & AUTH SCHEMAS
# ============================================================================

class UserCreate(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = None

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response"""
    user_id: UUID
    email: str
    full_name: Optional[str]
    subscription_tier: str
    email_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserResponse


# ============================================================================
# SEARCH & FILTER SCHEMAS
# ============================================================================

class TenderSearchRequest(BaseModel):
    """Request schema for tender search/filter"""
    query: Optional[str] = Field(None, description="Text search query")
    category: Optional[str] = None
    procuring_entity: Optional[str] = None
    status: Optional[str] = None
    cpv_code: Optional[str] = None
    min_value_mkd: Optional[Decimal] = None
    max_value_mkd: Optional[Decimal] = None
    opening_date_from: Optional[date] = None
    opening_date_to: Optional[date] = None
    closing_date_from: Optional[date] = None
    closing_date_to: Optional[date] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    sort_by: Optional[str] = Field("created_at", description="Field to sort by")
    sort_order: Optional[str] = Field("desc", description="asc or desc")


# ============================================================================
# ALERT SCHEMAS
# ============================================================================

class AlertCreate(BaseModel):
    """Schema for creating alert"""
    name: str = Field(..., min_length=1, max_length=255)
    filters: Dict[str, Any] = Field(..., description="Filter criteria for alerts")
    frequency: str = Field("daily", description="daily, weekly, or instant")
    is_active: bool = True


class AlertUpdate(BaseModel):
    """Schema for updating alert"""
    name: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    frequency: Optional[str] = None
    is_active: Optional[bool] = None


class AlertResponse(BaseModel):
    """Schema for alert response"""
    alert_id: UUID
    user_id: UUID
    name: str
    filters: Dict[str, Any]
    frequency: str
    is_active: bool
    last_triggered: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    """Schema for alert list"""
    total: int
    items: List[AlertResponse]


# ============================================================================
# NOTIFICATION SCHEMAS
# ============================================================================

class NotificationResponse(BaseModel):
    """Schema for notification response"""
    notification_id: UUID
    alert_id: Optional[UUID]
    tender_id: Optional[str]
    message: str
    is_read: bool
    sent_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Schema for notification list"""
    total: int
    unread_count: int
    items: List[NotificationResponse]


# ============================================================================
# SUBSCRIPTION SCHEMAS
# ============================================================================

class SubscriptionResponse(BaseModel):
    """Schema for subscription response"""
    subscription_id: UUID
    user_id: UUID
    tier: str
    status: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool

    class Config:
        from_attributes = True


# ============================================================================
# ANALYTICS SCHEMAS
# ============================================================================

class TenderStats(BaseModel):
    """Tender statistics"""
    total_tenders: int
    open_tenders: int
    closed_tenders: int
    total_value_mkd: Optional[Decimal]
    avg_value_mkd: Optional[Decimal]
    tenders_by_category: Dict[str, int]
    tenders_by_month: Dict[str, int]


class UserUsageStats(BaseModel):
    """User usage statistics"""
    total_queries: int
    queries_this_month: int
    favorite_categories: List[str]
    active_alerts: int
    query_history: List[Dict[str, Any]]


# ============================================================================
# UTILITY SCHEMAS
# ============================================================================

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    timestamp: datetime
    database: Optional[str] = None
    version: str = "1.0.0"

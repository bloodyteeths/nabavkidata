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
    source_category: Optional[str] = Field("active", description="Source category: active, awarded, cancelled, historical")

    # NEW FIELDS - Added 2025-11-24
    procedure_type: Optional[str] = None
    contract_signing_date: Optional[date] = None
    contract_duration: Optional[str] = None
    contracting_entity_category: Optional[str] = None
    procurement_holder: Optional[str] = None
    bureau_delivery_date: Optional[date] = None

    # Contact Information
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    # Additional Fields
    num_bidders: Optional[int] = None
    evaluation_method: Optional[str] = None

    # Requirements / Contract Details - Added 2025-11-27
    payment_terms: Optional[str] = None
    delivery_location: Optional[str] = None
    security_deposit_mkd: Optional[Decimal] = None
    performance_guarantee_mkd: Optional[Decimal] = None


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

    # NEW FIELDS - Added 2025-11-24
    procedure_type: Optional[str] = None
    contract_signing_date: Optional[date] = None
    contract_duration: Optional[str] = None
    contracting_entity_category: Optional[str] = None
    procurement_holder: Optional[str] = None
    bureau_delivery_date: Optional[date] = None

    # Requirements / Contract Details - Added 2025-11-27
    payment_terms: Optional[str] = None
    delivery_location: Optional[str] = None
    security_deposit_mkd: Optional[Decimal] = None
    performance_guarantee_mkd: Optional[Decimal] = None


class TenderResponse(TenderBase):
    """Schema for tender response"""
    tender_id: str
    scraped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    effective_status: Optional[str] = None  # Computed: considers closing_date

    class Config:
        from_attributes = True

    @validator('effective_status', pre=True, always=True)
    def compute_effective_status(cls, v, values):
        """
        Compute effective status based on closing_date:
        - If status is 'awarded' or 'cancelled' -> use as-is
        - If status is 'open' but closing_date < today -> 'closed'
        - Otherwise -> use original status
        """
        status = values.get('status', 'open')
        closing_date = values.get('closing_date')

        if status in ('awarded', 'cancelled'):
            return status

        if status == 'open' and closing_date:
            from datetime import date as date_type
            today = date_type.today()
            if closing_date < today:
                return 'closed'

        return status


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

    # AI Extraction fields (Phase 2.2)
    ai_summary: Optional[str] = None
    key_requirements: Optional[List[str]] = None
    items_mentioned: Optional[List[Dict[str, Any]]] = None


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


class DocumentContentResponse(BaseModel):
    """Schema for document content with full text and metadata"""
    doc_id: UUID
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    content_text: Optional[str] = None
    content_preview: Optional[str] = None
    word_count: int
    has_tables: bool
    extraction_status: str
    file_url: Optional[str] = None
    tender_id: str
    created_at: datetime

    # AI Extraction fields (Phase 2.2)
    ai_summary: Optional[str] = None
    key_requirements: Optional[List[str]] = None
    items_mentioned: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


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
    context_type: Optional[str] = Field(
        None,
        description="Context source: None=vector search, 'alerts'=user's alert matches"
    )
    session_id: Optional[str] = Field(
        None,
        description="Chat session ID for persistent memory. Auto-created if not provided."
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
    session_id: Optional[str] = None


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


class ChatFeedbackRequest(BaseModel):
    """Request schema for chat feedback"""
    session_id: Optional[str] = Field(None, description="Chat session ID")
    message_id: str = Field(..., description="Message ID being rated")
    question: str = Field(..., description="User's question")
    answer: str = Field(..., description="AI's answer")
    helpful: bool = Field(..., description="Whether the answer was helpful")
    comment: Optional[str] = Field(None, max_length=1000, description="Optional user comment")


class ChatFeedbackResponse(BaseModel):
    """Response schema for chat feedback"""
    success: bool
    feedback_id: int
    message: str


# ============================================================================
# USER & AUTH SCHEMAS
# ============================================================================

class UserCreate(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = None
    referral_code: Optional[str] = None

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
    role: Optional[str] = "user"
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
    source_category: Optional[str] = Field(None, description="Source category: active, awarded, cancelled, historical")
    # Estimated value filters (MKD)
    min_value_mkd: Optional[Decimal] = Field(None, description="Minimum estimated value in MKD")
    max_value_mkd: Optional[Decimal] = Field(None, description="Maximum estimated value in MKD")
    # Estimated value filters (EUR)
    min_value_eur: Optional[Decimal] = Field(None, description="Minimum estimated value in EUR")
    max_value_eur: Optional[Decimal] = Field(None, description="Maximum estimated value in EUR")
    opening_date_from: Optional[date] = None
    opening_date_to: Optional[date] = None
    closing_date_from: Optional[date] = None
    closing_date_to: Optional[date] = None

    # NEW FILTER FIELDS - Added 2025-11-24
    procedure_type: Optional[str] = None
    contracting_entity_category: Optional[str] = None
    contract_signing_date_from: Optional[date] = None
    contract_signing_date_to: Optional[date] = None

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


# ============================================================================
# PRODUCT SEARCH SCHEMAS
# ============================================================================

class ProductItemResponse(BaseModel):
    """Schema for product item response"""
    id: int
    tender_id: str
    document_id: Optional[UUID] = None
    item_number: Optional[int] = None
    lot_number: Optional[str] = None
    name: str
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    specifications: Optional[Dict[str, Any]] = None
    cpv_code: Optional[str] = None
    extraction_confidence: Optional[Decimal] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProductSearchRequest(BaseModel):
    """Request schema for product search"""
    query: str = Field(..., min_length=1, max_length=500, description="Search query for product names")
    year: Optional[int] = Field(None, description="Filter by year (based on tender opening date)")
    cpv_code: Optional[str] = Field(None, description="Filter by CPV code prefix")
    min_quantity: Optional[Decimal] = Field(None, description="Minimum quantity filter")
    max_quantity: Optional[Decimal] = Field(None, description="Maximum quantity filter")
    min_price: Optional[Decimal] = Field(None, description="Minimum unit price filter")
    max_price: Optional[Decimal] = Field(None, description="Maximum unit price filter")
    procuring_entity: Optional[str] = Field(None, description="Filter by procuring entity")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class ProductSearchResult(BaseModel):
    """Single product search result with tender context"""
    id: int
    name: str
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    specifications: Optional[Dict[str, Any]] = None
    cpv_code: Optional[str] = None
    extraction_confidence: Optional[Decimal] = None
    # Tender context
    tender_id: str
    tender_title: Optional[str] = None
    procuring_entity: Optional[str] = None
    opening_date: Optional[date] = None
    status: Optional[str] = None
    winner: Optional[str] = None


class ProductSearchResponse(BaseModel):
    """Response schema for product search"""
    query: str
    total: int
    page: int
    page_size: int
    items: List[ProductSearchResult]


class ProductAggregation(BaseModel):
    """Aggregated product statistics"""
    product_name: str
    total_quantity: Optional[Decimal] = None
    avg_unit_price: Optional[Decimal] = None
    min_unit_price: Optional[Decimal] = None
    max_unit_price: Optional[Decimal] = None
    tender_count: int
    years: List[int] = []


class ProductAggregationResponse(BaseModel):
    """Response schema for product aggregation"""
    query: str
    aggregations: List[ProductAggregation]


# ============================================================================
# E-PAZAR SCHEMAS
# ============================================================================

class EPazarTenderBase(BaseModel):
    """Base e-Pazar tender schema"""
    title: str
    description: Optional[str] = None
    contracting_authority: Optional[str] = None
    contracting_authority_id: Optional[str] = None
    estimated_value_mkd: Optional[Decimal] = None
    estimated_value_eur: Optional[Decimal] = None
    awarded_value_mkd: Optional[Decimal] = None
    awarded_value_eur: Optional[Decimal] = None
    procedure_type: Optional[str] = None
    status: str = "active"
    publication_date: Optional[date] = None
    closing_date: Optional[date] = None
    award_date: Optional[date] = None
    contract_date: Optional[date] = None
    contract_number: Optional[str] = None
    contract_duration: Optional[str] = None
    cpv_code: Optional[str] = None
    category: Optional[str] = None
    source_url: Optional[str] = None
    source_category: str = "epazar"
    language: str = "mk"


class EPazarTenderResponse(EPazarTenderBase):
    """Response schema for e-Pazar tender"""
    tender_id: str
    scraped_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    items: Optional[List[Dict[str, Any]]] = None
    offers: Optional[List[Dict[str, Any]]] = None
    awarded_items: Optional[List[Dict[str, Any]]] = None
    documents: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


class EPazarTenderListResponse(BaseModel):
    """Schema for paginated e-Pazar tender list"""
    total: int
    page: int
    page_size: int
    items: List[Dict[str, Any]]


class EPazarItemResponse(BaseModel):
    """Response schema for e-Pazar BOQ item"""
    item_id: Optional[UUID] = None
    tender_id: str
    line_number: int
    item_name: str
    item_description: Optional[str] = None
    item_code: Optional[str] = None
    cpv_code: Optional[str] = None
    quantity: Decimal
    unit: Optional[str] = None
    estimated_unit_price_mkd: Optional[Decimal] = None
    estimated_unit_price_eur: Optional[Decimal] = None
    estimated_total_price_mkd: Optional[Decimal] = None
    estimated_total_price_eur: Optional[Decimal] = None
    specifications: Optional[Dict[str, Any]] = None
    delivery_date: Optional[date] = None
    delivery_location: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EPazarOfferResponse(BaseModel):
    """Response schema for e-Pazar offer/bid"""
    offer_id: Optional[UUID] = None
    tender_id: str
    supplier_name: str
    supplier_tax_id: Optional[str] = None
    supplier_address: Optional[str] = None
    supplier_city: Optional[str] = None
    supplier_contact_email: Optional[str] = None
    supplier_contact_phone: Optional[str] = None
    offer_number: Optional[str] = None
    offer_date: Optional[datetime] = None
    total_bid_mkd: Decimal
    total_bid_eur: Optional[Decimal] = None
    evaluation_score: Optional[Decimal] = None
    ranking: Optional[int] = None
    is_winner: bool = False
    offer_status: str = "submitted"
    rejection_reason: Optional[str] = None
    disqualified: bool = False
    disqualification_date: Optional[date] = None
    documents_submitted: Optional[Dict[str, Any]] = None
    notes: Optional[Dict[str, Any]] = None
    items_count: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EPazarAwardedItemResponse(BaseModel):
    """Response schema for e-Pazar awarded contract item"""
    awarded_item_id: Optional[UUID] = None
    tender_id: str
    item_id: Optional[UUID] = None
    offer_id: Optional[UUID] = None
    supplier_name: str
    supplier_tax_id: Optional[str] = None
    contract_item_number: Optional[str] = None
    contracted_quantity: Decimal
    contracted_unit_price_mkd: Decimal
    contracted_total_mkd: Decimal
    contracted_unit_price_eur: Optional[Decimal] = None
    contracted_total_eur: Optional[Decimal] = None
    planned_delivery_date: Optional[date] = None
    actual_delivery_date: Optional[date] = None
    delivery_location: Optional[str] = None
    received_quantity: Optional[Decimal] = None
    quality_score: Optional[Decimal] = None
    quality_notes: Optional[str] = None
    on_time: Optional[bool] = None
    billed_amount_mkd: Optional[Decimal] = None
    paid_amount_mkd: Optional[Decimal] = None
    payment_date: Optional[date] = None
    status: str = "pending"
    completion_date: Optional[date] = None
    item_name: Optional[str] = None
    item_description: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EPazarDocumentResponse(BaseModel):
    """Response schema for e-Pazar document"""
    doc_id: Optional[UUID] = None
    tender_id: str
    doc_type: Optional[str] = None
    doc_category: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    content_text: Optional[str] = None
    extraction_status: str = "pending"
    file_size_bytes: Optional[int] = None
    page_count: Optional[int] = None
    mime_type: Optional[str] = None
    file_hash: Optional[str] = None
    upload_date: Optional[date] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EPazarSupplierResponse(BaseModel):
    """Response schema for e-Pazar supplier"""
    supplier_id: Optional[UUID] = None
    company_name: str
    tax_id: Optional[str] = None
    company_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None
    total_offers: int = 0
    total_wins: int = 0
    win_rate: Optional[Decimal] = None
    total_contract_value_mkd: Optional[Decimal] = None
    avg_bid_amount_mkd: Optional[Decimal] = None
    industries: Optional[Dict[str, Any]] = None
    recent_offers: Optional[List[Dict[str, Any]]] = None
    recent_wins: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EPazarStatsResponse(BaseModel):
    """Response schema for e-Pazar statistics"""
    total_tenders: int
    total_items: int
    total_offers: int
    total_suppliers: int
    total_documents: int
    total_value_mkd: Decimal
    awarded_value_mkd: Decimal
    status_breakdown: Dict[str, Dict[str, Any]]
    recent_tenders: List[Dict[str, Any]]
    top_suppliers: List[Dict[str, Any]]


# ============================================================================
# TENDER CHAT SCHEMAS (AI Chat with specific tender)
# ============================================================================

class TenderChatRequest(BaseModel):
    """Request schema for tender chat"""
    question: str = Field(..., min_length=1, max_length=1000, description="User question about the tender")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default=[],
        description="Previous Q&A pairs for context"
    )


class TenderChatSource(BaseModel):
    """Source document reference for tender chat"""
    doc_id: str
    file_name: Optional[str] = None
    excerpt: str = Field(..., description="Relevant excerpt from document")


class TenderChatResponse(BaseModel):
    """Response schema for tender chat"""
    answer: str = Field(..., description="AI-generated answer in Macedonian")
    sources: List[TenderChatSource] = Field(default=[], description="Document sources used")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score based on data availability")
    tender_id: str


# ============================================================================
# BID ADVISOR SCHEMAS
# ============================================================================

class BidRecommendation(BaseModel):
    """Single bid recommendation strategy"""
    strategy: str  # "aggressive", "balanced", "safe"
    recommended_bid: float
    win_probability: float  # 0-1
    reasoning: str


class BidAdvisorResponse(BaseModel):
    """AI-powered bid advisor response"""
    tender_id: str
    tender_title: str
    estimated_value: Optional[float]
    cpv_code: Optional[str]
    category: Optional[str]
    procuring_entity: Optional[str]
    market_analysis: Dict[str, Any]
    historical_data: Dict[str, Any]
    recommendations: List[BidRecommendation]
    competitor_insights: List[Dict[str, Any]]
    ai_summary: str
    generated_at: str


# ============================================================================
# COMPETITOR TRACKING SCHEMAS
# ============================================================================

class TrackedCompetitorCreate(BaseModel):
    """Schema for adding a competitor to track"""
    company_name: str = Field(..., min_length=1, max_length=500, description="Company name to track")
    tax_id: Optional[str] = Field(None, max_length=100, description="Optional tax ID")
    notes: Optional[str] = Field(None, description="Optional notes about this competitor")


class TrackedCompetitorResponse(BaseModel):
    """Schema for tracked competitor response"""
    tracking_id: UUID
    user_id: UUID
    company_name: str
    tax_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TrackedCompetitorListResponse(BaseModel):
    """Schema for list of tracked competitors"""
    total: int
    items: List[TrackedCompetitorResponse]


class CompetitorTender(BaseModel):
    """Single tender participation"""
    tender_id: str
    title: str
    procuring_entity: Optional[str] = None
    bid_amount_mkd: Optional[Decimal] = None
    estimated_value_mkd: Optional[Decimal] = None
    is_winner: bool = False
    rank: Optional[int] = None
    closing_date: Optional[date] = None
    status: Optional[str] = None


class CompetitorStatsResponse(BaseModel):
    """Detailed competitor statistics"""
    company_name: str
    total_bids: int
    total_wins: int
    win_rate: Optional[float] = None
    avg_bid_discount: Optional[float] = None
    top_cpv_codes: List[Dict[str, Any]] = []
    top_categories: List[Dict[str, Any]] = []
    recent_tenders: List[CompetitorTender] = []
    last_updated: Optional[datetime] = None


class CompetitorSearchResult(BaseModel):
    """Search result for companies"""
    company_name: str
    tax_id: Optional[str] = None
    total_bids: int = 0
    total_wins: int = 0
    win_rate: Optional[float] = None
    total_contract_value: Optional[Decimal] = None


class CompetitorSearchResponse(BaseModel):
    """Response for competitor search"""
    total: int
    items: List[CompetitorSearchResult]

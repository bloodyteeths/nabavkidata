"""
SQLAlchemy ORM Models for nabavkidata.com
Matches db/schema.sql structure exactly
"""
from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, ForeignKey, Boolean, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

from database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(20), default="user")  # admin, moderator, user
    subscription_tier = Column(String(50), default="free")
    stripe_customer_id = Column(String(255))
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserSession(Base):
    """Track active user sessions for single-device enforcement"""
    __tablename__ = "user_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, index=True)
    device_info = Column(Text)
    ip_address = Column(INET)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class Organization(Base):
    __tablename__ = "organizations"

    org_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    org_type = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class Tender(Base):
    __tablename__ = "tenders"

    tender_id = Column(String(100), primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(String(255), index=True)
    procuring_entity = Column(String(500))
    opening_date = Column(Date, index=True)
    closing_date = Column(Date, index=True)
    publication_date = Column(Date)
    estimated_value_mkd = Column(Numeric(15, 2))
    estimated_value_eur = Column(Numeric(15, 2))
    actual_value_mkd = Column(Numeric(15, 2))
    actual_value_eur = Column(Numeric(15, 2))
    cpv_code = Column(String(50), index=True)
    status = Column(String(50), default="open", index=True)
    winner = Column(String(500))
    source_url = Column(Text)
    language = Column(String(10), default="mk")
    scraped_at = Column(DateTime)
    source_category = Column(String(50), default="active", index=True)  # active, awarded, cancelled, opendata_*

    # EXTENDED FIELDS - Added 2025-11-24
    procedure_type = Column(String(200), nullable=True, index=True)
    contract_signing_date = Column(Date, nullable=True)
    contract_duration = Column(String(100), nullable=True)
    contracting_entity_category = Column(String(200), nullable=True, index=True)
    procurement_holder = Column(String(500), nullable=True)
    bureau_delivery_date = Column(Date, nullable=True)

    # PHASE 3 ADDITIONS - Contact & Financial Data
    contact_person = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(100), nullable=True)
    num_bidders = Column(Integer, nullable=True)
    security_deposit_mkd = Column(Numeric(15, 2), nullable=True)
    performance_guarantee_mkd = Column(Numeric(15, 2), nullable=True)
    payment_terms = Column(Text, nullable=True)
    evaluation_method = Column(String(200), nullable=True)
    award_criteria = Column(JSONB, nullable=True)
    has_lots = Column(Boolean, default=False)
    num_lots = Column(Integer, nullable=True)
    amendment_count = Column(Integer, default=0)
    last_amendment_date = Column(Date, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"

    doc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(String(100), ForeignKey("tenders.tender_id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type = Column(String(100))
    file_name = Column(String(500))
    file_path = Column(Text)
    file_url = Column(Text)
    content_text = Column(Text)
    extraction_status = Column(String(50), default="pending", index=True)
    file_size_bytes = Column(Integer)
    page_count = Column(Integer)
    mime_type = Column(String(100))
    uploaded_at = Column(DateTime, default=datetime.utcnow)

class Embedding(Base):
    __tablename__ = "embeddings"

    embed_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.doc_id", ondelete="CASCADE"), index=True)
    tender_id = Column(String(100), ForeignKey("tenders.tender_id", ondelete="CASCADE"), index=True)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer)
    vector = Column(Vector(768))
    chunk_metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

class QueryHistory(Base):
    __tablename__ = "query_history"

    query_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text)
    sources = Column(JSONB)
    confidence = Column(Numeric(3, 2))
    query_time_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class Subscription(Base):
    __tablename__ = "subscriptions"

    subscription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    stripe_subscription_id = Column(String(255), unique=True)
    stripe_customer_id = Column(String(255))
    tier = Column(String(50))
    status = Column(String(50))
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, default=False)
    cancelled_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    filters = Column(JSONB)
    frequency = Column(String(50), default="daily")
    is_active = Column(Boolean, default=True, index=True)
    last_triggered = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.alert_id", ondelete="CASCADE"))
    tender_id = Column(String(100), ForeignKey("tenders.tender_id", ondelete="CASCADE"))
    message = Column(Text)
    is_read = Column(Boolean, default=False, index=True)
    sent_at = Column(DateTime, default=datetime.utcnow)

class UsageTracking(Base):
    __tablename__ = "usage_tracking"

    tracking_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), index=True)
    action_type = Column(String(100), nullable=False, index=True)
    tracking_metadata = Column(JSONB)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class AuditLog(Base):
    __tablename__ = "audit_log"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), index=True)
    action = Column(String(255), nullable=False)
    details = Column(JSONB)
    ip_address = Column(INET)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class SystemConfig(Base):
    __tablename__ = "system_config"

    config_key = Column(String(255), primary_key=True)
    config_value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ScrapingJob(Base):
    __tablename__ = "scraping_jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(50), nullable=False, default="running", index=True)  # running, completed, failed
    tenders_scraped = Column(Integer, default=0)
    documents_scraped = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    error_message = Column(Text)
    spider_name = Column(String(100))
    incremental = Column(Boolean, default=True)
    last_scraped_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

# PHASE 3: COMPREHENSIVE PROCUREMENT DATA MODELS

class TenderLot(Base):
    """Individual lots/items within a tender"""
    __tablename__ = "tender_lots"

    lot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(String(100), ForeignKey("tenders.tender_id", ondelete="CASCADE"), nullable=False, index=True)
    lot_number = Column(String(50))
    lot_title = Column(Text)
    lot_description = Column(Text)
    estimated_value_mkd = Column(Numeric(15, 2))
    estimated_value_eur = Column(Numeric(15, 2))
    actual_value_mkd = Column(Numeric(15, 2))
    actual_value_eur = Column(Numeric(15, 2))
    cpv_code = Column(String(50))
    winner = Column(String(500))
    quantity = Column(String(200))
    unit = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class TenderBidder(Base):
    """Bidder/participant information for tenders"""
    __tablename__ = "tender_bidders"

    bidder_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(String(100), ForeignKey("tenders.tender_id", ondelete="CASCADE"), nullable=False, index=True)
    lot_id = Column(UUID(as_uuid=True), ForeignKey("tender_lots.lot_id", ondelete="CASCADE"), nullable=True)
    company_name = Column(String(500), nullable=False, index=True)
    company_tax_id = Column(String(100))
    company_address = Column(Text)
    bid_amount_mkd = Column(Numeric(15, 2))
    bid_amount_eur = Column(Numeric(15, 2))
    is_winner = Column(Boolean, default=False, index=True)
    rank = Column(Integer)  # Ranking in evaluation
    disqualified = Column(Boolean, default=False)
    disqualification_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class TenderAmendment(Base):
    """Tender modifications/amendments"""
    __tablename__ = "tender_amendments"

    amendment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(String(100), ForeignKey("tenders.tender_id", ondelete="CASCADE"), nullable=False, index=True)
    amendment_date = Column(Date, nullable=False, index=True)
    amendment_type = Column(String(100))  # deadline_extension, value_change, clarification, etc.
    field_changed = Column(String(100))
    old_value = Column(Text)
    new_value = Column(Text)
    reason = Column(Text)
    announcement_url = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class ProcuringEntity(Base):
    """Procuring entity/institution profiles"""
    __tablename__ = "procuring_entities"

    entity_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_name = Column(String(500), nullable=False, unique=True, index=True)
    entity_type = Column(String(200))  # ministry, municipality, public company, etc.
    category = Column(String(200), index=True)
    tax_id = Column(String(100))
    address = Column(Text)
    city = Column(String(200), index=True)
    contact_person = Column(String(255))
    contact_email = Column(String(255))
    contact_phone = Column(String(100))
    website = Column(Text)
    total_tenders = Column(Integer, default=0)
    total_value_mkd = Column(Numeric(20, 2))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Supplier(Base):
    """Supplier/contractor profiles"""
    __tablename__ = "suppliers"

    supplier_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(500), nullable=False, unique=True, index=True)
    tax_id = Column(String(100), unique=True, index=True)
    company_type = Column(String(200))
    address = Column(Text)
    city = Column(String(200), index=True)
    contact_person = Column(String(255))
    contact_email = Column(String(255))
    contact_phone = Column(String(100))
    website = Column(Text)
    total_wins = Column(Integer, default=0)
    total_bids = Column(Integer, default=0)
    win_rate = Column(Numeric(5, 2))  # Percentage
    total_contract_value_mkd = Column(Numeric(20, 2))
    industries = Column(JSONB)  # Array of CPV codes or categories
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TenderClarification(Base):
    """Clarifications and Q&A for tenders"""
    __tablename__ = "tender_clarifications"

    clarification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(String(100), ForeignKey("tenders.tender_id", ondelete="CASCADE"), nullable=False, index=True)
    question_date = Column(Date)
    question_text = Column(Text, nullable=False)
    answer_date = Column(Date)
    answer_text = Column(Text)
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OpenDataStats(Base):
    """Aggregated statistics from e-nabavki OpenData PowerBI reports"""
    __tablename__ = "opendata_stats"

    stat_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(50), nullable=False, index=True)  # announcements, contracts, auctions, cancellations, users
    stat_key = Column(String(200), nullable=False)  # e.g., "total", "by_entity_category", "by_procedure_type"
    stat_value = Column(JSONB, nullable=False)  # Flexible storage for different stat types
    source_report_id = Column(String(100))  # PowerBI report ID
    fetched_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProductItem(Base):
    """Product items extracted from tender documents for granular search"""
    __tablename__ = "product_items"

    id = Column(Integer, primary_key=True)
    tender_id = Column(String(100), ForeignKey("tenders.tender_id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.doc_id", ondelete="SET NULL"), nullable=True)
    item_number = Column(Integer)
    lot_number = Column(String(50))
    name = Column(Text, nullable=False, index=True)
    quantity = Column(Numeric(15, 4))
    unit = Column(String(50))
    unit_price = Column(Numeric(15, 2))
    total_price = Column(Numeric(15, 2))
    specifications = Column(JSONB)
    cpv_code = Column(String(20), index=True)
    raw_text = Column(Text)
    extraction_confidence = Column(Numeric(3, 2))
    created_at = Column(DateTime, default=datetime.utcnow)

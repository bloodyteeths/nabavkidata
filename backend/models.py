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
    subscription_tier = Column(String(50), default="free")
    stripe_customer_id = Column(String(255))
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

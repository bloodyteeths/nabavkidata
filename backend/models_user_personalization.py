"""
User Personalization Models
"""
from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, ARRAY, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

from database import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    pref_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"),
                     nullable=False, unique=True, index=True)

    # Preference filters
    sectors = Column(ARRAY(String), default=list)
    cpv_codes = Column(ARRAY(String), default=list)
    entities = Column(ARRAY(String), default=list)
    min_budget = Column(Numeric(15, 2))
    max_budget = Column(Numeric(15, 2))
    exclude_keywords = Column(ARRAY(String), default=list)
    competitor_companies = Column(ARRAY(String), default=list)

    # Notification settings
    notification_frequency = Column(String(20), default="daily")  # instant, daily, weekly
    email_enabled = Column(Boolean, default=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserBehavior(Base):
    __tablename__ = "user_behavior"

    behavior_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"),
                     nullable=False, index=True)
    tender_id = Column(String(100), ForeignKey("tenders.tender_id", ondelete="CASCADE"),
                       nullable=False, index=True)

    action = Column(String(50), nullable=False, index=True)  # click, view, save, share
    duration_seconds = Column(Integer)
    behavior_metadata = Column(JSONB)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class UserInterestVector(Base):
    __tablename__ = "user_interest_vectors"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"),
                     primary_key=True, index=True)

    embedding = Column(Vector(1536), nullable=False)

    # Metadata
    interaction_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    version = Column(Integer, default=1)


class EmailDigest(Base):
    __tablename__ = "email_digests"

    digest_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"),
                     nullable=False, index=True)

    digest_date = Column(DateTime, nullable=False, index=True)
    digest_html = Column(String)
    digest_text = Column(String)

    # Content metadata
    tender_count = Column(Integer, default=0)
    competitor_activity_count = Column(Integer, default=0)

    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    search_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"),
                     nullable=False, index=True)
    name = Column(String(255), nullable=False)
    query = Column(String)
    filters = Column(JSONB)
    notify = Column(Boolean, default=False)
    last_executed = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class TenderAlert(Base):
    __tablename__ = "tender_alerts"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"),
                     nullable=False, index=True)
    name = Column(String(255), nullable=False)
    criteria = Column(JSONB)
    frequency = Column(String(50), default="daily")
    is_active = Column(Boolean, default=True)
    last_triggered = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

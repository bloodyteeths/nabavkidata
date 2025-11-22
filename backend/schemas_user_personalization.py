"""
User Personalization Schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID


# ============================================================================
# USER PREFERENCES
# ============================================================================

class PreferencesBase(BaseModel):
    sectors: List[str] = Field(default_factory=list)
    cpv_codes: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    min_budget: Optional[Decimal] = None
    max_budget: Optional[Decimal] = None
    exclude_keywords: List[str] = Field(default_factory=list)
    competitor_companies: List[str] = Field(default_factory=list)
    notification_frequency: str = Field("daily", pattern="^(instant|daily|weekly)$")
    email_enabled: bool = True


class PreferencesCreate(PreferencesBase):
    pass


class PreferencesUpdate(BaseModel):
    sectors: Optional[List[str]] = None
    cpv_codes: Optional[List[str]] = None
    entities: Optional[List[str]] = None
    min_budget: Optional[Decimal] = None
    max_budget: Optional[Decimal] = None
    exclude_keywords: Optional[List[str]] = None
    competitor_companies: Optional[List[str]] = None
    notification_frequency: Optional[str] = None
    email_enabled: Optional[bool] = None


class PreferencesResponse(PreferencesBase):
    pref_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# USER BEHAVIOR
# ============================================================================

class BehaviorLog(BaseModel):
    tender_id: str
    action: str = Field(..., pattern="^(click|view|save|share)$")
    duration_seconds: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class BehaviorResponse(BaseModel):
    behavior_id: UUID
    user_id: UUID
    tender_id: str
    action: str
    duration_seconds: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# PERSONALIZED DASHBOARD
# ============================================================================

class RecommendedTender(BaseModel):
    tender_id: str
    title: str
    category: Optional[str]
    procuring_entity: Optional[str]
    estimated_value_mkd: Optional[Decimal]
    closing_date: Optional[datetime]
    score: float
    match_reasons: List[str]


class CompetitorActivity(BaseModel):
    tender_id: str
    title: str
    competitor_name: str
    status: str
    estimated_value_mkd: Optional[Decimal]
    closing_date: Optional[datetime]


class PersonalizedInsight(BaseModel):
    insight_type: str  # trend, opportunity, alert
    title: str
    description: str
    confidence: float
    metadata: Optional[Dict[str, Any]] = None


class DashboardResponse(BaseModel):
    recommended_tenders: List[RecommendedTender]
    competitor_activity: List[CompetitorActivity]
    insights: List[PersonalizedInsight]
    stats: Dict[str, Any]


# ============================================================================
# INTEREST VECTOR
# ============================================================================

class InterestVectorResponse(BaseModel):
    user_id: UUID
    interaction_count: int
    last_updated: datetime
    version: int

    class Config:
        from_attributes = True


# ============================================================================
# EMAIL DIGEST
# ============================================================================

class DigestResponse(BaseModel):
    digest_id: UUID
    user_id: UUID
    digest_date: datetime
    tender_count: int
    competitor_activity_count: int
    sent: bool
    sent_at: Optional[datetime]

    class Config:
        from_attributes = True

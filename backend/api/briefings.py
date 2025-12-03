"""
Daily Briefings API - AI-Curated Tender Briefings
Phase 6.2: Backend AI-Curated Briefings

Generates personalized daily briefings matching user alerts with new tenders.
Uses Gemini AI for executive summaries.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, date, timedelta
from uuid import UUID
import os
import json
import logging

from database import get_db
from models import User, Alert
from api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/briefings", tags=["briefings"])

# Import Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = bool(os.getenv('GEMINI_API_KEY'))
    if GEMINI_AVAILABLE:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        # Use configured model or default
        GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
except ImportError:
    GEMINI_AVAILABLE = False
    GEMINI_MODEL = None


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class TenderMatch(BaseModel):
    """Single tender match in briefing"""
    tender_id: str
    title: str
    procuring_entity: Optional[str] = None
    category: Optional[str] = None
    cpv_code: Optional[str] = None
    estimated_value_mkd: Optional[float] = None
    closing_date: Optional[date] = None
    status: Optional[str] = None
    alert_name: str
    score: float
    reasons: List[str]
    priority: str  # high, medium, low
    source_url: Optional[str] = None


class BriefingStats(BaseModel):
    """Statistics for briefing"""
    total_new_tenders: int
    total_matches: int
    high_priority_count: int
    medium_priority_count: int = 0
    low_priority_count: int = 0


class BriefingContent(BaseModel):
    """Structured briefing content"""
    high_priority: List[TenderMatch]
    all_matches: List[TenderMatch]
    stats: BriefingStats


class BriefingResponse(BaseModel):
    """Response for daily briefing"""
    briefing_id: str
    briefing_date: date
    content: BriefingContent
    ai_summary: Optional[str] = None
    total_matches: int
    high_priority_count: int
    generated_at: datetime
    is_viewed: bool


class BriefingListItem(BaseModel):
    """Brief summary of a briefing for history list"""
    briefing_id: str
    briefing_date: date
    total_matches: int
    high_priority_count: int
    ai_summary: Optional[str] = None
    generated_at: datetime
    is_viewed: bool


class BriefingHistoryResponse(BaseModel):
    """Response for briefing history"""
    total: int
    page: int
    page_size: int
    briefings: List[BriefingListItem]


# ============================================================================
# HELPER FUNCTIONS - ALERT MATCHING
# ============================================================================

async def get_user_alerts(user_id: UUID, db: AsyncSession) -> List[Dict[str, Any]]:
    """Get active alerts for user"""
    query = text("""
        SELECT alert_id, name, filters, frequency, is_active
        FROM alerts
        WHERE user_id = :user_id AND is_active = TRUE
        ORDER BY created_at DESC
    """)

    result = await db.execute(query, {"user_id": str(user_id)})
    rows = result.fetchall()

    alerts = []
    for row in rows:
        alerts.append({
            'alert_id': str(row.alert_id),
            'name': row.name,
            'filters': row.filters if isinstance(row.filters, dict) else {},
            'frequency': row.frequency,
            'is_active': row.is_active
        })

    return alerts


async def get_recent_tenders(hours: int, db: AsyncSession) -> List[Dict[str, Any]]:
    """Get tenders from last N hours"""
    query = text("""
        SELECT
            tender_id, title, description, category, cpv_code,
            procuring_entity, estimated_value_mkd, closing_date,
            status, source_url, publication_date, created_at
        FROM tenders
        WHERE created_at >= NOW() - INTERVAL ':hours hours'
        ORDER BY created_at DESC
        LIMIT 500
    """)

    result = await db.execute(query, {"hours": hours})
    rows = result.fetchall()

    tenders = []
    for row in rows:
        tenders.append({
            'tender_id': row.tender_id,
            'title': row.title or '',
            'description': row.description or '',
            'category': row.category,
            'cpv_code': row.cpv_code,
            'procuring_entity': row.procuring_entity,
            'estimated_value_mkd': float(row.estimated_value_mkd) if row.estimated_value_mkd else None,
            'closing_date': row.closing_date,
            'status': row.status,
            'source_url': row.source_url,
            'publication_date': row.publication_date,
            'created_at': row.created_at
        })

    return tenders


def check_alert_against_tender(alert: Dict[str, Any], tender: Dict[str, Any]) -> tuple[bool, float, List[str]]:
    """
    Check if tender matches alert criteria
    Returns: (is_match, score, reasons)
    """
    filters = alert.get('filters', {})
    score = 0.0
    reasons = []
    max_score = 0.0

    # Query/keyword match (40 points)
    if filters.get('query'):
        max_score += 40
        query = filters['query'].lower()
        title = tender.get('title', '').lower()
        description = tender.get('description', '').lower()

        if query in title:
            score += 40
            reasons.append(f"Клучен збор '{query}' во наслов")
        elif query in description:
            score += 25
            reasons.append(f"Клучен збор '{query}' во опис")

    # Category match (20 points)
    if filters.get('category'):
        max_score += 20
        if tender.get('category') == filters['category']:
            score += 20
            reasons.append(f"Категорија: {filters['category']}")

    # CPV code match (20 points)
    if filters.get('cpv_code'):
        max_score += 20
        tender_cpv = tender.get('cpv_code', '')
        alert_cpv = filters['cpv_code']

        if tender_cpv.startswith(alert_cpv):
            score += 20
            reasons.append(f"CPV код: {alert_cpv}")

    # Procuring entity match (15 points)
    if filters.get('procuring_entity'):
        max_score += 15
        tender_entity = (tender.get('procuring_entity') or '').lower()
        alert_entity = filters['procuring_entity'].lower()

        if alert_entity in tender_entity:
            score += 15
            reasons.append(f"Набавувач: {filters['procuring_entity']}")

    # Value range match (5 points)
    if filters.get('min_value_mkd') or filters.get('max_value_mkd'):
        max_score += 5
        tender_value = tender.get('estimated_value_mkd')

        if tender_value:
            min_val = filters.get('min_value_mkd', 0)
            max_val = filters.get('max_value_mkd', float('inf'))

            if min_val <= tender_value <= max_val:
                score += 5
                reasons.append(f"Вредност: {tender_value:,.0f} МКД")

    # Normalize score to 0-100
    if max_score > 0:
        score = (score / max_score) * 100

    # Match threshold: at least one filter matched
    is_match = score > 0 and len(reasons) > 0

    return is_match, round(score, 1), reasons


# ============================================================================
# BRIEFING GENERATION
# ============================================================================

async def generate_briefing_summary(matches: List[Dict[str, Any]], user_alerts: List[Dict[str, Any]]) -> str:
    """Use Gemini to generate executive summary in Macedonian"""
    if not GEMINI_AVAILABLE or not matches:
        return ""

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)

        high_priority_matches = [m for m in matches if m['priority'] == 'high']
        alert_names = ', '.join([a['name'] for a in user_alerts[:3]])

        top_tender_title = matches[0]['tender']['title'][:150] if matches else 'Нема'

        context = f"""Генерирај кратко извршно резиме (2-3 реченици) за дневен извештај за тендери на македонски јазик.

Информации:
- Вкупно совпаѓања: {len(matches)}
- Високо приоритетни: {len(high_priority_matches)}
- Корисникот следи: {alert_names}
- Најдобро совпаѓање: {top_tender_title}

Биди концизен и нагласи ги итните можности. Користи македонски јазик."""

        # Relaxed safety settings for business content
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
        ]
        response = model.generate_content(context, safety_settings=safety_settings)
        try:
            return response.text.strip()
        except ValueError:
            return f"Пронајдени {len(matches)} совпаѓања за вашите алерти."

    except Exception as e:
        logger.error(f"AI briefing summary failed: {e}")
        return f"Пронајдени {len(matches)} совпаѓања за вашите алерти."


async def generate_daily_briefing(user_id: UUID, db: AsyncSession, force_regenerate: bool = False) -> Dict[str, Any]:
    """Generate AI-curated daily briefing for user"""

    # 1. Get user's alerts
    alerts = await get_user_alerts(user_id, db)

    if not alerts:
        return {
            'high_priority': [],
            'all_matches': [],
            'summary': 'Немате активни алерти. Креирајте алерт за да добивате прилагодени известувања.',
            'stats': {
                'total_new_tenders': 0,
                'total_matches': 0,
                'high_priority_count': 0,
                'medium_priority_count': 0,
                'low_priority_count': 0
            }
        }

    # 2. Get new tenders from last 24 hours
    new_tenders = await get_recent_tenders(hours=24, db=db)

    # 3. Match tenders against alerts
    matches = []
    for tender in new_tenders:
        for alert in alerts:
            is_match, score, reasons = check_alert_against_tender(alert, tender)
            if is_match:
                # Determine priority based on score
                if score >= 70:
                    priority = 'high'
                elif score >= 40:
                    priority = 'medium'
                else:
                    priority = 'low'

                matches.append({
                    'tender': tender,
                    'alert_name': alert['name'],
                    'score': score,
                    'reasons': reasons,
                    'priority': priority
                })

    # 4. Sort by score and categorize
    matches.sort(key=lambda x: x['score'], reverse=True)

    high_priority = [m for m in matches if m['priority'] == 'high']
    medium_priority = [m for m in matches if m['priority'] == 'medium']
    low_priority = [m for m in matches if m['priority'] == 'low']

    # 5. Generate AI summary using Gemini
    ai_summary = await generate_briefing_summary(matches, user_alerts=alerts)

    return {
        'high_priority': high_priority[:5],  # Top 5 high priority
        'all_matches': matches[:20],  # Top 20 overall
        'summary': ai_summary,
        'stats': {
            'total_new_tenders': len(new_tenders),
            'total_matches': len(matches),
            'high_priority_count': len(high_priority),
            'medium_priority_count': len(medium_priority),
            'low_priority_count': len(low_priority)
        }
    }


async def get_or_create_briefing(
    user_id: UUID,
    briefing_date: date,
    db: AsyncSession,
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """Get existing briefing or generate new one"""

    # Check if briefing already exists (unless force regenerate)
    if not force_regenerate:
        check_query = text("""
            SELECT briefing_id, content, ai_summary, total_matches,
                   high_priority_count, generated_at, is_viewed
            FROM daily_briefings
            WHERE user_id = :user_id AND briefing_date = :briefing_date
        """)

        result = await db.execute(check_query, {
            "user_id": str(user_id),
            "briefing_date": briefing_date
        })
        row = result.fetchone()

        if row:
            # Return existing briefing
            return {
                'briefing_id': str(row.briefing_id),
                'briefing_date': briefing_date,
                'content': row.content,
                'ai_summary': row.ai_summary,
                'total_matches': row.total_matches,
                'high_priority_count': row.high_priority_count,
                'generated_at': row.generated_at,
                'is_viewed': row.is_viewed
            }

    # Generate new briefing
    briefing_data = await generate_daily_briefing(user_id, db, force_regenerate)

    # Format content for database
    content = {
        'high_priority': [
            {
                'tender_id': m['tender']['tender_id'],
                'title': m['tender']['title'],
                'procuring_entity': m['tender']['procuring_entity'],
                'category': m['tender']['category'],
                'cpv_code': m['tender']['cpv_code'],
                'estimated_value_mkd': m['tender']['estimated_value_mkd'],
                'closing_date': m['tender']['closing_date'].isoformat() if m['tender']['closing_date'] else None,
                'status': m['tender']['status'],
                'alert_name': m['alert_name'],
                'score': m['score'],
                'reasons': m['reasons'],
                'priority': m['priority'],
                'source_url': m['tender']['source_url']
            }
            for m in briefing_data['high_priority']
        ],
        'all_matches': [
            {
                'tender_id': m['tender']['tender_id'],
                'title': m['tender']['title'],
                'procuring_entity': m['tender']['procuring_entity'],
                'category': m['tender']['category'],
                'cpv_code': m['tender']['cpv_code'],
                'estimated_value_mkd': m['tender']['estimated_value_mkd'],
                'closing_date': m['tender']['closing_date'].isoformat() if m['tender']['closing_date'] else None,
                'status': m['tender']['status'],
                'alert_name': m['alert_name'],
                'score': m['score'],
                'reasons': m['reasons'],
                'priority': m['priority'],
                'source_url': m['tender']['source_url']
            }
            for m in briefing_data['all_matches']
        ],
        'stats': briefing_data['stats']
    }

    # Save to database
    if force_regenerate:
        # Delete existing and insert new
        delete_query = text("""
            DELETE FROM daily_briefings
            WHERE user_id = :user_id AND briefing_date = :briefing_date
        """)
        await db.execute(delete_query, {
            "user_id": str(user_id),
            "briefing_date": briefing_date
        })

    insert_query = text("""
        INSERT INTO daily_briefings
        (user_id, briefing_date, content, ai_summary, total_matches, high_priority_count, generated_at)
        VALUES (:user_id, :briefing_date, :content::jsonb, :ai_summary, :total_matches, :high_priority_count, NOW())
        RETURNING briefing_id, generated_at
    """)

    result = await db.execute(insert_query, {
        "user_id": str(user_id),
        "briefing_date": briefing_date,
        "content": json.dumps(content),
        "ai_summary": briefing_data['summary'],
        "total_matches": briefing_data['stats']['total_matches'],
        "high_priority_count": briefing_data['stats']['high_priority_count']
    })
    await db.commit()

    row = result.fetchone()

    return {
        'briefing_id': str(row.briefing_id),
        'briefing_date': briefing_date,
        'content': content,
        'ai_summary': briefing_data['summary'],
        'total_matches': briefing_data['stats']['total_matches'],
        'high_priority_count': briefing_data['stats']['high_priority_count'],
        'generated_at': row.generated_at,
        'is_viewed': False
    }


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/today", response_model=BriefingResponse)
async def get_today_briefing(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get today's briefing (generate if not exists)

    Returns AI-curated briefing with matching tenders for user's alerts.
    Cached - won't regenerate unless forced.
    """
    today = date.today()
    user_id = current_user.user_id

    briefing = await get_or_create_briefing(user_id, today, db, force_regenerate=False)

    # Mark as viewed
    await db.execute(
        text("UPDATE daily_briefings SET is_viewed = TRUE WHERE briefing_id = :id"),
        {"id": briefing['briefing_id']}
    )
    await db.commit()

    return BriefingResponse(
        briefing_id=briefing['briefing_id'],
        briefing_date=briefing['briefing_date'],
        content=BriefingContent(**briefing['content']),
        ai_summary=briefing['ai_summary'],
        total_matches=briefing['total_matches'],
        high_priority_count=briefing['high_priority_count'],
        generated_at=briefing['generated_at'],
        is_viewed=True
    )


@router.get("/history", response_model=BriefingHistoryResponse)
async def get_briefing_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List past briefings with pagination

    Returns briefing history for the current user.
    """
    user_id = current_user.user_id
    offset = (page - 1) * page_size

    # Get total count
    count_query = text("""
        SELECT COUNT(*) FROM daily_briefings
        WHERE user_id = :user_id
    """)
    count_result = await db.execute(count_query, {"user_id": str(user_id)})
    total = count_result.scalar() or 0

    # Get briefings
    query = text("""
        SELECT briefing_id, briefing_date, total_matches, high_priority_count,
               ai_summary, generated_at, is_viewed
        FROM daily_briefings
        WHERE user_id = :user_id
        ORDER BY briefing_date DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(query, {
        "user_id": str(user_id),
        "limit": page_size,
        "offset": offset
    })
    rows = result.fetchall()

    briefings = [
        BriefingListItem(
            briefing_id=str(row.briefing_id),
            briefing_date=row.briefing_date,
            total_matches=row.total_matches,
            high_priority_count=row.high_priority_count,
            ai_summary=row.ai_summary,
            generated_at=row.generated_at,
            is_viewed=row.is_viewed
        )
        for row in rows
    ]

    return BriefingHistoryResponse(
        total=total,
        page=page,
        page_size=page_size,
        briefings=briefings
    )


@router.get("/{briefing_date}", response_model=BriefingResponse)
async def get_briefing_by_date(
    briefing_date: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get specific date's briefing

    Returns briefing for the specified date.
    Generates if it doesn't exist (for past dates).
    """
    user_id = current_user.user_id

    # Don't allow future dates
    if briefing_date > date.today():
        raise HTTPException(
            status_code=400,
            detail="Cannot generate briefing for future dates"
        )

    briefing = await get_or_create_briefing(user_id, briefing_date, db, force_regenerate=False)

    # Mark as viewed
    await db.execute(
        text("UPDATE daily_briefings SET is_viewed = TRUE WHERE briefing_id = :id"),
        {"id": briefing['briefing_id']}
    )
    await db.commit()

    return BriefingResponse(
        briefing_id=briefing['briefing_id'],
        briefing_date=briefing['briefing_date'],
        content=BriefingContent(**briefing['content']),
        ai_summary=briefing['ai_summary'],
        total_matches=briefing['total_matches'],
        high_priority_count=briefing['high_priority_count'],
        generated_at=briefing['generated_at'],
        is_viewed=True
    )


@router.post("/generate", response_model=BriefingResponse, status_code=201)
async def force_regenerate_briefing(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Force regenerate today's briefing

    Deletes existing briefing and generates a fresh one.
    Use when user wants updated data.
    """
    today = date.today()
    user_id = current_user.user_id

    briefing = await get_or_create_briefing(user_id, today, db, force_regenerate=True)

    return BriefingResponse(
        briefing_id=briefing['briefing_id'],
        briefing_date=briefing['briefing_date'],
        content=BriefingContent(**briefing['content']),
        ai_summary=briefing['ai_summary'],
        total_matches=briefing['total_matches'],
        high_priority_count=briefing['high_priority_count'],
        generated_at=briefing['generated_at'],
        is_viewed=False
    )


@router.get("/health/status")
async def briefing_health():
    """
    Check briefing service health

    Returns service status and configuration
    """
    return {
        "status": "healthy" if GEMINI_AVAILABLE else "degraded",
        "service": "daily-briefings",
        "gemini_available": GEMINI_AVAILABLE,
        "gemini_model": GEMINI_MODEL,
        "features": {
            "briefing_generation": True,
            "ai_summaries": GEMINI_AVAILABLE,
            "alert_matching": True,
            "briefing_history": True
        }
    }

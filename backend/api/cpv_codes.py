"""
CPV Codes API endpoints
Browse and search CPV (Common Procurement Vocabulary) codes
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from database import get_db

router = APIRouter(prefix="/cpv-codes", tags=["cpv-codes"])


# ============================================================================
# CPV CODE HIERARCHY DATA (EU CPV 2008 standard)
# ============================================================================

CPV_DIVISIONS = {
    "03": {"name": "Agricultural products", "name_mk": "Земјоделски производи"},
    "09": {"name": "Petroleum products, fuel", "name_mk": "Нафтени производи, гориво"},
    "14": {"name": "Mining products", "name_mk": "Рударски производи"},
    "15": {"name": "Food, beverages, tobacco", "name_mk": "Храна, пијалоци, тутун"},
    "16": {"name": "Agricultural machinery", "name_mk": "Земјоделски машини"},
    "18": {"name": "Clothing, footwear", "name_mk": "Облека, обувки"},
    "19": {"name": "Leather products", "name_mk": "Кожни производи"},
    "22": {"name": "Printed matter", "name_mk": "Печатени материјали"},
    "24": {"name": "Chemical products", "name_mk": "Хемиски производи"},
    "30": {"name": "Office machinery, computers", "name_mk": "Канцелариски машини, компјутери"},
    "31": {"name": "Electrical machinery", "name_mk": "Електрични машини"},
    "32": {"name": "Radio, television, communication", "name_mk": "Радио, телевизија, комуникации"},
    "33": {"name": "Medical equipment", "name_mk": "Медицинска опрема"},
    "34": {"name": "Transport equipment", "name_mk": "Транспортна опрема"},
    "35": {"name": "Security, fire-fighting", "name_mk": "Безбедност, противпожарна заштита"},
    "37": {"name": "Musical instruments, sports", "name_mk": "Музички инструменти, спорт"},
    "38": {"name": "Laboratory equipment", "name_mk": "Лабораториска опрема"},
    "39": {"name": "Furniture", "name_mk": "Мебел"},
    "41": {"name": "Collected water", "name_mk": "Собрана вода"},
    "42": {"name": "Industrial machinery", "name_mk": "Индустриски машини"},
    "43": {"name": "Machinery for mining", "name_mk": "Машини за рударство"},
    "44": {"name": "Construction structures", "name_mk": "Градежни структури"},
    "45": {"name": "Construction work", "name_mk": "Градежни работи"},
    "48": {"name": "Software packages", "name_mk": "Софтверски пакети"},
    "50": {"name": "Repair and maintenance", "name_mk": "Поправка и одржување"},
    "51": {"name": "Installation services", "name_mk": "Услуги за инсталација"},
    "55": {"name": "Hotel and restaurant services", "name_mk": "Хотелски и ресторански услуги"},
    "60": {"name": "Transport services", "name_mk": "Транспортни услуги"},
    "63": {"name": "Supporting transport services", "name_mk": "Помошни транспортни услуги"},
    "64": {"name": "Postal and telecommunications", "name_mk": "Поштенски и телекомуникациски услуги"},
    "65": {"name": "Public utilities", "name_mk": "Јавни услуги"},
    "66": {"name": "Financial services", "name_mk": "Финансиски услуги"},
    "70": {"name": "Real estate services", "name_mk": "Услуги со недвижности"},
    "71": {"name": "Architectural services", "name_mk": "Архитектонски услуги"},
    "72": {"name": "IT services", "name_mk": "ИТ услуги"},
    "73": {"name": "Research services", "name_mk": "Истражувачки услуги"},
    "75": {"name": "Administration services", "name_mk": "Административни услуги"},
    "76": {"name": "Oil and gas services", "name_mk": "Нафтени и гасни услуги"},
    "77": {"name": "Agricultural services", "name_mk": "Земјоделски услуги"},
    "79": {"name": "Business services", "name_mk": "Деловни услуги"},
    "80": {"name": "Education services", "name_mk": "Образовни услуги"},
    "85": {"name": "Health and social services", "name_mk": "Здравствени и социјални услуги"},
    "90": {"name": "Sewage, refuse services", "name_mk": "Канализација, отпад"},
    "92": {"name": "Recreational services", "name_mk": "Рекреативни услуги"},
    "98": {"name": "Other community services", "name_mk": "Други јавни услуги"},
}


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class CPVCodeResponse(BaseModel):
    code: str
    name: Optional[str] = None
    name_mk: Optional[str] = None
    parent_code: Optional[str] = None
    level: int = 1
    tender_count: int = 0
    total_value_mkd: Optional[float] = None
    avg_value_mkd: Optional[float] = None


class CPVCodeListResponse(BaseModel):
    total: int
    prefix_filter: Optional[str] = None
    cpv_codes: List[CPVCodeResponse]


class CPVCodeDetailResponse(CPVCodeResponse):
    recent_tenders: List[dict] = []
    top_entities: List[dict] = []
    monthly_trend: List[dict] = []


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_cpv_name(code: str) -> tuple:
    """Get CPV code name from hierarchy data"""
    if not code:
        return None, None

    division = code[:2]
    if division in CPV_DIVISIONS:
        return CPV_DIVISIONS[division]["name"], CPV_DIVISIONS[division]["name_mk"]
    return None, None


def get_cpv_level(code: str) -> int:
    """Determine CPV hierarchy level (1-5)"""
    if not code:
        return 1
    code = code.replace("-", "")
    if len(code) <= 2:
        return 1  # Division
    elif len(code) <= 3:
        return 2  # Group
    elif len(code) <= 4:
        return 3  # Class
    elif len(code) <= 5:
        return 4  # Category
    else:
        return 5  # Full code


def get_parent_code(code: str) -> Optional[str]:
    """Get parent CPV code"""
    if not code or len(code) <= 2:
        return None
    return code[:2] + "000000"


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("", response_model=CPVCodeListResponse)
async def list_cpv_codes(
    prefix: Optional[str] = Query(None, description="Filter by CPV code prefix (e.g., '33' for medical)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of CPV codes to return"),
    min_tenders: int = Query(0, ge=0, description="Minimum number of tenders"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all CPV codes with tender statistics.

    Returns CPV codes sorted by tender count, with human-readable names.
    """
    filters = ["cpv_code IS NOT NULL", "cpv_code != ''"]
    params = {"limit": limit}

    if prefix:
        filters.append("cpv_code LIKE :prefix")
        params["prefix"] = f"{prefix}%"

    if min_tenders > 0:
        filters.append("COUNT(*) >= :min_tenders")
        params["min_tenders"] = min_tenders

    where_clause = " AND ".join(filters[:2])  # Basic filters
    having_clause = f"HAVING COUNT(*) >= {min_tenders}" if min_tenders > 0 else ""

    query = text(f"""
        SELECT
            cpv_code,
            COUNT(*) as tender_count,
            SUM(estimated_value_mkd) as total_value_mkd,
            AVG(estimated_value_mkd) as avg_value_mkd
        FROM tenders
        WHERE {where_clause}
        GROUP BY cpv_code
        {having_clause}
        ORDER BY COUNT(*) DESC
        LIMIT :limit
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    cpv_codes = []
    for row in rows:
        name, name_mk = get_cpv_name(row.cpv_code)
        cpv_codes.append(CPVCodeResponse(
            code=row.cpv_code,
            name=name,
            name_mk=name_mk,
            parent_code=get_parent_code(row.cpv_code),
            level=get_cpv_level(row.cpv_code),
            tender_count=row.tender_count,
            total_value_mkd=float(row.total_value_mkd) if row.total_value_mkd else None,
            avg_value_mkd=float(row.avg_value_mkd) if row.avg_value_mkd else None
        ))

    return CPVCodeListResponse(
        total=len(cpv_codes),
        prefix_filter=prefix,
        cpv_codes=cpv_codes
    )


@router.get("/search")
async def search_cpv_codes(
    prefix: str = Query(..., min_length=1, description="CPV code or category name to search"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """
    Search CPV codes by code prefix OR category name.

    The search parameter can be:
    - A numeric CPV code prefix (e.g., "33" for medical equipment)
    - A text category name in English or Macedonian (e.g., "medical", "медицинска")

    Returns matching CPV codes with statistics and hierarchy information.
    """
    cpv_codes = []

    # Check if the prefix is numeric (CPV code search) or text (name search)
    is_numeric = prefix.replace("-", "").isdigit()

    if is_numeric:
        # Search by CPV code prefix
        query = text("""
            SELECT
                cpv_code,
                COUNT(*) as tender_count,
                SUM(estimated_value_mkd) as total_value_mkd,
                AVG(estimated_value_mkd) as avg_value_mkd
            FROM tenders
            WHERE cpv_code IS NOT NULL
              AND cpv_code != ''
              AND cpv_code LIKE :prefix
            GROUP BY cpv_code
            ORDER BY COUNT(*) DESC
            LIMIT :limit
        """)
        result = await db.execute(query, {"prefix": f"{prefix}%", "limit": limit})
        rows = result.fetchall()

        for row in rows:
            name, name_mk = get_cpv_name(row.cpv_code)
            cpv_codes.append({
                "code": row.cpv_code,
                "name": name,
                "name_mk": name_mk,
                "parent_code": get_parent_code(row.cpv_code),
                "level": get_cpv_level(row.cpv_code),
                "tender_count": row.tender_count,
                "total_value_mkd": float(row.total_value_mkd) if row.total_value_mkd else None,
                "avg_value_mkd": float(row.avg_value_mkd) if row.avg_value_mkd else None
            })
    else:
        # Search by category name in CPV_DIVISIONS
        search_lower = prefix.lower()
        matching_divisions = []

        for code, info in CPV_DIVISIONS.items():
            if (search_lower in info["name"].lower() or
                search_lower in info["name_mk"].lower()):
                matching_divisions.append(code)

        if matching_divisions:
            # Get tenders for matching divisions
            placeholders = ",".join([f":div{i}" for i in range(len(matching_divisions))])
            params = {f"div{i}": div for i, div in enumerate(matching_divisions)}
            params["limit"] = limit

            like_conditions = " OR ".join([f"cpv_code LIKE :pattern{i}" for i in range(len(matching_divisions))])
            for i, div in enumerate(matching_divisions):
                params[f"pattern{i}"] = f"{div}%"

            query = text(f"""
                SELECT
                    cpv_code,
                    COUNT(*) as tender_count,
                    SUM(estimated_value_mkd) as total_value_mkd,
                    AVG(estimated_value_mkd) as avg_value_mkd
                FROM tenders
                WHERE cpv_code IS NOT NULL
                  AND cpv_code != ''
                  AND ({like_conditions})
                GROUP BY cpv_code
                ORDER BY COUNT(*) DESC
                LIMIT :limit
            """)
            result = await db.execute(query, params)
            rows = result.fetchall()

            for row in rows:
                name, name_mk = get_cpv_name(row.cpv_code)
                cpv_codes.append({
                    "code": row.cpv_code,
                    "name": name,
                    "name_mk": name_mk,
                    "parent_code": get_parent_code(row.cpv_code),
                    "level": get_cpv_level(row.cpv_code),
                    "tender_count": row.tender_count,
                    "total_value_mkd": float(row.total_value_mkd) if row.total_value_mkd else None,
                    "avg_value_mkd": float(row.avg_value_mkd) if row.avg_value_mkd else None
                })
        else:
            # No divisions matched, try to search in tender titles/descriptions
            # and get CPV codes associated with those tenders
            query = text("""
                SELECT
                    cpv_code,
                    COUNT(*) as tender_count,
                    SUM(estimated_value_mkd) as total_value_mkd,
                    AVG(estimated_value_mkd) as avg_value_mkd
                FROM tenders
                WHERE cpv_code IS NOT NULL
                  AND cpv_code != ''
                  AND (title ILIKE :search OR description ILIKE :search)
                GROUP BY cpv_code
                ORDER BY COUNT(*) DESC
                LIMIT :limit
            """)
            result = await db.execute(query, {"search": f"%{prefix}%", "limit": limit})
            rows = result.fetchall()

            for row in rows:
                name, name_mk = get_cpv_name(row.cpv_code)
                cpv_codes.append({
                    "code": row.cpv_code,
                    "name": name,
                    "name_mk": name_mk,
                    "parent_code": get_parent_code(row.cpv_code),
                    "level": get_cpv_level(row.cpv_code),
                    "tender_count": row.tender_count,
                    "total_value_mkd": float(row.total_value_mkd) if row.total_value_mkd else None,
                    "avg_value_mkd": float(row.avg_value_mkd) if row.avg_value_mkd else None
                })

    return {
        "query": prefix,
        "total": len(cpv_codes),
        "results": cpv_codes
    }


@router.get("/divisions")
async def get_cpv_divisions(
    db: AsyncSession = Depends(get_db)
):
    """
    Get all CPV divisions (top-level categories) with tender counts.

    Returns the main CPV division codes (2-digit) with statistics.
    """
    query = text("""
        SELECT
            SUBSTRING(cpv_code, 1, 2) as division,
            COUNT(*) as tender_count,
            SUM(estimated_value_mkd) as total_value_mkd
        FROM tenders
        WHERE cpv_code IS NOT NULL
          AND cpv_code != ''
          AND LENGTH(cpv_code) >= 2
        GROUP BY SUBSTRING(cpv_code, 1, 2)
        ORDER BY COUNT(*) DESC
    """)

    result = await db.execute(query)
    rows = result.fetchall()

    divisions = []
    for row in rows:
        div_info = CPV_DIVISIONS.get(row.division, {"name": "Other", "name_mk": "Друго"})
        divisions.append({
            "code": row.division,
            "name": div_info["name"],
            "name_mk": div_info["name_mk"],
            "tender_count": row.tender_count,
            "total_value_mkd": float(row.total_value_mkd) if row.total_value_mkd else None
        })

    return {
        "total": len(divisions),
        "divisions": divisions
    }


@router.get("/{code}", response_model=CPVCodeDetailResponse)
async def get_cpv_code_detail(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information for a specific CPV code.

    Returns statistics, recent tenders, top entities, and monthly trends.
    """
    # Get basic stats
    stats_query = text("""
        SELECT
            COUNT(*) as tender_count,
            SUM(estimated_value_mkd) as total_value_mkd,
            AVG(estimated_value_mkd) as avg_value_mkd
        FROM tenders
        WHERE cpv_code = :code OR cpv_code LIKE :prefix
    """)

    stats_result = await db.execute(stats_query, {"code": code, "prefix": f"{code}%"})
    stats = stats_result.fetchone()

    if not stats or stats.tender_count == 0:
        raise HTTPException(status_code=404, detail="CPV code not found or no tenders")

    # Get recent tenders
    tenders_query = text("""
        SELECT tender_id, title, procuring_entity, estimated_value_mkd, status, closing_date
        FROM tenders
        WHERE cpv_code = :code OR cpv_code LIKE :prefix
        ORDER BY created_at DESC
        LIMIT 10
    """)

    tenders_result = await db.execute(tenders_query, {"code": code, "prefix": f"{code}%"})
    recent_tenders = [
        {
            "tender_id": row.tender_id,
            "title": row.title,
            "procuring_entity": row.procuring_entity,
            "estimated_value_mkd": float(row.estimated_value_mkd) if row.estimated_value_mkd else None,
            "status": row.status,
            "closing_date": row.closing_date.isoformat() if row.closing_date else None
        }
        for row in tenders_result.fetchall()
    ]

    # Get top entities
    entities_query = text("""
        SELECT procuring_entity, COUNT(*) as count, SUM(estimated_value_mkd) as total_value
        FROM tenders
        WHERE (cpv_code = :code OR cpv_code LIKE :prefix)
          AND procuring_entity IS NOT NULL
        GROUP BY procuring_entity
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)

    entities_result = await db.execute(entities_query, {"code": code, "prefix": f"{code}%"})
    top_entities = [
        {
            "entity": row.procuring_entity,
            "tender_count": row.count,
            "total_value_mkd": float(row.total_value) if row.total_value else None
        }
        for row in entities_result.fetchall()
    ]

    # Get monthly trend
    trend_query = text("""
        SELECT
            date_trunc('month', opening_date) as month,
            COUNT(*) as count,
            SUM(estimated_value_mkd) as value
        FROM tenders
        WHERE (cpv_code = :code OR cpv_code LIKE :prefix)
          AND opening_date >= NOW() - INTERVAL '12 months'
        GROUP BY date_trunc('month', opening_date)
        ORDER BY month
    """)

    trend_result = await db.execute(trend_query, {"code": code, "prefix": f"{code}%"})
    monthly_trend = [
        {
            "month": row.month.isoformat() if row.month else None,
            "tender_count": row.count,
            "total_value_mkd": float(row.value) if row.value else None
        }
        for row in trend_result.fetchall()
    ]

    name, name_mk = get_cpv_name(code)

    return CPVCodeDetailResponse(
        code=code,
        name=name,
        name_mk=name_mk,
        parent_code=get_parent_code(code),
        level=get_cpv_level(code),
        tender_count=stats.tender_count,
        total_value_mkd=float(stats.total_value_mkd) if stats.total_value_mkd else None,
        avg_value_mkd=float(stats.avg_value_mkd) if stats.avg_value_mkd else None,
        recent_tenders=recent_tenders,
        top_entities=top_entities,
        monthly_trend=monthly_trend
    )

"""
SearchTendersTool — dynamic SQL search across the MK tenders table.

Supports free-text (ILIKE + pg_trgm), CPV codes, buyer name, value range,
status filter, date range, sorting, and pagination.
Includes bilingual Latin→Cyrillic conversion for cross-script search.
"""

from typing import Any

LATIN_TO_CYRILLIC = {
    'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д',
    'e': 'е', 'zh': 'ж', 'z': 'з', 'i': 'и', 'j': 'ј',
    'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о',
    'p': 'п', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у',
    'f': 'ф', 'h': 'х', 'c': 'ц', 'ch': 'ч', 'sh': 'ш',
    'dz': 'ѕ', 'gj': 'ѓ', 'kj': 'ќ', 'lj': 'љ', 'nj': 'њ',
}


def _latin_to_cyrillic(text: str) -> str:
    """Convert Latin text to Macedonian Cyrillic."""
    result = []
    i = 0
    lower = text.lower()
    while i < len(lower):
        matched = False
        for length in (2, 1):
            chunk = lower[i:i + length]
            if chunk in LATIN_TO_CYRILLIC:
                cyr = LATIN_TO_CYRILLIC[chunk]
                if text[i].isupper():
                    cyr = cyr.upper()
                result.append(cyr)
                i += length
                matched = True
                break
        if not matched:
            result.append(text[i])
            i += 1
    return ''.join(result)


def _is_latin(text: str) -> bool:
    """Check if text contains Latin characters."""
    return any('a' <= c.lower() <= 'z' for c in text)


class SearchTendersTool:
    name = "search_tenders"
    description = (
        "Search Macedonian procurement tenders with filters. "
        "Use this to find tenders by keyword, sector (CPV code), buyer, "
        "value range, status, or date range. Returns up to 20 results. "
        "Supports both Latin and Cyrillic input (auto-converts)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Free-text search across title and description. Works in both Latin and Cyrillic.",
            },
            "cpv_codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "CPV code prefixes to filter by, e.g. ['72'] for IT or ['45'] for construction.",
            },
            "buyer_name": {
                "type": "string",
                "description": "Procuring entity / buyer name (partial match).",
            },
            "winner_name": {
                "type": "string",
                "description": "Winner / supplier name (partial match).",
            },
            "min_value": {
                "type": "number",
                "description": "Minimum estimated value in MKD.",
            },
            "max_value": {
                "type": "number",
                "description": "Maximum estimated value in MKD.",
            },
            "status": {
                "type": "string",
                "description": "Tender status: open, awarded, completed, closed, cancelled.",
            },
            "date_from": {
                "type": "string",
                "description": "Published after this date (YYYY-MM-DD).",
            },
            "date_to": {
                "type": "string",
                "description": "Published before this date (YYYY-MM-DD).",
            },
            "sort_by": {
                "type": "string",
                "enum": ["relevance", "value_desc", "value_asc", "date_desc", "date_asc", "closing_date"],
                "description": "Sort order. Default: relevance when query given, date_desc otherwise.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (1-20, default 10).",
            },
        },
        "required": [],
    }

    async def execute(self, params: dict, conn: Any) -> dict:
        query_text = params.get("query")
        cpv_codes = params.get("cpv_codes", [])
        buyer_name = params.get("buyer_name")
        winner_name = params.get("winner_name")
        min_value = params.get("min_value")
        max_value = params.get("max_value")
        status = params.get("status")
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        sort_by = params.get("sort_by")
        limit = min(max(params.get("limit", 10), 1), 20)

        conditions: list[str] = []
        sql_params: list[Any] = []
        idx = 1

        if query_text:
            cyrillic_query = _latin_to_cyrillic(query_text) if _is_latin(query_text) else query_text

            select = f"""
SELECT
    tender_id, title,
    LEFT(description, 300) AS description,
    cpv_code, category,
    procuring_entity, delivery_location,
    estimated_value_mkd, actual_value_mkd,
    estimated_value_eur, actual_value_eur,
    publication_date, closing_date, status,
    winner, num_bidders, procedure_type,
    GREATEST(
        similarity(title, ${idx}) * 2 + similarity(COALESCE(description, ''), ${idx}),
        CASE WHEN title ILIKE '%' || ${idx} || '%' THEN 1.5 ELSE 0 END,
        CASE WHEN description ILIKE '%' || ${idx} || '%' THEN 0.8 ELSE 0 END
    ) AS relevance
FROM tenders
"""
            sql_params.append(cyrillic_query)
            idx += 1

            if _is_latin(query_text) and cyrillic_query != query_text:
                conditions.append(
                    f"(title ILIKE '%' || ${idx-1} || '%' OR description ILIKE '%' || ${idx-1} || '%' "
                    f"OR title ILIKE '%' || ${idx} || '%' OR description ILIKE '%' || ${idx} || '%' "
                    f"OR title %> ${idx-1} OR title %> ${idx})"
                )
                sql_params.append(query_text)
                idx += 1
            else:
                conditions.append(
                    f"(title ILIKE '%' || ${idx-1} || '%' OR description ILIKE '%' || ${idx-1} || '%' "
                    f"OR title %> ${idx-1})"
                )
        else:
            select = """
SELECT
    tender_id, title,
    LEFT(description, 300) AS description,
    cpv_code, category,
    procuring_entity, delivery_location,
    estimated_value_mkd, actual_value_mkd,
    estimated_value_eur, actual_value_eur,
    publication_date, closing_date, status,
    winner, num_bidders, procedure_type
FROM tenders
"""

        if cpv_codes:
            cpv_conds = []
            for cpv in cpv_codes:
                cpv_conds.append(f"cpv_code LIKE ${idx}")
                sql_params.append(f"{cpv}%")
                idx += 1
            conditions.append(f"({' OR '.join(cpv_conds)})")

        if buyer_name:
            conditions.append(f"(procuring_entity ILIKE '%' || ${idx} || '%' OR procuring_entity %> ${idx})")
            sql_params.append(buyer_name)
            idx += 1

        if winner_name:
            conditions.append(f"(winner ILIKE '%' || ${idx} || '%' OR winner %> ${idx})")
            sql_params.append(winner_name)
            idx += 1

        if min_value is not None:
            conditions.append(f"COALESCE(estimated_value_mkd, actual_value_mkd, 0) >= ${idx}")
            sql_params.append(float(min_value))
            idx += 1

        if max_value is not None:
            conditions.append(f"COALESCE(estimated_value_mkd, actual_value_mkd, 0) <= ${idx}")
            sql_params.append(float(max_value))
            idx += 1

        if status:
            conditions.append(f"status = ${idx}")
            sql_params.append(status)
            idx += 1

        if date_from:
            conditions.append(f"publication_date >= ${idx}::date")
            sql_params.append(date_from)
            idx += 1

        if date_to:
            conditions.append(f"publication_date <= ${idx}::date")
            sql_params.append(date_to)
            idx += 1

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        if sort_by is None:
            sort_by = "relevance" if query_text else "date_desc"

        order_map = {
            "relevance": "relevance DESC" if query_text else "publication_date DESC NULLS LAST",
            "value_desc": "COALESCE(estimated_value_mkd, actual_value_mkd, 0) DESC",
            "value_asc": "COALESCE(estimated_value_mkd, actual_value_mkd, 0) ASC",
            "date_desc": "publication_date DESC NULLS LAST",
            "date_asc": "publication_date ASC NULLS LAST",
            "closing_date": "closing_date ASC NULLS LAST",
        }
        order_clause = order_map.get(sort_by, "publication_date DESC NULLS LAST")

        sql_params.append(limit)
        full_sql = f"{select}\n{where}\nORDER BY {order_clause}\nLIMIT ${idx}"

        rows = await conn.fetch(full_sql, *sql_params)

        tenders = []
        for r in rows:
            tenders.append({
                "id": r["tender_id"],
                "title": r["title"],
                "description": r["description"],
                "procuring_entity": r["procuring_entity"],
                "delivery_location": r["delivery_location"],
                "status": r["status"],
                "cpv_code": r["cpv_code"],
                "category": r["category"],
                "estimated_value_mkd": float(r["estimated_value_mkd"]) if r["estimated_value_mkd"] else None,
                "actual_value_mkd": float(r["actual_value_mkd"]) if r["actual_value_mkd"] else None,
                "estimated_value_eur": float(r["estimated_value_eur"]) if r["estimated_value_eur"] else None,
                "actual_value_eur": float(r["actual_value_eur"]) if r["actual_value_eur"] else None,
                "publication_date": r["publication_date"].isoformat() if r["publication_date"] else None,
                "closing_date": r["closing_date"].isoformat() if r["closing_date"] else None,
                "winner": r["winner"],
                "num_bidders": r["num_bidders"],
                "procedure_type": r["procedure_type"],
            })

        count = len(tenders)
        summary = f"Found {count} tender(s)"
        if query_text:
            summary += f" matching '{query_text}'"
        if status:
            summary += f" with status '{status}'"
        if cpv_codes:
            summary += f" in CPV sector(s) {', '.join(cpv_codes)}"

        return {
            "data": tenders,
            "count": count,
            "summary": summary,
        }

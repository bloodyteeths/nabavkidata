"""
Product search tools — search MK e-pazar product items and price statistics.

epazar_items schema:
  item_id, tender_id, item_name, item_description, cpv_code,
  quantity, unit, estimated_unit_price_mkd, estimated_total_price_mkd

epazar_tenders schema:
  tender_id, title, contracting_authority, status
"""

from typing import Any


class SearchProductItemsTool:
    name = "search_product_items"
    description = (
        "Search per-item prices and specifications from e-pazar tenders. "
        "MK has 4M+ product items with detailed unit prices."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Product name or description to search for.",
            },
            "cpv_prefix": {
                "type": "string",
                "description": "Optional CPV code prefix filter.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default 10).",
            },
        },
        "required": ["query"],
    }

    async def execute(self, params: dict, conn: Any) -> dict:
        # Handle Gemini sometimes passing "keywords" instead of "query"
        query = params.get("query") or params.get("keywords", "")
        if isinstance(query, list):
            query = " ".join(query)
        query = str(query).strip()
        cpv_prefix = params.get("cpv_prefix")
        limit = min(max(params.get("limit", 10), 1), 20)

        if not query:
            return {"error": "Query is required", "data": [], "count": 0}

        conditions = ["(ei.item_name %> $1 OR ei.item_description %> $1)"]
        sql_params: list[Any] = [query]
        idx = 2

        if cpv_prefix:
            conditions.append(f"ei.cpv_code LIKE ${idx}")
            sql_params.append(f"{cpv_prefix}%")
            idx += 1

        where = " AND ".join(conditions)
        sql_params.append(limit)

        sql = f"""
SELECT
    ei.item_id, ei.item_name, ei.item_description,
    ei.unit, ei.quantity, ei.estimated_unit_price_mkd,
    ei.estimated_total_price_mkd, ei.cpv_code,
    et.tender_id, et.title AS tender_title,
    et.contracting_authority, et.status,
    similarity(ei.item_name, $1) AS relevance
FROM epazar_items ei
LEFT JOIN epazar_tenders et ON et.tender_id = ei.tender_id
WHERE {where}
ORDER BY relevance DESC
LIMIT ${idx}
"""

        rows = await conn.fetch(sql, *sql_params)

        items = []
        for r in rows:
            items.append({
                "item_name": r["item_name"],
                "description": (r["item_description"] or "")[:200],
                "unit": r["unit"],
                "quantity": float(r["quantity"]) if r["quantity"] else None,
                "unit_price_mkd": float(r["estimated_unit_price_mkd"]) if r["estimated_unit_price_mkd"] else None,
                "total_price_mkd": float(r["estimated_total_price_mkd"]) if r["estimated_total_price_mkd"] else None,
                "cpv_code": r["cpv_code"],
                "tender_id": r["tender_id"],
                "tender_title": r["tender_title"],
                "contracting_authority": r["contracting_authority"],
                "tender_status": r["status"],
            })

        return {
            "data": items,
            "count": len(items),
            "summary": f"Found {len(items)} product item(s) matching '{query}'",
        }


class GetPriceStatisticsTool:
    name = "get_price_statistics"
    description = (
        "Get aggregate price statistics (avg/min/max/median) for products matching a query. "
        "Useful for benchmarking prices in MKD."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Product name or type to get price stats for.",
            },
            "cpv_prefix": {
                "type": "string",
                "description": "Optional CPV code prefix filter.",
            },
        },
        "required": ["query"],
    }

    async def execute(self, params: dict, conn: Any) -> dict:
        query = params.get("query") or params.get("keywords", "")
        if isinstance(query, list):
            query = " ".join(query)
        query = str(query).strip()
        cpv_prefix = params.get("cpv_prefix")

        if not query:
            return {"error": "Query is required", "data": None}

        conditions = [
            "(item_name %> $1 OR item_description %> $1)",
            "estimated_unit_price_mkd > 0",
        ]
        sql_params: list[Any] = [query]
        idx = 2

        if cpv_prefix:
            conditions.append(f"cpv_code LIKE ${idx}")
            sql_params.append(f"{cpv_prefix}%")
            idx += 1

        where = " AND ".join(conditions)

        sql = f"""
SELECT
    COUNT(*) AS total,
    AVG(estimated_unit_price_mkd) AS avg_price,
    MIN(estimated_unit_price_mkd) AS min_price,
    MAX(estimated_unit_price_mkd) AS max_price,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY estimated_unit_price_mkd) AS median_price
FROM epazar_items
WHERE {where}
"""

        row = await conn.fetchrow(sql, *sql_params)

        if not row or not row["total"]:
            return {
                "data": None,
                "summary": f"No price data found for '{query}'",
            }

        stats = {
            "total_items": row["total"],
            "avg_price_mkd": round(float(row["avg_price"]), 2),
            "min_price_mkd": round(float(row["min_price"]), 2),
            "max_price_mkd": round(float(row["max_price"]), 2),
            "median_price_mkd": round(float(row["median_price"]), 2),
        }

        return {
            "data": stats,
            "summary": (
                f"Price stats for '{query}' ({stats['total_items']} items): "
                f"avg {stats['avg_price_mkd']:,.0f} МКД, "
                f"range {stats['min_price_mkd']:,.0f} - {stats['max_price_mkd']:,.0f} МКД"
            ),
        }

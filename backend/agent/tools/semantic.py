"""
SemanticSearchTool — vector similarity search for the MK AI agent.

Uses the embedding service to find tenders by meaning rather than keywords.
"""

from typing import Any


class SemanticSearchTool:
    name = "semantic_search"
    description = (
        "Search tenders using AI semantic understanding (vector similarity). "
        "Unlike keyword search, this finds tenders by MEANING — e.g. searching "
        "'gradezni raboti' also finds 'izgradba na patista'. "
        "Use this when keyword search returns poor results, or when the user's "
        "query is conceptual rather than exact. Returns tenders ranked by similarity."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Natural language description of what to search for. "
                    "Be descriptive for best results."
                ),
            },
            "status": {
                "type": "string",
                "description": "Optional: filter by tender status.",
            },
            "cpv_codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional: filter by CPV code prefix(es). E.g. ['90'] for cleaning, "
                    "['72', '48'] for IT. Matches any of the provided prefixes."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (1-20, default 10).",
            },
        },
        "required": ["query"],
    }

    async def execute(self, params: dict, conn: Any) -> dict:
        from services.embedding import semantic_search

        query = params.get("query", "")
        status = params.get("status")
        cpv_codes = params.get("cpv_codes")
        limit = min(max(params.get("limit", 10), 1), 20)

        if not query:
            return {"error": "Query is required", "data": [], "count": 0}

        fetch_limit = limit * 3 if cpv_codes else limit

        try:
            results = await semantic_search(
                conn,
                query=query,
                limit=fetch_limit,
                source_type="tender",
                status_filter=status,
            )
        except Exception:
            return await self._keyword_fallback(conn, query, status, limit)

        if cpv_codes:
            results = [
                r for r in results
                if r.get("cpv_code") and any(r["cpv_code"].startswith(c) for c in cpv_codes)
            ]

        results = results[:limit]

        tenders = []
        for r in results:
            tenders.append({
                "id": r["tender_id"],
                "title": r["title"],
                "description": r["chunk_text"][:300] if r.get("chunk_text") else None,
                "procuring_entity": r.get("procuring_entity"),
                "status": r.get("status"),
                "estimated_value_mkd": r.get("estimated_value_mkd"),
                "actual_value_mkd": r.get("actual_value_mkd"),
                "cpv_code": r.get("cpv_code"),
                "category": r.get("category"),
                "publication_date": r.get("publication_date"),
                "closing_date": r.get("closing_date"),
                "winner": r.get("winner"),
                "num_bidders": r.get("num_bidders"),
                "similarity": round(r["similarity"], 3),
            })

        count = len(tenders)
        summary = f"Found {count} semantically similar tender(s) for '{query}'"
        filters = []
        if status:
            filters.append(f"status: {status}")
        if cpv_codes:
            filters.append(f"CPV: {', '.join(cpv_codes)}")
        if filters:
            summary += f" ({', '.join(filters)})"

        return {
            "data": tenders,
            "count": count,
            "summary": summary,
        }

    async def _keyword_fallback(self, conn: Any, query: str, status: str | None, limit: int) -> dict:
        """Fall back to ILIKE + trigram keyword search when embeddings are unavailable."""
        conditions = ["(title ILIKE '%' || $1 || '%' OR description ILIKE '%' || $1 || '%' OR title %> $1)"]
        sql_params: list[Any] = [query]
        idx = 2

        if status:
            conditions.append(f"status = ${idx}")
            sql_params.append(status)
            idx += 1

        where = "WHERE " + " AND ".join(conditions)
        sql_params.append(limit)

        sql = f"""
SELECT
    tender_id, title, LEFT(description, 300) AS description,
    procuring_entity, status, estimated_value_mkd, actual_value_mkd,
    cpv_code, category,
    publication_date, closing_date, winner, num_bidders,
    GREATEST(
        similarity(title, $1) * 2 + similarity(COALESCE(description, ''), $1),
        CASE WHEN title ILIKE '%' || $1 || '%' THEN 1.5 ELSE 0 END
    ) AS relevance
FROM tenders
{where}
ORDER BY relevance DESC
LIMIT ${idx}
"""
        rows = await conn.fetch(sql, *sql_params)

        tenders = []
        for r in rows:
            tenders.append({
                "id": r["tender_id"],
                "title": r["title"],
                "description": r["description"],
                "procuring_entity": r["procuring_entity"],
                "status": r["status"],
                "estimated_value_mkd": float(r["estimated_value_mkd"]) if r["estimated_value_mkd"] else None,
                "actual_value_mkd": float(r["actual_value_mkd"]) if r["actual_value_mkd"] else None,
                "cpv_code": r["cpv_code"],
                "category": r["category"],
                "publication_date": r["publication_date"].isoformat() if r["publication_date"] else None,
                "closing_date": r["closing_date"].isoformat() if r["closing_date"] else None,
                "winner": r["winner"],
                "num_bidders": r["num_bidders"],
            })

        count = len(tenders)
        summary = (
            f"Semantic search was unavailable - returning {count} keyword result(s) "
            f"for '{query}' instead"
        )
        if status:
            summary += f" (status: {status})"

        return {
            "data": tenders,
            "count": count,
            "summary": summary,
            "fallback": True,
        }


class FindSimilarTendersTool:
    name = "find_similar_tenders"
    description = (
        "Find tenders similar to a specific tender using vector similarity. "
        "Given a tender ID, finds other tenders with similar scope, requirements, "
        "and sector. Useful for competitive analysis or finding related opportunities."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tender_id": {
                "type": "string",
                "description": "ID of the tender to find similar ones for.",
            },
            "status": {
                "type": "string",
                "description": "Optional: filter similar tenders by status.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (1-20, default 10).",
            },
        },
        "required": ["tender_id"],
    }

    async def execute(self, params: dict, conn: Any) -> dict:
        from services.embedding import find_similar_tenders

        tender_id = params.get("tender_id", "")
        status = params.get("status")
        limit = min(max(params.get("limit", 10), 1), 20)

        if not tender_id:
            return {"error": "tender_id is required", "data": [], "count": 0}

        try:
            data = await find_similar_tenders(
                conn,
                tender_id=tender_id,
                limit=limit,
                status_filter=status,
            )
            results = data["results"]
            price_summary = data.get("price_summary")
        except Exception as e:
            return {
                "error": f"Similar tender search failed: {str(e)}",
                "data": [],
                "count": 0,
                "summary": (
                    "Could not find similar tenders - the embedding service is "
                    "unavailable or this tender has not been embedded yet. "
                    "Try using search_tenders with keywords from the tender title instead."
                ),
                "fallback_hint": "search_tenders",
            }

        tenders = []
        for r in results:
            tenders.append({
                "id": r["tender_id"],
                "title": r["title"],
                "procuring_entity": r.get("procuring_entity"),
                "status": r.get("status"),
                "estimated_value_mkd": r.get("estimated_value_mkd"),
                "actual_value_mkd": r.get("actual_value_mkd"),
                "cpv_code": r.get("cpv_code"),
                "category": r.get("category"),
                "publication_date": r.get("publication_date"),
                "closing_date": r.get("closing_date"),
                "winner": r.get("winner"),
                "similarity": round(r["similarity"], 3) if r.get("similarity") is not None else None,
            })

        count = len(tenders)
        summary = f"Found {count} similar tender(s)"
        if price_summary:
            summary += f". {price_summary['text']}"

        return {
            "data": tenders,
            "count": count,
            "summary": summary,
            "price_summary": price_summary,
        }

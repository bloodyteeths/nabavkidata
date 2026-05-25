"""
Document tools — search document metadata and full-text content for MK.

Includes:
- SearchDocumentsTool: search by doc_type, file_name, ai_summary
- SearchDocumentContentTool: full-text search across content_text
"""

from typing import Any


class SearchDocumentsTool:
    """Search tender documents by metadata (file name, type, summary)."""

    name = "search_documents"
    description = (
        "Search tender-related documents by file name, type, or AI summary. "
        "Use this to find specific documents attached to tenders. "
        "Can filter by tender_id and document type."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Free-text search across file_name and ai_summary.",
            },
            "tender_id": {
                "type": "string",
                "description": "Filter documents belonging to a specific tender.",
            },
            "doc_type": {
                "type": "string",
                "description": "Filter by document type.",
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
        tender_id = params.get("tender_id")
        doc_type = params.get("doc_type")
        limit = min(max(params.get("limit", 10), 1), 20)

        conditions: list[str] = []
        sql_params: list[Any] = []
        idx = 1

        if query_text:
            conditions.append(
                f"(d.file_name ILIKE ${idx} OR d.ai_summary ILIKE ${idx})"
            )
            sql_params.append(f"%{query_text}%")
            idx += 1

        if tender_id:
            conditions.append(f"d.tender_id = ${idx}")
            sql_params.append(tender_id)
            idx += 1

        if doc_type:
            conditions.append(f"d.doc_type = ${idx}")
            sql_params.append(doc_type)
            idx += 1

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        sql_params.append(limit)
        sql = f"""
            SELECT
                d.doc_id, d.tender_id, d.doc_type, d.file_name,
                d.file_url, LEFT(d.ai_summary, 500) AS ai_summary,
                t.title AS tender_title,
                t.procuring_entity
            FROM documents d
            JOIN tenders t ON t.tender_id = d.tender_id
            {where}
            ORDER BY d.doc_id DESC
            LIMIT ${idx}
        """

        rows = await conn.fetch(sql, *sql_params)

        documents = []
        for r in rows:
            documents.append({
                "doc_id": str(r["doc_id"]),
                "tender_id": r["tender_id"],
                "tender_title": r["tender_title"],
                "procuring_entity": r["procuring_entity"],
                "doc_type": r["doc_type"],
                "file_name": r["file_name"],
                "file_url": r["file_url"],
                "ai_summary": r["ai_summary"],
            })

        count = len(documents)
        summary = f"Found {count} document(s)"
        if query_text:
            summary += f" matching '{query_text}'"
        if doc_type:
            summary += f" of type '{doc_type}'"
        if tender_id:
            summary += f" for tender {tender_id}"

        return {
            "data": documents,
            "count": count,
            "summary": summary,
        }


class SearchDocumentContentTool:
    """Full-text search across extracted document content."""

    name = "search_document_content"
    description = (
        "Search the actual text extracted from tender documents (PDFs, etc.). "
        "Use this when you need to find specific clauses, requirements, terms, "
        "or specifications inside documents - not just their file names. "
        "Uses PostgreSQL full-text search on the content_text_search tsvector column."
    )
    parameters = {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "One or more keywords to search for inside document text. "
                    "Example: ['osiguruvanje', 'garancija']"
                ),
            },
            "buyer_name": {
                "type": "string",
                "description": "Optionally filter by procuring entity name (partial match).",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (1-10, default 10).",
            },
        },
        "required": ["keywords"],
    }

    async def execute(self, params: dict, conn: Any) -> dict:
        keywords = params.get("keywords", [])
        if not keywords:
            return {
                "data": [],
                "count": 0,
                "summary": "No keywords provided for document content search.",
            }

        buyer_name = params.get("buyer_name")
        limit = min(max(params.get("limit", 10), 1), 10)

        ilike_patterns = [f"%{kw}%" for kw in keywords]

        conditions: list[str] = [
            "d.content_text IS NOT NULL",
            "LENGTH(d.content_text) > 100",
            "d.content_text ILIKE ANY($1)",
        ]
        sql_params: list[Any] = [ilike_patterns]
        idx = 2

        if buyer_name:
            conditions.append(f"t.procuring_entity ILIKE ${idx}")
            sql_params.append(f"%{buyer_name}%")
            idx += 1

        where = "WHERE " + " AND ".join(conditions)

        first_keyword = keywords[0]
        sql_params.append(first_keyword)
        kw_idx = idx
        idx += 1

        sql_params.append(limit)
        limit_idx = idx

        sql = f"""
            SELECT
                d.doc_id,
                d.file_name,
                d.doc_type,
                SUBSTRING(
                    d.content_text
                    FROM GREATEST(1, POSITION(lower(${kw_idx}) IN lower(d.content_text)) - 500)
                    FOR 3000
                ) AS content_snippet,
                t.title AS tender_title,
                t.tender_id,
                t.procuring_entity,
                t.status,
                d.file_url
            FROM documents d
            JOIN tenders t ON d.tender_id = t.tender_id
            {where}
            ORDER BY LENGTH(d.content_text) DESC
            LIMIT ${limit_idx}
        """

        rows = await conn.fetch(sql, *sql_params)

        documents = []
        for r in rows:
            documents.append({
                "doc_id": str(r["doc_id"]),
                "file_name": r["file_name"],
                "doc_type": r["doc_type"],
                "content_snippet": r["content_snippet"],
                "tender_title": r["tender_title"],
                "tender_id": r["tender_id"],
                "procuring_entity": r["procuring_entity"],
                "status": r["status"],
                "file_url": r["file_url"],
            })

        count = len(documents)
        kw_str = "', '".join(keywords)
        summary = f"Found {count} document(s) containing '{kw_str}' in extracted text."
        if buyer_name:
            summary += f" Buyer filter: '{buyer_name}'."

        return {
            "data": documents,
            "count": count,
            "summary": summary,
        }

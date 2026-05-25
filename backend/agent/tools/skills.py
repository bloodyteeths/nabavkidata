"""
Compound skill tools — high-level operations that chain multiple tools
in parallel to reduce Gemini API round-trips.
"""

import asyncio
from typing import Any


class SmartSearchSkill:
    """Run semantic + keyword + CPV search in parallel and deduplicate."""

    name = "smart_search"
    description = (
        "PREFERRED search tool. Runs semantic search, keyword/ILIKE search, AND CPV "
        "code search in parallel for maximum coverage, then deduplicates. "
        "Use this for any 'find me tenders' type query. "
        "IMPORTANT: Always pass cpv_prefix when you know the sector "
        "(e.g. '72' for IT, '45' for construction, '33' for medical). "
        "Supports both Latin and Cyrillic input (auto-converts)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query (Latin or Cyrillic).",
            },
            "cpv_prefix": {
                "type": "string",
                "description": (
                    "CPV code prefix — ALWAYS use when sector is known. "
                    "E.g. '72' for IT, '45' construction, '33' medical, "
                    "'34' vehicles, '90' cleaning, '15' food, '30' office equipment."
                ),
            },
            "status": {
                "type": "string",
                "description": "Filter: open, awarded, completed, closed, cancelled.",
            },
            "min_value": {
                "type": "number",
                "description": "Minimum tender value in MKD.",
            },
            "max_value": {
                "type": "number",
                "description": "Maximum tender value in MKD.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default 10, max 20).",
            },
        },
        "required": ["query"],
    }

    def __init__(self):
        self._registry = None

    async def execute(self, params: dict, conn: Any) -> dict:
        if not self._registry:
            from agent.tools import ToolRegistry
            self._registry = ToolRegistry()
            self._registry.discover()

        semantic_tool = self._registry.get("semantic_search")
        keyword_tool = self._registry.get("search_tenders")

        query = params.get("query", "")
        limit = min(params.get("limit", 10), 20)
        status = params.get("status")
        min_value = params.get("min_value")
        max_value = params.get("max_value")
        cpv_prefix = params.get("cpv_prefix")

        tasks = []

        # Task 1: Semantic search
        if semantic_tool:
            sem_params = {"query": query, "limit": limit}
            if status:
                sem_params["status"] = status
            if cpv_prefix:
                sem_params["cpv_codes"] = [cpv_prefix]
            tasks.append(semantic_tool.execute(sem_params, conn))
        else:
            tasks.append(asyncio.coroutine(lambda: {"data": []})())

        # Task 2: Keyword + ILIKE search (now with bilingual support)
        if keyword_tool:
            kw_params = {"query": query, "limit": limit}
            if status:
                kw_params["status"] = status
            if min_value:
                kw_params["min_value"] = min_value
            if max_value:
                kw_params["max_value"] = max_value
            if cpv_prefix:
                kw_params["cpv_codes"] = [cpv_prefix]
            tasks.append(keyword_tool.execute(kw_params, conn))
        else:
            tasks.append(asyncio.coroutine(lambda: {"data": []})())

        # Task 3: CPV-only search (no text filter, just sector + date sorted)
        if cpv_prefix and keyword_tool:
            cpv_params = {"cpv_codes": [cpv_prefix], "limit": limit, "sort_by": "date_desc"}
            if status:
                cpv_params["status"] = status
            if min_value:
                cpv_params["min_value"] = min_value
            if max_value:
                cpv_params["max_value"] = max_value
            tasks.append(keyword_tool.execute(cpv_params, conn))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge and deduplicate by tender ID
        seen_ids = set()
        combined = []
        for result in results:
            if isinstance(result, Exception):
                continue
            items = result.get("data", [])
            if isinstance(items, list):
                for item in items:
                    tid = item.get("id") or item.get("tender_id")
                    if tid and tid not in seen_ids:
                        seen_ids.add(tid)
                        combined.append(item)

        # Sort: semantic results first, then by value
        combined.sort(
            key=lambda x: (
                -(x.get("similarity") or 0),
                -(x.get("estimated_value_mkd") or x.get("actual_value_mkd") or 0),
            )
        )

        combined = combined[:limit]

        methods = ["semantic", "keyword"]
        if cpv_prefix:
            methods.append(f"cpv_{cpv_prefix}")

        return {
            "data": combined,
            "total_found": len(combined),
            "search_methods": methods,
            "summary": (
                f"Found {len(combined)} tenders for '{query}' "
                f"(searched {' + '.join(methods)} in parallel)"
            ),
        }

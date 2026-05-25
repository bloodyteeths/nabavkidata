"""
Analytics tools — market overview and upcoming deadlines for MK.
"""

from typing import Any


class MarketOverviewTool:
    name = "market_overview"
    description = (
        "Get market overview for a procurement sector. Returns total tenders, "
        "values, top buyers, top winners, AND recent example tenders by CPV sector. "
        "Uses the CPV code prefix (2-digit) to identify sectors. All values in MKD. "
        "This gives a complete picture: stats + examples in one call."
    )
    parameters = {
        "type": "object",
        "properties": {
            "cpv_prefix": {
                "type": "string",
                "description": (
                    "2-digit CPV sector prefix, e.g. '72' for IT, '45' for construction, "
                    "'33' for medical, '85' for health. Leave blank for all sectors."
                ),
            },
            "top_n": {
                "type": "integer",
                "description": "Number of sectors to return if no prefix given (default 10).",
            },
        },
        "required": [],
    }

    async def execute(self, params: dict, conn: Any) -> dict:
        cpv_prefix = params.get("cpv_prefix")
        top_n = min(params.get("top_n", 10), 50)

        if cpv_prefix:
            rows = await conn.fetch(
                """
                SELECT
                    LEFT(cpv_code, 2) AS cpv_prefix,
                    MAX(category) AS sector_name,
                    COUNT(*) AS tender_count,
                    COUNT(*) FILTER (WHERE status = 'awarded') AS awarded_count,
                    COUNT(*) FILTER (WHERE status = 'open') AS open_count,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed_count,
                    SUM(estimated_value_mkd) AS total_estimated_mkd,
                    SUM(actual_value_mkd) AS total_actual_mkd,
                    AVG(COALESCE(actual_value_mkd, estimated_value_mkd))
                        FILTER (WHERE COALESCE(actual_value_mkd, estimated_value_mkd) > 0) AS avg_value_mkd,
                    MIN(COALESCE(actual_value_mkd, estimated_value_mkd))
                        FILTER (WHERE COALESCE(actual_value_mkd, estimated_value_mkd) > 0) AS min_value_mkd,
                    MAX(COALESCE(actual_value_mkd, estimated_value_mkd)) AS max_value_mkd,
                    COUNT(DISTINCT procuring_entity) AS unique_buyers,
                    COUNT(DISTINCT winner) FILTER (WHERE winner IS NOT NULL) AS unique_winners,
                    MIN(publication_date) AS earliest_tender,
                    MAX(publication_date) AS latest_tender
                FROM tenders
                WHERE cpv_code LIKE $1
                GROUP BY LEFT(cpv_code, 2)
                """,
                f"{cpv_prefix}%",
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    LEFT(cpv_code, 2) AS cpv_prefix,
                    MAX(category) AS sector_name,
                    COUNT(*) AS tender_count,
                    COUNT(*) FILTER (WHERE status = 'awarded') AS awarded_count,
                    COUNT(*) FILTER (WHERE status = 'open') AS open_count,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed_count,
                    SUM(estimated_value_mkd) AS total_estimated_mkd,
                    SUM(actual_value_mkd) AS total_actual_mkd,
                    AVG(COALESCE(actual_value_mkd, estimated_value_mkd))
                        FILTER (WHERE COALESCE(actual_value_mkd, estimated_value_mkd) > 0) AS avg_value_mkd,
                    MIN(COALESCE(actual_value_mkd, estimated_value_mkd))
                        FILTER (WHERE COALESCE(actual_value_mkd, estimated_value_mkd) > 0) AS min_value_mkd,
                    MAX(COALESCE(actual_value_mkd, estimated_value_mkd)) AS max_value_mkd,
                    COUNT(DISTINCT procuring_entity) AS unique_buyers,
                    COUNT(DISTINCT winner) FILTER (WHERE winner IS NOT NULL) AS unique_winners,
                    MIN(publication_date) AS earliest_tender,
                    MAX(publication_date) AS latest_tender
                FROM tenders
                WHERE cpv_code IS NOT NULL
                GROUP BY LEFT(cpv_code, 2)
                ORDER BY COUNT(*) DESC
                LIMIT $1
                """,
                top_n,
            )

        sectors = []
        for r in rows:
            sectors.append({
                "cpv_prefix": r["cpv_prefix"],
                "sector_name": r["sector_name"],
                "tender_count": r["tender_count"],
                "awarded_count": r["awarded_count"],
                "open_count": r["open_count"],
                "completed_count": r["completed_count"],
                "total_estimated_mkd": float(r["total_estimated_mkd"]) if r["total_estimated_mkd"] else 0,
                "total_actual_mkd": float(r["total_actual_mkd"]) if r["total_actual_mkd"] else 0,
                "avg_value_mkd": float(r["avg_value_mkd"]) if r["avg_value_mkd"] else 0,
                "min_value_mkd": float(r["min_value_mkd"]) if r["min_value_mkd"] else 0,
                "max_value_mkd": float(r["max_value_mkd"]) if r["max_value_mkd"] else 0,
                "unique_buyers": r["unique_buyers"],
                "unique_winners": r["unique_winners"],
                "earliest_tender": r["earliest_tender"].isoformat() if r["earliest_tender"] else None,
                "latest_tender": r["latest_tender"].isoformat() if r["latest_tender"] else None,
            })

        # For specific sector: also fetch top winners and recent tenders
        top_winners = []
        recent_tenders = []
        if cpv_prefix:
            winner_rows = await conn.fetch(
                """
                SELECT winner, COUNT(*) as wins,
                    SUM(COALESCE(actual_value_mkd, estimated_value_mkd, 0)) as total_value
                FROM tenders
                WHERE cpv_code LIKE $1 AND winner IS NOT NULL AND winner != ''
                GROUP BY winner ORDER BY wins DESC LIMIT 10
                """,
                f"{cpv_prefix}%",
            )
            top_winners = [
                {"name": w["winner"], "wins": w["wins"], "total_value_mkd": float(w["total_value"])}
                for w in winner_rows
            ]

            recent_rows = await conn.fetch(
                """
                SELECT tender_id, title, procuring_entity, status,
                    estimated_value_mkd, actual_value_mkd, publication_date, closing_date, winner
                FROM tenders
                WHERE cpv_code LIKE $1
                ORDER BY publication_date DESC NULLS LAST
                LIMIT 10
                """,
                f"{cpv_prefix}%",
            )
            recent_tenders = [
                {
                    "id": r["tender_id"],
                    "title": r["title"],
                    "procuring_entity": r["procuring_entity"],
                    "status": r["status"],
                    "estimated_value_mkd": float(r["estimated_value_mkd"]) if r["estimated_value_mkd"] else None,
                    "actual_value_mkd": float(r["actual_value_mkd"]) if r["actual_value_mkd"] else None,
                    "publication_date": r["publication_date"].isoformat() if r["publication_date"] else None,
                    "closing_date": r["closing_date"].isoformat() if r["closing_date"] else None,
                    "winner": r["winner"],
                }
                for r in recent_rows
            ]

        result_data = {
            "sectors": sectors,
            "top_winners": top_winners,
            "recent_tenders": recent_tenders,
        }

        if cpv_prefix and sectors:
            s = sectors[0]
            summary = (
                f"Sector CPV {s['cpv_prefix']} ({s['sector_name']}): "
                f"{s['tender_count']} total tenders, {s['open_count']} open, "
                f"{s['awarded_count']} awarded, "
                f"avg value {s['avg_value_mkd']:,.0f} MKD, "
                f"range {s['min_value_mkd']:,.0f} - {s['max_value_mkd']:,.0f} MKD, "
                f"{s['unique_buyers']} buyers, {s['unique_winners']} winners. "
                f"Includes {len(top_winners)} top winners and {len(recent_tenders)} recent tenders."
            )
        else:
            summary = f"Top {len(sectors)} sectors by tender count."

        return {"data": result_data, "summary": summary}


class UpcomingDeadlinesTool:
    name = "upcoming_deadlines"
    description = (
        "Find open tenders with upcoming closing dates. "
        "Returns tenders closing within the specified number of days, "
        "sorted by closing date (soonest first). "
        "Use this to find urgent opportunities or to warn about expiring deadlines."
    )
    parameters = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Number of days to look ahead (default 7, max 90).",
            },
            "cpv_prefix": {
                "type": "string",
                "description": "Optional CPV prefix to filter by sector.",
            },
            "buyer_name": {
                "type": "string",
                "description": "Optional procuring entity filter (partial match).",
            },
            "min_value": {
                "type": "number",
                "description": "Minimum estimated value in MKD.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (1-20, default 10).",
            },
        },
        "required": [],
    }

    async def execute(self, params: dict, conn: Any) -> dict:
        days = min(max(params.get("days", 7), 1), 90)
        cpv_prefix = params.get("cpv_prefix")
        buyer_name = params.get("buyer_name")
        min_value = params.get("min_value")
        limit = min(max(params.get("limit", 10), 1), 20)

        conditions: list[str] = [
            "status = 'open'",
            "closing_date IS NOT NULL",
            "closing_date >= CURRENT_DATE",
            f"closing_date <= CURRENT_DATE + ${1}::int * INTERVAL '1 day'",
        ]
        sql_params: list[Any] = [days]
        idx = 2

        if cpv_prefix:
            conditions.append(f"cpv_code LIKE ${idx}")
            sql_params.append(f"{cpv_prefix}%")
            idx += 1

        if buyer_name:
            conditions.append(f"procuring_entity ILIKE ${idx}")
            sql_params.append(f"%{buyer_name}%")
            idx += 1

        if min_value is not None:
            conditions.append(f"COALESCE(estimated_value_mkd, 0) >= ${idx}")
            sql_params.append(float(min_value))
            idx += 1

        where = "WHERE " + " AND ".join(conditions)

        sql_params.append(limit)
        limit_idx = idx

        sql = f"""
            SELECT
                tender_id, title, procuring_entity,
                estimated_value_mkd, closing_date,
                cpv_code, category, procedure_type,
                delivery_location,
                closing_date - CURRENT_DATE AS days_remaining
            FROM tenders
            {where}
            ORDER BY closing_date ASC
            LIMIT ${limit_idx}
        """

        rows = await conn.fetch(sql, *sql_params)

        tenders = []
        for r in rows:
            tenders.append({
                "id": r["tender_id"],
                "title": r["title"],
                "procuring_entity": r["procuring_entity"],
                "estimated_value_mkd": float(r["estimated_value_mkd"]) if r["estimated_value_mkd"] else None,
                "closing_date": r["closing_date"].isoformat() if r["closing_date"] else None,
                "days_remaining": r["days_remaining"].days if r["days_remaining"] else None,
                "cpv_code": r["cpv_code"],
                "category": r["category"],
                "procedure_type": r["procedure_type"],
                "delivery_location": r["delivery_location"],
            })

        count = len(tenders)
        summary = f"Found {count} open tender(s) closing within {days} days."
        if cpv_prefix:
            summary += f" CPV sector: {cpv_prefix}."
        if buyer_name:
            summary += f" Buyer: {buyer_name}."

        return {
            "data": tenders,
            "count": count,
            "summary": summary,
        }

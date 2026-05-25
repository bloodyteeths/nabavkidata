"""
BuyerProfileTool — analyses a buyer's procurement patterns and spending for MK.

Queries the tenders table to build a profile of a procuring entity:
total spend, preferred winners, categories, statuses, etc.
"""

from typing import Any


class BuyerProfileTool:
    name = "buyer_profile"
    description = (
        "Analyse a buyer's (procuring entity) procurement profile. "
        "Returns total tenders, total spend, top winners, categories, "
        "statuses, and recent activity. Use for buyer research "
        "or understanding an organisation's procurement patterns."
    )
    parameters = {
        "type": "object",
        "properties": {
            "buyer_name": {
                "type": "string",
                "description": "Name of the procuring entity (uses fuzzy/trigram matching).",
            },
        },
        "required": ["buyer_name"],
    }

    async def execute(self, params: dict, conn: Any) -> dict:
        buyer_name = params["buyer_name"]

        # Find the best-matching procuring entity
        overview = await conn.fetchrow(
            """
            SELECT
                procuring_entity,
                COUNT(*) AS total_tenders,
                COUNT(*) FILTER (WHERE status = 'awarded') AS awarded_count,
                COUNT(*) FILTER (WHERE status = 'open') AS open_count,
                COUNT(*) FILTER (WHERE status = 'closed') AS closed_count,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_count,
                SUM(actual_value_mkd) AS total_spend_mkd,
                AVG(actual_value_mkd) FILTER (WHERE actual_value_mkd > 0) AS avg_contract_value_mkd,
                COUNT(DISTINCT winner) FILTER (WHERE winner IS NOT NULL) AS unique_winners,
                MIN(publication_date) AS first_tender,
                MAX(publication_date) AS latest_tender
            FROM tenders
            WHERE procuring_entity %> $1
            GROUP BY procuring_entity
            ORDER BY similarity(procuring_entity, $1) DESC
            LIMIT 1
            """,
            buyer_name,
        )

        if not overview:
            return {
                "data": None,
                "count": 0,
                "summary": f"No buyer found matching '{buyer_name}'. Try a different spelling or a shorter name.",
            }

        matched_name = overview["procuring_entity"]

        # Get top winners
        top_winners = await conn.fetch(
            """
            SELECT
                winner,
                COUNT(*) AS wins,
                SUM(actual_value_mkd) AS total_value_mkd,
                AVG(actual_value_mkd) AS avg_value_mkd
            FROM tenders
            WHERE procuring_entity = $1
              AND winner IS NOT NULL
            GROUP BY winner
            ORDER BY wins DESC, total_value_mkd DESC NULLS LAST
            LIMIT 10
            """,
            matched_name,
        )

        winners = []
        for w in top_winners:
            winners.append({
                "name": w["winner"],
                "wins": w["wins"],
                "total_value_mkd": float(w["total_value_mkd"]) if w["total_value_mkd"] else None,
                "avg_value_mkd": float(w["avg_value_mkd"]) if w["avg_value_mkd"] else None,
            })

        # Get top categories
        top_categories = await conn.fetch(
            """
            SELECT
                category,
                LEFT(cpv_code, 2) AS cpv_prefix,
                COUNT(*) AS tender_count,
                SUM(COALESCE(actual_value_mkd, estimated_value_mkd, 0)) AS total_value_mkd
            FROM tenders
            WHERE procuring_entity = $1
              AND category IS NOT NULL
            GROUP BY category, LEFT(cpv_code, 2)
            ORDER BY tender_count DESC
            LIMIT 10
            """,
            matched_name,
        )

        categories = []
        for c in top_categories:
            categories.append({
                "category": c["category"],
                "cpv_prefix": c["cpv_prefix"],
                "tender_count": c["tender_count"],
                "total_value_mkd": float(c["total_value_mkd"]) if c["total_value_mkd"] else 0,
            })

        # Get recent tenders
        recent = await conn.fetch(
            """
            SELECT
                tender_id, title, status, estimated_value_mkd, actual_value_mkd,
                publication_date, closing_date, winner
            FROM tenders
            WHERE procuring_entity = $1
            ORDER BY publication_date DESC NULLS LAST
            LIMIT 5
            """,
            matched_name,
        )

        recent_tenders = []
        for r in recent:
            recent_tenders.append({
                "id": r["tender_id"],
                "title": r["title"],
                "status": r["status"],
                "estimated_value_mkd": float(r["estimated_value_mkd"]) if r["estimated_value_mkd"] else None,
                "actual_value_mkd": float(r["actual_value_mkd"]) if r["actual_value_mkd"] else None,
                "publication_date": r["publication_date"].isoformat() if r["publication_date"] else None,
                "closing_date": r["closing_date"].isoformat() if r["closing_date"] else None,
                "winner": r["winner"],
            })

        total_spend = float(overview["total_spend_mkd"]) if overview["total_spend_mkd"] else 0
        avg_value = float(overview["avg_contract_value_mkd"]) if overview["avg_contract_value_mkd"] else 0

        profile = {
            "procuring_entity": matched_name,
            "total_tenders": overview["total_tenders"],
            "awarded_count": overview["awarded_count"],
            "open_count": overview["open_count"],
            "closed_count": overview["closed_count"],
            "cancelled_count": overview["cancelled_count"],
            "total_spend_mkd": total_spend,
            "avg_contract_value_mkd": avg_value,
            "unique_winners": overview["unique_winners"],
            "first_tender": overview["first_tender"].isoformat() if overview["first_tender"] else None,
            "latest_tender": overview["latest_tender"].isoformat() if overview["latest_tender"] else None,
            "top_winners": winners,
            "top_categories": categories,
            "recent_tenders": recent_tenders,
        }

        return {
            "data": profile,
            "summary": (
                f"Buyer profile for '{matched_name}': "
                f"{overview['total_tenders']} total tenders, "
                f"{total_spend:,.0f} MKD total spend, "
                f"{avg_value:,.0f} MKD avg contract value, "
                f"{overview['unique_winners']} unique winners."
            ),
        }

"""
GetTenderTool — retrieve full details of a specific tender by ID.
"""

from typing import Any


class GetTenderTool:
    name = "get_tender"
    description = (
        "Get full details of a specific tender by its ID. "
        "Use this when the user asks about a specific tender, says 'tell me more about' "
        "a tender, or when you need tender details for analysis. "
        "Returns title, buyer, value, deadline, status, description, documents, and lot awards."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tender_id": {
                "type": "string",
                "description": "ID of the tender.",
            },
        },
        "required": ["tender_id"],
    }

    async def execute(self, params: dict, conn: Any) -> dict:
        tender_id = params.get("tender_id")

        if not tender_id:
            return {
                "data": None,
                "summary": "Please provide a tender_id.",
            }

        row = await conn.fetchrow(
            """
            SELECT
                tender_id, title, description, status,
                procuring_entity, contact_person, contact_email, contact_phone,
                estimated_value_mkd, actual_value_mkd,
                estimated_value_eur, actual_value_eur,
                publication_date, closing_date, opening_date,
                cpv_code, category, procedure_type, evaluation_method,
                winner, num_bidders, delivery_location, contract_duration,
                has_lots, num_lots, source_url, source_category
            FROM tenders
            WHERE tender_id = $1
            """,
            tender_id,
        )

        if not row:
            return {
                "data": None,
                "summary": f"No tender found with ID '{tender_id}'.",
            }

        tender = {
            "id": row["tender_id"],
            "title": row["title"],
            "description": (row["description"] or "")[:2000],
            "status": row["status"],
            "procuring_entity": row["procuring_entity"],
            "contact_person": row["contact_person"],
            "contact_email": row["contact_email"],
            "contact_phone": row["contact_phone"],
            "estimated_value_mkd": float(row["estimated_value_mkd"]) if row["estimated_value_mkd"] else None,
            "actual_value_mkd": float(row["actual_value_mkd"]) if row["actual_value_mkd"] else None,
            "estimated_value_eur": float(row["estimated_value_eur"]) if row["estimated_value_eur"] else None,
            "actual_value_eur": float(row["actual_value_eur"]) if row["actual_value_eur"] else None,
            "publication_date": str(row["publication_date"]) if row["publication_date"] else None,
            "closing_date": str(row["closing_date"]) if row["closing_date"] else None,
            "opening_date": str(row["opening_date"]) if row["opening_date"] else None,
            "cpv_code": row["cpv_code"],
            "category": row["category"],
            "procedure_type": row["procedure_type"],
            "evaluation_method": row["evaluation_method"],
            "winner": row["winner"],
            "num_bidders": row["num_bidders"],
            "delivery_location": row["delivery_location"],
            "contract_duration": row["contract_duration"],
            "has_lots": row["has_lots"],
            "num_lots": row["num_lots"],
            "source_url": row["source_url"],
            "source_category": row["source_category"],
        }

        docs = await conn.fetch(
            """
            SELECT doc_id, doc_type, file_name, file_url, ai_summary
            FROM documents
            WHERE tender_id = $1
            ORDER BY doc_type, file_name
            LIMIT 20
            """,
            tender_id,
        )
        tender["documents"] = [
            {
                "doc_id": str(d["doc_id"]),
                "doc_type": d["doc_type"],
                "file_name": d["file_name"],
                "file_url": d["file_url"],
                "ai_summary": d["ai_summary"],
            }
            for d in docs
        ]

        lot_awards = await conn.fetch(
            """
            SELECT lot_numbers, winner_name, contract_value_mkd,
                   contract_value_no_vat, contract_date, contract_type,
                   award_number
            FROM lot_awards
            WHERE tender_id = $1
            ORDER BY award_number NULLS LAST
            LIMIT 50
            """,
            tender_id,
        )
        tender["lot_awards"] = [
            {
                "lot_numbers": la["lot_numbers"],
                "award_number": la["award_number"],
                "winner_name": la["winner_name"],
                "contract_value_mkd": float(la["contract_value_mkd"]) if la["contract_value_mkd"] else None,
                "contract_value_no_vat": float(la["contract_value_no_vat"]) if la["contract_value_no_vat"] else None,
                "contract_date": str(la["contract_date"]) if la["contract_date"] else None,
                "contract_type": la["contract_type"],
            }
            for la in lot_awards
        ]

        value = tender["estimated_value_mkd"] or tender["actual_value_mkd"]
        value_str = f"{value:,.0f} MKD" if value else "undisclosed"

        return {
            "data": tender,
            "summary": (
                f"Tender: {tender['title']} | Buyer: {tender['procuring_entity']} | "
                f"Value: {value_str} | Status: {tender['status']} | "
                f"{len(tender['documents'])} documents, {len(tender['lot_awards'])} lot awards"
            ),
        }

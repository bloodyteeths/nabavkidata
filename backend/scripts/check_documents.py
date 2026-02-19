import asyncio
import os
from datetime import datetime, timezone

import asyncpg

"""
Quick validation script for document coverage on active tenders.

Usage:
  DATABASE_URL=postgresql+asyncpg://... python scripts/check_documents.py

Outputs counts and highlights tenders missing documents or with failed extraction.
"""


async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    conn = await asyncpg.connect(db_url)
    try:
        total_docs = await conn.fetchval("SELECT COUNT(*) FROM documents")
        total_tenders = await conn.fetchval("SELECT COUNT(*) FROM tenders")
        latest = await conn.fetch(
            """
            SELECT t.tender_id, t.created_at, COALESCE(d.doc_count,0) as docs
            FROM tenders t
            LEFT JOIN (
                SELECT tender_id, COUNT(*) as doc_count
                FROM documents
                GROUP BY tender_id
            ) d ON d.tender_id = t.tender_id
            WHERE t.source_category = 'active'
            ORDER BY t.created_at DESC
            LIMIT 20
            """
        )
        failures = await conn.fetch(
            """
            SELECT tender_id, doc_id, extraction_status
            FROM documents
            WHERE extraction_status NOT IN ('success', 'pending')
            ORDER BY uploaded_at DESC
            LIMIT 20
            """
        )
        now = datetime.now(timezone.utc).isoformat()
        print(
            {
                "timestamp": now,
                "total_tenders": total_tenders,
                "total_documents": total_docs,
                "latest_active": [
                    {
                        "tender_id": row["tender_id"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                        "documents": row["docs"],
                    }
                    for row in latest
                ],
                "failed_documents": [
                    {
                        "tender_id": row["tender_id"],
                        "doc_id": str(row["doc_id"]),
                        "status": row["extraction_status"],
                    }
                    for row in failures
                ],
            }
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

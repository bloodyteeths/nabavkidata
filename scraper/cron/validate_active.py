import asyncio
import os
from datetime import datetime, timezone
import asyncpg
from dotenv import load_dotenv
load_dotenv()


THRESHOLD_HOURS = 4

async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return

    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    conn = await asyncpg.connect(db_url)
    try:
        latest = await conn.fetchrow(
            "SELECT tender_id, created_at, updated_at, source_category FROM tenders ORDER BY created_at DESC LIMIT 5"
        )
        count = await conn.fetchval("SELECT COUNT(*) FROM tenders")
        now = datetime.now(timezone.utc)
        anomalies = []
        if latest and latest[1]:
            delta_hours = (now - latest[1]).total_seconds() / 3600
            if delta_hours > THRESHOLD_HOURS:
                anomalies.append(f"latest_tender_older_than_{THRESHOLD_HOURS}h")
        print({
            "latest": {
                "tender_id": latest[0] if latest else None,
                "created_at": latest[1].isoformat() if latest and latest[1] else None,
                "source_category": latest[3] if latest else None,
            },
            "total": count,
            "anomalies": anomalies,
        })
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())

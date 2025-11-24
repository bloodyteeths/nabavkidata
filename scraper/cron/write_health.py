import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

DEFAULT_HEALTH_PATH = Path("/var/log/nabavkidata/health.json")


def parse_args():
    parser = argparse.ArgumentParser(description="Write scraper health JSON")
    parser.add_argument("--status", required=True, choices=["success", "failure"], help="Run status")
    parser.add_argument("--dataset", default="active", help="Dataset name")
    parser.add_argument("--log-file", required=True, help="Scrapy log file path")
    parser.add_argument("--started", required=True, help="Run start ISO timestamp")
    parser.add_argument("--finished", required=True, help="Run end ISO timestamp")
    parser.add_argument("--error-count", type=int, default=0, help="Number of errors seen in log")
    parser.add_argument("--exit-code", type=int, default=0, help="Scrapy exit code")
    return parser.parse_args()


async def get_db_stats():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None

    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    conn = await asyncpg.connect(db_url)
    try:
        latest = await conn.fetchrow(
            "SELECT tender_id, created_at, updated_at, source_category FROM tenders ORDER BY created_at DESC LIMIT 1"
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM tenders")
        return {
            "latest_tender_id": latest[0] if latest else None,
            "latest_created_at": latest[1].isoformat() if latest and latest[1] else None,
            "latest_source_category": latest[3] if latest else None,
            "total_tenders": total,
        }
    finally:
        await conn.close()


def compute_anomalies(db_stats, finished_iso, dataset):
    if not db_stats or not db_stats.get("latest_created_at"):
        return ["missing_db_stats"]

    anomalies = []
    try:
        latest_dt = datetime.fromisoformat(db_stats["latest_created_at"])
        finished_dt = datetime.fromisoformat(finished_iso)
        if latest_dt.tzinfo is None:
            latest_dt = latest_dt.replace(tzinfo=timezone.utc)
        delta_hours = (finished_dt - latest_dt).total_seconds() / 3600
        if dataset == "active" and delta_hours > 4:
            anomalies.append(f"latest_tender_older_than_4h ({delta_hours:.1f}h)")
    except Exception:
        anomalies.append("timestamp_parse_failed")
    return anomalies


async def main():
    args = parse_args()
    db_stats = await get_db_stats()
    anomalies = compute_anomalies(db_stats, args.finished, args.dataset)

    health = {
        "dataset": args.dataset,
        "status": args.status,
        "scrapy_exit_code": args.exit_code,
        "log_file": args.log_file,
        "error_count": args.error_count,
        "started_at": args.started,
        "finished_at": args.finished,
        "db": db_stats,
        "anomalies": anomalies,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    DEFAULT_HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_HEALTH_PATH.write_text(json.dumps(health, indent=2))
    print(json.dumps(health, indent=2))

if __name__ == "__main__":
    asyncio.run(main())

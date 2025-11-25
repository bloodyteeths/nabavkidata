import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import asyncio
import aiohttp
import os

HEALTH_PATH = Path("/var/log/nabavkidata/health.json")
THRESHOLD_HOURS = 4

async def send_slack(msg: str, health=None):
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        return
    payload = {"text": msg}
    if health:
        payload["health"] = health
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(webhook, json=payload, timeout=10)
    except Exception:
        pass

async def main():
    if not HEALTH_PATH.exists():
        await send_slack("[nabavkidata] health.json missing; cron may not be running")
        return
    data = json.loads(HEALTH_PATH.read_text())
    finished_at = data.get("finished_at")
    status = data.get("status")
    now = datetime.now(timezone.utc)
    if not finished_at:
        await send_slack("[nabavkidata] health.json missing finished_at", data)
        return
    try:
        finished_dt = datetime.fromisoformat(finished_at)
        if finished_dt.tzinfo is None:
            finished_dt = finished_dt.replace(tzinfo=timezone.utc)
    except Exception:
        await send_slack("[nabavkidata] health.json finished_at parse error", data)
        return
    delta = now - finished_dt
    if delta > timedelta(hours=THRESHOLD_HOURS):
        await send_slack(f"[nabavkidata] Scraper stale: last run {delta} ago", data)
    if status != "success":
        await send_slack(f"[nabavkidata] Scraper status {status}", data)

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Detect tenders our bid-service clients have won (success-fee pipeline).

Ported from BidFinder (tenderuk/cron/detect_client_wins.py). For every bid job
we prepared that reached submitted/approved/won, compare the tender's award
data (tender_bidders.is_winner rows, plus tenders.winner) against the client's
company name with a pg_trgm-style similarity on normalised names
(services/client_wins.py). A match >= WIN_MATCH_THRESHOLD inserts a
'suspected' client_wins row and emails the admin once ("win_detected"). Nothing
is charged here: the admin confirms in /admin/wins, which sends the client a
7-day notice and creates a DRAFT Stripe invoice.

Usage:
    cd /home/ubuntu/nabavkidata/backend
    python3 crons/detect_client_wins.py [--dry-run]

Cron (not yet in scraper/cron/setup_crontab.sh — add by hand):
    30 6 * * * cd /home/ubuntu/nabavkidata/backend && /usr/bin/python3 crons/detect_client_wins.py >> /var/log/nabavkidata/detect_client_wins.log 2>&1
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from db_pool import get_asyncpg_pool  # noqa: E402
from services import bid_notifications, client_wins  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("detect_client_wins")

CANDIDATES_SQL = """
    SELECT j.*, u.company_name, u.success_fee_pct AS u_pct, u.email, t.title, t.procuring_entity,
           t.winner, t.actual_value_mkd, t.estimated_value_mkd, t.contract_duration
    FROM bid_jobs j JOIN users u ON u.user_id = j.user_id JOIN tenders t ON t.tender_id = j.tender_id
    WHERE j.status IN ('submitted','approved','won')
      AND COALESCE(u.company_name, '') <> ''
      AND LOWER(COALESCE(u.role, '')) <> 'admin'
      AND u.email NOT ILIKE '%@nabavkidata.com'
      AND NOT EXISTS (SELECT 1 FROM client_wins w WHERE w.user_id = j.user_id AND w.tender_id = j.tender_id)
"""

WINNERS_SQL = """
    SELECT company_name, bid_amount_mkd FROM tender_bidders
    WHERE tender_id = $1 AND is_winner IS TRUE
"""


def winner_names(bidder_rows, winner_text) -> list[tuple[str, object]]:
    names: list[tuple[str, object]] = [
        (r["company_name"], r["bid_amount_mkd"]) for r in bidder_rows if r["company_name"]
    ]
    names += [(n, None) for n in client_wins.split_winner_names(winner_text)]
    return names


async def run(dry_run: bool = False) -> dict:
    stats = {"candidates": 0, "matched": 0, "inserted": 0, "notified": 0}
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        candidates = await conn.fetch(CANDIDATES_SQL)
    stats["candidates"] = len(candidates)
    for c in candidates:
        async with pool.acquire() as conn:
            bidders = await conn.fetch(WINNERS_SQL, c["tender_id"])
        names = winner_names(bidders, c["winner"])
        best_name, score, amount = client_wins.best_match(names, c["company_name"])
        if best_name is None or score < client_wins.WIN_MATCH_THRESHOLD:
            continue
        stats["matched"] += 1
        row = client_wins.build_win_row(c, {"success_fee_pct": c["u_pct"]}, c, best_name,
                                        score, amount)
        logger.info("match: job=%s tender=%s client=%r winner=%r score=%.3f fee=%s",
                    c["id"], c["tender_id"], c["company_name"], best_name, score,
                    row["success_fee_mkd"])
        if dry_run:
            continue
        async with pool.acquire() as conn:
            win_id = await conn.fetchval(client_wins.INSERT_WIN_SQL,
                                         *client_wins.win_insert_args(row))
        if win_id is None:
            continue
        stats["inserted"] += 1
        # notify() dedupes on bid_job_events, so a win emails the admin once.
        if await bid_notifications.notify(str(c["id"]), "win_detected"):
            stats["notified"] += 1
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE client_wins SET admin_notified_at = NOW(), updated_at = NOW() "
                "WHERE id = $1", win_id)
    logger.info("detect_client_wins%s: %s", " (dry run)" if dry_run else "", stats)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="log matches, write nothing")
    args = ap.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()

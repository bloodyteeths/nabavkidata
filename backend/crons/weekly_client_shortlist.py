#!/usr/bin/env python3
"""
Tuesday weekly client shortlist builder (Phase 4, Oct 2026).

Builds one DRAFT shortlist per target (managed clients + warm prospects) with
up to 8 candidate open tenders (services/client_shortlist.py). It sends NO
email of any kind: the admin hand-picks 2-4 per client in /admin/shortlists
and presses Send there. The only notification is the `shortlist_curate` item
in the next 06:30 focus email. Re-running in the same week is a no-op
(ON CONFLICT (user_id, week_start) DO NOTHING).

    0 4 * * 2 cd /home/ubuntu/nabavkidata/backend && /usr/bin/python3 crons/weekly_client_shortlist.py >> /var/log/nabavkidata/weekly_client_shortlist.log 2>&1

Flags:
    --dry-run   print targets and their candidates, write nothing
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
from services import client_shortlist, ops_copy  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("weekly_client_shortlist")


def _g(row, k):
    try:
        return row[k]
    except (KeyError, IndexError, TypeError):
        return None


async def run(*, dry_run: bool = False, pool=None) -> dict:
    today = ops_copy.today_skopje()
    pool = pool or await get_asyncpg_pool()
    async with pool.acquire() as conn:
        if dry_run:
            targets = await client_shortlist.shortlist_targets(conn, today)
            print(f"week {ops_copy.week_start(today)}: {len(targets)} targets")
            for t in targets:
                uid, email = _g(t, "user_id"), _g(t, "email")
                cands = await client_shortlist.candidates_for(conn, uid, email, today)
                print(f"- {email} ({_g(t, 'company_name') or '-'}): {len(cands)} candidates")
                for c in cands:
                    print(f"    {_g(c, 'tender_id')}  {ops_copy.fmt_date(_g(c, 'closing_date')) if _g(c, 'closing_date') else '-'}"
                          f"  {(_g(c, 'title') or '')[:80]}  [{_g(c, 'reason') or ''}]")
            return {"status": "dry_run", "targets": len(targets)}
        counts = await client_shortlist.build_week(conn, today)
    logger.info("shortlists week %s: %s", ops_copy.week_start(today), counts)
    print(counts)
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description="Build weekly draft client shortlists (no email).")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    asyncio.run(run(dry_run=a.dry_run))


if __name__ == "__main__":
    main()

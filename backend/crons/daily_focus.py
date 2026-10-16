#!/usr/bin/env python3
"""
06:30 Europe/Skopje operator focus email (Phase 4, Oct 2026).

The ONE automatic email of the ops system, and it goes only to the admin
(ops_copy.ADMIN_EMAIL). It lists every open focus item (services/ops_focus.py)
with its draft and a signed one-click "Готово/испратено" link. Nothing is ever
sent to a lead or client from here.

Two UTC slots cover CEST/CET; the Skopje-hour guard keeps exactly one, and
ops_digest_log keeps it to one email per day:
    30 4,5 * * 1-5 cd /home/ubuntu/nabavkidata/backend && /usr/bin/python3 crons/daily_focus.py >> /var/log/nabavkidata/daily_focus.log 2>&1

Flags:
    --dry-run   print the email, send nothing, write nothing
    --force     send even if today's digest was already sent
    --now       skip the 06:xx Skopje-hour guard
"""
from __future__ import annotations

import argparse
import asyncio
import html
import logging
import os
import re
import sys
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from db_pool import get_asyncpg_pool  # noqa: E402
from services import lead_watch, ops_copy, ops_focus  # noqa: E402
from services.postmark import postmark_service  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("daily_focus")

SKOPJE = ZoneInfo("Europe/Skopje")
SEND_HOUR = 6

# Claim the day BEFORE sending: two overlapping runs (cron + manual --now) cannot
# both pass a check-then-send. The claim is released when there is nothing to send.
SQL_DIGEST_CLAIM = ("INSERT INTO ops_digest_log (digest_date, item_count, message_ok) "
                    "VALUES ($1, 0, false) ON CONFLICT (digest_date) DO NOTHING RETURNING digest_date")
SQL_DIGEST_UNCLAIM = "DELETE FROM ops_digest_log WHERE digest_date = $1 AND item_count = 0 AND NOT message_ok"
SQL_DIGEST_LOG = (
    "INSERT INTO ops_digest_log (digest_date, item_count, message_ok) VALUES ($1, $2, $3) "
    "ON CONFLICT (digest_date) DO UPDATE SET sent_at = NOW(), item_count = EXCLUDED.item_count, "
    "message_ok = EXCLUDED.message_ok"
)
GROUP_ORDER = ("clients", "sales", "money", "reminders")
GROUP_LABELS = {"clients": "Клиенти", "sales": "Продажба", "money": "Наплата",
                "reminders": "Потсетници"}

FOOTER = (
    "Рачни потсетници и одмор: уреди backend/data/focus_manual.json на серверот "
    "(листа од {\"date\":\"YYYY-MM-DD\",\"title\":\"...\",\"detail\":\"...\"} или "
    "{\"holiday_until\":\"YYYY-MM-DD\"}). Сè останато се пресметува од живите податоци; "
    "ставката исчезнува кога ќе се реши. Целиот фокус: " + ops_copy.SITE + "/admin/focus"
)


def skopje_hour(now: datetime | None = None) -> int:
    return (now or datetime.now(SKOPJE)).astimezone(SKOPJE).hour


def subject_for(n: int) -> str:
    return f"НабавкиДата фокус: {n} {'ставка' if n == 1 else 'ставки'} денес"


def mailto_link(draft: dict) -> str:
    """One tap from the phone: opens the mail app with To/Cc/Subject/Body filled."""
    return (f"mailto:{quote(draft.get('to') or '', safe='@')}"
            f"?cc={quote(ops_copy.ADMIN_EMAIL, safe='@')}"
            f"&subject={quote(draft.get('subject') or '', safe='')}"
            f"&body={quote(draft.get('body_text') or '', safe='')}")


def _deadline(it: dict) -> str:
    cd = (it.get("tender") or {}).get("closing_date")
    return f" (рок {ops_copy.fmt_date(cd)})" if cd else ""


def build_body(data: dict, now: datetime | None = None) -> str:
    """Phone-first: a grouped one-line index on the first screen, then per item
    the detail, links, one-tap mail link, the draft, and the signed done link."""
    items = data.get("items") or []
    out = [f"НабавкиДата фокус за {ops_copy.fmt_date(ops_copy.today_skopje())}"
           + (" (неработен ден)" if data.get("off_day") else ""), ""]
    num = {it["key"]: n for n, it in enumerate(items, 1)}
    for g in GROUP_ORDER:
        grp = [it for it in items if it.get("group") == g]
        if not grp:
            continue
        out.append(f"{GROUP_LABELS[g].upper()} ({len(grp)})")
        out += [f"{num[it['key']]}. {it.get('title') or ''}{_deadline(it)}" for it in grp]
        out.append("")
    out += ["=" * 30, ""]
    for it in items:
        out.append(f"{num[it['key']]}. {it.get('title') or ''}")
        if it.get("detail"):
            out.append(f"   {it['detail']}")
        for ln in it.get("links") or []:
            out.append(f"   {ln.get('label')}: {ln.get('href')}")
        out.append(f"   Во фокусот: {ops_copy.SITE}/admin/focus#{quote(it['key'], safe=':')}")
        d = it.get("draft")
        if d:
            out.append(f"   Испрати од пошта: {mailto_link(d)}")
            out += ["--- нацрт ---", f"До: {d.get('to')}", f"Тема: {d.get('subject')}", "",
                    d.get("body_text") or "", "--- крај ---"]
        out.append(f"   Готово/испратено: {ops_copy.ops_done_link(it['key'], now)}")
        out.append("")
    notes = data.get("notes") or []
    if notes:
        out.append("Белешки:")
        out += [f"- {x}" for x in notes]
        out.append("")
    out.append(FOOTER)
    return "\n".join(out)


_URL_RE = re.compile(r"(https?://[^\s<]+)")
_MAILTO_RE = re.compile(r"Испрати од пошта: (mailto:[^\s<]+)")


def to_html(body: str) -> str:
    esc = html.escape(body)
    # mailto first (its body may contain encoded https links), shown as a short label.
    marks: list[str] = []

    def _mailto(m):
        marks.append(f'<a href="{m.group(1)}">Испрати од пошта</a>')
        return f"\x00{len(marks) - 1}\x00"
    esc = _MAILTO_RE.sub(_mailto, esc)
    linked = _URL_RE.sub(lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', esc)
    linked = re.sub("\x00(\\d+)\x00", lambda m: marks[int(m.group(1))], linked)
    return ("<pre style=\"font-family:Menlo,Consolas,monospace;font-size:13px;"
            f"white-space:pre-wrap;word-wrap:break-word\">{linked}</pre>")


async def run(*, dry_run: bool = False, force: bool = False, now_flag: bool = False,
              pool=None, now: datetime | None = None) -> dict:
    if not now_flag and skopje_hour(now) != SEND_HOUR:
        logger.info("not 06:xx in Skopje; exiting")
        return {"status": "wrong_hour"}
    today = ops_copy.today_skopje()
    # Weekdays only (Atilla, 16 Oct 2026): no sales follow-ups go out at weekends,
    # so there is no morning list either; Monday's list is built from live state.
    if not now_flag and today.weekday() >= 5:
        logger.info("weekend in Skopje; exiting")
        return {"status": "weekend"}
    pool = pool or await get_asyncpg_pool()
    async with pool.acquire() as conn:
        claimed = False
        if not dry_run:
            claimed = bool(await conn.fetchval(SQL_DIGEST_CLAIM, today))
            if not claimed and not force:
                logger.info("digest already sent (or being sent) for %s; exiting", today)
                return {"status": "already_sent"}
        try:
            if not dry_run:
                try:
                    await lead_watch.sync_watches(conn, today)
                except Exception as e:  # noqa: BLE001
                    logger.exception("sync_watches failed: %s", e)
            data = await ops_focus.build_focus(conn, today)
        except BaseException:
            if claimed:   # crashed before sending: release so a later --now run can retry
                await conn.execute(SQL_DIGEST_UNCLAIM, today)
            raise
        items = data.get("items") or []
        if not items:
            logger.info("no focus items for %s; nothing sent", today)
            if claimed:
                await conn.execute(SQL_DIGEST_UNCLAIM, today)
            return {"status": "empty"}
        n = len(items)
        subject = subject_for(n)
        body = build_body(data, now)
        if dry_run:
            print(subject)
            print(body)
            return {"status": "dry_run", "items": n}
        ok = await postmark_service.send_email(
            to=ops_copy.ADMIN_EMAIL, subject=subject, html_content=to_html(body),
            text_content=body, tag="daily_focus")
        await conn.execute(SQL_DIGEST_LOG, today, n, bool(ok))
    logger.info("focus email %s: %d items", "sent" if ok else "FAILED", n)
    return {"status": "sent" if ok else "send_failed", "items": n}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--now", action="store_true")
    a = ap.parse_args()
    asyncio.run(run(dry_run=a.dry_run, force=a.force, now_flag=a.now))


if __name__ == "__main__":
    main()

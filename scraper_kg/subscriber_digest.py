"""
Per-subscriber personalized KG tender digest.

Reads from kg.alert_subscriptions, sends each verified subscriber a daily
digest of tenders matching their keywords over the last 24 hours.

Cron: daily 06:00 UTC (~12:00 Bishkek) — after the daily_it_digest run.

Design:
- Bilingual matching via latin_to_russian (backend function)
- Skip subscribers with no new matches
- Every email includes one-click unsubscribe link
- Idempotent per day — check last_digest_sent_at
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request as U
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg

POSTMARK_TOKEN = os.getenv("POSTMARK_API_TOKEN", "97e9c355-08fc-4ef0-85b7-c3243b1bd330")
POSTMARK_URL = "https://api.postmarkapp.com/email"
FROM_ADDR = "Zakupki.KG <hello@facturino.mk>"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://nabavkidata.com")

# Minimum tender value to include (kill tiny administrative buys)
MIN_AMOUNT_KGS = 50000


def latin_to_russian_transliterate(text: str) -> str:
    """
    Simple Latin → Russian Cyrillic transliteration.
    Mirrors backend/api/corruption.py::latin_to_russian for the scraper env.
    """
    if not text:
        return ""

    # Only transliterate if input is pure latin/ascii
    if any("Ѐ" <= c <= "ӿ" for c in text):
        return text

    lower = text.lower()

    # Multi-char digraphs first (order matters)
    for src, dst in [
        ("shch", "щ"), ("zh", "ж"), ("ch", "ч"), ("sh", "ш"), ("kh", "х"),
        ("yu", "ю"), ("ya", "я"), ("ye", "е"), ("yo", "ё"), ("ts", "ц"),
        ("ng", "ң"),  # Kyrgyz-specific
    ]:
        lower = lower.replace(src, dst)

    single = {
        "a": "а", "b": "б", "v": "в", "g": "г", "d": "д", "e": "е", "z": "з",
        "i": "и", "y": "й", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
        "p": "п", "r": "р", "s": "с", "t": "т", "u": "у", "f": "ф", "h": "х",
        "c": "ц", "q": "к", "w": "в", "x": "х",
    }
    return "".join(single.get(ch, ch) for ch in lower)


async def get_active_subscribers(conn) -> list[dict]:
    """Fetch verified, non-unsubscribed subscribers."""
    rows = await conn.fetch(
        """
        SELECT id, email, keywords, unsubscribe_token, last_digest_sent_at
        FROM kg.alert_subscriptions
        WHERE is_verified = TRUE
          AND unsubscribed_at IS NULL
        """
    )
    return [dict(r) for r in rows]


async def query_matches_for_subscriber(
    conn, keywords: list[str], since_hours: int = 24
) -> list[dict]:
    """
    Return tenders matching ANY of the subscriber's keywords, first-seen in last N hours.
    Bilingual: transliterates Latin input to Russian and matches both.
    """
    if not keywords:
        return []

    # Build OR condition — each keyword matches title in original + transliterated form
    conditions: list[str] = []
    params: list = []
    param_num = 0

    for kw in keywords:
        # Original form
        param_num += 1
        conditions.append(f"title ILIKE '%' || ${param_num} || '%'")
        params.append(kw)
        # Transliterated form (only if input was Latin)
        cyr = latin_to_russian_transliterate(kw)
        if cyr != kw.lower():
            param_num += 1
            conditions.append(f"title ILIKE '%' || ${param_num} || '%'")
            params.append(cyr)

    where_kw = " OR ".join(conditions)
    param_num += 1
    amount_param = param_num
    params.append(MIN_AMOUNT_KGS)

    sql = f"""
        SELECT tender_id, tender_number, title, buyer_name, amount_kgs,
               date_published, date_contest, procurement_method, source
        FROM kg.tenders
        WHERE first_seen_at > NOW() - INTERVAL '{since_hours} hours'
          AND (date_contest > NOW() OR date_contest IS NULL)
          AND amount_kgs >= ${amount_param}
          AND ({where_kw})
        ORDER BY amount_kgs DESC NULLS LAST, date_contest ASC NULLS LAST
        LIMIT 50
    """
    rows = await conn.fetch(sql, *params)
    return [dict(r) for r in rows]


def build_digest_email(
    subscriber: dict, tenders: list[dict], now: datetime
) -> tuple[str, str, str]:
    """Return (subject, html, text) for the digest email."""
    date_str = now.strftime("%d.%m.%Y")
    kw_display = ", ".join(subscriber["keywords"][:3]) + (
        "..." if len(subscriber["keywords"]) > 3 else ""
    )
    subject = f"Zakupki.KG — {len(tenders)} новых тендеров по вашим ключевым словам · {date_str}"
    unsub_url = f"{PUBLIC_BASE_URL}/kg/alerts/unsubscribe?token={subscriber['unsubscribe_token']}"

    # Text version
    lines = [
        f"Zakupki.KG — ежедневный дайджест · {date_str}",
        f"Ключевые слова: {kw_display}",
        f"Новых тендеров за 24 часа: {len(tenders)}",
        "",
    ]
    for t in tenders:
        amt = (
            f"{int(t['amount_kgs']):,} сом".replace(",", " ")
            if t.get("amount_kgs")
            else "не указана"
        )
        deadline = str(t.get("date_contest", ""))[:10]
        detail_url = f"{PUBLIC_BASE_URL}/kg/tenders/{t['tender_id']}"
        lines.append(f"— {t.get('title', '')[:100]}")
        lines.append(f"   Заказчик: {t.get('buyer_name', '')[:80]}")
        lines.append(f"   Сумма: {amt} | Крайний срок: {deadline}")
        lines.append(f"   Подробнее: {detail_url}")
        lines.append("")
    lines.append(f"---")
    lines.append(f"Отписаться: {unsub_url}")
    text = "\n".join(lines)

    # HTML version
    rows = []
    for t in tenders:
        amt = (
            f"{int(t['amount_kgs']):,} сом".replace(",", " ")
            if t.get("amount_kgs")
            else "не указана"
        )
        deadline = str(t.get("date_contest", ""))[:10]
        detail_url = f"{PUBLIC_BASE_URL}/kg/tenders/{t['tender_id']}"
        rows.append(
            f"""
<tr>
  <td style='padding:10px;border-bottom:1px solid #e5e7eb;vertical-align:top'>
    <a href='{detail_url}' style='color:#1e40af;text-decoration:none;font-weight:600'>{t.get('title', '')[:150]}</a><br>
    <span style='color:#6b7280;font-size:13px'>Заказчик: {t.get('buyer_name', '')[:100]}</span><br>
    <span style='color:#9ca3af;font-size:12px'>Метод: {t.get('procurement_method', '')} · Номер: {t.get('tender_number')}</span>
  </td>
  <td style='padding:10px;border-bottom:1px solid #e5e7eb;text-align:right;vertical-align:top;white-space:nowrap'>
    <strong style='color:#111827'>{amt}</strong><br>
    <span style='color:#6b7280;font-size:12px'>до {deadline}</span>
  </td>
</tr>
"""
        )

    html = f"""<html><body style='font-family:-apple-system,BlinkMacSystemFont,Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px;color:#111827;background:#f9fafb'>
<div style='background:white;padding:24px;border-radius:8px'>
  <h1 style='margin:0 0 4px;font-size:22px'>🇰🇬 Zakupki.KG — {date_str}</h1>
  <p style='margin:0 0 16px;color:#6b7280;font-size:14px'>
    Новых тендеров по вашим ключевым словам за 24 часа: <strong>{len(tenders)}</strong><br>
    Ключевые слова: <em>{kw_display}</em>
  </p>
  <table style='width:100%;border-collapse:collapse;margin-top:12px'>
    <thead>
      <tr style='background:#f3f4f6'>
        <th style='padding:10px;text-align:left;font-size:12px;text-transform:uppercase;color:#6b7280'>Тендер</th>
        <th style='padding:10px;text-align:right;font-size:12px;text-transform:uppercase;color:#6b7280'>Сумма / срок</th>
      </tr>
    </thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p style='margin-top:20px'>
    <a href='{PUBLIC_BASE_URL}/kg/tenders' style='background:#2563eb;color:white;padding:10px 18px;text-decoration:none;border-radius:6px;font-weight:500'>
      Смотреть все тендеры →
    </a>
  </p>
</div>
<div style='padding:16px 4px;color:#6b7280;font-size:12px;text-align:center'>
  <p>Вы получили это письмо потому что подписались на Zakupki.KG.<br>
  Не хотите получать больше уведомлений? <a href='{unsub_url}' style='color:#6b7280'>Отписаться в один клик</a></p>
</div>
</body></html>"""

    return subject, html, text


def send_email_postmark(
    to: str, subject: str, html: str, text: str, tag: str = "kg-daily-digest"
) -> Optional[str]:
    """Send via Postmark, return MessageID or None on failure."""
    payload = {
        "From": FROM_ADDR,
        "To": to,
        "Subject": subject,
        "HtmlBody": html,
        "TextBody": text,
        "MessageStream": "outbound",
        "Tag": tag,
    }
    req = U.Request(
        POSTMARK_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Postmark-Server-Token": POSTMARK_TOKEN,
        },
        method="POST",
    )
    try:
        with U.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode())
            return resp.get("MessageID")
    except Exception as e:
        print(f"  ✗ Send error: {e}", file=sys.stderr)
        return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-hours", type=int, default=24)
    ap.add_argument("--dry-run", action="store_true", help="Don't send, don't mark sent")
    ap.add_argument("--force", action="store_true", help="Send even if already sent today")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    conn = await asyncpg.connect("postgresql:///nabavkidata")

    subscribers = await get_active_subscribers(conn)
    print(f"Active verified subscribers: {len(subscribers)}", file=sys.stderr)

    stats = {"sent": 0, "skipped_no_matches": 0, "skipped_already_today": 0, "failed": 0}

    for sub in subscribers:
        # Skip if already sent today (unless --force)
        if not args.force and sub.get("last_digest_sent_at"):
            last = sub["last_digest_sent_at"]
            if last > now - timedelta(hours=20):
                stats["skipped_already_today"] += 1
                print(f"  · {sub['email']}: already sent today, skip", file=sys.stderr)
                continue

        matches = await query_matches_for_subscriber(
            conn, sub["keywords"], since_hours=args.since_hours
        )
        if not matches:
            stats["skipped_no_matches"] += 1
            print(f"  · {sub['email']}: 0 matches, skip", file=sys.stderr)
            continue

        subject, html, text = build_digest_email(sub, matches, now)
        print(
            f"  → {sub['email']}: {len(matches)} matches, subject: {subject[:60]}",
            file=sys.stderr,
        )

        if args.dry_run:
            stats["sent"] += 1
            continue

        msg_id = send_email_postmark(sub["email"], subject, html, text)
        if msg_id:
            stats["sent"] += 1
            await conn.execute(
                "UPDATE kg.alert_subscriptions SET last_digest_sent_at = NOW() WHERE id = $1",
                sub["id"],
            )
            print(f"    ✓ sent · MessageID {msg_id}", file=sys.stderr)
        else:
            stats["failed"] += 1

    await conn.close()
    print(f"\nDONE — {json.dumps(stats)}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())

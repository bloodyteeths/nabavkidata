#!/usr/bin/env python3
"""
Service-launch announcement to existing NabavkiData users (Oct 2026).

NabavkiData became a done-for-you bid-writing service; alerts, AI analyses,
price history and competitor analysis are now client perks. This tells
existing users what changed and invites them to order a bid.

Rules: no prices in the email (they live on /pricing), no "free" offers,
never imply the platform is closing, Macedonian, no emojis.

Segments (exclusions first): internal/disposable, suppressed/unsubscribed,
unverified are never sent.
  A  had active tender alerts      -> names their alert keywords
  B  active in the last 60 days
  C  dormant

Usage (on the server, from backend/):
  python3 scripts/send_service_launch.py                     # dry run: counts + samples
  python3 scripts/send_service_launch.py --test-to you@x.com # one email per segment to you
  python3 scripts/send_service_launch.py --send [--segment A] [--limit N]

Each real send is logged in campaign_sends (source=service_launch_2026_10),
so re-running never emails anyone twice.
"""
import argparse
import asyncio
import html
import json
import os
import sys

import asyncpg
import httpx
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from services.postmark import build_unsubscribe_url  # noqa: E402

SOURCE = "service_launch_2026_10"
SITE = "https://nabavkidata.com"
POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN", "")
FROM = "Атилла Танрикулу — НабавкиДата <hello@nabavkidata.com>"

SEGMENT_SQL = r"""
WITH base AS (
  SELECT u.user_id, u.email, u.full_name, u.email_verified, u.role,
    (SELECT MAX(last_activity) FROM user_sessions s WHERE s.user_id = u.user_id) AS last_seen,
    (SELECT COUNT(*) FROM search_history h
      WHERE h.user_id = u.user_id AND h.created_at > NOW() - INTERVAL '60 days') AS srch60,
    (SELECT COALESCE(jsonb_agg(DISTINCT kw), '[]'::jsonb)
       FROM tender_alerts a, jsonb_array_elements_text(COALESCE(a.criteria->'keywords', '[]'::jsonb)) kw
      WHERE a.user_id = u.user_id AND a.is_active) AS keywords,
    (SELECT COUNT(*) FROM tender_alerts a WHERE a.user_id = u.user_id AND a.is_active) AS alerts,
    (LOWER(u.email) IN (SELECT LOWER(email) FROM suppression_list)
     OR LOWER(u.email) IN (SELECT LOWER(email) FROM campaign_unsubscribes)) AS suppressed,
    EXISTS (SELECT 1 FROM campaign_sends c WHERE LOWER(c.email) = LOWER(u.email) AND c.source = $1 AND c.status = 'sent') AS already_sent
  FROM users u
  WHERE u.account_type IN ('free', 'prospect')
)
SELECT *,
  CASE WHEN role = 'admin' OR email ILIKE '%nabavkidata.com' OR email ILIKE '%golfercase%'
            OR email ~* '(grr\.la|jobscai|omanarts|mailinator|tempmail|guerrilla)' THEN 'X'
       WHEN suppressed OR NOT COALESCE(email_verified, FALSE) THEN 'X'
       WHEN alerts > 0 THEN 'A'
       WHEN last_seen > NOW() - INTERVAL '60 days' OR srch60 > 0 THEN 'B'
       ELSE 'C' END AS segment
FROM base
ORDER BY email
"""


def _first_name(full_name):
    if not full_name:
        return None
    first = full_name.strip().split()[0]
    # Company-ish or junk names get the plural greeting.
    if len(first) < 2 or any(ch.isdigit() for ch in first) or first.isupper() and len(first) > 3:
        return None
    return first


def _keywords_line(keywords):
    kws = [k.strip() for k in (keywords or []) if k and len(k.strip()) > 2][:3]
    if not kws:
        return "вашите клучни зборови"
    return ", ".join(f"„{html.escape(k)}“" for k in kws)


def render(segment, row):
    # Stored names are often company names ("Alat Box", "106 Radio"), so no first-name greeting.
    greeting = "Почитувани,"
    order_url = f"{SITE}/usluga?src=launch_{segment.lower()}"
    pricing_url = f"{SITE}/pricing?src=launch_{segment.lower()}"

    intro = ("Го надградивме НабавкиДата. Повеќе не сме само алатка за пребарување: сега сме тим "
             "што ја подготвува вашата тендерска понуда од почеток до крај. Ја анализираме "
             "тендерската документација и ги подготвуваме условите за способност, техничката и "
             "финансиската понуда и сите изјави. Вие ја прегледувате, ја потпишувате и ја поднесувате.")
    perks = ("Алертите, AI анализите, историјата на победнички цени и анализата на конкуренцијата "
             "сега се дел од услугата за нашите клиенти.")
    if segment == "A":
        keywords = row["keywords"]
        if isinstance(keywords, str):
            keywords = json.loads(keywords)
        perks += (f" Вашите алерти за {_keywords_line(keywords)} се зачувани и повторно се "
                  f"активираат штом ја нарачате првата понуда.")
        subject = "Вашите алерти за јавни набавки — надградба на НабавкиДата"
    else:
        subject = "НабавкиДата е надграден: сега ја пишуваме понудата за вас"

    reply_line = ("" if segment == "C" else
                  "<p>Ако веќе имате тендер на ум, одговорете на оваа порака со неговиот број "
                  "и ќе ви кажеме што е потребно.</p>")
    unsub = build_unsubscribe_url(row["email"])
    html_body = f"""<!doctype html><html><body style="margin:0;padding:24px;background:#f8fafc">
<div style="max-width:580px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:28px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;color:#1e293b">
<p>{greeting}</p>
<p>{intro}</p>
<p>{perks}</p>
<p style="margin:26px 0">
  <a href="{order_url}" style="background:#2563eb;color:#ffffff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;display:inline-block">Нарачајте понуда</a>
  &nbsp;&nbsp;<a href="{pricing_url}" style="color:#2563eb">Цени и услови</a>
</p>
{reply_line}
<p>Поздрав,<br>Атилла Танрикулу<br>НабавкиДата · Фактурино ДООЕЛ</p>
<hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
<p style="font-size:12px;color:#64748b">Ја добивате оваа порака бидејќи имате профил на nabavkidata.com.
<a href="{unsub}" style="color:#64748b">Одјава од известувања</a></p>
</div></body></html>"""
    text_body = "\n\n".join(filter(None, [
        html.unescape(greeting), intro, html.unescape(perks),
        f"Нарачајте понуда: {order_url}", f"Цени и услови: {pricing_url}",
        None if segment == "C" else "Ако веќе имате тендер на ум, одговорете на оваа порака со неговиот број.",
        "Поздрав,\nАтилла Танрикулу\nНабавкиДата · Фактурино ДООЕЛ",
        f"Одјава: {unsub}",
    ]))
    return subject, html_body, text_body, unsub


async def send(client, to, subject, html_body, text_body, unsub, segment):
    r = await client.post(
        "https://api.postmarkapp.com/email",
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "X-Postmark-Server-Token": POSTMARK_API_TOKEN},
        json={
            "From": FROM, "To": to, "ReplyTo": "hello@nabavkidata.com",
            "Subject": subject, "HtmlBody": html_body, "TextBody": text_body,
            "MessageStream": "broadcast", "TrackOpens": True, "TrackLinks": "HtmlOnly",
            "Tag": f"service-launch-{segment.lower()}",
            "Headers": [
                {"Name": "List-Unsubscribe", "Value": f"<{unsub}>"},
                {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"},
            ],
        },
        timeout=30.0,
    )
    if r.status_code == 200:
        return r.json().get("MessageID"), None
    return None, r.text[:300]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="really send to users")
    ap.add_argument("--test-to", help="send one sample per segment to this address only")
    ap.add_argument("--segment", choices=["A", "B", "C"])
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    dsn = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(SEGMENT_SQL, SOURCE)
        counts = {}
        for r in rows:
            counts[r["segment"]] = counts.get(r["segment"], 0) + 1
        todo = [r for r in rows if r["segment"] in ("A", "B", "C") and not r["already_sent"]
                and (not args.segment or r["segment"] == args.segment)]
        print(f"segments: {counts}  | to send now: {len(todo)}")

        if not args.send and not args.test_to:
            for seg in ("A", "B", "C"):
                sample = next((r for r in todo if r["segment"] == seg), None)
                if sample:
                    subject, _, text, _ = render(seg, sample)
                    print(f"\n--- {seg} sample ({sample['email']}) ---\nSubject: {subject}\n{text[:900]}")
            print("\nDry run only. Use --test-to or --send.")
            return

        if not POSTMARK_API_TOKEN:
            sys.exit("POSTMARK_API_TOKEN missing")

        async with httpx.AsyncClient() as client:
            if args.test_to:
                for seg in ("A", "B", "C"):
                    sample = next((r for r in rows if r["segment"] == seg), None)
                    if not sample:
                        continue
                    subject, html_body, text_body, unsub = render(seg, sample)
                    mid, err = await send(client, args.test_to, f"[ТЕСТ {seg}] {subject}",
                                          html_body, text_body, unsub, seg)
                    print(f"test {seg} (as {sample['email']}): {'sent ' + mid if mid else 'FAILED ' + err}")
                return

            sent = failed = 0
            for r in todo[: args.limit or None]:
                subject, html_body, text_body, unsub = render(r["segment"], r)
                mid, err = await send(client, r["email"], subject, html_body, text_body, unsub, r["segment"])
                await conn.execute(
                    "INSERT INTO campaign_sends (email, campaign_id, source, postmark_message_id, status, sent_at) "
                    "VALUES ($1, $2, $3, $4, $5, NOW())",
                    r["email"], f"service-launch-{r['segment'].lower()}", SOURCE, mid,
                    "sent" if mid else f"failed: {err}",
                )
                if mid:
                    sent += 1
                else:
                    failed += 1
                    print(f"FAILED {r['email']}: {err}")
                await asyncio.sleep(0.2)
            print(f"done: sent={sent} failed={failed}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

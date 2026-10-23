#!/usr/bin/env python3
"""
Consulting Follow-Up Campaign — Mar 24, 2026
Pivots messaging from SaaS platform to consulting service:
"We do the research FOR you. You just sign and bid."

4 groups:
  A: Consulting openers (warm follow-up, free dossier offer)
  B: Consulting not-opened (re-send with new subject)
  C: Personalized openers (THE PIVOT — SaaS→consulting)
  D: Personalized not-opened (short data hook)
"""

import os
import sys
import json
import hashlib
import logging
import asyncio
import argparse
import httpx
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN")
if not POSTMARK_API_TOKEN:
    raise SystemExit(
        "POSTMARK_API_TOKEN is not set. Export it or put it in .env.production.\n"
        "There is deliberately no default: the token that used to be hardcoded here was "
        "revoked and every caller relying on it failed with a silent HTTP 401."
    )
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://nabavkidata.com")
UNSUBSCRIBE_SECRET = os.getenv("UNSUBSCRIBE_SECRET", "nabavki-unsub-secret-2025")
FROM_EMAIL = "Тамара од НабавкиДата <hello@nabavkidata.com>"
DELAY_BETWEEN = 5.0

# ─────────────────────────────────────────────────────────────
# RECIPIENT DATA
# ─────────────────────────────────────────────────────────────

GROUP_A = [
    # Consulting openers — opened our "exposed" analysis but didn't reply
    {"email": "emil.stankov@expecta.mk", "company": "Експекта Медикал", "keyword": "медицинска опрема", "competitor": "АЛКАЛОИД КОНС"},
    {"email": "vardargradba@mt.net.mk", "company": "Вардарградба", "keyword": "градежништво", "competitor": "ГРАНИТ"},
    {"email": "Vladimir.Tosevski@ospol.mk", "company": "Осигурителна Полиса", "keyword": "осигурување", "competitor": "ВИНЕР"},
]

GROUP_B = [
    # Consulting not-opened — delivered but 0 opens, re-send with new subject
    {"email": "ljupka@eurofarm.com.mk", "company": "Еуро-Фарм", "keyword": "фармацевтски", "competitor": "АЛКАЛОИД"},
    {"email": "r.guberova@euroins.com.mk", "company": "Евроинс", "keyword": "осигурување", "competitor": "ПОЛИСА"},
    {"email": "finance@intecsystem.net", "company": "Интек Систем", "keyword": "информатичк", "competitor": "СЕАВУС"},
    {"email": "info@gim.com.mk", "company": "ГИМ", "keyword": "градежништво", "competitor": "ГРАНИТ"},
    {"email": "info@gradbapromet.com", "company": "Градба Промет", "keyword": "градежништво", "competitor": "БАУЕР БГ"},
]

GROUP_C = [
    # Personalized openers — opened SaaS pitch, now pivot to consulting
    {"email": "elta@t-home.mk", "company": "Елта Инженеринг", "keyword": "инженеринг"},
    {"email": "goran_semering@yahoo.com", "company": "Семеринг МГ", "keyword": "хидраулика"},
    {"email": "shale.bastion@gmail.com", "company": "Бастион Секјурити", "keyword": "обезбедување"},
    {"email": "dancececova@yahoo.com", "company": "Данце Цецова", "keyword": "услуги"},
    {"email": "Luxvipdrive@gmail.com", "company": "VIP LVD", "keyword": "превоз"},
    {"email": "jomifood@yahoo.com", "company": "Јоми Фуд", "keyword": "прехранбен"},
    {"email": "sanistefanovic@yahoo.com", "company": "Сани Стефановиќ", "keyword": "услуги"},
    {"email": "melaoptics@gmail.com", "company": "Оптика Мела", "keyword": "оптика"},
    {"email": "zoran.vasilevski@multikop.com", "company": "Мултикоп Консалтинг", "keyword": "консалтинг"},
    {"email": "hidroarts@gmail.com", "company": "Хидро-Арт", "keyword": "хидроизолација"},
    {"email": "namaelektronik@gmail.com", "company": "На Ма Електроник", "keyword": "електроника"},
    {"email": "info@zurmarket.mk", "company": "Жур Маркет", "keyword": "прехранбен"},
    {"email": "repro@bomat.com.mk", "company": "Бомат Графикс", "keyword": "печатење"},
    {"email": "slavko_mirceski@yahoo.com", "company": "Канонада", "keyword": "возила"},
    {"email": "gel.teaching@gmail.com", "company": "ГЕЛ Тичинг", "keyword": "образование"},
    {"email": "info@mobeskvalitet.mk", "company": "Мобес Квалитет", "keyword": "квалитет"},
    {"email": "oscarkp@t.mk", "company": "Irish Pub St. Patrick", "keyword": "кетеринг"},
    {"email": "tehnogen@tehnogenex.com.mk", "company": "Техно Генекс", "keyword": "бојлери"},
    {"email": "info@uniatlas.mk", "company": "Уни-Атлас", "keyword": "компресори"},
    {"email": "tocev_b@yahoo.com", "company": "Точев", "keyword": "метални делови"},
    {"email": "bose1@t.mk", "company": "Мега Трејд", "keyword": "бела техника"},
    {"email": "info@aktovis.com", "company": "Актовис", "keyword": "услуги"},
    {"email": "info@bezbednost.mk", "company": "Корпоративна Безбедност", "keyword": "безбедност"},
]

GROUP_D = [
    # Personalized not-opened — short data hook with new subject
    {"email": "aturundze@yahoo.com", "company": "АТА Турунџе", "keyword": "услуги"},
    {"email": "inkom1@t.mk", "company": "ИНКОМ", "keyword": "услуги"},
    {"email": "uniga@uniga.com.mk", "company": "УНИГА", "keyword": "услуги"},
    {"email": "kegi.kolev@gmail.com", "company": "К&К Македонија", "keyword": "обувки"},
    {"email": "zarina-komerc@live.com", "company": "Жарина Комерц", "keyword": "челични јажиња"},
    {"email": "bobi@tobi.com.mk", "company": "ТОБИ", "keyword": "хидраулика"},
    {"email": "vladodent@yahoo.com", "company": "Владодент", "keyword": "стоматолош"},
    {"email": "nadzakov.n@t.mk", "company": "Наџаков", "keyword": "правни услуги"},
    {"email": "flores@flores.com.mk", "company": "Флорес", "keyword": "билки"},
    {"email": "kinetoartskopje@gmail.com", "company": "КинетоАрт", "keyword": "физиотерапи"},
    {"email": "mladenovatanja@yahoo.com", "company": "Тани Текс Мода", "keyword": "униформи"},
    {"email": "eurotermgr@gmail.com", "company": "Еуро Терм ГР", "keyword": "греење"},
    {"email": "info@cetusled.mk", "company": "Цетус Лед", "keyword": "LED"},
    {"email": "m.simovska@adriamed.com.mk", "company": "Адриамед", "keyword": "медицинска опрема"},
]

ALL_GROUPS = {"A": GROUP_A, "B": GROUP_B, "C": GROUP_C, "D": GROUP_D}


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def short_name(full):
    """Extract brand name from long legal company name."""
    import re
    if not full:
        return "N/A"
    # Remove common legal prefixes
    name = re.sub(
        r"(Друштво за|Трговско друштво|Приватна|производство|трговија|услуги|промет|градежништво|увоз|извоз|и\s|,)+",
        " ", full, flags=re.IGNORECASE
    )
    name = re.sub(r"\b(ДООЕЛ|ДОО|АД)\b", "", name)
    name = re.sub(r"\b(Скопје|Битола|Тетово|Прилеп|Штип|Охрид|Куманово|Кавадарци)\b", "", name)
    name = " ".join(name.split()).strip(" ,-.")
    # If still too long, take first 2 meaningful words
    parts = [p for p in name.split() if len(p) >= 3]
    return " ".join(parts[:3]) if parts else full[:30]


def unsubscribe_url(email):
    token = hashlib.sha256(f"{email}:{UNSUBSCRIBE_SECRET}".encode()).hexdigest()[:32]
    return f"{FRONTEND_URL}/unsubscribe?e={email}&t={token}"


def format_mkd(val):
    if not val:
        return "N/A"
    if val >= 1_000_000_000:
        return f"{val/1_000_000_000:.1f} милијарди МКД"
    if val >= 1_000_000:
        return f"{val/1_000_000:.0f} милиони МКД"
    if val >= 1_000:
        return f"{val/1_000:.0f} илјади МКД"
    return f"{val:.0f} МКД"


async def get_market_data(conn, keyword):
    """Get market stats for an industry keyword."""
    row = await conn.fetchrow("""
        SELECT COUNT(*) as cnt, COALESCE(SUM(estimated_value_mkd), 0) as total
        FROM tenders WHERE title ILIKE $1
    """, f"%{keyword}%")

    active = await conn.fetchval("""
        SELECT COUNT(*) FROM tenders
        WHERE title ILIKE $1 AND status IN ('open', 'published')
    """, f"%{keyword}%")

    competitors = await conn.fetch("""
        SELECT winner, COUNT(*) as cnt
        FROM tenders
        WHERE title ILIKE $1 AND winner IS NOT NULL AND winner <> ''
        GROUP BY winner ORDER BY cnt DESC LIMIT 5
    """, f"%{keyword}%")

    active_tenders = await conn.fetch("""
        SELECT tender_id, title, estimated_value_mkd
        FROM tenders
        WHERE title ILIKE $1 AND status IN ('open', 'published')
        ORDER BY publication_date DESC LIMIT 3
    """, f"%{keyword}%")

    return {
        "total_tenders": row["cnt"] if row else 0,
        "total_value": row["total"] if row else 0,
        "active_count": active or 0,
        "competitors": [{"name": short_name(c["winner"]), "count": c["cnt"]} for c in competitors],
        "active_tenders": [
            {"id": t["tender_id"], "title": t["title"][:80], "value": t["estimated_value_mkd"]}
            for t in active_tenders
        ],
    }


# ─────────────────────────────────────────────────────────────
# EMAIL TEMPLATES
# ─────────────────────────────────────────────────────────────

def wrap_html(body_content, email):
    """Wrap body content in standard HTML email wrapper."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#333; background:#fff;">
<div style="max-width:600px; margin:0 auto;">
{body_content}
<hr style="border:none; border-top:1px solid #eee; margin:30px 0;">
<p style="font-size:12px; color:#999;">
Тамара од НабавкиДата<br>
hello@nabavkidata.com | 070 253 467<br><br>
<a href="{unsubscribe_url(email)}" style="color:#999;">Одјавете се</a>
</p>
</div></body></html>"""


def template_group_a(recipient, market):
    """Group A: Consulting openers — warm follow-up, free dossier offer."""
    company = recipient["company"]
    competitor = recipient.get("competitor", "вашите конкуренти")
    active = market["active_count"]
    subject = f"{company} -- бесплатен досие за 1 тендер"

    body = f"""<p style="margin:15px 0; color:#000;">Здраво,</p>

<p style="margin:15px 0; color:#000;">Видовме дека го отворивте нашиот извештај за {company}. Значи ве интересира -- и тоа е доволно за нас.</p>

<p style="margin:15px 0; color:#000;">Нека зборуваат резултатите: <strong>изберете еден тендер</strong> и ние ќе ви подготвиме комплетен досие -- бесплатно, без обврска.</p>

<p style="margin:15px 0; color:#000; background:#f0f9ff; padding:15px; border-radius:6px; border-left:4px solid #2563eb;">
<strong>Што добивате во досието:</strong><br>
- Цени на конкурентите од претходни тендери<br>
- Споредба на технички спецификации<br>
- Листа на потребни документи<br>
- Рокови и клучни датуми<br>
- Препорака дали да учествувате или не
</p>

<p style="margin:15px 0; color:#000;">Моментално има <strong>{active} отворени тендери</strong> во вашата област. {competitor} веќе аплицира на повеќето.</p>

<p style="margin:15px 0; color:#000;">Одговорете на овој мејл со линк до тендерот или само кажете ни ја областа -- ние ќе најдеме.</p>

<p style="margin:15px 0; color:#000;">Поздрав,<br>Тамара</p>"""

    return subject, wrap_html(body, recipient["email"])


def template_group_b(recipient, market):
    """Group B: Consulting not-opened — re-send with FOMO subject."""
    company = recipient["company"]
    competitor = recipient.get("competitor", "Вашиот конкурент")
    active = market["active_count"]
    total_value = format_mkd(market["total_value"])

    subject = f"{competitor} веќе аплицира -- {company}, а вие?"

    body = f"""<p style="margin:15px 0; color:#000;">Здраво,</p>

<p style="margin:15px 0; color:#000;">Ви пишав минатата недела но можеби го пропуштивте мејлот.</p>

<p style="margin:15px 0; color:#000;">Кратко: анализиравме <strong>{market['total_tenders']} тендери</strong> во вашата област (вкупно {total_value}). {competitor} доминира. Видовме каде {company} може да биде поконкурентна.</p>

<p style="margin:15px 0; color:#000;">Не ви нудиме платформа. <strong>Ние го правиме целото истражување за вас</strong> -- цени, конкуренти, документи, стратегија. Вие само потпишете и аплицирајте.</p>"""

    if active > 0:
        body += f"""
<p style="margin:15px 0; color:#000; background:#fef3c7; padding:15px; border-radius:6px;">
Моментално: <strong>{active} отворени тендери</strong> во вашиот сектор. Секој ден без анализа е пропуштена шанса.
</p>"""

    body += f"""
<p style="margin:15px 0; color:#000;">Одговорете со "да" и ќе ви испратиме бесплатен извештај за еден тендер по ваш избор.</p>

<p style="margin:15px 0; color:#000;">Поздрав,<br>Тамара<br>070 253 467</p>"""

    return subject, wrap_html(body, recipient["email"])


def template_group_c(recipient, market):
    """Group C: Personalized openers — THE PIVOT from SaaS to consulting."""
    company = recipient["company"]
    active = market["active_count"]
    total_value = format_mkd(market["total_value"])
    competitors = market.get("competitors", [])
    active_tenders = market.get("active_tenders", [])

    subject = f"{company} -- ние истражуваме, вие потпишете"

    comp_names = ", ".join(c["name"][:25] for c in competitors[:3]) if competitors else "вашите конкуренти"

    body = f"""<p style="margin:15px 0; color:#000;">Здраво,</p>

<p style="margin:15px 0; color:#000;">Ви пишав за нашата платформа НабавкиДата. Но размислив -- <strong>не ви треба платформа. Ви треба некој кој ќе го направи истражувањето за вас.</strong></p>

<p style="margin:15px 0; color:#000;">Тоа е токму нашата нова услуга.</p>

<p style="margin:15px 0; color:#000; background:#f0f9ff; padding:15px; border-radius:6px; border-left:4px solid #2563eb;">
<strong>Што правиме ние:</strong><br>
- Ги наоѓаме тендерите каде имате најголема шанса<br>
- Анализираме цени и понуди на конкурентите ({comp_names})<br>
- Подготвуваме целосна документација<br>
- Ви кажуваме точна цена за победа<br><br>
<strong>Што правите вие:</strong> Прегледате, потпишете, аплицирате.
</p>"""

    if active > 0:
        body += f"""
<p style="margin:15px 0; color:#000;">Во вашата област моментално има <strong>{active} отворени тендери</strong> (вкупен пазар: {total_value}).</p>"""

    if active_tenders:
        body += '<p style="margin:15px 0; color:#000;"><strong>Пример:</strong></p><ul style="color:#000;">'
        for t in active_tenders[:2]:
            val = format_mkd(t["value"]) if t["value"] else "непознато"
            body += f'<li>{t["title"][:70]} ({val})</li>'
        body += '</ul>'

    body += f"""
<p style="margin:15px 0; color:#000;">Одговорете на овој мејл или јавете се на 070 253 467 -- ќе ви испратиме бесплатна анализа за еден тендер по ваш избор.</p>

<p style="margin:15px 0; color:#000;">Поздрав,<br>Тамара</p>"""

    return subject, wrap_html(body, recipient["email"])


def template_group_d(recipient, market):
    """Group D: Personalized not-opened — ultra short data hook."""
    company = recipient["company"]
    active = market["active_count"]
    competitors = market.get("competitors", [])

    if active > 0:
        subject = f"{active} тендери за {company} оваа недела"
    else:
        subject = f"{company} -- вашите конкуренти освоија нови тендери"

    comp_names = ", ".join(c["name"][:20] for c in competitors[:2]) if competitors else "вашите конкуренти"

    body = f"""<p style="margin:15px 0; color:#000;">Здраво,</p>

<p style="margin:15px 0; color:#000;"><strong>{active} отворени тендери</strong> во вашиот сектор. {comp_names} веќе аплицираат.</p>

<p style="margin:15px 0; color:#000;">Одговорете "<strong>да</strong>" и ќе ви испратиме бесплатна анализа -- кој аплицира, по која цена, и дали имате шанса.</p>

<p style="margin:15px 0; color:#000;">Поздрав,<br>Тамара<br>070 253 467</p>"""

    return subject, wrap_html(body, recipient["email"])


TEMPLATES = {
    "A": template_group_a,
    "B": template_group_b,
    "C": template_group_c,
    "D": template_group_d,
}


# ─────────────────────────────────────────────────────────────
# SEND
# ─────────────────────────────────────────────────────────────

async def send_email(email, subject, html_body):
    """Send one email via Postmark broadcast stream."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.postmarkapp.com/email",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": POSTMARK_API_TOKEN,
            },
            json={
                "From": FROM_EMAIL,
                "To": email,
                "ReplyTo": "hello@nabavkidata.com",
                "Subject": subject,
                "HtmlBody": html_body,
                "MessageStream": "broadcast",
                "TrackOpens": True,
                "TrackLinks": "HtmlAndText",
                "Tag": "consulting-followup-mar24",
                "Headers": [
                    {"Name": "List-Unsubscribe", "Value": f"<{unsubscribe_url(email)}>"},
                    {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"},
                ],
            },
            timeout=30.0,
        )
    return resp


async def check_suppressed(conn, email):
    """Check if email is in suppression list."""
    row = await conn.fetchrow(
        "SELECT email FROM suppression_list WHERE email = $1", email
    )
    return row is not None


async def main():
    parser = argparse.ArgumentParser(description="Consulting follow-up campaign")
    parser.add_argument("--group", choices=["A", "B", "C", "D", "all"], default="all",
                        help="Which group to send (default: all)")
    parser.add_argument("--live", action="store_true", help="Actually send emails")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending (default)")
    parser.add_argument("--preview", type=str, metavar="EMAIL",
                        help="Send all emails for a group to this address instead")
    parser.add_argument("--delay", type=float, default=DELAY_BETWEEN, help="Seconds between sends")
    args = parser.parse_args()

    is_live = args.live and not args.dry_run

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        groups_to_send = list(ALL_GROUPS.keys()) if args.group == "all" else [args.group]

        total_sent = 0
        total_skipped = 0
        total_errors = 0

        for group_name in groups_to_send:
            recipients = ALL_GROUPS[group_name]
            template_fn = TEMPLATES[group_name]

            logger.info(f"\n{'='*60}")
            logger.info(f"GROUP {group_name}: {len(recipients)} recipients")
            logger.info(f"{'='*60}")

            for i, recipient in enumerate(recipients, 1):
                email = recipient["email"]

                # Check suppression
                if await check_suppressed(conn, email):
                    logger.info(f"  [{i}/{len(recipients)}] SKIPPED (suppressed): {email}")
                    total_skipped += 1
                    continue

                # Get market data
                market = await get_market_data(conn, recipient["keyword"])

                # Generate email
                subject, html_body = template_fn(recipient, market)

                if args.preview:
                    # Send to preview address instead
                    subject = f"[{group_name}:{email}] {subject}"
                    target = args.preview
                elif not is_live:
                    # Dry run — just print
                    logger.info(f"  [{i}/{len(recipients)}] {recipient['company']}")
                    logger.info(f"    TO: {email}")
                    logger.info(f"    SUBJECT: {subject}")
                    logger.info(f"    Market: {market['total_tenders']} tenders, {market['active_count']} active, {format_mkd(market['total_value'])}")
                    if market["competitors"]:
                        logger.info(f"    Top competitors: {', '.join(c['name'][:25] for c in market['competitors'][:3])}")
                    total_sent += 1
                    continue
                else:
                    target = email

                # SEND
                try:
                    resp = await send_email(target, subject, html_body)
                    if resp.status_code == 200:
                        msg_id = resp.json().get("MessageID", "?")
                        logger.info(f"  [{i}/{len(recipients)}] SENT {recipient['company']} -> {target} (ID: {msg_id})")
                        total_sent += 1
                    else:
                        logger.error(f"  [{i}/{len(recipients)}] ERROR {resp.status_code}: {resp.text[:200]}")
                        total_errors += 1
                except Exception as e:
                    logger.error(f"  [{i}/{len(recipients)}] EXCEPTION: {e}")
                    total_errors += 1

                await asyncio.sleep(args.delay)

        logger.info(f"\n{'='*60}")
        logger.info(f"DONE: {total_sent} {'sent' if is_live else 'previewed'}, {total_skipped} skipped, {total_errors} errors")
        logger.info(f"{'='*60}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

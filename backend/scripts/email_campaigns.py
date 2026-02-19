#!/usr/bin/env python3
"""
Cold Email Campaign System for NabavkiData
Sends personalized, professional emails to different segments.

Segments:
- A: Active tender participants (e-Nabavki) - Know the system, need better tools
- B: IT Decision makers (Apollo/IT.mk) - Tech-savvy, value efficiency
- C: General MK companies - May not know about tender opportunities

Usage:
    python3 scripts/email_campaigns.py --segment A --dry-run
    python3 scripts/email_campaigns.py --segment A --send --limit 100
"""
import os
import sys
import asyncio
import asyncpg
import aiohttp
import json
import argparse
from datetime import datetime, timedelta
import pytz

DATABASE_URL = os.getenv("DATABASE_URL")

# Postmark configuration
POSTMARK_API_KEY = os.environ.get("POSTMARK_API_TOKEN") or os.environ.get("POSTMARK_API_KEY", "")
POSTMARK_API_URL = "https://api.postmarkapp.com/email"
FROM_EMAIL = "hello@nabavkidata.com"  # So recipients can reply
FROM_NAME = "Тамара од НабавкиДата"

SKOPJE_TZ = pytz.timezone('Europe/Skopje')

# Path to HTML templates
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================================================
# HORMOZI-STYLE HTML TEMPLATE (for openers who didn't click)
# Short sentences, fear-based, clear value prop, PS with CTA
# ============================================================================

# Follow-up email - Story-based, FOMO, Loss aversion (accurate for open bidding)
HORMOZI_SUBJECT = "Една кратка приказна"

HORMOZI_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Ти пишав минатата недела.</p>

        <p>Веројатно беше зафатен. Разбирам.</p>

        <p>Но морам да ти кажам една кратка приказна.</p>

        <p>&nbsp;</p>

        <p>Пред 2 месеци ми се јави сопственик на фирма за медицинска опрема.</p>

        <p>Секој ден проверувал на е-Набавки дали има нов тендер. Читал PDF-ови со часови. Пресметувал цени на слепо - без да знае колку чинеле истите производи минатата година.</p>

        <p>Му покажав како со НабавкиДата:</p>

        <ul style="padding-left:20px;">
            <li>Добива известување штом излезе тендер од неговата дејност</li>
            <li>AI го чита PDF-от за 10 секунди и ги вади клучните барања</li>
            <li>Гледа историски цени - колку чинеле истите работи кај други институции</li>
            <li>Знае кој најчесто добива и со какви понуди</li>
        </ul>

        <p>По една недела ми рече: <em>"Тамара, за 3 часа подготвив понуда за која претходно ми требаа 3 дена."</em></p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:20px 0;">

        <p>&nbsp;</p>

        <p><strong>4,152 компании</strong> во Македонија веќе го користат НабавкиДата.</p>

        <p>Првата и единствена платформа од овој тип кај нас.</p>

        <p>15,000+ тендери. AI што чита документи. Историја на цени. Анализа на победници.</p>

        <p>Моментално нудиме <strong>бесплатен пробен период</strong> - но нема да трае засекогаш.</p>

        <p>&nbsp;</p>

        <p>Ако сакаш да видиш како изгледа:</p>

        <p><a href="https://nabavkidata.com" style="color:#0066cc; font-weight:bold;">nabavkidata.com</a></p>

        <p>Без обврска. Без картичка. Само погледни.</p>

        <p>&nbsp;</p>

        <p>- Тамара</p>

        <p>&nbsp;</p>

        <p><strong>ПС</strong> - Секој ден без вистински податоци е уште еден тендер каде конкуренцијата има предност. Пробај бесплатно и сам процени.</p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

        <p style="font-size:12px; color:#666666;">
            TAMSAR INC<br>
            131 Continental Dr Ste 305<br>
            New Castle, DE 19713<br>
            hello@nabavkidata.com<br><br>
            <a href="https://nabavkidata.com/unsubscribe?email={email}" style="color:#666666;">Отпиши се</a>
        </p>

    </div>
</body>
</html>
"""

# Plain text version (REQUIRED for deliverability)
HORMOZI_TEXT = """Ти пишав минатата недела.

Веројатно беше зафатен. Разбирам.

Но морам да ти кажам една кратка приказна.

Пред 2 месеци ми се јави сопственик на фирма за медицинска опрема.

Секој ден проверувал на е-Набавки дали има нов тендер. Читал PDF-ови со часови. Пресметувал цени на слепо - без да знае колку чинеле истите производи минатата година.

Му покажав како со НабавкиДата:
- Добива известување штом излезе тендер од неговата дејност
- AI го чита PDF-от за 10 секунди и ги вади клучните барања
- Гледа историски цени - колку чинеле истите работи кај други институции
- Знае кој најчесто добива и со какви понуди

По една недела ми рече: "Тамара, за 3 часа подготвив понуда за која претходно ми требаа 3 дена."

---

4,152 компании во Македонија веќе го користат НабавкиДата.

Првата и единствена платформа од овој тип кај нас.

15,000+ тендери. AI што чита документи. Историја на цени. Анализа на победници.

Моментално нудиме бесплатен пробен период - но нема да трае засекогаш.

Ако сакаш да видиш како изгледа:
https://nabavkidata.com

Без обврска. Без картичка. Само погледни.

- Тамара

ПС - Секој ден без вистински податоци е уште еден тендер каде конкуренцијата има предност. Пробај бесплатно и сам процени.

---
TAMSAR INC
131 Continental Dr Ste 305
New Castle, DE 19713
hello@nabavkidata.com

Отпиши се: https://nabavkidata.com/unsubscribe?email={email}
"""


# ============================================================================
# EMAIL TEMPLATES - SEGMENT A (Active Tender Participants)
# HORMOZI: Empathy → Story → Problem → Solution (no hype)
# ============================================================================

SEGMENT_A_SUBJECT = "Како една фирма од Битола почна да добива тендери"

SEGMENT_A_BODY = """Здраво,

Пред неколку месеци разговарав со сопственик на градежна фирма од Битола.

Учествувал на 15 тендери таа година. Добил 2.

Не затоа што немал капацитет. Не затоа што бил прескап. Туку затоа што секогаш дознавал за тендерите 2-3 дена пред рок. Журкал со понудата. Гаѓал цена на слепо.

Му покажав како неговиот конкурент од Скопје го гледа секој тендер истиот ден кога излегува. Како за 10 секунди го чита целиот PDF. Како гледа колку понудиле другите минатата година за ист тип набавка.

Не веруваше. Мислеше дека претерувам.

Па му дадов пристап да проба. Бесплатно.

По 2 недели ми се јави. Добил тендер од 8 милиони денари. Прв пат оваа година понудил цена базирана на реални податоци, не на претпоставки.

Ако и ти учествуваш на тендери и сакаш да видиш како изгледа ова - дај ми шанса да ти покажам.

nabavkidata.com - пробај бесплатно, па сам процени.

Тамара

---
Ако не сакаш повеќе вакви пораки: https://nabavkidata.com/unsubscribe?email={email}
"""


# ============================================================================
# EMAIL TEMPLATES - SEGMENT B (IT Decision Makers)
# HORMOZI: Personal, direct, no fluff
# ============================================================================

SEGMENT_B_SUBJECT = "{first_name}, кратко прашање"

SEGMENT_B_BODY = """Здраво {first_name},

Кратко и директно.

Дали {company_name} учествува на јавни набавки? Или сте размислувале да почнете?

Ако да - имам нешто што можеби ќе ти помогне.

Направивме алатка која го следи секој тендер во Македонија. Кога излегува нов тендер од твојата дејност, добиваш известување. AI го чита PDF-от и ти ги вади клучните барања. Гледаш колку понудиле другите фирми за слични набавки.

Не е магија. Само автоматизација на она што инаку би го правел рачно со часови.

Ако ти е интересно, пробај бесплатно на nabavkidata.com

Ако не - нема проблем, извини за пораката.

Поздрав,
Тамара

---
Ако не сакаш повеќе вакви пораки: https://nabavkidata.com/unsubscribe?email={email}
"""


# ============================================================================
# EMAIL TEMPLATES - SEGMENT C (General Companies)
# HORMOZI: Education + Opportunity (not fear)
# ============================================================================

SEGMENT_C_SUBJECT = "Дали знаевте за ова?"

SEGMENT_C_BODY = """Здраво,

Веројатно ова веќе го знаеш, но за секој случај:

Државата секоја година троши околу 60 милијарди денари на купување од приватни фирми. Канцелариски материјал, услуги, опрема, градежни работи - речиси се.

Многу мали фирми не знаат дека можат да учествуваат. Или мислат дека е премногу комплицирано.

А всушност не е. Се објавува на е-Набавки, се пополнува понуда, и толку.

Проблемот е што никој нема време секој ден да проверува дали излегол нов тендер. Затоа ја направивме НабавкиДата - алатка која автоматски те известува кога ќе излезе тендер од твојата дејност.

Не знам дали {company_name} има интерес за вакво нешто. Можеби веќе учествувате. Можеби не е за вас.

Но ако си љубопитен, погледни на nabavkidata.com - бесплатно е да се проба.

Поздрав,
Тамара

---
Ако не сакаш повеќе вакви пораки: https://nabavkidata.com/unsubscribe?email={email}
"""


# ============================================================================
# FOLLOW-UP TEMPLATES (for leads already contacted)
# ============================================================================

FOLLOWUP_SUBJECT = "Re: {original_subject}"

FOLLOWUP_BODY = """Здраво,

Само кратко потсетување - дали имавте прилика да ја погледнете НабавкиДата?

Оваа недела имаше {tender_count}+ нови тендери. Колку од нив беа релевантни за вас?

Линк: https://nabavkidata.com

Поздрав,
Тамара

---
Unsubscribe: https://nabavkidata.com/unsubscribe?email={email}
"""


def personalize_email(template: str, lead: dict) -> str:
    """Replace placeholders with lead data"""
    text = template

    # Extract data from raw_data JSON if available
    raw_data = {}
    if lead.get('raw_data'):
        try:
            raw_data = json.loads(lead['raw_data']) if isinstance(lead['raw_data'], str) else lead['raw_data']
        except:
            pass

    # Available replacements
    replacements = {
        '{company_name}': lead.get('company_name') or 'вашата компанија',
        '{first_name}': lead.get('first_name') or '',
        '{last_name}': lead.get('last_name') or '',
        '{email}': lead.get('email') or '',
        '{job_title}': lead.get('job_title') or '',
        '{city}': raw_data.get('city') or '',
        '{category}': raw_data.get('category') or '',
        '{tender_count}': '150',  # This week's tenders
        '{original_subject}': 'Дали ги следите сите тендери?',
    }

    for placeholder, value in replacements.items():
        text = text.replace(placeholder, str(value))

    return text


def personalize_subject(template: str, lead: dict) -> str:
    """Personalize subject line"""
    return personalize_email(template, lead)


async def get_leads(pool, segment: str, limit: int = 100, only_new: bool = True):
    """Get leads for a segment, excluding bounced and already contacted"""
    async with pool.acquire() as conn:
        if only_new:
            query = """
                SELECT lead_id, email, company_name, first_name, last_name, job_title,
                       country, raw_data, segment, source
                FROM outreach_leads ol
                WHERE segment = $1
                AND email NOT LIKE '%@example%'
                AND email NOT LIKE '%.jpg'
                AND email NOT LIKE '%.png'
                AND COALESCE(is_bounced, FALSE) = FALSE
                AND total_emails_sent = 0
                AND NOT EXISTS (
                    SELECT 1 FROM supplier_contacts sc
                    JOIN outreach_messages om ON sc.id = om.contact_id
                    WHERE sc.email = ol.email AND om.status = 'sent'
                )
                LIMIT $2
            """
        else:
            query = """
                SELECT lead_id, email, company_name, first_name, last_name, job_title,
                       country, raw_data, segment, source
                FROM outreach_leads ol
                WHERE segment = $1
                AND email NOT LIKE '%@example%'
                AND email NOT LIKE '%.jpg'
                AND email NOT LIKE '%.png'
                AND COALESCE(is_bounced, FALSE) = FALSE
                AND NOT EXISTS (
                    SELECT 1 FROM supplier_contacts sc
                    JOIN outreach_messages om ON sc.id = om.contact_id
                    WHERE sc.email = ol.email AND om.status = 'sent'
                )
                LIMIT $2
            """
        return await conn.fetch(query, segment, limit)


async def mark_email_sent(pool, lead_id, subject: str):
    """Mark lead as emailed"""
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE outreach_leads
            SET total_emails_sent = total_emails_sent + 1,
                first_contact_at = COALESCE(first_contact_at, NOW()),
                last_contact_at = NOW()
            WHERE lead_id = $1
        """, lead_id)


async def send_email(session, to_email: str, subject: str, body: str, dry_run: bool = True, html_body: str = None):
    """Send email via Postmark API. Use html_body for HTML emails."""
    if dry_run:
        print(f"\n{'='*60}")
        print(f"TO: {to_email}")
        print(f"SUBJECT: {subject}")
        print(f"FORMAT: {'HTML' if html_body else 'Plain Text'}")
        print(f"{'='*60}")
        content = html_body if html_body else body
        print(content[:500] + "..." if len(content) > 500 else content)
        return True

    if not POSTMARK_API_KEY:
        print("ERROR: POSTMARK_API_KEY not set")
        return False

    try:
        payload = {
            "From": f"{FROM_NAME} <{FROM_EMAIL}>",
            "To": to_email,
            "Subject": subject,
            "MessageStream": "outbound",  # Transactional stream - better deliverability
            "TrackOpens": False,
            "TrackLinks": "None"
        }

        # Use HTML if provided, otherwise plain text
        if html_body:
            payload["HtmlBody"] = html_body
        else:
            payload["TextBody"] = body

        async with session.post(
            POSTMARK_API_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": POSTMARK_API_KEY
            },
            json=payload
        ) as resp:
            if resp.status == 200:
                return True
            else:
                error = await resp.text()
                print(f"Postmark error for {to_email}: {error}")
                return False

    except Exception as e:
        print(f"Error sending to {to_email}: {e}")
        return False


async def send_test_email(to_email: str):
    """Send a test HTML email to verify template - with proper multipart"""
    print(f"Sending test email to {to_email}...")
    print(f"Subject: {HORMOZI_SUBJECT}")

    if not POSTMARK_API_KEY:
        print("ERROR: POSTMARK_API_KEY not set")
        return False

    html = HORMOZI_HTML.replace("{email}", to_email)
    text = HORMOZI_TEXT.replace("{email}", to_email)

    # Send with BOTH HTML and Text body for deliverability
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "From": f"{FROM_NAME} <{FROM_EMAIL}>",
                "To": to_email,
                "Subject": HORMOZI_SUBJECT,
                "HtmlBody": html,
                "TextBody": text,  # CRITICAL: Plain text version
                "MessageStream": "outbound",
                "TrackOpens": False,
                "TrackLinks": "None"
            }

            async with session.post(
                POSTMARK_API_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Postmark-Server-Token": POSTMARK_API_KEY
                },
                json=payload
            ) as resp:
                if resp.status == 200:
                    print(f"✓ Test email sent to {to_email}")
                    return True
                else:
                    error = await resp.text()
                    print(f"✗ Postmark error: {error}")
                    return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


async def run_campaign(segment: str, limit: int, dry_run: bool, send_now: bool):
    """Run email campaign for a segment"""

    print("=" * 70)
    print(f"EMAIL CAMPAIGN - SEGMENT {segment}")
    print("=" * 70)
    print(f"Dry run: {dry_run}")
    print(f"Limit: {limit}")

    # Select template based on segment
    if segment == 'A':
        subject_template = SEGMENT_A_SUBJECT
        body_template = SEGMENT_A_BODY
    elif segment == 'B':
        subject_template = SEGMENT_B_SUBJECT
        body_template = SEGMENT_B_BODY
    else:  # C
        subject_template = SEGMENT_C_SUBJECT
        body_template = SEGMENT_C_BODY

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)

    leads = await get_leads(pool, segment, limit)
    print(f"Found {len(leads)} leads to email")

    if not leads:
        print("No leads to process")
        await pool.close()
        return

    sent = 0
    failed = 0

    async with aiohttp.ClientSession() as session:
        for lead in leads:
            email = lead['email']
            subject = personalize_subject(subject_template, dict(lead))
            body = personalize_email(body_template, dict(lead))

            success = await send_email(session, email, subject, body, dry_run)

            if success:
                sent += 1
                if not dry_run:
                    await mark_email_sent(pool, lead['lead_id'], subject)
            else:
                failed += 1

            if dry_run and sent >= 3:
                print(f"\n[Dry run - showing first 3 emails only]")
                break

            # Rate limit: 1 email every 2.5s = 24/min = 1,440/hour (9AM-4PM = 7hrs)
            if not dry_run:
                await asyncio.sleep(2.5)

    print(f"\n{'='*70}")
    print(f"CAMPAIGN COMPLETE")
    print(f"{'='*70}")
    print(f"Sent: {sent}")
    print(f"Failed: {failed}")

    await pool.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--segment', choices=['A', 'B', 'C'])
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--send', action='store_true', help='Actually send emails')
    parser.add_argument('--test-email', type=str, help='Send test Hormozi HTML email to this address')
    args = parser.parse_args()

    # Test email mode
    if args.test_email:
        await send_test_email(args.test_email)
        return

    # Regular campaign mode
    if not args.segment:
        parser.error("--segment is required unless using --test-email")

    dry_run = not args.send

    await run_campaign(args.segment, args.limit, dry_run, args.send)


if __name__ == "__main__":
    asyncio.run(main())

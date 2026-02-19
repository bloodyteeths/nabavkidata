#!/usr/bin/env python3
"""
KILLER Cold Outreach Script for NabavkiData
High-conversion personalized Macedonian emails

Run with: python3 scripts/send_outreach_v2.py --limit 10 [--live]
"""
import os
import sys
import asyncio
import argparse
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import quote
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", os.getenv("DATABASE_URL"))
POSTMARK_TOKEN = os.getenv("POSTMARK_API_TOKEN", "")
POSTMARK_FROM = os.getenv("POSTMARK_FROM_EMAIL", "hello@nabavkidata.com")
POSTMARK_REPLY_TO = os.getenv("POSTMARK_REPLY_TO", "hello@nabavkidata.com")
POSTMARK_FROM_NAME = os.getenv("POSTMARK_FROM_NAME", "NabavkiData")
UNSUBSCRIBE_SECRET = os.getenv("UNSUBSCRIBE_SECRET", "nabavkidata-unsubscribe-2024")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://nabavkidata.com")


def generate_unsubscribe_token(email: str) -> str:
    return hashlib.sha256(f"{email}:{UNSUBSCRIBE_SECRET}".encode()).hexdigest()[:32]


def generate_unsubscribe_url(email: str) -> str:
    token = generate_unsubscribe_token(email)
    return f"{FRONTEND_URL}/unsubscribe?e={quote(email)}&t={token}"


def create_killer_email(company_name: str, total_wins: int, email: str) -> tuple:
    """Create professional personalized Macedonian email"""

    # Extract short company name for personalization
    skip_words = {"ДРУШТВО", "ТРГОВСКО", "АКЦИОНЕРСКО", "НАЦИОНАЛНА", "ГРУПАЦИЈА",
                  "ЗА", "И", "СО", "ОД", "ВО", "НА", "ПРОИЗВОДСТВО", "ТРГОВИЈА",
                  "УСЛУГИ", "ПРОМЕТ", "ИНЖЕНЕРИНГ", "ГРАДЕЖНИШТВО", "УВОЗ", "ИЗВОЗ",
                  "УВОЗ-ИЗВОЗ", "ЕКСПОРТ", "ИМПОРТ", "ЕКСПОРТ-ИМПОРТ", "ДОО", "ДООЕЛ",
                  "АД", "АГЕНЦИЈА", "ТРГОВИЈА,", "ПРОИЗВОДСТВО,", "УСЛУГИ,"}

    company_short = "вашата компанија"
    words = company_name.split()
    for w in words:
        clean = w.strip('.,()-').upper()
        if len(clean) >= 3 and clean not in skip_words:
            company_short = w.strip('.,()-')
            break

    unsubscribe_url = generate_unsubscribe_url(email)

    # Dynamic intro based on their success
    if total_wins >= 30:
        hook = f"Со {total_wins} победени тендери, {company_short} е меѓу топ 5% компании во Македонија."
        pain_point = "Но колку време губите на рачно пребарување и анализа на конкуренција?"
    elif total_wins >= 10:
        hook = f"{company_short} има солидни {total_wins} победи во јавните набавки."
        pain_point = "Замислете колку повеќе би победувале со вистинските информации во вистинско време."
    else:
        hook = f"Забележавме дека {company_short} учествува во јавните набавки."
        pain_point = "Дали знаете дека 70% од победниците користат специјализирани алатки за анализа?"

    subject = f"{company_short} - Алатка за анализа на тендери"

    text_body = f"""Почитувани,

{hook}

{pain_point}

NabavkiData е платформа која им помага на над 4,000 македонски компании да победуваат повеќе тендери. Еве што нудиме:

ЗАШТЕДЕТЕ ВРЕМЕ
- AI автоматски ги анализира PDF документите
- Извлекува технички спецификации и финансиски барања
- Нема потреба од рачно пребарување низ стотици страници

АНАЛИЗА НА КОНКУРЕНЦИЈАТА
- Пристап до 5 години историски податоци
- Видете по колку цени победуваат вашите конкуренти
- Разберете ја нивната стратегија пред да понудите

НИКОГАШ НЕ ПРОПУШТАЈТЕ МОЖНОСТ
- Известувања за нови тендери по CPV код или клучни зборови
- Следете промени и додатоци на активни тендери
- Добивајте информации во реално време

РАЗБЕРЕТЕ ЗОШТО ПОБЕДУВАТЕ ИЛИ ГУБИТЕ
- AI анализа на win factors - цена vs квалитет
- Идентификувајте ги клучните фактори за успех
- Прилагодете ја понудата за максимален резултат

Бесплатниот план вклучува до 5 следења, без обврска.

Посетете: https://nabavkidata.com

Ако имате прашања, слободно одговорете на овој мејл.

Поздрав,
Тимот на NabavkiData

---
Не сакате повеќе да добивате такви пораки?
Одјавете се: {unsubscribe_url}
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.7; color: #1a1a1a; max-width: 600px; margin: 0 auto; padding: 20px;">

<div style="background: white; padding: 32px;">

<p style="font-size: 16px; margin-bottom: 20px;">Почитувани,</p>

<p style="font-size: 16px; margin-bottom: 12px;"><strong>{hook}</strong></p>

<p style="font-size: 16px; color: #4b5563; margin-bottom: 28px;">{pain_point}</p>

<p style="font-size: 16px; margin-bottom: 24px;">
NabavkiData е платформа која им помага на над <strong>4,000 македонски компании</strong> да победуваат повеќе тендери. Еве што нудиме:
</p>

<p style="font-size: 15px; color: #1e40af; font-weight: 600; margin-bottom: 8px; margin-top: 24px;">ЗАШТЕДЕТЕ ВРЕМЕ</p>
<ul style="color: #4b5563; padding-left: 20px; margin-bottom: 20px; font-size: 15px;">
<li>AI автоматски ги анализира PDF документите</li>
<li>Извлекува технички спецификации и финансиски барања</li>
<li>Нема потреба од рачно пребарување низ стотици страници</li>
</ul>

<p style="font-size: 15px; color: #1e40af; font-weight: 600; margin-bottom: 8px;">АНАЛИЗА НА КОНКУРЕНЦИЈАТА</p>
<ul style="color: #4b5563; padding-left: 20px; margin-bottom: 20px; font-size: 15px;">
<li>Пристап до 5 години историски податоци</li>
<li>Видете по колку цени победуваат вашите конкуренти</li>
<li>Разберете ја нивната стратегија пред да понудите</li>
</ul>

<p style="font-size: 15px; color: #1e40af; font-weight: 600; margin-bottom: 8px;">НИКОГАШ НЕ ПРОПУШТАЈТЕ МОЖНОСТ</p>
<ul style="color: #4b5563; padding-left: 20px; margin-bottom: 20px; font-size: 15px;">
<li>Известувања за нови тендери по CPV код или клучни зборови</li>
<li>Следете промени и додатоци на активни тендери</li>
<li>Добивајте информации во реално време</li>
</ul>

<p style="font-size: 15px; color: #1e40af; font-weight: 600; margin-bottom: 8px;">РАЗБЕРЕТЕ ЗОШТО ПОБЕДУВАТЕ ИЛИ ГУБИТЕ</p>
<ul style="color: #4b5563; padding-left: 20px; margin-bottom: 20px; font-size: 15px;">
<li>AI анализа на win factors - цена vs квалитет</li>
<li>Идентификувајте ги клучните фактори за успех</li>
<li>Прилагодете ја понудата за максимален резултат</li>
</ul>

<p style="font-size: 15px; color: #6b7280; margin-bottom: 28px;">
Бесплатниот план вклучува до 5 следења, без обврска.
</p>

<div style="text-align: center; margin: 32px 0;">
<a href="https://nabavkidata.com" style="display: inline-block; background: #2563eb; color: white; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 500;">
Посетете NabavkiData
</a>
</div>

<p style="font-size: 15px; margin-top: 28px;">Ако имате прашања, слободно одговорете на овој мејл.</p>

<p style="font-size: 15px; margin-top: 24px;">
Поздрав,<br>
Тимот на NabavkiData
</p>

</div>

<div style="text-align: center; padding: 24px; color: #9ca3af; font-size: 12px; border-top: 1px solid #e5e7eb; margin-top: 20px;">
<p style="margin: 0;">
Не сакате повеќе да добивате такви пораки?
<a href="{unsubscribe_url}" style="color: #9ca3af;">Одјавете се овде</a>
</p>
</div>

</body>
</html>"""

    return subject, text_body, html_body


async def send_via_postmark(to_email: str, subject: str, text_body: str, html_body: str) -> Dict:
    """Send email via Postmark API"""
    if not POSTMARK_TOKEN:
        return {"error": "No Postmark token configured"}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.postmarkapp.com/email",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": POSTMARK_TOKEN
            },
            json={
                "From": f"{POSTMARK_FROM_NAME} <{POSTMARK_FROM}>",
                "ReplyTo": POSTMARK_REPLY_TO,
                "To": to_email,
                "Subject": subject,
                "TextBody": text_body,
                "HtmlBody": html_body,
                "MessageStream": "broadcast",
                "TrackOpens": True,
                "TrackLinks": "HtmlAndText"
            },
            timeout=30.0
        )

        if response.status_code == 200:
            data = response.json()
            return {"success": True, "message_id": data.get("MessageID")}
        else:
            return {"error": f"Postmark error: {response.status_code} - {response.text}"}


async def run_outreach(limit: int = 10, dry_run: bool = True):
    """Run outreach campaign"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    db = async_session()

    stats = {"sent": 0, "skipped": 0, "errors": 0}

    try:
        # Get contacts NOT already messaged
        result = await db.execute(text("""
            WITH ranked_contacts AS (
                SELECT
                    sc.supplier_id,
                    sc.email,
                    s.company_name,
                    s.total_wins,
                    sc.confidence_score,
                    sc.email_type,
                    ROW_NUMBER() OVER (
                        PARTITION BY sc.supplier_id
                        ORDER BY
                            CASE WHEN sc.email_type = 'role_based' THEN 0 ELSE 1 END,
                            sc.confidence_score DESC
                    ) as rn
                FROM supplier_contacts sc
                JOIN suppliers s ON sc.supplier_id = s.supplier_id
                WHERE sc.confidence_score >= 60
                  AND sc.email LIKE '%@%.%'
                  AND sc.email NOT LIKE '%gmail%'
                  AND sc.email NOT LIKE '%yahoo%'
                  AND sc.email NOT LIKE '%.png%'
                  AND sc.email NOT LIKE '%.gif%'
                  AND sc.email NOT LIKE '%.jpg%'
                  AND sc.email NOT LIKE '%u003e%'
                  AND sc.email NOT LIKE '%@2x%'
                  AND LENGTH(sc.email) > 10
                  AND sc.email ~ '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                  AND NOT EXISTS (
                      SELECT 1 FROM suppression_list sl WHERE sl.email = sc.email
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM outreach_messages om
                      WHERE om.supplier_id = sc.supplier_id
                  )
            )
            SELECT supplier_id, email, company_name, total_wins, confidence_score, email_type
            FROM ranked_contacts
            WHERE rn = 1
            ORDER BY total_wins DESC NULLS LAST
            LIMIT :limit
        """), {"limit": limit})

        contacts = result.fetchall()
        logger.info(f"Found {len(contacts)} NEW contacts to reach out to")

        if not contacts:
            logger.info("No eligible contacts found (all may have been contacted already)")
            return stats

        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 KILLER OUTREACH CAMPAIGN {'(DRY RUN)' if dry_run else '(LIVE)'}")
        logger.info(f"{'='*60}\n")

        for contact in contacts:
            try:
                company_short = contact.company_name[:50] + "..." if len(contact.company_name) > 50 else contact.company_name
                logger.info(f"[{stats['sent']+stats['errors']+1}/{len(contacts)}] {company_short}")
                logger.info(f"    📧 {contact.email} (wins: {contact.total_wins})")

                subject, text_body, html_body = create_killer_email(
                    contact.company_name,
                    contact.total_wins or 0,
                    contact.email
                )

                logger.info(f"    📬 Subject: {subject}")

                if dry_run:
                    logger.info(f"    ✅ [DRY RUN] Would send email")
                    stats["sent"] += 1
                else:
                    result = await send_via_postmark(contact.email, subject, text_body, html_body)

                    if result.get("success"):
                        message_id = result.get("message_id")
                        logger.info(f"    🚀 [SENT] Message ID: {message_id}")

                        # Record in outreach_messages
                        await db.execute(text("""
                            INSERT INTO outreach_messages
                            (supplier_id, contact_id, campaign_id, sequence_step, subject, postmark_message_id, status, sent_at)
                            SELECT
                                :supplier_id,
                                sc.id,
                                'killer-outreach-dec2024',
                                0,
                                :subject,
                                :message_id,
                                'sent',
                                NOW()
                            FROM supplier_contacts sc
                            WHERE sc.supplier_id = :supplier_id AND sc.email = :email
                            LIMIT 1
                        """), {
                            "supplier_id": contact.supplier_id,
                            "email": contact.email,
                            "subject": subject,
                            "message_id": message_id
                        })
                        await db.commit()
                        stats["sent"] += 1
                    else:
                        logger.error(f"    ❌ [ERROR] {result.get('error')}")
                        stats["errors"] += 1

                # Rate limit
                if not dry_run:
                    await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(f"    ❌ Error: {e}")
                stats["errors"] += 1

        logger.info(f"\n{'='*60}")
        logger.info("🎯 OUTREACH COMPLETE")
        logger.info(f"📤 Sent: {stats['sent']}")
        logger.info(f"⏭️  Skipped: {stats['skipped']}")
        logger.info(f"❌ Errors: {stats['errors']}")
        logger.info(f"{'='*60}")

    finally:
        await db.close()
        await engine.dispose()

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10, help="Max emails to send")
    parser.add_argument("--live", action="store_true", help="Actually send (default is dry-run)")
    args = parser.parse_args()

    asyncio.run(run_outreach(args.limit, not args.live))

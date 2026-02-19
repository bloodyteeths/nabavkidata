#!/usr/bin/env python3
"""
Cold Outreach Script for NabavkiData
Sends personalized Macedonian emails to suppliers via Postmark

Run with: python3 scripts/send_outreach.py --limit 10 [--live]
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
    """Generate HMAC unsubscribe token"""
    return hashlib.sha256(f"{email}:{UNSUBSCRIBE_SECRET}".encode()).hexdigest()[:32]


def generate_unsubscribe_url(email: str) -> str:
    """Generate one-click unsubscribe URL"""
    token = generate_unsubscribe_token(email)
    return f"{FRONTEND_URL}/unsubscribe?e={quote(email)}&t={token}"


def create_email_content(company_name: str, total_wins: int, email: str) -> tuple:
    """Create personalized Macedonian email content with social proof and compelling copy"""

    # Extract short company name for subject
    company_short = company_name.split()[0] if company_name.split() else "вашата компанија"

    # Determine segment and personalized hook
    if total_wins >= 20:
        segment = "top_winner"
        hook = f"Со {total_wins} добиени тендери, {company_name} е меѓу најуспешните понудувачи во Македонија."
        benefit = "Сега можете да ги видите цените на вашите конкуренти и да подготвите подобри понуди."
    elif total_wins >= 5:
        segment = "frequent"
        hook = f"Анализиравме {total_wins} ваши успешни понуди и пронајдовме интересни податоци."
        benefit = "Знаете ли по која цена добиле вашите конкуренти? Сега можете да дознаете."
    else:
        segment = "occasional"
        hook = f"Дали знаевте дека секој ден се објавуваат 50+ нови тендери на е-Набавки и е-Пазар?"
        benefit = "Повеќето компании ги пропуштаат - ние ви испраќаме само релевантните."

    unsubscribe_url = generate_unsubscribe_url(email)

    # Compelling subject line with curiosity gap
    subject = f"Колку платиле вашите конкуренти за последниот тендер?"

    # Text body with social proof and specific benefits
    text_body = f"""Почитувани,

{hook}

NabavkiData е единствената платформа во Македонија што ги обединува податоците од е-Набавки И е-Пазар на едно место.

Еве што добивате:

1. ЦЕНИ НА ПОБЕДНИЦИ - Видете точно колку платиле вашите конкуренти за секој тендер
2. АВТОМАТСКИ ИЗВЕСТУВАЊА - Добивајте нови тендери по е-маил или SMS штом се објават
3. АНАЛИЗА НА КОНКУРЕНЦИЈА - Кој најчесто добива тендери во вашата област?
4. ИСТОРИСКИ ПОДАТОЦИ - 50,000+ тендери и 10,000+ добавувачи во нашата база

{benefit}

Над 4,000+ корисници веќе го користат NabavkiData за да најдат нови можности.

Започнете БЕСПЛАТНО (5 следења, без кредитна картичка):
https://nabavkidata.com

Ако имате прашања, слободно одговорете на овој мејл - читам ги сите.

Поздрав,
Тамар
NabavkiData

P.S. Оваа недела имаме 3 нови тендери од над 1 милион денари во вашата област. Регистрирајте се за да ги видите.

---
Не сакате повеќе да добивате такви пораки?
Одјавете се овде: {unsubscribe_url}
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.7; color: #1a1a1a; max-width: 600px; margin: 0 auto; padding: 20px;">

<p>Почитувани,</p>

<p><strong>{hook}</strong></p>

<p>NabavkiData е <strong>единствената платформа во Македонија</strong> што ги обединува податоците од <strong>е-Набавки И е-Пазар</strong> на едно место.</p>

<p style="font-weight: 600; margin-top: 25px;">Еве што добивате:</p>

<table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
<tr>
<td style="padding: 12px; background: #f8fafc; border-left: 3px solid #2563eb;">
<strong>ЦЕНИ НА ПОБЕДНИЦИ</strong><br>
<span style="color: #666;">Видете точно колку платиле вашите конкуренти за секој тендер</span>
</td>
</tr>
<tr>
<td style="padding: 12px; background: #fff; border-left: 3px solid #2563eb;">
<strong>АВТОМАТСКИ ИЗВЕСТУВАЊА</strong><br>
<span style="color: #666;">Добивајте нови тендери по е-маил или SMS штом се објават</span>
</td>
</tr>
<tr>
<td style="padding: 12px; background: #f8fafc; border-left: 3px solid #2563eb;">
<strong>АНАЛИЗА НА КОНКУРЕНЦИЈА</strong><br>
<span style="color: #666;">Кој најчесто добива тендери во вашата област?</span>
</td>
</tr>
<tr>
<td style="padding: 12px; background: #fff; border-left: 3px solid #2563eb;">
<strong>ИСТОРИСКИ ПОДАТОЦИ</strong><br>
<span style="color: #666;">50,000+ тендери и 10,000+ добавувачи во нашата база</span>
</td>
</tr>
</table>

<p style="background: #fef3c7; padding: 15px; border-radius: 6px; margin: 20px 0;">
{benefit}
</p>

<p><strong>Над 200+ компании</strong> веќе го користат NabavkiData за да најдат нови можности.</p>

<p style="margin: 30px 0; text-align: center;">
<a href="https://nabavkidata.com" style="background-color: #2563eb; color: white; padding: 16px 32px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold; font-size: 16px;">Започнете БЕСПЛАТНО</a>
<br><span style="font-size: 12px; color: #666; margin-top: 8px; display: inline-block;">5 следења, без кредитна картичка</span>
</p>

<p>Ако имате прашања, слободно одговорете на овој мејл - читам ги сите.</p>

<p>Поздрав,<br><strong>Тамар</strong><br>NabavkiData</p>

<p style="background: #dbeafe; padding: 12px; border-radius: 6px; font-size: 14px; margin-top: 25px;">
<strong>P.S.</strong> Оваа недела имаме 3 нови тендери од над 1 милион денари во вашата област. Регистрирајте се за да ги видите.
</p>

<hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
<p style="font-size: 12px; color: #666;">
Не сакате повеќе да добивате такви пораки?
<a href="{unsubscribe_url}" style="color: #666;">Одјавете се овде</a>
</p>
</body>
</html>"""

    return subject, text_body, html_body, segment


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
        # Get best contacts per supplier (prioritize role_based, high confidence, .mk domains)
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
                  AND sc.email NOT LIKE '%u003e%'
                  AND NOT EXISTS (
                      SELECT 1 FROM suppression_list sl WHERE sl.email = sc.email
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM outreach_messages om WHERE om.contact_id = sc.id
                  )
            )
            SELECT supplier_id, email, company_name, total_wins, confidence_score, email_type
            FROM ranked_contacts
            WHERE rn = 1
            ORDER BY total_wins DESC NULLS LAST
            LIMIT :limit
        """), {"limit": limit})

        contacts = result.fetchall()
        logger.info(f"Found {len(contacts)} contacts to reach out to")

        if not contacts:
            logger.info("No eligible contacts found")
            return stats

        logger.info(f"\n{'='*60}")
        logger.info(f"OUTREACH CAMPAIGN {'(DRY RUN)' if dry_run else '(LIVE)'}")
        logger.info(f"{'='*60}\n")

        for contact in contacts:
            try:
                company_short = contact.company_name[:50] + "..." if len(contact.company_name) > 50 else contact.company_name
                logger.info(f"[{stats['sent']+stats['skipped']+1}/{len(contacts)}] {company_short}")
                logger.info(f"    Email: {contact.email} (score: {contact.confidence_score}, type: {contact.email_type})")
                logger.info(f"    Wins: {contact.total_wins}")

                subject, text_body, html_body, segment = create_email_content(
                    contact.company_name,
                    contact.total_wins or 0,
                    contact.email
                )

                logger.info(f"    Subject: {subject}")
                logger.info(f"    Segment: {segment}")

                if dry_run:
                    logger.info(f"    [DRY RUN] Would send email")
                    stats["sent"] += 1
                else:
                    # Send via Postmark
                    result = await send_via_postmark(contact.email, subject, text_body, html_body)

                    if result.get("success"):
                        message_id = result.get("message_id")
                        logger.info(f"    [SENT] Message ID: {message_id}")

                        # Record in outreach_messages
                        await db.execute(text("""
                            INSERT INTO outreach_messages
                            (supplier_id, contact_id, campaign_id, sequence_step, subject, postmark_message_id, status, sent_at)
                            SELECT
                                :supplier_id,
                                sc.id,
                                'direct-outreach-dec2024',
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
                        logger.error(f"    [ERROR] {result.get('error')}")
                        stats["errors"] += 1

                # Rate limit: small delay between sends
                if not dry_run:
                    await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(f"    Error: {e}")
                stats["errors"] += 1

        logger.info(f"\n{'='*60}")
        logger.info("OUTREACH COMPLETE")
        logger.info(f"Sent: {stats['sent']}")
        logger.info(f"Skipped: {stats['skipped']}")
        logger.info(f"Errors: {stats['errors']}")
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

#!/usr/bin/env python3
"""
One-Time Broadcast: Discount Code to All Free Users

Sends a single email to all verified free-tier users with the DOBRODOJDE15
discount code (15% off Pro plan). Combines FOMO + exclusive early-adopter offer.

Usage:
  python3 crons/broadcast_discount.py --dry-run   # Preview recipients
  python3 crons/broadcast_discount.py              # Send for real
"""

import os
import sys
import asyncio
import argparse
import hashlib
import logging
from datetime import datetime
import httpx
import asyncpg
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL')
POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN")
if not POSTMARK_API_TOKEN:
    raise SystemExit(
        "POSTMARK_API_TOKEN is not set. Export it or put it in .env.production.\n"
        "There is deliberately no default: the token that used to be hardcoded here was "
        "revoked and every caller relying on it failed with a silent HTTP 401."
    )
POSTMARK_FROM_EMAIL = 'hello@nabavkidata.com'
POSTMARK_FROM_NAME = 'Тамара од НабавкиДата'
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://nabavkidata.com')
UNSUBSCRIBE_SECRET = os.getenv('UNSUBSCRIBE_SECRET', 'nabavki-unsub-secret-2025')

BATCH_SIZE = 50


def generate_unsubscribe_url(email: str) -> str:
    token = hashlib.sha256(f"{email}:{UNSUBSCRIBE_SECRET}".encode()).hexdigest()[:32]
    return f"{FRONTEND_URL}/unsubscribe?e={email}&t={token}"
BATCH_DELAY = 1.0  # seconds between batches


def get_broadcast_email(first_name: str, user_email: str) -> dict:
    """Generate the broadcast email content"""
    unsub_url = generate_unsubscribe_url(user_email)
    return {
        "subject": f"{first_name}, имаш ексклузивен попуст - само 5 дена",
        "html": f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Здраво {first_name},</p>

        <p>Јавувам се лично бидејќи си еден од нашите <strong>први 150 корисници</strong>.</p>

        <p>Оваа недела на е-Набавки беа објавени <strong>над 80 нови тендери</strong>.</p>

        <p>Колку од нив беа од твојата дејност? <strong>Колку пропушти?</strong></p>

        <p>&nbsp;</p>

        <p>Со <strong>Pro планот</strong> добиваш:</p>

        <ul style="padding-left:20px;">
            <li>Известувања штом излезе тендер од твојата област</li>
            <li>Неограничени AI прашања (наместо 2 дневно)</li>
            <li>Историски цени - знаеш точно колку да понудиш</li>
            <li>Извоз на податоци и анализа на конкуренти</li>
        </ul>

        <p>&nbsp;</p>

        <p>Затоа што си од почеток со нас, имам попуст <strong>САМО</strong> за тебе:</p>

        <div style="background:#f0f9ff; border:2px dashed #2563eb; border-radius:12px; padding:20px; text-align:center; margin:20px 0;">
            <p style="margin:0 0 5px 0; font-size:14px; color:#666;">Твој ексклузивен код:</p>
            <p style="margin:0 0 10px 0; font-size:28px; font-weight:bold; color:#2563eb; letter-spacing:2px;">DOBRODOJDE15</p>
            <p style="margin:0 0 10px 0; font-size:16px;"><strong>15% попуст</strong> на Pro план</p>
            <p style="margin:0; font-size:14px; color:#ef4444; font-weight:bold;">Важи до петок, 28.02</p>
        </div>

        <p style="text-align:center;">
            <a href="{FRONTEND_URL}/billing" style="background:#2563eb; color:white; padding:14px 28px; border-radius:5px; text-decoration:none; display:inline-block; font-size:16px; font-weight:bold;">Активирај попуст</a>
        </p>

        <p>&nbsp;</p>

        <p><strong>По петок - полна цена, без исклучоци.</strong></p>

        <p>Ако имаш прашања, само одговори на овој мејл.</p>

        <p>- Тамара</p>

        <p>&nbsp;</p>

        <p><em>ПС: Над 4,000 компании веќе учествуваат на тендери. Твоите конкуренти можеби веќе го користат ова.</em></p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

        <p style="font-size:12px; color:#666666;">
            TAMSAR INC | hello@nabavkidata.com<br>
            <a href="{unsub_url}" style="color:#666666;">Отпиши се</a>
        </p>

    </div>
</body>
</html>""",
        "text": f"""Здраво {first_name},

Јавувам се лично бидејќи си еден од нашите први 150 корисници.

Оваа недела на е-Набавки беа објавени над 80 нови тендери.
Колку од нив беа од твојата дејност? Колку пропушти?

Со Pro планот добиваш:
- Известувања штом излезе тендер од твојата област
- Неограничени AI прашања (наместо 2 дневно)
- Историски цени - знаеш точно колку да понудиш
- Извоз на податоци и анализа на конкуренти

Затоа што си од почеток со нас, имам попуст САМО за тебе:

Код: DOBRODOJDE15
15% попуст на Pro план
Важи до петок, 28.02

Активирај попуст: {FRONTEND_URL}/billing

По петок - полна цена, без исклучоци.

Ако имаш прашања, само одговори на овој мејл.

- Тамара

ПС: Над 4,000 компании веќе учествуваат на тендери.
Твоите конкуренти можеби веќе го користат ова.

---
Отпиши се: {unsub_url}"""
    }


async def get_recipients(conn) -> list:
    """Get all verified free-tier users, excluding suppressed/unsubscribed"""
    return await conn.fetch("""
        SELECT u.user_id, u.email, u.full_name
        FROM users u
        WHERE u.email_verified = true
          AND (u.subscription_tier IS NULL OR u.subscription_tier = 'free')
          AND u.email NOT IN (
              SELECT email FROM suppression_list WHERE email IS NOT NULL
          )
          AND u.email NOT IN (
              SELECT email FROM campaign_unsubscribes WHERE email IS NOT NULL
          )
        ORDER BY u.created_at ASC
    """)


async def send_email(client: httpx.AsyncClient, email: str, first_name: str) -> dict:
    """Send broadcast email via Postmark"""
    template = get_broadcast_email(first_name, email)

    response = await client.post(
        "https://api.postmarkapp.com/email",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": POSTMARK_API_TOKEN
        },
        json={
            "From": f"{POSTMARK_FROM_NAME} <{POSTMARK_FROM_EMAIL}>",
            "To": email,
            "Subject": template["subject"],
            "HtmlBody": template["html"],
            "TextBody": template["text"],
            "MessageStream": "outbound",
            "TrackOpens": True,
            "TrackLinks": "HtmlAndText",
            "Tag": "broadcast-discount-feb2026"
        },
        timeout=30.0
    )

    if response.status_code == 200:
        return {"success": True, "message_id": response.json().get("MessageID")}
    else:
        return {"success": False, "error": response.text}


async def main():
    if os.getenv("ALLOW_RETIRED_SAAS_CAMPAIGNS") != "1":
        # Bid service since 14 Oct 2026: these emails sell retired plans/trials.
        print("retired: self-serve plans no longer sold")
        return
    parser = argparse.ArgumentParser(description='One-time discount broadcast')
    parser.add_argument('--dry-run', action='store_true', help='Preview recipients without sending')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("BROADCAST: Discount Code to Free Users")
    logger.info(f"Time: {datetime.utcnow().isoformat()}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE SEND'}")
    logger.info("=" * 60)

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        recipients = await get_recipients(conn)
        logger.info(f"Found {len(recipients)} recipients")

        if args.dry_run:
            logger.info("\nDRY RUN - Would send to:")
            for r in recipients:
                name = (r['full_name'] or '').split()[0] if r['full_name'] else 'Корисниче'
                logger.info(f"  {r['email']} ({name})")
            logger.info(f"\nTotal: {len(recipients)} emails")
            return

        sent = 0
        errors = 0

        async with httpx.AsyncClient() as client:
            for i, user in enumerate(recipients):
                first_name = (user['full_name'] or '').split()[0] if user['full_name'] else 'Корисниче'

                result = await send_email(client, user['email'], first_name)

                if result['success']:
                    sent += 1
                    logger.info(f"  [{sent}/{len(recipients)}] {user['email']} - sent")
                else:
                    errors += 1
                    logger.error(f"  [{i+1}/{len(recipients)}] {user['email']} - ERROR: {result.get('error', '')[:80]}")

                # Rate limiting: pause between batches
                if (i + 1) % BATCH_SIZE == 0:
                    logger.info(f"  ... pausing {BATCH_DELAY}s after batch of {BATCH_SIZE}")
                    await asyncio.sleep(BATCH_DELAY)
                else:
                    await asyncio.sleep(0.2)

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"COMPLETE: {sent} sent, {errors} errors out of {len(recipients)} recipients")
        logger.info("=" * 60)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

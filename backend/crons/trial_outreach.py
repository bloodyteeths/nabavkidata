#!/usr/bin/env python3
"""
Trial Outreach - Send personalized trial offers to engaged free users.

Identifies the top 30 most engaged free users and sends them a personal
email offering a 7-day Pro trial.

Only sends once per user (tracks in welcome_series.stopped_reason or
a simple check against audit_log).

Run manually: python3 crons/trial_outreach.py
Or schedule: weekly on Mondays
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
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

DATABASE_URL = os.getenv('DATABASE_URL')
POSTMARK_API_TOKEN = os.getenv('POSTMARK_API_TOKEN', '')
POSTMARK_FROM_EMAIL = 'hello@nabavkidata.com'
POSTMARK_FROM_NAME = 'Тамара од НабавкиДата'
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://nabavkidata.com')


async def get_engaged_free_users(conn) -> list:
    """Find top 30 most engaged free users who haven't been offered a trial yet."""
    rows = await conn.fetch("""
        WITH engagement AS (
            SELECT
                u.user_id,
                u.email,
                u.full_name,
                u.created_at,
                u.last_login,
                COALESCE(
                    (SELECT COUNT(*) FROM user_behavior ub WHERE ub.user_id = u.user_id), 0
                ) as behavior_actions,
                COALESCE(
                    (SELECT COUNT(*) FROM user_sessions us WHERE us.user_id = u.user_id), 0
                ) as session_count,
                COALESCE(
                    (SELECT COUNT(*) FROM chat_sessions cs WHERE cs.user_id = u.user_id), 0
                ) as chat_count,
                COALESCE(
                    (SELECT COUNT(*) FROM usage_tracking ut WHERE ut.user_id = u.user_id), 0
                ) as usage_actions
            FROM users u
            WHERE u.subscription_tier = 'free'
              AND u.email_verified = true
              AND u.last_login >= NOW() - INTERVAL '14 days'
              -- Exclude users who already received trial outreach
              AND NOT EXISTS (
                  SELECT 1 FROM audit_log al
                  WHERE al.user_id = u.user_id
                  AND al.action = 'trial_outreach_sent'
              )
              -- Exclude users who already had a trial
              AND u.trial_ends_at IS NULL
        )
        SELECT user_id, email, full_name, created_at, last_login,
               behavior_actions, session_count, chat_count, usage_actions,
               (behavior_actions + session_count * 2 + chat_count * 3 + usage_actions) as engagement_score
        FROM engagement
        WHERE (behavior_actions + session_count + chat_count + usage_actions) > 0
        ORDER BY engagement_score DESC
        LIMIT 30
    """)
    return rows


def get_email_template(user_name: str, email: str) -> dict:
    """Generate personalized trial offer email."""
    name = user_name or email.split('@')[0].capitalize()
    unsub_url = f"{FRONTEND_URL}/unsubscribe?email={email}"

    subject = f"{name}, имаме нешто специјално за тебе"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1a1a2e;">

<p>Здраво {name},</p>

<p>Јас сум Тамара од НабавкиДата. Видов дека го користиш НабавкиДата за следење на тендери - и сакам лично да ти понудам нешто.</p>

<p><strong>7 дена бесплатен Pro пристап</strong> - без картичка, без обврска.</p>

<p>Со Pro планот добиваш:</p>
<ul style="line-height: 1.8;">
    <li><strong>25 AI прашања дневно</strong> наместо 5</li>
    <li><strong>Анализа на ризик</strong> - откријте сомнителни тендери</li>
    <li><strong>AI совети за понуди</strong> - колку да понудите</li>
    <li><strong>200 ценовни прегледи</strong> дневно</li>
    <li><strong>Извоз на податоци</strong> во CSV и PDF</li>
    <li><strong>15 зачувани пребарувања</strong> со дневни известувања</li>
</ul>

<p style="text-align: center; margin: 30px 0;">
    <a href="{FRONTEND_URL}/settings#plans"
       style="background-color: #6366f1; color: white; padding: 14px 32px; border-radius: 8px;
              text-decoration: none; font-weight: 600; font-size: 16px; display: inline-block;">
        Активирај бесплатна Pro проба
    </a>
</p>

<p>Ако имаш било какви прашања, само одговори на овој мејл - лично ќе ти одговорам.</p>

<p>Поздрав,<br>
<strong>Тамара</strong><br>
<span style="color: #6366f1;">НабавкиДата</span></p>

<hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
<p style="font-size: 12px; color: #9ca3af;">
    <a href="{unsub_url}" style="color: #9ca3af;">Отпиши се од емаил известувања</a>
</p>

</body>
</html>"""

    text_body = f"""Здраво {name},

Јас сум Тамара од НабавкиДата. Видов дека го користиш НабавкиДата и сакам лично да ти понудам 7 дена бесплатен Pro пристап.

Со Pro добиваш:
- 25 AI прашања дневно наместо 5
- Анализа на ризик и корупција
- AI совети за понуди
- 200 ценовни прегледи дневно
- Извоз на податоци
- 15 зачувани пребарувања

Активирај: {FRONTEND_URL}/settings#plans

Ако имаш прашања - само одговори на овој мејл.

- Тамара

---
Отпиши се: {unsub_url}"""

    return {"subject": subject, "html": html, "text": text_body}


async def send_trial_email(client: httpx.AsyncClient, email: str, user_name: str) -> dict:
    """Send trial offer email via Postmark."""
    template = get_email_template(user_name, email)

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
            "Tag": "trial-outreach"
        },
        timeout=30.0
    )

    if response.status_code == 200:
        return {"success": True, "message_id": response.json().get("MessageID")}
    else:
        return {"success": False, "error": response.text}


async def main():
    """Main outreach process."""
    logger.info("=" * 60)
    logger.info("TRIAL OUTREACH - Personal offers to engaged free users")
    logger.info(f"Time: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    if not POSTMARK_API_TOKEN:
        logger.error("POSTMARK_API_TOKEN not set")
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        users = await get_engaged_free_users(conn)
        logger.info(f"Found {len(users)} engaged free users for trial outreach")

        if not users:
            logger.info("No eligible users found. Exiting.")
            return

        sent = 0
        failed = 0

        async with httpx.AsyncClient() as client:
            for user in users:
                email = user['email']
                name = user['full_name']
                score = user['engagement_score']

                logger.info(f"  Sending to {email} (score: {score}, sessions: {user['session_count']}, actions: {user['behavior_actions']})")

                result = await send_trial_email(client, email, name)

                if result['success']:
                    sent += 1
                    # Record that we sent the outreach (prevents duplicates)
                    await conn.execute("""
                        INSERT INTO audit_log (user_id, action, details, created_at)
                        VALUES ($1, 'trial_outreach_sent', $2, NOW())
                    """, user['user_id'], f'{{"engagement_score": {score}, "message_id": "{result.get("message_id", "")}"}}')
                else:
                    failed += 1
                    logger.error(f"  Failed: {result.get('error', 'unknown')}")

                # Respect Postmark rate limits
                await asyncio.sleep(1)

        logger.info(f"\nResults: {sent} sent, {failed} failed, {len(users)} total")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

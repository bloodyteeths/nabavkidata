"""
Campaign Sender Service
Sends personalized report emails via Postmark with throttling, A/B testing, and follow-ups
All content in Macedonian language
"""
import os
import re
import json
import random
import asyncio
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import uuid

import httpx
import asyncpg

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN", "")
POSTMARK_MESSAGE_STREAM = os.getenv("POSTMARK_MESSAGE_STREAM", "broadcast")
POSTMARK_FROM_EMAIL = os.getenv("POSTMARK_FROM_EMAIL", "tamara@nabavkidata.com")
POSTMARK_FROM_NAME = os.getenv("POSTMARK_FROM_NAME", "Тамара, NabavkiData")
POSTMARK_REPLY_TO = os.getenv("POSTMARK_REPLY_TO", "hello@nabavkidata.com")

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://nabavkidata.com")
CHECKOUT_URL = os.getenv("CHECKOUT_URL", f"{FRONTEND_URL}/plans")
UNSUBSCRIBE_SECRET = os.getenv("UNSUBSCRIBE_SECRET", "nabavki-unsub-secret-2025")

# Default campaign settings
DEFAULT_SETTINGS = {
    "daily_limit": 3000,
    "hourly_limit": 200,
    "min_jitter_seconds": 30,
    "max_jitter_seconds": 180,
    "followup_1_days": 3,
    "followup_2_days": 7,
    "followup_3_days": 14,
    "followup_4_days": 21,
    "attach_pdf_first_n": 20
}


# ============================================================================
# EMAIL TEMPLATES (Macedonian)
# ============================================================================

SUBJECT_VARIANTS = {
    "A": "{company}: тендерски извештај (последни 90 дена)",
    "B": "{company} vs конкуренција: победи, пропуштени тендери"
}

FOLLOWUP_1_SUBJECT = "Дали да продолжам со неделни извештаи за {company}?"
FOLLOWUP_2_SUBJECT = "Сакате извештај прилагоден на вашите клучни зборови?"
FOLLOWUP_3_SUBJECT = "Нови тендери за {company} — овој месец"
FOLLOWUP_4_SUBJECT = "Последна порака: дали да продолжам со извештаи за {company}?"


def generate_email_html(
    company_name: str,
    stats: Dict,
    missed_count: int,
    report_url: str,
    checkout_url: str,
    unsubscribe_url: str
) -> str:
    """Generate HTML email body in Macedonian"""
    participations = stats.get("participations_12m", 0)
    wins = stats.get("wins_12m", 0)
    win_rate = stats.get("win_rate", 0)
    top_cpvs = stats.get("top_cpvs", [])

    cpv_text = ", ".join([c.get("name", c.get("code", "")) for c in top_cpvs[:2]]) if top_cpvs else "различни категории"

    html = f"""
<!DOCTYPE html>
<html lang="mk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">

<p>Почитувани,</p>

<p>Генерирав приватен тендерски извештај за <strong>{company_name}</strong> од јавно достапни податоци.</p>

<p style="background: #f5f5f5; padding: 15px; border-radius: 5px;">
<strong>Последни 12 месеци:</strong> {participations} учества, {wins} победи ({win_rate}%).<br>
<strong>Топ категории:</strong> {cpv_text}
</p>

<p style="color: #c00;">
Пронајдовме <strong>{missed_count} релевантни тендери</strong> во последните 90 дена каде што не учествувавте (наведени во извештајот со причини за совпаѓање).
</p>

<p>
<a href="{report_url}" style="display: inline-block; background: #1e3a5f; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 10px 0;">Преземи го извештајот (PDF)</a>
</p>

<p>
Ако сакате овој извештај неделно + дневни известувања за нови тендери:
</p>
<ul style="margin: 10px 0;">
<li>Одговорете <strong>ФАКТУРА</strong> за активирање со фактура (EUR)</li>
<li>Или активирајте со картичка: <a href="{checkout_url}">{checkout_url}</a></li>
</ul>

<p style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; font-size: 12px; color: #666;">
Поздрав,<br>
Тамара<br>
NabavkiData
</p>

<p style="font-size: 11px; color: #999;">
Одговорете СТОП за да не добивате повеќе вакви пораки или <a href="{unsubscribe_url}">кликнете тука за одјава</a>.
</p>

</body>
</html>
"""
    return html


def generate_email_text(
    company_name: str,
    stats: Dict,
    missed_count: int,
    report_url: str,
    checkout_url: str,
    unsubscribe_url: str
) -> str:
    """Generate plain text email body in Macedonian"""
    participations = stats.get("participations_12m", 0)
    wins = stats.get("wins_12m", 0)
    win_rate = stats.get("win_rate", 0)
    top_cpvs = stats.get("top_cpvs", [])

    cpv_text = ", ".join([c.get("name", c.get("code", "")) for c in top_cpvs[:2]]) if top_cpvs else "различни категории"

    text = f"""Почитувани,

Генерирав приватен тендерски извештај за {company_name} од јавно достапни податоци.

Последни 12 месеци: {participations} учества, {wins} победи ({win_rate}%).
Топ категории: {cpv_text}

Пронајдовме {missed_count} релевантни тендери во последните 90 дена каде што не учествувавте (наведени во извештајот со причини за совпаѓање).

Преземи го извештајот: {report_url}

---

Ако сакате овој извештај неделно + дневни известувања:
- Одговорете ФАКТУРА за активирање со фактура (EUR)
- Или активирајте со картичка: {checkout_url}

---

Поздрав,
Тамара
NabavkiData

Одговорете СТОП за одјава или посетете: {unsubscribe_url}
"""
    return text


def generate_followup_1_html(company_name: str, checkout_url: str, unsubscribe_url: str) -> str:
    """Generate first follow-up email HTML"""
    return f"""
<!DOCTYPE html>
<html lang="mk">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">

<p>Почитувани,</p>

<p>Дали да продолжам со генерирање неделни извештаи за <strong>{company_name}</strong>?</p>

<p>Извештаите вклучуваат:</p>
<ul>
<li>Нови тендери во вашите категории</li>
<li>Активности на конкуренцијата</li>
<li>Пропуштени можности</li>
</ul>

<p>
<a href="{checkout_url}" style="display: inline-block; background: #1e3a5f; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Активирај неделни извештаи</a>
</p>

<p>Или одговорете <strong>ФАКТУРА</strong> за плаќање со фактура.</p>

<p style="margin-top: 30px; font-size: 12px; color: #666;">
Поздрав,<br>Тамара
</p>

<p style="font-size: 11px; color: #999;">
<a href="{unsubscribe_url}">Одјава</a> | Одговорете СТОП
</p>

</body>
</html>
"""


def generate_followup_2_html(company_name: str, checkout_url: str, unsubscribe_url: str) -> str:
    """Generate second follow-up email HTML"""
    return f"""
<!DOCTYPE html>
<html lang="mk">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">

<p>Почитувани,</p>

<p>Сакате извештај прилагоден на вашите точни потреби?</p>

<p>Одговорете со 2-3 клучни зборови (на пример: "медицинска опрема", "ИТ услуги") и ќе генерирам нов извештај специјално за вас.</p>

<p>Или активирајте целосен пристап: <a href="{checkout_url}">{checkout_url}</a></p>

<p style="margin-top: 30px; font-size: 12px; color: #666;">
Поздрав,<br>Тамара
</p>

<p style="font-size: 11px; color: #999;">
<a href="{unsubscribe_url}">Одјава</a> | Одговорете СТОП
</p>

</body>
</html>
"""


def generate_followup_3_html(company_name: str, checkout_url: str, unsubscribe_url: str) -> str:
    """Generate third follow-up email HTML — new tender alert"""
    return f"""
<!DOCTYPE html>
<html lang="mk">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">

<p>Почитувани,</p>

<p>Оваа недела има <strong>нови активни тендери</strong> во категориите каде {company_name} учествува.</p>

<p>Нашите корисници добиваат <strong>автоматски известувања</strong> штом се објави нов тендер — директно на мејл.</p>

<p>
<a href="{checkout_url}" style="display: inline-block; background: #1e3a5f; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Активирај AI известувања</a>
</p>

<p style="margin-top: 30px; font-size: 12px; color: #666;">
Поздрав,<br>Тамара
</p>

<p style="font-size: 11px; color: #999;">
<a href="{unsubscribe_url}">Одјава</a> | Одговорете СТОП
</p>

</body>
</html>
"""


def generate_followup_4_html(company_name: str, checkout_url: str, unsubscribe_url: str) -> str:
    """Generate fourth follow-up email HTML — soft close"""
    return f"""
<!DOCTYPE html>
<html lang="mk">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">

<p>Почитувани,</p>

<p>Ова е последната порака од мене.</p>

<p>Ви испратив информации за тоа како NabavkiData може да ви помогне со тендерски известувања, конкурентски анализи и AI пребарување за <strong>{company_name}</strong>.</p>

<p>Ако имате интерес — одговорете <strong>ДА</strong> и ќе ви отворам бесплатна пробна сметка.</p>

<p>Ако не — нема проблем, нема да ви пишувам повеќе.</p>

<p>Ви посакувам успешна тендерска сезона!</p>

<p style="margin-top: 30px; font-size: 12px; color: #666;">
Поздрав,<br>Тамара<br>NabavkiData
</p>

<p style="font-size: 11px; color: #999;">
<a href="{unsubscribe_url}">Одјава</a> | Одговорете СТОП
</p>

</body>
</html>
"""


# ============================================================================
# UNSUBSCRIBE HANDLING
# ============================================================================

def generate_unsubscribe_token(email: str) -> str:
    """Generate unsubscribe token"""
    data = f"{email}:{UNSUBSCRIBE_SECRET}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def verify_unsubscribe_token(email: str, token: str) -> bool:
    """Verify unsubscribe token"""
    expected = generate_unsubscribe_token(email)
    return token == expected


def generate_unsubscribe_url(email: str) -> str:
    """Generate unsubscribe URL"""
    token = generate_unsubscribe_token(email)
    return f"{FRONTEND_URL}/unsubscribe?email={email}&token={token}"


# ============================================================================
# CAMPAIGN SENDER SERVICE
# ============================================================================

class CampaignSender:
    """Sends campaign emails via Postmark with throttling"""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": POSTMARK_API_TOKEN
            }
        )

    async def close(self):
        await self.http_client.aclose()

    async def get_rate_limits(self, campaign_id: str) -> Tuple[int, int, int, int]:
        """Get current sending counts vs limits"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_start = now.replace(minute=0, second=0, microsecond=0)

        async with self.pool.acquire() as conn:
            # Get campaign settings
            campaign = await conn.fetchrow(
                "SELECT settings FROM report_campaigns WHERE id = $1",
                uuid.UUID(campaign_id)
            )
            settings = json.loads(campaign['settings']) if campaign and campaign['settings'] else DEFAULT_SETTINGS

            daily_limit = settings.get("daily_limit", DEFAULT_SETTINGS["daily_limit"])
            hourly_limit = settings.get("hourly_limit", DEFAULT_SETTINGS["hourly_limit"])

            # Count today's sends
            daily_count = await conn.fetchval("""
                SELECT COUNT(*) FROM outreach_events
                WHERE event_type = 'sent' AND created_at >= $1
            """, today_start)

            # Count this hour's sends
            hourly_count = await conn.fetchval("""
                SELECT COUNT(*) FROM outreach_events
                WHERE event_type = 'sent' AND created_at >= $1
            """, hour_start)

            return daily_count or 0, daily_limit, hourly_count or 0, hourly_limit

    async def can_send(self, campaign_id: str) -> Tuple[bool, str]:
        """Check if we can send more emails"""
        daily_count, daily_limit, hourly_count, hourly_limit = await self.get_rate_limits(campaign_id)

        if daily_count >= daily_limit:
            return False, f"Дневен лимит достигнат ({daily_count}/{daily_limit})"
        if hourly_count >= hourly_limit:
            return False, f"Часовен лимит достигнат ({hourly_count}/{hourly_limit})"

        return True, f"OK (ден: {daily_count}/{daily_limit}, час: {hourly_count}/{hourly_limit})"

    async def is_suppressed(self, email: str) -> bool:
        """Check if email is suppressed"""
        async with self.pool.acquire() as conn:
            # Check suppression list
            suppressed = await conn.fetchval("""
                SELECT 1 FROM suppression_list WHERE email = $1
            """, email.lower())
            if suppressed:
                return True

            # Check campaign unsubscribes
            unsubbed = await conn.fetchval("""
                SELECT 1 FROM campaign_unsubscribes WHERE email = $1
            """, email.lower())

            return bool(unsubbed)

    async def send_initial_email(
        self,
        target_id: str,
        attach_pdf: bool = False,
        dry_run: bool = False
    ) -> Dict:
        """Send initial report email to a target"""

        async with self.pool.acquire() as conn:
            # Get target with report data
            target = await conn.fetchrow("""
                SELECT ct.*, gr.pdf_path, gr.signed_url, gr.stats as report_stats
                FROM campaign_targets ct
                LEFT JOIN generated_reports gr ON ct.report_id = gr.id
                WHERE ct.id = $1
            """, uuid.UUID(target_id))

            if not target:
                return {"error": "Target not found", "target_id": target_id}

            if not target['report_id']:
                return {"error": "No report generated", "target_id": target_id}

            # Check suppression
            if await self.is_suppressed(target['email']):
                await conn.execute("""
                    UPDATE campaign_targets SET status = 'unsubscribed', updated_at = NOW()
                    WHERE id = $1
                """, uuid.UUID(target_id))
                return {"error": "Email suppressed", "target_id": target_id}

            # Parse stats
            stats = json.loads(target['stats']) if target['stats'] else {}
            report_stats = json.loads(target['report_stats']) if target['report_stats'] else stats

            # Generate URLs
            unsubscribe_url = generate_unsubscribe_url(target['email'])
            report_url = target['signed_url']

            # Select subject variant
            variant = target['subject_variant'] or 'A'
            subject = SUBJECT_VARIANTS.get(variant, SUBJECT_VARIANTS['A']).format(
                company=target['company_name']
            )

            # Generate email content
            missed_count = stats.get("missed_opportunities_count", report_stats.get("missed_opportunities_count", 0))
            html_body = generate_email_html(
                company_name=target['company_name'],
                stats=report_stats,
                missed_count=missed_count,
                report_url=report_url,
                checkout_url=CHECKOUT_URL,
                unsubscribe_url=unsubscribe_url
            )
            text_body = generate_email_text(
                company_name=target['company_name'],
                stats=report_stats,
                missed_count=missed_count,
                report_url=report_url,
                checkout_url=CHECKOUT_URL,
                unsubscribe_url=unsubscribe_url
            )

            if dry_run:
                return {
                    "dry_run": True,
                    "target_id": target_id,
                    "email": target['email'],
                    "subject": subject,
                    "company": target['company_name'],
                    "attach_pdf": attach_pdf
                }

            # Build Postmark payload
            payload = {
                "From": f"{POSTMARK_FROM_NAME} <{POSTMARK_FROM_EMAIL}>",
                "To": target['email'],
                "ReplyTo": POSTMARK_REPLY_TO,
                "Subject": subject,
                "HtmlBody": html_body,
                "TextBody": text_body,
                "MessageStream": POSTMARK_MESSAGE_STREAM,
                "TrackOpens": True,
                "TrackLinks": "HtmlAndText",
                "Tag": f"report-campaign-{str(target['campaign_id'])[:8]}",
                "Headers": [
                    {"Name": "List-Unsubscribe", "Value": f"<{unsubscribe_url}>"},
                    {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"}
                ],
                "Metadata": {
                    "campaign_id": str(target['campaign_id']),
                    "target_id": target_id,
                    "company_name": target['company_name'],
                    "variant": variant,
                    "sequence_step": "0"
                }
            }

            # Attach PDF if requested
            if attach_pdf and target['pdf_path'] and Path(target['pdf_path']).exists():
                import base64
                with open(target['pdf_path'], 'rb') as f:
                    pdf_content = base64.b64encode(f.read()).decode('utf-8')

                payload["Attachments"] = [{
                    "Name": f"Извештај-{target['company_name'][:30]}.pdf",
                    "Content": pdf_content,
                    "ContentType": "application/pdf"
                }]

            # Send via Postmark
            try:
                response = await self.http_client.post(
                    "https://api.postmarkapp.com/email",
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    postmark_id = data.get("MessageID")

                    # Update target status
                    await conn.execute("""
                        UPDATE campaign_targets
                        SET status = 'sent',
                            sequence_step = 0,
                            initial_sent_at = NOW(),
                            postmark_message_id = $1,
                            pdf_attached = $2,
                            updated_at = NOW(),
                            last_event_at = NOW()
                        WHERE id = $3
                    """, postmark_id, attach_pdf, uuid.UUID(target_id))

                    # Log event
                    await conn.execute("""
                        INSERT INTO outreach_events (
                            campaign_id, target_id, email, event_type, sequence_step,
                            postmark_message_id, payload
                        ) VALUES ($1, $2, $3, 'sent', 0, $4, $5)
                    """,
                        target['campaign_id'], uuid.UUID(target_id), target['email'],
                        postmark_id, json.dumps({"variant": variant, "attached": attach_pdf})
                    )

                    logger.info(f"Sent initial email to {target['email']} (Postmark ID: {postmark_id})")

                    return {
                        "success": True,
                        "target_id": target_id,
                        "email": target['email'],
                        "postmark_id": postmark_id,
                        "company": target['company_name']
                    }
                else:
                    error = response.text
                    logger.error(f"Postmark error for {target['email']}: {error}")

                    await conn.execute("""
                        UPDATE campaign_targets SET status = 'failed', updated_at = NOW()
                        WHERE id = $1
                    """, uuid.UUID(target_id))

                    return {"error": error, "target_id": target_id}

            except Exception as e:
                logger.error(f"Send error for {target['email']}: {e}")
                return {"error": str(e), "target_id": target_id}

    async def send_followup(
        self,
        target_id: str,
        followup_number: int,  # 1, 2, 3, or 4
        dry_run: bool = False
    ) -> Dict:
        """Send follow-up email"""

        async with self.pool.acquire() as conn:
            target = await conn.fetchrow("""
                SELECT * FROM campaign_targets WHERE id = $1
            """, uuid.UUID(target_id))

            if not target:
                return {"error": "Target not found", "target_id": target_id}

            # Check suppression
            if await self.is_suppressed(target['email']):
                return {"error": "Email suppressed", "target_id": target_id}

            # Generate URLs
            unsubscribe_url = generate_unsubscribe_url(target['email'])

            # Select template based on followup number
            if followup_number == 1:
                subject = FOLLOWUP_1_SUBJECT.format(company=target['company_name'])
                html_body = generate_followup_1_html(
                    target['company_name'], CHECKOUT_URL, unsubscribe_url
                )
            elif followup_number == 2:
                subject = FOLLOWUP_2_SUBJECT.format(company=target['company_name'])
                html_body = generate_followup_2_html(
                    target['company_name'], CHECKOUT_URL, unsubscribe_url
                )
            elif followup_number == 3:
                subject = FOLLOWUP_3_SUBJECT.format(company=target['company_name'])
                html_body = generate_followup_3_html(
                    target['company_name'], CHECKOUT_URL, unsubscribe_url
                )
            else:
                subject = FOLLOWUP_4_SUBJECT.format(company=target['company_name'])
                html_body = generate_followup_4_html(
                    target['company_name'], CHECKOUT_URL, unsubscribe_url
                )

            if dry_run:
                return {
                    "dry_run": True,
                    "target_id": target_id,
                    "email": target['email'],
                    "subject": subject,
                    "followup": followup_number
                }

            payload = {
                "From": f"{POSTMARK_FROM_NAME} <{POSTMARK_FROM_EMAIL}>",
                "To": target['email'],
                "ReplyTo": POSTMARK_REPLY_TO,
                "Subject": subject,
                "HtmlBody": html_body,
                "MessageStream": POSTMARK_MESSAGE_STREAM,
                "TrackOpens": True,
                "TrackLinks": "HtmlAndText",
                "Tag": f"followup-{followup_number}",
                "Headers": [
                    {"Name": "List-Unsubscribe", "Value": f"<{unsubscribe_url}>"}
                ],
                "Metadata": {
                    "campaign_id": str(target['campaign_id']),
                    "target_id": target_id,
                    "sequence_step": str(followup_number)
                }
            }

            try:
                response = await self.http_client.post(
                    "https://api.postmarkapp.com/email",
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    postmark_id = data.get("MessageID")

                    # Update target based on followup number
                    followup_col_map = {
                        1: "followup1_sent_at",
                        2: "followup2_sent_at",
                        3: "followup3_sent_at",
                        4: "followup4_sent_at",
                    }
                    sent_col = followup_col_map.get(followup_number, "followup1_sent_at")
                    await conn.execute(f"""
                        UPDATE campaign_targets
                        SET sequence_step = $1, {sent_col} = NOW(),
                            postmark_message_id = $2, updated_at = NOW()
                        WHERE id = $3
                    """, followup_number, postmark_id, uuid.UUID(target_id))

                    # Log event
                    await conn.execute("""
                        INSERT INTO outreach_events (
                            campaign_id, target_id, email, event_type, sequence_step,
                            postmark_message_id
                        ) VALUES ($1, $2, $3, 'sent', $4, $5)
                    """,
                        target['campaign_id'], uuid.UUID(target_id), target['email'],
                        followup_number, postmark_id
                    )

                    logger.info(f"Sent followup {followup_number} to {target['email']}")
                    return {
                        "success": True,
                        "target_id": target_id,
                        "email": target['email'],
                        "followup": followup_number,
                        "postmark_id": postmark_id
                    }
                else:
                    return {"error": response.text, "target_id": target_id}

            except Exception as e:
                logger.error(f"Followup error for {target['email']}: {e}")
                return {"error": str(e), "target_id": target_id}

    async def send_campaign_batch(
        self,
        campaign_id: str,
        batch_size: int = 10,
        dry_run: bool = False
    ) -> Dict:
        """Send a batch of emails with throttling and jitter"""
        stats = {
            "sent": 0,
            "failed": 0,
            "skipped_rate_limit": 0,
            "skipped_no_report": 0,
            "results": []
        }

        async with self.pool.acquire() as conn:
            # Get campaign settings
            campaign = await conn.fetchrow("""
                SELECT * FROM report_campaigns WHERE id = $1
            """, uuid.UUID(campaign_id))

            if not campaign:
                return {"error": "Campaign not found"}

            if campaign['status'] != 'active':
                return {"error": f"Campaign status is {campaign['status']}, not active"}

            settings = json.loads(campaign['settings']) if campaign['settings'] else DEFAULT_SETTINGS
            attach_pdf_first_n = settings.get("attach_pdf_first_n", 20)
            min_jitter = settings.get("min_jitter_seconds", 30)
            max_jitter = settings.get("max_jitter_seconds", 180)

            # Count how many have been sent (for PDF attachment logic)
            sent_count = await conn.fetchval("""
                SELECT COUNT(*) FROM campaign_targets
                WHERE campaign_id = $1 AND status NOT IN ('pending', 'report_generated')
            """, uuid.UUID(campaign_id))

            # Get pending targets with reports
            targets = await conn.fetch("""
                SELECT id FROM campaign_targets
                WHERE campaign_id = $1
                  AND status = 'report_generated'
                  AND report_id IS NOT NULL
                ORDER BY created_at
                LIMIT $2
            """, uuid.UUID(campaign_id), batch_size)

        for i, target in enumerate(targets):
            # Check rate limits
            can_send, msg = await self.can_send(campaign_id)
            if not can_send and not dry_run:
                stats["skipped_rate_limit"] += batch_size - i
                logger.info(f"Rate limit reached: {msg}")
                break

            # Determine if PDF should be attached
            attach_pdf = (sent_count + i) < attach_pdf_first_n

            # Send email
            result = await self.send_initial_email(
                target_id=str(target['id']),
                attach_pdf=attach_pdf,
                dry_run=dry_run
            )

            if result.get("success") or result.get("dry_run"):
                stats["sent"] += 1
            else:
                stats["failed"] += 1

            stats["results"].append(result)

            # Add jitter between sends (not in dry run)
            if not dry_run and i < len(targets) - 1:
                jitter = random.uniform(min_jitter, max_jitter)
                logger.debug(f"Waiting {jitter:.1f}s before next send...")
                await asyncio.sleep(jitter)

        # Update campaign stats
        if not dry_run:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE report_campaigns
                    SET emails_sent = emails_sent + $1, updated_at = NOW()
                    WHERE id = $2
                """, stats["sent"], uuid.UUID(campaign_id))

        return stats

    async def send_followups(
        self,
        campaign_id: str,
        dry_run: bool = False
    ) -> Dict:
        """Send follow-up emails to eligible targets (up to 4 follow-ups)"""
        stats = {
            "followup1_sent": 0, "followup2_sent": 0,
            "followup3_sent": 0, "followup4_sent": 0,
            "skipped": 0, "results": []
        }

        async with self.pool.acquire() as conn:
            # Get campaign settings
            campaign = await conn.fetchrow("""
                SELECT settings FROM report_campaigns WHERE id = $1 AND status = 'active'
            """, uuid.UUID(campaign_id))

            if not campaign:
                return {"error": "Campaign not active"}

            settings = json.loads(campaign['settings']) if campaign['settings'] else DEFAULT_SETTINGS

            # Define follow-up schedule: (step, current_sequence_step, delay_days, sent_at_col)
            followup_schedule = [
                (1, 0, settings.get("followup_1_days", 3), "initial_sent_at"),
                (2, 1, settings.get("followup_2_days", 7), "followup1_sent_at"),
                (3, 2, settings.get("followup_3_days", 14), "followup2_sent_at"),
                (4, 3, settings.get("followup_4_days", 21), "followup3_sent_at"),
            ]

            all_targets = {}
            for fnum, cur_step, delay_days, sent_col in followup_schedule:
                cutoff = datetime.utcnow() - timedelta(days=delay_days)
                targets = await conn.fetch(f"""
                    SELECT id FROM campaign_targets
                    WHERE campaign_id = $1
                      AND sequence_step = $2
                      AND status IN ('sent', 'delivered', 'opened', 'clicked')
                      AND {sent_col} <= $3
                    LIMIT 50
                """, uuid.UUID(campaign_id), cur_step, cutoff)
                all_targets[fnum] = targets

        # Send all follow-ups in order
        for fnum, targets in all_targets.items():
            stat_key = f"followup{fnum}_sent"
            for target in targets:
                can_send, _ = await self.can_send(campaign_id)
                if not can_send and not dry_run:
                    stats["skipped"] += 1
                    continue

                result = await self.send_followup(str(target['id']), fnum, dry_run)
                if result.get("success") or result.get("dry_run"):
                    stats[stat_key] += 1
                stats["results"].append(result)

                if not dry_run:
                    await asyncio.sleep(random.uniform(30, 120))

        return stats


# ============================================================================
# WEBHOOK HANDLER
# ============================================================================

async def handle_postmark_webhook(pool: asyncpg.Pool, event_data: Dict) -> Dict:
    """Handle Postmark webhook events"""
    record_type = event_data.get("RecordType", "").lower()
    message_id = event_data.get("MessageID")
    email = event_data.get("Recipient", event_data.get("Email", "")).lower()
    metadata = event_data.get("Metadata", {})

    target_id = metadata.get("target_id")
    campaign_id = metadata.get("campaign_id")

    event_type_map = {
        "delivery": "delivered",
        "open": "opened",
        "click": "clicked",
        "bounce": "bounced",
        "spamcomplaint": "complained"
    }

    event_type = event_type_map.get(record_type)
    if not event_type:
        return {"ignored": True, "reason": f"Unknown event type: {record_type}"}

    async with pool.acquire() as conn:
        # Log event
        await conn.execute("""
            INSERT INTO outreach_events (
                campaign_id, target_id, email, event_type,
                postmark_message_id, payload
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """,
            uuid.UUID(campaign_id) if campaign_id else None,
            uuid.UUID(target_id) if target_id else None,
            email,
            event_type,
            message_id,
            json.dumps(event_data)
        )

        # Update target status for significant events
        if target_id and event_type in ["delivered", "opened", "clicked"]:
            await conn.execute("""
                UPDATE campaign_targets
                SET status = $1, last_event_at = NOW(), updated_at = NOW()
                WHERE id = $2 AND status NOT IN ('replied', 'converted', 'unsubscribed')
            """, event_type, uuid.UUID(target_id))

        # Handle bounces and complaints - add to suppression
        if event_type in ["bounced", "complained"]:
            bounce_type = event_data.get("Type", "")

            # Add to suppression list
            await conn.execute("""
                INSERT INTO suppression_list (email, reason, source, notes)
                VALUES ($1, $2, 'postmark', $3)
                ON CONFLICT (email) DO NOTHING
            """, email, "bounce" if event_type == "bounced" else "complaint", bounce_type)

            # Add to campaign unsubscribes
            await conn.execute("""
                INSERT INTO campaign_unsubscribes (email, source, campaign_id, token, reason)
                VALUES ($1, 'postmark_bounce', $2, $3, $4)
                ON CONFLICT (email) DO NOTHING
            """,
                email,
                uuid.UUID(campaign_id) if campaign_id else None,
                generate_unsubscribe_token(email),
                f"Postmark {event_type}: {bounce_type}"
            )

            # Update target
            if target_id:
                await conn.execute("""
                    UPDATE campaign_targets SET status = $1, updated_at = NOW()
                    WHERE id = $2
                """, event_type, uuid.UUID(target_id))

            logger.info(f"Added {email} to suppression: {event_type}")

        # Update campaign stats
        if campaign_id:
            stat_col = {
                "opened": "emails_opened",
                "clicked": "emails_clicked"
            }.get(event_type)

            if stat_col:
                await conn.execute(f"""
                    UPDATE report_campaigns
                    SET {stat_col} = {stat_col} + 1, updated_at = NOW()
                    WHERE id = $1
                """, uuid.UUID(campaign_id))

    return {"processed": True, "event_type": event_type, "email": email}


# ============================================================================
# UNSUBSCRIBE HANDLER
# ============================================================================

async def handle_unsubscribe(
    pool: asyncpg.Pool,
    email: str,
    token: str,
    source: str = "email_link",
    campaign_id: Optional[str] = None
) -> Dict:
    """Handle unsubscribe request"""
    email = email.lower().strip()

    # Verify token
    if not verify_unsubscribe_token(email, token):
        return {"success": False, "error": "Невалиден токен"}

    async with pool.acquire() as conn:
        # Add to campaign unsubscribes
        await conn.execute("""
            INSERT INTO campaign_unsubscribes (email, source, campaign_id, token)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (email) DO UPDATE SET updated_at = NOW()
        """,
            email, source,
            uuid.UUID(campaign_id) if campaign_id else None,
            token
        )

        # Add to suppression list
        await conn.execute("""
            INSERT INTO suppression_list (email, reason, source)
            VALUES ($1, 'unsubscribed', 'user_request')
            ON CONFLICT (email) DO NOTHING
        """, email)

        # Update any campaign targets
        await conn.execute("""
            UPDATE campaign_targets SET status = 'unsubscribed', updated_at = NOW()
            WHERE email = $1
        """, email)

    logger.info(f"Unsubscribed: {email} via {source}")
    return {"success": True, "message": "Успешно се одјавивте"}

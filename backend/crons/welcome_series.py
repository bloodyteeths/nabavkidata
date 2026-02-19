#!/usr/bin/env python3
"""
Welcome Email Series - 6-Email Onboarding Sequence

Sends educational emails to new users over 10 days:
- Email 1: Welcome + Quick Start (immediate after verification)
- Email 2: AI Chat Feature (Day 1)
- Email 3: Alerts Setup (Day 3)
- Email 4: Success Story (Day 5)
- Email 5: Price History & Winners (Day 7)
- Email 6: Upgrade CTA (Day 10)

Stops when:
- User upgrades to paid subscription
- User unsubscribes
- Email bounces
- Series completed

Run: python3 crons/welcome_series.py
Cron: Every hour
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import httpx
import asyncpg
from dotenv import load_dotenv
load_dotenv()


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL')
POSTMARK_API_TOKEN = os.getenv('POSTMARK_API_TOKEN', '33d10a6c-0906-42c6-ab14-441ad12b9e2a')
POSTMARK_FROM_EMAIL = 'hello@nabavkidata.com'
POSTMARK_FROM_NAME = 'Тамара од НабавкиДата'
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://nabavkidata.com')

# Email schedule (step -> days after registration)
EMAIL_SCHEDULE = {
    1: 0,    # Immediate (after email verification)
    2: 1,    # Day 1
    3: 3,    # Day 3
    4: 5,    # Day 5
    5: 7,    # Day 7
    6: 10,   # Day 10
}

# =============================================================================
# EMAIL TEMPLATES (Macedonian, Hormozi-style)
# =============================================================================

def get_email_template(step: int, user_name: str, user_email: str) -> Dict:
    """Get email template for given step"""

    # Use first name or fallback
    first_name = user_name.split()[0] if user_name else "Корисниче"

    templates = {
        # =====================================================================
        # EMAIL 1: Welcome + Quick Start
        # =====================================================================
        1: {
            "subject": f"Добредојде, {first_name}!",
            "html": f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Здраво {first_name},</p>

        <p>Добредојде во НабавкиДата!</p>

        <p>Сега имаш пристап до <strong>15,000+ тендери</strong> и AI алатки што ќе ти заштедат часови работа.</p>

        <p>&nbsp;</p>

        <p><strong>Еве што можеш да направиш веднаш:</strong></p>

        <p style="background:#f0f9ff; padding:15px; border-radius:8px; border-left:4px solid #2563eb;">
            <strong>Пробај го AI чатот</strong><br>
            Прашај нешто како: "тендери за IT опрема во последните 30 дена"<br><br>
            <a href="{FRONTEND_URL}/chat" style="background:#2563eb; color:white; padding:10px 20px; border-radius:5px; text-decoration:none; display:inline-block;">Оди на AI чат</a>
        </p>

        <p>&nbsp;</p>

        <p>Во следните денови ќе ти покажам како да го искористиш максимумот од платформата.</p>

        <p>Ако имаш прашања - само одговори на овој мејл.</p>

        <p>- Тамара</p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

        <p style="font-size:12px; color:#666666;">
            TAMSAR INC | hello@nabavkidata.com<br>
            <a href="{FRONTEND_URL}/unsubscribe?email={user_email}" style="color:#666666;">Отпиши се</a>
        </p>

    </div>
</body>
</html>""",
            "text": f"""Здраво {first_name},

Добредојде во НабавкиДата!

Сега имаш пристап до 15,000+ тендери и AI алатки што ќе ти заштедат часови работа.

Еве што можеш да направиш веднаш:

Пробај го AI чатот - прашај нешто како: "тендери за IT опрема во последните 30 дена"
{FRONTEND_URL}/chat

Во следните денови ќе ти покажам како да го искористиш максимумот од платформата.

Ако имаш прашања - само одговори на овој мејл.

- Тамара

---
Отпиши се: {FRONTEND_URL}/unsubscribe?email={user_email}"""
        },

        # =====================================================================
        # EMAIL 2: AI Chat Feature Deep Dive
        # =====================================================================
        2: {
            "subject": "AI што чита тендери за тебе",
            "html": f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Здраво {first_name},</p>

        <p>Знаеш ли колку време се троши на читање тендерска документација?</p>

        <p>Нашиот AI може да ти заштеди <strong>3-4 часа дневно</strong>.</p>

        <p>&nbsp;</p>

        <p><strong>Еве 5 примери што можеш да прашаш:</strong></p>

        <ol style="padding-left:20px;">
            <li>"Тендери за медицинска опрема над 1 милион денари"</li>
            <li>"Кој најчесто добива тендери за градежни работи?"</li>
            <li>"Колку чини лаптоп во јавни набавки?"</li>
            <li>"Активни тендери од Министерство за здравство"</li>
            <li>"Споредба: А1 vs Телеком на IT тендери"</li>
        </ol>

        <p>&nbsp;</p>

        <p style="background:#fef3c7; padding:15px; border-radius:8px; border-left:4px solid #f59e0b;">
            <strong>Тајна:</strong> AI-от пребарува низ PDF документи и извлекува информации што би ти требале часови да ги најдеш рачно.
        </p>

        <p>&nbsp;</p>

        <p><a href="{FRONTEND_URL}/chat" style="background:#2563eb; color:white; padding:12px 24px; border-radius:5px; text-decoration:none; display:inline-block;">Пробај го AI чатот</a></p>

        <p>- Тамара</p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

        <p style="font-size:12px; color:#666666;">
            TAMSAR INC | hello@nabavkidata.com<br>
            <a href="{FRONTEND_URL}/unsubscribe?email={user_email}" style="color:#666666;">Отпиши се</a>
        </p>

    </div>
</body>
</html>""",
            "text": f"""Здраво {first_name},

Знаеш ли колку време се троши на читање тендерска документација?

Нашиот AI може да ти заштеди 3-4 часа дневно.

Еве 5 примери што можеш да прашаш:

1. "Тендери за медицинска опрема над 1 милион денари"
2. "Кој најчесто добива тендери за градежни работи?"
3. "Колку чини лаптоп во јавни набавки?"
4. "Активни тендери од Министерство за здравство"
5. "Споредба: А1 vs Телеком на IT тендери"

Тајна: AI-от пребарува низ PDF документи и извлекува информации што би ти требале часови да ги најдеш рачно.

Пробај го AI чатот: {FRONTEND_URL}/chat

- Тамара

---
Отпиши се: {FRONTEND_URL}/unsubscribe?email={user_email}"""
        },

        # =====================================================================
        # EMAIL 3: Alerts Setup
        # =====================================================================
        3: {
            "subject": "Никогаш повеќе да не пропуштиш тендер",
            "html": f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Здраво {first_name},</p>

        <p>Колку тендери пропуштивте минатата година затоа што не знаевте дека постојат?</p>

        <p>Со <strong>известувањата</strong> ќе добиваш мејл штом излезе тендер од твојата дејност.</p>

        <p>&nbsp;</p>

        <p><strong>Како да поставиш известување:</strong></p>

        <ol style="padding-left:20px;">
            <li>Оди на <a href="{FRONTEND_URL}/alerts">Известувања</a></li>
            <li>Кликни "Ново известување"</li>
            <li>Избери категорија (пр. IT опрема, градежни работи)</li>
            <li>Избери минимална вредност (опционално)</li>
            <li>Зачувај - готово!</li>
        </ol>

        <p>&nbsp;</p>

        <p style="background:#ecfdf5; padding:15px; border-radius:8px; border-left:4px solid #10b981;">
            <strong>Резултат:</strong> Добиваш мејл во рок од неколку часа откако ќе се објави нов тендер. Никогаш повеќе да не пропуштиш прилика.
        </p>

        <p>&nbsp;</p>

        <p><a href="{FRONTEND_URL}/alerts" style="background:#2563eb; color:white; padding:12px 24px; border-radius:5px; text-decoration:none; display:inline-block;">Постави известување</a></p>

        <p>- Тамара</p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

        <p style="font-size:12px; color:#666666;">
            TAMSAR INC | hello@nabavkidata.com<br>
            <a href="{FRONTEND_URL}/unsubscribe?email={user_email}" style="color:#666666;">Отпиши се</a>
        </p>

    </div>
</body>
</html>""",
            "text": f"""Здраво {first_name},

Колку тендери пропуштивте минатата година затоа што не знаевте дека постојат?

Со известувањата ќе добиваш мејл штом излезе тендер од твојата дејност.

Како да поставиш известување:

1. Оди на Известувања ({FRONTEND_URL}/alerts)
2. Кликни "Ново известување"
3. Избери категорија (пр. IT опрема, градежни работи)
4. Избери минимална вредност (опционално)
5. Зачувај - готово!

Резултат: Добиваш мејл во рок од неколку часа откако ќе се објави нов тендер.

Постави известување: {FRONTEND_URL}/alerts

- Тамара

---
Отпиши се: {FRONTEND_URL}/unsubscribe?email={user_email}"""
        },

        # =====================================================================
        # EMAIL 4: Success Story / Social Proof
        # =====================================================================
        4: {
            "subject": "Од 3 дена на 3 часа",
            "html": f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Здраво {first_name},</p>

        <p>Сакам да ти кажам една приказна.</p>

        <p>Пред неколку месеци ми се јави сопственик на фирма за медицинска опрема.</p>

        <p>Секој ден проверувал на е-Набавки дали има нов тендер. Читал PDF-ови со часови. Пресметувал цени на слепо.</p>

        <p>Му покажав како со НабавкиДата:</p>

        <ul style="padding-left:20px;">
            <li>Добива известување штом излезе тендер</li>
            <li>AI го чита PDF-от за 10 секунди</li>
            <li>Гледа историски цени од претходни тендери</li>
            <li>Знае кој најчесто добива</li>
        </ul>

        <p>По една недела ми рече:</p>

        <p style="background:#f0f9ff; padding:15px; border-radius:8px; border-left:4px solid #2563eb; font-style:italic;">
            "Тамара, за 3 часа подготвив понуда за која претходно ми требаа 3 дена."
        </p>

        <p>&nbsp;</p>

        <p><strong>4,152 компании</strong> во Македонија веќе го користат НабавкиДата.</p>

        <p>Ти си една од нив. Искористи го!</p>

        <p><a href="{FRONTEND_URL}/dashboard" style="background:#2563eb; color:white; padding:12px 24px; border-radius:5px; text-decoration:none; display:inline-block;">Оди на Dashboard</a></p>

        <p>- Тамара</p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

        <p style="font-size:12px; color:#666666;">
            TAMSAR INC | hello@nabavkidata.com<br>
            <a href="{FRONTEND_URL}/unsubscribe?email={user_email}" style="color:#666666;">Отпиши се</a>
        </p>

    </div>
</body>
</html>""",
            "text": f"""Здраво {first_name},

Сакам да ти кажам една приказна.

Пред неколку месеци ми се јави сопственик на фирма за медицинска опрема.

Секој ден проверувал на е-Набавки дали има нов тендер. Читал PDF-ови со часови. Пресметувал цени на слепо.

Му покажав како со НабавкиДата:
- Добива известување штом излезе тендер
- AI го чита PDF-от за 10 секунди
- Гледа историски цени од претходни тендери
- Знае кој најчесто добива

По една недела ми рече:
"Тамара, за 3 часа подготвив понуда за која претходно ми требаа 3 дена."

4,152 компании во Македонија веќе го користат НабавкиДата.

Ти си една од нив. Искористи го!

{FRONTEND_URL}/dashboard

- Тамара

---
Отпиши се: {FRONTEND_URL}/unsubscribe?email={user_email}"""
        },

        # =====================================================================
        # EMAIL 5: Price History & Winner Analysis
        # =====================================================================
        5: {
            "subject": "Како да понудиш точна цена",
            "html": f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Здраво {first_name},</p>

        <p>Еден од најголемите проблеми кога правиш понуда: <strong>која цена да ја ставиш?</strong></p>

        <p>Премногу ниска = губиш пари. Премногу висока = губиш тендер.</p>

        <p>&nbsp;</p>

        <p><strong>Решение: Историски цени</strong></p>

        <p>Во НабавкиДата можеш да видиш:</p>

        <ul style="padding-left:20px;">
            <li>Колку чинеле истите производи во претходни тендери</li>
            <li>Кој добил и со која понуда</li>
            <li>Просечни цени по институции</li>
            <li>Трендови на цени во последните години</li>
        </ul>

        <p>&nbsp;</p>

        <p><strong>Пробај:</strong> Прашај го AI-от "колку чинат лаптопи во јавни набавки" или "просечна цена за тонер"</p>

        <p style="background:#fef3c7; padding:15px; border-radius:8px; border-left:4px solid #f59e0b;">
            <strong>Pro tip:</strong> Погледни ги победниците на слични тендери. Научи од нивните понуди.
        </p>

        <p>&nbsp;</p>

        <p><a href="{FRONTEND_URL}/chat" style="background:#2563eb; color:white; padding:12px 24px; border-radius:5px; text-decoration:none; display:inline-block;">Провери историски цени</a></p>

        <p>- Тамара</p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

        <p style="font-size:12px; color:#666666;">
            TAMSAR INC | hello@nabavkidata.com<br>
            <a href="{FRONTEND_URL}/unsubscribe?email={user_email}" style="color:#666666;">Отпиши се</a>
        </p>

    </div>
</body>
</html>""",
            "text": f"""Здраво {first_name},

Еден од најголемите проблеми кога правиш понуда: која цена да ја ставиш?

Премногу ниска = губиш пари. Премногу висока = губиш тендер.

Решение: Историски цени

Во НабавкиДата можеш да видиш:
- Колку чинеле истите производи во претходни тендери
- Кој добил и со која понуда
- Просечни цени по институции
- Трендови на цени во последните години

Пробај: Прашај го AI-от "колку чинат лаптопи во јавни набавки" или "просечна цена за тонер"

Pro tip: Погледни ги победниците на слични тендери. Научи од нивните понуди.

Провери историски цени: {FRONTEND_URL}/chat

- Тамара

---
Отпиши се: {FRONTEND_URL}/unsubscribe?email={user_email}"""
        },

        # =====================================================================
        # EMAIL 6: Upgrade CTA (Final)
        # =====================================================================
        6: {
            "subject": f"{first_name}, време е за одлука",
            "html": f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Здраво {first_name},</p>

        <p>Минаа 10 дена откако се регистрира.</p>

        <p>Сега веќе знаеш што нуди НабавкиДата:</p>

        <ul style="padding-left:20px;">
            <li>AI што чита тендери за тебе</li>
            <li>Известувања за нови тендери</li>
            <li>Историски цени за точни понуди</li>
            <li>Анализа на победници</li>
        </ul>

        <p>&nbsp;</p>

        <p>На бесплатната верзија имаш ограничен број AI прашања дневно.</p>

        <p>Со <strong>Pro планот</strong> добиваш:</p>

        <ul style="padding-left:20px;">
            <li>Неограничени AI прашања</li>
            <li>Неограничени известувања</li>
            <li>Извоз на податоци</li>
            <li>Приоритетна поддршка</li>
        </ul>

        <p>&nbsp;</p>

        <p style="background:#fef2f2; padding:15px; border-radius:8px; border-left:4px solid #ef4444;">
            <strong>Размисли:</strong> Секој пропуштен тендер е изгубена прилика. Секој лошо ценет тендер е загуба. Колку вреди да ги избегнеш тие грешки?
        </p>

        <p>&nbsp;</p>

        <p><a href="{FRONTEND_URL}/billing" style="background:#2563eb; color:white; padding:12px 24px; border-radius:5px; text-decoration:none; display:inline-block;">Погледни ги плановите</a></p>

        <p>Или ако имаш прашања - само одговори на овој мејл.</p>

        <p>- Тамара</p>

        <p>&nbsp;</p>

        <p><em>ПС: Ова е последниот мејл од оваа серија. Понатаму ќе добиваш само известувања за тендери (ако ги имаш поставено).</em></p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

        <p style="font-size:12px; color:#666666;">
            TAMSAR INC | hello@nabavkidata.com<br>
            <a href="{FRONTEND_URL}/unsubscribe?email={user_email}" style="color:#666666;">Отпиши се</a>
        </p>

    </div>
</body>
</html>""",
            "text": f"""Здраво {first_name},

Минаа 10 дена откако се регистрира.

Сега веќе знаеш што нуди НабавкиДата:
- AI што чита тендери за тебе
- Известувања за нови тендери
- Историски цени за точни понуди
- Анализа на победници

На бесплатната верзија имаш ограничен број AI прашања дневно.

Со Pro планот добиваш:
- Неограничени AI прашања
- Неограничени известувања
- Извоз на податоци
- Приоритетна поддршка

Размисли: Секој пропуштен тендер е изгубена прилика. Секој лошо ценет тендер е загуба. Колку вреди да ги избегнеш тие грешки?

Погледни ги плановите: {FRONTEND_URL}/billing

Или ако имаш прашања - само одговори на овој мејл.

- Тамара

ПС: Ова е последниот мејл од оваа серија.

---
Отпиши се: {FRONTEND_URL}/unsubscribe?email={user_email}"""
        },
    }

    return templates.get(step, templates[1])


# =============================================================================
# EMAIL SENDING
# =============================================================================

async def send_welcome_email(client: httpx.AsyncClient, email: str, step: int, user_name: str) -> dict:
    """Send welcome series email via Postmark"""
    template = get_email_template(step, user_name, email)

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
            "Tag": f"welcome-series-{step}"
        },
        timeout=30.0
    )

    if response.status_code == 200:
        return {"success": True, "message_id": response.json().get("MessageID")}
    else:
        return {"success": False, "error": response.text}


# =============================================================================
# MAIN PROCESSING
# =============================================================================

async def process_welcome_series():
    """Process all pending welcome series emails"""
    logger.info("=" * 60)
    logger.info("WELCOME SERIES PROCESSOR")
    logger.info(f"Time: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get users due for welcome email
        users_due = await conn.fetch("""
            SELECT
                ws.id as welcome_id,
                ws.user_id,
                ws.current_step,
                ws.next_email_at,
                u.email,
                u.full_name,
                u.subscription_tier,
                u.email_verified,
                u.created_at as user_created_at
            FROM welcome_series ws
            JOIN users u ON ws.user_id = u.user_id
            WHERE ws.completed_at IS NULL
              AND ws.stopped_reason IS NULL
              AND ws.next_email_at <= NOW()
              AND u.email_verified = true
              AND (u.subscription_tier IS NULL OR u.subscription_tier = 'free')
            ORDER BY ws.next_email_at ASC
            LIMIT 100
        """)

        logger.info(f"Found {len(users_due)} users due for welcome email")

        if not users_due:
            logger.info("No users due for welcome emails")
            return

        sent = 0
        errors = 0

        async with httpx.AsyncClient() as client:
            for user in users_due:
                next_step = user['current_step'] + 1

                if next_step > 6:
                    # Series completed
                    await conn.execute("""
                        UPDATE welcome_series
                        SET completed_at = NOW(),
                            stopped_reason = 'completed',
                            updated_at = NOW()
                        WHERE id = $1
                    """, user['welcome_id'])
                    logger.info(f"  Completed series for {user['email']}")
                    continue

                logger.info(f"  [{next_step}/6] {user['email']}")

                # Send email
                result = await send_welcome_email(
                    client,
                    user['email'],
                    next_step,
                    user['full_name'] or ""
                )

                if result['success']:
                    # Calculate next email time
                    if next_step < 6:
                        days_until_next = EMAIL_SCHEDULE.get(next_step + 1, 0) - EMAIL_SCHEDULE.get(next_step, 0)
                        next_email_at = datetime.utcnow() + timedelta(days=days_until_next)
                    else:
                        next_email_at = None

                    # Update progress
                    sent_col = f"email_{next_step}_sent_at"
                    await conn.execute(f"""
                        UPDATE welcome_series
                        SET current_step = $1,
                            last_email_at = NOW(),
                            next_email_at = $2,
                            {sent_col} = NOW(),
                            updated_at = NOW()
                        WHERE id = $3
                    """, next_step, next_email_at, user['welcome_id'])

                    sent += 1
                    logger.info(f"    ✓ Sent (step {next_step})")
                else:
                    errors += 1
                    logger.error(f"    ✗ Error: {result.get('error', 'Unknown')[:50]}")

                    # Check if bounced
                    if 'bounce' in result.get('error', '').lower() or 'invalid' in result.get('error', '').lower():
                        await conn.execute("""
                            UPDATE welcome_series
                            SET completed_at = NOW(),
                                stopped_reason = 'bounced',
                                updated_at = NOW()
                            WHERE id = $1
                        """, user['welcome_id'])

                # Small delay between emails
                await asyncio.sleep(0.5)

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"COMPLETE: {sent} sent, {errors} errors")
        logger.info("=" * 60)

    finally:
        await conn.close()


async def initialize_new_users():
    """Initialize welcome series for verified users who don't have one yet"""
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Find verified users without welcome series
        new_users = await conn.fetch("""
            SELECT u.user_id, u.email, u.full_name, u.created_at
            FROM users u
            LEFT JOIN welcome_series ws ON u.user_id = ws.user_id
            WHERE u.email_verified = true
              AND ws.id IS NULL
              AND u.created_at > NOW() - INTERVAL '30 days'
            ORDER BY u.created_at DESC
        """)

        if new_users:
            logger.info(f"Initializing welcome series for {len(new_users)} new users")

            for user in new_users:
                await conn.execute("""
                    INSERT INTO welcome_series (user_id, current_step, next_email_at)
                    VALUES ($1, 0, NOW())
                    ON CONFLICT (user_id) DO NOTHING
                """, user['user_id'])
                logger.info(f"  + {user['email']}")

    finally:
        await conn.close()


async def main():
    """Main entry point"""
    # First, initialize any new verified users
    await initialize_new_users()

    # Then process pending welcome emails
    await process_welcome_series()


if __name__ == "__main__":
    asyncio.run(main())

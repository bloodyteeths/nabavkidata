#!/usr/bin/env python3
"""
Cold Outreach Drip - 5-Step Email Sequence for mk_companies leads.

Two lead types:
  Segment A = Tender-active companies (already bid on public tenders)
  Segment B = Growth-potential companies (general business, could benefit from tenders)

5-step drip per type with different templates and timing:
  Step 1: Day 0  — Introduction / free report
  Step 2: Day 3  — Missed opportunities / tender examples
  Step 3: Day 7  — Competitor analysis / social proof
  Step 4: Day 14 — Real-time alert / educational
  Step 5: Day 21 — Soft close

Run: python3 crons/cold_outreach_drip.py
     python3 crons/cold_outreach_drip.py --dry-run
     python3 crons/cold_outreach_drip.py --limit 50 --segment A
Cron: */30 * * * * cd /home/ubuntu/nabavkidata/backend && python3 crons/cold_outreach_drip.py >> /var/log/nabavkidata/cold_outreach.log 2>&1
"""

import os
import sys
import asyncio
import random
import hashlib
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, Optional

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
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)
POSTMARK_API_TOKEN = os.getenv('POSTMARK_API_TOKEN', '33d10a6c-0906-42c6-ab14-441ad12b9e2a')
POSTMARK_FROM_EMAIL = 'hello@nabavkidata.com'
POSTMARK_FROM_NAME = 'Тамара од НабавкиДата'
POSTMARK_MESSAGE_STREAM = 'broadcast'
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://nabavkidata.com')
UNSUBSCRIBE_SECRET = os.getenv('UNSUBSCRIBE_SECRET', 'nabavki-unsub-secret-2025')

DAILY_LIMIT = int(os.getenv('COLD_OUTREACH_DAILY_LIMIT', '3000'))
HOURLY_LIMIT = int(os.getenv('COLD_OUTREACH_HOURLY_LIMIT', '200'))
MIN_JITTER = 5    # seconds between sends
MAX_JITTER = 15


# =============================================================================
# UNSUBSCRIBE
# =============================================================================

def generate_unsubscribe_url(email: str) -> str:
    token = hashlib.sha256(f"{email}:{UNSUBSCRIBE_SECRET}".encode()).hexdigest()[:32]
    return f"{FRONTEND_URL}/unsubscribe?e={email}&t={token}"


# =============================================================================
# EMAIL TEMPLATES
# =============================================================================

EMAIL_FOOTER = """
        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">
        <p style="font-size:12px; color:#666666;">
            TAMSAR INC | hello@nabavkidata.com<br>
            <a href="{unsub_url}" style="color:#666666;">Одјава од маркетинг пораки</a> |
            Одговорете СТОП за одјава
        </p>
"""

TEXT_FOOTER = """
---
Одговорете СТОП за одјава или посетете: {unsub_url}
"""


def get_template_a(step: int, company: str, unsub_url: str) -> Dict:
    """Templates for Segment A — Tender-Active Companies."""
    templates = {
        1: {
            "subject": f"{company}: тендерски извештај (бесплатен)",
            "html": f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000; background:#fff;">
    <div style="max-width:600px; margin:0 auto;">
        <p>Почитувани,</p>

        <p>Забележавме дека <strong>{company}</strong> учествува на јавни набавки во Македонија.</p>

        <p>Генериравме <strong>бесплатен тендерски извештај</strong> за вашата компанија — вклучува:</p>

        <ul>
            <li>Број на учества и победи во последните 12 месеци</li>
            <li>Вашите топ категории (CPV кодови)</li>
            <li>Конкуренти кои најчесто побеждуваат во истите тендери</li>
            <li>Пропуштени тендери во последните 90 дена</li>
        </ul>

        <p><a href="{FRONTEND_URL}/signup?ref=cold-a1" style="display:inline-block; background:#1e3a5f; color:white; padding:12px 24px; border-radius:5px; text-decoration:none;">Преземи бесплатен извештај</a></p>

        <p>Извештајот е генериран од јавно достапни податоци — целосно бесплатно, без обврска.</p>

        <p>Поздрав,<br>Тамара<br>NabavkiData</p>
        {EMAIL_FOOTER.format(unsub_url=unsub_url)}
    </div>
</body></html>""",
            "text": f"""Почитувани,

Забележавме дека {company} учествува на јавни набавки во Македонија.

Генериравме бесплатен тендерски извештај за вашата компанија — вклучува:
- Број на учества и победи во последните 12 месеци
- Вашите топ категории
- Конкуренти кои побеждуваат во истите тендери
- Пропуштени тендери во последните 90 дена

Преземи бесплатен извештај: {FRONTEND_URL}/signup?ref=cold-a1

Поздрав,
Тамара, NabavkiData
{TEXT_FOOTER.format(unsub_url=unsub_url)}"""
        },

        2: {
            "subject": f"3 тендери што {company} ги пропушти минатиот месец",
            "html": f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000; background:#fff;">
    <div style="max-width:600px; margin:0 auto;">
        <p>Почитувани,</p>

        <p>Во последните 30 дена пронајдовме <strong>тендери релевантни за {company}</strong> каде што не учествувавте.</p>

        <p style="background:#fef3c7; padding:15px; border-radius:8px; border-left:4px solid #f59e0b;">
            Секој пропуштен тендер е изгубена можност. NabavkiData ви испраќа <strong>дневни известувања</strong> за нови тендери во вашите категории — за да не пропуштите повеќе.
        </p>

        <p>Ние ги следиме <strong>сите тендери на е-набавки</strong> — вие само одберете кои категории ве интересираат.</p>

        <p><a href="{FRONTEND_URL}/signup?ref=cold-a2" style="display:inline-block; background:#1e3a5f; color:white; padding:12px 24px; border-radius:5px; text-decoration:none;">Активирај дневни известувања</a></p>

        <p>Поздрав,<br>Тамара</p>
        {EMAIL_FOOTER.format(unsub_url=unsub_url)}
    </div>
</body></html>""",
            "text": f"""Почитувани,

Во последните 30 дена пронајдовме тендери релевантни за {company} каде што не учествувавте.

Секој пропуштен тендер е изгубена можност. NabavkiData ви испраќа дневни известувања за нови тендери во вашите категории.

Активирај дневни известувања: {FRONTEND_URL}/signup?ref=cold-a2

Поздрав,
Тамара
{TEXT_FOOTER.format(unsub_url=unsub_url)}"""
        },

        3: {
            "subject": f"Вашите конкуренти на тендери — дали ги следите?",
            "html": f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000; background:#fff;">
    <div style="max-width:600px; margin:0 auto;">
        <p>Почитувани,</p>

        <p>Дали знаете кои компании најчесто побеждуваат во тендерите каде што <strong>{company}</strong> учествува?</p>

        <p>NabavkiData анализира <strong>15,000+ тендери</strong> и може да ви покаже:</p>

        <ul>
            <li>Кои конкуренти побеждуваат во вашите категории</li>
            <li>Колку често добиваат и со какви цени</li>
            <li>Во кои институции имаат предност</li>
        </ul>

        <p style="background:#f0f9ff; padding:15px; border-radius:8px; border-left:4px solid #2563eb;">
            <strong>Бесплатен пробен период</strong> — целосен пристап до конкурентски анализи 7 дена, без обврска.
        </p>

        <p><a href="{FRONTEND_URL}/signup?ref=cold-a3" style="display:inline-block; background:#1e3a5f; color:white; padding:12px 24px; border-radius:5px; text-decoration:none;">Погледни ја конкуренцијата</a></p>

        <p>Поздрав,<br>Тамара</p>
        {EMAIL_FOOTER.format(unsub_url=unsub_url)}
    </div>
</body></html>""",
            "text": f"""Почитувани,

Дали знаете кои компании најчесто побеждуваат во тендерите каде што {company} учествува?

NabavkiData анализира 15,000+ тендери и може да ви покаже:
- Кои конкуренти побеждуваат во вашите категории
- Колку често добиваат и со какви цени
- Во кои институции имаат предност

Бесплатен пробен период — целосен пристап 7 дена, без обврска.

Погледни ја конкуренцијата: {FRONTEND_URL}/signup?ref=cold-a3

Поздрав,
Тамара
{TEXT_FOOTER.format(unsub_url=unsub_url)}"""
        },

        4: {
            "subject": f"Нови тендери за {company} — овој месец",
            "html": f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000; background:#fff;">
    <div style="max-width:600px; margin:0 auto;">
        <p>Почитувани,</p>

        <p>Оваа недела има <strong>нови активни тендери</strong> во категориите каде што {company} учествува.</p>

        <p>Дали рачно ја проверувате е-набавки секој ден? Нашите корисници добиваат <strong>автоматски известувања</strong> штом се објави нов тендер — директно на мејл.</p>

        <p><strong>Како функционира:</strong></p>
        <ol>
            <li>Изберете ги вашите категории (CPV кодови)</li>
            <li>Додадете клучни зборови (пр: "медицинска опрема", "градежни работи")</li>
            <li>Добивајте известувања секој ден</li>
        </ol>

        <p><a href="{FRONTEND_URL}/signup?ref=cold-a4" style="display:inline-block; background:#1e3a5f; color:white; padding:12px 24px; border-radius:5px; text-decoration:none;">Активирај AI известувања</a></p>

        <p>Поздрав,<br>Тамара</p>
        {EMAIL_FOOTER.format(unsub_url=unsub_url)}
    </div>
</body></html>""",
            "text": f"""Почитувани,

Оваа недела има нови активни тендери во категориите каде што {company} учествува.

Дали рачно ја проверувате е-набавки секој ден? Нашите корисници добиваат автоматски известувања штом се објави нов тендер.

Како функционира:
1. Изберете ги вашите категории
2. Додадете клучни зборови
3. Добивајте известувања секој ден

Активирај AI известувања: {FRONTEND_URL}/signup?ref=cold-a4

Поздрав,
Тамара
{TEXT_FOOTER.format(unsub_url=unsub_url)}"""
        },

        5: {
            "subject": f"Последна порака: дали да продолжам со извештаи за {company}?",
            "html": f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000; background:#fff;">
    <div style="max-width:600px; margin:0 auto;">
        <p>Почитувани,</p>

        <p>Ова е последната порака од мене.</p>

        <p>Ви испратив информации за тоа како NabavkiData може да ви помогне со тендерски известувања, конкурентски анализи и AI пребарување.</p>

        <p>Ако имате интерес — одговорете <strong>ДА</strong> и ќе ви отворам бесплатна пробна сметка.</p>

        <p>Ако не — нема проблем, нема да ви пишувам повеќе.</p>

        <p>Ви посакувам успешна тендерска сезона!</p>

        <p>Поздрав,<br>Тамара<br>NabavkiData</p>
        {EMAIL_FOOTER.format(unsub_url=unsub_url)}
    </div>
</body></html>""",
            "text": f"""Почитувани,

Ова е последната порака од мене.

Ви испратив информации за тоа како NabavkiData може да ви помогне со тендерски известувања, конкурентски анализи и AI пребарување.

Ако имате интерес — одговорете ДА и ќе ви отворам бесплатна пробна сметка.

Ако не — нема проблем, нема да ви пишувам повеќе.

Ви посакувам успешна тендерска сезона!

Поздрав,
Тамара, NabavkiData
{TEXT_FOOTER.format(unsub_url=unsub_url)}"""
        },
    }
    return templates.get(step, templates[1])


def get_template_b(step: int, company: str, city: str, industry: str, unsub_url: str) -> Dict:
    """Templates for Segment B — Growth-Potential Companies."""
    industry_display = industry or "вашата дејност"
    city_display = city or "Македонија"

    templates = {
        1: {
            "subject": f"{company}: дали знаевте за тендери во {industry_display}?",
            "html": f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000; background:#fff;">
    <div style="max-width:600px; margin:0 auto;">
        <p>Почитувани,</p>

        <p>Јавните набавки во Македонија вредат над <strong>1 милијарда EUR годишно</strong>.</p>

        <p>Секој ден државни институции, болници, општини и јавни претпријатија објавуваат тендери за производи и услуги — вклучувајќи и такви што одговараат на <strong>{industry_display}</strong>.</p>

        <p style="background:#f0f9ff; padding:15px; border-radius:8px; border-left:4px solid #2563eb;">
            <strong>NabavkiData</strong> ги следи сите тендери на е-набавки и ви помага да ги најдете оние што одговараат на вашиот бизнис — <strong>без рачно пребарување</strong>.
        </p>

        <p><a href="{FRONTEND_URL}/tenders?ref=cold-b1" style="display:inline-block; background:#1e3a5f; color:white; padding:12px 24px; border-radius:5px; text-decoration:none;">Погледни активни тендери</a></p>

        <p>Регистрацијата е бесплатна. Пробајте — можеби има тендер токму за вас.</p>

        <p>Поздрав,<br>Тамара<br>NabavkiData</p>
        {EMAIL_FOOTER.format(unsub_url=unsub_url)}
    </div>
</body></html>""",
            "text": f"""Почитувани,

Јавните набавки во Македонија вредат над 1 милијарда EUR годишно.

Секој ден државни институции објавуваат тендери за производи и услуги — вклучувајќи и такви што одговараат на {industry_display}.

NabavkiData ги следи сите тендери на е-набавки и ви помага да ги најдете оние што одговараат на вашиот бизнис.

Погледни активни тендери: {FRONTEND_URL}/tenders?ref=cold-b1

Регистрацијата е бесплатна.

Поздрав,
Тамара, NabavkiData
{TEXT_FOOTER.format(unsub_url=unsub_url)}"""
        },

        2: {
            "subject": f"Тендери за {industry_display} во последните 30 дена",
            "html": f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000; background:#fff;">
    <div style="max-width:600px; margin:0 auto;">
        <p>Почитувани,</p>

        <p>Само во последните 30 дена се објавени десетици тендери релевантни за компании од <strong>{industry_display}</strong> во <strong>{city_display}</strong>.</p>

        <p><strong>Тендерите вклучуваат:</strong></p>
        <ul>
            <li>Набавка на производи и услуги од државни институции</li>
            <li>Рамковни договори со општини и јавни претпријатија</li>
            <li>Мали набавки (до 500.000 МКД) — идеални за мали фирми</li>
        </ul>

        <p style="background:#fef3c7; padding:15px; border-radius:8px; border-left:4px solid #f59e0b;">
            <strong>Дали знаевте?</strong> Повеќето тендери бараат минимум 1 понуда. Многу компании не учествуваат само затоа што не знаат за нив.
        </p>

        <p><a href="{FRONTEND_URL}/signup?ref=cold-b2" style="display:inline-block; background:#1e3a5f; color:white; padding:12px 24px; border-radius:5px; text-decoration:none;">Регистрирај се бесплатно</a></p>

        <p>Поздрав,<br>Тамара</p>
        {EMAIL_FOOTER.format(unsub_url=unsub_url)}
    </div>
</body></html>""",
            "text": f"""Почитувани,

Само во последните 30 дена се објавени десетици тендери релевантни за компании од {industry_display} во {city_display}.

Тендерите вклучуваат:
- Набавка на производи и услуги од државни институции
- Рамковни договори со општини
- Мали набавки (до 500.000 МКД) — идеални за мали фирми

Дали знаевте? Многу компании не учествуваат само затоа што не знаат за тендерите.

Регистрирај се бесплатно: {FRONTEND_URL}/signup?ref=cold-b2

Поздрав,
Тамара
{TEXT_FOOTER.format(unsub_url=unsub_url)}"""
        },

        3: {
            "subject": "Вашите конкуренти веќе учествуваат на тендери",
            "html": f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000; background:#fff;">
    <div style="max-width:600px; margin:0 auto;">
        <p>Почитувани,</p>

        <p>Компании слични на {company} веќе учествуваат на јавни набавки и добиваат договори со државни институции.</p>

        <p><strong>Зошто тендерите се привлечни?</strong></p>
        <ul>
            <li>Државата <strong>секогаш плаќа</strong> — нема ризик од неплаќање</li>
            <li>Договорите се на 1-3 години — <strong>стабилен приход</strong></li>
            <li>Мали набавки (до 500.000 МКД) имаат <strong>едноставна процедура</strong></li>
        </ul>

        <p style="background:#f0fdf4; padding:15px; border-radius:8px; border-left:4px solid #22c55e;">
            NabavkiData ви испраќа <strong>дневни известувања</strong> за тендери во вашата дејност. Не пропуштајте повеќе можности.
        </p>

        <p><a href="{FRONTEND_URL}/signup?ref=cold-b3" style="display:inline-block; background:#1e3a5f; color:white; padding:12px 24px; border-radius:5px; text-decoration:none;">Пробај бесплатно</a></p>

        <p>Поздрав,<br>Тамара</p>
        {EMAIL_FOOTER.format(unsub_url=unsub_url)}
    </div>
</body></html>""",
            "text": f"""Почитувани,

Компании слични на {company} веќе учествуваат на јавни набавки и добиваат договори со државни институции.

Зошто тендерите се привлечни?
- Државата секогаш плаќа — нема ризик
- Договорите се на 1-3 години — стабилен приход
- Мали набавки имаат едноставна процедура

NabavkiData ви испраќа дневни известувања за тендери во вашата дејност.

Пробај бесплатно: {FRONTEND_URL}/signup?ref=cold-b3

Поздрав,
Тамара
{TEXT_FOOTER.format(unsub_url=unsub_url)}"""
        },

        4: {
            "subject": "Како да аплицирате на тендер за 30 минути",
            "html": f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000; background:#fff;">
    <div style="max-width:600px; margin:0 auto;">
        <p>Почитувани,</p>

        <p>Многу компании мислат дека тендерите се комплицирани. Всушност, за мали набавки — процесот е <strong>поедноставен отколку што мислите</strong>.</p>

        <p><strong>5 чекори до прва понуда:</strong></p>
        <ol>
            <li><strong>Најдете тендер</strong> — NabavkiData ви испраќа релевантни тендери на мејл</li>
            <li><strong>Прочитајте ја документацијата</strong> — нашиот AI ги извлекува клучните барања</li>
            <li><strong>Подгответе понуда</strong> — цена + техничка спецификација</li>
            <li><strong>Поднесете електронски</strong> — преку е-набавки (espp.finance.gov.mk)</li>
            <li><strong>Чекајте резултат</strong> — добивате известување за одлука</li>
        </ol>

        <p style="background:#f0f9ff; padding:15px; border-radius:8px; border-left:4px solid #2563eb;">
            <strong>NabavkiData го поедноставува чекор 1 и 2</strong> — наместо рачно пребарување и читање PDF-ови, добивате AI-обработени известувања.
        </p>

        <p><a href="{FRONTEND_URL}/signup?ref=cold-b4" style="display:inline-block; background:#1e3a5f; color:white; padding:12px 24px; border-radius:5px; text-decoration:none;">Започни бесплатно</a></p>

        <p>Поздрав,<br>Тамара</p>
        {EMAIL_FOOTER.format(unsub_url=unsub_url)}
    </div>
</body></html>""",
            "text": f"""Почитувани,

Многу компании мислат дека тендерите се комплицирани. Всушност, за мали набавки — процесот е поедноставен отколку што мислите.

5 чекори до прва понуда:
1. Најдете тендер — NabavkiData ви испраќа релевантни тендери на мејл
2. Прочитајте ја документацијата — нашиот AI ги извлекува клучните барања
3. Подгответе понуда — цена + техничка спецификација
4. Поднесете електронски — преку е-набавки
5. Чекајте резултат — добивате известување

NabavkiData го поедноставува чекор 1 и 2.

Започни бесплатно: {FRONTEND_URL}/signup?ref=cold-b4

Поздрав,
Тамара
{TEXT_FOOTER.format(unsub_url=unsub_url)}"""
        },

        5: {
            "subject": f"Последна порака — дали имате интерес за тендери?",
            "html": f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000; background:#fff;">
    <div style="max-width:600px; margin:0 auto;">
        <p>Почитувани,</p>

        <p>Ова е последната порака од мене.</p>

        <p>Ви испратив информации за тоа како {company} може да учествува на јавни набавки — стабилен пазар од над 1 милијарда EUR годишно.</p>

        <p>Ако тендерите се интересни за вашиот бизнис — одговорете <strong>ДА</strong> и ќе ви помогнам лично да се регистрирате.</p>

        <p>Ако не — нема проблем, нема повеќе да ви пишувам.</p>

        <p>Ви посакувам многу успех!</p>

        <p>Поздрав,<br>Тамара<br>NabavkiData</p>
        {EMAIL_FOOTER.format(unsub_url=unsub_url)}
    </div>
</body></html>""",
            "text": f"""Почитувани,

Ова е последната порака од мене.

Ви испратив информации за тоа како {company} може да учествува на јавни набавки.

Ако тендерите се интересни — одговорете ДА и ќе ви помогнам лично.

Ако не — нема проблем, нема повеќе да ви пишувам.

Ви посакувам многу успех!

Поздрав,
Тамара, NabavkiData
{TEXT_FOOTER.format(unsub_url=unsub_url)}"""
        },
    }
    return templates.get(step, templates[1])


# =============================================================================
# RATE LIMITING
# =============================================================================

async def check_rate_limits(conn) -> tuple:
    """Check daily and hourly send limits. Returns (can_send, message)."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    daily_count = await conn.fetchval("""
        SELECT COUNT(*) FROM outreach_emails
        WHERE sent_at >= $1
    """, today_start) or 0

    hourly_count = await conn.fetchval("""
        SELECT COUNT(*) FROM outreach_emails
        WHERE sent_at >= $1
    """, hour_start) or 0

    if daily_count >= DAILY_LIMIT:
        return False, f"Daily limit reached ({daily_count}/{DAILY_LIMIT})"
    if hourly_count >= HOURLY_LIMIT:
        return False, f"Hourly limit reached ({hourly_count}/{HOURLY_LIMIT})"

    return True, f"OK (daily: {daily_count}/{DAILY_LIMIT}, hourly: {hourly_count}/{HOURLY_LIMIT})"


async def is_suppressed(conn, email: str) -> bool:
    """Check suppression list and campaign unsubscribes."""
    suppressed = await conn.fetchval(
        "SELECT 1 FROM suppression_list WHERE email = $1", email.lower()
    )
    if suppressed:
        return True

    unsubbed = await conn.fetchval(
        "SELECT 1 FROM campaign_unsubscribes WHERE email = $1", email.lower()
    )
    return bool(unsubbed)


# =============================================================================
# SENDING
# =============================================================================

async def send_drip_email(
    client: httpx.AsyncClient,
    lead: dict,
    step: int,
    dry_run: bool = False
) -> dict:
    """Send a single drip email."""
    email = lead['email']
    company = lead['company_name'] or 'Вашата компанија'
    segment = lead['segment']
    city = lead.get('city') or ''
    industry = lead.get('company_industry') or ''
    unsub_url = generate_unsubscribe_url(email)

    # Get the right template
    if segment == 'A':
        template = get_template_a(step, company, unsub_url)
    else:
        template = get_template_b(step, company, city, industry, unsub_url)

    if dry_run:
        return {
            "dry_run": True,
            "email": email,
            "company": company,
            "segment": segment,
            "step": step,
            "subject": template["subject"]
        }

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
            "MessageStream": POSTMARK_MESSAGE_STREAM,
            "TrackOpens": True,
            "TrackLinks": "HtmlAndText",
            "Tag": f"cold-drip-{segment.lower()}-step{step}",
            "Headers": [
                {"Name": "List-Unsubscribe", "Value": f"<{unsub_url}>"},
                {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"}
            ],
            "Metadata": {
                "lead_id": str(lead['lead_id']),
                "segment": segment,
                "step": str(step),
                "company": company[:50]
            }
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

async def process_drip(args):
    """Process all leads ready for their next drip email."""
    logger.info("=" * 60)
    logger.info("COLD OUTREACH DRIP PROCESSOR")
    logger.info(f"Time: {datetime.utcnow().isoformat()}")
    logger.info(f"Limits: {DAILY_LIMIT}/day, {HOURLY_LIMIT}/hour")
    if args.dry_run:
        logger.info("*** DRY RUN — no emails will be sent ***")
    logger.info("=" * 60)

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Check rate limits first
        can_send, rate_msg = await check_rate_limits(conn)
        logger.info(f"Rate limits: {rate_msg}")
        if not can_send and not args.dry_run:
            logger.info("Rate limit reached, skipping this run")
            return

        # Build query for leads ready for next email
        # Uses the leads_ready_for_outreach view
        segment_filter = ""
        if args.segment:
            segment_filter = f"AND segment = '{args.segment}'"

        leads = await conn.fetch(f"""
            SELECT lead_id, email, company_name, segment, city,
                   company_industry, outreach_status, next_email_number
            FROM leads_ready_for_outreach
            WHERE next_email_number > 0
              {segment_filter}
            ORDER BY segment ASC, quality_score DESC
            LIMIT $1
        """, args.limit)

        logger.info(f"Found {len(leads)} leads ready for next email")

        if not leads:
            logger.info("No leads ready for drip emails")
            return

        sent = 0
        errors = 0
        skipped = 0

        async with httpx.AsyncClient() as client:
            for lead in leads:
                step = lead['next_email_number']
                email = lead['email']

                # Re-check rate limits periodically
                if sent > 0 and sent % 10 == 0 and not args.dry_run:
                    can_send, _ = await check_rate_limits(conn)
                    if not can_send:
                        logger.info(f"Rate limit reached after {sent} sends")
                        break

                # Check suppression
                if not args.dry_run and await is_suppressed(conn, email):
                    await conn.execute("""
                        UPDATE outreach_leads
                        SET outreach_status = 'unsubscribed', updated_at = NOW()
                        WHERE lead_id = $1
                    """, lead['lead_id'])
                    skipped += 1
                    continue

                # Send email
                result = await send_drip_email(client, dict(lead), step, args.dry_run)

                if result.get('success') or result.get('dry_run'):
                    sent += 1

                    if not args.dry_run:
                        # Update lead status
                        new_status = f"email_{step}_sent"
                        await conn.execute("""
                            UPDATE outreach_leads SET
                                outreach_status = $1,
                                last_contact_at = NOW(),
                                total_emails_sent = total_emails_sent + 1,
                                first_contact_at = COALESCE(first_contact_at, NOW()),
                                updated_at = NOW()
                            WHERE lead_id = $2
                        """, new_status, lead['lead_id'])

                        # Log to outreach_emails
                        await conn.execute("""
                            INSERT INTO outreach_emails (
                                lead_id, email_sequence, subject, sent_at
                            ) VALUES ($1, $2, $3, NOW())
                        """, lead['lead_id'], step, result.get('subject', f'Step {step}'))

                    logger.info(
                        f"  [{lead['segment']}/{step}] {email} — "
                        f"{lead['company_name'][:30]} "
                        f"{'(dry)' if args.dry_run else 'SENT'}"
                    )
                else:
                    errors += 1
                    error_msg = result.get('error', 'Unknown')[:80]
                    logger.error(f"  FAIL [{lead['segment']}/{step}] {email}: {error_msg}")

                    # Mark bounced if applicable
                    if 'inactive' in error_msg.lower() or 'bounce' in error_msg.lower():
                        await conn.execute("""
                            UPDATE outreach_leads
                            SET outreach_status = 'bounced', updated_at = NOW()
                            WHERE lead_id = $1
                        """, lead['lead_id'])
                        await conn.execute("""
                            INSERT INTO suppression_list (email, reason, source)
                            VALUES ($1, 'bounce', 'cold_drip')
                            ON CONFLICT (email) DO NOTHING
                        """, email.lower())

                # Jitter between sends
                if not args.dry_run and sent < len(leads):
                    jitter = random.uniform(MIN_JITTER, MAX_JITTER)
                    await asyncio.sleep(jitter)

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"COMPLETE: {sent} sent, {errors} errors, {skipped} skipped")
        logger.info("=" * 60)

        # Show outreach stats
        stats = await conn.fetch("""
            SELECT segment, outreach_status, COUNT(*) as count
            FROM outreach_leads
            GROUP BY segment, outreach_status
            ORDER BY segment, outreach_status
        """)
        if stats:
            logger.info("\nOutreach stats:")
            for row in stats:
                logger.info(f"  Segment {row['segment']} / {row['outreach_status']}: {row['count']}")

    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description='Cold outreach drip processor')
    parser.add_argument('--dry-run', action='store_true', help='Preview without sending')
    parser.add_argument('--limit', type=int, default=100, help='Max emails per run')
    parser.add_argument('--segment', choices=['A', 'B'], help='Only process specific segment')
    args = parser.parse_args()

    await process_drip(args)


if __name__ == '__main__':
    asyncio.run(main())

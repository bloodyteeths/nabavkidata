#!/usr/bin/env python3
"""
Standalone PDF Report Generator - No FastAPI dependencies
Run with: python3 backend/cli/standalone_report_gen.py --limit 5
"""
import os
import sys
import asyncio
import argparse
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
load_dotenv()


# Try to import weasyprint
try:
    from weasyprint import HTML
except ImportError:
    print("ERROR: weasyprint not installed. Run: pip3 install weasyprint")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "nabavkidata")
DB_USER = os.getenv("DB_USER", "nabavki_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

REPORTS_DIR = os.getenv("REPORTS_DIR", "/tmp/nabavkidata_reports")
Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

FRONTEND_URL = "https://nabavkidata.com"
CHECKOUT_URL = f"{FRONTEND_URL}/plans"

# CPV Names in Macedonian
CPV_NAMES_MK = {
    "33000000": "Медицинска опрема",
    "33600000": "Фармацевтски производи",
    "33100000": "Медицински апарати",
    "34000000": "Транспортна опрема",
    "34100000": "Моторни возила",
    "45000000": "Градежни работи",
    "45200000": "Градежни работи на згради",
    "50000000": "Услуги за поправка и одржување",
    "55000000": "Хотелски и угостителски услуги",
    "60000000": "Транспортни услуги",
    "71000000": "Архитектонски услуги",
    "72000000": "ИТ услуги",
    "79000000": "Деловни услуги",
    "85000000": "Здравствени услуги",
    "90000000": "Услуги за отпад и животна средина",
    "48000000": "Софтверски пакети",
    "30000000": "Канцелариска опрема",
    "39000000": "Мебел и опрема",
    "15000000": "Прехранбени производи",
    "44000000": "Градежни материјали",
}


def get_cpv_name(cpv_code):
    if not cpv_code:
        return "Непознато"
    if cpv_code in CPV_NAMES_MK:
        return CPV_NAMES_MK[cpv_code]
    prefix = cpv_code[:8] if len(cpv_code) >= 8 else cpv_code
    for code, name in CPV_NAMES_MK.items():
        if code.startswith(prefix[:2]):
            return name
    return f"CPV {cpv_code}"


def format_value(value):
    if value is None or value == 0:
        return "Н/А"
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}М МКД"
    if value >= 1_000:
        return f"{value/1_000:.0f}К МКД"
    return f"{value:.0f} МКД"


# ============================================================================
# DATABASE QUERIES
# ============================================================================

async def get_pool():
    return await asyncpg.create_pool(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
        min_size=2, max_size=10
    )


async def get_top_companies(pool, limit=10):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                tb.company_name,
                tb.company_tax_id,
                COUNT(DISTINCT tb.tender_id) as participations,
                COUNT(DISTINCT CASE WHEN tb.is_winner THEN tb.tender_id END) as wins,
                COALESCE(SUM(CASE WHEN tb.is_winner THEN t.actual_value_mkd END), 0) as total_value
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE t.publication_date >= NOW() - INTERVAL '12 months'
              AND tb.company_name IS NOT NULL
              AND LENGTH(TRIM(tb.company_name)) > 3
            GROUP BY tb.company_name, tb.company_tax_id
            HAVING COUNT(DISTINCT tb.tender_id) >= 5
               AND COUNT(DISTINCT CASE WHEN tb.is_winner THEN tb.tender_id END) >= 2
            ORDER BY wins DESC, total_value DESC
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]


async def get_company_stats(conn, company_name, company_tax_id=None):
    cutoff = datetime.utcnow() - timedelta(days=365)

    if company_tax_id:
        condition = "(tb.company_name ILIKE $1 OR tb.company_tax_id = $2)"
        params = [f"%{company_name}%", company_tax_id, cutoff]
    else:
        condition = "tb.company_name ILIKE $1"
        params = [f"%{company_name}%", cutoff]

    query = f"""
        SELECT
            COUNT(DISTINCT tb.tender_id) as total_participations,
            COUNT(DISTINCT CASE WHEN tb.is_winner THEN tb.tender_id END) as total_wins,
            COALESCE(SUM(CASE WHEN tb.is_winner THEN t.actual_value_mkd END), 0) as total_value_won
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE {condition} AND t.publication_date >= ${len(params)}
    """

    row = await conn.fetchrow(query, *params)
    participations = row['total_participations'] or 0
    wins = row['total_wins'] or 0
    total_value = row['total_value_won'] or 0
    win_rate = round(100 * wins / participations, 1) if participations > 0 else 0

    return {
        "participations_12m": participations,
        "wins_12m": wins,
        "win_rate": win_rate,
        "total_value_mkd": float(total_value)
    }


async def get_top_cpvs(conn, company_name, company_tax_id=None, limit=3):
    if company_tax_id:
        condition = "(tb.company_name ILIKE $1 OR tb.company_tax_id = $2)"
        params = [f"%{company_name}%", company_tax_id, limit]
    else:
        condition = "tb.company_name ILIKE $1"
        params = [f"%{company_name}%", limit]

    query = f"""
        SELECT
            SUBSTRING(t.cpv_code FROM 1 FOR 8) as cpv_prefix,
            COUNT(*) as count,
            SUM(CASE WHEN tb.is_winner THEN 1 ELSE 0 END) as wins,
            COALESCE(SUM(CASE WHEN tb.is_winner THEN t.actual_value_mkd END), 0) as value_won
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE {condition} AND t.cpv_code IS NOT NULL
        GROUP BY SUBSTRING(t.cpv_code FROM 1 FOR 8)
        ORDER BY count DESC, value_won DESC
        LIMIT ${len(params)}
    """

    rows = await conn.fetch(query, *params)
    return [
        {"code": r['cpv_prefix'], "name": get_cpv_name(r['cpv_prefix']),
         "count": r['count'], "wins": r['wins'], "value_won": float(r['value_won'] or 0)}
        for r in rows
    ]


async def get_top_buyers(conn, company_name, company_tax_id=None, limit=3):
    if company_tax_id:
        condition = "(tb.company_name ILIKE $1 OR tb.company_tax_id = $2)"
        params = [f"%{company_name}%", company_tax_id, limit]
    else:
        condition = "tb.company_name ILIKE $1"
        params = [f"%{company_name}%", limit]

    query = f"""
        SELECT
            t.procuring_entity as buyer_name,
            COUNT(*) as tender_count,
            SUM(CASE WHEN tb.is_winner THEN 1 ELSE 0 END) as wins,
            COALESCE(SUM(CASE WHEN tb.is_winner THEN t.actual_value_mkd END), 0) as value_won
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE {condition} AND t.procuring_entity IS NOT NULL
        GROUP BY t.procuring_entity
        ORDER BY tender_count DESC, value_won DESC
        LIMIT ${len(params)}
    """

    rows = await conn.fetch(query, *params)
    return [
        {"name": r['buyer_name'], "count": r['tender_count'],
         "wins": r['wins'], "value_won": float(r['value_won'] or 0)}
        for r in rows
    ]


async def get_competitors(conn, company_name, top_cpvs, limit=5):
    if not top_cpvs:
        return []

    cpv_codes = [c['code'] for c in top_cpvs]

    query = """
        SELECT
            tb.company_name,
            COUNT(DISTINCT tb.tender_id) as participations,
            COUNT(DISTINCT CASE WHEN tb.is_winner THEN tb.tender_id END) as wins,
            COALESCE(SUM(CASE WHEN tb.is_winner THEN t.actual_value_mkd END), 0) as total_value
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE SUBSTRING(t.cpv_code FROM 1 FOR 8) = ANY($1)
          AND tb.company_name NOT ILIKE $2
          AND tb.is_winner = true
          AND t.publication_date >= NOW() - INTERVAL '12 months'
        GROUP BY tb.company_name
        HAVING COUNT(DISTINCT CASE WHEN tb.is_winner THEN tb.tender_id END) >= 2
        ORDER BY wins DESC, total_value DESC
        LIMIT $3
    """

    rows = await conn.fetch(query, cpv_codes, f"%{company_name}%", limit)
    return [
        {"name": r['company_name'], "participations": r['participations'],
         "wins": r['wins'], "total_value": float(r['total_value'] or 0)}
        for r in rows
    ]


async def get_missed_opportunities(conn, company_name, company_tax_id, top_cpvs, days=90, limit=10):
    if not top_cpvs:
        return []

    cpv_codes = [c['code'] for c in top_cpvs]
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = """
        SELECT
            t.tender_id,
            t.title,
            t.procuring_entity,
            t.closing_date,
            t.estimated_value_mkd,
            t.actual_value_mkd,
            t.cpv_code,
            t.winner
        FROM tenders t
        WHERE SUBSTRING(t.cpv_code FROM 1 FOR 8) = ANY($1)
          AND t.publication_date >= $2
          AND t.status IN ('awarded', 'closed')
          AND NOT EXISTS (
              SELECT 1 FROM tender_bidders tb
              WHERE tb.tender_id = t.tender_id
                AND (tb.company_name ILIKE $3 OR tb.company_tax_id = $4)
          )
        ORDER BY t.closing_date DESC
        LIMIT $5
    """

    rows = await conn.fetch(query, cpv_codes, cutoff, f"%{company_name}%", company_tax_id or "", limit)
    return [
        {"tender_id": r['tender_id'],
         "title": (r['title'][:100] + "...") if r['title'] and len(r['title']) > 100 else r['title'],
         "buyer": r['procuring_entity'],
         "deadline": r['closing_date'].strftime("%d.%m.%Y") if r['closing_date'] else "Н/А",
         "value": float(r['actual_value_mkd'] or r['estimated_value_mkd'] or 0),
         "cpv": get_cpv_name(r['cpv_code']),
         "winner": r['winner'],
         "match_reason": f"CPV совпаѓање ({r['cpv_code'][:8] if r['cpv_code'] else 'N/A'})"}
        for r in rows
    ]


async def get_expected_tenders(conn, top_cpvs):
    if not top_cpvs:
        return {"low": 0, "mid": 0, "high": 0, "confidence": "low"}

    cpv_codes = [c['code'] for c in top_cpvs]

    query = """
        SELECT
            DATE_TRUNC('month', t.publication_date) as month,
            COUNT(*) as tender_count
        FROM tenders t
        WHERE SUBSTRING(t.cpv_code FROM 1 FOR 8) = ANY($1)
          AND t.publication_date >= NOW() - INTERVAL '12 months'
        GROUP BY DATE_TRUNC('month', t.publication_date)
        ORDER BY month
    """

    rows = await conn.fetch(query, cpv_codes)

    if not rows:
        return {"low": 0, "mid": 0, "high": 0, "confidence": "low"}

    monthly_counts = [r['tender_count'] for r in rows]
    avg = sum(monthly_counts) / len(monthly_counts) if monthly_counts else 0

    return {
        "low": max(0, int(avg * 0.5)),
        "mid": int(avg),
        "high": int(avg * 1.5),
        "confidence": "medium" if len(monthly_counts) >= 6 else "low"
    }


async def get_buyer_map(conn, top_cpvs, limit=10):
    if not top_cpvs:
        return []

    cpv_codes = [c['code'] for c in top_cpvs]

    query = """
        WITH buyer_stats AS (
            SELECT
                t.procuring_entity,
                COUNT(DISTINCT t.tender_id) as tender_count,
                COALESCE(SUM(t.actual_value_mkd), 0) as total_value
            FROM tenders t
            WHERE SUBSTRING(t.cpv_code FROM 1 FOR 8) = ANY($1)
              AND t.publication_date >= NOW() - INTERVAL '12 months'
              AND t.procuring_entity IS NOT NULL
            GROUP BY t.procuring_entity
            ORDER BY tender_count DESC
            LIMIT $2
        ),
        top_winners AS (
            SELECT
                t.procuring_entity,
                tb.company_name as winner,
                COUNT(*) as wins
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE SUBSTRING(t.cpv_code FROM 1 FOR 8) = ANY($1)
              AND tb.is_winner = true
              AND t.publication_date >= NOW() - INTERVAL '12 months'
            GROUP BY t.procuring_entity, tb.company_name
        )
        SELECT
            bs.procuring_entity,
            bs.tender_count,
            bs.total_value,
            (SELECT tw.winner FROM top_winners tw
             WHERE tw.procuring_entity = bs.procuring_entity
             ORDER BY tw.wins DESC LIMIT 1) as top_winner
        FROM buyer_stats bs
    """

    rows = await conn.fetch(query, cpv_codes, limit)
    return [
        {"name": r['procuring_entity'], "tender_count": r['tender_count'],
         "total_value": float(r['total_value'] or 0), "top_winner": r['top_winner']}
        for r in rows
    ]


# ============================================================================
# HTML TEMPLATE
# ============================================================================

def generate_report_html(company_name, stats, top_cpvs, top_buyers, competitors,
                         missed_opportunities, expected_tenders, buyer_map):
    win_rate = stats.get('win_rate', 0)
    total_value_formatted = format_value(stats.get('total_value_mkd', 0))

    # CPV rows
    cpv_rows = ""
    for cpv in top_cpvs[:3]:
        cpv_rows += f"""
        <tr>
            <td>{cpv['name']}</td>
            <td style="text-align: center;">{cpv['count']}</td>
            <td style="text-align: center;">{cpv['wins']}</td>
            <td style="text-align: right;">{format_value(cpv['value_won'])}</td>
        </tr>"""

    # Buyer rows
    buyer_rows = ""
    for buyer in top_buyers[:3]:
        name = buyer['name'][:40] + '...' if len(buyer['name']) > 40 else buyer['name']
        buyer_rows += f"""
        <tr>
            <td>{name}</td>
            <td style="text-align: center;">{buyer['count']}</td>
            <td style="text-align: center;">{buyer['wins']}</td>
        </tr>"""

    # Competitor rows
    competitor_rows = ""
    for comp in competitors[:5]:
        name = comp['name'][:35] + '...' if len(comp['name']) > 35 else comp['name']
        competitor_rows += f"""
        <tr>
            <td>{name}</td>
            <td style="text-align: center;">{comp['wins']}</td>
            <td style="text-align: right;">{format_value(comp['total_value'])}</td>
        </tr>"""

    # Missed opportunities
    missed_rows = ""
    for opp in missed_opportunities[:10]:
        title = opp['title'][:50] + '...' if opp['title'] and len(opp['title']) > 50 else opp['title']
        buyer = opp['buyer'][:25] + '...' if opp['buyer'] and len(opp['buyer']) > 25 else opp['buyer']
        missed_rows += f"""
        <tr>
            <td>{title}</td>
            <td>{buyer}</td>
            <td style="text-align: center;">{opp['deadline']}</td>
            <td style="text-align: right;">{format_value(opp['value'])}</td>
            <td>{opp['cpv']}</td>
        </tr>"""

    # Buyer map
    buyer_map_rows = ""
    for bm in buyer_map[:10]:
        name = bm['name'][:35] + '...' if len(bm['name']) > 35 else bm['name']
        winner = bm['top_winner'][:30] + '...' if bm['top_winner'] and len(bm['top_winner']) > 30 else (bm['top_winner'] or 'Н/А')
        buyer_map_rows += f"""
        <tr>
            <td>{name}</td>
            <td style="text-align: center;">{bm['tender_count']}</td>
            <td>{winner}</td>
        </tr>"""

    expected_text = f"{expected_tenders['low']}-{expected_tenders['high']} тендери"
    confidence_text = {"low": "(ниска доверба)", "medium": "(средна доверба)", "high": "(висока доверба)"}.get(expected_tenders.get('confidence', 'low'), "")

    generated_date = datetime.utcnow().strftime("%d.%m.%Y")

    html = f"""
<!DOCTYPE html>
<html lang="mk">
<head>
    <meta charset="UTF-8">
    <title>Тендерски Извештај - {company_name}</title>
    <style>
        @page {{ size: A4; margin: 1.5cm; }}
        body {{ font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10pt; line-height: 1.4; color: #333; }}
        .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); color: white; padding: 20px; margin: -1.5cm -1.5cm 20px -1.5cm; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 18pt; }}
        .header .company {{ font-size: 14pt; margin-top: 5px; font-weight: normal; }}
        .header .date {{ font-size: 9pt; margin-top: 10px; opacity: 0.8; }}
        h2 {{ color: #1e3a5f; border-bottom: 2px solid #1e3a5f; padding-bottom: 5px; font-size: 12pt; margin-top: 25px; }}
        .metrics {{ display: flex; justify-content: space-around; margin: 20px 0; flex-wrap: wrap; }}
        .metric {{ text-align: center; padding: 15px; background: #f8f9fa; border-radius: 8px; min-width: 120px; margin: 5px; }}
        .metric .value {{ font-size: 24pt; font-weight: bold; color: #1e3a5f; }}
        .metric .label {{ font-size: 9pt; color: #666; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 9pt; }}
        th {{ background: #1e3a5f; color: white; padding: 8px; text-align: left; }}
        td {{ padding: 6px 8px; border-bottom: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .disclaimer {{ background: #fff3cd; border: 1px solid #ffc107; padding: 10px; font-size: 8pt; margin: 15px 0; border-radius: 4px; }}
        .cta-box {{ background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 20px; text-align: center; border-radius: 8px; margin: 25px 0; }}
        .cta-box h3 {{ margin: 0 0 10px 0; font-size: 14pt; }}
        .cta-box p {{ margin: 5px 0; font-size: 10pt; }}
        .cta-box .options {{ margin-top: 15px; font-size: 9pt; }}
        .footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; font-size: 8pt; color: #666; text-align: center; }}
        .page-break {{ page-break-before: always; }}
        .confidence {{ font-size: 8pt; color: #666; font-style: italic; }}
    </style>
</head>
<body>

<div class="header">
    <h1>Тендерски Извештај</h1>
    <div class="company">{company_name}</div>
    <div class="date">Генерирано: {generated_date}</div>
</div>

<h2>1. Преглед на Активности (последни 12 месеци)</h2>

<div class="metrics">
    <div class="metric"><div class="value">{stats.get('participations_12m', 0)}</div><div class="label">Учества</div></div>
    <div class="metric"><div class="value">{stats.get('wins_12m', 0)}</div><div class="label">Победи</div></div>
    <div class="metric"><div class="value">{win_rate}%</div><div class="label">Стапка на успех</div></div>
    <div class="metric"><div class="value">{total_value_formatted}</div><div class="label">Вкупна вредност</div></div>
</div>

<h3>Топ CPV категории</h3>
<table>
    <tr><th>Категорија</th><th style="text-align: center;">Учества</th><th style="text-align: center;">Победи</th><th style="text-align: right;">Вредност</th></tr>
    {cpv_rows if cpv_rows else '<tr><td colspan="4">Нема податоци</td></tr>'}
</table>

<h3>Топ договорни органи</h3>
<table>
    <tr><th>Институција</th><th style="text-align: center;">Тендери</th><th style="text-align: center;">Победи</th></tr>
    {buyer_rows if buyer_rows else '<tr><td colspan="3">Нема податоци</td></tr>'}
</table>

<h3>Конкурентски притисок</h3>
<table>
    <tr><th>Конкурент</th><th style="text-align: center;">Победи (12м)</th><th style="text-align: right;">Вредност</th></tr>
    {competitor_rows if competitor_rows else '<tr><td colspan="3">Нема податоци за конкуренти</td></tr>'}
</table>

<h3>Очекувани тендери (следни 30 дена)</h3>
<p>Врз основа на историски шаблони, очекуваме <strong>{expected_text}</strong> релевантни за вашите категории. <span class="confidence">{confidence_text}</span></p>

<div class="page-break"></div>

<h2>2. Пропуштени можности (последни 90 дена)</h2>

<div class="disclaimer"><strong>Напомена:</strong> Пропуштените можности се пресметани според совпаѓање на вашите историски CPV кодови и договорни органи. Ова не е гарантиран список.</div>

<table>
    <tr><th>Наслов</th><th>Договорен орган</th><th style="text-align: center;">Рок</th><th style="text-align: right;">Вредност</th><th>CPV</th></tr>
    {missed_rows if missed_rows else '<tr><td colspan="5">Нема пропуштени тендери во овој период</td></tr>'}
</table>

<div class="page-break"></div>

<h2>3. Мапа на договорни органи и победници</h2>

<table>
    <tr><th>Договорен орган</th><th style="text-align: center;">Тендери (12м)</th><th>Најчест победник</th></tr>
    {buyer_map_rows if buyer_map_rows else '<tr><td colspan="3">Нема податоци</td></tr>'}
</table>

<div class="cta-box">
    <h3>Продолжете да го добивате овој извештај неделно + дневни известувања</h3>
    <p>Следете ги конкурентите, не пропуштајте релевантни тендери</p>
    <div class="options">
        <p><strong>Одговорете ФАКТУРА</strong> за активирање со фактура (EUR)</p>
        <p>или активирајте со картичка: <strong>{CHECKOUT_URL}</strong></p>
    </div>
</div>

<div class="footer">
    <p>Овој извештај е генериран автоматски од NabavkiData врз основа на јавно достапни податоци од е-Набавки (e-nabavki.gov.mk).</p>
    <p>Ако не сакате да добивате вакви извештаи, одговорете СТОП.</p>
    <p style="margin-top: 10px;">NabavkiData | nabavkidata.com | hello@nabavkidata.com</p>
</div>

</body>
</html>
"""
    return html


# ============================================================================
# MAIN
# ============================================================================

async def generate_report(pool, company_name, company_tax_id=None):
    async with pool.acquire() as conn:
        stats = await get_company_stats(conn, company_name, company_tax_id)
        top_cpvs = await get_top_cpvs(conn, company_name, company_tax_id)
        top_buyers = await get_top_buyers(conn, company_name, company_tax_id)
        competitors = await get_competitors(conn, company_name, top_cpvs)
        missed = await get_missed_opportunities(conn, company_name, company_tax_id, top_cpvs)
        expected = await get_expected_tenders(conn, top_cpvs)
        buyer_map = await get_buyer_map(conn, top_cpvs)

    html = generate_report_html(
        company_name=company_name,
        stats=stats,
        top_cpvs=top_cpvs,
        top_buyers=top_buyers,
        competitors=competitors,
        missed_opportunities=missed,
        expected_tenders=expected,
        buyer_map=buyer_map
    )

    report_id = str(uuid.uuid4())[:8]
    safe_name = "".join(c for c in company_name[:30] if c.isalnum() or c in ' -_').strip()
    pdf_filename = f"report_{safe_name}_{report_id}.pdf"
    pdf_path = os.path.join(REPORTS_DIR, pdf_filename)

    HTML(string=html).write_pdf(pdf_path)

    return {
        "success": True,
        "pdf_path": pdf_path,
        "pdf_size": os.path.getsize(pdf_path),
        "stats": stats,
        "missed_count": len(missed)
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", "-l", type=int, default=5)
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"Generating {args.limit} sample PDF reports")
    print(f"{'='*60}")

    pool = await get_pool()

    print("\nFetching top companies...")
    companies = await get_top_companies(pool, args.limit)

    if not companies:
        print("No companies found!")
        return

    print(f"Found {len(companies)} companies:\n")
    for i, c in enumerate(companies, 1):
        print(f"  {i}. {c['company_name'][:50]}")
        print(f"     Wins: {c['wins']}, Value: {c['total_value']:,.0f} MKD")

    print(f"\n{'='*60}")
    print("Generating PDF reports...")
    print(f"{'='*60}\n")

    generated = []
    for i, company in enumerate(companies, 1):
        print(f"[{i}/{len(companies)}] {company['company_name'][:40]}...")

        try:
            result = await generate_report(pool, company['company_name'], company.get('company_tax_id'))

            if result.get('success'):
                print(f"  OK: {result['pdf_path']}")
                print(f"      Size: {result['pdf_size']:,} bytes, Missed: {result['missed_count']}")
                generated.append(result)
            else:
                print(f"  FAIL: {result.get('error')}")
        except Exception as e:
            print(f"  ERROR: {e}")

    await pool.close()

    print(f"\n{'='*60}")
    print(f"DONE: Generated {len(generated)}/{len(companies)} reports")
    print(f"Location: {REPORTS_DIR}")
    print(f"{'='*60}\n")

    for r in generated:
        print(f"  {r['pdf_path']}")


if __name__ == "__main__":
    asyncio.run(main())

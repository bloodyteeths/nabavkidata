"""
Report Generator Service
Generates personalized tender intelligence PDF reports for companies
All content in Macedonian language
"""
import os
import json
import uuid
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import hashlib
import hmac

import asyncpg
from weasyprint import HTML, CSS

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

REPORTS_DIR = os.getenv("REPORTS_DIR", "/tmp/nabavkidata_reports")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://nabavkidata.com")
REPORT_SECRET = os.getenv("REPORT_SECRET", "nabavki-report-secret-2025")
CHECKOUT_URL = os.getenv("CHECKOUT_URL", f"{FRONTEND_URL}/plans")

# Ensure reports directory exists
Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

# ============================================================================
# CPV CODE TRANSLATIONS (Common ones)
# ============================================================================

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


def get_cpv_name(cpv_code: str) -> str:
    """Get Macedonian name for CPV code"""
    if not cpv_code:
        return "Непознато"
    # Try exact match first
    if cpv_code in CPV_NAMES_MK:
        return CPV_NAMES_MK[cpv_code]
    # Try prefix match (first 8 digits)
    prefix = cpv_code[:8] if len(cpv_code) >= 8 else cpv_code
    for code, name in CPV_NAMES_MK.items():
        if code.startswith(prefix[:2]):
            return name
    return f"CPV {cpv_code}"


def format_value(value: float) -> str:
    """Format monetary value in Macedonian style"""
    if value is None or value == 0:
        return "Н/А"
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}М МКД"
    if value >= 1_000:
        return f"{value/1_000:.0f}К МКД"
    return f"{value:.0f} МКД"


# ============================================================================
# REPORT DATA FETCHER
# ============================================================================

class ReportDataFetcher:
    """Fetches all data needed for a company report from the database"""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_company_stats(
        self, company_name: str, company_tax_id: Optional[str] = None, lookback_days: int = 365
    ) -> Dict:
        """Get participation and win statistics for a company"""
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        async with self.pool.acquire() as conn:
            # Build company match condition
            if company_tax_id:
                company_condition = """
                    (tb.company_name ILIKE $1 OR tb.company_tax_id = $2)
                """
                params = [f"%{company_name}%", company_tax_id, cutoff_date]
            else:
                company_condition = "tb.company_name ILIKE $1"
                params = [f"%{company_name}%", cutoff_date]

            # Get participation stats
            participations_query = f"""
                SELECT
                    COUNT(DISTINCT tb.tender_id) as total_participations,
                    COUNT(DISTINCT CASE WHEN tb.is_winner THEN tb.tender_id END) as total_wins,
                    COALESCE(SUM(CASE WHEN tb.is_winner THEN t.actual_value_mkd END), 0) as total_value_won
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE {company_condition}
                  AND t.publication_date >= ${len(params)}
            """

            row = await conn.fetchrow(participations_query, *params)

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

    async def get_top_cpvs(
        self, company_name: str, company_tax_id: Optional[str] = None, limit: int = 3
    ) -> List[Dict]:
        """Get top CPV codes by participation frequency"""
        async with self.pool.acquire() as conn:
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
                WHERE {condition}
                  AND t.cpv_code IS NOT NULL
                GROUP BY SUBSTRING(t.cpv_code FROM 1 FOR 8)
                ORDER BY count DESC, value_won DESC
                LIMIT ${len(params)}
            """

            rows = await conn.fetch(query, *params)

            return [
                {
                    "code": row['cpv_prefix'],
                    "name": get_cpv_name(row['cpv_prefix']),
                    "count": row['count'],
                    "wins": row['wins'],
                    "value_won": float(row['value_won'] or 0)
                }
                for row in rows
            ]

    async def get_top_buyers(
        self, company_name: str, company_tax_id: Optional[str] = None, limit: int = 3
    ) -> List[Dict]:
        """Get top contracting authorities the company works with"""
        async with self.pool.acquire() as conn:
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
                WHERE {condition}
                  AND t.procuring_entity IS NOT NULL
                GROUP BY t.procuring_entity
                ORDER BY tender_count DESC, value_won DESC
                LIMIT ${len(params)}
            """

            rows = await conn.fetch(query, *params)

            return [
                {
                    "name": row['buyer_name'],
                    "count": row['tender_count'],
                    "wins": row['wins'],
                    "value_won": float(row['value_won'] or 0)
                }
                for row in rows
            ]

    async def get_competitors(
        self, company_name: str, company_tax_id: Optional[str] = None, limit: int = 5
    ) -> List[Dict]:
        """Get top competitors in the same CPV categories"""
        async with self.pool.acquire() as conn:
            # First get the company's top CPV codes
            top_cpvs = await self.get_top_cpvs(company_name, company_tax_id, limit=5)
            if not top_cpvs:
                return []

            cpv_codes = [c['code'] for c in top_cpvs]

            # Find other winners in these CPV categories
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
                {
                    "name": row['company_name'],
                    "participations": row['participations'],
                    "wins": row['wins'],
                    "total_value": float(row['total_value'] or 0)
                }
                for row in rows
            ]

    async def get_missed_opportunities(
        self, company_name: str, company_tax_id: Optional[str] = None, days: int = 90, limit: int = 10
    ) -> List[Dict]:
        """Get tenders the company likely missed based on their CPV patterns"""
        async with self.pool.acquire() as conn:
            # Get company's CPV patterns
            top_cpvs = await self.get_top_cpvs(company_name, company_tax_id, limit=5)
            if not top_cpvs:
                return []

            cpv_codes = [c['code'] for c in top_cpvs]
            cutoff = datetime.utcnow() - timedelta(days=days)

            # Find tenders in their CPVs where they didn't participate
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

            rows = await conn.fetch(
                query, cpv_codes, cutoff, f"%{company_name}%", company_tax_id or "", limit
            )

            return [
                {
                    "tender_id": row['tender_id'],
                    "title": row['title'][:100] + "..." if len(row['title'] or "") > 100 else row['title'],
                    "buyer": row['procuring_entity'],
                    "deadline": row['closing_date'].strftime("%d.%m.%Y") if row['closing_date'] else "Н/А",
                    "value": float(row['actual_value_mkd'] or row['estimated_value_mkd'] or 0),
                    "cpv": get_cpv_name(row['cpv_code']),
                    "winner": row['winner'],
                    "match_reason": f"CPV совпаѓање ({row['cpv_code'][:8]})"
                }
                for row in rows
            ]

    async def get_expected_tenders(
        self, company_name: str, company_tax_id: Optional[str] = None
    ) -> Dict:
        """Estimate expected tenders in next 30 days based on historical patterns"""
        async with self.pool.acquire() as conn:
            # Get company's top CPVs
            top_cpvs = await self.get_top_cpvs(company_name, company_tax_id, limit=5)
            if not top_cpvs:
                return {"low": 0, "mid": 0, "high": 0, "confidence": "low"}

            cpv_codes = [c['code'] for c in top_cpvs]

            # Count tenders in last 12 months by month
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

            monthly_counts = [row['tender_count'] for row in rows]
            avg = sum(monthly_counts) / len(monthly_counts) if monthly_counts else 0

            return {
                "low": max(0, int(avg * 0.5)),
                "mid": int(avg),
                "high": int(avg * 1.5),
                "confidence": "medium" if len(monthly_counts) >= 6 else "low"
            }

    async def get_buyer_map(
        self, company_name: str, company_tax_id: Optional[str] = None, limit: int = 10
    ) -> List[Dict]:
        """Get top buyers in company's segment with their typical winners"""
        async with self.pool.acquire() as conn:
            top_cpvs = await self.get_top_cpvs(company_name, company_tax_id, limit=5)
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
                {
                    "name": row['procuring_entity'],
                    "tender_count": row['tender_count'],
                    "total_value": float(row['total_value'] or 0),
                    "top_winner": row['top_winner']
                }
                for row in rows
            ]


# ============================================================================
# REPORT HTML TEMPLATE
# ============================================================================

def generate_report_html(
    company_name: str,
    stats: Dict,
    top_cpvs: List[Dict],
    top_buyers: List[Dict],
    competitors: List[Dict],
    missed_opportunities: List[Dict],
    expected_tenders: Dict,
    buyer_map: List[Dict],
    checkout_url: str,
    unsubscribe_url: str
) -> str:
    """Generate the HTML content for the PDF report"""

    # Format stats
    win_rate = stats.get('win_rate', 0)
    total_value_formatted = format_value(stats.get('total_value_mkd', 0))

    # Build CPV list
    cpv_rows = ""
    for cpv in top_cpvs[:3]:
        cpv_rows += f"""
        <tr>
            <td>{cpv['name']}</td>
            <td style="text-align: center;">{cpv['count']}</td>
            <td style="text-align: center;">{cpv['wins']}</td>
            <td style="text-align: right;">{format_value(cpv['value_won'])}</td>
        </tr>
        """

    # Build buyers list
    buyer_rows = ""
    for buyer in top_buyers[:3]:
        buyer_rows += f"""
        <tr>
            <td>{buyer['name'][:40]}{'...' if len(buyer['name']) > 40 else ''}</td>
            <td style="text-align: center;">{buyer['count']}</td>
            <td style="text-align: center;">{buyer['wins']}</td>
        </tr>
        """

    # Build competitors list
    competitor_rows = ""
    for comp in competitors[:5]:
        competitor_rows += f"""
        <tr>
            <td>{comp['name'][:35]}{'...' if len(comp['name']) > 35 else ''}</td>
            <td style="text-align: center;">{comp['wins']}</td>
            <td style="text-align: right;">{format_value(comp['total_value'])}</td>
        </tr>
        """

    # Build missed opportunities list
    missed_rows = ""
    for opp in missed_opportunities[:10]:
        missed_rows += f"""
        <tr>
            <td>{opp['title'][:50]}{'...' if len(opp['title'] or '') > 50 else ''}</td>
            <td>{opp['buyer'][:25]}{'...' if len(opp['buyer'] or '') > 25 else ''}</td>
            <td style="text-align: center;">{opp['deadline']}</td>
            <td style="text-align: right;">{format_value(opp['value'])}</td>
            <td>{opp['cpv']}</td>
        </tr>
        """

    # Build buyer map
    buyer_map_rows = ""
    for bm in buyer_map[:10]:
        buyer_map_rows += f"""
        <tr>
            <td>{bm['name'][:35]}{'...' if len(bm['name']) > 35 else ''}</td>
            <td style="text-align: center;">{bm['tender_count']}</td>
            <td>{bm['top_winner'][:30] if bm['top_winner'] else 'Н/А'}{'...' if bm['top_winner'] and len(bm['top_winner']) > 30 else ''}</td>
        </tr>
        """

    # Expected tenders text
    expected_text = f"{expected_tenders['low']}-{expected_tenders['high']} тендери"
    confidence_text = {
        "low": "(ниска доверба)",
        "medium": "(средна доверба)",
        "high": "(висока доверба)"
    }.get(expected_tenders.get('confidence', 'low'), "")

    generated_date = datetime.utcnow().strftime("%d.%m.%Y")

    html = f"""
<!DOCTYPE html>
<html lang="mk">
<head>
    <meta charset="UTF-8">
    <title>Тендерски Извештај - {company_name}</title>
    <style>
        @page {{
            size: A4;
            margin: 1.5cm;
        }}
        body {{
            font-family: 'DejaVu Sans', Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            color: #333;
        }}
        .header {{
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            color: white;
            padding: 20px;
            margin: -1.5cm -1.5cm 20px -1.5cm;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 18pt;
        }}
        .header .company {{
            font-size: 14pt;
            margin-top: 5px;
            font-weight: normal;
        }}
        .header .date {{
            font-size: 9pt;
            margin-top: 10px;
            opacity: 0.8;
        }}
        h2 {{
            color: #1e3a5f;
            border-bottom: 2px solid #1e3a5f;
            padding-bottom: 5px;
            font-size: 12pt;
            margin-top: 25px;
        }}
        .metrics {{
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        .metric {{
            text-align: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            min-width: 120px;
            margin: 5px;
        }}
        .metric .value {{
            font-size: 24pt;
            font-weight: bold;
            color: #1e3a5f;
        }}
        .metric .label {{
            font-size: 9pt;
            color: #666;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            font-size: 9pt;
        }}
        th {{
            background: #1e3a5f;
            color: white;
            padding: 8px;
            text-align: left;
        }}
        td {{
            padding: 6px 8px;
            border-bottom: 1px solid #ddd;
        }}
        tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        .disclaimer {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 10px;
            font-size: 8pt;
            margin: 15px 0;
            border-radius: 4px;
        }}
        .cta-box {{
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 8px;
            margin: 25px 0;
        }}
        .cta-box h3 {{
            margin: 0 0 10px 0;
            font-size: 14pt;
        }}
        .cta-box p {{
            margin: 5px 0;
            font-size: 10pt;
        }}
        .cta-box .options {{
            margin-top: 15px;
            font-size: 9pt;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #ddd;
            font-size: 8pt;
            color: #666;
            text-align: center;
        }}
        .page-break {{
            page-break-before: always;
        }}
        .confidence {{
            font-size: 8pt;
            color: #666;
            font-style: italic;
        }}
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
    <div class="metric">
        <div class="value">{stats.get('participations_12m', 0)}</div>
        <div class="label">Учества</div>
    </div>
    <div class="metric">
        <div class="value">{stats.get('wins_12m', 0)}</div>
        <div class="label">Победи</div>
    </div>
    <div class="metric">
        <div class="value">{win_rate}%</div>
        <div class="label">Стапка на успех</div>
    </div>
    <div class="metric">
        <div class="value">{total_value_formatted}</div>
        <div class="label">Вкупна вредност</div>
    </div>
</div>

<h3>Топ CPV категории</h3>
<table>
    <tr>
        <th>Категорија</th>
        <th style="text-align: center;">Учества</th>
        <th style="text-align: center;">Победи</th>
        <th style="text-align: right;">Вредност</th>
    </tr>
    {cpv_rows if cpv_rows else '<tr><td colspan="4">Нема податоци</td></tr>'}
</table>

<h3>Топ договорни органи</h3>
<table>
    <tr>
        <th>Институција</th>
        <th style="text-align: center;">Тендери</th>
        <th style="text-align: center;">Победи</th>
    </tr>
    {buyer_rows if buyer_rows else '<tr><td colspan="3">Нема податоци</td></tr>'}
</table>

<h3>Конкурентски притисок</h3>
<table>
    <tr>
        <th>Конкурент</th>
        <th style="text-align: center;">Победи (12м)</th>
        <th style="text-align: right;">Вредност</th>
    </tr>
    {competitor_rows if competitor_rows else '<tr><td colspan="3">Нема податоци за конкуренти</td></tr>'}
</table>

<h3>Очекувани тендери (следни 30 дена)</h3>
<p>
    Врз основа на историски шаблони, очекуваме <strong>{expected_text}</strong>
    релевантни за вашите категории. <span class="confidence">{confidence_text}</span>
</p>

<div class="page-break"></div>

<h2>2. Пропуштени можности (последни 90 дена)</h2>

<div class="disclaimer">
    <strong>Напомена:</strong> Пропуштените можности се пресметани според совпаѓање на вашите
    историски CPV кодови и договорни органи. Ова не е гарантиран список.
</div>

<table>
    <tr>
        <th>Наслов</th>
        <th>Договорен орган</th>
        <th style="text-align: center;">Рок</th>
        <th style="text-align: right;">Вредност</th>
        <th>CPV</th>
    </tr>
    {missed_rows if missed_rows else '<tr><td colspan="5">Нема пропуштени тендери во овој период</td></tr>'}
</table>

<div class="page-break"></div>

<h2>3. Мапа на договорни органи и победници</h2>

<table>
    <tr>
        <th>Договорен орган</th>
        <th style="text-align: center;">Тендери (12м)</th>
        <th>Најчест победник</th>
    </tr>
    {buyer_map_rows if buyer_map_rows else '<tr><td colspan="3">Нема податоци</td></tr>'}
</table>

<div class="cta-box">
    <h3>Продолжете да го добивате овој извештај неделно + дневни известувања</h3>
    <p>Следете ги конкурентите, не пропуштајте релевантни тендери</p>
    <div class="options">
        <p><strong>Одговорете ФАКТУРА</strong> за активирање со фактура (EUR)</p>
        <p>или активирајте со картичка: <strong>{checkout_url}</strong></p>
    </div>
</div>

<div class="footer">
    <p>
        Овој извештај е генериран автоматски од NabavkiData врз основа на јавно достапни податоци
        од е-Набавки (e-nabavki.gov.mk).
    </p>
    <p>
        Ако не сакате да добивате вакви извештаи, одговорете СТОП или
        <a href="{unsubscribe_url}">кликнете тука за одјава</a>.
    </p>
    <p style="margin-top: 10px;">
        NabavkiData | nabavkidata.com | hello@nabavkidata.com
    </p>
</div>

</body>
</html>
"""
    return html


# ============================================================================
# PDF GENERATOR
# ============================================================================

class ReportGenerator:
    """Generates PDF reports for companies"""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.data_fetcher = ReportDataFetcher(pool)

    def generate_signed_url(self, report_id: str, valid_days: int = 14) -> Tuple[str, datetime]:
        """Generate a signed URL for report download"""
        expires = datetime.utcnow() + timedelta(days=valid_days)
        expires_ts = int(expires.timestamp())

        # Create signature
        data = f"{report_id}:{expires_ts}:{REPORT_SECRET}"
        signature = hashlib.sha256(data.encode()).hexdigest()[:16]

        url = f"{FRONTEND_URL}/api/report/{report_id}?expires={expires_ts}&sig={signature}"
        return url, expires

    def verify_signed_url(self, report_id: str, expires_ts: int, signature: str) -> bool:
        """Verify a signed URL"""
        if expires_ts < int(datetime.utcnow().timestamp()):
            return False

        data = f"{report_id}:{expires_ts}:{REPORT_SECRET}"
        expected_sig = hashlib.sha256(data.encode()).hexdigest()[:16]
        return hmac.compare_digest(signature, expected_sig)

    def generate_unsubscribe_token(self, email: str) -> str:
        """Generate unsubscribe token for email"""
        data = f"{email}:{REPORT_SECRET}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    def generate_unsubscribe_url(self, email: str) -> str:
        """Generate unsubscribe URL"""
        token = self.generate_unsubscribe_token(email)
        return f"{FRONTEND_URL}/unsubscribe?email={email}&token={token}"

    async def generate_report(
        self,
        company_name: str,
        company_tax_id: Optional[str] = None,
        company_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        email: Optional[str] = None,
        lookback_days: int = 365,
        missed_days: int = 90,
        report_valid_days: int = 14
    ) -> Dict:
        """Generate a complete PDF report for a company"""
        start_time = datetime.utcnow()
        report_id = str(uuid.uuid4())

        try:
            # Fetch all data
            stats = await self.data_fetcher.get_company_stats(company_name, company_tax_id, lookback_days)
            top_cpvs = await self.data_fetcher.get_top_cpvs(company_name, company_tax_id)
            top_buyers = await self.data_fetcher.get_top_buyers(company_name, company_tax_id)
            competitors = await self.data_fetcher.get_competitors(company_name, company_tax_id)
            missed_opportunities = await self.data_fetcher.get_missed_opportunities(
                company_name, company_tax_id, missed_days
            )
            expected_tenders = await self.data_fetcher.get_expected_tenders(company_name, company_tax_id)
            buyer_map = await self.data_fetcher.get_buyer_map(company_name, company_tax_id)

            # Generate URLs
            signed_url, expires_at = self.generate_signed_url(report_id, report_valid_days)
            unsubscribe_url = self.generate_unsubscribe_url(email) if email else f"{FRONTEND_URL}/unsubscribe"

            # Generate HTML
            html_content = generate_report_html(
                company_name=company_name,
                stats=stats,
                top_cpvs=top_cpvs,
                top_buyers=top_buyers,
                competitors=competitors,
                missed_opportunities=missed_opportunities,
                expected_tenders=expected_tenders,
                buyer_map=buyer_map,
                checkout_url=CHECKOUT_URL,
                unsubscribe_url=unsubscribe_url
            )

            # Generate PDF
            pdf_filename = f"report_{report_id}.pdf"
            pdf_path = os.path.join(REPORTS_DIR, pdf_filename)

            html = HTML(string=html_content)
            html.write_pdf(pdf_path)

            pdf_size = os.path.getsize(pdf_path)
            generation_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Store in database
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO generated_reports (
                        id, campaign_id, company_id, company_name, company_tax_id,
                        stats, missed_opportunities, competitor_data, buyer_data,
                        pdf_path, pdf_size_bytes, signed_url, signed_url_expires_at,
                        generation_time_ms
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                    uuid.UUID(report_id),
                    uuid.UUID(campaign_id) if campaign_id else None,
                    uuid.UUID(company_id) if company_id else None,
                    company_name,
                    company_tax_id,
                    json.dumps(stats),
                    json.dumps(missed_opportunities),
                    json.dumps(competitors),
                    json.dumps(buyer_map),
                    pdf_path,
                    pdf_size,
                    signed_url,
                    expires_at,
                    generation_time
                )

            return {
                "success": True,
                "report_id": report_id,
                "company_name": company_name,
                "pdf_path": pdf_path,
                "pdf_size_bytes": pdf_size,
                "signed_url": signed_url,
                "signed_url_expires_at": expires_at.isoformat(),
                "generation_time_ms": generation_time,
                "stats": stats,
                "missed_opportunities_count": len(missed_opportunities)
            }

        except Exception as e:
            logger.error(f"Error generating report for {company_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "company_name": company_name
            }


# ============================================================================
# BATCH REPORT GENERATION
# ============================================================================

async def generate_reports_for_campaign(
    pool: asyncpg.Pool,
    campaign_id: str,
    limit: int = 100
) -> Dict:
    """Generate reports for all targets in a campaign"""
    generator = ReportGenerator(pool)

    async with pool.acquire() as conn:
        # Get targets without reports
        targets = await conn.fetch("""
            SELECT id, company_name, company_tax_id, company_id, email
            FROM campaign_targets
            WHERE campaign_id = $1
              AND report_id IS NULL
              AND status = 'pending'
            ORDER BY created_at
            LIMIT $2
        """, uuid.UUID(campaign_id), limit)

    stats = {
        "total": len(targets),
        "success": 0,
        "failed": 0,
        "reports": []
    }

    for target in targets:
        result = await generator.generate_report(
            company_name=target['company_name'],
            company_tax_id=target['company_tax_id'],
            company_id=str(target['company_id']) if target['company_id'] else None,
            campaign_id=campaign_id,
            email=target['email']
        )

        if result.get('success'):
            stats['success'] += 1
            stats['reports'].append({
                "target_id": str(target['id']),
                "report_id": result['report_id'],
                "company_name": target['company_name']
            })

            # Update target with report ID
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE campaign_targets
                    SET report_id = $1, stats = $2, status = 'report_generated', updated_at = NOW()
                    WHERE id = $3
                """, uuid.UUID(result['report_id']), json.dumps(result['stats']), target['id'])
        else:
            stats['failed'] += 1
            logger.error(f"Failed to generate report for {target['company_name']}: {result.get('error')}")

        # Small delay to avoid overwhelming the system
        await asyncio.sleep(0.5)

    return stats

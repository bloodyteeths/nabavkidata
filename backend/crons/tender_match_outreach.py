#!/usr/bin/env python3
"""
Tender Match Outreach - Sends personalized tender recommendations to outreach leads.

Finds tenders created in the last 24 hours with status 'open', matches them
against outreach leads by industry keywords and CPV code prefixes, then sends
up to 3 matching tenders per lead via a personalized email.

Tracking: stores send records in the `raw_data` JSONB on `outreach_leads`
under the key 'tender_match_sends' (array of {date, tender_ids, message_id}).

Skips leads that are unsubscribed, bounced, or received a tender-match email
in the last 7 days.

Run: python3 crons/tender_match_outreach.py
     python3 crons/tender_match_outreach.py --dry-run
     python3 crons/tender_match_outreach.py --limit 20
Cron: 0 8 * * * cd /home/ubuntu/nabavkidata/backend && python3 crons/tender_match_outreach.py >> /var/log/nabavkidata/tender_match_outreach.log 2>&1
"""

import os
import sys
import asyncio
import json
import hashlib
import logging
import argparse
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

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
POSTMARK_API_TOKEN = os.getenv('POSTMARK_API_TOKEN')
if not POSTMARK_API_TOKEN:
    logger.error("POSTMARK_API_TOKEN not set in environment")
    sys.exit(1)

POSTMARK_FROM_EMAIL = 'hello@nabavkidata.com'
POSTMARK_FROM_NAME = 'Тамара од НабавкиДата'
POSTMARK_MESSAGE_STREAM = 'broadcast'
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://nabavkidata.com')
UNSUBSCRIBE_SECRET = os.getenv('UNSUBSCRIBE_SECRET', 'nabavki-unsub-secret-2025')

MAX_EMAILS_PER_RUN = 50
MAX_TENDERS_PER_EMAIL = 3
COOLDOWN_DAYS = 7
MIN_JITTER = 2   # seconds between sends
MAX_JITTER = 5


# =============================================================================
# HELPERS
# =============================================================================

def generate_unsubscribe_url(email: str) -> str:
    token = hashlib.sha256(f"{email}:{UNSUBSCRIBE_SECRET}".encode()).hexdigest()[:32]
    return f"{FRONTEND_URL}/unsubscribe?e={email}&t={token}"


def tender_url(tender_id: str) -> str:
    """Convert tender_id like '12345/2024' to URL path '/tenders/12345-2024'."""
    slug = tender_id.replace('/', '-')
    return f"{FRONTEND_URL}/tenders/{slug}"


def format_value_mkd(value) -> str:
    """Format MKD value for display, e.g. 1,500,000 МКД."""
    if not value:
        return "Не е наведено"
    try:
        v = int(value)
        return f"{v:,} МКД".replace(",", ".")
    except (ValueError, TypeError):
        return str(value)


def format_date(dt) -> str:
    """Format a date for display."""
    if not dt:
        return "Не е наведено"
    if hasattr(dt, 'strftime'):
        return dt.strftime('%d.%m.%Y')
    return str(dt)


# =============================================================================
# INDUSTRY KEYWORD MAP
# =============================================================================

# Maps common company_industry values to Macedonian keywords for tender title matching.
# Both Cyrillic and Latin variants included for bilingual matching.
INDUSTRY_KEYWORDS = {
    # IT / Software
    "IT": ["ИТ", "софтвер", "информатички", "компјутер", "лаптоп", "сервер", "мрежна", "IT", "software", "хардвер"],
    "информатичка технологија": ["ИТ", "софтвер", "информатички", "компјутер", "лаптоп", "сервер", "мрежна", "хардвер"],
    "софтвер": ["софтвер", "информатички", "ИТ", "software", "апликација", "систем"],
    # Construction
    "градежништво": ["градежни", "градба", "реконструкција", "асфалт", "бетон", "изградба", "санација"],
    "градежни работи": ["градежни", "градба", "реконструкција", "асфалт", "бетон", "изградба", "санација"],
    # Medical
    "медицина": ["медицинск", "лекови", "фармацевтск", "здравствен", "болнички", "лабораториск"],
    "фармација": ["лекови", "фармацевтск", "медицинск", "здравствен"],
    "медицинска опрема": ["медицинск", "болнички", "хируршк", "лабораториск", "дијагностик"],
    # Food
    "прехранбена индустрија": ["прехранбен", "храна", "месо", "млеко", "пекарск", "кетеринг"],
    "храна": ["храна", "прехранбен", "кетеринг", "исхрана", "месо"],
    # Cleaning / Laundry
    "хигиена": ["хигиена", "чистење", "средства за чистење", "дезинфекц"],
    "перење": ["перење", "пеглање", "хигиена", "перална"],
    # Security
    "безбедност": ["обезбедување", "безбедност", "видео надзор", "аларм", "чување"],
    "обезбедување": ["обезбедување", "безбедност", "физичко обезбедување", "чување"],
    # Transport
    "транспорт": ["транспорт", "превоз", "возил", "гориво", "логистик"],
    # Printing
    "печатење": ["печатење", "печатарск", "печатница", "тонер", "канцелариск"],
    # Electrical
    "електрика": ["електрични", "електро", "електрична енергија", "кабел", "осветлување"],
    # General services
    "консултантски услуги": ["консултантск", "советодавн", "студија", "анализа", "проект"],
    "проектирање": ["проектирање", "проект", "надзор", "техничк"],
}


def get_keywords_for_industry(industry: str) -> List[str]:
    """Get matching keywords for an industry string.

    Tries exact match first, then substring match on keys, then falls back
    to using the industry string itself as a keyword.
    """
    if not industry:
        return []

    industry_lower = industry.lower().strip()

    # Exact match
    for key, keywords in INDUSTRY_KEYWORDS.items():
        if key.lower() == industry_lower:
            return keywords

    # Substring match (e.g. "медицинска опрема и инструменти" matches "медицинска опрема")
    for key, keywords in INDUSTRY_KEYWORDS.items():
        if key.lower() in industry_lower or industry_lower in key.lower():
            return keywords

    # Fallback: use the industry string itself as keyword (min 3 chars)
    if len(industry) >= 3:
        return [industry]

    return []


# =============================================================================
# MATCHING LOGIC
# =============================================================================

def match_tender_to_lead(
    tender: dict,
    lead_industry: str,
    lead_cpv_prefixes: List[str],
) -> Tuple[bool, str]:
    """Check if a tender matches a lead. Returns (matched, reason)."""
    tender_title = (tender.get('title') or '').lower()
    tender_cpv = tender.get('cpv_code') or ''

    # CPV prefix matching (more precise)
    if lead_cpv_prefixes and tender_cpv:
        for prefix in lead_cpv_prefixes:
            if tender_cpv.startswith(prefix):
                return True, f"CPV {prefix}"

    # Keyword matching against tender title
    keywords = get_keywords_for_industry(lead_industry)
    for kw in keywords:
        if kw.lower() in tender_title:
            return True, f"клучен збор: {kw}"

    return False, ""


async def get_new_tenders(conn) -> List[dict]:
    """Fetch tenders created in the last 24 hours with status open."""
    rows = await conn.fetch("""
        SELECT tender_id, title, procuring_entity, estimated_value_mkd,
               closing_date, cpv_code, status, created_at
        FROM tenders
        WHERE created_at >= NOW() - INTERVAL '24 hours'
          AND status = 'active'
        ORDER BY estimated_value_mkd DESC NULLS LAST
    """)
    return [dict(r) for r in rows]


async def get_eligible_leads(conn, limit: int) -> List[dict]:
    """Fetch outreach leads eligible for tender-match emails.

    Excludes:
    - unsubscribed, bounced leads
    - leads without company_industry
    - leads that received a tender-match email in the last 7 days
    """
    rows = await conn.fetch("""
        SELECT ol.lead_id, ol.email, ol.company_name, ol.company_industry,
               ol.raw_data, ol.outreach_status
        FROM outreach_leads ol
        WHERE ol.company_industry IS NOT NULL
          AND ol.company_industry <> ''
          AND ol.outreach_status NOT IN ('unsubscribed', 'bounced', 'do_not_contact')
          AND ol.is_bounced IS NOT TRUE
          AND NOT EXISTS (
              SELECT 1 FROM suppression_list sl WHERE sl.email = LOWER(ol.email)
          )
          AND NOT EXISTS (
              SELECT 1 FROM campaign_unsubscribes cu WHERE cu.email = LOWER(ol.email)
          )
        ORDER BY ol.quality_score DESC NULLS LAST, ol.lead_id
        LIMIT $1
    """, limit * 3)  # fetch extra because many won't match or will be in cooldown
    return [dict(r) for r in rows]


async def get_supplier_cpv_prefixes(conn, company_name: str) -> List[str]:
    """Get CPV code prefixes from the suppliers table for a company."""
    if not company_name:
        return []
    row = await conn.fetchrow("""
        SELECT industries FROM suppliers
        WHERE LOWER(company_name) = LOWER($1)
        LIMIT 1
    """, company_name)
    if not row or not row['industries']:
        return []

    industries = row['industries']
    if isinstance(industries, str):
        try:
            industries = json.loads(industries)
        except (json.JSONDecodeError, TypeError):
            return []

    # Extract first 2 digits of each CPV code as prefix for broader matching
    prefixes = set()
    for cpv in industries:
        if isinstance(cpv, str) and len(cpv) >= 2:
            prefixes.add(cpv[:2])
    return list(prefixes)


def is_in_cooldown(raw_data, cooldown_days: int = COOLDOWN_DAYS) -> bool:
    """Check if lead received a tender-match email within the cooldown period."""
    if not raw_data:
        return False
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except (json.JSONDecodeError, TypeError):
            return False
    sends = raw_data.get('tender_match_sends', [])
    if not sends:
        return False
    cutoff = (datetime.utcnow() - timedelta(days=cooldown_days)).isoformat()
    for send in sends:
        if send.get('date', '') > cutoff:
            return True
    return False


# =============================================================================
# EMAIL TEMPLATE
# =============================================================================

def build_tender_match_email(
    company_name: str,
    industry: str,
    tenders: List[dict],
    match_reasons: List[str],
    email: str,
) -> Dict:
    """Build personalized tender match email HTML and text."""
    unsub_url = generate_unsubscribe_url(email)
    company_display = company_name or "Вашата компанија"
    industry_display = industry or "вашата дејност"

    # Build tender rows for HTML
    tender_rows_html = ""
    tender_rows_text = ""
    for i, t in enumerate(tenders):
        url = tender_url(t['tender_id'])
        title = t.get('title') or 'Без наслов'
        entity = t.get('procuring_entity') or 'Не е наведено'
        value = format_value_mkd(t.get('estimated_value_mkd'))
        closing = format_date(t.get('closing_date'))

        tender_rows_html += f"""
        <tr>
            <td style="padding:12px 15px; border-bottom:1px solid #eee;">
                <a href="{url}" style="color:#2563eb; text-decoration:none; font-weight:bold;">{title}</a><br>
                <span style="font-size:14px; color:#555;">{entity}</span>
            </td>
            <td style="padding:12px 15px; border-bottom:1px solid #eee; text-align:right; white-space:nowrap;">
                <strong>{value}</strong><br>
                <span style="font-size:13px; color:#888;">Рок: {closing}</span>
            </td>
        </tr>"""

        tender_rows_text += f"\n{i+1}. {title}\n   Институција: {entity}\n   Вредност: {value}\n   Рок: {closing}\n   Линк: {url}\n"

    subject = f"Нови тендери за {industry_display} - НабавкиДата"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Почитувани,</p>

        <p>Пронајдовме <strong>{len(tenders)} нови тендери</strong> релевантни за <strong>{company_display}</strong> во категоријата <strong>{industry_display}</strong>.</p>

        <table style="width:100%; border-collapse:collapse; margin:20px 0; border:1px solid #e5e7eb; border-radius:8px;">
            <thead>
                <tr style="background:#f8fafc;">
                    <th style="padding:10px 15px; text-align:left; border-bottom:2px solid #e5e7eb; font-size:14px; color:#666;">Тендер</th>
                    <th style="padding:10px 15px; text-align:right; border-bottom:2px solid #e5e7eb; font-size:14px; color:#666;">Вредност / Рок</th>
                </tr>
            </thead>
            <tbody>
                {tender_rows_html}
            </tbody>
        </table>

        <p>Кликнете на тендерот за целосна документација, услови и детали.</p>

        <p>&nbsp;</p>

        <p style="background:#f0f9ff; padding:15px; border-radius:8px; border-left:4px solid #2563eb;">
            Сакате автоматски известувања за секој нов тендер од вашата дејност?<br><br>
            <a href="{FRONTEND_URL}/auth/register?ref=tender-match" style="background:#2563eb; color:white; padding:10px 20px; border-radius:5px; text-decoration:none; display:inline-block;">Регистрирајте се бесплатно</a>
        </p>

        <p>&nbsp;</p>

        <p>Ако имате прашања — одговорете на овој мејл или јавете се на 070 253 467.</p>

        <p>Поздрав,<br>Тамара<br>NabavkiData</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

        <p style="font-size:12px; color:#666666;">
            TAMSAR INC | hello@nabavkidata.com<br>
            <a href="{unsub_url}" style="color:#666666;">Одјава од маркетинг пораки</a> |
            Одговорете СТОП за одјава
        </p>

    </div>
</body>
</html>"""

    text = f"""Почитувани,

Пронајдовме {len(tenders)} нови тендери релевантни за {company_display} во категоријата {industry_display}.
{tender_rows_text}
Кликнете на линкот за целосна документација, услови и детали.

Сакате автоматски известувања за секој нов тендер од вашата дејност?
Регистрирајте се бесплатно: {FRONTEND_URL}/auth/register?ref=tender-match

Ако имате прашања — одговорете на овој мејл или јавете се на 070 253 467.

Поздрав,
Тамара, NabavkiData

---
Одговорете СТОП за одјава или посетете: {unsub_url}"""

    return {
        "subject": subject,
        "html": html,
        "text": text,
    }


# =============================================================================
# SENDING
# =============================================================================

async def send_tender_match_email(
    client: httpx.AsyncClient,
    email: str,
    template: Dict,
    lead_id: int,
    industry: str,
    dry_run: bool = False,
) -> dict:
    """Send a single tender-match email via Postmark."""
    if dry_run:
        return {"dry_run": True, "subject": template["subject"]}

    unsub_url = generate_unsubscribe_url(email)

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
            "Tag": "tender-match",
            "Headers": [
                {"Name": "List-Unsubscribe", "Value": f"<{unsub_url}>"},
                {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"}
            ],
            "Metadata": {
                "lead_id": str(lead_id),
                "type": "tender_match",
                "industry": (industry or "")[:50]
            }
        },
        timeout=30.0
    )

    if response.status_code == 200:
        return {"success": True, "message_id": response.json().get("MessageID")}
    else:
        return {"success": False, "error": response.text}


# =============================================================================
# TRACKING
# =============================================================================

async def record_send(conn, lead_id: int, tender_ids: List[str], message_id: Optional[str]):
    """Record the send in the lead's raw_data JSONB under 'tender_match_sends'."""
    row = await conn.fetchrow(
        "SELECT raw_data FROM outreach_leads WHERE lead_id = $1", lead_id
    )
    raw_data = {}
    if row and row['raw_data']:
        rd = row['raw_data']
        if isinstance(rd, str):
            try:
                raw_data = json.loads(rd)
            except (json.JSONDecodeError, TypeError):
                raw_data = {}
        elif isinstance(rd, dict):
            raw_data = rd
        else:
            raw_data = {}

    sends = raw_data.get('tender_match_sends', [])
    sends.append({
        'date': datetime.utcnow().isoformat(),
        'tender_ids': tender_ids,
        'message_id': message_id,
    })
    raw_data['tender_match_sends'] = sends

    await conn.execute("""
        UPDATE outreach_leads
        SET raw_data = $1::jsonb,
            last_contact_at = NOW(),
            updated_at = NOW()
        WHERE lead_id = $2
    """, json.dumps(raw_data), lead_id)


# =============================================================================
# MAIN
# =============================================================================

async def process_tender_matches(args):
    """Main processing loop."""
    logger.info("=" * 60)
    logger.info("TENDER MATCH OUTREACH")
    logger.info(f"Time: {datetime.utcnow().isoformat()}")
    logger.info(f"Max emails: {args.limit}")
    if args.dry_run:
        logger.info("*** DRY RUN — no emails will be sent ***")
    logger.info("=" * 60)

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Step 1: Get new tenders from last 24 hours
        new_tenders = await get_new_tenders(conn)
        logger.info(f"Found {len(new_tenders)} new active tenders in last 24 hours")

        if not new_tenders:
            logger.info("No new tenders — nothing to send")
            return

        # Log a sample
        for t in new_tenders[:5]:
            logger.info(f"  Tender: {t['tender_id']} — {(t['title'] or '')[:60]}")
        if len(new_tenders) > 5:
            logger.info(f"  ... and {len(new_tenders) - 5} more")

        # Step 2: Get eligible leads
        leads = await get_eligible_leads(conn, args.limit)
        logger.info(f"Fetched {len(leads)} eligible leads with industry data")

        if not leads:
            logger.info("No eligible leads — nothing to send")
            return

        # Step 3: Match tenders to leads and send
        sent = 0
        skipped_cooldown = 0
        skipped_no_match = 0
        errors = 0

        async with httpx.AsyncClient() as client:
            for lead in leads:
                if sent >= args.limit:
                    logger.info(f"Reached send limit ({args.limit})")
                    break

                lead_id = lead['lead_id']
                email = lead['email']
                company = lead['company_name'] or ''
                industry = lead['company_industry'] or ''

                # Check cooldown
                if is_in_cooldown(lead.get('raw_data')):
                    skipped_cooldown += 1
                    continue

                # Get CPV prefixes from suppliers table
                cpv_prefixes = await get_supplier_cpv_prefixes(conn, company)

                # Find matching tenders
                matched_tenders = []
                match_reasons = []
                for t in new_tenders:
                    matched, reason = match_tender_to_lead(t, industry, cpv_prefixes)
                    if matched:
                        matched_tenders.append(t)
                        match_reasons.append(reason)
                    if len(matched_tenders) >= MAX_TENDERS_PER_EMAIL:
                        break

                if not matched_tenders:
                    skipped_no_match += 1
                    continue

                # Build and send email
                template = build_tender_match_email(
                    company, industry, matched_tenders, match_reasons, email
                )

                result = await send_tender_match_email(
                    client, email, template, lead_id, industry, args.dry_run
                )

                if result.get('success') or result.get('dry_run'):
                    sent += 1
                    tender_ids = [t['tender_id'] for t in matched_tenders]

                    if not args.dry_run:
                        await record_send(
                            conn, lead_id, tender_ids,
                            result.get('message_id')
                        )

                    logger.info(
                        f"  {'[DRY]' if args.dry_run else 'SENT'} "
                        f"{email} ({company[:25]}) — "
                        f"{len(matched_tenders)} tenders ({industry[:20]})"
                    )
                else:
                    errors += 1
                    error_msg = (result.get('error') or 'Unknown')[:80]
                    logger.error(f"  FAIL {email}: {error_msg}")

                    # Mark bounced if permanent failure
                    error_lower = (result.get('error') or '').lower()
                    if any(w in error_lower for w in ['inactive', 'bounce', 'invalid']):
                        await conn.execute("""
                            UPDATE outreach_leads
                            SET outreach_status = 'bounced',
                                is_bounced = true,
                                bounced_at = NOW(),
                                updated_at = NOW()
                            WHERE lead_id = $1
                        """, lead_id)

                # Jitter between sends
                if not args.dry_run and sent < args.limit:
                    jitter = random.uniform(MIN_JITTER, MAX_JITTER)
                    await asyncio.sleep(jitter)

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"COMPLETE: {sent} sent, {errors} errors")
        logger.info(f"  Skipped (cooldown): {skipped_cooldown}")
        logger.info(f"  Skipped (no match): {skipped_no_match}")
        logger.info("=" * 60)

    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description='Tender match outreach — send personalized tender recommendations')
    parser.add_argument('--dry-run', action='store_true', help='Preview matches without sending emails')
    parser.add_argument('--limit', type=int, default=MAX_EMAILS_PER_RUN, help=f'Max emails per run (default: {MAX_EMAILS_PER_RUN})')
    args = parser.parse_args()

    await process_tender_matches(args)


if __name__ == '__main__':
    asyncio.run(main())

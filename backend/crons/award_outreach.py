#!/usr/bin/env python3
"""
Award Outreach - Competitive Intelligence Emails

When a tender is awarded, finds outreach leads whose companies have previously
bid on similar tenders (same CPV code prefix or similar title keywords) and
sends a "competitive intelligence" email notifying them of the award.

Goal: drive registrations by showing leads that their competitors are winning
tenders they could be bidding on.

Run: python3 crons/award_outreach.py --dry-run
     python3 crons/award_outreach.py --limit 10
Cron: Every 6 hours
      0 */6 * * * cd /home/ubuntu/nabavkidata/backend && python3 crons/award_outreach.py >> /var/log/nabavkidata/award_outreach.log 2>&1
"""

import os
import sys
import json
import asyncio
import hashlib
import logging
import argparse
import random
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

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
POSTMARK_FROM_EMAIL = 'hello@nabavkidata.com'
POSTMARK_FROM_NAME = 'Тамара од НабавкиДата'
POSTMARK_MESSAGE_STREAM = 'broadcast'
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://nabavkidata.com')
UNSUBSCRIBE_SECRET = os.getenv('UNSUBSCRIBE_SECRET', 'nabavki-unsub-secret-2025')

MAX_EMAILS_PER_RUN = 30
MIN_JITTER = 2    # seconds between sends
MAX_JITTER = 5

# Stop words to exclude from title keyword extraction (Macedonian + common)
STOP_WORDS = {
    'за', 'на', 'од', 'во', 'со', 'до', 'и', 'или', 'не', 'се', 'е',
    'ќе', 'да', 'по', 'при', 'без', 'кон', 'низ', 'над', 'под', 'меѓу',
    'набавка', 'јавна', 'тендер', 'оглас', 'договор', 'рамковен',
    'потреби', 'потребите', 'услуги', 'работи', 'стоки', 'добра',
    'the', 'for', 'and', 'of', 'to', 'in', 'with', 'from',
}


def generate_unsubscribe_url(email: str) -> str:
    """Generate HMAC-based unsubscribe URL."""
    token = hashlib.sha256(f"{email}:{UNSUBSCRIBE_SECRET}".encode()).hexdigest()[:32]
    return f"{FRONTEND_URL}/unsubscribe?e={email}&t={token}"


def tender_url(tender_id: str) -> str:
    """Convert tender_id like '12345/2025' to frontend URL path."""
    slug = tender_id.replace('/', '-')
    return f"{FRONTEND_URL}/tenders/{slug}"


def format_value(value) -> str:
    """Format MKD value with thousands separator."""
    if value is None:
        return "непознато"
    try:
        v = int(float(value))
        # Format with dots as thousands separators (Macedonian style)
        formatted = f"{v:,}".replace(",", ".")
        return f"{formatted} МКД"
    except (ValueError, TypeError):
        return "непознато"


def extract_title_keywords(title: str) -> List[str]:
    """Extract meaningful keywords from a tender title for similarity matching."""
    if not title:
        return []
    # Remove punctuation, split into words
    words = re.findall(r'[\w]+', title.lower(), re.UNICODE)
    # Filter: at least 4 chars, not a stop word, not all digits
    keywords = [
        w for w in words
        if len(w) >= 4 and w not in STOP_WORDS and not w.isdigit()
    ]
    return keywords[:8]  # Max 8 keywords


def build_award_email(
    tender_title: str,
    tender_id: str,
    winner: str,
    value_display: str,
    company_name: str,
    unsub_url: str,
) -> Dict:
    """Build competitive intelligence email for an awarded tender."""
    t_url = tender_url(tender_id)

    subject = f"{winner} победи на тендер — дали конкурирате?"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Почитувани,</p>

        <p>Тендер од вашата област токму беше доделен:</p>

        <div style="background:#f0f9ff; padding:20px; border-radius:8px; border-left:4px solid #2563eb; margin:20px 0;">
            <p style="margin:0 0 8px 0; font-size:14px; color:#666;">Тендер:</p>
            <p style="margin:0 0 12px 0; font-weight:bold;">{tender_title}</p>
            <p style="margin:0 0 4px 0;"><strong>Победник:</strong> {winner}</p>
            <p style="margin:0 0 4px 0;"><strong>Вредност:</strong> {value_display}</p>
            <p style="margin:0;">
                <a href="{t_url}?ref=award-email" style="color:#2563eb; text-decoration:underline;">Погледни детали</a>
            </p>
        </div>

        <p>Компании од вашата дејност редовно учествуваат на вакви тендери. Следниот може да биде ваш.</p>

        <p>Со <strong>НабавкиДата</strong> добивате:</p>
        <ul style="padding-left:20px;">
            <li>Известувања штом се објави нов тендер во вашата област</li>
            <li>Анализа на конкуренти — кој колку често победува</li>
            <li>Историски цени — знаете колку да понудите</li>
        </ul>

        <p style="text-align:center; margin:25px 0;">
            <a href="{FRONTEND_URL}/auth/register?ref=award-outreach" style="display:inline-block; background:#1e3a5f; color:white; padding:14px 28px; border-radius:5px; text-decoration:none; font-weight:bold;">Регистрирајте се бесплатно</a>
        </p>

        <p>Регистрацијата е бесплатна. Нема обврска.</p>

        <p>Поздрав,<br>Тамара<br>NabavkiData</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">
        <p style="font-size:12px; color:#666666;">
            TAMSAR INC | hello@nabavkidata.com<br>
            <a href="{unsub_url}" style="color:#666666;">Отпиши се од маркетинг пораки</a> |
            Одговорете СТОП за одјава
        </p>

    </div>
</body>
</html>"""

    text = f"""Почитувани,

Тендер од вашата област токму беше доделен:

Тендер: {tender_title}
Победник: {winner}
Вредност: {value_display}
Детали: {t_url}?ref=award-email

Компании од вашата дејност редовно учествуваат на вакви тендери. Следниот може да биде ваш.

Со НабавкиДата добивате:
- Известувања штом се објави нов тендер во вашата област
- Анализа на конкуренти — кој колку често победува
- Историски цени — знаете колку да понудите

Регистрирајте се бесплатно: {FRONTEND_URL}/auth/register?ref=award-outreach

Регистрацијата е бесплатна. Нема обврска.

Поздрав,
Тамара, NabavkiData

---
Отпиши се: {unsub_url}
Одговорете СТОП за одјава"""

    return {"subject": subject, "html": html, "text": text}


# =============================================================================
# SUPPRESSION CHECKS
# =============================================================================

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


async def already_sent_for_tender(conn, lead_id, tender_id: str) -> bool:
    """Check if we already sent an award email for this tender to this lead.
    Uses the raw_data JSONB field on outreach_leads."""
    raw = await conn.fetchval(
        "SELECT raw_data FROM outreach_leads WHERE lead_id = $1", lead_id
    )
    if not raw:
        return False
    if isinstance(raw, str):
        raw = json.loads(raw)
    award_emails = raw.get('award_emails_sent', [])
    return any(entry.get('tender_id') == tender_id for entry in award_emails)


async def record_award_email(conn, lead_id, tender_id: str):
    """Record that we sent an award email for this tender to this lead."""
    raw = await conn.fetchval(
        "SELECT raw_data FROM outreach_leads WHERE lead_id = $1", lead_id
    )
    if raw is None:
        data = {}
    elif isinstance(raw, str):
        data = json.loads(raw) if raw else {}
    else:
        data = dict(raw)

    award_emails = data.get('award_emails_sent', [])
    award_emails.append({
        'tender_id': tender_id,
        'sent_at': datetime.utcnow().isoformat(),
    })
    data['award_emails_sent'] = award_emails

    await conn.execute(
        "UPDATE outreach_leads SET raw_data = $1::jsonb, updated_at = NOW() WHERE lead_id = $2",
        json.dumps(data, ensure_ascii=False),
        lead_id,
    )


# =============================================================================
# CORE LOGIC
# =============================================================================

async def find_recently_awarded(conn, hours: int = 48) -> List[dict]:
    """Find tenders awarded in the last N hours."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    rows = await conn.fetch("""
        SELECT tender_id, title, winner, cpv_code,
               estimated_value_mkd, actual_value_mkd,
               category, procuring_entity
        FROM tenders
        WHERE status = 'awarded'
          AND winner IS NOT NULL
          AND winner <> ''
          AND scraped_at >= $1
        ORDER BY scraped_at DESC
        LIMIT 200
    """, cutoff)
    return [dict(r) for r in rows]


async def find_competitor_leads(
    conn,
    tender: dict,
    exclude_winner: str,
    limit: int = 10,
) -> List[dict]:
    """Find outreach leads whose companies bid on similar tenders.

    Matching strategy (in priority order):
    1. CPV code prefix match (first 5 digits) — companies that bid on same CPV
    2. Title keyword overlap — companies that bid on tenders with similar titles

    Returns leads with valid emails that haven't been sent this tender's award email.
    """
    leads = []
    seen_emails = set()
    cpv = tender.get('cpv_code')
    title = tender.get('title', '')

    # Strategy 1: CPV code prefix match
    # Find companies that have won or bid on tenders with the same CPV prefix
    if cpv and len(cpv) >= 5:
        cpv_prefix = cpv[:5]
        cpv_leads = await conn.fetch("""
            SELECT DISTINCT ol.lead_id, ol.email, ol.company_name,
                   ol.company_industry, ol.outreach_status, ol.raw_data
            FROM outreach_leads ol
            WHERE ol.outreach_status NOT IN ('bounced', 'complained', 'unsubscribed')
              AND ol.email IS NOT NULL
              AND ol.company_name IS NOT NULL
              AND UPPER(ol.company_name) <> UPPER($1)
              AND EXISTS (
                  SELECT 1 FROM tenders t
                  WHERE t.winner ILIKE '%' || ol.company_name || '%'
                    AND t.cpv_code LIKE $2 || '%'
                    AND t.tender_id <> $3
              )
            LIMIT $4
        """, exclude_winner, cpv_prefix, tender['tender_id'], limit)

        for row in cpv_leads:
            email = row['email'].lower()
            if email not in seen_emails:
                seen_emails.add(email)
                leads.append(dict(row))

    # Strategy 2: Title keyword overlap
    # Find companies that won tenders with similar keywords in the title
    if len(leads) < limit:
        keywords = extract_title_keywords(title)
        if keywords:
            # Use top 3 keywords for matching
            for kw in keywords[:3]:
                if len(leads) >= limit:
                    break
                kw_leads = await conn.fetch("""
                    SELECT DISTINCT ol.lead_id, ol.email, ol.company_name,
                           ol.company_industry, ol.outreach_status, ol.raw_data
                    FROM outreach_leads ol
                    WHERE ol.outreach_status NOT IN ('bounced', 'complained', 'unsubscribed')
                      AND ol.email IS NOT NULL
                      AND ol.company_name IS NOT NULL
                      AND UPPER(ol.company_name) <> UPPER($1)
                      AND EXISTS (
                          SELECT 1 FROM tenders t
                          WHERE t.winner ILIKE '%' || ol.company_name || '%'
                            AND t.title ILIKE '%' || $2 || '%'
                            AND t.tender_id <> $3
                      )
                    LIMIT $4
                """, exclude_winner, kw, tender['tender_id'], limit - len(leads))

                for row in kw_leads:
                    email = row['email'].lower()
                    if email not in seen_emails:
                        seen_emails.add(email)
                        leads.append(dict(row))

    return leads[:limit]


async def send_award_email(
    client: httpx.AsyncClient,
    lead: dict,
    tender: dict,
    dry_run: bool = False,
) -> dict:
    """Send a single award outreach email via Postmark."""
    email = lead['email']
    company = lead['company_name'] or ''
    winner = tender['winner']
    title = tender['title']
    value = tender.get('actual_value_mkd') or tender.get('estimated_value_mkd')
    value_display = format_value(value)
    unsub_url = generate_unsubscribe_url(email)

    template = build_award_email(
        tender_title=title,
        tender_id=tender['tender_id'],
        winner=winner,
        value_display=value_display,
        company_name=company,
        unsub_url=unsub_url,
    )

    if dry_run:
        return {
            "dry_run": True,
            "email": email,
            "company": company,
            "winner": winner,
            "tender_id": tender['tender_id'],
            "subject": template["subject"],
        }

    response = await client.post(
        "https://api.postmarkapp.com/email",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": POSTMARK_API_TOKEN,
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
            "Tag": "award-outreach",
            "Headers": [
                {"Name": "List-Unsubscribe", "Value": f"<{unsub_url}>"},
                {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"},
            ],
            "Metadata": {
                "lead_id": str(lead['lead_id']),
                "tender_id": tender['tender_id'],
                "winner": winner[:50],
                "company": company[:50],
            },
        },
        timeout=30.0,
    )

    if response.status_code == 200:
        return {"success": True, "message_id": response.json().get("MessageID")}
    else:
        return {"success": False, "error": response.text}


# =============================================================================
# MAIN
# =============================================================================

async def process_award_outreach(args):
    """Main processing loop."""
    logger.info("=" * 60)
    logger.info("AWARD OUTREACH — COMPETITIVE INTELLIGENCE")
    logger.info(f"Time: {datetime.utcnow().isoformat()}")
    logger.info(f"Limit: {args.limit} emails per run")
    if args.dry_run:
        logger.info("*** DRY RUN — no emails will be sent ***")
    logger.info("=" * 60)

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # 1. Find recently awarded tenders
        awarded = await find_recently_awarded(conn, hours=48)
        logger.info(f"Found {len(awarded)} tenders awarded in last 48 hours")

        if not awarded:
            logger.info("No recently awarded tenders found, exiting")
            return

        total_sent = 0
        total_skipped = 0
        total_errors = 0

        async with httpx.AsyncClient() as client:
            for tender in awarded:
                if total_sent >= args.limit:
                    logger.info(f"Reached limit of {args.limit} emails, stopping")
                    break

                tid = tender['tender_id']
                winner = tender['winner']
                logger.info(f"\nTender: {tid} — Winner: {winner}")
                logger.info(f"  Title: {tender['title'][:80]}")
                logger.info(f"  CPV: {tender.get('cpv_code', 'N/A')}")

                # 2. Find competitor leads for this tender
                remaining = args.limit - total_sent
                leads = await find_competitor_leads(
                    conn, tender, exclude_winner=winner, limit=min(remaining, 5)
                )
                logger.info(f"  Found {len(leads)} competitor leads")

                if not leads:
                    continue

                for lead in leads:
                    if total_sent >= args.limit:
                        break

                    email = lead['email']
                    lead_id = lead['lead_id']

                    # Skip if already sent for this tender
                    if await already_sent_for_tender(conn, lead_id, tid):
                        logger.info(f"    SKIP (already sent): {email}")
                        total_skipped += 1
                        continue

                    # Skip if suppressed
                    if not args.dry_run and await is_suppressed(conn, email):
                        logger.info(f"    SKIP (suppressed): {email}")
                        total_skipped += 1
                        continue

                    # Skip if already a registered user
                    is_user = await conn.fetchval(
                        "SELECT 1 FROM users WHERE LOWER(email) = LOWER($1)", email
                    )
                    if is_user:
                        logger.info(f"    SKIP (registered user): {email}")
                        total_skipped += 1
                        continue

                    # Send email
                    result = await send_award_email(client, lead, tender, args.dry_run)

                    if result.get('success') or result.get('dry_run'):
                        total_sent += 1

                        if not args.dry_run:
                            # Record in raw_data
                            await record_award_email(conn, lead_id, tid)

                            # Log to outreach_emails
                            await conn.execute("""
                                INSERT INTO outreach_emails (
                                    lead_id, email_sequence, subject, sent_at
                                ) VALUES ($1, 0, $2, NOW())
                            """, lead_id, result.get('subject', f'Award: {tid}'))

                        logger.info(
                            f"    {'[DRY]' if args.dry_run else 'SENT'} "
                            f"{email} ({lead['company_name'][:30]})"
                        )
                    else:
                        total_errors += 1
                        error_msg = result.get('error', 'Unknown')[:80]
                        logger.error(f"    FAIL {email}: {error_msg}")

                        # Mark bounced on permanent failures
                        error_lower = result.get('error', '').lower()
                        if any(x in error_lower for x in ['inactive', 'bounce', 'illegal']):
                            await conn.execute("""
                                UPDATE outreach_leads
                                SET outreach_status = 'bounced',
                                    updated_at = NOW()
                                WHERE lead_id = $1
                            """, lead_id)
                            await conn.execute("""
                                INSERT INTO suppression_list (email, reason, source)
                                VALUES ($1, 'bounce', 'award_outreach')
                                ON CONFLICT (email) DO NOTHING
                            """, email.lower())

                    # Jitter between sends
                    if not args.dry_run:
                        await asyncio.sleep(random.uniform(MIN_JITTER, MAX_JITTER))

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"COMPLETE: {total_sent} sent, {total_skipped} skipped, {total_errors} errors")
        logger.info("=" * 60)

    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description='Award outreach — competitive intelligence emails')
    parser.add_argument('--dry-run', action='store_true', help='Preview without sending')
    parser.add_argument('--limit', type=int, default=MAX_EMAILS_PER_RUN, help='Max emails per run (default: 30)')
    args = parser.parse_args()

    await process_award_outreach(args)


if __name__ == '__main__':
    asyncio.run(main())

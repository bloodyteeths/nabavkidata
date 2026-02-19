#!/usr/bin/env python3
"""
Personalized Follow-up Campaign with FOMO
Sends highly personalized emails based on supplier's tender history and competitors.
"""

import os
import sys
import json
import logging
import asyncio
import httpx
from datetime import datetime
from uuid import uuid4

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN")
POSTMARK_FROM_EMAIL = os.getenv("POSTMARK_FROM_EMAIL", "hello@nabavkidata.com")


def format_value_mkd(value):
    """Format MKD value in millions or thousands."""
    if not value:
        return None
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f} милиони денари"
    elif value >= 1_000:
        return f"{value/1_000:.0f} илјади денари"
    return f"{value:.0f} денари"


def get_short_company_name(full_name):
    """Extract the key brand name from long company name."""
    import re

    # Common patterns to remove (order matters - longer first)
    patterns_to_remove = [
        r"Друштво за производство,?\s*трговија,?\s*(и\s*)?услуги",
        r"Друштво за трговија,?\s*(и\s*)?услуги",
        r"Друштво за промет,?\s*(и\s*)?услуги",
        r"Друштво за производство,?\s*(и\s*)?трговија",
        r"Друштво за градежништво,?\s*трговија,?\s*(и\s*)?услуги",
        r"Трговско друштво за.*?(?=[A-ZА-Ш])",
        r"Трговско друштво",
        r"Друштво за.*?(?=[A-ZА-Ш]{2,})",
        r"Приватна здравствена установа[^А-Ша-ш]*",
        r"Приватна агенција за[^А-Ша-ш]*",
        r"увоз[\-\s]*извоз",
        r"експорт[\-\s]*импорт",
        r"ДООЕЛ",
        r"ДОО",
        r"АД\s",
        r"Скопје$",
        r"Битола$",
        r"Тетово$",
        r"Прилеп$",
        r"Штип$",
        r"с\.[А-Яа-я]+\s*[А-Яа-я]*$",  # village names
    ]

    name = full_name
    for pattern in patterns_to_remove:
        name = re.sub(pattern, " ", name, flags=re.IGNORECASE)

    # Clean up whitespace
    name = " ".join(name.split())

    # Find brand words (all caps or title case, at least 3 chars, not common words)
    skip_words = {'ЗА', 'НА', 'ОД', 'ВО', 'СО', 'И', 'ИЛИ', 'КОН', 'ПРИ'}
    parts = name.split()
    brand_parts = []

    for part in parts:
        clean_part = part.strip('.,()-')
        if len(clean_part) < 3:
            continue
        if clean_part.upper() in skip_words:
            continue
        # Prefer all-caps words (brand names)
        if clean_part.isupper() and len(clean_part) >= 3:
            brand_parts.append(clean_part)
        # Also accept Title Case
        elif clean_part[0].isupper() and len(clean_part) >= 4:
            brand_parts.append(clean_part)

    if brand_parts:
        # Return up to 2 brand words
        return " ".join(brand_parts[:2])

    # Fallback: first meaningful word
    for part in parts:
        if len(part) >= 4:
            return part

    return full_name[:25]


async def get_supplier_personalization(conn, supplier_id):
    """Get rich personalization data for a supplier."""

    # Get basic supplier info with tax_id for reliable matching
    supplier = await conn.fetchrow("""
        SELECT
            s.supplier_id,
            s.company_name,
            s.tax_id,
            s.total_wins,
            s.total_bids,
            s.win_rate,
            s.total_contract_value_mkd,
            s.industries
        FROM suppliers s
        WHERE s.supplier_id = $1
    """, supplier_id)

    if not supplier:
        return None

    data = dict(supplier)
    data['short_name'] = get_short_company_name(data['company_name'])
    tax_id = data.get('tax_id')

    # Get recent tenders - try tax_id first, then company name
    short_name = data['short_name']
    if tax_id:
        recent_tenders = await conn.fetch("""
            SELECT DISTINCT
                t.title,
                t.estimated_value_mkd,
                tb.is_winner,
                t.publication_date
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE tb.company_tax_id = $1
            ORDER BY t.publication_date DESC
            LIMIT 3
        """, tax_id)

    if not tax_id or len(recent_tenders) == 0:
        recent_tenders = await conn.fetch("""
            SELECT DISTINCT
                t.title,
                t.estimated_value_mkd,
                tb.is_winner,
                t.publication_date
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE tb.company_name ILIKE '%' || $1 || '%'
            ORDER BY t.publication_date DESC
            LIMIT 3
        """, short_name)

    data['recent_tenders'] = [dict(t) for t in recent_tenders]

    # Get competitors - companies bidding on same tenders
    # First try with tax_id, then fallback to company name matching
    short_name = data['short_name']
    if tax_id:
        competitors = await conn.fetch("""
            SELECT tb2.company_name, COUNT(DISTINCT tb2.tender_id) as overlap_count
            FROM tender_bidders tb
            JOIN tender_bidders tb2 ON tb.tender_id = tb2.tender_id
            WHERE tb.company_tax_id = $1
              AND tb2.company_tax_id != $1
              AND tb2.company_tax_id IS NOT NULL
              AND tb2.company_name NOT ILIKE '%конзорциум%'
            GROUP BY tb2.company_name
            ORDER BY overlap_count DESC
            LIMIT 5
        """, tax_id)

    # Fallback: use company name matching if no tax_id or no results
    if not tax_id or len(competitors) == 0:
        competitors = await conn.fetch("""
            SELECT tb2.company_name, COUNT(DISTINCT tb2.tender_id) as overlap_count
            FROM tender_bidders tb
            JOIN tender_bidders tb2 ON tb.tender_id = tb2.tender_id
            WHERE tb.company_name ILIKE '%' || $1 || '%'
              AND tb2.company_name NOT ILIKE '%' || $1 || '%'
              AND tb2.company_name NOT ILIKE '%конзорциум%'
            GROUP BY tb2.company_name
            ORDER BY overlap_count DESC
            LIMIT 5
        """, short_name)

    # Only include competitors with at least 2 shared tenders for reliability
    data['competitors'] = [
        {'name': get_short_company_name(c['company_name']), 'full_name': c['company_name'], 'count': c['overlap_count']}
        for c in competitors
        if c['overlap_count'] >= 2  # Minimum 2 shared tenders for credibility
    ]

    # Get total market value from their tender participation
    if tax_id:
        market_value = await conn.fetchval("""
            SELECT SUM(t.estimated_value_mkd)
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE tb.company_tax_id = $1
              AND t.estimated_value_mkd > 0
        """, tax_id)
    else:
        market_value = None

    # Fallback to company name matching
    if not market_value:
        market_value = await conn.fetchval("""
            SELECT SUM(t.estimated_value_mkd)
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE tb.company_name ILIKE '%' || $1 || '%'
              AND t.estimated_value_mkd > 0
        """, short_name)

    # Final fallback to supplier's total contract value
    if not market_value:
        market_value = data.get('total_contract_value_mkd')

    data['total_market_value'] = market_value

    return data


def generate_personalized_email(data):
    """Generate highly personalized FOMO email."""

    short_name = data['short_name']
    total_wins = data.get('total_wins', 0) or 0
    win_rate = data.get('win_rate', 0) or 0
    competitors = data.get('competitors', [])
    recent_tenders = data.get('recent_tenders', [])
    total_market_value = data.get('total_market_value')

    # Pick top 2 competitors for FOMO
    competitor_names = [c['name'] for c in competitors[:2] if c['name'] != short_name]

    # Format market value
    market_value_str = format_value_mkd(total_market_value) if total_market_value else "значителен износ"

    # Dynamic subject lines based on data
    if competitors:
        subject = f"{competitor_names[0] if competitor_names else 'Вашите конкуренти'} веќе го користат ова - вие?"
    else:
        subject = f"{short_name}: Вашите конкуренти имаат предност што вие ја немате"

    # Build personalized body
    body_parts = []

    # Opening - show we know them
    if total_wins > 10:
        opening = f"""Здраво,

Го следев успехот на {short_name} на јавните набавки - импресивни {total_wins} добиени тендери."""
    elif total_wins > 0:
        opening = f"""Здраво,

Забележав дека {short_name} активно учествува на јавни набавки со {total_wins} успешни понуди."""
    else:
        opening = f"""Здраво,

Го следев учеството на {short_name} на пазарот на јавни набавки во Македонија."""

    body_parts.append(opening)

    # FOMO section - competitors
    if competitor_names:
        fomo = f"""
Но, морам да бидам директен: компании како **{competitor_names[0]}**{f' и **{competitor_names[1]}**' if len(competitor_names) > 1 else ''} - вашите директни конкуренти - веќе користат алатки за анализа на тендери.

Тие гледаат:
- Колку точно плаќаат другите понудувачи (вклучувајќи ве вас)
- Кои тендери се објавуваат во реално време
- Историја на цени за секој тип на набавка
- Кој добива и зошто"""
    else:
        fomo = """
Но, морам да бидам директен: вашите конкуренти веќе користат алатки за анализа на тендери.

Тие гледаат:
- Колку точно плаќаат другите понудувачи
- Кои тендери се објавуваат во реално време
- Историја на цени за секој тип на набавка
- Кој добива и зошто"""

    body_parts.append(fomo)

    # Value proposition with their data
    if total_market_value and total_market_value > 1000000:
        value_prop = f"""
На пазар од {market_value_str} каде што се натпреварувате, секоја информација е предност.

**NabavkiData** ви дава пристап до:
✓ База од 15,000+ тендери и 4,000+ компании
✓ Реални цени од сите понуди (не само победничките)
✓ AI асистент што одговара на прашања за било кој тендер
✓ Известувања за нови тендери во вашата индустрија"""
    else:
        value_prop = """
**NabavkiData** ви дава пристап до:
✓ База од 15,000+ тендери и 4,000+ компании
✓ Реални цени од сите понуди (не само победничките)
✓ AI асистент што одговара на прашања за било кој тендер
✓ Известувања за нови тендери во вашата индустрија"""

    body_parts.append(value_prop)

    # Urgency/CTA
    cta = f"""
**Бесплатен пристап за 7 дена** - без обврска, без картичка.

👉 [Активирајте го вашиот пристап](https://nabavkidata.mk?utm_source=followup&utm_medium=email&utm_campaign=fomo)

Не дозволувајте конкуренцијата да има информации што вие ги немате.

Поздрав,
Тамар
NabavkiData.mk

P.S. Веќе имаме над 4,000 корисници од Македонија. {f'Компании од вашиот сектор како {competitor_names[0]} активно ја користат платформата.' if competitor_names else 'Вашите конкуренти веројатно се меѓу нив.'}"""

    body_parts.append(cta)

    # Convert markdown to HTML
    body_text = "\n".join(body_parts)
    body_html = body_text.replace("\n", "<br>")
    body_html = body_html.replace("**", "<strong>").replace("</strong><strong>", "")
    # Fix bold tags
    import re
    body_html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', body_text.replace("\n", "<br>"))

    return {
        'subject': subject,
        'body_text': body_text,
        'body_html': f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
{body_html}
</body>
</html>
"""
    }


async def send_email(email, subject, body_html, body_text):
    """Send email via Postmark."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.postmarkapp.com/email",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": POSTMARK_API_TOKEN,
            },
            json={
                "From": f"Тамар од NabavkiData <{POSTMARK_FROM_EMAIL}>",
                "To": email,
                "Subject": subject,
                "HtmlBody": body_html,
                "TextBody": body_text,
                "MessageStream": "outbound",
                "TrackOpens": True,
                "TrackLinks": "HtmlAndText",
            },
            timeout=30.0
        )
        return response


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=1000, help='Max emails to send')
    parser.add_argument('--live', action='store_true', help='Actually send emails')
    parser.add_argument('--preview', type=int, help='Preview email for specific supplier count')
    parser.add_argument('--delay', type=float, default=5.0, help='Seconds between emails (default: 5)')
    parser.add_argument('--min-wins', type=int, default=0, help='Minimum wins to include')
    args = parser.parse_args()

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get suppliers we've already contacted - prioritize high-value ones
        contacts = await conn.fetch("""
            WITH eligible AS (
                SELECT DISTINCT ON (sc.supplier_id)
                    sc.id as contact_id,
                    sc.supplier_id,
                    sc.email,
                    s.company_name,
                    s.total_wins,
                    om.sent_at
                FROM supplier_contacts sc
                JOIN suppliers s ON sc.supplier_id = s.supplier_id
                JOIN outreach_messages om ON om.contact_id = sc.id
                WHERE om.status = 'sent'
                  AND om.campaign_id IN ('direct-outreach-dec2024', 'killer-outreach-dec2024')
                  AND sc.confidence_score >= 60
                  AND (s.total_wins >= $2 OR s.total_wins IS NULL)
                  AND NOT EXISTS (
                      SELECT 1 FROM outreach_messages om2
                      WHERE om2.contact_id = sc.id
                      AND om2.campaign_id = 'followup_fomo_v1'
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM suppression_list sl WHERE sl.email = sc.email
                  )
                ORDER BY sc.supplier_id, sc.confidence_score DESC
            )
            SELECT * FROM eligible
            ORDER BY total_wins DESC NULLS LAST
            LIMIT $1
        """, args.limit, args.min_wins)

        logger.info(f"Found {len(contacts)} contacts for follow-up")

        if args.preview:
            # Preview mode - show sample emails
            for i, contact in enumerate(contacts[:args.preview]):
                data = await get_supplier_personalization(conn, contact['supplier_id'])
                if data:
                    email_content = generate_personalized_email(data)
                    print(f"\n{'='*60}")
                    print(f"TO: {contact['email']}")
                    print(f"COMPANY: {contact['company_name']}")
                    print(f"SUBJECT: {email_content['subject']}")
                    print(f"{'='*60}")
                    print(email_content['body_text'])
                    print(f"{'='*60}\n")
            return

        if not args.live:
            logger.info("DRY RUN - use --live to actually send")
            for contact in contacts[:5]:
                data = await get_supplier_personalization(conn, contact['supplier_id'])
                if data:
                    email_content = generate_personalized_email(data)
                    logger.info(f"Would send to {contact['email']}: {email_content['subject']}")
            return

        # Live mode
        sent = 0
        errors = 0

        total_contacts = len(contacts)
        estimated_time_min = (total_contacts * args.delay) / 60

        logger.info("\n" + "="*60)
        logger.info("PERSONALIZED FOLLOW-UP CAMPAIGN (LIVE)")
        logger.info(f"Total contacts: {total_contacts}")
        logger.info(f"Delay between emails: {args.delay}s")
        logger.info(f"Estimated duration: {estimated_time_min:.0f} minutes")
        logger.info("="*60 + "\n")

        for contact in contacts:
            data = await get_supplier_personalization(conn, contact['supplier_id'])
            if not data:
                continue

            email_content = generate_personalized_email(data)

            logger.info(f"[{sent+1}/{len(contacts)}] {data['short_name']}")
            logger.info(f"    Email: {contact['email']}")
            logger.info(f"    Subject: {email_content['subject']}")

            try:
                response = await send_email(
                    contact['email'],
                    email_content['subject'],
                    email_content['body_html'],
                    email_content['body_text']
                )

                if response.status_code == 200:
                    result = response.json()
                    message_id = result.get('MessageID')

                    # Record in database
                    await conn.execute("""
                        INSERT INTO outreach_messages (
                            id, supplier_id, contact_id, campaign_id, sequence_step,
                            subject, template_version, personalization,
                            postmark_message_id, status, sent_at, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    """,
                        uuid4(),
                        contact['supplier_id'],
                        contact['contact_id'],
                        'followup_fomo_v1',
                        2,  # Second email in sequence
                        email_content['subject'],
                        'personalized_fomo_v1',
                        json.dumps({
                            'short_name': data['short_name'],
                            'total_wins': data.get('total_wins'),
                            'competitors': [c['name'] for c in data.get('competitors', [])[:2]]
                        }),
                        message_id,
                        'sent',
                        datetime.utcnow(),
                        datetime.utcnow(),
                        datetime.utcnow()
                    )

                    sent += 1
                    logger.info(f"    [SENT] Message ID: {message_id}")
                else:
                    errors += 1
                    logger.error(f"    [ERROR] {response.status_code}: {response.text}")

            except Exception as e:
                errors += 1
                logger.error(f"    [ERROR] {e}")

            # Rate limit for deliverability
            await asyncio.sleep(args.delay)

            # Progress update every 50 emails
            if (sent + errors) % 50 == 0 and (sent + errors) > 0:
                elapsed = (sent + errors) * args.delay / 60
                remaining = (total_contacts - sent - errors) * args.delay / 60
                logger.info(f"    [PROGRESS] {sent + errors}/{total_contacts} processed, ~{remaining:.0f} min remaining")

        logger.info("\n" + "="*60)
        logger.info("FOLLOW-UP CAMPAIGN COMPLETE")
        logger.info(f"Sent: {sent}")
        logger.info(f"Errors: {errors}")
        logger.info("="*60)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

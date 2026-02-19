#!/usr/bin/env python3
"""
Email Campaign - Friday Dec 19, 2025 at 7 AM
Sends the Hormozi-style story email to ALL company contacts.

Sources:
- supplier_contacts (tender bidders)
- outreach_leads (apollo, it.mk, mk_companies, e-nabavki)

Excludes:
- Hard bounces from Postmark
- Government emails (.gov.mk)
- Already sent this campaign
- Malformed emails

Run: python3 scripts/send_followup_friday.py [--dry-run] [--limit N]
"""
import os
import sys
import asyncio
import argparse
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
POSTMARK_API_TOKEN = os.getenv('POSTMARK_API_TOKEN', '33d10a6c-0906-42c6-ab14-441ad12b9e2a')
POSTMARK_FROM_EMAIL = 'hello@nabavkidata.com'
POSTMARK_FROM_NAME = 'Тамара од НабавкиДата'

# Campaign settings
CAMPAIGN_ID = 'followup_story_dec2024'
SEQUENCE_STEP = 3  # Third email in sequence
DELAY_BETWEEN_EMAILS = 3.0  # 3 seconds = ~1,200/hour (~6 hours for 7k emails)

# Email content
SUBJECT = "Една кратка приказна"

HTML_BODY = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Читаш PDF-ови со часови?</p>

        <p>Пред 2 месеци ми се јави сопственик на фирма за медицинска опрема. Правеше истото.</p>

        <p>Секој ден проверувал на е-Набавки дали има нов тендер. Читал PDF-ови со часови. Пресметувал цени на слепо - без да знае колку чинеле истите производи минатата година.</p>

        <p>Му покажав како со НабавкиДата:</p>

        <ul style="padding-left:20px;">
            <li>Добива известување штом излезе тендер од неговата дејност</li>
            <li>AI го чита PDF-от за 10 секунди и ги вади клучните барања</li>
            <li>Гледа историски цени - колку чинеле истите работи кај други институции</li>
            <li>Знае кој најчесто добива и со какви понуди</li>
        </ul>

        <p>По една недела ми рече: <em>"Тамара, за 3 часа подготвив понуда за која претходно ми требаа 3 дена."</em></p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:20px 0;">

        <p>&nbsp;</p>

        <p><strong>4,152 компании</strong> во Македонија веќе го користат НабавкиДата.</p>

        <p>Првата и единствена платформа од овој тип кај нас.</p>

        <p>15,000+ тендери. AI што чита документи. Историја на цени. Анализа на победници.</p>

        <p>Моментално нудиме <strong>бесплатен пробен период</strong> - но нема да трае засекогаш.</p>

        <p>&nbsp;</p>

        <p>Ако сакаш да видиш како изгледа:</p>

        <p><a href="https://nabavkidata.com" style="color:#0066cc; font-weight:bold;">nabavkidata.com</a></p>

        <p>Без обврска. Без картичка. Само погледни.</p>

        <p>&nbsp;</p>

        <p>- Тамара</p>

        <p>&nbsp;</p>

        <p><strong>ПС</strong> - Секој ден без вистински податоци е уште еден тендер каде конкуренцијата има предност. Пробај бесплатно и сам процени.</p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

        <p style="font-size:12px; color:#666666;">
            TAMSAR INC<br>
            131 Continental Dr Ste 305<br>
            New Castle, DE 19713<br>
            hello@nabavkidata.com<br><br>
            <a href="https://nabavkidata.com/unsubscribe?email={email}" style="color:#666666;">Отпиши се</a>
        </p>

    </div>
</body>
</html>"""

TEXT_BODY = """Читаш PDF-ови со часови?

Пред 2 месеци ми се јави сопственик на фирма за медицинска опрема. Правеше истото.

Секој ден проверувал на е-Набавки дали има нов тендер. Читал PDF-ови со часови. Пресметувал цени на слепо - без да знае колку чинеле истите производи минатата година.

Му покажав како со НабавкиДата:
- Добива известување штом излезе тендер од неговата дејност
- AI го чита PDF-от за 10 секунди и ги вади клучните барања
- Гледа историски цени - колку чинеле истите работи кај други институции
- Знае кој најчесто добива и со какви понуди

По една недела ми рече: "Тамара, за 3 часа подготвив понуда за која претходно ми требаа 3 дена."

---

4,152 компании во Македонија веќе го користат НабавкиДата.

Првата и единствена платформа од овој тип кај нас.

15,000+ тендери. AI што чита документи. Историја на цени. Анализа на победници.

Моментално нудиме бесплатен пробен период - но нема да трае засекогаш.

Ако сакаш да видиш како изгледа:
https://nabavkidata.com

Без обврска. Без картичка. Само погледни.

- Тамара

ПС - Секој ден без вистински податоци е уште еден тендер каде конкуренцијата има предност. Пробај бесплатно и сам процени.

---
TAMSAR INC
131 Continental Dr Ste 305
New Castle, DE 19713
hello@nabavkidata.com

Отпиши се: https://nabavkidata.com/unsubscribe?email={email}"""


async def get_hard_bounces() -> set:
    """Fetch all hard bounces from Postmark"""
    bounces = set()
    offset = 0

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
                f"https://api.postmarkapp.com/bounces?count=500&offset={offset}&type=HardBounce",
                headers={
                    "Accept": "application/json",
                    "X-Postmark-Server-Token": POSTMARK_API_TOKEN
                },
                timeout=30.0
            )
            data = response.json()
            page_bounces = [b.get('Email', '').lower() for b in data.get('Bounces', [])]
            bounces.update(page_bounces)

            if len(page_bounces) < 500:
                break
            offset += 500

    logger.info(f"Loaded {len(bounces)} hard bounces from Postmark")
    return bounces


async def send_email(client: httpx.AsyncClient, email: str) -> dict:
    """Send email via Postmark transactional stream"""
    html = HTML_BODY.replace("{email}", email)
    text = TEXT_BODY.replace("{email}", email)

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
            "Subject": SUBJECT,
            "HtmlBody": html,
            "TextBody": text,
            "MessageStream": "outbound",  # Transactional stream
            "TrackOpens": False,
            "TrackLinks": "None"
        },
        timeout=30.0
    )

    if response.status_code == 200:
        return {"success": True, "message_id": response.json().get("MessageID")}
    else:
        return {"success": False, "error": response.text}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Preview without sending')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of emails (0=all)')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("FOLLOW-UP CAMPAIGN - Story Email")
    logger.info(f"Campaign ID: {CAMPAIGN_ID}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info("=" * 60)

    # Get hard bounces
    hard_bounces = await get_hard_bounces()

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)

    # Create campaign_sends table if not exists (for outreach_leads tracking)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS campaign_sends (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            campaign_id TEXT NOT NULL,
            source TEXT,
            postmark_message_id TEXT,
            status TEXT DEFAULT 'sent',
            sent_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(email, campaign_id)
        )
    """)

    try:
        # Get ALL company contacts from both sources
        # Source 1: supplier_contacts (tender bidders)
        supplier_contacts = await conn.fetch("""
            SELECT DISTINCT ON (sc.email)
                sc.id as contact_id,
                sc.supplier_id,
                sc.email,
                s.company_name,
                'supplier_contacts' as source
            FROM supplier_contacts sc
            JOIN suppliers s ON sc.supplier_id = s.supplier_id
            WHERE sc.email IS NOT NULL
            AND sc.email != ''
            ORDER BY sc.email, s.total_wins DESC NULLS LAST
        """)

        # Source 2: outreach_leads (apollo, it.mk, mk_companies, e-nabavki)
        outreach_leads = await conn.fetch("""
            SELECT DISTINCT ON (email)
                lead_id::text as contact_id,
                supplier_id::text,
                email,
                company_name,
                source
            FROM outreach_leads
            WHERE email IS NOT NULL
            AND email != ''
            ORDER BY email
        """)

        # Get emails already sent this campaign (from both tables)
        already_sent = await conn.fetch("""
            SELECT DISTINCT LOWER(email) as email FROM (
                SELECT sc.email
                FROM outreach_messages om
                JOIN supplier_contacts sc ON om.contact_id = sc.id
                WHERE om.campaign_id = $1
                UNION
                SELECT email
                FROM campaign_sends
                WHERE campaign_id = $1
            ) combined
        """, CAMPAIGN_ID)
        already_sent_set = {r['email'] for r in already_sent}

        # Combine and deduplicate by email
        all_emails_seen = set()
        contacts = []

        for c in supplier_contacts:
            email = c['email'].lower() if c['email'] else ''
            if email and email not in all_emails_seen:
                all_emails_seen.add(email)
                contacts.append(dict(c))

        for c in outreach_leads:
            email = c['email'].lower() if c['email'] else ''
            if email and email not in all_emails_seen:
                all_emails_seen.add(email)
                contacts.append(dict(c))

        logger.info(f"Total unique contacts: {len(contacts)}")
        logger.info(f"  - From supplier_contacts: {len(supplier_contacts)}")
        logger.info(f"  - From outreach_leads: {len(outreach_leads)}")
        logger.info(f"Already sent this campaign: {len(already_sent_set)}")

        # Filter out bounces, already sent, and invalid emails
        valid_contacts = []
        skipped_bounces = 0
        skipped_gov = 0
        skipped_already_sent = 0
        skipped_malformed = 0

        for c in contacts:
            email = c['email'].lower()
            # Skip already sent this campaign
            if email in already_sent_set:
                skipped_already_sent += 1
                continue
            # Skip hard bounces
            if email in hard_bounces:
                skipped_bounces += 1
                continue
            # Skip government emails
            if '.gov.mk' in email:
                skipped_gov += 1
                continue
            # Skip malformed emails (URL encoding issues)
            if '%' in email or ' ' in email:
                skipped_malformed += 1
                continue
            # Skip image files mistakenly captured as emails
            if '.jpg' in email or '.png' in email or '.gif' in email:
                skipped_malformed += 1
                continue
            valid_contacts.append(c)

        logger.info(f"Filtered out:")
        logger.info(f"  - Hard bounces: {skipped_bounces}")
        logger.info(f"  - Government (.gov.mk): {skipped_gov}")
        logger.info(f"  - Already sent this campaign: {skipped_already_sent}")
        logger.info(f"  - Malformed emails: {skipped_malformed}")
        logger.info(f"Valid contacts to send: {len(valid_contacts)}")

        if args.limit > 0:
            valid_contacts = valid_contacts[:args.limit]
            logger.info(f"Limited to: {len(valid_contacts)}")

        if not valid_contacts:
            logger.info("No contacts to send to!")
            return

        # Calculate estimated time
        total_seconds = len(valid_contacts) * DELAY_BETWEEN_EMAILS
        hours = total_seconds / 3600
        logger.info(f"Estimated duration: {hours:.1f} hours")
        logger.info(f"Delay between emails: {DELAY_BETWEEN_EMAILS}s")
        logger.info("")

        if args.dry_run:
            logger.info("DRY RUN - First 5 contacts:")
            for c in valid_contacts[:5]:
                logger.info(f"  - {c['email']} ({c['company_name'][:40]}...)")
            return

        # Send emails
        sent = 0
        errors = 0

        async with httpx.AsyncClient() as client:
            for i, contact in enumerate(valid_contacts):
                email = contact['email']
                company = contact['company_name'][:40]

                logger.info(f"[{i+1}/{len(valid_contacts)}] {email}")

                result = await send_email(client, email)

                if result['success']:
                    # Record in database - handle both supplier_contacts and outreach_leads
                    if contact.get('supplier_id'):
                        # From supplier_contacts
                        await conn.execute("""
                            INSERT INTO outreach_messages
                            (supplier_id, contact_id, campaign_id, sequence_step,
                             subject, postmark_message_id, status, sent_at, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, $6, 'sent', NOW(), NOW(), NOW())
                        """,
                            contact['supplier_id'],
                            contact['contact_id'],
                            CAMPAIGN_ID,
                            SEQUENCE_STEP,
                            SUBJECT,
                            result['message_id']
                        )
                    else:
                        # From outreach_leads - track separately
                        await conn.execute("""
                            INSERT INTO campaign_sends
                            (email, campaign_id, source, postmark_message_id, status, sent_at)
                            VALUES ($1, $2, $3, $4, 'sent', NOW())
                            ON CONFLICT (email, campaign_id) DO NOTHING
                        """,
                            contact['email'],
                            CAMPAIGN_ID,
                            contact.get('source', 'outreach_leads'),
                            result['message_id']
                        )
                    sent += 1
                    logger.info(f"    ✓ Sent ({result['message_id'][:20]}...)")
                else:
                    errors += 1
                    logger.error(f"    ✗ Error: {result['error'][:50]}")

                # Progress update every 50 emails
                if (i + 1) % 50 == 0:
                    elapsed_pct = (i + 1) / len(valid_contacts) * 100
                    logger.info(f"    --- Progress: {elapsed_pct:.1f}% ({sent} sent, {errors} errors) ---")

                # Delay between emails
                await asyncio.sleep(DELAY_BETWEEN_EMAILS)

        logger.info("")
        logger.info("=" * 60)
        logger.info("CAMPAIGN COMPLETE")
        logger.info(f"Sent: {sent}")
        logger.info(f"Errors: {errors}")
        logger.info("=" * 60)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

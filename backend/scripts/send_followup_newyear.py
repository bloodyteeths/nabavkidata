#!/usr/bin/env python3
"""
Follow-up Campaign - New Year 2026
Sends to ALL contacts from previous Dec 2025 campaigns.

Fixes from last campaign:
- Uses broadcast stream (not transactional)
- TrackOpens: True, TrackLinks: HtmlAndText
- List-Unsubscribe headers for deliverability
- Checks suppression_list + campaign_unsubscribes tables
- Dynamic tender count from DB

Sources:
- supplier_contacts (tender bidders)
- outreach_leads (apollo, it.mk, mk_companies, e-nabavki)

Excludes:
- Hard bounces from Postmark
- suppression_list table entries
- campaign_unsubscribes table entries
- Government emails (.gov.mk)
- Already sent this campaign
- Malformed emails

Run: python3 scripts/send_followup_newyear.py [--dry-run] [--limit N] [--live]
"""
import os
import sys
import asyncio
import argparse
import logging
import hashlib
from datetime import datetime
from urllib.parse import quote
import httpx
import asyncpg

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
FRONTEND_URL = 'https://nabavkidata.com'
UNSUBSCRIBE_SECRET = os.getenv('UNSUBSCRIBE_SECRET', 'nabavki-unsub-secret-2025')

# Campaign settings
CAMPAIGN_ID = 'followup_newyear_feb2026'
SEQUENCE_STEP = 4
DELAY_BETWEEN_EMAILS = 3.0  # 3 seconds = ~1,200/hour (~6 hours for 7k emails)

# Email content
SUBJECT = "2026 почна. Вашата конкуренција веќе гледа."


def generate_unsubscribe_token(email: str) -> str:
    """Generate HMAC unsubscribe token"""
    return hashlib.sha256(f"{email}:{UNSUBSCRIBE_SECRET}".encode()).hexdigest()[:32]


def generate_unsubscribe_url(email: str) -> str:
    """Generate one-click unsubscribe URL"""
    token = generate_unsubscribe_token(email)
    return f"{FRONTEND_URL}/unsubscribe?e={quote(email)}&t={token}"


def get_html_body(tender_count: int) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; font-family:Arial, sans-serif; font-size:16px; line-height:1.6; color:#000000; background-color:#ffffff;">
    <div style="max-width:600px; margin:0 auto;">

        <p>Нова година, нови буџети, нови тендери.</p>

        <p>Од 1 јануари до денес, на е-Набавки се објавени <strong>{tender_count}+ нови тендери</strong>.</p>

        <p>Институциите почнаа да трошат. Q1 буџетите се одобрени. А повеќето фирми уште не ги следат.</p>

        <p>&nbsp;</p>

        <p>Ти пишав во декември. Оттогаш, додадовме:</p>

        <ul style="padding-left:20px;">
            <li><strong>AI анализа на документи</strong> - чита PDF за секунди, вади клучни барања</li>
            <li><strong>Историски цени</strong> - види по колку се склучени договори минатите години</li>
            <li><strong>Дневни известувања</strong> - добиј мејл штом излезе тендер од твојата дејност</li>
            <li><strong>Анализа на победници</strong> - кој добива, со колку, и зошто</li>
        </ul>

        <p>&nbsp;</p>

        <p><strong>4,500+ компании</strong> веќе го користат НабавкиДата.</p>

        <p>Ако не си погледнал - сега е вистинскиот момент. Тендерите од Q1 веќе течат.</p>

        <p>&nbsp;</p>

        <p><a href="https://nabavkidata.com?utm_source=email&utm_medium=followup&utm_campaign=newyear2026" style="display:inline-block; background-color:#2563eb; color:#ffffff; padding:14px 28px; text-decoration:none; border-radius:6px; font-weight:bold; font-size:16px;">Погледни ги новите тендери</a></p>

        <p style="font-size:14px; color:#666666;">Бесплатно. Без картичка. Без обврска.</p>

        <p>&nbsp;</p>

        <p>- Тамара</p>

        <p>&nbsp;</p>

        <p><strong>ПС</strong> - Секоја недела без вистински податоци е уште една изгубена можност. Твојата конкуренција веќе гледа - ти?</p>

        <p>&nbsp;</p>

        <hr style="border:none; border-top:1px solid #eeeeee; margin:30px 0;">

        <p style="font-size:12px; color:#666666;">
            TAMSAR INC<br>
            131 Continental Dr Ste 305<br>
            New Castle, DE 19713<br>
            hello@nabavkidata.com<br><br>
            <a href="{{{{unsubscribe_url}}}}" style="color:#666666;">Отпиши се</a>
        </p>

    </div>
</body>
</html>"""


def get_text_body(tender_count: int) -> str:
    return f"""Нова година, нови буџети, нови тендери.

Од 1 јануари до денес, на е-Набавки се објавени {tender_count}+ нови тендери.

Институциите почнаа да трошат. Q1 буџетите се одобрени. А повеќето фирми уште не ги следат.

Ти пишав во декември. Оттогаш, додадовме:
- AI анализа на документи - чита PDF за секунди, вади клучни барања
- Историски цени - види по колку се склучени договори минатите години
- Дневни известувања - добиј мејл штом излезе тендер од твојата дејност
- Анализа на победници - кој добива, со колку, и зошто

4,500+ компании веќе го користат НабавкиДата.

Ако не си погледнал - сега е вистинскиот момент. Тендерите од Q1 веќе течат.

Погледни ги новите тендери: https://nabavkidata.com?utm_source=email&utm_medium=followup&utm_campaign=newyear2026

Бесплатно. Без картичка. Без обврска.

- Тамара

ПС - Секоја недела без вистински податоци е уште една изгубена можност. Твојата конкуренција веќе гледа - ти?

---
TAMSAR INC
131 Continental Dr Ste 305
New Castle, DE 19713
hello@nabavkidata.com

Отпиши се: {{{{unsubscribe_url}}}}"""


async def get_postmark_suppressions() -> set:
    """Fetch permanent suppression lists from Postmark (both streams)"""
    suppressed = set()

    async with httpx.AsyncClient() as client:
        for stream in ["broadcast", "outbound"]:
            response = await client.get(
                f"https://api.postmarkapp.com/message-streams/{stream}/suppressions/dump",
                headers={
                    "Accept": "application/json",
                    "X-Postmark-Server-Token": POSTMARK_API_TOKEN
                },
                timeout=60.0
            )
            data = response.json()
            emails = [s.get('EmailAddress', '').lower() for s in data.get('Suppressions', [])]
            suppressed.update(emails)
            logger.info(f"  Postmark {stream} suppressions: {len(emails)}")

    logger.info(f"Total Postmark suppressions: {len(suppressed)}")
    return suppressed


async def get_suppressed_emails(conn) -> set:
    """Get emails from suppression_list and campaign_unsubscribes tables"""
    suppressed = set()

    # Check suppression_list table
    try:
        rows = await conn.fetch("SELECT LOWER(email) as email FROM suppression_list")
        suppressed.update(r['email'] for r in rows)
        logger.info(f"  Suppression list: {len(rows)} entries")
    except Exception:
        logger.info("  suppression_list table not found, skipping")

    # Check campaign_unsubscribes table
    try:
        rows = await conn.fetch("SELECT LOWER(email) as email FROM campaign_unsubscribes")
        suppressed.update(r['email'] for r in rows)
        logger.info(f"  Campaign unsubscribes: {len(rows)} entries")
    except Exception:
        logger.info("  campaign_unsubscribes table not found, skipping")

    return suppressed


async def send_email(client: httpx.AsyncClient, email: str, html: str, text: str) -> dict:
    """Send email via Postmark broadcast stream with full tracking"""
    unsubscribe_url = generate_unsubscribe_url(email)
    html_final = html.replace("{{unsubscribe_url}}", unsubscribe_url)
    text_final = text.replace("{{unsubscribe_url}}", unsubscribe_url)

    response = await client.post(
        "https://api.postmarkapp.com/email",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": POSTMARK_API_TOKEN
        },
        json={
            "From": f"{POSTMARK_FROM_NAME} <{POSTMARK_FROM_EMAIL}>",
            "ReplyTo": POSTMARK_FROM_EMAIL,
            "To": email,
            "Subject": SUBJECT,
            "HtmlBody": html_final,
            "TextBody": text_final,
            "MessageStream": "broadcast",
            "TrackOpens": True,
            "TrackLinks": "HtmlAndText",
            "Headers": [
                {"Name": "List-Unsubscribe", "Value": f"<{unsubscribe_url}>"},
                {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"}
            ]
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
    parser.add_argument('--live', action='store_true', help='Actually send (safety flag)')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of emails (0=all)')
    args = parser.parse_args()

    is_live = args.live and not args.dry_run

    logger.info("=" * 60)
    logger.info("FOLLOW-UP CAMPAIGN - New Year 2026")
    logger.info(f"Campaign ID: {CAMPAIGN_ID}")
    logger.info(f"Mode: {'LIVE' if is_live else 'DRY RUN'}")
    logger.info("=" * 60)

    # Get permanent suppressions from Postmark (bounces + complaints)
    logger.info("Loading Postmark suppressions...")
    postmark_suppressions = await get_postmark_suppressions()

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)

    # Ensure campaign_sends table exists
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
        # Get suppressed emails from DB tables
        logger.info("Loading suppression lists...")
        suppressed_emails = await get_suppressed_emails(conn)
        logger.info(f"Total suppressed emails: {len(suppressed_emails)}")

        # Get dynamic tender count for email body
        tender_count_row = await conn.fetchrow(
            "SELECT COUNT(*) as cnt FROM tenders WHERE created_at >= '2026-01-01'"
        )
        tender_count = tender_count_row['cnt'] if tender_count_row else 500
        # Round down to nearest hundred for cleaner display
        tender_count = (tender_count // 100) * 100
        logger.info(f"Tenders since Jan 1, 2026: {tender_count}")

        # Build email content with dynamic tender count
        html_body = get_html_body(tender_count)
        text_body = get_text_body(tender_count)

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

        # Source 2: outreach_leads
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

        # Get emails already sent THIS campaign
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

        # Filter
        valid_contacts = []
        skipped_bounces = 0
        skipped_gov = 0
        skipped_already_sent = 0
        skipped_malformed = 0
        skipped_suppressed = 0

        for c in contacts:
            email = c['email'].lower()
            if email in already_sent_set:
                skipped_already_sent += 1
                continue
            if email in postmark_suppressions:
                skipped_bounces += 1
                continue
            if email in suppressed_emails:
                skipped_suppressed += 1
                continue
            if '.gov.mk' in email:
                skipped_gov += 1
                continue
            if '%' in email or ' ' in email:
                skipped_malformed += 1
                continue
            if '.jpg' in email or '.png' in email or '.gif' in email:
                skipped_malformed += 1
                continue
            # Basic email format check
            if '@' not in email or '.' not in email.split('@')[-1]:
                skipped_malformed += 1
                continue
            valid_contacts.append(c)

        logger.info(f"Filtered out:")
        logger.info(f"  - Postmark suppressions: {skipped_bounces}")
        logger.info(f"  - Suppressed (DB): {skipped_suppressed}")
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

        # Estimated time
        total_seconds = len(valid_contacts) * DELAY_BETWEEN_EMAILS
        hours = total_seconds / 3600
        logger.info(f"Estimated duration: {hours:.1f} hours")
        logger.info(f"Delay between emails: {DELAY_BETWEEN_EMAILS}s")
        logger.info("")

        if not is_live:
            logger.info("DRY RUN - First 10 contacts:")
            for c in valid_contacts[:10]:
                name = c.get('company_name', 'N/A')[:40]
                logger.info(f"  - {c['email']} ({name})")
            logger.info("")
            logger.info("Email preview:")
            logger.info(f"  Subject: {SUBJECT}")
            logger.info(f"  Tender count in body: {tender_count}")
            logger.info(f"  Stream: broadcast")
            logger.info(f"  TrackOpens: True")
            logger.info(f"  TrackLinks: HtmlAndText")
            logger.info(f"  List-Unsubscribe: Yes")
            logger.info("")
            logger.info("To send for real, use: --live")
            return

        # Send emails
        sent = 0
        errors = 0

        async with httpx.AsyncClient() as client:
            for i, contact in enumerate(valid_contacts):
                email = contact['email']

                logger.info(f"[{i+1}/{len(valid_contacts)}] {email}")

                result = await send_email(client, email, html_body, text_body)

                if result['success']:
                    # Record in database
                    if contact.get('source') == 'supplier_contacts' and contact.get('supplier_id'):
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
                    logger.error(f"    ✗ Error: {result['error'][:80]}")

                # Progress update every 100 emails
                if (i + 1) % 100 == 0:
                    elapsed_pct = (i + 1) / len(valid_contacts) * 100
                    logger.info(f"    --- Progress: {elapsed_pct:.1f}% ({sent} sent, {errors} errors) ---")

                await asyncio.sleep(DELAY_BETWEEN_EMAILS)

        logger.info("")
        logger.info("=" * 60)
        logger.info("CAMPAIGN COMPLETE")
        logger.info(f"Sent: {sent}")
        logger.info(f"Errors: {errors}")
        logger.info(f"Campaign ID: {CAMPAIGN_ID}")
        logger.info("=" * 60)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

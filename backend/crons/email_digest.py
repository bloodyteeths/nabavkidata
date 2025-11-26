#!/usr/bin/env python3
"""
Email Digest Generator Cron
Generates and sends daily/weekly email digests for users via Mailersend
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(env_path)

from sqlalchemy import select, and_
from database import AsyncSessionLocal
from models import User, Tender
from services.mailer import mailer_service

# Personalization disabled - table doesn't exist yet
HAS_PERSONALIZATION = False


async def generate_digest_html(
    user_name: str,
    tenders: List[Dict],
    frequency: str = "daily"
) -> str:
    """Generate HTML digest using Mailersend template style"""

    period = "Today's" if frequency == "daily" else "This Week's"

    tender_rows = ""
    for tender in tenders[:10]:
        value = tender.get('estimated_value_mkd') or tender.get('estimated_value')
        value_str = f"{value:,.0f} MKD" if value else "N/A"
        closing = tender.get('closing_date', 'N/A')
        if hasattr(closing, 'strftime'):
            closing = closing.strftime('%Y-%m-%d')

        tender_rows += f"""
        <tr>
            <td style="padding: 15px; border-bottom: 1px solid #e5e7eb;">
                <h3 style="margin: 0 0 8px 0; color: #1f2937; font-size: 16px;">
                    <a href="https://nabavkidata.com/tenders/{tender.get('tender_id', '')}"
                       style="color: #2563eb; text-decoration: none;">
                        {tender.get('title', 'Untitled')}
                    </a>
                </h3>
                <p style="margin: 0; color: #6b7280; font-size: 14px;">
                    <strong>Entity:</strong> {tender.get('procuring_entity', 'N/A')} |
                    <strong>Budget:</strong> {value_str} |
                    <strong>Closes:</strong> {closing}
                </p>
            </td>
        </tr>
        """

    content = f"""
    <p>Hello <strong>{user_name}</strong>,</p>
    <p>Here's your {frequency} digest of public procurement opportunities in North Macedonia.</p>

    <div style="margin: 25px 0; padding: 15px; background-color: #eff6ff; border-radius: 8px; border-left: 4px solid #2563eb;">
        <p style="margin: 0; font-size: 18px; font-weight: 600; color: #1e40af;">
            {period} Highlights: {len(tenders)} matching tenders
        </p>
    </div>

    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
        {tender_rows}
    </table>

    <p style="margin-top: 25px;">
        Visit your dashboard to see all matching tenders and manage your alerts.
    </p>
    """

    return mailer_service._get_email_template(
        title=f"{period} Tender Digest",
        content=content,
        button_text="View All Tenders",
        button_link="https://nabavkidata.com/dashboard"
    )


async def get_recent_tenders(db, days: int = 1) -> List[Dict]:
    """Get recent open tenders"""
    since = datetime.utcnow() - timedelta(days=days)

    query = select(Tender).where(
        and_(
            Tender.status == 'open',
            Tender.created_at >= since
        )
    ).order_by(Tender.created_at.desc()).limit(20)

    result = await db.execute(query)
    tenders = result.scalars().all()

    return [
        {
            'tender_id': t.tender_id,
            'title': t.title,
            'procuring_entity': t.procuring_entity,
            'estimated_value_mkd': t.estimated_value_mkd,
            'closing_date': t.closing_date,
            'category': t.category
        }
        for t in tenders
    ]


async def send_digest_to_user(
    email: str,
    name: str,
    tenders: List[Dict],
    frequency: str
) -> bool:
    """Send digest email to user"""

    if not tenders:
        return False

    html_content = await generate_digest_html(name, tenders, frequency)

    period = "Daily" if frequency == "daily" else "Weekly"
    subject = f"{period} Tender Digest - {len(tenders)} New Opportunities"

    return await mailer_service.send_transactional_email(
        to=email,
        subject=subject,
        html_content=html_content,
        reply_to="support@nabavkidata.com"
    )


async def generate_all_digests(frequency: str = "daily"):
    """Generate and send digests for all eligible users"""

    print(f"\n{'='*60}")
    print(f"EMAIL DIGEST GENERATOR - {frequency.upper()}")
    print(f"{'='*60}")
    print(f"Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    async with AsyncSessionLocal() as db:
        # Get recent tenders
        days = 1 if frequency == "daily" else 7
        tenders = await get_recent_tenders(db, days)

        print(f"Found {len(tenders)} tenders from last {days} day(s)")

        if not tenders:
            print("No new tenders to send. Exiting.")
            return

        # Get users with email notifications enabled
        if HAS_PERSONALIZATION:
            query = select(UserPreferences, User).join(
                User, User.user_id == UserPreferences.user_id
            ).where(
                and_(
                    UserPreferences.email_enabled == True,
                    UserPreferences.notification_frequency == frequency,
                    User.email_verified == True
                )
            )
            result = await db.execute(query)
            users = [(prefs.user_id, user.email, user.full_name) for prefs, user in result.all()]
        else:
            # Fallback: send to all verified users
            query = select(User).where(User.email_verified == True)
            result = await db.execute(query)
            users = [(u.user_id, u.email, u.full_name) for u in result.scalars().all()]

        print(f"Found {len(users)} eligible users for {frequency} digest")

        if not users:
            print("No eligible users found. Exiting.")
            return

        sent_count = 0
        failed_count = 0

        for user_id, email, name in users:
            try:
                success = await send_digest_to_user(
                    email=email,
                    name=name or "User",
                    tenders=tenders,
                    frequency=frequency
                )

                if success:
                    sent_count += 1
                    print(f"  ✓ Sent to {email}")
                else:
                    failed_count += 1
                    print(f"  ✗ Failed: {email}")

            except Exception as e:
                failed_count += 1
                print(f"  ✗ Error for {email}: {e}")

        print(f"\n{'='*60}")
        print(f"DIGEST SUMMARY")
        print(f"{'='*60}")
        print(f"  Tenders included: {len(tenders)}")
        print(f"  Emails sent: {sent_count}")
        print(f"  Emails failed: {failed_count}")
        print(f"Completed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")


def main():
    """Main entry point"""

    frequency = sys.argv[1] if len(sys.argv) > 1 else "daily"

    if frequency not in ["daily", "weekly", "instant"]:
        print(f"Invalid frequency: {frequency}")
        print("Usage: python email_digest.py [daily|weekly|instant]")
        sys.exit(1)

    asyncio.run(generate_all_digests(frequency))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Instant Alert Trigger
Monitors for new tenders and sends instant notifications to users with matching preferences

Run this every 15-30 minutes via cron to provide near-real-time alerts
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal
from models import User, Tender
from models_user_personalization import UserPreferences, TenderAlert
from services.postmark import postmark_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://www.nabavkidata.com")

# Track last check time in a simple file
LAST_CHECK_FILE = "/tmp/nabavkidata_instant_alert_last_check"


def get_last_check_time() -> datetime:
    """Get the last time we checked for new tenders"""
    try:
        with open(LAST_CHECK_FILE, 'r') as f:
            timestamp = float(f.read().strip())
            return datetime.utcfromtimestamp(timestamp)
    except:
        # Default to 30 minutes ago if no file exists
        return datetime.utcnow() - timedelta(minutes=30)


def save_last_check_time():
    """Save the current time as last check time"""
    try:
        with open(LAST_CHECK_FILE, 'w') as f:
            f.write(str(datetime.utcnow().timestamp()))
    except Exception as e:
        logger.error(f"Failed to save last check time: {e}")


# Sector keywords for matching
SECTOR_KEYWORDS = {
    "it": ["софтвер", "ИТ", "информатички", "компјутер", "систем", "апликација", "веб", "дигитал", "software", "IT", "computer", "digital", "hardware", "сервер", "мрежа"],
    "construction": ["градежн", "изградба", "реконструкција", "санација", "објект", "зграда", "пат", "construction", "building", "infrastructure"],
    "consulting": ["консултант", "советодавн", "consulting", "advisory", "студија", "анализа"],
    "equipment": ["опрема", "машини", "апарат", "уред", "equipment", "machinery", "device"],
    "medical": ["медицин", "здравств", "болница", "лек", "фармацевт", "medical", "health", "hospital", "pharma"],
    "education": ["образова", "училиш", "универзитет", "обука", "education", "school", "training"],
    "transport": ["транспорт", "превоз", "возил", "transport", "vehicle", "logistics"],
    "food": ["храна", "пијалоц", "прехран", "food", "beverage", "catering"],
    "cleaning": ["чистење", "хигиена", "одржување", "cleaning", "maintenance", "hygiene"],
    "security": ["безбедност", "обезбедување", "заштита", "security", "protection", "surveillance"],
    "energy": ["енергија", "електрична", "струја", "гориво", "energy", "electricity", "fuel"],
    "printing": ["печатење", "печатница", "printing", "publishing"]
}

SECTOR_NAMES_MK = {
    "it": "ИТ", "construction": "Градежништво", "consulting": "Консултантски услуги",
    "equipment": "Опрема", "medical": "Медицина", "education": "Образование",
    "transport": "Транспорт", "food": "Храна", "cleaning": "Чистење",
    "security": "Безбедност", "energy": "Енергија", "printing": "Печатење"
}


def tender_matches_preferences(tender: Tender, prefs: UserPreferences) -> tuple[bool, List[str]]:
    """Check if a tender matches user preferences and return match reasons"""
    reasons = []
    tender_text = f"{tender.title or ''} {tender.description or ''}".lower()

    # Check exclude keywords first (hard filter)
    if prefs.exclude_keywords:
        for kw in prefs.exclude_keywords:
            if kw.lower() in tender_text:
                return False, []

    # Check sector match
    if prefs.sectors:
        for sector in prefs.sectors:
            keywords = SECTOR_KEYWORDS.get(sector, [])
            for keyword in keywords:
                if keyword.lower() in tender_text:
                    reasons.append(f"📁 {SECTOR_NAMES_MK.get(sector, sector)}")
                    break

    # Check CPV match
    if prefs.cpv_codes and tender.cpv_code:
        for cpv in prefs.cpv_codes:
            if tender.cpv_code.startswith(cpv[:2]):
                reasons.append(f"🏷️ CPV: {tender.cpv_code}")
                break

    # Check entity match
    if prefs.entities and tender.procuring_entity:
        for entity in prefs.entities:
            if entity.lower() in tender.procuring_entity.lower():
                reasons.append(f"🏛️ {entity}")
                break

    # Check budget match
    if tender.estimated_value_mkd:
        in_budget = True
        if prefs.min_budget and tender.estimated_value_mkd < float(prefs.min_budget):
            in_budget = False
        if prefs.max_budget and tender.estimated_value_mkd > float(prefs.max_budget):
            in_budget = False
        if in_budget and (prefs.min_budget or prefs.max_budget):
            reasons.append("💰 Во вашиот буџет")

    # Match if at least one reason found
    return len(reasons) > 0, reasons


async def generate_instant_alert_html(
    user_name: str,
    tender: Tender,
    reasons: List[str]
) -> str:
    """Generate HTML for instant alert email"""

    value = tender.estimated_value_mkd
    value_str = f"{value:,.0f} МКД" if value else "N/A"
    closing = tender.closing_date
    if hasattr(closing, 'strftime'):
        closing = closing.strftime('%d.%m.%Y')

    reasons_html = " ".join([f'<span style="background-color: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-right: 4px;">{r}</span>' for r in reasons])

    content = f"""
    <p>Здраво <strong>{user_name}</strong>,</p>
    <p>Нов тендер што одговара на вашите преференци е објавен!</p>

    <div style="margin: 25px 0; padding: 20px; background-color: #f0fdf4; border-radius: 12px; border-left: 4px solid #22c55e;">
        <h2 style="margin: 0 0 12px 0; color: #166534; font-size: 18px; line-height: 1.4;">
            {tender.title or 'Без наслов'}
        </h2>

        <table style="width: 100%; margin: 15px 0;">
            <tr>
                <td style="padding: 8px 0; color: #6b7280; width: 140px;">Договорен орган:</td>
                <td style="padding: 8px 0; color: #1f2937; font-weight: 500;">{tender.procuring_entity or 'N/A'}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #6b7280;">Проценета вредност:</td>
                <td style="padding: 8px 0; color: #1f2937; font-weight: 500;">{value_str}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #6b7280;">Рок за поднесување:</td>
                <td style="padding: 8px 0; color: #dc2626; font-weight: 600;">{closing}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #6b7280;">CPV код:</td>
                <td style="padding: 8px 0; color: #1f2937;">{tender.cpv_code or 'N/A'}</td>
            </tr>
        </table>

        <div style="margin-top: 15px;">
            <p style="margin: 0 0 8px 0; color: #6b7280; font-size: 13px;">Зошто ви го препорачуваме:</p>
            {reasons_html}
        </div>
    </div>

    <p style="margin-top: 20px; color: #6b7280; font-size: 14px;">
        Кликнете подолу за да ги видите целосните детали и документација за тендерот.
    </p>
    """

    return postmark_service._get_email_template(
        title="🔔 Нов Тендер",
        content=content,
        button_text="Погледни го тендерот",
        button_link=f"{FRONTEND_URL}/tenders/{tender.tender_id}"
    )


async def send_instant_alert(
    user: User,
    tender: Tender,
    reasons: List[str]
) -> bool:
    """Send instant alert for a single tender to a user"""

    try:
        html_content = await generate_instant_alert_html(
            user_name=user.full_name or "User",
            tender=tender,
            reasons=reasons
        )

        success = await postmark_service.send_email(
            to=user.email,
            subject=f"🔔 Нов тендер: {tender.title[:50]}..." if len(tender.title or '') > 50 else f"🔔 Нов тендер: {tender.title}",
            html_content=html_content,
            tag="instant-alert",
            reply_to="support@nabavkidata.com"
        )

        return success

    except Exception as e:
        logger.error(f"Error sending instant alert to {user.email}: {e}")
        return False


async def process_instant_alerts():
    """Main function to process instant alerts"""

    print(f"\n{'='*60}")
    print(f"INSTANT ALERT PROCESSOR")
    print(f"{'='*60}")
    print(f"Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    last_check = get_last_check_time()
    print(f"Checking for tenders since: {last_check.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    async with AsyncSessionLocal() as db:
        # Get new tenders since last check
        query = select(Tender).where(
            and_(
                Tender.status == 'open',
                Tender.created_at >= last_check
            )
        ).order_by(Tender.created_at.desc())

        result = await db.execute(query)
        new_tenders = result.scalars().all()

        print(f"Found {len(new_tenders)} new tenders")

        if not new_tenders:
            save_last_check_time()
            print("No new tenders. Exiting.")
            return

        # Get users with instant notifications enabled
        users_query = select(User, UserPreferences).join(
            UserPreferences, User.user_id == UserPreferences.user_id
        ).where(
            and_(
                User.email_verified == True,
                UserPreferences.notification_frequency == "instant",
                UserPreferences.email_enabled == True
            )
        )

        users_result = await db.execute(users_query)
        users_with_prefs = users_result.all()

        print(f"Found {len(users_with_prefs)} users with instant alerts enabled")

        if not users_with_prefs:
            save_last_check_time()
            print("No users with instant alerts. Exiting.")
            return

        # Match tenders to users
        alerts_sent = 0
        alerts_failed = 0

        for tender in new_tenders:
            for user, prefs in users_with_prefs:
                matches, reasons = tender_matches_preferences(tender, prefs)

                if matches:
                    success = await send_instant_alert(user, tender, reasons)

                    if success:
                        alerts_sent += 1
                        print(f"  ✓ Alert sent to {user.email} for tender {tender.tender_id[:20]}...")
                    else:
                        alerts_failed += 1
                        print(f"  ✗ Failed to send to {user.email}")

        # Save last check time
        save_last_check_time()

        print(f"\n{'='*60}")
        print(f"INSTANT ALERT SUMMARY")
        print(f"{'='*60}")
        print(f"  New tenders processed: {len(new_tenders)}")
        print(f"  Alerts sent: {alerts_sent}")
        print(f"  Alerts failed: {alerts_failed}")
        print(f"Completed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")


def main():
    """Main entry point"""
    asyncio.run(process_instant_alerts())


if __name__ == "__main__":
    main()

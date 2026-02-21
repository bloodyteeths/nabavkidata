#!/usr/bin/env python3
"""
Instant Alert Trigger
Monitors for new tenders and sends instant notifications to users with matching preferences

Run this every 15-30 minutes via cron to provide near-real-time alerts
"""
import asyncio
import sys
import os
import json
import uuid
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import quote
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

from sqlalchemy import select, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal
from models import User, Tender
from models_user_personalization import UserPreferences, TenderAlert
from services.postmark import postmark_service
from api.alerts import check_alert_against_tender
from api.notifications import create_notification

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
                kw_lower = keyword.lower()
                # Short keywords (<=3 chars) use word boundary to avoid false positives
                if len(kw_lower) <= 3:
                    if re.search(r'(?<!\w)' + re.escape(kw_lower) + r'(?!\w)', tender_text):
                        reasons.append(f"📁 {SECTOR_NAMES_MK.get(sector, sector)}")
                        break
                elif kw_lower in tender_text:
                    reasons.append(f"📁 {SECTOR_NAMES_MK.get(sector, sector)}")
                    break

    # Check CPV match
    if prefs.cpv_codes and tender.cpv_code:
        for cpv in prefs.cpv_codes:
            if tender.cpv_code.startswith(cpv[:4]):
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

    from urllib.parse import quote
    return postmark_service._get_email_template(
        title="🔔 Нов Тендер",
        content=content,
        button_text="Погледни го тендерот",
        button_link=f"{FRONTEND_URL}/tenders/{quote(tender.tender_id, safe='')}"
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


async def generate_alert_email_html(user_name: str, tender: dict, reasons: List[str]) -> str:
    """Generate HTML for alert email from a dict-based tender (e-nabavki or e-pazar)."""
    value = tender.get('estimated_value_mkd')
    value_str = f"{value:,.0f} МКД" if value else "N/A"
    closing = tender.get('closing_date')
    if hasattr(closing, 'strftime'):
        closing = closing.strftime('%d.%m.%Y')
    elif closing:
        closing = str(closing)
    else:
        closing = "N/A"

    source_label = "е-Пазар" if tender.get('source') == 'e-pazar' else "е-Набавки"
    reasons_html = " ".join([
        f'<span style="background-color: #e0e7ff; color: #3730a3; padding: 2px 8px; '
        f'border-radius: 12px; font-size: 11px; margin-right: 4px;">{r}</span>'
        for r in reasons
    ])

    content = f"""
    <p>Здраво <strong>{user_name}</strong>,</p>
    <p>Нов тендер од <strong>{source_label}</strong> што одговара на вашите алерти!</p>

    <div style="margin: 25px 0; padding: 20px; background-color: #f0fdf4; border-radius: 12px; border-left: 4px solid #22c55e;">
        <h2 style="margin: 0 0 12px 0; color: #166534; font-size: 18px; line-height: 1.4;">
            {tender.get('title') or 'Без наслов'}
        </h2>
        <table style="width: 100%; margin: 15px 0;">
            <tr><td style="padding: 8px 0; color: #6b7280; width: 140px;">Договорен орган:</td>
                <td style="padding: 8px 0; color: #1f2937; font-weight: 500;">{tender.get('procuring_entity') or 'N/A'}</td></tr>
            <tr><td style="padding: 8px 0; color: #6b7280;">Проценета вредност:</td>
                <td style="padding: 8px 0; color: #1f2937; font-weight: 500;">{value_str}</td></tr>
            <tr><td style="padding: 8px 0; color: #6b7280;">Рок за поднесување:</td>
                <td style="padding: 8px 0; color: #dc2626; font-weight: 600;">{closing}</td></tr>
            <tr><td style="padding: 8px 0; color: #6b7280;">CPV код:</td>
                <td style="padding: 8px 0; color: #1f2937;">{tender.get('cpv_code') or 'N/A'}</td></tr>
            <tr><td style="padding: 8px 0; color: #6b7280;">Извор:</td>
                <td style="padding: 8px 0; color: #1f2937;">{source_label}</td></tr>
        </table>
        <div style="margin-top: 15px;">
            <p style="margin: 0 0 8px 0; color: #6b7280; font-size: 13px;">Зошто ви го препорачуваме:</p>
            {reasons_html}
        </div>
    </div>
    """

    return postmark_service._get_email_template(
        title="🔔 Нов Тендер",
        content=content,
        button_text="Погледни го тендерот",
        button_link=f"{FRONTEND_URL}/tenders/{quote(tender.get('tender_id', ''), safe='')}"
    )


async def send_alert_email(user_email: str, user_name: str, tender: dict, reasons: List[str]) -> bool:
    """Send alert email for a dict-based tender."""
    try:
        html = await generate_alert_email_html(user_name, tender, reasons)
        title = tender.get('title') or 'Без наслов'
        subject = f"🔔 Нов тендер: {title[:50]}..." if len(title) > 50 else f"🔔 Нов тендер: {title}"
        return await postmark_service.send_email(
            to=user_email, subject=subject, html_content=html,
            tag="instant-alert", reply_to="support@nabavkidata.com"
        )
    except Exception as e:
        logger.error(f"Error sending alert email to {user_email}: {e}")
        return False


async def process_tender_alert_matches(db: AsyncSession, tenders: List[dict], source: str, already_emailed: set = None) -> tuple:
    """
    Match tenders against all active tender_alerts.
    Creates alert_matches, in-app notifications, and sends emails.
    Returns (matches_count, emails_sent).
    """
    if not tenders:
        return 0, 0

    # Get all active tender_alerts with user info
    result = await db.execute(text("""
        SELECT ta.alert_id, ta.user_id, ta.name, ta.criteria, ta.notification_channels,
               u.email, u.full_name, u.email_verified
        FROM tender_alerts ta
        JOIN users u ON u.user_id = ta.user_id::uuid
        WHERE ta.is_active = true AND u.email_verified = true
    """))
    alerts_with_users = result.fetchall()

    if not alerts_with_users:
        return 0, 0

    matches_count = 0
    emails_sent = 0
    MAX_EMAILS_PER_RUN = 20  # Cap to protect rate limits

    for tender in tenders:
        for row in alerts_with_users:
            alert_id, user_id, alert_name, criteria_raw, channels_raw, \
                user_email, user_name, _ = row

            # Parse JSONB criteria
            criteria = criteria_raw if isinstance(criteria_raw, dict) else json.loads(criteria_raw) if criteria_raw else {}
            channels = channels_raw if isinstance(channels_raw, list) else json.loads(channels_raw) if channels_raw else []

            alert_dict = {'criteria': criteria}
            matches, score, reasons = await check_alert_against_tender(alert_dict, tender)

            if not matches:
                continue

            # Insert match (ON CONFLICT skip if already exists)
            match_id = str(uuid.uuid4())
            try:
                await db.execute(text("""
                    INSERT INTO alert_matches
                        (match_id, alert_id, tender_id, tender_source, match_score, match_reasons, is_read, created_at)
                    VALUES (:match_id, :alert_id, :tender_id, :source, :score, CAST(:reasons AS jsonb), false, NOW())
                    ON CONFLICT (alert_id, tender_id) DO NOTHING
                """), {
                    'match_id': match_id,
                    'alert_id': str(alert_id),
                    'tender_id': tender['tender_id'],
                    'source': source,
                    'score': score,
                    'reasons': json.dumps(reasons)
                })
                matches_count += 1
            except Exception as e:
                logger.warning(f"Match insert failed: {e}")
                continue

            # In-app notification
            if 'in_app' in channels:
                try:
                    await create_notification(
                        db, str(user_id), 'alert_match',
                        title=f"🔔 {alert_name}: {tender.get('title', '')[:60]}",
                        message=', '.join(reasons[:3]),
                        data={'tender_id': tender['tender_id'], 'source': source, 'score': score},
                        tender_id=tender['tender_id'],
                        alert_id=str(alert_id)
                    )
                except Exception as e:
                    logger.warning(f"Notification create failed: {e}")

            # Email notification (capped, skip if already emailed via preferences)
            if 'email' in channels and emails_sent < MAX_EMAILS_PER_RUN:
                if already_emailed and (user_email, tender['tender_id']) in already_emailed:
                    print(f"  ~ Skipped email to {user_email} for {tender['tender_id'][:20]}... (already emailed via prefs)")
                else:
                    success = await send_alert_email(user_email, user_name or "User", tender, reasons)
                    if success:
                        emails_sent += 1
                        print(f"  ✓ Alert email to {user_email} for {tender['tender_id'][:20]}... ({alert_name})")

    await db.commit()
    return matches_count, emails_sent


async def check_tender_changes(db: AsyncSession, last_check: datetime) -> int:
    """Check for tender status changes and notify watchers."""
    # Find tenders that were updated (not just created) since last check
    result = await db.execute(text("""
        SELECT t.tender_id, t.title, t.status, t.winner, t.procuring_entity
        FROM tenders t
        WHERE t.updated_at >= :since
          AND t.updated_at > t.created_at + interval '1 minute'
        LIMIT 100
    """), {'since': last_check})
    changed = result.fetchall()

    if not changed:
        return 0

    notifications_sent = 0
    for tender_row in changed:
        tid, title, status, winner, entity = tender_row

        # Find users watching this tender (have it in alert_matches)
        watchers = await db.execute(text("""
            SELECT DISTINCT ta.user_id, u.email, u.full_name
            FROM alert_matches am
            JOIN tender_alerts ta ON ta.alert_id = am.alert_id
            JOIN users u ON u.user_id = ta.user_id::uuid
            WHERE am.tender_id = :tid AND ta.is_active = true
        """), {'tid': tid})

        for watcher in watchers.fetchall():
            user_id, email, name = watcher
            status_msg = f"Статус: {status}"
            if winner:
                status_msg += f" | Победник: {winner}"

            try:
                await create_notification(
                    db, str(user_id), 'tender_update',
                    title=f"📋 Промена: {title[:60]}",
                    message=status_msg,
                    data={'tender_id': tid, 'status': status, 'winner': winner},
                    tender_id=tid
                )
                notifications_sent += 1
            except Exception as e:
                logger.warning(f"Change notification failed for {tid}: {e}")

    if notifications_sent > 0:
        await db.commit()

    return notifications_sent


async def process_instant_alerts():
    """Main function to process instant alerts"""
    from services.cron_logger import log_cron_start, log_cron_complete, log_cron_failed

    job_name = "instant_alerts"

    print(f"\n{'='*60}")
    print(f"INSTANT ALERT PROCESSOR")
    print(f"{'='*60}")
    print(f"Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    last_check = get_last_check_time()
    print(f"Checking for tenders since: {last_check.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    async with AsyncSessionLocal() as db:
        # Log cron start
        execution_id = await log_cron_start(db, job_name, {"last_check": last_check.isoformat()})

        try:
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

            # Also fetch new e-pazar tenders
            epazar_result = await db.execute(text("""
                SELECT tender_id, title, description,
                       contracting_authority as procuring_entity,
                       estimated_value_mkd, cpv_code, closing_date,
                       '' as winner, 'e-pazar' as source
                FROM epazar_tenders
                WHERE created_at >= :since
                ORDER BY created_at DESC
            """), {'since': last_check})
            new_epazar = [
                {
                    'tender_id': r[0], 'title': r[1], 'description': r[2],
                    'procuring_entity': r[3], 'estimated_value_mkd': float(r[4]) if r[4] else 0,
                    'cpv_code': r[5], 'closing_date': r[6],
                    'winner': r[7], 'source': r[8]
                }
                for r in epazar_result.fetchall()
            ]
            print(f"Found {len(new_epazar)} new e-pazar tenders")

            # Convert e-nabavki tenders to dicts for tender_alerts matching
            nabavki_dicts = [
                {
                    'tender_id': t.tender_id, 'title': t.title, 'description': t.description,
                    'procuring_entity': t.procuring_entity,
                    'estimated_value_mkd': float(t.estimated_value_mkd) if t.estimated_value_mkd else 0,
                    'cpv_code': t.cpv_code, 'closing_date': t.closing_date,
                    'winner': t.winner or '', 'source': 'e-nabavki'
                }
                for t in new_tenders
            ]

            all_new = len(new_tenders) + len(new_epazar)
            if all_new == 0:
                # Still check for tender changes
                changes = await check_tender_changes(db, last_check)
                save_last_check_time()
                print(f"No new tenders. Change notifications: {changes}. Exiting.")
                await log_cron_complete(db, execution_id, 0, {"message": "No new tenders", "changes": changes})
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
                await log_cron_complete(db, execution_id, 0, {
                    "message": "No users with instant alerts",
                    "tenders_checked": len(new_tenders)
                })
                return

            # Match tenders to users
            alerts_sent = 0
            alerts_failed = 0
            MAX_PREF_EMAILS_PER_USER = 5  # Cap emails per user per run

            # Track emails per user and (email, tender_id) pairs for dedup
            user_email_counts: Dict[str, int] = {}
            emailed_pairs: set = set()  # (email, tender_id) pairs already emailed

            for tender in new_tenders:
                for user, prefs in users_with_prefs:
                    # Check per-user cap
                    uid = str(user.user_id)
                    if user_email_counts.get(uid, 0) >= MAX_PREF_EMAILS_PER_USER:
                        continue

                    matches, reasons = tender_matches_preferences(tender, prefs)

                    if matches:
                        success = await send_instant_alert(user, tender, reasons)

                        if success:
                            alerts_sent += 1
                            user_email_counts[uid] = user_email_counts.get(uid, 0) + 1
                            emailed_pairs.add((user.email, tender.tender_id))
                            print(f"  ✓ Alert sent to {user.email} for tender {tender.tender_id[:20]}...")
                        else:
                            alerts_failed += 1
                            print(f"  ✗ Failed to send to {user.email}")

            # ===== Process tender_alerts table (UI-created alerts) =====
            # Pass emailed_pairs to avoid sending duplicate emails
            print(f"\n--- Processing tender_alerts (e-nabavki: {len(nabavki_dicts)}, e-pazar: {len(new_epazar)}) ---")

            ta_matches_nabavki, ta_emails_nabavki = await process_tender_alert_matches(
                db, nabavki_dicts, 'e-nabavki', already_emailed=emailed_pairs
            )
            ta_matches_epazar, ta_emails_epazar = await process_tender_alert_matches(
                db, new_epazar, 'e-pazar', already_emailed=emailed_pairs
            )

            ta_total_matches = ta_matches_nabavki + ta_matches_epazar
            ta_total_emails = ta_emails_nabavki + ta_emails_epazar
            print(f"  tender_alerts: {ta_total_matches} matches, {ta_total_emails} emails")

            # ===== Check for tender status changes =====
            changes = await check_tender_changes(db, last_check)
            if changes > 0:
                print(f"  Tender changes: {changes} notifications sent")

            # Save last check time
            save_last_check_time()

            print(f"\n{'='*60}")
            print(f"INSTANT ALERT SUMMARY")
            print(f"{'='*60}")
            print(f"  New e-nabavki tenders: {len(new_tenders)}")
            print(f"  New e-pazar tenders: {len(new_epazar)}")
            print(f"  Preference alerts sent: {alerts_sent}")
            print(f"  Preference alerts failed: {alerts_failed}")
            print(f"  Tender alert matches: {ta_total_matches}")
            print(f"  Tender alert emails: {ta_total_emails}")
            print(f"  Change notifications: {changes}")
            print(f"Completed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

            # Log cron completion
            await log_cron_complete(db, execution_id, alerts_sent + ta_total_emails, {
                "nabavki_tenders": len(new_tenders),
                "epazar_tenders": len(new_epazar),
                "users_checked": len(users_with_prefs),
                "pref_alerts_sent": alerts_sent,
                "pref_alerts_failed": alerts_failed,
                "tender_alert_matches": ta_total_matches,
                "tender_alert_emails": ta_total_emails,
                "change_notifications": changes
            })

        except Exception as e:
            logger.error(f"Instant alerts processing failed: {e}")
            await log_cron_failed(db, execution_id, str(e))
            try:
                from api.clawd_monitor import notify_clawd
                await notify_clawd("cron_failed", {"job": job_name, "error": str(e)})
            except Exception:
                pass
            raise


def main():
    """Main entry point"""
    asyncio.run(process_instant_alerts())


if __name__ == "__main__":
    main()

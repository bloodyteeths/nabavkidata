#!/usr/bin/env python3
"""
AI-Personalized Email Digest Generator
Generates and sends daily/weekly email digests with personalized tender recommendations

Features:
- Per-user personalized tender selection via HybridSearchEngine
- AI-generated insights (trending sectors, budget opportunities, deadlines)
- Competitor activity tracking
- Digest history stored in database
- Respects user notification preferences
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal
from models import User, Tender
from models_user_personalization import UserPreferences, EmailDigest
from services.postmark import postmark_service
from services.personalization_engine import (
    HybridSearchEngine,
    InsightGenerator,
    CompetitorTracker
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://www.nabavkidata.com")


def tender_url(tender_id: str) -> str:
    """Convert tender_id like '12345/2024' to frontend URL."""
    return f"{FRONTEND_URL}/tenders/{tender_id.replace('/', '-')}"


def generate_match_reasons(tender: Tender, prefs: Optional[UserPreferences]) -> List[str]:
    """Generate human-readable match reasons for a tender"""
    reasons = []

    if not prefs:
        reasons.append("Нов тендер")
        return reasons

    tender_text = f"{tender.title or ''} {tender.description or ''}".lower()

    # Sector keywords mapping
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
    if tender.estimated_value_mkd and prefs.min_budget:
        if tender.estimated_value_mkd >= float(prefs.min_budget):
            if not prefs.max_budget or tender.estimated_value_mkd <= float(prefs.max_budget):
                reasons.append("💰 Во вашиот буџет")

    if not reasons:
        reasons.append("🆕 Нов тендер")

    return reasons


def generate_pro_upgrade_section(user_tier: str, alert_matches_count: int, tenders_count: int) -> str:
    """Render Pro upgrade curiosity-gap + CTA for non-paying users. Empty string for paid users."""
    if user_tier in ("starter", "professional", "pro", "enterprise"):
        return ""

    settings_url = f"{FRONTEND_URL}/settings"
    return f"""
    <div style="margin: 30px 0; padding: 22px; background-color: #f8fafc; border: 2px solid #e2e8f0; border-radius: 10px;">
        <h3 style="margin: 0 0 14px 0; color: #0f172a; font-size: 17px;">Што уште би видел со Pro</h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; color: #475569; margin-bottom: 16px;">
            <tr>
                <td style="padding: 8px 0;">AI препорака за цена на понуда (по тендер)</td>
                <td style="padding: 8px 0; text-align: right;"><span style="color:#94a3b8;">Заклучено</span></td>
            </tr>
            <tr>
                <td style="padding: 8px 0;">Историски цени на победниците за секој тендер</td>
                <td style="padding: 8px 0; text-align: right;"><span style="color:#94a3b8;">Заклучено</span></td>
            </tr>
            <tr>
                <td style="padding: 8px 0;">Анализа на ризик и корупција (DOZORRO)</td>
                <td style="padding: 8px 0; text-align: right;"><span style="color:#94a3b8;">Заклучено</span></td>
            </tr>
            <tr>
                <td style="padding: 8px 0;">Неограничен AI чат (25 прашања/ден)</td>
                <td style="padding: 8px 0; text-align: right;"><span style="color:#94a3b8;">Заклучено</span></td>
            </tr>
            <tr>
                <td style="padding: 8px 0;">CSV/PDF извоз и следење на конкуренти</td>
                <td style="padding: 8px 0; text-align: right;"><span style="color:#94a3b8;">Заклучено</span></td>
            </tr>
        </table>
        <p style="margin: 0 0 14px 0; font-size: 13px; color: #64748b;">
            Денеска ти стигнаа {alert_matches_count} совпаѓања и {tenders_count} препораки. Со Pro ги добиваш и AI препораките и историјата на цени за секој тендер — да знаеш точно колку да понудиш.
        </p>
        <p style="margin: 0; text-align: center;">
            <a href="{settings_url}" style="background-color: #2563eb; color: #ffffff; padding: 12px 26px; border-radius: 6px; text-decoration: none; display: inline-block; font-size: 14px; font-weight: 600;">Активирај Pro — 1,990 МКД/месец</a>
        </p>
        <p style="margin: 10px 0 0 0; text-align: center; font-size: 12px; color: #94a3b8;">
            Можеш да откажеш во секое време од Поставки.
        </p>
    </div>
    """


async def generate_personalized_digest_html(
    user_name: str,
    tenders: List[Tuple[Tender, float]],
    prefs: Optional[UserPreferences],
    insights: List[Dict],
    competitor_activity: List[Dict],
    frequency: str = "daily",
    alert_matches: List = None,
    user_tier: str = "free"
) -> str:
    """Generate HTML digest with personalized content"""

    period = "Денешен" if frequency == "daily" else "Неделен"
    period_en = "Today's" if frequency == "daily" else "This Week's"

    # Build tender rows with match reasons
    tender_rows = ""
    for tender, score in tenders[:10]:
        value = tender.estimated_value_mkd
        value_str = f"{value:,.0f} МКД" if value else "N/A"
        closing = tender.closing_date
        if hasattr(closing, 'strftime'):
            closing = closing.strftime('%d.%m.%Y')

        # Get match reasons
        reasons = generate_match_reasons(tender, prefs)
        reasons_html = " ".join([f'<span style="background-color: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-right: 4px;">{r}</span>' for r in reasons[:3]])

        # Score indicator
        score_color = "#10b981" if score > 0.7 else "#f59e0b" if score > 0.5 else "#6b7280"
        score_pct = int(score * 100)

        tender_rows += f"""
        <tr>
            <td style="padding: 18px; border-bottom: 1px solid #e5e7eb; background-color: #ffffff;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div style="flex: 1;">
                        <h3 style="margin: 0 0 8px 0; color: #1f2937; font-size: 16px; line-height: 1.4;">
                            <a href="{tender_url(tender.tender_id)}"
                               style="color: #2563eb; text-decoration: none;">
                                {tender.title or 'Без наслов'}
                            </a>
                        </h3>
                        <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 13px;">
                            <strong>Договорен орган:</strong> {tender.procuring_entity or 'N/A'}
                        </p>
                        <p style="margin: 0 0 10px 0; color: #374151; font-size: 14px;">
                            <span style="margin-right: 15px;"><strong>Буџет:</strong> {value_str}</span>
                            <span style="color: #dc2626;"><strong>Рок:</strong> {closing}</span>
                        </p>
                        <div style="margin-top: 8px;">
                            {reasons_html}
                        </div>
                    </div>
                    <div style="text-align: right; min-width: 60px;">
                        <div style="background-color: {score_color}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">
                            {score_pct}%
                        </div>
                    </div>
                </div>
            </td>
        </tr>
        """

    # Build insights section
    insights_html = ""
    if insights:
        insights_items = ""
        for insight in insights[:3]:
            icon = "📈" if insight.get('insight_type') == 'trend' else "💡" if insight.get('insight_type') == 'opportunity' else "⏰"
            insights_items += f"""
            <div style="padding: 12px; background-color: #fef3c7; border-radius: 8px; margin-bottom: 8px;">
                <p style="margin: 0; font-size: 14px; color: #92400e;">
                    <strong>{icon} {insight.get('title', '')}</strong><br>
                    <span style="font-size: 13px;">{insight.get('description', '')}</span>
                </p>
            </div>
            """
        insights_html = f"""
        <div style="margin: 25px 0;">
            <h3 style="margin: 0 0 15px 0; color: #1f2937; font-size: 16px;">🎯 AI Insights за вас</h3>
            {insights_items}
        </div>
        """

    # Build competitor section
    competitor_html = ""
    if competitor_activity:
        competitor_items = ""
        for activity in competitor_activity[:5]:
            competitor_items += f"""
            <li style="margin-bottom: 8px; color: #374151; font-size: 13px;">
                <strong>{activity.get('competitor_name', '')}</strong> -
                <a href="{tender_url(activity.get('tender_id', ''))}" style="color: #2563eb; text-decoration: none;">
                    {activity.get('title', '')[:50]}...
                </a>
            </li>
            """
        competitor_html = f"""
        <div style="margin: 25px 0; padding: 15px; background-color: #fef2f2; border-radius: 8px; border-left: 4px solid #ef4444;">
            <h3 style="margin: 0 0 12px 0; color: #991b1b; font-size: 16px;">👀 Активност на конкуренти</h3>
            <ul style="margin: 0; padding-left: 20px;">
                {competitor_items}
            </ul>
        </div>
        """

    # Build alert matches section
    alert_matches_html = ""
    if alert_matches:
        alert_items = ""
        for row in alert_matches:
            match_id, tender_id, score, reasons, alert_name, title, entity, value, closing = row
            value_str = f"{value:,.0f} МКД" if value else "N/A"
            closing_str = closing.strftime('%d.%m.%Y') if closing and hasattr(closing, 'strftime') else "N/A"
            reasons_list = reasons if isinstance(reasons, list) else []
            reasons_str = ", ".join(reasons_list[:2]) if reasons_list else ""

            alert_items += f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                    <div>
                        <span style="background-color: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 10px; font-size: 11px;">{alert_name}</span>
                        <span style="background-color: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 10px; font-size: 11px; margin-left: 4px;">{int(score)}%</span>
                    </div>
                    <h4 style="margin: 8px 0 4px 0; font-size: 14px;">
                        <a href="{tender_url(tender_id)}" style="color: #2563eb; text-decoration: none;">{title or 'Без наслов'}</a>
                    </h4>
                    <p style="margin: 0; font-size: 12px; color: #6b7280;">
                        {entity or 'N/A'} | {value_str} | Рок: {closing_str}
                    </p>
                    {f'<p style="margin: 4px 0 0 0; font-size: 11px; color: #9ca3af;">{reasons_str}</p>' if reasons_str else ''}
                </td>
            </tr>
            """

        alert_matches_html = f"""
        <div style="margin: 25px 0; padding: 15px; background-color: #fef3c7; border-radius: 8px; border-left: 4px solid #f59e0b;">
            <h3 style="margin: 0 0 12px 0; color: #92400e; font-size: 16px;">🔔 Совпаѓања од вашите алерти ({len(alert_matches)})</h3>
            <table style="width: 100%; border-collapse: collapse;">
                {alert_items}
            </table>
            <p style="margin: 12px 0 0 0; text-align: center;">
                <a href="{FRONTEND_URL}/alerts" style="color: #2563eb; font-size: 13px;">Погледни ги сите алерти →</a>
            </p>
        </div>
        """

    content = f"""
    <p>Здраво <strong>{user_name}</strong>,</p>
    <p>Еве го вашиот {frequency} преглед на јавни набавки персонализиран според вашите преференци.</p>

    <div style="margin: 25px 0; padding: 15px; background-color: #eff6ff; border-radius: 8px; border-left: 4px solid #2563eb;">
        <p style="margin: 0; font-size: 18px; font-weight: 600; color: #1e40af;">
            {period} преглед: {len(tenders)} препорачани тендери
        </p>
    </div>

    {alert_matches_html}

    {insights_html}

    <table style="width: 100%; border-collapse: collapse; margin: 20px 0; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        {tender_rows}
    </table>

    {competitor_html}

    {generate_pro_upgrade_section(user_tier, len(alert_matches or []), len(tenders))}

    <p style="margin-top: 25px; color: #6b7280; font-size: 14px;">
        Оваа листа е генерирана од нашиот AI систем врз основа на вашите преференци и однесување.
        <a href="{FRONTEND_URL}/settings" style="color: #2563eb;">Ажурирајте ги преференците</a> за подобри препораки.
    </p>
    """

    return postmark_service._get_email_template(
        title=f"{period} Преглед на Тендери",
        content=content,
        button_text="Погледни ги сите тендери",
        button_link=f"{FRONTEND_URL}/dashboard"
    )


async def get_personalized_tenders(
    db: AsyncSession,
    user_id: str,
    limit: int = 15
) -> List[Tuple[Tender, float]]:
    """Get personalized tenders for a user using HybridSearchEngine"""
    engine = HybridSearchEngine(db)
    return await engine.search(str(user_id), limit=limit)


async def get_user_insights(db: AsyncSession, user_id: str) -> List[Dict]:
    """Get AI-generated insights for user"""
    generator = InsightGenerator(db)
    insights = await generator.generate_insights(str(user_id))
    return [
        {
            'insight_type': i.insight_type,
            'title': i.title,
            'description': i.description,
            'confidence': i.confidence
        }
        for i in insights
    ]


async def get_competitor_activity(db: AsyncSession, user_id: str) -> List[Dict]:
    """Get competitor activity for user"""
    tracker = CompetitorTracker(db)
    activities = await tracker.get_competitor_activity(str(user_id), limit=5)
    return [
        {
            'tender_id': a.tender_id,
            'title': a.title,
            'competitor_name': a.competitor_name,
            'status': a.status
        }
        for a in activities
    ]


async def save_digest_to_db(
    db: AsyncSession,
    user_id: str,
    html_content: str,
    tender_count: int,
    competitor_count: int
) -> str:
    """Save digest to database for history tracking"""
    import re

    # Generate plain text from HTML
    text_content = re.sub('<[^<]+?>', '', html_content)
    text_content = re.sub(r'\s+', ' ', text_content).strip()

    digest = EmailDigest(
        user_id=user_id,
        digest_date=datetime.utcnow(),
        digest_html=html_content,
        digest_text=text_content[:5000],  # Limit text length
        tender_count=tender_count,
        competitor_activity_count=competitor_count,
        sent=True,
        sent_at=datetime.utcnow()
    )
    db.add(digest)
    await db.commit()
    await db.refresh(digest)
    return str(digest.digest_id)


async def send_personalized_digest(
    db: AsyncSession,
    user_id: str,
    email: str,
    name: str,
    prefs: Optional[UserPreferences],
    frequency: str,
    user_tier: str = "free"
) -> str:
    """Generate and send personalized digest to a single user.
    Returns: 'sent', 'no_tenders', 'send_failed', or error description."""

    try:
        # Get personalized tenders
        tenders = await get_personalized_tenders(db, user_id, limit=15)

        if not tenders:
            logger.info(f"No tenders for user {email}, skipping")
            return "no_tenders"

        # Get AI insights
        insights = await get_user_insights(db, user_id)

        # Get competitor activity
        competitor_activity = await get_competitor_activity(db, user_id)

        # Get unread alert matches from the last day
        alert_matches_data = []
        try:
            alert_result = await db.execute(text("""
                SELECT am.match_id, am.tender_id, am.match_score, am.match_reasons,
                       ta.name as alert_name,
                       t.title, t.procuring_entity, t.estimated_value_mkd, t.closing_date
                FROM alert_matches am
                JOIN tender_alerts ta ON ta.alert_id = am.alert_id
                LEFT JOIN tenders t ON am.tender_id = t.tender_id
                WHERE ta.user_id = :user_id
                  AND am.created_at >= NOW() - INTERVAL '1 day'
                  AND am.notified_at IS NULL
                ORDER BY am.match_score DESC
                LIMIT 10
            """), {'user_id': user_id})
            alert_matches_data = alert_result.fetchall()
        except Exception as e:
            logger.warning(f"Failed to fetch alert matches for digest: {e}")

        # Generate HTML
        html_content = await generate_personalized_digest_html(
            user_name=name,
            tenders=tenders,
            prefs=prefs,
            insights=insights,
            competitor_activity=competitor_activity,
            frequency=frequency,
            alert_matches=alert_matches_data,
            user_tier=user_tier
        )

        # Send email
        period = "Дневен" if frequency == "daily" else "Неделен"
        subject = f"{period} преглед - {len(tenders)} препорачани тендери"

        success = await postmark_service.send_email(
            to=email,
            subject=subject,
            html_content=html_content,
            tag=f"digest-{frequency}",
            reply_to="support@nabavkidata.com"
        )

        if success:
            # Save to database
            await save_digest_to_db(
                db=db,
                user_id=user_id,
                html_content=html_content,
                tender_count=len(tenders),
                competitor_count=len(competitor_activity)
            )

            # Mark alert matches as notified
            if alert_matches_data:
                match_ids = [str(row[0]) for row in alert_matches_data]
                try:
                    await db.execute(text("""
                        UPDATE alert_matches SET notified_at = NOW()
                        WHERE match_id = ANY(:match_ids)
                    """), {'match_ids': match_ids})
                    await db.commit()
                except Exception as e:
                    logger.warning(f"Failed to mark alert matches as notified: {e}")

        if success:
            return "sent"
        return "send_failed"

    except Exception as e:
        logger.error(f"Error generating digest for {email}: {e}")
        return f"error: {e}"


async def generate_all_digests(frequency: str = "daily"):
    """Generate and send personalized digests for all eligible users"""
    from services.cron_logger import log_cron_start, log_cron_complete, log_cron_failed

    job_name = f"email_digest_{frequency}"

    print(f"\n{'='*60}")
    print(f"AI-PERSONALIZED EMAIL DIGEST GENERATOR - {frequency.upper()}")
    print(f"{'='*60}")
    print(f"Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    async with AsyncSessionLocal() as db:
        # Log cron start
        execution_id = await log_cron_start(db, job_name, {"frequency": frequency})

        try:
            # Get users with matching notification preferences
            query = select(User, UserPreferences).outerjoin(
                UserPreferences, User.user_id == UserPreferences.user_id
            ).where(
                and_(
                    User.email_verified == True,
                    # Include users who have matching frequency OR no preferences yet (default to daily)
                    or_(
                        UserPreferences.notification_frequency == frequency,
                        and_(
                            UserPreferences.user_id == None,
                            frequency == "daily"  # Default frequency for users without preferences
                        )
                    ),
                    # Respect email_enabled flag (default True if no preferences)
                    or_(
                        UserPreferences.email_enabled == True,
                        UserPreferences.user_id == None
                    )
                )
            )

            result = await db.execute(query)
            users_data = result.all()

            print(f"Found {len(users_data)} eligible users for {frequency} digest")

            if not users_data:
                print("No eligible users found. Exiting.")
                await log_cron_complete(db, execution_id, 0, {"message": "No eligible users"})
                return

            sent_count = 0
            failed_count = 0
            skipped_count = 0

            for user, prefs in users_data:
                try:
                    result = await send_personalized_digest(
                        db=db,
                        user_id=str(user.user_id),
                        email=user.email,
                        name=user.full_name or "User",
                        prefs=prefs,
                        frequency=frequency,
                        user_tier=user.subscription_tier or "free"
                    )

                    if result == "sent":
                        sent_count += 1
                        print(f"  ✓ Sent to {user.email}")
                    elif result == "no_tenders":
                        skipped_count += 1
                        print(f"  - Skipped {user.email} (no matching tenders)")
                    else:
                        failed_count += 1
                        print(f"  ✗ Failed: {user.email} ({result})")

                except Exception as e:
                    failed_count += 1
                    print(f"  ✗ Error for {user.email}: {e}")

            print(f"\n{'='*60}")
            print(f"DIGEST SUMMARY")
            print(f"{'='*60}")
            print(f"  Emails sent: {sent_count}")
            print(f"  Emails skipped: {skipped_count}")
            print(f"  Emails failed: {failed_count}")
            print(f"Completed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

            # Log cron completion
            await log_cron_complete(db, execution_id, sent_count, {
                "sent": sent_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "total_users": len(users_data)
            })

        except Exception as e:
            logger.error(f"Digest generation failed: {e}")
            await log_cron_failed(db, execution_id, str(e))
            try:
                from api.clawd_monitor import notify_clawd
                await notify_clawd("cron_failed", {"job": job_name, "error": str(e)})
            except Exception:
                pass
            raise


# Import or_ for the query
from sqlalchemy import or_


def main():
    """Main entry point"""

    frequency = sys.argv[1] if len(sys.argv) > 1 else "daily"

    if frequency not in ["daily", "weekly"]:
        print(f"Invalid frequency: {frequency}")
        print("Usage: python email_digest.py [daily|weekly]")
        sys.exit(1)

    asyncio.run(generate_all_digests(frequency))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Email Digest Generator Cron
Generates daily/weekly email digests for users
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import select, and_

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import AsyncSessionLocal
from models import User, Tender
from models_user_personalization import UserPreferences, EmailDigest
from services.personalization_engine import HybridSearchEngine, CompetitorTracker


async def generate_digest_html(
    user_id: str,
    tenders: List[Tender],
    competitor_activity: List[Dict],
    insights: str
) -> str:
    """Generate HTML digest"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .header {{ background: #1976d2; color: white; padding: 20px; }}
            .tender {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; }}
            .insights {{ background: #f5f5f5; padding: 15px; margin: 20px 0; }}
            .footer {{ color: #666; padding: 20px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>nabavkidata.com - Your Daily Digest</h1>
            <p>{datetime.utcnow().strftime('%Y-%m-%d')}</p>
        </div>

        <div class="content">
            <h2>Recommended Tenders ({len(tenders)})</h2>
    """

    for tender in tenders[:10]:
        html += f"""
            <div class="tender">
                <h3>{tender.title}</h3>
                <p><strong>Entity:</strong> {tender.procuring_entity or 'N/A'}</p>
                <p><strong>Budget:</strong> {tender.estimated_value_mkd or 'N/A'} MKD</p>
                <p><strong>Closing:</strong> {tender.closing_date or 'N/A'}</p>
                <p><a href="https://nabavkidata.com/tenders/{tender.tender_id}">View Details</a></p>
            </div>
        """

    if competitor_activity:
        html += f"""
            <h2>Competitor Activity ({len(competitor_activity)})</h2>
        """
        for activity in competitor_activity[:5]:
            html += f"""
            <div class="tender">
                <h3>{activity['title']}</h3>
                <p><strong>Competitor:</strong> {activity['competitor_name']}</p>
                <p><strong>Status:</strong> {activity['status']}</p>
            </div>
            """

    if insights:
        html += f"""
            <div class="insights">
                <h2>AI Insights</h2>
                <p>{insights}</p>
            </div>
        """

    html += """
        </div>
        <div class="footer">
            <p>nabavkidata.com - Macedonian Tender Intelligence</p>
            <p><a href="https://nabavkidata.com/preferences">Update Preferences</a></p>
        </div>
    </body>
    </html>
    """

    return html


async def generate_user_digest(user_id: str, frequency: str = "daily"):
    """Generate digest for single user"""

    async with AsyncSessionLocal() as db:
        # Get user preferences
        prefs_query = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await db.execute(prefs_query)
        prefs = result.scalar_one_or_none()

        if not prefs or not prefs.email_enabled:
            return None

        if prefs.notification_frequency != frequency:
            return None

        # Get recommended tenders
        search_engine = HybridSearchEngine(db)
        scored_tenders = await search_engine.search(user_id, limit=20)
        tenders = [t[0] for t in scored_tenders]

        if not tenders:
            return None

        # Get competitor activity
        tracker = CompetitorTracker(db)
        competitor_activity = await tracker.get_competitor_activity(user_id, limit=5)

        # Generate AI insights summary
        insights = f"We found {len(tenders)} tenders matching your preferences."
        if competitor_activity:
            insights += f" Your competitors are active in {len(competitor_activity)} recent tenders."

        # Generate HTML
        html = await generate_digest_html(
            user_id,
            tenders,
            [
                {
                    'title': a.title,
                    'competitor_name': a.competitor_name,
                    'status': a.status
                }
                for a in competitor_activity
            ],
            insights
        )

        # Create digest record
        digest = EmailDigest(
            user_id=user_id,
            digest_date=datetime.utcnow(),
            digest_html=html,
            digest_text=insights,
            tender_count=len(tenders),
            competitor_activity_count=len(competitor_activity)
        )

        db.add(digest)
        await db.commit()
        await db.refresh(digest)

        return digest


async def generate_all_digests(frequency: str = "daily"):
    """Generate digests for all eligible users"""

    print(f"[{datetime.utcnow()}] Generating {frequency} email digests...")

    async with AsyncSessionLocal() as db:
        # Get users with matching frequency
        query = select(UserPreferences).where(
            and_(
                UserPreferences.email_enabled == True,
                UserPreferences.notification_frequency == frequency
            )
        )
        result = await db.execute(query)
        prefs_list = result.scalars().all()

        print(f"Found {len(prefs_list)} users for {frequency} digest")

        generated_count = 0
        skipped_count = 0

        for prefs in prefs_list:
            try:
                digest = await generate_user_digest(str(prefs.user_id), frequency)
                if digest:
                    generated_count += 1
                    print(f"✓ Generated digest for user {prefs.user_id}")
                else:
                    skipped_count += 1
            except Exception as e:
                print(f"✗ Error for user {prefs.user_id}: {e}")
                skipped_count += 1

        print(f"\n[{datetime.utcnow()}] Generation complete:")
        print(f"  ✓ Generated: {generated_count}")
        print(f"  - Skipped: {skipped_count}")


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

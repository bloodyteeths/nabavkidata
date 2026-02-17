"""
Trial Service for nabavkidata.com
Manages 7-day Pro trial with credit-based usage

Trial Configuration:
- Duration: 7 days
- Credits: 50 AI messages, 15 document extractions, 5 exports, 20 competitor alerts
- Auto-downgrade to Free after trial expires
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from config.plans import TRIAL_DAYS, TRIAL_CREDITS, PlanTier

logger = logging.getLogger(__name__)


class TrialService:
    """Service for managing user trials"""

    def __init__(self):
        self.trial_days = TRIAL_DAYS  # 7 days
        self.credits = TRIAL_CREDITS

    async def start_trial(
        self,
        db: AsyncSession,
        user_id: str,
        email: str
    ) -> Dict[str, Any]:
        """
        Start a 7-day Pro trial for a user

        Args:
            db: Database session
            user_id: User's UUID
            email: User's email (for notifications)

        Returns:
            Dict with trial details

        Raises:
            ValueError: If user already had a trial
        """
        # Check if user already had a trial
        result = await db.execute(
            text("SELECT trial_started_at, trial_expired FROM users WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        row = result.fetchone()

        if row and row[0] is not None:
            raise ValueError("Корисникот веќе го искористил пробниот период")

        # Calculate trial end date
        now = datetime.utcnow()
        trial_ends = now + timedelta(days=self.trial_days)

        # Update user with trial dates
        await db.execute(
            text("""
                UPDATE users
                SET trial_started_at = :started,
                    trial_ends_at = :ends,
                    subscription_tier = 'trial',
                    updated_at = NOW()
                WHERE user_id = :user_id
            """),
            {
                "user_id": user_id,
                "started": now,
                "ends": trial_ends,
            }
        )

        # Create trial credits
        credits_to_create = [
            ("ai_messages", self.credits.ai_messages),
            ("document_extractions", self.credits.document_extractions),
            ("exports", self.credits.exports),
            ("competitor_alerts", self.credits.competitor_alerts),
        ]

        for credit_type, total in credits_to_create:
            await db.execute(
                text("""
                    INSERT INTO trial_credits (user_id, credit_type, total_credits, used_credits, expires_at)
                    VALUES (:user_id, :credit_type, :total, 0, :expires)
                    ON CONFLICT (user_id, credit_type) DO UPDATE
                    SET total_credits = :total, used_credits = 0, expires_at = :expires, updated_at = NOW()
                """),
                {
                    "user_id": user_id,
                    "credit_type": credit_type,
                    "total": total,
                    "expires": trial_ends,
                }
            )

        await db.commit()

        logger.info(f"Started trial for user {user_id}, expires {trial_ends}")

        return {
            "trial_started": True,
            "started_at": now.isoformat(),
            "ends_at": trial_ends.isoformat(),
            "days": self.trial_days,
            "credits": {
                "ai_messages": self.credits.ai_messages,
                "document_extractions": self.credits.document_extractions,
                "exports": self.credits.exports,
                "competitor_alerts": self.credits.competitor_alerts,
            }
        }

    async def get_trial_status(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get current trial status for a user

        Args:
            db: Database session
            user_id: User's UUID

        Returns:
            Dict with trial status and remaining credits
        """
        # Get user trial info
        result = await db.execute(
            text("""
                SELECT trial_started_at, trial_ends_at, trial_expired, subscription_tier
                FROM users WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )
        row = result.fetchone()

        if not row or row[0] is None:
            return {
                "in_trial": False,
                "eligible": True,
                "credits": None,
            }

        started, ends, expired, tier = row
        now = datetime.utcnow()

        # Check if trial is active
        if expired or (ends and ends < now):
            return {
                "in_trial": False,
                "eligible": False,
                "expired": True,
                "expired_at": ends.isoformat() if ends else None,
            }

        # Get remaining credits
        credits_result = await db.execute(
            text("""
                SELECT credit_type, total_credits, used_credits
                FROM trial_credits
                WHERE user_id = :user_id AND expires_at > NOW()
            """),
            {"user_id": user_id}
        )
        credits = {}
        for cr in credits_result:
            credits[cr[0]] = {
                "total": cr[1],
                "used": cr[2],
                "remaining": cr[1] - cr[2],
            }

        days_remaining = (ends - now).days if ends else 0

        return {
            "in_trial": True,
            "started_at": started.isoformat() if started else None,
            "ends_at": ends.isoformat() if ends else None,
            "days_remaining": max(0, days_remaining),
            "credits": credits,
        }

    async def use_credit(
        self,
        db: AsyncSession,
        user_id: str,
        credit_type: str,
        amount: int = 1
    ) -> Dict[str, Any]:
        """
        Use trial credits

        Args:
            db: Database session
            user_id: User's UUID
            credit_type: Type of credit to use
            amount: Amount to use (default: 1)

        Returns:
            Dict with remaining credits

        Raises:
            ValueError: If no credits available
        """
        # Get current credits
        result = await db.execute(
            text("""
                SELECT total_credits, used_credits
                FROM trial_credits
                WHERE user_id = :user_id
                  AND credit_type = :credit_type
                  AND expires_at > NOW()
                FOR UPDATE
            """),
            {"user_id": user_id, "credit_type": credit_type}
        )
        row = result.fetchone()

        if not row:
            raise ValueError(f"Нема достапни кредити за {credit_type}")

        total, used = row
        remaining = total - used

        if remaining < amount:
            raise ValueError(f"Недоволно кредити. Достапни: {remaining}, Побарани: {amount}")

        # Use credits
        await db.execute(
            text("""
                UPDATE trial_credits
                SET used_credits = used_credits + :amount, updated_at = NOW()
                WHERE user_id = :user_id AND credit_type = :credit_type
            """),
            {"user_id": user_id, "credit_type": credit_type, "amount": amount}
        )
        await db.commit()

        return {
            "credit_type": credit_type,
            "used": amount,
            "remaining": remaining - amount,
            "total": total,
        }

    async def expire_trials(self, db: AsyncSession) -> int:
        """
        Expire all trials that have passed their end date
        Should be run via cron job

        Args:
            db: Database session

        Returns:
            Number of trials expired
        """
        result = await db.execute(
            text("""
                UPDATE users
                SET trial_expired = TRUE,
                    subscription_tier = 'free',
                    updated_at = NOW()
                WHERE trial_ends_at < NOW()
                  AND trial_expired = FALSE
                  AND subscription_tier = 'trial'
                RETURNING user_id
            """)
        )
        expired_users = result.fetchall()
        await db.commit()

        count = len(expired_users)
        if count > 0:
            logger.info(f"Expired {count} trials")

        return count

    async def check_trial_eligibility(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Check if user is eligible for a trial

        Args:
            db: Database session
            user_id: User's UUID

        Returns:
            Dict with eligibility info
        """
        result = await db.execute(
            text("""
                SELECT trial_started_at, trial_expired, subscription_tier, created_at
                FROM users WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )
        row = result.fetchone()

        if not row:
            return {"eligible": False, "reason": "Корисникот не е пронајден"}

        trial_started, expired, tier, created = row

        # Already had a trial
        if trial_started is not None:
            return {
                "eligible": False,
                "reason": "Веќе го искористивте пробниот период",
                "trial_used": True,
            }

        # Already on a paid plan
        if tier and tier.lower() in ("starter", "professional", "enterprise"):
            return {
                "eligible": False,
                "reason": "Веќе имате платен план",
                "current_tier": tier,
            }

        # Account too old (30+ days)
        if created:
            account_age = (datetime.utcnow() - created).days
            if account_age > 30:
                return {
                    "eligible": False,
                    "reason": "Пробниот период е достапен само за нови корисници",
                    "account_age_days": account_age,
                }

        return {
            "eligible": True,
            "trial_days": self.trial_days,
            "credits": {
                "ai_messages": self.credits.ai_messages,
                "document_extractions": self.credits.document_extractions,
                "exports": self.credits.exports,
                "competitor_alerts": self.credits.competitor_alerts,
            }
        }


# Global trial service instance
trial_service = TrialService()

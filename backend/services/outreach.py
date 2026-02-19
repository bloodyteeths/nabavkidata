"""
Outreach Campaign Service
Handles sending personalized cold outreach emails via Postmark
"""
import os
import re
import json
import random
import hashlib
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlencode
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.dialects.postgresql import insert

from models import (
    Supplier, SupplierContact, OutreachMessage, OutreachTemplate,
    SuppressionList, TenderBidder
)

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

POSTMARK_SERVER_TOKEN = os.getenv("POSTMARK_SERVER_TOKEN", "")
POSTMARK_MESSAGE_STREAM = os.getenv("POSTMARK_MESSAGE_STREAM", "outreach")
POSTMARK_FROM_EMAIL = os.getenv("POSTMARK_FROM_EMAIL", "hello@nabavkidata.com")
POSTMARK_FROM_NAME = os.getenv("POSTMARK_FROM_NAME", "NabavkiData")

OUTREACH_DAILY_LIMIT = int(os.getenv("OUTREACH_DAILY_LIMIT", "3000"))
OUTREACH_HOURLY_LIMIT = int(os.getenv("OUTREACH_HOURLY_LIMIT", "200"))

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://nabavkidata.com")
UNSUBSCRIBE_SECRET = os.getenv("UNSUBSCRIBE_SECRET", "nabavki-unsub-secret-2025")

# Minimum confidence for outreach
MIN_CONFIDENCE_ROLE_BASED = 30
MIN_CONFIDENCE_PERSONAL = 70


class OutreachService:
    """Service for managing outreach campaigns via Postmark"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": POSTMARK_SERVER_TOKEN
            }
        )

    async def close(self):
        await self.http_client.aclose()

    # ========================================================================
    # SEGMENTATION
    # ========================================================================

    async def get_supplier_segment(self, supplier: Supplier) -> str:
        """
        Determine supplier segment based on their tender history
        - frequent_winner: >= 5 awards in last 12 months
        - occasional: 1-4 awards or bids in last 12 months
        - new_unknown: no recent activity
        """
        one_year_ago = datetime.utcnow() - timedelta(days=365)

        # Count recent wins
        wins_result = await self.db.execute(
            select(func.count(TenderBidder.bidder_id)).where(
                and_(
                    or_(
                        TenderBidder.company_name == supplier.company_name,
                        TenderBidder.company_tax_id == supplier.tax_id
                    ),
                    TenderBidder.is_winner == True,
                    TenderBidder.created_at >= one_year_ago
                )
            )
        )
        recent_wins = wins_result.scalar() or 0

        if recent_wins >= 5:
            return "frequent_winner"
        elif recent_wins >= 1:
            return "occasional"
        else:
            return "new_unknown"

    # ========================================================================
    # PERSONALIZATION
    # ========================================================================

    async def build_personalization(self, supplier: Supplier) -> Dict:
        """Build personalization data for email templates"""
        one_year_ago = datetime.utcnow() - timedelta(days=365)

        # Get recent awards count
        wins_result = await self.db.execute(
            select(func.count(TenderBidder.bidder_id)).where(
                and_(
                    or_(
                        TenderBidder.company_name == supplier.company_name,
                        TenderBidder.company_tax_id == supplier.tax_id
                    ),
                    TenderBidder.is_winner == True,
                    TenderBidder.created_at >= one_year_ago
                )
            )
        )
        recent_awards_count = wins_result.scalar() or 0

        # Get top CPV categories from industries
        top_cpv_categories = "различни категории"
        if supplier.industries:
            categories = supplier.industries if isinstance(supplier.industries, list) else []
            if categories:
                top_cpv_categories = ", ".join(categories[:2])

        # Get an example tender/authority
        example_tender = ""
        bidder_result = await self.db.execute(
            select(TenderBidder).where(
                or_(
                    TenderBidder.company_name == supplier.company_name,
                    TenderBidder.company_tax_id == supplier.tax_id
                )
            ).order_by(TenderBidder.created_at.desc()).limit(1)
        )
        recent_bidder = bidder_result.scalar_one_or_none()
        if recent_bidder:
            # Get tender details
            from models import Tender
            tender_result = await self.db.execute(
                select(Tender).where(Tender.tender_id == recent_bidder.tender_id)
            )
            tender = tender_result.scalar_one_or_none()
            if tender:
                example_tender = f"учествувавте во тендер за {tender.procuring_entity or 'државна институција'}"

        # Determine value pitch based on segment
        segment = await self.get_supplier_segment(supplier)
        value_pitches = {
            "frequent_winner": "Следете ја конкуренцијата и дознајте кога понудуваат",
            "occasional": "Не пропуштајте релевантни тендери со AI известувања",
            "new_unknown": "Пронајдете нови тендерски можности за вашиот бизнис"
        }
        value_pitch = value_pitches.get(segment, value_pitches["new_unknown"])

        return {
            "supplier_name": supplier.company_name,
            "top_cpv_categories": top_cpv_categories,
            "recent_awards_count": recent_awards_count,
            "example_tender": example_tender,
            "value_pitch": value_pitch,
            "segment": segment
        }

    # ========================================================================
    # UNSUBSCRIBE URL GENERATION
    # ========================================================================

    def generate_unsubscribe_url(self, email: str) -> str:
        """Generate a secure unsubscribe URL with token"""
        # Create HMAC token
        token_data = f"{email}:{UNSUBSCRIBE_SECRET}"
        token = hashlib.sha256(token_data.encode()).hexdigest()[:32]

        params = urlencode({
            "e": email,
            "t": token
        })

        return f"{FRONTEND_URL}/unsubscribe?{params}"

    def verify_unsubscribe_token(self, email: str, token: str) -> bool:
        """Verify an unsubscribe token"""
        expected_data = f"{email}:{UNSUBSCRIBE_SECRET}"
        expected_token = hashlib.sha256(expected_data.encode()).hexdigest()[:32]
        return token == expected_token

    # ========================================================================
    # TEMPLATE RENDERING
    # ========================================================================

    async def get_template(self, segment: str, sequence_step: int) -> Optional[OutreachTemplate]:
        """Get the appropriate template for segment and step"""
        # First try segment-specific
        result = await self.db.execute(
            select(OutreachTemplate).where(
                and_(
                    OutreachTemplate.segment == segment,
                    OutreachTemplate.sequence_step == sequence_step,
                    OutreachTemplate.is_active == True
                )
            ).limit(1)
        )
        template = result.scalar_one_or_none()

        # Fallback to "all" segment
        if not template:
            result = await self.db.execute(
                select(OutreachTemplate).where(
                    and_(
                        OutreachTemplate.segment == "all",
                        OutreachTemplate.sequence_step == sequence_step,
                        OutreachTemplate.is_active == True
                    )
                ).limit(1)
            )
            template = result.scalar_one_or_none()

        return template

    def render_template(self, template: OutreachTemplate, personalization: Dict, email: str) -> Tuple[str, str, str]:
        """Render template with personalization. Returns (subject, html, text)"""
        # Pick random subject variant
        subjects = template.subject_variants or ["NabavkiData"]
        if isinstance(subjects, str):
            subjects = json.loads(subjects)
        subject = random.choice(subjects)

        # Add unsubscribe URL to personalization
        personalization["unsubscribe_url"] = self.generate_unsubscribe_url(email)

        # Render subject
        for key, value in personalization.items():
            subject = subject.replace(f"{{{{{key}}}}}", str(value))

        # Render HTML body
        html_body = template.body_html
        for key, value in personalization.items():
            html_body = html_body.replace(f"{{{{{key}}}}}", str(value))

        # Render text body
        text_body = template.body_text or ""
        for key, value in personalization.items():
            text_body = text_body.replace(f"{{{{{key}}}}}", str(value))

        return subject, html_body, text_body

    # ========================================================================
    # RATE LIMITING
    # ========================================================================

    async def check_rate_limits(self) -> Tuple[bool, str]:
        """Check if we can send more emails (daily and hourly limits)"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_start = now.replace(minute=0, second=0, microsecond=0)

        # Count sent today
        daily_result = await self.db.execute(
            select(func.count(OutreachMessage.id)).where(
                and_(
                    OutreachMessage.sent_at >= today_start,
                    OutreachMessage.status.in_(["sent", "delivered", "opened", "clicked"])
                )
            )
        )
        daily_count = daily_result.scalar() or 0

        if daily_count >= OUTREACH_DAILY_LIMIT:
            return False, f"Daily limit reached ({daily_count}/{OUTREACH_DAILY_LIMIT})"

        # Count sent this hour
        hourly_result = await self.db.execute(
            select(func.count(OutreachMessage.id)).where(
                and_(
                    OutreachMessage.sent_at >= hour_start,
                    OutreachMessage.status.in_(["sent", "delivered", "opened", "clicked"])
                )
            )
        )
        hourly_count = hourly_result.scalar() or 0

        if hourly_count >= OUTREACH_HOURLY_LIMIT:
            return False, f"Hourly limit reached ({hourly_count}/{OUTREACH_HOURLY_LIMIT})"

        return True, f"OK (daily: {daily_count}/{OUTREACH_DAILY_LIMIT}, hourly: {hourly_count}/{OUTREACH_HOURLY_LIMIT})"

    # ========================================================================
    # ELIGIBILITY CHECKS
    # ========================================================================

    async def is_suppressed(self, email: str) -> bool:
        """Check if email is in suppression list"""
        result = await self.db.execute(
            select(SuppressionList).where(SuppressionList.email == email.lower())
        )
        return result.scalar_one_or_none() is not None

    async def get_eligible_contact(self, supplier: Supplier) -> Optional[SupplierContact]:
        """Get the best eligible contact for outreach"""
        # Get contacts ordered by preference
        result = await self.db.execute(
            select(SupplierContact).where(
                and_(
                    SupplierContact.supplier_id == supplier.supplier_id,
                    SupplierContact.status.in_(["new", "verified"])
                )
            ).order_by(
                # Prefer role_based, then by confidence
                SupplierContact.email_type.desc(),  # role_based > personal > unknown
                SupplierContact.confidence_score.desc()
            )
        )
        contacts = result.scalars().all()

        for contact in contacts:
            # Check confidence thresholds
            if contact.email_type == "role_based" and contact.confidence_score >= MIN_CONFIDENCE_ROLE_BASED:
                if not await self.is_suppressed(contact.email):
                    return contact
            elif contact.email_type == "personal" and contact.confidence_score >= MIN_CONFIDENCE_PERSONAL:
                if not await self.is_suppressed(contact.email):
                    return contact
            elif contact.email_type == "unknown" and contact.confidence_score >= MIN_CONFIDENCE_PERSONAL:
                if not await self.is_suppressed(contact.email):
                    return contact

        return None

    async def has_pending_outreach(self, supplier_id: str, campaign_id: str = "default") -> bool:
        """Check if supplier already has pending/active outreach"""
        result = await self.db.execute(
            select(OutreachMessage).where(
                and_(
                    OutreachMessage.supplier_id == supplier_id,
                    OutreachMessage.campaign_id == campaign_id,
                    OutreachMessage.status.in_(["queued", "sent", "delivered", "opened", "clicked"])
                )
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    # ========================================================================
    # SENDING
    # ========================================================================

    async def send_email(
        self,
        supplier: Supplier,
        contact: SupplierContact,
        sequence_step: int = 0,
        campaign_id: str = "default",
        dry_run: bool = False
    ) -> Dict:
        """Send a single outreach email"""

        # Build personalization
        personalization = await self.build_personalization(supplier)

        # Get template
        template = await self.get_template(personalization["segment"], sequence_step)
        if not template:
            return {"error": "No template found", "supplier_id": str(supplier.supplier_id)}

        # Render template
        subject, html_body, text_body = self.render_template(
            template, personalization, contact.email
        )

        # Create outreach message record
        message = OutreachMessage(
            supplier_id=supplier.supplier_id,
            contact_id=contact.id,
            campaign_id=campaign_id,
            sequence_step=sequence_step,
            subject=subject,
            template_version=template.version,
            personalization=personalization,
            status="queued"
        )
        self.db.add(message)
        await self.db.commit()

        if dry_run:
            return {
                "dry_run": True,
                "message_id": str(message.id),
                "supplier_name": supplier.company_name,
                "email": contact.email,
                "subject": subject,
                "segment": personalization["segment"],
                "personalization": personalization
            }

        # Send via Postmark
        try:
            payload = {
                "From": f"{POSTMARK_FROM_NAME} <{POSTMARK_FROM_EMAIL}>",
                "To": contact.email,
                "Subject": subject,
                "HtmlBody": html_body,
                "TextBody": text_body,
                "MessageStream": POSTMARK_MESSAGE_STREAM,
                "TrackOpens": True,
                "TrackLinks": "HtmlAndText",
                "Tag": f"outreach-{campaign_id}",
                "Metadata": {
                    "supplier_id": str(supplier.supplier_id),
                    "contact_id": str(contact.id),
                    "message_id": str(message.id),
                    "segment": personalization["segment"]
                }
            }

            resp = await self.http_client.post(
                "https://api.postmarkapp.com/email",
                json=payload
            )

            if resp.status_code == 200:
                data = resp.json()
                message.postmark_message_id = data.get("MessageID")
                message.status = "sent"
                message.sent_at = datetime.utcnow()
                await self.db.commit()

                return {
                    "success": True,
                    "message_id": str(message.id),
                    "postmark_id": data.get("MessageID"),
                    "supplier_name": supplier.company_name,
                    "email": contact.email,
                    "subject": subject
                }
            else:
                error_msg = resp.text
                message.status = "failed"
                message.metadata = {"error": error_msg}
                await self.db.commit()

                return {"error": error_msg, "supplier_id": str(supplier.supplier_id)}

        except Exception as e:
            logger.error(f"Postmark send error: {e}")
            message.status = "failed"
            message.metadata = {"error": str(e)}
            await self.db.commit()
            return {"error": str(e), "supplier_id": str(supplier.supplier_id)}

    # ========================================================================
    # CAMPAIGN EXECUTION
    # ========================================================================

    async def run_campaign(
        self,
        segment: Optional[str] = None,
        limit: int = 100,
        campaign_id: str = "default",
        dry_run: bool = False
    ) -> Dict:
        """Run outreach campaign for a segment"""

        stats = {
            "total_eligible": 0,
            "sent": 0,
            "skipped_rate_limit": 0,
            "skipped_no_contact": 0,
            "skipped_already_contacted": 0,
            "errors": 0,
            "messages": []
        }

        # Get suppliers with contacts
        query = select(Supplier).join(
            SupplierContact,
            Supplier.supplier_id == SupplierContact.supplier_id
        ).where(
            SupplierContact.status.in_(["new", "verified"])
        ).distinct().order_by(
            Supplier.total_wins.desc().nullslast()
        ).limit(limit * 2)  # Get more to account for filtering

        result = await self.db.execute(query)
        suppliers = result.scalars().all()

        for supplier in suppliers:
            if stats["sent"] >= limit:
                break

            # Check rate limits
            can_send, rate_msg = await self.check_rate_limits()
            if not can_send and not dry_run:
                stats["skipped_rate_limit"] += 1
                continue

            # Check if already contacted
            if await self.has_pending_outreach(str(supplier.supplier_id), campaign_id):
                stats["skipped_already_contacted"] += 1
                continue

            # Get eligible contact
            contact = await self.get_eligible_contact(supplier)
            if not contact:
                stats["skipped_no_contact"] += 1
                continue

            # Filter by segment if specified
            supplier_segment = await self.get_supplier_segment(supplier)
            if segment and supplier_segment != segment:
                continue

            stats["total_eligible"] += 1

            # Send email
            result = await self.send_email(
                supplier=supplier,
                contact=contact,
                sequence_step=0,
                campaign_id=campaign_id,
                dry_run=dry_run
            )

            if "error" in result:
                stats["errors"] += 1
            else:
                stats["sent"] += 1
                stats["messages"].append(result)

        return stats


# ============================================================================
# SUPPRESSION MANAGEMENT
# ============================================================================

async def add_to_suppression(
    db: AsyncSession,
    email: str,
    reason: str,
    source: str = "manual",
    notes: str = None
) -> bool:
    """Add email to suppression list and update contact status"""
    email = email.lower().strip()

    try:
        # Add to suppression list
        stmt = insert(SuppressionList).values(
            email=email,
            reason=reason,
            source=source,
            notes=notes
        ).on_conflict_do_nothing(index_elements=["email"])
        await db.execute(stmt)

        # Update any supplier_contacts
        await db.execute(
            text("""
                UPDATE supplier_contacts
                SET status = :status, updated_at = NOW()
                WHERE email = :email
            """),
            {"status": "unsubscribed" if reason == "unsubscribed" else "bounced", "email": email}
        )

        # Stop any pending outreach
        await db.execute(
            text("""
                UPDATE outreach_messages om
                SET status = 'stopped', updated_at = NOW()
                FROM supplier_contacts sc
                WHERE om.contact_id = sc.id
                  AND sc.email = :email
                  AND om.status IN ('queued')
            """),
            {"email": email}
        )

        await db.commit()
        return True

    except Exception as e:
        logger.error(f"Error adding to suppression: {e}")
        return False

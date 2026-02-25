"""
Postmark Email Service for nabavkidata.com
Handles all transactional emails via Postmark HTTP API
"""

import os
import logging
import httpx
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Postmark API Configuration
POSTMARK_API_URL = "https://api.postmarkapp.com/email"
POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN", "")
POSTMARK_FROM_EMAIL = os.getenv("POSTMARK_FROM_EMAIL", "hello@nabavkidata.com")
POSTMARK_FROM_NAME = os.getenv("POSTMARK_FROM_NAME", "NabavkiData")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://nabavkidata.com")


class PostmarkService:
    """Async email service using Postmark HTTP API."""

    def __init__(self):
        self.api_url = POSTMARK_API_URL
        self.api_token = POSTMARK_API_TOKEN
        self.from_email = POSTMARK_FROM_EMAIL
        self.from_name = POSTMARK_FROM_NAME
        self.frontend_url = FRONTEND_URL

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Postmark API requests."""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": self.api_token
        }

    async def send_email(
        self,
        to: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        tag: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Send a transactional email via Postmark API.

        Args:
            to: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text version (optional)
            tag: Email tag for tracking (optional)
            reply_to: Reply-to email address

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.api_token:
            logger.error("POSTMARK_API_TOKEN not configured")
            return False

        # Build the request payload
        payload: Dict[str, Any] = {
            "From": f"{self.from_name} <{self.from_email}>",
            "To": to,
            "Subject": subject,
            "HtmlBody": html_content,
            "MessageStream": "outbound"
        }

        # Add plain text if provided
        if text_content:
            payload["TextBody"] = text_content
        else:
            # Generate plain text from HTML
            import re
            text_content = re.sub('<[^<]+?>', '', html_content)
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            payload["TextBody"] = text_content

        # Add optional fields
        if tag:
            payload["Tag"] = tag
        if reply_to:
            payload["ReplyTo"] = reply_to

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=self._get_headers(),
                    json=payload
                )

                if response.status_code == 200:
                    logger.info(f"Email sent successfully to {to} - Subject: {subject}")
                    return True
                else:
                    logger.error(
                        f"Postmark API error: {response.status_code} - {response.text}"
                    )
                    return False

        except httpx.TimeoutException:
            logger.error(f"Timeout sending email to {to}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {str(e)}")
            return False

    def _get_email_template(
        self,
        title: str,
        content: str,
        button_text: Optional[str] = None,
        button_link: Optional[str] = None
    ) -> str:
        """
        Generate HTML email template with inline CSS.

        Args:
            title: Email title
            content: Main content text (can include HTML)
            button_text: Optional button text
            button_link: Optional button link

        Returns:
            str: HTML email template
        """
        button_html = ""
        if button_text and button_link:
            button_html = f"""
            <table role="presentation" style="margin: 30px auto;">
                <tr>
                    <td style="border-radius: 4px; background-color: #2563eb;">
                        <a href="{button_link}" target="_blank" style="display: inline-block; padding: 14px 40px; font-family: Arial, sans-serif; font-size: 16px; color: #ffffff; text-decoration: none; border-radius: 4px; font-weight: 600;">
                            {button_text}
                        </a>
                    </td>
                </tr>
            </table>
            """

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f4f4f7; padding: 40px 0;">
        <tr>
            <td align="center">
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 30px; text-align: center; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); border-radius: 12px 12px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 26px; font-weight: 700; letter-spacing: -0.5px;">
                                {title}
                            </h1>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <div style="color: #374151; font-size: 16px; line-height: 1.7;">
                                {content}
                            </div>
                            {button_html}
                            <div style="margin-top: 35px; padding-top: 25px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                <p style="margin: 0 0 8px 0;">Best regards,</p>
                                <p style="margin: 0; font-weight: 600; color: #374151;">The NabavkiData Team</p>
                            </div>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 25px 40px; background-color: #f9fafb; border-radius: 0 0 12px 12px; text-align: center;">
                            <p style="margin: 0 0 10px 0; color: #9ca3af; font-size: 12px;">
                                &copy; 2025 NabavkiData. All rights reserved.
                            </p>
                            <p style="margin: 0 0 10px 0; color: #9ca3af; font-size: 12px;">
                                Skopje, North Macedonia
                            </p>
                            <p style="margin: 0; color: #9ca3af; font-size: 11px;">
                                <a href="{self.frontend_url}/privacy" style="color: #2563eb; text-decoration: none;">Privacy Policy</a> |
                                <a href="mailto:support@nabavkidata.com" style="color: #2563eb; text-decoration: none;">Contact Support</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    async def send_verification_email(self, email: str, token: str, name: str) -> bool:
        """Send email verification link to user."""
        verification_link = f"{self.frontend_url}/auth/verify-email?token={token}"

        content = f"""
        <p>Здраво <strong>{name}</strong>,</p>
        <p>Ви благодариме за регистрацијата на NabavkiData. За да ја завршите регистрацијата и да го активирате вашиот профил, потврдете ја вашата е-пошта со кликнување на копчето подолу.</p>
        <p style="margin-top: 20px; padding: 15px; background-color: #fef3c7; border-left: 4px solid #f59e0b; color: #92400e; font-size: 14px;">
            <strong>Напомена:</strong> Овој линк ќе истече за 24 часа.
        </p>
        <p style="margin-top: 20px; font-size: 14px; color: #6b7280;">
            Доколку не креиравте профил на NabavkiData, можете слободно да ја игнорирате оваа порака.
        </p>
        """

        html_content = self._get_email_template(
            title="Потврдете ја вашата е-пошта",
            content=content,
            button_text="Потврди е-пошта",
            button_link=verification_link
        )

        return await self.send_email(
            to=email,
            subject="Потврдете ја вашата е-пошта - NabavkiData",
            html_content=html_content,
            tag="verification",
            reply_to="support@nabavkidata.com"
        )

    async def send_password_reset_email(self, email: str, token: str, name: str) -> bool:
        """Send password reset link to user."""
        reset_link = f"{self.frontend_url}/auth/reset-password?token={token}"

        content = f"""
        <p>Здраво <strong>{name}</strong>,</p>
        <p>Добивме барање за промена на лозинката на вашиот NabavkiData профил.</p>
        <p style="margin-top: 20px;">Кликнете на копчето подолу за да ја промените лозинката. Овој линк ќе истече за <strong>1 час</strong>.</p>
        <p style="margin-top: 25px; padding: 15px; background-color: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; font-size: 14px;">
            <strong>Безбедносно известување:</strong> Доколку не побаравте промена на лозинка, игнорирајте ја оваа порака или контактирајте не доколку имате грижи за безбедноста на вашиот профил.
        </p>
        """

        html_content = self._get_email_template(
            title="Промена на лозинка",
            content=content,
            button_text="Промени лозинка",
            button_link=reset_link
        )

        return await self.send_email(
            to=email,
            subject="Барање за промена на лозинка - NabavkiData",
            html_content=html_content,
            tag="password-reset",
            reply_to="support@nabavkidata.com"
        )

    async def send_welcome_email(self, email: str, name: str) -> bool:
        """Send welcome email after successful verification."""
        dashboard_link = f"{self.frontend_url}/dashboard"

        content = f"""
        <p>Здраво <strong>{name}</strong>,</p>
        <p>Добредојдовте на NabavkiData! Вашата е-пошта е успешно потврдена и вашиот профил е активен.</p>
        <p style="margin-top: 20px;">Сега имате пристап до сите функции на платформата:</p>
        <ul style="color: #374151; font-size: 16px; line-height: 2; margin-top: 15px; padding-left: 20px;">
            <li>Пребарувајте јавни набавки</li>
            <li>Поставете персонализирани известувања за тендери</li>
            <li>Следете ги зачуваните тендери</li>
            <li>Добијте AI препораки за тендери</li>
        </ul>
        <p style="margin-top: 25px;">Започнете со прегледување на контролната табла:</p>
        """

        html_content = self._get_email_template(
            title="Добредојдовте на NabavkiData!",
            content=content,
            button_text="Оди на контролна табла",
            button_link=dashboard_link
        )

        return await self.send_email(
            to=email,
            subject="Добредојдовте на NabavkiData!",
            html_content=html_content,
            tag="welcome",
            reply_to="support@nabavkidata.com"
        )

    async def send_password_changed_email(self, email: str, name: str) -> bool:
        """Send confirmation email after password change."""
        content = f"""
        <p>Здраво <strong>{name}</strong>,</p>
        <p>Ова е потврда дека лозинката на вашиот NabavkiData профил е успешно променета.</p>
        <p style="margin-top: 20px; padding: 15px; background-color: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; font-size: 14px;">
            <strong>Важно:</strong> Доколку не ја направивте оваа промена, контактирајте не веднаш за да го заштитите вашиот профил.
        </p>
        <p style="margin-top: 25px;"><strong>Совети за безбедност:</strong></p>
        <ul style="color: #374151; font-size: 16px; line-height: 2; margin-top: 10px; padding-left: 20px;">
            <li>Користете силна, уникатна лозинка</li>
            <li>Никогаш не ја споделувајте лозинката</li>
            <li>Активирајте двофакторска автентикација доколку е достапна</li>
        </ul>
        """

        html_content = self._get_email_template(
            title="Лозинката е успешно променета",
            content=content,
            button_text="Контактирај поддршка",
            button_link="mailto:support@nabavkidata.com"
        )

        return await self.send_email(
            to=email,
            subject="Промена на лозинка - NabavkiData",
            html_content=html_content,
            tag="security",
            reply_to="support@nabavkidata.com"
        )


    async def send_tender_notification(
        self,
        email: str,
        name: str,
        tender_title: str,
        tender_id: str,
        contracting_authority: str,
        estimated_value: Optional[str] = None,
        deadline: Optional[str] = None,
        category: Optional[str] = None
    ) -> bool:
        """Send tender notification email to user."""
        from urllib.parse import quote
        tender_link = f"{self.frontend_url}/tenders/{quote(tender_id, safe='')}"

        details_html = f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Contracting Authority:</td>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{contracting_authority}</td>
        </tr>
        """

        if estimated_value:
            details_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Estimated Value:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{estimated_value}</td>
            </tr>
            """

        if deadline:
            details_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Deadline:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #dc2626;">{deadline}</td>
            </tr>
            """

        if category:
            details_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Category:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{category}</td>
            </tr>
            """

        content = f"""
        <p>Hello <strong>{name}</strong>,</p>
        <p>A new tender matching your criteria has been published:</p>
        <div style="margin: 25px 0; padding: 20px; background-color: #f0f9ff; border-radius: 8px; border-left: 4px solid #2563eb;">
            <h3 style="margin: 0 0 15px 0; color: #1e40af; font-size: 18px;">{tender_title}</h3>
            <table style="width: 100%; border-collapse: collapse;">
                {details_html}
            </table>
        </div>
        <p>Click below to view full tender details and documents:</p>
        """

        html_content = self._get_email_template(
            title="New Tender Alert",
            content=content,
            button_text="View Tender Details",
            button_link=tender_link
        )

        return await self.send_email(
            to=email,
            subject=f"New Tender: {tender_title[:50]}..." if len(tender_title) > 50 else f"New Tender: {tender_title}",
            html_content=html_content,
            tag="tender-alert",
            reply_to="support@nabavkidata.com"
        )

    async def send_test_email(self, to: str) -> bool:
        """Send a test email to verify configuration."""
        content = """
        <p>This is a test email from NabavkiData.</p>
        <p>If you received this email, your email configuration is working correctly.</p>
        <p style="margin-top: 20px; padding: 15px; background-color: #d1fae5; border-left: 4px solid #10b981; color: #065f46;">
            <strong>Success!</strong> Your Postmark integration is configured correctly.
        </p>
        """

        html_content = self._get_email_template(
            title="Test Email - NabavkiData",
            content=content,
            button_text="Visit NabavkiData",
            button_link=self.frontend_url
        )

        return await self.send_email(
            to=to,
            subject="Test Email - NabavkiData",
            html_content=html_content,
            tag="test"
        )


# Global postmark service instance
postmark_service = PostmarkService()


# Convenience functions for easy import
async def send_verification_email(email: str, token: str, name: str) -> bool:
    """Send verification email to user."""
    return await postmark_service.send_verification_email(email, token, name)


async def send_password_reset_email(email: str, token: str, name: str) -> bool:
    """Send password reset email to user."""
    return await postmark_service.send_password_reset_email(email, token, name)


async def send_welcome_email(email: str, name: str) -> bool:
    """Send welcome email to user."""
    return await postmark_service.send_welcome_email(email, name)


async def send_password_changed_email(email: str, name: str) -> bool:
    """Send password changed confirmation email to user."""
    return await postmark_service.send_password_changed_email(email, name)


async def send_tender_notification(
    email: str,
    name: str,
    tender_title: str,
    tender_id: str,
    contracting_authority: str,
    estimated_value: Optional[str] = None,
    deadline: Optional[str] = None,
    category: Optional[str] = None
) -> bool:
    """Send tender notification email to user."""
    return await postmark_service.send_tender_notification(
        email, name, tender_title, tender_id, contracting_authority,
        estimated_value, deadline, category
    )


async def send_test_email(to: str) -> bool:
    """Send test email."""
    return await postmark_service.send_test_email(to)

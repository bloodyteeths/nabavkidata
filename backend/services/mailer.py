"""
Mailersend Email Service for nabavkidata.com
Handles all transactional emails via Mailersend HTTP API
"""

import os
import logging
import httpx
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# Mailersend API Configuration
MAILERSEND_API_URL = "https://api.mailersend.com/v1/email"
MAILERSEND_API_KEY = os.getenv("MAILERSEND_API_KEY", "")
MAILERSEND_FROM_EMAIL = os.getenv("MAILERSEND_FROM_EMAIL", "noreply@nabavkidata.com")
MAILERSEND_FROM_NAME = os.getenv("MAILERSEND_FROM_NAME", "NabavkiData")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://nabavkidata.com")


class MailerService:
    """Async email service using Mailersend HTTP API."""

    def __init__(self):
        self.api_url = MAILERSEND_API_URL
        self.api_key = MAILERSEND_API_KEY
        self.from_email = MAILERSEND_FROM_EMAIL
        self.from_name = MAILERSEND_FROM_NAME
        self.frontend_url = FRONTEND_URL

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Mailersend API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }

    async def send_transactional_email(
        self,
        to: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        template_id: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Send a transactional email via Mailersend API.

        Args:
            to: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text version (optional)
            template_id: Mailersend template ID (optional, overrides html_content)
            variables: Template variables for personalization
            reply_to: Reply-to email address

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.api_key:
            logger.error("MAILERSEND_API_KEY not configured")
            return False

        # Build the request payload
        payload: Dict[str, Any] = {
            "from": {
                "email": self.from_email,
                "name": self.from_name
            },
            "to": [
                {"email": to}
            ],
            "subject": subject
        }

        # Use template if provided, otherwise use HTML content
        if template_id:
            payload["template_id"] = template_id
            if variables:
                payload["personalization"] = [
                    {
                        "email": to,
                        "data": variables
                    }
                ]
        else:
            payload["html"] = html_content
            if text_content:
                payload["text"] = text_content
            else:
                # Generate plain text from HTML
                import re
                text_content = re.sub('<[^<]+?>', '', html_content)
                text_content = re.sub(r'\s+', ' ', text_content).strip()
                payload["text"] = text_content

        # Add reply-to if provided
        if reply_to:
            payload["reply_to"] = {"email": reply_to}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=self._get_headers(),
                    json=payload
                )

                if response.status_code in (200, 202):
                    logger.info(f"Email sent successfully to {to} - Subject: {subject}")
                    return True
                else:
                    logger.error(
                        f"Mailersend API error: {response.status_code} - {response.text}"
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
                                <a href="{self.frontend_url}/unsubscribe" style="color: #2563eb; text-decoration: none;">Unsubscribe</a> |
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
        """
        Send email verification link to user.

        Args:
            email: User's email address
            token: Verification token
            name: User's name

        Returns:
            bool: True if sent successfully
        """
        verification_link = f"{self.frontend_url}/auth/verify-email?token={token}"

        content = f"""
        <p>Hello <strong>{name}</strong>,</p>
        <p>Thank you for registering with NabavkiData. To complete your registration and activate your account, please verify your email address by clicking the button below.</p>
        <p style="margin-top: 20px; padding: 15px; background-color: #fef3c7; border-left: 4px solid #f59e0b; color: #92400e; font-size: 14px;">
            <strong>Note:</strong> This verification link will expire in 24 hours.
        </p>
        <p style="margin-top: 20px; font-size: 14px; color: #6b7280;">
            If you didn't create an account with NabavkiData, you can safely ignore this email.
        </p>
        """

        html_content = self._get_email_template(
            title="Verify Your Email Address",
            content=content,
            button_text="Verify Email Address",
            button_link=verification_link
        )

        return await self.send_transactional_email(
            to=email,
            subject="Verify Your Email Address - NabavkiData",
            html_content=html_content,
            reply_to="support@nabavkidata.com"
        )

    async def send_password_reset_email(self, email: str, token: str, name: str) -> bool:
        """
        Send password reset link to user.

        Args:
            email: User's email address
            token: Password reset token
            name: User's name

        Returns:
            bool: True if sent successfully
        """
        reset_link = f"{self.frontend_url}/auth/reset-password?token={token}"

        content = f"""
        <p>Hello <strong>{name}</strong>,</p>
        <p>We received a request to reset the password for your NabavkiData account.</p>
        <p style="margin-top: 20px;">Click the button below to reset your password. This link will expire in <strong>1 hour</strong>.</p>
        <p style="margin-top: 25px; padding: 15px; background-color: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; font-size: 14px;">
            <strong>Security Notice:</strong> If you didn't request a password reset, please ignore this email or contact support if you have concerns about your account security.
        </p>
        """

        html_content = self._get_email_template(
            title="Reset Your Password",
            content=content,
            button_text="Reset Password",
            button_link=reset_link
        )

        return await self.send_transactional_email(
            to=email,
            subject="Password Reset Request - NabavkiData",
            html_content=html_content,
            reply_to="support@nabavkidata.com"
        )

    async def send_welcome_email(self, email: str, name: str) -> bool:
        """
        Send welcome email after successful verification.

        Args:
            email: User's email address
            name: User's name

        Returns:
            bool: True if sent successfully
        """
        dashboard_link = f"{self.frontend_url}/dashboard"

        content = f"""
        <p>Hello <strong>{name}</strong>,</p>
        <p>Welcome to NabavkiData! Your email has been successfully verified and your account is now active.</p>
        <p style="margin-top: 20px;">You can now access all features of our platform:</p>
        <ul style="color: #374151; font-size: 16px; line-height: 2; margin-top: 15px; padding-left: 20px;">
            <li>Browse public procurement opportunities</li>
            <li>Set up personalized tender alerts</li>
            <li>Track your saved tenders</li>
            <li>Get AI-powered tender recommendations</li>
        </ul>
        <p style="margin-top: 25px;">Get started by exploring your dashboard:</p>
        """

        html_content = self._get_email_template(
            title="Welcome to NabavkiData!",
            content=content,
            button_text="Go to Dashboard",
            button_link=dashboard_link
        )

        return await self.send_transactional_email(
            to=email,
            subject="Welcome to NabavkiData - Let's Get Started!",
            html_content=html_content,
            reply_to="support@nabavkidata.com"
        )

    async def send_password_changed_email(self, email: str, name: str) -> bool:
        """
        Send confirmation email after password change.

        Args:
            email: User's email address
            name: User's name

        Returns:
            bool: True if sent successfully
        """
        support_link = f"{self.frontend_url}/support"

        content = f"""
        <p>Hello <strong>{name}</strong>,</p>
        <p>This is to confirm that the password for your NabavkiData account has been successfully changed.</p>
        <p style="margin-top: 20px; padding: 15px; background-color: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; font-size: 14px;">
            <strong>Important:</strong> If you did not make this change, please contact our support team immediately to secure your account.
        </p>
        <p style="margin-top: 25px;"><strong>Account Security Tips:</strong></p>
        <ul style="color: #374151; font-size: 16px; line-height: 2; margin-top: 10px; padding-left: 20px;">
            <li>Use a strong, unique password</li>
            <li>Never share your password with anyone</li>
            <li>Enable two-factor authentication if available</li>
        </ul>
        """

        html_content = self._get_email_template(
            title="Password Changed Successfully",
            content=content,
            button_text="Contact Support",
            button_link=support_link
        )

        return await self.send_transactional_email(
            to=email,
            subject="Password Changed - NabavkiData",
            html_content=html_content,
            reply_to="support@nabavkidata.com"
        )

    async def send_scraper_failure_alert(
        self,
        admin_email: str,
        job_id: str,
        error_message: str,
        tenders_scraped: int = 0
    ) -> bool:
        """
        Send scraper failure alert to admin.

        Args:
            admin_email: Admin email address
            job_id: Scraping job ID
            error_message: Error message from scraper
            tenders_scraped: Number of tenders scraped before failure

        Returns:
            bool: True if sent successfully
        """
        admin_link = f"{self.frontend_url}/admin/scraper"

        content = f"""
        <p style="padding: 15px; background-color: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; font-size: 16px;">
            <strong>Alert:</strong> A scraping job has failed and requires attention.
        </p>
        <p style="margin-top: 20px;"><strong>Job Details:</strong></p>
        <table style="width: 100%; margin-top: 10px; border-collapse: collapse;">
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Job ID:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{job_id}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Status:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #ef4444; font-weight: 600;">Failed</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Tenders Scraped:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{tenders_scraped}</td>
            </tr>
        </table>
        <p style="margin-top: 20px;"><strong>Error Message:</strong></p>
        <p style="padding: 15px; background-color: #f3f4f6; border-left: 3px solid #6b7280; font-family: monospace; font-size: 13px; color: #374151; word-break: break-word;">
            {error_message}
        </p>
        <p style="margin-top: 25px;">Please investigate this issue and restart the scraper if necessary.</p>
        """

        html_content = self._get_email_template(
            title="Scraper Failure Alert",
            content=content,
            button_text="View Scraper Status",
            button_link=admin_link
        )

        return await self.send_transactional_email(
            to=admin_email,
            subject="[ALERT] Scraper Job Failed - NabavkiData",
            html_content=html_content,
            reply_to="admin@nabavkidata.com"
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
        """
        Send tender notification email to user.

        Args:
            email: User's email address
            name: User's name
            tender_title: Title of the tender
            tender_id: Tender ID for link
            contracting_authority: Name of contracting authority
            estimated_value: Estimated contract value
            deadline: Submission deadline
            category: Tender category

        Returns:
            bool: True if sent successfully
        """
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

        return await self.send_transactional_email(
            to=email,
            subject=f"New Tender: {tender_title[:50]}... - NabavkiData",
            html_content=html_content,
            reply_to="support@nabavkidata.com"
        )

    async def send_test_email(self, to: str) -> bool:
        """
        Send a test email to verify Mailersend configuration.

        Args:
            to: Recipient email address

        Returns:
            bool: True if sent successfully
        """
        from datetime import datetime

        content = f"""
        <p>This is a test email from NabavkiData to verify that Mailersend is configured correctly.</p>
        <p style="margin-top: 20px;"><strong>Configuration Details:</strong></p>
        <table style="width: 100%; margin-top: 10px; border-collapse: collapse;">
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Sent at:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">From:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{self.from_email}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Service:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">Mailersend API</td>
            </tr>
        </table>
        <p style="margin-top: 25px; padding: 15px; background-color: #d1fae5; border-left: 4px solid #10b981; color: #065f46; font-size: 14px;">
            <strong>Success!</strong> If you're reading this, your email configuration is working correctly.
        </p>
        """

        html_content = self._get_email_template(
            title="Test Email - NabavkiData",
            content=content,
            button_text="Visit Dashboard",
            button_link=f"{self.frontend_url}/dashboard"
        )

        return await self.send_transactional_email(
            to=to,
            subject="[TEST] NabavkiData Email Configuration Test",
            html_content=html_content
        )


# Global mailer service instance
mailer_service = MailerService()


# Convenience functions for easy import (backwards compatible with old email_service)
async def send_verification_email(email: str, token: str, name: str) -> bool:
    """Send verification email to user."""
    return await mailer_service.send_verification_email(email, token, name)


async def send_password_reset_email(email: str, token: str, name: str) -> bool:
    """Send password reset email to user."""
    return await mailer_service.send_password_reset_email(email, token, name)


async def send_welcome_email(email: str, name: str) -> bool:
    """Send welcome email to user."""
    return await mailer_service.send_welcome_email(email, name)


async def send_password_changed_email(email: str, name: str) -> bool:
    """Send password changed confirmation email to user."""
    return await mailer_service.send_password_changed_email(email, name)


async def send_scraper_failure_alert(
    admin_email: str,
    job_id: str,
    error_message: str,
    tenders_scraped: int = 0
) -> bool:
    """Send scraper failure alert to admin."""
    return await mailer_service.send_scraper_failure_alert(
        admin_email, job_id, error_message, tenders_scraped
    )


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
    return await mailer_service.send_tender_notification(
        email, name, tender_title, tender_id, contracting_authority,
        estimated_value, deadline, category
    )


async def send_test_email(to: str) -> bool:
    """Send test email to verify configuration."""
    return await mailer_service.send_test_email(to)

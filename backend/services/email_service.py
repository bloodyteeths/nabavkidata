import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import aiosmtplib

logger = logging.getLogger(__name__)


class EmailService:
    """Async email service for sending transactional emails."""

    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_user)
        self.from_name = os.getenv('FROM_NAME', 'Nabavki Platform')

    async def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """
        Send an email using aiosmtplib.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = f"{self.from_name} <{self.from_email}>"
            message['To'] = to_email

            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)

            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True
            )

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    def _get_email_template(self, title: str, content: str, button_text: Optional[str] = None, button_link: Optional[str] = None) -> str:
        """
        Generate HTML email template with inline CSS.

        Args:
            title: Email title
            content: Main content text
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
                    <td style="border-radius: 4px; background-color: #007bff;">
                        <a href="{button_link}" target="_blank" style="display: inline-block; padding: 12px 40px; font-family: Arial, sans-serif; font-size: 16px; color: #ffffff; text-decoration: none; border-radius: 4px;">
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
        <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
            <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f4f4f4; padding: 20px 0;">
                <tr>
                    <td align="center">
                        <table role="presentation" style="width: 600px; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <tr>
                                <td style="padding: 40px 30px; text-align: center; background-color: #007bff; border-radius: 8px 8px 0 0;">
                                    <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">
                                        {title}
                                    </h1>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 40px 30px;">
                                    <div style="color: #333333; font-size: 16px; line-height: 1.6;">
                                        {content}
                                    </div>
                                    {button_html}
                                    <div style="margin-top: 30px; padding-top: 30px; border-top: 1px solid #eeeeee; color: #666666; font-size: 14px; line-height: 1.5;">
                                        <p style="margin: 0 0 10px 0;">Best regards,</p>
                                        <p style="margin: 0; font-weight: 600;">The Nabavki Team</p>
                                    </div>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 20px 30px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; text-align: center;">
                                    <p style="margin: 0; color: #999999; font-size: 12px;">
                                        &copy; 2025 Nabavki Platform. All rights reserved.
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
        verification_link = f"{self.frontend_url}/verify-email?token={token}"

        content = f"""
        <p>Hello <strong>{name}</strong>,</p>
        <p>Thank you for registering with Nabavki Platform. To complete your registration and activate your account, please verify your email address by clicking the button below.</p>
        <p style="margin-top: 20px;">This verification link will expire in 24 hours.</p>
        <p style="margin-top: 20px; font-size: 14px; color: #666666;">
            If you didn't create an account, you can safely ignore this email.
        </p>
        """

        html_content = self._get_email_template(
            title="Verify Your Email Address",
            content=content,
            button_text="Verify Email Address",
            button_link=verification_link
        )

        return await self._send_email(
            to_email=email,
            subject="Verify Your Email Address - Nabavki Platform",
            html_content=html_content
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
        reset_link = f"{self.frontend_url}/reset-password?token={token}"

        content = f"""
        <p>Hello <strong>{name}</strong>,</p>
        <p>We received a request to reset the password for your Nabavki Platform account.</p>
        <p style="margin-top: 20px;">Click the button below to reset your password. This link will expire in 1 hour.</p>
        <p style="margin-top: 30px; padding: 15px; background-color: #fff3cd; border-left: 4px solid #ffc107; color: #856404; font-size: 14px;">
            <strong>Security Notice:</strong> If you didn't request a password reset, please ignore this email or contact support if you have concerns about your account security.
        </p>
        """

        html_content = self._get_email_template(
            title="Reset Your Password",
            content=content,
            button_text="Reset Password",
            button_link=reset_link
        )

        return await self._send_email(
            to_email=email,
            subject="Password Reset Request - Nabavki Platform",
            html_content=html_content
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
        <p>Welcome to Nabavki Platform! Your email has been successfully verified and your account is now active.</p>
        <p style="margin-top: 20px;">You can now access all features of our platform:</p>
        <ul style="color: #333333; font-size: 16px; line-height: 1.8; margin-top: 15px;">
            <li>Browse procurement opportunities</li>
            <li>Submit tender proposals</li>
            <li>Track your applications</li>
            <li>Manage your profile and settings</li>
        </ul>
        <p style="margin-top: 25px;">Get started by exploring your dashboard:</p>
        """

        html_content = self._get_email_template(
            title="Welcome to Nabavki Platform",
            content=content,
            button_text="Go to Dashboard",
            button_link=dashboard_link
        )

        return await self._send_email(
            to_email=email,
            subject="Welcome to Nabavki Platform",
            html_content=html_content
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
        <p>This is to confirm that the password for your Nabavki Platform account has been successfully changed.</p>
        <p style="margin-top: 20px; padding: 15px; background-color: #d1ecf1; border-left: 4px solid #17a2b8; color: #0c5460; font-size: 14px;">
            <strong>Important:</strong> If you did not make this change, please contact our support team immediately to secure your account.
        </p>
        <p style="margin-top: 25px;">Account Security Tips:</p>
        <ul style="color: #333333; font-size: 16px; line-height: 1.8; margin-top: 15px;">
            <li>Use a strong, unique password</li>
            <li>Never share your password with anyone</li>
            <li>Enable two-factor authentication if available</li>
            <li>Regularly update your password</li>
        </ul>
        <p style="margin-top: 25px;">If you need assistance, please contact our support team:</p>
        """

        html_content = self._get_email_template(
            title="Password Changed Successfully",
            content=content,
            button_text="Contact Support",
            button_link=support_link
        )

        return await self._send_email(
            to_email=email,
            subject="Password Changed - Nabavki Platform",
            html_content=html_content
        )


# Global email service instance
email_service = EmailService()


# Convenience functions for easy import
async def send_verification_email(email: str, token: str, name: str) -> bool:
    """Send verification email to user."""
    return await email_service.send_verification_email(email, token, name)


async def send_password_reset_email(email: str, token: str, name: str) -> bool:
    """Send password reset email to user."""
    return await email_service.send_password_reset_email(email, token, name)


async def send_welcome_email(email: str, name: str) -> bool:
    """Send welcome email to user."""
    return await email_service.send_welcome_email(email, name)


async def send_password_changed_email(email: str, name: str) -> bool:
    """Send password changed confirmation email to user."""
    return await email_service.send_password_changed_email(email, name)

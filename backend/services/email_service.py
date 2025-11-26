"""
Email Service - DEPRECATED
This module now redirects to the Mailersend service (mailer.py).
Kept for backwards compatibility with existing imports.

All email functionality has been migrated from AWS SES/SMTP to Mailersend HTTP API.
"""

import logging

logger = logging.getLogger(__name__)

# Re-export everything from the new mailer service for backwards compatibility
from services.mailer import (
    mailer_service as email_service,
    MailerService as EmailService,
    send_verification_email,
    send_password_reset_email,
    send_welcome_email,
    send_password_changed_email,
    send_scraper_failure_alert,
    send_tender_notification,
    send_test_email,
)

# Log deprecation warning on import
logger.warning(
    "email_service is deprecated. Please import from services.mailer instead. "
    "This module will be removed in a future version."
)

__all__ = [
    'email_service',
    'EmailService',
    'send_verification_email',
    'send_password_reset_email',
    'send_welcome_email',
    'send_password_changed_email',
    'send_scraper_failure_alert',
    'send_tender_notification',
    'send_test_email',
]

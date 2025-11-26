#!/usr/bin/env python3
"""
Test Mailersend Email Delivery Script
Tests all email types to verify Mailersend configuration is working.

Usage:
    python scripts/test_mailersend.py [recipient_email]

If no recipient is provided, uses TEST_EMAIL env var or admin@nabavkidata.com
"""

import os
import sys
import asyncio
import httpx
from datetime import datetime
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    env_prod = Path(__file__).parent.parent / '.env.production'
    if env_prod.exists():
        load_dotenv(dotenv_path=env_prod)
except ImportError:
    print("Warning: python-dotenv not installed, using system environment variables only")

# Mailersend Configuration from environment
MAILERSEND_API_KEY = os.getenv('MAILERSEND_API_KEY', '')
MAILERSEND_FROM_EMAIL = os.getenv('MAILERSEND_FROM_EMAIL', 'noreply@nabavkidata.com')
MAILERSEND_FROM_NAME = os.getenv('MAILERSEND_FROM_NAME', 'NabavkiData')
MAILERSEND_API_URL = 'https://api.mailersend.com/v1/email'

# Test recipient
TEST_RECIPIENT = os.getenv('TEST_EMAIL', 'admin@nabavkidata.com')


async def send_test_email(subject: str, html: str, text: str, test_name: str) -> bool:
    """Send email via Mailersend API and report result."""
    print(f"\n{'='*60}")
    print(f"Testing: {test_name}")
    print(f"{'='*60}")
    print(f"From: {MAILERSEND_FROM_NAME} <{MAILERSEND_FROM_EMAIL}>")
    print(f"To: {TEST_RECIPIENT}")
    print(f"Subject: {subject}")

    payload = {
        "from": {
            "email": MAILERSEND_FROM_EMAIL,
            "name": MAILERSEND_FROM_NAME
        },
        "to": [{"email": TEST_RECIPIENT}],
        "subject": subject,
        "html": html,
        "text": text
    }

    headers = {
        "Authorization": f"Bearer {MAILERSEND_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                MAILERSEND_API_URL,
                headers=headers,
                json=payload
            )

            if response.status_code in (200, 202):
                print(f"✅ {test_name}: SUCCESS (HTTP {response.status_code})")
                return True
            else:
                print(f"❌ {test_name}: FAILED (HTTP {response.status_code})")
                print(f"Response: {response.text}")
                return False

    except Exception as e:
        print(f"❌ {test_name}: FAILED")
        print(f"Error: {str(e)}")
        return False


async def test_welcome_email() -> bool:
    """Test welcome email."""
    subject = "[TEST] Welcome to NabavkiData"
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #2563eb;">Welcome to NabavkiData!</h2>
        <p>Thank you for joining our tender notification platform.</p>
        <p>This is a test email to verify Mailersend configuration.</p>
        <hr style="border: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="color: #6b7280; font-size: 14px;">
          Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
          Environment: Production<br>
          Service: Mailersend API
        </p>
      </body>
    </html>
    """
    text = f"""
    Welcome to NabavkiData!

    Thank you for joining our tender notification platform.
    This is a test email to verify Mailersend configuration.

    Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    Service: Mailersend API
    """
    return await send_test_email(subject, html, text, "Welcome Email")


async def test_password_reset_email() -> bool:
    """Test password reset email."""
    subject = "[TEST] Reset Your Password"
    reset_link = "https://nabavkidata.com/reset-password?token=test_token_123"
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #2563eb;">Password Reset Request</h2>
        <p>You requested to reset your password for NabavkiData.</p>
        <div style="margin: 30px 0;">
          <a href="{reset_link}"
             style="background-color: #2563eb; color: white; padding: 12px 24px;
                    text-decoration: none; border-radius: 6px; display: inline-block;">
            Reset Password
          </a>
        </div>
        <p style="color: #ef4444; font-size: 14px;">
          This link expires in 1 hour.
        </p>
        <hr style="border: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="color: #6b7280; font-size: 14px;">
          Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
      </body>
    </html>
    """
    text = f"""
    Password Reset Request

    You requested to reset your password for NabavkiData.
    Click: {reset_link}
    This link expires in 1 hour.

    Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    return await send_test_email(subject, html, text, "Password Reset Email")


async def test_verification_email() -> bool:
    """Test email verification."""
    subject = "[TEST] Verify Your Email Address"
    verification_link = "https://nabavkidata.com/verify-email?token=verify_test_789"
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #2563eb;">Verify Your Email Address</h2>
        <p>Please verify your email to activate your NabavkiData account.</p>
        <div style="margin: 30px 0;">
          <a href="{verification_link}"
             style="background-color: #10b981; color: white; padding: 12px 24px;
                    text-decoration: none; border-radius: 6px; display: inline-block;">
            Verify Email
          </a>
        </div>
        <p style="color: #6b7280; font-size: 14px;">
          This link expires in 24 hours.
        </p>
        <hr style="border: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="color: #6b7280; font-size: 14px;">
          Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
      </body>
    </html>
    """
    text = f"""
    Verify Your Email Address

    Please verify your email to activate your NabavkiData account.
    Click: {verification_link}
    This link expires in 24 hours.

    Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    return await send_test_email(subject, html, text, "Verification Email")


async def test_tender_notification() -> bool:
    """Test tender notification email."""
    subject = "[TEST] New Tender Match: Construction Project"
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #2563eb;">New Tender Matches Your Criteria</h2>
        <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
          <h3 style="color: #1f2937; margin-top: 0;">Construction Project - School Building</h3>
          <p><strong>Contracting Authority:</strong> Ministry of Education</p>
          <p><strong>Estimated Value:</strong> €2,500,000</p>
          <p><strong>Deadline:</strong> 2025-12-15</p>
          <p><strong>Category:</strong> Construction</p>
        </div>
        <div style="margin: 30px 0;">
          <a href="https://nabavkidata.com/tenders/12345"
             style="background-color: #2563eb; color: white; padding: 12px 24px;
                    text-decoration: none; border-radius: 6px; display: inline-block;">
            View Tender Details
          </a>
        </div>
        <hr style="border: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="color: #6b7280; font-size: 14px;">
          Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
      </body>
    </html>
    """
    text = f"""
    New Tender Matches Your Criteria

    Construction Project - School Building
    Contracting Authority: Ministry of Education
    Estimated Value: €2,500,000
    Deadline: 2025-12-15
    Category: Construction

    View: https://nabavkidata.com/tenders/12345

    Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    return await send_test_email(subject, html, text, "Tender Notification")


async def main():
    """Run all email tests."""
    global TEST_RECIPIENT

    # Allow recipient from command line
    if len(sys.argv) > 1:
        TEST_RECIPIENT = sys.argv[1]

    print("\n" + "=" * 60)
    print("MAILERSEND EMAIL DELIVERY TEST")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API URL: {MAILERSEND_API_URL}")
    print(f"From: {MAILERSEND_FROM_NAME} <{MAILERSEND_FROM_EMAIL}>")
    print(f"Test Recipient: {TEST_RECIPIENT}")

    # Verify API key is set
    if not MAILERSEND_API_KEY:
        print("\n❌ ERROR: MAILERSEND_API_KEY not set!")
        print("Please set the MAILERSEND_API_KEY environment variable")
        sys.exit(1)

    api_key_preview = MAILERSEND_API_KEY[:20] + "..."
    print(f"API Key: {api_key_preview}")
    print("=" * 60)

    # Run tests
    results = []
    results.append(await test_welcome_email())
    results.append(await test_password_reset_email())
    results.append(await test_verification_email())
    results.append(await test_tender_notification())

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    total_tests = len(results)
    passed_tests = sum(results)
    failed_tests = total_tests - passed_tests

    print(f"Total Tests: {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {failed_tests}")

    if all(results):
        print("\n🎉 ALL TESTS PASSED - Mailersend is working correctly!")
        print(f"\nCheck your inbox at: {TEST_RECIPIENT}")
        print("You should have received 4 test emails.")
        sys.exit(0)
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("\nPlease check:")
        print("1. MAILERSEND_API_KEY is correct")
        print("2. Domain is verified in Mailersend")
        print("3. SPF/DKIM records are configured")
        print("4. Check Mailersend dashboard for errors")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

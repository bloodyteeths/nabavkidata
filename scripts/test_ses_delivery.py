#!/usr/bin/env python3
"""
Test SES Email Delivery Script
Tests all email types to verify SES configuration is working
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    print("Warning: python-dotenv not installed, using system environment variables only")

# SMTP Configuration from environment
SMTP_HOST = os.getenv('SMTP_HOST', 'email-smtp.eu-central-1.amazonaws.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_FROM = os.getenv('SMTP_FROM', 'no-reply@nabavkidata.com')
SMTP_FROM_NAME = os.getenv('SMTP_FROM_NAME', 'Nabavkidata')

# Test recipient (must be verified in sandbox mode)
TEST_RECIPIENT = os.getenv('TEST_EMAIL', 'admin@nabavkidata.com')

def create_email(subject, body_html, body_text=None):
    """Create a MIME multipart email message"""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
    msg['To'] = TEST_RECIPIENT

    # Add text version
    if body_text:
        part1 = MIMEText(body_text, 'plain')
        msg.attach(part1)

    # Add HTML version
    part2 = MIMEText(body_html, 'html')
    msg.attach(part2)

    return msg

def send_email(msg, test_name):
    """Send email via SMTP and report result"""
    try:
        print(f"\n{'='*60}")
        print(f"Testing: {test_name}")
        print(f"{'='*60}")
        print(f"From: {SMTP_FROM_NAME} <{SMTP_FROM}>")
        print(f"To: {TEST_RECIPIENT}")
        print(f"Subject: {msg['Subject']}")

        # Connect to SMTP server
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.set_debuglevel(0)  # Set to 1 for detailed SMTP logs
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"✅ {test_name}: SUCCESS")
        return True

    except Exception as e:
        print(f"❌ {test_name}: FAILED")
        print(f"Error: {str(e)}")
        return False

def test_welcome_email():
    """Test welcome email"""
    subject = "[TEST] Welcome to Nabavkidata"
    html = """
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #2563eb;">Welcome to Nabavkidata!</h2>
        <p>Thank you for joining our tender notification platform.</p>
        <p>This is a test email to verify SES configuration.</p>
        <hr style="border: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="color: #6b7280; font-size: 14px;">
          Test sent at: {timestamp}<br>
          Environment: Production<br>
          Service: AWS SES (eu-central-1)
        </p>
      </body>
    </html>
    """.format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    text = f"""
    Welcome to Nabavkidata!

    Thank you for joining our tender notification platform.
    This is a test email to verify SES configuration.

    Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    Environment: Production
    Service: AWS SES (eu-central-1)
    """

    msg = create_email(subject, html, text)
    return send_email(msg, "Welcome Email")

def test_password_reset_email():
    """Test password reset email"""
    subject = "[TEST] Reset Your Password"
    reset_token = "test_token_123456789"
    reset_link = f"https://nabavkidata.com/reset-password?token={reset_token}"

    html = """
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #2563eb;">Password Reset Request</h2>
        <p>You requested to reset your password for Nabavkidata.</p>
        <p>Click the button below to reset your password:</p>
        <div style="margin: 30px 0;">
          <a href="{reset_link}"
             style="background-color: #2563eb; color: white; padding: 12px 24px;
                    text-decoration: none; border-radius: 6px; display: inline-block;">
            Reset Password
          </a>
        </div>
        <p style="color: #6b7280; font-size: 14px;">
          Or copy this link: {reset_link}
        </p>
        <p style="color: #ef4444; font-size: 14px;">
          This link will expire in 1 hour. If you didn't request this, please ignore this email.
        </p>
        <hr style="border: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="color: #6b7280; font-size: 14px;">
          Test sent at: {timestamp}
        </p>
      </body>
    </html>
    """.format(reset_link=reset_link, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    text = f"""
    Password Reset Request

    You requested to reset your password for Nabavkidata.

    Click this link to reset your password:
    {reset_link}

    This link will expire in 1 hour. If you didn't request this, please ignore this email.

    Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """

    msg = create_email(subject, html, text)
    return send_email(msg, "Password Reset Email")

def test_verification_email():
    """Test email verification"""
    subject = "[TEST] Verify Your Email Address"
    verification_token = "verify_test_987654321"
    verification_link = f"https://nabavkidata.com/verify-email?token={verification_token}"

    html = """
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #2563eb;">Verify Your Email Address</h2>
        <p>Please verify your email address to activate your Nabavkidata account.</p>
        <div style="margin: 30px 0;">
          <a href="{verification_link}"
             style="background-color: #10b981; color: white; padding: 12px 24px;
                    text-decoration: none; border-radius: 6px; display: inline-block;">
            Verify Email
          </a>
        </div>
        <p style="color: #6b7280; font-size: 14px;">
          Or copy this link: {verification_link}
        </p>
        <p style="color: #6b7280; font-size: 14px;">
          This verification link will expire in 24 hours.
        </p>
        <hr style="border: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="color: #6b7280; font-size: 14px;">
          Test sent at: {timestamp}
        </p>
      </body>
    </html>
    """.format(verification_link=verification_link, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    text = f"""
    Verify Your Email Address

    Please verify your email address to activate your Nabavkidata account.

    Click this link to verify:
    {verification_link}

    This verification link will expire in 24 hours.

    Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """

    msg = create_email(subject, html, text)
    return send_email(msg, "Verification Email")

def test_tender_notification():
    """Test tender notification email"""
    subject = "[TEST] New Tender Match: Construction Project"

    html = """
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
          Test sent at: {timestamp}
        </p>
      </body>
    </html>
    """.format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    text = f"""
    New Tender Matches Your Criteria

    Construction Project - School Building

    Contracting Authority: Ministry of Education
    Estimated Value: €2,500,000
    Deadline: 2025-12-15
    Category: Construction

    View details: https://nabavkidata.com/tenders/12345

    Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """

    msg = create_email(subject, html, text)
    return send_email(msg, "Tender Notification")

def main():
    """Run all email tests"""
    print("\n" + "="*60)
    print("AWS SES EMAIL DELIVERY TEST")
    print("="*60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Region: eu-central-1")
    print(f"SMTP Host: {SMTP_HOST}:{SMTP_PORT}")
    print(f"From: {SMTP_FROM}")
    print(f"Test Recipient: {TEST_RECIPIENT}")

    # Verify credentials are set
    if not SMTP_USER or not SMTP_PASSWORD:
        print("\n❌ ERROR: SMTP credentials not set!")
        print("Please set SMTP_USER and SMTP_PASSWORD environment variables")
        sys.exit(1)

    print(f"SMTP User: {SMTP_USER[:10]}..." if SMTP_USER else "Not set")
    print("="*60)

    # Run tests
    results = []
    results.append(test_welcome_email())
    results.append(test_password_reset_email())
    results.append(test_verification_email())
    results.append(test_tender_notification())

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    total_tests = len(results)
    passed_tests = sum(results)
    failed_tests = total_tests - passed_tests

    print(f"Total Tests: {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {failed_tests}")

    if all(results):
        print("\n🎉 ALL TESTS PASSED - SES is working correctly!")
        print("\nCheck your inbox at:", TEST_RECIPIENT)
        print("You should have received 4 test emails.")
        sys.exit(0)
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("\nPlease check:")
        print("1. SMTP credentials are correct")
        print("2. Email addresses are verified (sandbox mode)")
        print("3. DKIM status is SUCCESS")
        print("4. Backend logs for detailed errors")
        sys.exit(1)

if __name__ == "__main__":
    main()

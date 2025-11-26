#!/usr/bin/env python3
"""
Management CLI for NabavkiData Backend
Usage: python manage.py <command> [args]

Commands:
    test_email <email>  - Send a test email to verify Mailersend configuration
    test_all_emails <email> - Send all email types for testing
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # Try production env
        env_prod = Path(__file__).parent.parent / '.env.production'
        if env_prod.exists():
            load_dotenv(env_prod)
except ImportError:
    pass


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_config():
    """Print current email configuration."""
    from services.mailer import (
        MAILERSEND_API_KEY,
        MAILERSEND_FROM_EMAIL,
        MAILERSEND_FROM_NAME,
        FRONTEND_URL
    )

    api_key_preview = MAILERSEND_API_KEY[:20] + "..." if MAILERSEND_API_KEY else "NOT SET"

    print(f"\nCurrent Configuration:")
    print(f"  API Key: {api_key_preview}")
    print(f"  From Email: {MAILERSEND_FROM_EMAIL}")
    print(f"  From Name: {MAILERSEND_FROM_NAME}")
    print(f"  Frontend URL: {FRONTEND_URL}")


async def cmd_test_email(email: str):
    """Send a single test email."""
    from services.mailer import mailer_service

    print_header("MAILERSEND EMAIL TEST")
    print_config()

    print(f"\nSending test email to: {email}")
    print("-" * 40)

    result = await mailer_service.send_test_email(email)

    if result:
        print("\n✅ SUCCESS: Test email sent!")
        print(f"   Check inbox at: {email}")
        return 0
    else:
        print("\n❌ FAILED: Could not send test email")
        print("\nTroubleshooting:")
        print("  1. Check MAILERSEND_API_KEY is set correctly")
        print("  2. Verify domain is configured in Mailersend")
        print("  3. Check Mailersend dashboard for errors")
        return 1


async def cmd_test_all_emails(email: str):
    """Send all email types for comprehensive testing."""
    from services.mailer import mailer_service

    print_header("MAILERSEND COMPREHENSIVE EMAIL TEST")
    print_config()

    print(f"\nSending all email types to: {email}")
    print("-" * 40)

    results = []

    # Test 1: Generic test email
    print("\n[1/5] Sending test email...")
    result = await mailer_service.send_test_email(email)
    results.append(("Test Email", result))
    print(f"      {'✅ Success' if result else '❌ Failed'}")

    # Test 2: Verification email
    print("\n[2/5] Sending verification email...")
    result = await mailer_service.send_verification_email(
        email, "test_token_123456", "Test User"
    )
    results.append(("Verification Email", result))
    print(f"      {'✅ Success' if result else '❌ Failed'}")

    # Test 3: Password reset email
    print("\n[3/5] Sending password reset email...")
    result = await mailer_service.send_password_reset_email(
        email, "reset_token_789012", "Test User"
    )
    results.append(("Password Reset Email", result))
    print(f"      {'✅ Success' if result else '❌ Failed'}")

    # Test 4: Welcome email
    print("\n[4/5] Sending welcome email...")
    result = await mailer_service.send_welcome_email(email, "Test User")
    results.append(("Welcome Email", result))
    print(f"      {'✅ Success' if result else '❌ Failed'}")

    # Test 5: Tender notification
    print("\n[5/5] Sending tender notification...")
    result = await mailer_service.send_tender_notification(
        email=email,
        name="Test User",
        tender_title="Test Tender - Construction Project",
        tender_id="12345",
        contracting_authority="Ministry of Education",
        estimated_value="€2,500,000",
        deadline="2025-12-31",
        category="Construction"
    )
    results.append(("Tender Notification", result))
    print(f"      {'✅ Success' if result else '❌ Failed'}")

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    failed = len(results) - passed

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {name}")

    print(f"\nTotal: {passed}/{len(results)} passed")

    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED!")
        print(f"   Check inbox at: {email}")
        print("   You should have received 5 test emails.")
        return 0
    else:
        print(f"\n⚠️  {failed} TEST(S) FAILED")
        print("\nCheck Mailersend dashboard for error details.")
        return 1


def main():
    """Main entry point for CLI."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "test_email":
        if len(sys.argv) < 3:
            print("Usage: python manage.py test_email <email>")
            print("Example: python manage.py test_email user@example.com")
            sys.exit(1)
        email = sys.argv[2]
        exit_code = asyncio.run(cmd_test_email(email))
        sys.exit(exit_code)

    elif command == "test_all_emails":
        if len(sys.argv) < 3:
            print("Usage: python manage.py test_all_emails <email>")
            print("Example: python manage.py test_all_emails user@example.com")
            sys.exit(1)
        email = sys.argv[2]
        exit_code = asyncio.run(cmd_test_all_emails(email))
        sys.exit(exit_code)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Test script for verification spider
Checks dependencies and spider configuration before running
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    """Check if all required dependencies are installed."""
    print("Checking dependencies...")
    print("-" * 60)

    deps_ok = True

    # Core dependencies
    dependencies = [
        ('scrapy', 'Scrapy'),
        ('playwright', 'Playwright'),
        ('asyncpg', 'asyncpg'),
    ]

    for module, name in dependencies:
        try:
            __import__(module)
            print(f"✓ {name} installed")
        except ImportError:
            print(f"✗ {name} NOT installed")
            deps_ok = False

    # Optional: Gemini (for web search)
    try:
        import google.generativeai as genai
        print(f"✓ google-generativeai installed (web search enabled)")
    except ImportError:
        print(f"⚠ google-generativeai NOT installed (web search disabled)")

    print("-" * 60)
    return deps_ok


def check_database_connection():
    """Check database connection and table existence."""
    print("\nChecking database connection...")
    print("-" * 60)

    import asyncio
    import asyncpg
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'nabavkidata'),
        'user': os.getenv('DB_USER', 'nabavkidata_admin'),
        'password': os.getenv('DB_PASSWORD', ''),
    }

    if not DB_CONFIG['password']:
        print("✗ DB_PASSWORD not set in environment")
        print("-" * 60)
        return False

    async def test_connection():
        try:
            conn = await asyncpg.connect(**DB_CONFIG, timeout=10)
            print(f"✓ Connected to {DB_CONFIG['host']}")

            # Check tender_verifications table
            table_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tender_verifications')"
            )

            if table_exists:
                count = await conn.fetchval("SELECT COUNT(*) FROM tender_verifications")
                print(f"✓ tender_verifications table exists ({count} rows)")
            else:
                print("✗ tender_verifications table NOT found")
                print("  Run migration: db/migrations/020_tender_verifications.sql")

            # Check corruption_flags table
            flags_count = await conn.fetchval(
                "SELECT COUNT(*) FROM corruption_flags WHERE anomaly_score >= 0.8"
            )
            print(f"✓ Found {flags_count} high-risk tenders (score >= 0.8)")

            # Check web_verified column
            web_verified_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'corruption_flags' AND column_name = 'web_verified'
                )
            """)

            if web_verified_exists:
                print(f"✓ corruption_flags.web_verified column exists")
            else:
                print("⚠ corruption_flags.web_verified column NOT found")

            await conn.close()
            print("-" * 60)
            return True

        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            print("-" * 60)
            return False

    try:
        return asyncio.run(test_connection())
    except Exception as e:
        print(f"✗ Error testing connection: {e}")
        print("-" * 60)
        return False


def check_spider_configuration():
    """Check if spider is properly configured."""
    print("\nChecking spider configuration...")
    print("-" * 60)

    spider_path = os.path.join(
        os.path.dirname(__file__),
        'scraper', 'spiders', 'verification_spider.py'
    )

    if not os.path.exists(spider_path):
        print(f"✗ Spider not found at: {spider_path}")
        print("-" * 60)
        return False

    print(f"✓ Spider found at: {spider_path}")

    # Check spider can be imported
    try:
        from scraper.spiders.verification_spider import VerificationSpider
        print(f"✓ VerificationSpider imported successfully")
        print(f"  Spider name: {VerificationSpider.name}")
        print(f"  Allowed domains: {VerificationSpider.allowed_domains}")
    except Exception as e:
        print(f"✗ Failed to import spider: {e}")
        print("-" * 60)
        return False

    print("-" * 60)
    return True


def check_environment():
    """Check environment variables."""
    print("\nChecking environment variables...")
    print("-" * 60)

    from dotenv import load_dotenv
    load_dotenv()

    env_vars = {
        'DB_HOST': os.getenv('DB_HOST'),
        'DB_NAME': os.getenv('DB_NAME'),
        'DB_USER': os.getenv('DB_USER'),
        'DB_PASSWORD': os.getenv('DB_PASSWORD'),
        'GEMINI_API_KEY': os.getenv('GEMINI_API_KEY'),
    }

    all_ok = True

    for var, value in env_vars.items():
        if value:
            if 'PASSWORD' in var or 'KEY' in var:
                print(f"✓ {var} is set (hidden)")
            else:
                print(f"✓ {var} = {value}")
        else:
            if var == 'GEMINI_API_KEY':
                print(f"⚠ {var} not set (web search will be disabled)")
            else:
                print(f"✗ {var} not set")
                all_ok = False

    print("-" * 60)
    return all_ok


def get_sample_tenders():
    """Get sample high-risk tenders for testing."""
    print("\nFetching sample high-risk tenders...")
    print("-" * 60)

    import asyncio
    import asyncpg
    from dotenv import load_dotenv

    load_dotenv()

    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'nabavkidata'),
        'user': os.getenv('DB_USER', 'nabavkidata_admin'),
        'password': os.getenv('DB_PASSWORD', ''),
    }

    async def fetch_samples():
        try:
            conn = await asyncpg.connect(**DB_CONFIG, timeout=10)

            rows = await conn.fetch("""
                SELECT
                    t.tender_id,
                    t.title,
                    cf.anomaly_score,
                    cf.flag_type
                FROM tenders t
                JOIN corruption_flags cf ON t.tender_id = cf.tender_id
                WHERE cf.anomaly_score >= 0.8
                  AND NOT EXISTS (
                      SELECT 1 FROM tender_verifications tv
                      WHERE tv.tender_id = t.tender_id
                  )
                ORDER BY cf.anomaly_score DESC
                LIMIT 5
            """)

            if rows:
                print(f"Found {len(rows)} high-risk tenders to verify:\n")
                for i, row in enumerate(rows, 1):
                    print(f"{i}. {row['tender_id']}")
                    print(f"   Score: {row['anomaly_score']:.2f} | Flag: {row['flag_type']}")
                    print(f"   Title: {row['title'][:60]}...")
                    print()

                tender_ids = ','.join(row['tender_id'] for row in rows)
                print("Test command:")
                print(f"scrapy crawl verify -a tender_ids={tender_ids[:3]} -a web_search=false")
            else:
                print("No high-risk tenders found needing verification")

            await conn.close()
            print("-" * 60)
            return True

        except Exception as e:
            print(f"✗ Error fetching samples: {e}")
            print("-" * 60)
            return False

    try:
        return asyncio.run(fetch_samples())
    except Exception as e:
        print(f"✗ Error: {e}")
        print("-" * 60)
        return False


def main():
    """Run all checks."""
    print("=" * 60)
    print("VERIFICATION SPIDER TEST")
    print("=" * 60)

    results = {
        'Dependencies': check_dependencies(),
        'Environment Variables': check_environment(),
        'Spider Configuration': check_spider_configuration(),
        'Database Connection': check_database_connection(),
    }

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{check:.<40} {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✓ All checks passed! Spider is ready to run.\n")
        get_sample_tenders()
        print("\nRecommended test commands:")
        print("\n1. Test without web search (fast):")
        print("   scrapy crawl verify -a from_db=true -a min_score=0.9 -a limit=3 -a web_search=false")
        print("\n2. Test with web search (slower, requires GEMINI_API_KEY):")
        print("   scrapy crawl verify -a from_db=true -a min_score=0.9 -a limit=3 -a web_search=true")
        print("\n3. Full production run:")
        print("   scrapy crawl verify -a from_db=true -a min_score=0.8 -a limit=20 -a web_search=true")
        print()
        return 0
    else:
        print("\n✗ Some checks failed. Please fix the issues above.\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())

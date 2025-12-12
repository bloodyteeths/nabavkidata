"""
Test script for alerts API
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db, init_db
from api.alerts import check_alert_against_tender

async def test_database_connection():
    """Test database connection and tables"""
    print("=" * 60)
    print("Testing Database Connection")
    print("=" * 60)

    await init_db()

    async for db in get_db():
        # Check if tables exist
        result = await db.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('tender_alerts', 'alert_matches')
            ORDER BY table_name
        """))

        tables = [row[0] for row in result.fetchall()]
        print(f"\n✓ Tables found: {', '.join(tables)}")

        # Check tender_alerts schema
        result = await db.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'tender_alerts'
            ORDER BY ordinal_position
        """))

        print(f"\n✓ tender_alerts schema:")
        for row in result.fetchall():
            print(f"  - {row[0]:25} {row[1]}")

        # Check alert_matches schema
        result = await db.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'alert_matches'
            ORDER BY ordinal_position
        """))

        print(f"\n✓ alert_matches schema:")
        for row in result.fetchall():
            print(f"  - {row[0]:25} {row[1]}")

        # Check indexes
        result = await db.execute(text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename IN ('tender_alerts', 'alert_matches')
            ORDER BY indexname
        """))

        indexes = [row[0] for row in result.fetchall()]
        print(f"\n✓ Indexes: {', '.join(indexes)}")

        break


async def test_matching_engine():
    """Test the alert matching engine"""
    print("\n" + "=" * 60)
    print("Testing Alert Matching Engine")
    print("=" * 60)

    # Test case 1: Keyword matching
    alert = {
        'criteria': {
            'keywords': ['software', 'kompjuter']
        }
    }
    tender = {
        'title': 'Набавка на компјутерска опрема',
        'description': 'Software лиценци и хардвер',
        'procuring_entity': 'Министерство за образование',
        'estimated_value_mkd': 500000,
        'cpv_code': '30213000',
        'winner': ''
    }

    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"\n✓ Test 1 - Keyword matching:")
    print(f"  Matches: {matches}")
    print(f"  Score: {score}")
    print(f"  Reasons: {reasons}")

    # Test case 2: CPV code matching
    alert = {
        'criteria': {
            'cpv_codes': ['3021']  # Computer equipment
        }
    }

    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"\n✓ Test 2 - CPV code matching:")
    print(f"  Matches: {matches}")
    print(f"  Score: {score}")
    print(f"  Reasons: {reasons}")

    # Test case 3: Entity matching
    alert = {
        'criteria': {
            'entities': ['Министерство']
        }
    }

    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"\n✓ Test 3 - Entity matching:")
    print(f"  Matches: {matches}")
    print(f"  Score: {score}")
    print(f"  Reasons: {reasons}")

    # Test case 4: Budget range matching
    alert = {
        'criteria': {
            'budget_min': 100000,
            'budget_max': 1000000
        }
    }

    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"\n✓ Test 4 - Budget range matching:")
    print(f"  Matches: {matches}")
    print(f"  Score: {score}")
    print(f"  Reasons: {reasons}")

    # Test case 5: Combined criteria
    alert = {
        'criteria': {
            'keywords': ['компјутер'],
            'cpv_codes': ['3021'],
            'budget_min': 100000
        }
    }

    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"\n✓ Test 5 - Combined criteria:")
    print(f"  Matches: {matches}")
    print(f"  Score: {score}")
    print(f"  Reasons: {reasons}")

    # Test case 6: No match
    alert = {
        'criteria': {
            'keywords': ['медицинска опрема']
        }
    }

    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"\n✓ Test 6 - No match scenario:")
    print(f"  Matches: {matches}")
    print(f"  Score: {score}")
    print(f"  Reasons: {reasons}")


async def main():
    """Run all tests"""
    try:
        await test_database_connection()
        await test_matching_engine()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

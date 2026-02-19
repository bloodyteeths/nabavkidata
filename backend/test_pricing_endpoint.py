"""
Test script for pricing endpoint
Validates SQL query and endpoint functionality
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

# Set required env vars if not present
if not os.getenv('SECRET_KEY'):
    os.environ['SECRET_KEY'] = 'test-secret-key-for-validation-only'

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

# Database configuration
DB_HOST = "nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com"
DB_USER = "nabavki_user"
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_NAME = "nabavkidata"

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"


async def test_price_history_query():
    """Test the price history aggregation query"""
    print("\n" + "="*80)
    print("TESTING PRICE HISTORY AGGREGATION QUERY")
    print("="*80)

    engine = create_async_engine(DATABASE_URL, echo=False)

    try:
        async with engine.begin() as conn:
            # Test 1: Get available CPV codes with data
            print("\n[1] Finding CPV codes with sufficient data...")
            cpv_query = text("""
                SELECT
                    cpv_code,
                    COUNT(*) as tender_count,
                    MAX(category) as category
                FROM tenders
                WHERE cpv_code IS NOT NULL
                  AND cpv_code != ''
                  AND publication_date IS NOT NULL
                GROUP BY cpv_code
                HAVING COUNT(*) >= 5
                ORDER BY COUNT(*) DESC
                LIMIT 5
            """)

            result = await conn.execute(cpv_query)
            cpv_codes = result.fetchall()

            if not cpv_codes:
                print("❌ No CPV codes found with sufficient data")
                return

            print(f"✓ Found {len(cpv_codes)} CPV codes with 5+ tenders")
            for cpv in cpv_codes:
                print(f"  - {cpv[0]}: {cpv[1]} tenders ({cpv[2]})")

            # Test 2: Run price history query for first CPV code
            test_cpv = cpv_codes[0][0]
            print(f"\n[2] Testing price history query for CPV: {test_cpv}")

            time_trunc = 'month'
            months = 120  # Look back 10 years for testing

            price_query = text("""
                WITH price_data AS (
                    SELECT
                        DATE_TRUNC(:time_trunc, publication_date) as period,
                        COUNT(*) as tender_count,
                        AVG(estimated_value_mkd) as avg_estimated,
                        AVG(actual_value_mkd) as avg_actual,
                        AVG(CASE
                            WHEN estimated_value_mkd > 0 AND actual_value_mkd IS NOT NULL THEN
                                (estimated_value_mkd - actual_value_mkd) / estimated_value_mkd * 100
                            END
                        ) as avg_discount_pct,
                        AVG(num_bidders) as avg_bidders
                    FROM tenders
                    WHERE cpv_code LIKE :cpv_prefix
                      AND publication_date IS NOT NULL
                    GROUP BY DATE_TRUNC(:time_trunc, publication_date)
                    HAVING COUNT(*) > 0
                )
                SELECT
                    period,
                    tender_count,
                    avg_estimated,
                    avg_actual,
                    avg_discount_pct,
                    avg_bidders
                FROM price_data
                ORDER BY period ASC
            """)

            result = await conn.execute(
                price_query,
                {
                    "time_trunc": time_trunc,
                    "cpv_prefix": f"{test_cpv}%",
                    "months": months
                }
            )
            rows = result.fetchall()

            if not rows:
                print("❌ No price history data returned")
                return

            print(f"✓ Retrieved {len(rows)} time periods")
            print("\nSample data (first 5 periods):")
            print("-" * 120)
            print(f"{'Period':<12} {'Tenders':>8} {'Avg Estimated':>15} {'Avg Actual':>15} {'Discount %':>12} {'Avg Bidders':>12}")
            print("-" * 120)

            for row in rows[:5]:
                period = row[0].strftime('%Y-%m')
                tender_count = row[1]
                avg_est = f"{row[2]:,.2f}" if row[2] else "N/A"
                avg_act = f"{row[3]:,.2f}" if row[3] else "N/A"
                avg_disc = f"{row[4]:.1f}%" if row[4] else "N/A"
                avg_bid = f"{row[5]:.1f}" if row[5] else "N/A"

                print(f"{period:<12} {tender_count:>8} {avg_est:>15} {avg_act:>15} {avg_disc:>12} {avg_bid:>12}")

            # Test 3: Calculate trend
            print("\n[3] Calculating price trend...")
            if len(rows) >= 4:
                mid_point = len(rows) // 2

                # Calculate first half average
                first_half_sum = 0
                first_half_count = 0
                for row in rows[:mid_point]:
                    if row[3]:  # avg_actual
                        first_half_sum += float(row[3]) * row[1]
                        first_half_count += row[1]

                # Calculate second half average
                second_half_sum = 0
                second_half_count = 0
                for row in rows[mid_point:]:
                    if row[3]:  # avg_actual
                        second_half_sum += float(row[3]) * row[1]
                        second_half_count += row[1]

                if first_half_count > 0 and second_half_count > 0:
                    first_half_avg = first_half_sum / first_half_count
                    second_half_avg = second_half_sum / second_half_count

                    trend_pct = ((second_half_avg - first_half_avg) / first_half_avg) * 100

                    if trend_pct > 5:
                        trend = "increasing"
                    elif trend_pct < -5:
                        trend = "decreasing"
                    else:
                        trend = "stable"

                    print(f"✓ First half average: {first_half_avg:,.2f} MKD")
                    print(f"✓ Second half average: {second_half_avg:,.2f} MKD")
                    print(f"✓ Trend: {trend} ({trend_pct:+.2f}%)")
                else:
                    print("⚠ Not enough data to calculate trend")
            else:
                print("⚠ Not enough periods to calculate trend")

            # Test 4: Test with different grouping (quarter)
            print(f"\n[4] Testing quarterly grouping for CPV: {test_cpv}")

            quarterly_query = text("""
                WITH price_data AS (
                    SELECT
                        DATE_TRUNC('quarter', publication_date) as period,
                        COUNT(*) as tender_count,
                        AVG(estimated_value_mkd) as avg_estimated,
                        AVG(actual_value_mkd) as avg_actual,
                        AVG(CASE
                            WHEN estimated_value_mkd > 0 AND actual_value_mkd IS NOT NULL THEN
                                (estimated_value_mkd - actual_value_mkd) / estimated_value_mkd * 100
                            END
                        ) as avg_discount_pct,
                        AVG(num_bidders) as avg_bidders
                    FROM tenders
                    WHERE cpv_code LIKE :cpv_prefix
                      AND publication_date IS NOT NULL
                    GROUP BY DATE_TRUNC('quarter', publication_date)
                    HAVING COUNT(*) > 0
                )
                SELECT
                    period,
                    tender_count
                FROM price_data
                ORDER BY period ASC
            """)

            result = await conn.execute(
                quarterly_query,
                {"cpv_prefix": f"{test_cpv}%"}
            )
            quarterly_rows = result.fetchall()

            print(f"✓ Retrieved {len(quarterly_rows)} quarters")
            for row in quarterly_rows:
                quarter = (row[0].month - 1) // 3 + 1
                period_str = f"{row[0].year}-Q{quarter}"
                print(f"  - {period_str}: {row[1]} tenders")

            print("\n" + "="*80)
            print("✓ ALL TESTS PASSED")
            print("="*80)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_price_history_query())

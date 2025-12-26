"""
Test script for Dozorro-style indicators

Usage:
    python test_indicators.py
"""

import asyncio
import asyncpg
from dozorro_indicators import IndicatorRegistry

# Database configuration
DB_URL = "postgresql://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com/nabavkidata"


async def test_indicators():
    """Test indicator system on a sample tender."""

    # Connect to database
    pool = await asyncpg.create_pool(
        DB_URL,
        min_size=1,
        max_size=3,
        command_timeout=120
    )

    try:
        # Create registry
        registry = IndicatorRegistry(pool)

        # Get indicator counts
        counts = registry.get_indicator_count()
        print("\n" + "="*60)
        print("DOZORRO-STYLE INDICATOR SYSTEM")
        print("="*60)
        print(f"\nTotal Indicators: {sum(counts.values())}")
        for category, count in counts.items():
            print(f"  {category}: {count} indicators")

        # Test on a sample tender
        sample_query = """
            SELECT tender_id, title, num_bidders, estimated_value_mkd
            FROM tenders
            WHERE num_bidders = 1
              AND status = 'awarded'
              AND estimated_value_mkd > 1000000
            LIMIT 1
        """

        row = await pool.fetchrow(sample_query)

        if row:
            tender_id = row['tender_id']
            print(f"\n" + "="*60)
            print(f"Testing on tender: {tender_id}")
            print(f"Title: {row['title'][:60]}...")
            print(f"Bidders: {row['num_bidders']}")
            print(f"Value: {row['estimated_value_mkd']:,.0f} МКД")
            print("="*60)

            # Run all indicators
            results = await registry.run_all(tender_id)

            print(f"\nTriggered Indicators: {len(results)}")
            print("-"*60)

            # Sort by score
            results.sort(key=lambda x: x.score, reverse=True)

            for result in results[:10]:  # Show top 10
                print(f"\n{result.indicator_name}")
                print(f"  Category: {result.category}")
                print(f"  Score: {result.score:.1f}/100 (threshold: {result.threshold})")
                print(f"  Weight: {result.weight}")
                print(f"  Description: {result.description}")
                print(f"  Confidence: {result.confidence:.0%}")

            # Test category-specific
            print(f"\n" + "="*60)
            print("COMPETITION INDICATORS")
            print("="*60)

            competition_results = await registry.run_category(tender_id, "Competition")
            for result in competition_results[:3]:
                print(f"\n{result.indicator_name}: {result.score:.1f}")
                print(f"  {result.description}")

        else:
            print("\nNo sample tender found. Run scraper first.")

    finally:
        await pool.close()


async def test_single_indicator():
    """Test a single indicator in detail."""
    from dozorro_indicators import SingleBidderIndicator

    pool = await asyncpg.create_pool(DB_URL)

    try:
        indicator = SingleBidderIndicator(pool)

        # Get a single-bidder tender
        query = """
            SELECT tender_id
            FROM tenders
            WHERE num_bidders = 1
              AND status = 'awarded'
            LIMIT 1
        """

        row = await pool.fetchrow(query)

        if row:
            result = await indicator.calculate(row['tender_id'])

            print("\n" + "="*60)
            print("SINGLE INDICATOR TEST: SingleBidderIndicator")
            print("="*60)
            print(f"\nTender: {row['tender_id']}")
            print(f"Score: {result.score}/100")
            print(f"Triggered: {result.triggered}")
            print(f"Description: {result.description}")
            print(f"\nEvidence:")
            for key, value in result.evidence.items():
                print(f"  {key}: {value}")

    finally:
        await pool.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("TESTING DOZORRO-STYLE INDICATORS")
    print("="*60)

    # Run tests
    asyncio.run(test_indicators())

    print("\n" + "="*60)
    print("Testing single indicator...")
    asyncio.run(test_single_indicator())

    print("\n" + "="*60)
    print("Tests complete!")
    print("="*60 + "\n")

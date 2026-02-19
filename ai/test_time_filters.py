#!/usr/bin/env python3
"""
Test script for time-based query filtering in RAG system
"""

import sys
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Import the RAG query module
from rag_query import RAGQueryPipeline

def test_time_filter_extraction():
    """Test that time filters are correctly extracted from questions"""

    pipeline = RAGQueryPipeline(
        database_url="postgresql://test",
        gemini_api_key="test"
    )

    test_cases = [
        # Open/Active tenders
        ("What tenders are open right now?", "open"),
        ("Show me active tenders", "open"),
        ("Кои тендери се отворени?", "open"),

        # Closing soon
        ("What closes this week?", "closing_soon"),
        ("Тендери што заклучуваат наскоро", "closing_soon"),

        # Recent
        ("Last month's tenders", "recent"),
        ("Show me recent tenders", "recent"),
        ("Последни тендери", "recent"),

        # Year-based
        ("Show me 2024 tenders", "year"),
        ("What tenders were published last year?", "year"),
        ("Тендери од оваа година", "year"),

        # Historical
        ("Historical tenders", "historical"),
        ("Историски тендери", "historical"),

        # Closed
        ("Show me closed tenders", "closed"),
        ("Затворени тендери", "closed"),

        # Upcoming
        ("When is the next tender for X?", "upcoming"),
        ("Следен тендер", "upcoming"),

        # No time filter
        ("What are the prices for surgical supplies?", None),
    ]

    print("Testing time filter extraction...")
    print("=" * 60)

    for question, expected_filter_type in test_cases:
        result = pipeline._extract_time_filter(question)
        actual = result['filter_type']
        status = "✓" if actual == expected_filter_type else "✗"

        print(f"{status} Question: {question}")
        print(f"  Expected: {expected_filter_type}, Got: {actual}")

        if result['filter_type']:
            if result.get('date_from'):
                print(f"  Date from: {result['date_from']}")
            if result.get('date_to'):
                print(f"  Date to: {result['date_to']}")
            if result.get('status_filter'):
                print(f"  Status: {result['status_filter']}")
        print()

    print("=" * 60)

def test_where_clause_generation():
    """Test SQL WHERE clause generation"""

    pipeline = RAGQueryPipeline(
        database_url="postgresql://test",
        gemini_api_key="test"
    )

    mk_tz = ZoneInfo("Europe/Skopje")
    now = datetime.now(mk_tz)

    test_cases = [
        # Open tenders
        {
            'filter_type': 'open',
            'status_filter': 'active',
            'date_from': now,
            'date_to': None,
            'year': None
        },
        # Closing soon
        {
            'filter_type': 'closing_soon',
            'status_filter': 'active',
            'date_from': now,
            'date_to': now + timedelta(days=7),
            'year': None
        },
        # 2024
        {
            'filter_type': 'year',
            'status_filter': None,
            'date_from': datetime(2024, 1, 1, tzinfo=mk_tz),
            'date_to': datetime(2024, 12, 31, 23, 59, 59, tzinfo=mk_tz),
            'year': 2024
        },
    ]

    print("\nTesting WHERE clause generation...")
    print("=" * 60)

    for i, time_filter in enumerate(test_cases, 1):
        where_clause = pipeline._build_time_where_clause(time_filter, 't')
        print(f"Test case {i}: {time_filter['filter_type']}")
        print(f"  WHERE: {where_clause}")
        print()

    print("=" * 60)

if __name__ == "__main__":
    print("TIME-BASED QUERY FILTER TESTS")
    print("=" * 60)
    print()

    try:
        test_time_filter_extraction()
        test_where_clause_generation()
        print("\n✓ All tests completed successfully!")
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

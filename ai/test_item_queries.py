"""
Test Item-Level RAG Queries

This script demonstrates the enhanced RAG system's ability to handle
item-level queries like "What are past prices for surgical drapes?"

Example queries and expected behaviors:
1. "What are past prices for surgical drapes?"
   → Returns price history, top suppliers, specifications

2. "Who wins medical supply tenders?"
   → Returns top winning suppliers for medical items

3. "What specifications are required for surgical gloves?"
   → Returns technical specs from product_items

4. "Last year around this time, what surgical drape tenders were there?"
   → Returns historical data filtered by date and product

Usage:
    python test_item_queries.py
"""

import asyncio
import os
from rag_query import RAGQueryPipeline, ask_question
from dotenv import load_dotenv
load_dotenv()



# Example queries to test
EXAMPLE_QUERIES = [
    # Item price queries
    {
        "query": "What are past prices for surgical drapes?",
        "description": "Item-level price history query",
        "expected": [
            "Price statistics by year (avg, min, max)",
            "Top suppliers/winners",
            "Specifications if available",
            "Source tender IDs"
        ]
    },
    {
        "query": "Колку чинат хируршки ракавици?",
        "description": "Macedonian item price query",
        "expected": [
            "Unit prices in MKD",
            "Price ranges",
            "Suppliers"
        ]
    },

    # Supplier/winner queries
    {
        "query": "Who wins medical supply tenders?",
        "description": "Top suppliers for medical items",
        "expected": [
            "List of winning companies",
            "Number of wins per company",
            "Average bid amounts"
        ]
    },
    {
        "query": "Кој добива тендери за медицински материјал?",
        "description": "Macedonian supplier query",
        "expected": [
            "Supplier names",
            "Win statistics"
        ]
    },

    # Specification queries
    {
        "query": "What specifications are required for surgical gloves?",
        "description": "Technical specifications query",
        "expected": [
            "Material specifications",
            "Size requirements",
            "Quality standards",
            "Certifications"
        ]
    },

    # Historical/temporal queries
    {
        "query": "Last year around this time, what surgical drape tenders were there?",
        "description": "Historical item query with date filtering",
        "expected": [
            "Tenders from same period last year",
            "Prices from that period",
            "Winning bidders"
        ]
    },

    # Office supplies
    {
        "query": "How much do printer toner cartridges cost?",
        "description": "Office supplies price query",
        "expected": [
            "Toner cartridge prices",
            "Different models/brands",
            "Suppliers"
        ]
    },
    {
        "query": "Претходни цени за канцелариски материјал",
        "description": "Historical prices for office supplies",
        "expected": [
            "Price history",
            "Product categories",
            "Suppliers"
        ]
    },

    # Comparison queries
    {
        "query": "Compare prices for surgical masks from different suppliers",
        "description": "Multi-supplier price comparison",
        "expected": [
            "Price per supplier",
            "Quality/specifications",
            "Contract values"
        ]
    },

    # General product search
    {
        "query": "Show me all medical equipment tenders with per-item prices",
        "description": "Broad product category search",
        "expected": [
            "List of medical equipment items",
            "Individual unit prices",
            "Quantities and units"
        ]
    }
]


async def test_single_query(query_info: dict):
    """Test a single item-level query"""
    print("\n" + "="*80)
    print(f"QUERY: {query_info['query']}")
    print(f"DESCRIPTION: {query_info['description']}")
    print(f"EXPECTED RESULTS:")
    for exp in query_info['expected']:
        print(f"  - {exp}")
    print("-"*80)

    try:
        # Create RAG pipeline
        pipeline = RAGQueryPipeline(
            top_k=5,
            max_context_tokens=5000,
            enable_personalization=False
        )

        # Generate answer
        answer = await pipeline.generate_answer(query_info['query'])

        print("\nANSWER:")
        print(answer.answer)

        print(f"\nCONFIDENCE: {answer.confidence}")
        print(f"SOURCES: {len(answer.sources)} documents")

        if answer.sources:
            print("\nSOURCE DETAILS:")
            for i, source in enumerate(answer.sources[:5], 1):
                print(f"  {i}. Tender: {source.tender_id}, Similarity: {source.similarity:.2%}")
                metadata = source.chunk_metadata
                if 'item_name' in metadata:
                    print(f"     Item: {metadata['item_name']}")

        print("\n" + "="*80)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        print("="*80)


async def test_all_queries():
    """Test all example queries"""
    print("\n" + "#"*80)
    print("# ITEM-LEVEL RAG QUERY TESTING")
    print("# Enhanced RAG system with product_items and epazar_items support")
    print("#"*80)

    for i, query_info in enumerate(EXAMPLE_QUERIES, 1):
        print(f"\n\nTEST {i}/{len(EXAMPLE_QUERIES)}")
        await test_single_query(query_info)

        # Brief pause between queries to avoid rate limits
        await asyncio.sleep(1)

    print("\n" + "#"*80)
    print("# TESTING COMPLETE")
    print("#"*80)


async def test_price_history_aggregation():
    """Test price history aggregation for a specific item"""
    print("\n" + "="*80)
    print("SPECIALIZED TEST: Price History Aggregation")
    print("="*80)

    query = "Show me price trends for surgical drapes over the last 3 years"

    pipeline = RAGQueryPipeline(enable_personalization=False)
    answer = await pipeline.generate_answer(query)

    print(f"\nQUERY: {query}")
    print("\nRESPONSE:")
    print(answer.answer)
    print("\n" + "="*80)


async def test_supplier_analysis():
    """Test supplier/winner analysis for specific items"""
    print("\n" + "="*80)
    print("SPECIALIZED TEST: Supplier Analysis for Medical Items")
    print("="*80)

    query = "Which companies supply surgical equipment and what are their average prices?"

    pipeline = RAGQueryPipeline(enable_personalization=False)
    answer = await pipeline.generate_answer(query)

    print(f"\nQUERY: {query}")
    print("\nRESPONSE:")
    print(answer.answer)
    print("\n" + "="*80)


async def interactive_mode():
    """Interactive mode for testing custom queries"""
    print("\n" + "="*80)
    print("INTERACTIVE ITEM QUERY MODE")
    print("Enter your queries (or 'quit' to exit)")
    print("="*80 + "\n")

    pipeline = RAGQueryPipeline(enable_personalization=False)

    while True:
        try:
            query = input("\nYour query: ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                print("Exiting...")
                break

            if not query:
                continue

            print("\nProcessing...")
            answer = await pipeline.generate_answer(query)

            print("\n" + "-"*80)
            print("ANSWER:")
            print(answer.answer)
            print(f"\nConfidence: {answer.confidence}")
            print(f"Sources: {len(answer.sources)}")
            print("-"*80)

        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")


async def main():
    """Main test runner"""
    import sys

    if len(sys.argv) > 1:
        mode = sys.argv[1]

        if mode == 'interactive':
            await interactive_mode()
        elif mode == 'price':
            await test_price_history_aggregation()
        elif mode == 'supplier':
            await test_supplier_analysis()
        elif mode.startswith('query:'):
            # Single query mode: python test_item_queries.py "query:What are prices for masks?"
            query = mode[6:]
            await test_single_query({
                'query': query,
                'description': 'Custom query',
                'expected': []
            })
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python test_item_queries.py [interactive|price|supplier|all]")
    else:
        # Default: run all tests
        await test_all_queries()


if __name__ == "__main__":
    # Check environment variables
    if not os.getenv('DATABASE_URL'):
        print("ERROR: DATABASE_URL environment variable not set")
        exit(1)

    if not os.getenv('GEMINI_API_KEY'):
        print("ERROR: GEMINI_API_KEY environment variable not set")
        exit(1)

    asyncio.run(main())

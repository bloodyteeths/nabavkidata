"""
Test script for the new get_entity_profile tool

This demonstrates how the tool can be called to get entity profiles.
"""

import asyncio
from ai.rag_query import execute_tool
from db_pool import get_pool


async def test_entity_profile():
    """Test the get_entity_profile tool"""

    # Get database connection
    pool = await get_pool()

    async with pool.acquire() as conn:
        print("=" * 80)
        print("TEST 1: Search for a procuring entity (buyer)")
        print("=" * 80)

        result1 = await execute_tool(
            tool_name="get_entity_profile",
            tool_args={
                "entity_name": "Municipality of Skopje",
                "entity_type": "auto"  # Auto-detect
            },
            conn=conn
        )
        print(result1)
        print("\n\n")

        print("=" * 80)
        print("TEST 2: Search for a supplier (company)")
        print("=" * 80)

        result2 = await execute_tool(
            tool_name="get_entity_profile",
            tool_args={
                "entity_name": "Alkaloid",
                "entity_type": "supplier"  # Specifically search suppliers
            },
            conn=conn
        )
        print(result2)
        print("\n\n")

        print("=" * 80)
        print("TEST 3: Auto-detect entity type")
        print("=" * 80)

        result3 = await execute_tool(
            tool_name="get_entity_profile",
            tool_args={
                "entity_name": "Град Скопје"  # Macedonian name
                # entity_type defaults to "auto"
            },
            conn=conn
        )
        print(result3)
        print("\n\n")

        print("=" * 80)
        print("TEST 4: Entity not found")
        print("=" * 80)

        result4 = await execute_tool(
            tool_name="get_entity_profile",
            tool_args={
                "entity_name": "NonExistentCompany12345"
            },
            conn=conn
        )
        print(result4)


if __name__ == "__main__":
    asyncio.run(test_entity_profile())

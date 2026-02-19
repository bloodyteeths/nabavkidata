#!/usr/bin/env python3
"""
Example: Using Follow-Up Question Handling

This demonstrates how to use the enhanced RAG query pipeline with
follow-up question support in a real application.
"""

import asyncio
import os
from rag_query import LLMDrivenAgent
from dotenv import load_dotenv
load_dotenv()



async def example_conversation():
    """
    Simulate a realistic conversation with follow-up questions.
    """
    print("=" * 80)
    print("EXAMPLE: Conversational Procurement Research")
    print("=" * 80)
    print()

    # Initialize the agent
    agent = LLMDrivenAgent(
        database_url=os.getenv('DATABASE_URL'),
        gemini_api_key=os.getenv('GEMINI_API_KEY')
    )

    # Simulate a user session
    session_id = "example_user_123"

    # Conversation turns
    conversation = [
        {
            "user": "Кои се тендерите за интраокуларни леќи во 2024?",
            "description": "Initial question about IOL tenders in 2024"
        },
        {
            "user": "А за минатата година?",
            "description": "Follow-up: time shift to 2023"
        },
        {
            "user": "Покажи ми повеќе",
            "description": "Follow-up: request more results"
        },
        {
            "user": "Која е просечната цена?",
            "description": "Related question using same context"
        },
        {
            "user": "Спореди со 2022",
            "description": "Follow-up: comparison with different year"
        },
        {
            "user": "Кои се тендерите за хируршки ракавици?",
            "description": "New question (changes context)"
        },
        {
            "user": "Што со 2023?",
            "description": "Follow-up: time shift for new topic"
        },
    ]

    # Track conversation history
    history = []

    print("Starting conversation...")
    print("-" * 80)
    print()

    for i, turn in enumerate(conversation, 1):
        print(f"Turn {i}: {turn['description']}")
        print(f"User: {turn['user']}")
        print()

        try:
            # Get answer with follow-up handling
            answer = await agent.answer_question(
                question=turn['user'],
                conversation_history=history,
                session_id=session_id
            )

            print(f"AI: {answer[:200]}...")  # Show first 200 chars
            print()

            # Add to history
            history.append({
                "question": turn['user'],
                "answer": answer
            })

            # Show context status
            context = agent.query_context.get(session_id)
            if context:
                print(f"[Context: {len(context.get('tool_calls', []))} tool(s) stored]")
            else:
                print(f"[Context: None]")

            print("-" * 80)
            print()

        except Exception as e:
            print(f"Error: {e}")
            print("-" * 80)
            print()

    # Clean up
    agent.query_context.clear(session_id)
    print("Conversation ended. Context cleared.")
    print()


async def example_time_shifts():
    """
    Example demonstrating time-based follow-ups.
    """
    print("=" * 80)
    print("EXAMPLE: Time Shift Follow-Ups")
    print("=" * 80)
    print()

    agent = LLMDrivenAgent(
        database_url=os.getenv('DATABASE_URL'),
        gemini_api_key=os.getenv('GEMINI_API_KEY')
    )

    session_id = "time_shift_example"

    questions = [
        ("Кои се тендерите за медицинска опрема во 2024?", "Base question"),
        ("А за 2023?", "Previous year"),
        ("Што со 2022?", "Two years ago"),
        ("За оваа година", "Current year"),
    ]

    for question, label in questions:
        print(f"{label}: {question}")
        try:
            answer = await agent.answer_question(
                question=question,
                session_id=session_id
            )
            print(f"✓ Answer generated ({len(answer)} chars)")
        except Exception as e:
            print(f"✗ Error: {e}")
        print()

    agent.query_context.clear(session_id)
    print()


async def example_more_results():
    """
    Example demonstrating "show more" functionality.
    """
    print("=" * 80)
    print("EXAMPLE: Progressive Result Loading")
    print("=" * 80)
    print()

    agent = LLMDrivenAgent(
        database_url=os.getenv('DATABASE_URL'),
        gemini_api_key=os.getenv('GEMINI_API_KEY')
    )

    session_id = "more_results_example"

    questions = [
        ("Кои добавувачи продаваат медицинска опрема?", "Initial query (15 results)"),
        ("Покажи ми повеќе", "Request more (30 results)"),
        ("Уште", "Request even more (50 results - max)"),
    ]

    for question, label in questions:
        print(f"{label}: {question}")
        try:
            answer = await agent.answer_question(
                question=question,
                session_id=session_id
            )

            # Count results in answer (simple heuristic)
            result_count = answer.count('\n') // 3  # Rough estimate
            print(f"✓ Answer generated (~{result_count} results)")

            # Show limit from context
            context = agent.query_context.get(session_id)
            if context:
                for tool_call in context.get('tool_calls', []):
                    limit = tool_call.get('args', {}).get('limit', 15)
                    print(f"  Current limit: {limit}")
        except Exception as e:
            print(f"✗ Error: {e}")
        print()

    agent.query_context.clear(session_id)
    print()


async def main():
    """Run all examples"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "FOLLOW-UP USAGE EXAMPLES" + " " * 34 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")

    # Check environment variables
    if not os.getenv('DATABASE_URL'):
        print("⚠️  DATABASE_URL not set. Examples will fail.")
        print("   Set with: export DATABASE_URL='postgresql://...'")
        print()

    if not os.getenv('GEMINI_API_KEY'):
        print("⚠️  GEMINI_API_KEY not set. Examples will fail.")
        print("   Set with: export GEMINI_API_KEY='your-key'")
        print()

    if not (os.getenv('DATABASE_URL') and os.getenv('GEMINI_API_KEY')):
        print("Skipping examples due to missing configuration.")
        return

    # Run examples
    await example_time_shifts()
    await example_more_results()
    await example_conversation()

    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 25 + "EXAMPLES COMPLETED" + " " * 35 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())

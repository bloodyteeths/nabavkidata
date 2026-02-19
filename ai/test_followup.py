#!/usr/bin/env python3
"""
Test script for follow-up question handling in RAG Query Pipeline

This demonstrates the follow-up question detection and handling capabilities.
"""

import asyncio
import sys
from followup_handler import FollowUpDetector, QueryModifier, LastQueryContext


def test_followup_detector():
    """Test the FollowUpDetector class"""
    print("=" * 80)
    print("TESTING FOLLOW-UP DETECTOR")
    print("=" * 80)

    detector = FollowUpDetector()

    test_cases = [
        # Macedonian - time shifts
        ("А за минатата година?", True, "time_shift"),
        ("Што со 2023?", True, "time_shift"),
        ("За оваа година", True, "time_shift"),
        ("Кои се тендерите за интраокуларни леќи?", False, "none"),

        # Macedonian - more results
        ("Покажи ми повеќе", True, "more_results"),
        ("Уште примери", True, "more_results"),
        ("Повеќе", True, "more_results"),

        # Macedonian - detail requests
        ("Детали за ОХИС", True, "detail_request"),
        ("Кажи ми повеќе за овој тендер", True, "detail_request"),
        ("Што е со овој добавувач?", True, "detail_request"),

        # Macedonian - comparison
        ("Спореди со 2022", True, "comparison"),
        ("Исто така за болници", True, "comparison"),

        # English
        ("And for last year?", True, "time_shift"),
        ("Show more", True, "more_results"),
        ("What about 2024?", True, "time_shift"),
        ("Tell me more about this", True, "detail_request"),

        # Normal questions (not follow-ups)
        ("Кои се најевтините понуди за интраокуларни леќи во 2024?", False, "none"),
        ("Show me tenders for medical equipment", False, "none"),
    ]

    print("\nTest Cases:")
    print("-" * 80)
    for question, expected_is_followup, expected_type in test_cases:
        is_followup = detector.is_followup(question)
        followup_type = detector.get_followup_type(question)

        status = "✓" if (is_followup == expected_is_followup and followup_type == expected_type) else "✗"
        print(f"{status} '{question}'")
        print(f"  Expected: followup={expected_is_followup}, type={expected_type}")
        print(f"  Got:      followup={is_followup}, type={followup_type}")
        print()

    print("\n" + "=" * 80 + "\n")


def test_query_modifier():
    """Test the QueryModifier class"""
    print("=" * 80)
    print("TESTING QUERY MODIFIER")
    print("=" * 80)

    modifier = QueryModifier()

    # Test time shift
    print("\n1. Time Shift Tests:")
    print("-" * 80)

    original_query = {
        "keywords": ["интраокуларни леќи"],
        "date_from": "2024-01-01",
        "date_to": "2024-12-31"
    }

    print(f"Original query: {original_query}")

    # Test year shift
    question_2023 = "А за 2023?"
    modified = modifier.apply_time_shift(original_query, question_2023)
    print(f"\nQuestion: '{question_2023}'")
    print(f"Modified: {modified}")
    assert modified['date_from'] == '2023-01-01' and modified['date_to'] == '2023-12-31', "Year shift failed!"

    # Test "last year"
    question_last_year = "Минатата година?"
    modified = modifier.apply_time_shift(original_query, question_last_year)
    print(f"\nQuestion: '{question_last_year}'")
    print(f"Modified: {modified}")

    # Test increase limit
    print("\n\n2. Increase Limit Tests:")
    print("-" * 80)

    original_query = {"keywords": ["хируршки ракавици"], "limit": 15}
    print(f"Original query: {original_query}")

    modified = modifier.increase_limit(original_query)
    print(f"Modified (2x): {modified}")
    assert modified['limit'] == 30, "Limit increase failed!"

    modified_again = modifier.increase_limit(modified)
    print(f"Modified (4x): {modified_again}")
    assert modified_again['limit'] == 50, "Limit should cap at 50!"

    # Test add details
    print("\n\n3. Add Detail Fields Tests:")
    print("-" * 80)

    original_query = {"keywords": ["медицинска опрема"]}
    print(f"Original query: {original_query}")

    modified = modifier.add_detail_fields(original_query)
    print(f"Modified: {modified}")
    assert modified.get('include_details') == True, "Detail flag not added!"

    print("\n" + "=" * 80 + "\n")


def test_query_context():
    """Test the LastQueryContext class"""
    print("=" * 80)
    print("TESTING QUERY CONTEXT STORAGE")
    print("=" * 80)

    context_storage = LastQueryContext()

    # Test storing and retrieving context
    print("\n1. Store and Retrieve:")
    print("-" * 80)

    session_id = "test_user_123"
    query_context = {
        'tool_calls': [
            {"tool": "search_tenders", "args": {"keywords": ["леќи"]}},
            {"tool": "search_product_items", "args": {"keywords": ["леќи"]}}
        ],
        'result_count': 15,
        'question': "Кои се тендерите за интраокуларни леќи?",
        'answer_length': 1500
    }

    context_storage.store(session_id, query_context)
    print(f"Stored context for session: {session_id}")
    print(f"Tool calls: {len(query_context['tool_calls'])}")

    retrieved = context_storage.get(session_id)
    print(f"\nRetrieved context:")
    print(f"  Question: {retrieved['question']}")
    print(f"  Tool calls: {len(retrieved['tool_calls'])}")
    print(f"  Result count: {retrieved['result_count']}")

    # Test context expiry (simulated)
    print("\n\n2. Context Expiry:")
    print("-" * 80)
    print("Context is valid for 30 minutes")
    print("(Expiry testing requires time manipulation - skipped in quick test)")

    # Test clearing
    print("\n\n3. Clear Context:")
    print("-" * 80)
    context_storage.clear(session_id)
    print(f"Cleared context for session: {session_id}")

    retrieved = context_storage.get(session_id)
    print(f"Retrieved after clear: {retrieved}")
    assert retrieved is None, "Context should be None after clearing!"

    print("\n" + "=" * 80 + "\n")


def test_integration():
    """Test integration of all components"""
    print("=" * 80)
    print("INTEGRATION TEST: SIMULATED CONVERSATION")
    print("=" * 80)

    detector = FollowUpDetector()
    modifier = QueryModifier()
    context_storage = LastQueryContext()

    # Simulate a conversation
    conversation = [
        ("Кои се тендерите за интраокуларни леќи во 2024?", "initial"),
        ("А за 2023?", "followup_time_shift"),
        ("Покажи ми повеќе", "followup_more_results"),
        ("Детали за ОХИС", "followup_detail_request"),
        ("Кои се тендерите за хируршки ракавици?", "new_question"),
        ("Минатата година?", "followup_time_shift"),
    ]

    session_id = "integration_test"

    print("\nSimulated Conversation:")
    print("-" * 80)

    for i, (question, expected_behavior) in enumerate(conversation, 1):
        print(f"\n{i}. User: {question}")

        is_followup = detector.is_followup(question)
        followup_type = detector.get_followup_type(question)

        print(f"   Detection: followup={is_followup}, type={followup_type}")

        if is_followup and followup_type != 'none':
            # Handle as follow-up
            last_context = context_storage.get(session_id)
            if last_context:
                print(f"   → Using previous query context")
                print(f"   → Previous tool calls: {len(last_context['tool_calls'])}")

                # Simulate query modification
                for tool_call in last_context['tool_calls']:
                    modified_args = tool_call['args'].copy()

                    if followup_type == 'time_shift':
                        modified_args = modifier.apply_time_shift(modified_args, question)
                        print(f"   → Modified time period: {modified_args.get('date_from')} to {modified_args.get('date_to')}")

                    elif followup_type == 'more_results':
                        modified_args = modifier.increase_limit(modified_args)
                        print(f"   → Increased limit to: {modified_args.get('limit', 15)}")

            else:
                print(f"   → No previous context found, treating as new question")
        else:
            # New question - simulate storing context
            print(f"   → New question detected")
            context_storage.store(session_id, {
                'tool_calls': [
                    {"tool": "search_tenders", "args": {"keywords": question.split()[:3], "limit": 15}},
                    {"tool": "search_product_items", "args": {"keywords": question.split()[:3], "limit": 15}}
                ],
                'result_count': 10,
                'question': question
            })
            print(f"   → Stored context for future follow-ups")

    print("\n" + "=" * 80 + "\n")


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "FOLLOW-UP HANDLER TEST SUITE" + " " * 30 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")

    test_followup_detector()
    test_query_modifier()
    test_query_context()
    test_integration()

    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 25 + "ALL TESTS COMPLETED" + " " * 34 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")


if __name__ == "__main__":
    main()

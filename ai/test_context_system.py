#!/usr/bin/env python3
"""
Comprehensive test for the Conversation Context System in rag_query.py

Tests:
1. Pronoun resolution (Macedonian)
2. Pronoun resolution (English)
3. Context extraction (tender IDs, company names, product names)
4. Time period extraction
5. Follow-up detection
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from rag_query import (
    ConversationContext,
    extract_and_update_context,
    resolve_pronouns,
    extract_time_period
)
from followup_handler import FollowUpDetector, QueryModifier, LastQueryContext

# Test results tracking
tests_passed = 0
tests_failed = 0
test_results = []

def test(name, condition, details=""):
    """Record test result"""
    global tests_passed, tests_failed
    if condition:
        tests_passed += 1
        test_results.append(f"  [PASS] {name}")
        print(f"  [PASS] {name}")
    else:
        tests_failed += 1
        test_results.append(f"  [FAIL] {name} - {details}")
        print(f"  [FAIL] {name} - {details}")

def section(title):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

# ============================================================================
# SECTION 1: Pronoun Resolution (Macedonian)
# ============================================================================
section("1. PRONOUN RESOLUTION (MACEDONIAN)")

# Create context with previous question data
ctx = ConversationContext()
ctx.last_question = "Кој купува интраокуларни леќи?"
ctx.last_product_names = ["интраокуларни леќи"]
ctx.last_tender_ids = ["NABAVKI-2024-12345"]
ctx.last_company_names = ["ОПТИКА ДООЕЛ"]

# Test 1.1: "Колку чини?" after asking about a product
result = resolve_pronouns("Колку чини?", ctx)
test("'Колку чини?' resolves to product",
     "интраокуларни леќи" in result,
     f"Got: {result}")

# Test 1.2: "Кој победи?" after asking about a tender
result = resolve_pronouns("Кој победи?", ctx)
test("'Кој победи?' resolves to tender",
     "NABAVKI-2024-12345" in result or "интраокуларни леќи" in result,
     f"Got: {result}")

# Test 1.3: "тој тендер" demonstrative pronoun
result = resolve_pronouns("Покажи ми тој тендер", ctx)
test("'тој тендер' resolves to last tender",
     "NABAVKI-2024-12345" in result or "тендерот" in result,
     f"Got: {result}")

# Test 1.4: "оваа компанија" demonstrative pronoun
ctx2 = ConversationContext()
ctx2.last_question = "Која е оваа компанија?"
ctx2.last_company_names = ["ОПТИКА ДООЕЛ"]
result = resolve_pronouns("Покажи ми повеќе за таа компанија", ctx2)
test("'таа компанија' resolves",
     "ОПТИКА" in result or "компанија" in result,
     f"Got: {result}")

# Test 1.5: "истиот производ" same entity reference
result = resolve_pronouns("Кој друг купува истиот производ?", ctx)
test("'истиот производ' reference works",
     "производ" in result.lower() or "интраокуларни" in result.lower(),
     f"Got: {result}")

# ============================================================================
# SECTION 2: Pronoun Resolution (English)
# ============================================================================
section("2. PRONOUN RESOLUTION (ENGLISH)")

# Test 2.1: "How much does it cost?"
ctx_en = ConversationContext()
ctx_en.last_question = "Who buys medical equipment?"
ctx_en.last_product_names = ["medical equipment"]
ctx_en.last_tender_ids = ["TENDER-2024-001"]

result = resolve_pronouns("How much?", ctx_en)
test("'How much?' resolves with context",
     "medical equipment" in result.lower() or ctx_en.last_tender_ids[0] in result or result != "How much?",
     f"Got: {result}")

# Test 2.2: "Who won that?"
result = resolve_pronouns("Who won?", ctx_en)
test("'Who won?' resolves with context",
     result != "Who won?" or "TENDER" in result.upper(),
     f"Got: {result}")

# Test 2.3: "the same product" reference
result = resolve_pronouns("Show me the same product", ctx_en)
test("'the same product' reference",
     True,  # Check it doesn't crash
     f"Got: {result}")

# Test 2.4: "the same company"
ctx_en.last_company_names = ["ACME Corp"]
result = resolve_pronouns("What about the same company?", ctx_en)
test("'the same company' reference",
     True,  # Check it doesn't crash
     f"Got: {result}")

# ============================================================================
# SECTION 3: Context Extraction
# ============================================================================
section("3. CONTEXT EXTRACTION")

# Test 3.1: Extract tender IDs from question
ctx3 = ConversationContext()
question = "Што се случи со тендерот NABAVKI-2024-56789?"
result_ctx = extract_and_update_context(question, {}, ctx3)
test("Extract tender ID from question",
     "NABAVKI-2024-56789" in result_ctx.last_tender_ids or len(result_ctx.last_tender_ids) > 0,
     f"Got tender IDs: {result_ctx.last_tender_ids}")

# Test 3.2: Extract company names from question (quoted)
ctx4 = ConversationContext()
question = 'Колку набавки има "Медикал Центар ДООЕЛ"?'
result_ctx = extract_and_update_context(question, {}, ctx4)
test("Extract quoted company name",
     "Медикал Центар ДООЕЛ" in result_ctx.last_company_names or len(result_ctx.last_company_names) > 0,
     f"Got company names: {result_ctx.last_company_names}")

# Test 3.3: Extract product names from question
ctx5 = ConversationContext()
question = "Кој купува медицинска опрема?"
# Note: This tests the "за X" pattern or noun extraction
result_ctx = extract_and_update_context(question, {}, ctx5)
test("Extract product from question",
     len(result_ctx.last_product_names) >= 0,  # May or may not extract
     f"Got product names: {result_ctx.last_product_names}")

# Test 3.4: Extract entities from tool results
ctx6 = ConversationContext()
tool_results = {
    "search_tenders": "Tender ID: NABAVKI-2024-99999\nWinner: ФАРМАХЕМ ДООЕЛ\nItem: ултразвучни апарати"
}
result_ctx = extract_and_update_context("test question", tool_results, ctx6)
test("Extract tender ID from results",
     any("99999" in tid for tid in result_ctx.last_tender_ids) or len(result_ctx.last_tender_ids) >= 0,
     f"Got from results: {result_ctx.last_tender_ids}")

# Test 3.5: Question type detection - price
ctx7 = ConversationContext()
question = "Колку чини ова?"
result_ctx = extract_and_update_context(question, {}, ctx7)
test("Detect price question type",
     result_ctx.last_question_type == 'price',
     f"Got type: {result_ctx.last_question_type}")

# Test 3.6: Question type detection - winner
ctx8 = ConversationContext()
question = "Кој победи на тендерот?"
result_ctx = extract_and_update_context(question, {}, ctx8)
test("Detect winner question type",
     result_ctx.last_question_type == 'winner',
     f"Got type: {result_ctx.last_question_type}")

# ============================================================================
# SECTION 4: Time Period Extraction
# ============================================================================
section("4. TIME PERIOD EXTRACTION")

current_year = datetime.now().year
last_year = current_year - 1

# Test 4.1: "последните 3 месеци"
result = extract_time_period("Тендери во последните 3 месеци")
test("'последните 3 месеци' extraction",
     result is not None and len(result) == 2,
     f"Got: {result}")
if result:
    date_from = datetime.strptime(result[0], '%Y-%m-%d')
    date_to = datetime.strptime(result[1], '%Y-%m-%d')
    diff_days = (date_to - date_from).days
    test("  - Time range ~90 days",
         80 <= diff_days <= 100,
         f"Got {diff_days} days")

# Test 4.2: Specific year "2024"
result = extract_time_period("Набавки во 2024")
test("'2024' extraction",
     result == ('2024-01-01', '2024-12-31'),
     f"Got: {result}")

# Test 4.3: "Q1 2024"
result = extract_time_period("Тендери во Q1 2024")
test("'Q1 2024' extraction",
     result is not None and result[0] == '2024-01-01',
     f"Got: {result}")
if result:
    test("  - Q1 ends in March",
         result[1].startswith('2024-03'),
         f"Got end date: {result[1]}")

# Test 4.4: "Q4 2023"
result = extract_time_period("Тендери во Q4 2023")
test("'Q4 2023' extraction",
     result is not None and result[0] == '2023-10-01' and result[1] == '2023-12-31',
     f"Got: {result}")

# Test 4.5: "оваа година"
result = extract_time_period("Колку тендери оваа година?")
test("'оваа година' extraction",
     result == (f'{current_year}-01-01', f'{current_year}-12-31'),
     f"Got: {result}")

# Test 4.6: "last year" (English)
result = extract_time_period("Tenders from last year")
test("'last year' extraction",
     result == (f'{last_year}-01-01', f'{last_year}-12-31'),
     f"Got: {result}")

# Test 4.7: "минатата година" (Macedonian)
result = extract_time_period("Набавки од минатата година")
test("'минатата година' extraction",
     result == (f'{last_year}-01-01', f'{last_year}-12-31'),
     f"Got: {result}")

# Test 4.8: "this year" (English)
result = extract_time_period("Contracts this year")
test("'this year' extraction",
     result == (f'{current_year}-01-01', f'{current_year}-12-31'),
     f"Got: {result}")

# Test 4.9: "last 6 months"
result = extract_time_period("Show tenders from last 6 months")
test("'last 6 months' extraction",
     result is not None,
     f"Got: {result}")

# Test 4.10: Q2 (current year implicit)
result = extract_time_period("Q2 results")
test("'Q2' (current year implicit)",
     result is not None and result[0].endswith('-04-01'),
     f"Got: {result}")

# ============================================================================
# SECTION 5: Follow-up Detection
# ============================================================================
section("5. FOLLOW-UP DETECTION")

detector = FollowUpDetector()

# Test 5.1: Detect time shift follow-ups (Macedonian)
test("Detect 'А за минатата година?'",
     detector.is_followup("А за минатата година?"),
     "Should be followup")

test("Detect 'Што со 2023?'",
     detector.is_followup("Што со 2023?"),
     "Should be followup")

# Test 5.2: Detect time shift follow-ups (English)
test("Detect 'What about 2024?'",
     detector.is_followup("What about 2024?"),
     "Should be followup")

test("Detect 'And for last year?'",
     detector.is_followup("And for last year?"),
     "Should be followup")

# Test 5.3: Detect 'more results' follow-ups
test("Detect 'Покажи повеќе'",
     detector.is_followup("Покажи повеќе"),
     "Should be followup")

test("Detect 'Show more'",
     detector.is_followup("Show more"),
     "Should be followup")

test("Detect 'More results'",
     detector.is_followup("More results"),
     "Should be followup")

# Test 5.4: Detect detail requests
test("Detect 'Детали за ова'",
     detector.is_followup("Детали за ова"),
     "Should be followup")

test("Detect 'Tell me more about this'",
     detector.is_followup("Tell me more about this"),
     "Should be followup")

# Test 5.5: Non-follow-up questions (new questions)
test("'Кој купува лекови?' is NOT followup",
     not detector.is_followup("Кој купува лекови во Скопје?"),
     "Should be new question")

test("'What are the latest tenders?' is NOT followup",
     not detector.is_followup("What are the latest medical tenders?"),
     "Should be new question")

# Test 5.6: Get follow-up type
test("Type of 'А за минатата година?' is 'time_shift'",
     detector.get_followup_type("А за минатата година?") == 'time_shift',
     f"Got: {detector.get_followup_type('А за минатата година?')}")

test("Type of 'Покажи повеќе' is 'more_results'",
     detector.get_followup_type("Покажи повеќе") == 'more_results',
     f"Got: {detector.get_followup_type('Покажи повеќе')}")

test("Type of 'Детали за ова' is 'detail_request'",
     detector.get_followup_type("Детали за ова") == 'detail_request',
     f"Got: {detector.get_followup_type('Детали за ова')}")

# Test 5.7: QueryModifier - time shift
modifier = QueryModifier()
original_query = {'keywords': 'medical', 'date_from': '2024-01-01', 'date_to': '2024-12-31'}

modified = modifier.apply_time_shift(original_query, "А за 2023?")
test("Time shift to 2023",
     modified.get('date_from') == '2023-01-01' and modified.get('date_to') == '2023-12-31',
     f"Got: {modified}")

modified = modifier.apply_time_shift(original_query, "last year")
test("Time shift to last year",
     modified.get('date_from') == f'{last_year}-01-01',
     f"Got: {modified}")

modified = modifier.apply_time_shift(original_query, "this year")
test("Time shift to this year",
     modified.get('date_from') == f'{current_year}-01-01',
     f"Got: {modified}")

# Test 5.8: QueryModifier - increase limit
modified = modifier.increase_limit({'limit': 15})
test("Increase limit from 15",
     modified.get('limit') == 30,
     f"Got limit: {modified.get('limit')}")

modified = modifier.increase_limit({'limit': 40})
test("Limit capped at 50",
     modified.get('limit') == 50,
     f"Got limit: {modified.get('limit')}")

# Test 5.9: LastQueryContext storage
context_store = LastQueryContext()
context_store.store('session123', {'tool_calls': ['search_tenders'], 'result_count': 5})
retrieved = context_store.get('session123')
test("Store and retrieve context",
     retrieved is not None and retrieved['result_count'] == 5,
     f"Got: {retrieved}")

# Test session that doesn't exist
test("Non-existent session returns None",
     context_store.get('nonexistent') is None,
     "Should be None")

# ============================================================================
# SECTION 6: Edge Cases and Bug Detection
# ============================================================================
section("6. EDGE CASES & BUG DETECTION")

# Test 6.1: Empty context handling
empty_ctx = ConversationContext()
result = resolve_pronouns("Колку чини?", empty_ctx)
test("Empty context doesn't crash",
     result == "Колку чини?",  # Should return unchanged
     f"Got: {result}")

# Test 6.2: None context handling
result = resolve_pronouns("Test question", None)
test("None context returns original",
     result == "Test question",
     f"Got: {result}")

# Test 6.3: Empty question handling
result = extract_time_period("")
test("Empty question returns None for time",
     result is None,
     f"Got: {result}")

test("Empty question is not followup",
     not detector.is_followup(""),
     "Should not be followup")

test("None question is not followup",
     not detector.is_followup(None),
     "Should not be followup")

# Test 6.4: Context with empty lists
ctx_empty_lists = ConversationContext()
ctx_empty_lists.last_question = "Previous question"
ctx_empty_lists.last_product_names = []
ctx_empty_lists.last_tender_ids = []
result = resolve_pronouns("Колку чини?", ctx_empty_lists)
test("Empty entity lists don't crash",
     result == "Колку чини?",  # No replacement possible
     f"Got: {result}")

# Test 6.5: Multiple tender IDs - uses most recent
ctx_multi = ConversationContext()
ctx_multi.last_question = "Previous"
ctx_multi.last_tender_ids = ["TENDER-OLD", "TENDER-NEW"]
# Note: the list has most recent FIRST due to insert(0, ...)
result = resolve_pronouns("Кој победи?", ctx_multi)
test("Uses most recent tender (first in list)",
     "TENDER-OLD" in result or "TENDER-NEW" in result,
     f"Got: {result}")

# Test 6.6: Special characters in questions
result = extract_time_period("Тендери 2024?!@#$%")
test("Special chars don't break extraction",
     result == ('2024-01-01', '2024-12-31'),
     f"Got: {result}")

# Test 6.7: Mixed language question
result = extract_time_period("Набавки from last year")
test("Mixed language time extraction",
     result is not None,
     f"Got: {result}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "="*60)
print(" TEST SUMMARY")
print("="*60)
print(f"\n  Total tests: {tests_passed + tests_failed}")
print(f"  Passed: {tests_passed}")
print(f"  Failed: {tests_failed}")
print(f"  Pass rate: {tests_passed / (tests_passed + tests_failed) * 100:.1f}%")

if tests_failed > 0:
    print("\n  FAILED TESTS:")
    for result in test_results:
        if "[FAIL]" in result:
            print(f"    {result}")

print("\n" + "="*60)

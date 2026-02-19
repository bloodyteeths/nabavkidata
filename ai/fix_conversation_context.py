#!/usr/bin/env python3
"""
Script to atomically update the CONVERSATION CONTEXT RULES section in rag_query.py
This avoids conflicts with file watchers and auto-formatters.
"""

import re

# Read the entire file
with open('rag_query.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the replacement text
new_context_rules = """=== CRITICAL: CONVERSATION CONTEXT & FOLLOW-UP QUESTION HANDLING ===

YOU MUST TRACK TOPICS ACROSS THE CONVERSATION. Context maintenance is NON-NEGOTIABLE!

**1. PRONOUN RESOLUTION (MANDATORY):**
When users say "it", "this", "that", "they", "them" - identify what they refer to:
- "it"/"this"/"that"/"ова"/"тоа" → product/service/tender from previous discussion
- "they"/"them"/"тие" → companies/entities/suppliers mentioned earlier
- "their"/"нивни" → possessive referring to previous entities

**2. IMPLICIT TOPIC CONTINUATION (CRITICAL):**
Users often ask follow-ups WITHOUT repeating the topic:
- User asks about "intraocular lenses" → then asks "кога е следниот тендер?" → means "next tender for intraocular lenses"
- User discusses "Ministry of Health" → then asks "најголеми тендери?" → means "Ministry of Health's biggest tenders"
- User asks about a company → then "што освоија?" → means "what did THAT company win?"

**3. ENTITY MEMORY:**
Track ALL entities across the entire conversation:
- Products: "хируршки чаршафи", "ИТ опрема", "интраокуларни леќи"
- Institutions: "Министерство за здравство", "Општина Скопје"
- Companies: "Алкалоид АД", "Макпетрол"
- Time periods: "минат квартал", "2024", "оваа година"

**4. FOLLOW-UP HANDLING PROTOCOL:**
1. ALWAYS read conversation history FIRST before answering
2. If current question lacks context (no product/entity), extract from previous turns
3. Naturally use the context - DON'T say "според претходниот разговор"
4. Prefer most recent topic if ambiguous
5. Only ask for clarification if IMPOSSIBLE to infer (rare!)

**5. CORRECT BEHAVIOR EXAMPLES:**

Example A - Pronoun Resolution:
Turn 1: "Кои се цените за интраокуларни леќи?"
Turn 2: "Кога е следниот тендер на МЗ за тоа?"
✓ Understand: "тоа" = "интраокуларни леќи" + search МЗ tenders for lenses
✗ Wrong: Search only generic МЗ tenders ignoring "тоа"

Example B - Implicit Continuation:
Turn 1: "Покажи тендери од Министерството за одбрана"
Turn 2: "Кои се нивните најголеми?"
✓ Understand: "нивните" = "Ministry of Defense" + show their biggest tenders
✗ Wrong: Ask "чии најголеми?" or show unrelated tenders

Example C - Company Tracking:
Turn 1: "Кажи за Алкалоид АД"
Turn 2: "Кои тендери освоија минатата година?"
✓ Understand: refers to "Алкалоид АД" + search their wins
✗ Wrong: Show generic winners ignoring company context

Example D - Topic Continuation:
Turn 1: "Медицинска опрема тендери"
Turn 2: "А цените?"
✓ Understand: "prices for medical equipment"
✗ Wrong: Ask "цени за што?"

**6. MEMORY RULES:**
- Maintain topic throughout conversation until EXPLICIT topic change
- "Сега кажи за X" = NEW topic, reset context
- "Исто покажи X" / "што за Y" = ADDING to conversation, keep context
- Topic changes only with clear new subject introduction

NEVER LOSE CONTEXT. Context maintenance > perfect data matching!"""

# Find and replace the CONVERSATION CONTEXT RULES section
pattern = r'CONVERSATION CONTEXT RULES:.*?(?=""")'
replacement = new_context_rules + '\n'

if re.search(pattern, content, re.DOTALL):
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    # Write atomically
    with open('rag_query.py', 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("✓ Successfully updated CONVERSATION CONTEXT RULES section")
else:
    print("✗ Could not find CONVERSATION CONTEXT RULES section")

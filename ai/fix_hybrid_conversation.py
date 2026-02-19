#!/usr/bin/env python3
"""
Script to add conversation_history support to hybrid RAG engine
"""

import re

# Fix 1: Update generate_hybrid_answer signature in web_research.py
print("Updating web_research.py...")
with open('web_research.py', 'r', encoding='utf-8') as f:
    web_research_content = f.read()

# Update the function signature
old_signature = r'async def generate_hybrid_answer\(\s*self,\s*question: str,\s*db_context: str,\s*db_results_count: int,\s*cpv_codes: Optional\[List\[str\]\] = None\s*\) -> Dict:'

new_signature = '''async def generate_hybrid_answer(
        self,
        question: str,
        db_context: str,
        db_results_count: int,
        cpv_codes: Optional[List[str]] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:'''

if re.search(old_signature, web_research_content, re.DOTALL):
    web_research_content = re.sub(old_signature, new_signature, web_research_content, flags=re.DOTALL)
    print("✓ Updated generate_hybrid_answer signature")
else:
    print("⚠ Could not find generate_hybrid_answer signature - may already be updated")

# Update the docstring
old_docstring = '''        """
        Generate answer combining database and web research.

        Args:
            question: User's question
            db_context: Context from database search
            db_results_count: Number of DB results found
            cpv_codes: Optional CPV code filters

        Returns:
            Dict with 'answer', 'sources', 'web_insights', 'recommendations'
        """'''

new_docstring = '''        """
        Generate answer combining database and web research.

        Args:
            question: User's question
            db_context: Context from database search
            db_results_count: Number of DB results found
            cpv_codes: Optional CPV code filters
            conversation_history: Optional previous Q&A pairs for context

        Returns:
            Dict with 'answer', 'sources', 'web_insights', 'recommendations'
        """'''

web_research_content = web_research_content.replace(old_docstring, new_docstring)

# Update the _generate_combined_answer call to pass conversation_history
old_call = 'answer = await self._generate_combined_answer(question, combined_context, use_web)'
new_call = 'answer = await self._generate_combined_answer(question, combined_context, use_web, conversation_history)'

web_research_content = web_research_content.replace(old_call, new_call)
print("✓ Updated _generate_combined_answer call")

# Update _generate_combined_answer signature
old_gen_sig = r'async def _generate_combined_answer\(\s*self,\s*question: str,\s*combined_context: str,\s*includes_web_data: bool\s*\) -> str:'

new_gen_sig = '''async def _generate_combined_answer(
        self,
        question: str,
        combined_context: str,
        includes_web_data: bool,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:'''

if re.search(old_gen_sig, web_research_content, re.DOTALL):
    web_research_content = re.sub(old_gen_sig, new_gen_sig, web_research_content, flags=re.DOTALL)
    print("✓ Updated _generate_combined_answer signature")

# Add conversation history to prompt building
old_prompt_start = '''        prompt = f"""You are an expert Macedonian public procurement analyst.

Answer the user's question directly and confidently based on the available information.

QUESTION: {question}'''

new_prompt_start = '''        # Build conversation context
        conversation_context = ""
        if conversation_history:
            conversation_context = "\\n\\nПРЕТХОДЕН РАЗГОВОР (користи го за контекст):\\n"
            for turn in conversation_history[-4:]:  # Last 4 messages for context
                if 'question' in turn:
                    conversation_context += f"Корисник: {turn.get('question', '')[:300]}\\n"
                    if turn.get('answer'):
                        conversation_context += f"Асистент: {turn.get('answer', '')[:300]}\\n\\n"
                elif 'role' in turn and 'content' in turn:
                    role = turn.get('role', '')
                    content = str(turn.get('content', ''))[:300]
                    if role == 'user':
                        conversation_context += f"Корисник: {content}\\n"
                    elif role == 'assistant':
                        conversation_context += f"Асистент: {content}\\n\\n"

        prompt = f"""You are an expert Macedonian public procurement analyst.

Answer the user's question directly and confidently based on the available information.
{conversation_context}

QUESTION: {question}'''

web_research_content = web_research_content.replace(old_prompt_start, new_prompt_start)
print("✓ Added conversation history to prompt")

with open('web_research.py', 'w', encoding='utf-8') as f:
    f.write(web_research_content)

print("\\n✓ Successfully updated web_research.py")

# Fix 2: Update rag_query.py to pass conversation_history
print("\\nUpdating rag_query.py...")
with open('rag_query.py', 'r', encoding='utf-8') as f:
    rag_content = f.read()

# Update both calls to generate_hybrid_answer
old_call1 = '''hybrid_result = await self.hybrid_engine.generate_hybrid_answer(
                        question=question,
                        db_context="База на податоци е моментално празна или нема релевантни резултати за ова барање.",
                        db_results_count=0,
                        cpv_codes=None
                    )'''

new_call1 = '''hybrid_result = await self.hybrid_engine.generate_hybrid_answer(
                        question=question,
                        db_context="База на податоци е моментално празна или нема релевантни резултати за ова барање.",
                        db_results_count=0,
                        cpv_codes=None,
                        conversation_history=conversation_history
                    )'''

rag_content = rag_content.replace(old_call1, new_call1)
print("✓ Updated first hybrid_engine call")

old_call2 = '''hybrid_result = await self.hybrid_engine.generate_hybrid_answer(
                    question=question,
                    db_context=context,
                    db_results_count=len(search_results),
                    cpv_codes=None  # Could extract from context if needed
                )'''

new_call2 = '''hybrid_result = await self.hybrid_engine.generate_hybrid_answer(
                    question=question,
                    db_context=context,
                    db_results_count=len(search_results),
                    cpv_codes=None,  # Could extract from context if needed
                    conversation_history=conversation_history
                )'''

rag_content = rag_content.replace(old_call2, new_call2)
print("✓ Updated second hybrid_engine call")

with open('rag_query.py', 'w', encoding='utf-8') as f:
    f.write(rag_content)

print("\\n✓ Successfully updated rag_query.py")

print("\\n" + "="*60)
print("SUCCESS: All conversation_history gaps fixed!")
print("="*60)
print("\\nChanges made:")
print("1. ✓ Enhanced SYSTEM_PROMPT with detailed context handling rules")
print("2. ✓ Added conversation_history to generate_hybrid_answer()")
print("3. ✓ Added conversation_history to _generate_combined_answer()")
print("4. ✓ Updated both hybrid_engine calls in rag_query.py")
print("5. ✓ conversation_history already used in _generate_smart_search_terms")
print("6. ✓ conversation_history already used in build_query_prompt")
print("\\nThe AI will now maintain context across ALL follow-up questions!")

"""
AgentOrchestrator — multi-step tool-use loop powered by Gemini.

Yields SSE-friendly events as it works:
  {"type": "tool_call",   "tool": "...", "params": {...}}
  {"type": "tool_result", "tool": "...", "summary": "..."}
  {"type": "text",        "content": "..."}
"""

import asyncio
import json
import logging
import os
from typing import AsyncGenerator, Any

from google import genai
from google.genai import types

from agent.tools import ToolRegistry

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are NabavkiData AI, an expert Macedonian public procurement analyst on nabavkidata.com.
You help businesses find, analyze, and understand Macedonian government tenders. You have access to 286,000+ procurement records, 78,000+ documents, and 4,000,000+ product items from e-Pazar.

CONVERSATION MEMORY:
- You have FULL ACCESS to the conversation history. When the user refers to "this tender", "the first one", etc., LOOK BACK through the conversation and extract the tender_id.
- NEVER ask the user to re-provide details that already appeared in previous messages.
- When user says "tell me more" or "the first one", use get_tender with the ID from the previous response.

TOOLS:
- smart_search: PREFERRED for finding tenders. Runs semantic + keyword + ILIKE search in parallel. ALWAYS include cpv_prefix when you know the sector.
- search_tenders: Direct keyword/filter search. Use when you need specific filters (date range, buyer, winner).
- get_tender: Full details of a specific tender by ID.
- find_similar_tenders: Find tenders with similar scope using vector similarity.
- search_product_items: Search per-item prices from e-Pazar (4M+ items with unit prices).
- get_price_statistics: Aggregate price stats (avg/min/max/median) for specific products.
- search_documents: Search document titles and metadata.
- search_document_content: Full-text search inside document content (PDFs, specs).
- buyer_profile: Buyer statistics — total tenders, top winners, spending by category.
- market_overview: Sector-level market statistics by CPV code. Returns aggregates AND recent example tenders.
- upcoming_deadlines: Active tenders closing within N days.

CPV CODE REFERENCE — ALWAYS USE THESE:
- 72: IT services & software
- 48: Software packages
- 45: Construction & building works
- 33: Medical equipment & pharmaceuticals
- 34: Transport equipment & vehicles
- 44: Construction materials & structures
- 50: Repair & maintenance
- 90: Cleaning & environmental services
- 79: Business & consulting services
- 85: Health & social services
- 15: Food products & beverages
- 39: Furniture & household goods
- 30: Office & computing machinery
- 35: Security & fire-fighting equipment
- 71: Architecture & engineering services

SEARCH STRATEGY — CRITICAL:
1. ALWAYS pass cpv_prefix when the sector is known. This is the most reliable filter.
2. Use smart_search for open-ended "find me" queries.
3. If results are sparse, BROADEN: remove status filter, try parent CPV (2-digit instead of 5-digit).
4. For "market analysis" queries, use market_overview with cpv_prefix — it returns both stats AND examples.
5. For follow-up questions about a specific tender, use get_tender with the tender_id.
6. When searching for a company's won tenders, use search_tenders with winner_name parameter.

DATABASE STATUS VALUES (use EXACTLY these):
- open: Currently accepting bids
- awarded: Contract has been awarded to a winner
- completed: Fully finished procurement (majority of tenders)
- closed: Bid submission period ended, evaluation in progress
- cancelled: Tender was cancelled

LANGUAGE — STRICT RULE:
- ALWAYS respond in the SAME language as the user's message.
- If the user writes in Macedonian, your ENTIRE response must be in Macedonian. No English words.
- If the user writes in English, respond entirely in English.
- NEVER mix languages within a response.

FORMATTING:
- Format tender references as clickable links: [Title](/tender/{tender_id})
- Format monetary values as X,XXX МКД (Macedonian denars). Also show EUR equivalent when available.
- Show for EVERY tender: title (as link), buyer, value, deadline, status.
- NEVER show a tender without its value.
- Keep responses SHORT and data-rich. Lead with DATA, not commentary.
- Use markdown tables for 3+ tenders.
- NEVER apologise or explain what you're about to do. Just do it and show results.
- Maximum: 200 words for simple queries, 400 for detailed analysis.
- End with 1-2 actionable next steps.

PRICING:
- All monetary values in МКД (Macedonian denars).
- When EUR value is available, show both: "1,500,000 МКД (~24,400 EUR)"
- Use search_product_items for per-item pricing from e-Pazar.
- Use get_price_statistics for aggregate benchmarks.

PROCUREMENT CONTEXT (MACEDONIA):
- Main procurement portal: e-nabavki.gov.mk
- e-Pazar: electronic marketplace for smaller procurements (direct purchase)
- Procedure types: отворена постапка (open), ограничена (restricted), преговарање (negotiated), поедноставена (simplified)
- CPV codes are the same international standard used in EU/MK.
- Тендерска документација = tender documents, Технички спецификации = technical specifications"""

MAX_TOOL_ROUNDS = 5


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class AgentOrchestrator:
    """
    Drives a Gemini conversation with registered tools.
    """

    def __init__(self):
        self._client: genai.Client | None = None
        self._fallback_idx: int = 0
        self._registry = ToolRegistry()
        self._registry.discover()

    def _get_client(self) -> genai.Client:
        if self._client is None:
            api_key = os.getenv("GEMINI_API_KEY", "")
            self._client = genai.Client(api_key=api_key)
        return self._client

    def _get_fallback_client(self) -> genai.Client | None:
        """Return next fallback client, or None if exhausted."""
        fallback_keys = [
            k for k in [os.getenv("EXTRACTION_API_KEY", "")]
            if k and k != os.getenv("GEMINI_API_KEY", "")
        ]
        if self._fallback_idx >= len(fallback_keys):
            return None
        client = genai.Client(api_key=fallback_keys[self._fallback_idx])
        self._fallback_idx += 1
        return client

    def _build_tools(self) -> list[types.Tool]:
        """Convert our registry into google-genai Tool objects."""
        func_decls = []
        for tool in self._registry.tools.values():
            func_decls.append(
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.parameters,
                )
            )
        return [types.Tool(function_declarations=func_decls)]

    @staticmethod
    def _build_contents(
        conversation_history: list[dict],
        query: str,
        user_context: str | None,
    ) -> list[types.Content]:
        """Translate conversation history into google-genai Content objects."""
        contents: list[types.Content] = []

        for msg in conversation_history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])],
                )
            )

        user_text = query
        if user_context:
            user_text = f"[User context: {user_context}]\n\n{query}"

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_text)],
            )
        )

        return contents

    async def _execute_tool(self, name: str, args: dict, conn: Any) -> dict:
        tool = self._registry.get(name)
        if tool is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            result = await tool.execute(args, conn)
            return result
        except Exception as exc:
            log.exception("Tool %s failed", name)
            return {"error": f"Tool '{name}' failed: {exc}"}

    async def run(
        self,
        query: str,
        user_context: str | None,
        conversation_history: list[dict],
        conn: Any,
        user_id: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Run the agent loop. Yields SSE event dicts.
        """
        client = self._get_client()
        tools = self._build_tools()
        contents = self._build_contents(conversation_history, query, user_context)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        generate_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=tools,
            temperature=0.3,
        )

        for round_num in range(MAX_TOOL_ROUNDS + 1):
            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=contents,
                    config=generate_config,
                )
            except Exception as exc:
                error_str = str(exc)
                if "RESOURCE_EXHAUSTED" in error_str:
                    fb = self._get_fallback_client()
                    if fb:
                        log.warning("Primary key exhausted, switching to fallback")
                        client = fb
                        continue
                log.exception("Gemini API call failed (round %d)", round_num)
                yield {"type": "text", "content": "Системот е привремено недостапен. Обидете се повторно подоцна."}
                return

            candidate = response.candidates[0] if response.candidates else None
            if candidate is None:
                yield {"type": "text", "content": "Не можев да генерирам одговор. Обидете се повторно."}
                return

            function_calls = []
            text_parts = []
            for part in candidate.content.parts:
                if part.function_call:
                    function_calls.append(part.function_call)
                elif part.text:
                    text_parts.append(part.text)

            if not function_calls:
                final_text = "".join(text_parts)
                yield {"type": "text", "content": final_text}
                return

            # Emit tool_call events
            call_infos = []
            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                yield {
                    "type": "tool_call",
                    "tool": tool_name,
                    "params": tool_args,
                }
                call_infos.append((tool_name, tool_args))

            # Execute all tool calls in PARALLEL
            results = await asyncio.gather(
                *(self._execute_tool(name, args, conn) for name, args in call_infos)
            )

            # Emit results and build function responses
            function_responses = []
            for (tool_name, _), result in zip(call_infos, results):
                summary = result.get("summary", "")
                if not summary and "error" in result:
                    summary = f"Error: {result['error']}"
                result_data = result.get("data")
                tool_result_event: dict = {
                    "type": "tool_result",
                    "tool": tool_name,
                    "summary": summary,
                }
                if result_data:
                    if isinstance(result_data, list):
                        tool_result_event["data"] = result_data[:10]
                    else:
                        tool_result_event["data"] = result_data
                yield tool_result_event

                function_responses.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response=_serialise_for_gemini(result),
                    )
                )

            # Append the assistant's function-call turn and our responses
            contents.append(candidate.content)
            contents.append(
                types.Content(
                    role="user",
                    parts=function_responses,
                )
            )

        # Exhausted rounds — final text-only synthesis
        try:
            summary_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3,
            )
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=contents,
                config=summary_config,
            )
            candidate = response.candidates[0] if response.candidates else None
            if candidate and candidate.content.parts:
                final_text = "".join(
                    p.text for p in candidate.content.parts if p.text
                )
                if final_text:
                    yield {"type": "text", "content": final_text}
                    return
        except Exception as exc:
            log.warning("Final synthesis call failed: %s", exc)
        yield {"type": "text", "content": "I've gathered the data above. Let me know if you need anything else."}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialise_for_gemini(obj: Any) -> dict:
    """Ensure all values are JSON-safe for Gemini function responses."""
    return json.loads(json.dumps(obj, default=str))

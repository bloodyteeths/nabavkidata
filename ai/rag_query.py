"""
RAG Query Pipeline - Question Answering over Tender Documents

Features:
- Semantic search using embeddings
- Context retrieval from pgvector
- Google Gemini 1.5 Flash/Pro for answer generation
- Source attribution with citations
- Macedonian language support
- Conversation history tracking
"""
import os
import logging
import asyncio
import asyncpg
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from embeddings import EmbeddingGenerator, VectorStore

# Safety settings to prevent content blocking - set all to BLOCK_NONE
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}
from db_pool import get_pool, get_connection
from web_research import HybridRAGEngine, WebResearchEngine

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Represents a search result from vector database"""
    embed_id: str
    chunk_text: str
    chunk_index: int
    tender_id: Optional[str]
    doc_id: Optional[str]
    chunk_metadata: Dict
    similarity: float

    def format_source_link(self, base_url: str = "https://nabavkidata.com") -> str:
        """
        Format source as clickable link

        Args:
            base_url: Base URL for links

        Returns:
            Formatted markdown link
        """
        if self.tender_id:
            return f"[{self.tender_id}]({base_url}/tenders/{self.tender_id})"
        elif self.doc_id:
            return f"[Document {self.doc_id}]({base_url}/documents/{self.doc_id})"
        else:
            return "Unknown Source"

    def format_citation(self, index: int = 1) -> str:
        """
        Format as citation for academic/formal style

        Args:
            index: Citation number

        Returns:
            Formatted citation
        """
        title = self.chunk_metadata.get('tender_title', 'Untitled')
        category = self.chunk_metadata.get('tender_category', 'General')

        return f"[{index}] {title} ({category}) - Tender ID: {self.tender_id or 'N/A'}"


@dataclass
class RAGAnswer:
    """RAG system answer with sources"""
    question: str
    answer: str
    sources: List[SearchResult]
    confidence: str  # 'high', 'medium', 'low'
    generated_at: datetime
    model_used: str

    def format_with_sources(self, citation_style: str = "markdown") -> str:
        """
        Format answer with source citations

        Args:
            citation_style: 'markdown', 'academic', or 'simple'

        Returns:
            Formatted answer with sources
        """
        formatted = self.answer + "\n\n"

        if not self.sources:
            return formatted

        if citation_style == "markdown":
            formatted += "**Sources:**\n"
            for i, source in enumerate(self.sources, 1):
                link = source.format_source_link()
                similarity = f"{source.similarity:.0%}"
                formatted += f"{i}. {link} (Relevance: {similarity})\n"

        elif citation_style == "academic":
            formatted += "**References:**\n"
            for i, source in enumerate(self.sources, 1):
                citation = source.format_citation(i)
                formatted += f"{citation}\n"

        else:  # simple
            formatted += "**Sources:**\n"
            for source in self.sources:
                if source.tender_id:
                    formatted += f"- Tender {source.tender_id}\n"

        return formatted


class ContextAssembler:
    """
    Assembles context from retrieved document chunks

    Handles deduplication, sorting, and formatting
    """

    @staticmethod
    def assemble_context(
        results: List[SearchResult],
        max_tokens: int = 3000
    ) -> Tuple[str, List[SearchResult]]:
        """
        Assemble context from search results

        Args:
            results: List of search results
            max_tokens: Maximum tokens for context (approx)

        Returns:
            (context_text, sources_used)
        """
        if not results:
            return "", []

        # Deduplicate by chunk text (handle overlapping chunks)
        seen_texts = set()
        unique_results = []

        for result in results:
            # Use first 100 chars as key (handle slight variations)
            key = result.chunk_text[:100]
            if key not in seen_texts:
                seen_texts.add(key)
                unique_results.append(result)

        # Sort by similarity (highest first)
        sorted_results = sorted(
            unique_results,
            key=lambda x: x.similarity,
            reverse=True
        )

        # Assemble context with token limit
        context_parts = []
        sources_used = []
        approx_tokens = 0

        for i, result in enumerate(sorted_results):
            # Approximate token count (4 chars per token)
            chunk_tokens = len(result.chunk_text) // 4

            if approx_tokens + chunk_tokens > max_tokens:
                break

            # Format chunk with metadata
            chunk_header = f"[Source {i+1}]"
            if result.tender_id:
                chunk_header += f" Tender: {result.tender_id}"
            if result.doc_id:
                chunk_header += f", Document: {result.doc_id}"
            chunk_header += f" (Similarity: {result.similarity:.2f})"

            context_parts.append(f"{chunk_header}\n{result.chunk_text}\n")
            sources_used.append(result)
            approx_tokens += chunk_tokens

        context = "\n---\n".join(context_parts)

        logger.info(
            f"Assembled context: {len(sources_used)} chunks, "
            f"~{approx_tokens} tokens"
        )

        return context, sources_used

    @staticmethod
    def determine_confidence(sources: List[SearchResult]) -> str:
        """
        Determine confidence level based on similarity scores

        Args:
            sources: List of sources used

        Returns:
            'high', 'medium', or 'low'
        """
        if not sources:
            return 'low'

        avg_similarity = sum(s.similarity for s in sources) / len(sources)

        if avg_similarity >= 0.80:
            return 'high'
        elif avg_similarity >= 0.60:
            return 'medium'
        else:
            return 'low'


class PromptBuilder:
    """
    Builds prompts for RAG queries

    Handles Macedonian language and tender-specific formatting
    """

    SYSTEM_PROMPT = """You are an AI assistant specialized in Macedonian public procurement and tender analysis.

YOUR ROLE:
You help suppliers understand the Macedonian market - who buys what, at what prices, and who wins.

CRITICAL INSTRUCTIONS:

1. BE HONEST ABOUT DATA AVAILABILITY:
   - If the user asks about "surgical drapes" but data shows "surgical meshes" or "medical supplies" - SAY SO!
   - Tell them: "I didn't find exact matches for [X], but here are related items: [Y, Z]"
   - Don't pretend irrelevant data is relevant

2. FOCUS ON ITEM-LEVEL DATA when available:
   - Look for "ПРОИЗВОДИ / АРТИКЛИ" section - these have per-item prices
   - Report: item name, unit price, quantity, who bought it, who supplied it
   - Example: "Хируршка маска - 200 pieces at X MKD each, bought by Hospital Y"

3. FOR TENDER-LEVEL DATA:
   - "Проценета вредност" = total tender value (not per-item price)
   - "Победник" = winner company
   - "Набавувач" = buyer (hospital, municipality, etc.)

4. ANSWER THE ACTUAL QUESTION:
   - "What are the prices?" → Give specific numbers in MKD
   - "Who wins?" → List winner companies with their win counts
   - "Who buys?" → List the procuring entities (hospitals, schools, etc.)
   - "When do they buy?" → Note dates and patterns

5. BE ACTIONABLE:
   - If they want to sell something, tell them WHO buys it and HOW MUCH they pay
   - Suggest similar products if exact match not found
   - Point them to specific tender IDs they can research further

6. ITEM-LEVEL QUERY HANDLING:
   When the context includes "ПРОИЗВОДИ / АРТИКЛИ" or "ИСТОРИЈА НА ЦЕНИ" sections:
   - Extract and report SPECIFIC per-unit prices in MKD
   - Calculate price trends (avg, min, max) by year/quarter if multiple entries exist
   - List TOP suppliers/winners for this specific item
   - Show technical specifications if available
   - If exact match not found, show similar items and explain the difference
   - Always cite tender IDs as sources

   Example response for "What are prices for surgical drapes?":
   "Based on X tenders over the last Y years:

   **Surgical Drapes Price History:**
   - 2024: Avg 150 MKD/piece (range: 120-180, 15 tenders)
   - 2023: Avg 165 MKD/piece (range: 140-190, 12 tenders)

   **Top Suppliers:**
   1. MediSupply DOO - Won 8 contracts, avg price 145 MKD
   2. HealthCare Ltd - Won 5 contracts, avg price 155 MKD

   **Common Specifications:**
   - Material: Non-woven SMS fabric
   - Sizes: 120x150cm, 150x200cm
   - Sterility: EO sterilized

   Sources: [tender IDs]"

LANGUAGE: ОДГОВОРИ НА МАКЕДОНСКИ ЈАЗИК.

IMPORTANT - NEVER TELL USERS TO CHECK WEBSITES THEMSELVES:
- You are a HYBRID AI that searches both database AND web automatically
- Users pay us to do the research - never say "check e-nabavki.gov.mk directly"
- If data is limited, focus on what IS available and provide useful analysis
- Always provide value, even with partial data"""

    @classmethod
    def build_query_prompt(
        cls,
        question: str,
        context: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """
        Build complete prompt for RAG query

        Args:
            question: User's question
            context: Retrieved context from documents
            conversation_history: Optional previous Q&A pairs

        Returns:
            Full prompt string for Gemini
        """
        # Add current date/time context
        from datetime import datetime
        now = datetime.now()
        date_context = f"""
ТЕКОВЕН ДАТУМ И ВРЕМЕ: {now.strftime('%d.%m.%Y %H:%M')} (ден: {now.strftime('%A')})

Ова е важно за:
- Определување дали тендер е сè уште отворен (ако краен рок < денес = затворен)
- Колку време остава до краен рок
- Временски релевантни прашања
"""
        prompt_parts = [cls.SYSTEM_PROMPT, date_context, "\n\n"]

        # Add conversation history if provided (with token limit)
        if conversation_history:
            prompt_parts.append("Previous conversation:\n")
            history_tokens = 0
            max_history_tokens = 1000  # Limit history to ~1000 tokens

            # Process only last 3 turns, with token limit
            for turn in conversation_history[-3:]:
                q_text = turn.get('question', '')[:500]  # Truncate long questions
                a_text = turn.get('answer', '')[:1000]   # Truncate long answers

                # Approximate token count (4 chars per token)
                turn_tokens = (len(q_text) + len(a_text)) // 4

                if history_tokens + turn_tokens > max_history_tokens:
                    break

                prompt_parts.append(f"Q: {q_text}\n")
                prompt_parts.append(f"A: {a_text}\n\n")
                history_tokens += turn_tokens

        # Add current query with context
        prompt_parts.append("Контекст од документи за тендери:\n\n")
        prompt_parts.append(context)
        prompt_parts.append("\n\n---\n\n")
        prompt_parts.append(f"Прашање: {question}\n\n")
        prompt_parts.append(
            "Based on the context above, answer the user's question. "
            "BE SPECIFIC - use actual numbers, company names, and dates from the data. "
            "If asked about prices, extract and report the 'Проценета вредност' values. "
            "If asked about winners, report the 'Победник' names and their statistics from 'НАЈЧЕСТИ ПОБЕДНИЦИ'. "
            "Match the language of the user's question in your response."
        )

        return "".join(prompt_parts)


class PersonalizationScorer:
    """
    Score and re-rank search results based on user personalization

    Uses user preferences and behavior to boost relevant results.
    Uses shared connection pool to prevent connection exhaustion.
    """

    def __init__(self, database_url: str):
        # database_url kept for compatibility but we use shared pool
        self.database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        self._pool = None

    async def connect(self):
        """Get reference to shared connection pool"""
        if not self._pool:
            self._pool = await get_pool()

    async def close(self):
        """Release reference to pool (does not close shared pool)"""
        self._pool = None

    async def get_user_interests(self, user_id: str) -> Dict:
        """
        Get user interest vector from database

        Returns:
            User interest data including categories, keywords, etc.
        """
        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetchrow("""
                    SELECT
                        interest_vector,
                        top_categories,
                        top_keywords,
                        avg_tender_value,
                        preferred_entities
                    FROM user_interests
                    WHERE user_id = $1
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, user_id)

            if not result:
                return {}

            return {
                'interest_vector': result['interest_vector'] or {},
                'top_categories': result['top_categories'] or [],
                'top_keywords': result['top_keywords'] or [],
                'avg_tender_value': result['avg_tender_value'],
                'preferred_entities': result['preferred_entities'] or []
            }
        except Exception as e:
            logger.warning(f"Failed to get user interests: {e}")
            return {}

    def calculate_personalization_score(
        self,
        search_result: SearchResult,
        user_interests: Dict
    ) -> float:
        """
        Calculate personalization score for a search result

        Args:
            search_result: Search result to score
            user_interests: User interest data

        Returns:
            Personalization score (0-1)
        """
        if not user_interests:
            return 0.0

        score = 0.0
        weights_sum = 0.0

        # 1. Category match (weight: 0.4)
        category = search_result.chunk_metadata.get('tender_category')
        top_categories = user_interests.get('top_categories', [])

        if category and top_categories:
            if category in top_categories:
                category_index = top_categories.index(category)
                # Higher score for top categories
                category_score = 1.0 - (category_index / len(top_categories))
                score += category_score * 0.4
                weights_sum += 0.4

        # 2. Keyword match (weight: 0.3)
        chunk_text = search_result.chunk_text.lower()
        top_keywords = user_interests.get('top_keywords', [])

        if top_keywords:
            keyword_matches = sum(
                1 for keyword in top_keywords[:10]
                if keyword.lower() in chunk_text
            )
            keyword_score = keyword_matches / len(top_keywords[:10])
            score += keyword_score * 0.3
            weights_sum += 0.3

        # 3. Entity match (weight: 0.3)
        tender_title = search_result.chunk_metadata.get('tender_title', '')
        preferred_entities = user_interests.get('preferred_entities', [])

        if preferred_entities:
            entity_matches = sum(
                1 for entity in preferred_entities[:5]
                if entity.lower() in tender_title.lower()
            )
            entity_score = entity_matches / len(preferred_entities[:5])
            score += entity_score * 0.3
            weights_sum += 0.3

        # Normalize score
        if weights_sum > 0:
            return score / weights_sum
        return 0.0

    async def rerank_results(
        self,
        search_results: List[SearchResult],
        user_id: Optional[str],
        personalization_weight: float = 0.3
    ) -> List[SearchResult]:
        """
        Re-rank search results using personalization

        Args:
            search_results: Original search results
            user_id: User ID for personalization
            personalization_weight: Weight of personalization (0-1)

        Returns:
            Re-ranked search results
        """
        if not user_id or not search_results:
            return search_results

        # Get user interests
        user_interests = await self.get_user_interests(user_id)

        if not user_interests:
            logger.info(f"No personalization data for user {user_id}")
            return search_results

        # Calculate combined scores
        scored_results = []
        for result in search_results:
            # Original similarity score
            similarity_score = result.similarity

            # Personalization score
            personalization_score = self.calculate_personalization_score(
                result,
                user_interests
            )

            # Combined score
            combined_score = (
                similarity_score * (1 - personalization_weight) +
                personalization_score * personalization_weight
            )

            # Store personalization score in metadata
            result.chunk_metadata['personalization_score'] = personalization_score
            result.chunk_metadata['combined_score'] = combined_score

            scored_results.append((combined_score, result))

        # Sort by combined score
        scored_results.sort(key=lambda x: x[0], reverse=True)

        # Extract sorted results
        reranked = [result for _, result in scored_results]

        logger.info(
            f"Personalized re-ranking applied (weight={personalization_weight:.2f})"
        )

        return reranked


class RAGQueryPipeline:
    """
    Complete RAG query pipeline: search → retrieve → generate

    Orchestrates the full question-answering workflow
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        top_k: int = 5,
        max_context_tokens: int = 3000,
        enable_personalization: bool = True,
        personalization_weight: float = 0.3
    ):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL not set")

        self.gemini_api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set")

        # Use env vars for model names, with sensible defaults
        model = model or os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        fallback_model = fallback_model or os.getenv('GEMINI_FALLBACK_MODEL', 'gemini-2.0-flash')

        genai.configure(api_key=self.gemini_api_key)
        self.model = model
        self.fallback_model = fallback_model
        self.top_k = top_k
        self.max_context_tokens = max_context_tokens
        self.enable_personalization = enable_personalization
        self.personalization_weight = personalization_weight

        # Initialize components
        self.embedder = EmbeddingGenerator(api_key=self.gemini_api_key)
        self.vector_store = VectorStore(self.database_url)
        self.context_assembler = ContextAssembler()
        self.prompt_builder = PromptBuilder()
        self.personalization_scorer = PersonalizationScorer(self.database_url)

        # Initialize hybrid RAG engine for web research augmentation
        self.hybrid_engine = HybridRAGEngine(
            database_url=self.database_url,
            gemini_api_key=self.gemini_api_key
        )

    async def generate_answer(
        self,
        question: str,
        tender_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
        user_id: Optional[str] = None
    ) -> RAGAnswer:
        """
        Generate answer to question using RAG

        Args:
            question: User's question
            tender_id: Optional filter by specific tender
            conversation_history: Optional previous Q&A pairs
            user_id: Optional user ID for personalization

        Returns:
            RAGAnswer with answer and sources
        """
        logger.info(f"Processing RAG query: {question[:100]}...")

        # Connect to database
        await self.vector_store.connect()

        # Connect personalization scorer if enabled
        if self.enable_personalization and user_id:
            await self.personalization_scorer.connect()

        try:
            # 1. Generate query embedding
            logger.info("Generating query embedding...")
            query_vector = await self.embedder.generate_embedding(question)

            # 2. Search for similar chunks
            logger.info(f"Searching for top {self.top_k} similar chunks...")
            raw_results = await self.vector_store.similarity_search(
                query_vector=query_vector,
                limit=self.top_k,
                tender_id=tender_id
            )

            # Convert to SearchResult objects
            search_results = [
                SearchResult(
                    embed_id=str(r['embed_id']),
                    chunk_text=r['chunk_text'],
                    chunk_index=r['chunk_index'],
                    tender_id=r.get('tender_id'),
                    doc_id=r.get('doc_id'),
                    chunk_metadata=r.get('metadata', {}),
                    similarity=r['similarity']
                )
                for r in raw_results
            ]

            # 2.5. Apply personalization re-ranking if enabled
            if self.enable_personalization and user_id and search_results:
                logger.info("Applying personalization re-ranking...")
                search_results = await self.personalization_scorer.rerank_results(
                    search_results=search_results,
                    user_id=user_id,
                    personalization_weight=self.personalization_weight
                )

            # IMPORTANT: We only have ~279 embeddings but 2700+ tenders.
            # Vector search often returns irrelevant results (e.g., office supplies for IT query)
            # ALWAYS use SQL search for now until we have comprehensive embeddings
            logger.info("Using SQL search (more reliable with current embedding coverage)...")
            search_results, context = await self._fallback_sql_search(question, tender_id)

            if not search_results:
                logger.warning("No tenders found in database")
                return RAGAnswer(
                    question=question,
                    answer="Моментално немаме тендери во базата. Обидете се повторно кога ќе имаме повеќе тендери во системот.",
                    sources=[],
                    confidence='low',
                    generated_at=datetime.utcnow(),
                    model_used=self.model
                )

            # Use pre-built context from SQL search
            sources_used = search_results

            # Use hybrid approach: database + web research when appropriate
            # This provides Gemini-like comprehensive answers with market analysis
            logger.info(f"Using hybrid RAG approach (DB results: {len(search_results)})...")

            try:
                hybrid_result = await self.hybrid_engine.generate_hybrid_answer(
                    question=question,
                    db_context=context,
                    db_results_count=len(search_results),
                    cpv_codes=None  # Could extract from context if needed
                )

                answer_text = hybrid_result.get('answer', '')

                # Append recommendations if available
                recommendations = hybrid_result.get('recommendations', [])
                if recommendations:
                    answer_text += "\n\n### Препораки\n"
                    for i, rec in enumerate(recommendations[:5], 1):
                        answer_text += f"{i}. {rec}\n"

                # Note the data source (internal logging only, no user-facing message)
                data_coverage = hybrid_result.get('data_coverage', 'database_only')
                logger.info(f"Hybrid answer generated ({data_coverage})")

            except Exception as e:
                logger.warning(f"Hybrid approach failed: {e}, falling back to standard prompt...")
                # Fallback to standard prompt-based approach
                prompt = self.prompt_builder.build_query_prompt(
                    question=question,
                    context=context,
                    conversation_history=conversation_history
                )
                try:
                    answer_text = await self._generate_with_gemini(prompt, self.model)
                except Exception as e2:
                    logger.warning(f"Primary model failed: {e2}, trying fallback...")
                    answer_text = await self._generate_with_gemini(prompt, self.fallback_model)

            return RAGAnswer(
                question=question,
                answer=answer_text,
                sources=sources_used,
                confidence='medium',
                generated_at=datetime.utcnow(),
                model_used=self.model
            )

            # NOTE: Vector search code below is temporarily disabled
            # 3. Assemble context
            logger.info("Assembling context from search results...")
            context, sources_used = self.context_assembler.assemble_context(
                search_results,
                max_tokens=self.max_context_tokens
            )

            # 4. Build prompt
            prompt = self.prompt_builder.build_query_prompt(
                question=question,
                context=context,
                conversation_history=conversation_history
            )

            # 5. Generate answer with Gemini
            logger.info(f"Generating answer with {self.model}...")
            try:
                answer_text = await self._generate_with_gemini(prompt, self.model)
            except Exception as e:
                logger.warning(f"Primary model {self.model} failed: {e}, trying fallback...")
                answer_text = await self._generate_with_gemini(prompt, self.fallback_model)

            # 6. Determine confidence
            confidence = self.context_assembler.determine_confidence(sources_used)

            logger.info(
                f"✓ Answer generated: {len(answer_text)} chars, "
                f"{len(sources_used)} sources, confidence={confidence}"
            )

            return RAGAnswer(
                question=question,
                answer=answer_text,
                sources=sources_used,
                confidence=confidence,
                generated_at=datetime.utcnow(),
                model_used=self.model
            )

        finally:
            await self.vector_store.close()
            if self.enable_personalization:
                await self.personalization_scorer.close()

    async def _search_external_sources(self, search_terms: List[str], question: str) -> Tuple[List[dict], str]:
        """
        Search external sources (e-nabavki.gov.mk, e-pazar.mk) when database has no results.

        This fetches live data from the procurement portals to answer user questions.
        Returns tender data and formatted context.
        """
        import aiohttp
        import re

        results = []
        context_parts = []

        # Try e-nabavki.gov.mk search
        try:
            search_query = ' '.join(search_terms[:3])  # Use top 3 terms
            e_nabavki_url = f"https://e-nabavki.gov.mk/SearchTender.aspx"

            logger.info(f"Searching e-nabavki.gov.mk for: {search_query}")

            async with aiohttp.ClientSession() as session:
                # Search e-nabavki
                async with session.get(
                    e_nabavki_url,
                    params={'q': search_query},
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={'User-Agent': 'NabavkiData/1.0'}
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        # Extract tender information from HTML
                        # This is a simplified extraction - would need proper parsing
                        tender_matches = re.findall(
                            r'<a[^>]*href="[^"]*TenderID=(\d+)[^"]*"[^>]*>([^<]+)</a>',
                            html, re.IGNORECASE
                        )
                        for tender_id, title in tender_matches[:10]:
                            results.append({
                                'source': 'e-nabavki.gov.mk',
                                'tender_id': tender_id,
                                'title': title.strip(),
                                'url': f"https://e-nabavki.gov.mk/PublicAccess/ViewTender.aspx?TenderID={tender_id}"
                            })

                        if tender_matches:
                            context_parts.append(f"=== Резултати од e-nabavki.gov.mk за '{search_query}' ===\n")
                            for tender_id, title in tender_matches[:10]:
                                context_parts.append(f"- {title.strip()} (ID: {tender_id})\n")
                                context_parts.append(f"  Линк: https://e-nabavki.gov.mk/PublicAccess/ViewTender.aspx?TenderID={tender_id}\n")
        except Exception as e:
            logger.warning(f"Error searching e-nabavki: {e}")

        # Try e-pazar.mk search
        try:
            search_query = ' '.join(search_terms[:3])
            e_pazar_url = "https://e-pazar.mk/api/search"

            logger.info(f"Searching e-pazar.mk for: {search_query}")

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://e-pazar.mk/search?q={search_query}",
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={'User-Agent': 'NabavkiData/1.0'}
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        # Extract tender/item information
                        item_matches = re.findall(
                            r'<div[^>]*class="[^"]*item[^"]*"[^>]*>.*?<h\d[^>]*>([^<]+)</h\d>.*?цена[:\s]*([0-9,.]+)',
                            html, re.IGNORECASE | re.DOTALL
                        )
                        for title, price in item_matches[:10]:
                            results.append({
                                'source': 'e-pazar.mk',
                                'title': title.strip(),
                                'price': price.strip()
                            })

                        if item_matches:
                            context_parts.append(f"\n=== Резултати од e-pazar.mk за '{search_query}' ===\n")
                            for title, price in item_matches[:10]:
                                context_parts.append(f"- {title.strip()}: {price} МКД\n")
        except Exception as e:
            logger.warning(f"Error searching e-pazar: {e}")

        # If we found results, add guidance for the LLM
        if results:
            context_parts.append("\n=== НАПОМЕНА ===\n")
            context_parts.append("Горенаведените резултати се пронајдени на официјалните портали.\n")
            context_parts.append("За детални информации, корисникот треба да ги посети линковите.\n")
        else:
            # No results found anywhere - provide helpful response
            context_parts.append(f"\n=== ПРЕБАРУВАЊЕ: '{' '.join(search_terms[:5])}' ===\n")
            context_parts.append("Не се пронајдени тендери со овие термини во базата или на порталите.\n")
            context_parts.append("Можни причини:\n")
            context_parts.append("- Моментално нема активни тендери за овој производ\n")
            context_parts.append("- Обидете се со други термини или синоними\n")
            context_parts.append("- Проверете директно на e-nabavki.gov.mk или e-pazar.mk\n")

        return results, ''.join(context_parts)

    async def _generate_smart_search_terms(self, question: str) -> List[str]:
        """
        Use LLM to generate intelligent search terms from user question.

        The LLM will:
        - Translate terms to Macedonian (the database language)
        - Generate synonyms and related terms
        - Fix typos and understand intent
        - Provide product category terms

        Returns list of search terms optimized for database search.
        """
        import json

        prompt = f"""You are a search query optimizer for a Macedonian public procurement database.
The database contains tender TITLES in MACEDONIAN language.

User question: "{question}"

Your task: Generate search terms that will match TENDER TITLES in the database.

IMPORTANT RULES:
1. DO NOT include words like "тендер", "тендери", "набавка", "јавна" - these are NOT in tender titles
2. Generate PRODUCT/SERVICE names only
3. Include variations: singular/plural, abbreviations, English terms used in Macedonia
4. Be specific to the product category

Examples:
- "ИТ тендери" → ["компјутер", "софтвер", "хардвер", "информатичк", "ИТ опрема", "сервер", "лаптоп", "монитор", "принтер", "мрежа"]
- "surgical drapes" → ["хируршки чаршафи", "хируршки драперии", "стерилни чаршафи", "операциски"]
- "toner" → ["тонер", "касета", "картриџ", "печатач", "принтер"]
- "medical supplies" → ["медицински материјал", "медицинска опрема", "санитетски", "здравствен"]
- "construction" → ["градежен", "градежни работи", "бетон", "цемент", "арматура", "градба"]
- "cleaning supplies" → ["средства за хигиена", "детергент", "чистење", "дезинфекција"]

Return ONLY a JSON array of 5-12 product/service terms (NO tender/nabavka words).
"""

        try:
            def _sync_generate():
                # Explicit BLOCK_NONE safety settings to avoid blocks
                model_obj = genai.GenerativeModel('gemini-2.0-flash')
                response = model_obj.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=200
                    ),
                    safety_settings=SAFETY_SETTINGS
                )
                try:
                    return response.text
                except ValueError:
                    return "[]"

            response_text = await asyncio.to_thread(_sync_generate)

            # Parse JSON array from response
            # Clean up response - remove markdown code blocks if present
            cleaned = response_text.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned.rsplit('```', 1)[0]
            cleaned = cleaned.strip()

            # Find JSON array in response
            import re
            json_match = re.search(r'\[.*\]', cleaned, re.DOTALL)
            if json_match:
                terms = json.loads(json_match.group())
                if isinstance(terms, list) and len(terms) > 0:
                    logger.info(f"LLM generated search terms: {terms}")
                    return terms[:15]

            logger.warning(f"Could not parse LLM search terms from: {response_text}")
            return []

        except Exception as e:
            logger.error(f"Error generating smart search terms: {e}")
            return []

    def _extract_basic_keywords(self, question: str) -> List[str]:
        """
        Basic keyword extraction as fallback.
        Extract meaningful words from the question.
        """
        import re

        # Stopwords to ignore
        stopwords = {
            'кој', 'која', 'кое', 'кои', 'што', 'каде', 'како', 'зошто', 'кога',
            'и', 'или', 'но', 'а', 'на', 'во', 'од', 'за', 'со', 'до', 'по', 'при',
            'дали', 'ли', 'да', 'не', 'е', 'се', 'има', 'имаат', 'беше', 'биде',
            'сите', 'овој', 'оваа', 'ова', 'овие', 'тој', 'таа', 'тоа', 'тие',
            'тендер', 'тендери', 'покажи', 'набавки', 'јавни', 'набавка',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'and', 'but', 'or', 'for', 'in', 'on', 'at', 'to', 'by', 'with',
            'who', 'what', 'where', 'when', 'why', 'how', 'which',
            'this', 'that', 'these', 'those', 'it', 'its',
            'want', 'need', 'looking', 'find', 'show', 'get',
        }

        # Extract all words 3+ characters
        words = re.findall(r'[а-яѓѕјљњќџА-ЯЃЅЈЉЊЌЏ]{3,}|[a-zA-Z]{3,}', question)

        keywords = []
        for word in words:
            word_lower = word.lower()
            if word_lower not in stopwords:
                keywords.append(word_lower)

        # Deduplicate
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)

        return unique[:10]

    def _is_item_level_query(self, question: str) -> bool:
        """
        Detect if query is asking about specific items/products rather than tenders.

        Returns:
            True if query is item-level (prices, specs, suppliers for specific products)
        """
        import re

        question_lower = question.lower()

        # Item-level query patterns
        ITEM_QUERY_PATTERNS = [
            r'price.*for\s+',
            r'prices.*for\s+',
            r'цена.*за\s+',
            r'цени.*за\s+',
            r'how much.*cost',
            r'what.*cost',
            r'колку чини',
            r'колку коштаат',
            r'who (sells|supplies|supplied|won)',
            r'кој (продава|испорачува|добил)',
            r'specification.*for',
            r'specifications.*for',
            r'specs.*for',
            r'технички.*барања',
            r'технички.*спецификации',
            r'спецификации.*за',
            # Medical/procurement product terms
            r'(surgical|медицински|хируршки)\s+(drapes|чаршафи|драперии|gloves|ракавици|masks|маски|equipment|опрема)',
            r'(медицински|хируршки|лабораториски|дентален)\s+',
            r'тонер|тонери|cartridge|касета|картриџ',
            r'канцелариски материјал',
            r'офис опрема',
            # Past price queries
            r'past prices',
            r'historical prices',
            r'price history',
            r'претходни цени',
            r'историја на цени',
            r'историски цени',
        ]

        for pattern in ITEM_QUERY_PATTERNS:
            if re.search(pattern, question_lower):
                logger.info(f"Item-level query detected: pattern '{pattern}' matched")
                return True

        return False

    async def _search_product_items(
        self,
        search_keywords: List[str],
        years: int = 3
    ) -> Tuple[List[Dict], str]:
        """
        Search product_items and epazar_items tables for item-level data.

        Args:
            search_keywords: Keywords to search for
            years: How many years of history to include (default: 3)

        Returns:
            (items_data, formatted_context)
        """
        pool = await get_pool()

        async with pool.acquire() as conn:
            keyword_patterns = [f'%{kw}%' for kw in search_keywords]

            # Search product_items table
            product_items = await conn.fetch(f"""
                SELECT
                    pi.id, pi.name, pi.quantity, pi.unit, pi.unit_price, pi.total_price,
                    pi.specifications, pi.cpv_code, pi.manufacturer, pi.model, pi.supplier,
                    t.tender_id, t.title as tender_title, t.procuring_entity,
                    t.status, t.publication_date, t.winner, t.actual_value_mkd
                FROM product_items pi
                JOIN tenders t ON pi.tender_id = t.tender_id
                WHERE (pi.name ILIKE ANY($1)
                   OR pi.name_mk ILIKE ANY($1)
                   OR pi.name_en ILIKE ANY($1)
                   OR pi.manufacturer ILIKE ANY($1)
                   OR pi.model ILIKE ANY($1)
                   OR pi.specifications::text ILIKE ANY($1))
                  AND t.publication_date >= NOW() - INTERVAL '{years} years'
                ORDER BY t.publication_date DESC NULLS LAST
                LIMIT 100
            """, keyword_patterns)

            # Search epazar_items table
            epazar_items = await conn.fetch(f"""
                SELECT
                    ei.item_id, ei.item_name, ei.item_description, ei.quantity, ei.unit,
                    ei.estimated_unit_price_mkd, ei.estimated_total_price_mkd,
                    ei.cpv_code, ei.specifications,
                    et.tender_id, et.title as tender_title, et.contracting_authority as procuring_entity,
                    et.status, et.publication_date,
                    (SELECT supplier_name FROM epazar_offers
                     WHERE tender_id = et.tender_id AND is_winner = true LIMIT 1) as winner,
                    (SELECT total_bid_mkd FROM epazar_offers
                     WHERE tender_id = et.tender_id AND is_winner = true LIMIT 1) as winning_price
                FROM epazar_items ei
                JOIN epazar_tenders et ON ei.tender_id = et.tender_id
                WHERE (ei.item_name ILIKE ANY($1)
                   OR ei.item_description ILIKE ANY($1)
                   OR ei.specifications::text ILIKE ANY($1))
                  AND et.publication_date >= NOW() - INTERVAL '{years} years'
                ORDER BY et.publication_date DESC NULLS LAST
                LIMIT 100
            """, keyword_patterns)

            # Get item-level price statistics for product_items
            product_stats = await conn.fetch(f"""
                SELECT
                    pi.name,
                    EXTRACT(YEAR FROM t.publication_date)::INTEGER as year,
                    EXTRACT(QUARTER FROM t.publication_date)::INTEGER as quarter,
                    COUNT(*) as tender_count,
                    AVG(pi.unit_price) as avg_price,
                    MIN(pi.unit_price) as min_price,
                    MAX(pi.unit_price) as max_price,
                    SUM(pi.quantity) as total_quantity,
                    pi.unit,
                    array_agg(DISTINCT t.winner) FILTER (WHERE t.winner IS NOT NULL) as winners,
                    array_agg(DISTINCT t.procuring_entity) as buyers
                FROM product_items pi
                JOIN tenders t ON pi.tender_id = t.tender_id
                WHERE (pi.name ILIKE ANY($1)
                   OR pi.name_mk ILIKE ANY($1)
                   OR pi.name_en ILIKE ANY($1))
                  AND pi.unit_price IS NOT NULL
                  AND t.publication_date >= NOW() - INTERVAL '{years} years'
                GROUP BY pi.name, year, quarter, pi.unit
                ORDER BY year DESC, quarter DESC, pi.name
                LIMIT 50
            """, keyword_patterns)

            # Get item-level price statistics for epazar_items
            epazar_stats = await conn.fetch(f"""
                SELECT
                    ei.item_name,
                    EXTRACT(YEAR FROM et.publication_date)::INTEGER as year,
                    EXTRACT(QUARTER FROM et.publication_date)::INTEGER as quarter,
                    COUNT(*) as tender_count,
                    AVG(ei.estimated_unit_price_mkd) as avg_price,
                    MIN(ei.estimated_unit_price_mkd) as min_price,
                    MAX(ei.estimated_unit_price_mkd) as max_price,
                    SUM(ei.quantity) as total_quantity,
                    ei.unit,
                    array_agg(DISTINCT eo.supplier_name) FILTER (WHERE eo.is_winner = true) as winners,
                    array_agg(DISTINCT et.contracting_authority) as buyers
                FROM epazar_items ei
                JOIN epazar_tenders et ON ei.tender_id = et.tender_id
                LEFT JOIN epazar_offers eo ON ei.tender_id = eo.tender_id AND eo.is_winner = true
                WHERE (ei.item_name ILIKE ANY($1)
                   OR ei.item_description ILIKE ANY($1))
                  AND ei.estimated_unit_price_mkd IS NOT NULL
                  AND et.publication_date >= NOW() - INTERVAL '{years} years'
                GROUP BY ei.item_name, year, quarter, ei.unit
                ORDER BY year DESC, quarter DESC, ei.item_name
                LIMIT 50
            """, keyword_patterns)

            # Get top suppliers for these items
            top_suppliers_product = await conn.fetch(f"""
                SELECT
                    t.winner,
                    COUNT(*) as wins,
                    AVG(pi.unit_price) as avg_unit_price,
                    SUM(pi.total_price) as total_contract_value,
                    array_agg(DISTINCT pi.name) as items_supplied
                FROM product_items pi
                JOIN tenders t ON pi.tender_id = t.tender_id
                WHERE (pi.name ILIKE ANY($1)
                   OR pi.name_mk ILIKE ANY($1))
                  AND t.winner IS NOT NULL AND t.winner != ''
                  AND t.publication_date >= NOW() - INTERVAL '{years} years'
                GROUP BY t.winner
                ORDER BY COUNT(*) DESC, AVG(pi.unit_price) ASC
                LIMIT 10
            """, keyword_patterns)

            top_suppliers_epazar = await conn.fetch(f"""
                SELECT
                    eo.supplier_name as winner,
                    COUNT(*) as wins,
                    AVG(ei.estimated_unit_price_mkd) as avg_unit_price,
                    SUM(eo.total_bid_mkd) as total_contract_value,
                    array_agg(DISTINCT ei.item_name) as items_supplied
                FROM epazar_items ei
                JOIN epazar_tenders et ON ei.tender_id = et.tender_id
                JOIN epazar_offers eo ON et.tender_id = eo.tender_id AND eo.is_winner = true
                WHERE (ei.item_name ILIKE ANY($1)
                   OR ei.item_description ILIKE ANY($1))
                  AND et.publication_date >= NOW() - INTERVAL '{years} years'
                GROUP BY eo.supplier_name
                ORDER BY COUNT(*) DESC, AVG(ei.estimated_unit_price_mkd) ASC
                LIMIT 10
            """, keyword_patterns)

        # Format context
        context_parts = []

        if not product_items and not epazar_items:
            context_parts.append(f"=== ПРЕБАРУВАЊЕ ПО АРТИКЛИ ===\n")
            context_parts.append(f"Барани термини: {', '.join(search_keywords)}\n\n")
            context_parts.append("Не се пронајдени артикли кои одговараат на барањето.\n")
            return [], ''.join(context_parts)

        # Add price statistics
        if product_stats or epazar_stats:
            context_parts.append("=== ИСТОРИЈА НА ЦЕНИ (ПО ПРОИЗВОД/АРТИКЛ) ===\n\n")

            # Group by item name
            all_stats = {}
            for stat in list(product_stats) + list(epazar_stats):
                item_name = stat.get('item_name') or stat.get('name')
                if item_name not in all_stats:
                    all_stats[item_name] = []
                all_stats[item_name].append(stat)

            for item_name, stats_list in all_stats.items():
                context_parts.append(f"**{item_name}**\n")

                # Group by year
                by_year = {}
                for stat in stats_list:
                    year = stat['year']
                    if year not in by_year:
                        by_year[year] = []
                    by_year[year].append(stat)

                for year in sorted(by_year.keys(), reverse=True):
                    year_stats = by_year[year]
                    total_tenders = sum(s['tender_count'] for s in year_stats)
                    avg_price = sum(s['avg_price'] * s['tender_count'] for s in year_stats if s['avg_price']) / total_tenders if total_tenders else 0
                    min_price = min((s['min_price'] for s in year_stats if s['min_price']), default=0)
                    max_price = max((s['max_price'] for s in year_stats if s['max_price']), default=0)
                    unit = year_stats[0].get('unit', '')

                    if avg_price > 0:
                        context_parts.append(
                            f"  {year}: Просечна цена {avg_price:,.2f} МКД/{unit} "
                            f"(опсег: {min_price:,.2f} - {max_price:,.2f}, {total_tenders} тендери)\n"
                        )

                context_parts.append("\n")

        # Add top suppliers
        if top_suppliers_product or top_suppliers_epazar:
            context_parts.append("=== НАЈЧЕСТИ ДОБАВУВАЧИ (ПО АРТИКЛ) ===\n\n")

            all_suppliers = {}
            for supplier in list(top_suppliers_product) + list(top_suppliers_epazar):
                name = supplier['winner']
                if name not in all_suppliers:
                    all_suppliers[name] = {
                        'wins': 0,
                        'avg_price': [],
                        'total_value': 0,
                        'items': set()
                    }
                all_suppliers[name]['wins'] += supplier['wins']
                if supplier.get('avg_unit_price'):
                    all_suppliers[name]['avg_price'].append(supplier['avg_unit_price'])
                if supplier.get('total_contract_value'):
                    all_suppliers[name]['total_value'] += supplier['total_contract_value']
                if supplier.get('items_supplied'):
                    all_suppliers[name]['items'].update(supplier['items_supplied'])

            # Sort by wins
            sorted_suppliers = sorted(all_suppliers.items(), key=lambda x: x[1]['wins'], reverse=True)[:10]

            for i, (name, data) in enumerate(sorted_suppliers, 1):
                avg_price = sum(data['avg_price']) / len(data['avg_price']) if data['avg_price'] else 0
                context_parts.append(
                    f"{i}. {name}: {data['wins']} победи, "
                    f"просечна цена {avg_price:,.2f} МКД"
                )
                if data['total_value'] > 0:
                    context_parts.append(f", вкупна вредност {data['total_value']:,.0f} МКД")
                context_parts.append("\n")

        # Add individual items
        context_parts.append("\n=== ПРОИЗВОДИ / АРТИКЛИ (Детали) ===\n\n")

        for i, item in enumerate(list(product_items)[:30] + list(epazar_items)[:30], 1):
            item_name = item.get('item_name') or item.get('name')
            unit_price = item.get('unit_price') or item.get('estimated_unit_price_mkd')
            total_price = item.get('total_price') or item.get('estimated_total_price_mkd')

            context_parts.append(f"**Артикл {i}: {item_name}**\n")
            context_parts.append(f"Количина: {item.get('quantity', 'N/A')} {item.get('unit', '')}\n")
            if unit_price:
                context_parts.append(f"Единечна цена: {unit_price:,.2f} МКД\n")
            if total_price:
                context_parts.append(f"Вкупна цена: {total_price:,.2f} МКД\n")
            context_parts.append(f"Тендер: {item.get('tender_title', 'N/A')} ({item['tender_id']})\n")
            context_parts.append(f"Набавувач: {item.get('procuring_entity', 'N/A')}\n")
            context_parts.append(f"Датум: {item.get('publication_date', 'N/A')}\n")
            if item.get('winner'):
                context_parts.append(f"Победник: {item['winner']}\n")

            # Add specifications if available
            specs = item.get('specifications')
            if specs:
                context_parts.append(f"Спецификации: {specs}\n")

            if item.get('manufacturer'):
                context_parts.append(f"Производител: {item['manufacturer']}\n")
            if item.get('model'):
                context_parts.append(f"Модел: {item['model']}\n")

            context_parts.append("\n")

        context = ''.join(context_parts)

        # Convert items to dict format for return
        items_data = [dict(item) for item in list(product_items) + list(epazar_items)]

        logger.info(f"Found {len(items_data)} product items matching keywords")

        return items_data, context

    async def _fallback_sql_search(
        self,
        question: str,
        tender_id: Optional[str] = None
    ) -> Tuple[List[SearchResult], str]:
        """
        Fallback: Query tenders AND epazar tables directly when no embeddings exist.

        This uses LLM to generate smart search terms (translations, synonyms, related terms)
        then searches both tenders and epazar_items tables for comprehensive results.
        Returns tender data formatted as context for Gemini.
        Uses shared connection pool to prevent connection exhaustion.
        """
        # Get shared pool instead of creating new one each time
        pool = await get_pool()

        async with pool.acquire() as conn:
            # Use LLM to generate smart search terms (translations, synonyms, etc.)
            search_keywords = await self._generate_smart_search_terms(question)

            # Fallback to basic extraction if LLM fails
            if not search_keywords:
                search_keywords = self._extract_basic_keywords(question)
                logger.info(f"Using basic keywords: {search_keywords}")

            # Check if this is an item-level query (prices, specs for specific products)
            is_item_query = self._is_item_level_query(question)

            if is_item_query and search_keywords:
                logger.info(f"Detected item-level query, searching product_items and epazar_items tables...")
                items_data, items_context = await self._search_product_items(search_keywords)

                if items_data:
                    # Create SearchResult objects from items
                    search_results = []
                    for i, item in enumerate(items_data[:20]):  # Limit to 20 for context
                        tender_id_val = item.get('tender_id')
                        item_name = item.get('item_name') or item.get('name')

                        search_results.append(SearchResult(
                            embed_id=f"item-{i}",
                            chunk_text=f"Item: {item_name}",
                            chunk_index=i,
                            tender_id=tender_id_val,
                            doc_id=None,
                            chunk_metadata={
                                'source': 'product_items',
                                'item_name': item_name,
                                'tender_title': item.get('tender_title', '')
                            },
                            similarity=0.95
                        ))

                    logger.info(f"Found {len(items_data)} items, returning item-level context")
                    return search_results, items_context
                else:
                    logger.info("No items found, falling back to tender-level search")
                    # Fall through to tender-level search

            # Query recent tenders (limit to 20 for context size)
            if tender_id:
                # Check if it's an e-pazar tender (starts with EPAZAR-)
                if tender_id.startswith('EPAZAR-'):
                    rows = await conn.fetch("""
                        SELECT tender_id, title, description, category, contracting_authority as procuring_entity,
                               estimated_value_mkd, estimated_value_eur, status,
                               publication_date, closing_date, procedure_type,
                               (SELECT supplier_name FROM epazar_offers WHERE tender_id = et.tender_id AND is_winner = true LIMIT 1) as winner
                        FROM epazar_tenders et
                        WHERE tender_id = $1
                        LIMIT 1
                    """, tender_id)

                    # Also get items for this e-pazar tender
                    items = await conn.fetch("""
                        SELECT item_name, item_description, quantity, unit,
                               estimated_unit_price_mkd, estimated_total_price_mkd
                        FROM epazar_items
                        WHERE tender_id = $1
                        ORDER BY line_number
                        LIMIT 50
                    """, tender_id)

                    # Get offers for this e-pazar tender
                    offers = await conn.fetch("""
                        SELECT supplier_name, total_bid_mkd, is_winner, ranking
                        FROM epazar_offers
                        WHERE tender_id = $1
                        ORDER BY ranking NULLS LAST, total_bid_mkd ASC
                        LIMIT 20
                    """, tender_id)
                else:
                    # Regular e-nabavki tender
                    rows = await conn.fetch("""
                        SELECT tender_id, title, description, category, procuring_entity,
                               estimated_value_mkd, estimated_value_eur, status,
                               publication_date, closing_date, procedure_type, winner,
                               cpv_code, num_bidders, evaluation_method, award_criteria,
                               contact_person, contact_email, contact_phone
                        FROM tenders
                        WHERE tender_id = $1
                        LIMIT 1
                    """, tender_id)

                    # Fetch documents for this tender
                    docs = await conn.fetch("""
                        SELECT doc_id, file_name, file_url, content_text as extracted_text
                        FROM documents
                        WHERE tender_id = $1
                        ORDER BY uploaded_at DESC NULLS LAST
                        LIMIT 10
                    """, tender_id)

                    # Fetch bidders for this tender
                    bidders = await conn.fetch("""
                        SELECT company_name as bidder_name, bid_amount_mkd, is_winner, rank as ranking,
                               disqualified, disqualification_reason
                        FROM tender_bidders
                        WHERE tender_id = $1
                        ORDER BY ranking NULLS LAST, bid_amount_mkd ASC
                        LIMIT 20
                    """, tender_id)

                    # Fetch lots if any
                    lots = await conn.fetch("""
                        SELECT lot_number, lot_title, lot_description,
                               estimated_value_mkd, winner, actual_value_mkd
                        FROM tender_lots
                        WHERE tender_id = $1
                        ORDER BY lot_number
                        LIMIT 20
                    """, tender_id)

                    items = []
                    offers = []
            else:
                # Search tenders by keywords if available
                if search_keywords:
                    # Build keyword search patterns
                    keyword_patterns = [f'%{kw}%' for kw in search_keywords]

                    # Search tenders matching keywords - INCLUDE raw_data_json for bidder prices
                    rows = await conn.fetch("""
                        SELECT tender_id, title, description, category, procuring_entity,
                               estimated_value_mkd, estimated_value_eur,
                               actual_value_mkd, status,
                               publication_date, closing_date, procedure_type, winner,
                               raw_data_json->>'bidders_data' as bidders_data
                        FROM tenders
                        WHERE title ILIKE ANY($1)
                           OR description ILIKE ANY($1)
                           OR category ILIKE ANY($1)
                        ORDER BY
                            CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                            publication_date DESC NULLS LAST
                        LIMIT 25
                    """, keyword_patterns)

                    # Get detailed price history - actual winning bids for these items
                    price_history = await conn.fetch("""
                        SELECT title, winner, actual_value_mkd, estimated_value_mkd,
                               procuring_entity, publication_date,
                               raw_data_json->>'bidders_data' as bidders_data
                        FROM tenders
                        WHERE (title ILIKE ANY($1) OR description ILIKE ANY($1))
                          AND actual_value_mkd IS NOT NULL
                          AND actual_value_mkd > 0
                        ORDER BY publication_date DESC
                        LIMIT 30
                    """, keyword_patterns)

                    # Also get winners/bidders for these keywords to answer "who wins" questions
                    winner_stats = await conn.fetch("""
                        SELECT winner, COUNT(*) as wins,
                               SUM(actual_value_mkd) as total_value,
                               AVG(actual_value_mkd) as avg_value,
                               MIN(actual_value_mkd) as min_value,
                               MAX(actual_value_mkd) as max_value,
                               array_agg(DISTINCT title) as tender_titles
                        FROM tenders
                        WHERE (title ILIKE ANY($1) OR description ILIKE ANY($1))
                          AND winner IS NOT NULL AND winner != ''
                        GROUP BY winner
                        ORDER BY COUNT(*) DESC
                        LIMIT 10
                    """, keyword_patterns)
                else:
                    # No keywords - get recent tenders
                    rows = await conn.fetch("""
                        SELECT tender_id, title, description, category, procuring_entity,
                               estimated_value_mkd, estimated_value_eur, status,
                               publication_date, closing_date, procedure_type, winner
                        FROM tenders
                        ORDER BY publication_date DESC NULLS LAST, created_at DESC
                        LIMIT 15
                    """)
                    winner_stats = []

                # Also search e-pazar tenders (by keywords if available)
                if search_keywords:
                    epazar_rows = await conn.fetch("""
                        SELECT tender_id, title, description, category, contracting_authority as procuring_entity,
                               estimated_value_mkd, estimated_value_eur, status,
                               publication_date, closing_date, procedure_type,
                               (SELECT supplier_name FROM epazar_offers WHERE tender_id = et.tender_id AND is_winner = true LIMIT 1) as winner
                        FROM epazar_tenders et
                        WHERE title ILIKE ANY($1)
                           OR description ILIKE ANY($1)
                        ORDER BY
                            CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                            publication_date DESC NULLS LAST
                        LIMIT 15
                    """, keyword_patterns)
                else:
                    epazar_rows = await conn.fetch("""
                        SELECT tender_id, title, description, category, contracting_authority as procuring_entity,
                               estimated_value_mkd, estimated_value_eur, status,
                               publication_date, closing_date, procedure_type,
                               (SELECT supplier_name FROM epazar_offers WHERE tender_id = et.tender_id AND is_winner = true LIMIT 1) as winner
                        FROM epazar_tenders et
                        ORDER BY publication_date DESC NULLS LAST
                        LIMIT 10
                    """)

                # Search epazar_items by product name if keywords present
                items = []
                offers = []
                if search_keywords:
                    items = await conn.fetch("""
                        SELECT ei.tender_id, ei.item_name, ei.item_description, ei.quantity, ei.unit,
                               ei.estimated_unit_price_mkd, ei.estimated_total_price_mkd,
                               et.title as tender_title, et.contracting_authority
                        FROM epazar_items ei
                        JOIN epazar_tenders et ON ei.tender_id = et.tender_id
                        WHERE ei.item_name ILIKE ANY($1)
                           OR ei.item_description ILIKE ANY($1)
                        ORDER BY et.publication_date DESC NULLS LAST
                        LIMIT 30
                    """, [f'%{kw}%' for kw in search_keywords])

                    # Get offers for matching items
                    if items:
                        tender_ids = list(set(item['tender_id'] for item in items))[:10]
                        offers = await conn.fetch("""
                            SELECT tender_id, supplier_name, total_bid_mkd, is_winner, ranking
                            FROM epazar_offers
                            WHERE tender_id = ANY($1)
                            ORDER BY tender_id, ranking NULLS LAST
                        """, tender_ids)

                rows = list(rows) + list(epazar_rows)

            # If no results in database, search external sources (live portals)
            if not rows and not items:
                logger.info(f"No results in database for keywords: {search_keywords}. Searching external sources...")
                external_results, external_context = await self._search_external_sources(search_keywords, question)

                if external_results or external_context:
                    # Create a SearchResult for external sources
                    search_results = [SearchResult(
                        embed_id="external-search",
                        chunk_text=external_context,
                        chunk_index=0,
                        tender_id=None,
                        doc_id=None,
                        chunk_metadata={
                            'source': 'external_portals',
                            'search_terms': search_keywords
                        },
                        similarity=0.7
                    )]
                    return search_results, external_context
                else:
                    # Even external search found nothing - return helpful message
                    no_results_context = f"""
=== ПРЕБАРУВАЊЕ ===
Термини за пребарување: {', '.join(search_keywords)}

Не се пронајдени тендери за овие производи/услуги ниту во нашата база, ниту на официјалните портали.

Ова може да значи:
1. Моментално нема активни тендери за овој тип производ/услуга
2. Пробајте со други термини или синоними
3. Проверете директно на:
   - https://e-nabavki.gov.mk - Систем за електронски јавни набавки
   - https://e-pazar.mk - Електронски пазар за мали набавки

Совет: Ако барате специфичен производ, обидете се со поширока категорија (пр. наместо "HP тонер 85A" обидете се со "тонер" или "канцелариски материјали").
"""
                    search_results = [SearchResult(
                        embed_id="no-results",
                        chunk_text=no_results_context,
                        chunk_index=0,
                        tender_id=None,
                        doc_id=None,
                        chunk_metadata={'source': 'no_results', 'search_terms': search_keywords},
                        similarity=0.5
                    )]
                    return search_results, no_results_context

            # Build context from tender data
            context_parts = []
            search_results = []

            # Add product/items context first (most relevant for product searches)
            if items:
                items_text = "=== ПРОИЗВОДИ / АРТИКЛИ ОД Е-ПАЗАР ===\n\n"
                for i, item in enumerate(items):
                    item_tender_id = item.get('tender_id', 'N/A')
                    item_text = f"""Производ {i+1}: {item['item_name']}
Опис: {item.get('item_description') or 'N/A'}
Количина: {item.get('quantity') or 'N/A'} {item.get('unit') or ''}
Единечна цена: {item.get('estimated_unit_price_mkd') or 'N/A'} МКД
Вкупна цена: {item.get('estimated_total_price_mkd') or 'N/A'} МКД
Тендер: {item.get('tender_title') or item_tender_id}
Набавувач: {item.get('contracting_authority') or 'N/A'}
"""
                    items_text += item_text + "\n"

                    search_results.append(SearchResult(
                        embed_id=f"epazar-item-{i}",
                        chunk_text=item_text,
                        chunk_index=i,
                        tender_id=item_tender_id,
                        doc_id=None,
                        chunk_metadata={
                            'tender_title': item.get('tender_title', ''),
                            'item_name': item['item_name'],
                            'source': 'epazar_items'
                        },
                        similarity=0.95
                    ))

                context_parts.append(items_text)

            # Add offers context
            if offers:
                offers_by_tender = {}
                for offer in offers:
                    tid = offer.get('tender_id', 'unknown')
                    if tid not in offers_by_tender:
                        offers_by_tender[tid] = []
                    offers_by_tender[tid].append(offer)

                offers_text = "\n=== ПОНУДИ / ЦЕНИ ===\n\n"
                for tid, tender_offers in offers_by_tender.items():
                    offers_text += f"Тендер {tid}:\n"
                    for offer in tender_offers:
                        winner_badge = " ✓ ПОБЕДНИК" if offer.get('is_winner') else ""
                        offers_text += f"  - {offer['supplier_name']}: {offer.get('total_bid_mkd') or 'N/A'} МКД (Ранг: #{offer.get('ranking') or 'N/A'}){winner_badge}\n"
                    offers_text += "\n"

                context_parts.append(offers_text)

            # Add winner statistics if available (for "who wins" questions)
            try:
                if winner_stats and len(winner_stats) > 0:
                    winners_text = "\n=== НАЈЧЕСТИ ПОБЕДНИЦИ ===\n\n"
                    for ws in winner_stats:
                        winners_text += f"- {ws['winner']}: {ws['wins']} победи"
                        if ws.get('total_value'):
                            winners_text += f", вкупна вредност: {ws['total_value']:,.0f} МКД"
                        winners_text += "\n"
                    context_parts.append(winners_text)
            except NameError:
                pass  # winner_stats not defined

            # Add PRICE HISTORY section with actual winning bid amounts
            try:
                if price_history and len(price_history) > 0:
                    import json as json_module
                    price_text = "\n=== ИСТОРИЈА НА ЦЕНИ (РЕАЛНИ ПОНУДИ) ===\n\n"
                    for ph in price_history:
                        price_text += f"• {ph['title']}\n"
                        price_text += f"  Набавувач: {ph['procuring_entity']}\n"
                        price_text += f"  Проценета вредност: {ph['estimated_value_mkd']:,.0f} МКД\n" if ph.get('estimated_value_mkd') else ""
                        price_text += f"  ПОБЕДНИЧКА ПОНУДА: {ph['actual_value_mkd']:,.0f} МКД\n" if ph.get('actual_value_mkd') else ""
                        price_text += f"  Победник: {ph['winner']}\n"
                        price_text += f"  Датум: {ph['publication_date']}\n"

                        # Parse bidders data to show all bids
                        if ph.get('bidders_data'):
                            try:
                                ph_bidders = json_module.loads(ph['bidders_data'])
                                if ph_bidders and len(ph_bidders) > 1:
                                    price_text += f"  Сите понуди:\n"
                                    for pb in ph_bidders:
                                        status = "✓ победник" if pb.get('is_winner') else ""
                                        bid_amt = pb.get('bid_amount_mkd')
                                        bid_str = f"{bid_amt:,.0f}" if bid_amt else 'N/A'
                                        price_text += f"    - {pb.get('company_name', 'N/A')}: {bid_str} МКД {status}\n"
                            except:
                                pass
                        price_text += "\n"
                    context_parts.append(price_text)
            except NameError:
                pass  # price_history not defined

            # Add tender context
            for i, row in enumerate(rows):
                # Format tender info as text - include extra fields if available
                cpv_code = row.get('cpv_code') or 'N/A'
                num_bidders = row.get('num_bidders') or 'N/A'
                evaluation = row.get('evaluation_method') or 'N/A'
                contact = row.get('contact_person') or 'N/A'
                email = row.get('contact_email') or 'N/A'

                tender_text = f"""
Тендер: {row['title']}
ID: {row['tender_id']}
Категорија: {row['category'] or 'N/A'}
CPV код: {cpv_code}
Набавувач: {row['procuring_entity'] or 'N/A'}
Проценета вредност (МКД): {row['estimated_value_mkd'] or 'N/A'}
Проценета вредност (EUR): {row['estimated_value_eur'] or 'N/A'}
Статус: {row['status'] or 'N/A'}
Датум на објава: {row['publication_date'] or 'N/A'}
Краен рок: {row['closing_date'] or 'N/A'}
Тип на постапка: {row['procedure_type'] or 'N/A'}
Победник: {row['winner'] or 'Не е избран'}
Број на понудувачи: {num_bidders}
Метод на евалуација: {evaluation}
Контакт: {contact} ({email})
Опис: {row['description'] or 'Нема опис'}
""".strip()

                context_parts.append(f"[Тендер {i+1}]\n{tender_text}")

                # Create SearchResult for source attribution
                search_results.append(SearchResult(
                    embed_id=f"sql-{row['tender_id']}",
                    chunk_text=tender_text,
                    chunk_index=0,
                    tender_id=row['tender_id'],
                    doc_id=None,
                    chunk_metadata={
                        'tender_title': row['title'],
                        'tender_category': row['category'],
                        'source': 'sql_fallback'
                    },
                    similarity=0.9
                ))

            # Add documents context for regular tenders (if docs variable exists)
            if tender_id and not tender_id.startswith('EPAZAR-') and 'docs' in dir():
                pass  # docs is local, need different approach

            # Check if we have docs/bidders/lots from regular tender query
            try:
                if docs:
                    docs_text = "\n=== ДОКУМЕНТИ ===\n\n"
                    for doc in docs:
                        doc_name = doc.get('file_name', 'N/A')
                        extracted = doc.get('extracted_text', '')
                        if extracted:
                            # Limit extracted text to first 1000 chars
                            extracted = extracted[:1000] + "..." if len(extracted) > 1000 else extracted
                        docs_text += f"Документ: {doc_name}\n"
                        if extracted:
                            docs_text += f"Содржина: {extracted}\n"
                        docs_text += "\n"
                    context_parts.append(docs_text)
            except NameError:
                pass  # docs not defined (epazar or general search)

            try:
                if bidders:
                    bidders_text = "\n=== ПОНУДУВАЧИ / ПОНУДИ ===\n\n"
                    for bidder in bidders:
                        winner_badge = " ✓ ПОБЕДНИК" if bidder.get('is_winner') else ""
                        disq = f" (Дисквалификуван: {bidder['disqualification_reason']})" if bidder.get('disqualification_reason') else ""
                        bidders_text += f"- {bidder['bidder_name']}: {bidder.get('bid_amount_mkd') or 'N/A'} МКД (Ранг: #{bidder.get('ranking') or 'N/A'}){winner_badge}{disq}\n"
                    context_parts.append(bidders_text)
            except NameError:
                pass  # bidders not defined

            try:
                if lots:
                    lots_text = "\n=== ЛОТОВИ / ДЕЛОВИ ===\n\n"
                    for lot in lots:
                        lot_winner = f" - Победник: {lot['winner']}" if lot.get('winner') else ""
                        lots_text += f"Лот {lot['lot_number']}: {lot['lot_title']}\n"
                        if lot.get('lot_description'):
                            lots_text += f"  Опис: {lot['lot_description'][:200]}\n"
                        lots_text += f"  Вредност: {lot.get('estimated_value_mkd') or 'N/A'} МКД{lot_winner}\n\n"
                    context_parts.append(lots_text)
            except NameError:
                pass  # lots not defined

            context = "\n\n---\n\n".join(context_parts)
            logger.info(f"SQL fallback: Found {len(rows)} tenders, {len(items)} items, {len(offers)} offers")

            return search_results, context

    async def _generate_with_gemini(self, prompt: str, model: str) -> str:
        """
        Generate answer using Gemini model

        Args:
            prompt: Full prompt
            model: Model name

        Returns:
            Generated answer text
        """
        def _sync_generate():
            # Explicit BLOCK_NONE safety settings to avoid blocks
            model_obj = genai.GenerativeModel(model)
            response = model_obj.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=1000
                ),
                safety_settings=SAFETY_SETTINGS
            )

            try:
                text = response.text
                if not text or not text.strip():
                    logger.warning("Gemini returned empty response")
                    return "Нема доволно податоци за генерирање одговор."
                return text
            except ValueError as e:
                logger.warning(f"Error accessing response text: {e}")
                return "Не можам да генерирам одговор моментално. Обидете се повторно."

        answer_text = await asyncio.to_thread(_sync_generate)
        return answer_text

    async def batch_query(
        self,
        questions: List[str],
        tender_id: Optional[str] = None
    ) -> List[RAGAnswer]:
        """
        Process multiple questions

        Args:
            questions: List of questions
            tender_id: Optional filter by tender

        Returns:
            List of RAGAnswer objects
        """
        answers = []

        for question in questions:
            answer = await self.generate_answer(
                question=question,
                tender_id=tender_id
            )
            answers.append(answer)

        return answers


class ConversationManager:
    """
    Manages conversation history for contextual RAG queries

    Stores Q&A pairs and provides conversation context.
    Uses shared connection pool to prevent connection exhaustion.
    """

    def __init__(self, database_url: Optional[str] = None):
        database_url = database_url or os.getenv('DATABASE_URL')
        # database_url kept for compatibility but we use shared pool
        self.database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        self._pool = None

    async def connect(self):
        """Get reference to shared connection pool"""
        if not self._pool:
            self._pool = await get_pool()

    async def close(self):
        """Release reference to pool (does not close shared pool)"""
        self._pool = None

    async def save_interaction(
        self,
        user_id: str,
        question: str,
        answer: str,
        sources: List[SearchResult],
        confidence: str,
        model_used: str
    ) -> str:
        """
        Save user interaction to database

        Returns:
            interaction_id
        """
        sources_data = [
            {
                'embed_id': s.embed_id,
                'tender_id': s.tender_id,
                'doc_id': s.doc_id,
                'similarity': s.similarity
            }
            for s in sources
        ]

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO rag_conversations (
                    user_id, question, answer, sources,
                    confidence, model_used, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING conversation_id
            """,
                user_id,
                question,
                answer,
                sources_data,
                confidence,
                model_used,
                datetime.utcnow()
            )

        return str(result['conversation_id'])

    async def get_user_history(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get recent conversation history for user

        Returns:
            List of Q&A pairs
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT question, answer, created_at
                FROM rag_conversations
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, user_id, limit)

        history = [
            {
                'question': row['question'],
                'answer': row['answer'],
                'created_at': row['created_at']
            }
            for row in reversed(rows)  # Chronological order
        ]

        return history


# Convenience functions

async def ask_question(
    question: str,
    tender_id: Optional[str] = None
) -> RAGAnswer:
    """
    Quick function to ask a question

    Usage:
        answer = await ask_question("What is the budget for this tender?", "TENDER-123")
        print(answer.answer)
        print(f"Confidence: {answer.confidence}")
        for source in answer.sources:
            print(f"  - {source.tender_id}: {source.similarity:.2f}")
    """
    pipeline = RAGQueryPipeline()
    return await pipeline.generate_answer(question, tender_id)


async def search_tenders(
    query: str,
    top_k: int = 10
) -> List[SearchResult]:
    """
    Search tenders by semantic similarity

    Returns matching document chunks without generating answer

    Usage:
        results = await search_tenders("construction projects in Skopje")
        for result in results:
            print(f"{result.tender_id}: {result.similarity:.2f}")
            print(result.chunk_text[:200])
    """
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not set")

    embedder = EmbeddingGenerator()
    vector_store = VectorStore(database_url)

    await vector_store.connect()

    try:
        # Generate query embedding
        query_vector = await embedder.generate_embedding(query)

        # Search
        raw_results = await vector_store.similarity_search(
            query_vector=query_vector,
            limit=top_k
        )

        # Convert to SearchResult
        results = [
            SearchResult(
                embed_id=str(r['embed_id']),
                chunk_text=r['chunk_text'],
                chunk_index=r['chunk_index'],
                tender_id=r.get('tender_id'),
                doc_id=r.get('doc_id'),
                chunk_metadata=r.get('metadata', {}),
                similarity=r['similarity']
            )
            for r in raw_results
        ]

        return results

    finally:
        await vector_store.close()


# ============================================================================
# E-PAZAR AI SUMMARIZATION FUNCTIONS
# ============================================================================

async def generate_tender_summary(context: Dict) -> str:
    """
    Generate AI summary of e-Pazar tender including items and offers.

    Args:
        context: Dictionary containing tender data, items, and offers

    Returns:
        AI-generated summary in Macedonian
    """
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY not set")

    genai.configure(api_key=gemini_api_key)
    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

    # Build context text
    tender_info = f"""
Тендер: {context.get('tender_title', 'N/A')}
Договорен орган: {context.get('contracting_authority', 'N/A')}
Проценета вредност: {context.get('estimated_value', 'N/A')} МКД
Статус: {context.get('status', 'N/A')}
"""

    # Format items
    items_text = ""
    items = context.get('items', [])
    if items:
        items_text = "\n\nАртикли (BOQ):\n"
        for i, item in enumerate(items[:20], 1):  # Limit to 20 items
            name = item.get('name', 'N/A')
            qty = item.get('quantity', 'N/A')
            unit = item.get('unit', '')
            price = item.get('estimated_price', 'N/A')
            items_text += f"{i}. {name} - {qty} {unit} @ {price} МКД\n"

        if len(items) > 20:
            items_text += f"\n... и уште {len(items) - 20} артикли\n"

    # Format offers
    offers_text = ""
    offers = context.get('offers', [])
    if offers:
        offers_text = "\n\nПонуди:\n"
        for i, offer in enumerate(offers[:10], 1):
            supplier = offer.get('supplier', 'N/A')
            amount = offer.get('amount', 'N/A')
            is_winner = " (ПОБЕДНИК)" if offer.get('is_winner') else ""
            ranking = offer.get('ranking', '')
            rank_text = f" (Ранг: #{ranking})" if ranking else ""
            offers_text += f"{i}. {supplier}: {amount} МКД{rank_text}{is_winner}\n"

    # Format document content (new!)
    docs_text = ""
    documents = context.get('documents', [])
    if documents:
        docs_text = "\n\nСодржина од документи:\n"
        for doc in documents[:3]:  # Limit to 3 docs max
            file_name = doc.get('file_name', 'document')
            doc_type = doc.get('doc_type', 'document')
            content = doc.get('content', '')
            if content:
                # Truncate long content
                preview = content[:2000] if len(content) > 2000 else content
                docs_text += f"\n--- {file_name} ({doc_type}) ---\n{preview}\n"

    full_context = tender_info + items_text + offers_text + docs_text

    # Build prompt
    prompt = f"""Ти си експерт за јавни набавки во Македонија. Направи кратко резиме на следниот тендер од е-Пазар платформата.

Контекст:
{full_context}

Резимето треба да вклучува:
1. Краток опис на набавката (2-3 реченици)
2. Клучни артикли/производи што се бараат (ако ги има)
3. Анализа на понудите и конкуренцијата (ако има)
4. Важни детали од документите (ако се дадени)
5. Препораки за потенцијални понудувачи

Одговори на македонски јазик. Биди концизен и прецизен. Ако нема доволно информации, кажи што недостасува."""

    def _sync_generate():
        # Explicit BLOCK_NONE safety settings to avoid blocks
        model_obj = genai.GenerativeModel(model_name)
        response = model_obj.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=800
            ),
            safety_settings=SAFETY_SETTINGS
        )

        try:
            text = response.text
            if not text or not text.strip():
                return "Нема доволно информации за генерирање резиме."
            return text
        except ValueError as e:
            logger.warning(f"Error accessing response text: {e}")
            return "Не можам да генерирам резиме моментално."

    summary = await asyncio.to_thread(_sync_generate)
    return summary


async def generate_supplier_analysis(context: Dict) -> str:
    """
    Generate AI analysis of supplier performance based on their bidding history.

    Args:
        context: Dictionary containing supplier data and offers history

    Returns:
        AI-generated analysis in Macedonian
    """
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY not set")

    genai.configure(api_key=gemini_api_key)
    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

    # Build context text
    supplier_info = f"""
Компанија: {context.get('company_name', 'N/A')}
Вкупно понуди: {context.get('total_offers', 0)}
Вкупно победи: {context.get('total_wins', 0)}
Процент на успех: {context.get('win_rate', 0):.1f}%
Вкупна вредност на договори: {context.get('total_contract_value', 0)} МКД
Индустрии: {context.get('industries', 'N/A')}
"""

    # Format recent offers
    offers_text = ""
    offers_history = context.get('offers_history', [])
    if offers_history:
        offers_text = "\n\nПоследни понуди:\n"
        for i, offer in enumerate(offers_history[:15], 1):
            title = offer.get('tender_title', 'N/A')[:50]
            amount = offer.get('bid_amount', 'N/A')
            is_winner = " ✓" if offer.get('is_winner') else ""
            ranking = offer.get('ranking', '')
            rank_text = f" (#{ranking})" if ranking else ""
            offers_text += f"{i}. {title}... - {amount} МКД{rank_text}{is_winner}\n"

    full_context = supplier_info + offers_text

    # Build prompt
    prompt = f"""Ти си експерт за анализа на добавувачи во јавни набавки. Анализирај го следниот добавувач од е-Пазар платформата.

Контекст:
{full_context}

Анализата треба да вклучува:
1. Профил на компанијата и нејзината активност
2. Анализа на успешноста во тендерирање
3. Области/категории каде се најактивни
4. Трендови во понудувањето (ако може да се забележат)
5. Оценка на конкурентноста на понудите

Одговори на македонски јазик. Биди објективен и аналитичен."""

    def _sync_generate():
        # Explicit BLOCK_NONE safety settings to avoid blocks
        model_obj = genai.GenerativeModel(model_name)
        response = model_obj.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=800
            ),
            safety_settings=SAFETY_SETTINGS
        )

        try:
            text = response.text
            if not text or not text.strip():
                return "Нема доволно информации за генерирање анализа."
            return text
        except ValueError as e:
            logger.warning(f"Error accessing response text: {e}")
            return "Не можам да генерирам анализа моментално."

    analysis = await asyncio.to_thread(_sync_generate)
    return analysis

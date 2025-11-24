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

from embeddings import EmbeddingGenerator, VectorStore

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

Your role:
- Answer questions about tenders, procurement procedures, and related documents
- Use ONLY information from the provided context (source documents)
- Cite sources when making claims
- Be precise and factual
- Support both Macedonian and English questions
- If information is not in context, say so clearly

Guidelines:
- Quote relevant parts of documents when appropriate
- Mention tender IDs and document names
- Explain procurement terminology when needed
- Handle both Macedonian (Cyrillic) and English
- Be concise but thorough"""

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
        prompt_parts = [cls.SYSTEM_PROMPT, "\n\n"]

        # Add conversation history if provided
        if conversation_history:
            prompt_parts.append("Previous conversation:\n")
            for turn in conversation_history[-3:]:  # Last 3 turns only
                prompt_parts.append(f"Q: {turn['question']}\n")
                prompt_parts.append(f"A: {turn['answer']}\n\n")

        # Add current query with context
        prompt_parts.append("Context from tender documents:\n\n")
        prompt_parts.append(context)
        prompt_parts.append("\n\n---\n\n")
        prompt_parts.append(f"Question: {question}\n\n")
        prompt_parts.append(
            "Please answer the question based ONLY on the context provided above. "
            "If the answer is not in the context, say \"I don't have enough information "
            "to answer this question based on the available documents.\""
        )

        return "".join(prompt_parts)


class PersonalizationScorer:
    """
    Score and re-rank search results based on user personalization

    Uses user preferences and behavior to boost relevant results
    """

    def __init__(self, database_url: str):
        # Convert SQLAlchemy URL format to asyncpg format
        # asyncpg doesn't understand postgresql+asyncpg://
        self.database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        self.conn = None

    async def connect(self):
        """Establish database connection"""
        if not self.conn:
            self.conn = await asyncpg.connect(self.database_url)

    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def get_user_interests(self, user_id: str) -> Dict:
        """
        Get user interest vector from database

        Returns:
            User interest data including categories, keywords, etc.
        """
        try:
            result = await self.conn.fetchrow("""
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
        model: str = "gemini-1.5-flash",
        fallback_model: str = "gemini-1.5-pro",
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

            if not search_results:
                logger.warning("No relevant documents found")
                # Return message in Macedonian
                return RAGAnswer(
                    question=question,
                    answer="Моментално немаме документи во базата што можат да го одговорат вашето прашање. Обидете се повторно кога ќе имаме повеќе тендери во системот.",
                    sources=[],
                    confidence='low',
                    generated_at=datetime.utcnow(),
                    model_used=self.model
                )

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
            model_obj = genai.GenerativeModel(model)
            response = model_obj.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,  # Low temperature for factual answers
                    max_output_tokens=1000
                )
            )
            return response.text

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

    Stores Q&A pairs and provides conversation context
    """

    def __init__(self, database_url: Optional[str] = None):
        database_url = database_url or os.getenv('DATABASE_URL')
        # Convert SQLAlchemy URL format to asyncpg format
        # asyncpg doesn't understand postgresql+asyncpg://
        self.database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        self.conn = None

    async def connect(self):
        """Establish database connection"""
        if not self.conn:
            self.conn = await asyncpg.connect(self.database_url)

    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()
            self.conn = None

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

        result = await self.conn.fetchrow("""
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
        rows = await self.conn.fetch("""
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

"""
RAG Query Pipeline - Question Answering over Tender Documents

Features:
- Semantic search using embeddings
- Context retrieval from pgvector
- OpenAI GPT-4 for answer generation
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
import openai

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


@dataclass
class RAGAnswer:
    """RAG system answer with sources"""
    question: str
    answer: str
    sources: List[SearchResult]
    confidence: str  # 'high', 'medium', 'low'
    generated_at: datetime
    model_used: str


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
    ) -> List[Dict[str, str]]:
        """
        Build complete prompt for RAG query

        Args:
            question: User's question
            context: Retrieved context from documents
            conversation_history: Optional previous Q&A pairs

        Returns:
            Messages list for OpenAI chat API
        """
        messages = [
            {"role": "system", "content": cls.SYSTEM_PROMPT}
        ]

        # Add conversation history if provided
        if conversation_history:
            for turn in conversation_history[-3:]:  # Last 3 turns only
                messages.append({"role": "user", "content": turn["question"]})
                messages.append({"role": "assistant", "content": turn["answer"]})

        # Add current query with context
        user_message = f"""Context from tender documents:

{context}

---

Question: {question}

Please answer the question based ONLY on the context provided above. If the answer is not in the context, say "I don't have enough information to answer this question based on the available documents." """

        messages.append({"role": "user", "content": user_message})

        return messages


class RAGQueryPipeline:
    """
    Complete RAG query pipeline: search → retrieve → generate

    Orchestrates the full question-answering workflow
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4",
        top_k: int = 5,
        max_context_tokens: int = 3000
    ):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL not set")

        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set")

        openai.api_key = self.openai_api_key
        self.model = model
        self.top_k = top_k
        self.max_context_tokens = max_context_tokens

        # Initialize components
        self.embedder = EmbeddingGenerator(api_key=self.openai_api_key)
        self.vector_store = VectorStore(self.database_url)
        self.context_assembler = ContextAssembler()
        self.prompt_builder = PromptBuilder()

    async def generate_answer(
        self,
        question: str,
        tender_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> RAGAnswer:
        """
        Generate answer to question using RAG

        Args:
            question: User's question
            tender_id: Optional filter by specific tender
            conversation_history: Optional previous Q&A pairs

        Returns:
            RAGAnswer with answer and sources
        """
        logger.info(f"Processing RAG query: {question[:100]}...")

        # Connect to database
        await self.vector_store.connect()

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

            if not search_results:
                logger.warning("No relevant documents found")
                return RAGAnswer(
                    question=question,
                    answer="I couldn't find any relevant documents to answer this question.",
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
            messages = self.prompt_builder.build_query_prompt(
                question=question,
                context=context,
                conversation_history=conversation_history
            )

            # 5. Generate answer with OpenAI
            logger.info(f"Generating answer with {self.model}...")
            response = await asyncio.to_thread(
                openai.ChatCompletion.create,
                model=self.model,
                messages=messages,
                temperature=0.3,  # Low temperature for factual answers
                max_tokens=1000
            )

            answer_text = response['choices'][0]['message']['content']

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
        self.database_url = database_url or os.getenv('DATABASE_URL')
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
        # Note: This assumes a conversations table exists
        # Schema would need to be created separately

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

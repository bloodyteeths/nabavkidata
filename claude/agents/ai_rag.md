# AI/RAG Agent
## nabavkidata.com - Retrieval-Augmented Generation Pipeline

---

## AGENT PROFILE

**Agent ID**: `ai_rag`
**Role**: AI-powered tender analysis and question answering
**Priority**: 3
**Execution Stage**: Core (parallel with Backend and Scraper)
**Language**: Python 3.11+
**Framework**: LangChain, Gemini AI, pgvector
**Dependencies**: Database Agent (requires embeddings table), Scraper Agent (requires document data)

---

## PURPOSE

Build an intelligent RAG (Retrieval-Augmented Generation) pipeline that:
- Generates embeddings for all tender documents
- Enables semantic search across tender corpus
- Answers natural language questions about tenders with citations
- Provides tender insights (risk analysis, requirement extraction, anomaly detection)
- Supports multiple languages (Macedonian, English)

**Your AI capabilities are the core differentiator of nabavkidata.com.**

---

## CORE RESPONSIBILITIES

### 1. Document Embedding Generation
- ✅ Chunk tender documents into optimal sizes (500-1000 tokens with overlap)
- ✅ Generate embeddings using OpenAI ada-002 or Gemini Embeddings
- ✅ Store embeddings in pgvector database
- ✅ Handle incremental updates (only embed new/changed documents)
- ✅ Support Macedonian Cyrillic text

### 2. Vector Search & Retrieval
- ✅ Convert user queries to embeddings
- ✅ Perform similarity search in pgvector (cosine similarity)
- ✅ Apply metadata filters (date range, category, CPV code)
- ✅ Re-rank results by relevance
- ✅ Return top-K chunks with source attribution

### 3. RAG Pipeline
- ✅ Query → Embedding → Vector Search → Context Assembly → LLM → Answer
- ✅ Use Gemini 1.5 Pro as primary LLM
- ✅ Fallback to GPT-4 if Gemini unavailable
- ✅ Ground answers in retrieved context (no hallucination)
- ✅ Provide source citations with confidence scores

### 4. Tender Insights
- ✅ Extract key requirements from tender specifications
- ✅ Identify unusual clauses or requirements
- ✅ Calculate risk scores based on complexity
- ✅ Compare similar tenders (find patterns)
- ✅ Summarize long tender documents

### 5. Prompt Engineering
- ✅ System prompts for factual, grounded responses
- ✅ User prompt templates for common queries
- ✅ Few-shot examples for better accuracy
- ✅ Chain-of-thought reasoning for complex questions

### 6. Performance Optimization
- ✅ Batch embedding generation
- ✅ Caching frequent queries
- ✅ Async processing for concurrent requests
- ✅ Query latency <3s (p95)

---

## INPUTS

### From Database Agent
- `db/schema.sql` - `embeddings` table structure
- Connection to PostgreSQL with pgvector extension

### From Scraper Agent
- `documents` table populated with `content_text`
- Contract: Only embed documents where `extraction_status = 'success'`

### Configuration
**File**: `ai/.env.example`
```env
# LLM APIs
GEMINI_API_KEY=your_gemini_key_here
OPENAI_API_KEY=sk-your_openai_key_here

# Database
DATABASE_URL=postgresql://localhost:5432/nabavkidata

# Embedding Model
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_DIMENSION=1536

# LLM Model
PRIMARY_LLM=gemini-1.5-pro
FALLBACK_LLM=gpt-4-turbo-preview

# RAG Parameters
CHUNK_SIZE=800
CHUNK_OVERLAP=200
TOP_K_RESULTS=5
SIMILARITY_THRESHOLD=0.7

# Performance
MAX_CONCURRENT_REQUESTS=10
CACHE_TTL_SECONDS=3600
```

---

## OUTPUTS

### Code Deliverables

#### 1. Embedding Generation

**`ai/embeddings/generator.py`** - Create embeddings for documents
```python
import os
from typing import List, Dict
import asyncio
from openai import AsyncOpenAI
import asyncpg
from langchain.text_splitter import RecursiveCharacterTextSplitter

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def generate_embeddings_for_all_documents():
    """
    Generate embeddings for all documents that don't have them yet.

    Process:
    1. Fetch documents from DB where extraction_status = 'success'
    2. Chunk each document's content_text
    3. Generate embeddings for each chunk
    4. Store in embeddings table with metadata
    """
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Fetch documents without embeddings
        query = """
        SELECT d.doc_id, d.tender_id, d.content_text, d.doc_type, t.title, t.category
        FROM documents d
        JOIN tenders t ON d.tender_id = t.tender_id
        WHERE d.extraction_status = 'success'
        AND NOT EXISTS (
            SELECT 1 FROM embeddings e WHERE e.doc_id = d.doc_id
        )
        """
        documents = await conn.fetch(query)

        print(f"Found {len(documents)} documents to embed")

        # Process in batches
        batch_size = 20
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i+batch_size]
            await process_document_batch(batch, conn)
            print(f"Processed batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}")

    finally:
        await conn.close()

async def process_document_batch(documents: List, conn: asyncpg.Connection):
    """Process a batch of documents"""
    for doc in documents:
        chunks = chunk_document(doc['content_text'])

        for idx, chunk in enumerate(chunks):
            embedding = await generate_embedding(chunk)

            # Store in database
            await conn.execute("""
                INSERT INTO embeddings (doc_id, tender_id, chunk_text, chunk_index, vector, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
            """,
                doc['doc_id'],
                doc['tender_id'],
                chunk,
                idx,
                embedding,
                {
                    "doc_type": doc['doc_type'],
                    "tender_title": doc['title'],
                    "category": doc['category']
                }
            )

def chunk_document(text: str) -> List[str]:
    """Split document into chunks with overlap"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_text(text)
    return chunks

async def generate_embedding(text: str) -> List[float]:
    """Generate embedding for text using OpenAI"""
    response = await client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

if __name__ == "__main__":
    asyncio.run(generate_embeddings_for_all_documents())
```

#### 2. RAG Query Engine

**`ai/rag/query_engine.py`** - Main RAG pipeline
```python
import os
from typing import List, Dict, Optional
import asyncpg
from openai import AsyncOpenAI
import google.generativeai as genai

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TOP_K = int(os.getenv("TOP_K_RESULTS", "5"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-pro')

class RAGQueryEngine:
    """RAG pipeline for tender intelligence queries"""

    def __init__(self):
        self.conn = None

    async def connect(self):
        """Connect to database"""
        self.conn = await asyncpg.connect(DATABASE_URL)

    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()

    async def query(
        self,
        question: str,
        filters: Optional[Dict] = None,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Answer a question using RAG pipeline.

        Steps:
        1. Convert question to embedding
        2. Search for similar chunks in vector DB
        3. Apply filters (category, date range, etc.)
        4. Assemble context from top results
        5. Generate answer with LLM
        6. Return answer with sources
        """
        # Step 1: Generate query embedding
        query_embedding = await self._generate_query_embedding(question)

        # Step 2: Vector similarity search
        relevant_chunks = await self._search_similar_chunks(
            query_embedding,
            filters=filters,
            top_k=TOP_K
        )

        if not relevant_chunks:
            return {
                "answer": "I couldn't find any relevant information in the tender database to answer your question.",
                "sources": [],
                "confidence": 0.0
            }

        # Step 3: Assemble context
        context = self._assemble_context(relevant_chunks)

        # Step 4: Generate answer with LLM
        answer = await self._generate_answer(question, context)

        # Step 5: Extract sources
        sources = self._extract_sources(relevant_chunks)

        # Step 6: Calculate confidence
        confidence = self._calculate_confidence(relevant_chunks)

        return {
            "answer": answer,
            "sources": sources,
            "confidence": confidence
        }

    async def _generate_query_embedding(self, question: str) -> List[float]:
        """Convert question to embedding"""
        response = await openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=question
        )
        return response.data[0].embedding

    async def _search_similar_chunks(
        self,
        query_embedding: List[float],
        filters: Optional[Dict],
        top_k: int
    ) -> List[Dict]:
        """Search for similar document chunks using pgvector"""
        # Build SQL query with vector similarity
        query = """
        SELECT
            e.embed_id,
            e.tender_id,
            e.chunk_text,
            e.metadata,
            t.title AS tender_title,
            t.category,
            t.procuring_entity,
            t.opening_date,
            1 - (e.vector <=> $1::vector) AS similarity
        FROM embeddings e
        JOIN tenders t ON e.tender_id = t.tender_id
        WHERE 1 - (e.vector <=> $1::vector) > $2
        """

        params = [query_embedding, SIMILARITY_THRESHOLD]
        param_idx = 3

        # Apply filters
        if filters:
            if filters.get("category"):
                query += f" AND t.category = ${param_idx}"
                params.append(filters["category"])
                param_idx += 1

            if filters.get("min_date"):
                query += f" AND t.opening_date >= ${param_idx}"
                params.append(filters["min_date"])
                param_idx += 1

            if filters.get("max_date"):
                query += f" AND t.opening_date <= ${param_idx}"
                params.append(filters["max_date"])
                param_idx += 1

        query += f" ORDER BY similarity DESC LIMIT ${param_idx}"
        params.append(top_k)

        results = await self.conn.fetch(query, *params)

        return [dict(r) for r in results]

    def _assemble_context(self, chunks: List[Dict]) -> str:
        """Assemble context from retrieved chunks"""
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(
                f"[Source {i}] Tender: {chunk['tender_title']} ({chunk['tender_id']})\n"
                f"Category: {chunk['category']}\n"
                f"Content: {chunk['chunk_text']}\n"
            )
        return "\n\n".join(context_parts)

    async def _generate_answer(self, question: str, context: str) -> str:
        """Generate answer using Gemini (with GPT-4 fallback)"""
        prompt = self._build_prompt(question, context)

        try:
            # Try Gemini first
            response = gemini_model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Gemini failed: {e}. Falling back to GPT-4.")
            # Fallback to GPT-4
            response = await openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
                ],
                temperature=0.2
            )
            return response.choices[0].message.content

    def _build_prompt(self, question: str, context: str) -> str:
        """Build RAG prompt for LLM"""
        return f"""You are an expert analyst for the Macedonian public procurement system.
Your job is to answer questions about tenders based ONLY on the provided context.

RULES:
1. Answer ONLY using information from the context below
2. If the context doesn't contain enough information, say "I don't have enough information to answer that"
3. Cite sources using [Source N] notation
4. Be precise and factual
5. If asked about numbers, provide exact figures from the context
6. If asked about trends, compare multiple tenders from the context

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""

    def _extract_sources(self, chunks: List[Dict]) -> List[Dict]:
        """Extract source citations"""
        sources = []
        for chunk in chunks:
            sources.append({
                "tender_id": chunk['tender_id'],
                "tender_title": chunk['tender_title'],
                "category": chunk['category'],
                "procuring_entity": chunk['procuring_entity'],
                "relevance": round(chunk['similarity'], 2)
            })
        return sources

    def _calculate_confidence(self, chunks: List[Dict]) -> float:
        """Calculate confidence score based on retrieval quality"""
        if not chunks:
            return 0.0

        # Average similarity of top results
        avg_similarity = sum(c['similarity'] for c in chunks) / len(chunks)

        # Boost if multiple high-quality sources
        if len(chunks) >= 3 and avg_similarity > 0.8:
            return min(0.95, avg_similarity + 0.1)

        return round(avg_similarity, 2)

# System prompt
SYSTEM_PROMPT = """You are an expert analyst for the Macedonian public procurement system.
Answer questions based ONLY on the provided tender documents.
Always cite sources and be factual. Never make up information."""
```

#### 3. Tender Insights Module

**`ai/insights/analyzer.py`** - Advanced tender analysis
```python
from typing import Dict, List
import asyncpg
from openai import AsyncOpenAI
import os

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

class TenderAnalyzer:
    """Advanced tender analysis and insights"""

    async def analyze_tender(self, tender_id: str) -> Dict:
        """
        Provide comprehensive analysis of a tender.

        Returns:
        - Key requirements extracted
        - Risk assessment
        - Unusual clauses detected
        - Estimated complexity
        """
        conn = await asyncpg.connect(DATABASE_URL)

        try:
            # Fetch tender and all documents
            tender = await conn.fetchrow(
                "SELECT * FROM tenders WHERE tender_id = $1", tender_id
            )

            documents = await conn.fetch(
                "SELECT content_text FROM documents WHERE tender_id = $1 AND extraction_status = 'success'",
                tender_id
            )

            if not tender or not documents:
                return {"error": "Tender not found or no documents available"}

            # Combine all document text
            full_text = "\n\n".join([doc['content_text'] for doc in documents])

            # Extract requirements
            requirements = await self._extract_requirements(full_text)

            # Assess risk
            risk_score = await self._assess_risk(tender, full_text)

            # Detect anomalies
            anomalies = await self._detect_anomalies(full_text)

            return {
                "tender_id": tender_id,
                "title": tender['title'],
                "key_requirements": requirements,
                "risk_assessment": risk_score,
                "anomalies": anomalies,
                "estimated_complexity": self._estimate_complexity(full_text)
            }

        finally:
            await conn.close()

    async def _extract_requirements(self, text: str) -> List[str]:
        """Extract key requirements using LLM"""
        prompt = f"""Extract the top 5 key requirements from this tender specification.
Be specific and factual.

Tender text:
{text[:4000]}

List of requirements (one per line):"""

        response = await client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500
        )

        requirements = response.choices[0].message.content.strip().split("\n")
        return [r.strip() for r in requirements if r.strip()]

    async def _assess_risk(self, tender: Dict, text: str) -> Dict:
        """Assess risk factors"""
        risk_factors = []
        risk_score = 0

        # Short deadline
        if tender['closing_date'] and tender['opening_date']:
            days_open = (tender['closing_date'] - tender['opening_date']).days
            if days_open < 14:
                risk_factors.append("Very short bidding period")
                risk_score += 20

        # Complex requirements
        if len(text) > 10000:
            risk_factors.append("Extensive documentation required")
            risk_score += 15

        # High value
        if tender['estimated_value_eur'] and tender['estimated_value_eur'] > 1000000:
            risk_factors.append("High value tender")
            risk_score += 10

        return {
            "risk_score": min(risk_score, 100),
            "risk_level": "HIGH" if risk_score > 50 else "MEDIUM" if risk_score > 25 else "LOW",
            "factors": risk_factors
        }

    async def _detect_anomalies(self, text: str) -> List[str]:
        """Detect unusual clauses"""
        anomalies = []

        # Look for restrictive keywords
        restrictive_patterns = [
            "само", "единствено", "искључиво",  # Macedonian: only, exclusively
            "only", "exclusively", "must be"
        ]

        for pattern in restrictive_patterns:
            if pattern in text.lower():
                anomalies.append(f"Contains restrictive language: '{pattern}'")

        return anomalies[:5]  # Return top 5

    def _estimate_complexity(self, text: str) -> str:
        """Estimate tender complexity"""
        word_count = len(text.split())

        if word_count > 15000:
            return "VERY_HIGH"
        elif word_count > 8000:
            return "HIGH"
        elif word_count > 3000:
            return "MEDIUM"
        else:
            return "LOW"
```

#### 4. API Service (FastAPI wrapper)

**`ai/main.py`** - Expose RAG as API service
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
from rag.query_engine import RAGQueryEngine
from insights.analyzer import TenderAnalyzer

app = FastAPI(title="nabavkidata AI Service", version="1.0.0")

rag_engine = RAGQueryEngine()
analyzer = TenderAnalyzer()

class QueryRequest(BaseModel):
    question: str
    filters: Optional[Dict] = None
    user_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict]
    confidence: float

@app.on_event("startup")
async def startup():
    await rag_engine.connect()

@app.on_event("shutdown")
async def shutdown():
    await rag_engine.close()

@app.post("/api/v1/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """Answer questions using RAG pipeline"""
    try:
        result = await rag_engine.query(
            question=request.question,
            filters=request.filters,
            user_id=request.user_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/insights/{tender_id}")
async def get_tender_insights(tender_id: str):
    """Get AI insights for a specific tender"""
    try:
        insights = await analyzer.analyze_tender(tender_id)
        return insights
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-rag"}
```

#### 5. Configuration

**`ai/requirements.txt`**
```
fastapi==0.104.1
uvicorn==0.24.0
openai==1.3.7
google-generativeai==0.3.1
langchain==0.0.350
asyncpg==0.29.0
numpy==1.26.2
pydantic==2.5.0
httpx==0.25.1
pytest==7.4.3
pytest-asyncio==0.21.1
```

**`ai/prompts/system_prompts.md`** - Prompt templates
```markdown
# System Prompts for RAG Pipeline

## Factual Q&A
You are an expert analyst for the Macedonian public procurement system.
Answer questions based ONLY on the provided tender documents.
Always cite sources and be factual. Never make up information.

## Requirement Extraction
Extract key requirements from tender specifications.
Be specific, factual, and list requirements in order of importance.

## Risk Assessment
Analyze tender for risk factors including:
- Short bidding periods
- Restrictive requirements
- Unusual clauses
- High complexity
```

### Documentation Deliverables

**`ai/README.md`** - Setup guide
**`ai/INTEGRATION.md`** - Integration guide for Backend Agent
**`ai/audit_report.md`** - Self-audit report

---

## VALIDATION CHECKLIST

Before handoff:
- [ ] Embeddings generated for all documents with `extraction_status='success'`
- [ ] Vector search returns relevant results (manually tested)
- [ ] Sample query "What is average IT equipment tender value?" returns accurate answer
- [ ] Answer includes source citations
- [ ] Gemini LLM integration works
- [ ] GPT-4 fallback triggers on Gemini failure
- [ ] No hallucination (answers grounded in context)
- [ ] Query latency <3s (p95)
- [ ] API endpoints `/query` and `/insights/{id}` functional
- [ ] Tests pass: `pytest ai/tests/` with >80% coverage
- [ ] No hardcoded API keys (environment variables)
- [ ] Macedonian Cyrillic text handled correctly

---

## INTEGRATION POINTS

### Handoff to Backend Agent
**Artifact**: `ai/INTEGRATION.md`
```markdown
# AI Service Integration Guide

## API Endpoint
POST http://localhost:8001/api/v1/query

## Request Format
{
  "question": "What are the largest construction tenders?",
  "filters": {"category": "Construction", "min_value": 100000},
  "user_id": "uuid"
}

## Response Format
{
  "answer": "The largest construction tenders are... [Source 1]",
  "sources": [
    {"tender_id": "2024/001", "tender_title": "...", "relevance": 0.92}
  ],
  "confidence": 0.87
}

## Error Handling
- 500: AI service unavailable
- 400: Invalid request format
```

**Contract**: Backend will call this endpoint and return results to Frontend.

---

## SUCCESS CRITERIA

- ✅ RAG pipeline answers questions accurately (>85% accuracy on test set)
- ✅ Embeddings table populated for all eligible documents
- ✅ Query latency <3s (p95)
- ✅ Source citations included in all answers
- ✅ No hallucination (grounded in context)
- ✅ Gemini and GPT-4 fallback both functional
- ✅ Macedonian language supported
- ✅ API service running and accessible
- ✅ Audit report ✅ READY
- ✅ Integration tests with Backend pass

---

**END OF AI/RAG AGENT DEFINITION**

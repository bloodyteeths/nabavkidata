# AI/RAG System Guide

## Overview

Complete Retrieval-Augmented Generation (RAG) system for intelligent question answering over Macedonian tender documents.

**Features:**
- **Vector embeddings** (OpenAI ada-002, 1536 dimensions)
- **Semantic search** (pgvector cosine similarity)
- **Semantic text chunking** (Cyrillic-aware, sentence boundaries)
- **Context assembly** (deduplication, relevance ranking)
- **Answer generation** (GPT-4 with source attribution)
- **Macedonian language support** (Cyrillic text handling)
- **Conversation tracking** (database-backed history)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Question                            │
│                 "Колку е буџетот?"                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              RAGQueryPipeline (rag_query.py)                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Generate Query Embedding                                │
│     ┌────────────────────────────────────────────┐         │
│     │  EmbeddingGenerator                         │         │
│     │  - OpenAI ada-002                          │         │
│     │  - 1536-dimensional vector                 │         │
│     └────────────────────────────────────────────┘         │
│                     ↓                                       │
│  2. Semantic Search                                         │
│     ┌────────────────────────────────────────────┐         │
│     │  VectorStore (embeddings.py)               │         │
│     │  - pgvector cosine similarity              │         │
│     │  - SELECT ... ORDER BY vector <=> query    │         │
│     │  - Returns top K most similar chunks       │         │
│     └────────────────────────────────────────────┘         │
│                     ↓                                       │
│  3. Context Assembly                                        │
│     ┌────────────────────────────────────────────┐         │
│     │  ContextAssembler                          │         │
│     │  - Deduplicate overlapping chunks          │         │
│     │  - Sort by similarity                      │         │
│     │  - Limit to max tokens                     │         │
│     │  - Determine confidence                    │         │
│     └────────────────────────────────────────────┘         │
│                     ↓                                       │
│  4. Prompt Construction                                     │
│     ┌────────────────────────────────────────────┐         │
│     │  PromptBuilder                             │         │
│     │  - System prompt (procurement expert)      │         │
│     │  - Context from retrieved chunks           │         │
│     │  - User question                           │         │
│     │  - Conversation history (optional)         │         │
│     └────────────────────────────────────────────┘         │
│                     ↓                                       │
│  5. Answer Generation                                       │
│     ┌────────────────────────────────────────────┐         │
│     │  OpenAI GPT-4                              │         │
│     │  - Generate factual answer                 │         │
│     │  - Use ONLY provided context               │         │
│     │  - Cite sources                            │         │
│     └────────────────────────────────────────────┘         │
│                     ↓                                       │
└─────────────────────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                    RAGAnswer                                │
├─────────────────────────────────────────────────────────────┤
│  Answer: "Проценета вредност е 500.000 МКД без ДДВ."        │
│  Sources: [TENDER-001, DOC-456]                             │
│  Confidence: high (similarity: 0.95)                        │
│  Generated: 2024-11-22 10:15:00                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Files

### 1. embeddings.py (556 lines)

**Purpose**: Vector embeddings generation and storage

**Classes:**

**`TextChunker`** - Semantic text chunking
- `chunk_text()` - Split text into 500-token chunks with 50-token overlap
- `_break_at_sentence()` - Break at sentence boundaries (Macedonian-aware)
- `chunk_document()` - Chunk with tender_id/doc_id attachment

**`EmbeddingGenerator`** - OpenAI embeddings
- `generate_embedding()` - Single text embedding
- `generate_embeddings_batch()` - Batch processing (up to 100 texts)
- `embed_chunks()` - Process TextChunk objects

**`VectorStore`** - pgvector database operations
- `store_embedding()` - Insert single embedding
- `store_embeddings_batch()` - Efficient batch insert (transaction)
- `similarity_search()` - Cosine similarity search

**`EmbeddingsPipeline`** - Complete workflow orchestration
- `process_document()` - chunk → embed → store
- `process_documents_batch()` - Batch document processing

### 2. rag_query.py (555 lines)

**Purpose**: Question answering over tender documents

**Classes:**

**`ContextAssembler`** - Context assembly from search results
- `assemble_context()` - Deduplicate, sort, format chunks
- `determine_confidence()` - Calculate confidence from similarity scores

**`PromptBuilder`** - Prompt construction for GPT-4
- `build_query_prompt()` - System prompt + context + question
- Handles conversation history (last 3 turns)

**`RAGQueryPipeline`** - Complete RAG workflow
- `generate_answer()` - Main RAG query method
- `batch_query()` - Process multiple questions

**`ConversationManager`** - Conversation history tracking
- `save_interaction()` - Store Q&A in database
- `get_user_history()` - Retrieve user conversation history

### 3. requirements.txt

```
openai==0.28.1
tiktoken==0.5.1
asyncpg==0.29.0
pgvector==0.2.4
python-dotenv==1.0.0
```

### 4. tests/

- `test_embeddings.py` (452 lines) - Embeddings pipeline tests
- `test_rag_query.py` (616 lines) - RAG query tests
- `__init__.py` - Test package marker

---

## Database Schema

### embeddings Table

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE embeddings (
    embed_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vector vector(1536),  -- OpenAI ada-002 dimensions
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    tender_id VARCHAR(100),
    doc_id VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for similarity search
CREATE INDEX embeddings_vector_idx ON embeddings
USING ivfflat (vector vector_cosine_ops)
WITH (lists = 100);

-- Index for tender filtering
CREATE INDEX embeddings_tender_id_idx ON embeddings(tender_id);
```

### rag_conversations Table (Optional)

```sql
CREATE TABLE rag_conversations (
    conversation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources JSONB,  -- Array of source metadata
    confidence VARCHAR(20),  -- 'high', 'medium', 'low'
    model_used VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX rag_conversations_user_id_idx ON rag_conversations(user_id);
CREATE INDEX rag_conversations_created_at_idx ON rag_conversations(created_at DESC);
```

---

## Setup

### 1. Install Dependencies

```bash
cd ai
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/nabavkidata"
export OPENAI_API_KEY="sk-..."
```

Or create `.env` file:
```
DATABASE_URL=postgresql://user:pass@localhost:5432/nabavkidata
OPENAI_API_KEY=sk-...
```

### 3. Create Database Schema

```bash
psql $DATABASE_URL -f schema.sql
```

Or using Python:
```python
import asyncpg
import asyncio

async def create_schema():
    conn = await asyncpg.connect('postgresql://...')

    # Enable extensions
    await conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create table
    await conn.execute('''
        CREATE TABLE embeddings (
            embed_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            vector vector(1536),
            chunk_text TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            tender_id VARCHAR(100),
            doc_id VARCHAR(100),
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create index
    await conn.execute('''
        CREATE INDEX embeddings_vector_idx ON embeddings
        USING ivfflat (vector vector_cosine_ops)
        WITH (lists = 100)
    ''')

    await conn.close()

asyncio.run(create_schema())
```

### 4. Test Installation

```bash
python -c "import embeddings, rag_query; print('✓ Imports successful')"
```

---

## Usage

### Embedding Documents

**Single document:**

```python
import asyncio
from embeddings import embed_tender_document

async def main():
    text = """
    Јавен повик за набавка на канцелариски материјали.
    Референтен број: 2024-001-КАНЦ
    Проценета вредност: 500.000 МКД
    """

    embed_ids = await embed_tender_document(
        text=text,
        tender_id='TENDER-2024-001',
        doc_id='DOC-001'
    )

    print(f"Created {len(embed_ids)} embeddings")

asyncio.run(main())
```

**Batch processing:**

```python
from embeddings import EmbeddingsPipeline

async def embed_multiple_documents():
    pipeline = EmbeddingsPipeline()

    documents = [
        {
            'text': 'Document 1 text...',
            'tender_id': 'TENDER-001',
            'doc_id': 'DOC-001',
            'metadata': {'type': 'tender_notice'}
        },
        {
            'text': 'Document 2 text...',
            'tender_id': 'TENDER-002',
            'doc_id': 'DOC-002',
            'metadata': {'type': 'technical_spec'}
        }
    ]

    results = await pipeline.process_documents_batch(documents)

    for doc_id, embed_ids in results.items():
        print(f"{doc_id}: {len(embed_ids)} chunks embedded")

asyncio.run(embed_multiple_documents())
```

### Asking Questions

**Simple question:**

```python
from rag_query import ask_question

async def simple_question():
    answer = await ask_question("Колку е буџетот за оваа набавка?")

    print(f"Question: {answer.question}")
    print(f"Answer: {answer.answer}")
    print(f"Confidence: {answer.confidence}")
    print(f"\nSources ({len(answer.sources)}):")
    for i, source in enumerate(answer.sources, 1):
        print(f"  {i}. {source.tender_id} (similarity: {source.similarity:.2f})")

asyncio.run(simple_question())
```

**Output:**
```
Question: Колку е буџетот за оваа набавка?
Answer: Проценета вредност на набавката е 500.000 МКД без ДДВ.
Confidence: high

Sources (3):
  1. TENDER-2024-001 (similarity: 0.95)
  2. TENDER-2024-001 (similarity: 0.87)
  3. TENDER-2024-001 (similarity: 0.82)
```

**Question about specific tender:**

```python
from rag_query import ask_question

async def tender_specific_question():
    answer = await ask_question(
        question="Кој е нарачателот?",
        tender_id='TENDER-2024-001'  # Filter by tender
    )

    print(answer.answer)

asyncio.run(tender_specific_question())
```

**Advanced RAG pipeline:**

```python
from rag_query import RAGQueryPipeline

async def advanced_rag():
    pipeline = RAGQueryPipeline(
        model='gpt-4',
        top_k=10,  # Retrieve top 10 chunks
        max_context_tokens=3000
    )

    # First question
    answer1 = await pipeline.generate_answer(
        "What is the procurement subject?"
    )

    # Follow-up with conversation history
    history = [
        {
            'question': answer1.question,
            'answer': answer1.answer
        }
    ]

    answer2 = await pipeline.generate_answer(
        question="When is the deadline?",
        conversation_history=history
    )

    print(f"Q1: {answer1.question}")
    print(f"A1: {answer1.answer}\n")
    print(f"Q2: {answer2.question}")
    print(f"A2: {answer2.answer}")

asyncio.run(advanced_rag())
```

### Semantic Search (No Answer Generation)

```python
from rag_query import search_tenders

async def search_only():
    results = await search_tenders(
        query="градежни проекти во Скопје",
        top_k=10
    )

    for result in results:
        print(f"\nTender: {result.tender_id}")
        print(f"Similarity: {result.similarity:.2f}")
        print(f"Text: {result.chunk_text[:200]}...")

asyncio.run(search_only())
```

---

## How It Works

### 1. Text Chunking

**Challenge**: Long documents exceed LLM context limits

**Solution**: Semantic chunking with overlap

```python
from embeddings import TextChunker

chunker = TextChunker(
    chunk_size=500,      # tokens per chunk
    chunk_overlap=50     # token overlap between chunks
)

text = "Very long document text..."
chunks = chunker.chunk_text(text)

# Each chunk:
# - ~500 tokens
# - Breaks at sentence boundaries
# - 50-token overlap with next chunk (preserves context)
```

**Why overlap?**
- Prevents information loss at chunk boundaries
- Query might match content that spans chunks
- 50 tokens ≈ 1-2 sentences of overlap

**Cyrillic handling:**
- Uses tiktoken with proper encoding
- Recognizes Macedonian sentence endings (. ! ?)
- Preserves Cyrillic characters in chunks

### 2. Embedding Generation

**Challenge**: Convert text to searchable vectors

**Solution**: OpenAI ada-002 embeddings

```python
from embeddings import EmbeddingGenerator

generator = EmbeddingGenerator()

text = "Јавен повик за набавка"
vector = await generator.generate_embedding(text)

# vector = [0.123, -0.456, 0.789, ..., 0.321]  # 1536 dimensions
```

**Why ada-002?**
- Multilingual support (Macedonian ✓)
- 1536 dimensions (good semantic representation)
- Fast and cost-effective ($0.0001 per 1K tokens)
- State-of-the-art retrieval performance

**Batch processing:**
```python
# Efficient batch processing
texts = ["Text 1", "Text 2", ..., "Text 100"]
vectors = await generator.generate_embeddings_batch(texts)
# Single API call for all 100 texts
```

### 3. Vector Storage (pgvector)

**Challenge**: Store and search millions of vectors efficiently

**Solution**: PostgreSQL with pgvector extension

```sql
-- Store embedding
INSERT INTO embeddings (vector, chunk_text, tender_id)
VALUES ($1, $2, $3);

-- Similarity search (cosine distance)
SELECT chunk_text, 1 - (vector <=> $1::vector) as similarity
FROM embeddings
ORDER BY vector <=> $1::vector  -- <=> is cosine distance operator
LIMIT 5;
```

**Index for fast search:**
```sql
-- IVFFlat index (Inverted File with Flat compression)
CREATE INDEX embeddings_vector_idx ON embeddings
USING ivfflat (vector vector_cosine_ops)
WITH (lists = 100);
```

**Performance:**
- Without index: O(n) - scan all vectors
- With IVFFlat: O(log n) - approximate nearest neighbor search
- 1M vectors: ~50ms query time

### 4. Semantic Search

**Challenge**: Find relevant documents for query

**Solution**: Vector similarity search

```python
from embeddings import EmbeddingGenerator
from rag_query import VectorStore

# 1. Embed query
query = "Колку е буџетот?"
query_vector = await generator.generate_embedding(query)

# 2. Search similar vectors
results = await vector_store.similarity_search(
    query_vector=query_vector,
    limit=5
)

# Results sorted by similarity (highest first)
# result[0]['similarity'] = 0.95  (very relevant)
# result[1]['similarity'] = 0.87  (relevant)
# result[2]['similarity'] = 0.82  (somewhat relevant)
```

**Cosine similarity:**
- Range: 0.0 to 1.0
- 1.0 = identical vectors
- 0.0 = completely different
- Threshold: 0.7+ = relevant, 0.8+ = highly relevant

### 5. Context Assembly

**Challenge**: Combine multiple chunks into coherent context

**Solution**: Deduplication, ranking, token limiting

```python
from rag_query import ContextAssembler

# Retrieved chunks (may have duplicates/overlaps)
search_results = [...]  # List of SearchResult objects

context, sources = ContextAssembler.assemble_context(
    search_results,
    max_tokens=3000  # GPT-4 context limit
)

# context = formatted text for prompt
# sources = deduplicated, sorted chunks actually used
```

**Process:**
1. **Deduplicate**: Remove identical/overlapping chunks
2. **Sort**: Order by similarity (highest first)
3. **Limit**: Respect max_tokens limit
4. **Format**: Add source attribution headers

**Example context:**
```
[Source 1] Tender: TENDER-001, Document: DOC-001 (Similarity: 0.95)
Проценета вредност на набавката е 500.000 МКД без ДДВ.

---

[Source 2] Tender: TENDER-001, Document: DOC-001 (Similarity: 0.87)
Референтен број: 2024-001-КАНЦ. Рок за доставување понуди: 30.11.2024.
```

### 6. Prompt Construction

**Challenge**: Instruct GPT-4 to answer based only on context

**Solution**: Structured prompt with system role and instructions

```python
messages = [
    {
        "role": "system",
        "content": "You are an AI assistant specialized in Macedonian public procurement..."
    },
    {
        "role": "user",
        "content": f"""Context from tender documents:

{context}

---

Question: {question}

Please answer based ONLY on the context provided above."""
    }
]
```

**System prompt emphasizes:**
- Use ONLY provided context
- Cite sources when making claims
- Say "I don't know" if answer not in context
- Support Macedonian and English
- Be precise and factual

### 7. Answer Generation

**Challenge**: Generate accurate, grounded answer

**Solution**: GPT-4 with low temperature

```python
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=messages,
    temperature=0.3,  # Low = more factual, less creative
    max_tokens=1000
)

answer = response['choices'][0]['message']['content']
```

**Why GPT-4?**
- Better instruction following (stays grounded in context)
- Multilingual (Macedonian ✓)
- Better reasoning for complex questions
- More accurate citations

**Temperature 0.3:**
- Lower = more deterministic, factual
- Higher = more creative, varied
- 0.3 = good balance for RAG

### 8. Confidence Scoring

**Challenge**: Indicate answer reliability

**Solution**: Confidence based on similarity scores

```python
avg_similarity = sum(s.similarity for s in sources) / len(sources)

if avg_similarity >= 0.80:
    confidence = 'high'    # Strong match to documents
elif avg_similarity >= 0.60:
    confidence = 'medium'  # Moderate match
else:
    confidence = 'low'     # Weak match
```

**Usage:**
- High confidence → Trust answer
- Medium confidence → Verify with sources
- Low confidence → Answer might be speculative

---

## Configuration

### Chunking Parameters

```python
TextChunker(
    chunk_size=500,      # Tokens per chunk (default: 500)
    chunk_overlap=50,    # Overlap between chunks (default: 50)
    model="gpt-3.5-turbo"  # Model for tokenization
)
```

**Tuning:**
- **Smaller chunks** (200-300): Better precision, more API calls
- **Larger chunks** (700-1000): More context per chunk, risk of losing focus
- **More overlap** (100): Better context preservation, more storage
- **Less overlap** (20): Less redundancy, risk of missing boundary content

**Recommended**: 500/50 for general use

### Embedding Parameters

```python
EmbeddingGenerator(
    model="text-embedding-ada-002",  # OpenAI model
    batch_size=100                   # Max texts per API call
)
```

**Tuning:**
- **Batch size**: Max 100 (OpenAI limit), use smaller if hitting rate limits

### RAG Pipeline Parameters

```python
RAGQueryPipeline(
    model="gpt-4",              # Answer generation model
    top_k=5,                    # Number of chunks to retrieve
    max_context_tokens=3000     # Max tokens in context
)
```

**Tuning:**
- **top_k**:
  - Smaller (3): Faster, less context, focused answers
  - Larger (10-20): More context, better for complex questions
- **max_context_tokens**:
  - GPT-4: 8K context, leave room for question/answer (3000-4000 safe)
  - GPT-4-32K: Can use up to 20000
- **model**:
  - gpt-4: Best quality
  - gpt-3.5-turbo: Faster, cheaper, lower quality

---

## Performance

### Embedding Cost

**OpenAI ada-002 pricing**: $0.0001 per 1K tokens

**Example calculation:**
- 1000 tender documents
- Average 2000 words per document
- ~2500 tokens per document
- Total: 2.5M tokens
- **Cost: $0.25** to embed entire corpus

**Chunking impact:**
- 500-token chunks with 50 overlap → ~5-6 chunks per doc
- 1000 docs × 5.5 chunks = **5500 embeddings**
- Storage: 5500 × 1536 dims × 4 bytes = **34MB** vector data

### Query Cost

**Per query:**
- Embed query: ~20 tokens = $0.000002
- Generate answer (GPT-4): ~500 tokens = $0.015
- **Total per query: ~$0.015** (mostly GPT-4)

**Cost reduction:**
- Use gpt-3.5-turbo: $0.002 per query (7× cheaper)
- Cache frequent queries
- Limit max_tokens in answers

### Latency

**Typical query breakdown:**
- Embed query: ~200ms
- Vector search: ~50ms (with index)
- GPT-4 generation: ~2-4 seconds
- **Total: 2-5 seconds** per query

**Optimization:**
- Use gpt-3.5-turbo: ~1-2 sec (2× faster)
- Smaller top_k: Less context = faster generation
- Database connection pooling

### Scalability

**Vector search performance:**
- 10K embeddings: ~20ms
- 100K embeddings: ~40ms
- 1M embeddings: ~50ms
- 10M embeddings: ~100ms (with proper index tuning)

**Concurrent queries:**
- PostgreSQL handles 100+ concurrent searches
- OpenAI rate limits: 3500 requests/min (varies by account)
- Bottleneck: Usually OpenAI API, not database

---

## Best Practices

### 1. Document Preparation

**Clean text before embedding:**
```python
import re

def clean_tender_text(text):
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove boilerplate headers/footers
    text = re.sub(r'Page \d+ of \d+', '', text)

    # Normalize Macedonian characters
    text = text.strip()

    return text

# Use cleaned text
cleaned = clean_tender_text(raw_text)
embed_ids = await embed_tender_document(cleaned, tender_id, doc_id)
```

### 2. Metadata Usage

**Store useful metadata:**
```python
metadata = {
    'doc_type': 'tender_notice',        # Document type
    'published_date': '2024-11-22',     # When published
    'cpv_codes': ['30190000-7'],        # Procurement codes
    'contracting_authority': 'Општина Скопје',  # Who issued it
    'estimated_value': 500000           # Budget
}

await pipeline.process_document(
    text=text,
    tender_id=tender_id,
    metadata=metadata  # Stored in JSONB column
)
```

**Use metadata in search:**
```python
# Filter by metadata in custom query
SELECT * FROM embeddings
WHERE metadata->>'doc_type' = 'tender_notice'
  AND (metadata->>'estimated_value')::int > 100000
ORDER BY vector <=> $1::vector
LIMIT 10;
```

### 3. Error Handling

**Robust error handling:**
```python
from rag_query import RAGQueryPipeline

async def safe_query(question):
    pipeline = RAGQueryPipeline()

    try:
        answer = await pipeline.generate_answer(question)
        return answer

    except ValueError as e:
        # Missing API key or DATABASE_URL
        print(f"Configuration error: {e}")
        return None

    except Exception as e:
        # OpenAI API error, database error, etc.
        print(f"Query failed: {e}")
        return None

    finally:
        # Ensure cleanup
        await pipeline.vector_store.close()
```

### 4. Conversation Context

**Multi-turn conversations:**
```python
from rag_query import RAGQueryPipeline, ConversationManager

async def conversation_example():
    pipeline = RAGQueryPipeline()
    conv_manager = ConversationManager()
    await conv_manager.connect()

    user_id = 'user-123'

    # First question
    answer1 = await pipeline.generate_answer("Што е предметот на набавка?")

    # Save interaction
    await conv_manager.save_interaction(
        user_id=user_id,
        question=answer1.question,
        answer=answer1.answer,
        sources=answer1.sources,
        confidence=answer1.confidence,
        model_used=answer1.model_used
    )

    # Get history for follow-up
    history = await conv_manager.get_user_history(user_id, limit=5)

    # Follow-up question (uses history for context)
    answer2 = await pipeline.generate_answer(
        question="Кој е нарачателот?",
        conversation_history=history
    )

    await conv_manager.close()
```

### 5. Testing

**Test with real queries:**
```bash
cd ai
pytest tests/test_embeddings.py -v
pytest tests/test_rag_query.py -v

# Integration tests (require database + API key)
pytest tests/ -v -m integration
```

**Manual testing:**
```python
# Test embeddings
from embeddings import TextChunker

chunker = TextChunker()
chunks = chunker.chunk_text("Test document text...")
print(f"Created {len(chunks)} chunks")

# Test RAG
from rag_query import ask_question

answer = await ask_question("Test question?")
print(answer.answer)
```

---

## Troubleshooting

### No results from search

**Symptoms:**
```python
answer = await ask_question("My question?")
# answer.sources = []
# answer.answer = "I couldn't find any relevant documents..."
```

**Causes:**
1. No documents embedded yet
2. Query doesn't match embedded content
3. Similarity threshold too high

**Solutions:**
```python
# Check if embeddings exist
import asyncpg
conn = await asyncpg.connect(DATABASE_URL)
count = await conn.fetchval("SELECT COUNT(*) FROM embeddings")
print(f"Total embeddings: {count}")

# Test direct search
from rag_query import search_tenders
results = await search_tenders("broad query", top_k=20)
for r in results:
    print(f"{r.tender_id}: {r.similarity:.2f}")
```

### Low confidence answers

**Symptoms:**
```python
answer.confidence == 'low'
# Similarity scores < 0.6
```

**Causes:**
1. Question doesn't match document content
2. Documents not properly chunked
3. Poor embedding quality

**Solutions:**
- Rephrase question to match document language
- Check chunk size (might be too large/small)
- Verify document text is clean (no encoding issues)
- Increase top_k to retrieve more candidates

### OpenAI API errors

**Rate limit errors:**
```
openai.error.RateLimitError: Rate limit exceeded
```

**Solution:**
```python
import time
from openai.error import RateLimitError

async def embed_with_retry(text, max_retries=3):
    for i in range(max_retries):
        try:
            return await generator.generate_embedding(text)
        except RateLimitError:
            wait = 2 ** i  # Exponential backoff
            print(f"Rate limited, waiting {wait}s...")
            time.sleep(wait)
    raise Exception("Max retries exceeded")
```

### Database connection errors

**Symptoms:**
```
asyncpg.exceptions.ConnectionDoesNotExistError
```

**Solutions:**
```python
# Check DATABASE_URL
import os
print(os.getenv('DATABASE_URL'))

# Test connection
import asyncpg
conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
print("✓ Connected")
await conn.close()

# Check pgvector extension
result = await conn.fetchval("""
    SELECT EXISTS(
        SELECT 1 FROM pg_extension WHERE extname = 'vector'
    )
""")
print(f"pgvector installed: {result}")
```

---

## Summary

**Complete RAG system with:**

✅ **Vector embeddings** (OpenAI ada-002, 1536 dimensions)
✅ **Semantic chunking** (Cyrillic-aware, sentence boundaries)
✅ **pgvector storage** (efficient similarity search)
✅ **Context assembly** (deduplication, ranking, limiting)
✅ **Answer generation** (GPT-4 with source attribution)
✅ **Macedonian support** (full Cyrillic handling)
✅ **Conversation tracking** (database-backed history)
✅ **Comprehensive tests** (unit + integration tests)

**Performance:**
- Embedding cost: ~$0.25 per 1000 documents
- Query cost: ~$0.015 per query (GPT-4)
- Query latency: 2-5 seconds
- Scales to 10M+ embeddings

**Ready for production!**

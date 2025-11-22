# AI/RAG Module

Intelligent question answering over Macedonian tender documents using Retrieval-Augmented Generation (RAG).

## Quick Start

### Installation

```bash
cd ai
pip install -r requirements.txt
```

### Environment Setup

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/nabavkidata"
export OPENAI_API_KEY="sk-..."
```

### Basic Usage

**Embed documents:**
```python
import asyncio
from embeddings import embed_tender_document

async def main():
    text = "Јавен повик за набавка..."
    embed_ids = await embed_tender_document(
        text=text,
        tender_id='TENDER-123',
        doc_id='DOC-456'
    )
    print(f"Created {len(embed_ids)} embeddings")

asyncio.run(main())
```

**Ask questions:**
```python
from rag_query import ask_question

async def main():
    answer = await ask_question("Колку е буџетот?")
    print(f"Answer: {answer.answer}")
    print(f"Confidence: {answer.confidence}")

asyncio.run(main())
```

## Features

- ✅ **Vector Embeddings** - OpenAI ada-002 (1536 dimensions)
- ✅ **Semantic Search** - pgvector cosine similarity
- ✅ **Smart Chunking** - Cyrillic-aware, sentence boundaries
- ✅ **Context Assembly** - Deduplication, relevance ranking
- ✅ **Answer Generation** - GPT-4 with source citations
- ✅ **Macedonian Support** - Full Cyrillic text handling
- ✅ **Conversation History** - Multi-turn conversations

## Files

```
ai/
├── embeddings.py           # Vector embeddings pipeline (556 lines)
├── rag_query.py            # RAG question answering (555 lines)
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── RAG_GUIDE.md          # Comprehensive documentation (1300+ lines)
└── tests/
    ├── __init__.py
    ├── test_embeddings.py    # Embeddings tests (452 lines)
    └── test_rag_query.py     # RAG tests (616 lines)
```

## Architecture

```
User Question
     ↓
Generate Query Embedding (OpenAI ada-002)
     ↓
Semantic Search (pgvector)
     ↓
Assemble Context (deduplicate, rank)
     ↓
Build Prompt (system + context + question)
     ↓
Generate Answer (GPT-4)
     ↓
RAGAnswer (answer + sources + confidence)
```

## Database Schema

```sql
CREATE EXTENSION vector;

CREATE TABLE embeddings (
    embed_id UUID PRIMARY KEY,
    vector vector(1536),
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,
    tender_id VARCHAR(100),
    doc_id VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX embeddings_vector_idx ON embeddings
USING ivfflat (vector vector_cosine_ops);
```

## Configuration

### Chunking
```python
TextChunker(
    chunk_size=500,      # Tokens per chunk
    chunk_overlap=50     # Overlap between chunks
)
```

### RAG Pipeline
```python
RAGQueryPipeline(
    model="gpt-4",              # Answer generation model
    top_k=5,                    # Chunks to retrieve
    max_context_tokens=3000     # Max context size
)
```

## Cost & Performance

### Embedding Cost
- **OpenAI ada-002**: $0.0001 per 1K tokens
- **1000 documents** (~2500 tokens each): **$0.25**

### Query Cost
- **Per query**: ~$0.015 (mostly GPT-4)
- **With GPT-3.5-turbo**: ~$0.002 (7× cheaper)

### Latency
- **Embed query**: ~200ms
- **Vector search**: ~50ms
- **GPT-4 generation**: ~2-4s
- **Total**: **2-5 seconds** per query

### Scalability
- **10K embeddings**: ~20ms search
- **100K embeddings**: ~40ms search
- **1M embeddings**: ~50ms search
- **10M embeddings**: ~100ms search

## Examples

### Embed Multiple Documents

```python
from embeddings import EmbeddingsPipeline

async def main():
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
        print(f"{doc_id}: {len(embed_ids)} chunks")

asyncio.run(main())
```

### Question About Specific Tender

```python
from rag_query import ask_question

async def main():
    answer = await ask_question(
        question="Кој е нарачателот?",
        tender_id='TENDER-2024-001'  # Filter by tender
    )

    print(f"Answer: {answer.answer}")
    print(f"Sources: {len(answer.sources)}")
    for source in answer.sources:
        print(f"  - {source.tender_id}: {source.similarity:.2f}")

asyncio.run(main())
```

### Multi-Turn Conversation

```python
from rag_query import RAGQueryPipeline

async def main():
    pipeline = RAGQueryPipeline()

    # First question
    answer1 = await pipeline.generate_answer(
        "What is the procurement subject?"
    )

    # Follow-up with history
    history = [
        {'question': answer1.question, 'answer': answer1.answer}
    ]

    answer2 = await pipeline.generate_answer(
        question="When is the deadline?",
        conversation_history=history
    )

    print(f"Q1: {answer1.question}")
    print(f"A1: {answer1.answer}\n")
    print(f"Q2: {answer2.question}")
    print(f"A2: {answer2.answer}")

asyncio.run(main())
```

### Semantic Search Only

```python
from rag_query import search_tenders

async def main():
    results = await search_tenders(
        query="градежни проекти во Скопје",
        top_k=10
    )

    for result in results:
        print(f"\n{result.tender_id} (similarity: {result.similarity:.2f})")
        print(result.chunk_text[:200])

asyncio.run(main())
```

## Testing

```bash
# Run all tests
cd ai
pytest tests/ -v

# Run specific test file
pytest tests/test_embeddings.py -v
pytest tests/test_rag_query.py -v

# Run integration tests (requires DB + API key)
pytest tests/ -v -m integration
```

## Documentation

See **[RAG_GUIDE.md](RAG_GUIDE.md)** for comprehensive documentation including:
- Detailed architecture
- Complete API reference
- Configuration tuning
- Best practices
- Troubleshooting
- Performance optimization

## Dependencies

- **openai** - OpenAI API client (ada-002, GPT-4)
- **tiktoken** - Tokenization for chunking
- **asyncpg** - Async PostgreSQL driver
- **pgvector** - Vector similarity search
- **python-dotenv** - Environment variables

## Requirements

- Python 3.9+
- PostgreSQL 14+ with pgvector extension
- OpenAI API key
- DATABASE_URL environment variable

## Support

For detailed documentation, see:
- **[RAG_GUIDE.md](RAG_GUIDE.md)** - Complete guide (1300+ lines)
- **[embeddings.py](embeddings.py)** - Embeddings API reference
- **[rag_query.py](rag_query.py)** - RAG query API reference

## License

Part of nabavkidata.com - Macedonian Tender Intelligence Platform

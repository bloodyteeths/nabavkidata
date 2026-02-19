# Performance Testing & Optimization Guide

## Overview

This document outlines performance targets, benchmarking methodology, and optimization strategies for the nabavkidata.com platform.

## Performance Targets

### API Response Times

| Endpoint Type | Target (p95) | Maximum (p99) |
|---------------|--------------|---------------|
| Health checks | < 50ms | < 100ms |
| Simple queries | < 200ms | < 500ms |
| List endpoints | < 500ms | < 1s |
| Search endpoints | < 800ms | < 2s |
| RAG queries | < 5s | < 10s |
| Embeddings | < 3s | < 5s |

### Database Performance

| Operation | Target | Notes |
|-----------|--------|-------|
| Indexed lookup | < 20ms | Primary key, foreign key lookups |
| Simple JOIN | < 50ms | With proper indexes |
| Aggregation | < 500ms | GROUP BY with WHERE clause |
| Full-text search | < 1s | Using PostgreSQL FTS |
| Vector search | < 500ms | Using pgvector with HNSW index |

### Concurrency

- **Concurrent requests**: Handle 100+ concurrent requests with 95% success rate
- **Sustained load**: 10 requests/second for 30+ seconds
- **Connection pool**: Support 30 concurrent database connections (pool_size=10, max_overflow=20)

### Resource Usage

- **Memory**: < 500MB increase under load
- **CPU**: < 80% utilization under normal load
- **Database connections**: Efficient pool utilization, no connection leaks

## Benchmarking Methodology

### Running Benchmarks

```bash
# Run all benchmarks
./scripts/benchmark.sh

# Run specific benchmark suite
pytest tests/performance/benchmark_api.py --benchmark-only

# Run with profiling
pytest tests/performance/benchmark_api.py --benchmark-only --profile

# Compare with baseline
pytest-benchmark compare baseline.json current.json
```

### Benchmark Suites

#### 1. API Benchmarks (`benchmark_api.py`)

Tests API endpoint performance:
- Health and status endpoints
- Tender listing and search
- RAG query endpoints
- Embedding generation
- Concurrent request handling

```bash
pytest tests/performance/benchmark_api.py --benchmark-only -v
```

#### 2. Database Benchmarks (`benchmark_database.py`)

Tests database query performance:
- Index effectiveness
- JOIN performance
- Aggregation queries
- Full-text search
- Vector similarity search
- Pagination strategies

```bash
pytest tests/performance/benchmark_database.py --benchmark-only -v
```

#### 3. RAG Benchmarks (`benchmark_rag.py`)

Tests RAG pipeline components:
- Embedding generation time
- Text chunking performance
- Vector search scaling
- Context retrieval
- Response generation
- Memory usage

```bash
# Requires OPENAI_API_KEY
export OPENAI_API_KEY="your-key"
pytest tests/performance/benchmark_rag.py --benchmark-only -v
```

#### 4. Stress Tests (`stress_test.py`)

Tests system behavior under load:
- Concurrent request handling
- Sustained load testing
- Connection pool limits
- Memory usage under load
- Burst traffic handling

```bash
pytest tests/performance/stress_test.py -v -m stress
```

### Statistical Analysis

Benchmarks provide:
- **Mean**: Average execution time
- **Median**: Middle value (less affected by outliers)
- **StdDev**: Standard deviation (consistency measure)
- **Min/Max**: Range of execution times
- **p95**: 95th percentile (most requests complete by this time)
- **p99**: 99th percentile (worst-case for most requests)

## Profiling

### cProfile - Function-level Profiling

```python
from tests.performance.profiling import PerformanceProfiler

profiler = PerformanceProfiler()

with profiler.cprofile_context("my_operation"):
    # Your code here
    result = expensive_operation()
```

### Line Profiler - Line-by-line Analysis

```python
from tests.performance.profiling import LineProfiler

lp = LineProfiler()

@lp.profile
def my_function():
    # Your code
    pass

my_function()
lp.print_stats()
```

### Memory Profiler

```python
from tests.performance.profiling import MemoryProfiler

@MemoryProfiler.profile_memory
def memory_intensive_function():
    # Your code
    pass
```

## Optimization Guide

### Database Optimization

#### 1. Index Strategy

```sql
-- Essential indexes
CREATE INDEX idx_tenders_publish_date ON tenders(publish_date);
CREATE INDEX idx_tenders_cpv_code ON tenders(cpv_code);
CREATE INDEX idx_documents_tender_id ON documents(tender_id);

-- Composite indexes for common queries
CREATE INDEX idx_tenders_date_status ON tenders(publish_date, status);

-- Full-text search index
CREATE INDEX idx_tenders_fts ON tenders USING GIN (to_tsvector('english', title || ' ' || description));

-- Vector search index (HNSW for better performance)
CREATE INDEX idx_embeddings_vector ON document_embeddings
USING hnsw (embedding vector_cosine_ops);
```

#### 2. Query Optimization

**Bad**: Using OFFSET for pagination
```sql
SELECT * FROM tenders
ORDER BY publish_date DESC
LIMIT 20 OFFSET 1000;  -- Slow for large offsets
```

**Good**: Keyset pagination
```sql
SELECT * FROM tenders
WHERE publish_date < :cursor_date
ORDER BY publish_date DESC
LIMIT 20;
```

**Bad**: N+1 queries
```python
# Fetches tenders, then documents one by one
tenders = await session.execute(select(Tender))
for tender in tenders:
    docs = await session.execute(
        select(Document).where(Document.tender_id == tender.id)
    )
```

**Good**: Eager loading with JOIN
```python
# Single query with JOIN
from sqlalchemy.orm import joinedload

tenders = await session.execute(
    select(Tender).options(joinedload(Tender.documents))
)
```

#### 3. Connection Pool Tuning

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,        # Base pool size
    max_overflow=40,     # Additional connections under load
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600    # Recycle connections after 1 hour
)
```

### API Optimization

#### 1. Response Caching

```python
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=128)
def get_cached_tenders(page: int, cache_key: str):
    # Cache key includes timestamp rounded to 5 minutes
    # Results cached for repeated requests
    pass

# In endpoint
cache_key = f"{datetime.now().timestamp() // 300}"
return get_cached_tenders(page, cache_key)
```

#### 2. Async Processing

```python
# Good: Concurrent database queries
tasks = [
    session.execute(query1),
    session.execute(query2),
    session.execute(query3)
]
results = await asyncio.gather(*tasks)
```

#### 3. Response Compression

```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### RAG Optimization

#### 1. Batch Embedding Generation

```python
# Good: Process multiple documents in parallel
async def batch_embed(documents: List[str]):
    tasks = [
        pipeline.generate_embedding(doc)
        for doc in documents
    ]
    return await asyncio.gather(*tasks)
```

#### 2. Vector Search Optimization

- Use HNSW index for faster approximate search
- Tune `m` and `ef_construction` parameters
- Limit `top_k` to reasonable values (< 50)

```sql
-- Create HNSW index with custom parameters
CREATE INDEX idx_embeddings_hnsw ON document_embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Query with ef_search parameter
SET hnsw.ef_search = 40;
SELECT * FROM document_embeddings
ORDER BY embedding <=> query_vector
LIMIT 10;
```

#### 3. Context Window Management

```python
# Limit context size to stay within token limits
MAX_CONTEXT_TOKENS = 3000

def prepare_context(chunks: List[str]) -> str:
    context = []
    token_count = 0

    for chunk in chunks:
        chunk_tokens = count_tokens(chunk)
        if token_count + chunk_tokens > MAX_CONTEXT_TOKENS:
            break
        context.append(chunk)
        token_count += chunk_tokens

    return "\n\n".join(context)
```

## Regression Detection

### Setting Baseline

```bash
# Run benchmarks and save as baseline
./scripts/benchmark.sh

# Baseline saved to: benchmark_baseline/*.json
```

### Continuous Monitoring

```bash
# Compare current performance with baseline
pytest-benchmark compare \
    benchmark_baseline/api_benchmarks_baseline.json \
    benchmark_results/api_benchmarks_current.json
```

### CI/CD Integration

```yaml
# .github/workflows/performance.yml
name: Performance Tests

on: [pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run benchmarks
        run: ./scripts/benchmark.sh

      - name: Check for regressions
        run: |
          # Fail if performance regressed by > 20%
          python scripts/check_regression.py --threshold 1.20
```

## Results Interpretation

### Understanding Metrics

- **Mean < Target**: Good overall performance
- **StdDev < 20% of Mean**: Consistent performance
- **p95 < Maximum**: Most requests meet SLA
- **p99 within reason**: Few outliers

### Warning Signs

🚨 **Performance Issues**:
- p95 > 2x mean: High variance, investigate outliers
- StdDev > 50% of mean: Inconsistent performance
- Success rate < 95%: System struggling under load
- Memory increase > 500MB: Possible memory leak

### Example Analysis

```
Benchmark: GET /api/tenders
Mean:     245ms  ✓ (target: < 500ms)
Median:   230ms  ✓
StdDev:    45ms  ✓ (18% of mean)
p95:      320ms  ✓ (target: < 500ms)
p99:      450ms  ✓ (target: < 1s)
Success:   100%  ✓

Assessment: Excellent performance, meets all targets
```

## Best Practices

### 1. Regular Benchmarking

- Run benchmarks before major releases
- Track performance trends over time
- Set up automated performance testing in CI/CD

### 2. Incremental Optimization

- Profile before optimizing
- Optimize the slowest parts first
- Measure impact of each change
- Don't over-optimize rarely used code

### 3. Monitoring in Production

- Track actual response times
- Monitor database query performance
- Alert on performance regressions
- Use APM tools (New Relic, DataDog, etc.)

### 4. Load Testing

- Test with production-like data volumes
- Simulate realistic traffic patterns
- Test peak load scenarios
- Verify graceful degradation under extreme load

## Troubleshooting

### Slow API Responses

1. Check database query performance with EXPLAIN ANALYZE
2. Verify indexes are being used
3. Check for N+1 query problems
4. Profile code to find bottlenecks

### High Memory Usage

1. Check for memory leaks with memory profiler
2. Verify connection pool isn't exhausted
3. Look for large in-memory data structures
4. Check for unclosed resources

### Database Connection Issues

1. Monitor connection pool utilization
2. Check for long-running transactions
3. Verify connection recycling is working
4. Look for connection leaks

## Additional Resources

- [PostgreSQL Performance Optimization](https://www.postgresql.org/docs/current/performance-tips.html)
- [FastAPI Performance Tips](https://fastapi.tiangolo.com/deployment/concepts/)
- [Python Profiling Guide](https://docs.python.org/3/library/profile.html)
- [pgvector Performance Tuning](https://github.com/pgvector/pgvector#performance)

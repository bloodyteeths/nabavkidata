# Performance Testing Suite

Comprehensive performance testing and benchmarking for the nabavkidata.com platform.

## Overview

This suite provides:
- **API benchmarks**: Endpoint response time testing
- **Database benchmarks**: Query performance and index effectiveness
- **RAG benchmarks**: Embedding and vector search performance
- **Stress tests**: Load testing and concurrency handling
- **Profiling tools**: cProfile, line profiler, memory profiler

## Quick Start

### Installation

```bash
# Install performance testing dependencies
pip install -r tests/performance/requirements.txt
```

### Running Benchmarks

```bash
# Run all benchmarks
./scripts/benchmark.sh

# Run specific benchmark suite
pytest tests/performance/benchmark_api.py --benchmark-only -v
pytest tests/performance/benchmark_database.py --benchmark-only -v
pytest tests/performance/benchmark_rag.py --benchmark-only -v

# Run stress tests
pytest tests/performance/stress_test.py -v -m stress
```

## Test Suites

### 1. API Benchmarks (`benchmark_api.py`)

Tests API endpoint performance with pytest-benchmark:

- Health and root endpoints
- Tender listing and search endpoints
- RAG query endpoints
- Embedding generation
- Concurrent request handling
- Vector search scaling

**Usage:**
```bash
pytest tests/performance/benchmark_api.py --benchmark-only -v
```

### 2. Database Benchmarks (`benchmark_database.py`)

Tests database query performance:

- Simple SELECT and COUNT queries
- Index effectiveness
- JOIN performance (simple and multi-table)
- Aggregation queries
- Full-text search
- Vector similarity search
- Pagination strategies (OFFSET vs keyset)

**Usage:**
```bash
pytest tests/performance/benchmark_database.py --benchmark-only -v
```

### 3. RAG Benchmarks (`benchmark_rag.py`)

Tests RAG pipeline components:

- Embedding generation time
- Text chunking performance
- Vector search with different top_k values
- Full RAG query pipeline
- Context retrieval
- Response generation with varying context sizes
- Memory usage tracking

**Requirements:** Requires `OPENAI_API_KEY` environment variable.

**Usage:**
```bash
export OPENAI_API_KEY="your-api-key"
pytest tests/performance/benchmark_rag.py --benchmark-only -v
```

### 4. Stress Tests (`stress_test.py`)

Tests system behavior under load:

- Concurrent request handling (10-200 concurrent)
- Sustained load testing (10 req/s for 30s)
- Connection pool limits
- Memory usage under load
- Database connection pool stress
- Gradual ramp-up testing
- Burst traffic handling

**Usage:**
```bash
pytest tests/performance/stress_test.py -v -m stress
```

### 5. Profiling (`profiling.py`)

Provides profiling utilities:

- **cProfile**: Function-level profiling
- **Line profiler**: Line-by-line analysis
- **Memory profiler**: Memory usage tracking

**Usage:**
```python
from tests.performance.profiling import PerformanceProfiler

profiler = PerformanceProfiler()

with profiler.cprofile_context("my_operation"):
    # Your code here
    result = expensive_operation()
```

## Benchmark Script

The `scripts/benchmark.sh` script runs all benchmarks and generates reports:

```bash
./scripts/benchmark.sh
```

Features:
- Runs all benchmark suites
- Compares with baseline results
- Generates HTML reports with histograms
- Saves timestamped results
- CI/CD integration support

Results saved to:
- `benchmark_results/`: Current test results
- `benchmark_baseline/`: Baseline for comparison
- `profiling_results/`: Profiling data

## Configuration

### Environment Variables

```bash
# API endpoint for testing
export API_BASE_URL="http://localhost:8000"

# Database connection
export DATABASE_URL="postgresql+asyncpg://localhost:5432/nabavkidata"

# OpenAI API key (for RAG tests)
export OPENAI_API_KEY="your-api-key"

# Enable CI mode
export CI="true"
```

### Performance Targets

See `docs/PERFORMANCE.md` for detailed performance targets and optimization guide.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Performance Tests

on: [pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install -r tests/performance/requirements.txt

      - name: Start services
        run: docker-compose up -d

      - name: Run benchmarks
        run: ./scripts/benchmark.sh

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: benchmark_results/
```

## Results Interpretation

### Understanding Metrics

- **Mean**: Average execution time
- **Median**: Middle value (less affected by outliers)
- **StdDev**: Standard deviation (consistency)
- **p95**: 95th percentile (most requests complete by this time)
- **p99**: 99th percentile (worst-case for most requests)

### Example Output

```
-------------------------------- benchmark: API Health Check --------------------------
Name                        Min      Max     Mean    StdDev  Median     p95     p99
-----------------------------------------------------------------------------------
test_health_endpoint     15.2ms   45.3ms   18.7ms    4.2ms   17.9ms   25.1ms  32.4ms
```

### Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| Mean < 50ms | 18.7ms | ✓ Pass |
| p95 < 100ms | 25.1ms | ✓ Pass |
| StdDev < 20% | 22.5% | ⚠ Warning |

## Troubleshooting

### Common Issues

**Issue: Benchmarks failing with connection errors**
```bash
# Ensure services are running
docker-compose up -d

# Check API is accessible
curl http://localhost:8000/health
```

**Issue: RAG tests skipped**
```bash
# Set OpenAI API key
export OPENAI_API_KEY="your-key"

# Verify RAG modules available
python -c "from ai.rag_query import RAGQueryPipeline"
```

**Issue: Database connection errors**
```bash
# Verify database is running
docker-compose ps postgres

# Check connection string
echo $DATABASE_URL
```

## Best Practices

1. **Baseline First**: Establish baseline before making changes
2. **Consistent Environment**: Run benchmarks in consistent conditions
3. **Multiple Runs**: Average results across multiple runs
4. **Realistic Data**: Use production-like data volumes
5. **Monitor Resources**: Track CPU, memory, disk I/O during tests

## Additional Resources

- [Performance Optimization Guide](../../docs/PERFORMANCE.md)
- [pytest-benchmark Documentation](https://pytest-benchmark.readthedocs.io/)
- [Python Profiling Guide](https://docs.python.org/3/library/profile.html)

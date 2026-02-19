"""
API Performance Benchmarks
Tests critical API endpoints for performance regression
"""
import pytest
import asyncio
import httpx
import time
from typing import Dict, List
from datetime import datetime, timedelta
import statistics
import os


# Test configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
BENCHMARK_ROUNDS = 100
TIMEOUT = 30.0


class APIBenchmark:
    """API benchmark helper class"""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.client = None

    async def setup(self):
        """Initialize async HTTP client"""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=TIMEOUT
        )

    async def teardown(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()

    async def measure_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Measure single request performance"""
        start = time.perf_counter()
        response = await self.client.request(method, endpoint, **kwargs)
        duration = time.perf_counter() - start

        return {
            "duration": duration,
            "status_code": response.status_code,
            "response_size": len(response.content)
        }

    async def benchmark_endpoint(
        self,
        method: str,
        endpoint: str,
        rounds: int = BENCHMARK_ROUNDS,
        **kwargs
    ) -> Dict:
        """Benchmark endpoint with multiple requests"""
        results = []

        for _ in range(rounds):
            result = await self.measure_request(method, endpoint, **kwargs)
            results.append(result)
            await asyncio.sleep(0.01)  # Small delay between requests

        durations = [r["duration"] for r in results]

        return {
            "mean": statistics.mean(durations),
            "median": statistics.median(durations),
            "stdev": statistics.stdev(durations) if len(durations) > 1 else 0,
            "min": min(durations),
            "max": max(durations),
            "p95": statistics.quantiles(durations, n=20)[18],  # 95th percentile
            "p99": statistics.quantiles(durations, n=100)[98],  # 99th percentile
            "total_requests": len(results),
            "successful_requests": sum(1 for r in results if r["status_code"] == 200)
        }


@pytest.fixture
async def api_benchmark():
    """Pytest fixture for API benchmark"""
    bench = APIBenchmark()
    await bench.setup()
    yield bench
    await bench.teardown()


# ============================================================================
# HEALTH & ROOT ENDPOINTS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_health_endpoint(benchmark, api_benchmark):
    """Benchmark /health endpoint"""

    async def run_health_check():
        return await api_benchmark.benchmark_endpoint("GET", "/health", rounds=100)

    stats = benchmark(lambda: asyncio.run(run_health_check()))

    # Assertions
    assert stats["mean"] < 0.050  # Should be under 50ms average
    assert stats["p95"] < 0.100   # 95th percentile under 100ms
    assert stats["successful_requests"] == stats["total_requests"]


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_root_endpoint(benchmark, api_benchmark):
    """Benchmark / root endpoint"""

    async def run_root():
        return await api_benchmark.benchmark_endpoint("GET", "/", rounds=100)

    stats = benchmark(lambda: asyncio.run(run_root()))

    assert stats["mean"] < 0.050
    assert stats["successful_requests"] == stats["total_requests"]


# ============================================================================
# TENDER ENDPOINTS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_tenders_list(benchmark, api_benchmark):
    """Benchmark GET /api/tenders endpoint"""

    async def run_tenders_list():
        return await api_benchmark.benchmark_endpoint(
            "GET",
            "/api/tenders",
            params={"page": 1, "size": 20},
            rounds=50
        )

    stats = benchmark(lambda: asyncio.run(run_tenders_list()))

    # Should complete within reasonable time with database query
    assert stats["mean"] < 0.500  # Under 500ms average
    assert stats["p95"] < 1.000   # 95th percentile under 1s


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_tenders_search(benchmark, api_benchmark):
    """Benchmark GET /api/tenders/search endpoint"""

    async def run_search():
        return await api_benchmark.benchmark_endpoint(
            "GET",
            "/api/tenders/search",
            params={"query": "construction", "page": 1, "size": 20},
            rounds=50
        )

    stats = benchmark(lambda: asyncio.run(run_search()))

    # Search should be reasonably fast with proper indexing
    assert stats["mean"] < 0.800
    assert stats["p95"] < 2.000


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_tender_detail(benchmark, api_benchmark):
    """Benchmark GET /api/tenders/{id} endpoint"""

    async def run_detail():
        return await api_benchmark.benchmark_endpoint(
            "GET",
            "/api/tenders/test-tender-123",
            rounds=100
        )

    stats = benchmark(lambda: asyncio.run(run_detail()))

    # Single record fetch should be fast
    assert stats["mean"] < 0.200
    assert stats["p95"] < 0.500


# ============================================================================
# RAG ENDPOINTS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OpenAI API key not configured"
)
async def test_benchmark_rag_query(benchmark, api_benchmark):
    """Benchmark POST /api/rag/query endpoint"""

    async def run_rag_query():
        return await api_benchmark.benchmark_endpoint(
            "POST",
            "/api/rag/query",
            json={
                "question": "What is the tender about?",
                "top_k": 5
            },
            rounds=10  # Fewer rounds for expensive operation
        )

    stats = benchmark(lambda: asyncio.run(run_rag_query()))

    # RAG queries are expensive but should complete in reasonable time
    assert stats["mean"] < 5.000   # Under 5s average
    assert stats["p95"] < 10.000   # 95th percentile under 10s


@pytest.mark.asyncio
@pytest.mark.benchmark
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OpenAI API key not configured"
)
async def test_benchmark_semantic_search(benchmark, api_benchmark):
    """Benchmark POST /api/rag/search endpoint"""

    async def run_semantic_search():
        return await api_benchmark.benchmark_endpoint(
            "POST",
            "/api/rag/search",
            json={
                "query": "construction projects",
                "top_k": 10
            },
            rounds=20
        )

    stats = benchmark(lambda: asyncio.run(run_semantic_search()))

    # Semantic search should be faster than full RAG
    assert stats["mean"] < 2.000
    assert stats["p95"] < 5.000


# ============================================================================
# EMBEDDING PERFORMANCE
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OpenAI API key not configured"
)
async def test_benchmark_document_embedding(benchmark, api_benchmark):
    """Benchmark POST /api/rag/embed/document endpoint"""

    test_text = "This is a sample tender document for testing embedding performance. " * 20

    async def run_embedding():
        return await api_benchmark.benchmark_endpoint(
            "POST",
            "/api/rag/embed/document",
            params={
                "tender_id": "test-tender-001",
                "doc_id": "test-doc-001",
                "text": test_text
            },
            rounds=5  # Few rounds for expensive operation
        )

    stats = benchmark(lambda: asyncio.run(run_embedding()))

    # Embedding should complete in reasonable time
    assert stats["mean"] < 3.000


# ============================================================================
# CONCURRENT REQUEST BENCHMARKS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_concurrent_requests(api_benchmark):
    """Test concurrent request handling"""

    async def run_concurrent():
        tasks = []
        for _ in range(50):
            task = api_benchmark.measure_request("GET", "/health")
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        durations = [r["duration"] for r in results]

        return {
            "mean": statistics.mean(durations),
            "max": max(durations),
            "successful": sum(1 for r in results if r["status_code"] == 200)
        }

    stats = await run_concurrent()

    # All concurrent requests should succeed
    assert stats["successful"] == 50
    # Average should still be reasonable under load
    assert stats["mean"] < 0.200


# ============================================================================
# VECTOR SEARCH PERFORMANCE
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OpenAI API key not configured"
)
async def test_benchmark_vector_search_scaling(api_benchmark):
    """Test vector search performance with different top_k values"""

    results = {}

    for top_k in [5, 10, 20, 50]:
        stats = await api_benchmark.benchmark_endpoint(
            "POST",
            "/api/rag/search",
            json={
                "query": "infrastructure development",
                "top_k": top_k
            },
            rounds=10
        )
        results[f"top_k_{top_k}"] = stats["mean"]

    # Verify scaling is reasonable
    # top_k=50 shouldn't be more than 2x slower than top_k=5
    assert results["top_k_50"] < results["top_k_5"] * 2.0


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def print_benchmark_results(stats: Dict):
    """Pretty print benchmark statistics"""
    print("\n" + "="*60)
    print("BENCHMARK RESULTS")
    print("="*60)
    print(f"Mean:           {stats['mean']*1000:.2f}ms")
    print(f"Median:         {stats['median']*1000:.2f}ms")
    print(f"Std Dev:        {stats['stdev']*1000:.2f}ms")
    print(f"Min:            {stats['min']*1000:.2f}ms")
    print(f"Max:            {stats['max']*1000:.2f}ms")
    print(f"95th %ile:      {stats['p95']*1000:.2f}ms")
    print(f"99th %ile:      {stats['p99']*1000:.2f}ms")
    print(f"Total Requests: {stats['total_requests']}")
    print(f"Success Rate:   {stats['successful_requests']/stats['total_requests']*100:.1f}%")
    print("="*60 + "\n")

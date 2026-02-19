"""
Database Performance Benchmarks
Tests database query performance, index effectiveness, and query optimization
"""
import pytest
import asyncio
import time
import statistics
from typing import List, Dict
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import os


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://localhost:5432/nabavkidata"
)


class DatabaseBenchmark:
    """Database benchmark helper class"""

    def __init__(self, db_url: str = DATABASE_URL):
        self.engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=20,
            max_overflow=40
        )
        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def setup(self):
        """Initialize database connection"""
        async with self.engine.begin() as conn:
            # Verify connection
            await conn.execute(text("SELECT 1"))

    async def teardown(self):
        """Close database connections"""
        await self.engine.dispose()

    async def measure_query(self, query: str, params: dict = None) -> Dict:
        """Measure single query performance"""
        async with self.session_maker() as session:
            start = time.perf_counter()
            result = await session.execute(text(query), params or {})
            rows = result.fetchall()
            duration = time.perf_counter() - start

            return {
                "duration": duration,
                "row_count": len(rows)
            }

    async def benchmark_query(
        self,
        query: str,
        params: dict = None,
        rounds: int = 100
    ) -> Dict:
        """Benchmark query with multiple executions"""
        results = []

        for _ in range(rounds):
            result = await self.measure_query(query, params)
            results.append(result)

        durations = [r["duration"] for r in results]

        return {
            "mean": statistics.mean(durations),
            "median": statistics.median(durations),
            "stdev": statistics.stdev(durations) if len(durations) > 1 else 0,
            "min": min(durations),
            "max": max(durations),
            "p95": statistics.quantiles(durations, n=20)[18],
            "p99": statistics.quantiles(durations, n=100)[98],
            "avg_row_count": statistics.mean([r["row_count"] for r in results])
        }


@pytest.fixture
async def db_benchmark():
    """Pytest fixture for database benchmark"""
    bench = DatabaseBenchmark()
    await bench.setup()
    yield bench
    await bench.teardown()


# ============================================================================
# SIMPLE QUERY BENCHMARKS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_simple_select(benchmark, db_benchmark):
    """Benchmark simple SELECT query"""

    query = "SELECT 1 as value"

    async def run_query():
        return await db_benchmark.benchmark_query(query, rounds=1000)

    stats = benchmark(lambda: asyncio.run(run_query()))

    # Simple query should be very fast
    assert stats["mean"] < 0.010  # Under 10ms
    assert stats["p95"] < 0.020   # 95th percentile under 20ms


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_count_query(benchmark, db_benchmark):
    """Benchmark COUNT(*) query on tenders table"""

    query = "SELECT COUNT(*) FROM tenders"

    async def run_query():
        return await db_benchmark.benchmark_query(query, rounds=100)

    stats = benchmark(lambda: asyncio.run(run_query()))

    # COUNT should use index
    assert stats["mean"] < 0.100
    assert stats["p95"] < 0.200


# ============================================================================
# INDEX EFFECTIVENESS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_indexed_lookup(benchmark, db_benchmark):
    """Benchmark lookup by indexed tender_id"""

    query = """
        SELECT tender_id, title, publish_date
        FROM tenders
        WHERE tender_id = :tender_id
    """

    async def run_query():
        return await db_benchmark.benchmark_query(
            query,
            params={"tender_id": "test-tender-001"},
            rounds=100
        )

    stats = benchmark(lambda: asyncio.run(run_query()))

    # Indexed lookup should be very fast
    assert stats["mean"] < 0.020
    assert stats["p95"] < 0.050


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_date_range_query(benchmark, db_benchmark):
    """Benchmark date range query (should use index)"""

    query = """
        SELECT tender_id, title, publish_date
        FROM tenders
        WHERE publish_date >= :start_date
          AND publish_date <= :end_date
        ORDER BY publish_date DESC
        LIMIT 20
    """

    async def run_query():
        return await db_benchmark.benchmark_query(
            query,
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31"
            },
            rounds=50
        )

    stats = benchmark(lambda: asyncio.run(run_query()))

    # Date range with index should be fast
    assert stats["mean"] < 0.200
    assert stats["p95"] < 0.500


# ============================================================================
# JOIN PERFORMANCE
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_simple_join(benchmark, db_benchmark):
    """Benchmark simple JOIN between tenders and documents"""

    query = """
        SELECT t.tender_id, t.title, d.doc_id, d.filename
        FROM tenders t
        INNER JOIN documents d ON t.tender_id = d.tender_id
        WHERE t.tender_id = :tender_id
    """

    async def run_query():
        return await db_benchmark.benchmark_query(
            query,
            params={"tender_id": "test-tender-001"},
            rounds=100
        )

    stats = benchmark(lambda: asyncio.run(run_query()))

    # JOIN on indexed columns should be fast
    assert stats["mean"] < 0.050
    assert stats["p95"] < 0.150


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_multi_join(benchmark, db_benchmark):
    """Benchmark multiple JOINs"""

    query = """
        SELECT
            t.tender_id,
            t.title,
            COUNT(d.doc_id) as doc_count,
            COUNT(e.embed_id) as embed_count
        FROM tenders t
        LEFT JOIN documents d ON t.tender_id = d.tender_id
        LEFT JOIN document_embeddings e ON d.doc_id = e.doc_id
        WHERE t.tender_id = :tender_id
        GROUP BY t.tender_id, t.title
    """

    async def run_query():
        return await db_benchmark.benchmark_query(
            query,
            params={"tender_id": "test-tender-001"},
            rounds=50
        )

    stats = benchmark(lambda: asyncio.run(run_query()))

    # Multi-join with aggregation should still be reasonable
    assert stats["mean"] < 0.150
    assert stats["p95"] < 0.400


# ============================================================================
# AGGREGATION QUERIES
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_group_by_aggregation(benchmark, db_benchmark):
    """Benchmark GROUP BY aggregation"""

    query = """
        SELECT
            cpv_code,
            COUNT(*) as tender_count,
            AVG(estimated_value) as avg_value
        FROM tenders
        WHERE publish_date >= :start_date
        GROUP BY cpv_code
        ORDER BY tender_count DESC
        LIMIT 20
    """

    async def run_query():
        return await db_benchmark.benchmark_query(
            query,
            params={"start_date": "2024-01-01"},
            rounds=50
        )

    stats = benchmark(lambda: asyncio.run(run_query()))

    # Aggregation should complete in reasonable time
    assert stats["mean"] < 0.500
    assert stats["p95"] < 1.000


# ============================================================================
# FULL-TEXT SEARCH
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_fulltext_search(benchmark, db_benchmark):
    """Benchmark full-text search using LIKE"""

    query = """
        SELECT tender_id, title, description
        FROM tenders
        WHERE title ILIKE :search_term
           OR description ILIKE :search_term
        LIMIT 20
    """

    async def run_query():
        return await db_benchmark.benchmark_query(
            query,
            params={"search_term": "%construction%"},
            rounds=50
        )

    stats = benchmark(lambda: asyncio.run(run_query()))

    # Full-text search may be slower without proper indexing
    assert stats["mean"] < 1.000
    assert stats["p95"] < 2.000


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_tsvector_search(benchmark, db_benchmark):
    """Benchmark PostgreSQL full-text search with tsvector"""

    # Skip if tsvector column doesn't exist
    query = """
        SELECT tender_id, title, description
        FROM tenders
        WHERE to_tsvector('english', title || ' ' || description) @@ to_tsquery('english', :search_term)
        LIMIT 20
    """

    async def run_query():
        return await db_benchmark.benchmark_query(
            query,
            params={"search_term": "construction"},
            rounds=50
        )

    stats = benchmark(lambda: asyncio.run(run_query()))

    # tsvector search should be faster than LIKE
    assert stats["mean"] < 0.500


# ============================================================================
# VECTOR SEARCH PERFORMANCE
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_vector_similarity_search(benchmark, db_benchmark):
    """Benchmark pgvector similarity search"""

    # Create a dummy embedding vector for testing
    query = """
        SELECT
            embed_id,
            tender_id,
            doc_id,
            1 - (embedding <=> :query_vector::vector) as similarity
        FROM document_embeddings
        ORDER BY embedding <=> :query_vector::vector
        LIMIT :top_k
    """

    # Create dummy 1536-dim vector (OpenAI embedding size)
    dummy_vector = "[" + ",".join(["0.0"] * 1536) + "]"

    async def run_query():
        return await db_benchmark.benchmark_query(
            query,
            params={
                "query_vector": dummy_vector,
                "top_k": 10
            },
            rounds=20
        )

    stats = benchmark(lambda: asyncio.run(run_query()))

    # Vector search should complete in reasonable time
    assert stats["mean"] < 0.500
    assert stats["p95"] < 1.000


# ============================================================================
# PAGINATION PERFORMANCE
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_pagination_offset(benchmark, db_benchmark):
    """Benchmark OFFSET-based pagination"""

    query = """
        SELECT tender_id, title, publish_date
        FROM tenders
        ORDER BY publish_date DESC
        LIMIT :page_size
        OFFSET :offset
    """

    async def run_query():
        return await db_benchmark.benchmark_query(
            query,
            params={"page_size": 20, "offset": 100},
            rounds=50
        )

    stats = benchmark(lambda: asyncio.run(run_query()))

    # OFFSET pagination should be reasonable for small offsets
    assert stats["mean"] < 0.200


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_pagination_keyset(benchmark, db_benchmark):
    """Benchmark keyset-based pagination"""

    query = """
        SELECT tender_id, title, publish_date
        FROM tenders
        WHERE publish_date < :cursor_date
        ORDER BY publish_date DESC
        LIMIT :page_size
    """

    async def run_query():
        return await db_benchmark.benchmark_query(
            query,
            params={
                "cursor_date": "2024-06-01",
                "page_size": 20
            },
            rounds=50
        )

    stats = benchmark(lambda: asyncio.run(run_query()))

    # Keyset pagination should be faster than OFFSET for large datasets
    assert stats["mean"] < 0.150


# ============================================================================
# EXPLAIN ANALYZE HELPER
# ============================================================================

@pytest.mark.asyncio
async def test_explain_analyze_sample_queries(db_benchmark):
    """Run EXPLAIN ANALYZE on sample queries for optimization"""

    queries = [
        "SELECT * FROM tenders WHERE tender_id = 'test-001'",
        "SELECT * FROM tenders WHERE publish_date >= '2024-01-01' LIMIT 20",
        "SELECT cpv_code, COUNT(*) FROM tenders GROUP BY cpv_code"
    ]

    for query in queries:
        async with db_benchmark.session_maker() as session:
            result = await session.execute(
                text(f"EXPLAIN ANALYZE {query}")
            )
            plan = result.fetchall()

            print(f"\n{'='*60}")
            print(f"Query: {query}")
            print(f"{'='*60}")
            for row in plan:
                print(row[0])
            print(f"{'='*60}\n")

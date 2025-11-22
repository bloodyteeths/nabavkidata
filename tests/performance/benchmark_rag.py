"""
RAG Pipeline Performance Benchmarks
Tests embedding generation, vector search, and RAG query performance
"""
import pytest
import asyncio
import time
import statistics
from typing import List, Dict
import os
import sys


# Add AI module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../ai'))


try:
    from embeddings import EmbeddingsPipeline, chunk_text
    from rag_query import RAGQueryPipeline, search_tenders
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False


# Skip all tests if RAG not available
pytestmark = pytest.mark.skipif(
    not RAG_AVAILABLE or not os.getenv("OPENAI_API_KEY"),
    reason="RAG modules or OpenAI API key not available"
)


class RAGBenchmark:
    """RAG pipeline benchmark helper"""

    def __init__(self):
        self.embeddings_pipeline = None
        self.rag_pipeline = None

    async def setup(self):
        """Initialize RAG components"""
        if RAG_AVAILABLE:
            self.embeddings_pipeline = EmbeddingsPipeline()
            self.rag_pipeline = RAGQueryPipeline(top_k=10)

    async def measure_embedding(self, text: str) -> Dict:
        """Measure embedding generation time"""
        start = time.perf_counter()
        embedding = await self.embeddings_pipeline.generate_embedding(text)
        duration = time.perf_counter() - start

        return {
            "duration": duration,
            "embedding_dim": len(embedding) if embedding else 0
        }

    async def measure_vector_search(self, query: str, top_k: int = 10) -> Dict:
        """Measure vector search time"""
        start = time.perf_counter()
        results = await search_tenders(query=query, top_k=top_k)
        duration = time.perf_counter() - start

        return {
            "duration": duration,
            "result_count": len(results)
        }

    async def measure_rag_query(self, question: str) -> Dict:
        """Measure full RAG query time"""
        start = time.perf_counter()
        answer = await self.rag_pipeline.generate_answer(question=question)
        duration = time.perf_counter() - start

        return {
            "duration": duration,
            "answer_length": len(answer.answer) if answer else 0,
            "source_count": len(answer.sources) if answer else 0
        }


@pytest.fixture
async def rag_benchmark():
    """Pytest fixture for RAG benchmark"""
    bench = RAGBenchmark()
    await bench.setup()
    yield bench


# ============================================================================
# EMBEDDING GENERATION BENCHMARKS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_single_embedding(benchmark, rag_benchmark):
    """Benchmark single embedding generation"""

    text = "This is a sample tender document for construction project."

    async def run_embedding():
        results = []
        for _ in range(10):
            result = await rag_benchmark.measure_embedding(text)
            results.append(result)

        durations = [r["duration"] for r in results]
        return {
            "mean": statistics.mean(durations),
            "min": min(durations),
            "max": max(durations)
        }

    stats = benchmark(lambda: asyncio.run(run_embedding()))

    # Single embedding should complete quickly
    assert stats["mean"] < 1.0  # Under 1 second


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_embedding_scaling(rag_benchmark):
    """Test embedding generation time vs text length"""

    text_lengths = [100, 500, 1000, 2000, 5000]
    results = {}

    for length in text_lengths:
        text = "word " * (length // 5)  # Approximate word count
        stats = await rag_benchmark.measure_embedding(text)
        results[f"length_{length}"] = stats["duration"]

    # Print results
    print("\nEmbedding time by text length:")
    for length, duration in results.items():
        print(f"  {length}: {duration*1000:.2f}ms")

    # Verify scaling is reasonable
    # Longer text shouldn't be dramatically slower (tokenization is fast)
    assert results["length_5000"] < results["length_100"] * 5.0


# ============================================================================
# TEXT CHUNKING BENCHMARKS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_text_chunking(benchmark):
    """Benchmark text chunking performance"""

    # Generate large document
    large_text = "This is a sample sentence. " * 1000  # ~5000 words

    def run_chunking():
        chunks = chunk_text(large_text, chunk_size=500, overlap=50)
        return {
            "chunk_count": len(chunks),
            "avg_chunk_size": statistics.mean([len(c) for c in chunks])
        }

    stats = benchmark(run_chunking)

    # Chunking should be very fast (no API calls)
    assert stats.stats.stats.mean < 0.1  # Under 100ms


# ============================================================================
# VECTOR SEARCH BENCHMARKS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_vector_search(benchmark, rag_benchmark):
    """Benchmark vector similarity search"""

    query = "construction infrastructure development"

    async def run_search():
        results = []
        for _ in range(10):
            result = await rag_benchmark.measure_vector_search(query, top_k=10)
            results.append(result)

        durations = [r["duration"] for r in results]
        return {
            "mean": statistics.mean(durations),
            "p95": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
        }

    stats = benchmark(lambda: asyncio.run(run_search()))

    # Vector search should be fast
    assert stats["mean"] < 2.0


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_vector_search_top_k_scaling(rag_benchmark):
    """Test vector search performance with different top_k values"""

    query = "infrastructure development projects"
    top_k_values = [5, 10, 20, 50, 100]
    results = {}

    for top_k in top_k_values:
        stats = await rag_benchmark.measure_vector_search(query, top_k=top_k)
        results[f"top_k_{top_k}"] = stats["duration"]

    # Print results
    print("\nVector search time by top_k:")
    for k, duration in results.items():
        print(f"  {k}: {duration*1000:.2f}ms")

    # Verify scaling
    # top_k=100 shouldn't be more than 2x slower than top_k=5
    assert results["top_k_100"] < results["top_k_5"] * 2.0


# ============================================================================
# FULL RAG QUERY BENCHMARKS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_rag_query(benchmark, rag_benchmark):
    """Benchmark full RAG query pipeline"""

    question = "What construction projects are available?"

    async def run_rag():
        results = []
        for _ in range(5):  # Fewer iterations for expensive operation
            result = await rag_benchmark.measure_rag_query(question)
            results.append(result)

        durations = [r["duration"] for r in results]
        return {
            "mean": statistics.mean(durations),
            "min": min(durations),
            "max": max(durations)
        }

    stats = benchmark(lambda: asyncio.run(run_rag()))

    # Full RAG query includes embedding + search + LLM
    assert stats["mean"] < 10.0  # Under 10 seconds


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_rag_query_complexity(rag_benchmark):
    """Test RAG performance with different question complexities"""

    questions = {
        "simple": "What is the tender about?",
        "medium": "What are the requirements and deadlines for this tender?",
        "complex": "Compare the technical requirements, deadlines, and budget across all construction tenders."
    }

    results = {}

    for complexity, question in questions.items():
        stats = await rag_benchmark.measure_rag_query(question)
        results[complexity] = stats["duration"]

    # Print results
    print("\nRAG query time by complexity:")
    for complexity, duration in results.items():
        print(f"  {complexity}: {duration:.2f}s")

    # More complex queries may take longer but should still be reasonable
    assert all(duration < 15.0 for duration in results.values())


# ============================================================================
# CONTEXT RETRIEVAL BENCHMARKS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_context_retrieval(rag_benchmark):
    """Benchmark context retrieval from vector store"""

    query = "tender requirements"
    top_k_values = [5, 10, 20]
    results = {}

    for top_k in top_k_values:
        durations = []
        for _ in range(10):
            stats = await rag_benchmark.measure_vector_search(query, top_k=top_k)
            durations.append(stats["duration"])

        results[f"top_k_{top_k}"] = {
            "mean": statistics.mean(durations),
            "p95": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
        }

    # Verify all retrievals are fast
    for top_k, stats in results.items():
        assert stats["mean"] < 1.0
        assert stats["p95"] < 2.0


# ============================================================================
# BATCH EMBEDDING BENCHMARKS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_batch_embeddings(rag_benchmark):
    """Benchmark batch embedding generation"""

    texts = [
        f"Sample tender document number {i} with some content."
        for i in range(10)
    ]

    start = time.perf_counter()

    # Generate embeddings sequentially
    sequential_embeddings = []
    for text in texts:
        result = await rag_benchmark.measure_embedding(text)
        sequential_embeddings.append(result)

    sequential_time = time.perf_counter() - start

    # Print results
    print(f"\nBatch embedding results:")
    print(f"  Sequential time: {sequential_time:.2f}s")
    print(f"  Average per embedding: {sequential_time/len(texts):.2f}s")

    # Batch should complete in reasonable time
    assert sequential_time < 15.0  # Under 15s for 10 embeddings


# ============================================================================
# RESPONSE GENERATION BENCHMARKS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_response_generation_with_context(rag_benchmark):
    """Benchmark response generation with different context sizes"""

    question = "What are the tender requirements?"
    context_sizes = [1, 3, 5, 10]
    results = {}

    for size in context_sizes:
        # Create mock RAG pipeline with different top_k
        pipeline = RAGQueryPipeline(top_k=size)

        start = time.perf_counter()
        answer = await pipeline.generate_answer(question=question)
        duration = time.perf_counter() - start

        results[f"context_{size}"] = duration

    # Print results
    print("\nResponse generation time by context size:")
    for ctx, duration in results.items():
        print(f"  {ctx}: {duration:.2f}s")

    # More context may take slightly longer but should scale reasonably
    assert results["context_10"] < results["context_1"] * 2.0


# ============================================================================
# MEMORY USAGE TRACKING
# ============================================================================

@pytest.mark.asyncio
async def test_rag_memory_usage(rag_benchmark):
    """Track memory usage during RAG operations"""
    import psutil
    import os as os_mod

    process = psutil.Process(os_mod.getpid())

    # Baseline memory
    baseline_mem = process.memory_info().rss / 1024 / 1024  # MB

    # Generate embeddings
    for _ in range(10):
        await rag_benchmark.measure_embedding("Sample text " * 100)

    after_embed_mem = process.memory_info().rss / 1024 / 1024

    # Run RAG queries
    for _ in range(5):
        await rag_benchmark.measure_rag_query("What is the tender about?")

    after_rag_mem = process.memory_info().rss / 1024 / 1024

    print(f"\nMemory usage:")
    print(f"  Baseline: {baseline_mem:.2f} MB")
    print(f"  After embeddings: {after_embed_mem:.2f} MB (+{after_embed_mem-baseline_mem:.2f} MB)")
    print(f"  After RAG: {after_rag_mem:.2f} MB (+{after_rag_mem-baseline_mem:.2f} MB)")

    # Memory increase should be reasonable
    assert after_rag_mem - baseline_mem < 500  # Less than 500MB increase

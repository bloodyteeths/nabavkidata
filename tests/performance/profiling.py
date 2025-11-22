"""
Code Profiling Setup
Provides profiling utilities for performance analysis
"""
import cProfile
import pstats
import io
import time
import functools
from typing import Callable, Any
from contextlib import contextmanager
from memory_profiler import profile as memory_profile
import line_profiler
import os


class PerformanceProfiler:
    """Performance profiling utility class"""

    def __init__(self, output_dir: str = "./profiling_results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    @contextmanager
    def cprofile_context(self, name: str = "profile"):
        """Context manager for cProfile profiling"""
        profiler = cProfile.Profile()
        profiler.enable()

        try:
            yield profiler
        finally:
            profiler.disable()

            # Save stats
            stats_file = os.path.join(self.output_dir, f"{name}.prof")
            profiler.dump_stats(stats_file)

            # Print summary
            stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stream)
            stats.sort_stats('cumulative')
            stats.print_stats(20)  # Top 20 functions

            print(f"\n{'='*60}")
            print(f"Profile: {name}")
            print(f"{'='*60}")
            print(stream.getvalue())
            print(f"Full stats saved to: {stats_file}")

    def profile_function(self, func: Callable) -> Callable:
        """Decorator to profile a function with cProfile"""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self.cprofile_context(func.__name__):
                return func(*args, **kwargs)

        return wrapper

    def time_function(self, func: Callable) -> Callable:
        """Decorator to measure function execution time"""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start

            print(f"\n{func.__name__} executed in {duration:.4f}s")
            return result

        return wrapper

    async def time_async_function(self, func: Callable, *args, **kwargs) -> tuple:
        """Time an async function"""
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        duration = time.perf_counter() - start

        return result, duration


class LineProfiler:
    """Line-by-line profiling utility"""

    def __init__(self):
        self.profiler = line_profiler.LineProfiler()

    def add_function(self, func: Callable):
        """Add function to profile"""
        self.profiler.add_function(func)

    def profile(self, func: Callable) -> Callable:
        """Decorator to add function to line profiler"""
        self.profiler.add_function(func)
        return func

    def print_stats(self):
        """Print profiling statistics"""
        self.profiler.print_stats()

    def save_stats(self, filename: str):
        """Save stats to file"""
        with open(filename, 'w') as f:
            stats = io.StringIO()
            self.profiler.print_stats(stream=stats)
            f.write(stats.getvalue())


class MemoryProfiler:
    """Memory profiling utility"""

    @staticmethod
    def profile_memory(func: Callable) -> Callable:
        """Decorator to profile memory usage"""
        return memory_profile(func)

    @staticmethod
    def measure_memory_usage():
        """Get current memory usage"""
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()

        return {
            "rss_mb": mem_info.rss / 1024 / 1024,
            "vms_mb": mem_info.vms / 1024 / 1024
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_cprofile():
    """Example: Using cProfile context manager"""
    profiler = PerformanceProfiler()

    with profiler.cprofile_context("example_computation"):
        # Your code here
        result = sum(i**2 for i in range(100000))

    print(f"Result: {result}")


def example_function_decorator():
    """Example: Using function decorator"""
    profiler = PerformanceProfiler()

    @profiler.profile_function
    def expensive_computation():
        return sum(i**2 for i in range(100000))

    result = expensive_computation()
    print(f"Result: {result}")


def example_line_profiling():
    """Example: Line-by-line profiling"""
    lp = LineProfiler()

    @lp.profile
    def process_data():
        data = []
        for i in range(1000):
            data.append(i**2)

        result = sum(data)
        return result

    # Run the function
    result = process_data()

    # Print stats
    lp.print_stats()


@memory_profile
def example_memory_profiling():
    """Example: Memory profiling"""
    # Allocate some memory
    large_list = [i for i in range(1000000)]

    # Process data
    result = sum(large_list)

    return result


# ============================================================================
# PYTEST INTEGRATION
# ============================================================================

import pytest


@pytest.fixture
def performance_profiler():
    """Pytest fixture for performance profiler"""
    return PerformanceProfiler()


@pytest.fixture
def line_profiler_fixture():
    """Pytest fixture for line profiler"""
    return LineProfiler()


def test_example_with_profiling(performance_profiler):
    """Example test with profiling"""

    with performance_profiler.cprofile_context("test_computation"):
        result = sum(i**2 for i in range(10000))

    assert result > 0


# ============================================================================
# PROFILING SPECIFIC FUNCTIONS
# ============================================================================

def profile_database_query():
    """Profile database query performance"""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import text

    profiler = PerformanceProfiler()

    async def run_query():
        engine = create_async_engine(
            "postgresql+asyncpg://localhost:5432/nabavkidata"
        )
        session_maker = async_sessionmaker(engine, class_=AsyncSession)

        async with session_maker() as session:
            result = await session.execute(
                text("SELECT * FROM tenders LIMIT 100")
            )
            rows = result.fetchall()

        await engine.dispose()
        return len(rows)

    with profiler.cprofile_context("database_query"):
        row_count = asyncio.run(run_query())

    print(f"Retrieved {row_count} rows")


def profile_embedding_generation():
    """Profile embedding generation"""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../ai'))

    try:
        from embeddings import EmbeddingsPipeline
        import asyncio

        profiler = PerformanceProfiler()

        async def generate_embeddings():
            pipeline = EmbeddingsPipeline()
            text = "Sample tender document for embedding generation. " * 50

            embedding = await pipeline.generate_embedding(text)
            return len(embedding)

        with profiler.cprofile_context("embedding_generation"):
            size = asyncio.run(generate_embeddings())

        print(f"Generated embedding of size {size}")

    except ImportError:
        print("RAG modules not available")


def profile_rag_query():
    """Profile RAG query pipeline"""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../ai'))

    try:
        from rag_query import RAGQueryPipeline
        import asyncio

        profiler = PerformanceProfiler()
        lp = LineProfiler()

        async def run_rag_query():
            pipeline = RAGQueryPipeline(top_k=10)
            answer = await pipeline.generate_answer(
                question="What is the tender about?"
            )
            return answer

        with profiler.cprofile_context("rag_query"):
            result = asyncio.run(run_rag_query())

        print(f"Generated answer: {len(result.answer)} chars")

    except ImportError:
        print("RAG modules not available")


if __name__ == "__main__":
    print("Running profiling examples...\n")

    # Example 1: cProfile
    print("\n1. cProfile example:")
    example_cprofile()

    # Example 2: Function decorator
    print("\n2. Function decorator example:")
    example_function_decorator()

    # Example 3: Line profiling
    print("\n3. Line profiling example:")
    example_line_profiling()

    # Example 4: Memory profiling
    print("\n4. Memory profiling example:")
    example_memory_profiling()

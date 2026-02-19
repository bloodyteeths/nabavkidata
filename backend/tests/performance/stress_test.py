"""
Stress Testing Suite
Tests system behavior under heavy load and concurrent requests
"""
import pytest
import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict
import os
import psutil


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


class StressTest:
    """Stress test helper class"""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session = None

    async def setup(self):
        """Initialize aiohttp session"""
        self.session = aiohttp.ClientSession(
            base_url=self.base_url,
            timeout=aiohttp.ClientTimeout(total=30)
        )

    async def teardown(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()

    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make single HTTP request"""
        start = time.perf_counter()
        try:
            async with self.session.request(method, endpoint, **kwargs) as response:
                await response.text()
                duration = time.perf_counter() - start
                return {
                    "success": True,
                    "status": response.status,
                    "duration": duration
                }
        except Exception as e:
            duration = time.perf_counter() - start
            return {
                "success": False,
                "error": str(e),
                "duration": duration
            }

    async def concurrent_requests(
        self,
        method: str,
        endpoint: str,
        count: int,
        **kwargs
    ) -> List[Dict]:
        """Execute concurrent requests"""
        tasks = [
            self.make_request(method, endpoint, **kwargs)
            for _ in range(count)
        ]
        return await asyncio.gather(*tasks)


@pytest.fixture
async def stress_test():
    """Pytest fixture for stress test"""
    test = StressTest()
    await test.setup()
    yield test
    await test.teardown()


# ============================================================================
# CONCURRENT REQUEST STRESS TESTS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.stress
async def test_stress_concurrent_health_checks(stress_test):
    """Stress test with concurrent health check requests"""

    concurrent_levels = [10, 50, 100, 200]
    results = {}

    for level in concurrent_levels:
        responses = await stress_test.concurrent_requests(
            "GET", "/health", count=level
        )

        success_count = sum(1 for r in responses if r["success"])
        durations = [r["duration"] for r in responses if r["success"]]

        results[f"concurrent_{level}"] = {
            "success_rate": success_count / level,
            "mean_duration": statistics.mean(durations) if durations else 0,
            "max_duration": max(durations) if durations else 0
        }

    # Print results
    print("\nConcurrent request stress test results:")
    for level, stats in results.items():
        print(f"  {level}:")
        print(f"    Success rate: {stats['success_rate']*100:.1f}%")
        print(f"    Mean duration: {stats['mean_duration']*1000:.2f}ms")
        print(f"    Max duration: {stats['max_duration']*1000:.2f}ms")

    # All requests should succeed
    for stats in results.values():
        assert stats["success_rate"] >= 0.95  # 95% success rate


@pytest.mark.asyncio
@pytest.mark.stress
async def test_stress_concurrent_api_requests(stress_test):
    """Stress test with concurrent API requests"""

    concurrent_count = 100

    responses = await stress_test.concurrent_requests(
        "GET",
        "/api/tenders",
        count=concurrent_count,
        params={"page": 1, "size": 20}
    )

    success_count = sum(1 for r in responses if r["success"])
    durations = [r["duration"] for r in responses if r["success"]]

    print(f"\nConcurrent API requests ({concurrent_count}):")
    print(f"  Success rate: {success_count/concurrent_count*100:.1f}%")
    print(f"  Mean duration: {statistics.mean(durations)*1000:.2f}ms")
    print(f"  95th percentile: {statistics.quantiles(durations, n=20)[18]*1000:.2f}ms")

    # Should handle concurrent requests well
    assert success_count / concurrent_count >= 0.90


# ============================================================================
# SUSTAINED LOAD TESTS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.stress
async def test_stress_sustained_load(stress_test):
    """Test system under sustained load"""

    duration_seconds = 30
    requests_per_second = 10
    total_requests = duration_seconds * requests_per_second

    start_time = time.time()
    results = []

    for i in range(total_requests):
        # Make request
        result = await stress_test.make_request("GET", "/health")
        results.append(result)

        # Calculate sleep time to maintain target RPS
        elapsed = time.time() - start_time
        target_time = (i + 1) / requests_per_second
        sleep_time = max(0, target_time - elapsed)
        await asyncio.sleep(sleep_time)

    total_time = time.time() - start_time
    success_count = sum(1 for r in results if r["success"])
    actual_rps = total_requests / total_time

    print(f"\nSustained load test:")
    print(f"  Duration: {total_time:.2f}s")
    print(f"  Total requests: {total_requests}")
    print(f"  Success rate: {success_count/total_requests*100:.1f}%")
    print(f"  Actual RPS: {actual_rps:.2f}")

    # Should maintain high success rate under sustained load
    assert success_count / total_requests >= 0.95


# ============================================================================
# CONNECTION POOL LIMITS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.stress
async def test_stress_connection_pool_limits(stress_test):
    """Test behavior at connection pool limits"""

    # Try to exceed typical pool size
    concurrent_count = 250

    responses = await stress_test.concurrent_requests(
        "GET", "/health", count=concurrent_count
    )

    success_count = sum(1 for r in responses if r["success"])
    error_types = {}

    for r in responses:
        if not r["success"]:
            error_type = type(r.get("error", "unknown")).__name__
            error_types[error_type] = error_types.get(error_type, 0) + 1

    print(f"\nConnection pool stress test:")
    print(f"  Concurrent requests: {concurrent_count}")
    print(f"  Success rate: {success_count/concurrent_count*100:.1f}%")
    if error_types:
        print(f"  Errors: {error_types}")

    # Should handle gracefully even if some fail
    assert success_count / concurrent_count >= 0.80


# ============================================================================
# MEMORY USAGE UNDER LOAD
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.stress
async def test_stress_memory_usage():
    """Monitor memory usage under load"""

    process = psutil.Process()

    # Baseline memory
    baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Create stress test instance
    stress_test = StressTest()
    await stress_test.setup()

    memory_samples = [baseline_memory]

    try:
        # Run requests and sample memory
        for i in range(10):
            # Burst of concurrent requests
            await stress_test.concurrent_requests(
                "GET", "/health", count=50
            )

            # Sample memory
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_samples.append(current_memory)

            await asyncio.sleep(1)

    finally:
        await stress_test.teardown()

    max_memory = max(memory_samples)
    memory_increase = max_memory - baseline_memory

    print(f"\nMemory usage under load:")
    print(f"  Baseline: {baseline_memory:.2f} MB")
    print(f"  Peak: {max_memory:.2f} MB")
    print(f"  Increase: {memory_increase:.2f} MB")

    # Memory increase should be reasonable
    assert memory_increase < 200  # Less than 200MB increase


# ============================================================================
# DATABASE CONNECTION LIMITS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.stress
async def test_stress_database_connections():
    """Test database connection pool under stress"""

    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import text

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://localhost:5432/nabavkidata"
    )

    # Create engine with known pool size
    engine = create_async_engine(
        db_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True
    )

    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async def make_query():
        """Execute simple query"""
        try:
            async with session_maker() as session:
                await session.execute(text("SELECT 1"))
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Try to exceed pool size
    concurrent_count = 50

    tasks = [make_query() for _ in range(concurrent_count)]
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r["success"])

    print(f"\nDatabase connection pool stress test:")
    print(f"  Concurrent queries: {concurrent_count}")
    print(f"  Pool size: 10, max overflow: 20")
    print(f"  Success rate: {success_count/concurrent_count*100:.1f}%")

    await engine.dispose()

    # Should handle up to pool_size + max_overflow
    assert success_count / concurrent_count >= 0.80


# ============================================================================
# GRADUAL RAMP-UP TEST
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.stress
async def test_stress_gradual_ramp_up(stress_test):
    """Test system with gradually increasing load"""

    ramp_levels = [5, 10, 25, 50, 100]
    results = {}

    for level in ramp_levels:
        responses = await stress_test.concurrent_requests(
            "GET", "/api/tenders", count=level,
            params={"page": 1, "size": 10}
        )

        success_count = sum(1 for r in responses if r["success"])
        durations = [r["duration"] for r in responses if r["success"]]

        results[level] = {
            "success_rate": success_count / level,
            "mean_duration": statistics.mean(durations) if durations else 0
        }

        # Small delay between ramp levels
        await asyncio.sleep(2)

    print("\nGradual ramp-up test results:")
    for level, stats in results.items():
        print(f"  {level} concurrent:")
        print(f"    Success: {stats['success_rate']*100:.1f}%")
        print(f"    Mean: {stats['mean_duration']*1000:.2f}ms")

    # All levels should maintain good success rate
    for stats in results.values():
        assert stats["success_rate"] >= 0.90


# ============================================================================
# BURST TRAFFIC TEST
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.stress
async def test_stress_burst_traffic(stress_test):
    """Test handling of sudden traffic bursts"""

    # Simulate burst pattern: quiet -> burst -> quiet -> burst
    patterns = [
        ("quiet", 5),
        ("burst", 100),
        ("quiet", 5),
        ("burst", 150),
        ("quiet", 5)
    ]

    results = []

    for pattern_type, count in patterns:
        responses = await stress_test.concurrent_requests(
            "GET", "/health", count=count
        )

        success_count = sum(1 for r in responses if r["success"])
        results.append({
            "pattern": pattern_type,
            "count": count,
            "success_rate": success_count / count
        })

        await asyncio.sleep(1)

    print("\nBurst traffic test:")
    for result in results:
        print(f"  {result['pattern']} ({result['count']} requests): "
              f"{result['success_rate']*100:.1f}% success")

    # All bursts should be handled
    for result in results:
        assert result["success_rate"] >= 0.85

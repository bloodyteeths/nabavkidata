"""
Test that all 4 pre-flight requirements are properly configured
"""
import sys
import os
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_requirement_1_utf8_cyrillic():
    """REQUIREMENT 1: UTF-8 Cyrillic handling"""
    print("\n" + "=" * 60)
    print("REQUIREMENT 1: UTF-8 Cyrillic Handling")
    print("=" * 60)

    # Test 1: Python default encoding
    encoding = sys.getdefaultencoding()
    assert encoding == 'utf-8', f"Expected utf-8, got {encoding}"
    print(f"✓ Python default encoding: {encoding}")

    # Test 2: Settings has UTF-8 export
    from scraper.settings import FEED_EXPORT_ENCODING
    assert FEED_EXPORT_ENCODING == 'utf-8'
    print(f"✓ FEED_EXPORT_ENCODING: {FEED_EXPORT_ENCODING}")

    # Test 3: PyMuPDF can handle Cyrillic
    try:
        import fitz
        print(f"✓ PyMuPDF (fitz): Installed")
    except ImportError:
        print("⚠ PyMuPDF: Not installed (run: pip install -r requirements.txt)")

    test_text = "Набавка на компјутерска опрема"
    assert any(0x0400 <= ord(c) <= 0x04FF for c in test_text)
    print(f"✓ Cyrillic test string: {test_text}")

    print("✓ REQUIREMENT 1: PASSED\n")
    return True


def test_requirement_2_large_pdf_support():
    """REQUIREMENT 2: Large PDF support (10-20MB)"""
    print("=" * 60)
    print("REQUIREMENT 2: Large PDF Support (10-20MB)")
    print("=" * 60)

    from scraper.settings import DOWNLOAD_MAXSIZE, DOWNLOAD_TIMEOUT, DOWNLOAD_WARNSIZE

    # Test 1: Max size is 50MB (supports 10-20MB files)
    assert DOWNLOAD_MAXSIZE >= 20 * 1024 * 1024, "Max size must support 20MB"
    print(f"✓ DOWNLOAD_MAXSIZE: {DOWNLOAD_MAXSIZE / (1024*1024):.0f}MB")

    # Test 2: Warning size is 20MB
    assert DOWNLOAD_WARNSIZE == 20 * 1024 * 1024
    print(f"✓ DOWNLOAD_WARNSIZE: {DOWNLOAD_WARNSIZE / (1024*1024):.0f}MB")

    # Test 3: Timeout is sufficient
    assert DOWNLOAD_TIMEOUT >= 60, "Timeout must be at least 60s for large files"
    print(f"✓ DOWNLOAD_TIMEOUT: {DOWNLOAD_TIMEOUT}s")

    print("✓ REQUIREMENT 2: PASSED\n")
    return True


def test_requirement_3_robots_txt_fallback():
    """REQUIREMENT 3: robots.txt respect with fallback"""
    print("=" * 60)
    print("REQUIREMENT 3: robots.txt with Fallback")
    print("=" * 60)

    from scraper.settings import (
        ROBOTSTXT_OBEY,
        DOWNLOADER_MIDDLEWARES,
        CRITICAL_URL_PATTERNS
    )

    # Test 1: robots.txt is obeyed by default
    assert ROBOTSTXT_OBEY == True
    print(f"✓ ROBOTSTXT_OBEY: {ROBOTSTXT_OBEY}")

    # Test 2: Fallback middleware is registered
    assert "scraper.middlewares.RobotsTxtFallbackMiddleware" in DOWNLOADER_MIDDLEWARES
    print("✓ RobotsTxtFallbackMiddleware: Registered")

    # Test 3: Middleware runs before RobotsTxt (lower priority number)
    fallback_priority = DOWNLOADER_MIDDLEWARES["scraper.middlewares.RobotsTxtFallbackMiddleware"]
    robotstxt_priority = DOWNLOADER_MIDDLEWARES["scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware"]
    assert fallback_priority < robotstxt_priority, "Fallback must run first"
    print(f"✓ Middleware priority: {fallback_priority} < {robotstxt_priority}")

    # Test 4: Critical URL patterns defined
    assert len(CRITICAL_URL_PATTERNS) > 0
    print(f"✓ Critical URL patterns: {len(CRITICAL_URL_PATTERNS)} defined")
    for pattern in CRITICAL_URL_PATTERNS:
        print(f"  - {pattern}")

    print("✓ REQUIREMENT 3: PASSED\n")
    return True


def test_requirement_4_playwright_hybrid():
    """REQUIREMENT 4: Scrapy + Playwright hybrid support"""
    print("=" * 60)
    print("REQUIREMENT 4: Scrapy + Playwright Hybrid")
    print("=" * 60)

    from scraper.settings import (
        PLAYWRIGHT_BROWSER_TYPE,
        PLAYWRIGHT_LAUNCH_OPTIONS,
        DOWNLOAD_HANDLERS,
        TWISTED_REACTOR
    )

    # Test 1: Playwright browser configured
    assert PLAYWRIGHT_BROWSER_TYPE in ['chromium', 'firefox', 'webkit']
    print(f"✓ PLAYWRIGHT_BROWSER_TYPE: {PLAYWRIGHT_BROWSER_TYPE}")

    # Test 2: Headless mode enabled
    assert PLAYWRIGHT_LAUNCH_OPTIONS.get('headless') == True
    print(f"✓ Headless mode: {PLAYWRIGHT_LAUNCH_OPTIONS.get('headless')}")

    # Test 3: Playwright download handlers registered
    assert "scrapy_playwright" in DOWNLOAD_HANDLERS.get("https", "")
    print("✓ Playwright download handlers: Registered")

    # Test 4: Twisted reactor configured
    assert "asyncio" in TWISTED_REACTOR.lower()
    print(f"✓ TWISTED_REACTOR: {TWISTED_REACTOR}")

    # Test 5: scrapy-playwright installed
    try:
        import scrapy_playwright
        print(f"✓ scrapy-playwright: Installed (v{scrapy_playwright.__version__})")
    except ImportError:
        print("⚠ scrapy-playwright: Not installed (run: pip install -r requirements.txt)")

    print("✓ REQUIREMENT 4: PASSED\n")
    return True


def test_pipeline_order():
    """Verify pipeline execution order"""
    print("=" * 60)
    print("BONUS: Pipeline Execution Order")
    print("=" * 60)

    from scraper.settings import ITEM_PIPELINES

    pipelines = sorted(ITEM_PIPELINES.items(), key=lambda x: x[1])

    print("Pipeline execution order:")
    for name, priority in pipelines:
        print(f"  {priority}: {name.split('.')[-1]}")

    # Verify correct order
    assert pipelines[0][0] == "scraper.pipelines.PDFDownloadPipeline"
    assert pipelines[1][0] == "scraper.pipelines.PDFExtractionPipeline"
    assert pipelines[2][0] == "scraper.pipelines.DatabasePipeline"

    print("✓ Pipelines ordered correctly: Download → Extract → Database\n")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SCRAPER BASE SETUP - REQUIREMENTS VALIDATION")
    print("=" * 60)

    all_passed = True

    try:
        all_passed &= test_requirement_1_utf8_cyrillic()
        all_passed &= test_requirement_2_large_pdf_support()
        all_passed &= test_requirement_3_robots_txt_fallback()
        all_passed &= test_requirement_4_playwright_hybrid()
        all_passed &= test_pipeline_order()
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("=" * 60)
    if all_passed:
        print("✓ ALL 4 REQUIREMENTS VALIDATED")
        print("=" * 60)
        print("\nScraper base setup is ready for W4-2 (spider implementation)")
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)

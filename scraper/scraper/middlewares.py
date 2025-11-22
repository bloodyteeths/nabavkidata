"""
Custom Scrapy middlewares
Includes: robots.txt fallback for critical URLs
"""
import re
import logging
from scrapy import signals
from scrapy.http import Request
from scrapy.exceptions import IgnoreRequest

logger = logging.getLogger(__name__)


class RobotsTxtFallbackMiddleware:
    """
    REQUIREMENT 3: robots.txt fallback strategy

    Allows bypassing robots.txt for critical public procurement URLs
    while still respecting it for general crawling.

    This middleware runs BEFORE RobotsTxtMiddleware (priority 85 vs 100).
    If a URL matches CRITICAL_URL_PATTERNS, it marks the request to bypass
    robots.txt checks.
    """

    def __init__(self, critical_patterns):
        self.critical_patterns = [re.compile(pattern) for pattern in critical_patterns]
        self.bypassed_urls = set()

    @classmethod
    def from_crawler(cls, crawler):
        # Get critical URL patterns from settings
        patterns = crawler.settings.getlist('CRITICAL_URL_PATTERNS', [])
        middleware = cls(critical_patterns=patterns)

        # Connect to spider_opened signal
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)

        return middleware

    def spider_opened(self, spider):
        logger.info(f"RobotsTxtFallbackMiddleware: Monitoring {len(self.critical_patterns)} critical URL patterns")

    def process_request(self, request, spider):
        """
        Check if URL matches critical patterns.
        If yes, mark it to bypass robots.txt.
        """
        url = request.url

        # Check if URL matches any critical pattern
        for pattern in self.critical_patterns:
            if pattern.search(url):
                # Mark request as critical (bypass robots.txt)
                request.meta['dont_obey_robotstxt'] = True

                # Log only once per unique URL
                if url not in self.bypassed_urls:
                    self.bypassed_urls.add(url)
                    logger.warning(
                        f"Critical URL detected - bypassing robots.txt: {url}"
                    )

                break

        return None  # Continue processing


class PlaywrightFallbackMiddleware:
    """
    REQUIREMENT 4: Scrapy + Playwright hybrid

    Automatically enables Playwright for pages that likely need JavaScript rendering.
    Falls back to plain Scrapy for static pages to save resources.
    """

    # URL patterns that typically need JavaScript rendering
    JS_PATTERNS = [
        r'/search',
        r'/filter',
        r'/dashboard',
        r'/api/',
    ]

    def __init__(self):
        self.js_patterns = [re.compile(pattern) for pattern in self.JS_PATTERNS]

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        """
        Enable Playwright for JavaScript-heavy pages if not already set.
        """
        # Skip if already configured
        if 'playwright' in request.meta:
            return None

        # Check if URL likely needs JavaScript
        url = request.url
        needs_js = any(pattern.search(url) for pattern in self.js_patterns)

        if needs_js:
            # Enable Playwright with default settings
            request.meta['playwright'] = True
            request.meta['playwright_include_page'] = True

            logger.debug(f"Enabling Playwright for: {url}")

        return None


class DownloadStatsMiddleware:
    """
    Track download statistics for large files (PDFs).
    Helps monitor REQUIREMENT 2: Large PDF support.
    """

    def __init__(self):
        self.stats = {
            'total_downloads': 0,
            'large_files': 0,  # > 10MB
            'failed_downloads': 0,
        }

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def process_response(self, request, response, spider):
        """Track successful downloads."""
        content_length = response.headers.get('Content-Length')

        if content_length:
            size_bytes = int(content_length)
            self.stats['total_downloads'] += 1

            # Track large files (> 10MB)
            if size_bytes > 10 * 1024 * 1024:
                self.stats['large_files'] += 1
                size_mb = size_bytes / (1024 * 1024)
                logger.info(
                    f"Large file downloaded: {size_mb:.2f}MB - {request.url}"
                )

        return response

    def process_exception(self, request, exception, spider):
        """Track failed downloads."""
        self.stats['failed_downloads'] += 1
        return None

    def spider_closed(self, spider):
        """Log statistics when spider closes."""
        logger.info("=" * 60)
        logger.info("Download Statistics:")
        logger.info(f"  Total downloads: {self.stats['total_downloads']}")
        logger.info(f"  Large files (>10MB): {self.stats['large_files']}")
        logger.info(f"  Failed downloads: {self.stats['failed_downloads']}")
        logger.info("=" * 60)

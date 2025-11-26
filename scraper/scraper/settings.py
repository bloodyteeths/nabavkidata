"""
Scrapy settings for nabavki scraper
Includes: UTF-8 Cyrillic, large PDF support, robots.txt fallback, Playwright integration
"""

import os
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

BOT_NAME = "nabavki_scraper"
SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"

# ============================================================================
# REQUIREMENT 1: UTF-8 CYRILLIC HANDLING
# ============================================================================
# Python 3 defaults to UTF-8, but enforce it explicitly
FEED_EXPORT_ENCODING = "utf-8"

# ============================================================================
# REQUIREMENT 2: LARGE PDF SUPPORT (10-20MB)
# ============================================================================
# Default is 1GB, but set explicit limits
DOWNLOAD_MAXSIZE = 52428800  # 50MB max file size
DOWNLOAD_WARNSIZE = 20971520  # 20MB warning threshold
DOWNLOAD_TIMEOUT = 180  # 3 minutes for large files

# Enable media pipeline for file downloads
FILES_STORE = "downloads/files"  # Local storage path
MEDIA_ALLOW_REDIRECTS = True

# ============================================================================
# REQUIREMENT 3: ROBOTS.TXT WITH FALLBACK
# ============================================================================
# Respect robots.txt by default
ROBOTSTXT_OBEY = True

# Custom middleware for critical URL fallback (order matters)
# Lower numbers = higher priority
DOWNLOADER_MIDDLEWARES = {
    "scraper.middlewares.RobotsTxtFallbackMiddleware": 85,  # Before RobotsTxt
    "scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware": 100,
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": 90,
    "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware": 110,
}

# Critical URLs that should bypass robots.txt if necessary
# (Only for legitimate public procurement data)
CRITICAL_URL_PATTERNS = [
    r"e-nabavki\.gov\.mk/.*tender",
    r"e-nabavki\.gov\.mk/.*document",
]

# ============================================================================
# REQUIREMENT 4: SCRAPY + PLAYWRIGHT HYBRID
# ============================================================================
# Enable Playwright for JavaScript-heavy pages (Angular SPA)
PLAYWRIGHT_BROWSER_TYPE = "chromium"

# ENHANCED: Improved launch options for stability
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-blink-features=AutomationControlled',  # Avoid detection
    ]
}

# ENHANCED: Increased timeout for slow-loading Angular pages
# Increased from 60s to 120s due to slow e-nabavki.gov.mk responses
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 120000  # 120 seconds (was 60s)

# Force Playwright for all e-nabavki.gov.mk requests
PLAYWRIGHT_PROCESS_REQUEST_HEADERS = None

# Add Playwright download handlers
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Required for Playwright async support
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Playwright contexts configuration
PLAYWRIGHT_CONTEXTS = {
    'default': {
        'viewport': {'width': 1920, 'height': 1080},
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'locale': 'mk-MK',  # Macedonian locale
        'timezone_id': 'Europe/Skopje',
    }
}

# ============================================================================
# RATE LIMITING & POLITENESS
# ============================================================================
# Configure maximum concurrent requests
CONCURRENT_REQUESTS = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1

# Configure delays (1 second minimum)
DOWNLOAD_DELAY = 1.0
RANDOMIZE_DOWNLOAD_DELAY = True

# AutoThrottle for adaptive throttling
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 3.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False

# ============================================================================
# REQUEST HEADERS
# ============================================================================
# Disable cookies (stateless scraping)
COOKIES_ENABLED = False

# Override the default request headers
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "mk,en",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Charset": "utf-8",
    "User-Agent": "Mozilla/5.0 (compatible; nabavkidata-bot/1.0; +https://nabavkidata.com/bot)",
}

# ============================================================================
# ITEM PIPELINES
# ============================================================================
ITEM_PIPELINES = {
    "scraper.pipelines.PDFDownloadPipeline": 100,  # Download PDFs first
    "scraper.pipelines.PDFExtractionPipeline": 200,  # Extract text from PDFs
    "scraper.pipelines.DataValidationPipeline": 250,  # Validate data before DB
    "scraper.pipelines.DatabasePipeline": 300,  # Save to database last
}

# ============================================================================
# RETRY & ERROR HANDLING
# ============================================================================
RETRY_ENABLED = True
RETRY_TIMES = 5  # Increased from 3 to 5 for better resilience
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]  # Include 403 for retry

# Additional retry settings for slow website
RETRY_PRIORITY_ADJUST = -1
DOWNLOAD_FAIL_ON_DATALOSS = False  # Don't fail on partial downloads

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_ENCODING = "utf-8"

# ============================================================================
# EXTENSIONS
# ============================================================================
EXTENSIONS = {
    "scrapy.extensions.telnet.TelnetConsole": None,  # Disable telnet
    "scrapy.extensions.logstats.LogStats": 500,
}

# ============================================================================
# DNS CACHE
# ============================================================================
DNSCACHE_ENABLED = True
DNSCACHE_SIZE = 10000

# ============================================================================
# HTTP CACHE (for development/testing)
# ============================================================================
# HTTPCACHE_ENABLED = True
# HTTPCACHE_EXPIRATION_SECS = 0
# HTTPCACHE_DIR = "httpcache"
# HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504]

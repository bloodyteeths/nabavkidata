"""
E-Nabavki Research Agent for Corruption Detection

This agent fetches OFFICIAL data directly from e-nabavki.gov.mk portal -
the authoritative source for Macedonian public procurement.

CRITICAL: When there's a discrepancy between our database and e-nabavki.gov.mk,
the official source (e-nabavki) ALWAYS wins. Our database may have incomplete
bidder data due to scraping limitations.

Key URLs:
- Tender details: https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/{tender_id}/basic-info
- Bidders: https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/{tender_id}/bidders
- Documents: https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/{tender_id}/documents
- Award decision: https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/{tender_id}/award

Author: nabavkidata.com
License: Proprietary
"""

import asyncio
import aiohttp
import logging
import json
import re
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
from urllib.parse import urlencode, quote

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TenderDetails:
    """Official tender details from e-nabavki"""
    tender_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    procuring_entity: Optional[str] = None
    estimated_value_mkd: Optional[float] = None
    estimated_value_eur: Optional[float] = None
    cpv_codes: List[str] = field(default_factory=list)
    deadline: Optional[str] = None
    procedure_type: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    publication_date: Optional[str] = None
    source_url: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    raw_data: Dict = field(default_factory=dict)


@dataclass
class BidderInfo:
    """Bidder information from official source"""
    company_name: str
    bid_amount_mkd: Optional[float] = None
    bid_amount_eur: Optional[float] = None
    rank: Optional[int] = None
    is_winner: bool = False
    disqualified: bool = False
    disqualification_reason: Optional[str] = None


@dataclass
class OfficialBidderData:
    """Complete bidder data from e-nabavki"""
    tender_id: str
    total_bidders: int
    bidders: List[BidderInfo] = field(default_factory=list)
    winner_name: Optional[str] = None
    winner_bid_amount: Optional[float] = None
    source_url: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class AwardDecision:
    """Official award decision data"""
    tender_id: str
    winner_name: Optional[str] = None
    award_amount_mkd: Optional[float] = None
    award_amount_eur: Optional[float] = None
    award_date: Optional[str] = None
    decision_document_url: Optional[str] = None
    has_protests: bool = False
    protest_details: Optional[str] = None
    source_url: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class DocumentInfo:
    """Document metadata from official source"""
    file_name: str
    url: str
    doc_type: str  # 'technical_specs', 'contract', 'award_decision', etc.
    upload_date: Optional[str] = None
    file_id: Optional[str] = None


@dataclass
class OfficialDocuments:
    """All documents for a tender from e-nabavki"""
    tender_id: str
    documents: List[DocumentInfo] = field(default_factory=list)
    total_count: int = 0
    source_url: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class DataDiscrepancy:
    """Represents a discrepancy between our DB and official source"""
    field_name: str
    our_value: Any
    official_value: Any
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str


@dataclass
class VerificationResult:
    """Result of verifying our data against official source"""
    tender_id: str
    is_verified: bool
    discrepancies: List[DataDiscrepancy] = field(default_factory=list)
    official_data: Dict = field(default_factory=dict)
    our_data: Dict = field(default_factory=dict)
    verification_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# =============================================================================
# CACHE IMPLEMENTATION
# =============================================================================

class TTLCache:
    """Simple TTL cache for API responses"""

    def __init__(self, default_ttl: int = 3600):
        """
        Initialize cache with default TTL in seconds.

        Args:
            default_ttl: Default time-to-live in seconds (default: 1 hour)
        """
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self.default_ttl = default_ttl
        self._lock = asyncio.Lock()

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a unique cache key"""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        async with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if datetime.utcnow() < expiry:
                    logger.debug(f"Cache hit for key: {key[:16]}...")
                    return value
                else:
                    # Expired, remove from cache
                    del self._cache[key]
                    logger.debug(f"Cache expired for key: {key[:16]}...")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        async with self._lock:
            expiry = datetime.utcnow() + timedelta(seconds=ttl or self.default_ttl)
            self._cache[key] = (value, expiry)
            logger.debug(f"Cache set for key: {key[:16]}...")

    async def invalidate(self, key: str) -> None:
        """Invalidate a specific cache entry"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]

    async def clear(self) -> None:
        """Clear all cache entries"""
        async with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")

    async def cleanup_expired(self) -> int:
        """Remove all expired entries and return count removed"""
        async with self._lock:
            now = datetime.utcnow()
            expired_keys = [
                key for key, (_, expiry) in self._cache.items()
                if now >= expiry
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)


# =============================================================================
# RATE LIMITER
# =============================================================================

class RateLimiter:
    """
    Token bucket rate limiter for API requests.
    Prevents overwhelming the e-nabavki servers.
    """

    def __init__(self, requests_per_second: float = 2.0, burst_size: int = 5):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Sustained request rate
            burst_size: Maximum burst of requests allowed
        """
        self.rate = requests_per_second
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_update = datetime.utcnow()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request token is available"""
        async with self._lock:
            now = datetime.utcnow()
            elapsed = (now - self.last_update).total_seconds()

            # Replenish tokens based on elapsed time
            self.tokens = min(
                self.burst_size,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now

            if self.tokens < 1:
                # Need to wait for tokens
                wait_time = (1 - self.tokens) / self.rate
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self.tokens = 1

            self.tokens -= 1


# =============================================================================
# MAIN AGENT CLASS
# =============================================================================

class ENabavkiAgent:
    """
    Agent for fetching official data from e-nabavki.gov.mk portal.

    This agent is the SOURCE OF TRUTH for Macedonian public procurement data.
    When discrepancies exist between our database and this source, the
    official source wins.

    Features:
    - Async HTTP requests with aiohttp
    - Built-in caching to reduce API load
    - Rate limiting to be a good citizen
    - Comprehensive error handling
    - Data verification against our database
    """

    # Base URLs for e-nabavki portal
    BASE_URL = "https://e-nabavki.gov.mk"
    PUBLIC_ACCESS_URL = f"{BASE_URL}/PublicAccess/home.aspx"

    # API endpoints (discovered from spider analysis)
    # The site uses Angular with hash-based routing
    ROUTES = {
        'basic_info': '#/dossie/{tender_id}/basic-info',
        'bidders': '#/dossie/{tender_id}/bidders',
        'documents': '#/dossie/{tender_id}/documents',
        'award': '#/dossie/{tender_id}/award',
        'dossie_acpp': '#/dossie-acpp/{dossier_uuid}',  # For contract notices
    }

    # API endpoints that may return JSON directly
    # (Need to discover these through network analysis)
    API_ENDPOINTS = {
        'search': '/api/public/search',
        'tender_details': '/api/public/tender/{tender_id}',
        'institution_search': '/api/public/institutions/search',
    }

    # HTTP headers to mimic browser requests
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'mk-MK,mk;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
    }

    # XPath selectors for data extraction (from spider analysis)
    FIELD_XPATHS = {
        'tender_id': [
            '//label[@label-for="PROCESS NUMBER FOR NOTIFICATION DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
            '//label[@label-for="ANNOUNCEMENT NUMBER DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
        ],
        'title': [
            '//label[@label-for="SUBJECT:"]/following-sibling::label[contains(@class, "dosie-value")][1]',
        ],
        'procuring_entity': [
            '//label[@label-for="CONTRACTING INSTITUTION NAME DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
            '//label[@label-for="CONTRACTING AUTHORITY NAME DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
        ],
        'num_bidders': [
            '//label[@label-for="NUMBER OF OFFERS DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
        ],
        'winner': [
            '//label[@label-for="NAME OF CONTACT OF PROCUREMENT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
            '//label[@label-for="WINNER NAME DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
        ],
    }

    def __init__(
        self,
        cache_ttl: int = 3600,
        requests_per_second: float = 2.0,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """
        Initialize the E-Nabavki agent.

        Args:
            cache_ttl: Cache TTL in seconds (default: 1 hour)
            requests_per_second: Rate limit for requests
            max_retries: Maximum retry attempts for failed requests
            timeout: HTTP request timeout in seconds
        """
        self.cache = TTLCache(default_ttl=cache_ttl)
        self.rate_limiter = RateLimiter(requests_per_second=requests_per_second)
        self.max_retries = max_retries
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers=self.DEFAULT_HEADERS
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    # =========================================================================
    # CORE HTTP METHODS
    # =========================================================================

    async def _fetch_with_retry(
        self,
        url: str,
        method: str = 'GET',
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Tuple[Optional[str], int]:
        """
        Fetch URL with retry logic and rate limiting.

        Args:
            url: URL to fetch
            method: HTTP method
            params: Query parameters
            data: POST data
            headers: Additional headers

        Returns:
            Tuple of (response_text, status_code)
        """
        session = await self._get_session()
        merged_headers = {**self.DEFAULT_HEADERS, **(headers or {})}

        for attempt in range(self.max_retries):
            try:
                await self.rate_limiter.acquire()

                async with session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=merged_headers
                ) as response:
                    text = await response.text()

                    if response.status == 200:
                        return text, response.status
                    elif response.status == 429:
                        # Rate limited, wait longer
                        wait_time = 2 ** (attempt + 1)
                        logger.warning(f"Rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    elif response.status >= 500:
                        # Server error, retry
                        logger.warning(f"Server error {response.status}, retry {attempt + 1}/{self.max_retries}")
                        await asyncio.sleep(1)
                    else:
                        logger.error(f"HTTP {response.status} for {url}")
                        return text, response.status

            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching {url}, retry {attempt + 1}/{self.max_retries}")
                await asyncio.sleep(1)
            except aiohttp.ClientError as e:
                logger.error(f"Client error fetching {url}: {e}")
                await asyncio.sleep(1)

        return None, 0

    async def _fetch_page(self, tender_id: str, section: str = 'basic-info') -> Optional[str]:
        """
        Fetch a tender page section.

        Note: e-nabavki uses Angular with hash-based routing. The actual data
        is loaded via JavaScript. For static scraping, we need to either:
        1. Find the underlying API endpoints
        2. Use a headless browser (Playwright/Selenium)
        3. Parse whatever static content is available

        Args:
            tender_id: Tender ID (e.g., "12345/2024")
            section: Page section ('basic-info', 'bidders', 'documents', 'award')

        Returns:
            HTML content or None
        """
        # Generate cache key
        cache_key = self.cache._generate_key('page', tender_id, section)

        # Check cache
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # Build URL
        url = f"{self.PUBLIC_ACCESS_URL}#/dossie/{quote(tender_id)}/{section}"

        logger.info(f"Fetching {section} for tender {tender_id}")

        content, status = await self._fetch_with_retry(url)

        if content and status == 200:
            await self.cache.set(cache_key, content)
            return content

        return None

    # =========================================================================
    # PARSING METHODS
    # =========================================================================

    def _parse_currency(self, value_str: str) -> Optional[float]:
        """Parse currency string to float"""
        if not value_str:
            return None

        # Remove non-numeric characters except . and ,
        cleaned = re.sub(r'[^\d.,\-]', '', value_str.strip())

        if not cleaned:
            return None

        try:
            # European format: 1.234.567,89
            if '.' in cleaned and ',' in cleaned:
                cleaned = cleaned.replace('.', '').replace(',', '.')
            elif ',' in cleaned:
                cleaned = cleaned.replace(',', '.')

            return float(cleaned)
        except ValueError:
            return None

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to ISO format"""
        if not date_str:
            return None

        date_str = date_str.strip()

        # Common date formats on e-nabavki
        formats = [
            '%d.%m.%Y',
            '%d.%m.%Y %H:%M',
            '%d/%m/%Y',
            '%Y-%m-%d',
            '%d-%m-%Y',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue

        return None

    def _extract_cpv_codes(self, html: str) -> List[str]:
        """Extract CPV codes from HTML content"""
        # CPV codes are 8-digit codes, optionally with -digit suffix
        pattern = r'\b(\d{8}(?:-\d)?)\b'
        matches = re.findall(pattern, html)

        # Filter valid CPV codes (divisions 01-98)
        valid_codes = []
        for match in matches:
            try:
                division = int(match[:2])
                if 1 <= division <= 98 and match not in valid_codes:
                    valid_codes.append(match)
            except ValueError:
                continue

        return valid_codes

    def _extract_json_from_ng_click(self, html: str) -> List[Dict]:
        """Extract document JSON from ng-click attributes"""
        documents = []

        # Pattern for PreviewDocumentConfirm({...})
        pattern = re.compile(r'PreviewDocumentConfirm\((\{.*?\})\)', re.DOTALL)

        for match in pattern.finditer(html):
            try:
                json_str = match.group(1)
                doc_data = json.loads(json_str)
                documents.append(doc_data)
            except json.JSONDecodeError:
                continue

        return documents

    # =========================================================================
    # PUBLIC API METHODS
    # =========================================================================

    async def get_tender_details(self, tender_id: str) -> TenderDetails:
        """
        Fetch official tender details from e-nabavki.

        Args:
            tender_id: Tender ID (e.g., "12345/2024")

        Returns:
            TenderDetails dataclass with official data
        """
        # Check cache first
        cache_key = self.cache._generate_key('tender_details', tender_id)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # Build the tender URL
        source_url = f"{self.PUBLIC_ACCESS_URL}#/dossie/{quote(tender_id)}/basic-info"

        # Note: Since e-nabavki is JavaScript-heavy, we'll try multiple approaches

        # Approach 1: Try to find an API endpoint
        # Based on spider analysis, there might be underlying APIs
        api_attempts = [
            f"{self.BASE_URL}/api/public/tender/{quote(tender_id)}",
            f"{self.BASE_URL}/api/dossie/{quote(tender_id)}",
            f"{self.BASE_URL}/PublicAccess/api/tender/{quote(tender_id)}",
        ]

        for api_url in api_attempts:
            try:
                content, status = await self._fetch_with_retry(
                    api_url,
                    headers={'Accept': 'application/json'}
                )
                if content and status == 200:
                    try:
                        data = json.loads(content)
                        # Parse API response
                        result = TenderDetails(
                            tender_id=tender_id,
                            title=data.get('title') or data.get('subject'),
                            description=data.get('description'),
                            procuring_entity=data.get('contractingAuthority') or data.get('procuringEntity'),
                            estimated_value_mkd=self._parse_currency(str(data.get('estimatedValue', ''))),
                            cpv_codes=data.get('cpvCodes', []),
                            deadline=self._parse_date(data.get('deadline', '')),
                            procedure_type=data.get('procedureType'),
                            status=data.get('status'),
                            category=data.get('category'),
                            publication_date=self._parse_date(data.get('publicationDate', '')),
                            source_url=source_url,
                            raw_data=data
                        )
                        await self.cache.set(cache_key, result)
                        return result
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                logger.debug(f"API attempt failed for {api_url}: {e}")

        # Approach 2: Fetch HTML page and parse static content
        # This may have limited data since content is loaded via JavaScript
        content = await self._fetch_page(tender_id, 'basic-info')

        result = TenderDetails(
            tender_id=tender_id,
            source_url=source_url,
            cpv_codes=self._extract_cpv_codes(content) if content else []
        )

        if content:
            result.raw_data = {'html_length': len(content)}

            # Try to extract any static content
            # Note: Most content requires JavaScript rendering

            # Extract CPV codes (these might be in static HTML)
            result.cpv_codes = self._extract_cpv_codes(content)

        await self.cache.set(cache_key, result)
        return result

    async def get_official_bidder_count(self, tender_id: str) -> OfficialBidderData:
        """
        CRITICAL: Get the ACTUAL number of bidders from official source.

        This is essential for corruption detection - our database may have
        incomplete bidder data due to scraping limitations. The official
        bidder count from e-nabavki is the SOURCE OF TRUTH.

        Args:
            tender_id: Tender ID (e.g., "12345/2024")

        Returns:
            OfficialBidderData with total bidders count and details
        """
        # Check cache first
        cache_key = self.cache._generate_key('bidder_count', tender_id)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        source_url = f"{self.PUBLIC_ACCESS_URL}#/dossie/{quote(tender_id)}/bidders"

        # Try API endpoints first
        api_attempts = [
            f"{self.BASE_URL}/api/public/tender/{quote(tender_id)}/bidders",
            f"{self.BASE_URL}/api/dossie/{quote(tender_id)}/bidders",
            f"{self.BASE_URL}/api/public/tender/{quote(tender_id)}/offers",
        ]

        for api_url in api_attempts:
            try:
                content, status = await self._fetch_with_retry(
                    api_url,
                    headers={'Accept': 'application/json'}
                )
                if content and status == 200:
                    try:
                        data = json.loads(content)

                        # Parse bidders from API response
                        bidders = []
                        bidder_list = data.get('bidders', data.get('offers', []))

                        for idx, b in enumerate(bidder_list, 1):
                            bidders.append(BidderInfo(
                                company_name=b.get('companyName', b.get('name', 'Unknown')),
                                bid_amount_mkd=self._parse_currency(str(b.get('bidAmount', ''))),
                                rank=b.get('rank', idx),
                                is_winner=b.get('isWinner', False),
                                disqualified=b.get('disqualified', False),
                                disqualification_reason=b.get('disqualificationReason')
                            ))

                        # Find winner
                        winner = next((b for b in bidders if b.is_winner), None)

                        result = OfficialBidderData(
                            tender_id=tender_id,
                            total_bidders=len(bidders),
                            bidders=bidders,
                            winner_name=winner.company_name if winner else None,
                            winner_bid_amount=winner.bid_amount_mkd if winner else None,
                            source_url=source_url
                        )

                        await self.cache.set(cache_key, result)
                        return result

                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                logger.debug(f"Bidder API attempt failed for {api_url}: {e}")

        # Fallback: Try to get basic info page which may contain num_bidders
        content = await self._fetch_page(tender_id, 'basic-info')

        result = OfficialBidderData(
            tender_id=tender_id,
            total_bidders=0,
            source_url=source_url
        )

        if content:
            # Try to extract num_bidders from static content
            # Pattern: NUMBER OF OFFERS DOSSIE followed by value
            num_pattern = re.search(
                r'NUMBER OF OFFERS[^>]*>.*?(\d+)',
                content,
                re.IGNORECASE | re.DOTALL
            )
            if num_pattern:
                result.total_bidders = int(num_pattern.group(1))

        await self.cache.set(cache_key, result)
        return result

    async def get_award_decision(self, tender_id: str) -> AwardDecision:
        """
        Get the official award decision from e-nabavki.

        Args:
            tender_id: Tender ID (e.g., "12345/2024")

        Returns:
            AwardDecision with winner info and decision details
        """
        # Check cache first
        cache_key = self.cache._generate_key('award_decision', tender_id)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        source_url = f"{self.PUBLIC_ACCESS_URL}#/dossie/{quote(tender_id)}/award"

        # Try API endpoints
        api_attempts = [
            f"{self.BASE_URL}/api/public/tender/{quote(tender_id)}/award",
            f"{self.BASE_URL}/api/dossie/{quote(tender_id)}/award",
            f"{self.BASE_URL}/api/public/tender/{quote(tender_id)}/decision",
        ]

        for api_url in api_attempts:
            try:
                content, status = await self._fetch_with_retry(
                    api_url,
                    headers={'Accept': 'application/json'}
                )
                if content and status == 200:
                    try:
                        data = json.loads(content)

                        result = AwardDecision(
                            tender_id=tender_id,
                            winner_name=data.get('winnerName') or data.get('selectedBidder'),
                            award_amount_mkd=self._parse_currency(str(data.get('awardAmount', ''))),
                            award_date=self._parse_date(data.get('awardDate', '')),
                            decision_document_url=data.get('decisionUrl'),
                            has_protests=data.get('hasProtests', False),
                            protest_details=data.get('protestDetails'),
                            source_url=source_url
                        )

                        await self.cache.set(cache_key, result)
                        return result

                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                logger.debug(f"Award API attempt failed for {api_url}: {e}")

        # Fallback with empty result
        result = AwardDecision(tender_id=tender_id, source_url=source_url)
        await self.cache.set(cache_key, result)
        return result

    async def get_all_documents(self, tender_id: str) -> OfficialDocuments:
        """
        List all official documents for a tender.

        Args:
            tender_id: Tender ID (e.g., "12345/2024")

        Returns:
            OfficialDocuments with list of all available documents
        """
        # Check cache first
        cache_key = self.cache._generate_key('documents', tender_id)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        source_url = f"{self.PUBLIC_ACCESS_URL}#/dossie/{quote(tender_id)}/documents"

        # Try API endpoints
        api_attempts = [
            f"{self.BASE_URL}/api/public/tender/{quote(tender_id)}/documents",
            f"{self.BASE_URL}/api/dossie/{quote(tender_id)}/documents",
            f"{self.BASE_URL}/api/public/tender/{quote(tender_id)}/attachments",
        ]

        for api_url in api_attempts:
            try:
                content, status = await self._fetch_with_retry(
                    api_url,
                    headers={'Accept': 'application/json'}
                )
                if content and status == 200:
                    try:
                        data = json.loads(content)

                        documents = []
                        doc_list = data.get('documents', data.get('attachments', []))

                        for doc in doc_list:
                            doc_type = self._categorize_document(doc.get('fileName', ''))

                            documents.append(DocumentInfo(
                                file_name=doc.get('fileName', 'Unknown'),
                                url=doc.get('url') or doc.get('downloadUrl', ''),
                                doc_type=doc_type,
                                upload_date=self._parse_date(doc.get('uploadDate', '')),
                                file_id=doc.get('fileId')
                            ))

                        result = OfficialDocuments(
                            tender_id=tender_id,
                            documents=documents,
                            total_count=len(documents),
                            source_url=source_url
                        )

                        await self.cache.set(cache_key, result)
                        return result

                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                logger.debug(f"Documents API attempt failed for {api_url}: {e}")

        # Try fetching HTML and parsing ng-click documents
        content = await self._fetch_page(tender_id, 'documents')
        documents = []

        if content:
            # Extract documents from ng-click attributes
            doc_data = self._extract_json_from_ng_click(content)

            for doc in doc_data:
                doc_url = doc.get('DocumentUrl', '')
                doc_name = doc.get('DocumentName', 'Unknown')
                file_id = doc.get('FileId', '')

                if doc_url:
                    if doc_url.startswith('/'):
                        doc_url = f"{self.BASE_URL}{doc_url}"

                    documents.append(DocumentInfo(
                        file_name=doc_name,
                        url=doc_url,
                        doc_type=self._categorize_document(doc_name),
                        file_id=file_id
                    ))

            # Also look for direct download links
            download_patterns = [
                r'href="([^"]*(?:Download|File)[^"]*)"',
                r'href="([^"]*\.pdf[^"]*)"',
                r'href="([^"]*\.docx?[^"]*)"',
                r'href="([^"]*\.xlsx?[^"]*)"',
            ]

            seen_urls = {d.url for d in documents}

            for pattern in download_patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    url = match.group(1)
                    if url not in seen_urls:
                        if url.startswith('/'):
                            url = f"{self.BASE_URL}{url}"

                        # Extract filename from URL
                        file_name = url.split('/')[-1].split('?')[0] or 'document.pdf'

                        documents.append(DocumentInfo(
                            file_name=file_name,
                            url=url,
                            doc_type=self._categorize_document(file_name)
                        ))
                        seen_urls.add(url)

        result = OfficialDocuments(
            tender_id=tender_id,
            documents=documents,
            total_count=len(documents),
            source_url=source_url
        )

        await self.cache.set(cache_key, result)
        return result

    def _categorize_document(self, filename: str) -> str:
        """Categorize document based on filename patterns"""
        filename_lower = filename.lower()

        # Technical specifications
        if any(kw in filename_lower for kw in [
            'technical', 'spec', 'tech', 'specs'
        ]):
            return 'technical_specs'

        # Award decision
        if any(kw in filename_lower for kw in [
            'decision', 'award', 'winner', 'result'
        ]):
            return 'award_decision'

        # Contract
        if any(kw in filename_lower for kw in [
            'contract', 'agreement'
        ]):
            return 'contract'

        # Amendment
        if any(kw in filename_lower for kw in [
            'amendment', 'addendum', 'modification'
        ]):
            return 'amendment'

        # Clarification
        if any(kw in filename_lower for kw in [
            'clarification', 'question', 'answer', 'q&a', 'qa'
        ]):
            return 'clarification'

        # Tender documentation
        if any(kw in filename_lower for kw in [
            'tender', 'documentation', 'notice'
        ]):
            return 'tender_docs'

        return 'other'

    async def search_institution_tenders(
        self,
        institution_name: str,
        year: Optional[int] = None,
        status: Optional[str] = None
    ) -> Dict:
        """
        Search e-nabavki for all tenders by an institution.

        Args:
            institution_name: Name of the procuring entity
            year: Optional year filter
            status: Optional status filter ('active', 'awarded', 'cancelled')

        Returns:
            Dict with search results and tender list
        """
        # Check cache
        cache_key = self.cache._generate_key('institution_search', institution_name, year, status)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        result = {
            'institution': institution_name,
            'year': year,
            'status': status,
            'tenders': [],
            'total_count': 0,
            'search_url': None,
            'fetched_at': datetime.utcnow().isoformat()
        }

        # Try search API
        search_apis = [
            f"{self.BASE_URL}/api/public/search",
            f"{self.BASE_URL}/api/public/tenders/search",
        ]

        search_params = {
            'contractingAuthority': institution_name,
            'q': institution_name,
        }

        if year:
            search_params['year'] = year
        if status:
            search_params['status'] = status

        for api_url in search_apis:
            try:
                content, http_status = await self._fetch_with_retry(
                    api_url,
                    params=search_params,
                    headers={'Accept': 'application/json'}
                )

                if content and http_status == 200:
                    try:
                        data = json.loads(content)

                        tenders = data.get('results', data.get('tenders', []))
                        result['tenders'] = tenders
                        result['total_count'] = data.get('totalCount', len(tenders))
                        result['search_url'] = api_url

                        await self.cache.set(cache_key, result)
                        return result

                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                logger.debug(f"Search API failed for {api_url}: {e}")

        # Fallback: build search URL for manual access
        search_url = f"{self.PUBLIC_ACCESS_URL}#/notices?search={quote(institution_name)}"
        if year:
            search_url += f"&year={year}"

        result['search_url'] = search_url

        await self.cache.set(cache_key, result)
        return result

    async def verify_tender_data(
        self,
        tender_id: str,
        our_data: Dict
    ) -> VerificationResult:
        """
        Compare our database data with official source.

        CRITICAL: This is essential for corruption detection.
        The official source is ALWAYS the source of truth.

        Args:
            tender_id: Tender ID to verify
            our_data: Dict with our database values for comparison

        Returns:
            VerificationResult with list of discrepancies
        """
        discrepancies = []

        # Fetch official data
        logger.info(f"Verifying tender {tender_id} against official source")

        # Get official tender details
        official_details = await self.get_tender_details(tender_id)
        official_bidders = await self.get_official_bidder_count(tender_id)
        official_award = await self.get_award_decision(tender_id)

        official_data = {
            'tender_id': tender_id,
            'details': asdict(official_details),
            'bidders': asdict(official_bidders),
            'award': asdict(official_award)
        }

        # Compare bidder count (CRITICAL for corruption detection)
        our_bidder_count = our_data.get('num_bidders')
        official_bidder_count = official_bidders.total_bidders

        if our_bidder_count is not None and official_bidder_count > 0:
            if our_bidder_count != official_bidder_count:
                severity = 'critical' if abs(our_bidder_count - official_bidder_count) > 2 else 'high'

                discrepancies.append(DataDiscrepancy(
                    field_name='num_bidders',
                    our_value=our_bidder_count,
                    official_value=official_bidder_count,
                    severity=severity,
                    description=f"Bidder count mismatch: Our DB shows {our_bidder_count} bidders, "
                               f"but official source shows {official_bidder_count}. "
                               f"Official source is authoritative."
                ))

        # Compare winner name
        our_winner = our_data.get('winner')
        official_winner = official_award.winner_name or official_bidders.winner_name

        if our_winner and official_winner:
            # Normalize names for comparison
            our_winner_norm = our_winner.lower().strip()
            official_winner_norm = official_winner.lower().strip()

            if our_winner_norm != official_winner_norm:
                discrepancies.append(DataDiscrepancy(
                    field_name='winner',
                    our_value=our_winner,
                    official_value=official_winner,
                    severity='high',
                    description=f"Winner name mismatch: Our DB shows '{our_winner}', "
                               f"but official source shows '{official_winner}'."
                ))

        # Compare estimated value
        our_value = our_data.get('estimated_value_mkd')
        official_value = official_details.estimated_value_mkd

        if our_value and official_value:
            # Allow 1% tolerance for rounding
            if abs(our_value - official_value) / official_value > 0.01:
                discrepancies.append(DataDiscrepancy(
                    field_name='estimated_value_mkd',
                    our_value=our_value,
                    official_value=official_value,
                    severity='medium',
                    description=f"Value mismatch: Our DB shows {our_value:,.0f} MKD, "
                               f"official shows {official_value:,.0f} MKD."
                ))

        # Compare status
        our_status = our_data.get('status')
        official_status = official_details.status

        if our_status and official_status:
            if our_status.lower() != official_status.lower():
                discrepancies.append(DataDiscrepancy(
                    field_name='status',
                    our_value=our_status,
                    official_value=official_status,
                    severity='medium',
                    description=f"Status mismatch: Our DB shows '{our_status}', "
                               f"official shows '{official_status}'."
                ))

        # Check for missing bidders in our data
        if official_bidders.bidders and our_data.get('bidders_data'):
            our_bidder_names = set()
            try:
                our_bidders = json.loads(our_data['bidders_data']) if isinstance(our_data['bidders_data'], str) else our_data['bidders_data']
                our_bidder_names = {b.get('company_name', '').lower().strip() for b in our_bidders if b.get('company_name')}
            except (json.JSONDecodeError, TypeError):
                pass

            official_bidder_names = {b.company_name.lower().strip() for b in official_bidders.bidders if b.company_name}

            missing_bidders = official_bidder_names - our_bidder_names
            if missing_bidders:
                discrepancies.append(DataDiscrepancy(
                    field_name='missing_bidders',
                    our_value=list(our_bidder_names),
                    official_value=list(official_bidder_names),
                    severity='high',
                    description=f"Missing bidders in our DB: {missing_bidders}"
                ))

        is_verified = len(discrepancies) == 0

        result = VerificationResult(
            tender_id=tender_id,
            is_verified=is_verified,
            discrepancies=discrepancies,
            official_data=official_data,
            our_data=our_data
        )

        if discrepancies:
            logger.warning(
                f"Tender {tender_id} has {len(discrepancies)} discrepancies "
                f"with official source"
            )
        else:
            logger.info(f"Tender {tender_id} verified successfully")

        return result

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    async def verify_multiple_tenders(
        self,
        tender_data_list: List[Dict]
    ) -> List[VerificationResult]:
        """
        Verify multiple tenders against official source.

        Args:
            tender_data_list: List of dicts with tender_id and our_data

        Returns:
            List of VerificationResult objects
        """
        results = []

        for item in tender_data_list:
            tender_id = item.get('tender_id')
            our_data = item.get('our_data', item)

            if tender_id:
                result = await self.verify_tender_data(tender_id, our_data)
                results.append(result)

                # Small delay between requests to be respectful
                await asyncio.sleep(0.5)

        return results

    async def bulk_get_bidder_counts(
        self,
        tender_ids: List[str]
    ) -> Dict[str, OfficialBidderData]:
        """
        Get official bidder counts for multiple tenders.

        Args:
            tender_ids: List of tender IDs

        Returns:
            Dict mapping tender_id to OfficialBidderData
        """
        results = {}

        # Process in batches to avoid overwhelming the server
        batch_size = 5

        for i in range(0, len(tender_ids), batch_size):
            batch = tender_ids[i:i + batch_size]

            tasks = [self.get_official_bidder_count(tid) for tid in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for tender_id, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error getting bidders for {tender_id}: {result}")
                    results[tender_id] = OfficialBidderData(
                        tender_id=tender_id,
                        total_bidders=0,
                        source_url=''
                    )
                else:
                    results[tender_id] = result

            # Delay between batches
            await asyncio.sleep(1)

        return results

    # =========================================================================
    # CORRUPTION DETECTION HELPERS
    # =========================================================================

    async def detect_bidder_count_discrepancies(
        self,
        tenders_from_db: List[Dict]
    ) -> List[Dict]:
        """
        Find tenders where our bidder count differs from official source.

        This is CRITICAL for corruption detection - single bidder tenders
        that actually had multiple bidders may indicate data manipulation
        in our database or scraping failures.

        Args:
            tenders_from_db: List of tender dicts from our database

        Returns:
            List of discrepancies with tender details
        """
        discrepancies = []

        tender_ids = [t.get('tender_id') for t in tenders_from_db if t.get('tender_id')]
        official_bidder_data = await self.bulk_get_bidder_counts(tender_ids)

        for tender in tenders_from_db:
            tender_id = tender.get('tender_id')
            if not tender_id:
                continue

            official = official_bidder_data.get(tender_id)
            if not official or official.total_bidders == 0:
                continue  # Couldn't get official data

            our_count = tender.get('num_bidders', 0) or 0
            official_count = official.total_bidders

            if our_count != official_count:
                discrepancies.append({
                    'tender_id': tender_id,
                    'title': tender.get('title'),
                    'procuring_entity': tender.get('procuring_entity'),
                    'our_bidder_count': our_count,
                    'official_bidder_count': official_count,
                    'difference': official_count - our_count,
                    'severity': 'critical' if abs(official_count - our_count) > 2 else 'high',
                    'official_bidders': [asdict(b) for b in official.bidders],
                    'verification_url': official.source_url
                })

        # Sort by severity and difference
        discrepancies.sort(
            key=lambda x: (x['severity'] == 'critical', -abs(x['difference'])),
            reverse=True
        )

        return discrepancies


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def quick_verify_tender(tender_id: str, our_data: Dict) -> VerificationResult:
    """
    Quick helper to verify a single tender.

    Usage:
        result = await quick_verify_tender("12345/2024", {"num_bidders": 1, "winner": "Company A"})
    """
    async with ENabavkiAgent() as agent:
        return await agent.verify_tender_data(tender_id, our_data)


async def quick_get_bidder_count(tender_id: str) -> int:
    """
    Quick helper to get official bidder count.

    Usage:
        count = await quick_get_bidder_count("12345/2024")
    """
    async with ENabavkiAgent() as agent:
        result = await agent.get_official_bidder_count(tender_id)
        return result.total_bidders


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    async def main():
        """Example usage of ENabavkiAgent"""

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        async with ENabavkiAgent() as agent:
            # Example: Get official bidder count
            tender_id = "12345/2024"

            print(f"\n--- Fetching official data for tender {tender_id} ---")

            # Get tender details
            details = await agent.get_tender_details(tender_id)
            print(f"\nTender Details:")
            print(f"  Title: {details.title}")
            print(f"  Procuring Entity: {details.procuring_entity}")
            print(f"  Estimated Value: {details.estimated_value_mkd} MKD")

            # Get official bidder count
            bidders = await agent.get_official_bidder_count(tender_id)
            print(f"\nOfficial Bidder Data:")
            print(f"  Total Bidders: {bidders.total_bidders}")
            for b in bidders.bidders:
                print(f"    - {b.company_name}: {b.bid_amount_mkd} MKD (Winner: {b.is_winner})")

            # Verify against our data
            our_data = {
                'tender_id': tender_id,
                'num_bidders': 1,  # Our DB says 1 bidder
                'winner': 'Some Company',
                'estimated_value_mkd': 1000000
            }

            verification = await agent.verify_tender_data(tender_id, our_data)
            print(f"\nVerification Result:")
            print(f"  Is Verified: {verification.is_verified}")
            print(f"  Discrepancies: {len(verification.discrepancies)}")

            for d in verification.discrepancies:
                print(f"\n  DISCREPANCY [{d.severity.upper()}]:")
                print(f"    Field: {d.field_name}")
                print(f"    Our Value: {d.our_value}")
                print(f"    Official Value: {d.official_value}")
                print(f"    Description: {d.description}")

    asyncio.run(main())

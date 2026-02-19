#!/usr/bin/env python3
"""
Web and News Research Agent for Corruption Detection

This agent uses Serper API to search the web and news for information about
companies, institutions, and tenders in the context of Macedonian public procurement.

Primary use cases:
- Company due diligence and background checks
- Institution research and transparency analysis
- News monitoring for corruption indicators
- Connection mapping between companies and institutions
- Tender coverage and controversy detection

Features:
- Async operations for high performance
- Rate limiting to prevent API abuse
- Comprehensive error handling
- Source credibility scoring
- Sentiment analysis for search results
- Evidence URL tracking
"""

import os
import asyncio
import logging
import json
import re
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import aiohttp
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class Sentiment(Enum):
    """Sentiment classification for search results."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class SourceCredibility(Enum):
    """Credibility classification for sources."""
    HIGH = "high"          # Official government, established news
    MEDIUM = "medium"      # Regional news, business directories
    LOW = "low"            # Unknown blogs, forums
    UNKNOWN = "unknown"


@dataclass
class SearchResult:
    """Represents a single search result with metadata."""
    title: str
    url: str
    snippet: str
    source_domain: str
    position: int
    date: Optional[str] = None
    sentiment: Sentiment = Sentiment.UNKNOWN
    credibility: SourceCredibility = SourceCredibility.UNKNOWN
    relevance_score: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class ResearchReport:
    """Comprehensive research report for an entity."""
    entity_name: str
    entity_type: str  # 'company', 'institution', 'tender'
    timestamp: str
    raw_results: List[SearchResult]
    key_facts: List[str]
    overall_sentiment: Sentiment
    risk_indicators: List[str]
    evidence_urls: List[str]
    summary: str
    metadata: Dict = field(default_factory=dict)


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.calls: List[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait if necessary to stay within rate limits."""
        async with self._lock:
            now = datetime.now()
            # Remove calls older than 1 minute
            self.calls = [c for c in self.calls if (now - c).seconds < 60]

            if len(self.calls) >= self.calls_per_minute:
                # Wait until the oldest call expires
                wait_time = 60 - (now - self.calls[0]).seconds
                if wait_time > 0:
                    logger.warning(f"Rate limit reached, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)

            self.calls.append(now)


class WebResearchAgent:
    """
    Web and News Research Agent for corruption detection.

    Uses Serper API to perform comprehensive web and news searches
    about companies, institutions, and tenders in Macedonia.

    Example usage:
        agent = WebResearchAgent()

        # Research a company
        company_info = await agent.research_company("ДКММ ДООЕЛ")

        # Search for news
        news = await agent.search_news("Министерство за здравство", days_back=90)

        # Find connections
        connections = await agent.find_connections(
            "ДКММ ДООЕЛ",
            "Министерство за здравство"
        )
    """

    # Serper API endpoints
    SERPER_SEARCH_URL = "https://google.serper.dev/search"
    SERPER_NEWS_URL = "https://google.serper.dev/news"

    # High credibility domains for Macedonian context
    HIGH_CREDIBILITY_DOMAINS = {
        'gov.mk', 'e-nabavki.gov.mk', 'e-pazar.gov.mk',
        'crm.com.mk', 'ujp.gov.mk', 'stat.gov.mk',
        'mf.gov.mk', 'vlada.mk', 'sobranie.mk',
        'mkd.mk', 'sdk.mk', '360stepeni.mk',
        'reuters.com', 'balkaninsight.com', 'slobodnaevropa.mk',
        'dw.com', 'mia.mk', 'meta.mk'
    }

    MEDIUM_CREDIBILITY_DOMAINS = {
        'time.mk', 'kurir.mk', 'netpress.mk', 'vecer.mk',
        'sitel.mk', 'telma.mk', 'alfa.mk', 'kanal5.mk',
        'linkedin.com', 'facebook.com', 'twitter.com',
        'kompas.com.mk', 'yellowpages.com.mk'
    }

    # Corruption-related keywords in Macedonian
    CORRUPTION_KEYWORDS_MK = [
        'корупција', 'скандал', 'криминал', 'измама', 'малверзација',
        'тендер', 'нелегално', 'истрага', 'апс', 'притвор',
        'злоупотреба', 'конфликт на интереси', 'поткуп', 'мито',
        'кривична', 'обвинение', 'судење', 'пресуда', 'казна',
        'ДЗР', 'ДКСК', 'ОЈО', 'СЈО', 'ревизија', 'неправилности',
        'фирма ќерка', 'тајна', 'криење', 'офшор'
    ]

    # Positive business keywords
    POSITIVE_KEYWORDS_MK = [
        'награда', 'успех', 'раст', 'инвестиција', 'иновација',
        'сертификат', 'квалитет', 'ISO', 'партнерство', 'експанзија',
        'вработување', 'нови работни места', 'извоз', 'признание'
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        calls_per_minute: int = 50
    ):
        """
        Initialize the Web Research Agent.

        Args:
            api_key: Serper API key (falls back to SERPER_API_KEY env var)
            calls_per_minute: Rate limit for API calls
        """
        self.api_key = api_key or os.getenv('SERPER_API_KEY', '')
        self.rate_limiter = RateLimiter(calls_per_minute)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _serper_search(
        self,
        query: str,
        search_type: str = "search",
        num_results: int = 10,
        gl: str = "mk",
        hl: str = "mk",
        tbs: Optional[str] = None
    ) -> Dict:
        """
        Execute a Serper API search.

        Args:
            query: Search query
            search_type: 'search' for web, 'news' for news
            num_results: Number of results to return
            gl: Geolocation (country code)
            hl: Language
            tbs: Time-based search filter (e.g., 'qdr:m' for past month)

        Returns:
            Dict with search results
        """
        await self.rate_limiter.acquire()

        url = self.SERPER_NEWS_URL if search_type == "news" else self.SERPER_SEARCH_URL

        payload = {
            "q": query,
            "gl": gl,
            "hl": hl,
            "num": num_results
        }

        if tbs:
            payload["tbs"] = tbs

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            session = await self._get_session()
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Serper search returned {len(data.get('organic', []))} results for: {query[:50]}")
                    return data
                elif response.status == 429:
                    logger.warning("Serper rate limit exceeded, retrying after delay")
                    await asyncio.sleep(5)
                    return await self._serper_search(query, search_type, num_results, gl, hl, tbs)
                else:
                    error_text = await response.text()
                    logger.error(f"Serper API error {response.status}: {error_text}")
                    return {"error": f"API error: {response.status}", "organic": [], "news": []}

        except asyncio.TimeoutError:
            logger.error(f"Serper API timeout for query: {query[:50]}")
            return {"error": "Request timeout", "organic": [], "news": []}
        except aiohttp.ClientError as e:
            logger.error(f"Serper API client error: {e}")
            return {"error": str(e), "organic": [], "news": []}

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception:
            return "unknown"

    def _assess_credibility(self, url: str) -> SourceCredibility:
        """Assess the credibility of a source based on its domain."""
        domain = self._extract_domain(url)

        # Check exact matches and parent domains
        for high_domain in self.HIGH_CREDIBILITY_DOMAINS:
            if domain == high_domain or domain.endswith('.' + high_domain):
                return SourceCredibility.HIGH

        for medium_domain in self.MEDIUM_CREDIBILITY_DOMAINS:
            if domain == medium_domain or domain.endswith('.' + medium_domain):
                return SourceCredibility.MEDIUM

        # Check for .gov.mk or .edu.mk domains
        if '.gov.mk' in domain or '.edu.mk' in domain:
            return SourceCredibility.HIGH

        # Check for established news patterns
        if any(word in domain for word in ['news', 'times', 'press', 'daily']):
            return SourceCredibility.MEDIUM

        return SourceCredibility.LOW

    def _analyze_sentiment(self, text: str) -> Sentiment:
        """Analyze sentiment of text based on keywords."""
        text_lower = text.lower()

        negative_count = sum(1 for kw in self.CORRUPTION_KEYWORDS_MK if kw.lower() in text_lower)
        positive_count = sum(1 for kw in self.POSITIVE_KEYWORDS_MK if kw.lower() in text_lower)

        if negative_count > positive_count and negative_count > 0:
            return Sentiment.NEGATIVE
        elif positive_count > negative_count and positive_count > 0:
            return Sentiment.POSITIVE
        elif negative_count > 0 or positive_count > 0:
            return Sentiment.NEUTRAL

        return Sentiment.UNKNOWN

    def _calculate_relevance(
        self,
        result: Dict,
        search_entity: str,
        position: int
    ) -> float:
        """Calculate relevance score for a search result."""
        score = 0.0

        title = result.get('title', '').lower()
        snippet = result.get('snippet', '').lower()
        entity_lower = search_entity.lower()

        # Exact entity match in title
        if entity_lower in title:
            score += 0.4

        # Entity match in snippet
        if entity_lower in snippet:
            score += 0.2

        # Position bonus (higher positions = more relevant)
        position_score = max(0, (10 - position) / 10) * 0.3
        score += position_score

        # Credibility bonus
        credibility = self._assess_credibility(result.get('link', ''))
        if credibility == SourceCredibility.HIGH:
            score += 0.1
        elif credibility == SourceCredibility.MEDIUM:
            score += 0.05

        return min(score, 1.0)

    def _parse_search_results(
        self,
        data: Dict,
        search_entity: str,
        result_type: str = "organic"
    ) -> List[SearchResult]:
        """Parse Serper API response into SearchResult objects."""
        results = []
        items = data.get(result_type, []) or data.get('news', [])

        for i, item in enumerate(items):
            url = item.get('link', '')
            title = item.get('title', '')
            snippet = item.get('snippet', '')

            result = SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source_domain=self._extract_domain(url),
                position=i + 1,
                date=item.get('date'),
                sentiment=self._analyze_sentiment(f"{title} {snippet}"),
                credibility=self._assess_credibility(url),
                relevance_score=self._calculate_relevance(item, search_entity, i),
                metadata={
                    'cached_page_link': item.get('cachedPageLink'),
                    'image_url': item.get('imageUrl'),
                    'source': item.get('source')
                }
            )
            results.append(result)

        return results

    def _extract_key_facts(self, results: List[SearchResult], entity_name: str) -> List[str]:
        """Extract key facts from search results."""
        facts = []
        seen = set()

        for result in results:
            # Skip low credibility sources for fact extraction
            if result.credibility == SourceCredibility.LOW:
                continue

            snippet = result.snippet
            if not snippet:
                continue

            # Split into sentences and filter
            sentences = re.split(r'[.!?]', snippet)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20:
                    continue

                # Check if sentence mentions the entity
                if entity_name.lower() in sentence.lower():
                    # Normalize and deduplicate
                    normalized = sentence[:100].lower()
                    if normalized not in seen:
                        facts.append(sentence[:200])
                        seen.add(normalized)
                        if len(facts) >= 10:
                            return facts

        return facts

    def _identify_risk_indicators(self, results: List[SearchResult]) -> List[str]:
        """Identify corruption/risk indicators from search results."""
        indicators = []

        for result in results:
            text = f"{result.title} {result.snippet}".lower()

            # Check for specific risk patterns
            risk_patterns = [
                (r'истрага|istraga', 'Investigation mentioned'),
                (r'апс|притвор|aretiran', 'Arrest/detention mentioned'),
                (r'обвинение|obtuzenie', 'Charges/accusations mentioned'),
                (r'корупција|korupcija', 'Corruption explicitly mentioned'),
                (r'скандал|skandal', 'Scandal mentioned'),
                (r'ДЗР|drzaven zavod za revizija', 'State Audit Office mentioned'),
                (r'ДКСК|antikorupcija', 'Anti-corruption commission mentioned'),
                (r'конфликт на интерес', 'Conflict of interest mentioned'),
                (r'незаконски|нелегално', 'Illegal activity mentioned'),
                (r'тендер.*злоупотреба|злоупотреба.*тендер', 'Tender abuse mentioned'),
                (r'фиктивн|phantom', 'Fictitious/phantom entity mentioned'),
                (r'перење пари|money laundering', 'Money laundering mentioned'),
                (r'даночна евазија|tax evasion', 'Tax evasion mentioned'),
            ]

            for pattern, indicator in risk_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    if indicator not in indicators:
                        indicators.append(indicator)
                        # Add source evidence
                        indicators.append(f"  Source: {result.url}")

        return indicators

    def _calculate_overall_sentiment(self, results: List[SearchResult]) -> Sentiment:
        """Calculate overall sentiment from all results."""
        if not results:
            return Sentiment.UNKNOWN

        sentiment_scores = {
            Sentiment.POSITIVE: 0,
            Sentiment.NEGATIVE: 0,
            Sentiment.NEUTRAL: 0
        }

        for result in results:
            if result.sentiment != Sentiment.UNKNOWN:
                # Weight by credibility
                weight = 1.0
                if result.credibility == SourceCredibility.HIGH:
                    weight = 2.0
                elif result.credibility == SourceCredibility.MEDIUM:
                    weight = 1.5

                sentiment_scores[result.sentiment] += weight

        if sentiment_scores[Sentiment.NEGATIVE] > sentiment_scores[Sentiment.POSITIVE]:
            return Sentiment.NEGATIVE
        elif sentiment_scores[Sentiment.POSITIVE] > sentiment_scores[Sentiment.NEGATIVE]:
            return Sentiment.POSITIVE
        elif any(sentiment_scores.values()):
            return Sentiment.NEUTRAL

        return Sentiment.UNKNOWN

    def _generate_summary(
        self,
        entity_name: str,
        entity_type: str,
        results: List[SearchResult],
        key_facts: List[str],
        risk_indicators: List[str]
    ) -> str:
        """Generate a summary of the research findings."""
        summary_parts = []

        # Count results by credibility
        high_cred = sum(1 for r in results if r.credibility == SourceCredibility.HIGH)
        medium_cred = sum(1 for r in results if r.credibility == SourceCredibility.MEDIUM)

        summary_parts.append(
            f"Research on {entity_type} '{entity_name}' found {len(results)} sources "
            f"({high_cred} high credibility, {medium_cred} medium credibility)."
        )

        # Add sentiment summary
        overall_sentiment = self._calculate_overall_sentiment(results)
        if overall_sentiment == Sentiment.NEGATIVE:
            summary_parts.append(
                "Overall sentiment is NEGATIVE - potential corruption or controversy indicators found."
            )
        elif overall_sentiment == Sentiment.POSITIVE:
            summary_parts.append(
                "Overall sentiment is POSITIVE - no significant negative indicators found."
            )
        else:
            summary_parts.append("Overall sentiment is NEUTRAL or mixed.")

        # Add risk indicator count
        if risk_indicators:
            risk_count = len([r for r in risk_indicators if not r.startswith('  Source:')])
            summary_parts.append(f"Found {risk_count} potential risk indicators.")

        # Add key facts summary
        if key_facts:
            summary_parts.append(f"Extracted {len(key_facts)} key facts from sources.")

        return " ".join(summary_parts)

    async def research_company(self, company_name: str) -> Dict:
        """
        Comprehensive research on a company.

        Searches for:
        - General company information
        - Ownership and directors
        - Scandals and controversies
        - Business registry info
        - Related companies

        Args:
            company_name: Name of the company to research

        Returns:
            Dict with research results including:
            - raw_results: List of SearchResult objects
            - key_facts: Extracted facts about the company
            - sentiment: Overall sentiment assessment
            - risk_indicators: List of corruption risk flags
            - evidence_urls: URLs for evidence
            - owner_info: Information about owners/directors
            - registry_info: Business registry information
        """
        logger.info(f"Researching company: {company_name}")

        # Define search queries for comprehensive company research
        search_queries = [
            (f'"{company_name}"', "general"),
            (f'"{company_name}" сопственик', "owner"),
            (f'"{company_name}" директор', "director"),
            (f'"{company_name}" скандал', "scandal"),
            (f'"{company_name}" корупција', "corruption"),
            (f'"{company_name}" ЦРМ регистар', "registry"),
            (f'"{company_name}" тендер набавка', "procurement"),
        ]

        all_results: List[SearchResult] = []
        category_results: Dict[str, List[SearchResult]] = {}

        # Execute all searches concurrently
        async def execute_search(query: str, category: str) -> Tuple[str, List[SearchResult]]:
            data = await self._serper_search(query, num_results=10)
            results = self._parse_search_results(data, company_name)
            return category, results

        tasks = [execute_search(q, cat) for q, cat in search_queries]
        search_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in search_results:
            if isinstance(result, Exception):
                logger.error(f"Search error: {result}")
                continue
            category, results = result
            category_results[category] = results
            all_results.extend(results)

        # Deduplicate results by URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

        # Sort by relevance
        unique_results.sort(key=lambda x: x.relevance_score, reverse=True)

        # Extract insights
        key_facts = self._extract_key_facts(unique_results, company_name)
        risk_indicators = self._identify_risk_indicators(unique_results)
        overall_sentiment = self._calculate_overall_sentiment(unique_results)
        evidence_urls = [r.url for r in unique_results if r.credibility in [SourceCredibility.HIGH, SourceCredibility.MEDIUM]]

        # Extract owner/director info specifically
        owner_info = []
        for result in category_results.get('owner', []) + category_results.get('director', []):
            if result.credibility != SourceCredibility.LOW:
                owner_info.append({
                    'text': result.snippet,
                    'source': result.url,
                    'credibility': result.credibility.value
                })

        # Extract registry info
        registry_info = []
        for result in category_results.get('registry', []):
            if result.credibility != SourceCredibility.LOW:
                registry_info.append({
                    'text': result.snippet,
                    'source': result.url,
                    'credibility': result.credibility.value
                })

        return {
            'entity_name': company_name,
            'entity_type': 'company',
            'timestamp': datetime.now().isoformat(),
            'raw_results': [self._result_to_dict(r) for r in unique_results],
            'key_facts': key_facts,
            'overall_sentiment': overall_sentiment.value,
            'risk_indicators': risk_indicators,
            'evidence_urls': evidence_urls,
            'owner_info': owner_info,
            'registry_info': registry_info,
            'category_breakdown': {cat: len(res) for cat, res in category_results.items()},
            'summary': self._generate_summary(
                company_name, 'company', unique_results, key_facts, risk_indicators
            ),
            'credibility_score': self._calculate_credibility_score(unique_results)
        }

    async def research_institution(self, institution_name: str) -> Dict:
        """
        Research a public institution.

        Searches for:
        - Official website and information
        - Leadership and management
        - Budget information
        - Investigations and audits
        - News coverage

        Args:
            institution_name: Name of the institution to research

        Returns:
            Dict with comprehensive institution information
        """
        logger.info(f"Researching institution: {institution_name}")

        search_queries = [
            (f'"{institution_name}"', "general"),
            (f'"{institution_name}" директор раководител', "leadership"),
            (f'"{institution_name}" буџет финансии', "budget"),
            (f'"{institution_name}" ревизија ДЗР', "audit"),
            (f'"{institution_name}" скандал корупција', "scandal"),
            (f'"{institution_name}" тендер набавка', "procurement"),
            (f'site:gov.mk "{institution_name}"', "official"),
        ]

        all_results: List[SearchResult] = []
        category_results: Dict[str, List[SearchResult]] = {}

        async def execute_search(query: str, category: str) -> Tuple[str, List[SearchResult]]:
            data = await self._serper_search(query, num_results=10)
            results = self._parse_search_results(data, institution_name)
            return category, results

        tasks = [execute_search(q, cat) for q, cat in search_queries]
        search_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in search_results:
            if isinstance(result, Exception):
                logger.error(f"Search error: {result}")
                continue
            category, results = result
            category_results[category] = results
            all_results.extend(results)

        # Deduplicate
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

        unique_results.sort(key=lambda x: x.relevance_score, reverse=True)

        key_facts = self._extract_key_facts(unique_results, institution_name)
        risk_indicators = self._identify_risk_indicators(unique_results)
        overall_sentiment = self._calculate_overall_sentiment(unique_results)
        evidence_urls = [r.url for r in unique_results if r.credibility in [SourceCredibility.HIGH, SourceCredibility.MEDIUM]]

        # Extract leadership info
        leadership_info = []
        for result in category_results.get('leadership', []):
            if result.credibility != SourceCredibility.LOW:
                leadership_info.append({
                    'text': result.snippet,
                    'source': result.url,
                    'credibility': result.credibility.value
                })

        # Extract official website
        official_website = None
        for result in category_results.get('official', []):
            if '.gov.mk' in result.url:
                official_website = result.url
                break

        # Extract audit findings
        audit_info = []
        for result in category_results.get('audit', []):
            audit_info.append({
                'text': result.snippet,
                'source': result.url,
                'credibility': result.credibility.value
            })

        return {
            'entity_name': institution_name,
            'entity_type': 'institution',
            'timestamp': datetime.now().isoformat(),
            'raw_results': [self._result_to_dict(r) for r in unique_results],
            'key_facts': key_facts,
            'overall_sentiment': overall_sentiment.value,
            'risk_indicators': risk_indicators,
            'evidence_urls': evidence_urls,
            'official_website': official_website,
            'leadership_info': leadership_info,
            'audit_info': audit_info,
            'category_breakdown': {cat: len(res) for cat, res in category_results.items()},
            'summary': self._generate_summary(
                institution_name, 'institution', unique_results, key_facts, risk_indicators
            ),
            'credibility_score': self._calculate_credibility_score(unique_results)
        }

    async def search_news(
        self,
        entity_name: str,
        days_back: int = 365,
        focus_corruption: bool = True
    ) -> Dict:
        """
        Search news for an entity with focus on corruption indicators.

        Args:
            entity_name: Name of entity to search for
            days_back: How many days back to search
            focus_corruption: Whether to include corruption-focused searches

        Returns:
            Dict with news results and analysis
        """
        logger.info(f"Searching news for: {entity_name} (last {days_back} days)")

        # Calculate time filter for Serper
        time_filter = self._get_time_filter(days_back)

        # Define news searches
        news_queries = [
            (f'"{entity_name}"', "general"),
        ]

        if focus_corruption:
            news_queries.extend([
                (f'"{entity_name}" корупција', "corruption"),
                (f'"{entity_name}" истрага', "investigation"),
                (f'"{entity_name}" скандал', "scandal"),
                (f'"{entity_name}" судење обвинение', "court"),
                (f'"{entity_name}" тендер', "procurement"),
            ])

        all_results: List[SearchResult] = []
        category_results: Dict[str, List[SearchResult]] = {}

        async def execute_news_search(query: str, category: str) -> Tuple[str, List[SearchResult]]:
            data = await self._serper_search(
                query,
                search_type="news",
                num_results=15,
                tbs=time_filter
            )
            results = self._parse_search_results(data, entity_name, result_type="news")
            return category, results

        tasks = [execute_news_search(q, cat) for q, cat in news_queries]
        search_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in search_results:
            if isinstance(result, Exception):
                logger.error(f"News search error: {result}")
                continue
            category, results = result
            category_results[category] = results
            all_results.extend(results)

        # Deduplicate
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

        # Sort by date if available, then relevance
        unique_results.sort(
            key=lambda x: (x.date or '1900-01-01', x.relevance_score),
            reverse=True
        )

        key_facts = self._extract_key_facts(unique_results, entity_name)
        risk_indicators = self._identify_risk_indicators(unique_results)
        overall_sentiment = self._calculate_overall_sentiment(unique_results)

        # Timeline analysis
        timeline = []
        for result in unique_results:
            if result.date:
                timeline.append({
                    'date': result.date,
                    'title': result.title,
                    'sentiment': result.sentiment.value,
                    'url': result.url
                })

        return {
            'entity_name': entity_name,
            'search_type': 'news',
            'days_back': days_back,
            'timestamp': datetime.now().isoformat(),
            'raw_results': [self._result_to_dict(r) for r in unique_results],
            'key_facts': key_facts,
            'overall_sentiment': overall_sentiment.value,
            'risk_indicators': risk_indicators,
            'evidence_urls': [r.url for r in unique_results[:20]],
            'timeline': timeline[:20],
            'category_breakdown': {cat: len(res) for cat, res in category_results.items()},
            'total_news_items': len(unique_results),
            'negative_news_count': sum(1 for r in unique_results if r.sentiment == Sentiment.NEGATIVE),
            'summary': self._generate_summary(
                entity_name, 'news search', unique_results, key_facts, risk_indicators
            ),
            'credibility_score': self._calculate_credibility_score(unique_results)
        }

    async def search_tender_coverage(
        self,
        tender_title: str,
        institution: str
    ) -> Dict:
        """
        Search for news/web coverage of a specific tender.

        Args:
            tender_title: Title or description of the tender
            institution: Name of the procuring institution

        Returns:
            Dict with tender coverage information
        """
        logger.info(f"Searching tender coverage: {tender_title[:50]}... ({institution})")

        # Simplify tender title for search
        simplified_title = tender_title[:100]

        search_queries = [
            (f'"{institution}" "{simplified_title}"', "exact"),
            (f'"{institution}" тендер {simplified_title[:50]}', "tender"),
            (f'"{simplified_title}" набавка', "procurement"),
            (f'"{institution}" жалба тендер', "complaint"),
            (f'"{institution}" протест тендер', "protest"),
            (f'site:e-nabavki.gov.mk "{institution}"', "official"),
        ]

        all_results: List[SearchResult] = []
        category_results: Dict[str, List[SearchResult]] = {}

        async def execute_search(query: str, category: str) -> Tuple[str, List[SearchResult]]:
            data = await self._serper_search(query, num_results=10)
            results = self._parse_search_results(data, institution)
            return category, results

        tasks = [execute_search(q, cat) for q, cat in search_queries]
        search_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in search_results:
            if isinstance(result, Exception):
                logger.error(f"Search error: {result}")
                continue
            category, results = result
            category_results[category] = results
            all_results.extend(results)

        # Deduplicate
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

        unique_results.sort(key=lambda x: x.relevance_score, reverse=True)

        risk_indicators = self._identify_risk_indicators(unique_results)

        # Check for complaints/protests
        has_complaints = len(category_results.get('complaint', [])) > 0
        has_protests = len(category_results.get('protest', [])) > 0

        # Find official e-nabavki link
        official_link = None
        for result in category_results.get('official', []):
            if 'e-nabavki.gov.mk' in result.url:
                official_link = result.url
                break

        return {
            'tender_title': tender_title,
            'institution': institution,
            'timestamp': datetime.now().isoformat(),
            'raw_results': [self._result_to_dict(r) for r in unique_results],
            'risk_indicators': risk_indicators,
            'evidence_urls': [r.url for r in unique_results[:15]],
            'official_link': official_link,
            'has_complaints': has_complaints,
            'has_protests': has_protests,
            'media_coverage_count': len(unique_results),
            'category_breakdown': {cat: len(res) for cat, res in category_results.items()},
            'overall_sentiment': self._calculate_overall_sentiment(unique_results).value,
            'credibility_score': self._calculate_credibility_score(unique_results)
        }

    async def find_connections(
        self,
        company_name: str,
        institution_name: str
    ) -> Dict:
        """
        Search for connections between a company and an institution.

        Looks for:
        - Joint mentions in news/web
        - Shared people (directors, officials)
        - Previous contract relationships
        - Any suspicious patterns

        Args:
            company_name: Name of the company
            institution_name: Name of the institution

        Returns:
            Dict with connection analysis
        """
        logger.info(f"Finding connections: {company_name} <-> {institution_name}")

        search_queries = [
            (f'"{company_name}" "{institution_name}"', "direct_mention"),
            (f'"{company_name}" "{institution_name}" тендер', "tender"),
            (f'"{company_name}" "{institution_name}" договор', "contract"),
            (f'"{company_name}" "{institution_name}" скандал', "scandal"),
            (f'"{company_name}" директор "{institution_name}"', "shared_people"),
        ]

        all_results: List[SearchResult] = []
        category_results: Dict[str, List[SearchResult]] = {}

        async def execute_search(query: str, category: str) -> Tuple[str, List[SearchResult]]:
            data = await self._serper_search(query, num_results=10)
            combined_entity = f"{company_name} {institution_name}"
            results = self._parse_search_results(data, combined_entity)
            return category, results

        tasks = [execute_search(q, cat) for q, cat in search_queries]
        search_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in search_results:
            if isinstance(result, Exception):
                logger.error(f"Search error: {result}")
                continue
            category, results = result
            category_results[category] = results
            all_results.extend(results)

        # Deduplicate
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

        unique_results.sort(key=lambda x: x.relevance_score, reverse=True)

        # Analyze connections
        connections = []
        for result in unique_results:
            text = f"{result.title} {result.snippet}".lower()
            company_lower = company_name.lower()
            inst_lower = institution_name.lower()

            if company_lower in text and inst_lower in text:
                connection_type = "unknown"
                if any(w in text for w in ['тендер', 'набавка', 'понуда']):
                    connection_type = "procurement"
                elif any(w in text for w in ['договор', 'контракт']):
                    connection_type = "contract"
                elif any(w in text for w in ['директор', 'раководител', 'вработен']):
                    connection_type = "personnel"
                elif any(w in text for w in ['скандал', 'корупција', 'истрага']):
                    connection_type = "scandal"

                connections.append({
                    'type': connection_type,
                    'text': result.snippet[:200],
                    'source': result.url,
                    'credibility': result.credibility.value,
                    'sentiment': result.sentiment.value
                })

        risk_indicators = self._identify_risk_indicators(unique_results)

        # Calculate connection strength
        connection_strength = "none"
        if len(connections) > 10:
            connection_strength = "strong"
        elif len(connections) > 5:
            connection_strength = "moderate"
        elif len(connections) > 0:
            connection_strength = "weak"

        return {
            'company_name': company_name,
            'institution_name': institution_name,
            'timestamp': datetime.now().isoformat(),
            'connections': connections,
            'connection_count': len(connections),
            'connection_strength': connection_strength,
            'risk_indicators': risk_indicators,
            'evidence_urls': [r.url for r in unique_results[:15]],
            'category_breakdown': {cat: len(res) for cat, res in category_results.items()},
            'has_tender_connection': len(category_results.get('tender', [])) > 0,
            'has_contract_connection': len(category_results.get('contract', [])) > 0,
            'has_scandal_connection': len(category_results.get('scandal', [])) > 0,
            'has_personnel_connection': len(category_results.get('shared_people', [])) > 0,
            'overall_sentiment': self._calculate_overall_sentiment(unique_results).value,
            'credibility_score': self._calculate_credibility_score(unique_results)
        }

    async def comprehensive_due_diligence(
        self,
        company_name: str,
        institution_name: Optional[str] = None
    ) -> Dict:
        """
        Perform comprehensive due diligence on a company.

        Combines:
        - Company research
        - News search
        - Connection analysis (if institution provided)

        Args:
            company_name: Name of the company
            institution_name: Optional institution to check connections with

        Returns:
            Dict with comprehensive due diligence report
        """
        logger.info(f"Starting comprehensive due diligence for: {company_name}")

        # Run research tasks concurrently
        tasks = [
            self.research_company(company_name),
            self.search_news(company_name, days_back=730),  # 2 years
        ]

        if institution_name:
            tasks.append(self.find_connections(company_name, institution_name))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        company_research = results[0] if not isinstance(results[0], Exception) else {}
        news_research = results[1] if not isinstance(results[1], Exception) else {}
        connection_research = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else {}

        # Combine risk indicators
        all_risk_indicators = []
        all_risk_indicators.extend(company_research.get('risk_indicators', []))
        all_risk_indicators.extend(news_research.get('risk_indicators', []))
        all_risk_indicators.extend(connection_research.get('risk_indicators', []))

        # Deduplicate risk indicators
        unique_risks = []
        seen_risks = set()
        for risk in all_risk_indicators:
            if risk not in seen_risks:
                unique_risks.append(risk)
                seen_risks.add(risk)

        # Calculate overall risk score (0-100)
        risk_score = self._calculate_risk_score(
            company_research,
            news_research,
            connection_research
        )

        # Determine risk level
        risk_level = "low"
        if risk_score >= 70:
            risk_level = "high"
        elif risk_score >= 40:
            risk_level = "medium"

        return {
            'company_name': company_name,
            'institution_name': institution_name,
            'timestamp': datetime.now().isoformat(),
            'company_research': company_research,
            'news_research': news_research,
            'connection_research': connection_research,
            'combined_risk_indicators': unique_risks,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'recommendation': self._generate_recommendation(risk_level, unique_risks),
            'evidence_summary': {
                'total_sources': (
                    len(company_research.get('raw_results', [])) +
                    len(news_research.get('raw_results', []))
                ),
                'high_credibility_sources': sum(
                    1 for r in company_research.get('raw_results', [])
                    if r.get('credibility') == 'high'
                ),
                'negative_news_items': news_research.get('negative_news_count', 0),
                'connection_strength': connection_research.get('connection_strength', 'none')
            }
        }

    def _result_to_dict(self, result: SearchResult) -> Dict:
        """Convert SearchResult to dictionary."""
        return {
            'title': result.title,
            'url': result.url,
            'snippet': result.snippet,
            'source_domain': result.source_domain,
            'position': result.position,
            'date': result.date,
            'sentiment': result.sentiment.value,
            'credibility': result.credibility.value,
            'relevance_score': result.relevance_score,
            'metadata': result.metadata
        }

    def _get_time_filter(self, days_back: int) -> str:
        """Get Serper time filter string."""
        if days_back <= 1:
            return "qdr:d"  # Past day
        elif days_back <= 7:
            return "qdr:w"  # Past week
        elif days_back <= 30:
            return "qdr:m"  # Past month
        elif days_back <= 365:
            return "qdr:y"  # Past year
        return ""  # No time filter

    def _calculate_credibility_score(self, results: List[SearchResult]) -> float:
        """Calculate overall credibility score (0-100)."""
        if not results:
            return 0.0

        high_count = sum(1 for r in results if r.credibility == SourceCredibility.HIGH)
        medium_count = sum(1 for r in results if r.credibility == SourceCredibility.MEDIUM)
        total = len(results)

        score = ((high_count * 100) + (medium_count * 60)) / total
        return round(score, 1)

    def _calculate_risk_score(
        self,
        company_research: Dict,
        news_research: Dict,
        connection_research: Dict
    ) -> int:
        """Calculate overall risk score (0-100)."""
        score = 0

        # Risk indicators weight
        risk_count = len([
            r for r in company_research.get('risk_indicators', [])
            if not r.startswith('  Source:')
        ])
        score += min(risk_count * 10, 40)

        # Negative news weight
        negative_news = news_research.get('negative_news_count', 0)
        score += min(negative_news * 5, 30)

        # Connection scandal weight
        if connection_research.get('has_scandal_connection'):
            score += 20

        # Sentiment weight
        if company_research.get('overall_sentiment') == 'negative':
            score += 10
        if news_research.get('overall_sentiment') == 'negative':
            score += 10

        return min(score, 100)

    def _generate_recommendation(self, risk_level: str, risk_indicators: List[str]) -> str:
        """Generate recommendation based on risk assessment."""
        if risk_level == "high":
            return (
                "HIGH RISK: This entity shows multiple corruption indicators. "
                "Exercise extreme caution. Consider additional manual investigation "
                "before any business engagement. Consult legal/compliance team."
            )
        elif risk_level == "medium":
            return (
                "MEDIUM RISK: Some concerning indicators found. "
                "Proceed with caution and conduct additional verification. "
                "Monitor for any new developments."
            )
        else:
            return (
                "LOW RISK: No significant red flags detected in available sources. "
                "Standard due diligence procedures should be sufficient."
            )


# Convenience functions for quick usage
async def quick_company_check(company_name: str) -> Dict:
    """Quick company research check."""
    async with WebResearchAgent() as agent:
        return await agent.research_company(company_name)


async def quick_news_search(entity_name: str, days_back: int = 365) -> Dict:
    """Quick news search."""
    async with WebResearchAgent() as agent:
        return await agent.search_news(entity_name, days_back)


async def quick_connection_check(company: str, institution: str) -> Dict:
    """Quick connection check."""
    async with WebResearchAgent() as agent:
        return await agent.find_connections(company, institution)


# Test function
async def test_web_research_agent():
    """Test the Web Research Agent."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async with WebResearchAgent() as agent:
        # Test 1: Company research
        print("\n" + "="*60)
        print("TEST 1: Company Research")
        print("="*60)

        company_result = await agent.research_company("Транспорт АД Скопје")
        print(f"Company: {company_result['entity_name']}")
        print(f"Summary: {company_result['summary']}")
        print(f"Sentiment: {company_result['overall_sentiment']}")
        print(f"Risk indicators: {len(company_result['risk_indicators'])}")
        print(f"Key facts: {len(company_result['key_facts'])}")

        # Test 2: Institution research
        print("\n" + "="*60)
        print("TEST 2: Institution Research")
        print("="*60)

        inst_result = await agent.research_institution("Министерство за здравство")
        print(f"Institution: {inst_result['entity_name']}")
        print(f"Summary: {inst_result['summary']}")
        print(f"Official website: {inst_result.get('official_website', 'Not found')}")
        print(f"Audit info found: {len(inst_result.get('audit_info', []))}")

        # Test 3: News search
        print("\n" + "="*60)
        print("TEST 3: News Search")
        print("="*60)

        news_result = await agent.search_news("јавни набавки корупција", days_back=90)
        print(f"News items found: {news_result['total_news_items']}")
        print(f"Negative news: {news_result['negative_news_count']}")
        print(f"Timeline entries: {len(news_result.get('timeline', []))}")

        # Test 4: Connection check
        print("\n" + "="*60)
        print("TEST 4: Connection Check")
        print("="*60)

        conn_result = await agent.find_connections(
            "Дрогерија ТАБ",
            "ФЗОМ"
        )
        print(f"Connections found: {conn_result['connection_count']}")
        print(f"Connection strength: {conn_result['connection_strength']}")
        print(f"Has tender connection: {conn_result['has_tender_connection']}")

        print("\n" + "="*60)
        print("All tests completed!")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(test_web_research_agent())

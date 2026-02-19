"""
Verification Spider for Flagged Tenders

This spider re-scrapes flagged tenders from e-nabavki.gov.mk and uses Gemini API
to search for additional context from news sources and verify corruption indicators.

Usage:
    # Verify specific tender IDs
    scrapy crawl verify -a tender_ids=12345/2024,67890/2023

    # Verify from database flagged tenders
    scrapy crawl verify -a from_db=true -a min_score=0.7

    # Verify with web search enrichment
    scrapy crawl verify -a tender_ids=12345/2024 -a web_search=true
"""

import scrapy
import logging
import os
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
import asyncpg

logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'nabavkidata'),
    'user': os.getenv('DB_USER', 'nabavkidata_admin'),
    'password': os.getenv('DB_PASSWORD', ''),
}


class VerificationSpider(scrapy.Spider):
    """Spider for verifying flagged tenders with fresh data and web enrichment."""

    name = 'verify'
    allowed_domains = ['e-nabavki.gov.mk']

    # Base URLs for tender detail pages
    TENDER_DETAIL_URLS = {
        'dossier': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/{tender_id}',
        'dossier_acpp': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/{tender_id}',
        'opentender': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/{dossier_id}'
    }

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,  # Be gentle on the server
        "CONCURRENT_REQUESTS": 1,
        "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 1,
        "PLAYWRIGHT_MAX_CONTEXTS": 1,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
    }

    def __init__(
        self,
        tender_ids: str = '',
        from_db: str = 'false',
        min_score: str = '0.5',
        web_search: str = 'false',
        limit: str = '50',
        *args, **kwargs
    ):
        """
        Initialize verification spider.

        Args:
            tender_ids: Comma-separated list of tender IDs to verify
            from_db: If 'true', fetch flagged tenders from database
            min_score: Minimum anomaly score for database selection
            web_search: If 'true', enrich with Gemini web search
            limit: Maximum number of tenders to verify
        """
        super().__init__(*args, **kwargs)

        self.tender_ids = [t.strip() for t in tender_ids.split(',') if t.strip()]
        self.from_db = from_db.lower() == 'true'
        self.min_score = float(min_score)
        self.web_search = web_search.lower() == 'true'
        self.limit = int(limit)

        self.stats = {
            'tenders_verified': 0,
            'data_updated': 0,
            'missing_data_filled': 0,
            'web_enrichments': 0,
            'corruption_indicators': 0,
            'errors': 0,
        }

        self.db_pool = None
        self.gemini_model = None

    async def _init_db(self):
        """Initialize database connection pool."""
        if not self.db_pool:
            self.db_pool = await asyncpg.create_pool(**DB_CONFIG, min_size=1, max_size=3)
            logger.info("Database pool initialized")

    async def _init_gemini(self):
        """Initialize Gemini API for web search enrichment."""
        if self.web_search and not self.gemini_model:
            try:
                import google.generativeai as genai
                api_key = os.getenv('GEMINI_API_KEY')
                if api_key:
                    genai.configure(api_key=api_key)
                    self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
                    logger.info("Gemini API initialized")
                else:
                    logger.warning("GEMINI_API_KEY not set - web search disabled")
                    self.web_search = False
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                self.web_search = False

    async def _fetch_flagged_tenders(self) -> List[Dict]:
        """Fetch flagged tenders from database."""
        await self._init_db()

        query = """
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.winner,
                t.estimated_value_mkd,
                t.actual_value_mkd,
                t.status,
                COALESCE(cf.anomaly_score, 0) as anomaly_score,
                cf.flags
            FROM tenders t
            LEFT JOIN corruption_flags cf ON t.tender_id = cf.tender_id
            WHERE cf.anomaly_score >= $1
            ORDER BY cf.anomaly_score DESC
            LIMIT $2
        """

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, self.min_score, self.limit)
            return [dict(r) for r in rows]

    async def _fetch_specific_tenders(self, tender_ids: List[str]) -> List[Dict]:
        """Fetch specific tenders from database."""
        await self._init_db()

        query = """
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.winner,
                t.estimated_value_mkd,
                t.actual_value_mkd,
                t.status,
                COALESCE(cf.anomaly_score, 0) as anomaly_score,
                cf.flags,
                t.dossier_id
            FROM tenders t
            LEFT JOIN corruption_flags cf ON t.tender_id = cf.tender_id
            WHERE t.tender_id = ANY($1)
        """

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, tender_ids)
            return [dict(r) for r in rows]

    def start_requests(self):
        """Generate requests for tenders to verify."""
        # Create event loop for async operations
        loop = asyncio.get_event_loop()

        tenders_to_verify = []

        if self.from_db:
            # Fetch flagged tenders from database
            logger.info(f"Fetching flagged tenders from DB with min_score={self.min_score}")
            tenders_to_verify = loop.run_until_complete(self._fetch_flagged_tenders())
            logger.info(f"Found {len(tenders_to_verify)} flagged tenders")

        elif self.tender_ids:
            # Fetch specific tenders
            logger.info(f"Fetching {len(self.tender_ids)} specific tenders")
            tenders_to_verify = loop.run_until_complete(
                self._fetch_specific_tenders(self.tender_ids)
            )

        if not tenders_to_verify:
            logger.warning("No tenders to verify. Provide tender_ids or use from_db=true")
            return

        # Initialize Gemini if web search enabled
        if self.web_search:
            loop.run_until_complete(self._init_gemini())

        # Generate requests for each tender
        for tender in tenders_to_verify:
            tender_id = tender['tender_id']
            dossier_id = tender.get('dossier_id')

            # Determine URL format based on tender_id format
            if tender_id.startswith('OT-'):
                # OpenTender format - use dossier_id if available
                url_id = dossier_id if dossier_id else tender_id.replace('OT-', '')
                url = self.TENDER_DETAIL_URLS['dossier'].format(tender_id=url_id)
            else:
                # Standard format (e.g., 12345/2024)
                url = self.TENDER_DETAIL_URLS['dossier'].format(tender_id=tender_id.replace('/', '-'))

            yield scrapy.Request(
                url,
                callback=self.parse_tender,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'networkidle',
                        'timeout': 60000,
                    },
                    'tender_data': tender,
                },
                errback=self.errback,
                dont_filter=True
            )

    async def parse_tender(self, response):
        """Parse tender detail page and extract verification data."""
        page = response.meta.get('playwright_page')
        tender_data = response.meta.get('tender_data', {})
        tender_id = tender_data.get('tender_id', 'unknown')

        logger.info(f"Verifying tender: {tender_id}")

        verification_result = {
            'tender_id': tender_id,
            'verified_at': datetime.utcnow().isoformat(),
            'source_url': response.url,
            'db_data': tender_data,
            'scraped_data': {},
            'discrepancies': [],
            'missing_filled': [],
            'web_context': None,
            'corruption_indicators': [],
        }

        if page:
            try:
                # Wait for page to fully load
                await page.wait_for_timeout(3000)

                # Extract key fields from the page
                scraped = await self._extract_tender_details(page)
                verification_result['scraped_data'] = scraped

                # Compare with database data
                discrepancies = self._find_discrepancies(tender_data, scraped)
                verification_result['discrepancies'] = discrepancies

                if discrepancies:
                    logger.warning(f"Found {len(discrepancies)} discrepancies for {tender_id}")
                    self.stats['data_updated'] += 1

                # Check for missing data that was filled
                missing_filled = self._check_missing_filled(tender_data, scraped)
                verification_result['missing_filled'] = missing_filled

                if missing_filled:
                    self.stats['missing_data_filled'] += len(missing_filled)

                # Web search enrichment
                if self.web_search and self.gemini_model:
                    web_context = await self._web_search_enrichment(tender_data)
                    verification_result['web_context'] = web_context

                    if web_context and web_context.get('corruption_mentions'):
                        verification_result['corruption_indicators'] = web_context['corruption_mentions']
                        self.stats['corruption_indicators'] += 1

                    self.stats['web_enrichments'] += 1

                self.stats['tenders_verified'] += 1

            except Exception as e:
                logger.error(f"Error verifying tender {tender_id}: {e}")
                verification_result['error'] = str(e)
                self.stats['errors'] += 1
            finally:
                try:
                    await page.close()
                except:
                    pass

        # Save verification result to database
        await self._save_verification_result(verification_result)

        yield verification_result

    async def _extract_tender_details(self, page) -> Dict[str, Any]:
        """Extract tender details from the page."""
        result = {}

        try:
            # Extract title
            title_elem = await page.query_selector('h1, .tender-title, [class*="title"]')
            if title_elem:
                result['title'] = await title_elem.inner_text()

            # Extract entity (procuring organization)
            entity_selectors = [
                '[class*="entity"]', '[class*="buyer"]',
                '[class*="institution"]', '[class*="contract"]'
            ]
            for selector in entity_selectors:
                elem = await page.query_selector(selector)
                if elem:
                    result['procuring_entity'] = await elem.inner_text()
                    break

            # Extract winner if available
            winner_selectors = [
                '[class*="winner"]', '[class*="contractor"]',
                '[class*="supplier"]', 'td:has-text("Добитник")+td'
            ]
            for selector in winner_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        result['winner'] = await elem.inner_text()
                        break
                except:
                    continue

            # Extract value
            value_patterns = ['МКД', 'денар', 'MKD']
            content = await page.content()
            for pattern in value_patterns:
                if pattern in content:
                    # Use regex to find value near the pattern
                    import re
                    matches = re.findall(rf'([\d\.,]+)\s*{pattern}', content)
                    if matches:
                        result['value_text'] = matches[0]
                        break

            # Extract bidder count
            bidder_table = await page.query_selector('table[class*="bidder"], table[class*="offer"]')
            if bidder_table:
                rows = await bidder_table.query_selector_all('tbody tr')
                result['bidder_count'] = len(rows)

            # Extract documents list
            doc_links = await page.query_selector_all('a[href*=".pdf"], a[href*="download"]')
            result['document_count'] = len(doc_links)

            # Extract dates
            date_patterns = [
                (r'Датум на објава[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{4})', 'publication_date'),
                (r'Рок за поднесување[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{4})', 'deadline'),
            ]
            for pattern, field in date_patterns:
                import re
                match = re.search(pattern, content)
                if match:
                    result[field] = match.group(1)

        except Exception as e:
            logger.error(f"Error extracting tender details: {e}")

        return result

    def _find_discrepancies(self, db_data: Dict, scraped: Dict) -> List[Dict]:
        """Compare database data with scraped data to find discrepancies."""
        discrepancies = []

        # Fields to compare
        compare_fields = [
            ('title', 'title'),
            ('procuring_entity', 'procuring_entity'),
            ('winner', 'winner'),
        ]

        for db_field, scraped_field in compare_fields:
            db_value = db_data.get(db_field, '')
            scraped_value = scraped.get(scraped_field, '')

            if db_value and scraped_value:
                # Normalize for comparison
                db_norm = str(db_value).lower().strip()
                scraped_norm = str(scraped_value).lower().strip()

                if db_norm != scraped_norm:
                    # Check if it's a significant difference
                    from difflib import SequenceMatcher
                    similarity = SequenceMatcher(None, db_norm, scraped_norm).ratio()

                    if similarity < 0.8:  # Less than 80% similar
                        discrepancies.append({
                            'field': db_field,
                            'db_value': db_value,
                            'scraped_value': scraped_value,
                            'similarity': similarity,
                        })

        return discrepancies

    def _check_missing_filled(self, db_data: Dict, scraped: Dict) -> List[Dict]:
        """Check what missing data was filled from scraping."""
        filled = []

        missing_fields = ['winner', 'bidder_count', 'document_count']

        for field in missing_fields:
            db_value = db_data.get(field)
            scraped_value = scraped.get(field)

            if not db_value and scraped_value:
                filled.append({
                    'field': field,
                    'value': scraped_value,
                })

        return filled

    async def _web_search_enrichment(self, tender_data: Dict) -> Optional[Dict]:
        """Use Gemini to search web for context about the tender."""
        if not self.gemini_model:
            return None

        try:
            # Build search query from tender data
            entity = tender_data.get('procuring_entity', '')
            winner = tender_data.get('winner', '')
            value = tender_data.get('estimated_value_mkd', '') or tender_data.get('actual_value_mkd', '')

            search_context = f"""
Analyze this Macedonian public procurement tender for potential corruption indicators:

Procuring Entity: {entity}
Winner/Contractor: {winner}
Value: {value} MKD
Title: {tender_data.get('title', '')}

Search for:
1. Any news articles mentioning corruption, investigation, or scandal involving these entities
2. Connections between the buyer and winner (conflicts of interest)
3. Historical contract patterns (always same winner, unusual pricing)
4. Red flags mentioned in Macedonian media

Return JSON with:
{{
  "corruption_mentions": [list of relevant news/articles found],
  "red_flags": [list of potential concerns],
  "entity_connections": [any known relationships],
  "recommendation": "low_risk" | "medium_risk" | "high_risk" | "investigate"
}}
"""

            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                search_context
            )

            # Parse response
            text = response.text
            # Try to extract JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())

            return {'raw_response': text}

        except Exception as e:
            logger.error(f"Web search enrichment error: {e}")
            return {'error': str(e)}

    async def _save_verification_result(self, result: Dict):
        """Save verification result to database."""
        await self._init_db()

        try:
            async with self.db_pool.acquire() as conn:
                # Upsert into tender_verifications table
                await conn.execute("""
                    INSERT INTO tender_verifications (
                        tender_id, verified_at, source_url,
                        scraped_data, discrepancies, missing_filled,
                        web_context, corruption_indicators
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (tender_id) DO UPDATE SET
                        verified_at = EXCLUDED.verified_at,
                        scraped_data = EXCLUDED.scraped_data,
                        discrepancies = EXCLUDED.discrepancies,
                        missing_filled = EXCLUDED.missing_filled,
                        web_context = EXCLUDED.web_context,
                        corruption_indicators = EXCLUDED.corruption_indicators
                """,
                    result['tender_id'],
                    datetime.utcnow(),
                    result['source_url'],
                    json.dumps(result.get('scraped_data', {})),
                    json.dumps(result.get('discrepancies', [])),
                    json.dumps(result.get('missing_filled', [])),
                    json.dumps(result.get('web_context')) if result.get('web_context') else None,
                    json.dumps(result.get('corruption_indicators', [])),
                )

                # Update corruption_flags if web search found indicators
                if result.get('corruption_indicators'):
                    await conn.execute("""
                        UPDATE corruption_flags
                        SET web_verified = true,
                            web_context = $2,
                            updated_at = NOW()
                        WHERE tender_id = $1
                    """,
                        result['tender_id'],
                        json.dumps(result['corruption_indicators']),
                    )

        except Exception as e:
            logger.error(f"Error saving verification result: {e}")

    async def errback(self, failure):
        """Handle request errors."""
        logger.error(f"Request failed: {failure.value}")
        self.stats['errors'] += 1

    def closed(self, reason):
        """Spider closed - log final statistics."""
        logger.warning("="*60)
        logger.warning("VERIFICATION SPIDER COMPLETED")
        logger.warning("="*60)
        logger.warning(f"Tenders verified: {self.stats['tenders_verified']}")
        logger.warning(f"Data discrepancies found: {self.stats['data_updated']}")
        logger.warning(f"Missing data filled: {self.stats['missing_data_filled']}")
        logger.warning(f"Web enrichments: {self.stats['web_enrichments']}")
        logger.warning(f"Corruption indicators found: {self.stats['corruption_indicators']}")
        logger.warning(f"Errors: {self.stats['errors']}")
        logger.warning("="*60)

        # Close database pool
        if self.db_pool:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.db_pool.close())

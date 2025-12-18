"""
E-Pazar Research Agent for Corruption Detection

This agent fetches data from e-pazar.mk - the Macedonian electronic marketplace
for small-value public procurement.

E-Pazar is complementary to e-nabavki.gov.mk:
- e-nabavki: Large tenders (above threshold)
- e-pazar: Small-value purchases (below threshold)

Both sources are essential for complete corruption analysis.

Key URLs:
- Tender listing: https://e-pazar.mk/PublicTenders
- Tender details: https://e-pazar.mk/PublicTenders/Details/{id}

Author: nabavkidata.com
"""

import asyncio
import aiohttp
import asyncpg
import logging
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import quote, urlencode

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EPazarTender:
    """E-Pazar tender details"""
    tender_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    contracting_authority: Optional[str] = None
    estimated_value_mkd: Optional[float] = None
    awarded_value_mkd: Optional[float] = None
    deadline: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    publication_date: Optional[str] = None
    source_url: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class EPazarOffer:
    """E-Pazar offer/bid information"""
    supplier_name: str
    offer_amount_mkd: Optional[float] = None
    is_winner: bool = False
    rank: Optional[int] = None
    submitted_at: Optional[str] = None


@dataclass
class EPazarTenderDetails:
    """Complete E-Pazar tender with offers"""
    tender: EPazarTender
    offers: List[EPazarOffer] = field(default_factory=list)
    total_offers: int = 0
    winner_name: Optional[str] = None
    winner_amount: Optional[float] = None


@dataclass
class EPazarSearchResult:
    """E-Pazar search results"""
    query: str
    tenders: List[EPazarTender] = field(default_factory=list)
    total_count: int = 0
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# =============================================================================
# DATABASE CONFIG
# =============================================================================

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'nabavki_user'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'nabavkidata')
}


# =============================================================================
# MAIN AGENT CLASS
# =============================================================================

class EPazarAgent:
    """
    Agent for researching E-Pazar (e-pazar.mk) data.

    This agent can:
    1. Query our local database for cached e-pazar data
    2. Fetch fresh data from the e-pazar.mk website
    3. Search e-pazar tenders by keyword, institution, or supplier
    4. Analyze e-pazar patterns for corruption indicators

    Key corruption indicators in e-pazar:
    - Same supplier winning repeatedly from same institution
    - Prices close to threshold (avoiding formal tender process)
    - Unusually short deadlines
    - Split purchases (avoiding threshold)
    """

    BASE_URL = "https://e-pazar.mk"

    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'mk-MK,mk;q=0.9,en;q=0.8',
    }

    def __init__(self, pool: Optional[asyncpg.Pool] = None):
        """
        Initialize the E-Pazar agent.

        Args:
            pool: Optional database connection pool
        """
        self._pool = pool
        self._owns_pool = pool is None
        self._session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=30)

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create database pool"""
        if self._pool is None or self._pool._closed:
            self._pool = await asyncpg.create_pool(**DB_CONFIG, min_size=1, max_size=5)
            self._owns_pool = True
        return self._pool

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers=self.DEFAULT_HEADERS
            )
        return self._session

    async def close(self):
        """Close connections"""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._owns_pool and self._pool and not self._pool._closed:
            await self._pool.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # =========================================================================
    # DATABASE METHODS (query our cached e-pazar data)
    # =========================================================================

    async def search_db_tenders(
        self,
        keywords: List[str],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        institution: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Search e-pazar tenders in our database.

        Args:
            keywords: Search keywords
            date_from: Start date filter
            date_to: End date filter
            institution: Institution name filter
            limit: Max results

        Returns:
            List of tender dicts
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            patterns = [f"%{kw}%" for kw in keywords if len(kw) >= 2]

            if not patterns:
                return []

            params = [patterns]
            filters = ["(et.title ILIKE ANY($1) OR et.description ILIKE ANY($1))"]

            if institution:
                params.append(f"%{institution}%")
                filters.append(f"et.contracting_authority ILIKE ${len(params)}")

            if date_from:
                params.append(date_from)
                filters.append(f"et.publication_date >= ${len(params)}")

            if date_to:
                params.append(date_to)
                filters.append(f"et.publication_date <= ${len(params)}")

            query = f"""
                SELECT
                    et.tender_id,
                    et.title,
                    et.description,
                    et.contracting_authority,
                    et.estimated_value_mkd,
                    et.awarded_value_mkd,
                    et.status,
                    et.publication_date,
                    et.deadline,
                    eo.supplier_name as winner,
                    eo.offer_amount_mkd as winning_bid
                FROM epazar_tenders et
                LEFT JOIN epazar_offers eo ON et.tender_id = eo.tender_id AND eo.is_winner = true
                WHERE {' AND '.join(filters)}
                ORDER BY et.publication_date DESC
                LIMIT {limit}
            """

            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]

    async def get_supplier_history(self, supplier_name: str) -> Dict:
        """
        Get complete history for a supplier in e-pazar.

        Args:
            supplier_name: Supplier/company name

        Returns:
            Dict with win statistics, institutions served, patterns
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # Get all offers by this supplier
            query = """
                SELECT
                    eo.tender_id,
                    eo.supplier_name,
                    eo.offer_amount_mkd,
                    eo.is_winner,
                    eo.rank,
                    et.title,
                    et.contracting_authority,
                    et.estimated_value_mkd,
                    et.awarded_value_mkd,
                    et.publication_date
                FROM epazar_offers eo
                JOIN epazar_tenders et ON eo.tender_id = et.tender_id
                WHERE LOWER(eo.supplier_name) ILIKE LOWER($1)
                   OR eo.supplier_name ILIKE $1
                ORDER BY et.publication_date DESC
            """

            rows = await conn.fetch(query, f"%{supplier_name}%")
            offers = [dict(r) for r in rows]

            # Calculate statistics
            total_bids = len(offers)
            wins = sum(1 for o in offers if o.get('is_winner'))
            win_rate = wins / total_bids * 100 if total_bids > 0 else 0

            # Group by institution
            institution_stats = {}
            for offer in offers:
                inst = offer.get('contracting_authority', 'Unknown')
                if inst not in institution_stats:
                    institution_stats[inst] = {'bids': 0, 'wins': 0, 'total_value': 0}
                institution_stats[inst]['bids'] += 1
                if offer.get('is_winner'):
                    institution_stats[inst]['wins'] += 1
                    institution_stats[inst]['total_value'] += offer.get('awarded_value_mkd') or 0

            return {
                'supplier_name': supplier_name,
                'total_bids': total_bids,
                'wins': wins,
                'win_rate': win_rate,
                'offers': offers[:50],  # Limit for response size
                'institution_breakdown': institution_stats
            }

    async def get_institution_epazar_stats(self, institution_name: str) -> Dict:
        """
        Get e-pazar statistics for an institution.

        Useful for corruption analysis:
        - Are they always using the same suppliers?
        - Are they splitting purchases to stay below threshold?
        - Unusual patterns in timing or values?

        Args:
            institution_name: Institution/authority name

        Returns:
            Dict with statistics and potential red flags
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # Get all tenders
            tender_query = """
                SELECT
                    et.tender_id,
                    et.title,
                    et.estimated_value_mkd,
                    et.awarded_value_mkd,
                    et.publication_date,
                    et.deadline,
                    eo.supplier_name as winner
                FROM epazar_tenders et
                LEFT JOIN epazar_offers eo ON et.tender_id = eo.tender_id AND eo.is_winner = true
                WHERE et.contracting_authority ILIKE $1
                ORDER BY et.publication_date DESC
            """

            tenders = await conn.fetch(tender_query, f"%{institution_name}%")
            tender_list = [dict(t) for t in tenders]

            # Winner distribution
            winner_query = """
                SELECT
                    eo.supplier_name,
                    COUNT(*) as wins,
                    SUM(et.awarded_value_mkd) as total_value
                FROM epazar_tenders et
                JOIN epazar_offers eo ON et.tender_id = eo.tender_id AND eo.is_winner = true
                WHERE et.contracting_authority ILIKE $1
                GROUP BY eo.supplier_name
                ORDER BY wins DESC
                LIMIT 20
            """

            winners = await conn.fetch(winner_query, f"%{institution_name}%")
            winner_dist = [dict(w) for w in winners]

            # Value distribution (check for threshold avoidance)
            value_query = """
                SELECT
                    CASE
                        WHEN estimated_value_mkd < 100000 THEN 'under_100k'
                        WHEN estimated_value_mkd < 500000 THEN '100k_500k'
                        WHEN estimated_value_mkd < 1000000 THEN '500k_1m'
                        ELSE 'over_1m'
                    END as value_range,
                    COUNT(*) as count,
                    SUM(awarded_value_mkd) as total_value
                FROM epazar_tenders
                WHERE contracting_authority ILIKE $1
                GROUP BY value_range
            """

            value_dist = await conn.fetch(value_query, f"%{institution_name}%")

            # Analyze for red flags
            red_flags = []

            # Check for dominant supplier (>50% wins)
            total_wins = sum(w.get('wins', 0) for w in winner_dist)
            if winner_dist and total_wins > 0:
                top_supplier_pct = winner_dist[0].get('wins', 0) / total_wins * 100
                if top_supplier_pct > 50:
                    red_flags.append({
                        'type': 'dominant_supplier',
                        'severity': 'high',
                        'description': f"{winner_dist[0]['supplier_name']} wins {top_supplier_pct:.0f}% of tenders"
                    })

            # Check for split purchasing pattern (many tenders just below threshold)
            threshold_tenders = [t for t in tender_list
                               if t.get('estimated_value_mkd') and
                               400000 <= t['estimated_value_mkd'] <= 500000]
            if len(threshold_tenders) > 5:
                red_flags.append({
                    'type': 'split_purchasing',
                    'severity': 'medium',
                    'description': f"{len(threshold_tenders)} tenders near 500k threshold - possible split purchasing"
                })

            return {
                'institution_name': institution_name,
                'total_tenders': len(tender_list),
                'tenders': tender_list[:30],
                'winner_distribution': winner_dist,
                'value_distribution': [dict(v) for v in value_dist],
                'red_flags': red_flags
            }

    async def detect_split_purchasing(self, institution_name: str, time_window_days: int = 30) -> Dict:
        """
        Detect potential split purchasing patterns.

        Split purchasing is when an institution breaks up a larger purchase
        into multiple smaller ones to avoid formal tender requirements.

        Red flag indicators:
        - Multiple similar purchases in short time period
        - Values just below threshold
        - Same or similar suppliers
        - Related product categories

        Args:
            institution_name: Institution to analyze
            time_window_days: Days to look for patterns

        Returns:
            Dict with potential split purchasing incidents
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            query = """
                WITH tenders_with_winner AS (
                    SELECT
                        et.tender_id,
                        et.title,
                        et.estimated_value_mkd,
                        et.publication_date,
                        eo.supplier_name as winner
                    FROM epazar_tenders et
                    LEFT JOIN epazar_offers eo ON et.tender_id = eo.tender_id AND eo.is_winner = true
                    WHERE et.contracting_authority ILIKE $1
                      AND et.publication_date >= NOW() - INTERVAL '%s days'
                    ORDER BY et.publication_date
                )
                SELECT * FROM tenders_with_winner
            """ % time_window_days

            tenders = await conn.fetch(query, f"%{institution_name}%")
            tender_list = [dict(t) for t in tenders]

            # Group by similar titles (potential splits)
            from collections import defaultdict
            title_groups = defaultdict(list)

            for tender in tender_list:
                # Normalize title for grouping
                title = tender.get('title', '').lower()
                # Remove numbers and common words
                normalized = re.sub(r'\d+|набавка|на|за|и|од|во|со', '', title).strip()
                if normalized:
                    title_groups[normalized[:30]].append(tender)

            # Find suspicious groups
            suspicious_splits = []

            for title_key, group in title_groups.items():
                if len(group) >= 3:  # 3+ similar tenders
                    total_value = sum(t.get('estimated_value_mkd') or 0 for t in group)
                    suppliers = set(t.get('winner') for t in group if t.get('winner'))

                    suspicious_splits.append({
                        'pattern': title_key,
                        'tender_count': len(group),
                        'total_combined_value': total_value,
                        'individual_tenders': group,
                        'unique_suppliers': len(suppliers),
                        'suppliers': list(suppliers),
                        'severity': 'high' if total_value > 1000000 and len(suppliers) <= 2 else 'medium'
                    })

            return {
                'institution': institution_name,
                'time_window_days': time_window_days,
                'total_tenders_analyzed': len(tender_list),
                'suspicious_split_patterns': suspicious_splits,
                'risk_level': 'high' if any(s['severity'] == 'high' for s in suspicious_splits) else
                             'medium' if suspicious_splits else 'low'
            }

    # =========================================================================
    # WEB SCRAPING METHODS (fetch fresh data from e-pazar.mk)
    # =========================================================================

    async def fetch_tender_details(self, tender_id: str) -> Optional[EPazarTenderDetails]:
        """
        Fetch fresh tender details from e-pazar.mk website.

        Note: E-pazar.mk may require JavaScript rendering.
        This method attempts to fetch what's available via HTTP.

        Args:
            tender_id: E-Pazar tender ID

        Returns:
            EPazarTenderDetails or None if fetch fails
        """
        session = await self._get_session()

        url = f"{self.BASE_URL}/PublicTenders/Details/{quote(tender_id)}"

        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"E-Pazar fetch failed: HTTP {response.status}")
                    return None

                html = await response.text()

                # Parse basic info from HTML
                # Note: This is best-effort parsing without JavaScript
                tender = EPazarTender(
                    tender_id=tender_id,
                    source_url=url
                )

                # Try to extract title
                title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
                if title_match:
                    tender.title = title_match.group(1).strip()

                # Try to extract value
                value_match = re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:ден|МКД|MKD)', html)
                if value_match:
                    value_str = value_match.group(1).replace('.', '').replace(',', '.')
                    try:
                        tender.estimated_value_mkd = float(value_str)
                    except ValueError:
                        pass

                return EPazarTenderDetails(
                    tender=tender,
                    offers=[],
                    total_offers=0
                )

        except Exception as e:
            logger.error(f"E-Pazar fetch error: {e}")
            return None

    async def search_web(self, query: str, limit: int = 20) -> EPazarSearchResult:
        """
        Search e-pazar.mk website for tenders.

        Args:
            query: Search query
            limit: Max results

        Returns:
            EPazarSearchResult with found tenders
        """
        session = await self._get_session()

        search_url = f"{self.BASE_URL}/PublicTenders"
        params = {'search': query}

        try:
            async with session.get(search_url, params=params) as response:
                if response.status != 200:
                    return EPazarSearchResult(query=query)

                html = await response.text()

                # Parse search results
                tenders = []

                # Look for tender links
                tender_links = re.findall(r'/PublicTenders/Details/(\d+)', html)

                for tid in tender_links[:limit]:
                    tenders.append(EPazarTender(
                        tender_id=tid,
                        source_url=f"{self.BASE_URL}/PublicTenders/Details/{tid}"
                    ))

                return EPazarSearchResult(
                    query=query,
                    tenders=tenders,
                    total_count=len(tenders)
                )

        except Exception as e:
            logger.error(f"E-Pazar search error: {e}")
            return EPazarSearchResult(query=query)

    # =========================================================================
    # PARALLEL SEARCH (combines DB + web)
    # =========================================================================

    async def parallel_search(
        self,
        keywords: List[str],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict:
        """
        Search both database and web in parallel.

        This is the recommended method for comprehensive results.

        Args:
            keywords: Search keywords
            date_from: Optional start date
            date_to: Optional end date

        Returns:
            Dict with combined results from DB and web
        """
        # Run DB and web searches in parallel
        db_task = self.search_db_tenders(keywords, date_from, date_to)
        web_task = self.search_web(" ".join(keywords[:3]))

        db_results, web_results = await asyncio.gather(
            db_task,
            web_task,
            return_exceptions=True
        )

        # Handle exceptions
        if isinstance(db_results, Exception):
            logger.error(f"DB search failed: {db_results}")
            db_results = []
        if isinstance(web_results, Exception):
            logger.error(f"Web search failed: {web_results}")
            web_results = EPazarSearchResult(query=" ".join(keywords))

        # Combine results
        db_tender_ids = {t['tender_id'] for t in db_results}

        return {
            'keywords': keywords,
            'db_results': db_results,
            'db_count': len(db_results),
            'web_results': [asdict(t) for t in web_results.tenders],
            'web_count': web_results.total_count,
            'new_from_web': [t for t in web_results.tenders if t.tender_id not in db_tender_ids],
            'sources': ['database', 'e-pazar.mk'],
            'fetched_at': datetime.utcnow().isoformat()
        }


# =============================================================================
# CLI INTERFACE
# =============================================================================

async def main():
    """Test the E-Pazar agent"""
    import sys

    logging.basicConfig(level=logging.INFO)

    async with EPazarAgent() as agent:
        if len(sys.argv) < 2:
            print("Usage:")
            print("  python epazar_agent.py search <keywords>")
            print("  python epazar_agent.py supplier <name>")
            print("  python epazar_agent.py institution <name>")
            print("  python epazar_agent.py splits <institution>")
            return

        command = sys.argv[1]
        target = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else ''

        if command == 'search':
            results = await agent.parallel_search(target.split())
            print(json.dumps(results, indent=2, ensure_ascii=False, default=str))

        elif command == 'supplier':
            results = await agent.get_supplier_history(target)
            print(json.dumps(results, indent=2, ensure_ascii=False, default=str))

        elif command == 'institution':
            results = await agent.get_institution_epazar_stats(target)
            print(json.dumps(results, indent=2, ensure_ascii=False, default=str))

        elif command == 'splits':
            results = await agent.detect_split_purchasing(target)
            print(json.dumps(results, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())

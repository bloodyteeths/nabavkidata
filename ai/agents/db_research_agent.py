"""
Database Research Agent for Corruption Detection

This agent performs comprehensive database queries to gather ALL relevant data
about a tender, company, or institution for corruption analysis.

It retrieves:
- Full tender details with bidders, documents, and product items
- Historical data for companies and institutions
- Price comparisons with similar tenders
- Existing corruption flags and risk scores
- Related entities and suspicious patterns

Author: nabavkidata.com
"""

import asyncio
import asyncpg
import logging
import os
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import json
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration from environment
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'nabavki_user'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'nabavkidata'),
    'min_size': 2,
    'max_size': 10,
    'command_timeout': 60
}


def json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return obj.total_seconds()
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    return str(obj)


@dataclass
class TenderResearch:
    """Complete research findings for a tender"""
    tender_id: str
    basic_info: Dict[str, Any]
    bidders: List[Dict[str, Any]]
    documents: List[Dict[str, Any]]
    product_items: List[Dict[str, Any]]
    winner_history: Dict[str, Any]
    institution_history: Dict[str, Any]
    similar_tenders: List[Dict[str, Any]]
    price_comparison: Dict[str, Any]
    corruption_flags: List[Dict[str, Any]]
    risk_score: Optional[Dict[str, Any]]
    related_companies: List[Dict[str, Any]]
    amendments: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=json_serializer, ensure_ascii=False, indent=2)


@dataclass
class CompanyResearch:
    """Complete research findings for a company"""
    company_name: str
    basic_info: Dict[str, Any]
    tender_history: List[Dict[str, Any]]
    win_statistics: Dict[str, Any]
    institution_relationships: List[Dict[str, Any]]
    bid_patterns: Dict[str, Any]
    product_categories: List[Dict[str, Any]]
    corruption_flags: List[Dict[str, Any]]
    related_companies: List[Dict[str, Any]]
    price_competitiveness: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=json_serializer, ensure_ascii=False, indent=2)


@dataclass
class InstitutionResearch:
    """Complete research findings for an institution"""
    institution_name: str
    basic_info: Dict[str, Any]
    tender_history: List[Dict[str, Any]]
    winner_distribution: List[Dict[str, Any]]
    bidder_statistics: Dict[str, Any]
    value_patterns: Dict[str, Any]
    deadline_patterns: Dict[str, Any]
    corruption_flags: List[Dict[str, Any]]
    category_breakdown: List[Dict[str, Any]]
    suspicious_patterns: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=json_serializer, ensure_ascii=False, indent=2)


class DBResearchAgent:
    """
    Database Research Agent for comprehensive corruption analysis.

    This agent queries the PostgreSQL database to gather ALL relevant data
    about tenders, companies, and institutions for corruption detection.
    """

    def __init__(self, pool: Optional[asyncpg.Pool] = None):
        """
        Initialize the agent.

        Args:
            pool: Optional existing connection pool. If not provided,
                  a new pool will be created when needed.
        """
        self._pool = pool
        self._owns_pool = pool is None

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create the connection pool"""
        if self._pool is None or self._pool._closed:
            logger.info("Creating new database connection pool")
            self._pool = await asyncpg.create_pool(**DB_CONFIG)
            self._owns_pool = True
        return self._pool

    async def close(self):
        """Close the connection pool if we own it"""
        if self._owns_pool and self._pool is not None and not self._pool._closed:
            logger.info("Closing database connection pool")
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def _get_connection(self):
        """Context manager for getting a database connection"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            yield conn

    # =========================================================================
    # TENDER RESEARCH
    # =========================================================================

    async def research_tender(self, tender_id: str) -> TenderResearch:
        """
        Gather ALL database information about a tender.

        Args:
            tender_id: The tender ID to research

        Returns:
            TenderResearch object with all findings
        """
        logger.info(f"Researching tender: {tender_id}")

        async with self._get_connection() as conn:
            # Execute all queries in parallel where possible
            results = await asyncio.gather(
                self._get_tender_basic_info(conn, tender_id),
                self._get_tender_bidders(conn, tender_id),
                self._get_tender_documents(conn, tender_id),
                self._get_tender_product_items(conn, tender_id),
                self._get_tender_amendments(conn, tender_id),
                self._get_tender_corruption_flags(conn, tender_id),
                self._get_tender_risk_score(conn, tender_id),
                return_exceptions=True
            )

            basic_info = results[0] if not isinstance(results[0], Exception) else {}
            bidders = results[1] if not isinstance(results[1], Exception) else []
            documents = results[2] if not isinstance(results[2], Exception) else []
            product_items = results[3] if not isinstance(results[3], Exception) else []
            amendments = results[4] if not isinstance(results[4], Exception) else []
            corruption_flags = results[5] if not isinstance(results[5], Exception) else []
            risk_score = results[6] if not isinstance(results[6], Exception) else None

            # Get winner and institution names from basic_info
            winner = basic_info.get('winner', '') if basic_info else ''
            institution = basic_info.get('procuring_entity', '') if basic_info else ''
            cpv_code = basic_info.get('cpv_code', '') if basic_info else ''

            # Execute dependent queries
            dependent_results = await asyncio.gather(
                self._get_company_history_summary(conn, winner) if winner else self._empty_dict(),
                self._get_institution_history_summary(conn, institution) if institution else self._empty_dict(),
                self._get_similar_tenders(conn, cpv_code, institution, tender_id) if cpv_code or institution else self._empty_list(),
                self._get_price_comparison(conn, tender_id, cpv_code) if cpv_code else self._empty_dict(),
                self._find_related_companies_for_tender(conn, tender_id),
                return_exceptions=True
            )

            winner_history = dependent_results[0] if not isinstance(dependent_results[0], Exception) else {}
            institution_history = dependent_results[1] if not isinstance(dependent_results[1], Exception) else {}
            similar_tenders = dependent_results[2] if not isinstance(dependent_results[2], Exception) else []
            price_comparison = dependent_results[3] if not isinstance(dependent_results[3], Exception) else {}
            related_companies = dependent_results[4] if not isinstance(dependent_results[4], Exception) else []

            return TenderResearch(
                tender_id=tender_id,
                basic_info=basic_info,
                bidders=bidders,
                documents=documents,
                product_items=product_items,
                winner_history=winner_history,
                institution_history=institution_history,
                similar_tenders=similar_tenders,
                price_comparison=price_comparison,
                corruption_flags=corruption_flags,
                risk_score=risk_score,
                related_companies=related_companies,
                amendments=amendments
            )

    async def _empty_dict(self) -> Dict:
        return {}

    async def _empty_list(self) -> List:
        return []

    async def _get_tender_basic_info(self, conn: asyncpg.Connection, tender_id: str) -> Dict[str, Any]:
        """Get basic tender information"""
        query = """
            SELECT
                t.tender_id,
                t.title,
                t.description,
                t.procuring_entity,
                t.procuring_entity_code,
                t.winner,
                t.winner_tax_id,
                t.estimated_value_mkd,
                t.estimated_value_eur,
                t.awarded_value_mkd,
                t.awarded_value_eur,
                t.status,
                t.cpv_code,
                t.category,
                t.procedure_type,
                t.publication_date,
                t.opening_date,
                t.closing_date,
                t.num_bidders,
                t.contact_person,
                t.contact_email,
                t.contact_phone,
                t.evaluation_method,
                t.award_criteria,
                t.has_lots,
                t.num_lots,
                t.amendment_count,
                t.source_url,
                t.created_at,
                t.updated_at
            FROM tenders t
            WHERE t.tender_id = $1
        """

        row = await conn.fetchrow(query, tender_id)
        if row:
            return dict(row)
        return {}

    async def _get_tender_bidders(self, conn: asyncpg.Connection, tender_id: str) -> List[Dict[str, Any]]:
        """Get all bidders for a tender with their bids"""
        query = """
            SELECT
                tb.bidder_id,
                tb.company_name,
                tb.company_tax_id,
                tb.company_address,
                tb.bid_amount_mkd,
                tb.bid_amount_eur,
                tb.is_winner,
                tb.rank,
                tb.disqualified,
                tb.disqualification_reason,
                tb.lot_id,
                tl.lot_number,
                tl.lot_title
            FROM tender_bidders tb
            LEFT JOIN tender_lots tl ON tb.lot_id = tl.lot_id
            WHERE tb.tender_id = $1
            ORDER BY tb.rank ASC NULLS LAST, tb.bid_amount_mkd ASC NULLS LAST
        """

        rows = await conn.fetch(query, tender_id)
        return [dict(row) for row in rows]

    async def _get_tender_documents(self, conn: asyncpg.Connection, tender_id: str) -> List[Dict[str, Any]]:
        """Get all documents associated with a tender"""
        query = """
            SELECT
                d.doc_id,
                d.doc_type,
                d.doc_category,
                d.file_name,
                d.file_url,
                d.file_size_bytes,
                d.mime_type,
                d.page_count,
                d.extraction_status,
                LENGTH(d.content_text) as content_length,
                d.created_at
            FROM documents d
            WHERE d.tender_id = $1
            ORDER BY d.created_at DESC
        """

        rows = await conn.fetch(query, tender_id)
        return [dict(row) for row in rows]

    async def _get_tender_product_items(self, conn: asyncpg.Connection, tender_id: str) -> List[Dict[str, Any]]:
        """Get all product items from a tender"""
        query = """
            SELECT
                pi.id,
                pi.item_number,
                pi.lot_number,
                pi.name,
                pi.name_mk,
                pi.name_en,
                pi.quantity,
                pi.unit,
                pi.unit_price,
                pi.total_price,
                pi.currency,
                pi.specifications,
                pi.cpv_code,
                pi.category,
                pi.manufacturer,
                pi.model,
                pi.supplier
            FROM product_items pi
            WHERE pi.tender_id = $1
            ORDER BY pi.lot_number, pi.item_number
        """

        rows = await conn.fetch(query, tender_id)
        return [dict(row) for row in rows]

    async def _get_tender_amendments(self, conn: asyncpg.Connection, tender_id: str) -> List[Dict[str, Any]]:
        """Get all amendments to a tender"""
        query = """
            SELECT
                ta.amendment_id,
                ta.amendment_date,
                ta.amendment_type,
                ta.field_changed,
                ta.old_value,
                ta.new_value,
                ta.reason,
                ta.announcement_url,
                ta.created_at
            FROM tender_amendments ta
            WHERE ta.tender_id = $1
            ORDER BY ta.amendment_date DESC
        """

        rows = await conn.fetch(query, tender_id)
        return [dict(row) for row in rows]

    async def _get_tender_corruption_flags(self, conn: asyncpg.Connection, tender_id: str) -> List[Dict[str, Any]]:
        """Get existing corruption flags for a tender"""
        query = """
            SELECT
                cf.flag_id,
                cf.flag_type,
                cf.severity,
                cf.score,
                cf.evidence,
                cf.description,
                cf.detected_at,
                cf.reviewed,
                cf.false_positive
            FROM corruption_flags cf
            WHERE cf.tender_id = $1
            ORDER BY cf.score DESC, cf.detected_at DESC
        """

        rows = await conn.fetch(query, tender_id)
        return [dict(row) for row in rows]

    async def _get_tender_risk_score(self, conn: asyncpg.Connection, tender_id: str) -> Optional[Dict[str, Any]]:
        """Get the aggregated risk score for a tender"""
        query = """
            SELECT
                trs.tender_id,
                trs.risk_score,
                trs.risk_level,
                trs.flag_count,
                trs.last_analyzed,
                trs.flags_summary
            FROM tender_risk_scores trs
            WHERE trs.tender_id = $1
        """

        row = await conn.fetchrow(query, tender_id)
        if row:
            return dict(row)
        return None

    async def _get_similar_tenders(
        self,
        conn: asyncpg.Connection,
        cpv_code: str,
        institution: str,
        exclude_tender_id: str
    ) -> List[Dict[str, Any]]:
        """Get similar tenders by CPV code or same institution"""
        query = """
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.winner,
                t.estimated_value_mkd,
                t.awarded_value_mkd,
                t.num_bidders,
                t.status,
                t.cpv_code,
                t.publication_date,
                CASE
                    WHEN t.cpv_code = $1 AND t.procuring_entity = $2 THEN 'same_cpv_and_institution'
                    WHEN t.cpv_code = $1 THEN 'same_cpv'
                    WHEN t.procuring_entity = $2 THEN 'same_institution'
                END as similarity_type
            FROM tenders t
            WHERE t.tender_id != $3
              AND (
                  (t.cpv_code = $1 AND $1 IS NOT NULL AND $1 != '')
                  OR (t.procuring_entity = $2 AND $2 IS NOT NULL AND $2 != '')
              )
              AND t.status IN ('awarded', 'closed')
            ORDER BY
                CASE WHEN t.cpv_code = $1 AND t.procuring_entity = $2 THEN 0
                     WHEN t.cpv_code = $1 THEN 1
                     ELSE 2
                END,
                t.publication_date DESC
            LIMIT 50
        """

        rows = await conn.fetch(query, cpv_code, institution, exclude_tender_id)
        return [dict(row) for row in rows]

    async def _get_price_comparison(
        self,
        conn: asyncpg.Connection,
        tender_id: str,
        cpv_code: str
    ) -> Dict[str, Any]:
        """Compare prices with similar tenders"""
        query = """
            WITH target_tender AS (
                SELECT
                    estimated_value_mkd,
                    awarded_value_mkd,
                    cpv_code,
                    num_bidders
                FROM tenders
                WHERE tender_id = $1
            ),
            similar_tenders AS (
                SELECT
                    t.estimated_value_mkd,
                    t.awarded_value_mkd,
                    t.num_bidders
                FROM tenders t, target_tender tt
                WHERE t.cpv_code = $2
                  AND t.tender_id != $1
                  AND t.status = 'awarded'
                  AND t.awarded_value_mkd > 0
            )
            SELECT
                (SELECT COUNT(*) FROM similar_tenders) as similar_count,
                AVG(st.estimated_value_mkd) as avg_estimated_mkd,
                AVG(st.awarded_value_mkd) as avg_awarded_mkd,
                MIN(st.awarded_value_mkd) as min_awarded_mkd,
                MAX(st.awarded_value_mkd) as max_awarded_mkd,
                STDDEV(st.awarded_value_mkd) as stddev_awarded_mkd,
                AVG(st.num_bidders) as avg_bidders,
                tt.estimated_value_mkd as target_estimated_mkd,
                tt.awarded_value_mkd as target_awarded_mkd,
                tt.num_bidders as target_bidders,
                CASE
                    WHEN AVG(st.awarded_value_mkd) > 0 THEN
                        (tt.awarded_value_mkd - AVG(st.awarded_value_mkd)) / AVG(st.awarded_value_mkd) * 100
                    ELSE NULL
                END as price_deviation_pct
            FROM similar_tenders st, target_tender tt
            GROUP BY tt.estimated_value_mkd, tt.awarded_value_mkd, tt.num_bidders
        """

        row = await conn.fetchrow(query, tender_id, cpv_code)
        if row:
            return dict(row)
        return {}

    async def _find_related_companies_for_tender(
        self,
        conn: asyncpg.Connection,
        tender_id: str
    ) -> List[Dict[str, Any]]:
        """Find related companies that bid on a tender"""
        query = """
            WITH tender_companies AS (
                SELECT DISTINCT company_name
                FROM tender_bidders
                WHERE tender_id = $1
            )
            SELECT
                cr.company_a,
                cr.company_b,
                cr.relationship_type,
                cr.confidence,
                cr.evidence,
                cr.verified
            FROM company_relationships cr
            WHERE cr.company_a IN (SELECT company_name FROM tender_companies)
               OR cr.company_b IN (SELECT company_name FROM tender_companies)
            ORDER BY cr.confidence DESC
        """

        rows = await conn.fetch(query, tender_id)
        return [dict(row) for row in rows]

    # =========================================================================
    # COMPANY RESEARCH
    # =========================================================================

    async def research_company(self, company_name: str) -> CompanyResearch:
        """
        Gather ALL database information about a company.

        Args:
            company_name: The company name to research

        Returns:
            CompanyResearch object with all findings
        """
        logger.info(f"Researching company: {company_name}")

        async with self._get_connection() as conn:
            results = await asyncio.gather(
                self._get_company_basic_info(conn, company_name),
                self._get_company_tender_history(conn, company_name),
                self._get_company_win_statistics(conn, company_name),
                self._get_company_institution_relationships(conn, company_name),
                self._get_company_bid_patterns(conn, company_name),
                self._get_company_product_categories(conn, company_name),
                self._get_company_corruption_flags(conn, company_name),
                self._find_related_companies(conn, company_name),
                self._get_company_price_competitiveness(conn, company_name),
                return_exceptions=True
            )

            return CompanyResearch(
                company_name=company_name,
                basic_info=results[0] if not isinstance(results[0], Exception) else {},
                tender_history=results[1] if not isinstance(results[1], Exception) else [],
                win_statistics=results[2] if not isinstance(results[2], Exception) else {},
                institution_relationships=results[3] if not isinstance(results[3], Exception) else [],
                bid_patterns=results[4] if not isinstance(results[4], Exception) else {},
                product_categories=results[5] if not isinstance(results[5], Exception) else [],
                corruption_flags=results[6] if not isinstance(results[6], Exception) else [],
                related_companies=results[7] if not isinstance(results[7], Exception) else [],
                price_competitiveness=results[8] if not isinstance(results[8], Exception) else {}
            )

    async def _get_company_basic_info(self, conn: asyncpg.Connection, company_name: str) -> Dict[str, Any]:
        """Get basic company information from suppliers table"""
        query = """
            SELECT
                s.supplier_id,
                s.company_name,
                s.tax_id,
                s.company_type,
                s.address,
                s.city,
                s.contact_person,
                s.contact_email,
                s.contact_phone,
                s.website,
                s.total_wins,
                s.total_bids,
                s.win_rate,
                s.total_contract_value_mkd,
                s.industries,
                s.created_at,
                s.updated_at
            FROM suppliers s
            WHERE LOWER(s.company_name) = LOWER($1)
               OR s.company_name ILIKE $1
        """

        row = await conn.fetchrow(query, company_name)
        if row:
            return dict(row)
        return {}

    async def _get_company_tender_history(self, conn: asyncpg.Connection, company_name: str) -> List[Dict[str, Any]]:
        """Get all tenders the company has bid on"""
        query = """
            SELECT
                tb.tender_id,
                t.title,
                t.procuring_entity,
                t.status,
                t.publication_date,
                t.closing_date,
                t.cpv_code,
                t.estimated_value_mkd,
                t.awarded_value_mkd,
                tb.bid_amount_mkd,
                tb.is_winner,
                tb.rank,
                tb.disqualified,
                t.num_bidders,
                t.winner
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE LOWER(tb.company_name) = LOWER($1)
               OR tb.company_name ILIKE $1
            ORDER BY t.publication_date DESC
            LIMIT 200
        """

        rows = await conn.fetch(query, company_name)
        return [dict(row) for row in rows]

    async def _get_company_history_summary(self, conn: asyncpg.Connection, company_name: str) -> Dict[str, Any]:
        """Get a summary of company's historical performance"""
        if not company_name:
            return {}

        query = """
            SELECT
                COUNT(*) as total_bids,
                COUNT(*) FILTER (WHERE tb.is_winner = true) as total_wins,
                ROUND(COUNT(*) FILTER (WHERE tb.is_winner = true) * 100.0 / NULLIF(COUNT(*), 0), 2) as win_rate,
                SUM(CASE WHEN tb.is_winner THEN t.awarded_value_mkd ELSE 0 END) as total_won_value_mkd,
                AVG(tb.bid_amount_mkd) FILTER (WHERE tb.bid_amount_mkd > 0) as avg_bid_amount,
                COUNT(DISTINCT t.procuring_entity) as unique_institutions,
                COUNT(DISTINCT t.cpv_code) as unique_cpv_codes,
                MIN(t.publication_date) as first_tender_date,
                MAX(t.publication_date) as last_tender_date
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE LOWER(tb.company_name) = LOWER($1)
               OR tb.company_name ILIKE $1
        """

        row = await conn.fetchrow(query, company_name)
        if row:
            return dict(row)
        return {}

    async def _get_company_win_statistics(self, conn: asyncpg.Connection, company_name: str) -> Dict[str, Any]:
        """Get detailed win statistics for a company"""
        query = """
            WITH company_bids AS (
                SELECT
                    tb.tender_id,
                    tb.is_winner,
                    tb.bid_amount_mkd,
                    tb.rank,
                    t.procuring_entity,
                    t.cpv_code,
                    t.num_bidders,
                    t.awarded_value_mkd,
                    t.publication_date,
                    EXTRACT(YEAR FROM t.publication_date) as tender_year
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE LOWER(tb.company_name) = LOWER($1)
            )
            SELECT
                COUNT(*) as total_bids,
                COUNT(*) FILTER (WHERE is_winner = true) as total_wins,
                COUNT(*) FILTER (WHERE is_winner = false) as total_losses,
                ROUND(AVG(CASE WHEN is_winner THEN 1 ELSE 0 END) * 100, 2) as overall_win_rate,
                AVG(rank) FILTER (WHERE rank IS NOT NULL) as avg_rank,
                AVG(num_bidders) as avg_competitors,
                SUM(CASE WHEN is_winner THEN awarded_value_mkd ELSE 0 END) as total_won_value_mkd,
                AVG(CASE WHEN is_winner THEN awarded_value_mkd END) as avg_won_value_mkd,
                COUNT(*) FILTER (WHERE is_winner = true AND num_bidders = 1) as single_bidder_wins,
                jsonb_object_agg(
                    tender_year::text,
                    wins_by_year
                ) as wins_by_year
            FROM company_bids cb
            LEFT JOIN LATERAL (
                SELECT COUNT(*) FILTER (WHERE is_winner = true) as wins_by_year
                FROM company_bids cb2
                WHERE cb2.tender_year = cb.tender_year
            ) yearly ON true
            GROUP BY cb.tender_year
        """

        # Simplified query for aggregated stats
        simple_query = """
            WITH company_bids AS (
                SELECT
                    tb.tender_id,
                    tb.is_winner,
                    tb.bid_amount_mkd,
                    tb.rank,
                    t.procuring_entity,
                    t.cpv_code,
                    t.num_bidders,
                    t.awarded_value_mkd,
                    t.publication_date
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE LOWER(tb.company_name) = LOWER($1)
            )
            SELECT
                COUNT(*) as total_bids,
                COUNT(*) FILTER (WHERE is_winner = true) as total_wins,
                COUNT(*) FILTER (WHERE is_winner = false) as total_losses,
                ROUND(AVG(CASE WHEN is_winner THEN 1.0 ELSE 0.0 END) * 100, 2) as overall_win_rate,
                ROUND(AVG(rank) FILTER (WHERE rank IS NOT NULL), 2) as avg_rank,
                ROUND(AVG(num_bidders), 2) as avg_competitors,
                SUM(CASE WHEN is_winner THEN awarded_value_mkd ELSE 0 END) as total_won_value_mkd,
                ROUND(AVG(CASE WHEN is_winner THEN awarded_value_mkd END), 2) as avg_won_value_mkd,
                COUNT(*) FILTER (WHERE is_winner = true AND num_bidders = 1) as single_bidder_wins
            FROM company_bids
        """

        row = await conn.fetchrow(simple_query, company_name)
        if row:
            result = dict(row)

            # Get wins by year separately
            yearly_query = """
                SELECT
                    EXTRACT(YEAR FROM t.publication_date)::int as year,
                    COUNT(*) FILTER (WHERE tb.is_winner = true) as wins,
                    COUNT(*) as bids
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE LOWER(tb.company_name) = LOWER($1)
                  AND t.publication_date IS NOT NULL
                GROUP BY EXTRACT(YEAR FROM t.publication_date)
                ORDER BY year DESC
            """
            yearly_rows = await conn.fetch(yearly_query, company_name)
            result['yearly_stats'] = [dict(r) for r in yearly_rows]

            return result
        return {}

    async def _get_company_institution_relationships(
        self,
        conn: asyncpg.Connection,
        company_name: str
    ) -> List[Dict[str, Any]]:
        """Get institutions the company works with most"""
        query = """
            SELECT
                t.procuring_entity as institution,
                COUNT(*) as total_bids,
                COUNT(*) FILTER (WHERE tb.is_winner = true) as wins,
                ROUND(COUNT(*) FILTER (WHERE tb.is_winner = true) * 100.0 / COUNT(*), 2) as win_rate,
                SUM(CASE WHEN tb.is_winner THEN t.awarded_value_mkd ELSE 0 END) as total_won_value,
                MIN(t.publication_date) as first_interaction,
                MAX(t.publication_date) as last_interaction
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE LOWER(tb.company_name) = LOWER($1)
            GROUP BY t.procuring_entity
            HAVING COUNT(*) >= 2
            ORDER BY wins DESC, total_bids DESC
            LIMIT 30
        """

        rows = await conn.fetch(query, company_name)
        return [dict(row) for row in rows]

    async def _get_company_bid_patterns(self, conn: asyncpg.Connection, company_name: str) -> Dict[str, Any]:
        """Analyze bidding patterns for suspicious behavior"""
        query = """
            WITH company_bids AS (
                SELECT
                    tb.tender_id,
                    tb.bid_amount_mkd,
                    tb.is_winner,
                    t.estimated_value_mkd,
                    t.num_bidders,
                    t.closing_date - t.publication_date as days_open,
                    t.cpv_code
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE LOWER(tb.company_name) = LOWER($1)
                  AND tb.bid_amount_mkd > 0
            )
            SELECT
                COUNT(*) as total_analyzed_bids,
                AVG(CASE WHEN estimated_value_mkd > 0
                    THEN (bid_amount_mkd - estimated_value_mkd) / estimated_value_mkd * 100
                    END) as avg_bid_vs_estimate_pct,
                STDDEV(bid_amount_mkd) as bid_amount_stddev,
                AVG(days_open) as avg_days_to_submit,
                COUNT(*) FILTER (WHERE is_winner AND num_bidders = 1) as single_bidder_wins,
                COUNT(*) FILTER (WHERE is_winner AND days_open < 7) as short_deadline_wins,
                COUNT(DISTINCT cpv_code) as cpv_diversity
            FROM company_bids
        """

        row = await conn.fetchrow(query, company_name)
        if row:
            result = dict(row)

            # Check for co-bidding patterns
            cobid_query = """
                WITH company_tenders AS (
                    SELECT tender_id
                    FROM tender_bidders
                    WHERE LOWER(company_name) = LOWER($1)
                ),
                cobidders AS (
                    SELECT
                        tb.company_name as cobidder,
                        COUNT(*) as times_together
                    FROM tender_bidders tb
                    JOIN company_tenders ct ON tb.tender_id = ct.tender_id
                    WHERE LOWER(tb.company_name) != LOWER($1)
                    GROUP BY tb.company_name
                    HAVING COUNT(*) >= 3
                    ORDER BY COUNT(*) DESC
                    LIMIT 10
                )
                SELECT * FROM cobidders
            """
            cobid_rows = await conn.fetch(cobid_query, company_name)
            result['frequent_cobidders'] = [dict(r) for r in cobid_rows]

            return result
        return {}

    async def _get_company_product_categories(
        self,
        conn: asyncpg.Connection,
        company_name: str
    ) -> List[Dict[str, Any]]:
        """Get product categories the company supplies"""
        query = """
            SELECT
                COALESCE(t.cpv_code, 'Unknown') as cpv_code,
                t.category,
                COUNT(*) as tender_count,
                COUNT(*) FILTER (WHERE tb.is_winner = true) as wins,
                SUM(CASE WHEN tb.is_winner THEN t.awarded_value_mkd ELSE 0 END) as total_value_mkd
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE LOWER(tb.company_name) = LOWER($1)
            GROUP BY t.cpv_code, t.category
            ORDER BY tender_count DESC
            LIMIT 20
        """

        rows = await conn.fetch(query, company_name)
        return [dict(row) for row in rows]

    async def _get_company_corruption_flags(
        self,
        conn: asyncpg.Connection,
        company_name: str
    ) -> List[Dict[str, Any]]:
        """Get corruption flags involving this company"""
        query = """
            SELECT DISTINCT
                cf.flag_id,
                cf.tender_id,
                cf.flag_type,
                cf.severity,
                cf.score,
                cf.description,
                cf.detected_at,
                cf.evidence
            FROM corruption_flags cf
            WHERE cf.evidence::text ILIKE '%' || $1 || '%'
               OR cf.tender_id IN (
                   SELECT tender_id FROM tender_bidders
                   WHERE LOWER(company_name) = LOWER($1)
               )
            ORDER BY cf.score DESC, cf.detected_at DESC
            LIMIT 50
        """

        rows = await conn.fetch(query, company_name)
        return [dict(row) for row in rows]

    async def _get_company_price_competitiveness(
        self,
        conn: asyncpg.Connection,
        company_name: str
    ) -> Dict[str, Any]:
        """Analyze how competitive the company's prices are"""
        query = """
            WITH company_bids AS (
                SELECT
                    tb.tender_id,
                    tb.bid_amount_mkd as company_bid,
                    tb.is_winner,
                    tb.rank
                FROM tender_bidders tb
                WHERE LOWER(tb.company_name) = LOWER($1)
                  AND tb.bid_amount_mkd > 0
            ),
            all_bids AS (
                SELECT
                    cb.tender_id,
                    cb.company_bid,
                    cb.is_winner,
                    cb.rank,
                    AVG(tb2.bid_amount_mkd) as avg_bid,
                    MIN(tb2.bid_amount_mkd) as min_bid,
                    MAX(tb2.bid_amount_mkd) as max_bid,
                    COUNT(tb2.*) as num_bidders
                FROM company_bids cb
                JOIN tender_bidders tb2 ON cb.tender_id = tb2.tender_id
                WHERE tb2.bid_amount_mkd > 0
                GROUP BY cb.tender_id, cb.company_bid, cb.is_winner, cb.rank
            )
            SELECT
                COUNT(*) as tenders_analyzed,
                AVG((company_bid - avg_bid) / NULLIF(avg_bid, 0) * 100) as avg_deviation_from_mean_pct,
                AVG((company_bid - min_bid) / NULLIF(min_bid, 0) * 100) as avg_deviation_from_lowest_pct,
                COUNT(*) FILTER (WHERE company_bid = min_bid) as times_lowest_bidder,
                COUNT(*) FILTER (WHERE company_bid = max_bid) as times_highest_bidder,
                AVG(rank) FILTER (WHERE rank IS NOT NULL) as avg_rank
            FROM all_bids
        """

        row = await conn.fetchrow(query, company_name)
        if row:
            return dict(row)
        return {}

    # =========================================================================
    # INSTITUTION RESEARCH
    # =========================================================================

    async def research_institution(self, institution_name: str) -> InstitutionResearch:
        """
        Gather ALL database information about an institution.

        Args:
            institution_name: The institution name to research

        Returns:
            InstitutionResearch object with all findings
        """
        logger.info(f"Researching institution: {institution_name}")

        async with self._get_connection() as conn:
            results = await asyncio.gather(
                self._get_institution_basic_info(conn, institution_name),
                self._get_institution_tender_history(conn, institution_name),
                self._get_institution_winner_distribution(conn, institution_name),
                self._get_institution_bidder_statistics(conn, institution_name),
                self._get_institution_value_patterns(conn, institution_name),
                self._get_institution_deadline_patterns(conn, institution_name),
                self._get_institution_corruption_flags(conn, institution_name),
                self._get_institution_category_breakdown(conn, institution_name),
                self._get_institution_suspicious_patterns(conn, institution_name),
                return_exceptions=True
            )

            return InstitutionResearch(
                institution_name=institution_name,
                basic_info=results[0] if not isinstance(results[0], Exception) else {},
                tender_history=results[1] if not isinstance(results[1], Exception) else [],
                winner_distribution=results[2] if not isinstance(results[2], Exception) else [],
                bidder_statistics=results[3] if not isinstance(results[3], Exception) else {},
                value_patterns=results[4] if not isinstance(results[4], Exception) else {},
                deadline_patterns=results[5] if not isinstance(results[5], Exception) else {},
                corruption_flags=results[6] if not isinstance(results[6], Exception) else [],
                category_breakdown=results[7] if not isinstance(results[7], Exception) else [],
                suspicious_patterns=results[8] if not isinstance(results[8], Exception) else {}
            )

    async def _get_institution_basic_info(
        self,
        conn: asyncpg.Connection,
        institution_name: str
    ) -> Dict[str, Any]:
        """Get basic institution information"""
        query = """
            SELECT
                pe.entity_id,
                pe.entity_name,
                pe.entity_type,
                pe.category,
                pe.tax_id,
                pe.address,
                pe.city,
                pe.contact_person,
                pe.contact_email,
                pe.contact_phone,
                pe.website,
                pe.total_tenders,
                pe.total_value_mkd,
                pe.created_at,
                pe.updated_at
            FROM procuring_entities pe
            WHERE LOWER(pe.entity_name) = LOWER($1)
               OR pe.entity_name ILIKE $1
        """

        row = await conn.fetchrow(query, institution_name)
        if row:
            return dict(row)

        # Fall back to aggregating from tenders
        fallback_query = """
            SELECT
                $1 as entity_name,
                COUNT(*) as total_tenders,
                SUM(estimated_value_mkd) as total_estimated_value_mkd,
                SUM(awarded_value_mkd) as total_awarded_value_mkd,
                MIN(publication_date) as first_tender_date,
                MAX(publication_date) as last_tender_date
            FROM tenders
            WHERE LOWER(procuring_entity) = LOWER($1)
               OR procuring_entity ILIKE $1
        """

        row = await conn.fetchrow(fallback_query, institution_name)
        if row:
            return dict(row)
        return {}

    async def _get_institution_history_summary(
        self,
        conn: asyncpg.Connection,
        institution_name: str
    ) -> Dict[str, Any]:
        """Get a summary of institution's tender history"""
        if not institution_name:
            return {}

        query = """
            SELECT
                COUNT(*) as total_tenders,
                COUNT(*) FILTER (WHERE status = 'awarded') as awarded_tenders,
                COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled_tenders,
                SUM(estimated_value_mkd) as total_estimated_value,
                SUM(awarded_value_mkd) as total_awarded_value,
                AVG(num_bidders) as avg_bidders,
                COUNT(DISTINCT winner) as unique_winners,
                MIN(publication_date) as first_tender_date,
                MAX(publication_date) as last_tender_date
            FROM tenders
            WHERE LOWER(procuring_entity) = LOWER($1)
               OR procuring_entity ILIKE $1
        """

        row = await conn.fetchrow(query, institution_name)
        if row:
            return dict(row)
        return {}

    async def _get_institution_tender_history(
        self,
        conn: asyncpg.Connection,
        institution_name: str
    ) -> List[Dict[str, Any]]:
        """Get all tenders from an institution"""
        query = """
            SELECT
                t.tender_id,
                t.title,
                t.status,
                t.cpv_code,
                t.category,
                t.estimated_value_mkd,
                t.awarded_value_mkd,
                t.winner,
                t.num_bidders,
                t.publication_date,
                t.closing_date,
                t.procedure_type
            FROM tenders t
            WHERE LOWER(t.procuring_entity) = LOWER($1)
               OR t.procuring_entity ILIKE $1
            ORDER BY t.publication_date DESC
            LIMIT 200
        """

        rows = await conn.fetch(query, institution_name)
        return [dict(row) for row in rows]

    async def _get_institution_winner_distribution(
        self,
        conn: asyncpg.Connection,
        institution_name: str
    ) -> List[Dict[str, Any]]:
        """Analyze winner distribution - do same companies keep winning?"""
        query = """
            SELECT
                t.winner,
                COUNT(*) as wins,
                SUM(t.awarded_value_mkd) as total_value_mkd,
                ROUND(COUNT(*) * 100.0 / (
                    SELECT COUNT(*) FROM tenders
                    WHERE (LOWER(procuring_entity) = LOWER($1) OR procuring_entity ILIKE $1)
                      AND winner IS NOT NULL AND winner != ''
                ), 2) as win_percentage,
                MIN(t.publication_date) as first_win,
                MAX(t.publication_date) as last_win,
                COUNT(*) FILTER (WHERE t.num_bidders = 1) as single_bidder_wins
            FROM tenders t
            WHERE (LOWER(t.procuring_entity) = LOWER($1) OR t.procuring_entity ILIKE $1)
              AND t.winner IS NOT NULL AND t.winner != ''
            GROUP BY t.winner
            ORDER BY wins DESC
            LIMIT 30
        """

        rows = await conn.fetch(query, institution_name)
        return [dict(row) for row in rows]

    async def _get_institution_bidder_statistics(
        self,
        conn: asyncpg.Connection,
        institution_name: str
    ) -> Dict[str, Any]:
        """Get statistics about bidding patterns"""
        query = """
            SELECT
                AVG(num_bidders) as avg_bidders,
                MIN(num_bidders) as min_bidders,
                MAX(num_bidders) as max_bidders,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY num_bidders) as median_bidders,
                COUNT(*) FILTER (WHERE num_bidders = 1) as single_bidder_tenders,
                COUNT(*) FILTER (WHERE num_bidders = 2) as two_bidder_tenders,
                COUNT(*) FILTER (WHERE num_bidders >= 3) as three_plus_bidder_tenders,
                COUNT(*) as total_tenders,
                ROUND(COUNT(*) FILTER (WHERE num_bidders = 1) * 100.0 / NULLIF(COUNT(*), 0), 2) as single_bidder_percentage
            FROM tenders
            WHERE (LOWER(procuring_entity) = LOWER($1) OR procuring_entity ILIKE $1)
              AND status = 'awarded'
        """

        row = await conn.fetchrow(query, institution_name)
        if row:
            return dict(row)
        return {}

    async def _get_institution_value_patterns(
        self,
        conn: asyncpg.Connection,
        institution_name: str
    ) -> Dict[str, Any]:
        """Analyze value patterns for the institution"""
        query = """
            SELECT
                AVG(estimated_value_mkd) as avg_estimated_value,
                AVG(awarded_value_mkd) as avg_awarded_value,
                AVG(CASE WHEN estimated_value_mkd > 0
                    THEN (awarded_value_mkd - estimated_value_mkd) / estimated_value_mkd * 100
                    END) as avg_award_vs_estimate_pct,
                MIN(awarded_value_mkd) FILTER (WHERE awarded_value_mkd > 0) as min_awarded_value,
                MAX(awarded_value_mkd) as max_awarded_value,
                STDDEV(awarded_value_mkd) as stddev_awarded_value,
                SUM(awarded_value_mkd) as total_awarded_value
            FROM tenders
            WHERE (LOWER(procuring_entity) = LOWER($1) OR procuring_entity ILIKE $1)
              AND status = 'awarded'
        """

        row = await conn.fetchrow(query, institution_name)
        if row:
            result = dict(row)

            # Get yearly breakdown
            yearly_query = """
                SELECT
                    EXTRACT(YEAR FROM publication_date)::int as year,
                    COUNT(*) as tender_count,
                    SUM(awarded_value_mkd) as total_value_mkd,
                    AVG(num_bidders) as avg_bidders
                FROM tenders
                WHERE (LOWER(procuring_entity) = LOWER($1) OR procuring_entity ILIKE $1)
                  AND publication_date IS NOT NULL
                GROUP BY EXTRACT(YEAR FROM publication_date)
                ORDER BY year DESC
            """
            yearly_rows = await conn.fetch(yearly_query, institution_name)
            result['yearly_breakdown'] = [dict(r) for r in yearly_rows]

            return result
        return {}

    async def _get_institution_deadline_patterns(
        self,
        conn: asyncpg.Connection,
        institution_name: str
    ) -> Dict[str, Any]:
        """Analyze deadline patterns"""
        query = """
            SELECT
                AVG(closing_date - publication_date) as avg_days_open,
                MIN(closing_date - publication_date) as min_days_open,
                MAX(closing_date - publication_date) as max_days_open,
                COUNT(*) FILTER (WHERE closing_date - publication_date < 7) as short_deadline_count,
                COUNT(*) FILTER (WHERE closing_date - publication_date < 7 AND num_bidders = 1) as short_deadline_single_bidder,
                ROUND(COUNT(*) FILTER (WHERE closing_date - publication_date < 7) * 100.0 /
                    NULLIF(COUNT(*), 0), 2) as short_deadline_percentage
            FROM tenders
            WHERE (LOWER(procuring_entity) = LOWER($1) OR procuring_entity ILIKE $1)
              AND closing_date IS NOT NULL
              AND publication_date IS NOT NULL
        """

        row = await conn.fetchrow(query, institution_name)
        if row:
            return dict(row)
        return {}

    async def _get_institution_corruption_flags(
        self,
        conn: asyncpg.Connection,
        institution_name: str
    ) -> List[Dict[str, Any]]:
        """Get corruption flags for tenders from this institution"""
        query = """
            SELECT
                cf.flag_id,
                cf.tender_id,
                cf.flag_type,
                cf.severity,
                cf.score,
                cf.description,
                cf.detected_at,
                t.title as tender_title,
                t.winner,
                t.awarded_value_mkd
            FROM corruption_flags cf
            JOIN tenders t ON cf.tender_id = t.tender_id
            WHERE (LOWER(t.procuring_entity) = LOWER($1) OR t.procuring_entity ILIKE $1)
            ORDER BY cf.score DESC, cf.detected_at DESC
            LIMIT 50
        """

        rows = await conn.fetch(query, institution_name)
        return [dict(row) for row in rows]

    async def _get_institution_category_breakdown(
        self,
        conn: asyncpg.Connection,
        institution_name: str
    ) -> List[Dict[str, Any]]:
        """Get breakdown by tender categories/CPV codes"""
        query = """
            SELECT
                COALESCE(cpv_code, 'Unknown') as cpv_code,
                category,
                COUNT(*) as tender_count,
                SUM(awarded_value_mkd) as total_value_mkd,
                AVG(num_bidders) as avg_bidders,
                COUNT(DISTINCT winner) as unique_winners
            FROM tenders
            WHERE (LOWER(procuring_entity) = LOWER($1) OR procuring_entity ILIKE $1)
            GROUP BY cpv_code, category
            ORDER BY tender_count DESC
            LIMIT 20
        """

        rows = await conn.fetch(query, institution_name)
        return [dict(row) for row in rows]

    async def _get_institution_suspicious_patterns(
        self,
        conn: asyncpg.Connection,
        institution_name: str
    ) -> Dict[str, Any]:
        """Identify suspicious patterns at the institution"""
        # Check for repeat winners with >50% win rate
        repeat_winner_query = """
            SELECT
                winner,
                COUNT(*) as wins,
                ROUND(COUNT(*) * 100.0 / (
                    SELECT COUNT(*) FROM tenders
                    WHERE (LOWER(procuring_entity) = LOWER($1) OR procuring_entity ILIKE $1)
                      AND winner IS NOT NULL
                ), 2) as win_rate
            FROM tenders
            WHERE (LOWER(procuring_entity) = LOWER($1) OR procuring_entity ILIKE $1)
              AND winner IS NOT NULL
            GROUP BY winner
            HAVING COUNT(*) >= 3
               AND COUNT(*) * 100.0 / (
                   SELECT COUNT(*) FROM tenders
                   WHERE (LOWER(procuring_entity) = LOWER($1) OR procuring_entity ILIKE $1)
                     AND winner IS NOT NULL
               ) > 50
        """

        # Check for high single-bidder rate
        single_bidder_query = """
            SELECT
                COUNT(*) FILTER (WHERE num_bidders = 1) as single_bidder_count,
                COUNT(*) as total_count,
                ROUND(COUNT(*) FILTER (WHERE num_bidders = 1) * 100.0 / NULLIF(COUNT(*), 0), 2) as single_bidder_rate
            FROM tenders
            WHERE (LOWER(procuring_entity) = LOWER($1) OR procuring_entity ILIKE $1)
              AND status = 'awarded'
        """

        # Check for short deadlines
        deadline_query = """
            SELECT
                COUNT(*) FILTER (WHERE closing_date - publication_date < 7) as short_deadline_count,
                COUNT(*) as total_count,
                ROUND(COUNT(*) FILTER (WHERE closing_date - publication_date < 7) * 100.0 /
                    NULLIF(COUNT(*), 0), 2) as short_deadline_rate
            FROM tenders
            WHERE (LOWER(procuring_entity) = LOWER($1) OR procuring_entity ILIKE $1)
              AND closing_date IS NOT NULL
              AND publication_date IS NOT NULL
        """

        repeat_winners = await conn.fetch(repeat_winner_query, institution_name)
        single_bidder = await conn.fetchrow(single_bidder_query, institution_name)
        deadline = await conn.fetchrow(deadline_query, institution_name)

        return {
            'dominant_winners': [dict(r) for r in repeat_winners],
            'single_bidder_stats': dict(single_bidder) if single_bidder else {},
            'deadline_stats': dict(deadline) if deadline else {},
            'risk_indicators': {
                'has_dominant_winner': len(repeat_winners) > 0,
                'high_single_bidder_rate': (single_bidder and single_bidder['single_bidder_rate']
                                            and single_bidder['single_bidder_rate'] > 30),
                'high_short_deadline_rate': (deadline and deadline['short_deadline_rate']
                                             and deadline['short_deadline_rate'] > 20)
            }
        }

    # =========================================================================
    # RELATED ENTITIES
    # =========================================================================

    async def find_related_entities(self, entity_name: str) -> Dict[str, Any]:
        """
        Find potentially related companies/entities.

        Args:
            entity_name: The company or entity name to find relations for

        Returns:
            Dictionary with related entities and relationship details
        """
        logger.info(f"Finding related entities for: {entity_name}")

        async with self._get_connection() as conn:
            results = await asyncio.gather(
                self._find_related_companies(conn, entity_name),
                self._find_similar_names(conn, entity_name),
                self._find_cobidders(conn, entity_name),
                self._find_address_matches(conn, entity_name),
                return_exceptions=True
            )

            return {
                'entity_name': entity_name,
                'known_relationships': results[0] if not isinstance(results[0], Exception) else [],
                'similar_names': results[1] if not isinstance(results[1], Exception) else [],
                'frequent_cobidders': results[2] if not isinstance(results[2], Exception) else [],
                'address_matches': results[3] if not isinstance(results[3], Exception) else []
            }

    async def _find_related_companies(
        self,
        conn: asyncpg.Connection,
        company_name: str
    ) -> List[Dict[str, Any]]:
        """Find known company relationships"""
        query = """
            SELECT
                cr.relationship_id,
                cr.company_a,
                cr.company_b,
                cr.relationship_type,
                cr.confidence,
                cr.evidence,
                cr.verified,
                cr.discovered_at
            FROM company_relationships cr
            WHERE LOWER(cr.company_a) = LOWER($1)
               OR LOWER(cr.company_b) = LOWER($1)
               OR cr.company_a ILIKE $1
               OR cr.company_b ILIKE $1
            ORDER BY cr.confidence DESC
        """

        rows = await conn.fetch(query, company_name)
        return [dict(row) for row in rows]

    async def _find_similar_names(
        self,
        conn: asyncpg.Connection,
        company_name: str
    ) -> List[Dict[str, Any]]:
        """Find companies with similar names (possible same owner)"""
        # Use trigram similarity for fuzzy matching
        query = """
            SELECT DISTINCT
                tb.company_name,
                similarity(LOWER(tb.company_name), LOWER($1)) as name_similarity,
                COUNT(DISTINCT tb.tender_id) as tender_count
            FROM tender_bidders tb
            WHERE tb.company_name != $1
              AND similarity(LOWER(tb.company_name), LOWER($1)) > 0.3
            GROUP BY tb.company_name
            ORDER BY name_similarity DESC
            LIMIT 20
        """

        try:
            rows = await conn.fetch(query, company_name)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.warning(f"Trigram similarity search failed: {e}")
            # Fall back to ILIKE pattern matching
            fallback_query = """
                SELECT DISTINCT
                    tb.company_name,
                    COUNT(DISTINCT tb.tender_id) as tender_count
                FROM tender_bidders tb
                WHERE tb.company_name != $1
                  AND (
                      tb.company_name ILIKE '%' || $1 || '%'
                      OR $1 ILIKE '%' || tb.company_name || '%'
                  )
                GROUP BY tb.company_name
                LIMIT 20
            """
            rows = await conn.fetch(fallback_query, company_name)
            return [dict(row) for row in rows]

    async def _find_cobidders(
        self,
        conn: asyncpg.Connection,
        company_name: str
    ) -> List[Dict[str, Any]]:
        """Find companies that frequently bid together"""
        query = """
            WITH company_tenders AS (
                SELECT tender_id
                FROM tender_bidders
                WHERE LOWER(company_name) = LOWER($1)
            ),
            cobidder_stats AS (
                SELECT
                    tb.company_name as cobidder,
                    COUNT(*) as times_together,
                    COUNT(*) FILTER (WHERE tb.is_winner) as cobidder_wins,
                    (SELECT COUNT(*) FROM company_tenders) as company_tender_count,
                    (SELECT COUNT(DISTINCT tender_id) FROM tender_bidders
                     WHERE LOWER(company_name) = LOWER(tb.company_name)) as cobidder_tender_count
                FROM tender_bidders tb
                JOIN company_tenders ct ON tb.tender_id = ct.tender_id
                WHERE LOWER(tb.company_name) != LOWER($1)
                GROUP BY tb.company_name
            )
            SELECT
                cobidder,
                times_together,
                cobidder_wins,
                ROUND(times_together * 100.0 / LEAST(company_tender_count, cobidder_tender_count), 2) as overlap_percentage
            FROM cobidder_stats
            WHERE times_together >= 2
            ORDER BY times_together DESC
            LIMIT 20
        """

        rows = await conn.fetch(query, company_name)
        return [dict(row) for row in rows]

    async def _find_address_matches(
        self,
        conn: asyncpg.Connection,
        company_name: str
    ) -> List[Dict[str, Any]]:
        """Find companies at same address"""
        query = """
            WITH company_address AS (
                SELECT company_address
                FROM tender_bidders
                WHERE LOWER(company_name) = LOWER($1)
                  AND company_address IS NOT NULL
                  AND company_address != ''
                LIMIT 1
            )
            SELECT DISTINCT
                tb.company_name,
                tb.company_address,
                COUNT(DISTINCT tb.tender_id) as tender_count
            FROM tender_bidders tb, company_address ca
            WHERE LOWER(tb.company_name) != LOWER($1)
              AND LOWER(tb.company_address) = LOWER(ca.company_address)
            GROUP BY tb.company_name, tb.company_address
            ORDER BY tender_count DESC
            LIMIT 20
        """

        rows = await conn.fetch(query, company_name)
        return [dict(row) for row in rows]

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics about the connection pool"""
        if self._pool is None:
            return {"status": "not_initialized"}

        if self._pool._closed:
            return {"status": "closed"}

        return {
            "status": "active",
            "size": self._pool.get_size(),
            "free_size": self._pool.get_idle_size(),
            "used_size": self._pool.get_size() - self._pool.get_idle_size(),
            "min_size": self._pool.get_min_size(),
            "max_size": self._pool.get_max_size(),
        }


# CLI interface for testing
async def main():
    """Main entry point for testing the agent"""
    import sys

    agent = DBResearchAgent()

    try:
        if len(sys.argv) < 3:
            print("Usage:")
            print("  python db_research_agent.py tender <tender_id>")
            print("  python db_research_agent.py company <company_name>")
            print("  python db_research_agent.py institution <institution_name>")
            print("  python db_research_agent.py related <entity_name>")
            return

        command = sys.argv[1]
        target = ' '.join(sys.argv[2:])

        if command == 'tender':
            result = await agent.research_tender(target)
            print(result.to_json())

        elif command == 'company':
            result = await agent.research_company(target)
            print(result.to_json())

        elif command == 'institution':
            result = await agent.research_institution(target)
            print(result.to_json())

        elif command == 'related':
            result = await agent.find_related_entities(target)
            print(json.dumps(result, default=json_serializer, ensure_ascii=False, indent=2))

        else:
            print(f"Unknown command: {command}")

    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())

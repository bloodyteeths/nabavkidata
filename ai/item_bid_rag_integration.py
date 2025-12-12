"""
Item Bids RAG Integration

Integrates item-level bidding data into the RAG query system.
Enables answering questions like:
- "Who bid what price for surgical drapes?"
- "What did Company X offer for item Y?"
- "Which bidder had the lowest price per item?"

This module extends rag_query.py with item-level search capabilities.
"""

import re
import asyncpg
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ItemBidRAGSearcher:
    """RAG search interface for item bids"""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def search_item_bids(
        self,
        query: str,
        tender_id: Optional[str] = None,
        limit: int = 50
    ) -> Dict:
        """
        Search item bids using natural language query

        Args:
            query: Natural language query
            tender_id: Optional tender ID to filter by
            limit: Maximum results to return

        Returns:
            Dict with results and metadata
        """
        # Detect query intent
        intent = self._detect_intent(query)

        if intent == 'who_bid_for_item':
            return await self._search_by_item(query, tender_id, limit)
        elif intent == 'what_company_offered':
            return await self._search_by_company(query, tender_id, limit)
        elif intent == 'lowest_bidder':
            return await self._search_lowest_bidders(query, tender_id, limit)
        elif intent == 'bid_comparison':
            return await self._search_bid_comparison(query, tender_id, limit)
        else:
            # Generic search
            return await self._generic_search(query, tender_id, limit)

    def _detect_intent(self, query: str) -> str:
        """Detect user intent from query"""
        query_lower = query.lower()

        # Who bid for X?
        if any(phrase in query_lower for phrase in ['who bid', 'кој понуди', 'who offered']):
            return 'who_bid_for_item'

        # What did X offer?
        if any(phrase in query_lower for phrase in ['what did', 'што понуди', 'what offered']):
            return 'what_company_offered'

        # Lowest bidder
        if any(phrase in query_lower for phrase in ['lowest', 'најниск', 'cheapest', 'најевтин']):
            return 'lowest_bidder'

        # Comparison
        if any(phrase in query_lower for phrase in ['compare', 'comparison', 'споредба']):
            return 'bid_comparison'

        return 'generic'

    def _extract_keywords(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract item keywords and company keywords from query

        Returns: (item_keywords, company_keywords)
        """
        # Simple keyword extraction (can be improved with NER)
        query_lower = query.lower()

        # Extract quoted strings as exact matches
        quoted = re.findall(r'["\']([^"\']+)["\']', query)
        if quoted:
            # First quoted string could be item or company
            return (quoted[0], None)

        # Look for known item categories
        item_patterns = [
            r'(хируршк[иа].*)',
            r'(surgical.*)',
            r'(gaza.*)',
            r'(bandages.*)',
            r'(медицинск[иа].*)',
            r'(medical.*)',
        ]

        item_match = None
        for pattern in item_patterns:
            match = re.search(pattern, query_lower)
            if match:
                item_match = match.group(1)
                break

        # Look for company names (capitalized words)
        company_patterns = [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',  # Capitalized words
        ]

        company_match = None
        for pattern in company_patterns:
            match = re.search(pattern, query)
            if match:
                company_match = match.group(1)
                break

        return (item_match, company_match)

    async def _search_by_item(
        self,
        query: str,
        tender_id: Optional[str],
        limit: int
    ) -> Dict:
        """Search: Who bid for item X?"""
        item_keywords, _ = self._extract_keywords(query)

        if not item_keywords:
            # Try to extract from the entire query
            item_keywords = query.replace('who bid for', '').replace('кој понуди за', '').strip()

        sql = """
            SELECT
                item_name,
                company_name,
                unit_price_mkd,
                quantity_offered,
                total_price_mkd,
                is_winner,
                rank,
                tender_id,
                tender_title,
                brand_model
            FROM v_item_bids_full
            WHERE (item_name ILIKE $1 OR item_name_mk ILIKE $1)
        """

        params = [f'%{item_keywords}%']

        if tender_id:
            sql += " AND tender_id = $2"
            params.append(tender_id)

        sql += " ORDER BY item_name, unit_price_mkd ASC LIMIT $" + str(len(params) + 1)
        params.append(limit)

        async with self.db_pool.acquire() as conn:
            results = await conn.fetch(sql, *params)

        return self._format_item_search_results(results, item_keywords)

    async def _search_by_company(
        self,
        query: str,
        tender_id: Optional[str],
        limit: int
    ) -> Dict:
        """Search: What did Company X offer?"""
        _, company_keywords = self._extract_keywords(query)

        if not company_keywords:
            # Try to extract from query
            company_keywords = query.replace('what did', '').replace('offer', '').replace('што понуди', '').strip()

        sql = """
            SELECT
                tender_id,
                tender_title,
                item_name,
                quantity_offered,
                unit_price_mkd,
                total_price_mkd,
                brand_model,
                is_winner,
                rank
            FROM v_item_bids_full
            WHERE company_name ILIKE $1
        """

        params = [f'%{company_keywords}%']

        if tender_id:
            sql += " AND tender_id = $2"
            params.append(tender_id)

        sql += " ORDER BY tender_id, unit_price_mkd DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)

        async with self.db_pool.acquire() as conn:
            results = await conn.fetch(sql, *params)

        return self._format_company_search_results(results, company_keywords)

    async def _search_lowest_bidders(
        self,
        query: str,
        tender_id: Optional[str],
        limit: int
    ) -> Dict:
        """Search: Who had the lowest price?"""
        sql = """
            SELECT
                item_name,
                total_bids,
                lowest_bidder,
                min_price,
                winner_name,
                winner_price,
                CASE
                    WHEN winner_price IS NOT NULL AND min_price IS NOT NULL
                    THEN ROUND(((winner_price - min_price) / min_price * 100)::numeric, 2)
                    ELSE NULL
                END as price_difference_percent
            FROM v_item_bid_comparison
            WHERE total_bids > 0
        """

        params = []

        if tender_id:
            sql += " AND tender_id = $1"
            params.append(tender_id)

        sql += " ORDER BY min_price DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)

        async with self.db_pool.acquire() as conn:
            results = await conn.fetch(sql, *params)

        return self._format_lowest_bidder_results(results)

    async def _search_bid_comparison(
        self,
        query: str,
        tender_id: Optional[str],
        limit: int
    ) -> Dict:
        """Search: Compare bids for tender/item"""
        item_keywords, _ = self._extract_keywords(query)

        sql = """
            SELECT
                item_name,
                total_bids,
                min_price,
                max_price,
                avg_price,
                price_stddev,
                winner_name,
                winner_price,
                lowest_bidder,
                all_bids
            FROM v_item_bid_comparison
            WHERE total_bids > 0
        """

        params = []

        if tender_id:
            sql += " AND tender_id = $1"
            params.append(tender_id)
            param_idx = 2
        else:
            param_idx = 1

        if item_keywords:
            sql += f" AND item_name ILIKE ${param_idx}"
            params.append(f'%{item_keywords}%')

        sql += " ORDER BY total_bids DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)

        async with self.db_pool.acquire() as conn:
            results = await conn.fetch(sql, *params)

        return self._format_comparison_results(results)

    async def _generic_search(
        self,
        query: str,
        tender_id: Optional[str],
        limit: int
    ) -> Dict:
        """Generic search across all item bids"""
        item_keywords, company_keywords = self._extract_keywords(query)

        sql = """
            SELECT
                tender_id,
                tender_title,
                item_name,
                company_name,
                unit_price_mkd,
                total_price_mkd,
                is_winner,
                rank
            FROM v_item_bids_full
            WHERE 1=1
        """

        params = []
        param_idx = 1

        if item_keywords:
            sql += f" AND (item_name ILIKE ${param_idx} OR item_name_mk ILIKE ${param_idx})"
            params.append(f'%{item_keywords}%')
            param_idx += 1

        if company_keywords:
            sql += f" AND company_name ILIKE ${param_idx}"
            params.append(f'%{company_keywords}%')
            param_idx += 1

        if tender_id:
            sql += f" AND tender_id = ${param_idx}"
            params.append(tender_id)
            param_idx += 1

        sql += f" ORDER BY unit_price_mkd ASC LIMIT ${param_idx}"
        params.append(limit)

        async with self.db_pool.acquire() as conn:
            results = await conn.fetch(sql, *params)

        return self._format_generic_results(results)

    # ========================================================================
    # Result Formatting
    # ========================================================================

    def _format_item_search_results(self, results: List, item_keywords: str) -> Dict:
        """Format results for 'who bid for item' query"""
        if not results:
            return {
                'answer': f"No bids found for items matching '{item_keywords}'.",
                'results': [],
                'count': 0
            }

        # Group by item
        items = {}
        for row in results:
            item = row['item_name']
            if item not in items:
                items[item] = []
            items[item].append(row)

        # Build answer
        answer_parts = [f"Found bids for {len(items)} item(s) matching '{item_keywords}':\n"]

        for item_name, bids in items.items():
            answer_parts.append(f"\n**{item_name}** ({len(bids)} bids):")

            for bid in bids[:5]:  # Show top 5 bids per item
                winner = " ✓ WINNER" if bid['is_winner'] else ""
                rank = f" (Rank {bid['rank']})" if bid['rank'] else ""
                brand = f" - {bid['brand_model']}" if bid['brand_model'] else ""

                answer_parts.append(
                    f"  • {bid['company_name']}: {bid['unit_price_mkd']:,.2f} MKD/unit"
                    f"{rank}{winner}{brand}"
                )

            if len(bids) > 5:
                answer_parts.append(f"  ... and {len(bids) - 5} more bids")

        return {
            'answer': '\n'.join(answer_parts),
            'results': [dict(r) for r in results],
            'count': len(results),
            'grouped_by': 'item'
        }

    def _format_company_search_results(self, results: List, company_keywords: str) -> Dict:
        """Format results for 'what did company offer' query"""
        if not results:
            return {
                'answer': f"No offers found from companies matching '{company_keywords}'.",
                'results': [],
                'count': 0
            }

        # Calculate totals
        total_value = sum(float(r['total_price_mkd'] or 0) for r in results)
        wins = sum(1 for r in results if r['is_winner'])

        # Group by tender
        tenders = {}
        for row in results:
            tender = row['tender_id']
            if tender not in tenders:
                tenders[tender] = []
            tenders[tender].append(row)

        # Build answer
        answer_parts = [
            f"Found {len(results)} offers from companies matching '{company_keywords}' "
            f"across {len(tenders)} tender(s):\n"
        ]

        for tender_id, items in list(tenders.items())[:3]:  # Show top 3 tenders
            tender_title = items[0]['tender_title']
            answer_parts.append(f"\n**{tender_title}** ({tender_id}):")

            for item in items[:5]:  # Show top 5 items per tender
                winner = " ✓" if item['is_winner'] else ""
                answer_parts.append(
                    f"  • {item['item_name'][:50]}: {item['unit_price_mkd']:,.2f} MKD/unit"
                    f" (Total: {item['total_price_mkd']:,.2f}){winner}"
                )

            if len(items) > 5:
                answer_parts.append(f"  ... and {len(items) - 5} more items")

        if len(tenders) > 3:
            answer_parts.append(f"\n... and {len(tenders) - 3} more tenders")

        answer_parts.append(f"\n**Summary:**")
        answer_parts.append(f"  • Total items bid on: {len(results)}")
        answer_parts.append(f"  • Items won: {wins}")
        answer_parts.append(f"  • Total bid value: {total_value:,.2f} MKD")

        return {
            'answer': '\n'.join(answer_parts),
            'results': [dict(r) for r in results],
            'count': len(results),
            'total_value': total_value,
            'wins': wins
        }

    def _format_lowest_bidder_results(self, results: List) -> Dict:
        """Format results for lowest bidder query"""
        if not results:
            return {
                'answer': "No bid data available.",
                'results': [],
                'count': 0
            }

        # Find items where winner != lowest bidder
        non_optimal = [r for r in results if r['winner_price'] and r['min_price']
                       and r['winner_price'] > r['min_price']]

        answer_parts = [f"Analyzed {len(results)} items:\n"]

        # Show items with price differences
        if non_optimal:
            answer_parts.append(f"\n**Non-optimal awards** ({len(non_optimal)} items):")
            for row in non_optimal[:5]:
                diff = row['price_difference_percent']
                answer_parts.append(
                    f"  • {row['item_name'][:50]}\n"
                    f"    Lowest: {row['lowest_bidder']} at {row['min_price']:,.2f} MKD\n"
                    f"    Winner: {row['winner_name']} at {row['winner_price']:,.2f} MKD "
                    f"(+{diff}%)"
                )

        # Show optimal awards
        optimal = len(results) - len(non_optimal)
        answer_parts.append(f"\n**Optimal awards:** {optimal} items (winner = lowest bidder)")

        return {
            'answer': '\n'.join(answer_parts),
            'results': [dict(r) for r in results],
            'count': len(results),
            'non_optimal_count': len(non_optimal)
        }

    def _format_comparison_results(self, results: List) -> Dict:
        """Format results for bid comparison query"""
        if not results:
            return {
                'answer': "No bid comparison data available.",
                'results': [],
                'count': 0
            }

        answer_parts = [f"Bid comparison for {len(results)} item(s):\n"]

        for row in results[:10]:  # Show top 10 items
            answer_parts.append(f"\n**{row['item_name']}**")
            answer_parts.append(f"  • Total bids: {row['total_bids']}")
            answer_parts.append(f"  • Price range: {row['min_price']:,.2f} - {row['max_price']:,.2f} MKD")
            answer_parts.append(f"  • Average: {row['avg_price']:,.2f} MKD")

            if row['lowest_bidder']:
                answer_parts.append(f"  • Lowest bidder: {row['lowest_bidder']} ({row['min_price']:,.2f})")

            if row['winner_name']:
                winner_diff = ""
                if row['winner_price'] and row['min_price'] and row['winner_price'] > row['min_price']:
                    pct = ((row['winner_price'] - row['min_price']) / row['min_price'] * 100)
                    winner_diff = f" (+{pct:.1f}% vs lowest)"

                answer_parts.append(f"  • Winner: {row['winner_name']} ({row['winner_price']:,.2f}){winner_diff}")

        if len(results) > 10:
            answer_parts.append(f"\n... and {len(results) - 10} more items")

        return {
            'answer': '\n'.join(answer_parts),
            'results': [dict(r) for r in results],
            'count': len(results)
        }

    def _format_generic_results(self, results: List) -> Dict:
        """Format results for generic search"""
        if not results:
            return {
                'answer': "No matching bids found.",
                'results': [],
                'count': 0
            }

        answer_parts = [f"Found {len(results)} matching bid(s):\n"]

        for idx, row in enumerate(results[:10], 1):
            winner = " ✓ WINNER" if row['is_winner'] else ""
            rank = f" (Rank {row['rank']})" if row['rank'] else ""

            answer_parts.append(
                f"{idx}. **{row['item_name'][:50]}**\n"
                f"   Company: {row['company_name']}\n"
                f"   Price: {row['unit_price_mkd']:,.2f} MKD/unit "
                f"(Total: {row['total_price_mkd']:,.2f}){rank}{winner}\n"
                f"   Tender: {row['tender_title'][:50]} ({row['tender_id']})"
            )

        if len(results) > 10:
            answer_parts.append(f"\n... and {len(results) - 10} more results")

        return {
            'answer': '\n'.join(answer_parts),
            'results': [dict(r) for r in results],
            'count': len(results)
        }


# ============================================================================
# Integration with existing rag_query.py
# ============================================================================

async def add_item_bid_search_to_rag(
    rag_searcher,  # Existing RAG searcher instance
    db_pool: asyncpg.Pool
):
    """
    Add item bid search capability to existing RAG system

    Usage:
        from rag_query import EnhancedRAGSearcher
        from item_bid_rag_integration import add_item_bid_search_to_rag

        rag = EnhancedRAGSearcher(...)
        await add_item_bid_search_to_rag(rag, db_pool)

        # Now can handle item bid queries
        result = await rag.search("Who bid for surgical drapes?")
    """
    item_searcher = ItemBidRAGSearcher(db_pool)

    # Store reference
    rag_searcher.item_bid_searcher = item_searcher

    # Optionally: Add to routing logic
    original_search = rag_searcher.search

    async def enhanced_search(query: str, **kwargs):
        # Detect if query is about item bids
        query_lower = query.lower()
        item_bid_triggers = [
            'who bid', 'кој понуди',
            'what did', 'што понуди',
            'price for', 'цена за',
            'offered for', 'понуди за',
            'lowest bid', 'најниска понуда',
        ]

        if any(trigger in query_lower for trigger in item_bid_triggers):
            logger.info(f"Routing query to item bid searcher: {query}")
            return await item_searcher.search_item_bids(query, **kwargs)
        else:
            return await original_search(query, **kwargs)

    rag_searcher.search = enhanced_search

    return rag_searcher

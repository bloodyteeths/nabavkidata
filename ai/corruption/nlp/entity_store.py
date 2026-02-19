"""
Entity Mention Storage and Querying

Stores extracted entities and their relationships in the entity_mentions table.
Supports conflict-of-interest detection by cross-referencing person mentions
across buyer and supplier documents.

Database operations use asyncpg via the shared connection pool.

Usage:
    from ai.corruption.nlp.entity_store import EntityStore
    from db_pool import get_asyncpg_pool

    store = EntityStore()
    pool = await get_asyncpg_pool()

    # Store entities
    await store.store_entities(pool, tender_id, doc_id, entities)

    # Find conflicts
    conflicts = await store.find_conflicts(pool)

    # Get entity network
    network = await store.get_entity_network(pool, "Име Презиме", "PERSON")

Author: nabavkidata.com
License: Proprietary
"""

import logging
import json
from typing import List, Dict, Optional, Any
from datetime import datetime

import asyncpg

from .ner_extractor import Entity

logger = logging.getLogger(__name__)


class EntityStore:
    """
    Entity mention storage, querying, and conflict detection.

    All methods accept an asyncpg pool and operate on the entity_mentions
    and ner_processing_log tables.
    """

    # ========================================================================
    # STORAGE
    # ========================================================================

    async def store_entities(
        self,
        pool: asyncpg.Pool,
        tender_id: str,
        doc_id: Optional[str],
        entities: List[Entity],
        processing_time_ms: Optional[int] = None,
    ) -> int:
        """
        Batch insert entities into entity_mentions table.

        Args:
            pool: asyncpg connection pool
            tender_id: Tender ID the entities belong to
            doc_id: Document ID (UUID) the entities were extracted from
            entities: List of Entity objects to store
            processing_time_ms: Optional processing time in milliseconds

        Returns:
            Number of entities stored
        """
        if not entities:
            return 0

        async with pool.acquire() as conn:
            # Use a transaction for atomicity
            async with conn.transaction():
                # Prepare batch insert
                records = []
                for entity in entities:
                    records.append((
                        tender_id,
                        doc_id,
                        entity.text,
                        entity.type,
                        entity.normalized or entity.text,
                        entity.start if entity.start >= 0 else None,
                        entity.end if entity.end > 0 else None,
                        entity.confidence,
                        entity.method,
                        entity.context,
                    ))

                # Batch insert using executemany for efficiency
                await conn.executemany("""
                    INSERT INTO entity_mentions (
                        tender_id, doc_id, entity_text, entity_type,
                        normalized_text, start_offset, end_offset,
                        confidence, extraction_method, context
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, records)

                # Log the processing
                extraction_method = 'both' if any(
                    e.method == 'llm' for e in entities
                ) else 'regex'

                try:
                    await conn.execute("""
                        INSERT INTO ner_processing_log (
                            doc_id, tender_id, extraction_method,
                            entity_count, processing_time_ms
                        ) VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (doc_id, extraction_method) DO UPDATE SET
                            entity_count = $4,
                            processing_time_ms = $5,
                            processed_at = NOW()
                    """, doc_id, tender_id, extraction_method,
                        len(entities), processing_time_ms)
                except Exception as e:
                    # Non-fatal: log and continue
                    logger.warning(f"Failed to log NER processing: {e}")

                logger.info(
                    f"Stored {len(entities)} entities for tender {tender_id} "
                    f"(doc_id={doc_id})"
                )

                return len(entities)

    async def is_processed(
        self,
        pool: asyncpg.Pool,
        doc_id: str,
        extraction_method: str = 'regex',
    ) -> bool:
        """
        Check if a document has already been processed by NER.

        Args:
            pool: asyncpg connection pool
            doc_id: Document UUID to check
            extraction_method: 'regex', 'llm', or 'both'

        Returns:
            True if already processed
        """
        async with pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM ner_processing_log
                    WHERE doc_id = $1 AND extraction_method = $2
                )
            """, doc_id, extraction_method)
            return result or False

    async def delete_entities_for_doc(
        self,
        pool: asyncpg.Pool,
        doc_id: str,
    ) -> int:
        """
        Delete all entities for a document (for reprocessing).

        Returns:
            Number of entities deleted
        """
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await conn.execute("""
                    DELETE FROM entity_mentions WHERE doc_id = $1
                """, doc_id)
                await conn.execute("""
                    DELETE FROM ner_processing_log WHERE doc_id = $1
                """, doc_id)

                count = int(result.split()[-1]) if result else 0
                logger.info(f"Deleted {count} entities for doc_id={doc_id}")
                return count

    # ========================================================================
    # CONFLICT OF INTEREST DETECTION
    # ========================================================================

    async def find_conflicts(
        self,
        pool: asyncpg.Pool,
        tender_id: Optional[str] = None,
        min_mentions: int = 2,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Find potential conflicts of interest from entity analysis.

        A conflict is identified when the same person name appears in
        documents from BOTH a buyer institution AND a winning company
        in different tenders.

        Args:
            pool: asyncpg connection pool
            tender_id: Optional - filter to conflicts involving this tender
            min_mentions: Minimum total mentions to be considered (default 2)
            limit: Maximum results to return

        Returns:
            List of dicts with conflict details:
            {person_name, institution, company, institution_tenders,
             company_tenders, mention_count, avg_confidence}
        """
        async with pool.acquire() as conn:
            base_query = """
                SELECT
                    person_name,
                    institution,
                    company,
                    institution_tenders,
                    company_tenders,
                    mention_count,
                    avg_confidence
                FROM v_potential_conflicts
                WHERE mention_count >= $1
            """
            params = [min_mentions]
            param_count = 1

            if tender_id:
                param_count += 1
                base_query += f"""
                    AND ($${param_count} = ANY(institution_tenders)
                         OR $${param_count} = ANY(company_tenders))
                """
                # Fix: use proper param syntax
                base_query = base_query.replace(f'$${param_count}', f'${param_count}')
                params.append(tender_id)

            base_query += f" LIMIT ${param_count + 1}"
            params.append(limit)

            try:
                rows = await conn.fetch(base_query, *params)
                return [dict(row) for row in rows]
            except Exception as e:
                logger.error(f"Error querying conflicts view: {e}")
                # Fallback: direct query if view doesn't exist
                return await self._find_conflicts_direct(conn, tender_id, min_mentions, limit)

    async def _find_conflicts_direct(
        self,
        conn: asyncpg.Connection,
        tender_id: Optional[str],
        min_mentions: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Direct conflict detection query (fallback if view not created yet).
        """
        query = """
            WITH person_in_tenders AS (
                SELECT
                    em.normalized_text AS person_name,
                    em.tender_id,
                    t.procuring_entity,
                    t.winner
                FROM entity_mentions em
                JOIN tenders t ON em.tender_id = t.tender_id
                WHERE em.entity_type = 'PERSON'
                  AND em.normalized_text IS NOT NULL
                  AND em.normalized_text != ''
            )
            SELECT
                p1.person_name,
                p1.procuring_entity AS institution,
                p2.winner AS company,
                ARRAY_AGG(DISTINCT p1.tender_id) AS institution_tenders,
                ARRAY_AGG(DISTINCT p2.tender_id) AS company_tenders,
                COUNT(DISTINCT p1.tender_id) + COUNT(DISTINCT p2.tender_id) AS mention_count
            FROM person_in_tenders p1
            JOIN person_in_tenders p2
                ON p1.person_name = p2.person_name
                AND p1.tender_id != p2.tender_id
            WHERE p1.procuring_entity IS NOT NULL
              AND p2.winner IS NOT NULL
              AND p1.procuring_entity != p2.winner
        """
        params = []
        param_count = 0

        if tender_id:
            param_count += 1
            query += f" AND (p1.tender_id = ${param_count} OR p2.tender_id = ${param_count})"
            params.append(tender_id)

        query += """
            GROUP BY p1.person_name, p1.procuring_entity, p2.winner
            HAVING COUNT(DISTINCT p1.tender_id) + COUNT(DISTINCT p2.tender_id) >= $%d
            ORDER BY mention_count DESC
            LIMIT $%d
        """ % (param_count + 1, param_count + 2)
        params.extend([min_mentions, limit])

        try:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Direct conflict query failed: {e}")
            return []

    # ========================================================================
    # ENTITY NETWORK
    # ========================================================================

    async def get_entity_network(
        self,
        pool: asyncpg.Pool,
        entity_name: str,
        entity_type: str = 'PERSON',
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get all tenders/documents where this entity appears,
        plus co-occurring entities for network visualization.

        Args:
            pool: asyncpg connection pool
            entity_name: Entity name to search for
            entity_type: Entity type filter (default 'PERSON')
            limit: Max co-occurring entities to return

        Returns:
            {
                entity: {name, type, total_mentions},
                tenders: [{tender_id, title, procuring_entity, winner}],
                co_entities: [{name, type, count, tenders_shared}],
            }
        """
        async with pool.acquire() as conn:
            # Find all mentions of this entity
            mentions = await conn.fetch("""
                SELECT
                    em.tender_id,
                    em.doc_id,
                    em.entity_text,
                    em.confidence,
                    em.extraction_method,
                    t.title,
                    t.procuring_entity,
                    t.winner,
                    t.status
                FROM entity_mentions em
                JOIN tenders t ON em.tender_id = t.tender_id
                WHERE em.normalized_text ILIKE $1
                  AND em.entity_type = $2
                ORDER BY em.extracted_at DESC
            """, entity_name, entity_type)

            if not mentions:
                # Try fuzzy match
                mentions = await conn.fetch("""
                    SELECT
                        em.tender_id,
                        em.doc_id,
                        em.entity_text,
                        em.confidence,
                        em.extraction_method,
                        t.title,
                        t.procuring_entity,
                        t.winner,
                        t.status
                    FROM entity_mentions em
                    JOIN tenders t ON em.tender_id = t.tender_id
                    WHERE em.normalized_text ILIKE '%' || $1 || '%'
                      AND em.entity_type = $2
                    ORDER BY em.extracted_at DESC
                    LIMIT 200
                """, entity_name, entity_type)

            tender_ids = list(set(row['tender_id'] for row in mentions))
            tenders_info = [
                {
                    'tender_id': row['tender_id'],
                    'title': row['title'],
                    'procuring_entity': row['procuring_entity'],
                    'winner': row['winner'],
                    'status': row['status'],
                }
                for row in mentions
            ]
            # Deduplicate tenders
            seen_tenders = set()
            unique_tenders = []
            for t in tenders_info:
                if t['tender_id'] not in seen_tenders:
                    seen_tenders.add(t['tender_id'])
                    unique_tenders.append(t)

            # Find co-occurring entities in the same tenders
            co_entities = []
            if tender_ids:
                co_rows = await conn.fetch("""
                    SELECT
                        normalized_text AS name,
                        entity_type AS type,
                        COUNT(*) AS count,
                        ARRAY_AGG(DISTINCT tender_id) AS tenders_shared
                    FROM entity_mentions
                    WHERE tender_id = ANY($1)
                      AND normalized_text != $2
                      AND normalized_text IS NOT NULL
                      AND normalized_text != ''
                    GROUP BY normalized_text, entity_type
                    ORDER BY count DESC
                    LIMIT $3
                """, tender_ids, entity_name, limit)

                co_entities = [
                    {
                        'name': row['name'],
                        'type': row['type'],
                        'count': row['count'],
                        'tenders_shared': row['tenders_shared'],
                    }
                    for row in co_rows
                ]

            return {
                'entity': {
                    'name': entity_name,
                    'type': entity_type,
                    'total_mentions': len(mentions),
                },
                'tenders': unique_tenders,
                'co_entities': co_entities,
            }

    # ========================================================================
    # STATISTICS
    # ========================================================================

    async def get_entity_stats(
        self,
        pool: asyncpg.Pool,
    ) -> Dict[str, Any]:
        """
        Get aggregate entity statistics.

        Returns:
            {
                total_entities: int,
                unique_entities: int,
                by_type: {PERSON: int, ORG: int, ...},
                by_method: {regex: int, llm: int},
                documents_processed: int,
                tenders_with_entities: int,
                top_persons: [{name, count}],
                top_orgs: [{name, count}],
                last_processed: datetime,
            }
        """
        async with pool.acquire() as conn:
            # Try the stats view first
            try:
                stats_rows = await conn.fetch("""
                    SELECT entity_type, total_mentions, unique_entities,
                           tenders_with_entities, documents_processed, avg_confidence
                    FROM v_entity_stats
                """)
            except Exception:
                # View doesn't exist yet, query directly
                stats_rows = await conn.fetch("""
                    SELECT
                        entity_type,
                        COUNT(*) AS total_mentions,
                        COUNT(DISTINCT normalized_text) AS unique_entities,
                        COUNT(DISTINCT tender_id) AS tenders_with_entities,
                        COUNT(DISTINCT doc_id) AS documents_processed,
                        ROUND(AVG(confidence)::numeric, 2) AS avg_confidence
                    FROM entity_mentions
                    GROUP BY entity_type
                    ORDER BY total_mentions DESC
                """)

            by_type = {}
            total_entities = 0
            unique_entities = 0
            docs_processed = 0
            tenders_count = 0

            for row in stats_rows:
                by_type[row['entity_type']] = row['total_mentions']
                total_entities += row['total_mentions']
                unique_entities += row['unique_entities']
                docs_processed = max(docs_processed, row['documents_processed'])
                tenders_count = max(tenders_count, row['tenders_with_entities'])

            # Method breakdown
            method_rows = await conn.fetch("""
                SELECT extraction_method, COUNT(*) AS count
                FROM entity_mentions
                GROUP BY extraction_method
            """)
            by_method = {row['extraction_method']: row['count'] for row in method_rows}

            # Top persons
            top_persons = await conn.fetch("""
                SELECT normalized_text AS name, COUNT(*) AS count
                FROM entity_mentions
                WHERE entity_type = 'PERSON'
                  AND normalized_text IS NOT NULL
                  AND normalized_text != ''
                GROUP BY normalized_text
                ORDER BY count DESC
                LIMIT 20
            """)

            # Top organizations
            top_orgs = await conn.fetch("""
                SELECT normalized_text AS name, COUNT(*) AS count
                FROM entity_mentions
                WHERE entity_type = 'ORG'
                  AND normalized_text IS NOT NULL
                  AND normalized_text != ''
                GROUP BY normalized_text
                ORDER BY count DESC
                LIMIT 20
            """)

            # Last processed
            last_processed = await conn.fetchval("""
                SELECT MAX(processed_at) FROM ner_processing_log
            """)

            return {
                'total_entities': total_entities,
                'unique_entities': unique_entities,
                'by_type': by_type,
                'by_method': by_method,
                'documents_processed': docs_processed,
                'tenders_with_entities': tenders_count,
                'top_persons': [dict(row) for row in top_persons],
                'top_orgs': [dict(row) for row in top_orgs],
                'last_processed': last_processed.isoformat() if last_processed else None,
            }

    # ========================================================================
    # ENTITY SEARCH
    # ========================================================================

    async def search_entities(
        self,
        pool: asyncpg.Pool,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search for entities by text (supports partial matching).

        Args:
            pool: asyncpg connection pool
            query: Search text
            entity_type: Optional filter by type
            limit: Max results

        Returns:
            List of matching entities with their tender context
        """
        async with pool.acquire() as conn:
            sql = """
                SELECT
                    em.entity_text,
                    em.entity_type,
                    em.normalized_text,
                    em.confidence,
                    em.extraction_method,
                    em.tender_id,
                    t.title AS tender_title,
                    t.procuring_entity,
                    t.winner
                FROM entity_mentions em
                JOIN tenders t ON em.tender_id = t.tender_id
                WHERE em.normalized_text ILIKE '%' || $1 || '%'
            """
            params = [query]
            param_count = 1

            if entity_type:
                param_count += 1
                sql += f" AND em.entity_type = ${param_count}"
                params.append(entity_type)

            sql += f" ORDER BY em.confidence DESC LIMIT ${param_count + 1}"
            params.append(limit)

            rows = await conn.fetch(sql, *params)
            return [dict(row) for row in rows]

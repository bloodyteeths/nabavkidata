"""
Table Storage Module - Database Integration for Extracted Tables

Stores extracted tables and items in PostgreSQL database.
Uses asyncpg for high-performance async operations.

Features:
- Batch insertion of tables and items
- Duplicate detection (same table/page/engine)
- Transaction support
- Full metadata preservation
- Query helpers for analytics
"""

import logging
import asyncio
import json
from typing import List, Dict, Optional, Any
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from table_extraction import ExtractedTable, TableType, extract_tables_from_pdf, extract_items_from_pdf

logger = logging.getLogger(__name__)


class TableStorage:
    """
    Storage manager for extracted tables and items
    """

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize storage manager

        Args:
            db_pool: asyncpg connection pool
        """
        self.pool = db_pool

    async def store_tables(
        self,
        tables: List[ExtractedTable],
        tender_id: Optional[str] = None,
        doc_id: Optional[str] = None
    ) -> List[UUID]:
        """
        Store extracted tables in database

        Args:
            tables: List of ExtractedTable objects
            tender_id: Optional tender ID reference
            doc_id: Optional document ID reference

        Returns:
            List of table_id UUIDs
        """
        if not tables:
            return []

        table_ids = []

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for table in tables:
                    # Convert DataFrame to JSONB-compatible format
                    raw_data = {
                        'columns': list(table.data.columns),
                        'data': table.data.to_dict(orient='records')
                    }

                    # Prepare normalized data (cleaned)
                    normalized_data = {
                        'columns': list(table.data.columns),
                        'data': table.data.fillna('').to_dict(orient='records')
                    }

                    # Insert table
                    table_id = await conn.fetchval("""
                        INSERT INTO extracted_tables (
                            doc_id,
                            tender_id,
                            page_number,
                            table_index,
                            extraction_engine,
                            table_type,
                            confidence_score,
                            row_count,
                            col_count,
                            raw_data,
                            normalized_data,
                            extraction_metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        RETURNING table_id
                    """,
                        UUID(doc_id) if doc_id and doc_id != '' else None,
                        tender_id,
                        table.page_number,
                        table.table_index,
                        table.engine_used,
                        table.table_type.value,
                        float(table.confidence),
                        len(table.data),
                        len(table.data.columns),
                        json.dumps(raw_data),
                        json.dumps(normalized_data),
                        json.dumps(table.metadata)
                    )

                    table_ids.append(table_id)
                    logger.info(f"Stored table {table_id} (page {table.page_number}, {len(table.data)} rows)")

        logger.info(f"Stored {len(table_ids)} tables in database")
        return table_ids

    async def store_items(
        self,
        items: List[Dict],
        table_ids_map: Dict[tuple, UUID],
        tender_id: Optional[str] = None
    ) -> List[UUID]:
        """
        Store extracted items in database

        Args:
            items: List of item dictionaries from ItemExtractor
            table_ids_map: Mapping of (page, index) -> table_id
            tender_id: Optional tender ID reference

        Returns:
            List of item_id UUIDs
        """
        if not items:
            return []

        item_ids = []

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for item in items:
                    # Get table_id from map
                    key = (item['source_table_page'], item['source_table_index'])
                    table_id = table_ids_map.get(key)

                    if not table_id:
                        logger.warning(f"No table_id found for item from page {key[0]}, table {key[1]}")
                        continue

                    # Insert item
                    item_id = await conn.fetchval("""
                        INSERT INTO extracted_items (
                            table_id,
                            tender_id,
                            item_number,
                            item_name,
                            quantity,
                            unit,
                            unit_price,
                            total_price,
                            cpv_code,
                            specifications,
                            notes,
                            source_row_index,
                            extraction_confidence,
                            raw_data
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        RETURNING item_id
                    """,
                        table_id,
                        tender_id,
                        item.get('item_number'),
                        item.get('item_name'),
                        float(item['quantity']) if item.get('quantity') else None,
                        item.get('unit'),
                        float(item['unit_price']) if item.get('unit_price') else None,
                        float(item['total_price']) if item.get('total_price') else None,
                        item.get('cpv_code'),
                        item.get('specifications'),
                        item.get('notes'),
                        item.get('source_row_index'),
                        float(item.get('extraction_confidence', 0.5)),
                        json.dumps(item.get('raw_data', {}))
                    )

                    item_ids.append(item_id)

        logger.info(f"Stored {len(item_ids)} items in database")
        return item_ids

    async def process_and_store_pdf(
        self,
        pdf_path: str,
        tender_id: Optional[str] = None,
        doc_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete pipeline: extract and store tables and items from PDF

        Args:
            pdf_path: Path to PDF file
            tender_id: Optional tender ID
            doc_id: Optional document ID

        Returns:
            Dictionary with extraction results
        """
        logger.info(f"Processing PDF: {pdf_path}")

        # Extract tables
        tables = extract_tables_from_pdf(pdf_path)

        if not tables:
            logger.warning("No tables found in PDF")
            return {
                'pdf_path': pdf_path,
                'tables_found': 0,
                'tables_stored': 0,
                'items_found': 0,
                'items_stored': 0
            }

        # Store tables
        table_ids = await self.store_tables(tables, tender_id=tender_id, doc_id=doc_id)

        # Create mapping of (page, index) -> table_id
        table_ids_map = {
            (table.page_number, table.table_index): table_id
            for table, table_id in zip(tables, table_ids)
        }

        # Extract items
        from table_extraction import ItemExtractor
        item_extractor = ItemExtractor()
        items = item_extractor.extract_items(tables)

        # Store items
        item_ids = await self.store_items(items, table_ids_map, tender_id=tender_id)

        result = {
            'pdf_path': pdf_path,
            'tables_found': len(tables),
            'tables_stored': len(table_ids),
            'items_found': len(items),
            'items_stored': len(item_ids),
            'table_ids': [str(tid) for tid in table_ids],
            'item_ids': [str(iid) for iid in item_ids]
        }

        logger.info(f"Processing complete: {result}")
        return result

    async def get_tables_by_tender(
        self,
        tender_id: str,
        table_type: Optional[TableType] = None
    ) -> List[Dict]:
        """
        Get all tables for a specific tender

        Args:
            tender_id: Tender ID
            table_type: Optional filter by table type

        Returns:
            List of table records
        """
        query = """
            SELECT
                table_id,
                doc_id,
                tender_id,
                page_number,
                table_index,
                extraction_engine,
                table_type,
                confidence_score,
                row_count,
                col_count,
                raw_data,
                normalized_data,
                extraction_metadata,
                created_at
            FROM extracted_tables
            WHERE tender_id = $1
        """

        params = [tender_id]

        if table_type:
            query += " AND table_type = $2"
            params.append(table_type.value)

        query += " ORDER BY page_number, table_index"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows]

    async def get_items_by_tender(
        self,
        tender_id: str,
        min_confidence: float = 0.0
    ) -> List[Dict]:
        """
        Get all extracted items for a specific tender

        Args:
            tender_id: Tender ID
            min_confidence: Minimum extraction confidence

        Returns:
            List of item records with table metadata
        """
        query = """
            SELECT
                item_id,
                tender_id,
                item_number,
                item_name,
                quantity,
                unit,
                unit_price,
                total_price,
                cpv_code,
                specifications,
                notes,
                extraction_confidence,
                page_number,
                table_type,
                extraction_engine
            FROM v_extracted_items_with_tables
            WHERE tender_id = $1
            AND extraction_confidence >= $2
            ORDER BY page_number, source_row_index
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, tender_id, min_confidence)

        return [dict(row) for row in rows]

    async def get_extraction_stats(self) -> Dict[str, Any]:
        """
        Get extraction statistics

        Returns:
            Dictionary with statistics
        """
        async with self.pool.acquire() as conn:
            # Total tables
            total_tables = await conn.fetchval("SELECT COUNT(*) FROM extracted_tables")

            # Total items
            total_items = await conn.fetchval("SELECT COUNT(*) FROM extracted_items")

            # Tables by engine
            engine_stats = await conn.fetch("""
                SELECT extraction_engine, COUNT(*) as count
                FROM extracted_tables
                GROUP BY extraction_engine
                ORDER BY count DESC
            """)

            # Tables by type
            type_stats = await conn.fetch("""
                SELECT table_type, COUNT(*) as count
                FROM extracted_tables
                GROUP BY table_type
                ORDER BY count DESC
            """)

            # Average confidence
            avg_confidence = await conn.fetchval("""
                SELECT AVG(confidence_score)
                FROM extracted_tables
            """)

        return {
            'total_tables': total_tables,
            'total_items': total_items,
            'tables_by_engine': {row['extraction_engine']: row['count'] for row in engine_stats},
            'tables_by_type': {row['table_type']: row['count'] for row in type_stats},
            'average_confidence': float(avg_confidence) if avg_confidence else 0.0
        }


# Convenience functions
async def store_pdf_tables(
    pdf_path: str,
    db_pool: asyncpg.Pool,
    tender_id: Optional[str] = None,
    doc_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract and store tables from PDF in one operation

    Args:
        pdf_path: Path to PDF file
        db_pool: Database connection pool
        tender_id: Optional tender ID
        doc_id: Optional document ID

    Returns:
        Extraction results dictionary
    """
    storage = TableStorage(db_pool)
    return await storage.process_and_store_pdf(pdf_path, tender_id=tender_id, doc_id=doc_id)


# Example usage and testing
async def main():
    """Example usage"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python table_storage.py <pdf_path> [tender_id]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    tender_id = sys.argv[2] if len(sys.argv) > 2 else None

    # Create database connection
    # NOTE: Update with your actual database credentials
    DATABASE_URL = "postgresql://localhost:5432/nabavkidata"

    print(f"\n{'='*60}")
    print(f"TABLE EXTRACTION AND STORAGE TEST")
    print(f"{'='*60}\n")
    print(f"PDF: {pdf_path}")
    print(f"Tender ID: {tender_id or 'None'}\n")

    pool = await asyncpg.create_pool(DATABASE_URL)

    try:
        storage = TableStorage(pool)

        # Process and store
        result = await storage.process_and_store_pdf(
            pdf_path,
            tender_id=tender_id
        )

        print(f"\n{'='*60}")
        print("EXTRACTION RESULTS")
        print(f"{'='*60}\n")

        for key, value in result.items():
            if key not in ['table_ids', 'item_ids']:
                print(f"{key}: {value}")

        # Get statistics
        stats = await storage.get_extraction_stats()

        print(f"\n{'='*60}")
        print("DATABASE STATISTICS")
        print(f"{'='*60}\n")

        for key, value in stats.items():
            print(f"{key}: {value}")

        print(f"\n{'='*60}\n")

    finally:
        await pool.close()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(main())

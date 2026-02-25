#!/usr/bin/env python3
"""
Comprehensive Embedding Generator for RAG System

Embeds multiple data sources:
1. Document content_text (highest priority - full tender specs)
2. Tender metadata (title, entity, CPV, estimated value)
3. Product items (names, quantities, specs)
4. Bidder information (company names, tax IDs, wins)

Target: 5,000+ embeddings for effective AI search
"""

import os
import sys
import json
import time
import logging
import argparse
from typing import List, Dict, Optional
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
import google.generativeai as genai

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'user': os.environ.get('DB_USER', 'nabavki_user'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'nabavkidata'),
}

# Configure Gemini
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Rate limiting
RATE_LIMIT_DELAY = 0.3  # seconds between API calls
BATCH_SIZE = 50  # embeddings per batch before commit


class EmbeddingGenerator:
    """Generate and store embeddings for various data sources"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.conn = None
        self.cur = None
        self.stats = {
            'documents': 0,
            'tenders': 0,
            'items': 0,
            'bidders': 0,
            'skipped': 0,
            'errors': 0,
        }

    def connect(self):
        """Connect to database"""
        self.conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            dbname=DB_CONFIG['database']
        )
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        logger.info("Connected to database")

    def close(self):
        """Close database connection"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using Gemini"""
        if not GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not set")
            return None

        try:
            result = genai.embed_content(
                model='models/text-embedding-004',
                content=text[:8000],  # Limit text length
                task_type='retrieval_document'
            )
            return result['embedding']
        except Exception as e:
            if 'rate' in str(e).lower() or '429' in str(e):
                logger.warning("Rate limited, waiting 60s...")
                time.sleep(60)
                return self.generate_embedding(text)
            logger.error(f"Embedding failed: {e}")
            return None

    def embedding_exists(self, source_type: str, source_id: str) -> bool:
        """Check if embedding already exists"""
        self.cur.execute("""
            SELECT 1 FROM embeddings
            WHERE metadata->>'source_type' = %s
              AND metadata->>'source_id' = %s
            LIMIT 1
        """, (source_type, source_id))
        return self.cur.fetchone() is not None

    def store_embedding(self, vector: List[float], text: str, tender_id: str,
                       metadata: Dict, doc_id = None):
        """Store embedding in database"""
        if self.dry_run:
            return

        # Convert doc_id to proper format if it's a UUID object
        doc_id_val = str(doc_id) if doc_id else None

        self.cur.execute("""
            INSERT INTO embeddings (tender_id, doc_id, chunk_text, chunk_index, metadata, vector)
            VALUES (%s, %s::uuid, %s, %s, %s, %s)
        """, (
            tender_id,
            doc_id_val,
            text[:10000],  # Limit stored text
            0,
            json.dumps(metadata),
            vector
        ))

    def embed_documents(self, limit: int = 500):
        """Embed document content_text - highest priority for RAG"""
        logger.info(f"=== Embedding Documents (limit={limit}) ===")

        # Get documents with content that aren't embedded yet
        self.cur.execute("""
            SELECT d.doc_id, d.tender_id, d.file_name, d.content_text,
                   d.specifications_json, t.title as tender_title, t.cpv_code
            FROM documents d
            LEFT JOIN tenders t ON d.tender_id = t.tender_id
            WHERE d.content_text IS NOT NULL
              AND LENGTH(d.content_text) > 500
              AND d.extraction_status = 'success'
              AND NOT EXISTS (
                  SELECT 1 FROM embeddings e
                  WHERE e.doc_id = d.doc_id
              )
            ORDER BY LENGTH(d.content_text) DESC
            LIMIT %s
        """, (limit,))

        docs = self.cur.fetchall()
        logger.info(f"Found {len(docs)} documents to embed")

        for i, doc in enumerate(docs):
            # Format document text
            text_parts = []
            if doc.get('tender_title'):
                text_parts.append(f"Tender: {doc['tender_title']}")
            if doc.get('cpv_code'):
                text_parts.append(f"CPV: {doc['cpv_code']}")
            if doc.get('file_name'):
                text_parts.append(f"Document: {doc['file_name']}")
            text_parts.append(f"\nContent:\n{doc['content_text']}")

            text = '\n'.join(text_parts)

            if self.dry_run:
                if i < 3:
                    logger.info(f"Would embed doc {doc['doc_id']}: {text[:200]}...")
                continue

            vector = self.generate_embedding(text)
            if not vector:
                self.stats['errors'] += 1
                continue

            metadata = {
                'source_type': 'document',
                'source_id': str(doc['doc_id']),
                'file_name': doc.get('file_name'),
                'tender_title': doc.get('tender_title'),
                'cpv_code': doc.get('cpv_code'),
            }

            self.store_embedding(
                vector=vector,
                text=text,
                tender_id=doc['tender_id'],
                metadata=metadata,
                doc_id=doc['doc_id']
            )

            self.stats['documents'] += 1

            if (i + 1) % 10 == 0:
                self.conn.commit()
                logger.info(f"Progress: {i+1}/{len(docs)} documents embedded")

            time.sleep(RATE_LIMIT_DELAY)

        self.conn.commit()
        logger.info(f"Embedded {self.stats['documents']} documents")

    def embed_tenders(self, limit: int = 500):
        """Embed tender metadata for search"""
        logger.info(f"=== Embedding Tenders (limit={limit}) ===")

        self.cur.execute("""
            SELECT t.tender_id, t.title, t.description, t.procuring_entity,
                   t.cpv_code, t.estimated_value_mkd,
                   t.status, t.procedure_type, t.publication_date,
                   t.raw_data_json
            FROM tenders t
            WHERE t.title IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM embeddings e
                  WHERE e.tender_id = t.tender_id
                    AND e.metadata->>'source_type' = 'tender'
              )
            ORDER BY t.estimated_value_mkd DESC NULLS LAST
            LIMIT %s
        """, (limit,))

        tenders = self.cur.fetchall()
        logger.info(f"Found {len(tenders)} tenders to embed")

        for i, tender in enumerate(tenders):
            # Format tender text
            text_parts = [f"Tender: {tender['title']}"]

            if tender.get('description'):
                text_parts.append(f"Description: {tender['description']}")
            if tender.get('procuring_entity'):
                text_parts.append(f"Procuring Entity: {tender['procuring_entity']}")
            if tender.get('cpv_code'):
                text_parts.append(f"CPV Code: {tender['cpv_code']}")
            if tender.get('estimated_value_mkd'):
                text_parts.append(f"Estimated Value: {tender['estimated_value_mkd']:,.0f} MKD")
            if tender.get('status'):
                text_parts.append(f"Status: {tender['status']}")
            if tender.get('procedure_type'):
                text_parts.append(f"Procedure Type: {tender['procedure_type']}")

            # Parse raw_data_json for additional info
            if tender.get('raw_data_json'):
                try:
                    raw = tender['raw_data_json'] if isinstance(tender['raw_data_json'], dict) else json.loads(tender['raw_data_json'])

                    # Add category
                    if raw.get('category'):
                        text_parts.append(f"Category: {raw['category']}")

                    # Add actual value if different from estimated
                    if raw.get('actual_value_mkd'):
                        text_parts.append(f"Actual Value: {float(raw['actual_value_mkd']):,.0f} MKD")

                    # Add contract signing date
                    if raw.get('contract_signing_date'):
                        text_parts.append(f"Contract Signed: {raw['contract_signing_date']}")

                    # Add winner from raw JSON
                    if raw.get('winner'):
                        text_parts.append(f"Winner: {raw['winner']}")

                    # Parse bidders_data for full bidder details
                    if raw.get('bidders_data'):
                        bidders_raw = raw['bidders_data']
                        # Handle string (JSON encoded) or list
                        if isinstance(bidders_raw, str):
                            try:
                                bidders = json.loads(bidders_raw)
                            except:
                                bidders = []
                        else:
                            bidders = bidders_raw if isinstance(bidders_raw, list) else []

                        if bidders:
                            bidder_texts = []
                            for b in bidders:
                                name = b.get('company_name', b.get('name', ''))
                                bid_amt = b.get('bid_amount_mkd')
                                is_winner = b.get('is_winner', False)
                                rank = b.get('rank')

                                if name:
                                    parts = [name]
                                    if bid_amt:
                                        parts.append(f"{float(bid_amt):,.0f} MKD")
                                    if is_winner:
                                        parts.append("(WINNER)")
                                    elif rank:
                                        parts.append(f"(rank {rank})")
                                    bidder_texts.append(' - '.join(parts))

                            if bidder_texts:
                                text_parts.append(f"Bidders: {'; '.join(bidder_texts)}")
                except Exception as e:
                    logger.warning(f"Error parsing raw_data_json for {tender['tender_id']}: {e}")

            text = '\n'.join(text_parts)

            if self.dry_run:
                if i < 3:
                    logger.info(f"Would embed tender {tender['tender_id']}: {text[:200]}...")
                continue

            vector = self.generate_embedding(text)
            if not vector:
                self.stats['errors'] += 1
                continue

            metadata = {
                'source_type': 'tender',
                'source_id': tender['tender_id'],
                'title': tender['title'],
                'procuring_entity': tender.get('procuring_entity'),
                'cpv_code': tender.get('cpv_code'),
                'estimated_value': float(tender['estimated_value_mkd']) if tender.get('estimated_value_mkd') else None,
                'status': tender.get('status'),
            }

            self.store_embedding(
                vector=vector,
                text=text,
                tender_id=tender['tender_id'],
                metadata=metadata
            )

            self.stats['tenders'] += 1

            if (i + 1) % 10 == 0:
                self.conn.commit()
                logger.info(f"Progress: {i+1}/{len(tenders)} tenders embedded")

            time.sleep(RATE_LIMIT_DELAY)

        self.conn.commit()
        logger.info(f"Embedded {self.stats['tenders']} tenders")

    def embed_items(self, limit: int = 500):
        """Embed product items for price/product search"""
        logger.info(f"=== Embedding Product Items (limit={limit}) ===")

        self.cur.execute("""
            SELECT pi.id, pi.tender_id, pi.name, pi.quantity, pi.unit,
                   pi.unit_price, pi.total_price, pi.cpv_code,
                   pi.specifications, pi.raw_text,
                   t.title as tender_title, t.procuring_entity
            FROM product_items pi
            LEFT JOIN tenders t ON pi.tender_id = t.tender_id
            WHERE pi.name IS NOT NULL
              AND LENGTH(pi.name) > 3
              AND NOT EXISTS (
                  SELECT 1 FROM embeddings e
                  WHERE e.metadata->>'source_type' = 'item'
                    AND e.metadata->>'source_id' = pi.id::text
              )
            ORDER BY pi.unit_price DESC NULLS LAST
            LIMIT %s
        """, (limit,))

        items = self.cur.fetchall()
        logger.info(f"Found {len(items)} items to embed")

        for i, item in enumerate(items):
            # Format item text
            text_parts = [f"Product: {item['name']}"]

            if item.get('quantity') and item.get('unit'):
                text_parts.append(f"Quantity: {item['quantity']} {item['unit']}")
            elif item.get('quantity'):
                text_parts.append(f"Quantity: {item['quantity']}")

            if item.get('unit_price'):
                text_parts.append(f"Unit Price: {item['unit_price']} MKD")
            if item.get('total_price'):
                text_parts.append(f"Total Price: {item['total_price']} MKD")
            if item.get('cpv_code'):
                text_parts.append(f"CPV Code: {item['cpv_code']}")
            if item.get('tender_title'):
                text_parts.append(f"Tender: {item['tender_title']}")
            if item.get('procuring_entity'):
                text_parts.append(f"Entity: {item['procuring_entity']}")

            # Add specifications
            if item.get('specifications'):
                try:
                    specs = item['specifications'] if isinstance(item['specifications'], dict) else json.loads(item['specifications'])
                    if specs:
                        specs_str = ', '.join(f"{k}: {v}" for k, v in specs.items() if v)
                        if specs_str:
                            text_parts.append(f"Specifications: {specs_str}")
                except:
                    pass

            text = '\n'.join(text_parts)

            if self.dry_run:
                if i < 3:
                    logger.info(f"Would embed item {item['id']}: {text[:200]}...")
                continue

            vector = self.generate_embedding(text)
            if not vector:
                self.stats['errors'] += 1
                continue

            metadata = {
                'source_type': 'item',
                'source_id': str(item['id']),
                'item_name': item['name'],
                'unit_price': float(item['unit_price']) if item.get('unit_price') else None,
                'cpv_code': item.get('cpv_code'),
                'tender_title': item.get('tender_title'),
            }

            self.store_embedding(
                vector=vector,
                text=text,
                tender_id=item['tender_id'],
                metadata=metadata
            )

            self.stats['items'] += 1

            if (i + 1) % 10 == 0:
                self.conn.commit()
                logger.info(f"Progress: {i+1}/{len(items)} items embedded")

            time.sleep(RATE_LIMIT_DELAY)

        self.conn.commit()
        logger.info(f"Embedded {self.stats['items']} items")

    def embed_bidders(self, limit: int = 200):
        """Embed bidder/supplier information for company search"""
        logger.info(f"=== Embedding Bidders (limit={limit}) ===")

        # Get unique companies with their stats
        self.cur.execute("""
            WITH company_stats AS (
                SELECT
                    company_name,
                    company_tax_id,
                    COUNT(*) as bid_count,
                    SUM(CASE WHEN is_winner THEN 1 ELSE 0 END) as win_count,
                    SUM(CASE WHEN is_winner THEN bid_amount_mkd ELSE 0 END) as total_value,
                    array_agg(DISTINCT tender_id) as tender_ids
                FROM tender_bidders
                WHERE company_name IS NOT NULL
                GROUP BY company_name, company_tax_id
                ORDER BY win_count DESC
                LIMIT %s
            )
            SELECT * FROM company_stats
            WHERE NOT EXISTS (
                SELECT 1 FROM embeddings e
                WHERE e.metadata->>'source_type' = 'bidder'
                  AND e.metadata->>'company_name' = company_stats.company_name
            )
        """, (limit,))

        bidders = self.cur.fetchall()
        logger.info(f"Found {len(bidders)} companies to embed")

        for i, bidder in enumerate(bidders):
            # Format bidder text
            text_parts = [f"Company: {bidder['company_name']}"]

            if bidder.get('company_tax_id'):
                text_parts.append(f"Tax ID: {bidder['company_tax_id']}")
            if bidder.get('bid_count'):
                text_parts.append(f"Total Bids: {bidder['bid_count']}")
            if bidder.get('win_count'):
                text_parts.append(f"Wins: {bidder['win_count']}")
                win_rate = (bidder['win_count'] / bidder['bid_count']) * 100
                text_parts.append(f"Win Rate: {win_rate:.1f}%")
            if bidder.get('total_value'):
                text_parts.append(f"Total Contract Value: {bidder['total_value']:,.0f} MKD")

            text = '\n'.join(text_parts)

            if self.dry_run:
                if i < 3:
                    logger.info(f"Would embed bidder: {text[:200]}...")
                continue

            vector = self.generate_embedding(text)
            if not vector:
                self.stats['errors'] += 1
                continue

            metadata = {
                'source_type': 'bidder',
                'company_name': bidder['company_name'],
                'company_tax_id': bidder.get('company_tax_id'),
                'bid_count': bidder.get('bid_count'),
                'win_count': bidder.get('win_count'),
                'total_value': float(bidder['total_value']) if bidder.get('total_value') else None,
            }

            # Use first tender_id for reference
            tender_id = bidder['tender_ids'][0] if bidder.get('tender_ids') else None

            self.store_embedding(
                vector=vector,
                text=text,
                tender_id=tender_id,
                metadata=metadata
            )

            self.stats['bidders'] += 1

            if (i + 1) % 10 == 0:
                self.conn.commit()
                logger.info(f"Progress: {i+1}/{len(bidders)} bidders embedded")

            time.sleep(RATE_LIMIT_DELAY)

        self.conn.commit()
        logger.info(f"Embedded {self.stats['bidders']} bidders")

    def run(self, sources: List[str], limit_per_source: int = 500):
        """Run embedding for specified sources"""
        try:
            self.connect()

            # Get current embedding count
            self.cur.execute("SELECT COUNT(*) as cnt FROM embeddings")
            start_count = self.cur.fetchone()['cnt']
            logger.info(f"Starting embeddings: {start_count}")

            if 'documents' in sources or 'all' in sources:
                self.embed_documents(limit=limit_per_source)

            if 'tenders' in sources or 'all' in sources:
                self.embed_tenders(limit=limit_per_source)

            if 'items' in sources or 'all' in sources:
                self.embed_items(limit=limit_per_source)

            if 'bidders' in sources or 'all' in sources:
                self.embed_bidders(limit=min(limit_per_source, 200))

            # Final stats
            self.cur.execute("SELECT COUNT(*) as cnt FROM embeddings")
            end_count = self.cur.fetchone()['cnt']

            logger.info("\n" + "="*50)
            logger.info("EMBEDDING COMPLETE")
            logger.info("="*50)
            logger.info(f"Documents: {self.stats['documents']}")
            logger.info(f"Tenders: {self.stats['tenders']}")
            logger.info(f"Items: {self.stats['items']}")
            logger.info(f"Bidders: {self.stats['bidders']}")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info(f"Total embeddings: {start_count} -> {end_count} (+{end_count - start_count})")

        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description='Generate embeddings for RAG')
    parser.add_argument('--sources', nargs='+',
                       choices=['documents', 'tenders', 'items', 'bidders', 'all'],
                       default=['all'],
                       help='Data sources to embed')
    parser.add_argument('--limit', type=int, default=500,
                       help='Max items per source')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be embedded without storing')
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        print("ERROR: Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable")
        sys.exit(1)

    generator = EmbeddingGenerator(dry_run=args.dry_run)
    generator.run(sources=args.sources, limit_per_source=args.limit)


if __name__ == '__main__':
    main()

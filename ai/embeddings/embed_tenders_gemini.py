#!/usr/bin/env python3
"""
Generate embeddings from tender raw_data_json using Gemini API.
NEW script - does not modify existing flows.
"""
import asyncio
import json
import os
import logging
import google.generativeai as genai
import asyncpg
from typing import List
import time

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/nabavkidata/embed_tenders_gemini.log')
    ]
)
logger = logging.getLogger(__name__)

# Load from .env
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/nabavkidata/.env')

DATABASE_URL = os.getenv('DATABASE_URL')

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'gemini-embedding-001')

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

def get_embedding(text: str) -> str:
    """Get embedding from Gemini, return as pgvector string format."""
    result = genai.embed_content(
        model=f'models/{EMBEDDING_MODEL}',
        content=text[:8000],
        task_type='retrieval_document',
        output_dimensionality=768
    )
    # Convert to pgvector string format: '[0.1, 0.2, ...]'
    embedding_list = result['embedding']
    return '[' + ','.join(str(x) for x in embedding_list) + ']'

async def embed_tenders(batch_size: int = 50, max_tenders: int = 10000):
    """Generate embeddings for tenders with raw_data_json but no embeddings."""
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Get tenders with raw_data_json but no tender-level embeddings
    query = """
        SELECT t.tender_id, t.raw_data_json
        FROM tenders t
        WHERE t.raw_data_json IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM embeddings e 
              WHERE e.tender_id = t.tender_id 
              AND e.doc_id IS NULL
          )
        ORDER BY t.created_at DESC
        LIMIT $1
    """
    tenders = await conn.fetch(query, max_tenders)
    
    logger.info(f'Found {len(tenders)} tenders needing embeddings')
    
    count = 0
    errors = 0
    
    for tender in tenders:
        try:
            # Extract data from raw_data_json
            data = tender['raw_data_json']
            if isinstance(data, str):
                data = json.loads(data)
            
            # Build searchable text in Macedonian
            text_parts = []
            if data.get('tender_id'):
                text_parts.append(f"Тендер: {data['tender_id']}")
            if data.get('title'):
                text_parts.append(f"Наслов: {data['title']}")
            if data.get('description'):
                text_parts.append(f"Опис: {data['description']}")
            if data.get('procuring_entity'):
                text_parts.append(f"Договорен орган: {data['procuring_entity']}")
            if data.get('winner'):
                text_parts.append(f"Добитник: {data['winner']}")
            if data.get('estimated_value_mkd'):
                text_parts.append(f"Проценета вредност: {data['estimated_value_mkd']} МКД")
            if data.get('cpv_code'):
                text_parts.append(f"CPV код: {data['cpv_code']}")
            if data.get('status'):
                text_parts.append(f"Статус: {data['status']}")
            
            text = '\n'.join(text_parts)
            
            if len(text) < 20:
                continue  # Skip empty tenders
            
            # Get embedding from Gemini (returns pgvector string format)
            embedding_str = get_embedding(text)
            
            # Store embedding (doc_id=NULL indicates tender-level embedding)
            await conn.execute("""
                INSERT INTO embeddings (tender_id, doc_id, chunk_text, chunk_index, vector, metadata)
                VALUES ($1, NULL, $2, 0, $3::vector, $4::jsonb)
                ON CONFLICT DO NOTHING
            """, 
                tender['tender_id'], 
                text[:2000], 
                embedding_str, 
                json.dumps({'source': 'tender_raw_data_json', 'model': EMBEDDING_MODEL})
            )
            
            count += 1
            if count % 100 == 0:
                logger.info(f'Embedded {count}/{len(tenders)} tenders ({errors} errors)')
            
            # Small delay to avoid rate limits
            if count % 50 == 0:
                time.sleep(1)
                
        except Exception as e:
            errors += 1
            if errors <= 10:
                logger.error(f'Error embedding {tender["tender_id"]}: {e}')
            time.sleep(2)  # Rate limit backoff
    
    await conn.close()
    logger.info(f'Done! Embedded {count} tenders, {errors} errors')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Embed tender raw_data_json using Gemini')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size')
    parser.add_argument('--max-tenders', type=int, default=10000, help='Max tenders to process')
    args = parser.parse_args()
    
    asyncio.run(embed_tenders(args.batch_size, args.max_tenders))

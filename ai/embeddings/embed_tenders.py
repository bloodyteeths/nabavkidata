#!/usr/bin/env python3
"""Generate embeddings from tender raw_data_json for semantic search."""
import asyncio
import json
import os
import logging
from openai import OpenAI
import asyncpg
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL', 
    os.getenv('DATABASE_URL'))

client = OpenAI()

def get_embedding(text: str) -> list:
    """Get embedding from OpenAI."""
    response = client.embeddings.create(
        model='text-embedding-3-small',
        input=text[:8000]  # Limit to 8k chars
    )
    return response.data[0].embedding

async def embed_tenders(batch_size: int = 100, max_tenders: int = 10000):
    """Generate embeddings for tenders without embeddings."""
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Get tenders with raw_data_json but no embeddings
    tenders = await conn.fetch('''
        SELECT t.tender_id, t.raw_data_json
        FROM tenders t
        WHERE t.raw_data_json IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.tender_id = t.tender_id)
        LIMIT $1
    ''', max_tenders)
    
    logger.info(f'Found {len(tenders)} tenders to embed')
    
    count = 0
    for tender in tenders:
        try:
            # Create text from raw_data_json
            data = tender['raw_data_json']
            if isinstance(data, str):
                data = json.loads(data)
            
            text = f"""
Tender: {data.get('tender_id', '')}
Title: {data.get('title', '')}
Description: {data.get('description', '')}
Procuring Entity: {data.get('procuring_entity', '')}
Winner: {data.get('winner', '')}
Value: {data.get('estimated_value_mkd', '')} MKD
CPV: {data.get('cpv_code', '')}
Status: {data.get('status', '')}
"""
            
            # Get embedding
            embedding = get_embedding(text)
            
            # Store embedding
            await conn.execute('''
                INSERT INTO embeddings (tender_id, chunk_text, chunk_index, vector, metadata)
                VALUES ($1, $2, 0, $3, $4)
                ON CONFLICT DO NOTHING
            ''', tender['tender_id'], text[:2000], embedding, json.dumps({'source': 'raw_data_json'}))
            
            count += 1
            if count % 100 == 0:
                logger.info(f'Embedded {count}/{len(tenders)} tenders')
                
        except Exception as e:
            logger.error(f'Error embedding {tender["tender_id"]}: {e}')
    
    await conn.close()
    logger.info(f'Done! Embedded {count} tenders')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--max-tenders', type=int, default=10000)
    args = parser.parse_args()
    
    asyncio.run(embed_tenders(args.batch_size, args.max_tenders))

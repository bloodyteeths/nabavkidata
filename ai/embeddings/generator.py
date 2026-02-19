"""Generate embeddings for tender documents"""
import os
import asyncio
import asyncpg
from openai import AsyncOpenAI
from typing import List
from dotenv import load_dotenv
load_dotenv()


client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_embeddings():
    """Generate embeddings for all documents"""
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))

    try:
        docs = await conn.fetch("""
            SELECT d.doc_id, d.tender_id, d.content_text, t.title, t.category
            FROM documents d
            JOIN tenders t ON d.tender_id = t.tender_id
            WHERE d.extraction_status = 'success'
            AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.doc_id = d.doc_id)
            LIMIT 100
        """)

        for doc in docs:
            chunks = chunk_text(doc['content_text'])

            for idx, chunk in enumerate(chunks):
                embedding = await get_embedding(chunk)

                await conn.execute("""
                    INSERT INTO embeddings (doc_id, tender_id, chunk_text, chunk_index, vector, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, doc['doc_id'], doc['tender_id'], chunk, idx, embedding,
                    {'title': doc['title'], 'category': doc['category']})

        print(f"Generated embeddings for {len(docs)} documents")
    finally:
        await conn.close()

def chunk_text(text: str, size: int = 800) -> List[str]:
    """Split text into chunks"""
    words = text.split()
    chunks = []
    for i in range(0, len(words), size):
        chunks.append(' '.join(words[i:i+size]))
    return chunks

async def get_embedding(text: str) -> List[float]:
    """Get embedding from OpenAI"""
    response = await client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

if __name__ == "__main__":
    asyncio.run(generate_embeddings())

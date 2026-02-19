"""
Test script for /api/tenders/{number}/{year}/chat endpoint
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

# Set environment variables
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL')
os.environ['GEMINI_API_KEY'] = 'YOUR_GEMINI_API_KEY'
os.environ['GEMINI_MODEL'] = 'gemini-2.0-flash'

from models import Tender, TenderBidder, Document

async def test_chat_data():
    """Test that we can fetch tender data for chat"""
    
    # Create engine
    engine = create_async_engine(os.environ['DATABASE_URL'], echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        # Test tender: 01714/2025 (has bidders and documents)
        tender_id = "01714/2025"
        
        # Get tender
        result = await db.execute(select(Tender).where(Tender.tender_id == tender_id))
        tender = result.scalar_one_or_none()
        
        if not tender:
            print(f"❌ Tender {tender_id} not found")
            return False
        
        print(f"✓ Found tender: {tender.title[:80]}")
        print(f"  - Procuring entity: {tender.procuring_entity}")
        print(f"  - Estimated value: {tender.estimated_value_mkd} MKD")
        
        # Get bidders
        result = await db.execute(select(TenderBidder).where(TenderBidder.tender_id == tender_id))
        bidders = result.scalars().all()
        print(f"✓ Found {len(bidders)} bidders")
        for b in bidders[:3]:
            print(f"  - {b.company_name}: {b.bid_amount_mkd} MKD")
        
        # Get documents
        result = await db.execute(
            select(Document)
            .where(Document.tender_id == tender_id)
            .where(Document.content_text.isnot(None))
        )
        documents = result.scalars().all()
        print(f"✓ Found {len(documents)} documents with content")
        for d in documents:
            content_len = len(d.content_text) if d.content_text else 0
            print(f"  - {d.file_name}: {content_len} chars")
        
        print("\n✓ All data checks passed!")
        return True

if __name__ == "__main__":
    asyncio.run(test_chat_data())

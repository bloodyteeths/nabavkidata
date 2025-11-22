#!/usr/bin/env python3
"""
User Interest Vector Update Cron
Daily job to update all user interest vectors
"""
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import AsyncSessionLocal
from models import User
from services.personalization_engine import InterestVectorBuilder
from sqlalchemy import select


async def update_all_user_vectors():
    """Update interest vectors for all active users"""

    print(f"[{datetime.utcnow()}] Starting user interest vector update...")

    async with AsyncSessionLocal() as db:
        # Get all users
        query = select(User.user_id)
        result = await db.execute(query)
        user_ids = [row[0] for row in result.all()]

        print(f"Found {len(user_ids)} users to process")

        builder = InterestVectorBuilder(db)

        updated_count = 0
        error_count = 0

        for user_id in user_ids:
            try:
                await builder.update_user_vector(user_id)
                updated_count += 1

                if updated_count % 10 == 0:
                    print(f"Processed {updated_count}/{len(user_ids)} users")

            except Exception as e:
                print(f"Error updating user {user_id}: {e}")
                error_count += 1
                continue

        print(f"\n[{datetime.utcnow()}] Update complete:")
        print(f"  ✓ Updated: {updated_count}")
        print(f"  ✗ Errors: {error_count}")


async def update_single_user(user_id: str):
    """Update interest vector for single user"""

    async with AsyncSessionLocal() as db:
        builder = InterestVectorBuilder(db)
        await builder.update_user_vector(user_id)
        print(f"✓ Updated interest vector for user {user_id}")


def main():
    """Main entry point"""

    if len(sys.argv) > 1:
        # Single user mode
        user_id = sys.argv[1]
        asyncio.run(update_single_user(user_id))
    else:
        # Batch mode (all users)
        asyncio.run(update_all_user_vectors())


if __name__ == "__main__":
    main()

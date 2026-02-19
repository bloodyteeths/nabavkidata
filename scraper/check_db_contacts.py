#!/usr/bin/env python3
"""Check existing contact data in database"""

import asyncio
import asyncpg

async def check_data():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))

    # Check what winner/contact data we already have
    print('=== Winner data in tenders table ===')
    winners = await conn.fetch('''
        SELECT winner, contact_email, contact_phone, contact_person, procuring_entity
        FROM tenders
        WHERE winner IS NOT NULL AND winner != ''
        LIMIT 10
    ''')
    for row in winners:
        print(f'Winner: {row["winner"][:50] if row["winner"] else "N/A"}')
        print(f'  Email: {row["contact_email"]}')
        print(f'  Phone: {row["contact_phone"]}')
        print(f'  Contact: {row["contact_person"]}')
        print(f'  Entity: {row["procuring_entity"][:40] if row["procuring_entity"] else "N/A"}')
        print()

    # Count totals
    print('=== Counts ===')
    total = await conn.fetchval('SELECT COUNT(*) FROM tenders')
    with_winner = await conn.fetchval("SELECT COUNT(*) FROM tenders WHERE winner IS NOT NULL AND winner != ''")
    with_email = await conn.fetchval("SELECT COUNT(*) FROM tenders WHERE contact_email IS NOT NULL AND contact_email != ''")
    with_phone = await conn.fetchval("SELECT COUNT(*) FROM tenders WHERE contact_phone IS NOT NULL AND contact_phone != ''")

    print(f'Total tenders: {total}')
    print(f'With winner: {with_winner}')
    print(f'With contact_email: {with_email}')
    print(f'With contact_phone: {with_phone}')

    # Check unique procuring entities with emails
    print('\n=== Unique procuring entities with contact_email ===')
    entities = await conn.fetch('''
        SELECT DISTINCT procuring_entity, contact_email, contact_phone
        FROM tenders
        WHERE contact_email IS NOT NULL AND contact_email != ''
        LIMIT 20
    ''')
    print(f'Sample entities with email ({len(entities)}):')
    for e in entities:
        print(f'  {e["procuring_entity"][:40] if e["procuring_entity"] else "N/A"}: {e["contact_email"]}')

    # Check suppliers table
    print('\n=== Suppliers table ===')
    try:
        suppliers_count = await conn.fetchval('SELECT COUNT(*) FROM suppliers')
        print(f'Suppliers count: {suppliers_count}')
        suppliers = await conn.fetch('SELECT company_name, contact_email, contact_phone FROM suppliers LIMIT 5')
        for s in suppliers:
            print(f'  {s["company_name"]}: email={s["contact_email"]}, phone={s["contact_phone"]}')
    except Exception as e:
        print(f'  Error: {e}')

    # Check tender_bidders table
    print('\n=== Tender Bidders table ===')
    try:
        bidders_count = await conn.fetchval('SELECT COUNT(*) FROM tender_bidders')
        print(f'Total bidders: {bidders_count}')
        bidders = await conn.fetch('SELECT company_name, is_winner FROM tender_bidders LIMIT 5')
        for b in bidders:
            print(f'  {b["company_name"]}: winner={b["is_winner"]}')
    except Exception as e:
        print(f'  Error: {e}')

    # Get unique winners
    print('\n=== Unique winners (company names) ===')
    unique_winners = await conn.fetch('''
        SELECT winner, COUNT(*) as wins
        FROM tenders
        WHERE winner IS NOT NULL AND winner != ''
        GROUP BY winner
        ORDER BY wins DESC
        LIMIT 15
    ''')
    print(f'Top winners:')
    for w in unique_winners:
        name = w["winner"][:60] if w["winner"] else "N/A"
        print(f'  {name}: {w["wins"]} wins')

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_data())

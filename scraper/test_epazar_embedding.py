#!/usr/bin/env python3
"""
Quick test to preview how epazar tender text will be built for embeddings.
"""
import os
import psycopg2
from dotenv import load_dotenv
load_dotenv()


DATABASE_URL = os.getenv('DATABASE_URL')


def build_epazar_text(tender_data, items_text=''):
    """Build searchable text from epazar tender fields."""
    parts = []

    if tender_data.get('tender_id'):
        parts.append(f"epazar_{tender_data['tender_id']}")

    if tender_data.get('title'):
        parts.append(tender_data['title'])

    if tender_data.get('description'):
        desc = str(tender_data['description'])[:500]
        parts.append(desc)

    if tender_data.get('contracting_authority'):
        parts.append(tender_data['contracting_authority'])

    if tender_data.get('procedure_type'):
        parts.append(tender_data['procedure_type'])

    if tender_data.get('category'):
        parts.append(tender_data['category'])

    if tender_data.get('cpv_code'):
        parts.append(f"CPV: {tender_data['cpv_code']}")

    if items_text:
        parts.append(items_text[:500])

    text = ' | '.join(parts)
    return text[:1500] if text else ''


def main():
    print("Testing e-Pazar embedding text generation...\n")
    print("=" * 80)

    conn = psycopg2.connect(DATABASE_URL, connect_timeout=30)
    cur = conn.cursor()

    # Get a few sample tenders with their items
    cur.execute("""
        SELECT
            e.tender_id,
            e.title,
            e.description,
            e.contracting_authority,
            e.procedure_type,
            e.category,
            e.cpv_code
        FROM epazar_tenders e
        LIMIT 5
    """)

    for row in cur.fetchall():
        tender = {
            'tender_id': row[0],
            'title': row[1],
            'description': row[2],
            'contracting_authority': row[3],
            'procedure_type': row[4],
            'category': row[5],
            'cpv_code': row[6]
        }

        # Get items for this tender
        cur.execute("""
            SELECT STRING_AGG(
                COALESCE(item_name, '') || ' ' || COALESCE(item_description, ''),
                ', '
            )
            FROM epazar_items
            WHERE tender_id = %s
        """, (tender['tender_id'],))

        items_result = cur.fetchone()
        items_text = items_result[0] if items_result and items_result[0] else ''

        # Build text
        text = build_epazar_text(tender, items_text)

        print(f"\nTender ID: {tender['tender_id']}")
        print(f"Embedding ID: epazar_{tender['tender_id']}")
        print(f"Text length: {len(text)} chars")
        print(f"Text preview:\n{text[:300]}...")
        print("-" * 80)

    cur.close()
    conn.close()

    print("\nDone! This shows how the text will be constructed for embeddings.")


if __name__ == '__main__':
    main()

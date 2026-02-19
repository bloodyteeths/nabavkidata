#!/usr/bin/env python3
"""
Match opentender tenders to e-nabavki tenders by title, entity, date, and value.
Updates source_url and dossier_id for matched records.
"""
import asyncio
import os
import re
from datetime import timedelta
import asyncpg

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


def normalize_title(title):
    """Normalize title for comparison."""
    if not title:
        return ""
    # Remove extra whitespace, lowercase
    title = re.sub(r'\s+', ' ', title.lower().strip())
    # Remove common punctuation
    title = re.sub(r'[.,;:!?\-–—\'"()[\]{}]', '', title)
    return title


def normalize_entity(entity):
    """Normalize entity name for comparison."""
    if not entity:
        return ""
    entity = re.sub(r'\s+', ' ', entity.lower().strip())
    # Remove common prefixes/suffixes
    entity = re.sub(r'^(општина|јкп|јп|ад|дооел|доо)\s+', '', entity)
    entity = re.sub(r'\s+(скопје|битола|прилеп|охрид|куманово|тетово|велес|штип|струмица|кавадарци)$', '', entity)
    return entity


async def main():
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get opentender tenders without e-nabavki links
        print("Loading opentender tenders...")
        ot_tenders = await conn.fetch("""
            SELECT tender_id, title, procuring_entity, publication_date,
                   estimated_value_mkd, cpv_code
            FROM tenders
            WHERE tender_id LIKE 'OT-%'
            AND (dossier_id IS NULL OR source_url LIKE '%opentender%')
            AND title IS NOT NULL
            AND procuring_entity IS NOT NULL
        """)
        print(f"Found {len(ot_tenders)} opentender tenders to match")

        # Get e-nabavki tenders with dossier_id
        print("Loading e-nabavki tenders...")
        en_tenders = await conn.fetch("""
            SELECT tender_id, title, procuring_entity, publication_date,
                   estimated_value_mkd, cpv_code, dossier_id, source_url
            FROM tenders
            WHERE tender_id NOT LIKE 'OT-%'
            AND dossier_id IS NOT NULL
            AND source_url LIKE '%e-nabavki%'
            AND title IS NOT NULL
        """)
        print(f"Found {len(en_tenders)} e-nabavki tenders with dossier_id")

        # Build lookup index by normalized entity
        entity_index = {}
        for en in en_tenders:
            norm_entity = normalize_entity(en['procuring_entity'])
            if norm_entity not in entity_index:
                entity_index[norm_entity] = []
            entity_index[norm_entity].append(en)

        print(f"Built index with {len(entity_index)} unique entities")

        matched = 0
        no_match = 0

        for ot in ot_tenders:
            norm_entity = normalize_entity(ot['procuring_entity'])
            norm_title = normalize_title(ot['title'])

            # Find candidates by entity
            candidates = entity_index.get(norm_entity, [])

            best_match = None
            best_score = 0

            for en in candidates:
                score = 0

                # Title similarity (most important)
                en_title = normalize_title(en['title'])
                if norm_title == en_title:
                    score += 100
                elif norm_title in en_title or en_title in norm_title:
                    score += 50
                else:
                    # Check word overlap
                    ot_words = set(norm_title.split())
                    en_words = set(en_title.split())
                    if len(ot_words) > 0 and len(en_words) > 0:
                        overlap = len(ot_words & en_words) / max(len(ot_words), len(en_words))
                        score += int(overlap * 40)

                # Date proximity
                if ot['publication_date'] and en['publication_date']:
                    date_diff = abs((ot['publication_date'] - en['publication_date']).days)
                    if date_diff <= 7:
                        score += 30
                    elif date_diff <= 30:
                        score += 15
                    elif date_diff <= 90:
                        score += 5

                # Value similarity
                if ot['estimated_value_mkd'] and en['estimated_value_mkd']:
                    ot_val = float(ot['estimated_value_mkd'])
                    en_val = float(en['estimated_value_mkd'])
                    if ot_val > 0 and en_val > 0:
                        ratio = min(ot_val, en_val) / max(ot_val, en_val)
                        if ratio > 0.95:
                            score += 20
                        elif ratio > 0.8:
                            score += 10

                # CPV code match
                if ot['cpv_code'] and en['cpv_code']:
                    if ot['cpv_code'] == en['cpv_code']:
                        score += 15
                    elif ot['cpv_code'][:5] == en['cpv_code'][:5]:
                        score += 8

                if score > best_score:
                    best_score = score
                    best_match = en

            # Require minimum score for match (title match is essential)
            if best_match and best_score >= 80:
                await conn.execute("""
                    UPDATE tenders
                    SET source_url = $1, dossier_id = $2
                    WHERE tender_id = $3
                """, best_match['source_url'], best_match['dossier_id'], ot['tender_id'])
                matched += 1
                if matched % 100 == 0:
                    print(f"  Matched {matched} tenders...")
            else:
                no_match += 1

        print(f"\nDone!")
        print(f"  Matched: {matched}")
        print(f"  No match: {no_match}")

    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())

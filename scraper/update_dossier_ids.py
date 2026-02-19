#!/usr/bin/env python3
"""
Update tenders with dossier_ids from ocds_mapping table.
Uses batched updates to avoid blocking.
"""
import psycopg2

DATABASE_URL = os.getenv('DATABASE_URL')

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Create index on mapping table
    print("Creating index on mapping table...")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ocds_mapping_uuid ON ocds_mapping(uuid)")
    conn.commit()

    # Check how many need updating
    cur.execute("""
        SELECT COUNT(*) FROM tenders
        WHERE source_url LIKE '%%opentender%%'
        AND dossier_id IS NULL
    """)
    total = cur.fetchone()[0]
    print(f"Tenders to update: {total}")

    # Update in batches
    updated = 0
    batch_size = 500

    while True:
        cur.execute("""
            WITH to_update AS (
                SELECT t.tender_id, m.dossier_id, m.enabavki_url
                FROM tenders t
                JOIN ocds_mapping m ON SUBSTRING(t.source_url FROM '[a-f0-9-]{36}$') = m.uuid
                WHERE t.source_url LIKE '%%opentender%%'
                AND t.dossier_id IS NULL
                LIMIT %s
            )
            UPDATE tenders t SET
                dossier_id = u.dossier_id,
                source_url = u.enabavki_url,
                updated_at = NOW()
            FROM to_update u
            WHERE t.tender_id = u.tender_id
        """, (batch_size,))

        rows = cur.rowcount
        conn.commit()
        updated += rows

        if updated % 5000 == 0 or rows == 0:
            print(f"Updated {updated} tenders...")

        if rows == 0:
            break

    print(f"Done! Total updated: {updated}")

    # Verify
    cur.execute("SELECT COUNT(*) FROM tenders WHERE dossier_id IS NOT NULL")
    with_dossier = cur.fetchone()[0]
    print(f"Tenders with dossier_id: {with_dossier}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

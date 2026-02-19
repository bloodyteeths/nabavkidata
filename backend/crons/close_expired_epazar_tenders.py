#!/usr/bin/env python3
"""
Close Expired E-Pazar Tenders Cron Job

Runs daily to update epazar_tenders with status='active'
where closing_date has passed to status='closed'.

Usage:
    python3 close_expired_epazar_tenders.py

Crontab entry:
    0 6 * * * cd /home/ubuntu/nabavkidata && /home/ubuntu/nabavkidata/backend/venv/bin/python3 backend/crons/close_expired_epazar_tenders.py >> /var/log/nabavkidata/close_expired_epazar.log 2>&1
"""

import os
import sys
from datetime import datetime, date

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    """Get database connection from environment or defaults."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com'),
        database=os.getenv('DB_NAME', 'nabavkidata'),
        user=os.getenv('DB_USER', 'nabavki_user'),
        password=os.getenv('DB_PASSWORD', ''),
        port=os.getenv('DB_PORT', 5432)
    )


def close_expired_epazar_tenders():
    """Update expired active e-pazar tenders to closed status."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] Starting close_expired_epazar_tenders job")

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get count before update
        cur.execute("""
            SELECT COUNT(*) as count
            FROM epazar_tenders
            WHERE status = 'active'
              AND closing_date IS NOT NULL
              AND closing_date < CURRENT_DATE
        """)
        pending_count = cur.fetchone()['count']
        print(f"[{timestamp}] Found {pending_count} expired e-pazar tenders to close")

        if pending_count == 0:
            print(f"[{timestamp}] No expired e-pazar tenders to update")
            return 0

        # Update the tenders
        cur.execute("""
            UPDATE epazar_tenders
            SET status = 'closed',
                updated_at = NOW()
            WHERE status = 'active'
              AND closing_date IS NOT NULL
              AND closing_date < CURRENT_DATE
            RETURNING tender_id, closing_date
        """)

        updated = cur.fetchall()
        conn.commit()

        updated_count = len(updated)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] Successfully closed {updated_count} expired e-pazar tenders")

        # Log sample of updated tenders
        if updated_count > 0:
            print(f"[{timestamp}] Sample updated e-pazar tender IDs:")
            for row in updated[:10]:
                print(f"  - {row['tender_id']} (closed: {row['closing_date']})")

        return updated_count

    except Exception as e:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] ERROR: {e}")
        if conn:
            conn.rollback()
        raise

    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    try:
        count = close_expired_epazar_tenders()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] Job completed successfully. Updated {count} e-pazar tenders.")
        sys.exit(0)
    except Exception as e:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] Job failed: {e}")
        sys.exit(1)

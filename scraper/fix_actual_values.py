#!/usr/bin/env python3
"""
Fix actual_value_mkd for OCDS tenders
Extracts award values from OCDS data and updates tenders table

Background:
- We have 260,901 completed tenders from OCDS (OpenTender.eu)
- Only 1,718 (0.66%) have actual_value_mkd populated
- Analysis shows 6,675 OCDS records have award values
- The import_opentender.py script incorrectly used award values as estimated_value
- This script extracts actual values from awards and populates actual_value_mkd

Usage:
    python fix_actual_values.py [--dry-run] [--batch-size 500] [--limit 10000]
"""

import asyncio
import gzip
import json
import os
import sys
from pathlib import Path
import argparse
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed. Run: pip install asyncpg")
    sys.exit(1)

# Database URL
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    os.getenv("DATABASE_URL")
)

# OpenTender dataset file
DATASET_FILE = Path(__file__).parent / "downloads" / "opentender_mk.jsonl.gz"


def extract_actual_value(release: dict) -> tuple:
    """
    Extract actual value from OCDS awards or contracts

    Returns:
        tuple: (actual_value_mkd, winner_name, ocid, date_str)
    """
    ocid = release.get("ocid", "")
    date_str = release.get("date", "")
    awards = release.get("awards", [])

    actual_value_mkd = None
    winner = None

    # Primary source: awards with value
    if awards:
        # Get the first award (usually the winning award)
        primary_award = awards[0]

        # Get award value
        award_value = primary_award.get("value", {})
        amount = award_value.get("amount")
        currency = award_value.get("currency", "MKD")

        if amount:
            # Convert EUR to MKD if needed (approximate rate)
            if currency == "EUR":
                actual_value_mkd = float(amount) * 61.5
            else:
                actual_value_mkd = float(amount)

        # Get winner from award suppliers
        suppliers = primary_award.get("suppliers", [])
        if suppliers:
            winner = suppliers[0].get("name")

    # Fallback: check bids if no award value
    if not actual_value_mkd:
        bids = release.get("bids", {}).get("details", [])
        if bids:
            # Find winning bid or first valid bid
            for bid in bids:
                if bid.get("status") == "valid" or len(bids) == 1:
                    bid_value = bid.get("value", {})
                    amount = bid_value.get("amount")
                    currency = bid_value.get("currency", "MKD")

                    if amount:
                        if currency == "EUR":
                            actual_value_mkd = float(amount) * 61.5
                        else:
                            actual_value_mkd = float(amount)

                    # Get winner from bid tenderers if not already set
                    if not winner:
                        tenderers = bid.get("tenderers", [])
                        if tenderers:
                            winner = tenderers[0].get("name")

                    break

    return actual_value_mkd, winner, ocid, date_str


def generate_tender_id(ocid: str, date_str: str = None) -> str:
    """
    Generate tender_id from OCID (same logic as import_opentender.py)

    Args:
        ocid: OCID string like 'ocds-70d2nz-ce3b436a-d5a2-3f9c-a4d1-3b97de73a37e'
        date_str: ISO date string to extract year from

    Returns:
        tender_id like 'OT-3b97de73a37e/2020'
    """
    import hashlib

    tender_id_parts = ocid.split("-")
    if len(tender_id_parts) >= 2:
        try:
            # Extract last 12 chars from OCID UUID
            # OCID format: ocds-70d2nz-ce3b436a-d5a2-3f9c-a4d1-3b97de73a37e
            # We use the last UUID part (3b97de73a37e)
            num = tender_id_parts[-1][:12] if tender_id_parts[-1] else hashlib.md5(ocid.encode()).hexdigest()[:12]

            # Extract year from date string
            year = "2020"  # default
            if date_str and len(date_str) >= 4:
                year = date_str[:4]

            return f"OT-{num}/{year}"
        except:
            return f"OT-{hashlib.md5(ocid.encode()).hexdigest()[:12]}/2020"
    else:
        return f"OT-{hashlib.md5(ocid.encode()).hexdigest()[:12]}/2020"


async def update_database(updates: list, dry_run: bool = False):
    """
    Update tenders with actual values

    Args:
        updates: List of dicts with tender_id, actual_value_mkd, winner
        dry_run: If True, only print what would be updated
    """
    if dry_run:
        print("\nDRY RUN MODE - No database changes will be made\n")
        print(f"Would update {len(updates)} tenders:")
        for i, update in enumerate(updates[:10], 1):
            print(f"  {i}. {update['tender_id']}")
            print(f"     OCID: {update['ocid']}")
            print(f"     Actual value: {update['actual_value_mkd']:,.2f} MKD")
            if update['winner']:
                print(f"     Winner: {update['winner'][:60]}")
        if len(updates) > 10:
            print(f"  ... and {len(updates) - 10} more")
        return

    # Convert DATABASE_URL to asyncpg format
    db_url = DATABASE_URL.replace("postgresql://", "").replace("postgresql+asyncpg://", "")

    pool = await asyncpg.create_pool(
        f"postgresql://{db_url}",
        min_size=5,
        max_size=25,
        command_timeout=120,
    )

    print(f"\nUpdating {len(updates)} tenders...")

    updated = 0
    not_found = 0
    errors = 0
    skipped_has_value = 0

    async with pool.acquire() as conn:
        for update in updates:
            try:
                # Find tender by tender_id
                result = await conn.fetchrow("""
                    SELECT actual_value_mkd, winner
                    FROM tenders
                    WHERE tender_id = $1
                """, update['tender_id'])

                if not result:
                    not_found += 1
                    continue

                current_actual = result['actual_value_mkd']
                current_winner = result['winner']

                # Only update if actual_value is NULL or if we have a better value
                should_update_value = current_actual is None and update['actual_value_mkd'] is not None
                should_update_winner = current_winner is None and update['winner'] is not None

                if should_update_value or should_update_winner:
                    await conn.execute("""
                        UPDATE tenders SET
                            actual_value_mkd = COALESCE($2, actual_value_mkd),
                            winner = COALESCE($3, winner),
                            updated_at = NOW()
                        WHERE tender_id = $1
                    """,
                        update['tender_id'],
                        update['actual_value_mkd'],
                        update['winner']
                    )
                    updated += 1
                else:
                    skipped_has_value += 1

            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"  Error updating {update['tender_id']}: {e}")

            # Progress update
            if (updated + not_found + errors + skipped_has_value) % 100 == 0:
                total = updated + not_found + errors + skipped_has_value
                percent = total * 100 / len(updates)
                print(f"\rProgress: {percent:.1f}% ({updated} updated, {not_found} not found, {skipped_has_value} skipped, {errors} errors)", end="", flush=True)

    await pool.close()

    print(f"\n\nUpdate complete!")
    print(f"  Updated: {updated}")
    print(f"  Not found: {not_found}")
    print(f"  Skipped (already has value): {skipped_has_value}")
    print(f"  Errors: {errors}")

    return updated


async def main():
    parser = argparse.ArgumentParser(description="Fix actual_value_mkd from OCDS data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without making changes")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for processing")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of records to process (0 = all)")
    args = parser.parse_args()

    print("=" * 70)
    print("Fix actual_value_mkd for OCDS Tenders")
    print("=" * 70)

    if not DATASET_FILE.exists():
        print(f"ERROR: Dataset file not found: {DATASET_FILE}")
        print("Run import_opentender.py first to download the dataset")
        sys.exit(1)

    print(f"\nReading OCDS dataset from {DATASET_FILE}...")
    print("This will take a few minutes...\n")

    updates = []
    line_count = 0
    records_with_awards = 0
    parse_errors = 0

    try:
        with gzip.open(DATASET_FILE, "rt", encoding="utf-8") as f:
            for line in f:
                line_count += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)

                    # Extract actual value from awards
                    actual_value_mkd, winner, ocid, date_str = extract_actual_value(record)

                    if actual_value_mkd:
                        records_with_awards += 1

                        # Generate tender_id from OCID
                        tender_id = generate_tender_id(ocid, date_str)

                        updates.append({
                            'tender_id': tender_id,
                            'ocid': ocid,
                            'actual_value_mkd': actual_value_mkd,
                            'winner': winner
                        })

                except json.JSONDecodeError as e:
                    parse_errors += 1
                    if parse_errors <= 5:
                        print(f"  JSON parse error on line {line_count}: {e}")
                except Exception as e:
                    parse_errors += 1
                    if parse_errors <= 10:
                        print(f"  Parse error on line {line_count}: {e}")

                # Progress indicator
                if line_count % 50000 == 0:
                    print(f"  Processed {line_count} lines, found {records_with_awards} with award values...")

                # Limit for testing
                if args.limit > 0 and line_count >= args.limit:
                    break

    except Exception as e:
        print(f"ERROR reading file: {e}")
        sys.exit(1)

    print(f"\nProcessed {line_count} lines, {parse_errors} parse errors")
    print(f"Found {len(updates)} tenders with award values to update")

    if updates:
        await update_database(updates, dry_run=args.dry_run)
    else:
        print("No tenders to update!")


if __name__ == "__main__":
    asyncio.run(main())

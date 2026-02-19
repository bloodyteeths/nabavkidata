#!/usr/bin/env python3
"""
OpenTender OCDS Dataset Importer
Downloads and imports 260,901 historical tenders from OpenTender.eu

Usage:
    python import_opentender.py [--download-only] [--import-only]

The script:
1. Downloads the OCDS JSON dataset (~125MB) from data.open-contracting.org
2. Parses and transforms the data to match our schema
3. Bulk inserts into PostgreSQL with conflict handling
"""

import asyncio
import gzip
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import argparse
import urllib.request
import hashlib
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

# OpenTender download URL
OPENTENDER_URL = "https://data.open-contracting.org/download/138/json"
DOWNLOAD_DIR = Path(__file__).parent / "downloads"
DATASET_FILE = DOWNLOAD_DIR / "opentender_mk.jsonl.gz"  # JSONL format (line-delimited JSON)

def download_dataset():
    """Download OpenTender dataset with progress indicator"""
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    if DATASET_FILE.exists():
        print(f"Dataset already exists: {DATASET_FILE}")
        size_mb = DATASET_FILE.stat().st_size / (1024 * 1024)
        print(f"Size: {size_mb:.1f} MB")
        return True

    print(f"Downloading OpenTender dataset from {OPENTENDER_URL}")
    print("This may take a few minutes (~125MB)...")

    try:
        # Download with progress
        def reporthook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, downloaded * 100 / total_size)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                print(f"\rProgress: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="", flush=True)

        urllib.request.urlretrieve(OPENTENDER_URL, DATASET_FILE, reporthook)
        print(f"\n\nDownload complete: {DATASET_FILE}")
        return True

    except Exception as e:
        print(f"\nERROR downloading: {e}")
        return False

# Valid status values for our database
VALID_STATUSES = {'open', 'closed', 'awarded', 'cancelled', 'published', 'planned', 'active', 'pending', 'completed'}
STATUS_MAP = {
    'unknown': 'completed',
    'complete': 'completed',
    'unsuccessful': 'cancelled',
    'withdrawn': 'cancelled',
    'planning': 'planned',
    'tender': 'open',
    'award': 'awarded',
    'contract': 'completed',
}

def parse_ocds_release(release: dict) -> dict:
    """Parse OCDS release into our tender schema"""
    tender_data = release.get("tender", {})
    buyer = release.get("buyer", {})
    awards = release.get("awards", [])
    contracts = release.get("contracts", [])
    bids = release.get("bids", {}).get("details", [])

    # Get primary award winner from awards or bids
    winner = None
    award_value = None

    # Try awards first
    if awards:
        primary_award = awards[0]
        suppliers = primary_award.get("suppliers", [])
        if suppliers:
            winner = suppliers[0].get("name")
        award_value = primary_award.get("value", {})

    # Fallback to winning bid if no award
    if not winner and bids:
        # Find winning bid
        for bid in bids:
            if bid.get("status") == "valid" or len(bids) == 1:
                tenderers = bid.get("tenderers", [])
                if tenderers:
                    winner = tenderers[0].get("name")
                    if not award_value:
                        award_value = bid.get("value", {})
                    break

    # Get tender value
    tender_value = tender_data.get("value", {}) or {}
    value_amount = tender_value.get("amount") or (award_value.get("amount") if award_value else None)
    value_currency = tender_value.get("currency") or (award_value.get("currency") if award_value else "MKD")

    # Convert EUR to MKD if needed (approximate rate)
    estimated_value_mkd = None
    if value_amount:
        if value_currency == "EUR":
            estimated_value_mkd = float(value_amount) * 61.5  # EUR to MKD approximate
        else:
            estimated_value_mkd = float(value_amount)

    # Extract CPV codes
    items = tender_data.get("items", [])
    cpv_code = None
    if items:
        classification = items[0].get("classification", {})
        cpv_code = classification.get("id")

    # Get dates
    tender_period = tender_data.get("tenderPeriod", {}) or {}
    publication_date = tender_period.get("startDate") or release.get("date")
    deadline = tender_period.get("endDate")

    # Generate tender_id from OCID
    ocid = release.get("ocid", "")
    # Extract numeric ID from OCID like "ocds-xxx-MK-2023-12345"
    tender_id_parts = ocid.split("-")
    if len(tender_id_parts) >= 2:
        # Try to get year and number from OCID
        try:
            year = tender_id_parts[-2] if tender_id_parts[-2].isdigit() else "2020"
            num = tender_id_parts[-1] if tender_id_parts[-1].isdigit() else tender_id_parts[-1]
            tender_id = f"OT-{num}/{year}"
        except:
            tender_id = f"OT-{hashlib.md5(ocid.encode()).hexdigest()[:8]}"
    else:
        tender_id = f"OT-{hashlib.md5(ocid.encode()).hexdigest()[:8]}"

    # Map status to valid values
    raw_status = tender_data.get("status", "unknown")
    if raw_status in VALID_STATUSES:
        status = raw_status
    elif raw_status in STATUS_MAP:
        status = STATUS_MAP[raw_status]
    else:
        status = "completed"  # Default for historical data

    return {
        "tender_id": tender_id,
        "ocid": ocid,
        "title": tender_data.get("title", ""),
        "description": tender_data.get("description", ""),
        "procuring_entity": buyer.get("name"),
        "status": status,
        "cpv_code": cpv_code,
        "estimated_value_mkd": estimated_value_mkd,
        "publication_date": parse_date(publication_date),
        "closing_date": parse_date(deadline),  # Mapped to closing_date
        "winner": winner,
        "source_url": f"https://opentender.eu/mk/tender/{ocid}",
    }

def parse_date(date_str):
    """Parse ISO date string to datetime"""
    if not date_str:
        return None
    try:
        # Handle various ISO formats
        if "T" in date_str:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except:
        return None

async def import_to_database(tenders: list, batch_size: int = 500):
    """Bulk import tenders to PostgreSQL"""
    print(f"\nConnecting to database...")

    # Convert DATABASE_URL to asyncpg format
    db_url = DATABASE_URL.replace("postgresql://", "").replace("postgresql+asyncpg://", "")

    pool = await asyncpg.create_pool(
        f"postgresql://{db_url}",
        min_size=5,
        max_size=25,
        command_timeout=120,
    )

    print(f"Importing {len(tenders)} tenders in batches of {batch_size}...")

    imported = 0
    skipped = 0
    errors = 0

    async with pool.acquire() as conn:
        for i in range(0, len(tenders), batch_size):
            batch = tenders[i:i + batch_size]

            for tender in batch:
                try:
                    # Ensure title is never null
                    title = tender["title"]
                    if not title or not title.strip():
                        title = tender["procuring_entity"] or f"Tender {tender['tender_id']}"
                    title = title[:500]

                    # Use UPSERT to handle conflicts
                    await conn.execute("""
                        INSERT INTO tenders (
                            tender_id, title, description, procuring_entity,
                            status, cpv_code, estimated_value_mkd,
                            publication_date, closing_date, winner,
                            source_url, scraped_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        ON CONFLICT (tender_id) DO UPDATE SET
                            title = COALESCE(EXCLUDED.title, tenders.title),
                            procuring_entity = COALESCE(EXCLUDED.procuring_entity, tenders.procuring_entity),
                            estimated_value_mkd = COALESCE(EXCLUDED.estimated_value_mkd, tenders.estimated_value_mkd),
                            winner = COALESCE(EXCLUDED.winner, tenders.winner)
                    """,
                        tender["tender_id"],
                        title,
                        tender["description"][:2000] if tender["description"] else None,
                        tender["procuring_entity"],
                        tender["status"],
                        tender["cpv_code"],
                        tender["estimated_value_mkd"],
                        tender["publication_date"],
                        tender["closing_date"],
                        tender["winner"],
                        tender["source_url"],
                        datetime.now(),
                    )
                    imported += 1

                except asyncpg.UniqueViolationError:
                    skipped += 1
                except Exception as e:
                    errors += 1
                    if errors <= 10:
                        print(f"  Error: {e}")

            # Progress update
            total_processed = i + len(batch)
            percent = total_processed * 100 / len(tenders)
            print(f"\rProgress: {percent:.1f}% ({imported} imported, {skipped} skipped, {errors} errors)", end="", flush=True)

    await pool.close()

    print(f"\n\nImport complete!")
    print(f"  Imported: {imported}")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"  Errors: {errors}")

    return imported

async def main():
    parser = argparse.ArgumentParser(description="Import OpenTender OCDS dataset")
    parser.add_argument("--download-only", action="store_true", help="Only download, don't import")
    parser.add_argument("--import-only", action="store_true", help="Only import existing download")
    args = parser.parse_args()

    print("=" * 60)
    print("OpenTender OCDS Dataset Importer")
    print("Expected: ~260,901 historical tenders (2011-2024)")
    print("=" * 60)

    # Step 1: Download
    if not args.import_only:
        if not download_dataset():
            print("Download failed. Exiting.")
            sys.exit(1)

    if args.download_only:
        print("\nDownload complete. Run with --import-only to import.")
        return

    # Step 2: Parse dataset
    print(f"\nParsing dataset from {DATASET_FILE}...")

    if not DATASET_FILE.exists():
        print(f"ERROR: Dataset file not found: {DATASET_FILE}")
        print("Run without --import-only to download first.")
        sys.exit(1)

    tenders = []
    line_count = 0
    parse_errors = 0

    try:
        # JSONL format: one JSON object per line (gzip compressed)
        print("Reading JSONL file (one record per line)...")
        with gzip.open(DATASET_FILE, "rt", encoding="utf-8") as f:
            for line in f:
                line_count += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)

                    # Handle different OCDS formats per line
                    releases = []
                    if isinstance(record, list):
                        releases = record
                    elif "releases" in record:
                        releases = record["releases"]
                    elif "compiledRelease" in record:
                        releases = [record["compiledRelease"]]
                    elif "tender" in record or "buyer" in record:
                        # Direct release object
                        releases = [record]

                    for release in releases:
                        tender = parse_ocds_release(release)
                        if tender["title"] or tender["procuring_entity"]:
                            tenders.append(tender)

                except json.JSONDecodeError as e:
                    parse_errors += 1
                    if parse_errors <= 5:
                        print(f"  JSON parse error on line {line_count}: {e}")
                except Exception as e:
                    parse_errors += 1
                    if parse_errors <= 10:
                        print(f"  Parse error on line {line_count}: {e}")

                if line_count % 50000 == 0:
                    print(f"  Processed {line_count} lines, {len(tenders)} tenders parsed...")

    except Exception as e:
        print(f"ERROR reading file: {e}")
        sys.exit(1)

    print(f"\nProcessed {line_count} lines, {parse_errors} parse errors")

    print(f"\nParsed {len(tenders)} valid tenders")

    # Step 3: Import to database
    if tenders:
        await import_to_database(tenders)
    else:
        print("No tenders to import!")

if __name__ == "__main__":
    asyncio.run(main())

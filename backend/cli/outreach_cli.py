#!/usr/bin/env python3
"""
Outreach CLI Commands
Run with: python -m cli.outreach_cli <command> [options]

Commands:
  list-missing       List top suppliers missing email contacts
  enrich             Run email enrichment for suppliers
  preview            Preview email for a specific supplier
  campaign           Run outreach campaign
  export             Export contacts to CSV
  stats              Show outreach statistics
"""
import asyncio
import argparse
import csv
import sys
import os
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select

DATABASE_URL = os.getenv("DATABASE_URL", os.getenv("DATABASE_URL"))


async def get_db_session() -> AsyncSession:
    """Create async database session"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()


# ============================================================================
# LIST MISSING CONTACTS
# ============================================================================

async def list_missing(limit: int = 500):
    """List top suppliers without enriched email contacts"""
    db = await get_db_session()

    try:
        result = await db.execute(
            text("""
                SELECT s.supplier_id, s.company_name, s.tax_id, s.city,
                       s.total_wins, s.total_bids, s.win_rate,
                       s.total_contract_value_mkd
                FROM suppliers s
                LEFT JOIN supplier_contacts sc ON s.supplier_id = sc.supplier_id
                WHERE sc.id IS NULL
                ORDER BY s.total_wins DESC NULLS LAST
                LIMIT :limit
            """),
            {"limit": limit}
        )

        rows = result.fetchall()
        print(f"\n{'='*80}")
        print(f"TOP {len(rows)} SUPPLIERS MISSING EMAIL CONTACTS")
        print(f"{'='*80}\n")

        print(f"{'#':<4} {'Company Name':<40} {'City':<15} {'Wins':<6} {'Value (MKD)':<15}")
        print("-" * 80)

        for i, row in enumerate(rows, 1):
            value = f"{int(row.total_contract_value_mkd):,}" if row.total_contract_value_mkd else "N/A"
            print(f"{i:<4} {row.company_name[:38]:<40} {(row.city or 'N/A')[:13]:<15} {row.total_wins or 0:<6} {value:<15}")

        print(f"\nTotal: {len(rows)} suppliers")

    finally:
        await db.close()


# ============================================================================
# ENRICH SUPPLIERS
# ============================================================================

async def enrich(supplier_id: Optional[str] = None, limit: int = 100):
    """Run enrichment for suppliers"""
    db = await get_db_session()

    # Import here to avoid circular imports
    from services.enrichment import EnrichmentService, enrich_top_suppliers
    from models import Supplier

    try:
        if supplier_id:
            # Single supplier enrichment
            print(f"\nEnriching supplier: {supplier_id}")
            service = EnrichmentService(db)
            result = await service.enrich_supplier(supplier_id)
            await service.close()

            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Company: {result.get('company_name')}")
                print(f"Queries executed: {result.get('queries_executed')}")
                print(f"URLs crawled: {result.get('urls_crawled')}")
                print(f"Emails found: {result.get('emails_found')}")
        else:
            # Batch enrichment
            print(f"\nRunning batch enrichment for top {limit} suppliers...")
            stats = await enrich_top_suppliers(db, limit)

            print(f"\n{'='*50}")
            print("ENRICHMENT COMPLETE")
            print(f"{'='*50}")
            print(f"Total processed: {stats['processed']}")
            print(f"Emails found: {stats['emails_found']}")
            print(f"Errors: {stats['errors']}")

    finally:
        await db.close()


# ============================================================================
# PREVIEW EMAIL
# ============================================================================

async def preview(supplier_id: str, step: int = 0):
    """Preview email for a specific supplier"""
    db = await get_db_session()

    from services.outreach import OutreachService
    from models import Supplier

    try:
        # Get supplier
        result = await db.execute(
            select(Supplier).where(Supplier.supplier_id == supplier_id)
        )
        supplier = result.scalar_one_or_none()

        if not supplier:
            print(f"Error: Supplier not found: {supplier_id}")
            return

        service = OutreachService(db)

        # Get contact
        contact = await service.get_eligible_contact(supplier)
        email = contact.email if contact else "example@example.com"

        # Build personalization
        personalization = await service.build_personalization(supplier)

        # Get template
        template = await service.get_template(personalization["segment"], step)
        if not template:
            print(f"Error: No template found for segment '{personalization['segment']}' step {step}")
            await service.close()
            return

        # Render
        subject, html_body, text_body = service.render_template(template, personalization, email)

        await service.close()

        print(f"\n{'='*80}")
        print("EMAIL PREVIEW")
        print(f"{'='*80}")
        print(f"\nTo: {email}")
        print(f"Company: {supplier.company_name}")
        print(f"Segment: {personalization['segment']}")
        print(f"Sequence Step: {step}")
        print(f"\nSubject: {subject}")
        print(f"\n{'-'*40}")
        print("TEXT BODY:")
        print(f"{'-'*40}")
        print(text_body)
        print(f"\n{'-'*40}")
        print("PERSONALIZATION:")
        print(f"{'-'*40}")
        for key, value in personalization.items():
            print(f"  {key}: {value}")

    finally:
        await db.close()


# ============================================================================
# RUN CAMPAIGN
# ============================================================================

async def campaign(segment: Optional[str] = None, limit: int = 100, campaign_id: str = "default", dry_run: bool = True):
    """Run outreach campaign"""
    db = await get_db_session()

    from services.outreach import OutreachService

    try:
        service = OutreachService(db)

        print(f"\n{'='*60}")
        print(f"OUTREACH CAMPAIGN {'(DRY RUN)' if dry_run else '(LIVE)'}")
        print(f"{'='*60}")
        print(f"Segment: {segment or 'all'}")
        print(f"Limit: {limit}")
        print(f"Campaign ID: {campaign_id}")
        print()

        result = await service.run_campaign(
            segment=segment,
            limit=limit,
            campaign_id=campaign_id,
            dry_run=dry_run
        )

        await service.close()

        print(f"\nRESULTS:")
        print(f"  Total eligible: {result['total_eligible']}")
        print(f"  Sent: {result['sent']}")
        print(f"  Skipped (rate limit): {result['skipped_rate_limit']}")
        print(f"  Skipped (no contact): {result['skipped_no_contact']}")
        print(f"  Skipped (already contacted): {result['skipped_already_contacted']}")
        print(f"  Errors: {result['errors']}")

        if dry_run and result['messages']:
            print(f"\nPREVIEW OF MESSAGES:")
            for msg in result['messages'][:5]:
                print(f"\n  To: {msg['email']}")
                print(f"  Company: {msg['supplier_name']}")
                print(f"  Subject: {msg['subject']}")
                print(f"  Segment: {msg['segment']}")

    finally:
        await db.close()


# ============================================================================
# EXPORT CONTACTS
# ============================================================================

async def export(output_file: str = "contacts_export.csv", min_confidence: int = 50, limit: int = 1000):
    """Export supplier contacts to CSV"""
    db = await get_db_session()

    try:
        result = await db.execute(
            text("""
                SELECT
                    s.company_name,
                    sc.email,
                    sc.source_url,
                    sc.confidence_score,
                    sc.email_type,
                    sc.status,
                    s.total_wins as recent_awards_count,
                    s.city,
                    s.tax_id
                FROM supplier_contacts sc
                JOIN suppliers s ON sc.supplier_id = s.supplier_id
                WHERE sc.status IN ('new', 'verified')
                  AND sc.confidence_score >= :min_confidence
                ORDER BY s.total_wins DESC NULLS LAST, sc.confidence_score DESC
                LIMIT :limit
            """),
            {"min_confidence": min_confidence, "limit": limit}
        )

        rows = result.fetchall()

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'company_name', 'email', 'source_url', 'confidence_score',
                'email_type', 'status', 'recent_awards_count', 'city', 'tax_id'
            ])

            for row in rows:
                writer.writerow([
                    row.company_name,
                    row.email,
                    row.source_url,
                    row.confidence_score,
                    row.email_type,
                    row.status,
                    row.recent_awards_count,
                    row.city,
                    row.tax_id
                ])

        print(f"\nExported {len(rows)} contacts to {output_file}")

    finally:
        await db.close()


# ============================================================================
# SHOW STATS
# ============================================================================

async def stats():
    """Show outreach statistics"""
    db = await get_db_session()

    try:
        # Message stats
        msg_result = await db.execute(
            text("""
                SELECT status, COUNT(*) as count
                FROM outreach_messages
                GROUP BY status
                ORDER BY count DESC
            """)
        )

        # Contact stats
        contact_result = await db.execute(
            text("""
                SELECT status, email_type, COUNT(*) as count
                FROM supplier_contacts
                GROUP BY status, email_type
                ORDER BY count DESC
            """)
        )

        # Suppression stats
        supp_result = await db.execute(
            text("""
                SELECT reason, COUNT(*) as count
                FROM suppression_list
                GROUP BY reason
                ORDER BY count DESC
            """)
        )

        # Enrichment stats
        enrich_result = await db.execute(
            text("""
                SELECT status, COUNT(*) as jobs, SUM(emails_found) as emails
                FROM enrichment_jobs
                GROUP BY status
            """)
        )

        print(f"\n{'='*60}")
        print("OUTREACH STATISTICS")
        print(f"{'='*60}")

        print("\nMESSAGE STATUS:")
        for row in msg_result:
            print(f"  {row.status}: {row.count}")

        print("\nCONTACT STATUS:")
        for row in contact_result:
            print(f"  {row.status} ({row.email_type}): {row.count}")

        print("\nSUPPRESSION REASONS:")
        for row in supp_result:
            print(f"  {row.reason}: {row.count}")

        print("\nENRICHMENT JOBS:")
        for row in enrich_result:
            print(f"  {row.status}: {row.jobs} jobs, {row.emails or 0} emails found")

    finally:
        await db.close()


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Outreach CLI Commands")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list-missing
    list_parser = subparsers.add_parser("list-missing", help="List suppliers missing email contacts")
    list_parser.add_argument("--limit", type=int, default=500, help="Number of suppliers to list")

    # enrich
    enrich_parser = subparsers.add_parser("enrich", help="Run email enrichment")
    enrich_parser.add_argument("--supplier-id", type=str, help="Specific supplier ID to enrich")
    enrich_parser.add_argument("--limit", type=int, default=100, help="Number of suppliers to enrich")

    # preview
    preview_parser = subparsers.add_parser("preview", help="Preview email for a supplier")
    preview_parser.add_argument("supplier_id", type=str, help="Supplier ID")
    preview_parser.add_argument("--step", type=int, default=0, help="Sequence step (0, 1, 2)")

    # campaign
    campaign_parser = subparsers.add_parser("campaign", help="Run outreach campaign")
    campaign_parser.add_argument("--segment", type=str, help="Target segment (frequent_winner, occasional, new_unknown)")
    campaign_parser.add_argument("--limit", type=int, default=100, help="Maximum emails to send")
    campaign_parser.add_argument("--campaign-id", type=str, default="default", help="Campaign identifier")
    campaign_parser.add_argument("--live", action="store_true", help="Actually send emails (default is dry-run)")

    # export
    export_parser = subparsers.add_parser("export", help="Export contacts to CSV")
    export_parser.add_argument("--output", type=str, default="contacts_export.csv", help="Output file")
    export_parser.add_argument("--min-confidence", type=int, default=50, help="Minimum confidence score")
    export_parser.add_argument("--limit", type=int, default=1000, help="Maximum contacts to export")

    # stats
    subparsers.add_parser("stats", help="Show outreach statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "list-missing":
        asyncio.run(list_missing(args.limit))
    elif args.command == "enrich":
        asyncio.run(enrich(args.supplier_id, args.limit))
    elif args.command == "preview":
        asyncio.run(preview(args.supplier_id, args.step))
    elif args.command == "campaign":
        asyncio.run(campaign(args.segment, args.limit, args.campaign_id, not args.live))
    elif args.command == "export":
        asyncio.run(export(args.output, args.min_confidence, args.limit))
    elif args.command == "stats":
        asyncio.run(stats())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Corruption Flag Review Tool

Command-line interface for reviewing and validating corruption flags.
Allows reviewers to mark flags as valid, false positive, or skip for later.

Usage:
    python review_flags.py --limit 10
    python review_flags.py --flag-type single_bidder --severity high
    python review_flags.py --dry-run

Author: NabavkiData
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import asyncpg
from dotenv import load_dotenv
load_dotenv()


# Database configuration
DB_CONFIG = {
    'host': 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com',
    'user': 'nabavki_user',
    'password': os.getenv('DB_PASSWORD', ''),
    'database': 'nabavkidata',
    'port': 5432
}

logger = logging.getLogger(__name__)


@dataclass
class FlagContext:
    """Full context for a corruption flag."""
    # Flag info
    flag_id: str
    flag_type: str
    severity: str
    score: int
    evidence: Optional[Dict[str, Any]]
    description: Optional[str]
    detected_at: datetime

    # Tender info
    tender_id: str
    tender_title: Optional[str]
    buyer_name: Optional[str]
    estimated_value: Optional[float]
    estimated_currency: Optional[str]
    actual_value: Optional[float]
    winner: Optional[str]
    publication_date: Optional[datetime]
    deadline: Optional[datetime]
    status: Optional[str]

    # Bidder info (if available)
    bidder_count: int
    bidders: Optional[List[str]]


class FlagReviewer:
    """Async CLI tool for reviewing corruption flags."""

    def __init__(self, dry_run: bool = False):
        self.pool: Optional[asyncpg.Pool] = None
        self.dry_run = dry_run
        self.stats = {
            'reviewed': 0,
            'valid': 0,
            'false_positive': 0,
            'skipped': 0
        }

    async def connect(self):
        """Connect to the database."""
        self.pool = await asyncpg.create_pool(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            port=DB_CONFIG['port'],
            min_size=1,
            max_size=5,
            command_timeout=60
        )
        logger.info("Connected to database")

    async def disconnect(self):
        """Close database connection."""
        if self.pool:
            await self.pool.close()
            logger.info("Disconnected from database")

    async def get_pending_flags(
        self,
        limit: int = 10,
        flag_type: Optional[str] = None,
        severity: Optional[str] = None,
        min_score: Optional[int] = None
    ) -> List[FlagContext]:
        """
        Fetch unreviewed corruption flags with full context.

        Args:
            limit: Maximum number of flags to fetch
            flag_type: Filter by flag type
            severity: Filter by severity
            min_score: Minimum score threshold

        Returns:
            List of FlagContext objects
        """
        query = """
            SELECT
                cf.flag_id::text,
                cf.flag_type,
                cf.severity,
                cf.score,
                cf.evidence,
                cf.description,
                cf.detected_at,
                t.tender_id,
                t.title as tender_title,
                t.procuring_entity as buyer_name,
                t.estimated_value_mkd as estimated_value,
                'MKD' as estimated_currency,
                t.actual_value_mkd as actual_value,
                t.winner,
                t.publication_date,
                t.closing_date as deadline,
                t.status,
                COALESCE(t.num_bidders, 0) as bidder_count,
                t.all_bidders_json as bidders
            FROM corruption_flags cf
            JOIN tenders t ON cf.tender_id = t.tender_id
            WHERE cf.reviewed = FALSE
              AND cf.false_positive = FALSE
        """

        params = []
        param_idx = 1

        if flag_type:
            query += f" AND cf.flag_type = ${param_idx}"
            params.append(flag_type)
            param_idx += 1

        if severity:
            query += f" AND cf.severity = ${param_idx}"
            params.append(severity)
            param_idx += 1

        if min_score is not None:
            query += f" AND cf.score >= ${param_idx}"
            params.append(min_score)
            param_idx += 1

        query += " ORDER BY cf.score DESC, cf.detected_at DESC"
        query += f" LIMIT ${param_idx}"
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        flags = []
        for row in rows:
            # Parse evidence JSON if it's a string
            evidence = row['evidence']
            if isinstance(evidence, str):
                try:
                    evidence = json.loads(evidence)
                except json.JSONDecodeError:
                    evidence = None

            # Parse bidders if available
            bidders = row['bidders']
            if isinstance(bidders, str):
                try:
                    bidders = json.loads(bidders)
                except json.JSONDecodeError:
                    bidders = None

            flag = FlagContext(
                flag_id=row['flag_id'],
                flag_type=row['flag_type'],
                severity=row['severity'],
                score=row['score'],
                evidence=evidence,
                description=row['description'],
                detected_at=row['detected_at'],
                tender_id=row['tender_id'],
                tender_title=row['tender_title'],
                buyer_name=row['buyer_name'],
                estimated_value=row['estimated_value'],
                estimated_currency=row['estimated_currency'],
                actual_value=row['actual_value'],
                winner=row['winner'],
                publication_date=row['publication_date'],
                deadline=row['deadline'],
                status=row['status'],
                bidder_count=row['bidder_count'],
                bidders=bidders if isinstance(bidders, list) else None
            )
            flags.append(flag)

        return flags

    async def update_flag(
        self,
        flag_id: str,
        is_valid: bool,
        notes: Optional[str] = None,
        reviewed_by: Optional[str] = None
    ):
        """
        Update a flag's review status.

        Args:
            flag_id: UUID of the flag
            is_valid: True if confirmed suspicious, False if false positive
            notes: Optional review notes
            reviewed_by: Optional reviewer identifier
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update flag {flag_id}: valid={is_valid}, notes={notes}")
            return

        query = """
            UPDATE corruption_flags
            SET reviewed = TRUE,
                false_positive = $2,
                review_notes = $3,
                reviewed_by = $4
            WHERE flag_id = $1::uuid
        """

        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                flag_id,
                not is_valid,  # false_positive is the opposite of is_valid
                notes,
                None  # reviewed_by is UUID, keeping NULL for now
            )

        logger.debug(f"Updated flag {flag_id}")

    def format_flag(self, flag: FlagContext, index: int, total: int) -> str:
        """Format a flag for display."""
        lines = []

        # Header
        lines.append("\n" + "=" * 80)
        lines.append(f"FLAG {index}/{total}")
        lines.append("=" * 80)

        # Flag details
        lines.append(f"\nFLAG TYPE:    {flag.flag_type}")
        lines.append(f"SEVERITY:     {flag.severity.upper()}")
        lines.append(f"SCORE:        {flag.score}/100")
        lines.append(f"DETECTED:     {flag.detected_at.strftime('%Y-%m-%d %H:%M') if flag.detected_at else 'N/A'}")

        if flag.description:
            lines.append(f"\nDESCRIPTION:")
            lines.append(f"  {flag.description}")

        # Tender details
        lines.append("\n" + "-" * 40)
        lines.append("TENDER DETAILS")
        lines.append("-" * 40)
        lines.append(f"TENDER ID:    {flag.tender_id}")

        if flag.tender_title:
            # Wrap long titles
            title = flag.tender_title
            if len(title) > 70:
                title = title[:67] + "..."
            lines.append(f"TITLE:        {title}")

        if flag.buyer_name:
            lines.append(f"BUYER:        {flag.buyer_name}")

        if flag.winner:
            lines.append(f"WINNER:       {flag.winner}")

        if flag.estimated_value:
            currency = flag.estimated_currency or "MKD"
            lines.append(f"EST. VALUE:   {flag.estimated_value:,.2f} {currency}")

        if flag.actual_value:
            lines.append(f"ACTUAL VALUE: {flag.actual_value:,.2f}")

        if flag.publication_date:
            lines.append(f"PUBLISHED:    {flag.publication_date.strftime('%Y-%m-%d')}")

        if flag.status:
            lines.append(f"STATUS:       {flag.status}")

        # Bidder info
        lines.append(f"BIDDER COUNT: {flag.bidder_count}")

        if flag.bidders and len(flag.bidders) > 0:
            lines.append("BIDDERS:")
            for i, bidder in enumerate(flag.bidders[:5], 1):
                if isinstance(bidder, dict):
                    name = bidder.get('name', 'Unknown')
                else:
                    name = str(bidder)
                lines.append(f"  {i}. {name}")
            if len(flag.bidders) > 5:
                lines.append(f"  ... and {len(flag.bidders) - 5} more")

        # Evidence
        if flag.evidence:
            lines.append("\n" + "-" * 40)
            lines.append("EVIDENCE")
            lines.append("-" * 40)

            if isinstance(flag.evidence, dict):
                for key, value in flag.evidence.items():
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value, ensure_ascii=False, indent=2)
                    lines.append(f"  {key}: {value}")
            else:
                lines.append(f"  {flag.evidence}")

        # Actions
        lines.append("\n" + "-" * 40)
        lines.append("ACTIONS: [v]alid  [f]alse positive  [s]kip  [q]uit")
        lines.append("-" * 40)

        return "\n".join(lines)

    def get_input(self, prompt: str = "> ") -> str:
        """Get user input with prompt."""
        try:
            return input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 'q'

    async def review_session(
        self,
        limit: int = 10,
        flag_type: Optional[str] = None,
        severity: Optional[str] = None,
        min_score: Optional[int] = None
    ):
        """
        Run an interactive review session.

        Args:
            limit: Maximum flags to review
            flag_type: Filter by flag type
            severity: Filter by severity
            min_score: Minimum score threshold
        """
        print("\n" + "=" * 80)
        print("CORRUPTION FLAG REVIEW SESSION")
        print("=" * 80)

        if self.dry_run:
            print("*** DRY RUN MODE - No changes will be saved ***")

        print(f"\nFetching up to {limit} unreviewed flags...")

        flags = await self.get_pending_flags(
            limit=limit,
            flag_type=flag_type,
            severity=severity,
            min_score=min_score
        )

        if not flags:
            print("\nNo pending flags to review matching your criteria.")
            return

        print(f"Found {len(flags)} flags to review.\n")

        for i, flag in enumerate(flags, 1):
            # Display flag
            print(self.format_flag(flag, i, len(flags)))

            # Get user action
            while True:
                action = self.get_input()

                if action == 'v':
                    # Valid (confirmed suspicious)
                    notes = input("Add notes (optional, press Enter to skip): ").strip()
                    await self.update_flag(flag.flag_id, is_valid=True, notes=notes or None)
                    self.stats['valid'] += 1
                    self.stats['reviewed'] += 1
                    print("-> Marked as VALID (confirmed suspicious)")
                    break

                elif action == 'f':
                    # False positive
                    notes = input("Reason for false positive (optional): ").strip()
                    await self.update_flag(flag.flag_id, is_valid=False, notes=notes or None)
                    self.stats['false_positive'] += 1
                    self.stats['reviewed'] += 1
                    print("-> Marked as FALSE POSITIVE")
                    break

                elif action == 's':
                    # Skip
                    self.stats['skipped'] += 1
                    print("-> Skipped")
                    break

                elif action == 'q':
                    # Quit
                    print("\nQuitting review session...")
                    self._print_summary()
                    return

                else:
                    print("Invalid action. Use: [v]alid, [f]alse positive, [s]kip, [q]uit")

        self._print_summary()

    def _print_summary(self):
        """Print session summary."""
        print("\n" + "=" * 80)
        print("REVIEW SESSION SUMMARY")
        print("=" * 80)
        print(f"Total reviewed:    {self.stats['reviewed']}")
        print(f"Marked valid:      {self.stats['valid']}")
        print(f"False positives:   {self.stats['false_positive']}")
        print(f"Skipped:           {self.stats['skipped']}")
        print("=" * 80)


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Review and validate corruption flags",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python review_flags.py --limit 10
  python review_flags.py --flag-type single_bidder --severity high
  python review_flags.py --min-score 70 --limit 20
  python review_flags.py --dry-run
        """
    )

    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=10,
        help='Maximum number of flags to review (default: 10)'
    )

    parser.add_argument(
        '--flag-type', '-t',
        type=str,
        choices=[
            'single_bidder', 'repeat_winner', 'price_anomaly',
            'bid_clustering', 'short_deadline', 'high_amendments',
            'spec_rigging', 'related_companies'
        ],
        help='Filter by flag type'
    )

    parser.add_argument(
        '--severity', '-s',
        type=str,
        choices=['low', 'medium', 'high', 'critical'],
        help='Filter by severity level'
    )

    parser.add_argument(
        '--min-score',
        type=int,
        help='Minimum score threshold (0-100)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview mode - do not save changes'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--test-connection',
        action='store_true',
        help='Test database connection and show flag count, then exit'
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Initialize reviewer
    reviewer = FlagReviewer(dry_run=args.dry_run)

    try:
        await reviewer.connect()

        if args.test_connection:
            # Just test connection and show stats
            print("\nDatabase connection successful!")

            async with reviewer.pool.acquire() as conn:
                # Count flags
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM corruption_flags"
                )
                pending = await conn.fetchval(
                    "SELECT COUNT(*) FROM corruption_flags WHERE reviewed = FALSE"
                )
                reviewed = await conn.fetchval(
                    "SELECT COUNT(*) FROM corruption_flags WHERE reviewed = TRUE"
                )
                false_pos = await conn.fetchval(
                    "SELECT COUNT(*) FROM corruption_flags WHERE false_positive = TRUE"
                )

                # Count by type
                by_type = await conn.fetch("""
                    SELECT flag_type, COUNT(*) as count
                    FROM corruption_flags
                    WHERE reviewed = FALSE
                    GROUP BY flag_type
                    ORDER BY count DESC
                """)

                # Count by severity
                by_severity = await conn.fetch("""
                    SELECT severity, COUNT(*) as count
                    FROM corruption_flags
                    WHERE reviewed = FALSE
                    GROUP BY severity
                    ORDER BY
                        CASE severity
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END
                """)

            print("\n" + "=" * 50)
            print("CORRUPTION FLAGS SUMMARY")
            print("=" * 50)
            print(f"Total flags:       {total}")
            print(f"Pending review:    {pending}")
            print(f"Already reviewed:  {reviewed}")
            print(f"False positives:   {false_pos}")

            if by_type:
                print("\nPending by Type:")
                for row in by_type:
                    print(f"  {row['flag_type']}: {row['count']}")

            if by_severity:
                print("\nPending by Severity:")
                for row in by_severity:
                    print(f"  {row['severity']}: {row['count']}")

            print("=" * 50)
            return

        # Run review session
        await reviewer.review_session(
            limit=args.limit,
            flag_type=args.flag_type,
            severity=args.severity,
            min_score=args.min_score
        )

    except asyncpg.PostgresError as e:
        print(f"\nDatabase error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        logger.exception("Unexpected error")
        sys.exit(1)
    finally:
        await reviewer.disconnect()


if __name__ == '__main__':
    asyncio.run(main())

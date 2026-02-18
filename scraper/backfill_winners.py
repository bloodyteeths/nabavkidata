#!/usr/bin/env python3
"""
Backfill missing winner data for awarded/completed tenders.

Queries the database for tenders with e-nabavki source URLs but no winner,
re-visits each page with Playwright, and extracts winner + bidder data
using the same XPath selectors as the main spider.

Usage:
    python3 backfill_winners.py --limit 500 --batch-size 20
    python3 backfill_winners.py --dry-run  # just show what would be scraped
"""
import asyncio
import asyncpg
import json
import logging
import os
import re
import sys
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# XPath selectors — same as nabavki_spider.py
# ---------------------------------------------------------------------------
WINNER_XPATHS = [
    '//label[@label-for="NAME OF CONTACT OF PROCUREMENT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[@label-for="WINNER NAME DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[@label-for="SELECTED BIDDER DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[@label-for="NAME OF CONTACT OF PROCUREMENT DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[@label-for="WINNER NAME DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[@label-for="SELECTED BIDDER DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(text(), "Избран понудувач")]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(text(), "Назив на носителот")]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(text(), "Договорна страна")]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(text(), "Име на понудувач")]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(@label-for, "WINNER")]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(@label-for, "SELECTED BIDDER")]/following-sibling::label[contains(@class, "dosie-value")][1]',
]

ACTUAL_VALUE_XPATHS = [
    '//label[@label-for="ASSIGNED CONTRACT VALUE WITHOUT VAT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[@label-for="ASSIGNED CONTRACT VALUE WITHOUT VAT DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[@label-for="ASSIGNED CONTRACT VALUE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[@label-for="ASSIGNED CONTRACT VALUE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(text(), "Вредност на доделениот договор без ДДВ")]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(text(), "Вредност на договорот")]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(@label-for, "ASSIGNED CONTRACT VALUE")]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(@label-for, "CONTRACT VALUE")]/following-sibling::label[contains(@class, "dosie-value")][1]',
]

NUM_BIDDERS_XPATHS = [
    '//label[@label-for="NUMBER OF OFFERS DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[@label-for="NUMBER OF OFFERS DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[@label-for="NUMBER OF BIDS DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[@label-for="NUMBER OF BIDS DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(text(), "Број на примени понуди")]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(@label-for, "NUMBER OF OFFERS")]/following-sibling::label[contains(@class, "dosie-value")][1]',
    '//label[contains(@label-for, "NUMBER OF BIDS")]/following-sibling::label[contains(@class, "dosie-value")][1]',
]

BIDDER_TABLE_SELECTORS = [
    'table:has(th:text-matches("Понудувач|Учесник|Економски оператор|Bidder|Participant", "i"))',
]

WINNER_INDICATORS = ['победник', 'добитник', 'избран', 'winner', 'selected']


async def get_db_pool():
    """Create asyncpg connection pool."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    dsn = db_url.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.create_pool(dsn, min_size=2, max_size=5, command_timeout=30)


async def get_tenders_missing_winners(pool, limit: int = 500, offset: int = 0) -> List[Dict]:
    """Get tenders that have e-nabavki source_urls but are missing winner.
    Only includes dossie-acpp URLs (awarded contracts) — these have winner data.
    Excludes dossie-realized-contract (different page structure, often times out)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT tender_id, source_url, status, num_bidders, actual_value_mkd
            FROM tenders
            WHERE winner IS NULL
              AND status IN ('awarded', 'completed')
              AND source_url LIKE '%e-nabavki.gov.mk%dossie-acpp%'
            ORDER BY tender_id
            LIMIT $1 OFFSET $2
        """, limit, offset)
        return [dict(r) for r in rows]


async def extract_from_page(page, tender_id: str) -> Dict[str, Any]:
    """Extract winner, actual_value, num_bidders, and bidders from a loaded page."""
    result = {
        'winner': None,
        'actual_value_mkd': None,
        'num_bidders': None,
        'bidders': [],
    }

    # Extract winner via XPath
    for xpath in WINNER_XPATHS:
        try:
            elem = await page.query_selector(f'xpath={xpath}')
            if elem:
                text = (await elem.text_content() or "").strip()
                if text and len(text) > 1 and text.lower() not in ('/', '-', 'n/a', 'не', 'no'):
                    result['winner'] = text
                    break
        except Exception:
            continue

    # Extract actual_value_mkd
    for xpath in ACTUAL_VALUE_XPATHS:
        try:
            elem = await page.query_selector(f'xpath={xpath}')
            if elem:
                text = (await elem.text_content() or "").strip()
                if text:
                    cleaned = re.sub(r'[^\d.,]', '', text.replace(',', ''))
                    if cleaned:
                        try:
                            result['actual_value_mkd'] = float(cleaned)
                            break
                        except ValueError:
                            continue
        except Exception:
            continue

    # Extract num_bidders
    for xpath in NUM_BIDDERS_XPATHS:
        try:
            elem = await page.query_selector(f'xpath={xpath}')
            if elem:
                text = (await elem.text_content() or "").strip()
                if text:
                    try:
                        result['num_bidders'] = int(re.sub(r'[^\d]', '', text))
                        break
                    except ValueError:
                        continue
        except Exception:
            continue

    # Extract bidders from table
    try:
        rows = await page.query_selector_all('table tr')
        if rows and len(rows) > 1:
            # Check if this looks like a bidder table
            header_row = rows[0]
            header_text = (await header_row.text_content() or "").lower()
            bidder_keywords = ['понудувач', 'учесник', 'економски оператор', 'bidder', 'participant']
            if any(kw in header_text for kw in bidder_keywords):
                for idx, row in enumerate(rows[1:], start=1):
                    cells = await row.query_selector_all('td')
                    if cells:
                        company_name = (await cells[0].text_content() or "").strip()
                        if not company_name or len(company_name) < 2:
                            continue

                        bid_amount = None
                        if len(cells) > 1:
                            amt_text = (await cells[1].text_content() or "").strip()
                            cleaned = re.sub(r'[^\d.,]', '', amt_text.replace(',', ''))
                            if cleaned:
                                try:
                                    bid_amount = float(cleaned)
                                except ValueError:
                                    pass

                        row_html = (await row.inner_html() or "").lower()
                        is_winner = any(ind in row_html for ind in WINNER_INDICATORS)

                        result['bidders'].append({
                            'company_name': company_name,
                            'bid_amount_mkd': bid_amount,
                            'is_winner': is_winner,
                            'rank': idx,
                            'disqualified': False,
                        })

        # If no winner from labels, try from bidder table
        if not result['winner'] and result['bidders']:
            for b in result['bidders']:
                if b['is_winner']:
                    result['winner'] = b['company_name']
                    break
            # If still no winner and single bidder, that's the winner
            if not result['winner'] and len(result['bidders']) == 1:
                result['winner'] = result['bidders'][0]['company_name']
                result['bidders'][0]['is_winner'] = True

        # Update num_bidders from extracted bidders if not found from label
        if not result['num_bidders'] and result['bidders']:
            result['num_bidders'] = len(result['bidders'])

    except Exception as e:
        logger.warning(f"Bidder extraction error for {tender_id}: {e}")

    return result


async def update_tender(pool, tender_id: str, data: Dict[str, Any]):
    """Update tender with extracted data."""
    updates = []
    params = []
    param_idx = 1

    if data['winner']:
        updates.append(f"winner = ${param_idx}")
        params.append(data['winner'])
        param_idx += 1

    if data['actual_value_mkd'] is not None:
        updates.append(f"actual_value_mkd = COALESCE(actual_value_mkd, ${param_idx})")
        params.append(data['actual_value_mkd'])
        param_idx += 1

    if data['num_bidders'] is not None:
        updates.append(f"num_bidders = COALESCE(num_bidders, ${param_idx})")
        params.append(data['num_bidders'])
        param_idx += 1

    if not updates:
        return False

    params.append(tender_id)
    sql = f"UPDATE tenders SET {', '.join(updates)} WHERE tender_id = ${param_idx} AND winner IS NULL"

    async with pool.acquire() as conn:
        result = await conn.execute(sql, *params)

        # Also update/insert bidders if we got any
        if data['bidders']:
            for bidder in data['bidders']:
                await conn.execute("""
                    INSERT INTO tender_bidders (
                        tender_id, company_name, bid_amount_mkd, is_winner, rank, disqualified
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (tender_id, company_name) DO UPDATE SET
                        bid_amount_mkd = COALESCE(EXCLUDED.bid_amount_mkd, tender_bidders.bid_amount_mkd),
                        is_winner = COALESCE(EXCLUDED.is_winner, tender_bidders.is_winner),
                        rank = COALESCE(EXCLUDED.rank, tender_bidders.rank)
                """,
                    tender_id,
                    bidder['company_name'],
                    bidder.get('bid_amount_mkd'),
                    bidder.get('is_winner', False),
                    bidder.get('rank'),
                    bidder.get('disqualified', False),
                )

    return 'UPDATE 1' in result


async def process_batch(browser, pool, tenders: List[Dict], stats: Dict):
    """Process a batch of tenders using a single browser context."""
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 800},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    )

    for tender in tenders:
        tender_id = tender['tender_id']
        url = tender['source_url']
        stats['attempted'] += 1

        try:
            page = await context.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)

            # Wait for Angular to render
            try:
                await page.wait_for_selector('label.dosie-value', timeout=20000)
                await page.wait_for_timeout(500)
            except Exception:
                logger.warning(f"  ⏳ Timeout waiting for content: {tender_id}")
                stats['timeout'] += 1
                await page.close()
                continue

            data = await extract_from_page(page, tender_id)
            await page.close()

            if data['winner']:
                updated = await update_tender(pool, tender_id, data)
                if updated:
                    stats['updated'] += 1
                    bidder_info = f", {len(data['bidders'])} bidders" if data['bidders'] else ""
                    value_info = f", value={data['actual_value_mkd']}" if data['actual_value_mkd'] else ""
                    logger.info(f"  ✅ {tender_id}: winner={data['winner']}{value_info}{bidder_info}")
                else:
                    stats['already_filled'] += 1
                    logger.debug(f"  ⏭️ {tender_id}: already has winner (race condition)")
            else:
                stats['no_winner_found'] += 1
                logger.debug(f"  ❌ {tender_id}: no winner found on page")

        except Exception as e:
            stats['errors'] += 1
            logger.error(f"  ❌ {tender_id}: {e}")
            try:
                await page.close()
            except Exception:
                pass

    await context.close()


async def main():
    parser = argparse.ArgumentParser(description='Backfill missing winner data')
    parser.add_argument('--limit', type=int, default=500, help='Max tenders to process')
    parser.add_argument('--batch-size', type=int, default=20, help='Tenders per browser context')
    parser.add_argument('--offset', type=int, default=0, help='Skip first N tenders')
    parser.add_argument('--dry-run', action='store_true', help='Just count, do not scrape')
    parser.add_argument('--concurrency', type=int, default=3, help='Concurrent browser pages')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("WINNER BACKFILL — Re-scraping e-nabavki pages")
    logger.info("=" * 60)

    pool = await get_db_pool()

    # Get count of missing winners
    async with pool.acquire() as conn:
        total_missing = await conn.fetchval("""
            SELECT COUNT(*) FROM tenders
            WHERE winner IS NULL
              AND status IN ('awarded', 'completed')
              AND source_url LIKE '%e-nabavki.gov.mk%dossie-acpp%'
        """)
    logger.info(f"Total tenders with e-nabavki URLs missing winner: {total_missing:,}")

    if args.dry_run:
        logger.info("DRY RUN — not scraping")
        await pool.close()
        return

    tenders = await get_tenders_missing_winners(pool, limit=args.limit, offset=args.offset)
    logger.info(f"Fetched {len(tenders)} tenders to process (limit={args.limit}, offset={args.offset})")

    if not tenders:
        logger.info("No tenders to process")
        await pool.close()
        return

    # Launch Playwright
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        logger.info("Browser launched")

        stats = {
            'attempted': 0,
            'updated': 0,
            'no_winner_found': 0,
            'timeout': 0,
            'errors': 0,
            'already_filled': 0,
        }

        # Process in batches
        for i in range(0, len(tenders), args.batch_size):
            batch = tenders[i:i + args.batch_size]
            batch_num = (i // args.batch_size) + 1
            total_batches = (len(tenders) + args.batch_size - 1) // args.batch_size
            logger.info(f"\nBatch {batch_num}/{total_batches} ({len(batch)} tenders)")

            await process_batch(browser, pool, batch, stats)

            # Progress report
            pct = round(100.0 * stats['attempted'] / len(tenders), 1)
            logger.info(
                f"Progress: {stats['attempted']}/{len(tenders)} ({pct}%) | "
                f"✅ {stats['updated']} updated | "
                f"❌ {stats['no_winner_found']} no winner | "
                f"⏳ {stats['timeout']} timeout | "
                f"💥 {stats['errors']} errors"
            )

        await browser.close()

    logger.info("\n" + "=" * 60)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 60)
    logger.info(f"  Attempted:      {stats['attempted']}")
    logger.info(f"  Winners found:  {stats['updated']}")
    logger.info(f"  No winner:      {stats['no_winner_found']}")
    logger.info(f"  Timeouts:       {stats['timeout']}")
    logger.info(f"  Errors:         {stats['errors']}")
    logger.info(f"  Already filled: {stats['already_filled']}")
    if stats['attempted'] > 0:
        success_rate = round(100.0 * stats['updated'] / stats['attempted'], 1)
        logger.info(f"  Success rate:   {success_rate}%")

    await pool.close()


if __name__ == '__main__':
    asyncio.run(main())

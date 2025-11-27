"""
Contracts Spider - Scrapes awarded contracts from e-nabavki.gov.mk
Extracts winner/bidder data from the contracts list table (#/contracts/0)

This spider is separate from nabavki_spider.py and focuses on:
- Awarded contracts with winner company names
- Contract values (estimated and actual)
- Contract dates

Table structure on contracts page (12 columns):
- Column 0: Број на оглас (Tender number) - links to dossie-acpp
- Column 1: Договорен орган (Contracting authority)
- Column 2: Предмет на договорот (Contract subject)
- Column 3: Вид на договор (Contract type: Стоки/Услуги/Работи)
- Column 4: Вид на постапка (Procedure type)
- Column 5: Датум на договор (Contract date)
- Column 6: Носител на набавката (Winner/Procurement holder) ***
- Column 7: Проценета вредност со ДДВ (Estimated value with VAT)
- Column 8: Вредност на договорот со ДДВ (Contract value with VAT)
- Column 9: Датум на објава (Publication date)
- Column 10: Вистински сопственици (Beneficial owners) - "Прикажи" button
- Column 11: Документи (Documents) - "Прикажи" button
"""

import scrapy
import json
import re
import logging
from datetime import datetime
from typing import Optional, Dict, List, Union
from scrapy_playwright.page import PageMethod
from scraper.items import TenderItem

logger = logging.getLogger(__name__)


class ContractsSpider(scrapy.Spider):
    name = 'contracts'
    allowed_domains = ['e-nabavki.gov.mk']

    # Start URL - contracts list page
    start_urls = ['https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0']

    custom_settings = {
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
        },
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 120000,
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
            'https': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
        },
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
        'CONCURRENT_REQUESTS': 1,  # Sequential to handle pagination properly
        'DOWNLOAD_DELAY': 1,
    }

    def __init__(self, max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages) if max_pages else 15000  # 109K records / 10 per page
        self.contracts_scraped = 0
        self.bidders_extracted = 0

    def start_requests(self):
        """Start with the contracts list page"""
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse_contracts_list,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'networkidle',
                        'timeout': 120000,
                    },
                },
                errback=self.errback_playwright,
                dont_filter=True,
            )

    async def parse_contracts_list(self, response):
        """
        Parse the contracts list table and extract winner data from each row.
        Handles pagination to scrape all 109K+ contracts.
        """
        page = response.meta.get('playwright_page')

        if not page:
            logger.error("No Playwright page available")
            return

        try:
            # Wait for contracts table to load
            await page.wait_for_selector('table#contracts-grid tbody tr', timeout=60000)
            await page.wait_for_timeout(3000)  # Extra wait for data binding
            logger.info("✓ Contracts table loaded successfully")

            current_page = 1
            consecutive_empty = 0

            consecutive_errors = 0
            while current_page <= self.max_pages:
                try:
                    # Extract data from current page's table rows
                    rows = await page.query_selector_all('table#contracts-grid tbody tr')

                    if not rows:
                        consecutive_empty += 1
                        if consecutive_empty >= 3:
                            logger.warning("No rows found for 3 consecutive pages, stopping")
                            break
                        await page.wait_for_timeout(2000)
                        continue
                    else:
                        consecutive_empty = 0
                        consecutive_errors = 0  # Reset error counter on success

                    logger.info(f"Page {current_page}: Processing {len(rows)} contract rows")

                    for row in rows:
                        try:
                            contract_data = await self._extract_row_data(row)
                            if contract_data:
                                self.contracts_scraped += 1
                                yield contract_data
                        except Exception as e:
                            logger.warning(f"Error extracting row: {e}")
                            continue

                    # Progress logging every 50 pages
                    if current_page % 50 == 0:
                        logger.warning(f"Progress: Page {current_page}, Contracts: {self.contracts_scraped}, Bidders: {self.bidders_extracted}")

                    # Try to go to next page
                    has_next = await self._click_next_page(page)
                    if not has_next:
                        logger.info("No more pages available")
                        break

                    current_page += 1

                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Error on page {current_page} (attempt {consecutive_errors}): {e}")
                    if consecutive_errors >= 5:
                        logger.error("Too many consecutive errors, stopping")
                        break
                    # Wait and try to recover
                    await page.wait_for_timeout(5000)
                    continue

            logger.warning(f"✓ Scraping complete: {self.contracts_scraped} contracts, {self.bidders_extracted} bidders")

        except Exception as e:
            logger.error(f"Error parsing contracts list: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                await page.close()
            except:
                pass

    async def _extract_row_data(self, row) -> Optional[Dict]:
        """
        Extract contract and winner data from a table row.

        Table columns (12 total):
        0: Tender number (with link)
        1: Contracting authority
        2: Contract subject
        3: Contract type
        4: Procedure type
        5: Contract date
        6: Winner company name ***
        7: Estimated value
        8: Contract value
        9: Publication date
        10: Beneficial owners (button)
        11: Documents (button)
        """
        cells = await row.query_selector_all('td')

        # Log cell count for debugging
        if len(cells) < 10:
            logger.warning(f"Row has only {len(cells)} cells, skipping")
            return None

        try:
            # Extract tender link and number
            tender_link_elem = await cells[0].query_selector('a')
            tender_link = await tender_link_elem.get_attribute('href') if tender_link_elem else None
            tender_number_text = await cells[0].inner_text()
            tender_number = tender_number_text.strip()

            # Extract tender ID from link (UUID format) or use tender number
            tender_id = None
            if tender_link:
                uuid_match = re.search(r'dossie-acpp/([a-f0-9-]{36})', tender_link)
                if uuid_match:
                    tender_id = uuid_match.group(1)

            # Fallback: use tender number as ID
            if not tender_id:
                tender_id = tender_number.replace('/', '_')

            # Extract other fields - use safe extraction
            contracting_authority = (await cells[1].inner_text()).strip() if len(cells) > 1 else ''
            contract_subject = (await cells[2].inner_text()).strip() if len(cells) > 2 else ''
            contract_type = (await cells[3].inner_text()).strip() if len(cells) > 3 else ''
            procedure_type = (await cells[4].inner_text()).strip() if len(cells) > 4 else ''
            contract_date = (await cells[5].inner_text()).strip() if len(cells) > 5 else ''
            winner_name = (await cells[6].inner_text()).strip() if len(cells) > 6 else ''  # *** WINNER ***
            estimated_value_text = (await cells[7].inner_text()).strip() if len(cells) > 7 else ''
            contract_value_text = (await cells[8].inner_text()).strip() if len(cells) > 8 else ''
            publication_date = (await cells[9].inner_text()).strip() if len(cells) > 9 else ''

            # Debug log first extraction
            if self.contracts_scraped == 0:
                logger.info(f"First row extracted: tender={tender_number}, winner={winner_name[:30]}...")

            # Parse currency values
            estimated_value = self._parse_currency(estimated_value_text)
            contract_value = self._parse_currency(contract_value_text)

            # Parse dates
            contract_date_parsed = self._parse_date(contract_date)
            publication_date_parsed = self._parse_date(publication_date)

            if winner_name:
                self.bidders_extracted += 1

            # Create bidder data for the winner
            bidders_data = None
            if winner_name:
                bidders_data = json.dumps([{
                    'company_name': winner_name,
                    'bid_amount_mkd': contract_value,
                    'is_winner': True,
                    'rank': 1,
                    'disqualified': False
                }], ensure_ascii=False)

            # Return a TenderItem for proper database pipeline handling
            item = TenderItem()
            item['tender_id'] = tender_id
            item['title'] = contract_subject
            item['procuring_entity'] = contracting_authority
            item['category'] = contract_type  # Стоки/Услуги/Работи
            item['procedure_type'] = procedure_type
            item['contract_signing_date'] = contract_date_parsed
            item['publication_date'] = publication_date_parsed
            item['estimated_value_mkd'] = estimated_value
            item['actual_value_mkd'] = contract_value
            item['winner'] = winner_name
            item['bidders_data'] = bidders_data
            item['status'] = 'awarded'
            item['source_category'] = 'awarded'  # Use 'awarded' to match UI filter
            item['source_url'] = tender_link
            item['scraped_at'] = datetime.now().isoformat()
            return item

        except Exception as e:
            logger.warning(f"Error extracting row data: {e}")
            return None

    def _parse_currency(self, value_text: str) -> Optional[float]:
        """Parse Macedonian currency format: 1.234.567,89ден."""
        if not value_text:
            return None

        try:
            # Remove "ден." suffix and whitespace
            cleaned = value_text.replace('ден.', '').replace('ден', '').strip()

            # Handle Macedonian format: 1.234.567,89
            # Remove thousand separators (.) and replace decimal comma with dot
            cleaned = cleaned.replace('.', '').replace(',', '.')

            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    def _parse_date(self, date_text: str) -> Optional[str]:
        """Parse date in DD.MM.YYYY format to ISO format"""
        if not date_text:
            return None

        try:
            # Format: 20.11.2025
            dt = datetime.strptime(date_text.strip(), '%d.%m.%Y')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            return None

    async def _click_next_page(self, page) -> bool:
        """Click the Next button in pagination, return False if no more pages"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Look for the Next button that's not disabled
                next_btn = await page.query_selector('li.next:not(.disabled) a')

                if not next_btn:
                    return False

                await next_btn.click()
                await page.wait_for_timeout(3000)  # Wait for page to load

                # Wait for table to update with longer timeout
                await page.wait_for_selector('table#contracts-grid tbody tr', timeout=120000)
                await page.wait_for_timeout(1500)

                return True

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Pagination attempt {attempt + 1} failed: {e}, retrying...")
                    await page.wait_for_timeout(5000)  # Wait before retry
                    continue
                else:
                    logger.warning(f"Pagination failed after {max_retries} attempts: {e}")
                    return False
        return False

    async def errback_playwright(self, failure):
        """Handle Playwright errors"""
        logger.error(f"Playwright error: {failure.value}")

        page = failure.request.meta.get('playwright_page')
        if page:
            try:
                await page.close()
            except:
                pass

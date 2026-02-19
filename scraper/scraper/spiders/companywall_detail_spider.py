"""
CompanyWall Detail Spider - Scrapes full company data (emails, EMBS, financials)

Requires a logged-in session. Uses Playwright for login, then visits company
detail pages already discovered by the sitemap spider.

Strategy:
- Login ONCE via Playwright (MVC + Keycloak SSO)
- Read company URLs from mk_companies table (where companywall_id IS NOT NULL)
- Visit each detail page and extract: email, phone, EMBS, EDB, financials, owners
- Stop gracefully when daily limit is reached
- Track progress: only visit companies not yet detail-scraped

IMPORTANT: Do NOT retry login - a single failed attempt creates stuck Keycloak
sessions. If login fails, stop immediately and use a fresh account next time.

Usage:
    # Scrape up to 100 company detail pages
    COMPANYWALL_EMAIL=x@y.com COMPANYWALL_PASSWORD=pass \
        scrapy crawl companywall_detail -a max_companies=100

    # Full run (all un-scraped companies, stops at daily limit)
    COMPANYWALL_EMAIL=x@y.com COMPANYWALL_PASSWORD=pass \
        scrapy crawl companywall_detail
"""
import json
import os
import re
import logging
from datetime import datetime

import scrapy
from scrapy_playwright.page import PageMethod

from scraper.items import CompanyWallItem
from dotenv import load_dotenv
load_dotenv()


logger = logging.getLogger(__name__)


class CompanyWallDetailSpider(scrapy.Spider):
    name = 'companywall_detail'
    allowed_domains = ['www.companywall.com.mk', 'companywall.com.mk', 'login.companywall.com']

    custom_settings = {
        'DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'RANDOMIZE_DOWNLOAD_DELAY': True,

        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 2.0,
        'AUTOTHROTTLE_MAX_DELAY': 15.0,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,

        'ITEM_PIPELINES': {
            'scraper.pipelines.CompanyWallValidationPipeline': 100,
            'scraper.pipelines.CompanyWallDatabasePipeline': 300,
        },

        'COOKIES_ENABLED': True,
        'RETRY_TIMES': 2,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408],
        'MEMUSAGE_LIMIT_MB': 1200,
        'PLAYWRIGHT_MAX_PAGES_PER_CONTEXT': 4,
        'PLAYWRIGHT_MAX_CONTEXTS': 1,
    }

    def __init__(self, max_companies=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_companies = int(max_companies) if max_companies else None
        self.companies_scraped = 0
        self.companies_skipped = 0
        self.consecutive_blocked = 0
        self.email = os.getenv('COMPANYWALL_EMAIL', '')
        self.password = os.getenv('COMPANYWALL_PASSWORD', '')

    def start_requests(self):
        if not self.email or not self.password:
            logger.error("COMPANYWALL_EMAIL and COMPANYWALL_PASSWORD required")
            return

        logger.info("CompanyWall Detail Spider starting - login attempt...")
        yield scrapy.Request(
            'https://www.companywall.com.mk/login',
            callback=self.do_login,
            meta={
                'playwright': True,
                'playwright_include_page': True,
                'playwright_page_methods': [
                    PageMethod('wait_for_timeout', 3000),
                ],
            },
            errback=self.on_error,
            dont_filter=True,
        )

    async def do_login(self, response):
        """Single login attempt. NO RETRIES - if it fails, stop."""
        page = response.meta.get('playwright_page')
        if not page:
            logger.error("No Playwright page")
            return

        try:
            # Load login page fresh
            await page.goto('https://www.companywall.com.mk/login',
                            wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)

            # Cookie consent
            try:
                btn = await page.query_selector('button:has-text("Се согласувам")')
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

            # Wait for Keycloak iframe to fully initialize
            await page.wait_for_timeout(8000)

            # Fill form
            await page.fill('#Email', self.email)
            await page.fill('#Password', self.password)
            await page.wait_for_timeout(500)

            # Track AJAX response
            login_status = {'code': 0}
            async def on_response(resp):
                if '/loginKeycloak' in resp.url:
                    login_status['code'] = resp.status
                    logger.info(f"loginKeycloak response: {resp.status}")
            page.on('response', on_response)

            # Click submit - let full JS flow run naturally
            logger.info("Clicking login button...")
            await page.click('button[onclick="submitMvcForm()"]')

            # Wait for FULL flow: AJAX → sendDataToIframe → Keycloak SSO → redirect
            # This is critical - don't cut short!
            await page.wait_for_timeout(20000)
            page.remove_listener('response', on_response)

            current_url = page.url
            logger.info(f"After login wait, URL: {current_url}")

            # Check MVC AJAX result
            if login_status['code'] != 200:
                error = ''
                try:
                    error = await page.text_content('#validation-summary')
                except Exception:
                    pass
                logger.error(f"Login failed (HTTP {login_status['code']}): {error}")
                await page.close()
                return

            # If still on login page, try manual redirect to Dashboard
            if '/login' in current_url.lower():
                logger.info("Still on login page, navigating to Dashboard...")
                await page.goto('https://www.companywall.com.mk/Home/Dashboard',
                                wait_until='networkidle', timeout=20000)
                await page.wait_for_timeout(5000)
                current_url = page.url
                logger.info(f"Dashboard URL: {current_url}")

            if '/login' in current_url or '/registracija' in current_url:
                logger.error(f"Login failed - ended on {current_url}")
                await page.close()
                return

            logger.info("Login successful! Starting detail scraping...")

            # Get company URLs from DB
            company_urls = await self._get_company_urls()
            if not company_urls:
                logger.error("No company URLs to scrape")
                await page.close()
                return

            logger.info(f"Found {len(company_urls)} companies to detail-scrape")

            # Scrape each company detail page
            for source_url, cw_id in company_urls:
                if self.max_companies and self.companies_scraped >= self.max_companies:
                    logger.info(f"Reached max_companies limit ({self.max_companies})")
                    break

                # Stop if we hit too many consecutive blocks (daily limit reached)
                if self.consecutive_blocked >= 5:
                    logger.warning("5 consecutive blocks - daily limit likely reached, stopping")
                    break

                try:
                    await page.goto(source_url, wait_until='networkidle', timeout=20000)
                    await page.wait_for_timeout(2000)

                    cur_url = page.url

                    # Check for blocks/redirects
                    if '/registracija' in cur_url or 'LoginOrRegister' in cur_url:
                        self.consecutive_blocked += 1
                        self.companies_skipped += 1
                        logger.warning(
                            f"Blocked ({self.consecutive_blocked}/5): {cw_id} → {cur_url}"
                        )
                        # Wait longer between requests when getting blocked
                        await page.wait_for_timeout(5000)
                        continue

                    self.consecutive_blocked = 0  # Reset on success

                    # Parse the detail page
                    content = await page.content()
                    item = self._parse_company(content, cw_id, source_url)
                    if item:
                        self.companies_scraped += 1
                        yield item

                        if self.companies_scraped % 10 == 0:
                            logger.info(
                                f"Progress: {self.companies_scraped} scraped, "
                                f"{self.companies_skipped} skipped"
                            )

                except Exception as e:
                    logger.warning(f"Error on {cw_id}: {e}")
                    self.companies_skipped += 1

            await page.close()

        except Exception as e:
            logger.error(f"Spider error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                await page.close()
            except Exception:
                pass

    async def _get_company_urls(self):
        """Get company URLs from DB that haven't been detail-scraped yet."""
        import asyncpg

        database_url = os.getenv('DATABASE_URL', '')
        if not database_url:
            logger.error("DATABASE_URL not set")
            return []

        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

        try:
            conn = await asyncpg.connect(database_url)
            # Get companies that have companywall_id but no EMBS (not detail-scraped yet)
            rows = await conn.fetch("""
                SELECT source_url, companywall_id
                FROM mk_companies
                WHERE companywall_id IS NOT NULL
                  AND source_url IS NOT NULL
                  AND embs IS NULL
                ORDER BY company_id
                LIMIT $1
            """, self.max_companies or 100000)
            await conn.close()
            return [(r['source_url'], r['companywall_id']) for r in rows]
        except Exception as e:
            logger.error(f"DB query error: {e}")
            return []

    def _parse_company(self, content, cw_id, url):
        """Parse company detail page HTML into CompanyWallItem."""
        sel = scrapy.Selector(text=content)
        item = CompanyWallItem()
        item['companywall_id'] = cw_id
        item['source_url'] = url
        item['scraped_at'] = datetime.utcnow().isoformat()

        # --- JSON-LD extraction (primary) ---
        json_ld_blocks = sel.css('script[type="application/ld+json"]::text').getall()
        json_ld_data = {}
        for block in json_ld_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict):
                    json_ld_data[data.get('@type', '')] = data
            except (json.JSONDecodeError, TypeError):
                continue

        # LocalBusiness schema
        biz = json_ld_data.get('LocalBusiness', {})
        if biz:
            item['name'] = biz.get('name', '')
            item['phone'] = biz.get('telephone', '')
            item['website'] = biz.get('url', '')
            addr = biz.get('address', {})
            if isinstance(addr, dict):
                item['address'] = addr.get('streetAddress', '')
                item['city'] = addr.get('addressLocality', '')
                item['postal_code'] = addr.get('postalCode', '')
                item['region'] = addr.get('addressRegion', '')

        # FAQPage (owners, activity)
        faq = json_ld_data.get('FAQPage', {})
        if faq:
            for entity in faq.get('mainEntity', []):
                q = entity.get('name', '').lower()
                a_obj = entity.get('acceptedAnswer', {})
                a = a_obj.get('text', '') if isinstance(a_obj, dict) else ''
                if not a:
                    continue
                if 'сопственик' in q or 'основач' in q:
                    item['owners'] = json.dumps([a.strip()], ensure_ascii=False)
                elif 'управител' in q or 'директор' in q:
                    item['directors'] = json.dumps([a.strip()], ensure_ascii=False)
                elif 'дејност' in q or 'активност' in q:
                    item['nace_description'] = a.strip()

        # Dataset (financials)
        ds = json_ld_data.get('Dataset', {})
        if ds:
            fin = ds.get('data', [])
            if fin and isinstance(fin, list):
                latest = fin[0] if len(fin) == 1 else max(fin, key=lambda x: x.get('Лето', 0))
                item['financial_year'] = latest.get('Лето')
                for key, field in [
                    ('Вкупни приходи', 'revenue'),
                    ('Добивка/загуба', 'profit'),
                    ('Просечна бруто плата', 'avg_salary'),
                ]:
                    val = latest.get(key, '')
                    if val:
                        item[field] = self._parse_amount(str(val))
                emp = latest.get('Број на работници', '')
                if emp:
                    try:
                        item['num_employees'] = int(float(str(emp).replace('.', '').replace(',', '.')))
                    except (ValueError, TypeError):
                        pass

        if json_ld_data:
            item['raw_data_json'] = json.dumps(json_ld_data, ensure_ascii=False, default=str)

        # --- HTML fallbacks ---
        if not item.get('name'):
            name = sel.css('h1::text').get() or sel.css('meta[property="og:title"]::attr(content)').get()
            if name:
                item['name'] = name.strip()

        # EMBS
        for pat in [r'ЕМБС\s*[:\s]+(\d{5,8})', r'embs[:\s]+(\d{5,8})']:
            m = re.search(pat, content, re.IGNORECASE)
            if m:
                item['embs'] = m.group(1)
                break

        # EDB
        for pat in [r'ЕДБ\s*[:\s]+(\d{10,15})', r'edb[:\s]+(\d{10,15})']:
            m = re.search(pat, content, re.IGNORECASE)
            if m:
                item['edb'] = m.group(1)
                break

        # Status
        tl = content.lower()
        if 'активно' in tl and 'неактивно' not in tl:
            item['status'] = 'active'
        elif 'неактивно' in tl:
            item['status'] = 'inactive'
        elif 'ликвидација' in tl:
            item['status'] = 'in_liquidation'
        elif 'стечај' in tl:
            item['status'] = 'in_bankruptcy'

        # Legal form
        name = item.get('name', '').upper()
        if 'ДООЕЛ' in name or 'DOOEL' in name:
            item['legal_form'] = 'DOOEL'
        elif 'ДОО' in name or 'DOO' in name:
            item['legal_form'] = 'DOO'
        elif ' АД' in name:
            item['legal_form'] = 'AD'
        elif ' ТП' in name or name.startswith('ТП '):
            item['legal_form'] = 'TP'

        # NACE
        m = re.search(r'(\d{2}\.\d{2,3})\s*[-–]\s*(.+?)(?:<|$|\n)', content)
        if m:
            item['nace_code'] = m.group(1).strip()
            if not item.get('nace_description'):
                item['nace_description'] = m.group(2).strip()[:500]

        # Founding date
        for pat in [
            r'(?:Датум на основање|Основано|основање)[:\s]*(\d{1,2})\.(\d{1,2})\.(\d{4})',
            r'основана?\s+(?:на\s+)?(\d{1,2})\.(\d{1,2})\.(\d{4})',
            r'(?:Основање|основање)</\w+>\s*<\w+[^>]*>\s*(\d{1,2})\.(\d{1,2})\.(\d{4})',
        ]:
            m = re.search(pat, content, re.IGNORECASE)
            if m:
                item['founding_date'] = f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
                break

        # Email
        if not item.get('email'):
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', content)
            for e in emails:
                if not any(x in e.lower() for x in ['companywall', 'google', 'recaptcha', 'gstatic', 'example']):
                    item['email'] = e
                    break

        # Municipality
        m = re.search(r'Општина[:\s]*([А-Яа-яЃѓЅѕЈјЉљЊњЌќЏџ\s]+?)(?:<|,|\n)', content)
        if m:
            item['municipality'] = m.group(1).strip()

        # Risk indicators
        if 'не е даночен должник' in tl or 'нема даночен долг' in tl:
            item['tax_debtor'] = False
        elif 'даночен должник' in tl:
            item['tax_debtor'] = True

        if 'нема судски постапки' in tl:
            item['court_proceedings'] = False
        elif 'судски постапки' in tl:
            item['court_proceedings'] = True

        if 'не е блокирана' in tl or 'нема блокада' in tl:
            item['bank_blocked'] = False
        elif 'блокирана' in tl or 'блокада' in tl:
            item['bank_blocked'] = True

        # Credit rating
        m = re.search(r'(?:кредитен рејтинг|credit rating)[:\s]*([A-Da-d][+\-]?)', content, re.IGNORECASE)
        if m:
            item['credit_rating'] = m.group(1).upper()

        if not item.get('name'):
            return None

        return item

    def _parse_amount(self, s):
        if not s:
            return None
        try:
            return float(s.replace('.', '').replace(',', '.'))
        except (ValueError, TypeError):
            return None

    async def on_error(self, failure):
        logger.error(f"Request failed: {failure.value}")

    def closed(self, reason):
        logger.info(
            f"CompanyWall Detail spider closed ({reason}). "
            f"Scraped: {self.companies_scraped}, "
            f"Skipped: {self.companies_skipped}"
        )

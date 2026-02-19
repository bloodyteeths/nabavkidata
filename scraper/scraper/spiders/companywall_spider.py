"""
CompanyWall.com.mk Spider - Scrapes all Macedonian companies via sitemap

Strategy:
- Downloads company URLs from the public sitemap (no login required)
- Parses company name, city, legal form, and status from URL slugs
- 201 sitemap pages × ~1000 unique companies each = ~183K companies
- All data stored in mk_companies table via CompanyWall pipelines

Usage:
    # Test run (2 sitemap pages = ~2000 companies)
    scrapy crawl companywall -a max_pages=2

    # Full run (all 201 pages)
    scrapy crawl companywall

    # Start from specific sitemap page
    scrapy crawl companywall -a start_page=50 -a max_pages=50
"""
import json
import re
import logging
from datetime import datetime
from urllib.parse import unquote, urljoin

import scrapy

from scraper.items import CompanyWallItem

logger = logging.getLogger(__name__)

# Known Macedonian cities for extraction from URL slugs
MK_CITIES = {
    'skopje', 'bitola', 'kumanovo', 'prilep', 'tetovo', 'ohrid', 'veles',
    'stip', 'kocani', 'gostivar', 'strumica', 'kavadarci', 'kicevo',
    'struga', 'radovis', 'gevgelija', 'debar', 'krusevo', 'sveti-nikole',
    'negotino', 'delcevo', 'vinica', 'resen', 'probistip', 'berovo',
    'kratovo', 'makedonski-brod', 'demir-hisar', 'valandovo', 'bogdanci',
    'pehcevo', 'kriva-palanka', 'makedonska-kamenica', 'demir-kapija',
    'sopiste', 'zelino', 'bogovinje', 'tearce', 'brvenica', 'jegunovce',
    'lipkovo', 'aracinovo', 'ilinden', 'petrovec', 'cucer-sandevo',
    'studenicani', 'saraj', 'centar-zupa', 'plasnica', 'dolneni',
    'krivogastani', 'mogila', 'novaci', 'demir-hisar', 'mavrovo-i-rostuse',
    'vasilevo', 'bosilovo', 'novo-selo', 'star-dojran', 'konche',
    'zrnovci', 'carbinci', 'lozovo', 'gradsko', 'rosoman', 'caska',
    'vevchani', 'centar', 'gazi-baba', 'karpos', 'kisela-voda',
    'aerodrom', 'butel', 'cair', 'suto-orizari', 'gjorce-petrov',
}


class CompanyWallSpider(scrapy.Spider):
    name = 'companywall'
    allowed_domains = ['www.companywall.com.mk', 'companywall.com.mk']

    custom_settings = {
        # Moderate concurrency for sitemap pages
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': True,

        # AutoThrottle
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 0.5,
        'AUTOTHROTTLE_MAX_DELAY': 5.0,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 2.0,

        # Pipelines
        'ITEM_PIPELINES': {
            'scraper.pipelines.CompanyWallValidationPipeline': 100,
            'scraper.pipelines.CompanyWallDatabasePipeline': 300,
        },

        # Retry
        'RETRY_TIMES': 5,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],

        # Memory safety
        'MEMUSAGE_LIMIT_MB': 1200,
    }

    TOTAL_SITEMAP_PAGES = 201

    def __init__(self, start_page=1, max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_page = int(start_page)
        self.max_pages = int(max_pages) if max_pages else self.TOTAL_SITEMAP_PAGES
        self.pages_scraped = 0
        self.companies_found = 0
        self.seen_ids = set()

    def start_requests(self):
        """Generate requests for sitemap pages."""
        end_page = min(self.start_page + self.max_pages, self.TOTAL_SITEMAP_PAGES + 1)
        logger.info(
            f"Starting CompanyWall sitemap crawl: pages {self.start_page} to {end_page - 1}"
        )

        for page_num in range(self.start_page, end_page):
            url = f'https://www.companywall.com.mk/SiteMap/Companies?p={page_num}'
            yield scrapy.Request(
                url,
                callback=self.parse_sitemap_page,
                meta={'page_num': page_num},
                dont_filter=True,
            )

    def parse_sitemap_page(self, response):
        """Parse a sitemap page and extract company items from URLs."""
        page_num = response.meta.get('page_num', '?')
        # Extract all <loc> URLs
        urls = re.findall(r'<loc>([^<]+)</loc>', response.text)

        page_companies = 0
        for url in urls:
            # Only process /kompanija/ URLs (skip CompanyBonitet etc)
            if '/kompanija/' not in url:
                continue

            # Skip Cyrillic-encoded URLs (duplicates of Latin ones)
            if '%D0%' in url or '%D1%' in url:
                continue

            # Extract companywall_id (last path segment)
            parts = url.rstrip('/').split('/')
            if len(parts) < 2:
                continue

            cw_id = parts[-1]
            slug = parts[-2] if len(parts) >= 3 else ''

            # Deduplicate by companywall_id
            if cw_id in self.seen_ids:
                continue
            self.seen_ids.add(cw_id)

            # Parse company data from URL slug
            item = self._parse_from_slug(slug, cw_id, url)
            if item:
                page_companies += 1
                self.companies_found += 1
                yield item

        self.pages_scraped += 1
        logger.info(
            f"Sitemap page {page_num}: {page_companies} companies "
            f"(total: {self.companies_found}, pages: {self.pages_scraped}/{self.max_pages})"
        )

    def _parse_from_slug(self, slug, cw_id, url):
        """Parse company data from URL slug.

        URL pattern: /kompanija/{name-with-dashes-and-city}/{companywall_id}
        Examples:
            bonanca-urban-doo-skopje/MM1K8aGD
            torelli-kaffe-dooel-uvoz-izvoz-svelesta-struga/MMHbDFq
            dominus-konstraksn-dooel-uvoz-izvoz-skopje---vo-likvidacija/MMHbYVC
        """
        if not slug or not cw_id:
            return None

        item = CompanyWallItem()
        item['companywall_id'] = cw_id
        item['source_url'] = url
        item['scraped_at'] = datetime.utcnow().isoformat()

        # Decode URL-encoded slug
        slug_decoded = unquote(slug)
        slug_lower = slug_decoded.lower()

        # Extract status from slug
        if 'vo-likvidacija' in slug_lower:
            item['status'] = 'in_liquidation'
            # Remove status suffix for name parsing
            slug_decoded = re.sub(r'---?vo-likvidacija$', '', slug_decoded, flags=re.IGNORECASE)
        elif 'vo-stecaj' in slug_lower:
            item['status'] = 'in_bankruptcy'
            slug_decoded = re.sub(r'---?vo-stecaj$', '', slug_decoded, flags=re.IGNORECASE)
        else:
            item['status'] = 'active'

        # Extract legal form
        slug_upper = slug_decoded.upper()
        if '-DOOEL-' in slug_upper or slug_upper.endswith('-DOOEL') or '-DOOEL ' in slug_upper:
            item['legal_form'] = 'DOOEL'
        elif '-DOO-' in slug_upper or slug_upper.endswith('-DOO'):
            item['legal_form'] = 'DOO'
        elif '-AD-' in slug_upper or slug_upper.endswith('-AD'):
            item['legal_form'] = 'AD'
        elif slug_upper.startswith('TP-') or '-TP-' in slug_upper:
            item['legal_form'] = 'TP'
        elif slug_upper.startswith('JP-') or '-JP-' in slug_upper:
            item['legal_form'] = 'JP'

        # Extract city (check last 1-3 words against known cities)
        words = slug_decoded.split('-')
        city = None
        city_words_count = 0
        for n in range(3, 0, -1):
            if len(words) >= n:
                candidate = '-'.join(words[-n:]).lower()
                if candidate in MK_CITIES:
                    city = candidate
                    city_words_count = n
                    break

        if city:
            item['city'] = city.replace('-', ' ').title()

        # Build company name from slug (exclude city at end)
        name_words = words[:-city_words_count] if city_words_count else words
        # Convert slug to readable name
        name = ' '.join(w for w in name_words if w).strip()
        # Capitalize properly
        name = name.title()
        # Fix common abbreviations that should be uppercase
        for abbr in ['Dooel', 'Doo', 'Doo ', 'Tp ', 'Jp ', 'Ad ', 'Dtu', 'Dptu', 'Dptstu',
                      'Uvoz', 'Izvoz', 'Eksport', 'Import', 'Zr', 'Zk']:
            name = name.replace(abbr, abbr.upper())

        if name:
            item['name'] = name
        else:
            return None

        return item

    def closed(self, reason):
        """Log final stats."""
        logger.info(
            f"CompanyWall spider closed ({reason}). "
            f"Sitemap pages: {self.pages_scraped}, "
            f"Companies found: {self.companies_found}"
        )

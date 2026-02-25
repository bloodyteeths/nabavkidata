---
name: scraper-run
description: Run the nabavki scraper on Hetzner server. Use when user wants to scrape tenders, run the spider, or fetch new data from e-nabavki.gov.mk.
allowed-tools: Bash
---

# Scraper Run Skill

Commands to run the nabavki spider on the Hetzner server.

## Server Access
```bash
ssh ubuntu@46.224.89.197
```

## Scraper Commands

### Active/Current Tenders (daily cron handles this)
```bash
cd /home/ubuntu/nabavkidata/scraper
scrapy crawl nabavki -a category=active -s CONCURRENT_REQUESTS=2
```

### Awarded Tenders
```bash
scrapy crawl nabavki -a category=awarded -s CONCURRENT_REQUESTS=2
```

### Archive Years (2008-2021) - Use `year` parameter
```bash
scrapy crawl nabavki -a category=awarded -a year=2019 -a force_full_scan=true -a max_listing_pages=4000
```

### Recent Years (2022-2024) - Use `year_filter` parameter
```bash
scrapy crawl nabavki -a category=awarded -a year_filter=2024 -a force_full_scan=true
```

## Key Parameters
- `category`: active, awarded, cancelled, contracts
- `year`: Archive modal selection (2008-2021 only)
- `year_filter`: Server-side date filter (2022+)
- `force_full_scan`: Continue past duplicate pages
- `start_page`: Start from specific page
- `max_listing_pages`: Limit pages to scrape

## Memory Limits
- Server has 8GB RAM
- Max 3-4 scrapers with Playwright
- Use `MEMUSAGE_LIMIT_MB=2000` for safety

## Check Running Scrapers
```bash
ssh ubuntu@46.224.89.197 "pgrep -f scrapy"
```

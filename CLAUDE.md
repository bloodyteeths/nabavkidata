# NabavkiData Project Context

## Project Overview
Macedonian public procurement data platform - scrapes tenders from e-nabavki.gov.mk, extracts documents, and provides AI-powered search/analysis.

## Memory & Context Files
- **DECISIONS.md**: `.claude/DECISIONS.md` - Technical decisions log
- **Skills**: `.claude/skills/` - Custom skills for db-status, scraper-run, deploy
- **Rules**: `.claude/rules/` - Code guidelines for backend, frontend, scraper
- Use `/db-status` skill for quick database queries
- Use `/deploy` skill for deployment commands

## Server Details
- **AWS EC2**: 18.197.185.30
- **SSH**: `ssh -i ~/.ssh/nabavki-key.pem ubuntu@18.197.185.30`
- **RAM**: 3.8GB (run max 2-3 scrapers concurrently)
- **Database**: RDS PostgreSQL at nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com

## Scraper Commands

### Active/Current Tenders
```bash
cd /home/ubuntu/nabavkidata/scraper
~/.local/bin/scrapy crawl nabavki -a category=awarded -s CONCURRENT_REQUESTS=2
```

### Archive Years (2008-2021) - Use `year` parameter
```bash
# Archive year selection (requires Playwright to click modal)
scrapy crawl nabavki -a category=awarded -a year=2019 -a force_full_scan=true -a max_listing_pages=4000
```

### Year Filter (2022-2024) - Use `year_filter` parameter
```bash
# Server-side date filter for recent years (no archive modal)
scrapy crawl nabavki -a category=awarded -a year_filter=2024 -a force_full_scan=true
```

### Key Spider Parameters
- `category`: active, awarded, cancelled, contracts
- `year`: Archive year 2008-2021 (uses modal selection)
- `year_filter`: Filter by tender_id year e.g., {2024} (server-side date filter)
- `force_full_scan`: Continue past duplicate pages (for backfills)
- `start_page`: Start from specific page number
- `max_listing_pages`: Limit pages to scrape
- `date_from`, `date_to`: Explicit date range filter

## Document Processing Pipeline

### Step 1: PDF Text Extraction (32K+ pending)
```bash
cd /home/ubuntu/nabavkidata/scraper
python3 process_documents.py --limit 1000
# Or for specific tender:
python3 process_documents.py --tender-id 12345/2025
```

### Step 2: Generate Embeddings
```bash
cd /home/ubuntu/nabavkidata/ai/embeddings
python3 pipeline.py --batch-size 20 --max-documents 1000
```

### Document Status Check
```sql
SELECT extraction_status, COUNT(*) FROM documents GROUP BY extraction_status;
SELECT COUNT(*) FROM embeddings;
SELECT COUNT(*) FROM documents d WHERE content_text IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.doc_id = d.doc_id);
```

## Database Quick Queries

### Tender counts by year
```sql
SELECT SUBSTRING(tender_id FROM '[0-9]+/([0-9]+)') as year, COUNT(*)
FROM tenders GROUP BY year ORDER BY year DESC;
```

### Check scraper progress
```sql
SELECT status, COUNT(*) FROM tenders GROUP BY status;
```

## Common Issues & Fixes

### Filter State Corruption
Both archive year and date filter can corrupt after ~80-100 pages. Spider has automatic recovery that re-navigates and re-applies filter.

### Memory Management
- Max 2-3 scrapers with Playwright concurrently
- Use `MEMUSAGE_LIMIT_MB=1200` for safety
- Clean up extracted PDFs: `rm downloads/files/*.pdf` after extraction

### Disk Cleanup
```bash
# Delete successfully extracted PDFs
cd /home/ubuntu/nabavkidata/scraper/downloads/files
PGPASSWORD='...' psql -h ... -c "SELECT file_name FROM documents WHERE extraction_status='success';" | while read f; do rm -f "$f"; done
```

## Log Locations
- Scraper logs: `/var/log/nabavkidata/*.log`
- API logs: `/var/log/nabavkidata/api.log`

## Cron Jobs
- **Active scraper**: Runs every 3 hours, scrapes first 10 pages only (new tenders appear on page 1)
- **Corruption views refresh**: Daily at 5 AM UTC
- Check: `crontab -l` on server
- Config: `/home/ubuntu/nabavkidata/scraper/cron/`

## Key Code Patterns

### Bilingual Search (Latin to Cyrillic)
```python
from backend.api.corruption import latin_to_cyrillic, build_bilingual_search_condition
cyrillic = latin_to_cyrillic("Alkaloid")  # Returns "Алкалоид"
```

### JSONB Handling in asyncpg
```python
import json
if isinstance(jsonb_value, str):
    data = json.loads(jsonb_value) if jsonb_value else {}
```

### Frontend Search Params
```tsx
import { useSearchParams } from 'next/navigation';
const searchParams = useSearchParams();
const query = searchParams.get('search') || '';
```

## Tech Stack
- **Frontend**: Next.js 14, React, TypeScript, Tailwind, shadcn/ui
- **Backend**: Python FastAPI, asyncpg
- **Database**: PostgreSQL on AWS RDS
- **AI**: Gemini embeddings, RAG search
- **Scraping**: Scrapy + Playwright, Chandra OCR
- **Hosting**: Vercel (frontend), AWS EC2 (backend/scraper)

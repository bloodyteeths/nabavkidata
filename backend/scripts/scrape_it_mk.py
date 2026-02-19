#!/usr/bin/env python3
"""
Scrape IT.mk directory for Macedonian IT companies.
No CAPTCHA required - clean company data with emails.

Usage:
    python3 scripts/scrape_it_mk.py
"""
import os
import sys
import asyncio
import asyncpg
import aiohttp
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = "https://it.mk"

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')


def decode_cloudflare_email(encoded):
    """Decode Cloudflare protected email (data-cfemail attribute)"""
    try:
        key = int(encoded[:2], 16)
        result = ""
        for i in range(2, len(encoded), 2):
            result += chr(int(encoded[i:i+2], 16) ^ key)
        return result
    except:
        return None


async def fetch_page(session, url):
    """Fetch a page and return BeautifulSoup object"""
    try:
        async with session.get(url, timeout=30) as resp:
            if resp.status == 200:
                html = await resp.text()
                return BeautifulSoup(html, 'html.parser')
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
    return None


async def get_company_list(session):
    """Get list of all company URLs from the index page"""
    companies = []

    # Main IT companies page
    index_url = f"{BASE_URL}/dejnost/it-kompanii/"
    soup = await fetch_page(session, index_url)

    if soup:
        # Find all company links - they follow pattern /index/company-slug/
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/index/' in href and href.count('/') >= 2:
                full_url = href if href.startswith('http') else f"{BASE_URL}{href}"
                if full_url not in companies and 'it.mk/index/' in full_url:
                    companies.append(full_url)

    # Also try paginated pages
    for page_num in range(2, 20):  # Check up to 20 pages
        page_url = f"{BASE_URL}/dejnost/it-kompanii/page/{page_num}/"
        soup = await fetch_page(session, page_url)
        if not soup:
            break

        found_any = False
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/index/' in href and href.count('/') >= 2:
                full_url = href if href.startswith('http') else f"{BASE_URL}{href}"
                if full_url not in companies and 'it.mk/index/' in full_url:
                    companies.append(full_url)
                    found_any = True

        if not found_any:
            break

        await asyncio.sleep(0.5)

    return list(set(companies))


async def scrape_company(session, url):
    """Scrape individual company page for contact info"""
    result = {
        'name': None,
        'email': None,
        'website': None,
        'phone': None,
        'address': None,
        'employees': None,
        'founded': None,
        'linkedin': None,
        'facebook': None,
        'source_url': url
    }

    soup = await fetch_page(session, url)
    if not soup:
        return result

    try:
        # Get page text for email extraction
        page_text = soup.get_text()

        # Extract company name from title or h1
        title = soup.find('h1')
        if title:
            result['name'] = title.get_text().strip()

        # Find Cloudflare protected emails first
        cf_emails = soup.find_all('span', class_='__cf_email__')
        for cf in cf_emails:
            encoded = cf.get('data-cfemail')
            if encoded:
                decoded = decode_cloudflare_email(encoded)
                if decoded and '@' in decoded:
                    result['email'] = decoded.lower()
                    break

        # Also check for href with email-protection
        for link in soup.find_all('a', href=True):
            if '/cdn-cgi/l/email-protection' in link.get('href', ''):
                cf_span = link.find('span', class_='__cf_email__')
                if cf_span:
                    encoded = cf_span.get('data-cfemail')
                    if encoded:
                        decoded = decode_cloudflare_email(encoded)
                        if decoded and '@' in decoded:
                            result['email'] = decoded.lower()
                            break

        # Fallback: Find regular emails on page
        if not result['email']:
            emails = EMAIL_PATTERN.findall(page_text.lower())
            if emails:
                # Filter out generic emails
                valid_emails = [e for e in emails if not any(x in e for x in
                    ['example', 'test', 'noreply', 'support@it.mk', 'info@it.mk', '.png', '.jpg'])]
                if valid_emails:
                    result['email'] = valid_emails[0]

        # Find website link
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().lower()

            if 'linkedin.com/company' in href:
                result['linkedin'] = href
            elif 'facebook.com' in href:
                result['facebook'] = href
            elif href.startswith('http') and 'it.mk' not in href and '.' in href:
                # Likely company website
                if not result['website'] and any(x in text or x in href for x in
                    ['website', 'web', 'www', '.com', '.mk']):
                    result['website'] = href

        # Look for structured data
        for meta in soup.find_all(['p', 'span', 'div']):
            text = meta.get_text()

            # Employee count - only look in specific contexts
            if ('вработени' in text.lower() or 'employees' in text.lower()) and len(text) < 100:
                nums = re.findall(r'\b(\d{1,5})\b', text)  # Max 5 digits (99999)
                if nums:
                    emp_count = int(nums[0])
                    if 1 <= emp_count <= 50000:  # Reasonable employee count
                        result['employees'] = emp_count

            # Founded year - only look in specific contexts
            if ('основана' in text.lower() or 'founded' in text.lower()) and len(text) < 100:
                years = re.findall(r'\b((?:19|20)\d{2})\b', text)
                if years:
                    year = int(years[0])
                    if 1990 <= year <= 2025:  # IT companies founded 1990-2025
                        result['founded'] = year

        # Extract domain from website or email
        if result['website']:
            from urllib.parse import urlparse
            parsed = urlparse(result['website'])
            result['domain'] = parsed.netloc.replace('www.', '')
        elif result['email'] and '@' in result['email']:
            result['domain'] = result['email'].split('@')[1]

    except Exception as e:
        print(f"  Error parsing {url}: {e}")

    return result


async def main():
    print("=" * 70)
    print("SCRAPE IT.MK DIRECTORY")
    print("=" * 70)

    conn = await asyncpg.connect(DATABASE_URL)

    # Create IT companies table if not exists
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS it_mk_companies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_name VARCHAR(500),
            email VARCHAR(255),
            website VARCHAR(500),
            phone VARCHAR(100),
            address TEXT,
            employees INT,
            founded INT,
            linkedin VARCHAR(500),
            facebook VARCHAR(500),
            source_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_it_mk_email ON it_mk_companies(email);
    """)

    print("\nFetching company list...")

    async with aiohttp.ClientSession(
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    ) as session:
        company_urls = await get_company_list(session)
        print(f"Found {len(company_urls)} company pages")

        if not company_urls:
            print("No companies found, exiting")
            return

        print("\nScraping company details...\n")

        scraped = 0
        emails_found = 0
        start_time = datetime.now()

        for i, url in enumerate(company_urls, 1):
            result = await scrape_company(session, url)
            scraped += 1

            if result['name']:
                # Save to it_mk_companies table
                await conn.execute("""
                    INSERT INTO it_mk_companies (
                        company_name, email, website, phone, address,
                        employees, founded, linkedin, facebook, source_url
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT DO NOTHING
                """,
                    result['name'],
                    result['email'],
                    result['website'],
                    result['phone'],
                    result['address'],
                    result['employees'],
                    result['founded'],
                    result['linkedin'],
                    result['facebook'],
                    result['source_url']
                )

                if result['email']:
                    emails_found += 1

                    # Add to outreach_leads (Segment B - IT decision makers)
                    await conn.execute("""
                        INSERT INTO outreach_leads (
                            email, company_name, segment, source, quality_score,
                            company_domain, country, linkedin_url, raw_data
                        ) VALUES ($1, $2, 'B', 'it_mk', 80, $3, 'North Macedonia', $4, $5)
                        ON CONFLICT (email) DO UPDATE SET
                            linkedin_url = COALESCE(outreach_leads.linkedin_url, EXCLUDED.linkedin_url),
                            updated_at = NOW()
                    """,
                        result['email'],
                        result['name'],
                        result.get('domain'),
                        result['linkedin'],
                        json.dumps({'source': 'it.mk', 'url': url, 'employees': result['employees']})
                    )

                    if emails_found <= 20 or emails_found % 50 == 0:
                        print(f"  ✓ [{i}/{len(company_urls)}] {result['name'][:40]}... -> {result['email']}")

            if i % 50 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = scraped / elapsed * 60 if elapsed > 0 else 0
                print(f"\n  Progress: {scraped}/{len(company_urls)} | {emails_found} emails | {rate:.0f}/min\n")

            await asyncio.sleep(0.3)  # Be respectful

    # Final stats
    total_it_companies = await conn.fetchval("SELECT COUNT(*) FROM it_mk_companies")
    total_outreach = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads")

    print("\n" + "=" * 70)
    print("SCRAPE COMPLETE")
    print("=" * 70)
    print(f"Companies scraped: {scraped}")
    print(f"Emails found: {emails_found}")
    print(f"\nTotal IT.mk companies: {total_it_companies}")
    print(f"Total outreach leads: {total_outreach}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

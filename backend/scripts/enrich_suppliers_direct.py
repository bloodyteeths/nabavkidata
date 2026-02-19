#!/usr/bin/env python3
"""
Direct Supplier Enrichment Script for Macedonian Companies
Finds emails by:
1. Extracting brand names and generating .mk domain guesses
2. Scraping company websites
3. Using known Macedonian company websites

Run with: python3 scripts/enrich_suppliers_direct.py --limit 100
"""
import os
import re
import sys
import asyncio
import argparse
import logging
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse, urljoin, quote
import httpx
from bs4 import BeautifulSoup

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", os.getenv("DATABASE_URL"))

# Role-based email prefixes
ROLE_BASED_PREFIXES = ["info", "kontakt", "contact", "office", "sales", "tender", "nabavki", "admin", "podrska", "support", "marketing"]

# Contact page patterns
CONTACT_PATTERNS = ["/contact", "/kontakt", "/about", "/za-nas", "/about-us", "/company", "/kompanija"]

# Known major Macedonian company domains (for faster lookup)
KNOWN_COMPANIES = {
    "А1 МАКЕДОНИЈА": "a1.mk",
    "A1 МАКЕДОНИЈА": "a1.mk",
    "МАКПЕТРОЛ": "makpetrol.com.mk",
    "АЛКАЛОИД": "alkaloid.com.mk",
    "БИОТЕК": "biotek.mk",
    "ПРОМЕДИКА": "promedika.mk",
    "ФАРМАХЕМ": "farmahem.mk",
    "МАКЕДОНИЈАЛЕК": "makedonija-lek.mk",
    "ВИЗИОМЕД": "visiomed.com.mk",
    "ЗЕГИН": "zegin.mk",
    "ЕСМ": "esm.com.mk",
    "ОСИГУРИТЕЛНА ПОЛИСА": "sava.mk",
    "КУБИС": "kubis.mk",
    "МЕДИКОН": "medikon.mk",
    "ФАРМА ТРЕЈД": "farmatrade.mk",
    "ОФИС ПЛУС": "officeplus.mk",
    "АСТРА": "astra-m.mk",
}


class DirectEnrichmentService:
    """Direct enrichment without search API"""

    def __init__(self):
        self.http = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "mk,en;q=0.5"
            }
        )

    async def close(self):
        await self.http.aclose()

    def extract_brand_name(self, full_name: str) -> Optional[str]:
        """Extract the brand/trade name from full Macedonian company name"""
        # First check known companies
        for known, domain in KNOWN_COMPANIES.items():
            if known in full_name.upper():
                return known

        # Common patterns to extract brand names
        # Brand names are typically:
        # 1. All caps Latin letters (e.g., "BIOTEK", "PROMEDIKA")
        # 2. After "Друштво за..." before "ДООЕЛ/ДОО"
        # 3. Single prominent word in caps

        # Try to find Latin brand name (all caps)
        latin_pattern = r'\b([A-Z]{2,}(?:-[A-Z]+)?)\b'
        latin_matches = re.findall(latin_pattern, full_name)
        for match in latin_matches:
            if len(match) >= 3 and match not in ['ДООЕЛ', 'ДОО', 'АД', 'DOO', 'DOOEL']:
                return match

        # Try to find Cyrillic brand name (all caps, not common words)
        ignore_words = {'ДРУШТВО', 'ПРОИЗВОДСТВО', 'ТРГОВИЈА', 'УСЛУГИ', 'ПРОМЕТ', 'ИЗВОЗ', 'УВОЗ',
                       'СКОПЈЕ', 'БИТОЛА', 'ОХРИД', 'ДООЕЛ', 'ДОО', 'АД', 'АКЦИОНЕРСКО', 'ТРГОВСКО',
                       'НАЦИОНАЛНА', 'ГРУПАЦИЈА', 'ВНАТРЕШЕН', 'НАДВОРЕШЕН', 'КОМУНИКАЦИСКИ'}

        words = full_name.upper().split()
        for word in words:
            word = word.strip('.,()-')
            if len(word) >= 3 and word not in ignore_words:
                # Check if it looks like a brand (not a common word)
                if word.isupper() or word[0].isupper():
                    return word

        return None

    def transliterate(self, text: str) -> str:
        """Transliterate Macedonian Cyrillic to Latin"""
        cyrillic_to_latin = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'ѓ': 'gj', 'е': 'e',
            'ж': 'z', 'з': 'z', 'ѕ': 'dz', 'и': 'i', 'ј': 'j', 'к': 'k', 'л': 'l',
            'љ': 'lj', 'м': 'm', 'н': 'n', 'њ': 'nj', 'о': 'o', 'п': 'p', 'р': 'r',
            'с': 's', 'т': 't', 'ќ': 'kj', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c',
            'ч': 'ch', 'џ': 'dz', 'ш': 'sh',
            'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Ѓ': 'GJ', 'Е': 'E',
            'Ж': 'Z', 'З': 'Z', 'Ѕ': 'DZ', 'И': 'I', 'Ј': 'J', 'К': 'K', 'Л': 'L',
            'Љ': 'LJ', 'М': 'M', 'Н': 'N', 'Њ': 'NJ', 'О': 'O', 'П': 'P', 'Р': 'R',
            'С': 'S', 'Т': 'T', 'Ќ': 'KJ', 'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'C',
            'Ч': 'CH', 'Џ': 'DZ', 'Ш': 'SH'
        }
        result = ''
        for char in text:
            result += cyrillic_to_latin.get(char, char)
        return result

    def generate_domains(self, company_name: str) -> List[str]:
        """Generate likely domain names"""
        domains = []

        # Check known companies first
        for known, domain in KNOWN_COMPANIES.items():
            if known in company_name.upper():
                domains.append(f"https://www.{domain}")
                domains.append(f"https://{domain}")
                break

        # Extract brand name
        brand = self.extract_brand_name(company_name)
        if brand:
            # Transliterate if Cyrillic
            brand_latin = self.transliterate(brand).lower()
            brand_latin = re.sub(r'[^a-z0-9]', '', brand_latin)

            if len(brand_latin) >= 3:
                domains.extend([
                    f"https://www.{brand_latin}.mk",
                    f"https://{brand_latin}.mk",
                    f"https://www.{brand_latin}.com.mk",
                    f"https://{brand_latin}.com.mk",
                    f"https://www.{brand_latin}.com",
                ])

        return domains[:6]  # Limit to 6 guesses

    async def try_fetch(self, url: str) -> Optional[str]:
        """Try to fetch a page"""
        try:
            resp = await self.http.get(url, timeout=10.0)
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            pass
        return None

    def extract_emails(self, html: str, source_url: str) -> List[Dict]:
        """Extract emails from HTML"""
        emails = []
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

        found = set(re.findall(pattern, html.lower()))

        for email in found:
            if len(email) < 5 or len(email) > 100:
                continue
            if ".." in email or email.startswith("."):
                continue
            if any(x in email for x in ["example", "sentry", "wix", "schema", "w3.org", "google", "facebook"]):
                continue

            local = email.split("@")[0]
            email_type = "unknown"
            if any(local.startswith(p) or local == p for p in ROLE_BASED_PREFIXES):
                email_type = "role_based"
            elif "." in local:
                email_type = "personal"

            score = 50
            if any(p in source_url.lower() for p in CONTACT_PATTERNS):
                score += 40
            if email_type == "role_based":
                score += 10
            if ".mk" in email:
                score += 10

            emails.append({
                "email": email,
                "email_type": email_type,
                "source_url": source_url,
                "source_domain": urlparse(source_url).netloc,
                "confidence_score": min(100, score)
            })

        return emails

    async def find_contact_pages(self, base_url: str, html: str) -> List[str]:
        """Find contact page URLs"""
        urls = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"].lower()
                for pattern in CONTACT_PATTERNS:
                    if pattern in href:
                        full_url = urljoin(base_url, link["href"])
                        if full_url not in urls:
                            urls.append(full_url)
                        break
        except:
            pass
        return urls[:3]

    async def enrich_supplier(self, supplier_id: str, company_name: str) -> List[Dict]:
        """Enrich a single supplier"""
        all_emails = []

        domains = self.generate_domains(company_name)
        if not domains:
            logger.info(f"    No domains to try")
            return []

        logger.info(f"    Trying {len(domains)} domains")

        for url in domains:
            html = await self.try_fetch(url)
            if html:
                logger.info(f"    ✓ Found: {url}")
                emails = self.extract_emails(html, url)
                all_emails.extend(emails)

                # Try contact pages
                contact_pages = await self.find_contact_pages(url, html)
                for cp in contact_pages:
                    cp_html = await self.try_fetch(cp)
                    if cp_html:
                        emails = self.extract_emails(cp_html, cp)
                        all_emails.extend(emails)
                break
            await asyncio.sleep(0.2)

        # Dedupe
        seen = set()
        unique = []
        for e in all_emails:
            if e["email"] not in seen:
                seen.add(e["email"])
                unique.append(e)

        unique.sort(key=lambda x: -x["confidence_score"])
        return unique


async def run_enrichment(limit: int = 100):
    """Run enrichment for top suppliers"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    db = async_session()

    try:
        result = await db.execute(text("""
            SELECT s.supplier_id, s.company_name, s.total_wins
            FROM suppliers s
            LEFT JOIN supplier_contacts sc ON s.supplier_id = sc.supplier_id
            WHERE sc.id IS NULL
            ORDER BY s.total_wins DESC NULLS LAST
            LIMIT :limit
        """), {"limit": limit})

        suppliers = result.fetchall()
        logger.info(f"Found {len(suppliers)} suppliers to enrich")

        service = DirectEnrichmentService()
        stats = {"processed": 0, "emails_found": 0, "sites_found": 0}

        for supplier in suppliers:
            try:
                logger.info(f"\n[{stats['processed']+1}/{len(suppliers)}] {supplier.company_name[:60]}")
                emails = await service.enrich_supplier(str(supplier.supplier_id), supplier.company_name)

                if emails:
                    stats["sites_found"] += 1

                for email_data in emails:
                    try:
                        await db.execute(text("""
                            INSERT INTO supplier_contacts (supplier_id, email, email_type, source_url, source_domain, confidence_score, status)
                            VALUES (:supplier_id, :email, :email_type, :source_url, :source_domain, :confidence_score, 'new')
                            ON CONFLICT (supplier_id, email) DO UPDATE SET
                                confidence_score = EXCLUDED.confidence_score,
                                source_url = EXCLUDED.source_url,
                                updated_at = NOW()
                        """), {
                            "supplier_id": supplier.supplier_id,
                            "email": email_data["email"],
                            "email_type": email_data["email_type"],
                            "source_url": email_data.get("source_url"),
                            "source_domain": email_data.get("source_domain"),
                            "confidence_score": email_data["confidence_score"]
                        })
                        stats["emails_found"] += 1
                        logger.info(f"    ✓ {email_data['email']} ({email_data['email_type']}, score: {email_data['confidence_score']})")
                    except Exception as e:
                        logger.error(f"    Error storing: {e}")

                await db.commit()
                stats["processed"] += 1

            except Exception as e:
                logger.error(f"  Error: {e}")

            await asyncio.sleep(0.5)

        await service.close()
        await db.close()
        await engine.dispose()

        logger.info(f"\n{'='*60}")
        logger.info(f"ENRICHMENT COMPLETE")
        logger.info(f"Processed: {stats['processed']}")
        logger.info(f"Sites found: {stats['sites_found']}")
        logger.info(f"Emails found: {stats['emails_found']}")
        logger.info(f"{'='*60}")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        await db.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    asyncio.run(run_enrichment(args.limit))

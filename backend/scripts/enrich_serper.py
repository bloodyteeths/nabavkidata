#!/usr/bin/env python3
"""
Supplier Enrichment via Serper (Google Search API)
Finds company emails by searching Google for contact information.

Free tier: 2,500 searches/month
Get API key at: https://serper.dev

Run with: python3 scripts/enrich_serper.py --limit 100
"""
import os
import re
import sys
import asyncio
import argparse
import logging
from typing import List, Dict, Optional
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", os.getenv("DATABASE_URL"))
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

# Email extraction pattern
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Role-based prefixes (higher priority)
ROLE_BASED_PREFIXES = ["info", "kontakt", "contact", "office", "sales", "tender", "nabavki", "admin", "podrska", "support", "marketing"]

# Domains to ignore
IGNORE_DOMAINS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "mail.ru", "yandex.ru",
                  "example.com", "sentry.io", "wix.com", "w3.org", "schema.org", "google.com",
                  "facebook.com", "twitter.com", "instagram.com", "linkedin.com"]


class SerperEnrichment:
    """Enrich suppliers using Serper Google Search API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.http = httpx.AsyncClient(timeout=30.0)
        self.searches_used = 0

    async def close(self):
        await self.http.aclose()

    async def search_google(self, query: str) -> Optional[Dict]:
        """Search Google via Serper API"""
        if not self.api_key:
            logger.error("No Serper API key configured")
            return None

        try:
            response = await self.http.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "q": query,
                    "gl": "mk",  # Macedonia
                    "hl": "mk",  # Macedonian language
                    "num": 10   # Get 10 results
                }
            )
            self.searches_used += 1

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Serper API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Search error: {e}")
            return None

    def extract_emails_from_results(self, results: Dict, company_name: str) -> List[Dict]:
        """Extract emails from search results"""
        emails = []
        seen = set()

        # Check organic results
        for result in results.get("organic", []):
            text_to_search = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('link', '')}"
            found = re.findall(EMAIL_PATTERN, text_to_search.lower())

            for email in found:
                if email in seen:
                    continue
                if not self._is_valid_email(email):
                    continue

                seen.add(email)
                emails.append({
                    "email": email,
                    "source_url": result.get("link", ""),
                    "source_domain": self._extract_domain(result.get("link", "")),
                    "email_type": self._classify_email(email),
                    "confidence_score": self._calculate_score(email, result, company_name)
                })

        # Check knowledge graph if available
        if "knowledgeGraph" in results:
            kg = results["knowledgeGraph"]
            for field in ["email", "emails"]:
                if field in kg:
                    email = kg[field].lower()
                    if email not in seen and self._is_valid_email(email):
                        seen.add(email)
                        emails.append({
                            "email": email,
                            "source_url": "Google Knowledge Graph",
                            "source_domain": "google.com",
                            "email_type": self._classify_email(email),
                            "confidence_score": 95  # High confidence from knowledge graph
                        })

        # Check answer box
        if "answerBox" in results:
            ab_text = str(results["answerBox"])
            found = re.findall(EMAIL_PATTERN, ab_text.lower())
            for email in found:
                if email not in seen and self._is_valid_email(email):
                    seen.add(email)
                    emails.append({
                        "email": email,
                        "source_url": "Google Answer Box",
                        "source_domain": "google.com",
                        "email_type": self._classify_email(email),
                        "confidence_score": 90
                    })

        # Sort by confidence score
        emails.sort(key=lambda x: -x["confidence_score"])
        return emails

    def _is_valid_email(self, email: str) -> bool:
        """Check if email is valid and not from ignored domains"""
        if len(email) < 5 or len(email) > 100:
            return False
        if ".." in email or email.startswith("."):
            return False

        domain = email.split("@")[-1]
        if domain in IGNORE_DOMAINS:
            return False

        # Ignore image/file extensions
        if any(ext in email for ext in [".png", ".jpg", ".gif", ".svg", ".pdf"]):
            return False

        return True

    def _classify_email(self, email: str) -> str:
        """Classify email as role_based, personal, or unknown"""
        local = email.split("@")[0].lower()

        if any(local.startswith(p) or local == p for p in ROLE_BASED_PREFIXES):
            return "role_based"
        elif "." in local:
            return "personal"
        return "unknown"

    def _calculate_score(self, email: str, result: Dict, company_name: str) -> int:
        """Calculate confidence score for email"""
        score = 50

        # Bonus for .mk domain
        if ".mk" in email:
            score += 20

        # Bonus for role-based email
        if self._classify_email(email) == "role_based":
            score += 15

        # Bonus if company name appears in domain
        company_words = company_name.lower().split()[:3]
        email_domain = email.split("@")[-1].lower()
        for word in company_words:
            if len(word) > 3 and word in email_domain:
                score += 10
                break

        # Bonus for contact/about pages
        link = result.get("link", "").lower()
        if any(p in link for p in ["/contact", "/kontakt", "/about", "/za-nas"]):
            score += 10

        return min(100, score)

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return ""

    async def enrich_supplier(self, company_name: str) -> List[Dict]:
        """Search for supplier emails using multiple queries"""
        all_emails = []
        seen_emails = set()

        # Try different search queries
        queries = [
            f'"{company_name}" email контакт',
            f'"{company_name}" @.mk',
            f'{company_name} контакт е-маил'
        ]

        for query in queries[:2]:  # Limit to 2 queries per company to save API calls
            results = await self.search_google(query)
            if results:
                emails = self.extract_emails_from_results(results, company_name)
                for e in emails:
                    if e["email"] not in seen_emails:
                        seen_emails.add(e["email"])
                        all_emails.append(e)

            if all_emails:  # Stop if we found emails
                break

            await asyncio.sleep(0.5)  # Rate limiting

        return all_emails


async def run_enrichment(limit: int = 100):
    """Run Serper-based enrichment"""
    if not SERPER_API_KEY:
        logger.error("SERPER_API_KEY environment variable not set!")
        logger.info("Get your free API key at: https://serper.dev")
        return

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    db = async_session()

    try:
        # Get suppliers without contacts, ordered by wins
        result = await db.execute(text("""
            SELECT s.supplier_id, s.company_name, s.total_wins
            FROM suppliers s
            LEFT JOIN supplier_contacts sc ON s.supplier_id = sc.supplier_id
            WHERE sc.id IS NULL
              AND s.total_wins > 0
            ORDER BY s.total_wins DESC NULLS LAST
            LIMIT :limit
        """), {"limit": limit})

        suppliers = result.fetchall()
        logger.info(f"Found {len(suppliers)} suppliers to enrich")

        if not suppliers:
            logger.info("No suppliers need enrichment")
            return

        service = SerperEnrichment(SERPER_API_KEY)
        stats = {"processed": 0, "emails_found": 0, "suppliers_with_emails": 0}

        for i, supplier in enumerate(suppliers):
            try:
                company_short = supplier.company_name[:60] + "..." if len(supplier.company_name) > 60 else supplier.company_name
                logger.info(f"\n[{i+1}/{len(suppliers)}] {company_short} (wins: {supplier.total_wins})")

                emails = await service.enrich_supplier(supplier.company_name)

                if emails:
                    stats["suppliers_with_emails"] += 1

                    for email_data in emails[:3]:  # Store up to 3 emails per supplier
                        try:
                            await db.execute(text("""
                                INSERT INTO supplier_contacts
                                (supplier_id, email, email_type, source_url, source_domain, confidence_score, status)
                                VALUES (:supplier_id, :email, :email_type, :source_url, :source_domain, :confidence_score, 'new')
                                ON CONFLICT (supplier_id, email) DO UPDATE SET
                                    confidence_score = GREATEST(supplier_contacts.confidence_score, EXCLUDED.confidence_score),
                                    source_url = EXCLUDED.source_url,
                                    updated_at = NOW()
                            """), {
                                "supplier_id": supplier.supplier_id,
                                "email": email_data["email"],
                                "email_type": email_data["email_type"],
                                "source_url": email_data.get("source_url", ""),
                                "source_domain": email_data.get("source_domain", ""),
                                "confidence_score": email_data["confidence_score"]
                            })
                            stats["emails_found"] += 1
                            logger.info(f"    + {email_data['email']} ({email_data['email_type']}, score: {email_data['confidence_score']})")
                        except Exception as e:
                            logger.error(f"    Error storing email: {e}")

                    await db.commit()
                else:
                    logger.info(f"    No emails found")

                stats["processed"] += 1

                # Rate limiting
                await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(f"  Error processing supplier: {e}")

        await service.close()

        logger.info(f"\n{'='*60}")
        logger.info("SERPER ENRICHMENT COMPLETE")
        logger.info(f"Processed: {stats['processed']}")
        logger.info(f"Suppliers with emails: {stats['suppliers_with_emails']}")
        logger.info(f"Total emails found: {stats['emails_found']}")
        logger.info(f"Serper API calls used: {service.searches_used}")
        logger.info(f"{'='*60}")

    finally:
        await db.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100, help="Max suppliers to process")
    args = parser.parse_args()

    asyncio.run(run_enrichment(args.limit))

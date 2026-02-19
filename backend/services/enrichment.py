"""
Supplier Contact Enrichment Service
Searches for publicly available business contact information
"""
import os
import re
import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.dialects.postgresql import insert

from models import Supplier, SupplierContact, EnrichmentJob, SuppressionList

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SEARCH_API_PROVIDER = os.getenv("SEARCH_API_PROVIDER", "bing")  # bing, serpapi, google_cse
BING_KEY = os.getenv("BING_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
GOOGLE_CSE_KEY = os.getenv("GOOGLE_CSE_KEY", "")
GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX", "")

ENRICH_SEARCH_RESULTS = int(os.getenv("ENRICH_SEARCH_RESULTS", "5"))
ENRICH_CRAWL_DEPTH = int(os.getenv("ENRICH_CRAWL_DEPTH", "1"))

# Role-based email prefixes (preferred for outreach)
ROLE_BASED_PREFIXES = [
    "info", "kontakt", "contact", "office", "sales", "tender", "nabavki",
    "admin", "bizdev", "podrska", "support", "marketing", "hello", "team"
]

# Disposable/free email domains (low confidence)
FREE_EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com",
    "mail.com", "aol.com", "icloud.com", "protonmail.com", "yandex.com"
]

# Contact page URL patterns
CONTACT_PAGE_PATTERNS = [
    "/contact", "/kontakt", "/about", "/za-nas", "/about-us",
    "/company", "/kompanija", "/info", "/footer"
]


class EnrichmentService:
    """Service for enriching supplier contacts via web search"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.http_client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; NabavkiData/1.0; +https://nabavkidata.com)"
            }
        )

    async def close(self):
        await self.http_client.aclose()

    # ========================================================================
    # MAIN ENRICHMENT FLOW
    # ========================================================================

    async def enrich_supplier(self, supplier_id: str) -> Dict:
        """
        Main enrichment function for a single supplier.
        Returns stats about discovered emails.
        """
        # Get supplier
        result = await self.db.execute(
            select(Supplier).where(Supplier.supplier_id == supplier_id)
        )
        supplier = result.scalar_one_or_none()

        if not supplier:
            return {"error": "Supplier not found", "supplier_id": supplier_id}

        # Create enrichment job
        job = EnrichmentJob(
            supplier_id=supplier.supplier_id,
            status="processing",
            started_at=datetime.utcnow()
        )
        self.db.add(job)
        await self.db.commit()

        try:
            # Build search queries
            queries = self._build_search_queries(supplier.company_name)
            job.search_queries = queries

            # Execute searches
            all_results = []
            for query in queries[:3]:  # Limit to 3 queries
                results = await self._search(query)
                all_results.extend(results)
                await asyncio.sleep(0.5)  # Rate limiting

            job.results_count = len(all_results)

            # Dedupe by domain
            unique_urls = self._dedupe_urls(all_results)

            # Crawl and extract emails
            all_emails = []
            for url in unique_urls[:ENRICH_SEARCH_RESULTS]:
                emails = await self._extract_emails_from_url(url, supplier.company_name)
                all_emails.extend(emails)

            # Dedupe and score emails
            scored_emails = self._score_and_dedupe_emails(all_emails, supplier.company_name)

            # Store contacts
            stored_count = await self._store_contacts(supplier.supplier_id, scored_emails)

            job.emails_found = stored_count
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            await self.db.commit()

            return {
                "supplier_id": str(supplier.supplier_id),
                "company_name": supplier.company_name,
                "queries_executed": len(queries[:3]),
                "urls_crawled": len(unique_urls[:ENRICH_SEARCH_RESULTS]),
                "emails_found": stored_count
            }

        except Exception as e:
            logger.error(f"Enrichment failed for {supplier_id}: {e}")
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            await self.db.commit()
            return {"error": str(e), "supplier_id": supplier_id}

    # ========================================================================
    # SEARCH API ADAPTERS
    # ========================================================================

    def _build_search_queries(self, company_name: str) -> List[str]:
        """Build search queries from company name"""
        # Clean company name
        name = company_name.strip()

        return [
            f'"{name}" Macedonia contact email',
            f'"{name}" MK kontakt email',
            f'"{name}" company website',
            f'{name} tender company contact Macedonia',
        ]

    async def _search(self, query: str) -> List[Dict]:
        """Execute search using configured provider"""
        if SEARCH_API_PROVIDER == "bing" and BING_KEY:
            return await self._search_bing(query)
        elif SEARCH_API_PROVIDER == "serpapi" and SERPAPI_KEY:
            return await self._search_serpapi(query)
        elif SEARCH_API_PROVIDER == "google_cse" and GOOGLE_CSE_KEY:
            return await self._search_google_cse(query)
        else:
            logger.warning("No search API configured, returning empty results")
            return []

    async def _search_bing(self, query: str) -> List[Dict]:
        """Search using Bing Web Search API"""
        try:
            resp = await self.http_client.get(
                "https://api.bing.microsoft.com/v7.0/search",
                params={"q": query, "count": ENRICH_SEARCH_RESULTS, "mkt": "en-US"},
                headers={"Ocp-Apim-Subscription-Key": BING_KEY}
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("webPages", {}).get("value", []):
                results.append({
                    "url": item.get("url"),
                    "title": item.get("name"),
                    "snippet": item.get("snippet")
                })
            return results
        except Exception as e:
            logger.error(f"Bing search error: {e}")
            return []

    async def _search_serpapi(self, query: str) -> List[Dict]:
        """Search using SerpAPI"""
        try:
            resp = await self.http_client.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": SERPAPI_KEY,
                    "num": ENRICH_SEARCH_RESULTS,
                    "engine": "google"
                }
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("organic_results", []):
                results.append({
                    "url": item.get("link"),
                    "title": item.get("title"),
                    "snippet": item.get("snippet")
                })
            return results
        except Exception as e:
            logger.error(f"SerpAPI search error: {e}")
            return []

    async def _search_google_cse(self, query: str) -> List[Dict]:
        """Search using Google Custom Search Engine"""
        try:
            resp = await self.http_client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "q": query,
                    "key": GOOGLE_CSE_KEY,
                    "cx": GOOGLE_CSE_CX,
                    "num": ENRICH_SEARCH_RESULTS
                }
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("items", []):
                results.append({
                    "url": item.get("link"),
                    "title": item.get("title"),
                    "snippet": item.get("snippet")
                })
            return results
        except Exception as e:
            logger.error(f"Google CSE search error: {e}")
            return []

    # ========================================================================
    # URL PROCESSING
    # ========================================================================

    def _dedupe_urls(self, results: List[Dict]) -> List[str]:
        """Deduplicate URLs by domain, preferring official-looking domains"""
        seen_domains = set()
        unique_urls = []

        for result in results:
            url = result.get("url")
            if not url:
                continue

            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()

                # Skip social media and irrelevant sites
                skip_domains = [
                    "facebook.com", "linkedin.com", "twitter.com", "instagram.com",
                    "youtube.com", "wikipedia.org", "pdf", "gov.mk"
                ]
                if any(skip in domain for skip in skip_domains):
                    continue

                if domain not in seen_domains:
                    seen_domains.add(domain)
                    unique_urls.append(url)
            except:
                continue

        return unique_urls

    # ========================================================================
    # EMAIL EXTRACTION
    # ========================================================================

    async def _extract_emails_from_url(self, url: str, company_name: str) -> List[Dict]:
        """Extract emails from a URL and its contact pages"""
        emails = []

        try:
            # Fetch main page
            resp = await self.http_client.get(url)
            if resp.status_code != 200:
                return emails

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            # Extract from main page
            page_emails = self._extract_emails_from_html(html, url)
            emails.extend(page_emails)

            # Find and crawl contact pages (depth 1)
            if ENRICH_CRAWL_DEPTH >= 1:
                contact_urls = self._find_contact_pages(soup, url)
                for contact_url in contact_urls[:3]:
                    try:
                        resp2 = await self.http_client.get(contact_url)
                        if resp2.status_code == 200:
                            page_emails = self._extract_emails_from_html(resp2.text, contact_url)
                            emails.extend(page_emails)
                    except:
                        continue
                    await asyncio.sleep(0.3)

        except Exception as e:
            logger.debug(f"Error extracting from {url}: {e}")

        return emails

    def _find_contact_pages(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Find contact page URLs from a page"""
        contact_urls = []

        for link in soup.find_all("a", href=True):
            href = link["href"].lower()

            for pattern in CONTACT_PAGE_PATTERNS:
                if pattern in href:
                    full_url = urljoin(base_url, link["href"])
                    if full_url not in contact_urls:
                        contact_urls.append(full_url)
                    break

        return contact_urls

    def _extract_emails_from_html(self, html: str, source_url: str) -> List[Dict]:
        """Extract and deobfuscate emails from HTML"""
        emails = []

        # Standard email regex
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

        # Find standard emails
        found = re.findall(email_pattern, html)

        # Deobfuscation patterns
        # Pattern: name [at] domain [dot] com
        obfuscated_pattern = r'([a-zA-Z0-9._%+-]+)\s*[\[\(]?\s*at\s*[\]\)]?\s*([a-zA-Z0-9.-]+)\s*[\[\(]?\s*dot\s*[\]\)]?\s*([a-zA-Z]{2,})'
        obfuscated = re.findall(obfuscated_pattern, html, re.IGNORECASE)
        for match in obfuscated:
            email = f"{match[0]}@{match[1]}.{match[2]}"
            found.append(email)

        # Pattern: name (at) domain (dot) com
        obfuscated_pattern2 = r'([a-zA-Z0-9._%+-]+)\s*\(at\)\s*([a-zA-Z0-9.-]+)\s*\(dot\)\s*([a-zA-Z]{2,})'
        obfuscated2 = re.findall(obfuscated_pattern2, html, re.IGNORECASE)
        for match in obfuscated2:
            email = f"{match[0]}@{match[1]}.{match[2]}"
            found.append(email)

        # Normalize and dedupe
        parsed = urlparse(source_url)
        domain = parsed.netloc.lower()

        seen = set()
        for email in found:
            email = email.lower().strip()

            # Skip invalid emails
            if len(email) > 254 or len(email) < 5:
                continue
            if ".." in email or email.startswith(".") or email.endswith("."):
                continue
            if "example.com" in email or "sentry" in email:
                continue

            if email not in seen:
                seen.add(email)
                emails.append({
                    "email": email,
                    "source_url": source_url,
                    "source_domain": domain
                })

        return emails

    # ========================================================================
    # SCORING AND CLASSIFICATION
    # ========================================================================

    def _score_and_dedupe_emails(self, emails: List[Dict], company_name: str) -> List[Dict]:
        """Score, classify, and dedupe discovered emails"""
        email_map = {}

        # Normalize company name for matching
        company_words = set(
            re.sub(r'[^\w\s]', '', company_name.lower()).split()
        )

        for email_data in emails:
            email = email_data["email"]
            source_url = email_data.get("source_url", "")
            source_domain = email_data.get("source_domain", "")

            # Skip if already processed with higher score
            if email in email_map and email_map[email]["confidence_score"] >= 50:
                continue

            # Calculate confidence score
            score = 50  # Base score

            # Check if on contact page
            if any(p in source_url.lower() for p in CONTACT_PAGE_PATTERNS):
                score += 40

            # Check if domain matches company name
            email_domain = email.split("@")[1] if "@" in email else ""
            domain_words = set(re.sub(r'[^\w]', '', email_domain.lower()).split("."))
            if company_words & domain_words:
                score += 20

            # Check if it's a free email provider (lower score)
            if any(email.endswith(f"@{d}") for d in FREE_EMAIL_DOMAINS):
                score -= 50

            # Determine email type
            local_part = email.split("@")[0].lower() if "@" in email else ""
            email_type = "unknown"

            if any(local_part.startswith(prefix) or local_part == prefix for prefix in ROLE_BASED_PREFIXES):
                email_type = "role_based"
                score += 10  # Prefer role-based
            elif "." in local_part or re.match(r'^[a-z]+[a-z]+$', local_part):
                # Looks like firstname.lastname or firstname
                email_type = "personal"

            # Cap score
            score = max(0, min(100, score))

            email_map[email] = {
                "email": email,
                "email_type": email_type,
                "source_url": source_url,
                "source_domain": source_domain,
                "confidence_score": score
            }

        # Sort by confidence (highest first)
        return sorted(email_map.values(), key=lambda x: -x["confidence_score"])

    # ========================================================================
    # DATABASE OPERATIONS
    # ========================================================================

    async def _store_contacts(self, supplier_id, emails: List[Dict]) -> int:
        """Store discovered contacts, avoiding duplicates"""
        stored = 0

        for email_data in emails:
            try:
                # Check suppression list
                suppressed = await self.db.execute(
                    select(SuppressionList).where(
                        SuppressionList.email == email_data["email"]
                    )
                )
                if suppressed.scalar_one_or_none():
                    continue

                # Upsert contact
                stmt = insert(SupplierContact).values(
                    supplier_id=supplier_id,
                    email=email_data["email"],
                    email_type=email_data["email_type"],
                    source_url=email_data.get("source_url"),
                    source_domain=email_data.get("source_domain"),
                    confidence_score=email_data["confidence_score"],
                    status="new"
                ).on_conflict_do_update(
                    index_elements=["supplier_id", "email"],
                    set_={
                        "confidence_score": email_data["confidence_score"],
                        "source_url": email_data.get("source_url"),
                        "updated_at": datetime.utcnow()
                    }
                )
                await self.db.execute(stmt)
                stored += 1

            except Exception as e:
                logger.error(f"Error storing contact {email_data['email']}: {e}")

        await self.db.commit()
        return stored


# ============================================================================
# BATCH ENRICHMENT
# ============================================================================

async def enrich_top_suppliers(db: AsyncSession, limit: int = 500) -> Dict:
    """Enrich top suppliers missing email contacts"""

    # Find suppliers without contacts, ordered by wins
    query = """
        SELECT s.supplier_id, s.company_name, s.total_wins
        FROM suppliers s
        LEFT JOIN supplier_contacts sc ON s.supplier_id = sc.supplier_id
        WHERE sc.id IS NULL
        ORDER BY s.total_wins DESC NULLS LAST
        LIMIT :limit
    """

    result = await db.execute(select(Supplier).order_by(Supplier.total_wins.desc()).limit(limit))
    suppliers = result.scalars().all()

    # Filter to those without contacts
    suppliers_to_enrich = []
    for supplier in suppliers:
        contacts = await db.execute(
            select(SupplierContact).where(SupplierContact.supplier_id == supplier.supplier_id).limit(1)
        )
        if not contacts.scalar_one_or_none():
            suppliers_to_enrich.append(supplier)

    service = EnrichmentService(db)
    stats = {
        "total": len(suppliers_to_enrich),
        "processed": 0,
        "emails_found": 0,
        "errors": 0
    }

    for supplier in suppliers_to_enrich[:limit]:
        try:
            result = await service.enrich_supplier(str(supplier.supplier_id))
            stats["processed"] += 1
            stats["emails_found"] += result.get("emails_found", 0)
        except Exception as e:
            logger.error(f"Error enriching {supplier.company_name}: {e}")
            stats["errors"] += 1

        # Rate limiting
        await asyncio.sleep(1)

    await service.close()
    return stats

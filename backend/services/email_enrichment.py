"""
Email Enrichment Service using Gemini API with Google Search
Searches for company emails using web search and extracts contact information
"""
import os
import re
import json
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid

import httpx
import asyncpg

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")  # Alternative to Gemini search

# Confidence thresholds
HIGH_CONFIDENCE = 80
MEDIUM_CONFIDENCE = 50
LOW_CONFIDENCE = 30

# Role-based email prefixes (preferred for B2B outreach)
ROLE_BASED_PREFIXES = [
    "info", "kontakt", "contact", "office", "sales", "tender", "nabavki",
    "admin", "bizdev", "support", "marketing", "hello", "team", "direktor"
]

# Free email domains (lower confidence)
FREE_EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com",
    "mail.com", "aol.com", "icloud.com", "protonmail.com", "yandex.com"
]


# ============================================================================
# GEMINI SEARCH INTEGRATION
# ============================================================================

class GeminiEmailSearcher:
    """Uses Gemini API with Google Search grounding to find company emails"""

    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model = "gemini-2.0-flash-exp"  # Supports Google Search grounding
        self.http_client = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        await self.http_client.aclose()

    async def search_company_email(self, company_name: str, country: str = "North Macedonia") -> Dict:
        """Search for company email using Gemini with Google Search grounding"""
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not configured")
            return {"success": False, "error": "API key not configured"}

        prompt = f"""Search for the business contact email address for the company "{company_name}" in {country}.

Look for:
1. Official company website contact page
2. Business directories listing this company
3. LinkedIn company page
4. Yellow pages or chamber of commerce listings

Return ONLY a JSON object with this exact structure (no markdown, no explanation):
{{
    "company_name": "{company_name}",
    "emails_found": [
        {{
            "email": "example@domain.com",
            "source": "where you found it",
            "confidence": "high/medium/low"
        }}
    ],
    "website": "company website if found",
    "notes": "any relevant notes"
}}

If no email is found, return emails_found as an empty array.
Only return valid email addresses that appear to belong to this specific company."""

        try:
            url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 1024
                }
            }

            response = await self.http_client.post(url, json=payload)

            if response.status_code != 200:
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                return {"success": False, "error": f"API error: {response.status_code}"}

            data = response.json()

            # Extract text from response
            candidates = data.get("candidates", [])
            if not candidates:
                return {"success": False, "error": "No response from Gemini"}

            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            # Parse JSON from response
            # Remove markdown code blocks if present
            text = re.sub(r'^```json\s*', '', text.strip())
            text = re.sub(r'\s*```$', '', text)

            try:
                result = json.loads(text)
                return {
                    "success": True,
                    "data": result,
                    "grounding_metadata": data.get("candidates", [{}])[0].get("groundingMetadata", {})
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini response: {text[:200]}")
                # Try to extract email with regex as fallback
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
                if emails:
                    return {
                        "success": True,
                        "data": {
                            "company_name": company_name,
                            "emails_found": [{"email": e, "source": "gemini_extraction", "confidence": "medium"} for e in emails[:3]],
                            "notes": "Extracted via regex fallback"
                        }
                    }
                return {"success": False, "error": f"Failed to parse response: {str(e)}"}

        except Exception as e:
            logger.error(f"Gemini search error for {company_name}: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# SERPER API INTEGRATION (Alternative)
# ============================================================================

class SerperEmailSearcher:
    """Uses Serper.dev API to search for company emails"""

    def __init__(self):
        self.api_key = SERPER_API_KEY
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.http_client.aclose()

    async def search_company_email(self, company_name: str, country: str = "North Macedonia") -> Dict:
        """Search for company email using Serper Google Search API"""
        if not self.api_key:
            logger.warning("SERPER_API_KEY not configured")
            return {"success": False, "error": "API key not configured"}

        # Try multiple search queries
        queries = [
            f'"{company_name}" Macedonia contact email',
            f'"{company_name}" MK kontakt email',
            f'{company_name} company website contact',
        ]

        all_emails = []

        for query in queries[:2]:  # Limit to 2 queries to save API calls
            try:
                response = await self.http_client.post(
                    "https://google.serper.dev/search",
                    headers={
                        "X-API-KEY": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={"q": query, "num": 5}
                )

                if response.status_code != 200:
                    continue

                data = response.json()

                # Extract emails from snippets and links
                for result in data.get("organic", []):
                    snippet = result.get("snippet", "") + " " + result.get("title", "")
                    link = result.get("link", "")

                    # Find emails in snippet
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                    for email in emails:
                        all_emails.append({
                            "email": email.lower(),
                            "source": link,
                            "confidence": "medium"
                        })

                await asyncio.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.error(f"Serper search error: {e}")
                continue

        # Dedupe and score emails
        seen = set()
        unique_emails = []
        for e in all_emails:
            if e["email"] not in seen:
                seen.add(e["email"])
                unique_emails.append(e)

        return {
            "success": True,
            "data": {
                "company_name": company_name,
                "emails_found": unique_emails[:5],
                "notes": f"Found via Serper search ({len(unique_emails)} unique)"
            }
        }


# ============================================================================
# EMAIL SCORING AND VALIDATION
# ============================================================================

def score_email(email: str, company_name: str, source: str = "") -> int:
    """Score an email based on relevance and quality (0-100)"""
    score = 50  # Base score

    email = email.lower()
    local_part = email.split("@")[0] if "@" in email else ""
    domain = email.split("@")[1] if "@" in email else ""

    # Penalize free email providers
    if any(email.endswith(f"@{d}") for d in FREE_EMAIL_DOMAINS):
        score -= 40

    # Bonus for role-based emails
    if any(local_part.startswith(prefix) or local_part == prefix for prefix in ROLE_BASED_PREFIXES):
        score += 20

    # Bonus if domain contains company name parts
    company_words = set(re.sub(r'[^\w\s]', '', company_name.lower()).split())
    domain_clean = re.sub(r'[^\w]', '', domain.lower())
    for word in company_words:
        if len(word) > 3 and word in domain_clean:
            score += 15
            break

    # Bonus for contact page source
    if source and any(p in source.lower() for p in ["contact", "kontakt", "about", "za-nas"]):
        score += 10

    # Penalize suspicious patterns
    if len(local_part) < 3 or len(local_part) > 50:
        score -= 20
    if ".." in email or email.startswith(".") or email.endswith("."):
        score -= 30

    return max(0, min(100, score))


def classify_email_type(email: str) -> str:
    """Classify email as role_based, personal, or unknown"""
    local_part = email.split("@")[0].lower() if "@" in email else ""

    if any(local_part.startswith(prefix) or local_part == prefix for prefix in ROLE_BASED_PREFIXES):
        return "role_based"
    elif "." in local_part or re.match(r'^[a-z]+[a-z]+$', local_part):
        return "personal"
    return "unknown"


# ============================================================================
# MAIN ENRICHMENT SERVICE
# ============================================================================

class EmailEnrichmentService:
    """Main service for enriching company emails using multiple sources"""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.gemini_searcher = GeminiEmailSearcher()
        self.serper_searcher = SerperEmailSearcher()

    async def close(self):
        await self.gemini_searcher.close()
        await self.serper_searcher.close()

    async def enrich_company(
        self,
        company_name: str,
        company_tax_id: Optional[str] = None,
        company_id: Optional[str] = None
    ) -> Dict:
        """Find email for a company using web search"""
        logger.info(f"Enriching email for: {company_name}")

        # Check if already in queue with results
        async with self.pool.acquire() as conn:
            existing = await conn.fetchrow("""
                SELECT * FROM email_enrichment_queue
                WHERE company_name = $1
                  AND (status = 'found' OR (status = 'searching' AND updated_at > NOW() - INTERVAL '1 hour'))
            """, company_name)

            if existing and existing['selected_email']:
                return {
                    "success": True,
                    "email": existing['selected_email'],
                    "source": "cache",
                    "company_name": company_name
                }

        # Create or update queue entry
        queue_id = str(uuid.uuid4())
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO email_enrichment_queue (id, company_name, company_tax_id, company_id, status)
                VALUES ($1, $2, $3, $4, 'searching')
                ON CONFLICT (company_name) DO UPDATE SET
                    status = 'searching',
                    search_attempts = email_enrichment_queue.search_attempts + 1,
                    last_search_at = NOW(),
                    updated_at = NOW()
            """, uuid.UUID(queue_id), company_name, company_tax_id,
                uuid.UUID(company_id) if company_id else None)

        all_emails = []

        # Try Gemini first (better quality with grounding)
        if GEMINI_API_KEY:
            result = await self.gemini_searcher.search_company_email(company_name)
            if result.get("success") and result.get("data", {}).get("emails_found"):
                for e in result["data"]["emails_found"]:
                    all_emails.append({
                        "email": e["email"].lower(),
                        "source": e.get("source", "gemini"),
                        "raw_confidence": e.get("confidence", "medium")
                    })

        # Fallback to Serper if no results
        if not all_emails and SERPER_API_KEY:
            result = await self.serper_searcher.search_company_email(company_name)
            if result.get("success") and result.get("data", {}).get("emails_found"):
                for e in result["data"]["emails_found"]:
                    all_emails.append({
                        "email": e["email"].lower(),
                        "source": e.get("source", "serper"),
                        "raw_confidence": e.get("confidence", "medium")
                    })

        # Score and sort emails
        scored_emails = []
        for e in all_emails:
            # Skip invalid
            if not e["email"] or "@" not in e["email"]:
                continue
            # Skip duplicates
            if any(se["email"] == e["email"] for se in scored_emails):
                continue

            score = score_email(e["email"], company_name, e.get("source", ""))
            email_type = classify_email_type(e["email"])

            scored_emails.append({
                "email": e["email"],
                "score": score,
                "type": email_type,
                "source": e.get("source", "unknown")
            })

        # Sort by score descending
        scored_emails.sort(key=lambda x: -x["score"])

        # Select best email
        selected_email = None
        if scored_emails:
            # Prefer role-based with score >= 50
            for e in scored_emails:
                if e["type"] == "role_based" and e["score"] >= 50:
                    selected_email = e["email"]
                    break
            # Fallback to any with score >= 40
            if not selected_email:
                for e in scored_emails:
                    if e["score"] >= 40:
                        selected_email = e["email"]
                        break
            # Last resort: best score
            if not selected_email and scored_emails:
                selected_email = scored_emails[0]["email"]

        # Update queue with results
        status = "found" if selected_email else "not_found"
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE email_enrichment_queue
                SET status = $1,
                    emails_found = $2,
                    selected_email = $3,
                    updated_at = NOW()
                WHERE company_name = $4
            """, status, json.dumps(scored_emails), selected_email, company_name)

        if selected_email:
            logger.info(f"Found email for {company_name}: {selected_email}")
            return {
                "success": True,
                "email": selected_email,
                "all_emails": scored_emails,
                "source": "web_search",
                "company_name": company_name
            }
        else:
            logger.info(f"No email found for {company_name}")
            return {
                "success": False,
                "error": "No email found",
                "all_emails": scored_emails,
                "company_name": company_name
            }

    async def enrich_batch(
        self,
        companies: List[Dict],
        max_concurrent: int = 5,
        delay_seconds: float = 2.0
    ) -> Dict:
        """Enrich multiple companies with rate limiting"""
        stats = {
            "total": len(companies),
            "success": 0,
            "failed": 0,
            "results": []
        }

        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_with_limit(company: Dict):
            async with semaphore:
                result = await self.enrich_company(
                    company_name=company["company_name"],
                    company_tax_id=company.get("company_tax_id"),
                    company_id=company.get("company_id")
                )
                await asyncio.sleep(delay_seconds)  # Rate limiting
                return result

        tasks = [enrich_with_limit(c) for c in companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                stats["failed"] += 1
                stats["results"].append({
                    "company_name": companies[i]["company_name"],
                    "success": False,
                    "error": str(result)
                })
            elif result.get("success"):
                stats["success"] += 1
                stats["results"].append(result)
            else:
                stats["failed"] += 1
                stats["results"].append(result)

        return stats


# ============================================================================
# TOP 100 COMPANY SELECTION
# ============================================================================

async def select_top_companies(
    pool: asyncpg.Pool,
    min_participations: int = 5,
    min_wins: int = 2,
    lookback_days: int = 365,
    exclude_contacted_days: int = 90,
    limit: int = 100
) -> List[Dict]:
    """
    Select top companies for outreach based on tender activity.
    Excludes:
    - Companies without email (to be enriched separately)
    - Companies contacted in last 90 days
    - Unsubscribed/bounced emails
    """
    cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
    contacted_cutoff = datetime.utcnow() - timedelta(days=exclude_contacted_days)

    async with pool.acquire() as conn:
        query = """
            WITH company_stats AS (
                SELECT
                    tb.company_name,
                    tb.company_tax_id,
                    COUNT(DISTINCT tb.tender_id) as participations,
                    COUNT(DISTINCT CASE WHEN tb.is_winner THEN tb.tender_id END) as wins,
                    COALESCE(SUM(CASE WHEN tb.is_winner THEN t.actual_value_mkd END), 0) as total_value,
                    MAX(t.publication_date) as last_activity
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE t.publication_date >= $1
                  AND tb.company_name IS NOT NULL
                  AND LENGTH(TRIM(tb.company_name)) > 3
                GROUP BY tb.company_name, tb.company_tax_id
                HAVING COUNT(DISTINCT tb.tender_id) >= $2
                   AND COUNT(DISTINCT CASE WHEN tb.is_winner THEN tb.tender_id END) >= $3
            )
            SELECT
                cs.*,
                s.supplier_id,
                COALESCE(sc.email, eq.selected_email) as email,
                sc.confidence_score as email_confidence
            FROM company_stats cs
            LEFT JOIN suppliers s ON (
                s.company_name ILIKE cs.company_name
                OR s.tax_id = cs.company_tax_id
            )
            LEFT JOIN supplier_contacts sc ON (
                sc.supplier_id = s.supplier_id
                AND sc.status IN ('new', 'verified')
            )
            LEFT JOIN email_enrichment_queue eq ON (
                eq.company_name = cs.company_name
                AND eq.status = 'found'
            )
            -- Exclude suppressed emails
            LEFT JOIN suppression_list sl ON (
                sl.email = COALESCE(sc.email, eq.selected_email)
            )
            LEFT JOIN campaign_unsubscribes cu ON (
                cu.email = COALESCE(sc.email, eq.selected_email)
            )
            -- Exclude recently contacted
            LEFT JOIN campaign_targets ct ON (
                ct.company_name = cs.company_name
                AND ct.initial_sent_at >= $4
            )
            WHERE sl.id IS NULL  -- Not suppressed
              AND cu.id IS NULL  -- Not unsubscribed
              AND ct.id IS NULL  -- Not recently contacted
            ORDER BY
                cs.wins DESC,
                cs.total_value DESC,
                cs.participations DESC
            LIMIT $5
        """

        rows = await conn.fetch(
            query, cutoff_date, min_participations, min_wins, contacted_cutoff, limit * 2
        )

        companies = []
        for row in rows:
            if len(companies) >= limit:
                break

            companies.append({
                "company_name": row['company_name'],
                "company_tax_id": row['company_tax_id'],
                "company_id": str(row['supplier_id']) if row['supplier_id'] else None,
                "email": row['email'],
                "email_confidence": row['email_confidence'],
                "participations": row['participations'],
                "wins": row['wins'],
                "total_value": float(row['total_value'] or 0),
                "last_activity": row['last_activity'].isoformat() if row['last_activity'] else None,
                "needs_enrichment": row['email'] is None
            })

        return companies


async def enrich_missing_emails(
    pool: asyncpg.Pool,
    companies: List[Dict],
    max_concurrent: int = 3
) -> List[Dict]:
    """Enrich companies that are missing emails"""
    service = EmailEnrichmentService(pool)

    # Filter to companies needing enrichment
    needs_enrichment = [c for c in companies if c.get("needs_enrichment")]

    if not needs_enrichment:
        return companies

    logger.info(f"Enriching {len(needs_enrichment)} companies missing emails...")

    results = await service.enrich_batch(needs_enrichment, max_concurrent=max_concurrent)

    # Update original list with found emails
    email_map = {r["company_name"]: r.get("email") for r in results["results"] if r.get("success")}

    for company in companies:
        if company["company_name"] in email_map:
            company["email"] = email_map[company["company_name"]]
            company["needs_enrichment"] = False

    await service.close()

    # Return only companies with emails
    return [c for c in companies if c.get("email")]

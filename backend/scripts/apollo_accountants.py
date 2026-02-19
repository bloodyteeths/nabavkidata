#!/usr/bin/env python3
"""
Find & enrich Macedonian accountants via Apollo.io API.

Two modes:
  1. ENRICH: Match ISOS accountants (name+company) against Apollo to get emails
  2. DISCOVER: Search Apollo for accounting professionals in MK not in ISOS

Usage:
    python3 scripts/apollo_accountants.py --dry-run              # Preview only
    python3 scripts/apollo_accountants.py enrich --limit=100     # Enrich 100 ISOS people
    python3 scripts/apollo_accountants.py discover --pages=20    # Search 20 pages of new accountants
    python3 scripts/apollo_accountants.py all --limit=500 --pages=20  # Both
"""
import os
import sys
import csv
import asyncio
import aiohttp
import json
from datetime import datetime
from pathlib import Path

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "M5Ker5RzIA9flD0s_IONEA")
APOLLO_BASE_URL = "https://api.apollo.io/v1"

# Paths to ISOS CSVs
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ISOS_AUTH_ACCOUNTANTS = PROJECT_ROOT / "isos_authorized_accountants.csv"
ISOS_ACCOUNTANTS = PROJECT_ROOT / "isos_accountants.csv"
ISOS_CONTACTS_UNIQUE = PROJECT_ROOT / "isos_contacts_unique.csv"

# Output
OUTPUT_DIR = PROJECT_ROOT / "apollo_accountant_results"

# Rate limiting
CONCURRENCY = 5
DELAY_BETWEEN_REQUESTS = 0.3
DELAY_BETWEEN_PAGES = 1.0

# Stats
stats = {
    "enrich_attempted": 0,
    "enrich_found": 0,
    "enrich_no_match": 0,
    "discover_found": 0,
    "discover_new": 0,
    "discover_duplicate": 0,
    "credits_exhausted": False,
}


def load_isos_people():
    """Load ISOS accountants who have name+company but no email."""
    people = []

    for csv_path, license_type in [
        (ISOS_AUTH_ACCOUNTANTS, "authorized"),
        (ISOS_ACCOUNTANTS, "regular"),
    ]:
        if not csv_path.exists():
            print(f"  WARNING: {csv_path.name} not found, skipping")
            continue

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                first_name = row.get("\u0418\u043c\u0435", "").strip()  # Име
                last_name = row.get("\u041f\u0440\u0435\u0437\u0438\u043c\u0435", "").strip()  # Презиме
                company = row.get("\u041a\u043e\u043c\u043f\u0430\u043d\u0438\u0458\u0430", "").strip()  # Компанија
                license_no = row.get("\u0411\u0440\u043e\u0458 \u043d\u0430 \u043b\u0438\u0446\u0435\u043d\u0446\u0430", "").strip()

                if first_name and last_name:
                    people.append({
                        "first_name": first_name,
                        "last_name": last_name,
                        "company": company,
                        "license_no": license_no,
                        "license_type": license_type,
                    })

    print(f"  Loaded {len(people)} ISOS people (with name, needing email)")
    return people


def load_existing_emails():
    """Load emails we already have from isos_contacts_unique.csv to deduplicate."""
    emails = set()
    names = set()

    csv_path = ISOS_CONTACTS_UNIQUE
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = (row.get("email") or "").strip().lower()
                name = (row.get("name") or "").strip().lower()
                if email:
                    emails.add(email)
                if name:
                    names.add(name)

    print(f"  Loaded {len(emails)} existing emails for dedup")
    return emails, names


async def apollo_people_match(session, first_name, last_name, company=None):
    """Match a person by name+company via Apollo People Match API. Uses 1 credit per reveal."""
    url = f"{APOLLO_BASE_URL}/people/match"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY,
    }
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "reveal_personal_emails": True,
    }
    if company:
        payload["organization_name"] = company

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                person = data.get("person")
                if not person:
                    return None
                email = person.get("email", "")
                if email and "@" in email and "not_unlocked" not in email.lower():
                    return {
                        "email": email,
                        "email_status": person.get("email_status"),
                        "phone": person.get("phone_number"),
                        "linkedin_url": person.get("linkedin_url"),
                        "title": person.get("title"),
                        "city": person.get("city"),
                        "company_name": (person.get("organization") or {}).get("name"),
                    }
                return None
            elif resp.status in (403, 429):
                text = await resp.text()
                if "credit" in text.lower() or "limit" in text.lower():
                    stats["credits_exhausted"] = True
                    return {"error": "OUT_OF_CREDITS"}
                await asyncio.sleep(5)
                return None
            else:
                return None
    except Exception as e:
        print(f"    Match error: {e}")
        return None


async def apollo_search_accountants(session, page=1):
    """Search Apollo for accounting professionals in Macedonia."""
    url = f"{APOLLO_BASE_URL}/mixed_people/search"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY,
    }

    payload = {
        "page": page,
        "per_page": 100,
        "person_locations": ["Macedonia", "North Macedonia", "Skopje"],
        "person_titles": [
            # English titles
            "Accountant", "Senior Accountant", "Chief Accountant",
            "Bookkeeper", "Tax Advisor", "Tax Consultant",
            "Auditor", "Finance Manager", "Financial Controller",
            "CFO", "Chief Financial Officer",
            "Accounting Manager", "Accounts Manager",
            "Payroll", "Finance Director",
            # Macedonian titles (common on LinkedIn)
            "Сметководител", "Овластен сметководител",
            "Ревизор", "Книговодител",
            "Финансиски директор",
        ],
        "organization_num_employees_ranges": [
            "1,10", "11,20", "21,50", "51,100", "101,200", "201,500",
        ],
        "reveal_personal_emails": True,
        "reveal_phone_number": True,
    }

    try:
        async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status in (403, 429):
                text = await resp.text()
                if "credit" in text.lower():
                    stats["credits_exhausted"] = True
                    return {"error": "OUT_OF_CREDITS"}
                print(f"    Rate limited, waiting 10s...")
                await asyncio.sleep(10)
                return None
            else:
                text = await resp.text()
                print(f"    Search error {resp.status}: {text[:200]}")
                return None
    except Exception as e:
        print(f"    Search error: {e}")
        return None


async def apollo_search_by_industry(session, page=1):
    """Search by accounting industry instead of titles (catches more people)."""
    url = f"{APOLLO_BASE_URL}/mixed_people/search"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY,
    }

    payload = {
        "page": page,
        "per_page": 100,
        "person_locations": ["Macedonia", "North Macedonia", "Skopje"],
        "q_organization_keyword_tags": [
            "accounting", "bookkeeping", "tax", "audit",
            "сметководство", "ревизија",
        ],
        "organization_num_employees_ranges": [
            "1,10", "11,20", "21,50", "51,100",
        ],
        "reveal_personal_emails": True,
        "reveal_phone_number": True,
    }

    try:
        async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status in (403, 429):
                text = await resp.text()
                if "credit" in text.lower():
                    stats["credits_exhausted"] = True
                    return {"error": "OUT_OF_CREDITS"}
                await asyncio.sleep(10)
                return None
            else:
                return None
    except Exception as e:
        print(f"    Industry search error: {e}")
        return None


def extract_person_data(person):
    """Extract useful fields from an Apollo person object."""
    org = person.get("organization") or {}
    email = person.get("email", "")
    if not email or "@" not in email or "not_unlocked" in email.lower():
        email = ""

    return {
        "first_name": person.get("first_name", ""),
        "last_name": person.get("last_name", ""),
        "full_name": person.get("name", ""),
        "email": email,
        "email_status": person.get("email_status", ""),
        "phone": person.get("phone_number", ""),
        "title": person.get("title", ""),
        "linkedin_url": person.get("linkedin_url", ""),
        "city": person.get("city", ""),
        "country": person.get("country", ""),
        "company_name": org.get("name", ""),
        "company_domain": org.get("primary_domain", ""),
        "company_industry": org.get("industry", ""),
        "company_size": org.get("estimated_num_employees", ""),
    }


async def run_enrich(session, dry_run=False, limit=None):
    """Part 1: Enrich ISOS accountants with Apollo emails."""
    print("\n" + "=" * 70)
    print("PART 1: ENRICH ISOS ACCOUNTANTS VIA APOLLO")
    print("=" * 70)

    people = load_isos_people()
    if limit:
        people = people[:limit]
        print(f"  Limited to first {limit} people")

    if dry_run:
        print("\n  [DRY RUN] Would attempt to match these people:")
        for p in people[:15]:
            print(f"    {p['first_name']} {p['last_name']} @ {p['company'] or '(no company)'} [{p['license_type']}]")
        print(f"    ... and {len(people) - 15} more")
        return []

    results = []
    sem = asyncio.Semaphore(CONCURRENCY)

    async def process_one(person):
        async with sem:
            if stats["credits_exhausted"]:
                return
            stats["enrich_attempted"] += 1

            result = await apollo_people_match(
                session,
                person["first_name"],
                person["last_name"],
                person["company"] or None,
            )

            if result and result.get("error") == "OUT_OF_CREDITS":
                print(f"\n  OUT OF CREDITS after {stats['enrich_found']} enriched")
                return

            if result and result.get("email"):
                stats["enrich_found"] += 1
                entry = {
                    "isos_first_name": person["first_name"],
                    "isos_last_name": person["last_name"],
                    "isos_company": person["company"],
                    "isos_license": person["license_no"],
                    "license_type": person["license_type"],
                    **result,
                }
                results.append(entry)

                if stats["enrich_found"] <= 30 or stats["enrich_found"] % 100 == 0:
                    print(f"  [{stats['enrich_found']}] {person['first_name']} {person['last_name']} -> {result['email']}")
            else:
                stats["enrich_no_match"] += 1

            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

            if stats["enrich_attempted"] % 200 == 0:
                print(f"  Progress: {stats['enrich_attempted']}/{len(people)} attempted, "
                      f"{stats['enrich_found']} found, {stats['enrich_no_match']} no match")

    # Process in batches
    batch_size = 50
    for i in range(0, len(people), batch_size):
        if stats["credits_exhausted"]:
            break
        batch = people[i:i + batch_size]
        tasks = [process_one(p) for p in batch]
        await asyncio.gather(*tasks)

        processed = min(i + batch_size, len(people))
        print(f"  Batch done: {processed}/{len(people)}, found {stats['enrich_found']} emails")

    return results


async def run_discover(session, existing_emails, existing_names, dry_run=False, max_pages=20):
    """Part 2: Search Apollo for NEW accountants not in ISOS."""
    print("\n" + "=" * 70)
    print("PART 2: DISCOVER NEW ACCOUNTANTS VIA APOLLO SEARCH")
    print("=" * 70)

    all_new = []

    # Strategy 1: Search by accounting titles
    print("\n  Strategy 1: Search by accounting job titles...")
    for page in range(1, max_pages + 1):
        if stats["credits_exhausted"]:
            break

        result = await apollo_search_accountants(session, page)
        if not result or result.get("error") == "OUT_OF_CREDITS":
            if result and result.get("error") == "OUT_OF_CREDITS":
                print(f"  OUT OF CREDITS")
            break

        people = result.get("people", [])
        if not people:
            print(f"  No more results at page {page}")
            break

        pagination = result.get("pagination", {})
        total = pagination.get("total_entries", 0)

        if dry_run:
            print(f"\n  [Page {page}] {len(people)} results (total available: {total:,})")
            for p in people[:5]:
                name = p.get("name", "?")
                title = p.get("title", "?")
                company = (p.get("organization") or {}).get("name", "?")
                email = p.get("email", "N/A")
                print(f"    {name} | {title} | {company} | {email}")
            if page >= 3:
                print(f"  [DRY RUN] Stopping after 3 pages preview")
                break
            await asyncio.sleep(0.5)
            continue

        page_new = 0
        for person in people:
            if stats["credits_exhausted"]:
                break

            data = extract_person_data(person)
            name_lower = data["full_name"].lower()

            stats["discover_found"] += 1

            # Skip if name already in ISOS
            if name_lower and name_lower in existing_names:
                stats["discover_duplicate"] += 1
                continue

            # Email from search is usually "not_unlocked" - need to reveal it
            if not data["email"] and data["first_name"] and data["last_name"]:
                revealed = await apollo_people_match(
                    session,
                    data["first_name"],
                    data["last_name"],
                    data["company_name"] or None,
                )
                if revealed and revealed.get("error") == "OUT_OF_CREDITS":
                    print(f"\n  OUT OF CREDITS during reveal")
                    break
                if revealed and revealed.get("email"):
                    data["email"] = revealed["email"]
                    data["email_status"] = revealed.get("email_status", "")
                    data["phone"] = revealed.get("phone") or data["phone"]
                    data["linkedin_url"] = revealed.get("linkedin_url") or data["linkedin_url"]
                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

            email_lower = data["email"].lower() if data["email"] else ""

            # Skip if email already known
            if email_lower and email_lower in existing_emails:
                stats["discover_duplicate"] += 1
                continue

            if data["email"]:
                existing_emails.add(email_lower)
                data["source"] = "apollo_title_search"
                all_new.append(data)
                stats["discover_new"] += 1
                page_new += 1

                if stats["discover_new"] <= 30 or stats["discover_new"] % 50 == 0:
                    print(f"    NEW: {data['full_name']} | {data['title']} | {data['company_name']} -> {data['email']}")

        print(f"  [Page {page}/{max_pages}] {page_new} new contacts "
              f"(total new: {stats['discover_new']}, dupes: {stats['discover_duplicate']})")
        await asyncio.sleep(DELAY_BETWEEN_PAGES)

    # Strategy 2: Search by accounting industry keywords
    if not stats["credits_exhausted"] and not dry_run:
        print(f"\n  Strategy 2: Search by accounting industry keywords...")
        for page in range(1, max_pages + 1):
            if stats["credits_exhausted"]:
                break

            result = await apollo_search_by_industry(session, page)
            if not result or result.get("error") == "OUT_OF_CREDITS":
                break

            people = result.get("people", [])
            if not people:
                break

            page_new = 0
            for person in people:
                if stats["credits_exhausted"]:
                    break

                data = extract_person_data(person)
                name_lower = data["full_name"].lower()

                if name_lower and name_lower in existing_names:
                    continue

                # Reveal email if not unlocked
                if not data["email"] and data["first_name"] and data["last_name"]:
                    revealed = await apollo_people_match(
                        session,
                        data["first_name"],
                        data["last_name"],
                        data["company_name"] or None,
                    )
                    if revealed and revealed.get("error") == "OUT_OF_CREDITS":
                        break
                    if revealed and revealed.get("email"):
                        data["email"] = revealed["email"]
                        data["email_status"] = revealed.get("email_status", "")
                        data["phone"] = revealed.get("phone") or data["phone"]
                        data["linkedin_url"] = revealed.get("linkedin_url") or data["linkedin_url"]
                    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

                email_lower = data["email"].lower() if data["email"] else ""

                if email_lower and email_lower in existing_emails:
                    continue

                if data["email"]:
                    existing_emails.add(email_lower)
                    data["source"] = "apollo_industry_search"
                    all_new.append(data)
                    stats["discover_new"] += 1
                    page_new += 1

            print(f"  [Industry page {page}] {page_new} new contacts (total new: {stats['discover_new']})")
            await asyncio.sleep(DELAY_BETWEEN_PAGES)

    return all_new


def save_results(enriched, discovered):
    """Save results to CSV files."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    saved_files = []

    if enriched:
        path = OUTPUT_DIR / f"isos_enriched_{timestamp}.csv"
        fieldnames = [
            "isos_first_name", "isos_last_name", "isos_company", "isos_license",
            "license_type", "email", "email_status", "phone",
            "linkedin_url", "title", "city", "company_name",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(enriched)
        saved_files.append(path)
        print(f"\n  Saved {len(enriched)} enriched contacts -> {path}")

    if discovered:
        path = OUTPUT_DIR / f"new_accountants_{timestamp}.csv"
        fieldnames = [
            "full_name", "first_name", "last_name", "email", "email_status",
            "phone", "title", "linkedin_url", "city", "country",
            "company_name", "company_domain", "company_industry", "company_size",
            "source",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(discovered)
        saved_files.append(path)
        print(f"  Saved {len(discovered)} new contacts -> {path}")

    # Also save a combined master list
    if enriched or discovered:
        path = OUTPUT_DIR / f"all_apollo_accountants_{timestamp}.csv"
        all_contacts = []
        for e in enriched:
            all_contacts.append({
                "name": f"{e['isos_first_name']} {e['isos_last_name']}",
                "email": e.get("email", ""),
                "phone": e.get("phone", ""),
                "company": e.get("isos_company") or e.get("company_name", ""),
                "title": e.get("title", ""),
                "linkedin": e.get("linkedin_url", ""),
                "source": "isos_enriched",
            })
        for d in discovered:
            all_contacts.append({
                "name": d.get("full_name", ""),
                "email": d.get("email", ""),
                "phone": d.get("phone", ""),
                "company": d.get("company_name", ""),
                "title": d.get("title", ""),
                "linkedin": d.get("linkedin_url", ""),
                "source": d.get("source", "apollo_discover"),
            })

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "email", "phone", "company", "title", "linkedin", "source"])
            writer.writeheader()
            writer.writerows(all_contacts)
        saved_files.append(path)
        print(f"  Saved {len(all_contacts)} combined contacts -> {path}")

    return saved_files


async def main():
    print("=" * 70)
    print("APOLLO ACCOUNTANT FINDER")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Parse arguments
    dry_run = "--dry-run" in sys.argv
    mode = "all"
    if "enrich" in sys.argv:
        mode = "enrich"
    elif "discover" in sys.argv:
        mode = "discover"

    limit = None
    max_pages = 20
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        elif arg.startswith("--pages="):
            max_pages = int(arg.split("=")[1])

    if dry_run:
        print("\n  [DRY RUN MODE - No API credits will be used]")

    # Load existing data
    print("\nLoading existing ISOS data...")
    existing_emails, existing_names = load_existing_emails()

    enriched = []
    discovered = []

    start_time = datetime.now()

    connector = aiohttp.TCPConnector(limit=CONCURRENCY)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Part 1: Enrich
        if mode in ("all", "enrich"):
            enriched = await run_enrich(session, dry_run=dry_run, limit=limit)

        # Part 2: Discover
        if mode in ("all", "discover") and not stats["credits_exhausted"]:
            discovered = await run_discover(
                session, existing_emails, existing_names,
                dry_run=dry_run, max_pages=max_pages,
            )

    elapsed = (datetime.now() - start_time).total_seconds()

    # Save results
    if not dry_run:
        print("\n\nSaving results...")
        save_results(enriched, discovered)

    # Final report
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(f"Time elapsed: {elapsed:.0f}s")
    print(f"\nEnrichment (ISOS people -> Apollo emails):")
    print(f"  Attempted:  {stats['enrich_attempted']}")
    print(f"  Found:      {stats['enrich_found']}")
    print(f"  No match:   {stats['enrich_no_match']}")
    print(f"\nDiscovery (new accountants from Apollo):")
    print(f"  Found:      {stats['discover_found']}")
    print(f"  New:        {stats['discover_new']}")
    print(f"  Duplicates: {stats['discover_duplicate']}")
    print(f"\nCredits exhausted: {stats['credits_exhausted']}")
    if not dry_run:
        print(f"\nOutput directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())

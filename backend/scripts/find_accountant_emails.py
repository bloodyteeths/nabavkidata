#!/usr/bin/env python3
"""
Find emails for ISOS accountants using 3 strategies:
  1. FREE: EMBS join (match individuals to company emails)
  2. SERPER: Google search for 3,212 companies missing emails
  3. SERPER: Google search for 2,329 people with no EMBS

Usage:
    python3 scripts/find_accountant_emails.py --dry-run
    python3 scripts/find_accountant_emails.py --step=1           # Free EMBS join only
    python3 scripts/find_accountant_emails.py --step=2 --limit=100  # Serper companies
    python3 scripts/find_accountant_emails.py --step=3 --limit=100  # Serper people
    python3 scripts/find_accountant_emails.py                     # All 3 steps
"""
import os
import sys
import csv
import re
import asyncio
import aiohttp
import json
from datetime import datetime
from pathlib import Path

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "44f30f72518dfebcc1c58fc2de13b41d9afc7cd0")
SERPER_URL = "https://google.serper.dev/search"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ISOS_AUTH_ACCOUNTANTS = PROJECT_ROOT / "isos_authorized_accountants.csv"
ISOS_ACCOUNTANTS = PROJECT_ROOT / "isos_accountants.csv"
ISOS_ALL_COMPANIES = PROJECT_ROOT / "isos_all_companies_unique.csv"
ISOS_CONTACTS_UNIQUE = PROJECT_ROOT / "isos_contacts_unique.csv"
OUTPUT_DIR = PROJECT_ROOT / "apollo_accountant_results"

CONCURRENCY = 5
EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
JUNK_EMAILS = {
    "example@example.com", "info@example.com", "email@example.com",
    "name@domain.com", "user@domain.com", "test@test.com",
    "wixpress.com", "sentry.io", "schema.org", "googleapis.com",
    "w3.org", "facebook.com", "twitter.com", "instagram.com",
    "linkedin.com", "youtube.com", "google.com", "wordpress.org",
    "cloudflare.com", "gravatar.com", "wp.com",
}

stats = {
    "step1_matched": 0,
    "step2_searched": 0,
    "step2_found": 0,
    "step2_people_covered": 0,
    "step3_searched": 0,
    "step3_found": 0,
    "serper_errors": 0,
}


def is_junk_email(email):
    """Filter out generic/junk emails from search results."""
    email = email.lower().strip()
    if not email or "@" not in email:
        return True
    domain = email.split("@")[1]
    for junk in JUNK_EMAILS:
        if junk in domain:
            return True
    if email.startswith("noreply") or email.startswith("no-reply"):
        return True
    return False


def extract_emails_from_text(text):
    """Extract valid email addresses from text."""
    if not text:
        return []
    found = EMAIL_RE.findall(text)
    return [e for e in found if not is_junk_email(e)]


def load_company_emails():
    """Load company emails indexed by EMBS."""
    company_emails = {}
    if ISOS_ALL_COMPANIES.exists():
        with open(ISOS_ALL_COMPANIES, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                embs = (row.get("embs") or "").strip()
                email = (row.get("email") or "").strip()
                name = (row.get("name") or "").strip()
                phone = (row.get("phone") or "").strip()
                if embs:
                    company_emails[embs] = {
                        "email": email,
                        "name": name,
                        "phone": phone,
                    }
    return company_emails


def load_individuals():
    """Load all individual accountants from ISOS."""
    people = []
    for csv_path, license_type in [
        (ISOS_AUTH_ACCOUNTANTS, "authorized"),
        (ISOS_ACCOUNTANTS, "regular"),
    ]:
        if not csv_path.exists():
            continue
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                people.append({
                    "first_name": (row.get("\u0418\u043c\u0435") or "").strip(),
                    "last_name": (row.get("\u041f\u0440\u0435\u0437\u0438\u043c\u0435") or "").strip(),
                    "company": (row.get("\u041a\u043e\u043c\u043f\u0430\u043d\u0438\u0458\u0430") or "").strip(),
                    "embs": (row.get("\u041c\u0430\u0442\u0438\u0447\u0435\u043d \u043d\u0430 \u043a\u043e\u043c\u043f\u0430\u043d\u0438\u0458\u0430") or "").strip(),
                    "license_no": (row.get("\u0411\u0440\u043e\u0458 \u043d\u0430 \u043b\u0438\u0446\u0435\u043d\u0446\u0430") or "").strip(),
                    "license_type": license_type,
                })
    return people


def load_existing_emails():
    """Load all emails we already have."""
    emails = set()
    if ISOS_CONTACTS_UNIQUE.exists():
        with open(ISOS_CONTACTS_UNIQUE, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                email = (row.get("email") or "").strip().lower()
                if email:
                    emails.add(email)

    # Also load Apollo results
    for csv_path in OUTPUT_DIR.glob("*.csv"):
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    email = (row.get("email") or "").strip().lower()
                    if email:
                        emails.add(email)
        except Exception:
            pass

    return emails


async def serper_search(session, query):
    """Search Google via Serper API."""
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "gl": "mk",
        "hl": "mk",
        "num": 10,
    }
    try:
        async with session.post(SERPER_URL, headers=headers, json=payload, timeout=15) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                text = await resp.text()
                if resp.status == 429:
                    await asyncio.sleep(5)
                stats["serper_errors"] += 1
                return None
    except Exception as e:
        stats["serper_errors"] += 1
        return None


def extract_emails_from_serper(result):
    """Extract emails from Serper search results."""
    emails = []
    if not result:
        return emails

    # Check organic results
    for item in result.get("organic", []):
        snippet = item.get("snippet", "")
        title = item.get("title", "")
        link = item.get("link", "")
        emails.extend(extract_emails_from_text(snippet))
        emails.extend(extract_emails_from_text(title))

    # Check knowledge graph
    kg = result.get("knowledgeGraph", {})
    if kg:
        for attr in kg.get("attributes", {}).values():
            if isinstance(attr, str):
                emails.extend(extract_emails_from_text(attr))
        desc = kg.get("description", "")
        emails.extend(extract_emails_from_text(desc))

    # Check answer box
    ab = result.get("answerBox", {})
    if ab:
        emails.extend(extract_emails_from_text(ab.get("answer", "")))
        emails.extend(extract_emails_from_text(ab.get("snippet", "")))

    # Deduplicate
    seen = set()
    unique = []
    for e in emails:
        e_lower = e.lower()
        if e_lower not in seen:
            seen.add(e_lower)
            unique.append(e)
    return unique


INCREMENTAL_STEP2 = OUTPUT_DIR / "step2_serper_companies_progress.csv"
INCREMENTAL_STEP3 = OUTPUT_DIR / "step3_serper_people_progress.csv"

def save_incremental(path, rows, fields):
    """Append rows to a progress CSV. Creates file with header if needed."""
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if write_header:
            w.writeheader()
        w.writerows(rows)


SEARCHED_COMPANIES_LOG = OUTPUT_DIR / "step2_searched_companies.txt"

def load_already_found_embs():
    """Load EMBS of companies already found by previous runs to skip them."""
    found = set()
    for p in [INCREMENTAL_STEP2] + list(OUTPUT_DIR.glob("step2_serper_companies_*.csv")):
        if not p.exists():
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    embs = (row.get("embs") or "").strip()
                    if embs:
                        found.add(embs)
        except Exception:
            pass
    return found


def load_already_searched_embs():
    """Load EMBS of ALL companies searched (found or not) to skip on resume."""
    searched = set()
    if SEARCHED_COMPANIES_LOG.exists():
        with open(SEARCHED_COMPANIES_LOG, "r") as f:
            for line in f:
                embs = line.strip()
                if embs:
                    searched.add(embs)
    return searched


def log_searched_embs(embs_list):
    """Log searched EMBS to file for resume."""
    with open(SEARCHED_COMPANIES_LOG, "a") as f:
        for embs in embs_list:
            f.write(embs + "\n")


# ── STEP 1: Free EMBS Join ──────────────────────────────────────────

def step1_embs_join(people, company_emails):
    """Match individuals to company emails via EMBS."""
    print("\n" + "=" * 70)
    print("STEP 1: FREE EMBS JOIN (individuals -> company emails)")
    print("=" * 70)

    results = []
    for person in people:
        embs = person["embs"]
        if embs and embs in company_emails:
            company = company_emails[embs]
            if company["email"]:
                results.append({
                    "first_name": person["first_name"],
                    "last_name": person["last_name"],
                    "person_company": person["company"],
                    "embs": embs,
                    "license_no": person["license_no"],
                    "license_type": person["license_type"],
                    "company_email": company["email"],
                    "company_name": company["name"],
                    "company_phone": company["phone"],
                })
                stats["step1_matched"] += 1

    print(f"  Matched {stats['step1_matched']} individuals to company emails")
    return results


# ── STEP 2: Serper for Companies Without Email ──────────────────────

async def step2_serper_companies(session, people, company_emails, existing_emails, dry_run=False, limit=None):
    """Google search for companies that have EMBS but no email."""
    print("\n" + "=" * 70)
    print("STEP 2: SERPER SEARCH FOR COMPANIES WITHOUT EMAIL")
    print("=" * 70)

    # Find unique companies needing email
    companies_need_email = {}
    for person in people:
        embs = person["embs"]
        if not embs:
            continue
        if embs in company_emails and company_emails[embs]["email"]:
            continue
        if embs not in companies_need_email:
            companies_need_email[embs] = {
                "company": person["company"],
                "embs": embs,
                "people": [],
            }
        companies_need_email[embs]["people"].append(person)

    # Skip companies already searched in previous runs
    already_searched = load_already_searched_embs()
    already_found = load_already_found_embs()
    skipped = already_searched | already_found
    for embs in skipped:
        companies_need_email.pop(embs, None)

    companies_list = list(companies_need_email.values())
    print(f"  {len(companies_list)} companies need email lookup (skipped {len(skipped)} already searched)")

    if limit:
        companies_list = companies_list[:limit]
        print(f"  Limited to {limit}")

    if dry_run:
        for c in companies_list[:10]:
            print(f"    Would search: {c['company']} (EMBS: {c['embs']}, {len(c['people'])} people)")
        return []

    results = []
    sem = asyncio.Semaphore(CONCURRENCY)

    async def search_company(company_info):
        async with sem:
            company_name = company_info["company"]
            if not company_name:
                log_searched_embs([company_info["embs"]])
                return

            # Try multiple search queries
            queries = [
                f'"{company_name}" email контакт',
                f'"{company_name}" @',
            ]

            found_emails = []
            for query in queries:
                if found_emails:
                    break
                result = await serper_search(session, query)
                found_emails = extract_emails_from_serper(result)
                await asyncio.sleep(0.3)

            stats["step2_searched"] += 1
            log_searched_embs([company_info["embs"]])

            if found_emails:
                email = found_emails[0]  # Take the best match
                if email.lower() not in existing_emails:
                    stats["step2_found"] += 1
                    stats["step2_people_covered"] += len(company_info["people"])
                    existing_emails.add(email.lower())

                    entry = {
                        "company_name": company_name,
                        "embs": company_info["embs"],
                        "email": email,
                        "people_count": len(company_info["people"]),
                        "source": "serper_company_search",
                    }
                    results.append(entry)

                    # Also create individual entries
                    for person in company_info["people"]:
                        results.append({
                            "first_name": person["first_name"],
                            "last_name": person["last_name"],
                            "company_name": company_name,
                            "embs": company_info["embs"],
                            "email": email,
                            "license_no": person["license_no"],
                            "license_type": person["license_type"],
                            "source": "serper_company_search",
                        })

                    if stats["step2_found"] <= 30 or stats["step2_found"] % 50 == 0:
                        print(f"    [{stats['step2_found']}] {company_name} -> {email} ({len(company_info['people'])} people)")

            if stats["step2_searched"] % 100 == 0:
                print(f"  Progress: {stats['step2_searched']}/{len(companies_list)} searched, "
                      f"{stats['step2_found']} found")

    # Process in batches with incremental save
    STEP2_FIELDS = ["first_name", "last_name", "company_name", "embs",
                     "email", "license_no", "license_type", "source", "people_count"]
    batch_size = 20
    batch_results = []
    for i in range(0, len(companies_list), batch_size):
        batch = companies_list[i:i + batch_size]
        pre_count = len(results)
        tasks = [search_company(c) for c in batch]
        await asyncio.gather(*tasks)

        # Save new rows from this batch incrementally
        new_rows = results[pre_count:]
        if new_rows:
            save_incremental(INCREMENTAL_STEP2, new_rows, STEP2_FIELDS)

        processed = min(i + batch_size, len(companies_list))
        if processed % 100 == 0 or processed == len(companies_list):
            print(f"  Batch: {processed}/{len(companies_list)}, found {stats['step2_found']} emails")

    return results


# ── STEP 3: Serper for People Without EMBS ──────────────────────────

async def step3_serper_people(session, people, company_emails, existing_emails, dry_run=False, limit=None):
    """Google search for individual accountants with no company EMBS."""
    print("\n" + "=" * 70)
    print("STEP 3: SERPER SEARCH FOR PEOPLE WITHOUT EMBS")
    print("=" * 70)

    # Find people with no EMBS (or company already has email via step 1)
    people_no_embs = []
    for person in people:
        if person["embs"]:
            continue
        if person["first_name"] and person["last_name"]:
            people_no_embs.append(person)

    print(f"  {len(people_no_embs)} people need direct search")

    if limit:
        people_no_embs = people_no_embs[:limit]
        print(f"  Limited to {limit}")

    if dry_run:
        for p in people_no_embs[:10]:
            print(f"    Would search: {p['first_name']} {p['last_name']} @ {p['company'] or '(no company)'}")
        return []

    results = []
    sem = asyncio.Semaphore(CONCURRENCY)

    async def search_person(person):
        async with sem:
            name = f"{person['first_name']} {person['last_name']}"
            company = person["company"]

            query = f'"{name}" email'
            if company:
                query = f'"{name}" "{company}" email'

            result = await serper_search(session, query)
            found_emails = extract_emails_from_serper(result)
            await asyncio.sleep(0.3)

            stats["step3_searched"] += 1

            if found_emails:
                email = found_emails[0]
                if email.lower() not in existing_emails:
                    stats["step3_found"] += 1
                    existing_emails.add(email.lower())

                    results.append({
                        "first_name": person["first_name"],
                        "last_name": person["last_name"],
                        "company_name": company,
                        "email": email,
                        "license_no": person["license_no"],
                        "license_type": person["license_type"],
                        "source": "serper_person_search",
                    })

                    if stats["step3_found"] <= 30 or stats["step3_found"] % 50 == 0:
                        print(f"    [{stats['step3_found']}] {name} -> {email}")

            if stats["step3_searched"] % 100 == 0:
                print(f"  Progress: {stats['step3_searched']}/{len(people_no_embs)} searched, "
                      f"{stats['step3_found']} found")

    STEP3_FIELDS = ["first_name", "last_name", "company_name",
                     "email", "license_no", "license_type", "source"]
    batch_size = 20
    for i in range(0, len(people_no_embs), batch_size):
        batch = people_no_embs[i:i + batch_size]
        pre_count = len(results)
        tasks = [search_person(p) for p in batch]
        await asyncio.gather(*tasks)

        new_rows = results[pre_count:]
        if new_rows:
            save_incremental(INCREMENTAL_STEP3, new_rows, STEP3_FIELDS)

        processed = min(i + batch_size, len(people_no_embs))
        if processed % 100 == 0 or processed == len(people_no_embs):
            print(f"  Batch: {processed}/{len(people_no_embs)}, found {stats['step3_found']} emails")

    return results


def save_all_results(step1, step2, step3):
    """Save all results to CSV files."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = []

    if step1:
        path = OUTPUT_DIR / f"step1_embs_matched_{ts}.csv"
        fields = ["first_name", "last_name", "person_company", "embs",
                   "license_no", "license_type", "company_email", "company_name", "company_phone"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(step1)
        saved.append(path)
        print(f"  Step 1: {len(step1)} rows -> {path.name}")

    if step2:
        path = OUTPUT_DIR / f"step2_serper_companies_{ts}.csv"
        fields = ["first_name", "last_name", "company_name", "embs",
                   "email", "license_no", "license_type", "source"]
        rows = [r for r in step2 if "first_name" in r]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        saved.append(path)
        print(f"  Step 2: {len(rows)} rows -> {path.name}")

    if step3:
        path = OUTPUT_DIR / f"step3_serper_people_{ts}.csv"
        fields = ["first_name", "last_name", "company_name",
                   "email", "license_no", "license_type", "source"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(step3)
        saved.append(path)
        print(f"  Step 3: {len(step3)} rows -> {path.name}")

    # Master combined
    if step1 or step2 or step3:
        path = OUTPUT_DIR / f"master_all_accountants_{ts}.csv"
        fields = ["name", "email", "company", "license_no", "license_type", "source"]
        all_rows = []
        for r in step1:
            all_rows.append({
                "name": f"{r['first_name']} {r['last_name']}",
                "email": r["company_email"],
                "company": r["person_company"],
                "license_no": r["license_no"],
                "license_type": r["license_type"],
                "source": "embs_join",
            })
        for r in step2:
            if "first_name" in r:
                all_rows.append({
                    "name": f"{r['first_name']} {r['last_name']}",
                    "email": r["email"],
                    "company": r["company_name"],
                    "license_no": r.get("license_no", ""),
                    "license_type": r.get("license_type", ""),
                    "source": "serper_company",
                })
        for r in step3:
            all_rows.append({
                "name": f"{r['first_name']} {r['last_name']}",
                "email": r["email"],
                "company": r["company_name"],
                "license_no": r["license_no"],
                "license_type": r["license_type"],
                "source": "serper_person",
            })

        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(all_rows)
        saved.append(path)
        print(f"  Master: {len(all_rows)} rows -> {path.name}")

    return saved


async def main():
    print("=" * 70)
    print("ACCOUNTANT EMAIL FINDER (EMBS + Serper)")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    dry_run = "--dry-run" in sys.argv
    step_filter = None
    limit = None
    for arg in sys.argv:
        if arg.startswith("--step="):
            step_filter = int(arg.split("=")[1])
        elif arg.startswith("--limit="):
            limit = int(arg.split("=")[1])

    if dry_run:
        print("  [DRY RUN]")

    # Load data
    print("\nLoading data...")
    company_emails = load_company_emails()
    people = load_individuals()
    existing_emails = load_existing_emails()
    print(f"  {len(people)} individuals, {len(company_emails)} companies, {len(existing_emails)} existing emails")

    start = datetime.now()

    step1_results = []
    step2_results = []
    step3_results = []

    # Step 1
    if step_filter is None or step_filter == 1:
        step1_results = step1_embs_join(people, company_emails)

    # Step 2
    if step_filter is None or step_filter == 2:
        connector = aiohttp.TCPConnector(limit=CONCURRENCY)
        async with aiohttp.ClientSession(connector=connector) as session:
            step2_results = await step2_serper_companies(
                session, people, company_emails, existing_emails,
                dry_run=dry_run, limit=limit,
            )

    # Step 3
    if step_filter is None or step_filter == 3:
        connector = aiohttp.TCPConnector(limit=CONCURRENCY)
        async with aiohttp.ClientSession(connector=connector) as session:
            step3_results = await step3_serper_people(
                session, people, company_emails, existing_emails,
                dry_run=dry_run, limit=limit,
            )

    elapsed = (datetime.now() - start).total_seconds()

    # Save
    if not dry_run:
        print("\nSaving results...")
        save_all_results(step1_results, step2_results, step3_results)

    # Report
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(f"Time: {elapsed:.0f}s")
    print(f"\nStep 1 (EMBS join, free):     {stats['step1_matched']} people matched")
    print(f"Step 2 (Serper companies):     {stats['step2_found']} companies found -> {stats['step2_people_covered']} people covered")
    print(f"  Searched: {stats['step2_searched']}, Errors: {stats['serper_errors']}")
    print(f"Step 3 (Serper people):        {stats['step3_found']} people found")
    print(f"  Searched: {stats['step3_searched']}")
    total = stats["step1_matched"] + stats["step2_people_covered"] + stats["step3_found"]
    print(f"\nTOTAL NEW REACHABLE: {total}")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())

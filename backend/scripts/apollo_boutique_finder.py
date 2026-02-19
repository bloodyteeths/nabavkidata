#!/usr/bin/env python3
"""
MyBabyByMerry - Children's Boutique Lead Finder
Uses Apollo company search + people lookup to find boutique owners.

This is a two-step process:
1. Find companies with children/kids/baby/boutique keywords
2. Find the Owner/Founder of each company

Usage:
    python3 apollo_boutique_finder.py --dry-run
    python3 apollo_boutique_finder.py --pages=5 --reveal
"""
import os
import sys
import asyncio
import aiohttp
import json
import csv
from datetime import datetime

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "M5Ker5RzIA9flD0s_IONEA")
APOLLO_BASE_URL = "https://api.apollo.io/v1"

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


async def search_boutique_companies(session, locations: list, page: int = 1) -> dict:
    """Search for children's boutique companies in specific locations"""
    url = f"{APOLLO_BASE_URL}/mixed_companies/search"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY
    }
    
    # If no specific locations provided, default to US
    if not locations:
        locations = ["United States"]

    payload = {
        "page": page,
        "per_page": 25,
        "organization_locations": locations,
        "organization_num_employees_ranges": ["1,10", "11,20", "21,50"],
        # Keywords to find children's boutiques
        "q_organization_keyword_tags": ["children", "kids", "baby", "boutique", "infant"]
    }
    
    try:
        async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                text = await resp.text()
                print(f"    Company search error {resp.status}: {text[:200]}")
                return None
    except Exception as e:
        print(f"    Request error: {e}")
        return None


async def find_company_contacts(session, company_domain: str, company_name: str) -> list:
    """Find Owner/Founder contacts for a specific company"""
    url = f"{APOLLO_BASE_URL}/mixed_people/search"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY
    }
    
    payload = {
        "page": 1,
        "per_page": 5,
        "person_titles": ["Owner", "Founder", "Co-Founder", "CEO", "President"],
        "q_organization_domains": company_domain
    }
    
    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("people", [])
            return []
    except:
        return []


async def enrich_person(session, person: dict) -> dict:
    """Reveal email for a person using people/match"""
    url = f"{APOLLO_BASE_URL}/people/match"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY
    }
    
    first_name = person.get('first_name', '')
    last_name = person.get('last_name', '')
    org = person.get('organization', {}) or {}
    org_name = org.get('name', '')
    domain = org.get('primary_domain', '')
    
    if not first_name or not last_name:
        return None
    
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "reveal_personal_emails": True,
    }
    
    if org_name:
        payload["organization_name"] = org_name
    if domain:
        payload["domain"] = domain
    
    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('person', {})
            elif resp.status == 403 or resp.status == 429:
                return {"error": "OUT_OF_CREDITS"}
            return None
    except:
        return None


def extract_contact(person: dict, company: dict) -> dict:
    """Extract contact data in CSV format"""
    org = person.get('organization', {}) or {}
    
    email = person.get('email', '')
    if email and 'not_unlocked' in email.lower():
        email = ''
    
    return {
        "first_name": person.get('first_name', ''),
        "last_name": person.get('last_name', ''),
        "full_name": person.get('name', ''),
        "email": email,
        "email_status": person.get('email_status', ''),
        "phone": person.get('phone_number', ''),
        "job_title": person.get('title', ''),
        "linkedin_url": person.get('linkedin_url', ''),
        "company_name": company.get('name', '') or org.get('name', ''),
        "company_domain": company.get('primary_domain', '') or org.get('primary_domain', ''),
        "company_website": f"https://{company.get('primary_domain', '')}" if company.get('primary_domain') else '',
        "company_industry": company.get('industry', ''),
        "city": person.get('city', ''),
        "state": person.get('state', ''),
        "country": person.get('country', 'United States'),
        "niche_category": "boutiques",
        "source": "apollo.io",
        "pulled_at": datetime.now().isoformat(),
    }


def write_csv(contacts: list, output_path: str):
    """Write contacts to CSV"""
    if not contacts:
        print("  No contacts to write")
        return
    
    fieldnames = list(contacts[0].keys())
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(contacts)
    
    print(f"  ✓ Wrote {len(contacts)} contacts to {output_path}")


async def main():
    print("=" * 70)
    print("CHILDREN'S BOUTIQUE LEAD FINDER")
    print("=" * 70)
    
    dry_run = '--dry-run' in sys.argv
    reveal_emails = '--reveal' in sys.argv
    
    max_pages = 5
    locations = []
    
    for arg in sys.argv:
        if arg.startswith('--pages='):
            max_pages = int(arg.split('=')[1])
        if arg.startswith('--states=') or arg.startswith('--locations='):
            # Parse comma-separated states/locations
            locs = arg.split('=')[1].split(',')
            locations = [l.strip() for l in locs if l.strip()]
            
    print(f"\nSettings:")
    print(f"  Pages: {max_pages}")
    print(f"  Locations: {locations if locations else 'United States (All)'}")
    print(f"  Reveal emails: {reveal_emails}")
    print(f"  Dry run: {dry_run}")
    
    contacts = []
    companies_processed = 0
    revealed_count = 0
    out_of_credits = False
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    async with aiohttp.ClientSession() as session:
        # Step 1: Find boutique companies
        for page in range(1, max_pages + 1):
            if out_of_credits:
                break
                
            print(f"\n[Page {page}/{max_pages}] Searching boutique companies...")
            
            result = await search_boutique_companies(session, locations, page)
            if not result:
                continue
            
            orgs = result.get('organizations', [])
            pagination = result.get('pagination', {})
            total = pagination.get('total_entries', 0)
            
            print(f"    Found {len(orgs)} companies (total available: {total:,})")
            
            if dry_run:
                for o in orgs[:5]:
                    print(f"      - {o.get('name')} | {o.get('primary_domain')}")
                continue
            
            # Step 2: Find contacts for each company
            print(f"    Processing {len(orgs)} companies for contacts...")
            for i, company in enumerate(orgs, 1):
                if out_of_credits:
                    break
                    
                domain = company.get('primary_domain', '')
                name = company.get('name', '')
                
                # print(f"      [{i}/{len(orgs)}] Checking {name} ({domain})...")
                
                if not domain:
                    continue
                
                # Find owners/founders
                people = await find_company_contacts(session, domain, name)
                
                if not people:
                    # print(f"        No owners found.")
                    companies_processed += 1
                    continue
                
                # print(f"        Found {len(people)} potential contacts.")
                
                for person in people[:2]:  # Max 2 contacts per company
                    # Reveal email if flag is set
                    if reveal_emails and not out_of_credits:
                        print(f"        Revealing email for {person.get('name')} at {name}...")
                        enriched = await enrich_person(session, person)
                        
                        if enriched and enriched.get('error') == 'OUT_OF_CREDITS':
                            print(f"\n    ⚠️ OUT OF CREDITS")
                            out_of_credits = True
                        elif enriched and enriched.get('email') and '@' in enriched.get('email', ''):
                            person['email'] = enriched['email']
                            person['email_status'] = enriched.get('email_status')
                            person['phone_number'] = enriched.get('phone_number')
                            revealed_count += 1
                            if revealed_count <= 15 or revealed_count % 25 == 0:
                                print(f"      ✓ [{revealed_count}] {person.get('name')} @ {name} -> {enriched['email']}")
                        else:
                             print(f"        No email found for {person.get('name')}")
                        
                        await asyncio.sleep(0.3)
                    
                    contact = extract_contact(person, company)
                    if contact['company_name']:
                        contacts.append(contact)
                
                companies_processed += 1
                await asyncio.sleep(0.2)
            
            await asyncio.sleep(0.5)
    
    if dry_run:
        print(f"\n[DRY RUN - No files created]")
        return
    
    # Write results
    if contacts:
        # All contacts
        all_path = os.path.join(OUTPUT_DIR, f"mybabybymerry_boutiques_ALL_{timestamp}.csv")
        write_csv(contacts, all_path)
        
        # Only with emails
        with_email = [c for c in contacts if c.get('email')]
        if with_email:
            email_path = os.path.join(OUTPUT_DIR, f"mybabybymerry_boutiques_WITH_EMAIL_{timestamp}.csv")
            write_csv(with_email, email_path)
    
    # Summary
    print("\n" + "=" * 70)
    print("BOUTIQUE LEAD GENERATION COMPLETE")
    print("=" * 70)
    
    with_email = [c for c in contacts if c.get('email')]
    
    print(f"\nResults:")
    print(f"  Companies processed: {companies_processed}")
    print(f"  Contacts found: {len(contacts)}")
    print(f"  With email: {len(with_email)}")
    if reveal_emails:
        print(f"  Emails revealed: {revealed_count}")
    
    print(f"\nCSV files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())

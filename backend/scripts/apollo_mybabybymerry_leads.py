#!/usr/bin/env python3
"""
MyBabyByMerry B2B Lead Generator - Apollo.io
Pulls targeted contacts for Faire newsletter outreach.

Target Niches:
  1. Newborn & Family Photographers (highest interest)
  2. Independent Children's Boutiques
  3. Wedding & Event Planners

API Note: Uses mixed_people/api_search (free search) + people/bulk_match (credits for reveal)

Usage:
    python3 scripts/apollo_mybabybymerry_leads.py --dry-run
    python3 scripts/apollo_mybabybymerry_leads.py --niche=photographers --pages=5
    python3 scripts/apollo_mybabybymerry_leads.py --niche=boutiques --pages=5
    python3 scripts/apollo_mybabybymerry_leads.py --niche=events --pages=5
    python3 scripts/apollo_mybabybymerry_leads.py --all --pages=10  # All niches
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

# Output directory for CSV files
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================================
# NICHE CONFIGURATIONS
# ============================================================================

NICHE_CONFIGS = {
    "photographers": {
        "name": "Newborn & Family Photographers",
        "description": "Photographers who need props/outfits for themed sessions",
        "person_titles": [
            "Photographer", "Owner", "Studio Owner", "Founder",
            "Newborn Photographer", "Family Photographer", "Portrait Photographer",
            "Creative Director", "Lead Photographer"
        ],
        "organization_num_employees_ranges": ["1,10", "11,20", "21,50"],
    },
    "boutiques": {
        "name": "Children's Boutiques & Gift Shops",
        "description": "Small retail stores selling premium children's clothing",
        "person_titles": [
            "Owner", "Store Owner", "Founder", "Buyer", "Purchasing Manager",
            "Store Manager", "E-commerce Manager", "Retail Manager",
            "Merchandiser", "General Manager", "Boutique Owner"
        ],
        "organization_num_employees_ranges": ["1,10", "11,20", "21,50", "51,100"],
    },
    "events": {
        "name": "Wedding & Event Planners",
        "description": "Planners who need flower girl dresses and party costumes",
        "person_titles": [
            "Event Planner", "Wedding Planner", "Owner", "Founder",
            "Party Planner", "Event Coordinator", "Wedding Coordinator",
            "Creative Director", "Event Manager"
        ],
        "organization_num_employees_ranges": ["1,10", "11,20", "21,50"],
    }
}


async def search_people_api(session, niche_config: dict, page: int = 1) -> dict:
    """
    Search for people in USA using Apollo's search endpoint.
    Returns partial profiles that can be enriched via people/match.
    """
    url = f"{APOLLO_BASE_URL}/mixed_people/search"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY
    }

    payload = {
        "page": page,
        "per_page": 25,  # Smaller batches for reliability
        
        # Location: USA focus
        "person_locations": ["United States"],
        
        # Niche-specific titles - this is the main filter
        "person_titles": niche_config["person_titles"],
        
        # Company size: Small businesses
        "organization_num_employees_ranges": niche_config["organization_num_employees_ranges"],
    }
    
    # Add keyword filter if specified (for boutique-specific matching)
    if niche_config.get("q_keywords"):
        payload["q_keywords"] = niche_config["q_keywords"]

    try:
        async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                text = await resp.text()
                print(f"    Apollo API error {resp.status}: {text[:300]}")
                return None
    except Exception as e:
        print(f"    Request error: {e}")
        return None


async def enrich_person(session, person: dict) -> dict:
    """Enrich a person to reveal their email using people/match endpoint (uses credits)"""
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
    
    # Add company info if available
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
                text = await resp.text()
                if "credit" in text.lower() or "limit" in text.lower():
                    return {"error": "OUT_OF_CREDITS"}
                return {"error": f"RATE_LIMITED_{resp.status}"}
            else:
                return None
    except Exception as e:
        print(f"    Enrich error: {e}")
        return None


def extract_contact_data(person: dict, niche: str) -> dict:
    """Extract contact data in Faire-friendly CSV format"""
    org = person.get('organization', {}) or {}
    
    # Get email - prefer revealed email
    email = person.get('email', '')
    if email and ('not_unlocked' in email.lower() or 'guessed' in str(person.get('email_status', '')).lower()):
        email = ''
    
    return {
        # Core Contact Info
        "first_name": person.get('first_name', ''),
        "last_name": person.get('last_name', ''),
        "full_name": person.get('name', ''),
        "email": email,
        "email_status": person.get('email_status', ''),
        "phone": person.get('phone_number', ''),
        
        # Professional Info
        "job_title": person.get('title', ''),
        "seniority": person.get('seniority', ''),
        "linkedin_url": person.get('linkedin_url', ''),
        
        # Company Info
        "company_name": org.get('name', ''),
        "company_domain": org.get('primary_domain', ''),
        "company_website": f"https://{org.get('primary_domain', '')}" if org.get('primary_domain') else '',
        "company_linkedin": org.get('linkedin_url', ''),
        "company_industry": org.get('industry', ''),
        "company_size": org.get('estimated_num_employees', ''),
        
        # Location
        "city": person.get('city', ''),
        "state": person.get('state', ''),
        "country": person.get('country', ''),
        
        # Metadata
        "niche_category": niche,
        "source": "apollo.io",
        "pulled_at": datetime.now().isoformat(),
    }


def write_csv(contacts: list, niche: str, output_path: str):
    """Write contacts to CSV file in Faire-friendly format"""
    if not contacts:
        print(f"  No contacts to write for {niche}")
        return
    
    # Get fieldnames from first contact
    fieldnames = list(contacts[0].keys())
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(contacts)
    
    print(f"  ✓ Wrote {len(contacts)} contacts to {output_path}")


async def process_niche(session, niche: str, config: dict, max_pages: int, dry_run: bool, reveal_emails: bool) -> list:
    """Process a single niche and return contacts"""
    print(f"\n{'='*70}")
    print(f"NICHE: {config['name']}")
    print(f"Description: {config['description']}")
    print(f"{'='*70}")
    
    contacts = []
    page = 1
    empty_pages = 0
    out_of_credits = False
    revealed_count = 0
    
    while page <= max_pages and empty_pages < 3 and not out_of_credits:
        print(f"\n[Page {page}/{max_pages}] Searching {niche} contacts...")
        
        result = await search_people_api(session, config, page)
        
        if not result:
            empty_pages += 1
            page += 1
            await asyncio.sleep(1)
            continue
        
        people = result.get('people', [])
        if not people:
            empty_pages += 1
            print(f"    No more contacts found")
            page += 1
            continue
        
        pagination = result.get('pagination', {})
        total_available = pagination.get('total_entries', 0)
        print(f"    Found {len(people)} contacts (total available: {total_available:,})")
        
        if dry_run:
            for p in people[:5]:
                name = p.get('name', 'N/A')
                title = p.get('title', 'N/A')
                company = p.get('organization', {}).get('name', 'N/A') if p.get('organization') else 'N/A'
                city = p.get('city', 'N/A')
                state = p.get('state', 'N/A')
                email = p.get('email', 'N/A')
                print(f"      - {name} | {title} | {company} | {city}, {state} | {email}")
        else:
            for person in people:
                # Try to reveal email if flag is set
                if reveal_emails:
                    enriched = await enrich_person(session, person)
                    
                    if enriched and enriched.get('error') == 'OUT_OF_CREDITS':
                        print(f"\n    ⚠️ OUT OF CREDITS - Stopping email reveals")
                        out_of_credits = True
                        reveal_emails = False  # Continue without revealing
                    elif enriched and enriched.get('email') and '@' in enriched.get('email', ''):
                        person['email'] = enriched['email']
                        person['email_status'] = enriched.get('email_status')
                        person['phone_number'] = enriched.get('phone_number')
                        revealed_count += 1
                        if revealed_count <= 10 or revealed_count % 25 == 0:
                            print(f"      ✓ [{revealed_count}] {person.get('name')} -> {enriched['email']}")
                    
                    await asyncio.sleep(0.3)  # Rate limit for reveals
                
                # Extract and store contact
                contact_data = extract_contact_data(person, niche)
                if contact_data['company_name']:  # Only add if has company
                    contacts.append(contact_data)
        
        page += 1
        await asyncio.sleep(0.5)
    
    # Stats
    contacts_with_email = [c for c in contacts if c.get('email')]
    
    print(f"\n  Summary for {niche}:")
    print(f"    Total contacts found: {len(contacts)}")
    print(f"    With email: {len(contacts_with_email)}")
    if reveal_emails or revealed_count > 0:
        print(f"    Emails revealed: {revealed_count}")
    
    return contacts


async def main():
    print("=" * 70)
    print("MYBABYBYMERRY B2B LEAD GENERATOR")
    print("Target: USA Photographers, Boutiques, Event Planners")
    print("=" * 70)
    
    # Parse arguments
    dry_run = '--dry-run' in sys.argv
    run_all = '--all' in sys.argv
    reveal_emails = '--reveal' in sys.argv or '--reveal-emails' in sys.argv
    
    # Parse pages
    max_pages = 5  # Default
    for arg in sys.argv:
        if arg.startswith('--pages='):
            max_pages = int(arg.split('=')[1])
    
    # Parse niche
    target_niche = None
    for arg in sys.argv:
        if arg.startswith('--niche='):
            target_niche = arg.split('=')[1]
    
    # Determine which niches to process
    if run_all:
        niches_to_process = list(NICHE_CONFIGS.keys())
    elif target_niche and target_niche in NICHE_CONFIGS:
        niches_to_process = [target_niche]
    else:
        print("\nUsage:")
        print("  --niche=photographers  | Target photographers")
        print("  --niche=boutiques      | Target children's boutiques")
        print("  --niche=events         | Target event planners")
        print("  --all                  | Target all niches")
        print("  --pages=N              | Number of pages per niche (default: 5)")
        print("  --reveal               | Reveal emails using credits")
        print("  --dry-run              | Preview without making changes")
        return
    
    print(f"\nSettings:")
    print(f"  Niches: {', '.join(niches_to_process)}")
    print(f"  Pages per niche: {max_pages}")
    print(f"  Reveal emails: {reveal_emails}")
    print(f"  Dry run: {dry_run}")
    
    if not reveal_emails and not dry_run:
        print("\n  ⚠️ Note: Running without --reveal flag. Emails may be partial/hidden.")
        print("     Add --reveal to use Apollo credits for email reveals.")
    
    all_contacts = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    async with aiohttp.ClientSession() as session:
        for niche in niches_to_process:
            config = NICHE_CONFIGS[niche]
            contacts = await process_niche(session, niche, config, max_pages, dry_run, reveal_emails)
            all_contacts.extend(contacts)
            
            if not dry_run and contacts:
                # Write individual niche CSV
                niche_filename = f"mybabybymerry_leads_{niche}_{timestamp}.csv"
                niche_path = os.path.join(OUTPUT_DIR, niche_filename)
                write_csv(contacts, niche, niche_path)
    
    if dry_run:
        print(f"\n[DRY RUN - No files created]")
        return
    
    # Write combined CSV
    if all_contacts:
        combined_filename = f"mybabybymerry_leads_ALL_{timestamp}.csv"
        combined_path = os.path.join(OUTPUT_DIR, combined_filename)
        write_csv(all_contacts, "all", combined_path)
        
        # Also write email-only version for easy import
        contacts_with_email = [c for c in all_contacts if c.get('email')]
        if contacts_with_email:
            email_filename = f"mybabybymerry_leads_WITH_EMAIL_{timestamp}.csv"
            email_path = os.path.join(OUTPUT_DIR, email_filename)
            write_csv(contacts_with_email, "all", email_path)
    
    # Final summary
    print("\n" + "=" * 70)
    print("LEAD GENERATION COMPLETE")
    print("=" * 70)
    
    contacts_with_email = [c for c in all_contacts if c.get('email')]
    
    print(f"\nTotal Results:")
    print(f"  Total contacts: {len(all_contacts)}")
    print(f"  With email: {len(contacts_with_email)}")
    
    print(f"\nBreakdown by niche:")
    for niche in niches_to_process:
        niche_contacts = [c for c in all_contacts if c.get('niche_category') == niche]
        niche_emails = [c for c in niche_contacts if c.get('email')]
        print(f"  {niche}: {len(niche_contacts)} contacts ({len(niche_emails)} with email)")
    
    print(f"\nCSV files saved to: {OUTPUT_DIR}")
    print("\nNext steps:")
    print("  1. Review the CSV files")
    print("  2. Import to Faire or your email tool")
    print("  3. Personalize outreach based on niche category")


if __name__ == "__main__":
    asyncio.run(main())

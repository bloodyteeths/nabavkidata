#!/usr/bin/env python3
"""Search Apollo.io for Macedonian journalists and reveal emails"""
import httpx
import json
import time

API_KEY = "M5Ker5RzIA9flD0s_IONEA"
BASE = "https://api.apollo.io/api/v1"

def search_people(titles, page=1):
    r = httpx.post(f"{BASE}/mixed_people/search", json={
        "api_key": API_KEY,
        "person_titles": titles,
        "person_locations": ["North Macedonia", "Macedonia", "Skopje"],
        "page": page,
        "per_page": 100
    }, timeout=30)
    return r.json()

def reveal_email(person_id):
    """Use Apollo credit to reveal email"""
    r = httpx.post(f"{BASE}/people/match", json={
        "api_key": API_KEY,
        "id": person_id,
        "reveal_personal_emails": True,
        "reveal_phone_number": False
    }, timeout=30)
    return r.json()

# Search multiple title variations
all_people = {}

title_searches = [
    ["journalist", "editor", "reporter", "news editor"],
    ["editor in chief", "managing editor", "chief editor"],
    ["correspondent", "columnist", "anchor", "presenter"],
    ["investigative journalist", "investigative reporter"],
    ["blogger", "content creator", "media"],
]

for titles in title_searches:
    print(f"\n=== Searching: {titles} ===")
    data = search_people(titles)
    total = data.get("pagination", {}).get("total_entries", 0)
    people = data.get("people", [])
    print(f"Found: {total} total, {len(people)} on page 1")

    for p in people:
        pid = p.get("id", "")
        if pid and pid not in all_people:
            all_people[pid] = {
                "id": pid,
                "name": p.get("name", "?"),
                "title": p.get("title", "?"),
                "org": p.get("organization", {}).get("name", "?") if p.get("organization") else "?",
                "email": p.get("email"),
                "email_status": p.get("email_status", "?"),
                "linkedin": p.get("linkedin_url", ""),
            }

    time.sleep(0.5)

# Also search by organization domains
org_domains = [
    "telma.com.mk", "sitel.com.mk", "kanal5.com.mk", "24vesti.mk",
    "alsat.mk", "sdk.mk", "a1on.mk", "mkd.mk", "meta.mk",
    "slobodenpecat.mk", "nezavisen.mk", "faktor.mk", "lokalno.mk",
    "kurir.mk", "press24.mk", "makfax.com.mk", "novamakedonija.com.mk",
    "mia.mk", "netpress.com.mk", "prizma.mk", "scoop.mk",
    "birn.eu.com", "metamorphosis.org.mk", "transparency.mk",
    "radiomof.mk", "rferl.org"
]

print(f"\n=== Searching by organization domains ===")
for domain in org_domains:
    r = httpx.post(f"{BASE}/mixed_people/search", json={
        "api_key": API_KEY,
        "q_organization_domains": domain,
        "page": 1,
        "per_page": 25
    }, timeout=30)
    data = r.json()
    people = data.get("people", [])
    if people:
        print(f"\n{domain}: {len(people)} contacts")
        for p in people:
            pid = p.get("id", "")
            if pid and pid not in all_people:
                all_people[pid] = {
                    "id": pid,
                    "name": p.get("name", "?"),
                    "title": p.get("title", "?"),
                    "org": p.get("organization", {}).get("name", "?") if p.get("organization") else "?",
                    "email": p.get("email"),
                    "email_status": p.get("email_status", "?"),
                    "linkedin": p.get("linkedin_url", ""),
                }
    time.sleep(0.3)

print(f"\n\n{'='*60}")
print(f"TOTAL UNIQUE CONTACTS: {len(all_people)}")
print(f"{'='*60}")

# Sort by org and show all
has_email = []
needs_reveal = []

for pid, p in sorted(all_people.items(), key=lambda x: x[1]["org"]):
    if p["email"] and p["email_status"] in ("verified", "guessed", "unavailable"):
        has_email.append(p)
    else:
        needs_reveal.append(p)

print(f"\nWith email already: {len(has_email)}")
print(f"Need reveal: {len(needs_reveal)}")

# Show those with emails
print(f"\n--- CONTACTS WITH EMAILS ---")
for p in has_email:
    print(f"{p['name']}|{p['title']}|{p['org']}|{p['email']}|{p['email_status']}")

# Reveal emails for top contacts without emails (up to 50)
print(f"\n--- REVEALING EMAILS ---")
revealed = []
reveal_count = 0
MAX_REVEALS = 50

for p in needs_reveal:
    if reveal_count >= MAX_REVEALS:
        break

    print(f"Revealing: {p['name']} ({p['org']})...", end=" ")
    try:
        result = reveal_email(p["id"])
        person = result.get("person", {})
        email = person.get("email")
        email_status = person.get("email_status", "?")

        if email:
            print(f"-> {email} ({email_status})")
            p["email"] = email
            p["email_status"] = email_status
            revealed.append(p)
        else:
            # Check personal emails
            personal = person.get("personal_emails", [])
            if personal:
                print(f"-> {personal[0]} (personal)")
                p["email"] = personal[0]
                p["email_status"] = "personal"
                revealed.append(p)
            else:
                print("-> no email found")

        reveal_count += 1
        time.sleep(0.3)
    except Exception as e:
        print(f"-> ERROR: {e}")

print(f"\n{'='*60}")
print(f"REVEALED: {len(revealed)} new emails")
print(f"{'='*60}")

# Final combined list
all_with_emails = has_email + revealed
print(f"\nTOTAL CONTACTS WITH EMAILS: {len(all_with_emails)}")
print(f"\n--- FINAL LIST ---")
for p in all_with_emails:
    print(f"{p['name']}|{p['title']}|{p['org']}|{p['email']}|{p['email_status']}")

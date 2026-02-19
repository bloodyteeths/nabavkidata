#!/usr/bin/env python3
"""Search Apollo.io for Macedonian journalists and reveal their emails"""
import httpx
import json
import time

API_KEY = "M5Ker5RzIA9flD0s_IONEA"
HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "X-Api-Key": API_KEY
}
BASE = "https://api.apollo.io/api/v1"

def search_people(titles=None, domains=None, page=1, per_page=100):
    payload = {"page": page, "per_page": per_page}
    if titles:
        payload["person_titles"] = titles
        payload["person_locations"] = ["North Macedonia", "Macedonia", "Skopje"]
    if domains:
        payload["q_organization_domains"] = domains
    r = httpx.post(f"{BASE}/people/search", headers=HEADERS, json=payload, timeout=30)
    return r.json()

def reveal_person(person_id):
    """Reveal email using Apollo credits"""
    r = httpx.post(f"{BASE}/people/match", headers=HEADERS, json={
        "id": person_id,
        "reveal_personal_emails": True,
        "reveal_phone_number": False
    }, timeout=30)
    return r.json()

# Collect all unique people
all_people = {}

# Search 1: Journalists by title
title_groups = [
    ["journalist", "reporter"],
    ["editor", "editor in chief", "managing editor"],
    ["correspondent", "anchor", "presenter", "news anchor"],
    ["investigative journalist", "investigative reporter"],
]

for titles in title_groups:
    print(f"\nSearching: {titles}")
    for page in [1, 2]:
        data = search_people(titles=titles, page=page, per_page=100)
        total = data.get("pagination", {}).get("total_entries", 0)
        people = data.get("people", [])
        print(f"  Page {page}: {len(people)} results (total: {total})")

        for p in people:
            pid = p.get("id", "")
            if pid and pid not in all_people:
                org_name = "?"
                if p.get("organization"):
                    org_name = p["organization"].get("name", "?")
                all_people[pid] = {
                    "id": pid,
                    "name": p.get("name", "?"),
                    "title": p.get("title", "?"),
                    "org": org_name,
                    "email": p.get("email"),
                    "email_status": p.get("email_status", "?"),
                }

        if len(people) < 100:
            break
        time.sleep(0.5)
    time.sleep(0.5)

# Search 2: By organization domains
org_domains = [
    "telma.com.mk", "sitel.com.mk", "kanal5.com.mk", "24vesti.mk",
    "alsat.mk", "sdk.mk", "a1on.mk", "mkd.mk",
    "slobodenpecat.mk", "nezavisen.mk", "faktor.mk", "lokalno.mk",
    "kurir.mk", "makfax.com.mk", "novamakedonija.com.mk",
    "mia.mk", "netpress.com.mk", "prizma.mk", "scoop.mk",
    "birn.eu.com", "metamorphosis.org.mk", "radiomof.mk",
]

print(f"\nSearching by org domains...")
for domain in org_domains:
    data = search_people(domains=domain, per_page=25)
    people = data.get("people", [])
    if people:
        print(f"  {domain}: {len(people)} contacts")
        for p in people:
            pid = p.get("id", "")
            if pid and pid not in all_people:
                org_name = "?"
                if p.get("organization"):
                    org_name = p["organization"].get("name", "?")
                all_people[pid] = {
                    "id": pid,
                    "name": p.get("name", "?"),
                    "title": p.get("title", "?"),
                    "org": org_name,
                    "email": p.get("email"),
                    "email_status": p.get("email_status", "?"),
                }
    time.sleep(0.3)

print(f"\n{'='*60}")
print(f"TOTAL UNIQUE CONTACTS: {len(all_people)}")

# Separate those with/without emails
has_real_email = []
needs_reveal = []

for pid, p in all_people.items():
    email = p.get("email", "")
    if email and "email_not_unlocked" not in email:
        has_real_email.append(p)
    else:
        needs_reveal.append(p)

print(f"Already have email: {len(has_real_email)}")
print(f"Need to reveal: {len(needs_reveal)}")

# Reveal up to 50 emails
print(f"\n{'='*60}")
print(f"REVEALING EMAILS (up to 50)...")
print(f"{'='*60}")

revealed = []
errors = 0

for p in needs_reveal[:50]:
    name = p["name"]
    org = p["org"]
    print(f"  Revealing: {name} ({org})...", end=" ", flush=True)

    try:
        result = reveal_person(p["id"])
        person = result.get("person", {})

        if not person:
            print(f"no data")
            errors += 1
            continue

        email = person.get("email")
        email_status = person.get("email_status", "?")
        personal_emails = person.get("personal_emails", [])

        if email and "email_not_unlocked" not in email:
            print(f"{email} ({email_status})")
            p["email"] = email
            p["email_status"] = email_status
            revealed.append(p)
        elif personal_emails:
            print(f"{personal_emails[0]} (personal)")
            p["email"] = personal_emails[0]
            p["email_status"] = "personal"
            revealed.append(p)
        else:
            print(f"no email available")

        time.sleep(0.3)
    except Exception as e:
        print(f"ERROR: {e}")
        errors += 1
        time.sleep(1)

# Final results
all_contacts = has_real_email + revealed
print(f"\n{'='*60}")
print(f"FINAL RESULTS")
print(f"{'='*60}")
print(f"Already had email: {len(has_real_email)}")
print(f"Newly revealed: {len(revealed)}")
print(f"Errors: {errors}")
print(f"TOTAL WITH EMAIL: {len(all_contacts)}")
print(f"\n--- ALL CONTACTS ---")

# Deduplicate by email
seen_emails = set()
final_list = []
for p in all_contacts:
    email = p.get("email", "").lower().strip()
    if email and email not in seen_emails:
        seen_emails.add(email)
        final_list.append(p)
        print(f"{p['name']}|{p['title']}|{p['org']}|{p['email']}|{p['email_status']}")

print(f"\nDEDUPLICATED TOTAL: {len(final_list)}")

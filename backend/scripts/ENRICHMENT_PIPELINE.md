# Complete Enrichment Pipeline - Deep Analysis

## Current State

```
┌─────────────────────────────────────────────────────────────────┐
│                     CURRENT DATA INVENTORY                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SUPPLIERS TABLE (e-nabavki)                                    │
│  ├── Total companies: ~4,000                                    │
│  ├── With email: ~2,246                                         │
│  └── Quality: ★★★★★ (proven tender participants)                │
│                                                                 │
│  APOLLO_CONTACTS TABLE                                          │
│  ├── Total MK contacts: 4,773                                   │
│  ├── With email: 1,459                                          │
│  ├── Without email: 3,314                                       │
│  ├── Apollo MK available: 6,855 (2,082 not yet pulled)          │
│  └── Quality: ★★★★☆ (decision makers)                           │
│                                                                 │
│  CENTRAL REGISTRY (not scraped)                                 │
│  ├── Available: 70,000+ companies                               │
│  └── Quality: ★★★☆☆ (just registered)                           │
│                                                                 │
│  ═══════════════════════════════════════════                    │
│  CURRENT UNIQUE EMAILS: ~3,600                                  │
│  TARGET: 40,000+                                                │
│  GAP: ~36,400 emails                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Apollo Data Extraction (Company Details)

### What Apollo Gives WITHOUT Email Credits:

```json
{
  "id": "5f8a1b2c3d4e5f6g7h8i9j0k",
  "first_name": "Darko",
  "last_name": "Petrovski",
  "name": "Darko Petrovski",
  "title": "Chief Executive Officer",
  "seniority": "c_suite",
  "departments": ["executive"],
  "linkedin_url": "https://linkedin.com/in/darkopetrovski",
  "city": "Skopje",
  "country": "North Macedonia",

  "organization": {
    "name": "TechMK Solutions",
    "primary_domain": "techmk.com.mk",        // ← GOLD!
    "website_url": "https://techmk.com.mk",   // ← GOLD!
    "linkedin_url": "linkedin.com/company/techmk",
    "industry": "Information Technology",
    "estimated_num_employees": 50,
    "raw_address": "Bul. VMRO 5, Skopje"
  },

  "email": "email_not_unlocked@domain.com"    // ← Locked without credits
}
```

**Key insight**: Even without email reveals, we get:
- ✅ Full name + title
- ✅ Company name
- ✅ Company domain (primary_domain)
- ✅ LinkedIn URL
- ✅ Industry, size, location

The **domain** is enough to find/generate emails!

---

## Step 2: Serper Email Finding Strategy

### Priority 1: Domain-Based Search (40% success rate)

```python
# If we have company domain from Apollo
domain = "techmk.com.mk"

queries = [
    f"site:{domain} email",           # Find emails on their website
    f"site:{domain} contact",         # Contact page
    f'"{domain}" email contact',      # Domain mentioned with email
]

# Expected results:
# - info@techmk.com.mk
# - contact@techmk.com.mk
# - sales@techmk.com.mk
```

### Priority 2: Person + Company Search (25% success rate)

```python
name = "Darko Petrovski"
company = "TechMK Solutions"

queries = [
    f'"{name}" "{company}" email',
    f'"{name}" {company} @',          # @ forces email presence
    f'"{name}" email Macedonia',
]

# Expected results:
# - darko.petrovski@techmk.com.mk (from LinkedIn, directories)
# - darko@techmk.com.mk
```

### Priority 3: Company-Only Search (20% success rate)

```python
company = "TechMK Solutions"

queries = [
    f'"{company}" Macedonia email contact',
    f'"{company}" Skopje email',
    f'"{company}" контакт email',     # Macedonian word
]
```

### Priority 4: Email Pattern Generation (When Domain Found)

```python
domain = "techmk.com.mk"
first = "darko"
last = "petrovski"

# Generate variants in order of likelihood
email_patterns = [
    f"{first}.{last}@{domain}",       # darko.petrovski@
    f"{first}@{domain}",               # darko@
    f"{first[0]}{last}@{domain}",     # dpetrovski@
    f"{last}.{first}@{domain}",       # petrovski.darko@
    f"{first}{last}@{domain}",        # darkopetrovski@
    f"{first[0]}.{last}@{domain}",    # d.petrovski@
]

# Use first pattern that matches company email format
# (detect from other emails found on domain)
```

---

## Step 3: Central Registry Scraping

### Source: crm.com.mk (Централен Регистар)

### Data Available:
```
Company Record:
├── ЕМБС (Tax ID): 1234567890123
├── Назив (Name): ТЕХМК СОЛУШНС ДООЕЛ
├── Латиница: TECHMK SOLUTIONS DOOEL
├── Адреса: Бул. ВМРО бр.5, Скопје
├── Дејност (NACE): 62.01 - Компјутерско програмирање
├── Основач/Управител: Дарко Петровски
├── Датум на основање: 15.03.2018
└── Статус: Активен
```

### Scraping Strategy:

```python
# Option A: By NACE code (industry)
# Focus on tender-relevant industries:
nace_codes = {
    "41": "Градежништво",           # Construction
    "43": "Специјализирано градежништво",
    "45": "Трговија со возила",
    "46": "Трговија на големо",
    "47": "Трговија на мало",
    "62": "Компјутерско програмирање",
    "71": "Архитектура и инженерство",
    "72": "Научно истражување",
    "73": "Рекламирање",
    "74": "Други стручни дејности",
}

# Option B: By city
cities = [
    "Скопје", "Битола", "Куманово", "Прилеп", "Тетово",
    "Охрид", "Велес", "Штип", "Струмица", "Гостивар"
]

# Option C: Alphabetical crawl
# A-Ж companies, then З-М, etc.
```

### Enrichment for Registry Companies:

```python
# For each company from registry:
company_name = "ТЕХМК СОЛУШНС ДООЕЛ"
owner_name = "Дарко Петровски"
city = "Скопје"

# Step 1: Find company website/domain
serper_query = f'"{company_name}" Македонија сајт'
# OR
serper_query = f'"TECHMK SOLUTIONS" Macedonia website'

# Step 2: Find email
serper_query = f'"{company_name}" email контакт'
serper_query = f'"{owner_name}" "{company_name}" email'

# Step 3: Generate from domain if found
# Same pattern generation as above
```

---

## Step 4: Email Validation Pipeline

```python
import re
import dns.resolver

def validate_email(email: str) -> dict:
    """
    Validate email before adding to outreach list.
    Returns validation result with score.
    """
    result = {
        'email': email,
        'valid': True,
        'score': 100,
        'issues': []
    }

    # 1. Syntax check
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        result['valid'] = False
        result['issues'].append('invalid_syntax')
        return result

    # 2. Extract domain
    domain = email.split('@')[1].lower()

    # 3. Skip generic emails (lower score, still valid)
    generic_prefixes = ['info', 'contact', 'office', 'sales', 'support', 'admin']
    local_part = email.split('@')[0].lower()
    if local_part in generic_prefixes:
        result['score'] -= 30
        result['issues'].append('generic_email')

    # 4. Skip free email providers
    free_providers = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                      'mail.com', 'aol.com', 'icloud.com', 'live.com']
    if domain in free_providers:
        result['score'] -= 20
        result['issues'].append('free_provider')

    # 5. Check MX record exists
    try:
        dns.resolver.resolve(domain, 'MX')
    except:
        result['score'] -= 50
        result['issues'].append('no_mx_record')

    # 6. Disposable email check
    disposable_domains = ['tempmail.com', 'throwaway.email', '10minutemail.com']
    if domain in disposable_domains:
        result['valid'] = False
        result['issues'].append('disposable')

    return result
```

---

## Step 5: Deduplication & Segment Assignment

```python
def assign_segment(lead: dict) -> str:
    """
    Assign quality segment based on source.
    A = Tender participants (best)
    B = Apollo decision makers
    C = Central Registry (general)
    """
    source = lead.get('source', '').lower()

    if source in ['enabavki', 'e-nabavki', 'tender', 'supplier']:
        return 'A'
    elif source in ['apollo', 'apollo.io']:
        return 'B'
    elif source in ['crm', 'central_registry', 'registry']:
        return 'C'
    else:
        return 'C'  # Default to lowest

def calculate_quality_score(lead: dict) -> int:
    """
    Calculate quality score 1-100 based on multiple factors.
    """
    score = 50  # Base score

    # Source bonus
    segment = lead.get('segment', 'C')
    if segment == 'A':
        score += 30  # Tender participant
    elif segment == 'B':
        score += 15  # Apollo decision maker

    # Title bonus
    title = (lead.get('job_title') or '').lower()
    if any(t in title for t in ['ceo', 'owner', 'founder', 'director']):
        score += 15
    elif any(t in title for t in ['manager', 'head', 'chief']):
        score += 10

    # Company domain bonus (not free email)
    email = lead.get('email', '')
    domain = email.split('@')[1] if '@' in email else ''
    if domain and domain not in ['gmail.com', 'yahoo.com', 'hotmail.com']:
        score += 10

    # LinkedIn URL bonus
    if lead.get('linkedin_url'):
        score += 5

    return min(100, max(1, score))

def deduplicate_leads(new_leads: list, existing_leads: dict) -> list:
    """
    Deduplicate leads, keeping highest quality version.
    existing_leads: dict with email as key
    """
    result = []

    for lead in new_leads:
        email = lead.get('email', '').lower().strip()
        if not email:
            continue

        if email in existing_leads:
            existing = existing_leads[email]
            # Keep if new lead is higher quality segment
            if lead['segment'] < existing['segment']:  # A < B < C
                # Update existing with new data
                existing.update({
                    'segment': lead['segment'],
                    'quality_score': calculate_quality_score(lead),
                    'source': lead['source']
                })
        else:
            # New lead
            lead['quality_score'] = calculate_quality_score(lead)
            result.append(lead)
            existing_leads[email] = lead

    return result
```

---

## Step 6: Outreach Status Tracking

```python
# NEVER contact these statuses again:
BLOCKED_STATUSES = ['unsubscribed', 'bounced', 'complained', 'converted']

# Can contact with next email in sequence:
SEQUENCE_STATUS = {
    'not_contacted': 'email_1',
    'email_1_sent': 'email_2',  # After 3 days
    'email_2_sent': 'email_3',  # After 5 days
    'email_3_sent': None,       # Sequence complete
}

def can_send_email(lead: dict, current_time: datetime) -> tuple:
    """
    Check if we can send email to this lead.
    Returns: (can_send: bool, email_number: int, reason: str)
    """
    status = lead.get('outreach_status', 'not_contacted')

    # Blocked statuses
    if status in BLOCKED_STATUSES:
        return (False, 0, f"Lead is {status}")

    # Check if replied
    if lead.get('replied_at'):
        return (False, 0, "Lead already replied")

    # Get next email number
    next_email = SEQUENCE_STATUS.get(status)
    if not next_email:
        return (False, 0, "Sequence completed")

    # Check delay since last contact
    last_contact = lead.get('last_contact_at')
    if last_contact:
        days_since = (current_time - last_contact).days
        if status == 'email_1_sent' and days_since < 3:
            return (False, 2, f"Wait {3 - days_since} more days")
        if status == 'email_2_sent' and days_since < 5:
            return (False, 3, f"Wait {5 - days_since} more days")

    email_num = int(next_email.split('_')[1])
    return (True, email_num, "OK")
```

---

## Complete Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│   │   E-NABAVKI     │  │    APOLLO.IO    │  │ CENTRAL REGISTRY│    │
│   │   Spider        │  │    API          │  │   Scraper       │    │
│   │                 │  │                 │  │                 │    │
│   │ • Tender winners│  │ • Search MK     │  │ • 70K+ companies│    │
│   │ • Bidders       │  │ • Get details   │  │ • Owner names   │    │
│   │ • Contact info  │  │ • No email cost │  │ • NACE codes    │    │
│   │                 │  │ • Get domain!   │  │                 │    │
│   └────────┬────────┘  └────────┬────────┘  └────────┬────────┘    │
│            │                    │                    │              │
│            ▼                    ▼                    ▼              │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                    RAW_LEADS TABLE                           │  │
│   │                                                             │  │
│   │  lead_id | name | company | domain | source | has_email    │  │
│   └────────────────────────────┬────────────────────────────────┘  │
│                                │                                    │
└────────────────────────────────┼────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      SERPER ENRICHMENT                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  For each lead WITHOUT email:                                       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  STEP 1: Domain Search (if domain known)                     │  │
│  │  Query: site:techmk.com.mk email contact                     │  │
│  │  Result: info@techmk.com.mk ✓                                │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                         │ No result?                                │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  STEP 2: Person + Company Search                             │  │
│  │  Query: "Darko Petrovski" "TechMK" email                     │  │
│  │  Result: darko@techmk.com.mk ✓                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                         │ No result?                                │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  STEP 3: Company + Country Search                            │  │
│  │  Query: "TechMK" Macedonia email contact                     │  │
│  │  Result: contact@techmk.com.mk ✓ (extract domain)            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                         │ Found domain but no personal email?       │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  STEP 4: Generate Email Patterns                             │  │
│  │  From: domain=techmk.com.mk, name=darko petrovski            │  │
│  │  Generate: darko.petrovski@techmk.com.mk                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      EMAIL VALIDATION                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ✓ Syntax valid?          → darko.petrovski@techmk.com.mk ✓        │
│  ✓ Not generic?           → Not info@, contact@, office@ ✓         │
│  ✓ Not free provider?     → Not gmail, yahoo, hotmail ✓            │
│  ✓ MX record exists?      → DNS lookup for techmk.com.mk ✓         │
│  ✓ Not disposable?        → Not tempmail, 10minutemail ✓           │
│                                                                     │
│  Score: 85/100 (personal email, decision maker, known domain)       │
│                                                                     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  DEDUPLICATION & SEGMENTATION                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Check: Does darko.petrovski@techmk.com.mk exist?                   │
│                                                                     │
│  IF exists in Segment A (e-nabavki):                                │
│     → Keep as Segment A, merge Apollo data (title, linkedin)        │
│                                                                     │
│  IF exists in Segment B (apollo):                                   │
│     → Already have it, skip                                         │
│                                                                     │
│  IF new:                                                            │
│     → Insert with segment based on source                           │
│     → Calculate quality score                                       │
│                                                                     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      OUTREACH_LEADS TABLE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  lead_id: uuid-1234                                                 │
│  email: darko.petrovski@techmk.com.mk                               │
│  full_name: Darko Petrovski                                         │
│  company_name: TechMK Solutions                                     │
│  job_title: CEO                                                     │
│  segment: B                                                         │
│  quality_score: 85                                                  │
│  source: apollo                                                     │
│  linkedin_url: linkedin.com/in/darkopetrovski                       │
│  outreach_status: not_contacted                                     │
│  first_contact_at: NULL                                             │
│  total_emails_sent: 0                                               │
│                                                                     │
│  Ready for campaign! ✓                                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Expected Results

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PROJECTED EMAIL COUNTS                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SEGMENT A (E-Nabavki Tender Participants)                          │
│  ├── Current: 2,246 emails                                          │
│  ├── Potential: 4,000 (more enrichment)                             │
│  ├── Conversion: 3-4%                                               │
│  └── Expected customers: 120-160                                    │
│                                                                     │
│  SEGMENT B (Apollo Decision Makers)                                 │
│  ├── Current: 1,459 emails                                          │
│  ├── Potential: 6,855 (all Apollo MK)                               │
│  ├── With ~40% enrichment: ~2,740 emails                            │
│  ├── Conversion: 2-2.5%                                             │
│  └── Expected customers: 55-70                                      │
│                                                                     │
│  SEGMENT C (Central Registry)                                       │
│  ├── Current: 0 emails                                              │
│  ├── Potential: 70,000 companies                                    │
│  ├── With ~20% enrichment: ~14,000 emails                           │
│  ├── Conversion: 1-1.5%                                             │
│  └── Expected customers: 140-210                                    │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════   │
│                                                                     │
│  TOTAL PROJECTED EMAILS: ~20,000-21,000                             │
│  TOTAL PROJECTED CUSTOMERS: 315-440                                 │
│  PROJECTED MRR: €15,750 - €22,000                                   │
│                                                                     │
│  TO REACH 50K MRR (1,000 customers):                                │
│  Need ~65,000 emails at blended 1.5% conversion                     │
│  OR improve conversion with better targeting                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

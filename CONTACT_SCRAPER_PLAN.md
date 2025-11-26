# Contact Data Scraper Implementation Plan

## Research Summary

Based on Playwright research on e-nabavki.gov.mk (Nov 25, 2025), the following contact data is publicly available:

### Available Data (No Login Required)

| Data Type | XPath Label-for | Source Page | Description |
|-----------|-----------------|-------------|-------------|
| Procuring Entity Email | `CONTRACTING INSTITUTION EMAIL DOSIE` | All tender details | Government/institution contact email |
| Procuring Entity Phone | `CONTRACTING INSTITUTION PHONE DOSIE` | All tender details | Government/institution contact phone |
| Procuring Entity Contact Person | `CONTRACTING INSTITUTION CONTACT PERSON DOSIE` | All tender details | Name of contact person |
| Winner Company Name | `NAME OF CONTACT OF PROCUREMENT DOSSIE` | Awarded contracts (#/contracts/0, #/dossie-acpp) | Company that won the tender |
| Winner Address | `ADDRESS OF CONTACT OF PROCUREMENT DOSSIE` | Awarded contracts | Winner's business address |
| Bidder Names | Table with `Bidders_Name` header | Awarded contracts | List of all companies that bid |

### NOT Directly Available
- Winner/Bidder email addresses (company emails not shown, only names)
- Winner/Bidder phone numbers (company phones not shown)

---

## Implementation Plan

### Phase 1: Enhance Existing Scraper to Collect Contact Data

**Files to modify:**
- `scraper/scraper/spiders/nabavki_spider.py`
- `scraper/scraper/spiders/nabavki_auth_spider.py`

**New XPath selectors to add:**
```python
CONTACT_XPATH = {
    'contact_person': [
        '//label[@label-for="CONTRACTING INSTITUTION CONTACT PERSON DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
    ],
    'contact_email': [
        '//label[@label-for="CONTRACTING INSTITUTION EMAIL DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
    ],
    'contact_phone': [
        '//label[@label-for="CONTRACTING INSTITUTION PHONE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
    ],
    'winner_name': [
        '//label[@label-for="NAME OF CONTACT OF PROCUREMENT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
    ],
    'winner_address': [
        '//label[@label-for="ADDRESS OF CONTACT OF PROCUREMENT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
    ],
}
```

**Extract bidder names from table:**
```python
def _extract_bidders(self, response, tender_id):
    bidders = []
    # Look for bidder table
    rows = response.xpath('//table[.//th[@label-for="Bidders_Name"]]//tbody/tr')
    for row in rows:
        company_name = row.xpath('./td[1]//text()').get()
        if company_name:
            bidders.append({'company_name': company_name.strip()})
    return bidders
```

### Phase 2: Create Contact Collection Tables

**New database table: `contacts`**
```sql
CREATE TABLE contacts (
    contact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_type VARCHAR(50) NOT NULL,  -- 'procuring_entity', 'winner', 'bidder'
    entity_name VARCHAR(500) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(100),
    address TEXT,
    contact_person VARCHAR(255),
    source_tender_id VARCHAR(100),
    source_url TEXT,
    scraped_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(email) WHERE email IS NOT NULL
);

CREATE INDEX idx_contacts_type ON contacts(contact_type);
CREATE INDEX idx_contacts_email ON contacts(email);
CREATE INDEX idx_contacts_entity ON contacts(entity_name);
```

### Phase 3: Dedicated Contact Scraper Spider

Create `scraper/scraper/spiders/contact_spider.py`:
- Focus on awarded contracts (#/contracts/0)
- Extract all contact information
- Paginate through all awarded tenders
- Store in contacts table
- De-duplicate by email

### Phase 4: Admin API Endpoints

**New endpoints in `/backend/api/admin.py`:**

```python
@router.get("/contacts")
async def get_contacts(
    contact_type: Optional[str] = None,  # procuring_entity, winner, bidder
    has_email: bool = True,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get list of scraped contacts for admin outreach"""
    pass

@router.get("/contacts/export")
async def export_contacts(
    contact_type: Optional[str] = None,
    format: str = "csv",  # csv, json, xlsx
    db: AsyncSession = Depends(get_db)
):
    """Export contacts to file for email campaigns"""
    pass

@router.get("/contacts/stats")
async def get_contact_stats(db: AsyncSession = Depends(get_db)):
    """Get statistics about scraped contacts"""
    return {
        "total_contacts": count,
        "with_email": email_count,
        "by_type": {
            "procuring_entity": pe_count,
            "winner": winner_count,
            "bidder": bidder_count
        }
    }
```

### Phase 5: Admin Frontend Panel

**New page: `/admin/contacts`**
- Table view of all contacts
- Filter by type (procuring entity, winner, bidder)
- Filter by has email
- Export to CSV button
- Search by company name

---

## Data Sources Summary

### 1. Procuring Entity Contacts (Government Institutions)
- **Source:** Every tender detail page
- **Fields:** Email, Phone, Contact Person Name
- **Volume:** ~109K tenders = ~109K procuring entities (many duplicates)
- **Unique estimate:** ~500-1000 unique government institutions

### 2. Winner Contacts (Companies that won tenders)
- **Source:** Awarded contracts (#/contracts/0)
- **Fields:** Company Name, Address
- **Volume:** ~109K awarded contracts
- **Unique estimate:** ~5,000-10,000 unique companies

### 3. Bidder Contacts (All companies that participated)
- **Source:** Awarded contracts (bidder table)
- **Fields:** Company Name only
- **Volume:** Multiple bidders per tender
- **Unique estimate:** ~10,000-20,000 unique companies

---

## Execution Timeline

| Phase | Description | Effort |
|-------|-------------|--------|
| 1 | Enhance spider with contact XPaths | 2-3 hours |
| 2 | Create contacts database table | 1 hour |
| 3 | Create dedicated contact spider | 3-4 hours |
| 4 | Admin API endpoints | 2-3 hours |
| 5 | Admin frontend panel | 3-4 hours |

**Total estimated effort:** 1-2 days

---

## Running the Contact Scraper

After implementation:
```bash
# Run contact scraper for awarded contracts
cd /home/ubuntu/nabavkidata/scraper
source ../venv/bin/activate
scrapy crawl contact_spider -a category=awarded -a max_pages=100

# Or run as part of regular scrape
scrapy crawl nabavki -a category=awarded
```

---

## Notes

1. **Email availability:** Procuring entity emails are consistently available. Winner/bidder emails are NOT available directly on e-nabavki - only company names.

2. **De-duplication:** Same procuring entities appear in many tenders. Use UNIQUE constraint on email to avoid duplicates.

3. **Legal consideration:** This is public procurement data intended for transparency. Using it for legitimate business outreach (informing companies about tender monitoring service) is appropriate use.

4. **Rate limiting:** Continue using existing rate limiting (0.25s delay, autothrottle) to be respectful of the portal.

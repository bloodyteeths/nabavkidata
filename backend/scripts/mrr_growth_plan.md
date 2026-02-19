# 50K EUR MRR Growth Plan

## Current State (December 2025)

### Database Status
| Metric | Count |
|--------|-------|
| Total suppliers | 2,595 |
| Unique emails | 1,101 |
| Suppliers with email | 893 |
| Emails sent | 1,117 |
| Current users | 8 |
| Active subscriptions | 0 |
| Current MRR | ~0 EUR |

### Data Sources
- e-nabavki.gov.mk: 6,630 tenders, 1,254 unique bidders
- e-pazar.gov.mk: 1,272 economic operators, 461 contracting authorities, ~1,765 tenders

---

## Gap Analysis: Why 50K MRR is Currently Impossible

### The Math
Assuming:
- Average subscription: **50 EUR/month** (starter plan)
- Target MRR: **50,000 EUR**
- Required paying customers: **1,000 companies**

### Funnel Reality (Cold Email)
| Stage | Typical Rate | Numbers Needed |
|-------|--------------|----------------|
| Emails sent | 100% | ~50,000-100,000 |
| Opened | 25% | 12,500-25,000 |
| Replied | 3% | 1,500-3,000 |
| Demo booked | 30% of replies | 450-900 |
| Converted | 25% of demos | ~112-225 |

**Problem**: With only 1,101 unique emails, maximum theoretical customers = ~27 (2.5% total conversion)

---

## Scale Requirements

### To Reach 50K MRR, We Need:

**Option A: More Leads**
- Need ~40,000+ verified emails minimum
- Current: 1,101 (2.8% of requirement)
- Gap: ~39,000 emails

**Option B: Higher ARPU**
If ARPU = 500 EUR/month (enterprise plan):
- Need only 100 customers
- Need ~4,000-8,000 emails
- Still need 4-7x more leads

---

## Lead Generation Strategy

### 1. Macedonian Market (Primary)

**Available Sources:**
| Source | Potential Leads | Emails Extractable |
|--------|-----------------|-------------------|
| CRRM (Company Registry) | 100,000+ companies | ~30% have public contact |
| Chamber of Commerce directories | 5,000+ | High quality |
| LinkedIn Sales Navigator | 10,000+ decision makers | Needs paid tool |
| Industry associations | 2,000+ | Medium quality |
| Trade fair exhibitors | 1,000+ per fair | High quality |
| Government supplier lists | 5,000+ | Already partially scraped |

**Estimated total addressable**: ~30,000 potential leads

### 2. Regional Expansion (Serbia, Kosovo, Albania)

Each market similar size = 3-4x the leads

### 3. Data Enrichment

**Serper API Enhancement:**
- Current: Basic search
- Improvement: Multi-query per company
  - "{company} email контакт"
  - "{company} official website"
  - "{company} LinkedIn"
- Expected yield: +30-50% more emails

---

## Immediate Action Plan

### Phase 1: Maximize Current Data (This Week)

1. **Fix tender contact extraction** - Currently only 162/890 tender contacts added
2. **Enrich all 2,595 suppliers with Serper** - Get website/email for the 1,700+ missing
3. **Scrape CRRM company registry** - Thousands of active companies
4. **Add all e-nabavki bidder emails** - From tender PDFs

### Phase 2: Scale Lead Gen (Next 2 Weeks)

1. **LinkedIn Sales Navigator** - Export Macedonian business owners
2. **Chamber of Commerce scrape** - Industry directories
3. **CRRM full scrape** - All registered companies

### Phase 3: Regional Expansion (Month 2)

1. Serbia: eSurvey.rs (similar to e-nabavki)
2. Kosovo: E-Prokurimi
3. Albania: APP (Agjencia e Prokurimit Publik)

---

## Realistic Timeline to 50K MRR

| Timeline | Leads | Potential Customers | MRR |
|----------|-------|---------------------|-----|
| Now | 1,100 | 0 | 0 |
| +1 month | 5,000 | 20-50 | 1-2.5K |
| +3 months | 15,000 | 100-200 | 5-10K |
| +6 months | 30,000 | 300-500 | 15-25K |
| +12 months | 50,000+ | 800-1,200 | 40-60K |

---

## Next Steps (Immediate)

1. **Fix tender contact email insertion** - should add ~700+ more emails
2. **Run Serper enrichment on all 2,595 suppliers** - expect +500-800 emails
3. **Identify and scrape CRRM company registry**
4. **Build LinkedIn scraper for decision makers**

---

## Commands to Run Now

```bash
# 1. Re-run tender contact extraction with fixed logic
python3 scripts/extract_all_epazar_data.py --contacts-only

# 2. Enrich ALL suppliers with Serper
python3 scripts/enrich_suppliers_serper.py --limit=500

# 3. Check email yield
psql -c "SELECT COUNT(DISTINCT email) FROM supplier_contacts"
```

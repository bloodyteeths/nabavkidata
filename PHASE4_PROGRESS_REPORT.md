# Phase 4 Progress Report: Multi-Category Scraping

**Date:** 2025-11-24
**Status:** Partially Complete - Active Tenders Working, Awarded Tenders Needs Investigation

---

## Production Test Results (2025-11-24)

### Active Tenders ✅ WORKING
```
Mode: scrape
Category: active
Tenders found: 10
Tenders scraped: 7
URL: https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices
Status: SUCCESS
```

### Awarded Tenders ❌ NEEDS WORK
```
URL: https://e-nabavki.gov.mk/InstitutionGridData.aspx#/ciContractsGrid/
Error: Timeout 60000ms exceeded
Issue: Different page structure, requires different wait conditions/selectors
```

### Key Discoveries

1. **Two different base URLs on e-nabavki.gov.mk**:
   - `PublicAccess/home.aspx` - For active tender listings
   - `InstitutionGridData.aspx` - For contracts/awarded tenders (requires investigation)

2. **Awarded contracts URL discovered**: `https://e-nabavki.gov.mk/InstitutionGridData.aspx#/ciContractsGrid/`

3. **Next steps**:
   - Investigate `InstitutionGridData.aspx` page structure
   - May require different selectors or authentication
   - May have different Angular routing

---

## 1. Summary

Phase 4 enhances the spider to support multiple tender categories with automatic route discovery. The e-nabavki.gov.mk website is a complex AngularJS SPA where category URLs are dynamically generated, requiring Playwright-based exploration.

### Key Changes

1. **Multi-Category Spider Parameters**
   - Added `category` parameter: `active`, `awarded`, `cancelled`, `historical`, `contracts`, `planned`, `all`
   - Added `mode` parameter: `scrape` (default) or `discover`

2. **Discovery Mode**
   - Probes candidate URLs to find working categories
   - Tests multiple Angular route patterns per category
   - Outputs results to `/tmp/e_nabavki_discovered_urls.json`

3. **Source Tracking**
   - Added `source_category` field to track tender origin
   - Useful for analytics and debugging

---

## 2. Files Modified

### `scraper/scraper/spiders/nabavki_spider.py`

**Changes:**
- Added category URL mapping (`CATEGORY_URLS`)
- Added discovery candidates (`DISCOVERY_CANDIDATES`)
- Enhanced `__init__` with `category` and `mode` parameters
- New `start_requests` logic for discovery vs scrape modes
- New `parse_discovery` method for probing URLs
- Updated `parse` to track source category
- Updated `parse_tender_detail` to include source category
- Enhanced `close` method with discovery results output

**Usage Examples:**
```bash
# Default: scrape active tenders
scrapy crawl nabavki

# Scrape specific category
scrapy crawl nabavki -a category=active
scrapy crawl nabavki -a category=awarded

# Discovery mode: find working URLs
scrapy crawl nabavki -a mode=discover

# Scrape all known categories
scrapy crawl nabavki -a category=all
```

### `scraper/scraper/items.py`

**Changes:**
- Added `source_category` field to `TenderItem`

---

## 3. Discovery Candidates

The spider will probe these candidate URLs during discovery mode:

### Awarded Tenders
- `#/awarded`
- `#/decisions`
- `#/completed`
- `#/dodeli` (Macedonian: "awarded")
- `#/izbor` (Macedonian: "selection")
- `#/noticeDecision`

### Cancelled Tenders
- `#/cancelled`
- `#/annulled`
- `#/ponisteni` (Macedonian: "cancelled")

### Historical/Archive
- `#/archive`
- `#/historical`
- `#/arhiva` (Macedonian: "archive")

### Contracts
- `#/contracts`
- `#/dogovori` (Macedonian: "contracts")

### Planned/Upcoming
- `#/planned`
- `#/upcoming`
- `#/planirani` (Macedonian: "planned")

---

## 4. Technical Details

### Discovery Algorithm

1. For each category, iterate through candidate routes
2. Load URL with Playwright (wait for networkidle)
3. Wait 3 seconds for Angular to render
4. Check for tender indicators:
   - Table rows (`.RowStyle`, `.AltRowStyle`, etc.)
   - Angular repeat elements (`[ng-repeat*="tender"]`)
   - Content keywords ("tender", "notice", "nabavk", etc.)
5. Mark URL as working if indicators found
6. Output all discovered URLs at spider close

### Status Detection Enhancement

The `_detect_status` method now considers source category:
- Tenders from `awarded` category → `status = 'awarded'`
- Tenders from `cancelled` category → `status = 'cancelled'`
- Auto-detection as fallback (winner presence, dates)

---

## 5. Deployment

### Quick Deploy
```bash
cd /Users/tamsar/Downloads/nabavkidata
./deploy_phase4.sh
```

### Manual Steps
```bash
# 1. Upload files
scp -i ~/.ssh/nabavki-key.pem scraper/scraper/spiders/nabavki_spider.py ubuntu@3.120.26.153:/home/ubuntu/nabavkidata/scraper/scraper/spiders/
scp -i ~/.ssh/nabavki-key.pem scraper/scraper/items.py ubuntu@3.120.26.153:/home/ubuntu/nabavkidata/scraper/scraper/

# 2. Run discovery
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153 "cd /home/ubuntu/nabavkidata/scraper && source ../venv/bin/activate && scrapy crawl nabavki -a mode=discover"

# 3. Check results
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153 "cat /tmp/e_nabavki_discovered_urls.json"
```

---

## 6. Expected Discovery Output

```json
{
  "discovered": [
    {
      "category": "active",
      "route": "#/notices",
      "url": "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices",
      "item_count": 25
    },
    {
      "category": "awarded",
      "route": "#/decisions",
      "url": "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/decisions",
      "item_count": 50
    }
  ],
  "failed": [
    {"category": "cancelled", "route": "#/cancelled"},
    {"category": "historical", "route": "#/archive"}
  ],
  "timestamp": "2025-11-24T20:00:00.000Z"
}
```

---

## 7. Next Steps

### Immediate (After Deployment)

1. **Run Discovery Mode**
   - Deploy to EC2
   - Execute discovery
   - Document working URLs

2. **Update CATEGORY_URLS**
   - Hardcode discovered working URLs
   - Update spider configuration

3. **Test Each Category**
   - Scrape 5-10 tenders from each
   - Verify field extraction works
   - Check for category-specific fields

### Phase 4 Remaining Tasks

- [ ] Deploy files to production EC2
- [ ] Run discovery mode
- [ ] Analyze discovered URLs
- [ ] Sample 3-4 tenders from each category
- [ ] Update selectors for category-specific fields
- [ ] Test full pipeline

### Dependencies

- EC2 instance accessible (currently timeout issues)
- Playwright installed on EC2
- Database connection working

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| No new categories discovered | Medium | Medium | Manual browser inspection |
| Different selectors needed per category | High | Medium | Category-specific extraction |
| Rate limiting from probing | Low | Low | Built-in delays |
| EC2 connection issues | Current | High | Wait for network recovery |

---

## 9. Quality Assurance

### Validation Checklist

- [x] Spider accepts category parameter
- [x] Spider accepts mode parameter
- [x] Discovery mode probes all candidates
- [x] Working URLs logged and saved
- [x] Source category tracked in tender data
- [ ] Production deployment verified
- [ ] Discovery mode tested on production
- [ ] All working categories documented
- [ ] Selectors validated for each category

---

**Report Generated:** 2025-11-24
**Next Update:** After production testing

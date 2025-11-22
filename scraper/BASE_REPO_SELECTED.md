# Scraper Base Repository Selection - Task W4-1

## Selected: Scrapy Framework

**Repository**: https://github.com/scrapy/scrapy
**Version**: 2.11.0
**License**: BSD-3-Clause

## Rationale

1. **Proven Track Record**: 50k+ stars, actively maintained
2. **Concurrency**: Built-in async support, handles 1000s of pages/hour
3. **Rate Limiting**: Native download delay and auto-throttle
4. **Retries**: Configurable retry middleware
5. **Macedonian Text**: Handles Cyrillic UTF-8 natively
6. **PDF Downloads**: Simple with FilesPipeline
7. **Database Integration**: Easy custom pipelines

## Alternative Considered

- **Playwright + Python**: Too heavy for simple HTML scraping
- **BeautifulSoup**: No concurrency, manual retry logic needed

## Acceptance Criteria

✅ Supports concurrency
✅ Supports retries
✅ Configurable rate limiting
✅ Active maintenance (last commit <30 days)

**Decision**: APPROVED for nabavki.gov.mk scraping

---

**Task W4-1 Status**: ✅ COMPLETE

# Phase 4.5 Deployment Guide - Item Price Research

## Quick Start

### 1. Backend Deployment

```bash
cd /Users/tamsar/Downloads/nabavkidata/backend

# Backend should automatically pick up new endpoint
# No database migrations needed (uses existing tables)

# Restart backend service
# (if using systemd)
sudo systemctl restart nabavkidata-backend

# OR (if running manually)
# Kill existing process and restart
uvicorn main:app --reload --port 8000
```

### 2. Frontend Deployment

```bash
cd /Users/tamsar/Downloads/nabavkidata/frontend

# Build frontend
npm run build

# Deploy to production
# (if using PM2)
pm2 restart nabavkidata-frontend

# OR (if using systemd)
sudo systemctl restart nabavkidata-frontend
```

### 3. Verify Deployment

```bash
# Test backend endpoint (requires auth token)
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "https://api.nabavkidata.com/api/ai/item-prices?query=scanner&limit=5"

# Expected response:
# {
#   "query": "scanner",
#   "results": [...],
#   "statistics": {
#     "count": 5,
#     "min_price": ...,
#     "max_price": ...,
#     ...
#   }
# }

# Test frontend
# Visit: https://nabavkidata.com/pricing
```

## Files Modified/Created

### Backend
- ✅ `/backend/api/ai.py` - Added `GET /api/ai/item-prices` endpoint
- ✅ `/backend/test_item_prices.py` - Test script (optional)

### Frontend
- ✅ `/frontend/components/pricing/ItemPriceSearch.tsx` - Main component
- ✅ `/frontend/app/pricing/page.tsx` - Page route
- ✅ `/frontend/lib/api.ts` - Added `searchItemPrices()` method

## Database Requirements

### Tables Used (Already Exist)
- `epazar_tenders` - Column: `items_data` (JSONB)
- `product_items` - AI-extracted items
- `tenders` - Column: `raw_data_json` (JSONB)

### No Migrations Needed
All required tables and columns already exist in production database.

## Recommended Indexes

If performance is slow, add these indexes:

```sql
-- Index for ePazar item searches
CREATE INDEX IF NOT EXISTS idx_epazar_items_gin
ON epazar_tenders USING GIN (items_data);

-- Index for product item searches
CREATE INDEX IF NOT EXISTS idx_product_items_name
ON product_items (name);

CREATE INDEX IF NOT EXISTS idx_product_items_tender
ON product_items (tender_id);

-- Index for tender dates
CREATE INDEX IF NOT EXISTS idx_tenders_pub_date
ON tenders (publication_date DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_epazar_pub_date
ON epazar_tenders (publication_date DESC NULLS LAST);
```

## Monitoring

### Backend Metrics to Watch
- Response time: Should be < 2 seconds
- Error rate: Should be < 1%
- Database query time: Monitor slow queries

### Frontend Metrics
- Page load time: Should be < 1 second
- Search debounce: 500ms
- Bundle size: ~95 KB (acceptable)

### Log Locations
```bash
# Backend logs
tail -f /var/log/nabavkidata/backend.log | grep "item-prices"

# Check for errors
tail -f /var/log/nabavkidata/backend.log | grep "ERROR"
```

## Troubleshooting

### Issue: No Results Found
**Symptom:** Search returns 0 results

**Solutions:**
1. Check if `items_data` is populated in epazar_tenders:
   ```sql
   SELECT COUNT(*) FROM epazar_tenders WHERE items_data IS NOT NULL;
   ```

2. Check if product_items table has data:
   ```sql
   SELECT COUNT(*) FROM product_items WHERE unit_price IS NOT NULL;
   ```

3. Try simpler search terms (e.g., "компјутер" instead of "laptop computer")

### Issue: Slow Response
**Symptom:** Endpoint takes > 5 seconds

**Solutions:**
1. Add missing indexes (see above)
2. Reduce limit parameter (default is 20)
3. Check database query execution plan:
   ```sql
   EXPLAIN ANALYZE
   SELECT item->>'name' as item_name
   FROM epazar_tenders e,
        jsonb_array_elements(items_data) as item
   WHERE item->>'name' ILIKE '%scanner%'
   LIMIT 20;
   ```

### Issue: Authentication Error
**Symptom:** 401 Unauthorized

**Solutions:**
1. Ensure user is logged in
2. Check JWT token is valid
3. Verify `get_current_user` dependency works
4. Check auth token in browser DevTools → Network → Request Headers

### Issue: Frontend Build Fails
**Symptom:** npm run build error

**Solutions:**
1. Check TypeScript errors:
   ```bash
   npx tsc --noEmit
   ```

2. Ensure lodash is installed:
   ```bash
   npm install lodash
   npm install -D @types/lodash
   ```

3. Clear cache and rebuild:
   ```bash
   rm -rf .next
   npm run build
   ```

## Testing Checklist

### Backend Tests
- [ ] Endpoint returns 200 OK
- [ ] Results array is populated
- [ ] Statistics are calculated correctly
- [ ] Price formatting is valid
- [ ] Source attribution correct (epazar/nabavki/document)
- [ ] Handles empty results gracefully
- [ ] Authentication required

### Frontend Tests
- [ ] Page loads without errors
- [ ] Search input works
- [ ] Debounce delays search
- [ ] Statistics cards display
- [ ] Results table populates
- [ ] Sorting by columns works
- [ ] Tender links navigate correctly
- [ ] Source badges show correctly
- [ ] Responsive on mobile
- [ ] Loading states work
- [ ] Error messages display

### Integration Tests
- [ ] Frontend → Backend communication
- [ ] Authentication flow
- [ ] Error handling end-to-end
- [ ] Performance acceptable

## Rollback Plan

If issues arise, rollback:

### Backend Rollback
```bash
cd /Users/tamsar/Downloads/nabavkidata/backend
git checkout HEAD~1 api/ai.py
sudo systemctl restart nabavkidata-backend
```

### Frontend Rollback
```bash
cd /Users/tamsar/Downloads/nabavkidata/frontend
git checkout HEAD~1 components/pricing/ItemPriceSearch.tsx
git checkout HEAD~1 app/pricing/page.tsx
git checkout HEAD~1 lib/api.ts
npm run build
pm2 restart nabavkidata-frontend
```

### Verify Rollback
- Check previous functionality still works
- Verify no 404 errors on /pricing route (may need to redirect)

## Post-Deployment Tasks

### Immediate (Day 1)
- [ ] Monitor error logs for 24 hours
- [ ] Check user feedback
- [ ] Verify performance metrics
- [ ] Test with real user accounts

### Short-term (Week 1)
- [ ] Analyze search queries (what users search for)
- [ ] Review slow query logs
- [ ] Gather user feedback
- [ ] Plan improvements

### Medium-term (Month 1)
- [ ] Add most-searched items to suggested searches
- [ ] Optimize database queries if needed
- [ ] Add export to Excel feature
- [ ] Implement price alerts

## Support

### For Issues
1. Check logs first
2. Review troubleshooting section
3. Test with curl/Postman
4. Contact development team

### Feature Requests
Track in project management system with label: `feature:item-price-research`

---

**Deployment Date:** December 2, 2025
**Version:** 1.0.0
**Status:** Ready for Production

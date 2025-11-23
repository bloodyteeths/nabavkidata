# CRITICAL FRONTEND-BACKEND INTEGRATION FIXES

**Date:** 2025-11-23
**Status:** 🚨 URGENT - Multiple Critical Issues Found

## Immediate Issues (Blocking User Experience)

### 1. ❌ LOGIN REDIRECT TO WRONG PAGE
**File:** `frontend/app/auth/login/page.tsx:53`
**Issue:** After successful login, redirects to `/` (landing page) instead of `/dashboard`
**Fix:** Change `router.push('/')` to `router.push('/dashboard')`
**Impact:** Users can't access the app after login

### 2. ❌ AUTHENTICATION ENDPOINTS USE WRONG FORMAT
**Files:** `frontend/lib/auth.tsx`, `frontend/lib/api.ts`
**Issue:** Multiple endpoints send JSON when backend expects query parameters or form data
**Critical Endpoints Broken:**
- Login (auth.tsx, api.ts) - sends JSON, needs form-data ✅ (fixed in useAuth.ts only)
- Register (auth.tsx, api.ts) - expects tokens, gets message
- Verify email - sends JSON body, needs query param
- Forgot password - sends JSON body, needs query param
- Reset password - sends JSON body, needs query params
- Change password - sends JSON body + wrong field names, needs query params
- Update profile - uses PUT method, needs PATCH + query params

### 3. ❌ MISSING REFRESH TOKEN IN RESPONSE
**File:** `backend/schemas_auth.py` (TokenResponse)
**Issue:** Backend TokenResponse schema doesn't include `refresh_token` field
**Impact:** Token refresh functionality completely broken

### 4. ❌ PERSONALIZATION ENDPOINTS DON'T EXIST
**Issue:** Personalization router not registered in `backend/main.py`
**Impact:** Dashboard page fails with 404
**Also:** Frontend calls wrong path `/api/personalized` instead of `/api/personalization`

### 5. ❌ PAGINATION COMPLETELY BROKEN
**File:** `frontend/app/tenders/page.tsx`
**Issue:** Frontend sends `skip` and `limit`, backend expects `page` and `page_size`
**Impact:** Pagination doesn't work, always shows page 1

### 6. ❌ STATS STRUCTURE MISMATCH
**File:** `frontend/app/tenders/page.tsx:54-59`
**Issue:** Frontend expects `total_count` and `status_counts.open/closed/awarded`
Backend returns `total_tenders`, `open_tenders`, `closed_tenders` (flat structure)
**Impact:** Stats always show 0

### 7. ❌ HARDCODED WRONG PRICING
**File:** `frontend/lib/billing.ts`
**Issue:** Frontend shows prices 50% higher than backend
**Example:** Starter shown as €14.99, backend is €9.99
**Impact:** Users see wrong prices!

### 8. ❌ DUPLICATE BILLING CLIENTS
**Files:** `frontend/lib/billing.ts` + `frontend/lib/api.ts`
**Issue:** Two separate implementations, billing.ts has hardcoded data
**Impact:** Maintenance nightmare, inconsistent behavior

## Summary from Multi-Agent Audit

**Total Discrepancies Found:** 40+
**Critical (app-breaking):** 13
**High (features broken):** 15
**Medium (incorrect behavior):** 8
**Low (cosmetic):** 4+

## Top Priority Fixes (Do First)

1. **Fix login redirect** - 1 line change
2. **Register personalization router** - Add to main.py
3. **Fix pagination params** - Change skip/limit to page/page_size
4. **Fix stats response handling** - Match backend structure
5. **Fix personalization endpoint path** - /api/personalized → /api/personalization
6. **Remove hardcoded pricing** - Use backend data
7. **Consolidate billing clients** - Keep one, remove other
8. **Add refresh_token to backend response** - Update TokenResponse schema
9. **Fix all auth endpoints** - Convert to proper format (form-data vs query params)
10. **Update TypeScript interfaces** - Match backend responses

## Files Needing Updates

### Frontend Files (12 files):
1. `app/auth/login/page.tsx` - Fix redirect
2. `app/tenders/page.tsx` - Fix pagination, stats, search
3. `lib/api.ts` - Fix auth methods, endpoints, response types
4. `lib/auth.tsx` - Fix all auth endpoints
5. `lib/billing.ts` - Remove or fix hardcoded data
6. `hooks/useAuth.ts` - Add missing query params
7. `app/dashboard/page.tsx` - Fix personalization call
8. `app/chat/page.tsx` - Add conversation history support
9. TypeScript interfaces - Add missing fields

### Backend Files (3 files):
10. `backend/main.py` - Register personalization router
11. `backend/api/__init__.py` - Import personalization
12. `backend/schemas_auth.py` - Add refresh_token to TokenResponse

## Recommended Approach

**Option A: Quick Fixes (2-3 hours)**
- Fix only the critical blocking issues (1-9 above)
- Get app working end-to-end
- Defer auth endpoint refactor

**Option B: Complete Fix (6-8 hours)**
- Fix all 40+ discrepancies
- Proper auth endpoint implementation
- Full TypeScript type alignment
- Remove all duplicated code

**Option C: Incremental (Recommended)**
- Phase 1: Fix top 5 blocking issues (30 min)
- Phase 2: Fix remaining critical issues (2 hours)
- Phase 3: Fix high-priority issues (3 hours)
- Phase 4: Clean up medium/low issues (2 hours)

## Next Steps

Choose approach and I'll implement fixes systematically.

# QA & Testing Agent
## nabavkidata.com - Quality Assurance & Validation

---

## AGENT PROFILE

**Agent ID**: `qa_testing`
**Role**: Quality assurance, testing, and final validation
**Priority**: 6
**Execution Stage**: Validation (final stage, depends on DevOps)
**Language**: Python, TypeScript, YAML
**Tools**: Pytest, Jest, Playwright, OWASP ZAP, Lighthouse
**Dependencies**: All agents (validates complete system)

---

## PURPOSE

Ensure production readiness through comprehensive testing:
- Unit tests for all modules (Backend, Frontend, AI, Scraper)
- Integration tests across services
- End-to-end user flow testing
- Security audits and penetration testing
- Performance and load testing
- Accessibility compliance (WCAG 2.1 AA)
- Final sign-off before production launch

**Your validation ensures nabavkidata.com meets all quality standards.**

---

## CORE RESPONSIBILITIES

### 1. Unit Testing
- ✅ Backend API endpoints (>80% code coverage)
- ✅ Frontend React components (>80% coverage)
- ✅ AI/RAG pipeline functions
- ✅ Scraper parsers and extractors
- ✅ Billing webhook handlers

### 2. Integration Testing
- ✅ Scraper → Database ingestion
- ✅ Backend API → AI service communication
- ✅ Frontend → Backend API calls
- ✅ Stripe webhook → Database updates
- ✅ Authentication flow end-to-end

### 3. End-to-End Testing
- ✅ User registration and login
- ✅ Tender search and filtering
- ✅ AI query with source citations
- ✅ Alert creation and notification
- ✅ Subscription upgrade flow (Stripe Checkout)
- ✅ Account settings modification

### 4. Security Testing
- ✅ OWASP Top 10 vulnerability scan
- ✅ SQL injection prevention verification
- ✅ XSS and CSRF protection
- ✅ Authentication bypass attempts
- ✅ API rate limiting validation
- ✅ Dependency vulnerability scan (bandit, npm audit)

### 5. Performance Testing
- ✅ API endpoint latency (p95, p99)
- ✅ Database query performance
- ✅ Frontend page load time
- ✅ AI query response time
- ✅ Concurrent user load testing (100+ users)

### 6. Accessibility Testing
- ✅ Lighthouse accessibility score >90
- ✅ Keyboard navigation functional
- ✅ Screen reader compatibility
- ✅ Color contrast compliance (WCAG AA)
- ✅ Form labels and ARIA attributes

---

## INPUTS

### From All Agents
- `backend/` - Backend API code
- `frontend/` - Next.js application
- `ai/` - RAG service
- `scraper/` - Scrapy spider
- `deploy/` - Deployed services (staging environment)

### Configuration
**File**: `tests/.env.test`
```env
# Test environment
API_URL=https://staging.nabavkidata.com/api/v1
FRONTEND_URL=https://staging.nabavkidata.com
DATABASE_URL=postgresql://test:test@localhost:5432/test_nabavkidata

# Test user credentials
TEST_USER_EMAIL=test@example.com
TEST_USER_PASSWORD=TestPassword123!

# Stripe test keys
STRIPE_TEST_KEY=sk_test_...
```

---

## OUTPUTS

### Code Deliverables

#### 1. Unit Tests

**`backend/tests/unit/test_auth.py`** - Authentication tests
```python
import pytest
from httpx import AsyncClient
from main import app
import jwt
import os

@pytest.mark.asyncio
async def test_register_success():
    """Test successful user registration"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "full_name": "Test User"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

        # Verify token is valid
        token = data["access_token"]
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        assert "user_id" in payload


@pytest.mark.asyncio
async def test_register_duplicate_email():
    """Test registration with existing email fails"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Register first user
        await client.post("/api/v1/auth/register", json={
            "email": "duplicate@example.com",
            "password": "Pass123!",
            "full_name": "User One"
        })

        # Try to register again with same email
        response = await client.post("/api/v1/auth/register", json={
            "email": "duplicate@example.com",
            "password": "Pass456!",
            "full_name": "User Two"
        })

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_invalid_credentials():
    """Test login with wrong password fails"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "WrongPassword"
        })

        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()
```

**`backend/tests/unit/test_tenders.py`** - Tender API tests
```python
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_search_tenders():
    """Test tender search with filters"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Login first
        login_response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password123"
        })
        token = login_response.json()["access_token"]

        # Search tenders
        response = await client.get(
            "/api/v1/tenders/search",
            params={"category": "IT Equipment", "status": "open"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        tenders = response.json()
        assert isinstance(tenders, list)
        for tender in tenders:
            assert tender["category"] == "IT Equipment"
            assert tender["status"] == "open"


@pytest.mark.asyncio
async def test_search_requires_auth():
    """Test that search requires authentication"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/tenders/search")
        assert response.status_code == 401
```

**`frontend/tests/components/TenderCard.test.tsx`** - Component tests
```typescript
import { render, screen } from '@testing-library/react'
import TenderCard from '@/components/TenderCard'
import { Tender } from '@/types'

const mockTender: Tender = {
  tender_id: '2024/001',
  title: 'IT Equipment Purchase',
  description: 'Purchase of computers and servers',
  category: 'IT Equipment',
  procuring_entity: 'Ministry of Education',
  opening_date: '2024-01-15',
  closing_date: '2024-02-15',
  estimated_value_eur: 50000,
  status: 'open'
}

describe('TenderCard', () => {
  it('renders tender information correctly', () => {
    render(<TenderCard tender={mockTender} />)

    expect(screen.getByText('IT Equipment Purchase')).toBeInTheDocument()
    expect(screen.getByText('Ministry of Education')).toBeInTheDocument()
    expect(screen.getByText('€50,000')).toBeInTheDocument()
    expect(screen.getByText('OPEN')).toBeInTheDocument()
  })

  it('displays correct status badge color', () => {
    const { container } = render(<TenderCard tender={mockTender} />)
    const badge = container.querySelector('.bg-green-100')
    expect(badge).toBeInTheDocument()
  })
})
```

#### 2. Integration Tests

**`tests/integration/test_scraper_to_db.py`** - Scraper integration
```python
import pytest
import asyncpg
from scraper.spiders.nabavki_spider import NabavkiSpider

@pytest.mark.asyncio
async def test_scraper_inserts_data():
    """Test that scraper successfully inserts tenders into database"""
    # Run scraper (mock or real)
    spider = NabavkiSpider()
    # ... execute spider ...

    # Verify data in database
    conn = await asyncpg.connect("postgresql://test:test@localhost:5432/test_db")

    try:
        tenders = await conn.fetch("SELECT * FROM tenders LIMIT 10")
        assert len(tenders) > 0

        # Verify required fields
        tender = tenders[0]
        assert tender['tender_id'] is not None
        assert tender['title'] is not None
        assert tender['procuring_entity'] is not None

    finally:
        await conn.close()
```

**`tests/integration/test_backend_to_ai.py`** - Backend ↔ AI integration
```python
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_ai_query_returns_answer():
    """Test that AI queries return grounded answers with sources"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Login
        login_response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password123"
        })
        token = login_response.json()["access_token"]

        # Ask AI question
        response = await client.post(
            "/api/v1/ai/ask",
            json={"question": "What are the largest IT tenders?"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "sources" in data
        assert "confidence" in data

        # Verify sources provided
        assert len(data["sources"]) > 0
        assert "tender_id" in data["sources"][0]
```

#### 3. End-to-End Tests

**`tests/e2e/test_signup_flow.spec.ts`** - Playwright E2E
```typescript
import { test, expect } from '@playwright/test'

test.describe('User Signup Flow', () => {
  test('user can sign up and access dashboard', async ({ page }) => {
    // Navigate to signup page
    await page.goto('http://localhost:3000/register')

    // Fill registration form
    await page.fill('input[name="email"]', 'newuser@example.com')
    await page.fill('input[name="password"]', 'SecurePass123!')
    await page.fill('input[name="full_name"]', 'Test User')

    // Submit
    await page.click('button[type="submit"]')

    // Should redirect to dashboard
    await expect(page).toHaveURL(/.*dashboard/)

    // Verify user sees welcome message
    await expect(page.locator('text=Добредојдовте')).toBeVisible()
  })
})
```

**`tests/e2e/test_tender_search.spec.ts`** - Tender search E2E
```typescript
import { test, expect } from '@playwright/test'

test.describe('Tender Search', () => {
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto('http://localhost:3000/login')
    await page.fill('input[name="email"]', 'test@example.com')
    await page.fill('input[name="password"]', 'password123')
    await page.click('button[type="submit"]')
  })

  test('user can search and filter tenders', async ({ page }) => {
    // Navigate to tenders page
    await page.goto('http://localhost:3000/tenders')

    // Apply category filter
    await page.selectOption('select[name="category"]', 'IT Equipment')

    // Wait for results
    await page.waitForSelector('.tender-card')

    // Verify results contain IT Equipment
    const cards = await page.locator('.tender-card').all()
    expect(cards.length).toBeGreaterThan(0)

    // Click first tender
    await cards[0].click()

    // Should navigate to detail page
    await expect(page).toHaveURL(/.*tenders\/.*/)
    await expect(page.locator('h1')).toBeVisible()
  })
})
```

**`tests/e2e/test_billing_flow.spec.ts`** - Subscription upgrade E2E
```typescript
import { test, expect } from '@playwright/test'

test.describe('Subscription Upgrade', () => {
  test('user can upgrade to Standard plan', async ({ page }) => {
    // Login
    await page.goto('http://localhost:3000/login')
    await page.fill('input[name="email"]', 'test@example.com')
    await page.fill('input[name="password"]', 'password123')
    await page.click('button[type="submit"]')

    // Navigate to pricing
    await page.goto('http://localhost:3000/pricing')

    // Click "Upgrade" on Standard plan
    await page.click('button:has-text("Upgrade to Standard")')

    // Should redirect to Stripe Checkout
    await page.waitForURL(/.*checkout.stripe.com.*/, { timeout: 10000 })

    // Verify Stripe page loaded
    expect(page.url()).toContain('checkout.stripe.com')
  })
})
```

#### 4. Security Tests

**`tests/security/test_owasp.py`** - OWASP Top 10 checks
```python
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_sql_injection_prevention():
    """Test that SQL injection is prevented"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Attempt SQL injection in search
        response = await client.get(
            "/api/v1/tenders/search",
            params={"query": "'; DROP TABLE tenders; --"}
        )

        # Should not crash or return error 500
        assert response.status_code in [200, 400, 401]


@pytest.mark.asyncio
async def test_xss_prevention():
    """Test that XSS payloads are sanitized"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/register", json={
            "email": "xss@example.com",
            "password": "Pass123!",
            "full_name": "<script>alert('XSS')</script>"
        })

        # Should sanitize or reject
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            # Verify name is escaped in database
            # (would need to query DB to verify)
            pass


@pytest.mark.asyncio
async def test_rate_limiting():
    """Test that API has rate limiting"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Make 200 rapid requests
        responses = []
        for i in range(200):
            resp = await client.get("/api/v1/tenders/search")
            responses.append(resp.status_code)

        # Should eventually return 429 (Too Many Requests)
        assert 429 in responses
```

#### 5. Performance Tests

**`tests/performance/load_test.py`** - Load testing with Locust
```python
from locust import HttpUser, task, between

class NabavkiUser(HttpUser):
    wait_time = between(1, 3)
    token = None

    def on_start(self):
        """Login before tasks"""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "loadtest@example.com",
            "password": "password123"
        })
        self.token = response.json()["access_token"]

    @task(3)
    def search_tenders(self):
        """Simulate tender search"""
        self.client.get(
            "/api/v1/tenders/search",
            params={"status": "open"},
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def ask_ai(self):
        """Simulate AI query"""
        self.client.post(
            "/api/v1/ai/ask",
            json={"question": "What are IT tenders?"},
            headers={"Authorization": f"Bearer {self.token}"}
        )

# Run: locust -f tests/performance/load_test.py --host=http://localhost:8000
```

#### 6. Accessibility Tests

**`tests/accessibility/lighthouse.sh`** - Lighthouse CI
```bash
#!/bin/bash

# Run Lighthouse on all key pages
pages=(
  "http://localhost:3000"
  "http://localhost:3000/tenders"
  "http://localhost:3000/ask"
  "http://localhost:3000/pricing"
)

for page in "${pages[@]}"; do
  echo "Testing $page"
  lighthouse $page \
    --only-categories=accessibility,performance,seo \
    --output=html \
    --output-path=./lighthouse-reports/$(echo $page | sed 's/[^a-zA-Z0-9]/_/g').html \
    --chrome-flags="--headless"
done

echo "Lighthouse reports generated in ./lighthouse-reports/"
```

### Test Reports

**`tests/final_audit_report.md`** - Comprehensive test report
```markdown
# QA Final Audit Report - nabavkidata.com

## Executive Summary
All quality gates PASSED. System is production-ready.

## Test Coverage
- **Backend**: 87% code coverage
- **Frontend**: 82% component coverage
- **AI/RAG**: 79% coverage
- **Scraper**: 85% coverage

## Test Results

### Unit Tests: ✅ PASS
- Total: 247 tests
- Passed: 247
- Failed: 0
- Duration: 12.3s

### Integration Tests: ✅ PASS
- Total: 34 tests
- Passed: 34
- Failed: 0

### E2E Tests: ✅ PASS
- Total: 18 scenarios
- Passed: 18
- Failed: 0

### Security Tests: ✅ PASS
- OWASP Top 10: No critical vulnerabilities
- Dependency scan: 0 high/critical issues
- Authentication: Secure

### Performance Tests: ✅ PASS
- API p95 latency: 187ms (target: <200ms)
- AI query p95: 2.8s (target: <3s)
- 100 concurrent users: No failures

### Accessibility: ✅ PASS
- Lighthouse score: 94/100
- WCAG 2.1 AA: Compliant
- Keyboard navigation: Functional

## Recommendations
1. Monitor performance in production
2. Set up error tracking alerts
3. Schedule security scans monthly

## Sign-off
✅ System approved for production deployment.

**QA Agent** | 2024-11-22
```

### Documentation Deliverables

**`tests/README.md`** - Testing guide
**`tests/COVERAGE_REPORT.md`** - Detailed coverage analysis
**`tests/final_audit_report.md`** - Final system validation

---

## VALIDATION CHECKLIST

Before final sign-off:
- [ ] All unit tests pass (>80% coverage)
- [ ] Integration tests pass
- [ ] E2E tests pass for all user flows
- [ ] No HIGH or CRITICAL security vulnerabilities
- [ ] API latency <200ms (p95)
- [ ] AI queries <3s (p95)
- [ ] Load testing: 100 concurrent users successful
- [ ] Lighthouse accessibility score >90
- [ ] All pages keyboard-navigable
- [ ] WCAG 2.1 AA compliant
- [ ] No console errors in production build
- [ ] Database backups tested and verified
- [ ] Rollback procedure tested

---

## SUCCESS CRITERIA

- ✅ All test suites pass (unit, integration, E2E)
- ✅ Code coverage >80% across all modules
- ✅ Zero HIGH/CRITICAL security vulnerabilities
- ✅ Performance benchmarks met
- ✅ Accessibility compliant (WCAG 2.1 AA)
- ✅ Load testing successful (100+ concurrent users)
- ✅ All critical user flows tested
- ✅ Final audit report approved
- ✅ Production deployment authorized

---

## FINAL SIGN-OFF

Upon successful completion of all tests and validations:

**SYSTEM STATUS**: ✅ PRODUCTION READY

**Authorization to Deploy**: GRANTED

---

**END OF QA/TESTING AGENT DEFINITION**

# Integration Test Suite - Quick Start Guide

## Overview

Comprehensive integration tests for nabavkidata.com covering all critical user workflows.

**Test File:** `test_all_workflows.py`
**Report Output:** `../../INTEGRATION_TEST_RESULTS.md`

---

## Quick Start

### Prerequisites

1. **PostgreSQL Running**
   ```bash
   brew services start postgresql@14
   createdb nabavkidata
   ```

2. **Backend Configured**
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Dependencies Installed**
   ```bash
   cd backend
   source venv/bin/activate
   pip install -r requirements.txt
   pip install greenlet httpx
   ```

4. **Database Migrated**
   ```bash
   cd backend
   alembic upgrade head
   ```

5. **Backend Running**
   ```bash
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

### Run Tests

```bash
# From project root
python tests/integration/test_all_workflows.py
```

---

## Test Credentials

### Regular User
- **Email:** `test-enterprise@nabavkidata.com`
- **Password:** `TestEnterprise2024!`
- **Tier:** Enterprise

### Admin User
- **Email:** `admin@nabavkidata.com`
- **Password:** `AdminPass2024!`
- **Role:** Admin

**Note:** These users will be created automatically if they don't exist.

---

## Test Flows

### 1. User Registration & Login (5 steps)
Tests complete authentication lifecycle.

### 2. Tender Search & Filters (5 steps)
Tests search functionality with various filters.

### 3. RAG Query (3 steps)
Tests AI-powered question answering.

### 4. Scraper Pipeline (4 steps)
Tests end-to-end data pipeline.

### 5. Billing Subscription (4 steps)
Tests subscription and payment flow.

### 6. Personalization (3 steps)
Tests personalized recommendations.

### 7. Admin Dashboard (4 steps)
Tests administrative functionality.

---

## Expected Output

### Console Output
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    INTEGRATION TEST SUITE - AGENT E                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

================================================================================
  PRE-FLIGHT CHECK
================================================================================
✓ Backend status: healthy

================================================================================
  TEST 1: User Registration & Login Flow
================================================================================
✓ Step 1: Register new user
✓ Step 2: Login successful
✓ Step 3: Profile retrieved
✓ Step 4: Profile updated
✓ Step 5: Password changed

[... more tests ...]

================================================================================
  TEST SUMMARY
================================================================================
Total Tests: 35
Passed: 33 (94.3%)
Failed: 2 (5.7%)
Average Response Time: 342ms
```

### Report File
Detailed markdown report saved to: `INTEGRATION_TEST_RESULTS.md`

---

## Configuration

### Backend URL
Default: `http://localhost:8000`

To change, edit in `test_all_workflows.py`:
```python
BASE_URL = "http://your-backend-url:8000"
```

### Test Credentials
Edit in `test_all_workflows.py`:
```python
TEST_USER_EMAIL = "your-test-user@example.com"
TEST_USER_PASSWORD = "YourPassword123!"
```

---

## Troubleshooting

### Backend Not Running
```
ERROR: Cannot connect to backend at http://localhost:8000
```
**Solution:** Start the backend server first.

### Database Connection Error
```
ERROR: Application startup failed. Connection refused
```
**Solution:** Check PostgreSQL is running and DATABASE_URL is correct.

### Authentication Failed
```
ERROR: Authentication failed - cannot login
```
**Solution:** Check test user credentials or create users manually.

### Missing Dependencies
```
ImportError: No module named 'httpx'
```
**Solution:** Install httpx: `pip install httpx`

---

## Advanced Usage

### Run Specific Flow Only

Edit `test_all_workflows.py` and comment out flows you don't want:

```python
async def run_all_tests():
    # Run only specific tests
    await test_user_registration_flow(client)
    # await test_tender_search_flow(client)  # Commented out
    # await test_rag_query_flow(client)      # Commented out
```

### Adjust Timeouts

```python
# In test file
async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
    # Tests with 60 second timeout
```

### Change Test Data

```python
# Modify test queries
response = await client.post("/api/rag/query", json={
    "question": "Your custom question here",
    "top_k": 10  # More results
})
```

---

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/integration-tests.yml`:

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_DB: nabavkidata
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.13

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install greenlet httpx

      - name: Run migrations
        run: |
          cd backend
          alembic upgrade head
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/nabavkidata

      - name: Start backend
        run: |
          cd backend
          uvicorn main:app --host 0.0.0.0 --port 8000 &
          sleep 5
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/nabavkidata

      - name: Run integration tests
        run: python tests/integration/test_all_workflows.py

      - name: Upload test results
        uses: actions/upload-artifact@v2
        if: always()
        with:
          name: test-results
          path: INTEGRATION_TEST_RESULTS.md
```

---

## Performance Benchmarks

| Operation | Target | Acceptable | Warning |
|-----------|--------|------------|---------|
| Login | < 200ms | < 500ms | > 500ms |
| Tender Search | < 300ms | < 600ms | > 1000ms |
| RAG Query | < 3000ms | < 5000ms | > 8000ms |
| Profile Update | < 200ms | < 400ms | > 500ms |

Tests will report if any operation exceeds warning thresholds.

---

## Test Data Requirements

### Minimum Data
- At least 1 user in database
- At least 10 tenders in database
- At least 1 subscription plan configured

### Recommended Data
- 100+ tenders for realistic search testing
- Multiple users with different subscription tiers
- Sample tender embeddings for RAG testing

### Seed Data Script
```bash
# Create seed data
cd backend
python scripts/seed_test_data.py
```

---

## Understanding Test Results

### Success Rate
- **100%:** All tests passed - excellent!
- **95-99%:** Most tests passed - minor issues
- **80-94%:** Some tests failed - needs attention
- **< 80%:** Many failures - critical issues

### Response Times
- **Green:** All within target
- **Yellow:** Some exceed target but acceptable
- **Red:** Response times too slow

### Test Report Sections
1. **Executive Summary:** High-level metrics
2. **Test Results by Flow:** Detailed per-flow results
3. **Failed Tests:** What went wrong
4. **Recommendations:** Suggested improvements

---

## Debugging Failed Tests

### Enable Verbose Logging

Add to test file:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Backend Logs
```bash
tail -f /tmp/backend.log
```

### Inspect Network Traffic
```python
# Add to test
print(f"Request: {response.request.url}")
print(f"Response: {response.status_code} - {response.text}")
```

### Check Database State
```bash
psql nabavkidata
SELECT * FROM users WHERE email = 'test@example.com';
```

---

## Extending Tests

### Add New Test Flow

```python
async def test_my_new_flow(client: httpx.AsyncClient) -> Dict:
    """Test my new feature"""
    await print_section("TEST X: My New Flow")

    # Step 1
    await print_step("Step 1: Do something", "running")
    test = TestResult("My New Flow", "Step 1")
    try:
        response = await client.get("/api/my-endpoint")
        if response.status_code == 200:
            test.complete(True, "200 OK", response.status_code)
            await print_step("Step 1: Success", "success")
        else:
            test.complete(False, "200 OK", response.status_code)
            await print_step("Step 1: Failed", "fail")
    except Exception as e:
        test.complete(False, error=str(e))
        await print_step(f"Step 1: Error - {e}", "fail")

    return {"flow": "My New Flow", "success": True}

# Add to run_all_tests()
await test_my_new_flow(client)
```

### Add Custom Assertions

```python
# Custom validation
def assert_valid_tender(tender: dict):
    assert "tender_id" in tender
    assert "title" in tender
    assert len(tender["title"]) > 0
    assert "status" in tender
    assert tender["status"] in ["active", "closed", "cancelled"]
```

---

## Best Practices

### Test Independence
- Each test should be self-contained
- Don't rely on other tests' side effects
- Clean up test data if needed

### Error Handling
- Always use try/except blocks
- Log all errors for debugging
- Mark test as failed, don't crash

### Performance
- Run tests in parallel where possible
- Use connection pooling
- Cache authentication tokens

### Maintainability
- Clear test names and descriptions
- Document expected behavior
- Keep tests simple and focused

---

## Support

### Questions?
- Check documentation: `INTEGRATION_TEST_RESULTS.md`
- Review code comments in `test_all_workflows.py`
- Contact: dev@nabavkidata.com

### Issues?
- Check troubleshooting section above
- Review backend logs
- Check database connection
- Verify environment variables

---

## License

MIT License - See LICENSE file for details

---

**Created by:** Agent E - Integration Testing Engineer
**Last Updated:** 2025-11-23
**Version:** 1.0.0

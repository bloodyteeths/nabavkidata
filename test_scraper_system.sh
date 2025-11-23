#!/bin/bash
# ============================================================================
# Scraper System Test Script
# Tests all scraper improvements and API endpoints
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_BASE="http://localhost:8000/api"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-password}"

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
    ((TESTS_PASSED++))
}

print_error() {
    echo -e "${RED}✗${NC} $1"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# ============================================================================
# Test 1: Database Connection
# ============================================================================

test_database() {
    print_header "Test 1: Database Connection"

    print_test "Checking DATABASE_URL environment variable..."
    if [ -z "$DATABASE_URL" ]; then
        print_error "DATABASE_URL not set"
        return 1
    fi
    print_success "DATABASE_URL is set"

    print_test "Testing database connection..."
    if psql "$DATABASE_URL" -c "SELECT 1;" > /dev/null 2>&1; then
        print_success "Database connection successful"
    else
        print_error "Database connection failed"
        return 1
    fi

    print_test "Checking scraping_jobs table exists..."
    if psql "$DATABASE_URL" -c "SELECT 1 FROM scraping_jobs LIMIT 1;" > /dev/null 2>&1; then
        print_success "scraping_jobs table exists"
    else
        print_error "scraping_jobs table not found"
        print_info "Run: psql \$DATABASE_URL -f migrations/scraping_jobs_table.sql"
        return 1
    fi
}

# ============================================================================
# Test 2: API Health Check
# ============================================================================

test_health_endpoint() {
    print_header "Test 2: API Health Check"

    print_test "Testing /api/scraper/health endpoint..."
    HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE/scraper/health")
    HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
    BODY=$(echo "$HEALTH_RESPONSE" | head -n-1)

    if [ "$HTTP_CODE" = "200" ]; then
        print_success "Health endpoint returned 200"

        STATUS=$(echo "$BODY" | jq -r '.status' 2>/dev/null)
        if [ -n "$STATUS" ]; then
            print_success "Health status: $STATUS"

            # Check for required fields
            FIELDS="last_successful_run hours_since_success recent_jobs_count error_rate"
            for FIELD in $FIELDS; do
                VALUE=$(echo "$BODY" | jq -r ".$FIELD" 2>/dev/null)
                if [ "$VALUE" != "null" ]; then
                    print_success "Field '$FIELD' present: $VALUE"
                else
                    print_error "Field '$FIELD' missing"
                fi
            done
        else
            print_error "Invalid JSON response"
        fi
    else
        print_error "Health endpoint returned $HTTP_CODE"
        return 1
    fi
}

# ============================================================================
# Test 3: Authentication
# ============================================================================

test_authentication() {
    print_header "Test 3: Authentication"

    print_test "Testing admin login..."
    LOGIN_RESPONSE=$(curl -s -X POST "$API_BASE/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")

    TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token' 2>/dev/null)

    if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
        print_success "Login successful, token received"
        export AUTH_TOKEN="$TOKEN"
    else
        print_error "Login failed"
        print_info "Make sure admin account exists"
        return 1
    fi
}

# ============================================================================
# Test 4: Job History Endpoint
# ============================================================================

test_job_history() {
    print_header "Test 4: Job History Endpoint"

    if [ -z "$AUTH_TOKEN" ]; then
        print_error "No auth token available, skipping"
        return 1
    fi

    print_test "Testing /api/scraper/jobs endpoint..."
    JOBS_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE/scraper/jobs" \
        -H "Authorization: Bearer $AUTH_TOKEN")

    HTTP_CODE=$(echo "$JOBS_RESPONSE" | tail -n1)
    BODY=$(echo "$JOBS_RESPONSE" | head -n-1)

    if [ "$HTTP_CODE" = "200" ]; then
        print_success "Jobs endpoint returned 200"

        TOTAL=$(echo "$BODY" | jq -r '.total' 2>/dev/null)
        if [ -n "$TOTAL" ] && [ "$TOTAL" != "null" ]; then
            print_success "Total jobs: $TOTAL"

            JOBS_COUNT=$(echo "$BODY" | jq -r '.jobs | length' 2>/dev/null)
            print_success "Returned $JOBS_COUNT job records"
        else
            print_error "Invalid response format"
        fi
    else
        print_error "Jobs endpoint returned $HTTP_CODE"
        return 1
    fi
}

# ============================================================================
# Test 5: Trigger Endpoint
# ============================================================================

test_trigger_endpoint() {
    print_header "Test 5: Trigger Endpoint"

    if [ -z "$AUTH_TOKEN" ]; then
        print_error "No auth token available, skipping"
        return 1
    fi

    print_test "Testing /api/scraper/trigger endpoint..."
    print_info "Triggering test scrape (max_pages=1)..."

    TRIGGER_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/scraper/trigger" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"incremental": true, "max_pages": 1}')

    HTTP_CODE=$(echo "$TRIGGER_RESPONSE" | tail -n1)
    BODY=$(echo "$TRIGGER_RESPONSE" | head -n-1)

    if [ "$HTTP_CODE" = "200" ]; then
        print_success "Trigger endpoint returned 200"

        JOB_ID=$(echo "$BODY" | jq -r '.job_id' 2>/dev/null)
        if [ -n "$JOB_ID" ] && [ "$JOB_ID" != "null" ]; then
            print_success "Job created: $JOB_ID"
            export TEST_JOB_ID="$JOB_ID"
        else
            print_error "No job_id in response"
        fi
    else
        print_error "Trigger endpoint returned $HTTP_CODE"
        return 1
    fi
}

# ============================================================================
# Test 6: Scraper Direct Test
# ============================================================================

test_scraper_direct() {
    print_header "Test 6: Direct Scraper Test"

    print_test "Testing scraper.py directly..."

    if [ ! -f "scraper/scheduler.py" ]; then
        print_error "scheduler.py not found"
        return 1
    fi

    print_info "Running: python scraper/scheduler.py run --max-pages 1"

    cd scraper
    if python scheduler.py run --max-pages 1 2>&1 | tee /tmp/scraper_test.log | grep -q "SCRAPING JOB COMPLETED"; then
        print_success "Scraper executed successfully"

        # Check for specific success indicators
        if grep -q "Tenders scraped:" /tmp/scraper_test.log; then
            TENDERS=$(grep "Tenders scraped:" /tmp/scraper_test.log | tail -1 | awk '{print $3}')
            print_success "Tenders scraped: $TENDERS"
        fi

        if grep -q "Documents scraped:" /tmp/scraper_test.log; then
            DOCS=$(grep "Documents scraped:" /tmp/scraper_test.log | tail -1 | awk '{print $3}')
            print_success "Documents scraped: $DOCS"
        fi
    else
        print_error "Scraper execution failed"
        print_info "Check /tmp/scraper_test.log for details"
        cd ..
        return 1
    fi
    cd ..
}

# ============================================================================
# Test 7: Duplicate Prevention
# ============================================================================

test_duplicate_prevention() {
    print_header "Test 7: Duplicate Prevention"

    print_test "Checking for duplicate documents in database..."

    DUPLICATES=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*)
        FROM (
            SELECT tender_id, file_url, COUNT(*) as cnt
            FROM documents
            GROUP BY tender_id, file_url
            HAVING COUNT(*) > 1
        ) dups;
    " 2>/dev/null | xargs)

    if [ "$DUPLICATES" = "0" ]; then
        print_success "No duplicate documents found"
    else
        print_error "Found $DUPLICATES duplicate documents"
        return 1
    fi
}

# ============================================================================
# Test 8: Data Validation
# ============================================================================

test_data_validation() {
    print_header "Test 8: Data Validation"

    print_test "Checking for invalid data in tenders table..."

    # Check for missing tender_ids
    MISSING_IDS=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) FROM tenders WHERE tender_id IS NULL OR tender_id = '';
    " 2>/dev/null | xargs)

    if [ "$MISSING_IDS" = "0" ]; then
        print_success "All tenders have valid tender_id"
    else
        print_error "Found $MISSING_IDS tenders with missing tender_id"
    fi

    # Check for negative prices
    NEGATIVE_PRICES=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) FROM tenders
        WHERE estimated_value_mkd < 0 OR estimated_value_eur < 0
           OR actual_value_mkd < 0 OR actual_value_eur < 0;
    " 2>/dev/null | xargs)

    if [ "$NEGATIVE_PRICES" = "0" ]; then
        print_success "No tenders with negative prices"
    else
        print_error "Found $NEGATIVE_PRICES tenders with negative prices"
    fi
}

# ============================================================================
# Test 9: Email Configuration
# ============================================================================

test_email_config() {
    print_header "Test 9: Email Configuration"

    print_test "Checking email environment variables..."

    if [ -n "$SMTP_USER" ]; then
        print_success "SMTP_USER is set: $SMTP_USER"
    else
        print_error "SMTP_USER not set"
    fi

    if [ -n "$SMTP_PASSWORD" ]; then
        print_success "SMTP_PASSWORD is set (hidden)"
    else
        print_error "SMTP_PASSWORD not set"
    fi

    if [ -n "$ADMIN_EMAIL" ]; then
        print_success "ADMIN_EMAIL is set: $ADMIN_EMAIL"
    else
        print_error "ADMIN_EMAIL not set"
    fi

    if [ -n "$SMTP_USER" ] && [ -n "$SMTP_PASSWORD" ]; then
        print_info "Email alerts are configured and ready"
    else
        print_info "Email alerts not configured (optional)"
    fi
}

# ============================================================================
# Test 10: File Downloads
# ============================================================================

test_file_downloads() {
    print_header "Test 10: File Downloads"

    print_test "Checking if download directory exists..."

    if [ -d "scraper/downloads/files" ]; then
        print_success "Download directory exists"

        FILE_COUNT=$(find scraper/downloads/files -type f | wc -l | xargs)
        print_success "Downloaded files: $FILE_COUNT"

        if [ "$FILE_COUNT" -gt 0 ]; then
            TOTAL_SIZE=$(du -sh scraper/downloads/files | awk '{print $1}')
            print_success "Total size: $TOTAL_SIZE"
        fi
    else
        print_error "Download directory not found"
        print_info "Create with: mkdir -p scraper/downloads/files"
    fi
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    print_header "Scraper System Test Suite"
    print_info "Starting comprehensive tests..."

    # Run all tests
    test_database || true
    test_health_endpoint || true
    test_authentication || true
    test_job_history || true
    test_trigger_endpoint || true
    test_scraper_direct || true
    test_duplicate_prevention || true
    test_data_validation || true
    test_email_config || true
    test_file_downloads || true

    # Summary
    print_header "Test Results"
    TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
    echo -e "Total Tests: ${BLUE}$TOTAL_TESTS${NC}"
    echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Failed: ${RED}$TESTS_FAILED${NC}"

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "\n${GREEN}All tests passed! System is ready for production.${NC}\n"
        exit 0
    else
        echo -e "\n${RED}Some tests failed. Please review and fix issues.${NC}\n"
        exit 1
    fi
}

# Run main function
main "$@"

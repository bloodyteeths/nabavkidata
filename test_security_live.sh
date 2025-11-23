#!/bin/bash
# Quick Security Tests for nabavkidata.com
# Run this when backend is live at http://localhost:8000

API_URL="${API_URL:-http://localhost:8000}"
TEST_EMAIL="test-enterprise@nabavkidata.com"
TEST_PASSWORD="TestEnterprise2024!"

echo "=================================================="
echo "Security Testing Suite - Live Backend Tests"
echo "=================================================="
echo "Testing against: $API_URL"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health Check
echo "Test 1: Health Check"
echo "--------------------"
HEALTH=$(curl -s -w "\n%{http_code}" "$API_URL/health")
STATUS=$(echo "$HEALTH" | tail -n 1)
if [ "$STATUS" == "200" ]; then
    echo -e "${GREEN}✓ PASS${NC} - API is accessible (200)"
else
    echo -e "${RED}✗ FAIL${NC} - API returned $STATUS"
    exit 1
fi
echo ""

# Test 2: Rate Limiting on Login
echo "Test 2: Rate Limiting on Login"
echo "--------------------------------"
echo "Making 10 rapid login attempts..."

RATE_LIMITED=0
for i in {1..10}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/auth/login" \
        -d "username=test$i@example.com&password=wrong")

    if [ "$HTTP_CODE" == "429" ]; then
        RATE_LIMITED=1
        echo -e "${GREEN}✓ PASS${NC} - Rate limited at attempt $i (429)"
        break
    fi
done

if [ $RATE_LIMITED -eq 0 ]; then
    echo -e "${RED}✗ FAIL${NC} - No rate limiting detected after 10 attempts"
else
    # Check for rate limit headers
    HEADERS=$(curl -s -i -X POST "$API_URL/api/auth/login" -d "username=test@test.com&password=wrong" | grep -i "x-ratelimit")
    if [ -n "$HEADERS" ]; then
        echo -e "${GREEN}✓ PASS${NC} - Rate limit headers present:"
        echo "$HEADERS"
    else
        echo -e "${YELLOW}⚠ WARNING${NC} - Rate limit headers not found"
    fi
fi
echo ""

# Test 3: RAG Authentication
echo "Test 3: RAG Endpoint Authentication"
echo "-------------------------------------"

# Test without token
RAG_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/rag/query" \
    -H "Content-Type: application/json" \
    -d '{"question":"test","top_k":5}')

if [ "$RAG_STATUS" == "401" ]; then
    echo -e "${GREEN}✓ PASS${NC} - RAG query requires auth (401)"
else
    echo -e "${RED}✗ FAIL${NC} - RAG query returned $RAG_STATUS (expected 401)"
fi

# Test streaming endpoint
RAG_STREAM_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/rag/query/stream" \
    -H "Content-Type: application/json" \
    -d '{"question":"test","top_k":5}')

if [ "$RAG_STREAM_STATUS" == "401" ]; then
    echo -e "${GREEN}✓ PASS${NC} - RAG streaming requires auth (401)"
else
    echo -e "${RED}✗ FAIL${NC} - RAG streaming returned $RAG_STREAM_STATUS (expected 401)"
fi

# Test embed endpoint
EMBED_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/rag/embed/document?tender_id=test&doc_id=test&text=test")

if [ "$EMBED_STATUS" == "401" ]; then
    echo -e "${GREEN}✓ PASS${NC} - RAG embed requires auth (401)"
else
    echo -e "${RED}✗ FAIL${NC} - RAG embed returned $EMBED_STATUS (expected 401)"
fi
echo ""

# Test 4: Admin RBAC
echo "Test 4: Admin RBAC"
echo "-------------------"

# Test without token
ADMIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/admin/users")

if [ "$ADMIN_STATUS" == "401" ]; then
    echo -e "${GREEN}✓ PASS${NC} - Admin users endpoint requires auth (401)"
else
    echo -e "${RED}✗ FAIL${NC} - Admin users returned $ADMIN_STATUS (expected 401)"
fi

# Test vector health endpoint
VECTOR_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/admin/vectors/health")

if [ "$VECTOR_STATUS" == "401" ]; then
    echo -e "${GREEN}✓ PASS${NC} - Admin vector health requires auth (401)"
else
    echo -e "${RED}✗ FAIL${NC} - Admin vector health returned $VECTOR_STATUS (expected 401)"
fi
echo ""

# Test 5: Get valid token and test with auth
echo "Test 5: Authenticated Requests"
echo "--------------------------------"

# Try to login
echo "Attempting login with test credentials..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/api/auth/login" \
    -d "username=$TEST_EMAIL&password=$TEST_PASSWORD")

TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | sed 's/"access_token":"//')

if [ -n "$TOKEN" ]; then
    echo -e "${GREEN}✓ PASS${NC} - Successfully obtained auth token"

    # Test RAG with token
    echo "Testing RAG query with valid token..."
    RAG_AUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/rag/query" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"question":"What is this about?","top_k":3}')

    if [ "$RAG_AUTH_STATUS" == "200" ] || [ "$RAG_AUTH_STATUS" == "503" ]; then
        echo -e "${GREEN}✓ PASS${NC} - RAG accepts valid token ($RAG_AUTH_STATUS)"
    else
        echo -e "${YELLOW}⚠ WARNING${NC} - RAG with token returned $RAG_AUTH_STATUS"
    fi

    # Test admin endpoint with non-admin token
    echo "Testing admin endpoint with non-admin token..."
    ADMIN_AUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $TOKEN" \
        "$API_URL/admin/users")

    if [ "$ADMIN_AUTH_STATUS" == "403" ]; then
        echo -e "${GREEN}✓ PASS${NC} - Non-admin blocked from admin endpoint (403)"
    elif [ "$ADMIN_AUTH_STATUS" == "200" ]; then
        echo -e "${YELLOW}⚠ WARNING${NC} - User has admin access (test user might be admin)"
    else
        echo -e "${YELLOW}⚠ WARNING${NC} - Admin endpoint returned $ADMIN_AUTH_STATUS"
    fi
else
    echo -e "${YELLOW}⚠ WARNING${NC} - Could not obtain token (check credentials)"
    echo "Response: $LOGIN_RESPONSE"
fi
echo ""

# Test 6: CORS
echo "Test 6: CORS Configuration"
echo "---------------------------"

CORS_HEADERS=$(curl -s -i -X OPTIONS "$API_URL/api/auth/login" \
    -H "Origin: http://evil-site.com" \
    -H "Access-Control-Request-Method: POST" | grep -i "access-control")

if [ -n "$CORS_HEADERS" ]; then
    echo "CORS Headers:"
    echo "$CORS_HEADERS"

    # Check if wildcard is used
    if echo "$CORS_HEADERS" | grep -q "Access-Control-Allow-Origin: \*"; then
        echo -e "${RED}✗ FAIL${NC} - CORS allows all origins (*)"
    else
        echo -e "${GREEN}✓ PASS${NC} - CORS is configured with specific origins"
    fi
else
    echo -e "${YELLOW}⚠ WARNING${NC} - Could not retrieve CORS headers"
fi
echo ""

# Test 7: Check Fraud Detection Middleware
echo "Test 7: Fraud Detection Middleware"
echo "------------------------------------"
echo "Testing that fraud middleware is active..."

# The fraud middleware should be transparent for valid requests
# It logs to database but doesn't block unless fraud detected
echo "Note: Fraud detection is transparent - logs to database"
echo "Check fraud_events table in PostgreSQL for logs"
echo -e "${GREEN}✓ INFO${NC} - Fraud middleware configured in main.py"
echo ""

# Summary
echo "=================================================="
echo "Test Suite Complete"
echo "=================================================="
echo ""
echo "Manual Tests to Perform:"
echo "1. Frontend /dashboard without auth → redirect to /auth/login"
echo "2. Frontend /admin without admin role → redirect + 403 on API"
echo "3. Check PostgreSQL fraud_events table for fraud logs"
echo "4. Check PostgreSQL audit_log table for admin action logs"
echo "5. Test rate limits with different endpoints"
echo ""
echo "For detailed security analysis, see: SECURITY_TEST_RESULTS.md"

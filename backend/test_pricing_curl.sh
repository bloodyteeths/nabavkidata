#!/bin/bash
# Test pricing endpoint with curl
# This script tests the pricing API endpoint

set -e

echo "================================================================================"
echo "TESTING PRICING API ENDPOINT WITH CURL"
echo "================================================================================"

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
EMAIL="${TEST_EMAIL:-test@nabavkidata.com}"
PASSWORD="${TEST_PASSWORD:-testpassword123}"

echo ""
echo "[1] Getting authentication token..."

# Login to get token
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('access_token', ''))" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
  echo "❌ Failed to get auth token"
  echo "Response: $LOGIN_RESPONSE"
  echo ""
  echo "Note: Make sure the backend server is running:"
  echo "  cd /Users/tamsar/Downloads/nabavkidata/backend"
  echo "  source venv/bin/activate"
  echo "  uvicorn main:app --reload"
  exit 1
fi

echo "✓ Got auth token"

echo ""
echo "[2] Testing pricing health endpoint..."
HEALTH_RESPONSE=$(curl -s "$API_URL/api/ai/pricing-health")
echo "$HEALTH_RESPONSE" | python3 -m json.tool

echo ""
echo "[3] Testing price history endpoint..."

# Get a sample CPV code
echo "  Getting sample CPV code..."
CPV_CODE=$(curl -s "$API_URL/api/ai/price-history/50000000" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('cpv_code', '50000000'))" 2>/dev/null || echo "50000000")

echo "  Testing with CPV code: $CPV_CODE"

# Test monthly grouping
echo ""
echo "  [3a] Monthly grouping (24 months)..."
MONTHLY_RESPONSE=$(curl -s "$API_URL/api/ai/price-history/$CPV_CODE?months=24&group_by=month" \
  -H "Authorization: Bearer $TOKEN")

echo "$MONTHLY_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'  ✓ CPV Code: {data.get(\"cpv_code\")}')
print(f'  ✓ Description: {data.get(\"cpv_description\", \"N/A\")}')
print(f'  ✓ Time Range: {data.get(\"time_range\")}')
print(f'  ✓ Total Tenders: {data.get(\"total_tenders\")}')
print(f'  ✓ Data Points: {len(data.get(\"data_points\", []))}')
print(f'  ✓ Trend: {data.get(\"trend\")} ({data.get(\"trend_pct\", 0):+.2f}%)')

if data.get('data_points'):
    print('  ✓ Sample data (first 3 periods):')
    for point in data['data_points'][:3]:
        print(f'    - {point[\"period\"]}: {point[\"tender_count\"]} tenders')
" 2>/dev/null || echo "❌ Failed to parse response"

# Test quarterly grouping
echo ""
echo "  [3b] Quarterly grouping (36 months)..."
QUARTERLY_RESPONSE=$(curl -s "$API_URL/api/ai/price-history/$CPV_CODE?months=36&group_by=quarter" \
  -H "Authorization: Bearer $TOKEN")

echo "$QUARTERLY_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'  ✓ Data Points: {len(data.get(\"data_points\", []))}')

if data.get('data_points'):
    print('  ✓ Quarterly data:')
    for point in data['data_points']:
        print(f'    - {point[\"period\"]}: {point[\"tender_count\"]} tenders')
" 2>/dev/null || echo "❌ Failed to parse response"

echo ""
echo "[4] Testing with different CPV codes..."

for CPV in "45000000" "09000000" "30000000"; do
  RESPONSE=$(curl -s "$API_URL/api/ai/price-history/$CPV?months=12" \
    -H "Authorization: Bearer $TOKEN")

  echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
cpv = data.get('cpv_code')
total = data.get('total_tenders', 0)
periods = len(data.get('data_points', []))
trend = data.get('trend')
print(f'  ✓ {cpv}: {total} tenders, {periods} periods, trend: {trend}')
" 2>/dev/null || echo "  ⚠ Failed for CPV $CPV"
done

echo ""
echo "[5] Testing edge cases..."

# Invalid CPV code
echo "  [5a] Invalid CPV code..."
INVALID_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$API_URL/api/ai/price-history/INVALID" \
  -H "Authorization: Bearer $TOKEN")

HTTP_CODE=$(echo "$INVALID_RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "400" ]; then
  echo "  ✓ Invalid CPV code rejected correctly (400)"
else
  echo "  ⚠ Expected 400, got $HTTP_CODE"
fi

# Non-existent CPV code
echo "  [5b] Non-existent CPV code..."
NONEXIST_RESPONSE=$(curl -s "$API_URL/api/ai/price-history/99999999" \
  -H "Authorization: Bearer $TOKEN")

echo "$NONEXIST_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('total_tenders') == 0:
    print('  ✓ Non-existent CPV code returns empty data')
else:
    print(f'  ⚠ Expected 0 tenders, got {data.get(\"total_tenders\")}')
" 2>/dev/null || echo "  ⚠ Failed to parse response"

echo ""
echo "================================================================================"
echo "✓ ALL CURL TESTS COMPLETED"
echo "================================================================================"

#!/bin/bash
set -e
BASE_URL=${BASE_URL:-https://api.nabavkidata.com}

fail() { echo "[FAIL] $1"; exit 1; }

echo "Running smoke tests against $BASE_URL"

# 1. Active tenders API
curl -sf "$BASE_URL/api/tenders?page=1&page_size=2" | python3 -c "import sys,json; d=json.load(sys.stdin); print('[OK] tenders total', d.get('total'));"

# 2. Tender detail API (use sample if available)
TENDER_ID=$(curl -sf "$BASE_URL/api/tenders?page=1&page_size=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['items'][0]['tender_id'])")
[ -z "$TENDER_ID" ] && fail "No tender id found"
curl -sf "$BASE_URL/api/tenders/${TENDER_ID}" >/dev/null && echo "[OK] tender detail $TENDER_ID"

# 3. AI summary endpoint
curl -sf "$BASE_URL/api/rag/query" -H 'Content-Type: application/json' \
  -d "{\"question\":\"Кратко резиме?\",\"tender_id\":\"$TENDER_ID\"}" >/dev/null && echo "[OK] AI query"

# 4. Search endpoint
curl -sf "$BASE_URL/api/tenders/search" -H 'Content-Type: application/json' -d '{"query":""}' >/dev/null && echo "[OK] search"

# 5. Health endpoint
curl -sf "$BASE_URL/api/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print('[OK] health status', d.get('status'))"

echo "Smoke tests completed."

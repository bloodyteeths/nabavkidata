#!/bin/bash
# ============================================================================
# Setup Script for Verification Spider
# ============================================================================
# Purpose: Install dependencies and run database migration
# Date: 2025-12-26
# ============================================================================

set -e  # Exit on error

echo "======================================================================"
echo "VERIFICATION SPIDER SETUP"
echo "======================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# Step 1: Check environment
# ============================================================================
echo -e "${YELLOW}[1/5] Checking environment...${NC}"

if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Error: requirements.txt not found. Run from scraper/ directory.${NC}"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Warning: venv not found. Creating virtual environment...${NC}"
    python3 -m venv venv
fi

echo -e "${GREEN}✓ Environment OK${NC}"
echo ""

# ============================================================================
# Step 2: Add Gemini dependency to requirements.txt
# ============================================================================
echo -e "${YELLOW}[2/5] Adding google-generativeai to requirements.txt...${NC}"

if grep -q "google-generativeai" requirements.txt; then
    echo -e "${GREEN}✓ google-generativeai already in requirements.txt${NC}"
else
    echo "google-generativeai>=0.3.0  # For verification spider web search" >> requirements.txt
    echo -e "${GREEN}✓ Added google-generativeai>=0.3.0${NC}"
fi

echo ""

# ============================================================================
# Step 3: Install dependencies
# ============================================================================
echo -e "${YELLOW}[3/5] Installing dependencies...${NC}"

source venv/bin/activate

pip install -q --upgrade pip
pip install -q -r requirements.txt

echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# ============================================================================
# Step 4: Install Playwright browsers (if needed)
# ============================================================================
echo -e "${YELLOW}[4/5] Checking Playwright browsers...${NC}"

if playwright --version > /dev/null 2>&1; then
    # Check if chromium is installed
    if [ ! -d "$HOME/.cache/ms-playwright/chromium-"* ]; then
        echo "Installing Playwright Chromium browser..."
        playwright install chromium
        echo -e "${GREEN}✓ Playwright Chromium installed${NC}"
    else
        echo -e "${GREEN}✓ Playwright browsers already installed${NC}"
    fi
else
    echo -e "${YELLOW}Installing Playwright and browsers...${NC}"
    pip install -q playwright==1.40.0
    playwright install chromium
    echo -e "${GREEN}✓ Playwright installed${NC}"
fi

echo ""

# ============================================================================
# Step 5: Run database migration
# ============================================================================
echo -e "${YELLOW}[5/5] Running database migration...${NC}"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. Using defaults.${NC}"
fi

# Load DB credentials from .env or use defaults
export $(cat .env 2>/dev/null | grep -v '^#' | xargs) || true

DB_HOST=${DB_HOST:-nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-nabavkidata}
DB_USER=${DB_USER:-nabavkidata_admin}

if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}Error: DB_PASSWORD not set in .env${NC}"
    echo "Please set DB_PASSWORD in .env or export it:"
    echo "  export DB_PASSWORD='your-password'"
    exit 1
fi

# Check if migration file exists
MIGRATION_FILE="../db/migrations/020_tender_verifications.sql"
if [ ! -f "$MIGRATION_FILE" ]; then
    echo -e "${RED}Error: Migration file not found: $MIGRATION_FILE${NC}"
    exit 1
fi

# Check if table already exists
TABLE_EXISTS=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -tAc \
    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tender_verifications');" 2>/dev/null || echo "error")

if [ "$TABLE_EXISTS" = "error" ]; then
    echo -e "${RED}Error: Could not connect to database${NC}"
    echo "Check DB credentials in .env"
    exit 1
elif [ "$TABLE_EXISTS" = "t" ]; then
    echo -e "${GREEN}✓ tender_verifications table already exists${NC}"
else
    echo "Running migration 020_tender_verifications.sql..."
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f $MIGRATION_FILE
    echo -e "${GREEN}✓ Migration completed${NC}"
fi

echo ""

# ============================================================================
# Final checks
# ============================================================================
echo -e "${YELLOW}Verifying setup...${NC}"

# Check table exists
TABLE_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -tAc \
    "SELECT COUNT(*) FROM tender_verifications;" 2>/dev/null)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ tender_verifications table: $TABLE_COUNT rows${NC}"
else
    echo -e "${RED}✗ Could not query tender_verifications table${NC}"
fi

# Check corruption_flags extensions
WEB_VERIFIED_EXISTS=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -tAc \
    "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'corruption_flags' AND column_name = 'web_verified');" 2>/dev/null)

if [ "$WEB_VERIFIED_EXISTS" = "t" ]; then
    echo -e "${GREEN}✓ corruption_flags.web_verified column exists${NC}"
else
    echo -e "${YELLOW}Warning: corruption_flags.web_verified column not found${NC}"
fi

# Check Gemini API key
if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${YELLOW}⚠ GEMINI_API_KEY not set - web search will be disabled${NC}"
    echo "  Set in .env: GEMINI_API_KEY=your-key-here"
else
    echo -e "${GREEN}✓ GEMINI_API_KEY is set${NC}"
fi

echo ""
echo "======================================================================"
echo -e "${GREEN}SETUP COMPLETE!${NC}"
echo "======================================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Test spider (without web search):"
echo "   scrapy crawl verify -a from_db=true -a min_score=0.9 -a limit=5 -a web_search=false"
echo ""
echo "2. Full run (with web search):"
echo "   scrapy crawl verify -a from_db=true -a min_score=0.8 -a limit=20 -a web_search=true"
echo ""
echo "3. Check results:"
echo "   psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c 'SELECT * FROM get_verification_stats();'"
echo ""
echo "4. View high-risk verified tenders:"
echo "   psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c 'SELECT * FROM high_risk_verified_tenders LIMIT 10;'"
echo ""
echo "======================================================================"

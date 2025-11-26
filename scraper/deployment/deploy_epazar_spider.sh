#!/bin/bash
# ============================================================================
# E-Pazar Spider Deployment Script for EC2
# ============================================================================
# Usage:
#   ./deploy_epazar_spider.sh                    # Deploy and setup
#   ./deploy_epazar_spider.sh --run              # Deploy and run spider
#   ./deploy_epazar_spider.sh --discover         # Run discovery mode
#   ./deploy_epazar_spider.sh --cron             # Setup cron job
# ============================================================================

set -e

# Configuration
EC2_HOST="${EC2_HOST:-ubuntu@18.197.185.30}"
SSH_KEY="${SSH_KEY:-~/.ssh/nabavki-key.pem}"
REMOTE_DIR="/home/ubuntu/nabavkidata"
LOCAL_DIR="$(dirname "$0")/../.."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    log_error "SSH key not found: $SSH_KEY"
    exit 1
fi

# Parse arguments
RUN_SPIDER=false
DISCOVER_MODE=false
SETUP_CRON=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --run)
            RUN_SPIDER=true
            shift
            ;;
        --discover)
            DISCOVER_MODE=true
            shift
            ;;
        --cron)
            SETUP_CRON=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ============================================================================
# 1. DEPLOY SPIDER FILES
# ============================================================================
log_info "Deploying e-Pazar spider files to EC2..."

# Copy spider file
scp -i "$SSH_KEY" \
    "$LOCAL_DIR/scraper/scraper/spiders/epazar_spider.py" \
    "$EC2_HOST:$REMOTE_DIR/scraper/scraper/spiders/"

# Copy updated pipelines
scp -i "$SSH_KEY" \
    "$LOCAL_DIR/scraper/scraper/pipelines.py" \
    "$EC2_HOST:$REMOTE_DIR/scraper/scraper/"

log_info "Spider files deployed successfully"

# ============================================================================
# 2. DEPLOY DATABASE MIGRATION
# ============================================================================
log_info "Deploying database migration..."

scp -i "$SSH_KEY" \
    "$LOCAL_DIR/db/migrations/006_epazar_tables.sql" \
    "$EC2_HOST:$REMOTE_DIR/db/migrations/"

log_info "Running database migration on EC2..."

ssh -i "$SSH_KEY" "$EC2_HOST" << 'EOF'
cd /home/ubuntu/nabavkidata
source venv/bin/activate

# Load environment variables
source .env 2>/dev/null || true

# Run migration
echo "Running e-Pazar migration..."
psql "$DATABASE_URL" -f db/migrations/006_epazar_tables.sql 2>&1 || {
    echo "Migration might have already run or there was an error. Continuing..."
}

echo "Migration complete"
EOF

log_info "Database migration completed"

# ============================================================================
# 3. INSTALL PLAYWRIGHT ON EC2 (if not already installed)
# ============================================================================
log_info "Checking Playwright installation on EC2..."

ssh -i "$SSH_KEY" "$EC2_HOST" << 'EOF'
cd /home/ubuntu/nabavkidata
source venv/bin/activate

# Check if Playwright is installed
python3 -c "import playwright" 2>/dev/null || {
    echo "Installing Playwright..."
    pip install playwright scrapy-playwright
    playwright install chromium
    playwright install-deps
    echo "Playwright installed"
}

# Verify installation
python3 -c "from playwright.async_api import async_playwright; print('Playwright OK')"
EOF

log_info "Playwright setup verified"

# ============================================================================
# 4. RUN DISCOVERY MODE (optional)
# ============================================================================
if [ "$DISCOVER_MODE" = true ]; then
    log_info "Running e-Pazar spider in discovery mode..."

    ssh -i "$SSH_KEY" "$EC2_HOST" << 'EOF'
cd /home/ubuntu/nabavkidata/scraper
source ../venv/bin/activate
source ../.env 2>/dev/null || true

echo "Starting discovery mode..."
scrapy crawl epazar -a mode=discover -L INFO 2>&1 | tee /var/log/nabavkidata/epazar_discovery.log

echo "Discovery complete. Results saved to epazar_discovery.json"
EOF

    log_info "Discovery mode completed"
fi

# ============================================================================
# 5. RUN SPIDER (optional)
# ============================================================================
if [ "$RUN_SPIDER" = true ]; then
    log_info "Running e-Pazar spider..."

    ssh -i "$SSH_KEY" "$EC2_HOST" << 'EOF'
cd /home/ubuntu/nabavkidata/scraper
source ../venv/bin/activate
source ../.env 2>/dev/null || true

echo "Starting e-Pazar spider (active tenders)..."
scrapy crawl epazar -a category=active -L INFO 2>&1 | tee /var/log/nabavkidata/epazar_scrape.log

echo "Starting e-Pazar spider (awarded tenders)..."
scrapy crawl epazar -a category=awarded -L INFO 2>&1 | tee -a /var/log/nabavkidata/epazar_scrape.log

echo "Spider run completed"
EOF

    log_info "Spider run completed"
fi

# ============================================================================
# 6. SETUP CRON JOB (optional)
# ============================================================================
if [ "$SETUP_CRON" = true ]; then
    log_info "Setting up cron job for e-Pazar spider..."

    ssh -i "$SSH_KEY" "$EC2_HOST" << 'EOF'
# Create e-Pazar scraper script
cat > /home/ubuntu/nabavkidata/scraper/cron/run_epazar_spider.sh << 'SCRIPT'
#!/bin/bash
# E-Pazar Spider Cron Script
cd /home/ubuntu/nabavkidata/scraper
source ../venv/bin/activate
source ../.env 2>/dev/null || true

LOG_FILE="/var/log/nabavkidata/epazar_cron_$(date +%Y%m%d_%H%M%S).log"

echo "Starting e-Pazar spider at $(date)" >> "$LOG_FILE"

# Run for active tenders
scrapy crawl epazar -a category=active -a mode=incremental -L INFO >> "$LOG_FILE" 2>&1

# Run for awarded tenders (less frequently)
if [ "$(date +%H)" -eq "02" ]; then
    scrapy crawl epazar -a category=awarded -a mode=incremental -L INFO >> "$LOG_FILE" 2>&1
fi

echo "Completed at $(date)" >> "$LOG_FILE"
SCRIPT

chmod +x /home/ubuntu/nabavkidata/scraper/cron/run_epazar_spider.sh

# Add cron job (runs every 6 hours)
(crontab -l 2>/dev/null | grep -v "run_epazar_spider"; echo "0 */6 * * * /home/ubuntu/nabavkidata/scraper/cron/run_epazar_spider.sh") | crontab -

echo "Cron job installed. Current crontab:"
crontab -l
EOF

    log_info "Cron job setup completed"
fi

# ============================================================================
# 7. DEPLOY BACKEND API CHANGES
# ============================================================================
log_info "Deploying backend API changes..."

# Copy API endpoint
scp -i "$SSH_KEY" \
    "$LOCAL_DIR/backend/api/epazar.py" \
    "$EC2_HOST:$REMOTE_DIR/backend/api/"

# Copy updated main.py
scp -i "$SSH_KEY" \
    "$LOCAL_DIR/backend/main.py" \
    "$EC2_HOST:$REMOTE_DIR/backend/"

# Copy updated schemas
scp -i "$SSH_KEY" \
    "$LOCAL_DIR/backend/schemas.py" \
    "$EC2_HOST:$REMOTE_DIR/backend/"

# Copy AI summarization updates
scp -i "$SSH_KEY" \
    "$LOCAL_DIR/ai/rag_query.py" \
    "$EC2_HOST:$REMOTE_DIR/ai/"

log_info "Backend API files deployed"

# Restart backend service
log_info "Restarting backend service..."

ssh -i "$SSH_KEY" "$EC2_HOST" << 'EOF'
cd /home/ubuntu/nabavkidata

# Restart backend with docker-compose
if [ -f "docker-compose.prod.yml" ]; then
    docker-compose -f docker-compose.prod.yml restart backend 2>/dev/null || {
        echo "Docker not in use, trying systemctl..."
        sudo systemctl restart nabavkidata-backend 2>/dev/null || {
            echo "No service found, trying direct restart..."
            pkill -f "uvicorn backend.main" || true
            cd backend
            source ../venv/bin/activate
            nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /var/log/nabavkidata/backend.log 2>&1 &
        }
    }
fi

echo "Backend service restarted"
EOF

log_info "Backend service restarted"

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
echo "============================================================================"
echo -e "${GREEN}E-Pazar Spider Deployment Complete!${NC}"
echo "============================================================================"
echo ""
echo "Files deployed:"
echo "  - scraper/scraper/spiders/epazar_spider.py"
echo "  - scraper/scraper/pipelines.py"
echo "  - db/migrations/006_epazar_tables.sql"
echo "  - backend/api/epazar.py"
echo "  - backend/main.py"
echo "  - backend/schemas.py"
echo "  - ai/rag_query.py"
echo ""
echo "Available commands on EC2:"
echo "  cd /home/ubuntu/nabavkidata/scraper"
echo "  source ../venv/bin/activate"
echo ""
echo "  # Discovery mode (explore site structure)"
echo "  scrapy crawl epazar -a mode=discover"
echo ""
echo "  # Scrape active tenders"
echo "  scrapy crawl epazar -a category=active"
echo ""
echo "  # Scrape awarded tenders"
echo "  scrapy crawl epazar -a category=awarded"
echo ""
echo "  # Scrape all categories"
echo "  scrapy crawl epazar -a category=all"
echo ""
echo "  # Incremental mode (only new/changed)"
echo "  scrapy crawl epazar -a mode=incremental"
echo ""
echo "API Endpoints available:"
echo "  GET  /api/epazar/tenders           - List tenders"
echo "  GET  /api/epazar/tenders/{id}      - Get tender details"
echo "  GET  /api/epazar/tenders/{id}/items - Get BOQ items"
echo "  GET  /api/epazar/tenders/{id}/offers - Get offers"
echo "  GET  /api/epazar/suppliers         - List suppliers"
echo "  GET  /api/epazar/stats/overview    - Statistics"
echo "  POST /api/epazar/tenders/{id}/summarize - AI summary"
echo ""
echo "============================================================================"

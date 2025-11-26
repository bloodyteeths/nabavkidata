#!/bin/bash
#
# PHASE 4 DEPLOYMENT SCRIPT
# Multi-Category Scraping & Route Discovery
#
# Usage:
#   ./deploy_phase4.sh              # Deploy and run discovery
#   ./deploy_phase4.sh deploy       # Deploy only
#   ./deploy_phase4.sh discover     # Run discovery mode
#   ./deploy_phase4.sh scrape       # Run default scrape
#

set -e

# Configuration
# Using Elastic IP (permanent): 18.197.185.30
EC2_HOST="ubuntu@18.197.185.30"
SSH_KEY="~/.ssh/nabavki-key.pem"
REMOTE_PATH="/home/ubuntu/nabavkidata"
DATABASE_URL="postgresql+asyncpg://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com:5432/nabavkidata"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  PHASE 4: Multi-Category Scraping Deployment   ${NC}"
echo -e "${GREEN}================================================${NC}"

MODE="${1:-all}"

deploy_files() {
    echo -e "${YELLOW}Deploying Phase 4 files to EC2...${NC}"

    # Upload updated spider
    echo "Uploading nabavki_spider.py..."
    scp -i $SSH_KEY scraper/scraper/spiders/nabavki_spider.py $EC2_HOST:$REMOTE_PATH/scraper/scraper/spiders/

    # Upload updated items
    echo "Uploading items.py..."
    scp -i $SSH_KEY scraper/scraper/items.py $EC2_HOST:$REMOTE_PATH/scraper/scraper/

    # Upload exploration script
    echo "Uploading explore_site_structure.py..."
    scp -i $SSH_KEY scraper/explore_site_structure.py $EC2_HOST:$REMOTE_PATH/scraper/

    echo -e "${GREEN}✓ Files deployed successfully${NC}"
}

run_discovery() {
    echo -e "${YELLOW}Running category discovery mode...${NC}"
    echo "This will probe all candidate URLs to find working categories"
    echo ""

    ssh -i $SSH_KEY $EC2_HOST << EOF
        cd $REMOTE_PATH/scraper
        source ../venv/bin/activate
        export DATABASE_URL='$DATABASE_URL'

        echo "Starting discovery mode..."
        scrapy crawl nabavki -a mode=discover -s LOG_LEVEL=WARNING 2>&1

        echo ""
        echo "Discovery results:"
        if [ -f /tmp/e_nabavki_discovered_urls.json ]; then
            cat /tmp/e_nabavki_discovered_urls.json
        else
            echo "No discovery results file found"
        fi
EOF
}

run_scrape() {
    CATEGORY="${1:-active}"
    echo -e "${YELLOW}Running scraper for category: ${CATEGORY}${NC}"

    ssh -i $SSH_KEY $EC2_HOST << EOF
        cd $REMOTE_PATH/scraper
        source ../venv/bin/activate
        export DATABASE_URL='$DATABASE_URL'

        echo "Starting scraper for category: $CATEGORY"
        scrapy crawl nabavki -a category=$CATEGORY -s CLOSESPIDER_ITEMCOUNT=5 -s LOG_LEVEL=INFO 2>&1
EOF
}

verify_deployment() {
    echo -e "${YELLOW}Verifying deployment...${NC}"

    ssh -i $SSH_KEY $EC2_HOST << EOF
        cd $REMOTE_PATH/scraper

        # Check spider supports new parameters
        echo "Checking spider configuration..."
        grep -q "category='active'" scraper/spiders/nabavki_spider.py && echo "✓ Category parameter supported"
        grep -q "mode='scrape'" scraper/spiders/nabavki_spider.py && echo "✓ Mode parameter supported"
        grep -q "DISCOVERY_CANDIDATES" scraper/spiders/nabavki_spider.py && echo "✓ Discovery candidates defined"
        grep -q "source_category" scraper/items.py && echo "✓ source_category field added to items"

        echo ""
        echo "Spider usage:"
        head -15 scraper/spiders/nabavki_spider.py | grep -A 10 "Usage:"
EOF
}

# Main execution
case "$MODE" in
    "deploy")
        deploy_files
        verify_deployment
        ;;
    "discover")
        run_discovery
        ;;
    "scrape")
        run_scrape "${2:-active}"
        ;;
    "verify")
        verify_deployment
        ;;
    "all")
        deploy_files
        verify_deployment
        echo ""
        run_discovery
        ;;
    *)
        echo "Usage: $0 [deploy|discover|scrape|verify|all]"
        echo ""
        echo "Commands:"
        echo "  deploy   - Deploy updated files to EC2"
        echo "  discover - Run discovery mode to find category URLs"
        echo "  scrape   - Run scraper (optional: scrape <category>)"
        echo "  verify   - Verify deployment"
        echo "  all      - Deploy, verify, and run discovery (default)"
        ;;
esac

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Phase 4 Deployment Complete                   ${NC}"
echo -e "${GREEN}================================================${NC}"

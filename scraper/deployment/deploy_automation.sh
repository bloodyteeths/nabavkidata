#!/bin/bash
# Deploy automation layer to EC2
# This script sets up all scraper automation infrastructure

set -e

echo "=========================================="
echo "NABAVKIDATA SCRAPER AUTOMATION DEPLOYMENT"
echo "=========================================="
echo ""

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on EC2
if [ ! -f "/home/ubuntu/.ssh/authorized_keys" ]; then
    print_warning "Not running on EC2 Ubuntu instance. Some paths may differ."
fi

# Step 1: Create directory structure
echo "Step 1: Creating directory structure..."
mkdir -p /home/ubuntu/nabavkidata/scraper/jobs
mkdir -p /home/ubuntu/nabavkidata/scraper/logs
mkdir -p /home/ubuntu/backups
print_success "Directories created"

# Step 2: Set permissions on job scripts
echo ""
echo "Step 2: Setting permissions on job scripts..."
chmod +x /home/ubuntu/nabavkidata/scraper/jobs/*.sh
print_success "Job scripts are executable"

# Step 3: Backup existing crontab
echo ""
echo "Step 3: Backing up existing crontab..."
BACKUP_FILE="/tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt"
crontab -l > "$BACKUP_FILE" 2>/dev/null || echo "# New crontab" > "$BACKUP_FILE"
print_success "Crontab backed up to $BACKUP_FILE"

# Step 4: Check if automation jobs already exist
echo ""
echo "Step 4: Checking for existing automation jobs..."
if crontab -l 2>/dev/null | grep -q "NABAVKIDATA SCRAPER AUTOMATION"; then
    print_warning "Automation jobs already exist in crontab"
    read -p "Do you want to replace them? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Skipping crontab installation"
        SKIP_CRON=1
    else
        # Remove old automation section
        crontab -l | grep -v "NABAVKIDATA SCRAPER AUTOMATION" | \
        grep -v "scrape_active.sh" | \
        grep -v "scrape_awards.sh" | \
        grep -v "scrape_backfill.sh" | \
        grep -v "process_documents.sh" | \
        grep -v "refresh_vectors.sh" | \
        grep -v "health_check.sh" | \
        grep -v "rotate_logs.sh" | \
        grep -v "backup_db.sh" | crontab -
        print_success "Removed old automation jobs"
    fi
fi

# Step 5: Install new cron jobs
if [ -z "$SKIP_CRON" ]; then
    echo ""
    echo "Step 5: Installing cron jobs..."
    CRON_FILE="/home/ubuntu/nabavkidata/scraper/deployment/crontab_additions.txt"

    if [ -f "$CRON_FILE" ]; then
        (crontab -l 2>/dev/null; echo ""; cat "$CRON_FILE") | crontab -
        print_success "Cron jobs installed successfully"
    else
        print_error "Crontab additions file not found: $CRON_FILE"
        exit 1
    fi
fi

# Step 6: Verify environment
echo ""
echo "Step 6: Verifying environment..."

# Check if virtualenv exists
if [ -d "/home/ubuntu/nabavkidata/venv" ]; then
    print_success "Virtual environment found"
else
    print_error "Virtual environment not found at /home/ubuntu/nabavkidata/venv"
    exit 1
fi

# Check if DATABASE_URL is set
source /home/ubuntu/nabavkidata/venv/bin/activate
if [ -z "$DATABASE_URL" ]; then
    print_error "DATABASE_URL environment variable not set"
    print_warning "Please set DATABASE_URL in your environment or .env file"
    exit 1
else
    print_success "DATABASE_URL is set"
fi

# Step 7: Test database connection
echo ""
echo "Step 7: Testing database connection..."
python3 << 'EOF'
import asyncio
import asyncpg
import os
import sys

async def test_connection():
    try:
        db_url = os.getenv('DATABASE_URL')
        conn = await asyncpg.connect(db_url, timeout=10)
        count = await conn.fetchval('SELECT COUNT(*) FROM tenders')
        await conn.close()
        print(f"Database connected successfully: {count} tenders found")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

success = asyncio.run(test_connection())
sys.exit(0 if success else 1)
EOF

if [ $? -eq 0 ]; then
    print_success "Database connection successful"
else
    print_error "Database connection failed"
    exit 1
fi

# Step 8: Test job scripts
echo ""
echo "Step 8: Testing job scripts (dry run)..."

# Test health check
if /home/ubuntu/nabavkidata/scraper/jobs/health_check.sh; then
    print_success "Health check script works"
else
    print_warning "Health check script reported issues"
fi

# Step 9: Display installed cron jobs
echo ""
echo "Step 9: Installed cron jobs:"
echo "=========================================="
crontab -l | grep -A 20 "NABAVKIDATA SCRAPER AUTOMATION" || echo "No automation jobs found"
echo "=========================================="

# Step 10: Display monitoring commands
echo ""
echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Useful commands:"
echo "----------------"
echo "View all cron jobs:"
echo "  crontab -l"
echo ""
echo "View active scrape logs:"
echo "  tail -f /home/ubuntu/nabavkidata/scraper/logs/cron_active.log"
echo ""
echo "View all recent logs:"
echo "  ls -lht /home/ubuntu/nabavkidata/scraper/logs/ | head -20"
echo ""
echo "Monitor database growth:"
echo "  watch -n 5 'psql \$DATABASE_URL -c \"SELECT COUNT(*) FROM tenders\"'"
echo ""
echo "Run monitoring dashboard:"
echo "  python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py"
echo ""
echo "Check cron execution in system logs:"
echo "  grep CRON /var/log/syslog | tail -20"
echo ""
echo "Manually test a job:"
echo "  /home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh"
echo ""
echo "=========================================="
echo ""
print_success "Automation layer deployed successfully!"
echo ""

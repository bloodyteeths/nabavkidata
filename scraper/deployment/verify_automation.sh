#!/bin/bash
# Comprehensive verification script for automation infrastructure
# Run this after deployment to verify everything is working

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

# Functions
print_header() {
    echo -e "\n${BOLD}${BLUE}================================${NC}"
    echo -e "${BOLD}${BLUE}$1${NC}"
    echo -e "${BOLD}${BLUE}================================${NC}\n"
}

print_check() {
    echo -e "${BLUE}[CHECK]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓ PASS]${NC} $1"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
}

print_fail() {
    echo -e "${RED}[✗ FAIL]${NC} $1"
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
}

print_warning() {
    echo -e "${YELLOW}[⚠ WARN]${NC} $1"
    CHECKS_WARNING=$((CHECKS_WARNING + 1))
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Start verification
echo -e "${BOLD}${GREEN}AUTOMATION INFRASTRUCTURE VERIFICATION${NC}"
echo "Starting comprehensive verification..."
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"

# ============================================================================
print_header "1. DIRECTORY STRUCTURE"
# ============================================================================

print_check "Checking job scripts directory..."
if [ -d "/home/ubuntu/nabavkidata/scraper/jobs" ]; then
    JOB_COUNT=$(ls -1 /home/ubuntu/nabavkidata/scraper/jobs/*.sh 2>/dev/null | wc -l)
    if [ "$JOB_COUNT" -eq 8 ]; then
        print_success "Jobs directory exists with all 8 scripts"
    else
        print_fail "Jobs directory exists but found $JOB_COUNT scripts (expected 8)"
    fi
else
    print_fail "Jobs directory not found"
fi

print_check "Checking logs directory..."
if [ -d "/home/ubuntu/nabavkidata/scraper/logs" ]; then
    print_success "Logs directory exists"
else
    print_fail "Logs directory not found"
fi

print_check "Checking backups directory..."
if [ -d "/home/ubuntu/backups" ]; then
    print_success "Backups directory exists"
else
    print_warning "Backups directory not found (will be created on first backup)"
fi

print_check "Checking deployment directory..."
if [ -d "/home/ubuntu/nabavkidata/scraper/deployment" ]; then
    print_success "Deployment directory exists"
else
    print_fail "Deployment directory not found"
fi

# ============================================================================
print_header "2. JOB SCRIPT PERMISSIONS"
# ============================================================================

JOBS_DIR="/home/ubuntu/nabavkidata/scraper/jobs"
JOB_SCRIPTS=(
    "scrape_active.sh"
    "scrape_awards.sh"
    "scrape_backfill.sh"
    "process_documents.sh"
    "refresh_vectors.sh"
    "health_check.sh"
    "rotate_logs.sh"
    "backup_db.sh"
)

for script in "${JOB_SCRIPTS[@]}"; do
    print_check "Checking $script..."
    if [ -f "$JOBS_DIR/$script" ]; then
        if [ -x "$JOBS_DIR/$script" ]; then
            print_success "$script is executable"
        else
            print_fail "$script is not executable"
        fi
    else
        print_fail "$script not found"
    fi
done

# ============================================================================
print_header "3. CRON JOB INSTALLATION"
# ============================================================================

print_check "Checking if cron service is running..."
if systemctl is-active --quiet cron 2>/dev/null || service cron status >/dev/null 2>&1; then
    print_success "Cron service is running"
else
    print_fail "Cron service is not running"
fi

print_check "Checking for automation cron jobs..."
if crontab -l 2>/dev/null | grep -q "NABAVKIDATA SCRAPER AUTOMATION"; then
    CRON_COUNT=$(crontab -l 2>/dev/null | grep "nabavkidata/scraper/jobs" | grep -v "^#" | wc -l)
    if [ "$CRON_COUNT" -eq 8 ]; then
        print_success "All 8 cron jobs are installed"
    else
        print_fail "Found $CRON_COUNT cron jobs (expected 8)"
    fi
else
    print_fail "Automation section not found in crontab"
fi

# ============================================================================
print_header "4. ENVIRONMENT VERIFICATION"
# ============================================================================

print_check "Checking virtual environment..."
if [ -d "/home/ubuntu/nabavkidata/venv" ]; then
    print_success "Virtual environment exists"
else
    print_fail "Virtual environment not found at /home/ubuntu/nabavkidata/venv"
fi

print_check "Checking DATABASE_URL..."
source /home/ubuntu/nabavkidata/venv/bin/activate 2>/dev/null || true
if [ -n "$DATABASE_URL" ]; then
    print_success "DATABASE_URL is set"
    print_info "Database: $(echo $DATABASE_URL | sed 's/:.*//' | sed 's/.*@//')"
else
    print_fail "DATABASE_URL is not set"
fi

print_check "Checking Python packages..."
if command -v python3 &> /dev/null; then
    SCRAPY_VERSION=$(python3 -c "import scrapy; print(scrapy.__version__)" 2>/dev/null || echo "not installed")
    ASYNCPG_VERSION=$(python3 -c "import asyncpg; print(asyncpg.__version__)" 2>/dev/null || echo "not installed")

    if [ "$SCRAPY_VERSION" != "not installed" ]; then
        print_success "Scrapy $SCRAPY_VERSION is installed"
    else
        print_fail "Scrapy is not installed"
    fi

    if [ "$ASYNCPG_VERSION" != "not installed" ]; then
        print_success "asyncpg $ASYNCPG_VERSION is installed"
    else
        print_fail "asyncpg is not installed"
    fi
else
    print_fail "python3 command not found"
fi

# ============================================================================
print_header "5. DATABASE CONNECTIVITY"
# ============================================================================

print_check "Testing database connection..."
DB_TEST=$(python3 << 'EOF' 2>&1
import asyncio
import asyncpg
import os
import sys

async def test():
    try:
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            print("ERROR: DATABASE_URL not set")
            return False

        conn = await asyncpg.connect(db_url, timeout=10)

        # Test query
        count = await conn.fetchval('SELECT COUNT(*) FROM tenders')

        # Test tables exist
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('tenders', 'documents', 'users')
        """)

        await conn.close()

        print(f"OK:{count}:{len(tables)}")
        return True

    except Exception as e:
        print(f"ERROR:{e}")
        return False

success = asyncio.run(test())
sys.exit(0 if success else 1)
EOF
)

if echo "$DB_TEST" | grep -q "^OK:"; then
    TENDER_COUNT=$(echo "$DB_TEST" | cut -d: -f2)
    TABLE_COUNT=$(echo "$DB_TEST" | cut -d: -f3)
    print_success "Database connected: $TENDER_COUNT tenders, $TABLE_COUNT tables"
else
    print_fail "Database connection failed: $DB_TEST"
fi

# ============================================================================
print_header "6. JOB SCRIPT SYNTAX VALIDATION"
# ============================================================================

for script in "${JOB_SCRIPTS[@]}"; do
    print_check "Validating syntax of $script..."
    if bash -n "$JOBS_DIR/$script" 2>/dev/null; then
        print_success "$script syntax is valid"
    else
        print_fail "$script has syntax errors"
    fi
done

# ============================================================================
print_header "7. LOG FILE STATUS"
# ============================================================================

print_check "Checking for existing log files..."
LOG_COUNT=$(find /home/ubuntu/nabavkidata/scraper/logs -name "*.log" -type f 2>/dev/null | wc -l)
if [ "$LOG_COUNT" -gt 0 ]; then
    print_success "Found $LOG_COUNT log files"

    # Check most recent log
    RECENT_LOG=$(find /home/ubuntu/nabavkidata/scraper/logs -name "*.log" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    if [ -n "$RECENT_LOG" ]; then
        LOG_AGE=$(( $(date +%s) - $(stat -c %Y "$RECENT_LOG" 2>/dev/null || echo 0) ))
        print_info "Most recent log: $(basename "$RECENT_LOG") (${LOG_AGE}s ago)"
    fi
else
    print_warning "No log files found yet (normal for new installation)"
fi

print_check "Checking log directory size..."
LOG_SIZE=$(du -sh /home/ubuntu/nabavkidata/scraper/logs 2>/dev/null | cut -f1)
print_info "Log directory size: $LOG_SIZE"

# ============================================================================
print_header "8. DISK SPACE"
# ============================================================================

print_check "Checking disk space..."
DISK_USAGE=$(df -h /home/ubuntu 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//')
DISK_AVAIL=$(df -h /home/ubuntu 2>/dev/null | tail -1 | awk '{print $4}')

if [ "$DISK_USAGE" -lt 80 ]; then
    print_success "Disk usage: ${DISK_USAGE}% (${DISK_AVAIL} available)"
elif [ "$DISK_USAGE" -lt 90 ]; then
    print_warning "Disk usage: ${DISK_USAGE}% (${DISK_AVAIL} available)"
else
    print_fail "Disk usage: ${DISK_USAGE}% - critically low (${DISK_AVAIL} available)"
fi

# ============================================================================
print_header "9. PROCESS CHECK"
# ============================================================================

print_check "Checking for running scraper processes..."
SCRAPER_PROCS=$(pgrep -f "scrapy\|nabavki_spider" 2>/dev/null | wc -l)
if [ "$SCRAPER_PROCS" -eq 0 ]; then
    print_success "No scraper processes running (good for idle state)"
elif [ "$SCRAPER_PROCS" -lt 5 ]; then
    print_info "$SCRAPER_PROCS scraper process(es) running"
else
    print_warning "$SCRAPER_PROCS scraper processes running (may indicate stuck jobs)"
fi

# ============================================================================
print_header "10. HEALTH CHECK TEST"
# ============================================================================

print_check "Running health check script..."
if /home/ubuntu/nabavkidata/scraper/jobs/health_check.sh >/dev/null 2>&1; then
    print_success "Health check script executed successfully"

    # Check if health log was created/updated
    if [ -f "/home/ubuntu/nabavkidata/scraper/logs/health_check.log" ]; then
        HEALTH_LOG_LINES=$(wc -l < /home/ubuntu/nabavkidata/scraper/logs/health_check.log)
        print_info "Health check log has $HEALTH_LOG_LINES lines"
    fi
else
    print_fail "Health check script failed"
fi

# ============================================================================
print_header "11. BACKUP SYSTEM"
# ============================================================================

print_check "Checking for existing backups..."
if [ -d "/home/ubuntu/backups" ]; then
    BACKUP_COUNT=$(find /home/ubuntu/backups -name "nabavkidata_*.sql.gz" 2>/dev/null | wc -l)
    if [ "$BACKUP_COUNT" -gt 0 ]; then
        print_success "Found $BACKUP_COUNT backup(s)"

        # Check most recent backup
        RECENT_BACKUP=$(ls -t /home/ubuntu/backups/nabavkidata_*.sql.gz 2>/dev/null | head -1)
        if [ -n "$RECENT_BACKUP" ]; then
            BACKUP_SIZE=$(du -h "$RECENT_BACKUP" | cut -f1)
            BACKUP_AGE=$(( $(date +%s) - $(stat -c %Y "$RECENT_BACKUP" 2>/dev/null || echo 0) ))
            BACKUP_AGE_HOURS=$(( BACKUP_AGE / 3600 ))
            print_info "Most recent backup: $(basename "$RECENT_BACKUP") ($BACKUP_SIZE, ${BACKUP_AGE_HOURS}h ago)"
        fi
    else
        print_warning "No backups found yet (normal for new installation)"
    fi
else
    print_warning "Backups directory not created yet"
fi

# ============================================================================
print_header "12. MONITORING DASHBOARD"
# ============================================================================

print_check "Checking monitoring dashboard..."
if [ -f "/home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py" ]; then
    if [ -x "/home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py" ]; then
        print_success "Monitoring dashboard is installed and executable"
    else
        print_warning "Monitoring dashboard exists but is not executable"
    fi
else
    print_fail "Monitoring dashboard not found"
fi

# ============================================================================
print_header "VERIFICATION SUMMARY"
# ============================================================================

TOTAL_CHECKS=$((CHECKS_PASSED + CHECKS_FAILED + CHECKS_WARNING))

echo ""
echo -e "${BOLD}Results:${NC}"
echo -e "  ${GREEN}Passed:${NC}   $CHECKS_PASSED"
echo -e "  ${RED}Failed:${NC}   $CHECKS_FAILED"
echo -e "  ${YELLOW}Warnings:${NC} $CHECKS_WARNING"
echo -e "  ${BLUE}Total:${NC}    $TOTAL_CHECKS"
echo ""

# Overall status
if [ "$CHECKS_FAILED" -eq 0 ]; then
    if [ "$CHECKS_WARNING" -eq 0 ]; then
        echo -e "${BOLD}${GREEN}✓ ALL CHECKS PASSED!${NC}"
        echo "Automation infrastructure is fully operational."
        EXIT_CODE=0
    else
        echo -e "${BOLD}${YELLOW}⚠ PASSED WITH WARNINGS${NC}"
        echo "Automation infrastructure is operational but has minor issues."
        EXIT_CODE=0
    fi
else
    echo -e "${BOLD}${RED}✗ VERIFICATION FAILED${NC}"
    echo "Please fix the failed checks before proceeding."
    EXIT_CODE=1
fi

echo ""
echo "Next steps:"
if [ "$CHECKS_FAILED" -eq 0 ]; then
    echo "  1. Monitor logs: tail -f /home/ubuntu/nabavkidata/scraper/logs/*.log"
    echo "  2. View dashboard: python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py"
    echo "  3. Check cron execution: grep CRON /var/log/syslog | tail -20"
    echo "  4. Wait for next scheduled run and verify success"
else
    echo "  1. Review failed checks above"
    echo "  2. Fix issues as needed"
    echo "  3. Re-run verification: ./verify_automation.sh"
    echo "  4. Check deployment guide: EC2_DEPLOYMENT_GUIDE.md"
fi

echo ""
exit $EXIT_CODE

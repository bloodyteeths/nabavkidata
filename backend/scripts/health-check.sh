#!/usr/bin/env bash

###############################################################################
# health-check.sh - System Health Check Script
#
# Checks the health of all services:
# - Backend API health endpoint
# - Frontend application
# - PostgreSQL database connection
# - Redis connection
# - Returns appropriate exit codes for monitoring
#
# Usage: ./scripts/health-check.sh [--verbose]
#
# Exit Codes:
#   0 - All services healthy
#   1 - One or more services unhealthy
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERBOSE=false
HEALTH_STATUS=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${GREEN}[INFO]${NC} $1"
    fi
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    HEALTH_STATUS=1
}

# Load environment variables
load_env() {
    if [ -f "$PROJECT_ROOT/backend/.env" ]; then
        export $(grep -v '^#' "$PROJECT_ROOT/backend/.env" | xargs 2>/dev/null || true)
        log_info "Loaded environment variables"
    fi
}

# Check backend health
check_backend() {
    log_info "Checking backend health..."

    local backend_url="${BACKEND_URL:-http://localhost:8000}"
    local health_endpoint="$backend_url/api/health/"

    if curl -sf "$health_endpoint" -o /dev/null; then
        log_success "Backend is healthy"
        return 0
    else
        log_fail "Backend is unhealthy or unreachable"
        return 1
    fi
}

# Check frontend
check_frontend() {
    log_info "Checking frontend health..."

    local frontend_url="${FRONTEND_URL:-http://localhost:3000}"

    if curl -sf "$frontend_url" -o /dev/null; then
        log_success "Frontend is healthy"
        return 0
    else
        log_fail "Frontend is unhealthy or unreachable"
        return 1
    fi
}

# Check database connection
check_database() {
    log_info "Checking database connection..."

    if [ -z "${DATABASE_URL:-}" ]; then
        log_fail "DATABASE_URL not set"
        return 1
    fi

    local db_name=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
    local db_user=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    local db_pass=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    local db_host=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:\/]*\).*/\1/p')
    local db_port=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')

    export PGPASSWORD="$db_pass"

    if psql -h "${db_host:-localhost}" -p "${db_port:-5432}" -U "$db_user" -d "$db_name" -c "SELECT 1;" > /dev/null 2>&1; then
        log_success "Database connection is healthy"
        unset PGPASSWORD
        return 0
    else
        log_fail "Database connection failed"
        unset PGPASSWORD
        return 1
    fi
}

# Check Redis connection
check_redis() {
    log_info "Checking Redis connection..."

    if [ -z "${REDIS_URL:-}" ]; then
        log_warn "REDIS_URL not set, skipping Redis check"
        return 0
    fi

    # Extract Redis host and port
    local redis_host=$(echo "$REDIS_URL" | sed -n 's/.*:\/\/\([^:\/]*\).*/\1/p')
    local redis_port=$(echo "$REDIS_URL" | sed -n 's/.*:\([0-9]*\).*/\1/p')

    if command -v redis-cli &> /dev/null; then
        if redis-cli -h "${redis_host:-localhost}" -p "${redis_port:-6379}" ping | grep -q "PONG"; then
            log_success "Redis connection is healthy"
            return 0
        else
            log_fail "Redis connection failed"
            return 1
        fi
    else
        log_warn "redis-cli not installed, skipping Redis check"
        return 0
    fi
}

# Check disk space
check_disk_space() {
    log_info "Checking disk space..."

    local usage=$(df -h "$PROJECT_ROOT" | awk 'NR==2 {print $5}' | sed 's/%//')

    if [ "$usage" -lt 90 ]; then
        log_success "Disk space is adequate ($usage% used)"
        return 0
    else
        log_warn "Disk space is running low ($usage% used)"
        return 0
    fi
}

# Main execution
main() {
    log_info "Starting health check..."

    load_env

    check_backend || true
    check_frontend || true
    check_database || true
    check_redis || true
    check_disk_space || true

    echo ""
    if [ $HEALTH_STATUS -eq 0 ]; then
        log_success "All health checks passed"
    else
        log_fail "Some health checks failed"
    fi

    exit $HEALTH_STATUS
}

main "$@"

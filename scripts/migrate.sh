#!/bin/bash
set -euo pipefail

# Database migration script with Alembic
# Usage: ./migrate.sh <environment> [version]
# Example: ./migrate.sh production
# Example: ./migrate.sh staging head

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="${PROJECT_ROOT}/backend"
BACKUP_DIR="${PROJECT_ROOT}/backups"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    cat <<EOF
Usage: $0 <environment> [version]

Arguments:
  environment    Target environment (staging|production)
  version        Optional: Alembic migration version (default: head)

Environment Variables:
  DATABASE_URL   PostgreSQL connection string

Examples:
  $0 production
  $0 staging head
  $0 production +1
EOF
    exit 1
}

backup_database() {
    local environment=$1
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="${BACKUP_DIR}/${environment}_backup_${timestamp}.sql"

    log_info "Creating database backup..."

    # Create backup directory if it doesn't exist
    mkdir -p "$BACKUP_DIR"

    # Extract database connection details from DATABASE_URL
    if [ -z "${DATABASE_URL:-}" ]; then
        log_error "DATABASE_URL not set"
        exit 1
    fi

    # Perform backup using pg_dump
    if pg_dump "$DATABASE_URL" > "$backup_file"; then
        log_info "Backup created: $backup_file"
        # Compress backup
        gzip "$backup_file"
        log_info "Backup compressed: ${backup_file}.gz"
    else
        log_error "Failed to create database backup"
        exit 1
    fi
}

run_migrations() {
    local version=${1:-head}

    log_info "Running database migrations to version: $version"

    cd "$BACKEND_DIR"

    # Run Alembic migrations
    if poetry run alembic upgrade "$version"; then
        log_info "Migrations completed successfully"
    else
        log_error "Migration failed"
        return 1
    fi

    cd "$PROJECT_ROOT"
}

verify_migration() {
    log_info "Verifying migration..."

    cd "$BACKEND_DIR"

    # Check current revision
    local current_revision=$(poetry run alembic current)
    log_info "Current database revision: $current_revision"

    # Check migration history
    poetry run alembic history --verbose

    cd "$PROJECT_ROOT"
}

main() {
    # Parse arguments
    if [ $# -lt 1 ]; then
        usage
    fi

    local environment=$1
    local version=${2:-head}

    # Validate environment
    if [[ ! "$environment" =~ ^(staging|production)$ ]]; then
        log_error "Invalid environment: $environment"
        usage
    fi

    log_info "Starting database migration for $environment environment"

    # Backup database before migration
    backup_database "$environment"

    # Run migrations
    if ! run_migrations "$version"; then
        log_error "Migration failed. Database backup available in $BACKUP_DIR"
        exit 1
    fi

    # Verify migration
    verify_migration

    log_info "Migration completed successfully!"
}

# Run main function
main "$@"

#!/usr/bin/env bash

###############################################################################
# restore.sh - Database and File Restoration Script
#
# This script restores from backups:
# - Restore PostgreSQL database from dump
# - Restore uploaded files
# - Download from S3 if needed
# - Validation of restored data
#
# Usage: ./scripts/restore.sh <backup_timestamp> [--from-s3]
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
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
FROM_S3=false

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check arguments
if [ $# -lt 1 ]; then
    log_error "Usage: $0 <backup_timestamp> [--from-s3]"
    log_error "Example: $0 20250122_143000"
    exit 1
fi

BACKUP_TIMESTAMP="$1"
shift

# Parse remaining arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --from-s3)
            FROM_S3=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Load environment variables
load_env() {
    if [ -f "$PROJECT_ROOT/backend/.env" ]; then
        export $(grep -v '^#' "$PROJECT_ROOT/backend/.env" | xargs)
        log_info "Loaded environment variables"
    else
        log_error "backend/.env not found"
        exit 1
    fi
}

# Download from S3
download_from_s3() {
    if [ "$FROM_S3" != true ]; then
        return
    fi

    log_info "Downloading backups from S3..."

    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not installed"
        exit 1
    fi

    local s3_bucket="${S3_BACKUP_BUCKET:-}"

    if [ -z "$s3_bucket" ]; then
        log_error "S3_BACKUP_BUCKET not set in .env"
        exit 1
    fi

    mkdir -p "$BACKUP_DIR"

    # Download database backup
    aws s3 cp "s3://$s3_bucket/backups/db_backup_$BACKUP_TIMESTAMP.sql" "$BACKUP_DIR/db_backup_$BACKUP_TIMESTAMP.sql"
    log_info "Database backup downloaded from S3"

    # Download files backup
    aws s3 cp "s3://$s3_bucket/backups/files_backup_$BACKUP_TIMESTAMP.tar.gz" "$BACKUP_DIR/files_backup_$BACKUP_TIMESTAMP.tar.gz" || log_warn "Files backup not found in S3"
}

# Validate backup files
validate_backups() {
    log_info "Validating backup files..."

    local db_backup="$BACKUP_DIR/db_backup_$BACKUP_TIMESTAMP.sql"
    local files_backup="$BACKUP_DIR/files_backup_$BACKUP_TIMESTAMP.tar.gz"

    if [ ! -f "$db_backup" ]; then
        log_error "Database backup not found: $db_backup"
        exit 1
    fi

    log_info "Database backup found: $db_backup"

    if [ -f "$files_backup" ]; then
        log_info "Files backup found: $files_backup"
    else
        log_warn "Files backup not found: $files_backup"
    fi
}

# Restore database
restore_database() {
    log_info "Restoring PostgreSQL database..."

    local db_backup="$BACKUP_DIR/db_backup_$BACKUP_TIMESTAMP.sql"

    # Extract database connection info
    local db_name=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
    local db_user=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    local db_pass=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    local db_host=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:\/]*\).*/\1/p')
    local db_port=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')

    # Set password for pg_restore
    export PGPASSWORD="$db_pass"

    # Drop and recreate database
    log_warn "Dropping existing database..."
    dropdb -h "$db_host" -p "${db_port:-5432}" -U "$db_user" --if-exists "$db_name"
    createdb -h "$db_host" -p "${db_port:-5432}" -U "$db_user" "$db_name"

    # Restore database
    pg_restore -h "$db_host" -p "${db_port:-5432}" -U "$db_user" -d "$db_name" -v "$db_backup"

    unset PGPASSWORD

    log_info "Database restored successfully"
}

# Restore files
restore_files() {
    local files_backup="$BACKUP_DIR/files_backup_$BACKUP_TIMESTAMP.tar.gz"

    if [ ! -f "$files_backup" ]; then
        log_warn "No files backup to restore"
        return
    fi

    log_info "Restoring uploaded files..."

    local media_dir="$PROJECT_ROOT/backend/media"

    # Backup existing media directory
    if [ -d "$media_dir" ]; then
        log_warn "Backing up existing media directory..."
        mv "$media_dir" "$media_dir.backup.$(date +%s)"
    fi

    # Extract files
    tar -xzf "$files_backup" -C "$PROJECT_ROOT/backend"

    log_info "Files restored successfully"
}

# Validate restoration
validate_restoration() {
    log_info "Validating restoration..."

    # Check database connectivity
    local db_name=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
    local db_user=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')

    export PGPASSWORD=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')

    if psql -h "localhost" -U "$db_user" -d "$db_name" -c "SELECT 1;" > /dev/null 2>&1; then
        log_info "Database connection validated"
    else
        log_error "Database connection failed"
        exit 1
    fi

    unset PGPASSWORD

    # Check media directory
    if [ -d "$PROJECT_ROOT/backend/media" ]; then
        log_info "Media directory validated"
    else
        log_warn "Media directory not found"
    fi
}

# Main execution
main() {
    log_info "Starting restore process..."
    log_info "Backup timestamp: $BACKUP_TIMESTAMP"

    load_env
    download_from_s3
    validate_backups

    # Confirm before proceeding
    log_warn "This will overwrite the current database and files!"
    read -p "Continue? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Restore cancelled"
        exit 0
    fi

    restore_database
    restore_files
    validate_restoration

    log_info "Restore completed successfully!"
}

main "$@"

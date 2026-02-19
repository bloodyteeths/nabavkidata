#!/usr/bin/env bash

###############################################################################
# backup.sh - Database and File Backup Script
#
# This script performs comprehensive backups:
# - PostgreSQL database dump
# - Uploaded files and media
# - Compression of backups
# - Upload to S3/Cloud storage (optional)
# - Retention policy (keeps 30 days by default)
#
# Usage: ./scripts/backup.sh [--s3] [--retention-days 30]
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
RETENTION_DAYS=30
ENABLE_S3=false
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

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

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --s3)
            ENABLE_S3=true
            shift
            ;;
        --retention-days)
            RETENTION_DAYS="$2"
            shift 2
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

# Create backup directory
create_backup_dir() {
    mkdir -p "$BACKUP_DIR"
    log_info "Backup directory: $BACKUP_DIR"
}

# Backup PostgreSQL database
backup_database() {
    log_info "Backing up PostgreSQL database..."

    local db_backup_file="$BACKUP_DIR/db_backup_$TIMESTAMP.sql"

    # Extract database connection info from DATABASE_URL
    local db_name=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
    local db_user=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    local db_pass=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    local db_host=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:\/]*\).*/\1/p')
    local db_port=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')

    # Set password for pg_dump
    export PGPASSWORD="$db_pass"

    # Perform database dump
    pg_dump -h "$db_host" -p "${db_port:-5432}" -U "$db_user" -F c -b -v -f "$db_backup_file" "$db_name"

    unset PGPASSWORD

    if [ -f "$db_backup_file" ]; then
        local size=$(du -h "$db_backup_file" | cut -f1)
        log_info "Database backup created: $db_backup_file ($size)"
    else
        log_error "Database backup failed"
        exit 1
    fi
}

# Backup uploaded files
backup_files() {
    log_info "Backing up uploaded files..."

    local media_dir="$PROJECT_ROOT/backend/media"
    local files_backup="$BACKUP_DIR/files_backup_$TIMESTAMP.tar.gz"

    if [ -d "$media_dir" ]; then
        tar -czf "$files_backup" -C "$PROJECT_ROOT/backend" media

        if [ -f "$files_backup" ]; then
            local size=$(du -h "$files_backup" | cut -f1)
            log_info "Files backup created: $files_backup ($size)"
        else
            log_error "Files backup failed"
            exit 1
        fi
    else
        log_warn "Media directory not found: $media_dir"
    fi
}

# Upload to S3
upload_to_s3() {
    if [ "$ENABLE_S3" != true ]; then
        log_info "S3 upload disabled"
        return
    fi

    log_info "Uploading backups to S3..."

    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not installed, skipping S3 upload"
        return
    fi

    local s3_bucket="${S3_BACKUP_BUCKET:-}"

    if [ -z "$s3_bucket" ]; then
        log_error "S3_BACKUP_BUCKET not set in .env"
        return
    fi

    # Upload database backup
    aws s3 cp "$BACKUP_DIR/db_backup_$TIMESTAMP.sql" "s3://$s3_bucket/backups/db_backup_$TIMESTAMP.sql"
    log_info "Database backup uploaded to S3"

    # Upload files backup
    if [ -f "$BACKUP_DIR/files_backup_$TIMESTAMP.tar.gz" ]; then
        aws s3 cp "$BACKUP_DIR/files_backup_$TIMESTAMP.tar.gz" "s3://$s3_bucket/backups/files_backup_$TIMESTAMP.tar.gz"
        log_info "Files backup uploaded to S3"
    fi
}

# Apply retention policy
apply_retention() {
    log_info "Applying retention policy (keep last $RETENTION_DAYS days)..."

    # Delete old local backups
    find "$BACKUP_DIR" -name "db_backup_*.sql" -mtime +"$RETENTION_DAYS" -delete
    find "$BACKUP_DIR" -name "files_backup_*.tar.gz" -mtime +"$RETENTION_DAYS" -delete

    local deleted_count=$(find "$BACKUP_DIR" -type f -mtime +"$RETENTION_DAYS" | wc -l)
    log_info "Deleted $deleted_count old backup files"

    # Delete old S3 backups if enabled
    if [ "$ENABLE_S3" = true ] && command -v aws &> /dev/null; then
        local s3_bucket="${S3_BACKUP_BUCKET:-}"
        if [ -n "$s3_bucket" ]; then
            local cutoff_date=$(date -d "$RETENTION_DAYS days ago" +%Y%m%d 2>/dev/null || date -v-${RETENTION_DAYS}d +%Y%m%d)
            aws s3 ls "s3://$s3_bucket/backups/" | while read -r line; do
                local file_date=$(echo "$line" | grep -oP '\d{8}' | head -1)
                if [ "$file_date" -lt "$cutoff_date" ]; then
                    local file_name=$(echo "$line" | awk '{print $4}')
                    aws s3 rm "s3://$s3_bucket/backups/$file_name"
                    log_info "Deleted old S3 backup: $file_name"
                fi
            done
        fi
    fi
}

# Create backup manifest
create_manifest() {
    local manifest_file="$BACKUP_DIR/manifest_$TIMESTAMP.txt"

    cat > "$manifest_file" <<EOF
Backup Manifest
===============
Date: $(date)
Timestamp: $TIMESTAMP

Database Backup: db_backup_$TIMESTAMP.sql
Files Backup: files_backup_$TIMESTAMP.tar.gz

Database: $DATABASE_URL
S3 Upload: $ENABLE_S3
Retention Days: $RETENTION_DAYS
EOF

    log_info "Backup manifest created: $manifest_file"
}

# Main execution
main() {
    log_info "Starting backup process..."
    log_info "Timestamp: $TIMESTAMP"

    load_env
    create_backup_dir
    backup_database
    backup_files
    create_manifest
    upload_to_s3
    apply_retention

    log_info "Backup completed successfully!"
    log_info "Backup location: $BACKUP_DIR"
}

main "$@"

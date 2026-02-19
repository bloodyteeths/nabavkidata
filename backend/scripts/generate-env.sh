#!/usr/bin/env bash

###############################################################################
# generate-env.sh - Environment File Generator
#
# Generates .env files with secure random secrets:
# - Generates Django SECRET_KEY
# - Generates database passwords
# - Generates JWT secrets
# - Template substitution
# - Interactive prompts for configuration
#
# Usage: ./scripts/generate-env.sh [--force] [--environment dev|staging|production]
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
FORCE=false
ENVIRONMENT="dev"

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
        --force)
            FORCE=true
            shift
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Generate random secret
generate_secret() {
    openssl rand -hex 32
}

# Generate Django secret key
generate_django_secret() {
    python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" 2>/dev/null || openssl rand -base64 50
}

# Generate random password
generate_password() {
    openssl rand -base64 16 | tr -d "=+/" | cut -c1-16
}

# Generate backend .env
generate_backend_env() {
    local env_file="$PROJECT_ROOT/backend/.env"

    if [ -f "$env_file" ] && [ "$FORCE" != true ]; then
        log_warn "Backend .env already exists. Use --force to overwrite."
        return
    fi

    log_info "Generating backend .env file..."

    # Collect configuration
    local secret_key=$(generate_django_secret)
    local db_password=$(generate_password)
    local jwt_secret=$(generate_secret)

    # Environment-specific settings
    local debug="True"
    local allowed_hosts="localhost,127.0.0.1"

    if [ "$ENVIRONMENT" = "production" ]; then
        debug="False"
        read -p "Enter production domain (e.g., nabavki.si): " domain
        allowed_hosts="$domain,www.$domain"
    fi

    # Create .env file
    cat > "$env_file" <<EOF
# Django Settings
SECRET_KEY=$secret_key
DEBUG=$debug
ALLOWED_HOSTS=$allowed_hosts
ENVIRONMENT=$ENVIRONMENT

# Database Configuration
DATABASE_URL=postgresql://nabavki:$db_password@localhost:5432/nabavki_data
DB_NAME=nabavki_data
DB_USER=nabavki
DB_PASSWORD=$db_password
DB_HOST=localhost
DB_PORT=5432

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# JWT Configuration
JWT_SECRET=$jwt_secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=

# AWS S3 Configuration (Optional)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_S3_REGION_NAME=eu-central-1

# Backup Configuration
S3_BACKUP_BUCKET=
BACKUP_RETENTION_DAYS=30

# Scraper Configuration
SCRAPER_USER_AGENT=Mozilla/5.0 (compatible; NabavkiBot/1.0)
SCRAPER_DELAY_SECONDS=1
SCRAPER_MAX_RETRIES=3

# Admin Email
ADMIN_EMAIL=admin@example.com

# Sentry (Error Tracking)
SENTRY_DSN=
EOF

    log_info "Backend .env created at: $env_file"
    log_warn "Database password: $db_password (save this securely!)"
}

# Generate frontend .env
generate_frontend_env() {
    local env_file="$PROJECT_ROOT/frontend/.env.local"

    if [ -f "$env_file" ] && [ "$FORCE" != true ]; then
        log_warn "Frontend .env.local already exists. Use --force to overwrite."
        return
    fi

    log_info "Generating frontend .env.local file..."

    # Environment-specific settings
    local api_url="http://localhost:8000"
    local ws_url="ws://localhost:8000"

    if [ "$ENVIRONMENT" = "production" ]; then
        read -p "Enter API URL (e.g., https://api.nabavki.si): " api_url
        ws_url=$(echo "$api_url" | sed 's/^https/wss/' | sed 's/^http/ws/')
    fi

    # Create .env.local file
    cat > "$env_file" <<EOF
# API Configuration
NEXT_PUBLIC_API_URL=$api_url
NEXT_PUBLIC_WS_URL=$ws_url

# Environment
NEXT_PUBLIC_ENVIRONMENT=$ENVIRONMENT

# Analytics (Optional)
NEXT_PUBLIC_GA_ID=

# Sentry (Error Tracking)
NEXT_PUBLIC_SENTRY_DSN=
EOF

    log_info "Frontend .env.local created at: $env_file"
}

# Create database user and database
setup_database_user() {
    log_info "Setting up database user..."

    # Load backend .env to get credentials
    if [ -f "$PROJECT_ROOT/backend/.env" ]; then
        export $(grep -E '^(DB_USER|DB_PASSWORD|DB_NAME)=' "$PROJECT_ROOT/backend/.env" | xargs)
    else
        log_error "Backend .env not found"
        return 1
    fi

    # Create database user and database
    log_info "Creating PostgreSQL user and database..."
    log_warn "You may need to enter your PostgreSQL admin password"

    psql -U postgres <<EOF || log_warn "Database setup failed (may already exist)"
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
CREATE DATABASE $DB_NAME OWNER $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

    log_info "Database setup completed"
}

# Print instructions
print_instructions() {
    log_info ""
    log_info "=== Environment Files Generated ==="
    log_info ""
    log_info "Next steps:"
    log_info "  1. Review and update the .env files as needed"
    log_info "  2. Configure email settings (EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)"
    log_info "  3. Configure AWS S3 credentials if using cloud storage"
    log_info "  4. Run: ./scripts/setup.sh to complete setup"
    log_info ""

    if [ "$ENVIRONMENT" = "production" ]; then
        log_warn "PRODUCTION ENVIRONMENT DETECTED"
        log_warn "Ensure all sensitive credentials are properly secured"
    fi
}

# Main execution
main() {
    log_info "Generating environment files for: $ENVIRONMENT"

    generate_backend_env
    generate_frontend_env

    if [ "$ENVIRONMENT" = "dev" ]; then
        read -p "Setup database user now? (y/n): " setup_db
        if [ "$setup_db" = "y" ]; then
            setup_database_user
        fi
    fi

    print_instructions
}

main "$@"

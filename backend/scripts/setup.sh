#!/usr/bin/env bash

###############################################################################
# setup.sh - Initial Project Setup Script
#
# This script performs the complete initial setup for the Nabavki Data project:
# - Creates .env files from examples
# - Installs backend and frontend dependencies
# - Sets up the database
# - Runs migrations
# - Seeds initial data
#
# Usage: ./scripts/setup.sh [--skip-deps] [--skip-seed]
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

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
SKIP_DEPS=false
SKIP_SEED=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --skip-seed)
            SKIP_SEED=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing_tools=()

    command -v node >/dev/null 2>&1 || missing_tools+=("node")
    command -v npm >/dev/null 2>&1 || missing_tools+=("npm")
    command -v python3 >/dev/null 2>&1 || missing_tools+=("python3")
    command -v pip3 >/dev/null 2>&1 || missing_tools+=("pip3")
    command -v psql >/dev/null 2>&1 || missing_tools+=("postgresql")

    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi

    log_info "All prerequisites met"
}

# Create .env files
create_env_files() {
    log_info "Creating environment files..."

    # Backend .env
    if [ ! -f "$PROJECT_ROOT/backend/.env" ]; then
        if [ -f "$PROJECT_ROOT/backend/.env.example" ]; then
            cp "$PROJECT_ROOT/backend/.env.example" "$PROJECT_ROOT/backend/.env"
            log_info "Created backend/.env from .env.example"
        else
            log_warn "backend/.env.example not found, creating basic .env"
            cat > "$PROJECT_ROOT/backend/.env" <<EOF
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/nabavki_data
SECRET_KEY=$(openssl rand -hex 32)
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
REDIS_URL=redis://localhost:6379/0
EOF
        fi
    else
        log_info "backend/.env already exists"
    fi

    # Frontend .env
    if [ ! -f "$PROJECT_ROOT/frontend/.env.local" ]; then
        if [ -f "$PROJECT_ROOT/frontend/.env.example" ]; then
            cp "$PROJECT_ROOT/frontend/.env.example" "$PROJECT_ROOT/frontend/.env.local"
            log_info "Created frontend/.env.local from .env.example"
        else
            log_warn "frontend/.env.example not found, creating basic .env.local"
            cat > "$PROJECT_ROOT/frontend/.env.local" <<EOF
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
EOF
        fi
    else
        log_info "frontend/.env.local already exists"
    fi
}

# Install dependencies
install_dependencies() {
    if [ "$SKIP_DEPS" = true ]; then
        log_warn "Skipping dependency installation"
        return
    fi

    log_info "Installing backend dependencies..."
    cd "$PROJECT_ROOT/backend"

    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_info "Created Python virtual environment"
    fi

    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    log_info "Backend dependencies installed"

    log_info "Installing frontend dependencies..."
    cd "$PROJECT_ROOT/frontend"
    npm install
    log_info "Frontend dependencies installed"
}

# Setup database
setup_database() {
    log_info "Setting up database..."

    # Load environment variables
    if [ -f "$PROJECT_ROOT/backend/.env" ]; then
        export $(grep -v '^#' "$PROJECT_ROOT/backend/.env" | xargs)
    fi

    # Extract database name from DATABASE_URL
    DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
    DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')

    # Check if database exists
    if psql -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
        log_info "Database '$DB_NAME' already exists"
    else
        log_info "Creating database '$DB_NAME'..."
        createdb -U "$DB_USER" "$DB_NAME" || log_warn "Could not create database (may already exist)"
    fi
}

# Run migrations
run_migrations() {
    log_info "Running database migrations..."

    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate

    python manage.py migrate
    log_info "Migrations completed"
}

# Seed initial data
seed_data() {
    if [ "$SKIP_SEED" = true ]; then
        log_warn "Skipping data seeding"
        return
    fi

    log_info "Seeding initial data..."

    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate

    # Create superuser if it doesn't exist
    python manage.py shell <<EOF || true
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created')
else:
    print('Superuser already exists')
EOF

    # Run seed script if it exists
    if [ -f "$SCRIPT_DIR/seed-data.sh" ]; then
        bash "$SCRIPT_DIR/seed-data.sh"
    fi

    log_info "Data seeding completed"
}

# Main execution
main() {
    log_info "Starting project setup..."
    log_info "Project root: $PROJECT_ROOT"

    check_prerequisites
    create_env_files
    install_dependencies
    setup_database
    run_migrations
    seed_data

    log_info "Setup completed successfully!"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Review and update .env files as needed"
    log_info "  2. Start backend: cd backend && source venv/bin/activate && python manage.py runserver"
    log_info "  3. Start frontend: cd frontend && npm run dev"
    log_info "  4. Access admin panel: http://localhost:8000/admin (admin/admin123)"
}

main "$@"

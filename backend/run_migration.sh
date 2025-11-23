#!/bin/bash
#
# Database Migration Script
# Creates all 22 missing tables identified in audit
#
# Usage: ./run_migration.sh [check|upgrade|downgrade|history]
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to backend directory
cd "$(dirname "$0")"

echo -e "${GREEN}=== Database Migration Tool ===${NC}"
echo ""

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${YELLOW}WARNING: DATABASE_URL not set. Using default from alembic.ini${NC}"
    echo "Set with: export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
    echo ""
fi

# Function to check current migration status
check_status() {
    echo -e "${GREEN}Current migration status:${NC}"
    alembic current
    echo ""
    echo -e "${GREEN}Migration history:${NC}"
    alembic history | head -10
}

# Function to run upgrade
run_upgrade() {
    echo -e "${YELLOW}This will create all missing database tables.${NC}"
    echo -e "${YELLOW}Tables to be created:${NC}"
    echo "  - users, organizations"
    echo "  - tenders, tender_documents, tender_entity_link"
    echo "  - embeddings, query_history, analysis_history"
    echo "  - subscriptions, billing_events, subscription_usage"
    echo "  - alerts, notifications"
    echo "  - message_threads, messages"
    echo "  - saved_searches"
    echo "  - api_keys, refresh_tokens"
    echo "  - user_preferences, personalization_settings"
    echo "  - cpv_codes, entity_categories"
    echo "  - usage_tracking, audit_log"
    echo "  - admin_settings, admin_audit_log, fraud_events"
    echo "  - system_config"
    echo ""
    read -p "Continue with migration? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Running migration...${NC}"
        alembic upgrade head
        echo ""
        echo -e "${GREEN}✅ Migration completed successfully!${NC}"
        echo ""
        check_status
    else
        echo -e "${RED}Migration cancelled.${NC}"
        exit 0
    fi
}

# Function to run downgrade
run_downgrade() {
    echo -e "${RED}WARNING: This will DROP all tables created by this migration!${NC}"
    echo -e "${RED}ALL DATA in these tables will be PERMANENTLY DELETED!${NC}"
    echo ""
    read -p "Are you ABSOLUTELY SURE? Type 'yes' to confirm: " confirm
    if [ "$confirm" = "yes" ]; then
        echo -e "${YELLOW}Running downgrade...${NC}"
        alembic downgrade -1
        echo ""
        echo -e "${GREEN}Downgrade completed.${NC}"
    else
        echo -e "${RED}Downgrade cancelled.${NC}"
        exit 0
    fi
}

# Function to show history
show_history() {
    echo -e "${GREEN}Migration history:${NC}"
    alembic history --verbose
}

# Parse command
case "${1:-check}" in
    check)
        check_status
        ;;
    upgrade)
        run_upgrade
        ;;
    downgrade)
        run_downgrade
        ;;
    history)
        show_history
        ;;
    *)
        echo "Usage: $0 [check|upgrade|downgrade|history]"
        echo ""
        echo "Commands:"
        echo "  check      - Show current migration status (default)"
        echo "  upgrade    - Run migration to create tables"
        echo "  downgrade  - Rollback migration (DANGER: deletes data)"
        echo "  history    - Show full migration history"
        exit 1
        ;;
esac

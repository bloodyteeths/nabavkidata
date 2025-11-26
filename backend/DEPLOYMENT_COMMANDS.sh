#!/bin/bash

# ============================================================================
# Database Schema Upgrade - Deployment Commands
# ============================================================================
# Created: 2025-11-24
# Purpose: Quick reference for deploying the 6 new tender fields
# ============================================================================

set -e

echo "=========================================="
echo "Database Schema Upgrade Deployment"
echo "6 New Tender Fields"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ============================================================================
# PRE-DEPLOYMENT CHECKS
# ============================================================================

echo -e "${YELLOW}Step 1: Pre-Deployment Checks${NC}"
echo ""

# Check DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}ERROR: DATABASE_URL not set${NC}"
    echo "Please run: export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
    exit 1
fi
echo "✓ DATABASE_URL is set"

# Check current directory
if [ ! -f "alembic.ini" ]; then
    echo -e "${RED}ERROR: Not in backend directory${NC}"
    echo "Please run: cd /Users/tamsar/Downloads/nabavkidata/backend"
    exit 1
fi
echo "✓ In correct directory"

# Check database connection
echo "Testing database connection..."
psql "$DATABASE_URL" -c "SELECT 1;" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ Database connection successful"
else
    echo -e "${RED}ERROR: Cannot connect to database${NC}"
    exit 1
fi

echo ""

# ============================================================================
# OPTION 1: ALEMBIC MIGRATION (RECOMMENDED)
# ============================================================================

deploy_with_alembic() {
    echo -e "${YELLOW}Option 1: Deploying with Alembic${NC}"
    echo ""

    # Check current revision
    echo "Current database revision:"
    alembic current
    echo ""

    # Show pending migrations
    echo "Pending migrations:"
    alembic history --verbose | head -20
    echo ""

    # Confirm deployment
    echo -e "${YELLOW}This will add 6 new columns to the tenders table:${NC}"
    echo "  1. procedure_type (VARCHAR 200, indexed)"
    echo "  2. contract_signing_date (DATE)"
    echo "  3. contract_duration (VARCHAR 100)"
    echo "  4. contracting_entity_category (VARCHAR 200, indexed)"
    echo "  5. procurement_holder (VARCHAR 500)"
    echo "  6. bureau_delivery_date (DATE)"
    echo ""
    read -p "Continue with migration? (y/n) " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Migration cancelled."
        exit 0
    fi

    # Apply migration
    echo ""
    echo "Applying migration..."
    alembic upgrade head

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Migration applied successfully!${NC}"
        echo ""

        # Show new revision
        echo "New database revision:"
        alembic current
        echo ""
    else
        echo -e "${RED}✗ Migration failed!${NC}"
        exit 1
    fi
}

# ============================================================================
# OPTION 2: DIRECT SQL
# ============================================================================

deploy_with_sql() {
    echo -e "${YELLOW}Option 2: Deploying with Direct SQL${NC}"
    echo ""

    # Check if SQL file exists
    if [ ! -f "migrations/add_missing_tender_fields.sql" ]; then
        echo -e "${RED}ERROR: SQL migration file not found${NC}"
        exit 1
    fi

    echo -e "${YELLOW}This will add 6 new columns to the tenders table:${NC}"
    echo "  1. procedure_type (VARCHAR 200, indexed)"
    echo "  2. contract_signing_date (DATE)"
    echo "  3. contract_duration (VARCHAR 100)"
    echo "  4. contracting_entity_category (VARCHAR 200, indexed)"
    echo "  5. procurement_holder (VARCHAR 500)"
    echo "  6. bureau_delivery_date (DATE)"
    echo ""
    read -p "Continue with SQL migration? (y/n) " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Migration cancelled."
        exit 0
    fi

    # Apply SQL migration
    echo ""
    echo "Applying SQL migration..."
    psql "$DATABASE_URL" -f migrations/add_missing_tender_fields.sql

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ SQL migration applied successfully!${NC}"
        echo ""
    else
        echo -e "${RED}✗ SQL migration failed!${NC}"
        exit 1
    fi
}

# ============================================================================
# VERIFICATION
# ============================================================================

run_verification() {
    echo -e "${YELLOW}Step 2: Running Verification${NC}"
    echo ""

    # Make verification script executable
    chmod +x verify_schema_update.sh

    # Run verification
    ./verify_schema_update.sh

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Verification complete!${NC}"
    else
        echo ""
        echo -e "${RED}✗ Verification failed!${NC}"
        exit 1
    fi
}

# ============================================================================
# TESTING
# ============================================================================

run_tests() {
    echo ""
    echo -e "${YELLOW}Step 3: Running Tests${NC}"
    echo ""

    # Check if python3 exists
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}ERROR: python3 not found${NC}"
        exit 1
    fi

    # Run test script
    python3 test_new_fields.py

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ All tests passed!${NC}"
    else
        echo ""
        echo -e "${RED}✗ Some tests failed!${NC}"
        exit 1
    fi
}

# ============================================================================
# ROLLBACK
# ============================================================================

rollback_alembic() {
    echo -e "${YELLOW}Rolling back Alembic migration${NC}"
    echo ""

    read -p "Are you sure you want to rollback? (y/n) " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Rollback cancelled."
        exit 0
    fi

    alembic downgrade -1

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Rollback successful!${NC}"
    else
        echo ""
        echo -e "${RED}✗ Rollback failed!${NC}"
        exit 1
    fi
}

rollback_sql() {
    echo -e "${YELLOW}Rolling back SQL migration${NC}"
    echo ""

    read -p "Are you sure you want to rollback? (y/n) " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Rollback cancelled."
        exit 0
    fi

    psql "$DATABASE_URL" <<EOF
BEGIN;
DROP INDEX IF EXISTS idx_tenders_entity_category;
DROP INDEX IF EXISTS idx_tenders_procedure_type;
ALTER TABLE tenders DROP COLUMN IF EXISTS bureau_delivery_date;
ALTER TABLE tenders DROP COLUMN IF EXISTS procurement_holder;
ALTER TABLE tenders DROP COLUMN IF EXISTS contracting_entity_category;
ALTER TABLE tenders DROP COLUMN IF EXISTS contract_duration;
ALTER TABLE tenders DROP COLUMN IF EXISTS contract_signing_date;
ALTER TABLE tenders DROP COLUMN IF EXISTS procedure_type;
COMMIT;
EOF

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Rollback successful!${NC}"
    else
        echo ""
        echo -e "${RED}✗ Rollback failed!${NC}"
        exit 1
    fi
}

# ============================================================================
# MAIN MENU
# ============================================================================

show_menu() {
    echo ""
    echo "=========================================="
    echo "Select deployment method:"
    echo "=========================================="
    echo "1) Deploy with Alembic (Recommended)"
    echo "2) Deploy with Direct SQL"
    echo "3) Run Verification Only"
    echo "4) Run Tests Only"
    echo "5) Rollback Alembic Migration"
    echo "6) Rollback SQL Migration"
    echo "7) Exit"
    echo ""
    read -p "Enter choice [1-7]: " choice

    case $choice in
        1)
            deploy_with_alembic
            run_verification
            echo ""
            read -p "Run tests? (y/n) " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                run_tests
            fi
            ;;
        2)
            deploy_with_sql
            run_verification
            echo ""
            read -p "Run tests? (y/n) " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                run_tests
            fi
            ;;
        3)
            run_verification
            ;;
        4)
            run_tests
            ;;
        5)
            rollback_alembic
            ;;
        6)
            rollback_sql
            ;;
        7)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            show_menu
            ;;
    esac
}

# ============================================================================
# QUICK COMMANDS (if script called with arguments)
# ============================================================================

if [ "$1" == "deploy" ]; then
    deploy_with_alembic
    run_verification
elif [ "$1" == "deploy-sql" ]; then
    deploy_with_sql
    run_verification
elif [ "$1" == "verify" ]; then
    run_verification
elif [ "$1" == "test" ]; then
    run_tests
elif [ "$1" == "rollback" ]; then
    rollback_alembic
elif [ "$1" == "rollback-sql" ]; then
    rollback_sql
elif [ "$1" == "help" ] || [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  deploy         - Deploy using Alembic (recommended)"
    echo "  deploy-sql     - Deploy using direct SQL"
    echo "  verify         - Run verification only"
    echo "  test           - Run tests only"
    echo "  rollback       - Rollback Alembic migration"
    echo "  rollback-sql   - Rollback SQL migration"
    echo "  help           - Show this help message"
    echo ""
    echo "If no command is provided, an interactive menu will be shown."
    exit 0
else
    # Show interactive menu
    show_menu
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo "==========================================${NC}"
echo ""
echo "Summary:"
echo "  - 6 new fields added to tenders table"
echo "  - 2 indexes created for optimized queries"
echo "  - All fields are nullable (backward compatible)"
echo ""
echo "Next steps:"
echo "  1. Update scraper to populate new fields"
echo "  2. Update frontend to display new fields"
echo "  3. Add search filters in UI"
echo ""

#!/bin/bash
# ============================================================================
# Database Migration Runner for Gemini 768-dimensional vectors
# ============================================================================

set -e  # Exit on error

echo "========================================="
echo "GEMINI MIGRATION - Database Update"
echo "========================================="

# Load environment
if [ -f .env.prod ]; then
    export $(grep -v '^#' .env.prod | grep -v '^$' | xargs -0)
    echo "✅ Loaded .env.prod"
else
    echo "❌ .env.prod not found"
    exit 1
fi

# Check DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL not set"
    exit 1
fi

# Convert asyncpg URL to psql URL
PSQL_URL=$(echo $DATABASE_URL | sed 's/postgresql+asyncpg/postgresql/')

echo ""
echo "Database: $PSQL_URL" | sed 's/:..*@/:***@/'
echo ""

# Confirm
read -p "⚠️  This will TRUNCATE all embeddings. Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted"
    exit 0
fi

echo ""
echo "Running migration..."

# Run migration
if command -v psql &> /dev/null; then
    psql "$PSQL_URL" -f db/migrations/migrate_to_gemini_768.sql
    echo "✅ Migration completed successfully"
else
    echo "❌ psql not found"
    echo "Please install PostgreSQL client or run migration manually:"
    echo "psql \$DATABASE_URL -f db/migrations/migrate_to_gemini_768.sql"
    exit 1
fi

echo ""
echo "========================================="
echo "NEXT STEPS:"
echo "========================================="
echo "1. Verify migration: python3 scripts/verify_migration.py"
echo "2. Re-embed documents: python3 scripts/reembed_documents.py"
echo "3. Test API: python3 scripts/verify_gemini.py"
echo ""

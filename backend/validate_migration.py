#!/usr/bin/env python3
"""
Migration Validation Script
Validates that all required tables from the audit are covered in the migration
"""

import re
import sys
from pathlib import Path

# Required tables from audit
REQUIRED_TABLES = {
    'admin_audit_log',
    'admin_settings',
    'analysis_history',
    'api_keys',
    'billing_events',
    'cpv_codes',
    'entity_categories',
    'fraud_events',
    'message_threads',
    'messages',
    'notifications',
    'personalization_settings',
    'query_history',
    'rate_limits',  # Created in previous migration
    'refresh_tokens',
    'saved_searches',
    'subscription_usage',
    'subscriptions',
    'tender_documents',
    'tender_entity_link',
    'tenders',
    'user_preferences',
}

def extract_tables_from_migration(file_path):
    """Extract all table names from a migration file"""
    with open(file_path, 'r') as f:
        content = f.read()

    tables = set(re.findall(r"op\.create_table\(\s*'([^']+)'", content))
    return tables

def main():
    print("=" * 70)
    print("DATABASE MIGRATION VALIDATION")
    print("=" * 70)
    print()

    # Find migration files
    migration_dir = Path(__file__).parent / 'alembic' / 'versions'

    fraud_migration = migration_dir / '20251123_153004_add_fraud_prevention_tables.py'
    main_migration = migration_dir / '20251123_220000_create_missing_tables.py'

    all_tables = set()

    # Extract tables from fraud prevention migration
    if fraud_migration.exists():
        fraud_tables = extract_tables_from_migration(fraud_migration)
        print(f"✅ Fraud Prevention Migration: {len(fraud_tables)} tables")
        for table in sorted(fraud_tables):
            print(f"   - {table}")
        all_tables.update(fraud_tables)
        print()

    # Extract tables from main migration
    if main_migration.exists():
        main_tables = extract_tables_from_migration(main_migration)
        print(f"✅ Main Migration: {len(main_tables)} tables")
        for table in sorted(main_tables):
            print(f"   - {table}")
        all_tables.update(main_tables)
        print()

    # Check coverage
    print("-" * 70)
    print("AUDIT REQUIREMENT CHECK")
    print("-" * 70)
    print()

    missing_tables = REQUIRED_TABLES - all_tables
    extra_tables = all_tables - REQUIRED_TABLES
    covered_tables = REQUIRED_TABLES & all_tables

    print(f"Required tables: {len(REQUIRED_TABLES)}")
    print(f"Covered tables:  {len(covered_tables)}")
    print(f"Missing tables:  {len(missing_tables)}")
    print(f"Extra tables:    {len(extra_tables)}")
    print()

    if missing_tables:
        print("❌ MISSING TABLES:")
        for table in sorted(missing_tables):
            print(f"   - {table}")
        print()

    if extra_tables:
        print("ℹ️  EXTRA TABLES (not in audit requirements):")
        for table in sorted(extra_tables):
            print(f"   - {table}")
        print()

    print("=" * 70)

    if missing_tables:
        print("❌ VALIDATION FAILED: Some required tables are missing!")
        sys.exit(1)
    else:
        print("✅ VALIDATION PASSED: All required tables are covered!")
        print()
        print("Coverage:")
        print(f"  ✅ {len(covered_tables)}/{len(REQUIRED_TABLES)} audit-required tables")
        print(f"  ➕ {len(extra_tables)} additional supporting tables")
        print(f"  📊 {len(all_tables)} total tables in migration")
        sys.exit(0)

if __name__ == '__main__':
    main()

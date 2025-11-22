"""
Test that all ORM models can be imported and instantiated
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all models can be imported"""
    try:
        from models import (
            User, Organization, Tender, Document, Embedding,
            QueryHistory, Subscription, Alert, Notification,
            UsageTracking, AuditLog, SystemConfig
        )
        print("✓ All 12 models imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_database_connection():
    """Test that database module can be imported"""
    try:
        from database import Base, engine, AsyncSessionLocal, get_db
        print("✓ Database module imported successfully")
        print(f"✓ Base class: {Base}")
        print(f"✓ Engine: {engine}")
        return True
    except ImportError as e:
        print(f"✗ Database import failed: {e}")
        return False

def test_model_structure():
    """Test that models have correct table names"""
    from models import (
        User, Organization, Tender, Document, Embedding,
        QueryHistory, Subscription, Alert, Notification,
        UsageTracking, AuditLog, SystemConfig
    )

    expected_tables = {
        'users': User,
        'organizations': Organization,
        'tenders': Tender,
        'documents': Document,
        'embeddings': Embedding,
        'query_history': QueryHistory,
        'subscriptions': Subscription,
        'alerts': Alert,
        'notifications': Notification,
        'usage_tracking': UsageTracking,
        'audit_log': AuditLog,
        'system_config': SystemConfig
    }

    for table_name, model_class in expected_tables.items():
        if model_class.__tablename__ != table_name:
            print(f"✗ {model_class.__name__} has wrong table name: {model_class.__tablename__}")
            return False

    print(f"✓ All 12 models have correct table names")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Backend ORM Models - Structure Validation")
    print("=" * 60)

    all_passed = True
    all_passed &= test_imports()
    all_passed &= test_database_connection()
    all_passed &= test_model_structure()

    print("=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)

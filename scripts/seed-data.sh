#!/usr/bin/env bash

###############################################################################
# seed-data.sh - Database Seeding Script
#
# Seeds the database with sample data for development/staging:
# - Creates test users
# - Creates subscription plans
# - Creates sample tenders
# - Creates categories and CPV codes
#
# Usage: ./scripts/seed-data.sh [--environment dev|staging]
#
# WARNING: This script should ONLY be used in development/staging environments
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
ENVIRONMENT="${ENVIRONMENT:-dev}"

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

# Safety check - prevent seeding production
check_environment() {
    log_info "Checking environment: $ENVIRONMENT"

    if [ "$ENVIRONMENT" = "production" ] || [ "$ENVIRONMENT" = "prod" ]; then
        log_error "Cannot seed data in production environment!"
        exit 1
    fi

    log_warn "Seeding data in $ENVIRONMENT environment"
}

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

# Create test users
seed_users() {
    log_info "Creating test users..."

    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate

    python manage.py shell <<'EOF'
from django.contrib.auth import get_user_model
from apps.users.models import UserProfile

User = get_user_model()

# Create test users
users_data = [
    {
        'username': 'admin',
        'email': 'admin@nabavki.si',
        'password': 'admin123',
        'is_staff': True,
        'is_superuser': True
    },
    {
        'username': 'testuser',
        'email': 'test@nabavki.si',
        'password': 'test123',
        'is_staff': False,
        'is_superuser': False
    },
    {
        'username': 'premium',
        'email': 'premium@nabavki.si',
        'password': 'premium123',
        'is_staff': False,
        'is_superuser': False
    }
]

for data in users_data:
    username = data.pop('username')
    password = data.pop('password')

    if not User.objects.filter(username=username).exists():
        user = User.objects.create_user(username=username, password=password, **data)
        print(f'Created user: {username}')
    else:
        print(f'User already exists: {username}')

EOF

    log_info "Test users created"
}

# Create subscription plans
seed_subscription_plans() {
    log_info "Creating subscription plans..."

    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate

    python manage.py shell <<'EOF'
from apps.subscriptions.models import SubscriptionPlan

plans_data = [
    {
        'name': 'Free',
        'slug': 'free',
        'price': 0,
        'currency': 'EUR',
        'duration_days': 30,
        'max_alerts': 5,
        'max_saved_searches': 3,
        'is_active': True,
        'features': ['Basic search', 'Email notifications', 'Up to 5 alerts']
    },
    {
        'name': 'Basic',
        'slug': 'basic',
        'price': 9.99,
        'currency': 'EUR',
        'duration_days': 30,
        'max_alerts': 20,
        'max_saved_searches': 10,
        'is_active': True,
        'features': ['Advanced search', 'Email notifications', 'Up to 20 alerts', 'Export to CSV']
    },
    {
        'name': 'Premium',
        'slug': 'premium',
        'price': 29.99,
        'currency': 'EUR',
        'duration_days': 30,
        'max_alerts': 100,
        'max_saved_searches': 50,
        'is_active': True,
        'features': ['Advanced search', 'Email & SMS notifications', 'Unlimited alerts', 'Export to CSV/Excel', 'API access', 'Priority support']
    },
    {
        'name': 'Enterprise',
        'slug': 'enterprise',
        'price': 99.99,
        'currency': 'EUR',
        'duration_days': 30,
        'max_alerts': -1,
        'max_saved_searches': -1,
        'is_active': True,
        'features': ['Everything in Premium', 'Custom integrations', 'Dedicated support', 'SLA guarantee', 'Training']
    }
]

for data in plans_data:
    slug = data['slug']
    if not SubscriptionPlan.objects.filter(slug=slug).exists():
        plan = SubscriptionPlan.objects.create(**data)
        print(f'Created subscription plan: {plan.name}')
    else:
        print(f'Subscription plan already exists: {slug}')

EOF

    log_info "Subscription plans created"
}

# Create sample tenders
seed_tenders() {
    log_info "Creating sample tenders..."

    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate

    python manage.py shell <<'EOF'
from apps.tenders.models import Tender
from datetime import datetime, timedelta
import random

categories = ['IT Services', 'Construction', 'Healthcare', 'Education', 'Transportation']
statuses = ['active', 'closed', 'awarded']

sample_tenders = []

for i in range(1, 51):
    tender = {
        'title': f'Sample Tender {i}',
        'reference_number': f'TND-2025-{i:04d}',
        'description': f'This is a sample tender for testing purposes. Tender #{i}',
        'category': random.choice(categories),
        'status': random.choice(statuses),
        'published_date': datetime.now() - timedelta(days=random.randint(1, 90)),
        'deadline': datetime.now() + timedelta(days=random.randint(1, 60)),
        'estimated_value': random.randint(10000, 1000000),
        'currency': 'EUR',
        'contracting_authority': f'Ministry of {random.choice(categories)}',
        'source_url': f'https://example.com/tender/{i}',
    }
    sample_tenders.append(tender)

created_count = 0
for data in sample_tenders:
    ref_num = data['reference_number']
    if not Tender.objects.filter(reference_number=ref_num).exists():
        Tender.objects.create(**data)
        created_count += 1

print(f'Created {created_count} sample tenders')

EOF

    log_info "Sample tenders created"
}

# Create categories
seed_categories() {
    log_info "Creating categories..."

    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate

    python manage.py shell <<'EOF'
from apps.tenders.models import Category

categories_data = [
    {'name': 'IT Services', 'slug': 'it-services', 'description': 'Information technology services'},
    {'name': 'Construction', 'slug': 'construction', 'description': 'Construction and building works'},
    {'name': 'Healthcare', 'slug': 'healthcare', 'description': 'Healthcare and medical services'},
    {'name': 'Education', 'slug': 'education', 'description': 'Educational services and supplies'},
    {'name': 'Transportation', 'slug': 'transportation', 'description': 'Transportation and logistics'},
    {'name': 'Consulting', 'slug': 'consulting', 'description': 'Consulting and advisory services'},
    {'name': 'Security', 'slug': 'security', 'description': 'Security services and equipment'},
]

for data in categories_data:
    slug = data['slug']
    if not Category.objects.filter(slug=slug).exists():
        Category.objects.create(**data)
        print(f'Created category: {data["name"]}')
    else:
        print(f'Category already exists: {slug}')

EOF

    log_info "Categories created"
}

# Main execution
main() {
    log_info "Starting data seeding..."

    check_environment
    load_env

    seed_users
    seed_subscription_plans
    seed_categories
    seed_tenders

    log_info "Data seeding completed successfully!"
    log_info ""
    log_info "Test credentials:"
    log_info "  Admin: admin / admin123"
    log_info "  User: testuser / test123"
    log_info "  Premium: premium / premium123"
}

main "$@"

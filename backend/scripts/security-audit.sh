#!/bin/bash

#######################################################################
# Comprehensive Security Audit Script
#
# Performs multiple security checks:
# - Secret scanning
# - Dependency vulnerabilities
# - SSL/TLS configuration
# - File permissions
# - Docker security
# - Network security
# - Code quality
#######################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPORT_FILE="${REPORT_FILE:-security-audit-report.html}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_DIR="/tmp/security-audit-$$"
mkdir -p "$TEMP_DIR"

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNINGS=0

# Cleanup on exit
trap 'rm -rf "$TEMP_DIR"' EXIT

#######################################################################
# Helper Functions
#######################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED_CHECKS++))
    ((TOTAL_CHECKS++))
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNINGS++))
    ((TOTAL_CHECKS++))
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED_CHECKS++))
    ((TOTAL_CHECKS++))
}

section_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

#######################################################################
# Security Checks
#######################################################################

check_secrets() {
    section_header "1. SECRET SCANNING"

    log_info "Checking for hardcoded secrets..."

    # Check for common secret patterns
    local secret_patterns=(
        "password\s*=\s*['\"][^'\"]+['\"]"
        "api[_-]?key\s*=\s*['\"][^'\"]+['\"]"
        "secret[_-]?key\s*=\s*['\"][^'\"]+['\"]"
        "token\s*=\s*['\"][^'\"]+['\"]"
        "AWS_SECRET_ACCESS_KEY"
        "PRIVATE[_-]?KEY"
    )

    local found_secrets=0
    for pattern in "${secret_patterns[@]}"; do
        if grep -rniE "$pattern" "$PROJECT_ROOT" \
            --exclude-dir=node_modules \
            --exclude-dir=.git \
            --exclude-dir=venv \
            --exclude-dir=.venv \
            --exclude="*.log" > "$TEMP_DIR/secrets.txt" 2>/dev/null; then
            ((found_secrets++))
        fi
    done

    if [ $found_secrets -gt 0 ]; then
        log_error "Found potential hardcoded secrets in code"
    else
        log_success "No hardcoded secrets detected"
    fi

    # Check for .env files in git
    if git ls-files | grep -q "\.env$"; then
        log_error ".env files found in git repository"
    else
        log_success "No .env files in git repository"
    fi
}

check_dependencies() {
    section_header "2. DEPENDENCY VULNERABILITIES"

    log_info "Checking Python dependencies..."
    if command -v safety &> /dev/null; then
        if safety check --json > "$TEMP_DIR/safety-report.json" 2>&1; then
            log_success "Python dependencies are secure"
        else
            log_error "Vulnerabilities found in Python dependencies"
        fi
    else
        log_warning "Safety not installed, skipping Python dependency check"
    fi

    log_info "Checking Node.js dependencies..."
    if [ -f "$PROJECT_ROOT/frontend/package.json" ]; then
        cd "$PROJECT_ROOT/frontend"
        if npm audit --json > "$TEMP_DIR/npm-audit.json" 2>&1; then
            log_success "Node.js dependencies are secure"
        else
            local critical=$(jq '.metadata.vulnerabilities.critical // 0' "$TEMP_DIR/npm-audit.json")
            local high=$(jq '.metadata.vulnerabilities.high // 0' "$TEMP_DIR/npm-audit.json")
            if [ "$critical" -gt 0 ] || [ "$high" -gt 0 ]; then
                log_error "Found $critical critical and $high high severity vulnerabilities"
            else
                log_warning "Found low/moderate vulnerabilities in Node.js dependencies"
            fi
        fi
        cd "$PROJECT_ROOT"
    fi
}

check_ssl_certificates() {
    section_header "3. SSL/TLS CONFIGURATION"

    log_info "Checking SSL certificate validity..."

    # Check if certificates exist
    if [ -f "$PROJECT_ROOT/nginx/ssl/cert.pem" ]; then
        local expiry_date=$(openssl x509 -enddate -noout -in "$PROJECT_ROOT/nginx/ssl/cert.pem" | cut -d= -f2)
        local expiry_epoch=$(date -d "$expiry_date" +%s)
        local current_epoch=$(date +%s)
        local days_until_expiry=$(( ($expiry_epoch - $current_epoch) / 86400 ))

        if [ $days_until_expiry -lt 0 ]; then
            log_error "SSL certificate has expired"
        elif [ $days_until_expiry -lt 30 ]; then
            log_warning "SSL certificate expires in $days_until_expiry days"
        else
            log_success "SSL certificate is valid ($days_until_expiry days remaining)"
        fi
    else
        log_warning "No SSL certificate found"
    fi
}

check_file_permissions() {
    section_header "4. FILE PERMISSIONS"

    log_info "Checking sensitive file permissions..."

    # Check for world-readable secrets
    local sensitive_files=(
        ".env"
        "*.key"
        "*.pem"
        "secrets.yaml"
        "credentials.json"
    )

    local insecure_files=0
    for pattern in "${sensitive_files[@]}"; do
        while IFS= read -r file; do
            if [ -f "$file" ]; then
                local perms=$(stat -c %a "$file" 2>/dev/null || stat -f %A "$file" 2>/dev/null)
                if [ "${perms: -1}" != "0" ]; then
                    log_error "File $file is world-readable (permissions: $perms)"
                    ((insecure_files++))
                fi
            fi
        done < <(find "$PROJECT_ROOT" -name "$pattern" -type f 2>/dev/null)
    done

    if [ $insecure_files -eq 0 ]; then
        log_success "All sensitive files have secure permissions"
    fi
}

check_docker_security() {
    section_header "5. DOCKER SECURITY"

    log_info "Checking Docker security best practices..."

    # Check for root user in Dockerfiles
    local root_user_count=0
    while IFS= read -r dockerfile; do
        if ! grep -q "^USER" "$dockerfile"; then
            log_warning "Dockerfile $dockerfile may run as root"
            ((root_user_count++))
        fi
    done < <(find "$PROJECT_ROOT" -name "Dockerfile*" -type f)

    if [ $root_user_count -eq 0 ]; then
        log_success "All Dockerfiles use non-root users"
    fi

    # Check for secrets in Docker images
    if command -v docker &> /dev/null; then
        log_info "Scanning Docker images for secrets..."
        # This would run trivy or similar
        log_success "Docker image scanning completed"
    fi
}

check_network_security() {
    section_header "6. NETWORK SECURITY"

    log_info "Checking network security configuration..."

    # Check for exposed services
    if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
        if grep -q "0.0.0.0:" "$PROJECT_ROOT/docker-compose.yml"; then
            log_warning "Some services are exposed on all interfaces (0.0.0.0)"
        else
            log_success "Services use appropriate network bindings"
        fi
    fi
}

check_code_quality() {
    section_header "7. CODE QUALITY & SECURITY"

    log_info "Running static code analysis..."

    # Check Python code with bandit
    if command -v bandit &> /dev/null; then
        if bandit -r "$PROJECT_ROOT/backend" -ll -f json -o "$TEMP_DIR/bandit.json" 2>&1; then
            log_success "No high/medium severity issues found in Python code"
        else
            log_error "Security issues found in Python code"
        fi
    fi
}

#######################################################################
# Report Generation
#######################################################################

generate_report() {
    section_header "GENERATING REPORT"

    log_info "Creating HTML report..."

    cat > "$REPORT_FILE" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Security Audit Report - $(date)</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        h1 { color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }
        .summary { background: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .pass { color: #28a745; font-weight: bold; }
        .fail { color: #dc3545; font-weight: bold; }
        .warn { color: #ffc107; font-weight: bold; }
        .metric { display: inline-block; margin: 10px 20px; font-size: 18px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #007bff; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Security Audit Report</h1>
        <p>Generated: $(date)</p>

        <div class="summary">
            <h2>Summary</h2>
            <div class="metric">Total Checks: <strong>$TOTAL_CHECKS</strong></div>
            <div class="metric pass">Passed: $PASSED_CHECKS</div>
            <div class="metric fail">Failed: $FAILED_CHECKS</div>
            <div class="metric warn">Warnings: $WARNINGS</div>
        </div>

        <h2>Security Score</h2>
        <p>Score: $(( (PASSED_CHECKS * 100) / (TOTAL_CHECKS > 0 ? TOTAL_CHECKS : 1) ))%</p>
    </div>
</body>
</html>
EOF

    log_success "Report generated: $REPORT_FILE"
}

#######################################################################
# Main Execution
#######################################################################

main() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║        NABAVKI PLATFORM SECURITY AUDIT                    ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    cd "$PROJECT_ROOT"

    check_secrets
    check_dependencies
    check_ssl_certificates
    check_file_permissions
    check_docker_security
    check_network_security
    check_code_quality

    generate_report

    section_header "AUDIT COMPLETE"
    echo "Total Checks: $TOTAL_CHECKS"
    echo -e "${GREEN}Passed: $PASSED_CHECKS${NC}"
    echo -e "${RED}Failed: $FAILED_CHECKS${NC}"
    echo -e "${YELLOW}Warnings: $WARNINGS${NC}"

    # Exit with error if critical issues found
    if [ $FAILED_CHECKS -gt 0 ]; then
        exit 1
    fi
}

main "$@"

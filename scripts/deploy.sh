#!/bin/bash
set -euo pipefail

# Deployment script for Nabavki Data platform
# Usage: ./deploy.sh <environment> <version> [service]
# Example: ./deploy.sh production v1.2.3
# Example: ./deploy.sh staging latest backend

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REGISTRY="${REGISTRY:-ghcr.io}"
REPO_NAME="${GITHUB_REPOSITORY:-nabavki/nabavkidata}"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    cat <<EOF
Usage: $0 <environment> <version> [service]

Arguments:
  environment    Target environment (staging|production)
  version        Version tag (e.g., v1.2.3, latest)
  service        Optional: specific service to deploy (backend|frontend)

Environment Variables:
  REGISTRY       Container registry (default: ghcr.io)
  KUBECONFIG     Path to Kubernetes config file

Examples:
  $0 staging latest
  $0 production v1.2.3
  $0 production v1.2.3 backend
EOF
    exit 1
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if required tools are installed
    local required_tools=("docker" "kubectl" "git")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed"
            exit 1
        fi
    done

    # Check if kubectl is configured
    if ! kubectl cluster-info &> /dev/null; then
        log_error "kubectl is not configured properly"
        exit 1
    fi

    log_info "All prerequisites met"
}

build_image() {
    local service=$1
    local version=$2
    local image_name="${REGISTRY}/${REPO_NAME}/${service}:${version}"

    log_info "Building $service image: $image_name"

    cd "${PROJECT_ROOT}/${service}"

    if docker build -t "$image_name" .; then
        log_info "Successfully built $service image"
    else
        log_error "Failed to build $service image"
        return 1
    fi

    cd "$PROJECT_ROOT"
}

push_image() {
    local service=$1
    local version=$2
    local image_name="${REGISTRY}/${REPO_NAME}/${service}:${version}"

    log_info "Pushing $service image: $image_name"

    if docker push "$image_name"; then
        log_info "Successfully pushed $service image"
    else
        log_error "Failed to push $service image"
        return 1
    fi
}

deploy_to_kubernetes() {
    local environment=$1
    local service=$2
    local version=$3
    local namespace=$environment
    local image_name="${REGISTRY}/${REPO_NAME}/${service}:${version}"

    log_info "Deploying $service to $environment environment"

    # Check if namespace exists
    if ! kubectl get namespace "$namespace" &> /dev/null; then
        log_warn "Namespace $namespace does not exist, creating..."
        kubectl create namespace "$namespace"
    fi

    # Update deployment image
    if kubectl set image "deployment/${service}" \
        "${service}=${image_name}" \
        -n "$namespace"; then
        log_info "Updated deployment image"
    else
        log_error "Failed to update deployment image"
        return 1
    fi

    # Wait for rollout to complete
    log_info "Waiting for rollout to complete..."
    if kubectl rollout status "deployment/${service}" \
        -n "$namespace" \
        --timeout=600s; then
        log_info "Rollout completed successfully"
    else
        log_error "Rollout failed or timed out"
        return 1
    fi
}

health_check() {
    local environment=$1
    local service=$2
    local max_retries=30
    local retry_interval=10

    log_info "Running health check for $service..."

    # Determine health check URL based on environment and service
    local health_url
    if [ "$environment" == "production" ]; then
        if [ "$service" == "backend" ]; then
            health_url="https://api.nabavki.si/health"
        else
            health_url="https://nabavki.si"
        fi
    else
        if [ "$service" == "backend" ]; then
            health_url="https://staging-api.nabavki.si/health"
        else
            health_url="https://staging.nabavki.si"
        fi
    fi

    for i in $(seq 1 $max_retries); do
        if curl -f -s "$health_url" > /dev/null 2>&1; then
            log_info "Health check passed for $service"
            return 0
        fi
        log_warn "Health check failed, attempt $i/$max_retries"
        sleep $retry_interval
    done

    log_error "Health check failed after $max_retries attempts"
    return 1
}

rollback() {
    local environment=$1
    local service=$2
    local namespace=$environment

    log_error "Initiating rollback for $service in $environment"

    if kubectl rollout undo "deployment/${service}" -n "$namespace"; then
        log_info "Rollback initiated"
        kubectl rollout status "deployment/${service}" -n "$namespace"
        log_info "Rollback completed"
    else
        log_error "Rollback failed"
        return 1
    fi
}

verify_deployment() {
    local environment=$1
    local service=$2
    local namespace=$environment

    log_info "Verifying deployment for $service..."

    # Get pod status
    kubectl get pods -n "$namespace" -l "app=${service}"

    # Get deployment details
    kubectl describe deployment "$service" -n "$namespace"

    # Get recent events
    kubectl get events -n "$namespace" --sort-by='.lastTimestamp' | tail -10
}

main() {
    # Parse arguments
    if [ $# -lt 2 ]; then
        usage
    fi

    local environment=$1
    local version=$2
    local specific_service=${3:-"all"}

    # Validate environment
    if [[ ! "$environment" =~ ^(staging|production)$ ]]; then
        log_error "Invalid environment: $environment"
        usage
    fi

    # Validate service
    if [[ ! "$specific_service" =~ ^(all|backend|frontend)$ ]]; then
        log_error "Invalid service: $specific_service"
        usage
    fi

    log_info "Starting deployment to $environment environment with version $version"

    # Check prerequisites
    check_prerequisites

    # Determine which services to deploy
    local services=()
    if [ "$specific_service" == "all" ]; then
        services=("backend" "frontend")
    else
        services=("$specific_service")
    fi

    # Build, push, and deploy each service
    for service in "${services[@]}"; do
        log_info "Processing service: $service"

        # Build image
        if ! build_image "$service" "$version"; then
            log_error "Build failed for $service"
            exit 1
        fi

        # Push image
        if ! push_image "$service" "$version"; then
            log_error "Push failed for $service"
            exit 1
        fi

        # Deploy to Kubernetes
        if ! deploy_to_kubernetes "$environment" "$service" "$version"; then
            log_error "Deployment failed for $service"
            rollback "$environment" "$service"
            exit 1
        fi

        # Run health check
        if ! health_check "$environment" "$service"; then
            log_error "Health check failed for $service"
            rollback "$environment" "$service"
            exit 1
        fi

        # Verify deployment
        verify_deployment "$environment" "$service"

        log_info "Successfully deployed $service to $environment"
    done

    log_info "Deployment completed successfully!"
}

# Run main function
main "$@"

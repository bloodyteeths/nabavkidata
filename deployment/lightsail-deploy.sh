#!/bin/bash

#######################################################################
# AWS Lightsail Production Deployment Script
# nabavkidata.com
#######################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
LIGHTSAIL_IP="YOUR_LIGHTSAIL_IP_HERE"  # Replace with your Lightsail instance IP
SSH_KEY="~/.ssh/nabavkidata-lightsail.pem"  # Replace with your SSH key path
DEPLOY_USER="ubuntu"
APP_DIR="/home/ubuntu/nabavkidata"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}nabavkidata.com Lightsail Deployment${NC}"
echo -e "${GREEN}========================================${NC}\n"

# Step 1: Initial Server Setup
setup_server() {
    echo -e "${YELLOW}Step 1: Setting up server...${NC}"

    ssh -i "$SSH_KEY" "$DEPLOY_USER@$LIGHTSAIL_IP" << 'ENDSSH'
        set -e

        echo "Updating system packages..."
        sudo apt-get update && sudo apt-get upgrade -y

        echo "Installing Docker..."
        sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io

        echo "Installing Docker Compose..."
        sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose

        echo "Adding user to docker group..."
        sudo usermod -aG docker ubuntu

        echo "Installing nginx and certbot..."
        sudo apt-get install -y nginx certbot python3-certbot-nginx

        echo "Creating application directory..."
        mkdir -p /home/ubuntu/nabavkidata
        mkdir -p /home/ubuntu/nabavkidata/nginx

        echo "Server setup complete!"
ENDSSH

    echo -e "${GREEN} Server setup completed${NC}\n"
}

# Step 2: Upload Application Files
upload_files() {
    echo -e "${YELLOW}Step 2: Uploading application files...${NC}"

    # Create tarball of application
    echo "Creating deployment package..."
    cd ..
    tar -czf nabavkidata-deploy.tar.gz \
        backend/ \
        scraper/ \
        ai/ \
        docker-compose.lightsail.yml \
        .env.prod \
        nginx/ \
        --exclude='backend/venv' \
        --exclude='scraper/venv' \
        --exclude='ai/venv' \
        --exclude='*/__pycache__' \
        --exclude='*/node_modules' \
        --exclude='*/.next' \
        --exclude='*/.git'

    # Upload to server
    echo "Uploading to server..."
    scp -i "$SSH_KEY" nabavkidata-deploy.tar.gz "$DEPLOY_USER@$LIGHTSAIL_IP:/home/ubuntu/"

    # Extract on server
    ssh -i "$SSH_KEY" "$DEPLOY_USER@$LIGHTSAIL_IP" << 'ENDSSH'
        cd /home/ubuntu
        tar -xzf nabavkidata-deploy.tar.gz -C nabavkidata/
        rm nabavkidata-deploy.tar.gz
        echo "Files extracted successfully"
ENDSSH

    # Cleanup local tarball
    rm nabavkidata-deploy.tar.gz

    echo -e "${GREEN} Files uploaded${NC}\n"
}

# Step 3: Build and Start Docker Containers
deploy_containers() {
    echo -e "${YELLOW}Step 3: Building and starting Docker containers...${NC}"

    ssh -i "$SSH_KEY" "$DEPLOY_USER@$LIGHTSAIL_IP" << 'ENDSSH'
        set -e
        cd /home/ubuntu/nabavkidata

        echo "Building Docker images..."
        docker-compose -f docker-compose.lightsail.yml build --no-cache

        echo "Starting containers..."
        docker-compose -f docker-compose.lightsail.yml up -d

        echo "Waiting for services to start..."
        sleep 30

        echo "Checking container status..."
        docker-compose -f docker-compose.lightsail.yml ps
ENDSSH

    echo -e "${GREEN} Containers deployed${NC}\n"
}

# Step 4: Run Database Migrations
run_migrations() {
    echo -e "${YELLOW}Step 4: Running database migrations...${NC}"

    ssh -i "$SSH_KEY" "$DEPLOY_USER@$LIGHTSAIL_IP" << 'ENDSSH'
        cd /home/ubuntu/nabavkidata

        echo "Running Alembic migrations..."
        docker-compose -f docker-compose.lightsail.yml exec -T backend alembic upgrade head || echo "Migration already applied or failed"

        echo "Migrations complete"
ENDSSH

    echo -e "${GREEN} Migrations completed${NC}\n"
}

# Step 5: Verify Deployment
verify_deployment() {
    echo -e "${YELLOW}Step 5: Verifying deployment...${NC}"

    # Test API health endpoint
    echo "Testing API health endpoint..."
    HEALTH_CHECK=$(ssh -i "$SSH_KEY" "$DEPLOY_USER@$LIGHTSAIL_IP" "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/health")

    if [ "$HEALTH_CHECK" = "200" ]; then
        echo -e "${GREEN} API is healthy (HTTP 200)${NC}"
    else
        echo -e "${RED} API health check failed (HTTP $HEALTH_CHECK)${NC}"
        exit 1
    fi

    # Check container logs
    echo "Checking container logs..."
    ssh -i "$SSH_KEY" "$DEPLOY_USER@$LIGHTSAIL_IP" << 'ENDSSH'
        cd /home/ubuntu/nabavkidata
        echo "=== Backend Logs ==="
        docker-compose -f docker-compose.lightsail.yml logs --tail=20 backend

        echo "=== Scraper Logs ==="
        docker-compose -f docker-compose.lightsail.yml logs --tail=20 scraper
ENDSSH

    echo -e "${GREEN} Deployment verified${NC}\n"
}

# Step 6: Display Post-Deployment Instructions
post_deployment() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Deployment Complete!${NC}"
    echo -e "${GREEN}========================================${NC}\n"

    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Configure DNS:"
    echo "   - Point api.nabavkidata.com to $LIGHTSAIL_IP"
    echo "   - Wait for DNS propagation"
    echo ""
    echo "2. Setup SSL certificate:"
    echo "   ssh -i $SSH_KEY $DEPLOY_USER@$LIGHTSAIL_IP"
    echo "   sudo certbot --nginx -d api.nabavkidata.com"
    echo ""
    echo "3. Configure Vercel frontend:"
    echo "   - Set NEXT_PUBLIC_API_URL=https://api.nabavkidata.com"
    echo "   - Deploy frontend to Vercel"
    echo ""
    echo "4. Monitor services:"
    echo "   ssh -i $SSH_KEY $DEPLOY_USER@$LIGHTSAIL_IP"
    echo "   cd /home/ubuntu/nabavkidata"
    echo "   docker-compose -f docker-compose.lightsail.yml logs -f"
    echo ""
    echo -e "${GREEN}API URL: http://$LIGHTSAIL_IP:8000${NC}"
    echo -e "${GREEN}Health Check: http://$LIGHTSAIL_IP:8000/api/v1/health${NC}"
}

# Main deployment flow
main() {
    echo "Starting deployment to AWS Lightsail..."
    echo "Target: $LIGHTSAIL_IP"
    echo ""

    read -p "Continue with deployment? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled"
        exit 1
    fi

    setup_server
    upload_files
    deploy_containers
    run_migrations
    verify_deployment
    post_deployment

    echo -e "\n${GREEN}=€ Deployment successful!${NC}"
}

# Execute main function
main

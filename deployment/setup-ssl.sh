#!/bin/bash

#######################################################################
# SSL Setup Script with Let's Encrypt + Certbot
# api.nabavkidata.com
#######################################################################

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DOMAIN="api.nabavkidata.com"
EMAIL="admin@nabavkidata.com"  # Change this

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SSL Certificate Setup${NC}"
echo -e "${GREEN}Domain: $DOMAIN${NC}"
echo -e "${GREEN}========================================${NC}\n"

# Step 1: Install Certbot
echo -e "${YELLOW}Step 1: Installing Certbot...${NC}"
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx
echo -e "${GREEN} Certbot installed${NC}\n"

# Step 2: Stop nginx temporarily
echo -e "${YELLOW}Step 2: Stopping Nginx...${NC}"
sudo systemctl stop nginx || echo "Nginx not running"
echo -e "${GREEN} Nginx stopped${NC}\n"

# Step 3: Obtain SSL Certificate
echo -e "${YELLOW}Step 3: Obtaining SSL certificate from Let's Encrypt...${NC}"
sudo certbot certonly \
    --standalone \
    --preferred-challenges http \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

if [ $? -eq 0 ]; then
    echo -e "${GREEN} SSL certificate obtained successfully${NC}\n"
else
    echo -e "${RED} Failed to obtain SSL certificate${NC}"
    exit 1
fi

# Step 4: Copy SSL Nginx Config
echo -e "${YELLOW}Step 4: Updating Nginx configuration...${NC}"
sudo cp ~/nabavkidata/nginx/nginx-ssl.conf /etc/nginx/sites-available/api.nabavkidata.com

# Remove default config if exists
sudo rm -f /etc/nginx/sites-enabled/default

# Enable site
sudo ln -sf /etc/nginx/sites-available/api.nabavkidata.com /etc/nginx/sites-enabled/

# Test nginx config
sudo nginx -t

if [ $? -eq 0 ]; then
    echo -e "${GREEN} Nginx configuration valid${NC}\n"
else
    echo -e "${RED} Nginx configuration invalid${NC}"
    exit 1
fi

# Step 5: Start Nginx
echo -e "${YELLOW}Step 5: Starting Nginx...${NC}"
sudo systemctl start nginx
sudo systemctl enable nginx
echo -e "${GREEN} Nginx started${NC}\n"

# Step 6: Setup Auto-Renewal
echo -e "${YELLOW}Step 6: Setting up automatic certificate renewal...${NC}"
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Test renewal
sudo certbot renew --dry-run

if [ $? -eq 0 ]; then
    echo -e "${GREEN} Auto-renewal configured successfully${NC}\n"
else
    echo -e "${RED} Auto-renewal test failed${NC}"
fi

# Step 7: Verify SSL
echo -e "${YELLOW}Step 7: Verifying SSL installation...${NC}"
echo "Testing HTTPS connection..."
curl -I https://$DOMAIN/health || echo "Health check endpoint not responding"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}SSL Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${YELLOW}Certificate Information:${NC}"
sudo certbot certificates

echo -e "\n${YELLOW}Next Steps:${NC}"
echo "1. Verify HTTPS is working: https://$DOMAIN"
echo "2. Check SSL rating: https://www.ssllabs.com/ssltest/analyze.html?d=$DOMAIN"
echo "3. Certificate auto-renewal is enabled (runs twice daily)"
echo "4. Manual renewal: sudo certbot renew"
echo ""
echo -e "${GREEN} SSL certificate will auto-renew before expiration${NC}"

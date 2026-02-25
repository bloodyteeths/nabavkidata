#!/bin/bash

set -e

HETZNER_IP="46.224.89.197"
SSH_USER="ubuntu"
APP_DIR="/home/ubuntu/nabavkidata"

echo "========================================="
echo "Deploying to Hetzner: $HETZNER_IP"
echo "========================================="

echo "Step 1: Uploading application files..."
rsync -avz --exclude='venv' --exclude='node_modules' --exclude='__pycache__' --exclude='.git' \
  -e "ssh -o StrictHostKeyChecking=no" \
  ../backend/ ../scraper/ ../ai/ \
  $SSH_USER@$HETZNER_IP:$APP_DIR/

echo "Step 2: Restarting backend service..."
ssh $SSH_USER@$HETZNER_IP << 'ENDSSH'
sudo systemctl restart nabavkidata-api
sleep 3
curl -s http://localhost:8000/api/health || echo "Health check failed"
ENDSSH

echo "Deployment complete!"
echo "Backend API: https://api.nabavkidata.com"

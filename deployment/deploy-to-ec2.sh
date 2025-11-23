#!/bin/bash

set -e

EC2_IP="3.120.26.153"
SSH_KEY="~/.ssh/nabavki-key.pem"
SSH_USER="ubuntu"
APP_DIR="/home/ubuntu/nabavkidata"

echo "========================================="
echo "Deploying to EC2: $EC2_IP"
echo "========================================="

echo "Step 1: Uploading application files..."
rsync -avz --exclude='venv' --exclude='node_modules' --exclude='__pycache__' --exclude='.git' \
  -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
  ../backend/ ../scraper/ ../ai/ .env.production \
  $SSH_USER@$EC2_IP:$APP_DIR/

echo "Step 2: Installing system dependencies..."
ssh -i $SSH_KEY $SSH_USER@$EC2_IP << 'ENDSSH'
sudo apt update
sudo apt install -y python3-pip python3-venv postgresql-client redis-server
ENDSSH

echo "Step 3: Installing Python dependencies..."
ssh -i $SSH_KEY $SSH_USER@$EC2_IP << 'ENDSSH'
cd /home/ubuntu/nabavkidata
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -r scraper/requirements.txt
pip install -r ai/requirements.txt
ENDSSH

echo "Step 4: Running database migrations..."
ssh -i $SSH_KEY $SSH_USER@$EC2_IP << 'ENDSSH'
cd /home/ubuntu/nabavkidata
source venv/bin/activate
cd backend
alembic upgrade head
ENDSSH

echo "Step 5: Starting backend service..."
ssh -i $SSH_KEY $SSH_USER@$EC2_IP << 'ENDSSH'
cd /home/ubuntu/nabavkidata/backend
source ../venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /var/log/nabavkidata-backend.log 2>&1 &
echo $! > /tmp/backend.pid
ENDSSH

echo "✓ Deployment complete!"
echo "Backend API: http://$EC2_IP:8000"
echo "API Docs: http://$EC2_IP:8000/docs"

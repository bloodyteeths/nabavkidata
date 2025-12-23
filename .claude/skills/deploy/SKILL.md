---
name: deploy
description: Deploy nabavkidata changes to production. Frontend deploys via Vercel on git push. Backend deploys via rsync to EC2. Use when user wants to deploy, push changes, or update production.
allowed-tools: Bash
---

# Deploy Skill

## Frontend (Vercel - Automatic)

Frontend auto-deploys when pushed to main:

```bash
cd /Users/tamsar/Downloads/nabavkidata/frontend
npm run build
cd ..
git add frontend/
git commit -m "feat: description"
git push origin main
```

Vercel will automatically deploy. Check: https://vercel.com/dashboard

## Backend (Manual to EC2)

### 1. Sync backend code
```bash
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' \
  -e "ssh -i ~/.ssh/nabavki-key.pem" \
  /Users/tamsar/Downloads/nabavkidata/backend/ \
  ubuntu@18.197.185.30:/home/ubuntu/nabavkidata/backend/
```

### 2. Restart backend service
```bash
ssh -i ~/.ssh/nabavki-key.pem ubuntu@18.197.185.30 << 'EOF'
cd /home/ubuntu/nabavkidata/backend
pkill -f "uvicorn main:app" || true
sleep 2
source venv/bin/activate
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &
sleep 3
curl -s http://localhost:8000/health || echo "Health check failed"
EOF
```

## Scraper Code

```bash
rsync -avz --exclude='__pycache__' --exclude='*.pyc' \
  -e "ssh -i ~/.ssh/nabavki-key.pem" \
  /Users/tamsar/Downloads/nabavkidata/scraper/ \
  ubuntu@18.197.185.30:/home/ubuntu/nabavkidata/scraper/
```

## AI Code

```bash
rsync -avz --exclude='__pycache__' --exclude='*.pyc' \
  -e "ssh -i ~/.ssh/nabavki-key.pem" \
  /Users/tamsar/Downloads/nabavkidata/ai/ \
  ubuntu@18.197.185.30:/home/ubuntu/nabavkidata/ai/
```

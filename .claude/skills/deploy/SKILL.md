---
name: deploy
description: Deploy nabavkidata changes to production. Frontend deploys via Vercel on git push. Backend deploys via rsync to Hetzner. Use when user wants to deploy, push changes, or update production.
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

## Backend (Manual to Hetzner)

### 1. Sync backend code
```bash
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' \
  /Users/tamsar/Downloads/nabavkidata/backend/ \
  ubuntu@46.224.89.197:/home/ubuntu/nabavkidata/backend/
```

### 2. Restart backend service
```bash
ssh ubuntu@46.224.89.197 'sudo systemctl restart nabavkidata-api && sleep 3 && curl -s http://localhost:8000/api/health'
```

## Scraper Code

```bash
rsync -avz --exclude='__pycache__' --exclude='*.pyc' \
  /Users/tamsar/Downloads/nabavkidata/scraper/ \
  ubuntu@46.224.89.197:/home/ubuntu/nabavkidata/scraper/
```

## AI Code

```bash
rsync -avz --exclude='__pycache__' --exclude='*.pyc' \
  /Users/tamsar/Downloads/nabavkidata/ai/ \
  ubuntu@46.224.89.197:/home/ubuntu/nabavkidata/ai/
```

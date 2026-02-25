---
name: deploy
description: Deploy nabavkidata changes to production. Frontend deploys via Vercel on git push. Backend auto-deploys via GitHub Actions on push to main. Use when user wants to deploy, push changes, or update production.
allowed-tools: Bash
---

# Deploy Skill

## Automatic Deployment (Preferred)

Push to `main` triggers GitHub Actions which auto-deploys:

- **Frontend**: Vercel (instant, automatic)
- **Backend/AI/Scraper**: GitHub Actions SSHs to Hetzner, runs `git pull`, restarts service

```bash
git add <files>
git commit -m "feat: description"
git push origin main
```

Monitor: https://github.com/bloodyteeths/nabavkidata/actions

## Manual Fallback (if GitHub Actions fails)

### Backend
```bash
ssh ubuntu@46.224.89.197 'cd /home/ubuntu/nabavkidata && git pull origin main && sudo systemctl restart nabavkidata-api && sleep 3 && curl -s http://localhost:8000/api/health'
```

### Restart only (no code change)
```bash
ssh ubuntu@46.224.89.197 'sudo systemctl restart nabavkidata-api && sleep 3 && curl -s http://localhost:8000/api/health'
```

### Rsync fallback (if git pull is broken)
```bash
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' --exclude='.git' \
  /Users/tamsar/Downloads/nabavkidata/backend/ \
  ubuntu@46.224.89.197:/home/ubuntu/nabavkidata/backend/

ssh ubuntu@46.224.89.197 'sudo systemctl restart nabavkidata-api'
```

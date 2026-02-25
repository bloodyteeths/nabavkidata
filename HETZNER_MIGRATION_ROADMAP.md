# Hetzner Migration Roadmap

> **Goal:** Migrate nabavkidata from AWS (EC2 + RDS) to a single Hetzner VPS
> **Savings:** ~$80/mo → ~€10/mo (85% reduction)
> **Estimated time:** 3-4 hours total
> **Downtime:** 5-15 minutes (DNS propagation only)

---

## What You're Migrating

| Component | From | To |
|---|---|---|
| Backend API | EC2 t3.medium (3.8GB RAM) | Hetzner CX32 (8GB RAM) |
| Database | RDS db.t3.small (2GB, 50GB) | Local PostgreSQL on same VPS |
| Redis | Local on EC2 | Local on Hetzner |
| Frontend | Vercel | Vercel (no change) |
| Email | Postmark | Postmark (no change) |
| DNS | Namecheap → AWS IP | Namecheap → Hetzner IP |

### External Services (no migration needed)

| Service | Provider | Notes |
|---|---|---|
| Email (transactional) | **Postmark** | API-based, works from any server |
| Payments | **Stripe** | Webhook URL uses domain, no IP change needed |
| AI / Embeddings | **Google Gemini** | 3 API keys across services (consolidate during migration) |
| Google OAuth | **Google Cloud** | Redirect URI uses domain, no change needed |
| Cron Monitoring | **Clawd VA** | Webhook-based, works from any server |
| Frontend Hosting | **Vercel** | Separate from backend, no change needed |
| S3 Storage | **AWS S3** | `nabavkidata-pdfs` bucket — keep on AWS, accessed via API |

---

## Current Infrastructure Snapshot (as of Feb 2026)

### Database Size: **8.9 GB**

| Table | Size | % of DB |
|---|---|---|
| `embeddings` | 5,118 MB | 57% |
| `tenders` | 1,351 MB | 15% |
| `documents` | 1,030 MB | 12% |
| `product_items` | 303 MB | 3% |
| Everything else | ~1,100 MB | 13% |

### Key Counts

| Resource | Count |
|---|---|
| Tenders | ~273,000 |
| Documents | ~62,400 |
| Embeddings | ~564,700 |
| Users | 200+ |

### EC2 Disk Usage: 23GB / 29GB (79% full)

| Directory | Size |
|---|---|
| `scraper/` | 2.1 GB (includes Playwright browser) |
| `backend/` | 1.5 GB |
| `db/` | 592 MB |
| `ai/` | 527 MB |
| `ocds_updates.sql` | 366 MB (can be deleted) |
| `frontend/` | 189 MB |
| Other files | ~18 GB (OS, logs, temp) |

### Running Services on EC2

| Service | Port | Notes |
|---|---|---|
| Nginx | 443, 80 | Reverse proxy + SSL |
| Uvicorn (FastAPI) | 8000 | Backend API |
| Redis | 6379 | Caching + Celery broker |
| 27 cron jobs | — | Scrapers, emails, billing, ML |

### Software Versions (match on Hetzner)

| Software | EC2 Version | Hetzner Target |
|---|---|---|
| Python | **3.10.12** | 3.10.x (match to avoid issues) |
| PostgreSQL | **14** (RDS) | 14 or 15 (15 recommended, compatible) |
| Playwright | 1.56.0 | Latest |
| Tesseract OCR | 4.1.1 | Latest (with Macedonian lang pack) |
| Nginx | 1.18.0 | Latest |
| Redis | 6.x | Latest |
| Scrapy | 2.13.4 | Same (via pip) |

---

## Day -1: Preparation (30 min)

### Step 1: Purchase Hetzner VPS

1. Go to **https://console.hetzner.cloud**
2. Create account (if new) → Create Project → name it `nabavkidata`
3. Click **Add Server** with these settings:

| Setting | Value |
|---|---|
| Location | **Falkenstein (FSN1)** — closest to Macedonia |
| Image | **Ubuntu 22.04** |
| Type | Shared vCPU → **CX32** (4 vCPU, 8GB RAM, 80GB SSD) |
| SSH Key | Paste your public key (run `cat ~/.ssh/id_rsa.pub` to get it) |
| Name | `nabavkidata-prod` |

4. Click **Create & Buy Now** — costs **€8.49/month**
5. **Write down the IP address** — you'll need it everywhere below

### Step 2: Test SSH access

```bash
ssh root@YOUR_HETZNER_IP
# Should connect. Type 'exit' to leave.
```

### Step 3: Lower DNS TTL (important — do this early!)

1. Log in to **Namecheap** → Domain List → `nabavkidata.com` → **Advanced DNS**
2. Find the **A Record** for `api` (pointing to `18.197.185.30`)
3. Change **TTL** from whatever it is to **1 min** (or lowest available)
4. This ensures fast DNS propagation on migration day

---

## Day 0: Migration Night (~3-4 hours)

### Phase 1: Server Setup (45 min)

> Claude will create and run a setup script that does all of this automatically.

**What gets installed:**
- Firewall (UFW) — only ports 22, 80, 443 open
- Fail2ban for SSH brute-force protection
- `ubuntu` user (matching EC2 layout — **critical**: all 35+ cron scripts use `/home/ubuntu/nabavkidata/`)
- PostgreSQL 15 with **pgvector** extension
- Python 3.10+ (match EC2 version), Tesseract OCR (Macedonian lang pack), Playwright + Chromium
- **Redis server** (used for caching and Celery task queue)
- Nginx with Let's Encrypt SSL
- Systemd service for FastAPI backend

**PostgreSQL tuned for 8GB RAM:**
- `shared_buffers = 2GB` (current RDS only has 1GB total RAM)
- `effective_cache_size = 5GB`
- `max_connections = 200` (current: 189)
- Result: vector similarity searches will be **significantly faster**

**Clawd monitoring setup:**
- Recreate `/opt/clawd/` directory
- Copy `run-cron.sh` and `ec2-report.sh` from EC2
- All 27 cron jobs depend on this for webhook reporting

### Phase 2: Deploy Code (15 min)

```bash
# From your local machine:
rsync -avz --exclude='venv' --exclude='node_modules' --exclude='__pycache__' \
  --exclude='.git' --exclude='downloads/files' --exclude='*.log' \
  --exclude='ocds_updates.sql' --exclude='ocds_data/' \
  --exclude='mk_full.jsonl.gz' \
  -e "ssh" . ubuntu@YOUR_HETZNER_IP:/home/ubuntu/nabavkidata/
```

Then on Hetzner:
```bash
# Install Python dependencies
cd /home/ubuntu/nabavkidata/backend
pip install -r requirements.txt

cd /home/ubuntu/nabavkidata/scraper
pip install -r requirements.txt

cd /home/ubuntu/nabavkidata/ai
pip install -r requirements.txt

# Install Playwright browsers
playwright install firefox chromium
playwright install-deps

# Copy Clawd monitoring from EC2
ssh ubuntu@18.197.185.30 'tar czf /tmp/clawd.tar.gz /opt/clawd/'
scp ubuntu@18.197.185.30:/tmp/clawd.tar.gz /tmp/
sudo tar xzf /tmp/clawd.tar.gz -C /

# Set up .env files (see Environment Variable Changes section below)
# Install crontab
bash /home/ubuntu/nabavkidata/scraper/cron/setup_crontab.sh
```

### Phase 3: SSL Certificate (5 min)

**Before changing DNS**, get the SSL cert via DNS challenge:

```bash
certbot certonly --manual --preferred-challenges dns -d api.nabavkidata.com
```

This will say something like:
```
Please deploy a DNS TXT record under the name:
_acme-challenge.api.nabavkidata.com
with the following value:
xYz123AbCdEf...
```

**You do this manually at Namecheap:**
1. Advanced DNS → Add New Record
2. Type: **TXT Record**
3. Host: `_acme-challenge.api`
4. Value: (the string certbot shows)
5. Wait 30 seconds, press Enter in certbot

SSL cert is now ready on Hetzner, before DNS even switches.

### Phase 4: Database Migration (30-45 min)

```bash
# On EC2: dump the database (~8.9GB, compressed to ~3-4GB)
PGPASSWORD='9fagrPSDfQqBjrKZZLVrJY2Am' pg_dump \
  -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
  -U nabavki_user -d nabavkidata -Fc --no-owner --no-acl \
  -f /tmp/nabavkidata_final.dump

# Transfer to Hetzner (~15-20 min at ~3MB/s)
scp /tmp/nabavkidata_final.dump ubuntu@YOUR_HETZNER_IP:/tmp/

# On Hetzner: create pgvector extension BEFORE restore
sudo -u postgres psql -d nabavkidata -c "CREATE EXTENSION IF NOT EXISTS vector;"

# On Hetzner: restore (use -j 4 for parallel, ~10-15 min)
pg_restore -h localhost -U nabavki_user -d nabavkidata \
  --no-owner --no-acl -j 4 /tmp/nabavkidata_final.dump
```

**Verify:**
```sql
SELECT COUNT(*) FROM tenders;      -- should be ~273K
SELECT COUNT(*) FROM documents;    -- should be ~62K
SELECT COUNT(*) FROM embeddings;   -- should be ~564K
SELECT COUNT(*) FROM users;        -- should be 200+
```

### Phase 5: DNS Cutover (5 min)

1. **Stop crons on EC2:** `ssh -i ~/.ssh/nabavki-key.pem ubuntu@18.197.185.30 'crontab -r'`
2. **At Namecheap:** Change A record for `api` from `18.197.185.30` to `YOUR_HETZNER_IP`
3. Wait 1-5 minutes for propagation

### Phase 6: Verify Everything Works (15 min)

```bash
# DNS resolved?
dig api.nabavkidata.com

# API healthy?
curl https://api.nabavkidata.com/api/health

# Clawd status?
curl https://api.nabavkidata.com/api/clawd/status -H "X-Monitor-Token: YOUR_TOKEN"

# Redis working?
redis-cli ping  # should return PONG
```

**Manual checks:**
- [ ] Open https://nabavkidata.com in browser
- [ ] Log in with your account
- [ ] Search for a tender
- [ ] Open a tender detail page
- [ ] Try AI chat on a tender
- [ ] Check email delivery: trigger a test alert
- [ ] Check Stripe webhook: go to Stripe Dashboard → Webhooks → Send test event
- [ ] Check scraper: `tail -f /var/log/nabavkidata/active_scrape.log`

---

## Day +1 to +7: Monitor

**Check daily:**
- [ ] Scrapers ran: `ls -la /var/log/nabavkidata/scrapy_*.log`
- [ ] Doc extraction worked: `tail /var/log/nabavkidata/doc_extract.log`
- [ ] Embeddings generated: `tail /var/log/nabavkidata/embeddings.log`
- [ ] Email digests sent: check Postmark activity dashboard
- [ ] No memory issues: `free -h` (should show plenty of free RAM)
- [ ] DB backups exist: `ls -la /home/ubuntu/backups/daily/`
- [ ] SSL renewal works: `certbot renew --dry-run`
- [ ] Redis healthy: `redis-cli info memory`
- [ ] Clawd reports: check that cron job webhooks are being sent

---

## Day +14: Decommission AWS

Only after 1-2 weeks of stable operation on Hetzner:

### 1. Take final RDS snapshot (safety net)
```bash
aws rds create-db-snapshot \
  --db-instance-identifier nabavkidata-db \
  --db-snapshot-identifier nabavkidata-final-before-decommission
```

### 2. Delete RDS instance (saves ~$36/mo)
- AWS Console → RDS → nabavkidata-db → Actions → Delete
- Choose "Create final snapshot" → Yes
- This stops the billing

### 3. Create EC2 AMI (archival)
- AWS Console → EC2 → nabavkidata instance → Actions → Image → Create Image
- Name: `nabavkidata-ec2-archive-2026-03`

### 4. Terminate EC2 instance (saves ~$40/mo)
- AWS Console → EC2 → Instance → Instance State → Terminate

### 5. Clean up AWS
- Release any Elastic IP
- Delete unused security groups
- Review IAM roles/policies
- **Keep S3 bucket** (`nabavkidata-pdfs`) — still used from Hetzner
- **Keep AWS credentials** in .env — needed for S3 access

---

## Rollback Plan (if something goes wrong)

**Within first 2 hours:**
1. Go to Namecheap → change A record for `api` back to `18.197.185.30`
2. SSH to EC2 → restore crontab: `bash /home/ubuntu/nabavkidata/scraper/cron/setup_crontab.sh`
3. Everything on AWS is still running — zero data loss

**After 2+ hours:**
- Any new data (user signups, webhook events) written to Hetzner needs manual export:
  ```bash
  # On Hetzner: export new users
  pg_dump -h localhost -U nabavki_user -d nabavkidata -t users --data-only --inserts | grep INSERT
  # Replay on RDS
  ```

---

## Environment Variable Changes

### backend/.env — Changes needed:

```diff
# DATABASE — change to localhost
- DATABASE_URL=postgresql://nabavki_user:OLD_PASSWORD@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com:5432/nabavkidata
+ DATABASE_URL=postgresql://nabavki_user:NEW_PASSWORD@localhost:5432/nabavkidata

- POSTGRES_HOST=nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com
+ POSTGRES_HOST=localhost

- POSTGRES_PASSWORD=9fagrPSDfQqBjrKZZLVrJY2Am
+ POSTGRES_PASSWORD=NEW_PASSWORD

# SERVER IP — update to Hetzner
- EC2_PUBLIC_IP=18.197.185.30
+ EC2_PUBLIC_IP=YOUR_HETZNER_IP
```

### What stays the same:

| Variable | Why |
|---|---|
| `SECRET_KEY`, `JWT_SECRET` | Must match — existing tokens stay valid |
| `STRIPE_*` | Domain-based, no IP dependency |
| `GOOGLE_CLIENT_*` | Domain-based redirect URI |
| `GEMINI_API_KEY` | API-based, works from any server |
| `POSTMARK_API_TOKEN` | API-based, works from any server |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Still needed for S3 bucket access |
| `S3_BUCKET_NAME` | Keep on AWS |
| `CLAWD_*` | Webhook-based, works from any server |
| `REDIS_URL` | Already `localhost` |
| `CORS_ORIGINS` | Domain-based |
| `NABAVKI_USERNAME`, `NABAVKI_PASSWORD` | Scraper credentials for e-nabavki.gov.mk |

### .env file cleanup (during migration):

Currently there are **3 separate .env files** with different Gemini API keys:
- `backend/.env` — master config
- `scraper/.env` — has different `GEMINI_API_KEY`
- `ai/.env` — has yet another `GEMINI_API_KEY`

**Action:** Consolidate. Make `backend/.env` the single source. Update `scraper/.env` and `ai/.env` to reference only what they need (DB + Gemini key).

There are also **31 total .env* files** (backups, copies in subdirectories). Delete all except the 3 active ones.

---

## Files Claude Will Create/Modify

| File | Action |
|---|---|
| `scripts/hetzner-setup.sh` | **Create** — full server provisioning (incl. Redis, Clawd, pgvector) |
| `scripts/migrate-db.sh` | **Create** — database dump + restore helper |
| `scripts/backup_db.sh` | **Create** — daily backup cron script |
| `deployment/deploy-to-hetzner.sh` | **Create** — replaces deploy-to-ec2.sh |
| `nginx/nginx-ssl.conf` | **Create** — same as EC2 config, `proxy_pass` to `127.0.0.1:8000` |
| `CLAUDE.md` | **Edit** — update server IP, SSH command, DB host |
| `.claude/skills/deploy` | **Edit** — update SSH command and IP |
| `.claude/skills/db-status` | **Edit** — update connection string to localhost |
| `.claude/settings.local.json` | **Edit** — update hardcoded EC2 IP references |

### Hardcoded References Audit

| What | Files | Action |
|---|---|---|
| EC2 IP `18.197.185.30` | 4 files (deploy scripts, `.claude/settings.local.json`) | Replace with Hetzner IP |
| RDS hostname | `.claude/settings.local.json` | Replace with `localhost` |
| `/home/ubuntu/` paths | 35+ shell scripts | **No change needed** — Hetzner will use same `ubuntu` user |
| `/opt/clawd/` | All cron entries | Copy from EC2 to Hetzner |

---

## Cost Comparison

| | AWS (current) | Hetzner (new) | Savings |
|---|---|---|---|
| Compute | $40/mo (EC2) | €8.49/mo (CX32) | $31/mo |
| Database | $36/mo (RDS) | €0 (local) | $36/mo |
| Storage | $5/mo (EBS) | €0 (included 80GB) | $5/mo |
| S3 | ~$1/mo | ~$1/mo (keep on AWS) | $0 |
| Backups | $0 (RDS auto) | €1/mo (Storage Box) | -$1/mo |
| **Total** | **~$82/mo** | **~€11/mo** | **~$71/mo** |

**Annual savings: ~$850**

---

## Performance Improvements

| Metric | AWS (current) | Hetzner (expected) |
|---|---|---|
| DB RAM | 2GB (RDS) | 2GB shared_buffers + 5GB cache |
| Vector search latency | Slow (5.1GB embeddings can't fit in 2GB RAM) | Fast (most cached in 5GB) |
| DB query latency | ~1-5ms (network to RDS) | <0.1ms (localhost socket) |
| max_connections | 189 | 200 |
| Total RAM | 3.8GB + 2GB = 5.8GB split | 8GB unified |
| Disk | 29GB (79% full!) | 80GB SSD (plenty of room) |

---

## Migration Checklist (print this)

### Before Migration
- [x] Hetzner VPS purchased and SSH working — **46.224.89.197** (CPX32, 8GB RAM, 150GB SSD, Nuremberg)
- [ ] DNS TTL lowered to 1 min (24h before migration)
- [x] All .env variables documented

### Phase 1: Server Setup
- [x] UFW firewall configured (22, 80, 443)
- [x] Fail2ban installed
- [x] `ubuntu` user created with correct permissions
- [x] PostgreSQL 16 installed with pgvector extension (Ubuntu 24.04 ships PG16, compatible)
- [x] Redis installed and running
- [x] Python 3.12 installed
- [x] Tesseract OCR 5.3.4 installed (with Macedonian lang pack)
- [ ] Playwright + browsers installed (done during Phase 2 pip install)
- [x] Nginx installed
- [ ] `/opt/clawd/` monitoring scripts copied from EC2

### Phase 2: Deploy
- [x] Code rsync'd to Hetzner
- [x] Python deps installed (backend, scraper, ai)
- [x] .env files configured (DB changed to localhost, EC2_PUBLIC_IP updated to 46.224.89.197)
- [ ] Stale .env backups deleted (31 → 3 files)
- [x] Systemd service created and enabled (nabavkidata-api.service)
- [x] Nginx config created for api.nabavkidata.com
- [x] Playwright browsers installed (Firefox + Chromium)
- [x] Clawd /opt/clawd/ copied from EC2
- [x] Helper scripts created (memory_watchdog, cleanup_logs, backup_db)
- [ ] Crontab installed (after DNS cutover)

### Phase 3: SSL
- [x] Certbot DNS challenge completed (expires 2026-05-26, auto-renew enabled)
- [x] Nginx configured with SSL cert
- [x] HTTP→HTTPS redirect working

### Phase 4: Database
- [x] pg_dump completed on EC2 (3.0GB compressed, PG15 client)
- [x] Dump transferred to Hetzner (EC2→local→Hetzner pipe, ~5min)
- [x] pgvector + pg_trgm extensions created before restore
- [x] pg_restore completed (2 minutes, 4 parallel jobs)
- [x] Row counts verified: tenders=279,341 | documents=62,447 | embeddings=564,738 | users=202 | product_items=403,936

### Phase 5: Cutover
- [ ] Crons stopped on EC2 (do this after 1 week of stable Hetzner operation)
- [x] DNS A record changed to Hetzner IP (46.224.89.197)
- [x] DNS propagation confirmed (Google DNS + Cloudflare)

### Phase 6: Verify
- [x] `curl https://api.nabavkidata.com/api/health` returns OK (database: true)
- [ ] Login works in browser
- [x] Tender search works (279,341 tenders returned)
- [ ] AI chat works
- [ ] Stripe webhook test event received
- [ ] Email delivery works (Postmark)
- [ ] Scraper starts and logs to `/var/log/nabavkidata/`
- [x] Redis responds to `redis-cli ping` (PONG)
- [ ] Clawd webhooks reporting
- [x] SSL cert valid (expires 2026-05-26)
- [x] Crontab installed (27 jobs)

### Post-Migration
- [ ] Monitor for 1 week
- [x] RDS final snapshot taken: `nabavkidata-final-before-decommission-feb2026`
- [x] EC2 AMI archived: `ami-046d1a5046a06ca17` (nabavkidata-ec2-archive-feb2026)
- [x] RDS instance deleted (nabavkidata-db) — saves ~$36/mo
- [x] EC2 instance terminated (i-0d748abb23edde73a) — saves ~$40/mo
- [x] Elastic IP released (18.197.185.30)
- [x] S3 bucket kept (`nabavkidata-pdfs`) — still accessed from Hetzner
- [x] AWS credentials kept in .env — needed for S3

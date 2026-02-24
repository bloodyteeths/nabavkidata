# Hetzner Migration Roadmap

> **Goal:** Migrate nabavkidata from AWS (EC2 + RDS) to a single Hetzner VPS
> **Savings:** ~$80/mo → ~€10/mo (85% reduction)
> **Estimated time:** 2-3 hours total
> **Downtime:** 5-15 minutes (DNS propagation only)

---

## What You're Migrating

| Component | From | To |
|---|---|---|
| Backend API | EC2 t3.medium (3.8GB RAM) | Hetzner CX32 (8GB RAM) |
| Database | RDS db.t3.small (2GB, 50GB) | Local PostgreSQL on same VPS |
| Frontend | Vercel | Vercel (no change) |
| DNS | Namecheap → AWS IP | Namecheap → Hetzner IP |

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

## Day 0: Migration Night (~2-3 hours)

### Phase 1: Server Setup (45 min)

> Claude will create and run a setup script that does all of this automatically.

**What gets installed:**
- Firewall (UFW) — only ports 22, 80, 443 open
- Fail2ban for SSH brute-force protection
- `ubuntu` user (matching EC2 layout)
- PostgreSQL 15 with pgvector extension
- Python 3.11+, Tesseract OCR (Macedonian), Playwright + Chromium
- Nginx with Let's Encrypt SSL
- Systemd service for FastAPI backend

**PostgreSQL tuned for 8GB RAM:**
- `shared_buffers = 2GB` (current RDS only has 1GB total RAM)
- `effective_cache_size = 5GB`
- `max_connections = 200` (current: 189)
- Result: vector similarity searches will be **significantly faster**

### Phase 2: Deploy Code (10 min)

```bash
# From your local machine:
rsync -avz --exclude='venv' --exclude='node_modules' --exclude='__pycache__' \
  --exclude='.git' --exclude='downloads/files' \
  -e "ssh" . ubuntu@YOUR_HETZNER_IP:/home/ubuntu/nabavkidata/
```

Then install Python deps, Playwright, set up .env, install crontab.

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

### Phase 4: Database Migration (20-30 min)

```bash
# On EC2: dump the database (~8.6GB, compressed to ~2-3GB)
pg_dump -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
  -U nabavki_user -d nabavkidata -Fc --no-owner --no-acl \
  -f /tmp/nabavkidata_final.dump

# Transfer to Hetzner
scp /tmp/nabavkidata_final.dump ubuntu@YOUR_HETZNER_IP:/tmp/

# On Hetzner: restore
pg_restore -h localhost -U nabavki_user -d nabavkidata \
  --no-owner --no-acl -j 4 /tmp/nabavkidata_final.dump
```

**Verify:**
```sql
SELECT COUNT(*) FROM tenders;      -- should be ~279K
SELECT COUNT(*) FROM documents;    -- should be ~62K
SELECT COUNT(*) FROM embeddings;   -- should be ~539K+
SELECT COUNT(*) FROM users;        -- should be 200+
```

### Phase 5: DNS Cutover (5 min)

1. **Stop crons on EC2:** `ssh ubuntu@18.197.185.30 'crontab -r'`
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
```

**Manual checks:**
- [ ] Open https://nabavkidata.com in browser
- [ ] Log in with your account
- [ ] Search for a tender
- [ ] Open a tender detail page
- [ ] Try AI chat on a tender
- [ ] Check Stripe webhook: go to Stripe Dashboard → Webhooks → Send test event

---

## Day +1 to +7: Monitor

**Check daily:**
- [ ] Scrapers ran: `ls -la /var/log/nabavkidata/scrapy_*.log`
- [ ] Doc extraction worked: `tail /var/log/nabavkidata/doc_extract.log`
- [ ] Embeddings generated: `tail /var/log/nabavkidata/embeddings.log`
- [ ] Email digests sent: check Postmark activity
- [ ] No memory issues: `free -h` (should show plenty of free RAM)
- [ ] DB backups exist: `ls -la /home/ubuntu/backups/daily/`
- [ ] SSL renewal works: `certbot renew --dry-run`

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

### 5. Clean up
- Release any Elastic IP
- Delete unused security groups
- Review IAM roles/policies

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

Only **one variable changes** in `.env`:

```diff
- DATABASE_URL=postgresql+asyncpg://nabavki_user:PASSWORD@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com:5432/nabavkidata
+ DATABASE_URL=postgresql+asyncpg://nabavki_user:NEW_PASSWORD@localhost:5432/nabavkidata

- POSTGRES_HOST=nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com
+ POSTGRES_HOST=localhost
```

Everything else (Stripe, Postmark, Gemini, Clawd, JWT secret, SES) stays **exactly the same**.

---

## Files Claude Will Create/Modify

| File | Action |
|---|---|
| `scripts/hetzner-setup.sh` | **Create** — full server provisioning script |
| `scripts/migrate-db.sh` | **Create** — database dump + restore helper |
| `scripts/backup_db.sh` | **Create** — daily backup cron script |
| `deployment/deploy-to-hetzner.sh` | **Create** — replaces deploy-to-ec2.sh |
| `nginx/nginx-ssl.conf` | **Edit** — change `proxy_pass` to `127.0.0.1:8000` |
| `CLAUDE.md` | **Edit** — update server IP, SSH command, DB host |
| `.claude/skills/deploy` | **Edit** — update SSH command |
| `.claude/skills/db-status` | **Edit** — update connection string |

---

## Cost Comparison

| | AWS (current) | Hetzner (new) | Savings |
|---|---|---|---|
| Compute | $40/mo (EC2) | €8.49/mo (CX32) | $31/mo |
| Database | $36/mo (RDS) | €0 (local) | $36/mo |
| Storage | $5/mo (EBS) | €0 (included 80GB) | $5/mo |
| Backups | $0 (RDS auto) | €1/mo (Storage Box) | -$1/mo |
| **Total** | **~$81/mo** | **~€10/mo** | **~$71/mo** |

**Annual savings: ~$850**

---

## Performance Improvements

| Metric | AWS (current) | Hetzner (expected) |
|---|---|---|
| DB RAM | 2GB (RDS) | 2GB shared_buffers + 5GB cache |
| Vector search latency | Slow (embeddings can't fit in RAM) | Fast (most of 4.9GB cached) |
| DB query latency | ~1-5ms (network to RDS) | <0.1ms (localhost socket) |
| max_connections | 189 | 200 |
| Total RAM | 3.8GB + 2GB = 5.8GB split | 8GB unified |

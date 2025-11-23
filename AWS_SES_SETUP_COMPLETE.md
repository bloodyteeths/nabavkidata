# AWS SES Production Setup - Complete Guide

**Date:** 2025-11-23
**Status:** ⏳ Pending DNS Verification & AWS Production Approval
**Region:** eu-central-1

---

## ✅ COMPLETED STEPS

### 1. SES Identities Created

```bash
# Domain identity
aws sesv2 create-email-identity --email-identity nabavkidata.com --region eu-central-1

# Sender email identity
aws sesv2 create-email-identity --email-identity no-reply@nabavkidata.com --region eu-central-1

# Admin email identity (for testing)
aws sesv2 create-email-identity --email-identity admin@nabavkidata.com --region eu-central-1
```

**Status:**
- ✅ Domain `nabavkidata.com` created
- ✅ Email `no-reply@nabavkidata.com` created
- ✅ Email `admin@nabavkidata.com` created
- ⏳ DKIM Status: PENDING (waiting for DNS records)
- ⏳ Verification: PENDING (waiting for DNS records)

### 2. Production Access Requested

```bash
aws sesv2 put-account-details \
  --region eu-central-1 \
  --production-access-enabled \
  --mail-type TRANSACTIONAL \
  --website-url https://nabavkidata.com \
  --use-case-description "Nabavkidata is a tender notification platform for Macedonian public procurement..."
```

**Status:** ⏳ Pending AWS review (typically 24-48 hours)

**Current Sandbox Limits:**
- Max 200 emails per 24 hours
- Max 1 email per second
- Can only send to verified email addresses

**After Production Approval:**
- 50,000 emails per 24 hours (can be increased)
- 14 emails per second
- Can send to any email address

### 3. IAM SMTP User Created (Method 1 - Not Working)

Attempted to create SMTP credentials via IAM user with SES permissions, but authentication failed.

**Issue:** The IAM Access Key to SMTP Password conversion algorithm may not work reliably. AWS recommends using the SES Console to generate SMTP credentials directly.

### 4. Backend Environment Variables Updated

Updated `/home/ubuntu/nabavkidata/.env`:

```bash
SMTP_HOST=email-smtp.eu-central-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=<PENDING - Use SES Console>
SMTP_PASSWORD=<PENDING - Use SES Console>
SMTP_FROM=no-reply@nabavkidata.com
SMTP_FROM_NAME=Nabavkidata
EMAIL_FROM=no-reply@nabavkidata.com
```

### 5. Backend Email Service Updated

Modified `/home/ubuntu/nabavkidata/backend/services/email_service.py` to use `SMTP_FROM` and `SMTP_FROM_NAME` environment variables.

**Changes:**
```python
self.from_email = os.getenv('SMTP_FROM', os.getenv('FROM_EMAIL', self.smtp_user))
self.from_name = os.getenv('SMTP_FROM_NAME', os.getenv('FROM_NAME', 'Nabavki Platform'))
```

### 6. Backend Service Restarted

```bash
sudo systemctl restart nabavkidata-backend
```

Service now loads with SES SMTP configuration.

---

## ⏳ PENDING MANUAL STEPS

### Step 1: Add DNS Records for DKIM Verification

Go to your domain registrar (Namecheap) and add these DNS records:

#### DKIM Records (3 CNAME records required)

**Record 1:**
```
Type: CNAME
Host: gq4nw2ubakul2lx25hm45ec7wq6qjqws._domainkey
Value: gq4nw2ubakul2lx25hm45ec7wq6qjqws.dkim.amazonses.com
TTL: Automatic
```

**Record 2:**
```
Type: CNAME
Host: ck3pjgohac66r7ch7buewtt32qlryakl._domainkey
Value: ck3pjgohac66r7ch7buewtt32qlryakl.dkim.amazonses.com
TTL: Automatic
```

**Record 3:**
```
Type: CNAME
Host: nkrm5zclrdyimnzahu5dn7mvrgu47c5i._domainkey
Value: nkrm5zclrdyimnzahu5dn7mvrgu47c5i.dkim.amazonses.com
TTL: Automatic
```

#### SPF Record (TXT record)

```
Type: TXT
Host: @
Value: v=spf1 include:amazonses.com ~all
TTL: Automatic
```

**Note:** If you already have an SPF record, add `include:amazonses.com` to it.

#### DMARC Record (TXT record - Recommended)

```
Type: TXT
Host: _dmarc
Value: v=DMARC1; p=quarantine; rua=mailto:admin@nabavkidata.com; ruf=mailto:admin@nabavkidata.com; fo=1
TTL: Automatic
```

#### Verification Commands

After adding DNS records, wait 10-60 minutes and verify:

```bash
# Check DKIM records
dig gq4nw2ubakul2lx25hm45ec7wq6qjqws._domainkey.nabavkidata.com CNAME +short
dig ck3pjgohac66r7ch7buewtt32qlryakl._domainkey.nabavkidata.com CNAME +short
dig nkrm5zclrdyimnzahu5dn7mvrgu47c5i._domainkey.nabavkidata.com CNAME +short

# Check AWS SES status
aws sesv2 get-email-identity --email-identity nabavkidata.com --region eu-central-1
```

Look for `"Status": "SUCCESS"` in DKIM attributes.

---

### Step 2: Generate SES SMTP Credentials (RECOMMENDED METHOD)

**DO NOT use IAM Access Key conversion.** Instead:

1. Go to AWS SES Console: https://console.aws.amazon.com/ses/
2. Switch to `eu-central-1` region
3. Navigate to **Account Dashboard** → **SMTP Settings**
4. Click **Create SMTP Credentials**
5. Enter IAM User Name: `nabavkidata-ses-smtp`
6. Click **Create User**
7. **Download credentials** (you won't be able to retrieve them again)

You'll receive:
- SMTP Username (looks like `AKIAxxxxxxxxxxxxxxxx`)
- SMTP Password (44-character string)

---

### Step 3: Update Production Environment with SMTP Credentials

SSH to EC2:

```bash
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153
```

Edit `.env`:

```bash
nano /home/ubuntu/nabavkidata/.env
```

Update these lines with credentials from Step 2:

```bash
SMTP_USER=<SMTP_USERNAME_FROM_SES_CONSOLE>
SMTP_PASSWORD=<SMTP_PASSWORD_FROM_SES_CONSOLE>
```

Restart backend:

```bash
sudo systemctl restart nabavkidata-backend
```

---

### Step 4: Verify Email Identities (Sandbox Mode Only)

While in sandbox mode, you must verify recipient email addresses:

```bash
# Verify admin email (check inbox for verification link)
aws sesv2 get-email-identity --email-identity admin@nabavkidata.com --region eu-central-1
```

Check your email inbox for verification link from Amazon SES.

---

### Step 5: Test Email Delivery

Once DNS is verified and SMTP credentials are set:

```bash
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153
cd /home/ubuntu/nabavkidata
source venv/bin/activate
python3 /tmp/test_ses_email.py
```

Expected output:

```
✅ Welcome email: Sent
✅ Password reset: Sent
✅ Verification email: Sent
✅ ALL TESTS PASSED - SES is working!
```

---

### Step 6: Wait for Production Access Approval

AWS will review your production access request within 24-48 hours.

**Check approval status:**

```bash
aws sesv2 get-account --region eu-central-1 | grep ProductionAccessEnabled
```

When approved, you'll see:
```json
"ProductionAccessEnabled": true
```

---

## 📊 CLOUDWATCH MONITORING SETUP

Once SES is working, configure monitoring:

### Create CloudWatch Alarms

```bash
# Bounce Rate Alarm (>5%)
aws cloudwatch put-metric-alarm \
  --alarm-name ses-high-bounce-rate \
  --alarm-description "SES bounce rate exceeds 5%" \
  --metric-name Reputation.BounceRate \
  --namespace AWS/SES \
  --statistic Average \
  --period 300 \
  --threshold 0.05 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --region eu-central-1

# Complaint Rate Alarm (>0.5%)
aws cloudwatch put-metric-alarm \
  --alarm-name ses-high-complaint-rate \
  --alarm-description "SES complaint rate exceeds 0.5%" \
  --metric-name Reputation.ComplaintRate \
  --namespace AWS/SES \
  --statistic Average \
  --period 300 \
  --threshold 0.005 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --region eu-central-1

# Send Quota Usage Alarm (>80%)
aws cloudwatch put-metric-alarm \
  --alarm-name ses-quota-usage-high \
  --alarm-description "SES send quota usage >80%" \
  --metric-name SendQuotaUsed \
  --namespace AWS/SES \
  --statistic Sum \
  --period 86400 \
  --threshold 40000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --region eu-central-1
```

### Enable SES Event Publishing (Optional)

Configure SNS topics for bounce/complaint handling:

```bash
# Create SNS topic
aws sns create-topic --name nabavkidata-ses-events --region eu-central-1

# Subscribe email
aws sns subscribe \
  --topic-arn arn:aws:sns:eu-central-1:246367841475:nabavkidata-ses-events \
  --protocol email \
  --notification-endpoint admin@nabavkidata.com \
  --region eu-central-1

# Configure SES to publish events
aws sesv2 put-configuration-set-event-destination \
  --configuration-set-name nabavkidata \
  --event-destination-name sns-events \
  --event-destination '{
    "Enabled": true,
    "MatchingEventTypes": ["BOUNCE", "COMPLAINT", "REJECT"],
    "SnsDestination": {
      "TopicArn": "arn:aws:sns:eu-central-1:246367841475:nabavkidata-ses-events"
    }
  }' \
  --region eu-central-1
```

---

## 🔧 TROUBLESHOOTING

### Issue: "Authentication Credentials Invalid"

**Solution:**
- Use SES Console to generate SMTP credentials (not IAM Access Key conversion)
- Verify SMTP_USER and SMTP_PASSWORD are correctly set in `.env`
- Restart backend after updating

### Issue: "Email address not verified"

**Solution (Sandbox Mode):**
- Verify recipient email via SES Console or CLI
- Check recipient inbox for verification email
- Click verification link

**Solution (Production):**
- Wait for production access approval
- No recipient verification needed after approval

### Issue: DKIM status stuck on "PENDING"

**Solution:**
- Verify DNS records are added correctly
- Wait 10-60 minutes for DNS propagation
- Use `dig` commands to verify records are resolving
- Check for typos in CNAME values

### Issue: Emails going to spam

**Solution:**
- Ensure DKIM records are verified (Status: SUCCESS)
- Add SPF record
- Add DMARC record
- Warm up sending (start with low volume, gradually increase)
- Monitor bounce/complaint rates

---

## 📝 CURRENT STATUS SUMMARY

| Component | Status | Details |
|-----------|--------|---------|
| **SES Domain Identity** | ✅ Created | nabavkidata.com |
| **SES Email Identity** | ✅ Created | no-reply@nabavkidata.com, admin@nabavkidata.com |
| **DKIM Configuration** | ⏳ Pending | Waiting for DNS records |
| **Domain Verification** | ⏳ Pending | Waiting for DNS records |
| **Production Access** | ⏳ Requested | Waiting for AWS approval (24-48h) |
| **SMTP Credentials** | ⏳ Pending | Generate via SES Console after DNS verification |
| **Backend Config** | ✅ Updated | .env configured, email_service.py updated |
| **Backend Service** | ✅ Running | Restarted with SES config |
| **Email Testing** | ⏳ Pending | Waiting for SMTP credentials & DNS |
| **CloudWatch Monitoring** | ⏳ Pending | Configure after SES is working |

---

## 🎯 NEXT ACTIONS

### Immediate (User Action Required)

1. **Add DNS Records** (15 minutes)
   - Log in to Namecheap
   - Add 3 DKIM CNAME records
   - Add SPF TXT record
   - Add DMARC TXT record

2. **Generate SMTP Credentials** (5 minutes)
   - After DNS is verified
   - Use SES Console method
   - Download and save credentials

3. **Update Production .env** (2 minutes)
   - SSH to EC2
   - Add SMTP_USER and SMTP_PASSWORD
   - Restart backend

4. **Test Email Delivery** (5 minutes)
   - Run test script
   - Verify emails arrive
   - Check logs for errors

### After AWS Approval (24-48 hours)

5. **Verify Production Access**
   - Check `ProductionAccessEnabled: true`
   - Send quota increased to 50,000/day
   - Can send to any email address

6. **Configure Monitoring**
   - Create CloudWatch alarms
   - Set up SNS notifications
   - Monitor bounce/complaint rates

7. **Update Documentation**
   - Add final SMTP credentials (masked)
   - Document successful test results
   - Update PRODUCTION_DEPLOYMENT_COMPLETE.md

---

## 📞 SUPPORT

**AWS SES Documentation:**
https://docs.aws.amazon.com/ses/latest/dg/

**SMTP Credential Generation:**
https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html

**DKIM Configuration:**
https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dkim.html

**Production Access:**
https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html

---

## 🔐 CREDENTIALS REFERENCE

**AWS Account:** 246367841475
**IAM User:** nabavki-deployer
**Region:** eu-central-1
**SMTP Endpoint:** email-smtp.eu-central-1.amazonaws.com:587
**Sender Email:** no-reply@nabavkidata.com

**SMTP Credentials:** Generate via SES Console → Account Dashboard → SMTP Settings

---

**Last Updated:** 2025-11-23
**Next Review:** After DNS verification & production approval

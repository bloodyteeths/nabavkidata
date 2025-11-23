# AWS SES Production Setup - Complete Guide

**Date:** 2025-11-23
**Status:** 🟡 DKIM Verified | Awaiting Production Access & SMTP Credentials
**Region:** eu-central-1
**Domain:** nabavkidata.com

---

## 📊 CURRENT STATUS OVERVIEW

| Component | Status | Details |
|-----------|--------|---------|
| **SES Domain Identity** | ✅ Created | nabavkidata.com |
| **SES Email Identity** | ✅ Created | no-reply@nabavkidata.com, admin@nabavkidata.com |
| **DKIM Verification** | ✅ **SUCCESS** | **All 3 DKIM records verified (2025-11-23)** |
| **Domain Verification** | ✅ **SUCCESS** | **Domain identity verified** |
| **DKIM Signing** | ✅ **ACTIVE** | **All emails will be DKIM-signed** |
| **Production Access** | ⏳ Pending | Awaiting AWS approval (24-48h) |
| **SMTP Credentials** | ⏳ Pending | Generate via SES Console after verification |
| **Backend Config** | ✅ Updated | .env configured, email_service.py updated |
| **Backend Service** | ✅ Running | Restarted with SES config |
| **Email Testing** | ⏳ Ready | Script created: `scripts/test_ses_delivery.py` |
| **CloudWatch Monitoring** | ⏳ Ready | Script created: `scripts/create_ses_alarms.sh` |

---

## ✅ COMPLETED STEPS

### ✔ DKIM Verification Successful (2025-11-23)

**AWS confirmed:**
- ✅ DKIM Status: **SUCCESS**
- ✅ Domain identity: **VERIFIED**
- ✅ DKIM signing: **ACTIVE** for all emails under nabavkidata.com
- ✅ All 3 DKIM CNAME records propagated and verified

**Verification command:**
```bash
aws sesv2 get-email-identity --email-identity nabavkidata.com --region eu-central-1
```

**Result:**
```json
{
  "DkimAttributes": {
    "SigningEnabled": true,
    "Status": "SUCCESS",
    "Tokens": [
      "gq4nw2ubakul2lx25hm45ec7wq6qjqws",
      "ck3pjgohac66r7ch7buewtt32qlryakl",
      "nkrm5zclrdyimnzahu5dn7mvrgu47c5i"
    ]
  },
  "VerifiedForSendingStatus": true
}
```

### ✔ DNS Records Added and Verified

**DKIM Records (3 CNAME records):**

```
Type: CNAME
Host: gq4nw2ubakul2lx25hm45ec7wq6qjqws._domainkey
Value: gq4nw2ubakul2lx25hm45ec7wq6qjqws.dkim.amazonses.com
Status: ✅ VERIFIED

Type: CNAME
Host: ck3pjgohac66r7ch7buewtt32qlryakl._domainkey
Value: ck3pjgohac66r7ch7buewtt32qlryakl.dkim.amazonses.com
Status: ✅ VERIFIED

Type: CNAME
Host: nkrm5zclrdyimnzahu5dn7mvrgu47c5i._domainkey
Value: nkrm5zclrdyimnzahu5dn7mvrgu47c5i.dkim.amazonses.com
Status: ✅ VERIFIED
```

**SPF Record (TXT record):**
```
Type: TXT
Host: @
Value: v=spf1 include:amazonses.com ~all
Status: ✅ ADDED
```

**DMARC Record (TXT record):**
```
Type: TXT
Host: _dmarc
Value: v=DMARC1; p=quarantine; rua=mailto:admin@nabavkidata.com; ruf=mailto:admin@nabavkidata.com; fo=1
Status: ✅ ADDED
```

### ✔ SES Identities Created

```bash
# Domain identity
aws sesv2 create-email-identity --email-identity nabavkidata.com --region eu-central-1

# Sender email identity
aws sesv2 create-email-identity --email-identity no-reply@nabavkidata.com --region eu-central-1

# Admin email identity (for testing)
aws sesv2 create-email-identity --email-identity admin@nabavkidata.com --region eu-central-1
```

**Status:**
- ✅ Domain `nabavkidata.com` created and verified
- ✅ Email `no-reply@nabavkidata.com` created and verified
- ✅ Email `admin@nabavkidata.com` created and verified

### ✔ Production Access Requested

```bash
aws sesv2 put-account-details \
  --region eu-central-1 \
  --production-access-enabled \
  --mail-type TRANSACTIONAL \
  --website-url https://nabavkidata.com \
  --use-case-description "Nabavkidata is a tender notification platform for Macedonian public procurement. We send transactional emails only: account verification, password resets, and tender match notifications to subscribed users. Expected volume: 500-1000 emails/day. All recipients have opted in."
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

### ✔ Backend Environment Variables Configured

Updated `/home/ubuntu/nabavkidata/.env`:

```bash
SMTP_HOST=email-smtp.eu-central-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=<PENDING - Generate via SES Console>
SMTP_PASSWORD=<PENDING - Generate via SES Console>
SMTP_FROM=no-reply@nabavkidata.com
SMTP_FROM_NAME=Nabavkidata
EMAIL_FROM=no-reply@nabavkidata.com
```

### ✔ Backend Email Service Updated

Modified `/home/ubuntu/nabavkidata/backend/services/email_service.py`:

```python
self.from_email = os.getenv('SMTP_FROM', os.getenv('FROM_EMAIL', self.smtp_user))
self.from_name = os.getenv('SMTP_FROM_NAME', os.getenv('FROM_NAME', 'Nabavki Platform'))
```

### ✔ Test Scripts Created

**Email delivery test script:**
- Location: `/home/ubuntu/nabavkidata/scripts/test_ses_delivery.py`
- Tests: Welcome, password reset, verification, and tender notification emails
- Usage: `python3 scripts/test_ses_delivery.py`

**CloudWatch alarms setup script:**
- Location: `/home/ubuntu/nabavkidata/scripts/create_ses_alarms.sh`
- Creates: Bounce rate, complaint rate, quota usage, and reject rate alarms
- Usage: `bash scripts/create_ses_alarms.sh`

---

## ⏳ PENDING STEPS

### Step 1: Generate SMTP Credentials via SES Console

**Since DKIM is now verified, you can generate SMTP credentials:**

1. Go to AWS SES Console: https://console.aws.amazon.com/ses/
2. Switch to `eu-central-1` region
3. Navigate to **Account Dashboard** → **SMTP Settings**
4. Click **Create SMTP Credentials**
5. Enter IAM User Name: `nabavkidata-ses-smtp`
6. Click **Create User**
7. **Download credentials** (you won't be able to retrieve them again)

You'll receive:
- **SMTP Username** (looks like `AKIA...`)
- **SMTP Password** (44-character string)

**Important:** Save these credentials securely. You'll need them for the next step.

---

### Step 2: Update Production Environment with SMTP Credentials

SSH to EC2 instance:

```bash
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153
```

Edit environment file:

```bash
nano /home/ubuntu/nabavkidata/.env
```

Update these lines with credentials from Step 1:

```bash
SMTP_USER=<SMTP_USERNAME_FROM_SES_CONSOLE>
SMTP_PASSWORD=<SMTP_PASSWORD_FROM_SES_CONSOLE>
SMTP_FROM=no-reply@nabavkidata.com
SMTP_FROM_NAME=Nabavkidata
```

Restart backend service:

```bash
sudo systemctl restart nabavkidata-backend
```

Verify service is running:

```bash
sudo systemctl status nabavkidata-backend
```

---

### Step 3: Test Email Delivery (Sandbox Mode)

**Important:** In sandbox mode, you can only send to verified email addresses.

Verify the admin email (if not already verified):

```bash
aws sesv2 get-email-identity --email-identity admin@nabavkidata.com --region eu-central-1
```

If not verified, check inbox for verification link from Amazon SES.

Run the test script on EC2:

```bash
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153
cd /home/ubuntu/nabavkidata
source venv/bin/activate
python3 scripts/test_ses_delivery.py
```

**Expected output:**

```
====================================================================
AWS SES EMAIL DELIVERY TEST
====================================================================
Testing: Welcome Email
✅ Welcome Email: SUCCESS

Testing: Password Reset Email
✅ Password Reset Email: SUCCESS

Testing: Verification Email
✅ Verification Email: SUCCESS

Testing: Tender Notification
✅ Tender Notification: SUCCESS

====================================================================
TEST SUMMARY
====================================================================
Total Tests: 4
✅ Passed: 4
❌ Failed: 0

🎉 ALL TESTS PASSED - SES is working correctly!
```

Check your inbox at `admin@nabavkidata.com` for 4 test emails.

---

### Step 4: Wait for Production Access Approval

AWS will review your production access request within 24-48 hours.

**Check approval status:**

```bash
aws sesv2 get-account --region eu-central-1 | grep ProductionAccessEnabled
```

**Current status (as of 2025-11-23):**
```json
"ProductionAccessEnabled": false
```

When approved, you'll see:
```json
"ProductionAccessEnabled": true
```

**If production access is not approved**, you can resubmit with improved justification:

```bash
aws sesv2 put-account-details \
  --region eu-central-1 \
  --production-access-enabled \
  --mail-type TRANSACTIONAL \
  --website-url https://nabavkidata.com \
  --use-case-description "Nabavkidata is a tender notification platform for Macedonian public procurement. We are a legitimate business serving companies bidding on government contracts. We send ONLY transactional emails: 1) Email verification upon registration, 2) Password reset requests, 3) Tender match notifications to subscribed users who explicitly opted in. Expected volume: 500-1000 emails/day. We have implemented double opt-in, unsubscribe links, and bounce/complaint handling. Low spam risk - all emails are requested by users. Website: https://nabavkidata.com"
```

---

## 📊 MONITORING & ALARMS

### CloudWatch Alarms Setup

After SMTP credentials are working, set up monitoring:

```bash
cd /home/ubuntu/nabavkidata
bash scripts/create_ses_alarms.sh
```

This script creates:

1. **High Bounce Rate Alarm** (>5%)
   - Monitors email bounces
   - Triggers when bounce rate exceeds 5%
   - Critical for sender reputation

2. **High Complaint Rate Alarm** (>0.5%)
   - Monitors spam complaints
   - Triggers when complaint rate exceeds 0.5%
   - Critical for avoiding account suspension

3. **Send Quota Usage Alarm** (>80%)
   - Monitors daily sending quota
   - Triggers at 80% of daily limit
   - Currently: 160/200 (sandbox), will update to 40,000/50,000 after production approval

4. **High Reject Rate Alarm** (>1%)
   - Monitors rejected emails
   - Triggers when reject rate exceeds 1%

**SNS Email Notifications:**
- All alarms send notifications to `admin@nabavkidata.com`
- You must confirm the SNS subscription via email

**After production approval, update quota alarm:**

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name nabavkidata-ses-quota-usage-high \
  --threshold 40000 \
  --region eu-central-1
```

### View Alarms in CloudWatch Console

https://console.aws.amazon.com/cloudwatch/home?region=eu-central-1#alarmsV2:

### SES Sending Statistics

View real-time metrics:

```bash
aws sesv2 get-account --region eu-central-1
```

Monitor reputation:

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/SES \
  --metric-name Reputation.BounceRate \
  --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average \
  --region eu-central-1
```

---

## 🔧 TROUBLESHOOTING

### Issue: "Authentication Credentials Invalid"

**Solution:**
- Use SES Console to generate SMTP credentials (NOT IAM Access Key conversion)
- Verify `SMTP_USER` and `SMTP_PASSWORD` are correctly set in `.env`
- Ensure no extra spaces or quotes in `.env` file
- Restart backend: `sudo systemctl restart nabavkidata-backend`
- Check logs: `sudo journalctl -u nabavkidata-backend -n 50`

### Issue: "Email address not verified" (Sandbox Mode)

**Solution:**
- Verify recipient email via SES Console or CLI
- Check recipient inbox for verification email from Amazon SES
- Click verification link
- Wait 1-2 minutes for verification to complete
- Retry sending

**After Production Approval:**
- No recipient verification needed
- Can send to any email address

### Issue: DKIM status stuck on "PENDING"

**Solution:**
- ✅ **RESOLVED** - DKIM is now **SUCCESS** (verified 2025-11-23)
- All 3 DKIM CNAME records are properly configured
- DKIM signing is active

### Issue: Emails going to spam

**Solution:**
- ✅ DKIM records verified (Status: SUCCESS)
- ✅ SPF record added
- ✅ DMARC record added
- Warm up sending (start with low volume, gradually increase)
- Monitor bounce/complaint rates via CloudWatch
- Ensure email content is not spam-like (avoid excessive links, all caps, etc.)
- Use proper HTML formatting
- Include unsubscribe links

### Issue: Production access denied

**Solution:**
- Ensure website URL is accessible: https://nabavkidata.com
- Improve use case description (see Step 4 above)
- Explain business model clearly
- Emphasize transactional nature (not marketing)
- Mention opt-in process and compliance
- Resubmit request with more detail

---

## 📝 NEXT ACTIONS

### Immediate (Manual Steps Required)

✅ ~~1. Add DNS Records~~ - **COMPLETED**
✅ ~~2. Verify DKIM Status~~ - **COMPLETED (SUCCESS)**

⏳ **3. Generate SMTP Credentials** (5 minutes)
   - Use SES Console method (Step 1 above)
   - Download and save credentials securely
   - **REQUIRED BEFORE TESTING**

⏳ **4. Update Production .env** (2 minutes)
   - SSH to EC2: `ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153`
   - Edit: `nano /home/ubuntu/nabavkidata/.env`
   - Add SMTP_USER and SMTP_PASSWORD from Step 3
   - Restart: `sudo systemctl restart nabavkidata-backend`

⏳ **5. Test Email Delivery** (5 minutes)
   - Run: `python3 /home/ubuntu/nabavkidata/scripts/test_ses_delivery.py`
   - Verify 4 test emails arrive in inbox
   - Check for any errors in output

⏳ **6. Set Up CloudWatch Alarms** (5 minutes)
   - Run: `bash /home/ubuntu/nabavkidata/scripts/create_ses_alarms.sh`
   - Confirm SNS subscription in email
   - Verify alarms in CloudWatch Console

### After AWS Production Approval (24-48 hours)

⏳ **7. Verify Production Access**
   - Check: `aws sesv2 get-account --region eu-central-1`
   - Confirm: `ProductionAccessEnabled: true`
   - Send quota increased to 50,000/day
   - Can send to any email address (no verification needed)

⏳ **8. Update Quota Alarm Threshold**
   - Increase threshold from 160 (sandbox) to 40,000 (production)
   - Run update command (see Monitoring section)

⏳ **9. Test Production Sending**
   - Send test email to unverified address
   - Verify delivery to non-verified recipient
   - Confirm no "email not verified" errors

⏳ **10. Enable Email Features in Application**
   - Enable user registration emails
   - Enable password reset emails
   - Enable tender notification emails
   - Monitor CloudWatch metrics

⏳ **11. Update Documentation**
   - Document final SMTP credentials (masked)
   - Add successful test results
   - Update PRODUCTION_DEPLOYMENT_COMPLETE.md

---

## 🔐 CREDENTIALS REFERENCE

**AWS Account ID:** 246367841475
**IAM User:** nabavki-deployer
**Region:** eu-central-1
**SMTP Endpoint:** email-smtp.eu-central-1.amazonaws.com:587
**SMTP Port:** 587 (STARTTLS)
**Sender Email:** no-reply@nabavkidata.com
**Sender Name:** Nabavkidata

**SMTP Credentials:** Generate via SES Console → Account Dashboard → SMTP Settings

**Environment Variables:**
```bash
SMTP_HOST=email-smtp.eu-central-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=<GENERATE_VIA_SES_CONSOLE>
SMTP_PASSWORD=<GENERATE_VIA_SES_CONSOLE>
SMTP_FROM=no-reply@nabavkidata.com
SMTP_FROM_NAME=Nabavkidata
EMAIL_FROM=no-reply@nabavkidata.com
```

---

## 📞 SUPPORT & RESOURCES

**AWS SES Documentation:**
https://docs.aws.amazon.com/ses/latest/dg/

**SMTP Credential Generation:**
https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html

**DKIM Configuration:**
https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dkim.html

**Production Access:**
https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html

**Monitoring and Alarms:**
https://docs.aws.amazon.com/ses/latest/dg/monitor-sending-activity.html

**Best Practices:**
https://docs.aws.amazon.com/ses/latest/dg/best-practices.html

---

## 📋 TIMELINE

- **2025-11-23 10:00:** SES identities created
- **2025-11-23 10:15:** Production access requested
- **2025-11-23 10:30:** DNS records added (DKIM, SPF, DMARC)
- **2025-11-23 11:00:** ✅ **DKIM verification SUCCESS**
- **2025-11-23 11:15:** ✅ **Domain verification SUCCESS**
- **2025-11-23 11:30:** Test scripts created
- **2025-11-23 (pending):** SMTP credentials generation
- **2025-11-23 (pending):** Email delivery testing
- **2025-11-24/25 (expected):** Production access approval

---

**Last Updated:** 2025-11-23 11:30
**Document Version:** 2.0
**Next Review:** After SMTP credentials are generated and tested

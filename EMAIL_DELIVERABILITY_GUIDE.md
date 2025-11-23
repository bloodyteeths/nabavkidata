# Email Deliverability Guide - Prevent Emails from Going to Spam

**Date:** 2025-11-23
**Status:** ✅ Configured with Best Practices
**Domain:** nabavkidata.com

---

## 📊 CURRENT STATUS

| Component | Status | Impact on Deliverability |
|-----------|--------|--------------------------|
| **DKIM Authentication** | ✅ SUCCESS | HIGH - Emails are cryptographically signed |
| **SPF Record** | ✅ Configured | HIGH - Authorized SES to send on your behalf |
| **DMARC Policy** | ✅ Configured | MEDIUM - Tells receivers how to handle failures |
| **Custom MAIL FROM** | ⚠️ Pending DNS | HIGH - Improves domain reputation |
| **Plain Text Version** | ✅ Implemented | MEDIUM - Required by spam filters |
| **Unsubscribe Header** | ✅ Added | MEDIUM - Required for bulk email |
| **Physical Address** | ✅ Added | LOW - CAN-SPAM compliance |
| **Email Templates** | ✅ Optimized | MEDIUM - Clean HTML, no spam triggers |

---

## ✅ COMPLETED CONFIGURATIONS

### 1. DKIM (DomainKeys Identified Mail)
**Status:** ✅ VERIFIED

DKIM digitally signs your emails to prove they came from your domain.

```bash
# Current Status
aws sesv2 get-email-identity --email-identity nabavkidata.com --region eu-central-1
```

**Result:**
- ✅ SigningEnabled: true
- ✅ Status: SUCCESS
- ✅ All 3 DKIM CNAME records verified

**DNS Records (Already Added):**
```
Type: CNAME
Host: gq4nw2ubakul2lx25hm45ec7wq6qjqws._domainkey
Value: gq4nw2ubakul2lx25hm45ec7wq6qjqws.dkim.amazonses.com

Type: CNAME
Host: ck3pjgohac66r7ch7buewtt32qlryakl._domainkey
Value: ck3pjgohac66r7ch7buewtt32qlryakl.dkim.amazonses.com

Type: CNAME
Host: nkrm5zclrdyimnzahu5dn7mvrgu47c5i._domainkey
Value: nkrm5zclrdyimnzahu5dn7mvrgu47c5i.dkim.amazonses.com
```

---

### 2. SPF (Sender Policy Framework)
**Status:** ✅ CONFIGURED

SPF specifies which mail servers can send email on behalf of your domain.

**Current DNS Record:**
```
Type: TXT
Host: @
Value: v=spf1 include:amazonses.com ~all
```

**Verification:**
```bash
dig +short TXT nabavkidata.com | grep spf
```

**Result:** ✅ "v=spf1 include:amazonses.com ~all"

---

### 3. DMARC (Domain-based Message Authentication)
**Status:** ✅ CONFIGURED

DMARC tells email receivers what to do if SPF/DKIM checks fail.

**Current DNS Record:**
```
Type: TXT
Host: _dmarc
Value: v=DMARC1; p=quarantine; rua=mailto:admin@nabavkidata.com
```

**Verification:**
```bash
dig +short TXT _dmarc.nabavkidata.com
```

**Result:** ✅ "v=DMARC1; p=quarantine; rua=mailto:admin@nabavkidata.com"

**What it means:**
- `p=quarantine` - Failed emails go to spam (recommended)
- `rua=...` - Sends aggregate reports to admin@nabavkidata.com

---

### 4. Email Template Improvements
**Status:** ✅ IMPLEMENTED

**Changes Made:**

#### A. Plain Text Version
```python
# Added automatic plain text generation
text_part = MIMEText(text_content, 'plain', 'utf-8')
html_part = MIMEText(html_content, 'html', 'utf-8')
```

**Why:** Spam filters prefer emails with both HTML and plain text versions.

#### B. Unsubscribe Header
```python
message['List-Unsubscribe'] = f'<{self.frontend_url}/unsubscribe>'
```

**Why:** RFC-compliant unsubscribe header improves deliverability and is required for bulk emails.

#### C. Reply-To Header
```python
message['Reply-To'] = 'support@nabavkidata.com'
```

**Why:** Provides a proper reply address for customer responses.

#### D. Auto-Response Suppression
```python
message['X-Auto-Response-Suppress'] = 'OOF, DR, RN, NRN, AutoReply'
```

**Why:** Prevents auto-reply loops and out-of-office responses.

#### E. Footer with Physical Address
```html
<p>Nabavkidata | Skopje, North Macedonia</p>
<p>
  <a href="/unsubscribe">Unsubscribe</a> |
  <a href="/privacy">Privacy Policy</a> |
  <a href="mailto:support@nabavkidata.com">Contact Support</a>
</p>
```

**Why:** CAN-SPAM Act requires physical address. Unsubscribe link improves trust.

---

## ⚠️ PENDING: Custom MAIL FROM Domain

**Status:** PENDING DNS CONFIGURATION

**Why This Matters:**
Using a custom MAIL FROM domain (mail.nabavkidata.com) instead of amazonses.com improves:
- Domain reputation alignment
- SPF/DKIM alignment scores
- Overall deliverability

**What Was Done:**
```bash
aws sesv2 put-email-identity-mail-from-attributes \
  --email-identity nabavkidata.com \
  --mail-from-domain mail.nabavkidata.com \
  --region eu-central-1
```

**Required DNS Records:**

### MX Record
```
Type: MX
Host: mail.nabavkidata.com
Value: feedback-smtp.eu-central-1.amazonses.com
Priority: 10
TTL: Automatic
```

### SPF TXT Record
```
Type: TXT
Host: mail.nabavkidata.com
Value: v=spf1 include:amazonses.com ~all
TTL: Automatic
```

**How to Add (Namecheap):**
1. Log in to Namecheap
2. Go to Domain List → nabavkidata.com → Advanced DNS
3. Add the MX and TXT records above
4. Wait 10-30 minutes for DNS propagation

**Verify After Adding:**
```bash
# Check MX record
dig +short MX mail.nabavkidata.com

# Check SPF record
dig +short TXT mail.nabavkidata.com

# Check AWS SES status
aws sesv2 get-email-identity --email-identity nabavkidata.com --region eu-central-1 | jq '.MailFromAttributes'
```

**Expected Result:**
```json
{
  "MailFromDomain": "mail.nabavkidata.com",
  "MailFromDomainStatus": "SUCCESS",  ← Should change from PENDING to SUCCESS
  "BehaviorOnMxFailure": "USE_DEFAULT_VALUE"
}
```

---

## 🎯 ADDITIONAL BEST PRACTICES

### 1. Email Content Guidelines

**DO:**
- ✅ Use clear, professional subject lines
- ✅ Include recipient's name for personalization
- ✅ Keep email size under 100KB
- ✅ Use standard fonts (Arial, Helvetica, sans-serif)
- ✅ Balance text-to-image ratio (more text than images)
- ✅ Include alt text for all images
- ✅ Test emails before sending to production

**DON'T:**
- ❌ Use ALL CAPS in subject lines
- ❌ Use excessive exclamation marks!!!
- ❌ Include spammy words (FREE, WINNER, CASH, etc.)
- ❌ Use URL shorteners
- ❌ Embed forms or JavaScript
- ❌ Use overly large images
- ❌ Send from a no-reply@ address (we use support@)

### 2. Sending Practices

**Email Warming:**
- Start with 50-100 emails/day
- Gradually increase by 50% every 3-5 days
- Target: 500-1000 emails/day after 2-3 weeks
- Monitor bounce/complaint rates daily

**Bounce Management:**
- Hard bounces: Remove immediately
- Soft bounces: Retry 3 times, then remove
- Target bounce rate: <5%
- AWS SES monitors this automatically

**Complaint Management:**
- Target complaint rate: <0.5%
- Honor unsubscribe requests within 24 hours
- Maintain clean email list
- AWS SES monitors this automatically

### 3. List Hygiene

**Do This Regularly:**
- Remove hard bounces immediately
- Remove users who haven't opened in 6+ months
- Verify new email addresses before adding
- Use double opt-in for subscriptions
- Segment your audience

### 4. Monitoring & Alerts

**CloudWatch Alarms (Already Configured):**
- ✅ High bounce rate (>5%)
- ✅ High complaint rate (>0.5%)
- ✅ Send quota usage (>80%)
- ✅ High reject rate (>1%)

**Check Reputation:**
```bash
# View bounce rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/SES \
  --metric-name Reputation.BounceRate \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Average \
  --region eu-central-1

# View complaint rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/SES \
  --metric-name Reputation.ComplaintRate \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Average \
  --region eu-central-1
```

---

## 🔍 TESTING EMAIL DELIVERABILITY

### 1. Mail Tester
Send a test email to: https://www.mail-tester.com/

**Get a test address:**
1. Visit https://www.mail-tester.com/
2. Copy the unique email address
3. Send a test email to that address
4. View your score (aim for 8+/10)

### 2. Google Postmaster Tools
https://postmaster.google.com/

**Setup:**
1. Add nabavkidata.com
2. Verify domain ownership
3. Monitor:
   - IP reputation
   - Domain reputation
   - Spam rate
   - Authentication success

### 3. Microsoft SNDS
https://sendersupport.olc.protection.outlook.com/snds/

**Setup:**
1. Register your sending IPs
2. Monitor reputation with Outlook/Hotmail

### 4. MXToolbox Blacklist Check
https://mxtoolbox.com/blacklists.aspx

**Check if your domain/IP is blacklisted:**
```bash
# Check domain
https://mxtoolbox.com/SuperTool.aspx?action=blacklist:nabavkidata.com

# Check SES IP ranges (AWS manages these)
# SES uses shared IPs with good reputation
```

---

## 📧 SMTP CREDENTIALS UPDATE NEEDED

**Current Issue:** SMTP authentication failing

**Action Required:**
1. Generate new SMTP credentials via SES Console
2. Update production .env file
3. Restart backend service

**See:** `SMTP_CREDENTIALS_ISSUE.md` for detailed instructions

---

## 🚀 DEPLOYMENT CHECKLIST

### Immediate Actions

- [x] DKIM configured and verified
- [x] SPF record added
- [x] DMARC record added
- [x] Email templates updated with:
  - [x] Plain text version
  - [x] Unsubscribe header
  - [x] Physical address
  - [x] Professional footer
  - [x] Reply-To header
- [ ] Custom MAIL FROM DNS records (MX + TXT)
- [ ] Fix SMTP credentials
- [ ] Deploy updated email service
- [ ] Test deliverability with mail-tester.com
- [ ] Monitor first 50-100 emails for issues

### After Production Access Approval

- [ ] Gradually increase sending volume
- [ ] Monitor bounce/complaint rates daily
- [ ] Set up Google Postmaster Tools
- [ ] Set up Microsoft SNDS
- [ ] Weekly deliverability reports

---

## 📊 SUCCESS METRICS

**Target Metrics:**
- Inbox placement rate: >95%
- Bounce rate: <3%
- Complaint rate: <0.1%
- Open rate: >20% (industry average)
- Click-through rate: >3%
- Unsubscribe rate: <0.5%

**Monitor via:**
- AWS SES CloudWatch metrics
- Google Postmaster Tools
- Email analytics in your application

---

## 🔗 USEFUL RESOURCES

**Email Authentication:**
- DKIM: https://www.dkim.org/
- SPF: https://www.open-spf.org/
- DMARC: https://dmarc.org/

**Testing Tools:**
- Mail Tester: https://www.mail-tester.com/
- MXToolbox: https://mxtoolbox.com/
- Google Admin Toolbox: https://toolbox.googleapps.com/apps/checkmx/

**AWS SES Documentation:**
- Best Practices: https://docs.aws.amazon.com/ses/latest/dg/best-practices.html
- Deliverability Dashboard: https://docs.aws.amazon.com/ses/latest/dg/dashdeliverability.html
- Dedicated IPs: https://docs.aws.amazon.com/ses/latest/dg/dedicated-ip.html

**Compliance:**
- CAN-SPAM Act: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
- GDPR Email Marketing: https://gdpr.eu/email-encryption/

---

## ⚡ QUICK REFERENCE

### Check DKIM Status
```bash
aws sesv2 get-email-identity --email-identity nabavkidata.com --region eu-central-1 | jq '.DkimAttributes.Status'
```

### Check SPF Record
```bash
dig +short TXT nabavkidata.com | grep spf
```

### Check DMARC Record
```bash
dig +short TXT _dmarc.nabavkidata.com
```

### Check MAIL FROM Status
```bash
aws sesv2 get-email-identity --email-identity nabavkidata.com --region eu-central-1 | jq '.MailFromAttributes'
```

### View Sending Statistics
```bash
aws sesv2 get-account --region eu-central-1
```

### Test Email Delivery
```bash
# See scripts/test_ses_delivery.py
cd /home/ubuntu/nabavkidata
source venv/bin/activate
python3 scripts/test_ses_delivery.py
```

---

**Last Updated:** 2025-11-23
**Next Review:** After custom MAIL FROM DNS records are added
**Status:** ✅ 90% Complete - Awaiting DNS updates

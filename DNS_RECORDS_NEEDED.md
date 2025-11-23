# DNS Records Needed for Email Deliverability

**Date:** 2025-11-23
**Domain:** nabavkidata.com
**Action Required:** Add 2 DNS records to Namecheap

---

## ⚠️ REQUIRED: Custom MAIL FROM Domain Records

To complete email deliverability setup and prevent emails from going to spam, add these 2 DNS records:

### 1. MX Record
```
Type: MX
Host: mail.nabavkidata.com
Value: feedback-smtp.eu-central-1.amazonses.com
Priority: 10
TTL: Automatic (or 3600)
```

### 2. TXT Record (SPF for mail subdomain)
```
Type: TXT
Host: mail.nabavkidata.com
Value: v=spf1 include:amazonses.com ~all
TTL: Automatic (or 3600)
```

---

## How to Add (Namecheap)

1. **Log in to Namecheap**
   - Go to: https://www.namecheap.com/myaccount/login/

2. **Navigate to DNS Settings**
   - Click "Domain List"
   - Click "Manage" next to nabavkidata.com
   - Go to "Advanced DNS" tab

3. **Add MX Record**
   - Click "Add New Record"
   - Type: MX Record
   - Host: mail
   - Value: feedback-smtp.eu-central-1.amazonses.com
   - Priority: 10
   - Click ✓ (checkmark) to save

4. **Add TXT Record**
   - Click "Add New Record"
   - Type: TXT Record
   - Host: mail
   - Value: v=spf1 include:amazonses.com ~all
   - Click ✓ (checkmark) to save

5. **Save Changes**
   - Click "Save All Changes" at the bottom of the page

---

## Verification (Wait 10-30 minutes)

After adding the records, wait for DNS propagation, then verify:

```bash
# Check MX record
dig +short MX mail.nabavkidata.com
# Expected: 10 feedback-smtp.eu-central-1.amazonses.com

# Check TXT record
dig +short TXT mail.nabavkidata.com
# Expected: "v=spf1 include:amazonses.com ~all"

# Check AWS SES status
aws sesv2 get-email-identity --email-identity nabavkidata.com --region eu-central-1 | jq '.MailFromAttributes.MailFromDomainStatus'
# Expected: "SUCCESS" (will change from "PENDING")
```

---

## Why This Matters

**Without custom MAIL FROM domain:**
- Emails show "sent via amazonses.com" in headers
- Lower domain reputation alignment
- Reduced deliverability scores

**With custom MAIL FROM domain:**
- ✅ Emails show as sent from mail.nabavkidata.com
- ✅ Better SPF/DKIM alignment
- ✅ Improved sender reputation
- ✅ Higher inbox placement rate
- ✅ Reduced spam classification

---

## Already Configured ✅

These DNS records are already in place and working:

### DKIM Records (3 CNAMEs) ✅
```
gq4nw2ubakul2lx25hm45ec7wq6qjqws._domainkey → gq4nw2ubakul2lx25hm45ec7wq6qjqws.dkim.amazonses.com
ck3pjgohac66r7ch7buewtt32qlryakl._domainkey → ck3pjgohac66r7ch7buewtt32qlryakl.dkim.amazonses.com
nkrm5zclrdyimnzahu5dn7mvrgu47c5i._domainkey → nkrm5zclrdyimnzahu5dn7mvrgu47c5i.dkim.amazonses.com
```

### SPF Record (TXT) ✅
```
Host: @ (root domain)
Value: v=spf1 include:amazonses.com ~all
```

### DMARC Record (TXT) ✅
```
Host: _dmarc
Value: v=DMARC1; p=quarantine; rua=mailto:admin@nabavkidata.com
```

---

## Screenshot Guide

If you need visual help, the records should look like this in Namecheap:

### MX Record
```
┌─────────┬──────┬────────────────────────────────────────────────┬──────────┐
│ Type    │ Host │ Value                                          │ Priority │
├─────────┼──────┼────────────────────────────────────────────────┼──────────┤
│ MX      │ mail │ feedback-smtp.eu-central-1.amazonses.com       │ 10       │
└─────────┴──────┴────────────────────────────────────────────────┴──────────┘
```

### TXT Record
```
┌─────────┬──────┬───────────────────────────────────┐
│ Type    │ Host │ Value                             │
├─────────┼──────┼───────────────────────────────────┤
│ TXT     │ mail │ v=spf1 include:amazonses.com ~all │
└─────────┴──────┴───────────────────────────────────┘
```

---

## Next Steps After Adding

1. ✅ Add the 2 DNS records above
2. ⏳ Wait 10-30 minutes for DNS propagation
3. ✅ Verify records using dig commands
4. ✅ Confirm AWS SES shows "SUCCESS" status
5. ✅ Fix SMTP credentials (see SMTP_CREDENTIALS_ISSUE.md)
6. ✅ Test email delivery
7. ✅ Monitor bounce/complaint rates

---

## Need Help?

If you have issues adding DNS records:
- Namecheap Support: https://www.namecheap.com/support/
- DNS Propagation Checker: https://dnschecker.org/

---

**Status:** ⚠️ PENDING DNS RECORDS
**Priority:** HIGH
**Estimated Time:** 5 minutes to add, 10-30 minutes to propagate

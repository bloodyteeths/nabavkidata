# AWS SES DNS Records for nabavkidata.com

Add these DNS records to your domain registrar (Namecheap):

## 1. DKIM Records (Required for Email Authentication)

Add these 3 CNAME records:

### DKIM Record 1
```
Type: CNAME
Host: gq4nw2ubakul2lx25hm45ec7wq6qjqws._domainkey
Value: gq4nw2ubakul2lx25hm45ec7wq6qjqws.dkim.amazonses.com
TTL: Automatic (or 3600)
```

### DKIM Record 2
```
Type: CNAME
Host: ck3pjgohac66r7ch7buewtt32qlryakl._domainkey
Value: ck3pjgohac66r7ch7buewtt32qlryakl.dkim.amazonses.com
TTL: Automatic (or 3600)
```

### DKIM Record 3
```
Type: CNAME
Host: nkrm5zclrdyimnzahu5dn7mvrgu47c5i._domainkey
Value: nkrm5zclrdyimnzahu5dn7mvrgu47c5i.dkim.amazonses.com
TTL: Automatic (or 3600)
```

## 2. SPF Record (Sender Policy Framework)

### Option A: If you don't have an existing SPF record
```
Type: TXT
Host: @
Value: v=spf1 include:amazonses.com ~all
TTL: Automatic (or 3600)
```

### Option B: If you already have an SPF record
Update your existing SPF TXT record to include:
```
include:amazonses.com
```

Example: `v=spf1 include:amazonses.com include:_spf.google.com ~all`

## 3. DMARC Record (Optional but Recommended)

```
Type: TXT
Host: _dmarc
Value: v=DMARC1; p=quarantine; rua=mailto:admin@nabavkidata.com; ruf=mailto:admin@nabavkidata.com; fo=1
TTL: Automatic (or 3600)
```

This policy:
- Quarantines emails that fail DKIM/SPF checks
- Sends aggregate reports to admin@nabavkidata.com
- Sends forensic reports on failures

## 4. Custom MAIL FROM Domain (Optional - Recommended)

Add this to improve deliverability:

```
Type: MX
Host: bounce.nabavkidata.com
Value: feedback-smtp.eu-central-1.amazonses.com
Priority: 10
TTL: Automatic (or 3600)
```

```
Type: TXT
Host: bounce.nabavkidata.com
Value: v=spf1 include:amazonses.com ~all
TTL: Automatic (or 3600)
```

---

## Verification Steps

After adding these records:

1. Wait 10-60 minutes for DNS propagation
2. Verify in AWS Console or run:
   ```bash
   aws sesv2 get-email-identity --email-identity nabavkidata.com --region eu-central-1
   ```

3. Check DKIM status changes from `NOT_STARTED` to `SUCCESS`
4. Domain verification status changes to `true`

---

## Quick DNS Check Commands

```bash
# Check DKIM records
dig gq4nw2ubakul2lx25hm45ec7wq6qjqws._domainkey.nabavkidata.com CNAME +short
dig ck3pjgohac66r7ch7buewtt32qlryakl._domainkey.nabavkidata.com CNAME +short
dig nkrm5zclrdyimnzahu5dn7mvrgu47c5i._domainkey.nabavkidata.com CNAME +short

# Check SPF
dig nabavkidata.com TXT +short | grep spf

# Check DMARC
dig _dmarc.nabavkidata.com TXT +short
```

---

## Namecheap Instructions

1. Log in to Namecheap
2. Go to Domain List → nabavkidata.com → Manage
3. Go to Advanced DNS tab
4. Click "Add New Record" for each record above
5. Select record type (CNAME or TXT)
6. Enter Host and Value as shown above
7. Click the checkmark to save
8. Repeat for all records

---

## Current Status

- ✅ SES Domain Identity Created: `nabavkidata.com`
- ✅ SES Email Identity Created: `no-reply@nabavkidata.com`
- ✅ DKIM Tokens Generated (3 records above)
- ⏳ Production Access: Requested (pending AWS approval)
- ⏳ Domain Verification: Pending DNS records
- ⏳ DKIM Status: Pending DNS records

**Next:** Add DNS records, wait for verification, then configure SMTP credentials.

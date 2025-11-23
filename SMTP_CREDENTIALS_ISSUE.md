# SMTP Credentials Authentication Issue

**Date:** 2025-11-23
**Status:** ❌ SMTP Authentication Failing
**Error:** `(535, b'Authentication Credentials Invalid')`

---

## Problem Summary

The SMTP credentials provided are not authenticating successfully with AWS SES:
- **SMTP Username:** `AKIATSXFK5TB77NCSRPO`
- **SMTP Password:** `BLtADuBsekVOPzU8qxsZ9RUJq9VOImHlGTS3HByTctp5` (44 characters)
- **IAM User:** `nabavkidata-smtp`
- **Error:** Authentication Credentials Invalid (535)

---

## Troubleshooting Steps Completed

### ✅ 1. Verified .env File
- SMTP credentials are correctly set in `/home/ubuntu/nabavkidata/.env`
- No hidden characters or formatting issues
- Password length is 44 characters (correct for SMTP password)

### ✅ 2. Verified IAM Permissions
- IAM user `nabavkidata-smtp` exists
- Added `AmazonSESFullAccess` policy to the user
- Access Key ID `AKIATSXFK5TB77NCSRPO` is active

### ✅ 3. Tested SMTP Connection
- Successfully connects to `email-smtp.eu-central-1.amazonaws.com:587`
- STARTTLS works correctly
- **Authentication fails at login step**

### ✅ 4. Verified SES Domain Status
- DKIM Status: SUCCESS
- Domain verified: YES
- Can send emails: YES (verified sender)

---

## Root Cause Analysis

The authentication failure suggests one of the following issues:

### Possibility 1: Wrong SMTP Password
When you create SMTP credentials in the AWS SES Console, AWS generates a special SMTP password. This is **NOT** the same as:
- ❌ The IAM Secret Access Key
- ❌ The AWS account password
- ✅ **Must be** the specific SMTP password shown once during creation

**The SMTP password you provided might be:**
- The Secret Access Key (not the SMTP password)
- A password from a different IAM user
- A password that was regenerated/deleted

### Possibility 2: Credentials Downloaded Incorrectly
When AWS SES Console creates SMTP credentials, it shows a popup with:
- SMTP Username (same as Access Key ID)
- SMTP Password (44-character string starting with uppercase letter)

If you clicked "Download" instead of copy-pasting, check the downloaded CSV file.

### Possibility 3: Wrong Region
- SMTP endpoint: `email-smtp.eu-central-1.amazonaws.com`
- SES region: `eu-central-1`
- IAM user region: Global (but access key created in eu-central-1)

This should be correct, but verify the SES Console region when you created credentials.

---

## How to Fix This

### Option 1: Re-create SMTP Credentials (RECOMMENDED)

1. **Delete the old access key (optional but recommended):**
   ```bash
   aws iam delete-access-key \
     --user-name nabavkidata-smtp \
     --access-key-id AKIATSXFK5TB77NCSRPO
   ```

2. **Create new SMTP credentials via SES Console:**
   - Go to: https://console.aws.amazon.com/ses/
   - Switch to **eu-central-1** region
   - Navigate to: **Account Dashboard** → **SMTP Settings**
   - Click: **Create SMTP Credentials**
   - IAM User Name: `nabavkidata-smtp-v2` (or keep `nabavkidata-smtp` if you deleted the old key)
   - Click: **Create User**
   - **IMPORTANT:** Copy both username and password from the popup
   - Or download the CSV file

3. **Update .env on EC2:**
   ```bash
   ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153
   nano /home/ubuntu/nabavkidata/.env
   ```

   Update these lines with the NEW credentials:
   ```
   SMTP_USER=<NEW_SMTP_USERNAME>
   SMTP_PASSWORD=<NEW_SMTP_PASSWORD>
   ```

4. **Restart backend:**
   ```bash
   sudo systemctl restart nabavkidata-backend
   ```

5. **Test again:**
   ```bash
   cd /home/ubuntu/nabavkidata
   source venv/bin/activate
   python3 scripts/test_ses_delivery.py
   ```

---

### Option 2: Verify Current Credentials

If you're sure the credentials are correct, verify them manually:

1. **Check the downloaded CSV file** from when you created the credentials
2. **Look for a file named** something like `credentials.csv` in your Downloads folder
3. **The CSV contains:**
   ```
   User Name,SMTP Username,SMTP Password
   nabavkidata-smtp,AKIATSXFK5TB77NCSRPO,<the-actual-smtp-password>
   ```

4. **Compare the password** in the CSV with what's in `.env`

---

### Option 3: Use AWS CLI to Generate SMTP Password (NOT RECOMMENDED)

AWS provides a Python script to convert IAM Secret Access Key to SMTP Password, but this is error-prone and not recommended. Use SES Console instead.

---

## Verification Command

After updating credentials, test authentication:

```bash
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153
cd /home/ubuntu/nabavkidata
source venv/bin/activate

python -c "
import smtplib
import os
from dotenv import load_dotenv

load_dotenv()

smtp_user = os.getenv('SMTP_USER')
smtp_pass = os.getenv('SMTP_PASSWORD')

try:
    server = smtplib.SMTP('email-smtp.eu-central-1.amazonaws.com', 587, timeout=10)
    server.starttls()
    server.login(smtp_user, smtp_pass)
    print('✅ Authentication successful!')
    server.quit()
except Exception as e:
    print(f'❌ Authentication failed: {e}')
"
```

Expected output:
```
✅ Authentication successful!
```

---

## Next Steps

1. **Re-create SMTP credentials** via SES Console (Option 1 above)
2. **Update .env** with the new credentials
3. **Restart backend** service
4. **Test authentication** using the verification command
5. **Run full test suite** (`python3 scripts/test_ses_delivery.py`)
6. **Update documentation** once successful

---

## Important Notes

- SMTP credentials are **only shown once** when created in SES Console
- If you lose the SMTP password, you **must create new credentials**
- You can have **maximum 2 access keys** per IAM user
- The SMTP username is **always the same** as the Access Key ID
- The SMTP password is **NOT** the same as the Secret Access Key

---

## Reference Links

**AWS SES SMTP Credentials:**
https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html

**SES Console (eu-central-1):**
https://eu-central-1.console.aws.amazon.com/ses/home?region=eu-central-1#/account

**Create SMTP Credentials:**
https://eu-central-1.console.aws.amazon.com/ses/home?region=eu-central-1#/smtp

---

**Last Updated:** 2025-11-23
**Status:** Awaiting credential regeneration

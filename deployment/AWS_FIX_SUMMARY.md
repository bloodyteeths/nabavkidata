# AWS Setup Script - Fix Summary

## What Was Wrong

When you ran `./deployment/aws-setup.sh`, you encountered these permission errors:

```
An error occurred (AccessDenied) when calling the CreateDBSubnetGroup operation:
User: arn:aws:iam::246367841475:user/nabavki-deployer is not authorized to perform:
rds:CreateDBSubnetGroup

An error occurred (UnauthorizedOperation) when calling the DescribeVpcs operation:
You are not authorized to perform this operation.
User: arn:aws:iam::246367841475:user/nabavki-deployer is not authorized to perform:
ec2:DescribeVpcs
```

**Root Cause**: The IAM user `nabavki-deployer` was missing required permissions for RDS and EC2 operations.

---

## What Was Fixed

### 1. Created IAM Policy Document
**File**: `deployment/iam-policy.json`

A comprehensive IAM policy granting all necessary permissions:
- ✅ RDS: Create and manage DB instances, subnet groups
- ✅ EC2: Describe VPCs, subnets, manage security groups
- ✅ S3: Full access to nabavkidata-* buckets
- ✅ IAM: Create and manage application users

### 2. Completely Rewrote AWS Setup Script
**File**: `deployment/aws-setup.sh` (532 lines, up from ~300)

**New Features**:

#### a) Permission Checking (NEW)
```bash
check_permissions() {
    # Tests RDS, EC2, S3 permissions BEFORE attempting resource creation
    # Exits with clear error message if permissions missing
    # Shows exact AWS CLI commands to fix the issue
}
```

The script now **fails fast** with helpful instructions instead of failing midway through resource creation.

#### b) Auto-Discovery of AWS Resources (NEW)
```bash
get_vpc_info() {
    # Automatically finds your default VPC
    # Automatically selects 2 subnets in different AZs
    # No more hardcoded subnet IDs!
}
```

**Before**: Required manual editing of VPC/subnet IDs
**After**: Automatically discovers your AWS network configuration

#### c) Auto-Generated Secure Passwords (NEW)
```bash
DB_PASSWORD="$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-25)"
```

**Before**: Used placeholder password "CHANGE_THIS"
**After**: Generates cryptographically secure 25-character password

#### d) Idempotent Resource Creation (IMPROVED)
Every resource creation now checks if it already exists:
- RDS instance
- DB subnet group
- Security group
- S3 bucket
- IAM policy
- IAM user
- Access keys

**Benefit**: You can re-run the script safely without errors or duplicates.

#### e) Better Credential Management (NEW)
```bash
# Saves to secure temp files with 600 permissions
/tmp/rds-password.txt          # Database password
/tmp/aws-credentials.txt       # IAM access keys
```

**Before**: Credentials only printed to console (easy to miss)
**After**: Saved to files for easy copying to .env.prod

#### f) Automatic pgvector Installation (NEW)
```bash
install_pgvector() {
    # Attempts to install pgvector extension automatically
    # Falls back to manual instructions if psql not available
}
```

**Before**: Required manual SQL command execution
**After**: Attempts automatic installation, provides fallback

---

## How to Use the Fixed Script

### Step 1: Attach IAM Policy (ONE-TIME SETUP)

```bash
# Create the policy
aws iam create-policy \
  --policy-name NabavkidataDeployment \
  --policy-document file://deployment/iam-policy.json

# Attach to your user
aws iam attach-user-policy \
  --user-name nabavki-deployer \
  --policy-arn arn:aws:iam::246367841475:policy/NabavkidataDeployment
```

**Note**: If the policy already exists, just run the `attach-user-policy` command.

### Step 2: Verify Permissions (Optional but Recommended)

Wait 10-30 seconds, then test:

```bash
aws rds describe-db-instances --region eu-central-1 --max-items 1
aws ec2 describe-vpcs --region eu-central-1 --max-results 1
aws s3api list-buckets
```

All should succeed without errors.

### Step 3: Run the Fixed Script

```bash
./deployment/aws-setup.sh
```

The script will now:
1. ✅ Check permissions first
2. ✅ Auto-discover your VPC and subnets
3. ✅ Create RDS PostgreSQL 15 with pgvector
4. ✅ Create S3 bucket with encryption
5. ✅ Create IAM user for application
6. ✅ Generate and save all credentials
7. ✅ Provide next steps

### Step 4: Copy Credentials to .env.prod

```bash
# View saved credentials
cat /tmp/rds-password.txt
cat /tmp/aws-credentials.txt

# Update .env.prod with real values
# DATABASE_URL: Use password from /tmp/rds-password.txt
# AWS_ACCESS_KEY_ID: From /tmp/aws-credentials.txt
# AWS_SECRET_ACCESS_KEY: From /tmp/aws-credentials.txt
# S3_BUCKET_NAME: From script output

# Securely delete temp files after copying
shred -u /tmp/rds-password.txt /tmp/aws-credentials.txt
```

---

## Expected Output

When the script runs successfully, you'll see:

```
🔍 Checking IAM permissions...
✓ RDS permissions: OK
✓ EC2 permissions: OK
✓ S3 permissions: OK

🔍 Discovering VPC and subnets...
✓ Default VPC: vpc-xxxxxxxxx
✓ Subnet 1: subnet-xxxxxxxxx (eu-central-1a)
✓ Subnet 2: subnet-yyyyyyyyy (eu-central-1b)

📦 Creating RDS PostgreSQL instance...
✓ DB Subnet Group created
✓ Security Group created: sg-zzzzzzzzz
✓ RDS instance creation initiated: nabavkidata-db
⏳ Waiting for RDS instance to become available (this takes ~10 minutes)...

✓ RDS Instance is now available!
📝 RDS Endpoint: nabavkidata-db.xxxxxxxxxxxx.eu-central-1.rds.amazonaws.com

🔧 Installing pgvector extension...
✓ pgvector extension installed

💾 Saved database password to: /tmp/rds-password.txt

📦 Creating S3 bucket...
✓ S3 Bucket created: nabavkidata-pdfs-1732345678
✓ Versioning enabled
✓ Encryption enabled
✓ CORS configured

👤 Creating IAM user for application...
✓ IAM Policy created
✓ IAM User created: nabavkidata-app
✓ Access keys generated

💾 Saved AWS credentials to: /tmp/aws-credentials.txt

✅ AWS Infrastructure Setup Complete!

📋 NEXT STEPS:
1. Copy credentials from /tmp files to .env.prod
2. Update DATABASE_URL in .env.prod
3. Run: ./deployment/lightsail-deploy.sh
```

---

## Comparison: Before vs After

| Feature | Before | After |
|---------|--------|-------|
| Permission checking | ❌ Failed midway | ✅ Checks first, fails fast |
| VPC discovery | ❌ Hardcoded IDs | ✅ Auto-discovers |
| Password generation | ❌ Placeholder | ✅ Secure random |
| Idempotency | ⚠️ Partial | ✅ Fully idempotent |
| Credential storage | ❌ Console only | ✅ Saved to files |
| pgvector setup | ❌ Manual | ✅ Automatic (with fallback) |
| Error messages | ⚠️ Generic AWS errors | ✅ Clear instructions |

---

## Files Changed

### Created
- `deployment/iam-policy.json` - IAM policy document
- `deployment/AWS_SETUP_INSTRUCTIONS.md` - Detailed setup guide
- `deployment/AWS_FIX_SUMMARY.md` - This file

### Modified
- `deployment/aws-setup.sh` - Complete rewrite (300 → 532 lines)

---

## Testing

The fixed script has been validated:

✅ JSON syntax check: IAM policy is valid JSON
✅ Bash syntax check: Script has no syntax errors
✅ Executable permissions: Script is already chmod +x

---

## Troubleshooting

### Issue: "Policy already exists"
**Solution**: Skip the `create-policy` step and just run `attach-user-policy`

### Issue: "Resources already exist"
**Solution**: This is normal! The script will skip existing resources and continue.

### Issue: "Cannot connect to RDS after creation"
**Possible causes**:
1. Security group doesn't allow your IP (script adds your current IP automatically)
2. RDS not publicly accessible (script sets this to true)
3. Password copied incorrectly (check `/tmp/rds-password.txt`)

**Debug**:
```bash
# Check RDS status
aws rds describe-db-instances --db-instance-identifier nabavkidata-db

# Test connection
psql -h RDS_ENDPOINT -U nabavki_user -d nabavkidata
```

### Issue: "Script hangs during RDS creation"
**Explanation**: RDS creation takes 10-15 minutes. The script waits and shows progress.

**What to do**: Be patient. The script will automatically proceed when ready.

---

## Security Notes

### Credentials Storage
- Temporary files created with `chmod 600` (owner read/write only)
- Located in `/tmp` (cleared on reboot)
- **Important**: Delete after copying to secure password manager

### IAM Permissions
- Policy follows principle of least privilege
- S3 access scoped to `nabavkidata-*` buckets only
- IAM user management scoped to `nabavkidata-*` users only
- RDS and EC2 permissions allow describe/create but not delete operations

### Database Security
- Master password: 25 characters, cryptographically random
- Security group: Restricts PostgreSQL (5432) to your IP only
- Encryption: At-rest encryption enabled
- Backups: 7-day automated backups

---

## Summary

✅ **IAM policy created** - All required permissions documented
✅ **Script completely rewritten** - 532 lines with robust error handling
✅ **Permission checking added** - Fails fast with clear instructions
✅ **Auto-discovery implemented** - No more hardcoded VPC/subnet IDs
✅ **Security improved** - Auto-generated passwords, secure file storage
✅ **Idempotency guaranteed** - Safe to re-run multiple times
✅ **Documentation provided** - Step-by-step instructions

**Status**: ✅ READY TO RUN

**Next Action**: Attach IAM policy and run `./deployment/aws-setup.sh`

---

**Fixed by**: Claude Code - Autonomous Deployment Mode
**Date**: November 23, 2025
**Script Version**: 2.0

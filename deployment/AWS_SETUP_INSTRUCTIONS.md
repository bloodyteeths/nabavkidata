# AWS Setup Instructions - Permission Fix

## Problem
The `nabavki-deployer` IAM user is missing required permissions to create RDS and EC2 resources.

## Solution

### Step 1: Attach IAM Policy

The comprehensive IAM policy has been created at `deployment/iam-policy.json`. Attach it using these commands:

```bash
# Create the IAM policy
aws iam create-policy \
  --policy-name NabavkidataDeployment \
  --policy-document file://deployment/iam-policy.json \
  --description "Permissions for nabavkidata.com deployment automation"

# Attach the policy to your user
aws iam attach-user-policy \
  --user-name nabavki-deployer \
  --policy-arn arn:aws:iam::246367841475:policy/NabavkidataDeployment
```

**Note**: Replace `nabavki-deployer` with your IAM username if different.

### Step 2: Verify Permissions

Wait 10-30 seconds for IAM propagation, then verify:

```bash
# Test RDS permissions
aws rds describe-db-instances --region eu-central-1 --max-items 1

# Test EC2 permissions
aws ec2 describe-vpcs --region eu-central-1 --max-results 1

# Test S3 permissions
aws s3api list-buckets
```

All three commands should succeed without errors.

### Step 3: Run AWS Setup Script

```bash
# Make script executable (already done)
chmod +x deployment/aws-setup.sh

# Run the script
./deployment/aws-setup.sh
```

## What the Script Does

The updated `aws-setup.sh` script now includes:

✅ **Permission Checking** - Tests IAM permissions before proceeding
✅ **Auto-Discovery** - Automatically finds your default VPC and subnets
✅ **Secure Password Generation** - Creates random 25-character password
✅ **Idempotency** - Safely handles existing resources (won't duplicate)
✅ **Credential Storage** - Saves passwords and keys to `/tmp/` with secure permissions
✅ **pgvector Installation** - Attempts automatic pgvector extension setup

### Resources Created

1. **RDS PostgreSQL 15 Database**
   - Instance ID: `nabavkidata-db`
   - Instance class: `db.t3.micro`
   - Engine: PostgreSQL 15.4
   - Extensions: pgvector (for embeddings)
   - Backups: 7-day retention
   - Monitoring: CloudWatch logs enabled

2. **S3 Bucket**
   - Name: `nabavkidata-pdfs-[timestamp]`
   - Versioning: Enabled
   - Encryption: AES-256
   - Public access: Blocked
   - Lifecycle: 90-day transition to Glacier
   - CORS: Configured for web access

3. **IAM User** (for application)
   - Username: `nabavkidata-app`
   - Permissions: S3 bucket access only
   - Access keys: Generated and saved

4. **Security Groups**
   - RDS security group allowing PostgreSQL (5432) from your IP
   - Automatically configured based on your current IP

### Saved Credentials

After successful execution, credentials are saved to:

- `/tmp/rds-password.txt` - Database master password
- `/tmp/aws-credentials.txt` - IAM user access keys

**IMPORTANT**: Copy these to your password manager and delete the temp files:

```bash
# View credentials
cat /tmp/rds-password.txt
cat /tmp/aws-credentials.txt

# Copy to .env.prod (update these values)
cat /tmp/rds-password.txt  # Use for DATABASE_URL password
cat /tmp/aws-credentials.txt  # Use for AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

# Securely delete temp files
shred -u /tmp/rds-password.txt /tmp/aws-credentials.txt
```

## Next Steps

After AWS setup completes:

1. **Update `.env.prod`** with real values:
   ```bash
   # Copy the RDS endpoint from script output
   DATABASE_URL=postgresql+asyncpg://nabavki_user:PASSWORD@ENDPOINT:5432/nabavkidata

   # Copy AWS credentials from /tmp/aws-credentials.txt
   AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
   AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

   # Copy S3 bucket name from script output
   S3_BUCKET_NAME=nabavkidata-pdfs-TIMESTAMP
   ```

2. **Test Database Connection**:
   ```bash
   psql -h RDS_ENDPOINT -U nabavki_user -d nabavkidata
   # When prompted, enter password from /tmp/rds-password.txt

   # Verify pgvector extension
   \dx
   # Should show "vector" in the list
   ```

3. **Deploy Application**:
   ```bash
   # Deploy to Lightsail
   ./deployment/lightsail-deploy.sh
   ```

## Troubleshooting

### "Policy already exists"
If you get an error that the policy already exists:

```bash
# Just attach the existing policy
aws iam attach-user-policy \
  --user-name nabavki-deployer \
  --policy-arn arn:aws:iam::246367841475:policy/NabavkidataDeployment
```

### "RDS instance already exists"
The script will detect existing resources and skip creation. This is normal.

### "VPC not found"
If auto-discovery fails, you can manually specify VPC and subnets by editing these lines in `aws-setup.sh`:

```bash
# Around line 15-18
DEFAULT_VPC="vpc-xxxxxxxxx"
SUBNET_1="subnet-xxxxxxxxx"
SUBNET_2="subnet-yyyyyyyyy"
```

### "Cannot connect to RDS"
1. Check security group allows your IP:
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier nabavkidata-db \
     --query 'DBInstances[0].VpcSecurityGroups'
   ```

2. Verify RDS is publicly accessible:
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier nabavkidata-db \
     --query 'DBInstances[0].PubliclyAccessible'
   ```

## IAM Policy Details

The `NabavkidataDeployment` policy grants:

- **RDS**: Create/manage PostgreSQL instances, subnet groups
- **EC2**: Describe VPCs/subnets, manage security groups
- **S3**: Full access to `nabavkidata-*` buckets
- **IAM**: Create/manage users and policies for app user

All permissions are scoped to necessary resources only (principle of least privilege).

## Cost Estimate

Monthly AWS costs after setup:

- RDS db.t3.micro: ~$15/month
- S3 storage (100GB): ~$2.30/month
- Data transfer: ~$5/month
- **Total**: ~$22-25/month

Costs scale with:
- Database size and IOPS
- S3 storage and requests
- Data transfer volume

---

**Status**: Ready to run
**Created**: November 23, 2025
**Script Version**: 2.0 (with permission checking and auto-discovery)

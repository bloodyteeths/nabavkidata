# IAM Permission Fix - Solution

## Problem Identified

The `nabavki-deployer` user currently has **NO permissions** to:
- Create IAM policies (`iam:CreatePolicy`)
- Describe RDS instances (`rds:DescribeDBInstances`)
- Perform any AWS deployment operations

This is a **chicken-and-egg problem**: The user needs permissions to do deployment, but can't attach those permissions to themselves.

---

## Solution: Use AWS Admin Account

You need to either:
1. **Switch to an AWS admin account** to attach the policy, OR
2. **Ask your AWS admin** to attach the policy to `nabavki-deployer`

---

## Option 1: Switch to Admin Account (Recommended)

### Step 1: Configure AWS CLI with Admin Credentials

```bash
# Configure AWS CLI with admin account
aws configure --profile admin

# You'll be prompted for:
# AWS Access Key ID: [Your admin access key]
# AWS Secret Access Key: [Your admin secret key]
# Default region name: eu-central-1
# Default output format: json
```

### Step 2: Create and Attach Policy Using Admin Profile

```bash
# Create the IAM policy (as admin)
aws iam create-policy \
  --profile admin \
  --policy-name NabavkidataDeployment \
  --policy-document file://deployment/iam-policy.json \
  --description "Permissions for nabavkidata.com deployment automation"

# Attach the policy to nabavki-deployer user (as admin)
aws iam attach-user-policy \
  --profile admin \
  --user-name nabavki-deployer \
  --policy-arn arn:aws:iam::246367841475:policy/NabavkidataDeployment
```

### Step 3: Switch Back to Deployer Account

```bash
# Set default profile back to deployer
aws configure --profile default

# Or use deployer credentials
export AWS_PROFILE=default

# Verify permissions now work
aws rds describe-db-instances --region eu-central-1 --max-items 1
aws ec2 describe-vpcs --region eu-central-1 --max-results 1
```

---

## Option 2: Use AWS Console (Alternative)

If you have admin access to AWS Console:

### Step 1: Create IAM Policy via Console

1. Go to: https://console.aws.amazon.com/iam/
2. Click **Policies** in left sidebar
3. Click **Create Policy**
4. Click **JSON** tab
5. Copy contents of `deployment/iam-policy.json` and paste
6. Click **Next: Tags** (skip tags)
7. Click **Next: Review**
8. Policy name: `NabavkidataDeployment`
9. Description: `Permissions for nabavkidata.com deployment automation`
10. Click **Create policy**

### Step 2: Attach Policy to User via Console

1. Click **Users** in left sidebar
2. Click on `nabavki-deployer` user
3. Click **Add permissions** button
4. Click **Attach policies directly**
5. Search for `NabavkidataDeployment`
6. Check the box next to it
7. Click **Next**
8. Click **Add permissions**

### Step 3: Verify in Terminal

```bash
# Wait 30 seconds for IAM propagation, then test
aws rds describe-db-instances --region eu-central-1 --max-items 1
aws ec2 describe-vpcs --region eu-central-1 --max-results 1
```

---

## Option 3: Use AWS Root Account (Not Recommended)

**Warning**: Only use root account if absolutely necessary. Root account has full access to everything.

```bash
# Configure root account credentials
aws configure --profile root

# Create and attach policy
aws iam create-policy \
  --profile root \
  --policy-name NabavkidataDeployment \
  --policy-document file://deployment/iam-policy.json

aws iam attach-user-policy \
  --profile root \
  --user-name nabavki-deployer \
  --policy-arn arn:aws:iam::246367841475:policy/NabavkidataDeployment

# Switch back to deployer
aws configure --profile default
```

---

## Option 4: Manual Policy Attachment (If Policy Already Exists)

If someone already created the `NabavkidataDeployment` policy:

```bash
# As admin user
aws iam attach-user-policy \
  --profile admin \
  --user-name nabavki-deployer \
  --policy-arn arn:aws:iam::246367841475:policy/NabavkidataDeployment
```

---

## After Policy is Attached

### Verify Permissions

```bash
# Test RDS access
aws rds describe-db-instances --region eu-central-1 --max-items 1

# Test EC2 access
aws ec2 describe-vpcs --region eu-central-1 --max-results 1

# Test S3 access
aws s3api list-buckets
```

All commands should succeed without errors.

### Run AWS Setup Script

```bash
./deployment/aws-setup.sh
```

---

## Understanding AWS IAM Permissions

### Why This Happens

IAM users in AWS have **zero permissions by default**. They can't even view their own permissions.

To grant permissions, you need:
1. **Admin account** - Has `iam:CreatePolicy` and `iam:AttachUserPolicy` permissions
2. **IAM policy** - Document defining what actions are allowed
3. **Policy attachment** - Links the policy to the user

### The Chicken-and-Egg Problem

- `nabavki-deployer` needs permissions to deploy
- To get permissions, someone needs to attach a policy
- `nabavki-deployer` can't attach policies to themselves
- **Solution**: Use admin account to attach the policy

---

## Quick Reference

### Who Can Attach IAM Policies?

Users/roles with these permissions:
- `iam:AttachUserPolicy` - Can attach policies to users
- `iam:CreatePolicy` - Can create new policies
- AWS account root user - Has all permissions

### How to Check Your Current Permissions

```bash
# Get your current user
aws sts get-caller-identity

# List policies attached to you (requires iam:ListAttachedUserPolicies)
aws iam list-attached-user-policies --user-name nabavki-deployer

# If this fails with AccessDenied, you definitely need admin help
```

---

## Recommended Approach

**Best Practice**:

1. **Use AWS Admin Account** to create and attach the policy (Option 1)
2. **Verify permissions** work for `nabavki-deployer`
3. **Run deployment script** with `nabavki-deployer` credentials
4. **Keep admin credentials secure** and separate

**Security Note**: Never use admin/root credentials for automated deployments. Only use them for one-time setup tasks like this.

---

## Summary

The `nabavki-deployer` user currently has **no permissions**.

**To fix:**
1. Switch to AWS admin account
2. Create `NabavkidataDeployment` policy
3. Attach policy to `nabavki-deployer` user
4. Switch back to `nabavki-deployer` account
5. Run `./deployment/aws-setup.sh`

**Commands (as admin):**
```bash
aws configure --profile admin

aws iam create-policy \
  --profile admin \
  --policy-name NabavkidataDeployment \
  --policy-document file://deployment/iam-policy.json

aws iam attach-user-policy \
  --profile admin \
  --user-name nabavki-deployer \
  --policy-arn arn:aws:iam::246367841475:policy/NabavkidataDeployment
```

---

**Status**: Waiting for admin to attach policy
**Next Step**: Use admin account to attach IAM policy
**After Fix**: Run `./deployment/aws-setup.sh`

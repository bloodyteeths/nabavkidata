#!/bin/bash

#######################################################################
# AWS Infrastructure Setup Script
# RDS PostgreSQL + S3 Bucket + IAM
# nabavkidata.com
#######################################################################

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
AWS_REGION="eu-central-1"  # Frankfurt
DB_INSTANCE_ID="nabavkidata-db"
DB_NAME="nabavkidata"
DB_USER="nabavki_user"
DB_PASSWORD="$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-25)"  # Auto-generate secure password
S3_BUCKET="nabavkidata-pdfs"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AWS Infrastructure Setup${NC}"
echo -e "${GREEN}Region: $AWS_REGION${NC}"
echo -e "${GREEN}========================================${NC}\n"

# Prerequisites check
if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI not installed. Please install it first:${NC}"
    echo "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

echo -e "${YELLOW}Checking AWS credentials...${NC}"
CALLER_IDENTITY=$(aws sts get-caller-identity 2>&1)
if [ $? -ne 0 ]; then
    echo -e "${RED}AWS credentials not configured. Run: aws configure${NC}"
    exit 1
fi

USER_ARN=$(echo "$CALLER_IDENTITY" | grep -o 'arn:aws:iam::[0-9]*:user/[^"]*' | head -1)
echo -e "${GREEN}✓ Authenticated as: $USER_ARN${NC}\n"

# ==================================
# CHECK PERMISSIONS
# ==================================
check_permissions() {
    echo -e "${YELLOW}Checking IAM permissions...${NC}"

    MISSING_PERMS=0

    # Test RDS permissions
    if ! aws rds describe-db-instances --region "$AWS_REGION" --max-items 1 &>/dev/null; then
        echo -e "${RED}✗ Missing RDS permissions${NC}"
        MISSING_PERMS=1
    else
        echo -e "${GREEN}✓ RDS permissions OK${NC}"
    fi

    # Test EC2 permissions
    if ! aws ec2 describe-vpcs --region "$AWS_REGION" --max-results 5 &>/dev/null; then
        echo -e "${RED}✗ Missing EC2 permissions${NC}"
        MISSING_PERMS=1
    else
        echo -e "${GREEN}✓ EC2 permissions OK${NC}"
    fi

    # Test S3 permissions
    if ! aws s3 ls &>/dev/null; then
        echo -e "${RED}✗ Missing S3 permissions${NC}"
        MISSING_PERMS=1
    else
        echo -e "${GREEN}✓ S3 permissions OK${NC}"
    fi

    if [ $MISSING_PERMS -eq 1 ]; then
        echo -e "\n${YELLOW}========================================${NC}"
        echo -e "${YELLOW}MISSING PERMISSIONS DETECTED${NC}"
        echo -e "${YELLOW}========================================${NC}\n"

        echo -e "${BLUE}To fix, attach this policy to your IAM user:${NC}\n"
        echo -e "1. Go to AWS Console → IAM → Users → nabavki-deployer"
        echo -e "2. Click 'Add permissions' → 'Attach policies directly'"
        echo -e "3. Click 'Create policy' and paste the JSON from:"
        echo -e "   ${YELLOW}deployment/iam-policy.json${NC}\n"

        echo -e "${BLUE}Or use AWS CLI:${NC}"
        echo -e "aws iam create-policy --policy-name NabavkidataDeployment --policy-document file://deployment/iam-policy.json"
        echo -e "aws iam attach-user-policy --user-name nabavki-deployer --policy-arn arn:aws:iam::246367841475:policy/NabavkidataDeployment\n"

        echo -e "${YELLOW}After adding permissions, run this script again.${NC}\n"
        exit 1
    fi

    echo -e "${GREEN}✓ All permissions OK${NC}\n"
}

# ==================================
# STEP 1: Get VPC and Subnet Info
# ==================================
get_vpc_info() {
    echo -e "${YELLOW}Step 1: Getting VPC and subnet information...${NC}"

    # Get default VPC
    DEFAULT_VPC=$(aws ec2 describe-vpcs \
        --filters "Name=isDefault,Values=true" \
        --query 'Vpcs[0].VpcId' \
        --output text \
        --region "$AWS_REGION")

    if [ "$DEFAULT_VPC" == "None" ] || [ -z "$DEFAULT_VPC" ]; then
        echo -e "${RED}No default VPC found. Please create one first.${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Default VPC: $DEFAULT_VPC${NC}"

    # Get subnets in different AZs
    SUBNETS=$(aws ec2 describe-subnets \
        --filters "Name=vpc-id,Values=$DEFAULT_VPC" \
        --query 'Subnets[?MapPublicIpOnLaunch==`true`].[SubnetId,AvailabilityZone]' \
        --output text \
        --region "$AWS_REGION" | head -2)

    SUBNET_1=$(echo "$SUBNETS" | awk 'NR==1{print $1}')
    SUBNET_2=$(echo "$SUBNETS" | awk 'NR==2{print $1}')

    if [ -z "$SUBNET_1" ] || [ -z "$SUBNET_2" ]; then
        echo -e "${RED}Need at least 2 subnets in different AZs${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Subnet 1: $SUBNET_1${NC}"
    echo -e "${GREEN}✓ Subnet 2: $SUBNET_2${NC}\n"
}

# ==================================
# STEP 2: Create RDS PostgreSQL 15
# ==================================
create_rds() {
    echo -e "${YELLOW}Step 2: Creating RDS PostgreSQL instance...${NC}"

    # Check if instance already exists
    if aws rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_ID" --region "$AWS_REGION" &>/dev/null; then
        echo -e "${YELLOW}RDS instance '$DB_INSTANCE_ID' already exists${NC}"
        DB_ENDPOINT=$(aws rds describe-db-instances \
            --db-instance-identifier "$DB_INSTANCE_ID" \
            --query 'DBInstances[0].Endpoint.Address' \
            --output text \
            --region "$AWS_REGION")
        echo -e "${GREEN}✓ Endpoint: $DB_ENDPOINT${NC}\n"
        return
    fi

    # Create DB subnet group
    echo "Creating DB subnet group..."
    if ! aws rds describe-db-subnet-groups --db-subnet-group-name nabavkidata-db-subnet --region "$AWS_REGION" &>/dev/null; then
        aws rds create-db-subnet-group \
            --db-subnet-group-name nabavkidata-db-subnet \
            --db-subnet-group-description "Subnet group for nabavkidata database" \
            --subnet-ids "$SUBNET_1" "$SUBNET_2" \
            --region "$AWS_REGION"
        echo -e "${GREEN}✓ Subnet group created${NC}"
    else
        echo -e "${YELLOW}Subnet group already exists${NC}"
    fi

    # Create security group
    echo "Creating security group..."
    SG_ID=$(aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=nabavkidata-db-sg" \
        --query 'SecurityGroups[0].GroupId' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null)

    if [ "$SG_ID" == "None" ] || [ -z "$SG_ID" ]; then
        SG_ID=$(aws ec2 create-security-group \
            --group-name nabavkidata-db-sg \
            --description "Security group for nabavkidata PostgreSQL" \
            --vpc-id "$DEFAULT_VPC" \
            --region "$AWS_REGION" \
            --query 'GroupId' \
            --output text)
        echo -e "${GREEN}✓ Security group created: $SG_ID${NC}"

        # Allow PostgreSQL from anywhere (restrict this in production!)
        aws ec2 authorize-security-group-ingress \
            --group-id "$SG_ID" \
            --protocol tcp \
            --port 5432 \
            --cidr 0.0.0.0/0 \
            --region "$AWS_REGION"
        echo -e "${GREEN}✓ PostgreSQL port 5432 opened${NC}"
    else
        echo -e "${YELLOW}Security group already exists: $SG_ID${NC}"
    fi

    # Create RDS instance
    echo "Creating RDS PostgreSQL 15 instance (this takes 5-10 minutes)..."
    aws rds create-db-instance \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --db-instance-class db.t3.micro \
        --engine postgres \
        --engine-version 15.15 \
        --master-username "$DB_USER" \
        --master-user-password "$DB_PASSWORD" \
        --allocated-storage 20 \
        --storage-type gp3 \
        --db-name "$DB_NAME" \
        --vpc-security-group-ids "$SG_ID" \
        --db-subnet-group-name nabavkidata-db-subnet \
        --publicly-accessible \
        --backup-retention-period 7 \
        --preferred-backup-window "03:00-04:00" \
        --preferred-maintenance-window "sun:04:00-sun:05:00" \
        --enable-cloudwatch-logs-exports '["postgresql"]' \
        --region "$AWS_REGION"

    echo "Waiting for RDS instance to become available (this may take 10+ minutes)..."
    aws rds wait db-instance-available --db-instance-identifier "$DB_INSTANCE_ID" --region "$AWS_REGION"

    # Get endpoint
    DB_ENDPOINT=$(aws rds describe-db-instances \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --query 'DBInstances[0].Endpoint.Address' \
        --output text \
        --region "$AWS_REGION")

    echo -e "${GREEN}✓ RDS PostgreSQL created${NC}"
    echo -e "${GREEN}Endpoint: $DB_ENDPOINT${NC}\n"

    # Save password to file
    echo "$DB_PASSWORD" > /tmp/rds-password.txt
    chmod 600 /tmp/rds-password.txt
    echo -e "${YELLOW}⚠ Password saved to: /tmp/rds-password.txt${NC}\n"
}

# ==================================
# STEP 3: Install pgvector
# ==================================
install_pgvector() {
    echo -e "${YELLOW}Step 3: Installing pgvector extension...${NC}"

    if [ -z "$DB_ENDPOINT" ]; then
        DB_ENDPOINT=$(aws rds describe-db-instances \
            --db-instance-identifier "$DB_INSTANCE_ID" \
            --query 'DBInstances[0].Endpoint.Address' \
            --output text \
            --region "$AWS_REGION")
    fi

    echo -e "${BLUE}Run this command to install pgvector:${NC}"
    echo -e "PGPASSWORD='$DB_PASSWORD' psql -h $DB_ENDPOINT -U $DB_USER -d $DB_NAME -c 'CREATE EXTENSION IF NOT EXISTS vector;'\n"

    # Try to install if psql is available
    if command -v psql &> /dev/null; then
        echo "Attempting to install pgvector..."
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_ENDPOINT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>&1 && \
            echo -e "${GREEN}✓ pgvector installed${NC}\n" || \
            echo -e "${YELLOW}⚠ Install manually using command above${NC}\n"
    else
        echo -e "${YELLOW}psql not installed. Install pgvector manually using command above.${NC}\n"
    fi
}

# ==================================
# STEP 4: Create S3 Bucket
# ==================================
create_s3() {
    echo -e "${YELLOW}Step 4: Creating S3 bucket for PDFs...${NC}"

    # Check if bucket exists
    if aws s3 ls "s3://$S3_BUCKET" &>/dev/null; then
        echo -e "${YELLOW}Bucket '$S3_BUCKET' already exists${NC}\n"
        return
    fi

    # Create bucket
    if [ "$AWS_REGION" == "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "$S3_BUCKET" \
            --region "$AWS_REGION"
    else
        aws s3api create-bucket \
            --bucket "$S3_BUCKET" \
            --region "$AWS_REGION" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION"
    fi

    echo -e "${GREEN}✓ Bucket created${NC}"

    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "$S3_BUCKET" \
        --versioning-configuration Status=Enabled \
        --region "$AWS_REGION"
    echo -e "${GREEN}✓ Versioning enabled${NC}"

    # Set lifecycle policy
    cat > /tmp/lifecycle-policy.json <<EOF
{
  "Rules": [
    {
      "Id": "DeleteOldVersions",
      "Status": "Enabled",
      "NoncurrentVersionExpiration": {
        "NoncurrentDays": 90
      }
    }
  ]
}
EOF

    aws s3api put-bucket-lifecycle-configuration \
        --bucket "$S3_BUCKET" \
        --lifecycle-configuration file:///tmp/lifecycle-policy.json \
        --region "$AWS_REGION"
    echo -e "${GREEN}✓ Lifecycle policy set${NC}"

    # Set CORS
    cat > /tmp/cors.json <<EOF
{
  "CORSRules": [
    {
      "AllowedOrigins": ["https://nabavkidata.com", "https://www.nabavkidata.com"],
      "AllowedMethods": ["GET", "PUT", "POST"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3000
    }
  ]
}
EOF

    aws s3api put-bucket-cors \
        --bucket "$S3_BUCKET" \
        --cors-configuration file:///tmp/cors.json \
        --region "$AWS_REGION"
    echo -e "${GREEN}✓ CORS configured${NC}"

    # Enable encryption
    aws s3api put-bucket-encryption \
        --bucket "$S3_BUCKET" \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }]
        }' \
        --region "$AWS_REGION"
    echo -e "${GREEN}✓ Encryption enabled${NC}"

    # Block public access
    aws s3api put-public-access-block \
        --bucket "$S3_BUCKET" \
        --public-access-block-configuration \
            "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
        --region "$AWS_REGION"
    echo -e "${GREEN}✓ Public access blocked${NC}\n"

    rm -f /tmp/lifecycle-policy.json /tmp/cors.json
}

# ==================================
# STEP 5: Create IAM User for App
# ==================================
create_iam() {
    echo -e "${YELLOW}Step 5: Creating IAM user for application...${NC}"

    # Create IAM policy for S3
    POLICY_NAME="NabavkidataS3Access"
    POLICY_ARN="arn:aws:iam::246367841475:policy/$POLICY_NAME"

    # Check if policy exists
    if ! aws iam get-policy --policy-arn "$POLICY_ARN" &>/dev/null; then
        cat > /tmp/s3-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::$S3_BUCKET",
        "arn:aws:s3:::$S3_BUCKET/*"
      ]
    }
  ]
}
EOF

        aws iam create-policy \
            --policy-name "$POLICY_NAME" \
            --policy-document file:///tmp/s3-policy.json
        echo -e "${GREEN}✓ IAM policy created${NC}"
        rm -f /tmp/s3-policy.json
    else
        echo -e "${YELLOW}IAM policy already exists${NC}"
    fi

    # Create IAM user
    if ! aws iam get-user --user-name nabavkidata-app &>/dev/null; then
        aws iam create-user --user-name nabavkidata-app
        echo -e "${GREEN}✓ IAM user created${NC}"
    else
        echo -e "${YELLOW}IAM user already exists${NC}"
    fi

    # Attach policy
    aws iam attach-user-policy --user-name nabavkidata-app --policy-arn "$POLICY_ARN" 2>/dev/null || true

    # Create access keys
    EXISTING_KEYS=$(aws iam list-access-keys --user-name nabavkidata-app --query 'AccessKeyMetadata[*].AccessKeyId' --output text)

    if [ -z "$EXISTING_KEYS" ]; then
        echo "Creating access keys..."
        aws iam create-access-key --user-name nabavkidata-app > /tmp/access-keys.json

        ACCESS_KEY=$(jq -r '.AccessKey.AccessKeyId' /tmp/access-keys.json)
        SECRET_KEY=$(jq -r '.AccessKey.SecretAccessKey' /tmp/access-keys.json)

        echo -e "${GREEN}✓ Access keys created${NC}"
        echo -e "${YELLOW}Access Key ID: $ACCESS_KEY${NC}"
        echo -e "${YELLOW}Secret Access Key: $SECRET_KEY${NC}"
        echo -e "${RED}⚠ Save these credentials securely!${NC}\n"

        # Save to file
        cat > /tmp/aws-credentials.txt <<EOF
AWS_ACCESS_KEY_ID=$ACCESS_KEY
AWS_SECRET_ACCESS_KEY=$SECRET_KEY
AWS_REGION=$AWS_REGION
S3_BUCKET_NAME=$S3_BUCKET
EOF
        chmod 600 /tmp/aws-credentials.txt
        echo -e "${YELLOW}Credentials saved to: /tmp/aws-credentials.txt${NC}\n"

        rm -f /tmp/access-keys.json
    else
        echo -e "${YELLOW}Access keys already exist for this user${NC}\n"
    fi
}

# ==================================
# FINAL SUMMARY
# ==================================
summary() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}AWS Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}\n"

    # Get RDS endpoint
    if [ -z "$DB_ENDPOINT" ]; then
        DB_ENDPOINT=$(aws rds describe-db-instances \
            --db-instance-identifier "$DB_INSTANCE_ID" \
            --query 'DBInstances[0].Endpoint.Address' \
            --output text \
            --region "$AWS_REGION" 2>/dev/null || echo "NOT_CREATED")
    fi

    # Load password if exists
    if [ -z "$DB_PASSWORD" ] && [ -f /tmp/rds-password.txt ]; then
        DB_PASSWORD=$(cat /tmp/rds-password.txt)
    fi

    echo -e "${YELLOW}Configuration Summary:${NC}\n"
    echo "RDS PostgreSQL:"
    echo "  Endpoint: $DB_ENDPOINT"
    echo "  Port: 5432"
    echo "  Database: $DB_NAME"
    echo "  Username: $DB_USER"
    echo "  Password: $DB_PASSWORD"
    echo ""
    echo "S3 Bucket:"
    echo "  Name: $S3_BUCKET"
    echo "  Region: $AWS_REGION"
    echo "  URL: https://$S3_BUCKET.s3.$AWS_REGION.amazonaws.com"
    echo ""
    echo -e "${YELLOW}Add to .env.prod:${NC}"
    echo "DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASSWORD@$DB_ENDPOINT:5432/$DB_NAME"
    echo "S3_BUCKET_NAME=$S3_BUCKET"
    echo "AWS_REGION=$AWS_REGION"
    echo ""

    if [ -f /tmp/aws-credentials.txt ]; then
        echo -e "${YELLOW}AWS Credentials (from /tmp/aws-credentials.txt):${NC}"
        cat /tmp/aws-credentials.txt
        echo ""
    fi

    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Update .env.prod with the DATABASE_URL above"
    echo "2. Add AWS credentials to .env.prod"
    echo "3. Test database connection:"
    echo "   PGPASSWORD='$DB_PASSWORD' psql -h $DB_ENDPOINT -U $DB_USER -d $DB_NAME"
    echo "4. Deploy application with: ./deployment/lightsail-deploy.sh"
}

# ==================================
# MAIN EXECUTION
# ==================================
main() {
    echo "This script will create AWS infrastructure for nabavkidata.com"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled"
        exit 1
    fi

    check_permissions
    get_vpc_info
    create_rds
    install_pgvector
    create_s3
    create_iam
    summary

    echo -e "\n${GREEN}🚀 AWS infrastructure ready!${NC}"
}

# Run
main

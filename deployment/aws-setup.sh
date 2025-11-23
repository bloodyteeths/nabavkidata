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
NC='\033[0m'

# Configuration
AWS_REGION="eu-central-1"  # Frankfurt
DB_INSTANCE_ID="nabavkidata-db"
DB_NAME="nabavkidata"
DB_USER="nabavki_user"
DB_PASSWORD="CHANGE_THIS_SECURE_PASSWORD"  # Change this!
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
aws sts get-caller-identity
if [ $? -ne 0 ]; then
    echo -e "${RED}AWS credentials not configured. Run: aws configure${NC}"
    exit 1
fi
echo -e "${GREEN} AWS credentials valid${NC}\n"

# ==================================
# STEP 1: Create RDS PostgreSQL 15
# ==================================
create_rds() {
    echo -e "${YELLOW}Step 1: Creating RDS PostgreSQL instance...${NC}"

    # Check if instance already exists
    if aws rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_ID" --region "$AWS_REGION" 2>/dev/null; then
        echo -e "${YELLOW}RDS instance already exists${NC}"
        return
    fi

    # Create DB subnet group
    echo "Creating DB subnet group..."
    aws rds create-db-subnet-group \
        --db-subnet-group-name nabavkidata-db-subnet \
        --db-subnet-group-description "Subnet group for nabavkidata database" \
        --subnet-ids subnet-xxxxx subnet-yyyyy \
        --region "$AWS_REGION" || echo "Subnet group may already exist"

    # Create security group
    echo "Creating security group..."
    VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")
    SG_ID=$(aws ec2 create-security-group \
        --group-name nabavkidata-db-sg \
        --description "Security group for nabavkidata PostgreSQL" \
        --vpc-id "$VPC_ID" \
        --region "$AWS_REGION" \
        --query 'GroupId' \
        --output text)

    # Allow PostgreSQL from Lightsail instance
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 5432 \
        --cidr 0.0.0.0/0 \
        --region "$AWS_REGION" || echo "Rule may already exist"

    # Create RDS instance
    echo "Creating RDS PostgreSQL 15 instance (this takes 5-10 minutes)..."
    aws rds create-db-instance \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --db-instance-class db.t3.micro \
        --engine postgres \
        --engine-version 15.4 \
        --master-username "$DB_USER" \
        --master-user-password "$DB_PASSWORD" \
        --allocated-storage 20 \
        --storage-type gp3 \
        --db-name "$DB_NAME" \
        --vpc-security-group-ids "$SG_ID" \
        --publicly-accessible \
        --backup-retention-period 7 \
        --preferred-backup-window "03:00-04:00" \
        --preferred-maintenance-window "sun:04:00-sun:05:00" \
        --enable-cloudwatch-logs-exports '["postgresql"]' \
        --region "$AWS_REGION"

    echo "Waiting for RDS instance to become available..."
    aws rds wait db-instance-available --db-instance-identifier "$DB_INSTANCE_ID" --region "$AWS_REGION"

    # Get endpoint
    DB_ENDPOINT=$(aws rds describe-db-instances \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --query 'DBInstances[0].Endpoint.Address' \
        --output text \
        --region "$AWS_REGION")

    echo -e "${GREEN} RDS PostgreSQL created${NC}"
    echo -e "${GREEN}Endpoint: $DB_ENDPOINT${NC}\n"

    # Install pgvector extension
    echo "Installing pgvector extension..."
    echo "Run this on RDS via psql:"
    echo "  psql -h $DB_ENDPOINT -U $DB_USER -d $DB_NAME -c 'CREATE EXTENSION IF NOT EXISTS vector;'"
    echo ""
}

# ==================================
# STEP 2: Create S3 Bucket
# ==================================
create_s3() {
    echo -e "${YELLOW}Step 2: Creating S3 bucket for PDFs...${NC}"

    # Create bucket
    aws s3api create-bucket \
        --bucket "$S3_BUCKET" \
        --region "$AWS_REGION" \
        --create-bucket-configuration LocationConstraint="$AWS_REGION" \
        || echo "Bucket may already exist"

    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "$S3_BUCKET" \
        --versioning-configuration Status=Enabled \
        --region "$AWS_REGION"

    # Set lifecycle policy (delete old versions after 90 days)
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

    # Set CORS configuration
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

    # Block public access (we'll use signed URLs)
    aws s3api put-public-access-block \
        --bucket "$S3_BUCKET" \
        --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
        --region "$AWS_REGION"

    echo -e "${GREEN} S3 bucket created: s3://$S3_BUCKET${NC}\n"
    rm -f /tmp/lifecycle-policy.json /tmp/cors.json
}

# ==================================
# STEP 3: Create IAM Policy + User
# ==================================
create_iam() {
    echo -e "${YELLOW}Step 3: Creating IAM user and policies...${NC}"

    # Create IAM policy for S3 access
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
        --policy-name NabavkidataS3Access \
        --policy-document file:///tmp/s3-policy.json \
        || echo "Policy may already exist"

    # Create IAM user
    aws iam create-user --user-name nabavkidata-app || echo "User may already exist"

    # Attach policy
    POLICY_ARN=$(aws iam list-policies --query 'Policies[?PolicyName==`NabavkidataS3Access`].Arn' --output text)
    aws iam attach-user-policy --user-name nabavkidata-app --policy-arn "$POLICY_ARN"

    # Create access keys
    echo "Creating access keys..."
    aws iam create-access-key --user-name nabavkidata-app > /tmp/access-keys.json

    ACCESS_KEY=$(cat /tmp/access-keys.json | grep -o '"AccessKeyId": "[^"]*' | cut -d'"' -f4)
    SECRET_KEY=$(cat /tmp/access-keys.json | grep -o '"SecretAccessKey": "[^"]*' | cut -d'"' -f4)

    echo -e "${GREEN} IAM user created${NC}"
    echo -e "${YELLOW}Access Key ID: $ACCESS_KEY${NC}"
    echo -e "${YELLOW}Secret Access Key: $SECRET_KEY${NC}"
    echo -e "${RED}  Save these credentials securely!${NC}\n"

    rm -f /tmp/s3-policy.json /tmp/access-keys.json
}

# ==================================
# STEP 4: Final Summary
# ==================================
summary() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}AWS Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}\n"

    # Get RDS endpoint
    DB_ENDPOINT=$(aws rds describe-db-instances \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --query 'DBInstances[0].Endpoint.Address' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "NOT_CREATED")

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
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Install pgvector extension on RDS (see above)"
    echo "2. Update .env.prod with the values above"
    echo "3. Test database connection from Lightsail"
    echo "4. Run Alembic migrations"
}

# Main execution
main() {
    echo "This script will create AWS infrastructure for nabavkidata.com"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled"
        exit 1
    fi

    create_rds
    create_s3
    create_iam
    summary

    echo -e "\n${GREEN}=€ AWS infrastructure ready!${NC}"
}

# Run
main

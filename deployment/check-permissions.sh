#!/bin/bash

# ============================================================================
# IAM Permission Checker
# ============================================================================
# This script checks what permissions the current user has and diagnoses
# why EC2 permissions might be failing
# ============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}IAM Permission Diagnostic${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Get current user
echo -e "${YELLOW}Step 1: Getting current AWS user...${NC}"
CURRENT_USER_ARN=$(aws sts get-caller-identity --query 'Arn' --output text 2>/dev/null || echo "")

if [ -z "$CURRENT_USER_ARN" ]; then
    echo -e "${RED}✗ Failed to get AWS credentials${NC}"
    echo -e "${YELLOW}Run: aws configure${NC}\n"
    exit 1
fi

echo -e "${GREEN}✓ Current user: ${CURRENT_USER_ARN}${NC}"

# Extract username
USERNAME=$(echo "$CURRENT_USER_ARN" | awk -F'/' '{print $NF}')
echo -e "${GREEN}✓ Username: ${USERNAME}${NC}\n"

# List attached policies
echo -e "${YELLOW}Step 2: Checking attached policies...${NC}"

ATTACHED_POLICIES=$(aws iam list-attached-user-policies --user-name "$USERNAME" 2>/dev/null || echo "")

if [ -z "$ATTACHED_POLICIES" ]; then
    echo -e "${RED}✗ Cannot list attached policies${NC}"
    echo -e "${YELLOW}You may not have iam:ListAttachedUserPolicies permission${NC}\n"
else
    echo -e "${GREEN}Attached Policies:${NC}"
    echo "$ATTACHED_POLICIES" | grep -E "PolicyName|PolicyArn" || echo "None"
    echo ""
fi

# Test specific permissions
echo -e "${YELLOW}Step 3: Testing specific permissions...${NC}\n"

# Test RDS DescribeDBInstances
echo -e "${BLUE}Testing RDS permissions...${NC}"
if aws rds describe-db-instances --region eu-central-1 --max-items 1 &>/dev/null; then
    echo -e "${GREEN}✓ rds:DescribeDBInstances - ALLOWED${NC}"
else
    echo -e "${RED}✗ rds:DescribeDBInstances - DENIED${NC}"
    aws rds describe-db-instances --region eu-central-1 --max-items 1 2>&1 | grep -i "error" | head -1
fi
echo ""

# Test EC2 DescribeVpcs
echo -e "${BLUE}Testing EC2 VPC permissions...${NC}"
if aws ec2 describe-vpcs --region eu-central-1 --max-results 5 &>/dev/null; then
    echo -e "${GREEN}✓ ec2:DescribeVpcs - ALLOWED${NC}"
else
    echo -e "${RED}✗ ec2:DescribeVpcs - DENIED${NC}"
    echo -e "${YELLOW}Error details:${NC}"
    aws ec2 describe-vpcs --region eu-central-1 --max-results 5 2>&1 | grep -A2 "error" | head -3
fi
echo ""

# Test EC2 DescribeSubnets
echo -e "${BLUE}Testing EC2 Subnet permissions...${NC}"
if aws ec2 describe-subnets --region eu-central-1 --max-results 5 &>/dev/null; then
    echo -e "${GREEN}✓ ec2:DescribeSubnets - ALLOWED${NC}"
else
    echo -e "${RED}✗ ec2:DescribeSubnets - DENIED${NC}"
fi
echo ""

# Test EC2 DescribeSecurityGroups
echo -e "${BLUE}Testing EC2 Security Group permissions...${NC}"
if aws ec2 describe-security-groups --region eu-central-1 --max-results 5 &>/dev/null; then
    echo -e "${GREEN}✓ ec2:DescribeSecurityGroups - ALLOWED${NC}"
else
    echo -e "${RED}✗ ec2:DescribeSecurityGroups - DENIED${NC}"
fi
echo ""

# Test S3 ListBucket
echo -e "${BLUE}Testing S3 permissions...${NC}"
if aws s3 ls &>/dev/null; then
    echo -e "${GREEN}✓ s3:ListBucket - ALLOWED${NC}"
else
    echo -e "${RED}✗ s3:ListBucket - DENIED${NC}"
fi
echo ""

# Test IAM permissions
echo -e "${BLUE}Testing IAM permissions...${NC}"
if aws iam get-user --user-name "$USERNAME" &>/dev/null; then
    echo -e "${GREEN}✓ iam:GetUser - ALLOWED${NC}"
else
    echo -e "${RED}✗ iam:GetUser - DENIED${NC}"
fi
echo ""

# Check if NabavkidataDeployment policy exists
echo -e "${YELLOW}Step 4: Checking if NabavkidataDeployment policy exists...${NC}"
POLICY_ARN="arn:aws:iam::246367841475:policy/NabavkidataDeployment"

if aws iam get-policy --policy-arn "$POLICY_ARN" &>/dev/null; then
    echo -e "${GREEN}✓ Policy exists: ${POLICY_ARN}${NC}\n"

    # Check if attached to current user
    echo -e "${YELLOW}Step 5: Checking if policy is attached to you...${NC}"
    IS_ATTACHED=$(aws iam list-attached-user-policies --user-name "$USERNAME" --query "AttachedPolicies[?PolicyArn=='${POLICY_ARN}'].PolicyName" --output text 2>/dev/null || echo "")

    if [ -n "$IS_ATTACHED" ]; then
        echo -e "${GREEN}✓ Policy IS attached to ${USERNAME}${NC}\n"

        echo -e "${YELLOW}Policy is attached but EC2 permissions are failing.${NC}"
        echo -e "${YELLOW}Possible causes:${NC}"
        echo -e "1. IAM propagation delay (wait 30-60 seconds)"
        echo -e "2. AWS region mismatch"
        echo -e "3. Service Control Policies (SCPs) blocking access"
        echo -e "4. Permission boundaries restricting access\n"

        echo -e "${BLUE}Try waiting 60 seconds then run:${NC}"
        echo -e "./deployment/aws-setup.sh\n"
    else
        echo -e "${RED}✗ Policy is NOT attached to ${USERNAME}${NC}\n"

        echo -e "${BLUE}To attach the policy:${NC}"
        echo -e "./deployment/attach-iam-policy.sh\n"

        echo -e "${YELLOW}Or manually via AWS CLI:${NC}"
        echo -e "aws iam attach-user-policy --user-name ${USERNAME} --policy-arn ${POLICY_ARN}\n"
    fi
else
    echo -e "${RED}✗ Policy does not exist${NC}\n"

    echo -e "${BLUE}To create and attach the policy:${NC}"
    echo -e "./deployment/attach-iam-policy.sh\n"

    echo -e "${YELLOW}Or manually via AWS CLI:${NC}"
    echo -e "aws iam create-policy --policy-name NabavkidataDeployment --policy-document file://deployment/iam-policy.json"
    echo -e "aws iam attach-user-policy --user-name ${USERNAME} --policy-arn ${POLICY_ARN}\n"
fi

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}========================================${NC}\n"

echo -e "${YELLOW}User:${NC} ${USERNAME}"
echo -e "${YELLOW}Region:${NC} eu-central-1\n"

echo -e "${YELLOW}Permissions Status:${NC}"
if aws rds describe-db-instances --region eu-central-1 --max-items 1 &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} RDS"
else
    echo -e "  ${RED}✗${NC} RDS"
fi

if aws ec2 describe-vpcs --region eu-central-1 --max-results 5 &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} EC2"
else
    echo -e "  ${RED}✗${NC} EC2  ${RED}<-- MISSING${NC}"
fi

if aws s3 ls &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} S3"
else
    echo -e "  ${RED}✗${NC} S3"
fi

echo ""

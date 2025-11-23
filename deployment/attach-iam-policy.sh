#!/bin/bash

# ============================================================================
# Attach IAM Policy to Current User
# ============================================================================
# This script attempts to attach the NabavkidataDeployment policy to the
# current AWS user. If the policy doesn't exist, it creates it first.
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

POLICY_NAME="NabavkidataDeployment"
POLICY_FILE="deployment/iam-policy.json"
AWS_ACCOUNT_ID="246367841475"
POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}IAM Policy Attachment Script${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Get current user
echo -e "${YELLOW}Getting current AWS user...${NC}"
CURRENT_USER=$(aws sts get-caller-identity --query 'Arn' --output text 2>/dev/null || echo "")

if [ -z "$CURRENT_USER" ]; then
    echo -e "${RED}✗ Failed to get AWS credentials${NC}"
    echo -e "${YELLOW}Run: aws configure${NC}\n"
    exit 1
fi

echo -e "${GREEN}✓ Current user: ${CURRENT_USER}${NC}\n"

# Extract username from ARN
USERNAME=$(echo "$CURRENT_USER" | awk -F'/' '{print $NF}')
echo -e "${BLUE}Username: ${USERNAME}${NC}\n"

# Check if policy exists
echo -e "${YELLOW}Checking if policy exists...${NC}"
POLICY_EXISTS=$(aws iam get-policy --policy-arn "$POLICY_ARN" 2>/dev/null || echo "")

if [ -z "$POLICY_EXISTS" ]; then
    echo -e "${YELLOW}Policy does not exist. Creating...${NC}"

    # Check if policy file exists
    if [ ! -f "$POLICY_FILE" ]; then
        echo -e "${RED}✗ Policy file not found: ${POLICY_FILE}${NC}"
        exit 1
    fi

    # Try to create policy
    if aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document "file://${POLICY_FILE}" \
        --description "Permissions for nabavkidata.com deployment automation" 2>/dev/null; then
        echo -e "${GREEN}✓ Policy created successfully${NC}\n"
    else
        echo -e "${RED}✗ Failed to create policy${NC}"
        echo -e "${YELLOW}You don't have iam:CreatePolicy permission${NC}"
        echo -e "${YELLOW}Ask an AWS admin to run this script with admin credentials${NC}\n"

        echo -e "${BLUE}Admin can run:${NC}"
        echo -e "aws iam create-policy --policy-name ${POLICY_NAME} --policy-document file://${POLICY_FILE}"
        echo -e "aws iam attach-user-policy --user-name ${USERNAME} --policy-arn ${POLICY_ARN}\n"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Policy already exists${NC}\n"
fi

# Check if policy is already attached
echo -e "${YELLOW}Checking if policy is attached to user...${NC}"
ATTACHED=$(aws iam list-attached-user-policies --user-name "$USERNAME" --query "AttachedPolicies[?PolicyArn=='${POLICY_ARN}'].PolicyName" --output text 2>/dev/null || echo "")

if [ -n "$ATTACHED" ]; then
    echo -e "${GREEN}✓ Policy is already attached to ${USERNAME}${NC}\n"
    echo -e "${BLUE}Verifying permissions...${NC}"

    # Wait for IAM propagation
    echo -e "${YELLOW}Waiting 10 seconds for IAM propagation...${NC}"
    sleep 10

    # Test permissions
    echo -e "\n${YELLOW}Testing permissions...${NC}"

    # Test RDS
    if aws rds describe-db-instances --region eu-central-1 --max-items 1 &>/dev/null; then
        echo -e "${GREEN}✓ RDS permissions OK${NC}"
    else
        echo -e "${RED}✗ RDS permissions missing${NC}"
    fi

    # Test EC2
    if aws ec2 describe-vpcs --region eu-central-1 --max-results 1 &>/dev/null; then
        echo -e "${GREEN}✓ EC2 permissions OK${NC}"
    else
        echo -e "${RED}✗ EC2 permissions missing${NC}"
    fi

    # Test S3
    if aws s3 ls &>/dev/null; then
        echo -e "${GREEN}✓ S3 permissions OK${NC}"
    else
        echo -e "${RED}✗ S3 permissions missing${NC}"
    fi

    echo -e "\n${GREEN}✓ Policy is attached. You can now run ./deployment/aws-setup.sh${NC}\n"
    exit 0
fi

# Try to attach policy
echo -e "${YELLOW}Attaching policy to user ${USERNAME}...${NC}"

if aws iam attach-user-policy \
    --user-name "$USERNAME" \
    --policy-arn "$POLICY_ARN" 2>/dev/null; then
    echo -e "${GREEN}✓ Policy attached successfully${NC}\n"

    echo -e "${YELLOW}Waiting 10 seconds for IAM propagation...${NC}"
    sleep 10

    echo -e "\n${YELLOW}Testing permissions...${NC}"

    # Test RDS
    if aws rds describe-db-instances --region eu-central-1 --max-items 1 &>/dev/null; then
        echo -e "${GREEN}✓ RDS permissions OK${NC}"
    else
        echo -e "${RED}✗ RDS permissions missing${NC}"
    fi

    # Test EC2
    if aws ec2 describe-vpcs --region eu-central-1 --max-results 1 &>/dev/null; then
        echo -e "${GREEN}✓ EC2 permissions OK${NC}"
    else
        echo -e "${RED}✗ EC2 permissions missing${NC}"
    fi

    # Test S3
    if aws s3 ls &>/dev/null; then
        echo -e "${GREEN}✓ S3 permissions OK${NC}"
    else
        echo -e "${RED}✗ S3 permissions missing${NC}"
    fi

    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}\n"

    echo -e "${BLUE}Next step:${NC}"
    echo -e "./deployment/aws-setup.sh\n"
else
    echo -e "${RED}✗ Failed to attach policy${NC}"
    echo -e "${YELLOW}You don't have iam:AttachUserPolicy permission${NC}"
    echo -e "${YELLOW}Ask an AWS admin to run this command:${NC}\n"

    echo -e "${BLUE}aws iam attach-user-policy --user-name ${USERNAME} --policy-arn ${POLICY_ARN}${NC}\n"

    echo -e "${YELLOW}Or attach via AWS Console:${NC}"
    echo -e "1. Go to: https://console.aws.amazon.com/iam/home#/users/${USERNAME}"
    echo -e "2. Click 'Add permissions'"
    echo -e "3. Click 'Attach policies directly'"
    echo -e "4. Search for '${POLICY_NAME}'"
    echo -e "5. Check the box and click 'Add permissions'\n"
    exit 1
fi

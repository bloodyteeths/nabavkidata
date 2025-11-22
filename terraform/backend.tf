terraform {
  backend "s3" {
    bucket         = "nabavki-data-terraform-state"
    key            = "terraform.tfstate"
    region         = "eu-central-1"
    encrypt        = true
    dynamodb_table = "nabavki-data-terraform-locks"

    # Uncomment and configure these for additional security
    # kms_key_id     = "arn:aws:kms:eu-central-1:ACCOUNT_ID:key/KEY_ID"
    # role_arn       = "arn:aws:iam::ACCOUNT_ID:role/TerraformRole"
  }
}

# Note: The S3 bucket and DynamoDB table must be created manually before using this backend
#
# Create S3 bucket for state:
# aws s3api create-bucket \
#   --bucket nabavki-data-terraform-state \
#   --region eu-central-1 \
#   --create-bucket-configuration LocationConstraint=eu-central-1
#
# aws s3api put-bucket-versioning \
#   --bucket nabavki-data-terraform-state \
#   --versioning-configuration Status=Enabled
#
# aws s3api put-bucket-encryption \
#   --bucket nabavki-data-terraform-state \
#   --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
#
# Create DynamoDB table for locking:
# aws dynamodb create-table \
#   --table-name nabavki-data-terraform-locks \
#   --attribute-definitions AttributeName=LockID,AttributeType=S \
#   --key-schema AttributeName=LockID,KeyType=HASH \
#   --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
#   --region eu-central-1

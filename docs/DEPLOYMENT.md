# Deployment Guide - Nabavki Data Platform

This comprehensive guide covers the complete deployment process for the Nabavki Data platform, from infrastructure provisioning to application deployment and monitoring setup.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Environment Configuration](#environment-configuration)
4. [Docker Deployment](#docker-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [CI/CD Setup](#cicd-setup)
7. [Monitoring and Observability](#monitoring-and-observability)
8. [Backup and Restore](#backup-and-restore)
9. [Troubleshooting](#troubleshooting)
10. [Security Best Practices](#security-best-practices)

## Prerequisites

### Required Tools

Install the following tools before beginning deployment:

```bash
# AWS CLI
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# Terraform
brew tap hashicorp/tap
brew install hashicorp/tap/terraform

# kubectl
brew install kubectl

# AWS IAM Authenticator
brew install aws-iam-authenticator

# Helm
brew install helm

# Docker
brew install --cask docker

# Optional but recommended
brew install k9s  # Kubernetes CLI UI
brew install kubectx  # Switch between clusters
```

### AWS Account Setup

1. Create an AWS account or use existing one
2. Configure AWS credentials:

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: eu-central-1
# Default output format: json
```

3. Verify credentials:

```bash
aws sts get-caller-identity
```

### Required Permissions

Ensure your AWS user/role has the following permissions:
- VPC management
- EC2 instances
- EKS cluster creation
- RDS database management
- S3 bucket operations
- ECR repository management
- IAM role creation
- CloudWatch logs

## Infrastructure Setup

### Step 1: Prepare Terraform Backend

Create the S3 bucket and DynamoDB table for Terraform state:

```bash
# Create S3 bucket for state
aws s3api create-bucket \
  --bucket nabavki-data-terraform-state \
  --region eu-central-1 \
  --create-bucket-configuration LocationConstraint=eu-central-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket nabavki-data-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket nabavki-data-terraform-state \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Block public access
aws s3api put-public-access-block \
  --bucket nabavki-data-terraform-state \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Create DynamoDB table for locking
aws dynamodb create-table \
  --table-name nabavki-data-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
  --region eu-central-1
```

### Step 2: Configure Terraform Variables

```bash
cd terraform

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your specific values
nano terraform.tfvars
```

**Important**: Update the following in `terraform.tfvars`:
- `db_password`: Set a strong password for the database
- `environment`: Set to "development", "staging", or "production"
- Adjust instance sizes based on your needs

### Step 3: Initialize and Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Review the execution plan
terraform plan

# Apply the configuration
terraform apply

# Confirm by typing 'yes' when prompted
```

This process will take 15-20 minutes to complete. Terraform will create:
- VPC with public and private subnets across 3 availability zones
- NAT gateways for outbound internet access
- EKS cluster with node groups
- RDS PostgreSQL database
- ECR repository for Docker images
- S3 buckets for storage and backups
- Security groups and IAM roles

### Step 4: Configure kubectl for EKS

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --region eu-central-1 \
  --name nabavki-data-production

# Verify cluster access
kubectl cluster-info
kubectl get nodes
```

## Environment Configuration

### Database Configuration

After infrastructure deployment, retrieve the database endpoint:

```bash
# Get database endpoint
terraform output rds_endpoint

# Test database connection
PGPASSWORD='your_db_password' psql \
  -h $(terraform output -raw rds_address) \
  -U admin \
  -d nabavki
```

### Environment Variables

Create environment-specific configuration files:

```bash
# Create Kubernetes secret for database credentials
kubectl create secret generic db-credentials \
  --from-literal=username=admin \
  --from-literal=password='your_db_password' \
  --from-literal=host=$(terraform output -raw rds_address) \
  --from-literal=database=nabavki

# Create secret for AWS credentials (if needed)
kubectl create secret generic aws-credentials \
  --from-literal=access_key_id='YOUR_ACCESS_KEY' \
  --from-literal=secret_access_key='YOUR_SECRET_KEY'

# Create configmap for application configuration
kubectl create configmap app-config \
  --from-literal=environment=production \
  --from-literal=log_level=info
```

## Docker Deployment

### Build Docker Images

```bash
# Navigate to project root
cd /Users/tamsar/Downloads/nabavkidata

# Build backend image
docker build -t nabavki-backend:latest -f backend/Dockerfile backend/

# Build frontend image
docker build -t nabavki-frontend:latest -f frontend/Dockerfile frontend/

# Test locally
docker-compose up -d
docker-compose ps
```

### Push to ECR

```bash
# Get ECR login credentials
aws ecr get-login-password --region eu-central-1 | \
  docker login --username AWS --password-stdin \
  $(terraform output -raw ecr_repository_url)

# Tag images
ECR_URL=$(cd terraform && terraform output -raw ecr_repository_url)
docker tag nabavki-backend:latest $ECR_URL:backend-latest
docker tag nabavki-frontend:latest $ECR_URL:frontend-latest

# Push images
docker push $ECR_URL:backend-latest
docker push $ECR_URL:frontend-latest
```

## Kubernetes Deployment

### Install AWS Load Balancer Controller

```bash
# Add EKS chart repository
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# Install AWS Load Balancer Controller
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=nabavki-data-production \
  --set serviceAccount.create=true \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$(cd terraform && terraform output -raw aws_load_balancer_controller_role_arn)
```

### Deploy Application

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/services.yaml
kubectl apply -f k8s/ingress.yaml

# Verify deployments
kubectl get deployments -n nabavki-data
kubectl get pods -n nabavki-data
kubectl get services -n nabavki-data
kubectl get ingress -n nabavki-data
```

### Configure Ingress

```bash
# Get load balancer URL
kubectl get ingress -n nabavki-data

# Configure DNS to point to the load balancer
# Example: nabavki.example.com -> a1b2c3d4e5f6g7h8.eu-central-1.elb.amazonaws.com
```

## CI/CD Setup

### GitHub Actions

Ensure the following secrets are configured in your GitHub repository:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `ECR_REPOSITORY`
- `EKS_CLUSTER_NAME`

The CI/CD pipeline will automatically:
1. Run tests on every push
2. Build Docker images
3. Push to ECR
4. Deploy to Kubernetes (on main branch)

### Manual Deployment Trigger

```bash
# Trigger deployment via GitHub CLI
gh workflow run deploy.yml

# Or via git tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

## Monitoring and Observability

### Install Prometheus and Grafana

```bash
# Add Prometheus community helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.adminPassword='admin' \
  --set prometheus.prometheusSpec.retention=30d

# Verify installation
kubectl get pods -n monitoring
```

### Access Grafana

```bash
# Port forward to access Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Access at http://localhost:3000
# Username: admin
# Password: admin (or what you set)
```

### CloudWatch Integration

```bash
# Install CloudWatch Container Insights
curl https://raw.githubusercontent.com/aws-samples/amazon-cloudwatch-container-insights/latest/k8s-deployment-manifest-templates/deployment-mode/daemonset/container-insights-monitoring/quickstart/cwagent-fluentd-quickstart.yaml | \
  sed "s/{{cluster_name}}/nabavki-data-production/;s/{{region_name}}/eu-central-1/" | \
  kubectl apply -f -
```

## Backup and Restore

### Database Backups

Automated backups are configured via RDS. For manual backups:

```bash
# Create manual RDS snapshot
aws rds create-db-snapshot \
  --db-instance-identifier nabavki-data-db-production \
  --db-snapshot-identifier nabavki-manual-backup-$(date +%Y%m%d-%H%M%S)

# List snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier nabavki-data-db-production
```

### Application Data Backups

```bash
# Backup to S3
kubectl exec -n nabavki-data deployment/backend -- \
  pg_dump -h $DB_HOST -U admin nabavki | \
  aws s3 cp - s3://nabavki-data-backups-production/backup-$(date +%Y%m%d).sql

# Automated backup via CronJob (see k8s/backup-cronjob.yaml)
kubectl apply -f k8s/backup-cronjob.yaml
```

### Restore Procedures

```bash
# Restore from RDS snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier nabavki-data-db-production-restored \
  --db-snapshot-identifier nabavki-manual-backup-20250101-120000

# Restore from SQL backup
aws s3 cp s3://nabavki-data-backups-production/backup-20250101.sql - | \
  kubectl exec -i -n nabavki-data deployment/backend -- \
  psql -h $DB_HOST -U admin nabavki
```

## Troubleshooting

### Common Issues

#### 1. Pods Not Starting

```bash
# Check pod status
kubectl get pods -n nabavki-data

# View pod logs
kubectl logs -n nabavki-data <pod-name>

# Describe pod for events
kubectl describe pod -n nabavki-data <pod-name>

# Check resource constraints
kubectl top nodes
kubectl top pods -n nabavki-data
```

#### 2. Database Connection Issues

```bash
# Test database connectivity from pod
kubectl exec -it -n nabavki-data <backend-pod> -- \
  psql -h $DB_HOST -U admin -d nabavki

# Check security groups
aws ec2 describe-security-groups \
  --group-ids $(cd terraform && terraform output -raw rds_security_group_id)

# Verify RDS instance status
aws rds describe-db-instances \
  --db-instance-identifier nabavki-data-db-production
```

#### 3. EKS Node Issues

```bash
# Check node status
kubectl get nodes

# Describe problematic node
kubectl describe node <node-name>

# Check AWS Auto Scaling Group
aws autoscaling describe-auto-scaling-groups \
  --query "AutoScalingGroups[?contains(AutoScalingGroupName, 'nabavki-data')]"
```

#### 4. Load Balancer Not Working

```bash
# Check ingress status
kubectl describe ingress -n nabavki-data

# Verify AWS Load Balancer Controller
kubectl logs -n kube-system deployment/aws-load-balancer-controller

# Check target groups
aws elbv2 describe-target-groups
aws elbv2 describe-target-health --target-group-arn <arn>
```

### Debug Mode

Enable debug logging:

```bash
# Update deployment with debug environment variable
kubectl set env deployment/backend -n nabavki-data LOG_LEVEL=debug

# Watch logs in real-time
kubectl logs -f -n nabavki-data deployment/backend
```

## Security Best Practices

### 1. Secrets Management

- Never commit secrets to Git
- Use AWS Secrets Manager or Kubernetes Secrets
- Rotate credentials regularly
- Use IAM roles instead of access keys when possible

### 2. Network Security

- Keep databases in private subnets
- Use security groups to restrict access
- Enable VPC Flow Logs for audit
- Use AWS WAF for web application firewall

### 3. Container Security

- Scan images for vulnerabilities (enabled in ECR)
- Use minimal base images
- Run containers as non-root user
- Keep images updated

### 4. Access Control

```bash
# Create read-only user for developers
kubectl create serviceaccount readonly-user -n nabavki-data
kubectl create rolebinding readonly-binding \
  --clusterrole=view \
  --serviceaccount=nabavki-data:readonly-user \
  --namespace=nabavki-data
```

### 5. Audit Logging

EKS audit logs are automatically sent to CloudWatch. Review them regularly:

```bash
# View audit logs
aws logs tail /aws/eks/nabavki-data-production/cluster --follow
```

## Maintenance

### Regular Updates

```bash
# Update Kubernetes version (plan carefully)
aws eks update-cluster-version \
  --name nabavki-data-production \
  --kubernetes-version 1.29

# Update node groups
aws eks update-nodegroup-version \
  --cluster-name nabavki-data-production \
  --nodegroup-name nabavki-data-general-production

# Update Helm charts
helm repo update
helm upgrade prometheus prometheus-community/kube-prometheus-stack -n monitoring
```

### Cost Optimization

- Review CloudWatch metrics for underutilized resources
- Consider Reserved Instances for predictable workloads
- Enable spot instances for non-critical workloads
- Set up AWS Cost Explorer alerts

## Additional Resources

- [EKS Documentation](https://docs.aws.amazon.com/eks/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

## Support

For issues and questions:
- Create an issue in the project repository
- Contact the DevOps team
- Check AWS Support (if you have a support plan)

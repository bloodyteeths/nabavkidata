#!/bin/bash
#
# AWS SES CloudWatch Alarms Setup Script
# Creates monitoring alarms for email deliverability and quota usage
#
# Date: 2025-11-23
# Region: eu-central-1
#

set -e

REGION="eu-central-1"
SNS_EMAIL="admin@nabavkidata.com"

echo "======================================================================"
echo "AWS SES CloudWatch Alarms Setup"
echo "======================================================================"
echo "Region: $REGION"
echo "Date: $(date)"
echo ""

# Create SNS topic for alarm notifications
echo "Creating SNS topic for alarm notifications..."
SNS_TOPIC_ARN=$(aws sns create-topic \
  --name nabavkidata-ses-alarms \
  --region $REGION \
  --output text \
  --query 'TopicArn')

echo "✅ SNS Topic created: $SNS_TOPIC_ARN"

# Subscribe email to SNS topic
echo "Subscribing email to SNS topic..."
aws sns subscribe \
  --topic-arn "$SNS_TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "$SNS_EMAIL" \
  --region $REGION

echo "✅ Email subscription created (check $SNS_EMAIL for confirmation)"
echo ""

# Alarm 1: High Bounce Rate (>5%)
echo "Creating alarm: High Bounce Rate..."
aws cloudwatch put-metric-alarm \
  --alarm-name nabavkidata-ses-high-bounce-rate \
  --alarm-description "SES bounce rate exceeds 5% - Risk of reputation damage" \
  --metric-name Reputation.BounceRate \
  --namespace AWS/SES \
  --statistic Average \
  --period 300 \
  --threshold 0.05 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region $REGION

echo "✅ Alarm created: High Bounce Rate (>5%)"

# Alarm 2: High Complaint Rate (>0.5%)
echo "Creating alarm: High Complaint Rate..."
aws cloudwatch put-metric-alarm \
  --alarm-name nabavkidata-ses-high-complaint-rate \
  --alarm-description "SES complaint rate exceeds 0.5% - Risk of account suspension" \
  --metric-name Reputation.ComplaintRate \
  --namespace AWS/SES \
  --statistic Average \
  --period 300 \
  --threshold 0.005 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region $REGION

echo "✅ Alarm created: High Complaint Rate (>0.5%)"

# Alarm 3: Send Quota Usage (>80%)
# Note: Threshold will be updated after production approval (80% of 50,000 = 40,000)
echo "Creating alarm: Send Quota Usage..."
aws cloudwatch put-metric-alarm \
  --alarm-name nabavkidata-ses-quota-usage-high \
  --alarm-description "SES send quota usage >80% of daily limit" \
  --metric-name SendQuotaUsed \
  --namespace AWS/SES \
  --statistic Sum \
  --period 86400 \
  --threshold 160 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region $REGION

echo "✅ Alarm created: Send Quota Usage (>80% - currently 160/200 sandbox limit)"

# Alarm 4: Reject Rate (>1%)
echo "Creating alarm: High Reject Rate..."
aws cloudwatch put-metric-alarm \
  --alarm-name nabavkidata-ses-high-reject-rate \
  --alarm-description "SES reject rate exceeds 1%" \
  --metric-name Reputation.RejectRate \
  --namespace AWS/SES \
  --statistic Average \
  --period 300 \
  --threshold 0.01 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region $REGION

echo "✅ Alarm created: High Reject Rate (>1%)"

# Create configuration set for event tracking (optional)
echo ""
echo "Creating SES configuration set for event tracking..."
aws sesv2 create-configuration-set \
  --configuration-set-name nabavkidata-events \
  --region $REGION \
  2>/dev/null || echo "ℹ️  Configuration set already exists"

# Create event destination for bounces and complaints
echo "Creating SNS event destination for bounce/complaint tracking..."
aws sesv2 put-configuration-set-event-destination \
  --configuration-set-name nabavkidata-events \
  --event-destination-name sns-bounce-complaint-events \
  --event-destination "{
    \"Enabled\": true,
    \"MatchingEventTypes\": [\"BOUNCE\", \"COMPLAINT\", \"REJECT\"],
    \"SnsDestination\": {
      \"TopicArn\": \"$SNS_TOPIC_ARN\"
    }
  }" \
  --region $REGION \
  2>/dev/null || echo "ℹ️  Event destination already exists"

echo "✅ Event tracking configured"

echo ""
echo "======================================================================"
echo "SETUP COMPLETE"
echo "======================================================================"
echo ""
echo "Alarms Created:"
echo "  1. High Bounce Rate (>5%)"
echo "  2. High Complaint Rate (>0.5%)"
echo "  3. Send Quota Usage (>80%)"
echo "  4. High Reject Rate (>1%)"
echo ""
echo "SNS Topic: $SNS_TOPIC_ARN"
echo "Email: $SNS_EMAIL"
echo ""
echo "⚠️  IMPORTANT: Check your email ($SNS_EMAIL) and confirm the SNS subscription!"
echo ""
echo "View alarms in CloudWatch Console:"
echo "https://console.aws.amazon.com/cloudwatch/home?region=$REGION#alarmsV2:"
echo ""
echo "After production access approval, update the quota alarm threshold:"
echo "  aws cloudwatch put-metric-alarm \\"
echo "    --alarm-name nabavkidata-ses-quota-usage-high \\"
echo "    --threshold 40000 \\"
echo "    --region $REGION"
echo ""
echo "======================================================================"

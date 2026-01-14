package test

import (
	"encoding/json"
	"strconv"
	"strings"
	"testing"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/cloudwatchevents"
	"github.com/aws/aws-sdk-go/service/iam"
	"github.com/aws/aws-sdk-go/service/lambda"
	"github.com/aws/aws-sdk-go/service/sns"
	"github.com/aws/aws-sdk-go/service/sqs"
	terratest_aws "github.com/gruntwork-io/terratest/modules/aws"
	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestTerraformBasicDeployment validates that the module deploys successfully
// and creates all core resources (SNS, SQS, IAM, Lambda, EventBridge)
func TestTerraformBasicDeployment(t *testing.T) {
	t.Parallel()

	// Retrieve AWS region from environment or default to us-east-1
	awsRegion := terratest_aws.GetRandomStableRegion(t, []string{"us-east-1", "us-west-2"}, nil)

	// Configure Terraform options
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Path to the Terraform code to test
		TerraformDir: "./fixtures/basic",

		// Variables to pass to the Terraform code
		Vars: map[string]interface{}{
			"aws_region":               awsRegion,
			"enable_compute_sp":        true,
			"enable_database_sp":       true,
			"coverage_target_percent":  70,
			"max_purchase_percent":     20,
			"dry_run":                  true,
			"notification_emails":      []string{"test@example.com"},
			"enable_lambda_error_alarm": true,
			"enable_dlq_alarm":          true,
		},

		// Disable colors in Terraform commands for cleaner test output
		NoColor: true,
	})

	// Ensure resources are destroyed at the end of the test
	defer terraform.Destroy(t, terraformOptions)

	// Initialize and apply Terraform
	terraform.InitAndApply(t, terraformOptions)

	// ============================================================================
	// Validate SQS Queues
	// ============================================================================

	// Retrieve SQS queue URLs from Terraform outputs
	queueURL := terraform.Output(t, terraformOptions, "queue_url")
	dlqURL := terraform.Output(t, terraformOptions, "dlq_url")

	// Validate main queue exists
	assert.NotEmpty(t, queueURL, "Main SQS queue URL should not be empty")
	assert.Contains(t, queueURL, "sp-autopilot-purchase-intents", "Queue URL should contain expected queue name")

	// Validate DLQ exists
	assert.NotEmpty(t, dlqURL, "DLQ URL should not be empty")
	assert.Contains(t, dlqURL, "sp-autopilot-purchase-intents-dlq", "DLQ URL should contain expected queue name")

	// Verify queue exists in AWS
	queueARN := terraform.Output(t, terraformOptions, "queue_arn")
	assert.NotEmpty(t, queueARN, "Queue ARN should not be empty")

	// ============================================================================
	// Validate SNS Topic
	// ============================================================================

	// Retrieve SNS topic ARN from Terraform outputs
	snsTopicARN := terraform.Output(t, terraformOptions, "sns_topic_arn")

	// Validate SNS topic exists
	assert.NotEmpty(t, snsTopicARN, "SNS topic ARN should not be empty")
	assert.Contains(t, snsTopicARN, "sp-autopilot-notifications", "SNS topic ARN should contain expected topic name")

	// ============================================================================
	// Validate Lambda Functions
	// ============================================================================

	// Retrieve Lambda function names from Terraform outputs
	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	purchaserLambdaName := terraform.Output(t, terraformOptions, "purchaser_lambda_name")

	// Validate Scheduler Lambda exists
	assert.NotEmpty(t, schedulerLambdaName, "Scheduler Lambda name should not be empty")
	assert.Contains(t, schedulerLambdaName, "sp-autopilot-scheduler", "Scheduler Lambda name should contain expected function name")

	// Validate Purchaser Lambda exists
	assert.NotEmpty(t, purchaserLambdaName, "Purchaser Lambda name should not be empty")
	assert.Contains(t, purchaserLambdaName, "sp-autopilot-purchaser", "Purchaser Lambda name should contain expected function name")

	// Retrieve Lambda ARNs
	schedulerLambdaARN := terraform.Output(t, terraformOptions, "scheduler_lambda_arn")
	purchaserLambdaARN := terraform.Output(t, terraformOptions, "purchaser_lambda_arn")

	// Validate Lambda ARNs are not empty
	assert.NotEmpty(t, schedulerLambdaARN, "Scheduler Lambda ARN should not be empty")
	assert.NotEmpty(t, purchaserLambdaARN, "Purchaser Lambda ARN should not be empty")

	// ============================================================================
	// Validate IAM Roles
	// ============================================================================

	// Retrieve IAM role ARNs from Terraform outputs
	schedulerRoleARN := terraform.Output(t, terraformOptions, "scheduler_role_arn")
	purchaserRoleARN := terraform.Output(t, terraformOptions, "purchaser_role_arn")

	// Validate Scheduler Lambda execution role exists
	assert.NotEmpty(t, schedulerRoleARN, "Scheduler Lambda role ARN should not be empty")
	assert.Contains(t, schedulerRoleARN, "sp-autopilot-scheduler", "Scheduler role ARN should contain expected role name")

	// Validate Purchaser Lambda execution role exists
	assert.NotEmpty(t, purchaserRoleARN, "Purchaser Lambda role ARN should not be empty")
	assert.Contains(t, purchaserRoleARN, "sp-autopilot-purchaser", "Purchaser role ARN should contain expected role name")

	// ============================================================================
	// Validate EventBridge Rules
	// ============================================================================

	// Retrieve EventBridge rule names from Terraform outputs
	schedulerRuleName := terraform.Output(t, terraformOptions, "scheduler_rule_name")
	purchaserRuleName := terraform.Output(t, terraformOptions, "purchaser_rule_name")

	// Validate Scheduler EventBridge rule exists
	assert.NotEmpty(t, schedulerRuleName, "Scheduler EventBridge rule name should not be empty")
	assert.Contains(t, schedulerRuleName, "sp-autopilot-scheduler", "Scheduler rule name should contain expected rule name")

	// Validate Purchaser EventBridge rule exists
	assert.NotEmpty(t, purchaserRuleName, "Purchaser EventBridge rule name should not be empty")
	assert.Contains(t, purchaserRuleName, "sp-autopilot-purchaser", "Purchaser rule name should contain expected rule name")

	// Retrieve EventBridge rule ARNs
	schedulerRuleARN := terraform.Output(t, terraformOptions, "scheduler_rule_arn")
	purchaserRuleARN := terraform.Output(t, terraformOptions, "purchaser_rule_arn")

	// Validate EventBridge rule ARNs are not empty
	assert.NotEmpty(t, schedulerRuleARN, "Scheduler rule ARN should not be empty")
	assert.NotEmpty(t, purchaserRuleARN, "Purchaser rule ARN should not be empty")

	// ============================================================================
	// Validate CloudWatch Alarms
	// ============================================================================

	// Retrieve CloudWatch alarm ARNs from Terraform outputs
	schedulerErrorAlarmARN := terraform.Output(t, terraformOptions, "scheduler_error_alarm_arn")
	purchaserErrorAlarmARN := terraform.Output(t, terraformOptions, "purchaser_error_alarm_arn")
	dlqAlarmARN := terraform.Output(t, terraformOptions, "dlq_alarm_arn")

	// Validate CloudWatch alarms exist
	assert.NotEmpty(t, schedulerErrorAlarmARN, "Scheduler error alarm ARN should not be empty")
	assert.NotEmpty(t, purchaserErrorAlarmARN, "Purchaser error alarm ARN should not be empty")
	assert.NotEmpty(t, dlqAlarmARN, "DLQ alarm ARN should not be empty")

	// ============================================================================
	// Validate Module Configuration
	// ============================================================================

	// Retrieve module configuration from Terraform outputs
	moduleConfig := terraform.OutputMap(t, terraformOptions, "module_configuration")

	// Validate configuration values
	assert.NotEmpty(t, moduleConfig, "Module configuration should not be empty")
	assert.Equal(t, "true", moduleConfig["enable_compute_sp"], "Compute SP should be enabled")
	assert.Equal(t, "true", moduleConfig["enable_database_sp"], "Database SP should be enabled")
	assert.Equal(t, "true", moduleConfig["dry_run"], "Dry run should be enabled")
}

// TestSQSQueueConfiguration validates SQS queue attributes including
// message retention, visibility timeout, and redrive policy
func TestSQSQueueConfiguration(t *testing.T) {
	t.Parallel()

	// Retrieve AWS region from environment or default to us-east-1
	awsRegion := terratest_aws.GetRandomStableRegion(t, []string{"us-east-1", "us-west-2"}, nil)

	// Configure Terraform options
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Path to the Terraform code to test
		TerraformDir: "./fixtures/basic",

		// Variables to pass to the Terraform code
		Vars: map[string]interface{}{
			"aws_region":          awsRegion,
			"enable_compute_sp":   true,
			"enable_database_sp":  true,
			"dry_run":             true,
			"notification_emails": []string{"test@example.com"},
		},

		// Disable colors in Terraform commands for cleaner test output
		NoColor: true,
	})

	// Ensure resources are destroyed at the end of the test
	defer terraform.Destroy(t, terraformOptions)

	// Initialize and apply Terraform
	terraform.InitAndApply(t, terraformOptions)

	// ============================================================================
	// Retrieve Queue URLs from Terraform Outputs
	// ============================================================================

	queueURL := terraform.Output(t, terraformOptions, "queue_url")
	dlqURL := terraform.Output(t, terraformOptions, "dlq_url")

	// Validate queue URLs are not empty
	require.NotEmpty(t, queueURL, "Main queue URL should not be empty")
	require.NotEmpty(t, dlqURL, "DLQ URL should not be empty")

	// ============================================================================
	// Create SQS Client
	// ============================================================================

	sqsClient := terratest_aws.NewSqsClient(t, awsRegion)

	// ============================================================================
	// Validate Dead Letter Queue (DLQ) Attributes
	// ============================================================================

	// Get DLQ attributes
	dlqAttrs, err := sqsClient.GetQueueAttributes(&sqs.GetQueueAttributesInput{
		QueueUrl: aws.String(dlqURL),
		AttributeNames: []*string{
			aws.String("MessageRetentionPeriod"),
			aws.String("QueueArn"),
		},
	})
	require.NoError(t, err, "Failed to get DLQ attributes")

	// Validate DLQ message retention is 14 days (1209600 seconds)
	dlqRetention, err := strconv.Atoi(*dlqAttrs.Attributes["MessageRetentionPeriod"])
	require.NoError(t, err, "Failed to parse DLQ message retention period")
	assert.Equal(t, 1209600, dlqRetention, "DLQ message retention should be 1209600 seconds (14 days)")

	// Get DLQ ARN for redrive policy validation
	dlqArn := *dlqAttrs.Attributes["QueueArn"]
	require.NotEmpty(t, dlqArn, "DLQ ARN should not be empty")

	// ============================================================================
	// Validate Main Queue Attributes
	// ============================================================================

	// Get main queue attributes
	queueAttrs, err := sqsClient.GetQueueAttributes(&sqs.GetQueueAttributesInput{
		QueueUrl: aws.String(queueURL),
		AttributeNames: []*string{
			aws.String("VisibilityTimeout"),
			aws.String("RedrivePolicy"),
		},
	})
	require.NoError(t, err, "Failed to get main queue attributes")

	// Validate visibility timeout is 300 seconds (5 minutes)
	visibilityTimeout, err := strconv.Atoi(*queueAttrs.Attributes["VisibilityTimeout"])
	require.NoError(t, err, "Failed to parse visibility timeout")
	assert.Equal(t, 300, visibilityTimeout, "Main queue visibility timeout should be 300 seconds (5 minutes)")

	// ============================================================================
	// Validate Redrive Policy
	// ============================================================================

	// Parse redrive policy JSON
	redrivePolicyJSON := *queueAttrs.Attributes["RedrivePolicy"]
	require.NotEmpty(t, redrivePolicyJSON, "Redrive policy should not be empty")

	var redrivePolicy map[string]interface{}
	err = json.Unmarshal([]byte(redrivePolicyJSON), &redrivePolicy)
	require.NoError(t, err, "Failed to parse redrive policy JSON")

	// Validate maxReceiveCount is 3
	maxReceiveCount, ok := redrivePolicy["maxReceiveCount"].(float64)
	require.True(t, ok, "maxReceiveCount should be a number")
	assert.Equal(t, float64(3), maxReceiveCount, "maxReceiveCount should be 3")

	// Validate deadLetterTargetArn points to the DLQ
	deadLetterTargetArn, ok := redrivePolicy["deadLetterTargetArn"].(string)
	require.True(t, ok, "deadLetterTargetArn should be a string")
	assert.Equal(t, dlqArn, deadLetterTargetArn, "deadLetterTargetArn should match DLQ ARN")
	assert.Contains(t, deadLetterTargetArn, "sp-autopilot-purchase-intents-dlq", "deadLetterTargetArn should contain DLQ name")
}

// TestSNSTopicConfiguration validates SNS topic attributes and email subscriptions
func TestSNSTopicConfiguration(t *testing.T) {
	t.Parallel()

	// Retrieve AWS region from environment or default to us-east-1
	awsRegion := terratest_aws.GetRandomStableRegion(t, []string{"us-east-1", "us-west-2"}, nil)

	// Test email addresses for subscriptions
	testEmails := []string{"test1@example.com", "test2@example.com"}

	// Configure Terraform options
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Path to the Terraform code to test
		TerraformDir: "./fixtures/basic",

		// Variables to pass to the Terraform code
		Vars: map[string]interface{}{
			"aws_region":          awsRegion,
			"enable_compute_sp":   true,
			"enable_database_sp":  true,
			"dry_run":             true,
			"notification_emails": testEmails,
		},

		// Disable colors in Terraform commands for cleaner test output
		NoColor: true,
	})

	// Ensure resources are destroyed at the end of the test
	defer terraform.Destroy(t, terraformOptions)

	// Initialize and apply Terraform
	terraform.InitAndApply(t, terraformOptions)

	// ============================================================================
	// Retrieve SNS Topic ARN from Terraform Outputs
	// ============================================================================

	snsTopicARN := terraform.Output(t, terraformOptions, "sns_topic_arn")
	require.NotEmpty(t, snsTopicARN, "SNS topic ARN should not be empty")
	assert.Contains(t, snsTopicARN, "sp-autopilot-notifications", "SNS topic ARN should contain expected topic name")

	// ============================================================================
	// Create SNS Client
	// ============================================================================

	snsClient := terratest_aws.NewSnsClient(t, awsRegion)

	// ============================================================================
	// Validate SNS Topic Attributes
	// ============================================================================

	// Get SNS topic attributes
	topicAttrs, err := snsClient.GetTopicAttributes(&sns.GetTopicAttributesInput{
		TopicArn: aws.String(snsTopicARN),
	})
	require.NoError(t, err, "Failed to get SNS topic attributes")

	// Validate topic display name
	displayName := topicAttrs.Attributes["DisplayName"]
	require.NotNil(t, displayName, "Display name should not be nil")
	assert.Equal(t, "AWS Savings Plans Automation Notifications", *displayName, "Display name should match expected value")

	// Validate topic name is correct
	topicName := topicAttrs.Attributes["TopicArn"]
	require.NotNil(t, topicName, "Topic ARN should not be nil")
	assert.Contains(t, *topicName, "sp-autopilot-notifications", "Topic ARN should contain expected topic name")

	// ============================================================================
	// Validate SNS Topic Subscriptions
	// ============================================================================

	// List all subscriptions for the topic
	subscriptions, err := snsClient.ListSubscriptionsByTopic(&sns.ListSubscriptionsByTopicInput{
		TopicArn: aws.String(snsTopicARN),
	})
	require.NoError(t, err, "Failed to list SNS topic subscriptions")

	// Validate subscription count matches number of test emails
	assert.Equal(t, len(testEmails), len(subscriptions.Subscriptions), "Should have subscription for each email")

	// Validate each subscription
	emailMap := make(map[string]bool)
	for _, email := range testEmails {
		emailMap[email] = false
	}

	for _, subscription := range subscriptions.Subscriptions {
		// Validate subscription protocol is email
		assert.NotNil(t, subscription.Protocol, "Subscription protocol should not be nil")
		assert.Equal(t, "email", *subscription.Protocol, "Subscription protocol should be 'email'")

		// Validate subscription endpoint is one of the test emails
		assert.NotNil(t, subscription.Endpoint, "Subscription endpoint should not be nil")
		endpoint := *subscription.Endpoint

		if _, exists := emailMap[endpoint]; exists {
			emailMap[endpoint] = true
		} else {
			t.Errorf("Unexpected subscription endpoint: %s", endpoint)
		}

		// Validate subscription is associated with the correct topic
		assert.NotNil(t, subscription.TopicArn, "Subscription topic ARN should not be nil")
		assert.Equal(t, snsTopicARN, *subscription.TopicArn, "Subscription should be associated with the correct topic")
	}

	// Verify all test emails have corresponding subscriptions
	for email, found := range emailMap {
		assert.True(t, found, "Email %s should have a subscription", email)
	}
}

// TestLambdaDeployment validates Lambda function deployment configuration
// including runtime, handler, environment variables, memory, and timeout
func TestLambdaDeployment(t *testing.T) {
	t.Parallel()

	// Retrieve AWS region from environment or default to us-east-1
	awsRegion := terratest_aws.GetRandomStableRegion(t, []string{"us-east-1", "us-west-2"}, nil)

	// Configure Terraform options
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Path to the Terraform code to test
		TerraformDir: "./fixtures/basic",

		// Variables to pass to the Terraform code
		Vars: map[string]interface{}{
			"aws_region":               awsRegion,
			"enable_compute_sp":        true,
			"enable_database_sp":       true,
			"coverage_target_percent":  70,
			"max_purchase_percent":     20,
			"dry_run":                  true,
			"notification_emails":      []string{"test@example.com"},
			"enable_lambda_error_alarm": true,
			"enable_dlq_alarm":          true,
		},

		// Disable colors in Terraform commands for cleaner test output
		NoColor: true,
	})

	// Ensure resources are destroyed at the end of the test
	defer terraform.Destroy(t, terraformOptions)

	// Initialize and apply Terraform
	terraform.InitAndApply(t, terraformOptions)

	// ============================================================================
	// Create Lambda Client
	// ============================================================================

	lambdaClient := terratest_aws.NewLambdaClient(t, awsRegion)

	// ============================================================================
	// Validate Scheduler Lambda Function
	// ============================================================================

	// Retrieve Scheduler Lambda function name from Terraform outputs
	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	require.NotEmpty(t, schedulerLambdaName, "Scheduler Lambda name should not be empty")

	// Get Scheduler Lambda function configuration
	schedulerConfig, err := lambdaClient.GetFunction(&lambda.GetFunctionInput{
		FunctionName: aws.String(schedulerLambdaName),
	})
	require.NoError(t, err, "Failed to get Scheduler Lambda function configuration")
	require.NotNil(t, schedulerConfig.Configuration, "Scheduler Lambda configuration should not be nil")

	// Validate runtime
	assert.Equal(t, "python3.11", *schedulerConfig.Configuration.Runtime, "Scheduler Lambda runtime should be python3.11")

	// Validate handler
	assert.Equal(t, "handler.handler", *schedulerConfig.Configuration.Handler, "Scheduler Lambda handler should be handler.handler")

	// Validate timeout (should be 300 seconds = 5 minutes)
	assert.Equal(t, int64(300), *schedulerConfig.Configuration.Timeout, "Scheduler Lambda timeout should be 300 seconds")

	// Validate memory size (should be at least 256 MB)
	assert.GreaterOrEqual(t, *schedulerConfig.Configuration.MemorySize, int64(256), "Scheduler Lambda memory should be at least 256 MB")

	// Validate IAM role is attached
	assert.NotEmpty(t, *schedulerConfig.Configuration.Role, "Scheduler Lambda should have an IAM role attached")
	assert.Contains(t, *schedulerConfig.Configuration.Role, "sp-autopilot-scheduler", "Scheduler Lambda role should contain expected role name")

	// Validate environment variables
	require.NotNil(t, schedulerConfig.Configuration.Environment, "Scheduler Lambda should have environment variables")
	require.NotNil(t, schedulerConfig.Configuration.Environment.Variables, "Scheduler Lambda environment variables should not be nil")

	env := schedulerConfig.Configuration.Environment.Variables

	// Validate critical environment variables exist
	assert.NotNil(t, env["QUEUE_URL"], "QUEUE_URL environment variable should exist")
	assert.NotNil(t, env["SNS_TOPIC_ARN"], "SNS_TOPIC_ARN environment variable should exist")
	assert.NotNil(t, env["DRY_RUN"], "DRY_RUN environment variable should exist")
	assert.NotNil(t, env["ENABLE_COMPUTE_SP"], "ENABLE_COMPUTE_SP environment variable should exist")
	assert.NotNil(t, env["ENABLE_DATABASE_SP"], "ENABLE_DATABASE_SP environment variable should exist")
	assert.NotNil(t, env["COVERAGE_TARGET_PERCENT"], "COVERAGE_TARGET_PERCENT environment variable should exist")
	assert.NotNil(t, env["MAX_PURCHASE_PERCENT"], "MAX_PURCHASE_PERCENT environment variable should exist")
	assert.NotNil(t, env["RENEWAL_WINDOW_DAYS"], "RENEWAL_WINDOW_DAYS environment variable should exist")
	assert.NotNil(t, env["LOOKBACK_DAYS"], "LOOKBACK_DAYS environment variable should exist")
	assert.NotNil(t, env["MIN_DATA_DAYS"], "MIN_DATA_DAYS environment variable should exist")
	assert.NotNil(t, env["MIN_COMMITMENT_PER_PLAN"], "MIN_COMMITMENT_PER_PLAN environment variable should exist")
	assert.NotNil(t, env["COMPUTE_SP_TERM_MIX"], "COMPUTE_SP_TERM_MIX environment variable should exist")
	assert.NotNil(t, env["COMPUTE_SP_PAYMENT_OPTION"], "COMPUTE_SP_PAYMENT_OPTION environment variable should exist")
	assert.NotNil(t, env["PARTIAL_UPFRONT_PERCENT"], "PARTIAL_UPFRONT_PERCENT environment variable should exist")

	// Validate environment variable values match input configuration
	assert.Equal(t, "true", *env["DRY_RUN"], "DRY_RUN should be 'true'")
	assert.Equal(t, "true", *env["ENABLE_COMPUTE_SP"], "ENABLE_COMPUTE_SP should be 'true'")
	assert.Equal(t, "true", *env["ENABLE_DATABASE_SP"], "ENABLE_DATABASE_SP should be 'true'")
	assert.Equal(t, "70", *env["COVERAGE_TARGET_PERCENT"], "COVERAGE_TARGET_PERCENT should be '70'")
	assert.Equal(t, "20", *env["MAX_PURCHASE_PERCENT"], "MAX_PURCHASE_PERCENT should be '20'")

	// Validate QUEUE_URL points to SQS queue
	assert.Contains(t, *env["QUEUE_URL"], "sp-autopilot-purchase-intents", "QUEUE_URL should contain queue name")
	assert.Contains(t, *env["QUEUE_URL"], "sqs", "QUEUE_URL should be an SQS URL")

	// Validate SNS_TOPIC_ARN is valid
	assert.Contains(t, *env["SNS_TOPIC_ARN"], "sp-autopilot-notifications", "SNS_TOPIC_ARN should contain topic name")
	assert.Contains(t, *env["SNS_TOPIC_ARN"], "sns", "SNS_TOPIC_ARN should be an SNS ARN")

	// ============================================================================
	// Validate Purchaser Lambda Function
	// ============================================================================

	// Retrieve Purchaser Lambda function name from Terraform outputs
	purchaserLambdaName := terraform.Output(t, terraformOptions, "purchaser_lambda_name")
	require.NotEmpty(t, purchaserLambdaName, "Purchaser Lambda name should not be empty")

	// Get Purchaser Lambda function configuration
	purchaserConfig, err := lambdaClient.GetFunction(&lambda.GetFunctionInput{
		FunctionName: aws.String(purchaserLambdaName),
	})
	require.NoError(t, err, "Failed to get Purchaser Lambda function configuration")
	require.NotNil(t, purchaserConfig.Configuration, "Purchaser Lambda configuration should not be nil")

	// Validate runtime
	assert.Equal(t, "python3.11", *purchaserConfig.Configuration.Runtime, "Purchaser Lambda runtime should be python3.11")

	// Validate handler
	assert.Equal(t, "handler.handler", *purchaserConfig.Configuration.Handler, "Purchaser Lambda handler should be handler.handler")

	// Validate timeout (should be 300 seconds = 5 minutes)
	assert.Equal(t, int64(300), *purchaserConfig.Configuration.Timeout, "Purchaser Lambda timeout should be 300 seconds")

	// Validate memory size (should be at least 256 MB)
	assert.GreaterOrEqual(t, *purchaserConfig.Configuration.MemorySize, int64(256), "Purchaser Lambda memory should be at least 256 MB")

	// Validate IAM role is attached
	assert.NotEmpty(t, *purchaserConfig.Configuration.Role, "Purchaser Lambda should have an IAM role attached")
	assert.Contains(t, *purchaserConfig.Configuration.Role, "sp-autopilot-purchaser", "Purchaser Lambda role should contain expected role name")

	// Validate environment variables
	require.NotNil(t, purchaserConfig.Configuration.Environment, "Purchaser Lambda should have environment variables")
	require.NotNil(t, purchaserConfig.Configuration.Environment.Variables, "Purchaser Lambda environment variables should not be nil")

	purchaserEnv := purchaserConfig.Configuration.Environment.Variables

	// Validate critical environment variables exist
	assert.NotNil(t, purchaserEnv["SNS_TOPIC_ARN"], "SNS_TOPIC_ARN environment variable should exist")
	assert.NotNil(t, purchaserEnv["DRY_RUN"], "DRY_RUN environment variable should exist")

	// Validate environment variable values
	assert.Equal(t, "true", *purchaserEnv["DRY_RUN"], "DRY_RUN should be 'true'")

	// Validate SNS_TOPIC_ARN is valid
	assert.Contains(t, *purchaserEnv["SNS_TOPIC_ARN"], "sp-autopilot-notifications", "SNS_TOPIC_ARN should contain topic name")
	assert.Contains(t, *purchaserEnv["SNS_TOPIC_ARN"], "sns", "SNS_TOPIC_ARN should be an SNS ARN")
}

// TestSchedulerLambdaInvocation validates that the Scheduler Lambda can be invoked
// successfully in dry-run mode and returns a valid response without queuing messages
func TestSchedulerLambdaInvocation(t *testing.T) {
	t.Parallel()

	// Retrieve AWS region from environment or default to us-east-1
	awsRegion := terratest_aws.GetRandomStableRegion(t, []string{"us-east-1", "us-west-2"}, nil)

	// Configure Terraform options
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Path to the Terraform code to test
		TerraformDir: "./fixtures/basic",

		// Variables to pass to the Terraform code
		Vars: map[string]interface{}{
			"aws_region":               awsRegion,
			"enable_compute_sp":        true,
			"enable_database_sp":       false,
			"coverage_target_percent":  90,
			"max_purchase_percent":     10,
			"dry_run":                  true,
			"notification_emails":      []string{"test@example.com"},
			"enable_lambda_error_alarm": true,
			"enable_dlq_alarm":          true,
		},

		// Disable colors in Terraform commands for cleaner test output
		NoColor: true,
	})

	// Ensure resources are destroyed at the end of the test
	defer terraform.Destroy(t, terraformOptions)

	// Initialize and apply Terraform
	terraform.InitAndApply(t, terraformOptions)

	// ============================================================================
	// Retrieve Lambda Function Name and Queue URL from Terraform Outputs
	// ============================================================================

	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	require.NotEmpty(t, schedulerLambdaName, "Scheduler Lambda name should not be empty")

	queueURL := terraform.Output(t, terraformOptions, "queue_url")
	require.NotEmpty(t, queueURL, "Queue URL should not be empty")

	// ============================================================================
	// Create AWS Clients
	// ============================================================================

	lambdaClient := terratest_aws.NewLambdaClient(t, awsRegion)
	sqsClient := terratest_aws.NewSqsClient(t, awsRegion)

	// ============================================================================
	// Get Queue Status Before Invocation
	// ============================================================================

	// Get initial queue message count
	queueAttrsBefore, err := sqsClient.GetQueueAttributes(&sqs.GetQueueAttributesInput{
		QueueUrl: aws.String(queueURL),
		AttributeNames: []*string{
			aws.String("ApproximateNumberOfMessages"),
		},
	})
	require.NoError(t, err, "Failed to get queue attributes before invocation")

	initialMessageCount, err := strconv.Atoi(*queueAttrsBefore.Attributes["ApproximateNumberOfMessages"])
	require.NoError(t, err, "Failed to parse initial message count")

	t.Logf("Initial queue message count: %d", initialMessageCount)

	// ============================================================================
	// Invoke Scheduler Lambda Function (Dry-Run Mode)
	// ============================================================================

	t.Log("Invoking Scheduler Lambda function with empty payload...")

	// Invoke Lambda with empty payload (matching the bash script pattern)
	invokeResult, err := lambdaClient.Invoke(&lambda.InvokeInput{
		FunctionName: aws.String(schedulerLambdaName),
		Payload:      []byte("{}"),
		LogType:      aws.String("Tail"), // Request execution logs
	})
	require.NoError(t, err, "Failed to invoke Scheduler Lambda function")

	// ============================================================================
	// Validate Invocation Result
	// ============================================================================

	// Validate invocation status code is 200
	assert.Equal(t, int64(200), *invokeResult.StatusCode, "Lambda invocation should return status code 200")

	// Validate no function error occurred
	assert.Nil(t, invokeResult.FunctionError, "Lambda invocation should not return a function error")

	// ============================================================================
	// Validate Response Payload
	// ============================================================================

	// Parse response payload as JSON
	var response map[string]interface{}
	err = json.Unmarshal(invokeResult.Payload, &response)
	require.NoError(t, err, "Failed to parse Lambda response as JSON")

	t.Logf("Lambda response: %+v", response)

	// Validate response contains expected fields
	assert.NotEmpty(t, response, "Lambda response should not be empty")

	// ============================================================================
	// Verify Dry-Run Mode: No Messages Queued to SQS
	// ============================================================================

	t.Log("Verifying that no messages were queued to SQS (dry-run mode)...")

	// Get queue message count after invocation
	queueAttrsAfter, err := sqsClient.GetQueueAttributes(&sqs.GetQueueAttributesInput{
		QueueUrl: aws.String(queueURL),
		AttributeNames: []*string{
			aws.String("ApproximateNumberOfMessages"),
		},
	})
	require.NoError(t, err, "Failed to get queue attributes after invocation")

	finalMessageCount, err := strconv.Atoi(*queueAttrsAfter.Attributes["ApproximateNumberOfMessages"])
	require.NoError(t, err, "Failed to parse final message count")

	t.Logf("Final queue message count: %d", finalMessageCount)

	// In dry-run mode, no messages should be queued
	assert.Equal(t, initialMessageCount, finalMessageCount, "In dry-run mode, no new messages should be queued to SQS")

	// ============================================================================
	// Validate Execution Logs
	// ============================================================================

	// The LogResult contains base64-encoded execution logs
	if invokeResult.LogResult != nil {
		// Note: We don't decode here since the logs are already available in CloudWatch
		// and the test focuses on invocation success
		t.Logf("Lambda execution logs are available (LogResult present)")
	}

	t.Log("✓ Scheduler Lambda invocation test completed successfully")
}

// TestLambdaIAMPermissions validates that Lambda functions have the correct
// IAM roles and policies attached with appropriate permissions
func TestLambdaIAMPermissions(t *testing.T) {
	t.Parallel()

	// Retrieve AWS region from environment or default to us-east-1
	awsRegion := terratest_aws.GetRandomStableRegion(t, []string{"us-east-1", "us-west-2"}, nil)

	// Configure Terraform options
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Path to the Terraform code to test
		TerraformDir: "./fixtures/basic",

		// Variables to pass to the Terraform code
		Vars: map[string]interface{}{
			"aws_region":          awsRegion,
			"enable_compute_sp":   true,
			"enable_database_sp":  true,
			"dry_run":             true,
			"notification_emails": []string{"test@example.com"},
		},

		// Disable colors in Terraform commands for cleaner test output
		NoColor: true,
	})

	// Ensure resources are destroyed at the end of the test
	defer terraform.Destroy(t, terraformOptions)

	// Initialize and apply Terraform
	terraform.InitAndApply(t, terraformOptions)

	// ============================================================================
	// Retrieve IAM Role ARNs from Terraform Outputs
	// ============================================================================

	schedulerRoleARN := terraform.Output(t, terraformOptions, "scheduler_role_arn")
	purchaserRoleARN := terraform.Output(t, terraformOptions, "purchaser_role_arn")

	require.NotEmpty(t, schedulerRoleARN, "Scheduler role ARN should not be empty")
	require.NotEmpty(t, purchaserRoleARN, "Purchaser role ARN should not be empty")

	// Extract role names from ARNs
	schedulerRoleName := extractRoleNameFromARN(schedulerRoleARN)
	purchaserRoleName := extractRoleNameFromARN(purchaserRoleARN)

	require.NotEmpty(t, schedulerRoleName, "Scheduler role name should not be empty")
	require.NotEmpty(t, purchaserRoleName, "Purchaser role name should not be empty")

	t.Logf("Scheduler Role Name: %s", schedulerRoleName)
	t.Logf("Purchaser Role Name: %s", purchaserRoleName)

	// ============================================================================
	// Create IAM Client
	// ============================================================================

	iamClient := terratest_aws.NewIamClient(t, awsRegion)

	// ============================================================================
	// Validate Scheduler Lambda IAM Role
	// ============================================================================

	t.Run("SchedulerLambdaIAMRole", func(t *testing.T) {
		// Get role details
		roleOutput, err := iamClient.GetRole(&iam.GetRoleInput{
			RoleName: aws.String(schedulerRoleName),
		})
		require.NoError(t, err, "Failed to get Scheduler IAM role")
		require.NotNil(t, roleOutput.Role, "Scheduler IAM role should not be nil")

		// Validate role name contains expected pattern
		assert.Contains(t, *roleOutput.Role.RoleName, "sp-autopilot-scheduler", "Scheduler role name should contain expected pattern")

		// Validate assume role policy (trust policy)
		assert.NotNil(t, roleOutput.Role.AssumeRolePolicyDocument, "Assume role policy should not be nil")

		// ============================================================================
		// Validate Scheduler Lambda Inline Policies
		// ============================================================================

		// List inline policies attached to the role
		listPoliciesOutput, err := iamClient.ListRolePolicies(&iam.ListRolePoliciesInput{
			RoleName: aws.String(schedulerRoleName),
		})
		require.NoError(t, err, "Failed to list Scheduler role policies")
		require.NotEmpty(t, listPoliciesOutput.PolicyNames, "Scheduler role should have inline policies")

		t.Logf("Scheduler role has %d inline policies", len(listPoliciesOutput.PolicyNames))

		// Expected inline policies for Scheduler Lambda
		expectedPolicies := []string{
			"cloudwatch-logs",
			"cost-explorer",
			"sqs",
			"sns",
			"savingsplans",
		}

		// Convert policy names to a map for easier lookup
		policyMap := make(map[string]bool)
		for _, policyName := range listPoliciesOutput.PolicyNames {
			policyMap[*policyName] = true
		}

		// Validate each expected policy exists
		for _, expectedPolicy := range expectedPolicies {
			assert.True(t, policyMap[expectedPolicy], "Scheduler role should have '%s' policy", expectedPolicy)
		}

		// ============================================================================
		// Validate CloudWatch Logs Policy Permissions
		// ============================================================================

		if policyMap["cloudwatch-logs"] {
			policyOutput, err := iamClient.GetRolePolicy(&iam.GetRolePolicyInput{
				RoleName:   aws.String(schedulerRoleName),
				PolicyName: aws.String("cloudwatch-logs"),
			})
			require.NoError(t, err, "Failed to get cloudwatch-logs policy")

			// Parse policy document
			policyDoc := parsePolicyDocument(t, policyOutput.PolicyDocument)

			// Validate policy has CloudWatch Logs permissions
			assert.True(t, hasPolicyAction(policyDoc, "logs:CreateLogStream"), "CloudWatch Logs policy should have logs:CreateLogStream permission")
			assert.True(t, hasPolicyAction(policyDoc, "logs:PutLogEvents"), "CloudWatch Logs policy should have logs:PutLogEvents permission")
		}

		// ============================================================================
		// Validate Cost Explorer Policy Permissions
		// ============================================================================

		if policyMap["cost-explorer"] {
			policyOutput, err := iamClient.GetRolePolicy(&iam.GetRolePolicyInput{
				RoleName:   aws.String(schedulerRoleName),
				PolicyName: aws.String("cost-explorer"),
			})
			require.NoError(t, err, "Failed to get cost-explorer policy")

			// Parse policy document
			policyDoc := parsePolicyDocument(t, policyOutput.PolicyDocument)

			// Validate policy has Cost Explorer permissions
			assert.True(t, hasPolicyAction(policyDoc, "ce:GetSavingsPlansPurchaseRecommendation"), "Cost Explorer policy should have ce:GetSavingsPlansPurchaseRecommendation permission")
			assert.True(t, hasPolicyAction(policyDoc, "ce:GetSavingsPlansUtilization"), "Cost Explorer policy should have ce:GetSavingsPlansUtilization permission")
			assert.True(t, hasPolicyAction(policyDoc, "ce:GetSavingsPlansCoverage"), "Cost Explorer policy should have ce:GetSavingsPlansCoverage permission")
			assert.True(t, hasPolicyAction(policyDoc, "ce:GetCostAndUsage"), "Cost Explorer policy should have ce:GetCostAndUsage permission")
		}

		// ============================================================================
		// Validate SQS Policy Permissions
		// ============================================================================

		if policyMap["sqs"] {
			policyOutput, err := iamClient.GetRolePolicy(&iam.GetRolePolicyInput{
				RoleName:   aws.String(schedulerRoleName),
				PolicyName: aws.String("sqs"),
			})
			require.NoError(t, err, "Failed to get sqs policy")

			// Parse policy document
			policyDoc := parsePolicyDocument(t, policyOutput.PolicyDocument)

			// Validate policy has SQS permissions for Scheduler (SendMessage, PurgeQueue, GetQueueAttributes)
			assert.True(t, hasPolicyAction(policyDoc, "sqs:SendMessage"), "SQS policy should have sqs:SendMessage permission")
			assert.True(t, hasPolicyAction(policyDoc, "sqs:PurgeQueue"), "SQS policy should have sqs:PurgeQueue permission")
			assert.True(t, hasPolicyAction(policyDoc, "sqs:GetQueueAttributes"), "SQS policy should have sqs:GetQueueAttributes permission")
		}

		// ============================================================================
		// Validate SNS Policy Permissions
		// ============================================================================

		if policyMap["sns"] {
			policyOutput, err := iamClient.GetRolePolicy(&iam.GetRolePolicyInput{
				RoleName:   aws.String(schedulerRoleName),
				PolicyName: aws.String("sns"),
			})
			require.NoError(t, err, "Failed to get sns policy")

			// Parse policy document
			policyDoc := parsePolicyDocument(t, policyOutput.PolicyDocument)

			// Validate policy has SNS permissions
			assert.True(t, hasPolicyAction(policyDoc, "sns:Publish"), "SNS policy should have sns:Publish permission")
		}

		// ============================================================================
		// Validate Savings Plans Policy Permissions
		// ============================================================================

		if policyMap["savingsplans"] {
			policyOutput, err := iamClient.GetRolePolicy(&iam.GetRolePolicyInput{
				RoleName:   aws.String(schedulerRoleName),
				PolicyName: aws.String("savingsplans"),
			})
			require.NoError(t, err, "Failed to get savingsplans policy")

			// Parse policy document
			policyDoc := parsePolicyDocument(t, policyOutput.PolicyDocument)

			// Validate policy has Savings Plans permissions for Scheduler (Describe operations only)
			assert.True(t, hasPolicyAction(policyDoc, "savingsplans:DescribeSavingsPlans"), "Savings Plans policy should have savingsplans:DescribeSavingsPlans permission")
			assert.True(t, hasPolicyAction(policyDoc, "savingsplans:DescribeSavingsPlansOfferingRates"), "Savings Plans policy should have savingsplans:DescribeSavingsPlansOfferingRates permission")
			assert.True(t, hasPolicyAction(policyDoc, "savingsplans:DescribeSavingsPlansOfferings"), "Savings Plans policy should have savingsplans:DescribeSavingsPlansOfferings permission")

			// Scheduler should NOT have CreateSavingsPlan permission
			assert.False(t, hasPolicyAction(policyDoc, "savingsplans:CreateSavingsPlan"), "Scheduler Savings Plans policy should NOT have savingsplans:CreateSavingsPlan permission")
		}
	})

	// ============================================================================
	// Validate Purchaser Lambda IAM Role
	// ============================================================================

	t.Run("PurchaserLambdaIAMRole", func(t *testing.T) {
		// Get role details
		roleOutput, err := iamClient.GetRole(&iam.GetRoleInput{
			RoleName: aws.String(purchaserRoleName),
		})
		require.NoError(t, err, "Failed to get Purchaser IAM role")
		require.NotNil(t, roleOutput.Role, "Purchaser IAM role should not be nil")

		// Validate role name contains expected pattern
		assert.Contains(t, *roleOutput.Role.RoleName, "sp-autopilot-purchaser", "Purchaser role name should contain expected pattern")

		// Validate assume role policy (trust policy)
		assert.NotNil(t, roleOutput.Role.AssumeRolePolicyDocument, "Assume role policy should not be nil")

		// ============================================================================
		// Validate Purchaser Lambda Inline Policies
		// ============================================================================

		// List inline policies attached to the role
		listPoliciesOutput, err := iamClient.ListRolePolicies(&iam.ListRolePoliciesInput{
			RoleName: aws.String(purchaserRoleName),
		})
		require.NoError(t, err, "Failed to list Purchaser role policies")
		require.NotEmpty(t, listPoliciesOutput.PolicyNames, "Purchaser role should have inline policies")

		t.Logf("Purchaser role has %d inline policies", len(listPoliciesOutput.PolicyNames))

		// Expected inline policies for Purchaser Lambda
		expectedPolicies := []string{
			"cloudwatch-logs",
			"cost-explorer",
			"sqs",
			"sns",
			"savingsplans",
		}

		// Convert policy names to a map for easier lookup
		policyMap := make(map[string]bool)
		for _, policyName := range listPoliciesOutput.PolicyNames {
			policyMap[*policyName] = true
		}

		// Validate each expected policy exists
		for _, expectedPolicy := range expectedPolicies {
			assert.True(t, policyMap[expectedPolicy], "Purchaser role should have '%s' policy", expectedPolicy)
		}

		// ============================================================================
		// Validate CloudWatch Logs Policy Permissions
		// ============================================================================

		if policyMap["cloudwatch-logs"] {
			policyOutput, err := iamClient.GetRolePolicy(&iam.GetRolePolicyInput{
				RoleName:   aws.String(purchaserRoleName),
				PolicyName: aws.String("cloudwatch-logs"),
			})
			require.NoError(t, err, "Failed to get cloudwatch-logs policy")

			// Parse policy document
			policyDoc := parsePolicyDocument(t, policyOutput.PolicyDocument)

			// Validate policy has CloudWatch Logs permissions
			assert.True(t, hasPolicyAction(policyDoc, "logs:CreateLogStream"), "CloudWatch Logs policy should have logs:CreateLogStream permission")
			assert.True(t, hasPolicyAction(policyDoc, "logs:PutLogEvents"), "CloudWatch Logs policy should have logs:PutLogEvents permission")
		}

		// ============================================================================
		// Validate Cost Explorer Policy Permissions
		// ============================================================================

		if policyMap["cost-explorer"] {
			policyOutput, err := iamClient.GetRolePolicy(&iam.GetRolePolicyInput{
				RoleName:   aws.String(purchaserRoleName),
				PolicyName: aws.String("cost-explorer"),
			})
			require.NoError(t, err, "Failed to get cost-explorer policy")

			// Parse policy document
			policyDoc := parsePolicyDocument(t, policyOutput.PolicyDocument)

			// Validate policy has Cost Explorer permissions
			assert.True(t, hasPolicyAction(policyDoc, "ce:GetSavingsPlansPurchaseRecommendation"), "Cost Explorer policy should have ce:GetSavingsPlansPurchaseRecommendation permission")
			assert.True(t, hasPolicyAction(policyDoc, "ce:GetSavingsPlansUtilization"), "Cost Explorer policy should have ce:GetSavingsPlansUtilization permission")
			assert.True(t, hasPolicyAction(policyDoc, "ce:GetSavingsPlansCoverage"), "Cost Explorer policy should have ce:GetSavingsPlansCoverage permission")
			assert.True(t, hasPolicyAction(policyDoc, "ce:GetCostAndUsage"), "Cost Explorer policy should have ce:GetCostAndUsage permission")
		}

		// ============================================================================
		// Validate SQS Policy Permissions
		// ============================================================================

		if policyMap["sqs"] {
			policyOutput, err := iamClient.GetRolePolicy(&iam.GetRolePolicyInput{
				RoleName:   aws.String(purchaserRoleName),
				PolicyName: aws.String("sqs"),
			})
			require.NoError(t, err, "Failed to get sqs policy")

			// Parse policy document
			policyDoc := parsePolicyDocument(t, policyOutput.PolicyDocument)

			// Validate policy has SQS permissions for Purchaser (ReceiveMessage, DeleteMessage, GetQueueAttributes)
			assert.True(t, hasPolicyAction(policyDoc, "sqs:ReceiveMessage"), "SQS policy should have sqs:ReceiveMessage permission")
			assert.True(t, hasPolicyAction(policyDoc, "sqs:DeleteMessage"), "SQS policy should have sqs:DeleteMessage permission")
			assert.True(t, hasPolicyAction(policyDoc, "sqs:GetQueueAttributes"), "SQS policy should have sqs:GetQueueAttributes permission")

			// Purchaser should NOT have SendMessage or PurgeQueue permissions
			assert.False(t, hasPolicyAction(policyDoc, "sqs:SendMessage"), "Purchaser SQS policy should NOT have sqs:SendMessage permission")
			assert.False(t, hasPolicyAction(policyDoc, "sqs:PurgeQueue"), "Purchaser SQS policy should NOT have sqs:PurgeQueue permission")
		}

		// ============================================================================
		// Validate SNS Policy Permissions
		// ============================================================================

		if policyMap["sns"] {
			policyOutput, err := iamClient.GetRolePolicy(&iam.GetRolePolicyInput{
				RoleName:   aws.String(purchaserRoleName),
				PolicyName: aws.String("sns"),
			})
			require.NoError(t, err, "Failed to get sns policy")

			// Parse policy document
			policyDoc := parsePolicyDocument(t, policyOutput.PolicyDocument)

			// Validate policy has SNS permissions
			assert.True(t, hasPolicyAction(policyDoc, "sns:Publish"), "SNS policy should have sns:Publish permission")
		}

		// ============================================================================
		// Validate Savings Plans Policy Permissions
		// ============================================================================

		if policyMap["savingsplans"] {
			policyOutput, err := iamClient.GetRolePolicy(&iam.GetRolePolicyInput{
				RoleName:   aws.String(purchaserRoleName),
				PolicyName: aws.String("savingsplans"),
			})
			require.NoError(t, err, "Failed to get savingsplans policy")

			// Parse policy document
			policyDoc := parsePolicyDocument(t, policyOutput.PolicyDocument)

			// Validate policy has Savings Plans permissions for Purchaser (includes CreateSavingsPlan)
			assert.True(t, hasPolicyAction(policyDoc, "savingsplans:DescribeSavingsPlans"), "Savings Plans policy should have savingsplans:DescribeSavingsPlans permission")
			assert.True(t, hasPolicyAction(policyDoc, "savingsplans:DescribeSavingsPlansOfferingRates"), "Savings Plans policy should have savingsplans:DescribeSavingsPlansOfferingRates permission")
			assert.True(t, hasPolicyAction(policyDoc, "savingsplans:DescribeSavingsPlansOfferings"), "Savings Plans policy should have savingsplans:DescribeSavingsPlansOfferings permission")
			assert.True(t, hasPolicyAction(policyDoc, "savingsplans:CreateSavingsPlan"), "Purchaser Savings Plans policy should have savingsplans:CreateSavingsPlan permission")
		}
	})

	t.Log("✓ Lambda IAM permissions validation completed successfully")
}

// ============================================================================
// Helper Functions for IAM Policy Testing
// ============================================================================

// extractRoleNameFromARN extracts the role name from an IAM role ARN
// Example: arn:aws:iam::123456789012:role/sp-autopilot-scheduler -> sp-autopilot-scheduler
func extractRoleNameFromARN(roleARN string) string {
	parts := strings.Split(roleARN, "/")
	if len(parts) > 0 {
		return parts[len(parts)-1]
	}
	return ""
}

// parsePolicyDocument parses a URL-encoded JSON policy document and returns it as a map
func parsePolicyDocument(t *testing.T, policyDocumentPtr *string) map[string]interface{} {
	require.NotNil(t, policyDocumentPtr, "Policy document should not be nil")

	// The policy document is URL-encoded JSON, need to decode it
	policyJSON := *policyDocumentPtr

	// URL decode the policy
	decodedPolicy := strings.ReplaceAll(policyJSON, "%22", "\"")
	decodedPolicy = strings.ReplaceAll(decodedPolicy, "%7B", "{")
	decodedPolicy = strings.ReplaceAll(decodedPolicy, "%7D", "}")
	decodedPolicy = strings.ReplaceAll(decodedPolicy, "%3A", ":")
	decodedPolicy = strings.ReplaceAll(decodedPolicy, "%2C", ",")
	decodedPolicy = strings.ReplaceAll(decodedPolicy, "%5B", "[")
	decodedPolicy = strings.ReplaceAll(decodedPolicy, "%5D", "]")

	var policyDoc map[string]interface{}
	err := json.Unmarshal([]byte(decodedPolicy), &policyDoc)
	require.NoError(t, err, "Failed to parse policy document JSON")

	return policyDoc
}

// hasPolicyAction checks if a policy document contains a specific action
func hasPolicyAction(policyDoc map[string]interface{}, action string) bool {
	statements, ok := policyDoc["Statement"].([]interface{})
	if !ok {
		return false
	}

	for _, stmt := range statements {
		statement, ok := stmt.(map[string]interface{})
		if !ok {
			continue
		}

		actions, ok := statement["Action"]
		if !ok {
			continue
		}

		// Action can be a string or an array of strings
		switch v := actions.(type) {
		case string:
			if v == action {
				return true
			}
		case []interface{}:
			for _, a := range v {
				if actionStr, ok := a.(string); ok && actionStr == action {
					return true
				}
			}
		}
	}

	return false
}

// TestEventBridgeSchedules validates EventBridge schedule configuration
// for both Scheduler and Purchaser Lambda functions
func TestEventBridgeSchedules(t *testing.T) {
	t.Parallel()

	// Retrieve AWS region from environment or default to us-east-1
	awsRegion := terratest_aws.GetRandomStableRegion(t, []string{"us-east-1", "us-west-2"}, nil)

	// Define custom schedule expressions for testing
	schedulerSchedule := "cron(0 8 1 * ? *)"  // 1st of month at 8:00 AM UTC
	purchaserSchedule := "cron(0 8 4 * ? *)"  // 4th of month at 8:00 AM UTC

	// Configure Terraform options
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Path to the Terraform code to test
		TerraformDir: "./fixtures/basic",

		// Variables to pass to the Terraform code
		Vars: map[string]interface{}{
			"aws_region":          awsRegion,
			"enable_compute_sp":   true,
			"enable_database_sp":  true,
			"dry_run":             true,
			"notification_emails": []string{"test@example.com"},
			"scheduler_schedule":  schedulerSchedule,
			"purchaser_schedule":  purchaserSchedule,
		},

		// Disable colors in Terraform commands for cleaner test output
		NoColor: true,
	})

	// Ensure resources are destroyed at the end of the test
	defer terraform.Destroy(t, terraformOptions)

	// Initialize and apply Terraform
	terraform.InitAndApply(t, terraformOptions)

	// ============================================================================
	// Retrieve EventBridge Rule Information from Terraform Outputs
	// ============================================================================

	schedulerRuleName := terraform.Output(t, terraformOptions, "scheduler_rule_name")
	purchaserRuleName := terraform.Output(t, terraformOptions, "purchaser_rule_name")
	schedulerRuleARN := terraform.Output(t, terraformOptions, "scheduler_rule_arn")
	purchaserRuleARN := terraform.Output(t, terraformOptions, "purchaser_rule_arn")

	// Validate rule names and ARNs are not empty
	require.NotEmpty(t, schedulerRuleName, "Scheduler rule name should not be empty")
	require.NotEmpty(t, purchaserRuleName, "Purchaser rule name should not be empty")
	require.NotEmpty(t, schedulerRuleARN, "Scheduler rule ARN should not be empty")
	require.NotEmpty(t, purchaserRuleARN, "Purchaser rule ARN should not be empty")

	// ============================================================================
	// Create CloudWatch Events Client
	// ============================================================================

	sess, err := terratest_aws.NewAuthenticatedSession(awsRegion)
	require.NoError(t, err, "Failed to create AWS session")

	eventsClient := cloudwatchevents.New(sess)

	// ============================================================================
	// Validate Scheduler EventBridge Rule
	// ============================================================================

	// Describe Scheduler rule
	schedulerRuleOutput, err := eventsClient.DescribeRule(&cloudwatchevents.DescribeRuleInput{
		Name: aws.String(schedulerRuleName),
	})
	require.NoError(t, err, "Failed to describe Scheduler EventBridge rule")

	// Validate Scheduler rule attributes
	assert.Equal(t, "ENABLED", *schedulerRuleOutput.State, "Scheduler rule should be ENABLED")
	assert.Equal(t, schedulerSchedule, *schedulerRuleOutput.ScheduleExpression, "Scheduler rule should have correct schedule expression")
	assert.Contains(t, *schedulerRuleOutput.Description, "Scheduler Lambda", "Scheduler rule description should mention Scheduler Lambda")
	assert.Equal(t, schedulerRuleName, *schedulerRuleOutput.Name, "Scheduler rule name should match")

	// Validate Scheduler rule targets
	schedulerTargetsOutput, err := eventsClient.ListTargetsByRule(&cloudwatchevents.ListTargetsByRuleInput{
		Rule: aws.String(schedulerRuleName),
	})
	require.NoError(t, err, "Failed to list targets for Scheduler EventBridge rule")
	require.Len(t, schedulerTargetsOutput.Targets, 1, "Scheduler rule should have exactly 1 target")

	// Validate Scheduler target is the Scheduler Lambda
	schedulerTarget := schedulerTargetsOutput.Targets[0]
	assert.Equal(t, "SchedulerLambda", *schedulerTarget.Id, "Scheduler target ID should be 'SchedulerLambda'")
	assert.Contains(t, *schedulerTarget.Arn, "sp-autopilot-scheduler", "Scheduler target ARN should reference the Scheduler Lambda")

	// ============================================================================
	// Validate Purchaser EventBridge Rule
	// ============================================================================

	// Describe Purchaser rule
	purchaserRuleOutput, err := eventsClient.DescribeRule(&cloudwatchevents.DescribeRuleInput{
		Name: aws.String(purchaserRuleName),
	})
	require.NoError(t, err, "Failed to describe Purchaser EventBridge rule")

	// Validate Purchaser rule attributes
	assert.Equal(t, "ENABLED", *purchaserRuleOutput.State, "Purchaser rule should be ENABLED")
	assert.Equal(t, purchaserSchedule, *purchaserRuleOutput.ScheduleExpression, "Purchaser rule should have correct schedule expression")
	assert.Contains(t, *purchaserRuleOutput.Description, "Purchaser Lambda", "Purchaser rule description should mention Purchaser Lambda")
	assert.Equal(t, purchaserRuleName, *purchaserRuleOutput.Name, "Purchaser rule name should match")

	// Validate Purchaser rule targets
	purchaserTargetsOutput, err := eventsClient.ListTargetsByRule(&cloudwatchevents.ListTargetsByRuleInput{
		Rule: aws.String(purchaserRuleName),
	})
	require.NoError(t, err, "Failed to list targets for Purchaser EventBridge rule")
	require.Len(t, purchaserTargetsOutput.Targets, 1, "Purchaser rule should have exactly 1 target")

	// Validate Purchaser target is the Purchaser Lambda
	purchaserTarget := purchaserTargetsOutput.Targets[0]
	assert.Equal(t, "PurchaserLambda", *purchaserTarget.Id, "Purchaser target ID should be 'PurchaserLambda'")
	assert.Contains(t, *purchaserTarget.Arn, "sp-autopilot-purchaser", "Purchaser target ARN should reference the Purchaser Lambda")

	// ============================================================================
	// Validate Schedule Expressions Format
	// ============================================================================

	// Both schedules should use cron expressions
	assert.True(t, strings.HasPrefix(schedulerSchedule, "cron("), "Scheduler schedule should be a cron expression")
	assert.True(t, strings.HasPrefix(purchaserSchedule, "cron("), "Purchaser schedule should be a cron expression")

	// Validate schedules are different (to avoid concurrent execution)
	assert.NotEqual(t, schedulerSchedule, purchaserSchedule, "Scheduler and Purchaser schedules should be different")
}

// TestFullDeploymentAndCleanup validates the complete deployment lifecycle:
// deployment, resource validation, Lambda invocation, and cleanup
// This is a comprehensive end-to-end integration test
func TestFullDeploymentAndCleanup(t *testing.T) {
	// Note: NOT using t.Parallel() for this end-to-end integration test
	// to ensure complete lifecycle validation

	// Retrieve AWS region from environment or default to us-east-1
	awsRegion := terratest_aws.GetRandomStableRegion(t, []string{"us-east-1", "us-west-2"}, nil)

	// Configure Terraform options with comprehensive settings
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Path to the Terraform code to test
		TerraformDir: "./fixtures/basic",

		// Variables to pass to the Terraform code
		Vars: map[string]interface{}{
			"aws_region":                awsRegion,
			"enable_compute_sp":         true,
			"enable_database_sp":        true,
			"coverage_target_percent":   80,
			"max_purchase_percent":      15,
			"dry_run":                   true,
			"notification_emails":       []string{"e2e-test@example.com"},
			"enable_lambda_error_alarm": true,
			"enable_dlq_alarm":          true,
			"scheduler_schedule":        "cron(0 9 1 * ? *)",
			"purchaser_schedule":        "cron(0 9 5 * ? *)",
		},

		// Disable colors in Terraform commands for cleaner test output
		NoColor: true,
	})

	// Ensure resources are destroyed at the end of the test
	defer terraform.Destroy(t, terraformOptions)

	t.Log("========================================")
	t.Log("Phase 1: Infrastructure Deployment")
	t.Log("========================================")

	// Initialize and apply Terraform
	terraform.InitAndApply(t, terraformOptions)

	t.Log("✓ Infrastructure deployed successfully")

	// ============================================================================
	// Phase 2: Comprehensive Resource Validation
	// ============================================================================

	t.Log("========================================")
	t.Log("Phase 2: Resource Validation")
	t.Log("========================================")

	// ============================================================================
	// Validate SQS Queues
	// ============================================================================

	t.Log("Validating SQS queues...")

	queueURL := terraform.Output(t, terraformOptions, "queue_url")
	dlqURL := terraform.Output(t, terraformOptions, "dlq_url")
	queueARN := terraform.Output(t, terraformOptions, "queue_arn")
	dlqARN := terraform.Output(t, terraformOptions, "dlq_arn")

	// Validate queue outputs
	require.NotEmpty(t, queueURL, "Main SQS queue URL should not be empty")
	require.NotEmpty(t, dlqURL, "DLQ URL should not be empty")
	require.NotEmpty(t, queueARN, "Queue ARN should not be empty")
	require.NotEmpty(t, dlqARN, "DLQ ARN should not be empty")

	assert.Contains(t, queueURL, "sp-autopilot-purchase-intents", "Queue URL should contain expected queue name")
	assert.Contains(t, dlqURL, "sp-autopilot-purchase-intents-dlq", "DLQ URL should contain expected queue name")

	t.Log("✓ SQS queues validated")

	// ============================================================================
	// Validate SNS Topic
	// ============================================================================

	t.Log("Validating SNS topic...")

	snsTopicARN := terraform.Output(t, terraformOptions, "sns_topic_arn")
	require.NotEmpty(t, snsTopicARN, "SNS topic ARN should not be empty")
	assert.Contains(t, snsTopicARN, "sp-autopilot-notifications", "SNS topic ARN should contain expected topic name")

	t.Log("✓ SNS topic validated")

	// ============================================================================
	// Validate Lambda Functions
	// ============================================================================

	t.Log("Validating Lambda functions...")

	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	purchaserLambdaName := terraform.Output(t, terraformOptions, "purchaser_lambda_name")
	schedulerLambdaARN := terraform.Output(t, terraformOptions, "scheduler_lambda_arn")
	purchaserLambdaARN := terraform.Output(t, terraformOptions, "purchaser_lambda_arn")

	require.NotEmpty(t, schedulerLambdaName, "Scheduler Lambda name should not be empty")
	require.NotEmpty(t, purchaserLambdaName, "Purchaser Lambda name should not be empty")
	require.NotEmpty(t, schedulerLambdaARN, "Scheduler Lambda ARN should not be empty")
	require.NotEmpty(t, purchaserLambdaARN, "Purchaser Lambda ARN should not be empty")

	assert.Contains(t, schedulerLambdaName, "sp-autopilot-scheduler", "Scheduler Lambda name should contain expected function name")
	assert.Contains(t, purchaserLambdaName, "sp-autopilot-purchaser", "Purchaser Lambda name should contain expected function name")

	// Validate Lambda function configuration
	lambdaClient := terratest_aws.NewLambdaClient(t, awsRegion)

	schedulerConfig, err := lambdaClient.GetFunction(&lambda.GetFunctionInput{
		FunctionName: aws.String(schedulerLambdaName),
	})
	require.NoError(t, err, "Failed to get Scheduler Lambda function configuration")
	require.NotNil(t, schedulerConfig.Configuration, "Scheduler Lambda configuration should not be nil")

	assert.Equal(t, "python3.11", *schedulerConfig.Configuration.Runtime, "Scheduler Lambda runtime should be python3.11")
	assert.Equal(t, "handler.handler", *schedulerConfig.Configuration.Handler, "Scheduler Lambda handler should be handler.handler")
	assert.Equal(t, int64(300), *schedulerConfig.Configuration.Timeout, "Scheduler Lambda timeout should be 300 seconds")

	t.Log("✓ Lambda functions validated")

	// ============================================================================
	// Validate IAM Roles
	// ============================================================================

	t.Log("Validating IAM roles...")

	schedulerRoleARN := terraform.Output(t, terraformOptions, "scheduler_role_arn")
	purchaserRoleARN := terraform.Output(t, terraformOptions, "purchaser_role_arn")

	require.NotEmpty(t, schedulerRoleARN, "Scheduler Lambda role ARN should not be empty")
	require.NotEmpty(t, purchaserRoleARN, "Purchaser Lambda role ARN should not be empty")

	assert.Contains(t, schedulerRoleARN, "sp-autopilot-scheduler", "Scheduler role ARN should contain expected role name")
	assert.Contains(t, purchaserRoleARN, "sp-autopilot-purchaser", "Purchaser role ARN should contain expected role name")

	t.Log("✓ IAM roles validated")

	// ============================================================================
	// Validate EventBridge Rules
	// ============================================================================

	t.Log("Validating EventBridge rules...")

	schedulerRuleName := terraform.Output(t, terraformOptions, "scheduler_rule_name")
	purchaserRuleName := terraform.Output(t, terraformOptions, "purchaser_rule_name")
	schedulerRuleARN := terraform.Output(t, terraformOptions, "scheduler_rule_arn")
	purchaserRuleARN := terraform.Output(t, terraformOptions, "purchaser_rule_arn")

	require.NotEmpty(t, schedulerRuleName, "Scheduler EventBridge rule name should not be empty")
	require.NotEmpty(t, purchaserRuleName, "Purchaser EventBridge rule name should not be empty")
	require.NotEmpty(t, schedulerRuleARN, "Scheduler rule ARN should not be empty")
	require.NotEmpty(t, purchaserRuleARN, "Purchaser rule ARN should not be empty")

	assert.Contains(t, schedulerRuleName, "sp-autopilot-scheduler", "Scheduler rule name should contain expected rule name")
	assert.Contains(t, purchaserRuleName, "sp-autopilot-purchaser", "Purchaser rule name should contain expected rule name")

	// Validate EventBridge rule details
	sess, err := terratest_aws.NewAuthenticatedSession(awsRegion)
	require.NoError(t, err, "Failed to create AWS session")

	eventsClient := cloudwatchevents.New(sess)

	schedulerRuleOutput, err := eventsClient.DescribeRule(&cloudwatchevents.DescribeRuleInput{
		Name: aws.String(schedulerRuleName),
	})
	require.NoError(t, err, "Failed to describe Scheduler EventBridge rule")
	assert.Equal(t, "ENABLED", *schedulerRuleOutput.State, "Scheduler rule should be ENABLED")

	purchaserRuleOutput, err := eventsClient.DescribeRule(&cloudwatchevents.DescribeRuleInput{
		Name: aws.String(purchaserRuleName),
	})
	require.NoError(t, err, "Failed to describe Purchaser EventBridge rule")
	assert.Equal(t, "ENABLED", *purchaserRuleOutput.State, "Purchaser rule should be ENABLED")

	t.Log("✓ EventBridge rules validated")

	// ============================================================================
	// Validate CloudWatch Alarms
	// ============================================================================

	t.Log("Validating CloudWatch alarms...")

	schedulerErrorAlarmARN := terraform.Output(t, terraformOptions, "scheduler_error_alarm_arn")
	purchaserErrorAlarmARN := terraform.Output(t, terraformOptions, "purchaser_error_alarm_arn")
	dlqAlarmARN := terraform.Output(t, terraformOptions, "dlq_alarm_arn")

	require.NotEmpty(t, schedulerErrorAlarmARN, "Scheduler error alarm ARN should not be empty")
	require.NotEmpty(t, purchaserErrorAlarmARN, "Purchaser error alarm ARN should not be empty")
	require.NotEmpty(t, dlqAlarmARN, "DLQ alarm ARN should not be empty")

	t.Log("✓ CloudWatch alarms validated")

	// ============================================================================
	// Validate Module Configuration
	// ============================================================================

	t.Log("Validating module configuration...")

	moduleConfig := terraform.OutputMap(t, terraformOptions, "module_configuration")
	require.NotEmpty(t, moduleConfig, "Module configuration should not be empty")

	assert.Equal(t, "true", moduleConfig["enable_compute_sp"], "Compute SP should be enabled")
	assert.Equal(t, "true", moduleConfig["enable_database_sp"], "Database SP should be enabled")
	assert.Equal(t, "true", moduleConfig["dry_run"], "Dry run should be enabled")

	t.Log("✓ Module configuration validated")

	// ============================================================================
	// Phase 3: End-to-End Functional Testing
	// ============================================================================

	t.Log("========================================")
	t.Log("Phase 3: Functional Testing")
	t.Log("========================================")

	// Get initial queue state
	sqsClient := terratest_aws.NewSqsClient(t, awsRegion)

	queueAttrsBefore, err := sqsClient.GetQueueAttributes(&sqs.GetQueueAttributesInput{
		QueueUrl: aws.String(queueURL),
		AttributeNames: []*string{
			aws.String("ApproximateNumberOfMessages"),
		},
	})
	require.NoError(t, err, "Failed to get queue attributes before invocation")

	initialMessageCount, err := strconv.Atoi(*queueAttrsBefore.Attributes["ApproximateNumberOfMessages"])
	require.NoError(t, err, "Failed to parse initial message count")

	t.Logf("Initial SQS queue message count: %d", initialMessageCount)

	// Invoke Scheduler Lambda function
	t.Log("Invoking Scheduler Lambda function...")

	invokeResult, err := lambdaClient.Invoke(&lambda.InvokeInput{
		FunctionName: aws.String(schedulerLambdaName),
		Payload:      []byte("{}"),
		LogType:      aws.String("Tail"),
	})
	require.NoError(t, err, "Failed to invoke Scheduler Lambda function")

	// Validate invocation result
	assert.Equal(t, int64(200), *invokeResult.StatusCode, "Lambda invocation should return status code 200")
	assert.Nil(t, invokeResult.FunctionError, "Lambda invocation should not return a function error")

	// Parse response payload
	var response map[string]interface{}
	err = json.Unmarshal(invokeResult.Payload, &response)
	require.NoError(t, err, "Failed to parse Lambda response as JSON")

	t.Logf("Lambda response: %+v", response)
	assert.NotEmpty(t, response, "Lambda response should not be empty")

	t.Log("✓ Scheduler Lambda invoked successfully")

	// Verify dry-run mode: no messages queued
	t.Log("Verifying dry-run mode (no messages should be queued)...")

	queueAttrsAfter, err := sqsClient.GetQueueAttributes(&sqs.GetQueueAttributesInput{
		QueueUrl: aws.String(queueURL),
		AttributeNames: []*string{
			aws.String("ApproximateNumberOfMessages"),
		},
	})
	require.NoError(t, err, "Failed to get queue attributes after invocation")

	finalMessageCount, err := strconv.Atoi(*queueAttrsAfter.Attributes["ApproximateNumberOfMessages"])
	require.NoError(t, err, "Failed to parse final message count")

	t.Logf("Final SQS queue message count: %d", finalMessageCount)

	// In dry-run mode, no messages should be queued
	assert.Equal(t, initialMessageCount, finalMessageCount, "In dry-run mode, no new messages should be queued to SQS")

	t.Log("✓ Dry-run mode verified (no side effects)")

	// ============================================================================
	// Phase 4: Cleanup Validation
	// ============================================================================

	t.Log("========================================")
	t.Log("Phase 4: Cleanup Validation")
	t.Log("========================================")

	// The defer statement will handle cleanup automatically
	// Validate that we have all resource identifiers needed for cleanup
	t.Log("Verifying all resource identifiers are available for cleanup...")

	resourceIdentifiers := map[string]string{
		"Queue URL":                   queueURL,
		"DLQ URL":                     dlqURL,
		"SNS Topic ARN":               snsTopicARN,
		"Scheduler Lambda Name":       schedulerLambdaName,
		"Purchaser Lambda Name":       purchaserLambdaName,
		"Scheduler Role ARN":          schedulerRoleARN,
		"Purchaser Role ARN":          purchaserRoleARN,
		"Scheduler EventBridge Rule":  schedulerRuleName,
		"Purchaser EventBridge Rule":  purchaserRuleName,
		"Scheduler Error Alarm ARN":   schedulerErrorAlarmARN,
		"Purchaser Error Alarm ARN":   purchaserErrorAlarmARN,
		"DLQ Alarm ARN":               dlqAlarmARN,
	}

	for resourceType, identifier := range resourceIdentifiers {
		assert.NotEmpty(t, identifier, "%s should not be empty for cleanup", resourceType)
	}

	t.Log("✓ All resource identifiers verified")
	t.Log("✓ Cleanup will be handled by defer terraform.Destroy()")

	// ============================================================================
	// Test Summary
	// ============================================================================

	t.Log("========================================")
	t.Log("End-to-End Test Summary")
	t.Log("========================================")
	t.Log("✓ Phase 1: Infrastructure deployment - SUCCESS")
	t.Log("✓ Phase 2: Resource validation - SUCCESS")
	t.Log("  - SQS queues (main queue and DLQ)")
	t.Log("  - SNS topic and subscriptions")
	t.Log("  - Lambda functions (scheduler and purchaser)")
	t.Log("  - IAM roles and policies")
	t.Log("  - EventBridge schedules")
	t.Log("  - CloudWatch alarms")
	t.Log("  - Module configuration")
	t.Log("✓ Phase 3: Functional testing - SUCCESS")
	t.Log("  - Scheduler Lambda invocation")
	t.Log("  - Dry-run mode verification")
	t.Log("✓ Phase 4: Cleanup validation - SUCCESS")
	t.Log("  - All resource identifiers available")
	t.Log("  - Cleanup will be performed automatically")
	t.Log("========================================")
	t.Log("✓ Full deployment and cleanup test completed successfully")
	t.Log("========================================")
}

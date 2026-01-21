package test

import (
	"encoding/json"
	"fmt"
	"strconv"
	"testing"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/cloudwatchevents"
	"github.com/aws/aws-sdk-go/service/lambda"
	"github.com/aws/aws-sdk-go/service/sqs"
	terratest_aws "github.com/gruntwork-io/terratest/modules/aws"
	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestFullDeploymentAndCleanup is a comprehensive end-to-end integration test
// that validates complete module deployment, resource configuration, functional
// behavior, and automatic cleanup.
//
// Test Phases:
// 1. Infrastructure Deployment - Apply Terraform and create all resources
// 2. Resource Validation - Verify SQS, SNS, Lambda, IAM, EventBridge, CloudWatch
// 3. Functional Testing - Invoke Lambda and verify dry-run behavior
// 4. Cleanup Validation - Ensure all resources can be destroyed
func TestFullDeploymentAndCleanup(t *testing.T) {
	// Note: NOT using t.Parallel() for this end-to-end integration test
	// to ensure complete lifecycle validation

	// Use us-east-1 as required by IAM policy region restriction
	// The GitHub Actions IAM policy only allows operations in us-east-1
	awsRegion := "us-east-1"

	// Generate unique name prefix using timestamp to avoid collisions between test runs
	// Format: sp-autopilot-test-YYYYMMDD-HHMMSS (e.g., sp-autopilot-test-20260117-143055)
	uniquePrefix := fmt.Sprintf("sp-autopilot-test-%s", time.Now().Format("20060102-150405"))
	t.Logf("Using unique name prefix: %s", uniquePrefix)
	t.Log("Note: Orphaned resources from previous runs should be cleaned by TestCleanupAllOrphanedResources")

	// Configure Terraform options with comprehensive settings
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Path to the Terraform code to test
		TerraformDir: "./fixtures/basic",

		// Use clean logger to avoid verbose prefixes
		Logger: getCleanLogger(),

		// Variables to pass to the Terraform code (v2.0 nested structure)
		Vars: map[string]interface{}{
			"aws_region":  awsRegion,
			"name_prefix": uniquePrefix,
			// Purchase strategy configuration
			"purchase_strategy": map[string]interface{}{
				"coverage_target_percent": 80,
				"max_coverage_cap":        95,
			"granularity":             "DAILY", // Use DAILY for test compatibility
				"fixed": map[string]interface{}{
					"max_purchase_percent": 15,
				},
			},
			// Savings Plans configuration
			"sp_plans": map[string]interface{}{
				"compute": map[string]interface{}{
					"enabled":   true,
					"plan_type": "all_upfront_one_year",
				},
				"database": map[string]interface{}{
					"enabled":   true,
					"plan_type": "no_upfront_one_year",
				},
				"sagemaker": map[string]interface{}{
					"enabled": false,
				},
			},
			// EventBridge schedules - SAFETY: far future to prevent accidental triggers
			"scheduler": map[string]interface{}{
				"scheduler": "cron(0 0 1 1 ? 2099)", // Jan 1, 2099 - will never trigger
				"purchaser": "cron(0 0 1 1 ? 2099)", // Jan 1, 2099 - will never trigger
				"reporter":  "cron(0 0 1 1 ? 2099)", // Jan 1, 2099 - will never trigger
			},
			// Notification configuration
			"notifications": map[string]interface{}{
				"emails": []string{"e2e-test@example.com"},
			},
			// Monitoring configuration
			"monitoring": map[string]interface{}{
				"dlq_alarm": true,
			},
			// Lambda configuration with dry-run and error alarms
			"lambda_config": map[string]interface{}{
				"scheduler": map[string]interface{}{
					"dry_run":     true,
					"error_alarm": true,
				},
				"purchaser": map[string]interface{}{
					"error_alarm": true,
				},
				"reporter": map[string]interface{}{
					"error_alarm": true,
				},
			},
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

	assert.Contains(t, queueURL, uniquePrefix+"-purchase-intents", "Queue URL should contain expected queue name")
	assert.Contains(t, dlqURL, uniquePrefix+"-purchase-intents-dlq", "DLQ URL should contain expected queue name")

	t.Log("✓ SQS queues validated")

	// ============================================================================
	// Validate SNS Topic
	// ============================================================================

	t.Log("Validating SNS topic...")

	snsTopicARN := terraform.Output(t, terraformOptions, "sns_topic_arn")
	require.NotEmpty(t, snsTopicARN, "SNS topic ARN should not be empty")
	assert.Contains(t, snsTopicARN, uniquePrefix+"-notifications", "SNS topic ARN should contain expected topic name")

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

	assert.Contains(t, schedulerLambdaName, uniquePrefix+"-scheduler", "Scheduler Lambda name should contain expected function name")
	assert.Contains(t, purchaserLambdaName, uniquePrefix+"-purchaser", "Purchaser Lambda name should contain expected function name")

	// Validate Lambda function configuration
	lambdaClient := terratest_aws.NewLambdaClient(t, awsRegion)

	schedulerConfig, err := lambdaClient.GetFunction(&lambda.GetFunctionInput{
		FunctionName: aws.String(schedulerLambdaName),
	})
	require.NoError(t, err, "Failed to get Scheduler Lambda function configuration")
	require.NotNil(t, schedulerConfig.Configuration, "Scheduler Lambda configuration should not be nil")

	assert.Equal(t, "python3.14", *schedulerConfig.Configuration.Runtime, "Scheduler Lambda runtime should be python3.14")
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

	assert.Contains(t, schedulerRoleARN, uniquePrefix+"-scheduler", "Scheduler role ARN should contain expected role name")
	assert.Contains(t, purchaserRoleARN, uniquePrefix+"-purchaser", "Purchaser role ARN should contain expected role name")

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

	assert.Contains(t, schedulerRuleName, uniquePrefix+"-scheduler", "Scheduler rule name should contain expected rule name")
	assert.Contains(t, purchaserRuleName, uniquePrefix+"-purchaser", "Purchaser rule name should contain expected rule name")

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
	reporterErrorAlarmARN := terraform.Output(t, terraformOptions, "reporter_error_alarm_arn")
	dlqAlarmARN := terraform.Output(t, terraformOptions, "dlq_alarm_arn")

	require.NotEmpty(t, schedulerErrorAlarmARN, "Scheduler error alarm ARN should not be empty")
	require.NotEmpty(t, purchaserErrorAlarmARN, "Purchaser error alarm ARN should not be empty")
	require.NotEmpty(t, reporterErrorAlarmARN, "Reporter error alarm ARN should not be empty")
	require.NotEmpty(t, dlqAlarmARN, "DLQ alarm ARN should not be empty")

	t.Log("✓ CloudWatch alarms validated")

	// ============================================================================
	// Validate Module Configuration
	// ============================================================================

	t.Log("Validating module configuration...")

	moduleConfig := terraform.OutputMap(t, terraformOptions, "module_configuration")
	require.NotEmpty(t, moduleConfig, "Module configuration should not be empty")

	assert.Equal(t, "true", moduleConfig["compute_sp_enabled"], "Compute SP should be enabled")
	assert.Equal(t, "true", moduleConfig["database_sp_enabled"], "Database SP should be enabled")
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
		"Reporter Error Alarm ARN":    reporterErrorAlarmARN,
		"DLQ Alarm ARN":               dlqAlarmARN,
	}

	for name, identifier := range resourceIdentifiers {
		assert.NotEmpty(t, identifier, "%s should not be empty for cleanup", name)
	}

	t.Log("✓ All resource identifiers validated for cleanup")

	t.Log("========================================")
	t.Log("Test Complete - Cleanup Will Run via defer")
	t.Log("========================================")

	// Note: terraform.Destroy() will be called automatically via defer
	// when this function exits, ensuring all AWS resources are cleaned up
}

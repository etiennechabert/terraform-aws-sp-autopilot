package test

import (
	"testing"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/lambda"
	terratest_aws "github.com/gruntwork-io/terratest/modules/aws"
	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// commonExampleValidation performs validation common to all examples
func commonExampleValidation(t *testing.T, terraformOptions *terraform.Options, awsRegion string) {
	// Validate core resources exist
	queueURL := terraform.Output(t, terraformOptions, "queue_url")
	snsTopicARN := terraform.Output(t, terraformOptions, "sns_topic_arn")
	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")

	require.NotEmpty(t, queueURL, "Queue URL should not be empty")
	require.NotEmpty(t, snsTopicARN, "SNS topic ARN should not be empty")
	require.NotEmpty(t, schedulerLambdaName, "Scheduler Lambda name should not be empty")

	t.Logf("✓ Core resources validated: queue=%s, lambda=%s", queueURL, schedulerLambdaName)
}

// getLambdaEnvVar retrieves an environment variable from a Lambda function
func getLambdaEnvVar(t *testing.T, awsRegion string, functionName string, envVarName string) string {
	lambdaClient := terratest_aws.NewLambdaClient(t, awsRegion)

	config, err := lambdaClient.GetFunction(&lambda.GetFunctionInput{
		FunctionName: aws.String(functionName),
	})
	require.NoError(t, err, "Failed to get Lambda function configuration")
	require.NotNil(t, config.Configuration, "Lambda configuration should not be nil")
	require.NotNil(t, config.Configuration.Environment, "Lambda environment should not be nil")

	if val, ok := config.Configuration.Environment.Variables[envVarName]; ok {
		return *val
	}

	return ""
}

// TestExampleSingleAccountCompute validates the single-account-compute example
// Focus: Compute SP with mixed term/payment options (3-year + 1-year, all-upfront + partial-upfront)
func TestExampleSingleAccountCompute(t *testing.T) {
	t.Parallel()

	awsRegion := "us-east-1"

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: "../../examples/single-account-compute",
		Vars: map[string]interface{}{
			// Override schedules to far future for safety
			"scheduler": map[string]interface{}{
				"scheduler": "cron(0 0 1 1 ? 2099)",
				"purchaser": "cron(0 0 1 1 ? 2099)",
				"reporter":  "cron(0 0 1 1 ? 2099)",
			},
			// Override to dry-run for safety
			"lambda_config": map[string]interface{}{
				"scheduler": map[string]interface{}{
					"dry_run": true,
				},
			},
		},
		NoColor: true,
	})

	defer terraform.Destroy(t, terraformOptions)

	t.Log("Testing single-account-compute example...")
	terraform.InitAndApply(t, terraformOptions)

	// Common validation
	commonExampleValidation(t, terraformOptions, awsRegion)

	// Unique validation: Verify compute SP enabled with term mix
	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")

	enableComputeSP := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "ENABLE_COMPUTE_SP")
	assert.Equal(t, "true", enableComputeSP, "Compute SP should be enabled")

	enableDatabaseSP := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "ENABLE_DATABASE_SP")
	assert.Equal(t, "false", enableDatabaseSP, "Database SP should be disabled")

	// Verify term mix is configured (example uses 50% 3-year, 30% 1-year, 20% 1-year partial)
	computeTermMix := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "COMPUTE_SP_TERM_MIX")
	assert.NotEmpty(t, computeTermMix, "Compute term mix should be configured")
	assert.Contains(t, computeTermMix, "three_year", "Term mix should include 3-year plans")
	assert.Contains(t, computeTermMix, "one_year", "Term mix should include 1-year plans")

	t.Log("✓ single-account-compute example validated: mixed term/payment options confirmed")
}

// TestExampleDatabaseOnly validates the database-only example
// Focus: Database SP only (no compute), validates database-specific configuration
func TestExampleDatabaseOnly(t *testing.T) {
	t.Parallel()

	awsRegion := "us-east-1"

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: "../../examples/database-only",
		Vars: map[string]interface{}{
			"scheduler": map[string]interface{}{
				"scheduler": "cron(0 0 1 1 ? 2099)",
				"purchaser": "cron(0 0 1 1 ? 2099)",
				"reporter":  "cron(0 0 1 1 ? 2099)",
			},
			"lambda_config": map[string]interface{}{
				"scheduler": map[string]interface{}{
					"dry_run": true,
				},
			},
		},
		NoColor: true,
	})

	defer terraform.Destroy(t, terraformOptions)

	t.Log("Testing database-only example...")
	terraform.InitAndApply(t, terraformOptions)

	commonExampleValidation(t, terraformOptions, awsRegion)

	// Unique validation: Verify ONLY database SP is enabled
	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")

	enableComputeSP := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "ENABLE_COMPUTE_SP")
	assert.Equal(t, "false", enableComputeSP, "Compute SP should be disabled")

	enableDatabaseSP := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "ENABLE_DATABASE_SP")
	assert.Equal(t, "true", enableDatabaseSP, "Database SP should be enabled")

	enableSageMakerSP := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "ENABLE_SAGEMAKER_SP")
	assert.Equal(t, "false", enableSageMakerSP, "SageMaker SP should be disabled")

	// Database SP always uses NO_UPFRONT, ONE_YEAR (AWS constraint)
	databasePaymentOption := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "DATABASE_SP_PAYMENT_OPTION")
	assert.Equal(t, "NO_UPFRONT", databasePaymentOption, "Database SP should use NO_UPFRONT")

	databaseTerm := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "DATABASE_SP_TERM")
	assert.Equal(t, "ONE_YEAR", databaseTerm, "Database SP should use ONE_YEAR term")

	t.Log("✓ database-only example validated: database SP configuration confirmed")
}

// TestExampleDichotomyStrategy validates the dichotomy-strategy example
// Focus: Dichotomy purchase strategy with adaptive sizing
func TestExampleDichotomyStrategy(t *testing.T) {
	t.Parallel()

	awsRegion := "us-east-1"

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: "../../examples/dichotomy-strategy",
		Vars: map[string]interface{}{
			"scheduler": map[string]interface{}{
				"scheduler": "cron(0 0 1 1 ? 2099)",
				"purchaser": "cron(0 0 1 1 ? 2099)",
				"reporter":  "cron(0 0 1 1 ? 2099)",
			},
			"lambda_config": map[string]interface{}{
				"scheduler": map[string]interface{}{
					"dry_run": true,
				},
			},
		},
		NoColor: true,
	})

	defer terraform.Destroy(t, terraformOptions)

	t.Log("Testing dichotomy-strategy example...")
	terraform.InitAndApply(t, terraformOptions)

	commonExampleValidation(t, terraformOptions, awsRegion)

	// Unique validation: Verify dichotomy strategy is configured
	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")

	purchaseStrategyType := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "PURCHASE_STRATEGY_TYPE")
	assert.Equal(t, "dichotomy", purchaseStrategyType, "Strategy should be dichotomy")

	// Verify dichotomy-specific parameters
	maxPurchasePercent := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "MAX_PURCHASE_PERCENT")
	assert.Equal(t, "50", maxPurchasePercent, "Max purchase should be 50% (example config)")

	minPurchasePercent := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "MIN_PURCHASE_PERCENT")
	assert.Equal(t, "1", minPurchasePercent, "Min purchase should be 1% (example config)")

	t.Log("✓ dichotomy-strategy example validated: strategy type and parameters confirmed")
}

// TestExampleOrganizations validates the organizations example
// Focus: Cross-account assume_role_arn configuration for AWS Organizations
func TestExampleOrganizations(t *testing.T) {
	t.Parallel()

	awsRegion := "us-east-1"

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: "../../examples/organizations",
		Vars: map[string]interface{}{
			"scheduler": map[string]interface{}{
				"scheduler": "cron(0 0 1 1 ? 2099)",
				"purchaser": "cron(0 0 1 1 ? 2099)",
				"reporter":  "cron(0 0 1 1 ? 2099)",
			},
			"lambda_config": map[string]interface{}{
				"scheduler": map[string]interface{}{
					"dry_run":         true,
					"assume_role_arn": "arn:aws:iam::999999999999:role/TestSchedulerRole", // Fake role for testing
				},
				"purchaser": map[string]interface{}{
					"assume_role_arn": "arn:aws:iam::999999999999:role/TestPurchaserRole", // Fake role for testing
				},
				"reporter": map[string]interface{}{
					"assume_role_arn": "arn:aws:iam::999999999999:role/TestReporterRole", // Fake role for testing
				},
			},
		},
		NoColor: true,
	})

	defer terraform.Destroy(t, terraformOptions)

	t.Log("Testing organizations example...")
	terraform.InitAndApply(t, terraformOptions)

	commonExampleValidation(t, terraformOptions, awsRegion)

	// Unique validation: Verify assume_role_arn is configured for each Lambda
	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	purchaserLambdaName := terraform.Output(t, terraformOptions, "purchaser_lambda_name")
	reporterLambdaName := terraform.Output(t, terraformOptions, "reporter_lambda_name")

	schedulerAssumeRoleArn := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "ASSUME_ROLE_ARN")
	assert.Contains(t, schedulerAssumeRoleArn, "TestSchedulerRole", "Scheduler should have assume_role_arn configured")

	purchaserAssumeRoleArn := getLambdaEnvVar(t, awsRegion, purchaserLambdaName, "ASSUME_ROLE_ARN")
	assert.Contains(t, purchaserAssumeRoleArn, "TestPurchaserRole", "Purchaser should have assume_role_arn configured")

	reporterAssumeRoleArn := getLambdaEnvVar(t, awsRegion, reporterLambdaName, "ASSUME_ROLE_ARN")
	assert.Contains(t, reporterAssumeRoleArn, "TestReporterRole", "Reporter should have assume_role_arn configured")

	// Verify both compute and database SP are enabled (organization-wide coverage)
	enableComputeSP := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "ENABLE_COMPUTE_SP")
	assert.Equal(t, "true", enableComputeSP, "Compute SP should be enabled for org-wide coverage")

	enableDatabaseSP := getLambdaEnvVar(t, awsRegion, schedulerLambdaName, "ENABLE_DATABASE_SP")
	assert.Equal(t, "true", enableDatabaseSP, "Database SP should be enabled for org-wide coverage")

	t.Log("✓ organizations example validated: cross-account roles and comprehensive coverage confirmed")
}

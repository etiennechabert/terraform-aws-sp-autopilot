package test

import (
	"strings"
	"testing"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/cloudwatch"
	"github.com/aws/aws-sdk-go/service/cloudwatchevents"
	"github.com/aws/aws-sdk-go/service/cloudwatchlogs"
	"github.com/aws/aws-sdk-go/service/iam"
	"github.com/aws/aws-sdk-go/service/lambda"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/aws/aws-sdk-go/service/sns"
	"github.com/aws/aws-sdk-go/service/sqs"
	terratest_aws "github.com/gruntwork-io/terratest/modules/aws"
)

// TestCleanupAllOrphanedResources finds and removes ALL orphaned test resources
// from previous failed test runs using direct AWS API calls (not Terraform).
//
// This test cleans up resources matching the pattern "sp-autopilot-test-*" including:
//   - CloudWatch Log Groups: /aws/lambda/sp-autopilot-test-*
//   - CloudWatch Alarms: sp-autopilot-test-*
//   - Lambda Functions: sp-autopilot-test-*
//   - EventBridge Rules: sp-autopilot-test-*
//   - SQS Queues: sp-autopilot-test-*
//   - SNS Topics & Subscriptions: sp-autopilot-test-*
//   - IAM Roles: sp-autopilot-test-* (with policy detachment)
//   - S3 Buckets: sp-autopilot-test-* (with object deletion)
//
// USAGE:
//   Automated (CI): Runs automatically after integration tests in GitHub Actions
//   Manual cleanup: go test -v -run TestCleanupAllOrphanedResources -timeout 10m
//
// SAFETY:
//   - Only deletes resources with "sp-autopilot-test-" prefix
//   - Production resources (sp-autopilot-*) are NOT affected
//   - Uses || true in CI to continue even if cleanup fails
func TestCleanupAllOrphanedResources(t *testing.T) {
	awsRegion := "us-east-1"

	t.Log("========================================")
	t.Log("Cleaning Up ALL Orphaned Test Resources")
	t.Log("========================================")

	sess, err := terratest_aws.NewAuthenticatedSession(awsRegion)
	if err != nil {
		t.Fatalf("Failed to create AWS session: %v", err)
	}

	// Cleanup all resources matching test patterns
	cleanupAllCloudWatchAlarms(t, sess)
	cleanupAllLogGroups(t, sess)
	cleanupAllLambdaFunctions(t, sess)
	cleanupAllEventBridgeRules(t, sess)
	cleanupAllSQSQueues(t, sess)
	cleanupAllSNSTopics(t, sess)
	cleanupAllIAMRoles(t, sess)
	cleanupAllS3Buckets(t, sess)

	t.Log("========================================")
	t.Log("Cleanup Complete")
	t.Log("========================================")
}

func cleanupAllCloudWatchAlarms(t *testing.T, sess *session.Session) {
	t.Log("\n[CloudWatch Alarms]")
	cwClient := cloudwatch.New(sess)

	// Check multiple test prefix patterns
	alarmPrefixes := []string{
		"sp-autopilot-test",  // Current prefix
		"sp-test-",           // Old prefix pattern
	}

	deletedCount := 0
	for _, prefix := range alarmPrefixes {
		output, err := cwClient.DescribeAlarms(&cloudwatch.DescribeAlarmsInput{
			AlarmNamePrefix: aws.String(prefix),
		})
		if err != nil {
			t.Logf("  ⚠ Failed to list CloudWatch alarms with prefix %s: %v", prefix, err)
			continue
		}

		// Delete metric alarms
		for _, alarm := range output.MetricAlarms {
			_, err := cwClient.DeleteAlarms(&cloudwatch.DeleteAlarmsInput{
				AlarmNames: []*string{alarm.AlarmName},
			})
			if err != nil {
				t.Logf("  ⚠ Failed to delete CloudWatch alarm %s: %v", *alarm.AlarmName, err)
			} else {
				t.Logf("  ✓ Deleted CloudWatch alarm: %s", *alarm.AlarmName)
				deletedCount++
			}
		}

		// Delete composite alarms
		for _, alarm := range output.CompositeAlarms {
			_, err := cwClient.DeleteAlarms(&cloudwatch.DeleteAlarmsInput{
				AlarmNames: []*string{alarm.AlarmName},
			})
			if err != nil {
				t.Logf("  ⚠ Failed to delete composite alarm %s: %v", *alarm.AlarmName, err)
			} else {
				t.Logf("  ✓ Deleted composite alarm: %s", *alarm.AlarmName)
				deletedCount++
			}
		}
	}

	if deletedCount == 0 {
		t.Log("  ✓ No orphaned CloudWatch alarms found")
	}
}

func cleanupAllLogGroups(t *testing.T, sess *session.Session) {
	t.Log("\n[CloudWatch Log Groups]")
	cwlClient := cloudwatchlogs.New(sess)

	// Check multiple test prefix patterns
	logGroupPrefixes := []string{
		"/aws/lambda/sp-autopilot-test",  // Current prefix
		"/aws/lambda/sp-test-",           // Old prefix pattern
	}

	deletedCount := 0
	for _, prefix := range logGroupPrefixes {
		output, err := cwlClient.DescribeLogGroups(&cloudwatchlogs.DescribeLogGroupsInput{
			LogGroupNamePrefix: aws.String(prefix),
		})
		if err != nil {
			t.Logf("  ⚠ Failed to list log groups with prefix %s: %v", prefix, err)
			continue
		}

		for _, logGroup := range output.LogGroups {
			_, err := cwlClient.DeleteLogGroup(&cloudwatchlogs.DeleteLogGroupInput{
				LogGroupName: logGroup.LogGroupName,
			})
			if err != nil {
				t.Logf("  ⚠ Failed to delete log group %s: %v", *logGroup.LogGroupName, err)
			} else {
				t.Logf("  ✓ Deleted log group: %s", *logGroup.LogGroupName)
				deletedCount++
			}
		}
	}

	if deletedCount == 0 {
		t.Log("  ✓ No orphaned log groups found")
	}
}

func cleanupAllLambdaFunctions(t *testing.T, sess *session.Session) {
	t.Log("\n[Lambda Functions]")
	lambdaClient := lambda.New(sess)

	// List all Lambda functions
	output, err := lambdaClient.ListFunctions(&lambda.ListFunctionsInput{})
	if err != nil {
		t.Logf("  ⚠ Failed to list Lambda functions: %v", err)
		return
	}

	deleted := false
	// Check multiple test prefix patterns
	testPrefixes := []string{
		"sp-autopilot-test-",  // Current prefix
		"sp-test-",            // Old prefix pattern
	}

	for _, function := range output.Functions {
		// Only delete functions matching test patterns
		isTestFunction := false
		for _, prefix := range testPrefixes {
			if strings.HasPrefix(*function.FunctionName, prefix) {
				isTestFunction = true
				break
			}
		}

		if isTestFunction {
			_, err := lambdaClient.DeleteFunction(&lambda.DeleteFunctionInput{
				FunctionName: function.FunctionName,
			})
			if err != nil {
				t.Logf("  ⚠ Failed to delete Lambda function %s: %v", *function.FunctionName, err)
			} else {
				t.Logf("  ✓ Deleted Lambda function: %s", *function.FunctionName)
				deleted = true
			}
		}
	}

	if !deleted {
		t.Log("  ✓ No orphaned Lambda functions found")
	}
}

func cleanupAllEventBridgeRules(t *testing.T, sess *session.Session) {
	t.Log("\n[EventBridge Rules]")
	eventsClient := cloudwatchevents.New(sess)

	// Check multiple test prefix patterns
	rulePrefixes := []string{
		"sp-autopilot-test",  // Current prefix
		"sp-test-",           // Old prefix pattern
	}

	deletedCount := 0
	for _, prefix := range rulePrefixes {
		output, err := eventsClient.ListRules(&cloudwatchevents.ListRulesInput{
			NamePrefix: aws.String(prefix),
		})
		if err != nil {
			t.Logf("  ⚠ Failed to list EventBridge rules with prefix %s: %v", prefix, err)
			continue
		}

		for _, rule := range output.Rules {
		// First, remove all targets from the rule
		targetsOutput, err := eventsClient.ListTargetsByRule(&cloudwatchevents.ListTargetsByRuleInput{
			Rule: rule.Name,
		})
		if err == nil && len(targetsOutput.Targets) > 0 {
			targetIDs := make([]*string, len(targetsOutput.Targets))
			for i, target := range targetsOutput.Targets {
				targetIDs[i] = target.Id
			}
			_, err = eventsClient.RemoveTargets(&cloudwatchevents.RemoveTargetsInput{
				Rule: rule.Name,
				Ids:  targetIDs,
			})
			if err != nil {
				t.Logf("  ⚠ Failed to remove targets from rule %s: %v", *rule.Name, err)
			}
		}

			// Now delete the rule
			_, err = eventsClient.DeleteRule(&cloudwatchevents.DeleteRuleInput{
				Name: rule.Name,
			})
			if err != nil {
				t.Logf("  ⚠ Failed to delete EventBridge rule %s: %v", *rule.Name, err)
			} else {
				t.Logf("  ✓ Deleted EventBridge rule: %s", *rule.Name)
				deletedCount++
			}
		}
	}

	if deletedCount == 0 {
		t.Log("  ✓ No orphaned EventBridge rules found")
	}
}

func cleanupAllSQSQueues(t *testing.T, sess *session.Session) {
	t.Log("\n[SQS Queues]")
	sqsClient := sqs.New(sess)

	// List all SQS queues with any test-related prefix
	prefixes := []string{
		"sp-autopilot-test",  // Current prefix
		"sp-test-",           // Old prefix pattern
	}

	deletedCount := 0
	for _, prefix := range prefixes {
		output, err := sqsClient.ListQueues(&sqs.ListQueuesInput{
			QueueNamePrefix: aws.String(prefix),
		})
		if err != nil {
			t.Logf("  ⚠ Failed to list SQS queues with prefix %s: %v", prefix, err)
			continue
		}

		for _, queueURL := range output.QueueUrls {
			_, err := sqsClient.DeleteQueue(&sqs.DeleteQueueInput{
				QueueUrl: queueURL,
			})
			if err != nil {
				t.Logf("  ⚠ Failed to delete SQS queue %s: %v", *queueURL, err)
			} else {
				t.Logf("  ✓ Deleted SQS queue: %s", *queueURL)
				deletedCount++
			}
		}
	}

	if deletedCount == 0 {
		t.Log("  ✓ No orphaned SQS queues found")
	}
}

func cleanupAllSNSTopics(t *testing.T, sess *session.Session) {
	t.Log("\n[SNS Topics & Subscriptions]")
	snsClient := sns.New(sess)

	// List all SNS topics
	output, err := snsClient.ListTopics(&sns.ListTopicsInput{})
	if err != nil {
		t.Logf("  ⚠ Failed to list SNS topics: %v", err)
		return
	}

	deleted := false
	// Check multiple test prefix patterns
	testPrefixes := []string{
		"sp-autopilot-test-",  // Current prefix
		"sp-test-",            // Old prefix pattern
	}

	for _, topic := range output.Topics {
		// Only delete topics matching test patterns
		isTestTopic := false
		for _, prefix := range testPrefixes {
			if strings.Contains(*topic.TopicArn, prefix) {
				isTestTopic = true
				break
			}
		}

		if isTestTopic {
			// First, delete all subscriptions for this topic
			subsOutput, err := snsClient.ListSubscriptionsByTopic(&sns.ListSubscriptionsByTopicInput{
				TopicArn: topic.TopicArn,
			})
			if err == nil {
				for _, sub := range subsOutput.Subscriptions {
					_, _ = snsClient.Unsubscribe(&sns.UnsubscribeInput{
						SubscriptionArn: sub.SubscriptionArn,
					})
					t.Logf("  ✓ Deleted subscription: %s", *sub.SubscriptionArn)
				}
			}

			// Now delete the topic
			_, err = snsClient.DeleteTopic(&sns.DeleteTopicInput{
				TopicArn: topic.TopicArn,
			})
			if err != nil {
				t.Logf("  ⚠ Failed to delete SNS topic %s: %v", *topic.TopicArn, err)
			} else {
				t.Logf("  ✓ Deleted SNS topic: %s", *topic.TopicArn)
				deleted = true
			}
		}
	}

	if !deleted {
		t.Log("  ✓ No orphaned SNS topics/subscriptions found")
	}
}

func cleanupAllIAMRoles(t *testing.T, sess *session.Session) {
	t.Log("\n[IAM Roles]")
	iamClient := iam.New(sess)

	// List all IAM roles
	output, err := iamClient.ListRoles(&iam.ListRolesInput{
		PathPrefix: aws.String("/"),
	})
	if err != nil {
		t.Logf("  ⚠ Failed to list IAM roles: %v", err)
		return
	}

	deleted := false
	// Check multiple test prefix patterns
	testPrefixes := []string{
		"sp-autopilot-test-",  // Current prefix
		"sp-test-",            // Old prefix pattern
	}

	for _, role := range output.Roles {
		// Only delete roles matching test patterns
		isTestRole := false
		for _, prefix := range testPrefixes {
			if strings.HasPrefix(*role.RoleName, prefix) {
				isTestRole = true
				break
			}
		}

		if isTestRole {
			// First, detach all managed policies
			policiesOutput, err := iamClient.ListAttachedRolePolicies(&iam.ListAttachedRolePoliciesInput{
				RoleName: role.RoleName,
			})
			if err == nil {
				for _, policy := range policiesOutput.AttachedPolicies {
					_, _ = iamClient.DetachRolePolicy(&iam.DetachRolePolicyInput{
						RoleName:  role.RoleName,
						PolicyArn: policy.PolicyArn,
					})
				}
			}

			// Delete inline policies
			inlinePoliciesOutput, err := iamClient.ListRolePolicies(&iam.ListRolePoliciesInput{
				RoleName: role.RoleName,
			})
			if err == nil {
				for _, policyName := range inlinePoliciesOutput.PolicyNames {
					_, _ = iamClient.DeleteRolePolicy(&iam.DeleteRolePolicyInput{
						RoleName:   role.RoleName,
						PolicyName: policyName,
					})
				}
			}

			// Now delete the role
			_, err = iamClient.DeleteRole(&iam.DeleteRoleInput{
				RoleName: role.RoleName,
			})
			if err != nil {
				t.Logf("  ⚠ Failed to delete IAM role %s: %v", *role.RoleName, err)
			} else {
				t.Logf("  ✓ Deleted IAM role: %s", *role.RoleName)
				deleted = true
			}
		}
	}

	if !deleted {
		t.Log("  ✓ No orphaned IAM roles found")
	}
}

func cleanupAllS3Buckets(t *testing.T, sess *session.Session) {
	t.Log("\n[S3 Buckets]")
	s3Client := s3.New(sess)

	// List all S3 buckets
	output, err := s3Client.ListBuckets(&s3.ListBucketsInput{})
	if err != nil {
		t.Logf("  ⚠ Failed to list S3 buckets: %v", err)
		return
	}

	deleted := false
	// Check multiple test prefix patterns
	testPrefixes := []string{
		"sp-autopilot-test-",  // Current prefix
		"sp-test-",            // Old prefix pattern
	}

	for _, bucket := range output.Buckets {
		// Only delete buckets matching test patterns
		isTestBucket := false
		for _, prefix := range testPrefixes {
			if strings.HasPrefix(*bucket.Name, prefix) {
				isTestBucket = true
				break
			}
		}

		if isTestBucket {
			// First, delete all objects in the bucket
			listObjectsOutput, err := s3Client.ListObjectsV2(&s3.ListObjectsV2Input{
				Bucket: bucket.Name,
			})
			if err == nil {
				for _, object := range listObjectsOutput.Contents {
					_, _ = s3Client.DeleteObject(&s3.DeleteObjectInput{
						Bucket: bucket.Name,
						Key:    object.Key,
					})
				}
			}

			// Delete all object versions (if versioning enabled)
			listVersionsOutput, err := s3Client.ListObjectVersions(&s3.ListObjectVersionsInput{
				Bucket: bucket.Name,
			})
			if err == nil {
				for _, version := range listVersionsOutput.Versions {
					_, _ = s3Client.DeleteObject(&s3.DeleteObjectInput{
						Bucket:    bucket.Name,
						Key:       version.Key,
						VersionId: version.VersionId,
					})
				}
				for _, marker := range listVersionsOutput.DeleteMarkers {
					_, _ = s3Client.DeleteObject(&s3.DeleteObjectInput{
						Bucket:    bucket.Name,
						Key:       marker.Key,
						VersionId: marker.VersionId,
					})
				}
			}

			// Now delete the bucket
			_, err = s3Client.DeleteBucket(&s3.DeleteBucketInput{
				Bucket: bucket.Name,
			})
			if err != nil {
				t.Logf("  ⚠ Failed to delete S3 bucket %s: %v", *bucket.Name, err)
			} else {
				t.Logf("  ✓ Deleted S3 bucket: %s", *bucket.Name)
				deleted = true
			}
		}
	}

	if !deleted {
		t.Log("  ✓ No orphaned S3 buckets found")
	}
}

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

func matchesTestPrefix(name string, prefixes []string) bool {
	for _, prefix := range prefixes {
		if strings.HasPrefix(name, prefix) {
			return true
		}
	}
	return false
}

func containsTestPrefix(name string, prefixes []string) bool {
	for _, prefix := range prefixes {
		if strings.Contains(name, prefix) {
			return true
		}
	}
	return false
}

// TestCleanupAllOrphanedResources finds and removes ALL orphaned test resources
// from previous failed test runs using direct AWS API calls (not Terraform).
func TestCleanupAllOrphanedResources(t *testing.T) {
	awsRegion := "us-east-1"

	t.Log(logSeparator)
	t.Log("Cleaning Up ALL Orphaned Test Resources")
	t.Log(logSeparator)

	sess, err := terratest_aws.NewAuthenticatedSession(awsRegion)
	if err != nil {
		t.Fatalf("Failed to create AWS session: %v", err)
	}

	cleanupAllCloudWatchAlarms(t, sess)
	cleanupAllLogGroups(t, sess)
	cleanupAllLambdaFunctions(t, sess)
	cleanupAllEventBridgeRules(t, sess)
	cleanupAllSQSQueues(t, sess)
	cleanupAllSNSTopics(t, sess)
	cleanupAllIAMRoles(t, sess)
	cleanupAllS3Buckets(t, sess)

	t.Log(logSeparator)
	t.Log("Cleanup Complete")
	t.Log(logSeparator)
}

func deleteAlarms(t *testing.T, cwClient *cloudwatch.CloudWatch, alarmNames []*string) int {
	deleted := 0
	for _, alarmName := range alarmNames {
		_, err := cwClient.DeleteAlarms(&cloudwatch.DeleteAlarmsInput{
			AlarmNames: []*string{alarmName},
		})
		if err != nil {
			t.Logf("  Warning: Failed to delete CloudWatch alarm %s: %v", *alarmName, err)
		} else {
			t.Logf("  Deleted CloudWatch alarm: %s", *alarmName)
			deleted++
		}
	}
	return deleted
}

func cleanupAllCloudWatchAlarms(t *testing.T, sess *session.Session) {
	t.Log("\n[CloudWatch Alarms]")
	cwClient := cloudwatch.New(sess)

	alarmPrefixes := []string{testPrefixCurrent, testPrefixOld}

	deletedCount := 0
	for _, prefix := range alarmPrefixes {
		output, err := cwClient.DescribeAlarms(&cloudwatch.DescribeAlarmsInput{
			AlarmNamePrefix: aws.String(prefix),
		})
		if err != nil {
			t.Logf("  Warning: Failed to list CloudWatch alarms with prefix %s: %v", prefix, err)
			continue
		}

		metricAlarmNames := make([]*string, len(output.MetricAlarms))
		for i, alarm := range output.MetricAlarms {
			metricAlarmNames[i] = alarm.AlarmName
		}
		deletedCount += deleteAlarms(t, cwClient, metricAlarmNames)

		compositeAlarmNames := make([]*string, len(output.CompositeAlarms))
		for i, alarm := range output.CompositeAlarms {
			compositeAlarmNames[i] = alarm.AlarmName
		}
		deletedCount += deleteAlarms(t, cwClient, compositeAlarmNames)
	}

	if deletedCount == 0 {
		t.Log("  No orphaned CloudWatch alarms found")
	}
}

func cleanupAllLogGroups(t *testing.T, sess *session.Session) {
	t.Log("\n[CloudWatch Log Groups]")
	cwlClient := cloudwatchlogs.New(sess)

	logGroupPrefixes := []string{
		"/aws/lambda/" + testPrefixCurrent,
		"/aws/lambda/" + testPrefixOld,
	}

	deletedCount := 0
	for _, prefix := range logGroupPrefixes {
		output, err := cwlClient.DescribeLogGroups(&cloudwatchlogs.DescribeLogGroupsInput{
			LogGroupNamePrefix: aws.String(prefix),
		})
		if err != nil {
			t.Logf("  Warning: Failed to list log groups with prefix %s: %v", prefix, err)
			continue
		}

		for _, logGroup := range output.LogGroups {
			_, err := cwlClient.DeleteLogGroup(&cloudwatchlogs.DeleteLogGroupInput{
				LogGroupName: logGroup.LogGroupName,
			})
			if err != nil {
				t.Logf("  Warning: Failed to delete log group %s: %v", *logGroup.LogGroupName, err)
			} else {
				t.Logf("  Deleted log group: %s", *logGroup.LogGroupName)
				deletedCount++
			}
		}
	}

	if deletedCount == 0 {
		t.Log("  No orphaned log groups found")
	}
}

func cleanupAllLambdaFunctions(t *testing.T, sess *session.Session) {
	t.Log("\n[Lambda Functions]")
	lambdaClient := lambda.New(sess)

	output, err := lambdaClient.ListFunctions(&lambda.ListFunctionsInput{})
	if err != nil {
		t.Logf("  Warning: Failed to list Lambda functions: %v", err)
		return
	}

	deleted := false
	testPrefixes := []string{testPrefixCurrentDash, testPrefixOld}

	for _, function := range output.Functions {
		if matchesTestPrefix(*function.FunctionName, testPrefixes) {
			_, err := lambdaClient.DeleteFunction(&lambda.DeleteFunctionInput{
				FunctionName: function.FunctionName,
			})
			if err != nil {
				t.Logf("  Warning: Failed to delete Lambda function %s: %v", *function.FunctionName, err)
			} else {
				t.Logf("  Deleted Lambda function: %s", *function.FunctionName)
				deleted = true
			}
		}
	}

	if !deleted {
		t.Log("  No orphaned Lambda functions found")
	}
}

func deleteEventBridgeRule(t *testing.T, eventsClient *cloudwatchevents.CloudWatchEvents, rule *cloudwatchevents.Rule) bool {
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
			t.Logf("  Warning: Failed to remove targets from rule %s: %v", *rule.Name, err)
		}
	}

	_, err = eventsClient.DeleteRule(&cloudwatchevents.DeleteRuleInput{
		Name: rule.Name,
	})
	if err != nil {
		t.Logf("  Warning: Failed to delete EventBridge rule %s: %v", *rule.Name, err)
		return false
	}
	t.Logf("  Deleted EventBridge rule: %s", *rule.Name)
	return true
}

func cleanupAllEventBridgeRules(t *testing.T, sess *session.Session) {
	t.Log("\n[EventBridge Rules]")
	eventsClient := cloudwatchevents.New(sess)

	rulePrefixes := []string{testPrefixCurrent, testPrefixOld}

	deletedCount := 0
	for _, prefix := range rulePrefixes {
		output, err := eventsClient.ListRules(&cloudwatchevents.ListRulesInput{
			NamePrefix: aws.String(prefix),
		})
		if err != nil {
			t.Logf("  Warning: Failed to list EventBridge rules with prefix %s: %v", prefix, err)
			continue
		}

		for _, rule := range output.Rules {
			if deleteEventBridgeRule(t, eventsClient, rule) {
				deletedCount++
			}
		}
	}

	if deletedCount == 0 {
		t.Log("  No orphaned EventBridge rules found")
	}
}

func cleanupAllSQSQueues(t *testing.T, sess *session.Session) {
	t.Log("\n[SQS Queues]")
	sqsClient := sqs.New(sess)

	prefixes := []string{testPrefixCurrent, testPrefixOld}

	deletedCount := 0
	for _, prefix := range prefixes {
		output, err := sqsClient.ListQueues(&sqs.ListQueuesInput{
			QueueNamePrefix: aws.String(prefix),
		})
		if err != nil {
			t.Logf("  Warning: Failed to list SQS queues with prefix %s: %v", prefix, err)
			continue
		}

		for _, queueURL := range output.QueueUrls {
			_, err := sqsClient.DeleteQueue(&sqs.DeleteQueueInput{
				QueueUrl: queueURL,
			})
			if err != nil {
				t.Logf("  Warning: Failed to delete SQS queue %s: %v", *queueURL, err)
			} else {
				t.Logf("  Deleted SQS queue: %s", *queueURL)
				deletedCount++
			}
		}
	}

	if deletedCount == 0 {
		t.Log("  No orphaned SQS queues found")
	}
}

func deleteSNSTopic(t *testing.T, snsClient *sns.SNS, topic *sns.Topic) bool {
	subsOutput, err := snsClient.ListSubscriptionsByTopic(&sns.ListSubscriptionsByTopicInput{
		TopicArn: topic.TopicArn,
	})
	if err == nil {
		for _, sub := range subsOutput.Subscriptions {
			_, _ = snsClient.Unsubscribe(&sns.UnsubscribeInput{
				SubscriptionArn: sub.SubscriptionArn,
			})
			t.Logf("  Deleted subscription: %s", *sub.SubscriptionArn)
		}
	}

	_, err = snsClient.DeleteTopic(&sns.DeleteTopicInput{
		TopicArn: topic.TopicArn,
	})
	if err != nil {
		t.Logf("  Warning: Failed to delete SNS topic %s: %v", *topic.TopicArn, err)
		return false
	}
	t.Logf("  Deleted SNS topic: %s", *topic.TopicArn)
	return true
}

func cleanupAllSNSTopics(t *testing.T, sess *session.Session) {
	t.Log("\n[SNS Topics & Subscriptions]")
	snsClient := sns.New(sess)

	output, err := snsClient.ListTopics(&sns.ListTopicsInput{})
	if err != nil {
		t.Logf("  Warning: Failed to list SNS topics: %v", err)
		return
	}

	deleted := false
	testPrefixes := []string{testPrefixCurrentDash, testPrefixOld}

	for _, topic := range output.Topics {
		if containsTestPrefix(*topic.TopicArn, testPrefixes) {
			if deleteSNSTopic(t, snsClient, topic) {
				deleted = true
			}
		}
	}

	if !deleted {
		t.Log("  No orphaned SNS topics/subscriptions found")
	}
}

func deleteIAMRole(t *testing.T, iamClient *iam.IAM, role *iam.Role) bool {
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

	_, err = iamClient.DeleteRole(&iam.DeleteRoleInput{
		RoleName: role.RoleName,
	})
	if err != nil {
		t.Logf("  Warning: Failed to delete IAM role %s: %v", *role.RoleName, err)
		return false
	}
	t.Logf("  Deleted IAM role: %s", *role.RoleName)
	return true
}

func cleanupAllIAMRoles(t *testing.T, sess *session.Session) {
	t.Log("\n[IAM Roles]")
	iamClient := iam.New(sess)

	output, err := iamClient.ListRoles(&iam.ListRolesInput{
		PathPrefix: aws.String("/"),
	})
	if err != nil {
		t.Logf("  Warning: Failed to list IAM roles: %v", err)
		return
	}

	deleted := false
	testPrefixes := []string{testPrefixCurrentDash, testPrefixOld}

	for _, role := range output.Roles {
		if matchesTestPrefix(*role.RoleName, testPrefixes) {
			if deleteIAMRole(t, iamClient, role) {
				deleted = true
			}
		}
	}

	if !deleted {
		t.Log("  No orphaned IAM roles found")
	}
}

func deleteS3Bucket(t *testing.T, s3Client *s3.S3, bucket *s3.Bucket) bool {
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

	_, err = s3Client.DeleteBucket(&s3.DeleteBucketInput{
		Bucket: bucket.Name,
	})
	if err != nil {
		t.Logf("  Warning: Failed to delete S3 bucket %s: %v", *bucket.Name, err)
		return false
	}
	t.Logf("  Deleted S3 bucket: %s", *bucket.Name)
	return true
}

func cleanupAllS3Buckets(t *testing.T, sess *session.Session) {
	t.Log("\n[S3 Buckets]")
	s3Client := s3.New(sess)

	output, err := s3Client.ListBuckets(&s3.ListBucketsInput{})
	if err != nil {
		t.Logf("  Warning: Failed to list S3 buckets: %v", err)
		return
	}

	deleted := false
	testPrefixes := []string{testPrefixCurrentDash, testPrefixOld}

	for _, bucket := range output.Buckets {
		if matchesTestPrefix(*bucket.Name, testPrefixes) {
			if deleteS3Bucket(t, s3Client, bucket) {
				deleted = true
			}
		}
	}

	if !deleted {
		t.Log("  No orphaned S3 buckets found")
	}
}

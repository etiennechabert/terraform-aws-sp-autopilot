package test

import (
	"fmt"
	"strings"
	"testing"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/cloudwatchlogs"
	"github.com/aws/aws-sdk-go/service/iam"
	"github.com/aws/aws-sdk-go/service/s3"
	terratest_aws "github.com/gruntwork-io/terratest/modules/aws"
)

// CleanupOrphanedResources removes any leftover resources from previous failed test runs
// that match the given name prefix. This prevents "resource already exists" errors.
func CleanupOrphanedResources(t *testing.T, awsRegion string, namePrefix string) {
	t.Logf("Cleaning up orphaned resources with prefix: %s", namePrefix)

	sess, err := terratest_aws.NewAuthenticatedSession(awsRegion)
	if err != nil {
		t.Logf("Warning: Failed to create AWS session for cleanup: %v", err)
		return
	}

	cleanupLogGroups(t, sess, namePrefix)
	cleanupIAMRoles(t, sess, namePrefix)
	cleanupS3Buckets(t, sess, namePrefix)

	t.Logf("Cleanup complete for prefix: %s", namePrefix)
}

func cleanupLogGroups(t *testing.T, sess *session.Session, namePrefix string) {
	cwlClient := cloudwatchlogs.New(sess)

	logGroupNames := []string{
		fmt.Sprintf("/aws/lambda/%s-scheduler", namePrefix),
		fmt.Sprintf("/aws/lambda/%s-purchaser", namePrefix),
		fmt.Sprintf("/aws/lambda/%s-reporter", namePrefix),
	}

	for _, logGroupName := range logGroupNames {
		_, err := cwlClient.DeleteLogGroup(&cloudwatchlogs.DeleteLogGroupInput{
			LogGroupName: aws.String(logGroupName),
		})
		if err != nil {
			if strings.Contains(err.Error(), "ResourceNotFoundException") {
				t.Logf("  Log group %s does not exist (already clean)", logGroupName)
			} else {
				t.Logf("  Warning: Failed to delete log group %s: %v", logGroupName, err)
			}
		} else {
			t.Logf("  Deleted log group: %s", logGroupName)
		}
	}
}

func cleanupRolePolicies(t *testing.T, iamClient *iam.IAM, roleName string) {
	listPoliciesOutput, err := iamClient.ListAttachedRolePolicies(&iam.ListAttachedRolePoliciesInput{
		RoleName: aws.String(roleName),
	})
	if err == nil {
		for _, policy := range listPoliciesOutput.AttachedPolicies {
			_, err := iamClient.DetachRolePolicy(&iam.DetachRolePolicyInput{
				RoleName:  aws.String(roleName),
				PolicyArn: policy.PolicyArn,
			})
			if err != nil {
				t.Logf("  Warning: Failed to detach policy %s from role %s: %v", *policy.PolicyArn, roleName, err)
			}
		}
	}

	listInlinePoliciesOutput, err := iamClient.ListRolePolicies(&iam.ListRolePoliciesInput{
		RoleName: aws.String(roleName),
	})
	if err == nil {
		for _, policyName := range listInlinePoliciesOutput.PolicyNames {
			_, err := iamClient.DeleteRolePolicy(&iam.DeleteRolePolicyInput{
				RoleName:   aws.String(roleName),
				PolicyName: policyName,
			})
			if err != nil {
				t.Logf("  Warning: Failed to delete inline policy %s from role %s: %v", *policyName, roleName, err)
			}
		}
	}
}

func cleanupIAMRoles(t *testing.T, sess *session.Session, namePrefix string) {
	iamClient := iam.New(sess)

	roleNames := []string{
		fmt.Sprintf("%s-scheduler", namePrefix),
		fmt.Sprintf("%s-purchaser", namePrefix),
		fmt.Sprintf("%s-reporter", namePrefix),
	}

	for _, roleName := range roleNames {
		// Check if the role exists by listing its policies
		_, err := iamClient.ListAttachedRolePolicies(&iam.ListAttachedRolePoliciesInput{
			RoleName: aws.String(roleName),
		})
		if err != nil {
			if strings.Contains(err.Error(), "NoSuchEntity") {
				t.Logf("  IAM role %s does not exist (already clean)", roleName)
				continue
			}
			t.Logf("  Warning: Failed to list policies for role %s: %v", roleName, err)
			continue
		}

		cleanupRolePolicies(t, iamClient, roleName)

		_, err = iamClient.DeleteRole(&iam.DeleteRoleInput{
			RoleName: aws.String(roleName),
		})
		if err != nil {
			if strings.Contains(err.Error(), "NoSuchEntity") {
				t.Logf("  IAM role %s does not exist (already clean)", roleName)
			} else {
				t.Logf("  Warning: Failed to delete IAM role %s: %v", roleName, err)
			}
		} else {
			t.Logf("  Deleted IAM role: %s", roleName)
		}
	}
}

func emptyS3Bucket(t *testing.T, s3Client *s3.S3, bucketName string) error {
	listObjectsOutput, err := s3Client.ListObjectsV2(&s3.ListObjectsV2Input{
		Bucket: aws.String(bucketName),
	})
	if err != nil {
		return err
	}

	for _, object := range listObjectsOutput.Contents {
		_, err := s3Client.DeleteObject(&s3.DeleteObjectInput{
			Bucket: aws.String(bucketName),
			Key:    object.Key,
		})
		if err != nil {
			t.Logf("  Warning: Failed to delete object %s from bucket %s: %v", *object.Key, bucketName, err)
		}
	}

	listVersionsOutput, err := s3Client.ListObjectVersions(&s3.ListObjectVersionsInput{
		Bucket: aws.String(bucketName),
	})
	if err != nil {
		return nil
	}

	for _, version := range listVersionsOutput.Versions {
		_, err := s3Client.DeleteObject(&s3.DeleteObjectInput{
			Bucket:    aws.String(bucketName),
			Key:       version.Key,
			VersionId: version.VersionId,
		})
		if err != nil {
			t.Logf("  Warning: Failed to delete version %s of object %s: %v", *version.VersionId, *version.Key, err)
		}
	}

	for _, marker := range listVersionsOutput.DeleteMarkers {
		_, err := s3Client.DeleteObject(&s3.DeleteObjectInput{
			Bucket:    aws.String(bucketName),
			Key:       marker.Key,
			VersionId: marker.VersionId,
		})
		if err != nil {
			t.Logf("  Warning: Failed to delete marker %s of object %s: %v", *marker.VersionId, *marker.Key, err)
		}
	}

	return nil
}

func cleanupS3Buckets(t *testing.T, sess *session.Session, namePrefix string) {
	s3Client := s3.New(sess)

	accountID := terratest_aws.GetAccountId(t)
	bucketName := fmt.Sprintf("%s-reports-%s", namePrefix, accountID)

	err := emptyS3Bucket(t, s3Client, bucketName)
	if err != nil {
		if strings.Contains(err.Error(), "NoSuchBucket") {
			t.Logf("  S3 bucket %s does not exist (already clean)", bucketName)
			return
		}
		t.Logf("  Warning: Failed to list objects in bucket %s: %v", bucketName, err)
		return
	}

	_, err = s3Client.DeleteBucket(&s3.DeleteBucketInput{
		Bucket: aws.String(bucketName),
	})
	if err != nil {
		if strings.Contains(err.Error(), "NoSuchBucket") {
			t.Logf("  S3 bucket %s does not exist (already clean)", bucketName)
		} else {
			t.Logf("  Warning: Failed to delete S3 bucket %s: %v", bucketName, err)
		}
	} else {
		t.Logf("  Deleted S3 bucket: %s", bucketName)
	}
}

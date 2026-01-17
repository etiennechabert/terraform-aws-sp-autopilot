package test

import (
	"fmt"
	"strings"
	"testing"

	"github.com/aws/aws-sdk-go/aws"
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

	// Cleanup CloudWatch Log Groups
	cleanupLogGroups(t, sess, namePrefix)

	// Cleanup IAM Roles (must be done after detaching policies)
	cleanupIAMRoles(t, sess, namePrefix)

	// Cleanup S3 Buckets
	cleanupS3Buckets(t, sess, namePrefix)

	t.Logf("Cleanup complete for prefix: %s", namePrefix)
}

func cleanupLogGroups(t *testing.T, sess *terratest_aws.Session, namePrefix string) {
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
				t.Logf("  ✓ Log group %s does not exist (already clean)", logGroupName)
			} else {
				t.Logf("  ⚠ Failed to delete log group %s: %v", logGroupName, err)
			}
		} else {
			t.Logf("  ✓ Deleted log group: %s", logGroupName)
		}
	}
}

func cleanupIAMRoles(t *testing.T, sess *terratest_aws.Session, namePrefix string) {
	iamClient := iam.New(sess)

	roleNames := []string{
		fmt.Sprintf("%s-scheduler", namePrefix),
		fmt.Sprintf("%s-purchaser", namePrefix),
		fmt.Sprintf("%s-reporter", namePrefix),
	}

	for _, roleName := range roleNames {
		// First, list and detach all attached policies
		listPoliciesOutput, err := iamClient.ListAttachedRolePolicies(&iam.ListAttachedRolePoliciesInput{
			RoleName: aws.String(roleName),
		})
		if err != nil {
			if strings.Contains(err.Error(), "NoSuchEntity") {
				t.Logf("  ✓ IAM role %s does not exist (already clean)", roleName)
				continue
			} else {
				t.Logf("  ⚠ Failed to list policies for role %s: %v", roleName, err)
				continue
			}
		}

		// Detach all managed policies
		for _, policy := range listPoliciesOutput.AttachedPolicies {
			_, err := iamClient.DetachRolePolicy(&iam.DetachRolePolicyInput{
				RoleName:  aws.String(roleName),
				PolicyArn: policy.PolicyArn,
			})
			if err != nil {
				t.Logf("  ⚠ Failed to detach policy %s from role %s: %v", *policy.PolicyArn, roleName, err)
			}
		}

		// List and delete inline policies
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
					t.Logf("  ⚠ Failed to delete inline policy %s from role %s: %v", *policyName, roleName, err)
				}
			}
		}

		// Now delete the role
		_, err = iamClient.DeleteRole(&iam.DeleteRoleInput{
			RoleName: aws.String(roleName),
		})
		if err != nil {
			if strings.Contains(err.Error(), "NoSuchEntity") {
				t.Logf("  ✓ IAM role %s does not exist (already clean)", roleName)
			} else {
				t.Logf("  ⚠ Failed to delete IAM role %s: %v", roleName, err)
			}
		} else {
			t.Logf("  ✓ Deleted IAM role: %s", roleName)
		}
	}
}

func cleanupS3Buckets(t *testing.T, sess *terratest_aws.Session, namePrefix string) {
	s3Client := s3.New(sess)

	// Get AWS account ID for bucket name
	accountID := terratest_aws.GetAccountId(t)
	bucketName := fmt.Sprintf("%s-reports-%s", namePrefix, accountID)

	// First, delete all objects in the bucket
	listObjectsOutput, err := s3Client.ListObjectsV2(&s3.ListObjectsV2Input{
		Bucket: aws.String(bucketName),
	})
	if err != nil {
		if strings.Contains(err.Error(), "NoSuchBucket") {
			t.Logf("  ✓ S3 bucket %s does not exist (already clean)", bucketName)
			return
		} else {
			t.Logf("  ⚠ Failed to list objects in bucket %s: %v", bucketName, err)
			return
		}
	}

	// Delete all objects
	for _, object := range listObjectsOutput.Contents {
		_, err := s3Client.DeleteObject(&s3.DeleteObjectInput{
			Bucket: aws.String(bucketName),
			Key:    object.Key,
		})
		if err != nil {
			t.Logf("  ⚠ Failed to delete object %s from bucket %s: %v", *object.Key, bucketName, err)
		}
	}

	// Delete all object versions (if versioning is enabled)
	listVersionsOutput, err := s3Client.ListObjectVersions(&s3.ListObjectVersionsInput{
		Bucket: aws.String(bucketName),
	})
	if err == nil {
		for _, version := range listVersionsOutput.Versions {
			_, err := s3Client.DeleteObject(&s3.DeleteObjectInput{
				Bucket:    aws.String(bucketName),
				Key:       version.Key,
				VersionId: version.VersionId,
			})
			if err != nil {
				t.Logf("  ⚠ Failed to delete version %s of object %s: %v", *version.VersionId, *version.Key, err)
			}
		}

		// Delete all delete markers
		for _, marker := range listVersionsOutput.DeleteMarkers {
			_, err := s3Client.DeleteObject(&s3.DeleteObjectInput{
				Bucket:    aws.String(bucketName),
				Key:       marker.Key,
				VersionId: marker.VersionId,
			})
			if err != nil {
				t.Logf("  ⚠ Failed to delete marker %s of object %s: %v", *marker.VersionId, *marker.Key, err)
			}
		}
	}

	// Now delete the bucket
	_, err = s3Client.DeleteBucket(&s3.DeleteBucketInput{
		Bucket: aws.String(bucketName),
	})
	if err != nil {
		if strings.Contains(err.Error(), "NoSuchBucket") {
			t.Logf("  ✓ S3 bucket %s does not exist (already clean)", bucketName)
		} else {
			t.Logf("  ⚠ Failed to delete S3 bucket %s: %v", bucketName, err)
		}
	} else {
		t.Logf("  ✓ Deleted S3 bucket: %s", bucketName)
	}
}

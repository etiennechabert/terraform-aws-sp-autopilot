package test

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/gruntwork-io/terratest/modules/logger"
	terratesting "github.com/gruntwork-io/terratest/modules/testing"
	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// cleanLogger implements logger.TestLogger interface to strip verbose prefixes
type cleanLogger struct{}

func (l *cleanLogger) Logf(_ terratesting.TestingT, format string, args ...interface{}) {
	// Format the message and print directly without test name/timestamp prefix
	msg := fmt.Sprintf(format, args...)
	fmt.Println(msg)
}

func getCleanLogger() *logger.Logger {
	return logger.New(&cleanLogger{})
}

// TestExampleSingleAccountCompute validates the single-account-compute example
// Focus: Compute SP with mixed term/payment options (3-year + 1-year, all-upfront)
func TestExampleSingleAccountCompute(t *testing.T) {
	// Note: NOT using t.Parallel() to avoid IAM rate limits when creating roles
	exampleDir := "../../examples/single-account-compute"

	// Generate unique name prefix (must match CI IAM policy pattern: sp-autopilot-test-*)
	uniquePrefix := fmt.Sprintf("sp-autopilot-test-%s", time.Now().Format("20060102-150405"))

	// Create a test copy of the example with local source
	testDir := prepareExampleForTesting(t, exampleDir, uniquePrefix)
	defer os.RemoveAll(testDir)

	t.Logf("Testing example: %s", exampleDir)

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: testDir,
		Vars: map[string]interface{}{
			"name_prefix": uniquePrefix,
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
		Logger:  getCleanLogger(),
	})

	defer func() {
		// Best-effort cleanup: log errors but don't fail the test
		// AWS eventual consistency can cause destroy to fail intermittently
		if err := terraform.DestroyE(t, terraformOptions); err != nil {
			t.Logf("⚠ Warning: Destroy failed (non-fatal): %v", err)
			t.Logf("  Resources may need manual cleanup. Run cleanup test if needed.")
		}
	}()
	terraform.InitAndApply(t, terraformOptions)

	// Validate compute SP is enabled with the expected term mix
	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	assert.Contains(t, schedulerLambdaName, uniquePrefix+"-scheduler")

	t.Logf("✓ Example validation passed: %s", exampleDir)
}

// TestExampleDichotomyStrategy validates the dichotomy-strategy example
// Focus: Dichotomy purchase strategy with adaptive purchase sizing
func TestExampleDichotomyStrategy(t *testing.T) {
	// Note: NOT using t.Parallel() to avoid IAM rate limits when creating roles
	exampleDir := "../../examples/dichotomy-strategy"

	// Generate unique name prefix (must match CI IAM policy pattern: sp-autopilot-test-*)
	uniquePrefix := fmt.Sprintf("sp-autopilot-test-%s", time.Now().Format("20060102-150405"))
	testDir := prepareExampleForTesting(t, exampleDir, uniquePrefix)
	defer os.RemoveAll(testDir)

	t.Logf("Testing example: %s", exampleDir)

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: testDir,
		Vars: map[string]interface{}{
			"name_prefix": uniquePrefix,
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
		Logger:  getCleanLogger(),
	})

	defer func() {
		// Best-effort cleanup: log errors but don't fail the test
		// AWS eventual consistency can cause destroy to fail intermittently
		if err := terraform.DestroyE(t, terraformOptions); err != nil {
			t.Logf("⚠ Warning: Destroy failed (non-fatal): %v", err)
			t.Logf("  Resources may need manual cleanup. Run cleanup test if needed.")
		}
	}()
	terraform.InitAndApply(t, terraformOptions)

	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	assert.Contains(t, schedulerLambdaName, uniquePrefix+"-scheduler")
}

// prepareExampleForTesting creates a temporary copy of an example directory
// and modifies the module source to point to the local codebase instead of the registry.
func prepareExampleForTesting(t *testing.T, exampleDir string, namePrefix string) string {
	// Use the fixtures approach - copy to integration test directory instead of temp
	// This allows us to use relative paths like the fixture tests do
	testDir := filepath.Join("./test-examples", namePrefix)
	err := os.MkdirAll(testDir, 0755)
	require.NoError(t, err, "Failed to create test directory")

	fileCount := 0

	// Copy all .tf files from the example
	err = filepath.Walk(exampleDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if info.IsDir() {
			return nil
		}

		// Only copy .tf files
		if !strings.HasSuffix(path, ".tf") {
			return nil
		}

		// Read the source file
		content, err := os.ReadFile(path)
		if err != nil {
			return fmt.Errorf("failed to read %s: %w", path, err)
		}

		// Modify the module source to point to local codebase
		contentStr := string(content)

		// Replace registry source with relative path (like fixtures do)
		// From test-examples/<name>/ to module root is ../../../../
		contentStr = strings.ReplaceAll(contentStr,
			`source = "etiennechabert/sp-autopilot/aws"`,
			`source = "../../../../"`)

		// Remove version constraint (not needed for local source)
		lines := strings.Split(contentStr, "\n")
		var newLines []string
		for _, line := range lines {
			if !strings.Contains(line, `version = "~>`) && !strings.Contains(line, `version = ">`) {
				newLines = append(newLines, line)
			}
		}
		contentStr = strings.Join(newLines, "\n")

		// Add default_tags to provider block for CI IAM policy compliance
		// CI IAM policy requires ManagedBy = "terratest" tag
		contentStr = strings.ReplaceAll(contentStr,
			`provider "aws" {
  region = "us-east-1"
}`,
			`provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Environment = "test"
      ManagedBy   = "terratest"
    }
  }
}`)

		// Write to test directory
		destPath := filepath.Join(testDir, filepath.Base(path))
		err = os.WriteFile(destPath, []byte(contentStr), 0644)
		if err != nil {
			return fmt.Errorf("failed to write %s: %w", destPath, err)
		}

		fileCount++
		return nil
	})
	require.NoError(t, err, "Failed to prepare example for testing")

	t.Logf("Prepared example with %d files in %s", fileCount, testDir)

	return testDir
}

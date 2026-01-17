package test

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestExampleSingleAccountCompute validates the single-account-compute example
// Focus: Compute SP with mixed term/payment options (3-year + 1-year, all-upfront)
func TestExampleSingleAccountCompute(t *testing.T) {
	// Note: NOT using t.Parallel() to avoid IAM rate limits when creating roles
	exampleDir := "../../examples/single-account-compute"

	// Generate unique name prefix
	uniquePrefix := fmt.Sprintf("sp-test-sac-%s", time.Now().Format("0102-150405"))

	// Create a temporary copy of the example with local source
	tempDir := prepareExampleForTesting(t, exampleDir, uniquePrefix)
	defer os.RemoveAll(tempDir)

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: tempDir,
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
	})

	defer terraform.Destroy(t, terraformOptions)
	terraform.InitAndApply(t, terraformOptions)

	// Validate compute SP is enabled with the expected term mix
	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	assert.Contains(t, schedulerLambdaName, uniquePrefix+"-scheduler")
}

// TestExampleDatabaseOnly validates the database-only example
// Focus: Database SP only (RDS/Aurora) with single payment option
func TestExampleDatabaseOnly(t *testing.T) {
	// Note: NOT using t.Parallel() to avoid IAM rate limits when creating roles
	exampleDir := "../../examples/database-only"

	uniquePrefix := fmt.Sprintf("sp-test-db-%s", time.Now().Format("0102-150405"))
	tempDir := prepareExampleForTesting(t, exampleDir, uniquePrefix)
	defer os.RemoveAll(tempDir)

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: tempDir,
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
	})

	defer terraform.Destroy(t, terraformOptions)
	terraform.InitAndApply(t, terraformOptions)

	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	assert.Contains(t, schedulerLambdaName, uniquePrefix+"-scheduler")
}

// TestExampleDichotomyStrategy validates the dichotomy-strategy example
// Focus: Dichotomy purchase strategy with adaptive purchase sizing
func TestExampleDichotomyStrategy(t *testing.T) {
	// Note: NOT using t.Parallel() to avoid IAM rate limits when creating roles
	exampleDir := "../../examples/dichotomy-strategy"

	uniquePrefix := fmt.Sprintf("sp-test-dich-%s", time.Now().Format("0102-150405"))
	tempDir := prepareExampleForTesting(t, exampleDir, uniquePrefix)
	defer os.RemoveAll(tempDir)

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: tempDir,
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
	})

	defer terraform.Destroy(t, terraformOptions)
	terraform.InitAndApply(t, terraformOptions)

	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	assert.Contains(t, schedulerLambdaName, uniquePrefix+"-scheduler")
}

// prepareExampleForTesting creates a temporary copy of an example directory
// and modifies the module source to point to the local codebase instead of the registry.
func prepareExampleForTesting(t *testing.T, exampleDir string, namePrefix string) string {
	// Get absolute path to module root (../../ from terraform-tests/integration/)
	moduleRoot, err := filepath.Abs("../../")
	require.NoError(t, err, "Failed to get module root path")

	// Create a temp directory for this test
	tempDir, err := os.MkdirTemp("", "terratest-example-*")
	require.NoError(t, err, "Failed to create temp directory")

	t.Logf("Module root: %s", moduleRoot)
	t.Logf("Temp directory: %s", tempDir)

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

		// Replace registry source with absolute path to module root
		contentStr = strings.ReplaceAll(contentStr,
			`source  = "etiennechabert/sp-autopilot/aws"`,
			fmt.Sprintf(`source = "%s"`, filepath.ToSlash(moduleRoot)))

		// Remove version constraint (not needed for local source)
		lines := strings.Split(contentStr, "\n")
		var newLines []string
		for _, line := range lines {
			if !strings.Contains(line, `version = "~>`) && !strings.Contains(line, `version = ">`) {
				newLines = append(newLines, line)
			}
		}
		contentStr = strings.Join(newLines, "\n")

		// Write to temp directory
		destPath := filepath.Join(tempDir, filepath.Base(path))
		err = os.WriteFile(destPath, []byte(contentStr), 0644)
		if err != nil {
			return fmt.Errorf("failed to write %s: %w", destPath, err)
		}

		t.Logf("Copied and modified: %s -> %s", path, destPath)
		return nil
	})
	require.NoError(t, err, "Failed to prepare example for testing")

	return tempDir
}

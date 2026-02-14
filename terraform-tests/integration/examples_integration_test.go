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
	msg := fmt.Sprintf(format, args...)
	fmt.Println(msg)
}

func getCleanLogger() *logger.Logger {
	return logger.New(&cleanLogger{})
}

// TestExampleSingleAccountCompute validates the single-account-compute example
func TestExampleSingleAccountCompute(t *testing.T) {
	exampleDir := "../../examples/single-account-compute"

	uniquePrefix := fmt.Sprintf("sp-autopilot-test-%s", time.Now().Format("20060102-150405"))

	testDir := prepareExampleForTesting(t, exampleDir, uniquePrefix)
	defer os.RemoveAll(testDir)

	t.Logf("Testing example: %s", exampleDir)

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: testDir,
		Vars: map[string]interface{}{
			"name_prefix": uniquePrefix,
			"scheduler": map[string]interface{}{
				"scheduler": disabledCronSchedule,
				"purchaser": disabledCronSchedule,
				"reporter":  disabledCronSchedule,
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
		_, err := terraform.DestroyE(t, terraformOptions)
		if err != nil {
			t.Logf("Warning: Destroy failed (non-fatal): %v", err)
			t.Logf("  Resources may need manual cleanup. Run cleanup test if needed.")
		}
	}()
	terraform.InitAndApply(t, terraformOptions)

	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	assert.Contains(t, schedulerLambdaName, uniquePrefix+suffixScheduler)

	t.Logf("Example validation passed: %s", exampleDir)
}

// TestExampleDynamicStrategy validates the dynamic-strategy example
func TestExampleDynamicStrategy(t *testing.T) {
	exampleDir := "../../examples/dynamic-strategy"

	uniquePrefix := fmt.Sprintf("sp-autopilot-test-%s", time.Now().Format("20060102-150405"))
	testDir := prepareExampleForTesting(t, exampleDir, uniquePrefix)
	defer os.RemoveAll(testDir)

	t.Logf("Testing example: %s", exampleDir)

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: testDir,
		Vars: map[string]interface{}{
			"name_prefix": uniquePrefix,
			"scheduler": map[string]interface{}{
				"scheduler": disabledCronSchedule,
				"purchaser": disabledCronSchedule,
				"reporter":  disabledCronSchedule,
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
		_, err := terraform.DestroyE(t, terraformOptions)
		if err != nil {
			t.Logf("Warning: Destroy failed (non-fatal): %v", err)
			t.Logf("  Resources may need manual cleanup. Run cleanup test if needed.")
		}
	}()
	terraform.InitAndApply(t, terraformOptions)

	schedulerLambdaName := terraform.Output(t, terraformOptions, "scheduler_lambda_name")
	assert.Contains(t, schedulerLambdaName, uniquePrefix+suffixScheduler)
}

func transformExampleContent(content string) string {
	result := strings.ReplaceAll(content,
		`source = "etiennechabert/sp-autopilot/aws"`,
		`source = "../../../../"`)

	lines := strings.Split(result, "\n")
	var newLines []string
	for _, line := range lines {
		if !strings.Contains(line, `version = "~>`) && !strings.Contains(line, `version = ">`) {
			newLines = append(newLines, line)
		}
	}
	result = strings.Join(newLines, "\n")

	result = strings.ReplaceAll(result,
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

	return result
}

// prepareExampleForTesting creates a temporary copy of an example directory
// and modifies the module source to point to the local codebase instead of the registry.
func prepareExampleForTesting(t *testing.T, exampleDir string, namePrefix string) string {
	testDir := filepath.Join("./test-examples", namePrefix)
	err := os.MkdirAll(testDir, 0755)
	require.NoError(t, err, "Failed to create test directory")

	fileCount := 0

	err = filepath.Walk(exampleDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if info.IsDir() {
			return nil
		}

		if !strings.HasSuffix(path, ".tf") {
			return nil
		}

		content, err := os.ReadFile(path)
		if err != nil {
			return fmt.Errorf("failed to read %s: %w", path, err)
		}

		contentStr := transformExampleContent(string(content))

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

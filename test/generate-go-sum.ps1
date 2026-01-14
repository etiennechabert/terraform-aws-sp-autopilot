# Helper script to generate go.sum file for Terratest
#
# This script must be run from the test/ directory with Go installed
#
# Usage:
#   cd test
#   .\generate-go-sum.ps1
#

Write-Host "=== Generating go.sum for Terratest ===" -ForegroundColor Cyan
Write-Host ""

# Check if Go is installed
try {
    $goVersion = go version
    Write-Host "Found: $goVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Go is not installed or not in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Go 1.21 or higher:"
    Write-Host "  1. Download: https://go.dev/dl/go1.21.6.windows-amd64.msi"
    Write-Host "  2. Run the installer"
    Write-Host "  3. Restart PowerShell/Terminal"
    Write-Host "  4. Verify: go version"
    Write-Host ""
    exit 1
}

# Ensure we're in the test directory
if (-not (Test-Path "go.mod")) {
    Write-Host "ERROR: go.mod not found. Please run this script from the test/ directory" -ForegroundColor Red
    exit 1
}

Write-Host "Downloading Go modules..." -ForegroundColor Yellow
go mod download

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to download modules" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Verifying Go modules..." -ForegroundColor Yellow
go mod verify

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to verify modules" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "✓ go.sum generated successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Run all tests: go test -v -timeout 30m"
Write-Host "  2. Run single test: go test -v -run TestTerraformBasicDeployment -timeout 15m"
Write-Host ""

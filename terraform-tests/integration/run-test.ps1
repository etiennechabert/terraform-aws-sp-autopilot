#
# Test Runner Script - Run Terratest Integration Tests (PowerShell)
#
# This script validates prerequisites and runs the Terratest integration tests
# with proper error handling and output formatting.
#
# Usage:
#   .\run-test.ps1 [-TestName <name>] [-Verbose] [-Timeout <duration>]
#
# Examples:
#   .\run-test.ps1                                        # Run all tests
#   .\run-test.ps1 -TestName TestTerraformBasicDeployment # Run specific test
#   .\run-test.ps1 -Verbose                               # Run with verbose output
#

[CmdletBinding()]
param(
    [string]$TestName = "",
    [switch]$Verbose,
    [string]$Timeout = "30m"
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Color output functions
function Write-Status {
    param([string]$Message)
    Write-Host "==> " -ForegroundColor Blue -NoNewline
    Write-Host $Message
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Failure {
    param([string]$Message)
    Write-Host "✗ " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "! " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

# Change to test directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host ""
Write-Status "Terratest Integration Test Runner"
Write-Host ""

# ============================================================================
# Prerequisite Checks
# ============================================================================

Write-Status "Checking prerequisites..."

# Check Go installation
try {
    $goVersion = (go version 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "Go command failed"
    }

    # Extract version number
    if ($goVersion -match 'go(\d+\.\d+)') {
        $version = $matches[1]
        $majorMinor = $version.Split('.')
        $major = [int]$majorMinor[0]
        $minor = [int]$majorMinor[1]

        if ($major -lt 1 -or ($major -eq 1 -and $minor -lt 21)) {
            Write-Failure "Go version $version is too old (requires 1.21+)"
            Write-Host ""
            Write-Host "Please upgrade Go:"
            Write-Host "  - Current: $version"
            Write-Host "  - Required: 1.21+"
            Write-Host ""
            exit 1
        }

        Write-Success "Go $version"
    } else {
        Write-Success "Go installed"
    }
}
catch {
    Write-Failure "Go is not installed or not in PATH"
    Write-Host ""
    Write-Host "Please install Go 1.21 or higher:"
    Write-Host "  - See INSTALL.md for installation instructions"
    Write-Host "  - Or visit: https://golang.org/doc/install"
    Write-Host ""
    exit 1
}

# Check if go.sum exists (dependencies downloaded)
if (-not (Test-Path "go.sum")) {
    Write-Warning-Custom "go.sum not found - downloading dependencies..."

    try {
        go mod download
        if ($LASTEXITCODE -ne 0) {
            throw "go mod download failed"
        }

        go mod verify
        if ($LASTEXITCODE -ne 0) {
            throw "go mod verify failed"
        }

        Write-Success "Dependencies downloaded and verified"
    }
    catch {
        Write-Failure "Failed to download Go dependencies: $_"
        exit 1
    }
}
else {
    Write-Success "Dependencies verified (go.sum exists)"
}

# Check Terraform installation
try {
    $tfVersion = (terraform version -json 2>$null | ConvertFrom-Json).terraform_version
    if ($LASTEXITCODE -ne 0) {
        throw "Terraform command failed"
    }
    Write-Success "Terraform $tfVersion"
}
catch {
    Write-Failure "Terraform is not installed or not in PATH"
    Write-Host ""
    Write-Host "Please install Terraform 1.0 or higher:"
    Write-Host "  - Visit: https://www.terraform.io/downloads"
    Write-Host ""
    exit 1
}

# Check AWS credentials
Write-Status "Checking AWS credentials..."

$hasCredentials = $false

if ($env:AWS_ACCESS_KEY_ID -or $env:AWS_PROFILE -or (Test-Path "$env:USERPROFILE\.aws\credentials")) {
    $hasCredentials = $true
}

if (-not $hasCredentials) {
    Write-Warning-Custom "No AWS credentials found"
    Write-Host ""
    Write-Host "Tests require AWS credentials to deploy infrastructure."
    Write-Host "Please configure AWS credentials using one of:"
    Write-Host "  1. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
    Write-Host "  2. AWS Profile: `$env:AWS_PROFILE='your-profile'"
    Write-Host "  3. AWS credentials file: ~/.aws/credentials"
    Write-Host ""
    Write-Host "See test/README.md for more details."
    Write-Host ""

    $response = Read-Host "Continue anyway? (y/N)"
    if ($response -ne "y" -and $response -ne "Y") {
        exit 1
    }
}
else {
    # Try to verify AWS credentials work
    try {
        $awsIdentity = (aws sts get-caller-identity 2>$null | ConvertFrom-Json)
        if ($LASTEXITCODE -eq 0) {
            $awsAccount = $awsIdentity.Account
            $awsRegion = (aws configure get region 2>$null)
            if (-not $awsRegion) {
                $awsRegion = if ($env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION } else { "us-east-1" }
            }
            Write-Success "AWS credentials valid (Account: $awsAccount, Region: $awsRegion)"
        }
        else {
            Write-Warning-Custom "AWS credentials found but validation failed"
        }
    }
    catch {
        Write-Success "AWS environment variables set"
    }
}

Write-Host ""

# ============================================================================
# Run Tests
# ============================================================================

# Build test command
$testCmd = "go test"

if ($Verbose) {
    $testCmd += " -v"
}

$testCmd += " -timeout $Timeout"

if ($TestName) {
    $testCmd += " -run $TestName"
    Write-Status "Running test: $TestName"
}
else {
    Write-Status "Running all tests (this may take up to 30 minutes)..."
}

Write-Host ""
Write-Status "Test Command: $testCmd"
Write-Host ""

# Run the tests
try {
    Invoke-Expression $testCmd

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Success "Tests completed successfully!"
        Write-Host ""
        exit 0
    }
    else {
        throw "Tests failed with exit code $LASTEXITCODE"
    }
}
catch {
    Write-Host ""
    Write-Failure "Tests failed: $_"
    Write-Host ""
    Write-Host "Common issues:"
    Write-Host "  - Insufficient AWS permissions"
    Write-Host "  - AWS service quotas/limits reached"
    Write-Host "  - Network connectivity issues"
    Write-Host "  - Resource naming conflicts"
    Write-Host ""
    Write-Host "See test/README.md for troubleshooting guidance."
    Write-Host ""
    exit 1
}

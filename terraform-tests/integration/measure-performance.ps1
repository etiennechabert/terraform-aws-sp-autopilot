#
# Performance Measurement Script - Measure Terratest Execution Time (PowerShell)
#
# This script runs the full Terratest suite with detailed timing measurements
# and generates a performance report. Use this to validate the test suite
# completes within the 15-minute target.
#
# Usage:
#   .\measure-performance.ps1 [-Save] [-Compare]
#
# Examples:
#   .\measure-performance.ps1              # Run all tests with timing
#   .\measure-performance.ps1 -Save        # Save results to performance report
#   .\measure-performance.ps1 -Compare     # Compare with previous run
#

[CmdletBinding()]
param(
    [switch]$Save,
    [switch]$Compare,
    [switch]$Help
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Configuration
$ReportFile = "performance-report.txt"
$ResultsFile = "test-results.log"

# Color output functions
function Write-Header {
    param([string]$Message)
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
    Write-Host "  $Message" -ForegroundColor Blue
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
}

function Write-Status {
    param([string]$Message)
    Write-Host "▶ " -ForegroundColor Cyan -NoNewline
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

function Write-Metric {
    param(
        [string]$Label,
        [string]$Value
    )
    $padding = 35 - $Label.Length
    Write-Host $Label -ForegroundColor Cyan -NoNewline
    Write-Host (" " * $padding) -NoNewline
    Write-Host $Value
}

# Convert timespan to human-readable format
function Format-Duration {
    param([int]$TotalSeconds)

    $minutes = [Math]::Floor($TotalSeconds / 60)
    $seconds = $TotalSeconds % 60

    if ($minutes -eq 0) {
        return "${seconds}s"
    }
    else {
        return "${minutes}m ${seconds}s"
    }
}

# Show help
if ($Help) {
    Write-Host "Usage: .\measure-performance.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Save       Save performance results to $ReportFile"
    Write-Host "  -Compare    Compare with previous performance report"
    Write-Host "  -Help       Show this help message"
    Write-Host ""
    exit 0
}

# Change to test directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# ============================================================================
# Header
# ============================================================================

Write-Host ""
Write-Header "Terratest Performance Measurement"
Write-Host ""
Write-Host "This script measures the execution time of the full Terratest suite"
Write-Host "Target: Complete all 7 tests in under 15 minutes (900 seconds)"
Write-Host ""

# ============================================================================
# Compare with Previous Run (if requested)
# ============================================================================

if ($Compare) {
    if (Test-Path $ReportFile) {
        Write-Status "Previous performance report found:"
        Write-Host ""
        Get-Content $ReportFile
        Write-Host ""

        $response = Read-Host "Continue with new measurement? (y/N)"
        if ($response -ne "y" -and $response -ne "Y") {
            exit 0
        }
    }
    else {
        Write-Warning-Custom "No previous performance report found at $ReportFile"
        Write-Host ""
    }
}

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

    if ($goVersion -match 'go(\d+\.\d+\.\d+)') {
        $version = $matches[1]
        Write-Success "Go $version"
    }
    else {
        Write-Success "Go installed"
    }
}
catch {
    Write-Failure "Go is not installed or not in PATH"
    Write-Host ""
    Write-Host "Please install Go 1.21+ (see INSTALL.md)"
    exit 1
}

# Check Terraform installation
try {
    $tfVersionObj = (terraform version -json 2>$null | ConvertFrom-Json)
    $tfVersion = $tfVersionObj.terraform_version
    Write-Success "Terraform $tfVersion"
}
catch {
    Write-Failure "Terraform is not installed or not in PATH"
    Write-Host ""
    Write-Host "Please install Terraform 1.0+ (see README.md)"
    exit 1
}

# Check AWS credentials
$hasCredentials = $false

if ($env:AWS_ACCESS_KEY_ID -or $env:AWS_PROFILE -or (Test-Path "$env:USERPROFILE\.aws\credentials")) {
    $hasCredentials = $true
}

if (-not $hasCredentials) {
    Write-Warning-Custom "No AWS credentials configured"
    Write-Host ""
    Write-Host "Tests require valid AWS credentials. See README.md for setup."
    Write-Host ""

    $response = Read-Host "Continue anyway? (y/N)"
    if ($response -ne "y" -and $response -ne "Y") {
        exit 1
    }
}
else {
    Write-Success "AWS credentials configured"
}

# Check if dependencies are downloaded
if (-not (Test-Path "go.sum")) {
    Write-Status "Downloading Go dependencies..."

    go mod download
    if ($LASTEXITCODE -ne 0) {
        Write-Failure "Failed to download dependencies"
        exit 1
    }

    go mod verify
    if ($LASTEXITCODE -ne 0) {
        Write-Failure "Failed to verify dependencies"
        exit 1
    }

    Write-Success "Dependencies downloaded"
}

Write-Host ""

# ============================================================================
# Run Tests with Timing
# ============================================================================

Write-Header "Running Full Test Suite"
Write-Host ""

Write-Status "Starting test execution..."
Write-Status "Output will be saved to: $ResultsFile"
Write-Host ""

# Record start time
$StartTime = Get-Date
$StartTimestamp = $StartTime.ToString("yyyy-MM-dd HH:mm:ss")

# Prepare results file
"Test execution started at: $StartTimestamp" | Out-File -FilePath $ResultsFile -Encoding UTF8
"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | Out-File -FilePath $ResultsFile -Append -Encoding UTF8
"" | Out-File -FilePath $ResultsFile -Append -Encoding UTF8

# Run tests and capture output
$testExitCode = 0

try {
    # Run tests with output to both console and file
    $output = go test -v -timeout 30m 2>&1 | Tee-Object -FilePath $ResultsFile -Append

    if ($LASTEXITCODE -ne 0) {
        $testExitCode = $LASTEXITCODE
    }
}
catch {
    $testExitCode = 1
}

# Record end time
$EndTime = Get-Date
$EndTimestamp = $EndTime.ToString("yyyy-MM-dd HH:mm:ss")

# Calculate duration
$Duration = ($EndTime - $StartTime).TotalSeconds
$DurationFormatted = Format-Duration ([int]$Duration)

"" | Out-File -FilePath $ResultsFile -Append -Encoding UTF8
"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | Out-File -FilePath $ResultsFile -Append -Encoding UTF8
"Test execution completed at: $EndTimestamp" | Out-File -FilePath $ResultsFile -Append -Encoding UTF8
"Total duration: $DurationFormatted ($([int]$Duration) seconds)" | Out-File -FilePath $ResultsFile -Append -Encoding UTF8

Write-Host ""
Write-Host ""

# ============================================================================
# Performance Summary
# ============================================================================

Write-Header "Performance Summary"
Write-Host ""

Write-Metric "Start Time:" $StartTimestamp
Write-Metric "End Time:" $EndTimestamp
Write-Metric "Total Duration:" "$DurationFormatted ($([int]$Duration) seconds)"

# Check if within target
$TargetSeconds = 900  # 15 minutes

if ($Duration -le $TargetSeconds) {
    $Remaining = $TargetSeconds - $Duration
    $RemainingFormatted = Format-Duration ([int]$Remaining)
    Write-Host ""
    Write-Success "Performance target MET! ✓"
    Write-Metric "Target:" "< 15 minutes (900 seconds)"
    Write-Metric "Under target by:" $RemainingFormatted
}
else {
    $Overtime = $Duration - $TargetSeconds
    $OvertimeFormatted = Format-Duration ([int]$Overtime)
    Write-Host ""
    Write-Failure "Performance target EXCEEDED ✗"
    Write-Metric "Target:" "< 15 minutes (900 seconds)"
    Write-Metric "Over target by:" $OvertimeFormatted
}

# Test result
Write-Host ""
if ($testExitCode -eq 0) {
    Write-Success "All tests PASSED"
}
else {
    Write-Failure "Some tests FAILED (exit code: $testExitCode)"
}

Write-Host ""
Write-Status "Detailed results saved to: $ResultsFile"

# ============================================================================
# Extract Individual Test Timings (if available)
# ============================================================================

$testResults = Get-Content $ResultsFile | Select-String -Pattern "^--- (PASS|FAIL):"

if ($testResults) {
    Write-Host ""
    Write-Header "Individual Test Timings"
    Write-Host ""

    foreach ($result in $testResults) {
        if ($result -match "--- PASS:\s+(\S+)\s+\(([^)]+)\)") {
            $testName = $matches[1]
            $testTime = $matches[2]
            Write-Host "✓ " -ForegroundColor Green -NoNewline
            Write-Host ("{0,-40} {1}" -f $testName, $testTime)
        }
        elseif ($result -match "--- FAIL:\s+(\S+)\s+\(([^)]+)\)") {
            $testName = $matches[1]
            $testTime = $matches[2]
            Write-Host "✗ " -ForegroundColor Red -NoNewline
            Write-Host ("{0,-40} {1}" -f $testName, $testTime)
        }
    }
}

# ============================================================================
# Save Performance Report (if requested)
# ============================================================================

if ($Save) {
    Write-Host ""
    Write-Status "Saving performance report to: $ReportFile"

    $reportContent = @"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Terratest Performance Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Execution Date:    $StartTimestamp
Go Version:        $(if ($goVersion -match 'go(\d+\.\d+\.\d+)') { $matches[1] } else { 'unknown' })
Terraform Version: $tfVersion

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Performance Metrics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Duration:    $DurationFormatted ($([int]$Duration) seconds)
Target Duration:   15 minutes (900 seconds)
Status:            $(if ($Duration -le $TargetSeconds) { "PASS ✓" } else { "FAIL ✗" })
Test Result:       $(if ($testExitCode -eq 0) { "PASS ✓" } else { "FAIL ✗" })

"@

    # Add individual test timings if available
    if ($testResults) {
        $reportContent += "`n"
        $reportContent += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n"
        $reportContent += "Individual Test Timings`n"
        $reportContent += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n"
        $reportContent += "`n"

        foreach ($result in $testResults) {
            if ($result -match "--- PASS:\s+(\S+)\s+\(([^)]+)\)") {
                $testName = $matches[1]
                $testTime = $matches[2]
                $reportContent += ("✓ {0,-40} {1}`n" -f $testName, $testTime)
            }
            elseif ($result -match "--- FAIL:\s+(\S+)\s+\(([^)]+)\)") {
                $testName = $matches[1]
                $testTime = $matches[2]
                $reportContent += ("✗ {0,-40} {1}`n" -f $testName, $testTime)
            }
        }
    }

    $reportContent += "`n"
    $reportContent += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n"
    $reportContent += "Full test output saved to: $ResultsFile`n"
    $reportContent += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n"

    $reportContent | Out-File -FilePath $ReportFile -Encoding UTF8

    Write-Success "Performance report saved"
}

# ============================================================================
# Footer
# ============================================================================

Write-Host ""
Write-Header "Next Steps"
Write-Host ""

if (($testExitCode -eq 0) -and ($Duration -le $TargetSeconds)) {
    Write-Host "✓ All tests passed within performance target"
    Write-Host ""
    Write-Host "The test suite is ready for production use."
}
else {
    if ($testExitCode -ne 0) {
        Write-Host "✗ Tests failed - review $ResultsFile for details"
        Write-Host ""
    }

    if ($Duration -gt $TargetSeconds) {
        Write-Host "! Performance target exceeded"
        Write-Host ""
        Write-Host "Consider:"
        Write-Host "  - Reviewing slow tests in the timing breakdown"
        Write-Host "  - Running tests in parallel (go test -parallel 4)"
        Write-Host "  - Optimizing Terraform apply/destroy operations"
        Write-Host "  - Using faster AWS regions"
    }
}

Write-Host ""

# Exit with test exit code
exit $testExitCode

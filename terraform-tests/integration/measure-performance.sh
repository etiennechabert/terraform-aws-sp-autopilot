#!/usr/bin/env bash
#
# Performance Measurement Script - Measure Terratest Execution Time
#
# This script runs the full Terratest suite with detailed timing measurements
# and generates a performance report. Use this to validate the test suite
# completes within the 15-minute target.
#
# Usage:
#   ./measure-performance.sh [options]
#
# Examples:
#   ./measure-performance.sh              # Run all tests with timing
#   ./measure-performance.sh --save       # Save results to performance report
#   ./measure-performance.sh --compare    # Compare with previous run
#

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_status() {
    echo -e "${CYAN}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

print_metric() {
    printf "${CYAN}%-35s${NC} %s\n" "$1" "$2"
}

# Convert seconds to human-readable format
format_duration() {
    local total_seconds=$1
    local minutes=$((total_seconds / 60))
    local seconds=$((total_seconds % 60))

    if [ $minutes -eq 0 ]; then
        echo "${seconds}s"
    else
        echo "${minutes}m ${seconds}s"
    fi
}

# Change to test directory
cd "$(dirname "$0")"

REPORT_FILE="performance-report.txt"
RESULTS_FILE="test-results.log"
SAVE_REPORT=false
COMPARE_MODE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --save|-s)
            SAVE_REPORT=true
            shift
            ;;
        --compare|-c)
            COMPARE_MODE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --save, -s       Save performance results to $REPORT_FILE"
            echo "  --compare, -c    Compare with previous performance report"
            echo "  --help, -h       Show this help message"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ============================================================================
# Header
# ============================================================================

echo ""
print_header "Terratest Performance Measurement"
echo ""
echo "This script measures the execution time of the full Terratest suite"
echo "Target: Complete all 7 tests in under 15 minutes (900 seconds)"
echo ""

# ============================================================================
# Compare with Previous Run (if requested)
# ============================================================================

if [ "$COMPARE_MODE" = true ]; then
    if [ -f "$REPORT_FILE" ]; then
        print_status "Previous performance report found:"
        echo ""
        cat "$REPORT_FILE"
        echo ""
        read -p "Continue with new measurement? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 0
        fi
    else
        print_warning "No previous performance report found at $REPORT_FILE"
        echo ""
    fi
fi

# ============================================================================
# Prerequisite Checks
# ============================================================================

print_status "Checking prerequisites..."

# Check Go installation
if ! command -v go &> /dev/null; then
    print_error "Go is not installed or not in PATH"
    echo ""
    echo "Please install Go 1.21+ (see INSTALL.md)"
    exit 1
fi

GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
print_success "Go $GO_VERSION"

# Check Terraform installation
if ! command -v terraform &> /dev/null; then
    print_error "Terraform is not installed or not in PATH"
    echo ""
    echo "Please install Terraform 1.0+ (see README.md)"
    exit 1
fi

TERRAFORM_VERSION=$(terraform version -json | grep -o '"terraform_version":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "unknown")
print_success "Terraform $TERRAFORM_VERSION"

# Check AWS credentials
if [ -z "$AWS_ACCESS_KEY_ID" ] && [ -z "$AWS_PROFILE" ] && [ ! -f "$HOME/.aws/credentials" ]; then
    print_warning "No AWS credentials configured"
    echo ""
    echo "Tests require valid AWS credentials. See README.md for setup."
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    print_success "AWS credentials configured"
fi

# Check if dependencies are downloaded
if [ ! -f "go.sum" ]; then
    print_status "Downloading Go dependencies..."
    go mod download
    go mod verify
    print_success "Dependencies downloaded"
fi

echo ""

# ============================================================================
# Run Tests with Timing
# ============================================================================

print_header "Running Full Test Suite"
echo ""

print_status "Starting test execution..."
print_status "Output will be saved to: $RESULTS_FILE"
echo ""

# Record start time
START_TIME=$(date +%s)
START_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Run tests with timing and capture output
echo "Test execution started at: $START_TIMESTAMP" > "$RESULTS_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

if time go test -v -timeout 30m 2>&1 | tee -a "$RESULTS_FILE"; then
    TEST_EXIT_CODE=0
else
    TEST_EXIT_CODE=$?
fi

# Record end time
END_TIME=$(date +%s)
END_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Calculate duration
DURATION=$((END_TIME - START_TIME))
DURATION_FORMATTED=$(format_duration $DURATION)

echo "" >> "$RESULTS_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$RESULTS_FILE"
echo "Test execution completed at: $END_TIMESTAMP" >> "$RESULTS_FILE"
echo "Total duration: $DURATION_FORMATTED ($DURATION seconds)" >> "$RESULTS_FILE"

echo ""
echo ""

# ============================================================================
# Performance Summary
# ============================================================================

print_header "Performance Summary"
echo ""

print_metric "Start Time:" "$START_TIMESTAMP"
print_metric "End Time:" "$END_TIMESTAMP"
print_metric "Total Duration:" "$DURATION_FORMATTED ($DURATION seconds)"

# Check if within target
TARGET_SECONDS=900  # 15 minutes
if [ $DURATION -le $TARGET_SECONDS ]; then
    REMAINING=$((TARGET_SECONDS - DURATION))
    REMAINING_FORMATTED=$(format_duration $REMAINING)
    echo ""
    print_success "Performance target MET! ✓"
    print_metric "Target:" "< 15 minutes (900 seconds)"
    print_metric "Under target by:" "$REMAINING_FORMATTED"
else
    OVERTIME=$((DURATION - TARGET_SECONDS))
    OVERTIME_FORMATTED=$(format_duration $OVERTIME)
    echo ""
    print_error "Performance target EXCEEDED ✗"
    print_metric "Target:" "< 15 minutes (900 seconds)"
    print_metric "Over target by:" "$OVERTIME_FORMATTED"
fi

# Test result
echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    print_success "All tests PASSED"
else
    print_error "Some tests FAILED (exit code: $TEST_EXIT_CODE)"
fi

echo ""
print_status "Detailed results saved to: $RESULTS_FILE"

# ============================================================================
# Extract Individual Test Timings (if available)
# ============================================================================

if grep -q "^--- PASS:" "$RESULTS_FILE" || grep -q "^--- FAIL:" "$RESULTS_FILE"; then
    echo ""
    print_header "Individual Test Timings"
    echo ""

    # Extract test timings from output
    grep -E "^--- (PASS|FAIL):" "$RESULTS_FILE" | while read -r line; do
        if [[ $line =~ PASS:\ ([^\ ]+)\ \(([^)]+)\) ]]; then
            test_name="${BASH_REMATCH[1]}"
            test_time="${BASH_REMATCH[2]}"
            printf "${GREEN}✓${NC} %-40s %s\n" "$test_name" "$test_time"
        elif [[ $line =~ FAIL:\ ([^\ ]+)\ \(([^)]+)\) ]]; then
            test_name="${BASH_REMATCH[1]}"
            test_time="${BASH_REMATCH[2]}"
            printf "${RED}✗${NC} %-40s %s\n" "$test_name" "$test_time"
        fi
    done
fi

# ============================================================================
# Save Performance Report (if requested)
# ============================================================================

if [ "$SAVE_REPORT" = true ]; then
    echo ""
    print_status "Saving performance report to: $REPORT_FILE"

    cat > "$REPORT_FILE" << EOF
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Terratest Performance Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Execution Date:    $START_TIMESTAMP
Go Version:        $GO_VERSION
Terraform Version: $TERRAFORM_VERSION

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Performance Metrics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Duration:    $DURATION_FORMATTED ($DURATION seconds)
Target Duration:   15 minutes (900 seconds)
Status:            $([ $DURATION -le $TARGET_SECONDS ] && echo "PASS ✓" || echo "FAIL ✗")
Test Result:       $([ $TEST_EXIT_CODE -eq 0 ] && echo "PASS ✓" || echo "FAIL ✗")

EOF

    # Add individual test timings if available
    if grep -q "^--- PASS:" "$RESULTS_FILE" || grep -q "^--- FAIL:" "$RESULTS_FILE"; then
        echo "" >> "$REPORT_FILE"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT_FILE"
        echo "Individual Test Timings" >> "$REPORT_FILE"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"

        grep -E "^--- (PASS|FAIL):" "$RESULTS_FILE" | while read -r line; do
            if [[ $line =~ PASS:\ ([^\ ]+)\ \(([^)]+)\) ]]; then
                printf "✓ %-40s %s\n" "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" >> "$REPORT_FILE"
            elif [[ $line =~ FAIL:\ ([^\ ]+)\ \(([^)]+)\) ]]; then
                printf "✗ %-40s %s\n" "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" >> "$REPORT_FILE"
            fi
        done
    fi

    echo "" >> "$REPORT_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT_FILE"
    echo "Full test output saved to: $RESULTS_FILE" >> "$REPORT_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT_FILE"

    print_success "Performance report saved"
fi

# ============================================================================
# Footer
# ============================================================================

echo ""
print_header "Next Steps"
echo ""

if [ $TEST_EXIT_CODE -eq 0 ] && [ $DURATION -le $TARGET_SECONDS ]; then
    echo "✓ All tests passed within performance target"
    echo ""
    echo "The test suite is ready for production use."
else
    if [ $TEST_EXIT_CODE -ne 0 ]; then
        echo "✗ Tests failed - review $RESULTS_FILE for details"
        echo ""
    fi

    if [ $DURATION -gt $TARGET_SECONDS ]; then
        echo "! Performance target exceeded"
        echo ""
        echo "Consider:"
        echo "  - Reviewing slow tests in the timing breakdown"
        echo "  - Running tests in parallel (go test -parallel 4)"
        echo "  - Optimizing Terraform apply/destroy operations"
        echo "  - Using faster AWS regions"
    fi
fi

echo ""

# Exit with test exit code
exit $TEST_EXIT_CODE

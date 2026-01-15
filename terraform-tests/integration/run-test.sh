#!/usr/bin/env bash
#
# Test Runner Script - Run Terratest Integration Tests
#
# This script validates prerequisites and runs the Terratest integration tests
# with proper error handling and output formatting.
#
# Usage:
#   ./run-test.sh [test-name] [options]
#
# Examples:
#   ./run-test.sh                              # Run all tests
#   ./run-test.sh TestTerraformBasicDeployment # Run specific test
#   ./run-test.sh --verbose                    # Run with verbose output
#

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}==>${NC} $1"
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

# Change to test directory
cd "$(dirname "$0")"

echo ""
print_status "Terratest Integration Test Runner"
echo ""

# ============================================================================
# Prerequisite Checks
# ============================================================================

print_status "Checking prerequisites..."

# Check Go installation
if ! command -v go &> /dev/null; then
    print_error "Go is not installed or not in PATH"
    echo ""
    echo "Please install Go 1.21 or higher:"
    echo "  - See INSTALL.md for installation instructions"
    echo "  - Or visit: https://golang.org/doc/install"
    echo ""
    exit 1
fi

# Check Go version
GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
GO_MAJOR=$(echo "$GO_VERSION" | cut -d. -f1)
GO_MINOR=$(echo "$GO_VERSION" | cut -d. -f2)

if [ "$GO_MAJOR" -lt 1 ] || ([ "$GO_MAJOR" -eq 1 ] && [ "$GO_MINOR" -lt 21 ]); then
    print_error "Go version $GO_VERSION is too old (requires 1.21+)"
    echo ""
    echo "Please upgrade Go:"
    echo "  - Current: $GO_VERSION"
    echo "  - Required: 1.21+"
    echo ""
    exit 1
fi

print_success "Go $GO_VERSION"

# Check if go.sum exists (dependencies downloaded)
if [ ! -f "go.sum" ]; then
    print_warning "go.sum not found - downloading dependencies..."
    if ! go mod download; then
        print_error "Failed to download Go dependencies"
        exit 1
    fi
    if ! go mod verify; then
        print_error "Go module verification failed"
        exit 1
    fi
    print_success "Dependencies downloaded and verified"
else
    print_success "Dependencies verified (go.sum exists)"
fi

# Check Terraform installation
if ! command -v terraform &> /dev/null; then
    print_error "Terraform is not installed or not in PATH"
    echo ""
    echo "Please install Terraform 1.0 or higher:"
    echo "  - Visit: https://www.terraform.io/downloads"
    echo ""
    exit 1
fi

TERRAFORM_VERSION=$(terraform version -json | grep -o '"terraform_version":"[^"]*"' | cut -d'"' -f4)
print_success "Terraform $TERRAFORM_VERSION"

# Check AWS credentials
print_status "Checking AWS credentials..."

if [ -z "$AWS_ACCESS_KEY_ID" ] && [ -z "$AWS_PROFILE" ] && [ ! -f "$HOME/.aws/credentials" ]; then
    print_warning "No AWS credentials found"
    echo ""
    echo "Tests require AWS credentials to deploy infrastructure."
    echo "Please configure AWS credentials using one of:"
    echo "  1. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
    echo "  2. AWS Profile: AWS_PROFILE=your-profile"
    echo "  3. AWS credentials file: ~/.aws/credentials"
    echo ""
    echo "See test/README.md for more details."
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    # Try to verify AWS credentials work
    if command -v aws &> /dev/null; then
        if aws sts get-caller-identity &> /dev/null; then
            AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "unknown")
            AWS_REGION=$(aws configure get region 2>/dev/null || echo "${AWS_DEFAULT_REGION:-us-east-1}")
            print_success "AWS credentials valid (Account: $AWS_ACCOUNT, Region: $AWS_REGION)"
        else
            print_warning "AWS credentials found but validation failed"
        fi
    else
        print_success "AWS environment variables set"
    fi
fi

echo ""

# ============================================================================
# Run Tests
# ============================================================================

# Parse arguments
TEST_NAME=""
VERBOSE=""
TIMEOUT="30m"

while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE="-v"
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        Test*)
            TEST_NAME="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [TestName] [--verbose] [--timeout 30m]"
            exit 1
            ;;
    esac
done

# Build test command
TEST_CMD="go test"

if [ -n "$VERBOSE" ]; then
    TEST_CMD="$TEST_CMD -v"
fi

TEST_CMD="$TEST_CMD -timeout $TIMEOUT"

if [ -n "$TEST_NAME" ]; then
    TEST_CMD="$TEST_CMD -run $TEST_NAME"
    print_status "Running test: $TEST_NAME"
else
    print_status "Running all tests (this may take up to 30 minutes)..."
fi

echo ""
print_status "Test Command: $TEST_CMD"
echo ""

# Run the tests
if eval "$TEST_CMD"; then
    echo ""
    print_success "Tests completed successfully!"
    echo ""
    exit 0
else
    EXIT_CODE=$?
    echo ""
    print_error "Tests failed with exit code $EXIT_CODE"
    echo ""
    echo "Common issues:"
    echo "  - Insufficient AWS permissions"
    echo "  - AWS service quotas/limits reached"
    echo "  - Network connectivity issues"
    echo "  - Resource naming conflicts"
    echo ""
    echo "See test/README.md for troubleshooting guidance."
    echo ""
    exit $EXIT_CODE
fi

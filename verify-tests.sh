#!/bin/bash
# Verification script for subtask-6-1
# Run full test suite and verify no AWS credential errors

set -e

echo "========================================"
echo "Terraform Test Suite Verification"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ============================================
# STEP 1: Check Terraform version
# ============================================

echo "Step 1: Checking Terraform version..."

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}ERROR: Terraform is not installed${NC}"
    echo "Please install Terraform >= 1.7 from https://www.terraform.io/downloads"
    exit 1
fi

TF_VERSION=$(terraform version -json | python3 -c "import sys,json; print(json.load(sys.stdin)['terraform_version'])" 2>/dev/null || terraform version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
echo "Terraform version: $TF_VERSION"

TF_MAJOR=$(echo "$TF_VERSION" | cut -d. -f1)
TF_MINOR=$(echo "$TF_VERSION" | cut -d. -f2)

if [ "$TF_MAJOR" -lt 1 ] || ([ "$TF_MAJOR" -eq 1 ] && [ "$TF_MINOR" -lt 7 ]); then
    echo -e "${RED}ERROR: Terraform >= 1.7 required, found $TF_VERSION${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Terraform version OK${NC}"
echo ""

# ============================================
# STEP 2: Unset AWS environment variables
# ============================================

echo "Step 2: Unsetting AWS credentials..."

export AWS_ACCESS_KEY_ID=""
export AWS_SECRET_ACCESS_KEY=""
export AWS_SESSION_TOKEN=""
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

if [ -n "$AWS_ACCESS_KEY_ID" ] || [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${RED}ERROR: Failed to unset AWS credentials${NC}"
    exit 1
fi

echo -e "${GREEN}✓ AWS credentials unset${NC}"
echo ""

# ============================================
# STEP 3: Run terraform init
# ============================================

echo "Step 3: Running terraform init..."

if terraform init -upgrade > /tmp/tf-init.log 2>&1; then
    echo -e "${GREEN}✓ Terraform init successful${NC}"
else
    echo -e "${RED}ERROR: Terraform init failed${NC}"
    cat /tmp/tf-init.log
    exit 1
fi
echo ""

# ============================================
# STEP 4: Run terraform test
# ============================================

echo "Step 4: Running terraform test..."

# Run tests and capture output
if terraform test > /tmp/tf-test.log 2>&1; then
    TEST_EXIT_CODE=0
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    TEST_EXIT_CODE=$?
    echo -e "${RED}ERROR: Tests failed with exit code $TEST_EXIT_CODE${NC}"
fi

# Show test output
cat /tmp/tf-test.log
echo ""

# ============================================
# STEP 5: Verify no credential errors
# ============================================

echo "Step 5: Checking for credential-related errors..."

CREDENTIAL_ERRORS=$(grep -i -E 'credential|authentication|NoCredentialProviders|InvalidClientTokenId|AccessDenied.*credential' /tmp/tf-test.log /tmp/tf-init.log 2>/dev/null || true)

if [ -n "$CREDENTIAL_ERRORS" ]; then
    echo -e "${RED}ERROR: Found credential-related errors:${NC}"
    echo "$CREDENTIAL_ERRORS"
    exit 1
else
    echo -e "${GREEN}✓ No credential errors found${NC}"
fi
echo ""

# ============================================
# STEP 6: Verify test file coverage
# ============================================

echo "Step 6: Verifying test file coverage..."

EXPECTED_FILES=(
    "tests/s3.tftest.hcl"
    "tests/sqs.tftest.hcl"
    "tests/sns.tftest.hcl"
    "tests/iam.tftest.hcl"
    "tests/cloudwatch.tftest.hcl"
    "tests/eventbridge.tftest.hcl"
    "tests/variables.tftest.hcl"
)

ALL_PRESENT=true
for file in "${EXPECTED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file (missing)"
        ALL_PRESENT=false
    fi
done

if [ "$ALL_PRESENT" = false ]; then
    echo -e "${RED}ERROR: Not all test files are present${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All test files present${NC}"
echo ""

# ============================================
# SUMMARY
# ============================================

echo "========================================"
echo "Verification Summary"
echo "========================================"

if [ $TEST_EXIT_CODE -eq 0 ] && [ -z "$CREDENTIAL_ERRORS" ]; then
    echo -e "${GREEN}✓ All verification steps passed${NC}"
    echo ""
    echo "Results:"
    echo "  - Terraform version: $TF_VERSION (>= 1.7 required)"
    echo "  - AWS credentials: Unset"
    echo "  - Terraform init: Success"
    echo "  - Terraform test: Success (exit code 0)"
    echo "  - Credential errors: None found"
    echo "  - Test file coverage: Complete (7/7 files)"
    echo ""
    echo "✅ SUBTASK-6-1 VERIFICATION COMPLETE"
    exit 0
else
    echo -e "${RED}✗ Verification failed${NC}"
    echo ""
    echo "Please review the errors above and fix before proceeding."
    exit 1
fi

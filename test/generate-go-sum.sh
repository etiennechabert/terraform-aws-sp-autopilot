#!/bin/bash
#
# Helper script to generate go.sum file
#
# This script must be run from the test/ directory with Go installed
#
# Usage:
#   cd test
#   ./generate-go-sum.sh
#

set -e

echo "=== Generating go.sum for Terratest ==="
echo ""

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo "ERROR: Go is not installed or not in PATH"
    echo ""
    echo "Please install Go 1.21 or higher:"
    echo "  - Download: https://go.dev/dl/"
    echo "  - Windows: https://go.dev/dl/go1.21.6.windows-amd64.msi"
    echo "  - After installation, add Go to your PATH:"
    echo "    set PATH=%PATH%;C:\\Program Files\\Go\\bin"
    echo ""
    exit 1
fi

# Check Go version
GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
echo "Found Go version: $GO_VERSION"

# Ensure we're in the test directory
if [ ! -f "go.mod" ]; then
    echo "ERROR: go.mod not found. Please run this script from the test/ directory"
    exit 1
fi

echo "Downloading Go modules..."
go mod download

echo ""
echo "Verifying Go modules..."
go mod verify

echo ""
echo "✓ go.sum generated successfully!"
echo ""
echo "Next steps:"
echo "  1. Run tests: go test -v -timeout 30m"
echo "  2. Or run single test: go test -v -run TestTerraformBasicDeployment -timeout 15m"
echo ""

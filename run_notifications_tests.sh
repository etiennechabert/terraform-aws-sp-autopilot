#!/bin/bash
# Test runner script for notifications module only

# Find Python installation
PYTHON=""
if [ -f "$LOCALAPPDATA/Programs/Python/Python314/python.exe" ]; then
    PYTHON="$LOCALAPPDATA/Programs/Python/Python314/python.exe"
elif [ -f "$LOCALAPPDATA/Programs/Python/Python311/python.exe" ]; then
    PYTHON="$LOCALAPPDATA/Programs/Python/Python311/python.exe"
else
    echo "ERROR: Python not found"
    exit 1
fi

echo "Using Python: $PYTHON"
$PYTHON --version

# Install dependencies
echo "Installing dependencies..."
$PYTHON -m pip install --quiet pytest pytest-cov pytest-mock moto boto3 botocore urllib3

# Set PYTHONPATH
export PYTHONPATH="$(pwd)/lambda"
export AWS_DEFAULT_REGION="us-east-1"

# Run only notifications tests
echo "Running notifications module tests..."
cd lambda/shared
$PYTHON -m pytest tests/test_notifications.py -v --cov=notifications --cov-report=term

TEST_EXIT_CODE=$?
echo "Test exit code: $TEST_EXIT_CODE"
exit $TEST_EXIT_CODE

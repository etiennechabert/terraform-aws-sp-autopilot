#!/bin/bash
# Test runner for handler_utils integration tests

PYTHON=""
if [ -f "$LOCALAPPDATA/Programs/Python/Python314/python.exe" ]; then
    PYTHON="$LOCALAPPDATA/Programs/Python/Python314/python.exe"
elif [ -f "$LOCALAPPDATA/Programs/Python/Python311/python.exe" ]; then
    PYTHON="$LOCALAPPDATA/Programs/Python/Python311/python.exe"
fi

echo "Running handler_utils integration tests with notifications..."
$PYTHON -m pip install --quiet pytest pytest-mock boto3 urllib3 >/dev/null 2>&1

export PYTHONPATH="$(pwd)/lambda"
export AWS_DEFAULT_REGION="us-east-1"

cd lambda/shared
$PYTHON -m pytest tests/test_handler_utils.py::test_send_error_notification_with_slack \
                  tests/test_handler_utils.py::test_send_error_notification_with_teams \
                  -v

echo "Exit code: $?"

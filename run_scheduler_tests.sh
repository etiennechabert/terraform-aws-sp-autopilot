#!/bin/bash
# Script to run scheduler tests only

PYTHON="/c/Users/etien/AppData/Local/Programs/Python/Python311/python.exe"

if [ ! -f "$PYTHON" ]; then
    echo "Error: Python not found at $PYTHON"
    exit 1
fi

echo "Using Python: $("$PYTHON" --version)"
echo ""
echo "Running scheduler tests..."
echo ""

# Set required AWS environment variables for testing
export AWS_DEFAULT_REGION=us-east-1
export AWS_REGION=us-east-1

cd "$(dirname "$0")"
"$PYTHON" -m pytest lambda/scheduler/tests/ -v --tb=short

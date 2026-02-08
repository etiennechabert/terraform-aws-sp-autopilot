"""
Import validation test for Purchaser Lambda handler.

This test verifies the handler module can be imported successfully,
catching import errors before deployment to AWS Lambda.
"""

import sys
from pathlib import Path


def test_handler_module_can_be_imported():
    """
    Test that handler module imports successfully without errors.

    This test catches:
    - Missing dependencies
    - Circular imports
    - Invalid import statements (wrong module paths)
    - ModuleNotFoundError errors

    Run this test FIRST - if handler can't import, nothing else matters.
    """
    # Ensure lambda directory is in path
    lambda_dir = Path(__file__).parent.parent
    if str(lambda_dir) not in sys.path:
        sys.path.insert(0, str(lambda_dir))

    # This should work without errors
    import handler

    # Verify handler function exists and is callable
    assert hasattr(handler, "handler"), "Handler module missing 'handler' function"
    assert callable(handler.handler), "handler.handler is not callable"

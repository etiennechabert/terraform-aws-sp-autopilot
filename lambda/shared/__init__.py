"""
Shared utilities module for Lambda functions.

This module contains common utilities used across multiple Lambda functions
to reduce code duplication and improve maintainability.
"""

__version__ = "1.0.0"

from . import notifications


__all__ = ["notifications"]

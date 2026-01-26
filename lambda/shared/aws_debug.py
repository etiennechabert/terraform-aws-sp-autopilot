"""
AWS API Debug Data Collection.

Global storage for collecting raw AWS API responses for debugging purposes.
Used by Reporter Lambda to capture all AWS API calls and include in debug data.
"""

from typing import Any


# Global list to collect AWS API responses
AWS_API_RESPONSES: list[dict[str, Any]] = []


def clear_responses() -> None:
    """Clear all collected AWS API responses."""
    global AWS_API_RESPONSES
    AWS_API_RESPONSES = []


def add_response(api: str, params: dict[str, Any], response: Any, **kwargs: Any) -> None:
    """
    Add an AWS API response to the collection.

    Args:
        api: API name (e.g., "get_savings_plans_coverage", "describe_savings_plans")
        params: Parameters passed to the API call
        response: Response from the API call (boto3 typed response)
        **kwargs: Additional metadata (e.g., sp_type, plan_type, context)
    """
    # Build entry with organized field order: simple strings first, then params, then response
    entry = {"api": api}

    # Add string metadata fields (sp_type, plan_type, context) before params/response
    for key in ["context", "sp_type", "plan_type"]:
        if key in kwargs:
            entry[key] = kwargs.pop(key)

    # Add any remaining kwargs
    entry.update(kwargs)

    # Add params and response last for better readability in JSON viewer
    entry["params"] = params
    entry["response"] = response

    AWS_API_RESPONSES.append(entry)


def get_responses() -> list[dict[str, Any]]:
    """Get all collected AWS API responses."""
    return AWS_API_RESPONSES

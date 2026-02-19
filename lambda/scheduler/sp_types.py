"""Shared SP type definitions used across scheduler modules."""

from typing import Any


SP_TYPES = [
    {
        "key": "compute",
        "enabled_config": "enable_compute_sp",
        "payment_option_config": "compute_sp_payment_option",
        "name": "Compute",
    },
    {
        "key": "database",
        "enabled_config": "enable_database_sp",
        "payment_option_config": "database_sp_payment_option",
        "name": "Database",
    },
    {
        "key": "sagemaker",
        "enabled_config": "enable_sagemaker_sp",
        "payment_option_config": "sagemaker_sp_payment_option",
        "name": "SageMaker",
    },
]


def get_term(key: str, config: dict[str, Any]) -> str:
    if key == "compute":
        return config.get("compute_sp_term", "THREE_YEAR")
    if key == "sagemaker":
        return config.get("sagemaker_sp_term", "THREE_YEAR")
    return "ONE_YEAR"

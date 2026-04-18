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
        return config["compute_sp_term"]
    if key == "sagemaker":
        return config["sagemaker_sp_term"]
    return "ONE_YEAR"

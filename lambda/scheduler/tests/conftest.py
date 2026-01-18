"""Scheduler tests configuration - imports shared fixtures."""

import sys
from pathlib import Path


# Ensure parent lambda directory is in path for tests.conftest import
_lambda_dir = Path(__file__).parent.parent.parent.absolute()
if str(_lambda_dir) not in sys.path:
    sys.path.insert(0, str(_lambda_dir))

# Import shared fixtures directly
from tests.conftest import (  # noqa: F401
    aws_create_savings_plan,
    aws_describe_savings_plans,
    aws_get_cost_and_usage,
    aws_get_savings_plans_coverage_grouped,
    aws_get_savings_plans_coverage_history,
    aws_get_savings_plans_utilization,
    aws_mock_builder,
    aws_recommendation_compute_sp,
    aws_recommendation_database_sp,
    aws_recommendation_sagemaker_sp,
    aws_response,
)

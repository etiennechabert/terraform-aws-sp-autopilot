"""
Scheduler tests configuration - imports shared fixtures.

⚠️ IMPORTANT: Read ../../TESTING.md before writing tests ⚠️
All tests MUST:
- Call handler.handler() as entry point
- Mock ONLY AWS clients
- Use aws_mock_builder fixtures
"""

import importlib.util
from pathlib import Path


# Load shared conftest module from absolute path
_shared_conftest_path = Path(__file__).parent.parent.parent / "tests" / "conftest.py"
_spec = importlib.util.spec_from_file_location("shared_conftest", _shared_conftest_path)
_shared_conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared_conftest)

# Re-export all fixtures from shared conftest
aws_response = _shared_conftest.aws_response
aws_describe_savings_plans = _shared_conftest.aws_describe_savings_plans
aws_create_savings_plan = _shared_conftest.aws_create_savings_plan
aws_get_cost_and_usage = _shared_conftest.aws_get_cost_and_usage
aws_get_savings_plans_coverage_grouped = _shared_conftest.aws_get_savings_plans_coverage_grouped
aws_get_savings_plans_coverage_history = _shared_conftest.aws_get_savings_plans_coverage_history
aws_get_savings_plans_utilization = _shared_conftest.aws_get_savings_plans_utilization
aws_recommendation_compute_sp = _shared_conftest.aws_recommendation_compute_sp
aws_recommendation_database_sp = _shared_conftest.aws_recommendation_database_sp
aws_recommendation_sagemaker_sp = _shared_conftest.aws_recommendation_sagemaker_sp
aws_mock_builder = _shared_conftest.aws_mock_builder

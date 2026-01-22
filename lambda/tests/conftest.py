"""
Shared pytest fixtures for all Lambda tests.

Provides AWS API response fixtures loaded from real anonymized AWS responses.

⚠️ IMPORTANT: Before writing or modifying tests, read TESTING.md ⚠️

All Lambda tests MUST follow these rules:
1. Test ONLY through handler.handler(event, context) entry point
2. Mock ONLY AWS client responses (never internal functions or shared modules)
3. Use aws_mock_builder for consistent AWS response structures
4. Verify behavior through handler outputs and AWS calls

Non-compliant tests will be rejected in code review.
See: ../../TESTING.md for complete guidelines.
"""

import json
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "aws_responses"


@pytest.fixture
def aws_response():
    """
    Load AWS API response fixtures.

    Usage:
        def test_something(aws_response):
            response = aws_response('describe_savings_plans.json')
            # Use response in your test

    Available fixtures:
        - describe_savings_plans.json
        - create_savings_plan.json
        - get_cost_and_usage.json
        - get_savings_plans_coverage_grouped.json
        - get_savings_plans_coverage_history.json
        - get_savings_plans_utilization.json
        - recommendation_compute_sp.json
        - recommendation_database_sp.json
        - recommendation_sagemaker_sp.json
    """

    def _load(filename: str) -> dict:
        fixture_path = FIXTURES_DIR / filename
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture file not found: {fixture_path}")
        with open(fixture_path) as f:
            return json.load(f)

    return _load


@pytest.fixture
def aws_describe_savings_plans(aws_response):
    """Fixture for describe_savings_plans API response."""
    return aws_response("describe_savings_plans.json")


@pytest.fixture
def aws_get_cost_and_usage(aws_response):
    """Fixture for get_cost_and_usage API response."""
    return aws_response("get_cost_and_usage.json")


@pytest.fixture
def aws_get_savings_plans_coverage_grouped(aws_response):
    """Fixture for get_savings_plans_coverage (grouped by SERVICE) API response."""
    return aws_response("get_savings_plans_coverage_grouped.json")


@pytest.fixture
def aws_get_savings_plans_coverage_history(aws_response):
    """Fixture for get_savings_plans_coverage (ungrouped history) API response."""
    return aws_response("get_savings_plans_coverage_history.json")


@pytest.fixture
def aws_get_savings_plans_utilization(aws_response):
    """Fixture for get_savings_plans_utilization API response."""
    return aws_response("get_savings_plans_utilization.json")


@pytest.fixture
def aws_recommendation_compute_sp(aws_response):
    """Fixture for Compute SP recommendation API response (empty)."""
    return aws_response("recommendation_compute_sp.json")


@pytest.fixture
def aws_recommendation_database_sp(aws_response):
    """Fixture for Database SP recommendation API response."""
    return aws_response("recommendation_database_sp.json")


@pytest.fixture
def aws_recommendation_sagemaker_sp(aws_response):
    """Fixture for SageMaker SP recommendation API response."""
    return aws_response("recommendation_sagemaker_sp.json")


@pytest.fixture
def aws_create_savings_plan(aws_response):
    """Fixture for create_savings_plan API response."""
    return aws_response("create_savings_plan.json")


@pytest.fixture
def aws_mock_builder(aws_response):
    """
    Build AWS API responses with easy overrides while maintaining real structure.

    Usage:
        def test_coverage(aws_mock_builder, mock_ce_client):
            # Use real AWS structure with custom coverage percentage
            mock_ce_client.get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
                coverage_percentage=85.5
            )

        def test_recommendations(aws_mock_builder, mock_ce_client):
            # Use real recommendation structure with custom commitment
            mock_ce_client.get_savings_plans_purchase_recommendation.return_value = (
                aws_mock_builder.recommendation('database', hourly_commitment=20.0)
            )
    """
    import copy

    class AwsMockBuilder:
        """Builder for AWS API responses with customization support."""

        def __init__(self, loader):
            self._load = loader

        def describe_savings_plans(self, plans_count=2, state="active", **overrides):
            """
            Create describe_savings_plans response.

            Args:
                plans_count: Number of plans to include (default: 2)
                state: Plan state (default: 'active')
                **overrides: Additional overrides

            Returns:
                dict: SavingsPlans API response
            """
            data = copy.deepcopy(self._load("describe_savings_plans.json"))

            # Adjust number of plans
            if plans_count != len(data["savingsPlans"]):
                data["savingsPlans"] = data["savingsPlans"][:plans_count]

            # Apply state filter
            for plan in data["savingsPlans"]:
                plan["state"] = overrides.get("state", state)

            return data

        def coverage(self, coverage_percentage=None, services=None, empty=False, **overrides):
            """
            Create get_savings_plans_coverage response.

            Args:
                coverage_percentage: Override coverage % for all items (optional)
                services: List of services to include (default: all from fixture)
                empty: Return empty coverage (default: False)
                **overrides: Additional field overrides

            Returns:
                dict: Cost Explorer coverage response
            """
            if empty:
                return {"SavingsPlansCoverages": []}

            data = copy.deepcopy(self._load("get_savings_plans_coverage_grouped.json"))

            # Filter by services if specified
            if services:
                data["SavingsPlansCoverages"] = [
                    item
                    for item in data["SavingsPlansCoverages"]
                    if item["Attributes"]["SERVICE"] in services
                ]

            # Override coverage percentage if specified
            if coverage_percentage is not None:
                for item in data["SavingsPlansCoverages"]:
                    item["Coverage"]["CoveragePercentage"] = str(coverage_percentage)

            return data

        def coverage_history(self, coverage_percentage=None, days=None, **overrides):
            """
            Create get_savings_plans_coverage response (ungrouped history).

            Args:
                coverage_percentage: Override coverage % for all days (optional)
                days: Number of days to include (default: all from fixture)
                **overrides: Additional field overrides

            Returns:
                dict: Cost Explorer coverage history response
            """
            data = copy.deepcopy(self._load("get_savings_plans_coverage_history.json"))

            # Limit number of days if specified
            if days:
                data["SavingsPlansCoverages"] = data["SavingsPlansCoverages"][:days]

            # Override coverage percentage if specified
            if coverage_percentage is not None:
                for item in data["SavingsPlansCoverages"]:
                    item["Coverage"]["CoveragePercentage"] = str(coverage_percentage)

            return data

        def recommendation(
            self, sp_type="database", hourly_commitment=None, empty=False, **overrides
        ):
            """
            Create get_savings_plans_purchase_recommendation response.

            Args:
                sp_type: Type of SP ('compute', 'database', 'sagemaker')
                hourly_commitment: Override hourly commitment (optional)
                empty: Return empty recommendation (default: False)
                **overrides: Additional field overrides

            Returns:
                dict: Cost Explorer recommendation response
            """
            data = copy.deepcopy(self._load(f"recommendation_{sp_type}_sp.json"))

            if empty:
                data["SavingsPlansPurchaseRecommendation"] = {}
                return data

            # Override hourly commitment if specified
            if hourly_commitment is not None:
                rec = data.get("SavingsPlansPurchaseRecommendation", {})
                details = rec.get("SavingsPlansPurchaseRecommendationDetails", [])
                if details:
                    # Format as string with 3 decimal places to match AWS API format
                    formatted_commitment = (
                        f"{hourly_commitment:.3f}"
                        if isinstance(hourly_commitment, (int, float))
                        else str(hourly_commitment)
                    )
                    details[0]["HourlyCommitmentToPurchase"] = formatted_commitment
                    # Also update summary
                    summary = rec.get("SavingsPlansPurchaseRecommendationSummary", {})
                    if summary:
                        summary["HourlyCommitmentToPurchase"] = formatted_commitment

            return data

        def utilization(self, utilization_percentage=None, days=None, **overrides):
            """
            Create get_savings_plans_utilization response.

            Args:
                utilization_percentage: Override utilization % for all days (optional)
                days: Number of days to include (default: all from fixture)
                **overrides: Additional field overrides

            Returns:
                dict: Cost Explorer utilization response
            """
            data = copy.deepcopy(self._load("get_savings_plans_utilization.json"))

            # Limit number of days if specified
            if days:
                data["SavingsPlansUtilizationsByTime"] = data["SavingsPlansUtilizationsByTime"][
                    :days
                ]

            # Override utilization percentage if specified
            if utilization_percentage is not None:
                for item in data["SavingsPlansUtilizationsByTime"]:
                    item["Utilization"]["UtilizationPercentage"] = str(utilization_percentage)

            return data

        def cost_and_usage(self, days=None, **overrides):
            """
            Create get_cost_and_usage response.

            Args:
                days: Number of days to include (default: all from fixture)
                **overrides: Additional field overrides

            Returns:
                dict: Cost Explorer cost and usage response
            """
            data = copy.deepcopy(self._load("get_cost_and_usage.json"))

            # Limit number of days if specified
            if days:
                data["ResultsByTime"] = data["ResultsByTime"][:days]

            return data

        def create_savings_plan(self, savings_plan_id=None, **overrides):
            """
            Create create_savings_plan response.

            Args:
                savings_plan_id: Override the returned SP ID (optional)
                **overrides: Additional field overrides

            Returns:
                dict: SavingsPlans create_savings_plan response
            """
            data = copy.deepcopy(self._load("create_savings_plan.json"))

            # Override SP ID if specified
            if savings_plan_id:
                data["savingsPlanId"] = savings_plan_id

            return data

    return AwsMockBuilder(aws_response)

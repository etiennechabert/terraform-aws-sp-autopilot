"""
Comprehensive unit tests for Reporter Lambda handler.

Tests cover all functions with edge cases to achieve >= 80% coverage.
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("REPORTS_BUCKET", "test-reports-bucket")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")
    monkeypatch.setenv("REPORT_FORMAT", "html")
    monkeypatch.setenv("EMAIL_REPORTS", "true")
    monkeypatch.setenv("MANAGEMENT_ACCOUNT_ROLE_ARN", "")
    monkeypatch.setenv("TAGS", "{}")


# ============================================================================
# Assume Role Tests
# ============================================================================


def test_get_assumed_role_session_with_valid_arn():
    """Test that AssumeRole is called when ARN is provided."""
    with patch("shared.aws_utils.boto3.client") as mock_boto3_client:
        mock_sts = MagicMock()
        mock_boto3_client.return_value = mock_sts

        # Mock STS AssumeRole response
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                "SessionToken": "FwoGZXIvYXdzEBYaDBexampletoken",
                "Expiration": datetime.now(timezone.utc),
            }
        }

        # Call function - now uses shared aws_utils default session name
        from shared.aws_utils import get_assumed_role_session

        session = get_assumed_role_session("arn:aws:iam::123456789012:role/TestRole")

        # Verify AssumeRole was called with correct parameters (default session name)
        assert session is not None
        mock_sts.assume_role.assert_called_once_with(
            RoleArn="arn:aws:iam::123456789012:role/TestRole",
            RoleSessionName="sp-autopilot-session",
        )


def test_get_assumed_role_session_without_arn():
    """Test that None is returned when ARN is not provided."""
    from shared.aws_utils import get_assumed_role_session

    # Test with None
    result = get_assumed_role_session(None)
    assert result is None

    # Test with empty string
    result = get_assumed_role_session("")
    assert result is None


def test_get_assumed_role_session_access_denied():
    """Test that AccessDenied error is raised with clear message."""
    with patch("shared.aws_utils.boto3.client") as mock_boto3_client:
        mock_sts = MagicMock()
        mock_boto3_client.return_value = mock_sts

        # Mock AccessDenied error
        error_response = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "User: arn:aws:sts::111:assumed-role/lambda is not authorized to perform: sts:AssumeRole",
            }
        }
        mock_sts.assume_role.side_effect = ClientError(error_response, "AssumeRole")

        # Verify ClientError is raised
        from shared.aws_utils import get_assumed_role_session

        with pytest.raises(ClientError) as exc_info:
            get_assumed_role_session("arn:aws:iam::123456789012:role/TestRole")

        # Verify error code
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"


def test_get_clients_with_role_arn():
    """Test that CE/SP clients use assumed credentials when role ARN is provided."""
    config = {"management_account_role_arn": "arn:aws:iam::123456789012:role/TestRole"}

    with (
        patch("shared.aws_utils.get_assumed_role_session") as mock_assume,
        patch("shared.aws_utils.boto3.client") as mock_boto3_client,
    ):
        # Mock session from assumed role
        mock_session = MagicMock()
        mock_assume.return_value = mock_session

        # Mock session.client() calls
        mock_session.client.return_value = MagicMock()

        # Mock boto3.client() calls (for SNS/S3)
        mock_boto3_client.return_value = MagicMock()

        # Call function with session_name parameter
        from shared.aws_utils import get_clients

        get_clients(config, session_name="sp-autopilot-reporter")

        # Verify assume role was called with session_name
        mock_assume.assert_called_once_with(
            "arn:aws:iam::123456789012:role/TestRole", "sp-autopilot-reporter"
        )

        # Verify CE and Savings Plans clients use session
        assert mock_session.client.call_count == 2
        mock_session.client.assert_any_call("ce")
        mock_session.client.assert_any_call("savingsplans")

        # Verify SNS, SQS, and S3 clients use local credentials (boto3.client directly)
        assert mock_boto3_client.call_count == 3
        mock_boto3_client.assert_any_call("sns")
        mock_boto3_client.assert_any_call("sqs")
        mock_boto3_client.assert_any_call("s3")


def test_get_clients_without_role_arn():
    """Test that all clients use default credentials when no role ARN provided."""
    config = {"management_account_role_arn": None}

    with patch("shared.aws_utils.boto3.client") as mock_boto3_client:
        mock_boto3_client.return_value = MagicMock()

        # Call function
        from shared.aws_utils import get_clients

        get_clients(config)

        # Verify all 5 clients use boto3.client directly (no assume role)
        assert mock_boto3_client.call_count == 5
        mock_boto3_client.assert_any_call("ce")
        mock_boto3_client.assert_any_call("savingsplans")
        mock_boto3_client.assert_any_call("sns")
        mock_boto3_client.assert_any_call("sqs")
        mock_boto3_client.assert_any_call("s3")


# ============================================================================
# Configuration Tests
# ============================================================================


def test_load_configuration_defaults(mock_env_vars):
    """Test that load_configuration returns correct default values."""
    config = handler.load_configuration()

    assert config["reports_bucket"] == "test-reports-bucket"
    assert config["sns_topic_arn"] == "arn:aws:sns:us-east-1:123456789012:test-topic"
    assert config["report_format"] == "html"
    assert config["email_reports"] is True
    assert config["management_account_role_arn"] == ""
    assert config["tags"] == {}


def test_load_configuration_custom_values(monkeypatch):
    """Test that load_configuration handles custom environment values."""
    monkeypatch.setenv("REPORTS_BUCKET", "custom-bucket")
    monkeypatch.setenv("SNS_TOPIC_ARN", "custom-sns-arn")
    monkeypatch.setenv("REPORT_FORMAT", "json")
    monkeypatch.setenv("EMAIL_REPORTS", "false")
    monkeypatch.setenv("MANAGEMENT_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/CustomRole")
    monkeypatch.setenv("TAGS", '{"env": "prod"}')

    config = handler.load_configuration()

    assert config["reports_bucket"] == "custom-bucket"
    assert config["sns_topic_arn"] == "custom-sns-arn"
    assert config["report_format"] == "json"
    assert config["email_reports"] is False
    assert config["management_account_role_arn"] == "arn:aws:iam::123456789012:role/CustomRole"
    assert config["tags"] == {"env": "prod"}


# ============================================================================
# Coverage History Tests
# ============================================================================


def test_get_coverage_history_success():
    """Test successful retrieval of coverage history."""
    with patch.object(handler.ce_client, "get_savings_plans_coverage") as mock_get_coverage:
        mock_get_coverage.return_value = {
            "SavingsPlansCoverages": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Coverage": {
                        "CoveragePercentage": "75.5",
                        "CoverageHours": {
                            "OnDemandHours": "100",
                            "CoveredHours": "300",
                            "TotalRunningHours": "400",
                        },
                    },
                },
                {
                    "TimePeriod": {"Start": "2026-01-11", "End": "2026-01-12"},
                    "Coverage": {
                        "CoveragePercentage": "80.0",
                        "CoverageHours": {
                            "OnDemandHours": "80",
                            "CoveredHours": "320",
                            "TotalRunningHours": "400",
                        },
                    },
                },
            ]
        }

        result = handler.get_coverage_history(lookback_days=2)

        assert len(result) == 2
        assert result[0]["date"] == "2026-01-10"
        assert result[0]["coverage_percentage"] == 75.5
        assert result[0]["on_demand_hours"] == 100.0
        assert result[0]["covered_hours"] == 300.0
        assert result[0]["total_hours"] == 400.0


def test_get_coverage_history_empty():
    """Test handling of no coverage data."""
    with patch.object(handler.ce_client, "get_savings_plans_coverage") as mock_get_coverage:
        mock_get_coverage.return_value = {"SavingsPlansCoverages": []}

        result = handler.get_coverage_history(lookback_days=30)

        assert result == []


def test_get_coverage_history_client_error():
    """Test that ClientError is raised on API failure."""
    with patch.object(handler.ce_client, "get_savings_plans_coverage") as mock_get_coverage:
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Not authorized"}}
        mock_get_coverage.side_effect = ClientError(error_response, "get_savings_plans_coverage")

        with pytest.raises(ClientError):
            handler.get_coverage_history(lookback_days=30)


# ============================================================================
# Actual Cost Data Tests
# ============================================================================


def test_get_actual_cost_data_success():
    """Test successful retrieval of actual cost data with mixed purchase options."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        mock_get_cost.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Groups": [
                        {
                            "Keys": ["Savings Plans"],
                            "Metrics": {"UnblendedCost": {"Amount": "50.25", "Unit": "USD"}},
                        },
                        {
                            "Keys": ["On Demand"],
                            "Metrics": {"UnblendedCost": {"Amount": "100.75", "Unit": "USD"}},
                        },
                    ],
                },
                {
                    "TimePeriod": {"Start": "2026-01-11", "End": "2026-01-12"},
                    "Groups": [
                        {
                            "Keys": ["Savings Plans"],
                            "Metrics": {"UnblendedCost": {"Amount": "52.00", "Unit": "USD"}},
                        },
                        {
                            "Keys": ["On Demand"],
                            "Metrics": {"UnblendedCost": {"Amount": "95.50", "Unit": "USD"}},
                        },
                    ],
                },
            ]
        }

        result = handler.get_actual_cost_data(lookback_days=2)

        # Verify structure
        assert "cost_by_day" in result
        assert "total_savings_plans_cost" in result
        assert "total_on_demand_cost" in result
        assert "total_cost" in result

        # Verify daily data
        assert len(result["cost_by_day"]) == 2

        # Day 1
        assert result["cost_by_day"][0]["date"] == "2026-01-10"
        assert result["cost_by_day"][0]["savings_plans_cost"] == 50.25
        assert result["cost_by_day"][0]["on_demand_cost"] == 100.75
        assert result["cost_by_day"][0]["total_cost"] == 151.00

        # Day 2
        assert result["cost_by_day"][1]["date"] == "2026-01-11"
        assert result["cost_by_day"][1]["savings_plans_cost"] == 52.00
        assert result["cost_by_day"][1]["on_demand_cost"] == 95.50
        assert result["cost_by_day"][1]["total_cost"] == 147.50

        # Verify totals
        assert result["total_savings_plans_cost"] == 102.25
        assert result["total_on_demand_cost"] == 196.25
        assert result["total_cost"] == 298.50


def test_get_actual_cost_data_empty():
    """Test handling of no cost data available."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        mock_get_cost.return_value = {"ResultsByTime": []}

        result = handler.get_actual_cost_data(lookback_days=30)

        # Verify empty data structure
        assert result["cost_by_day"] == []
        assert result["total_savings_plans_cost"] == 0.0
        assert result["total_on_demand_cost"] == 0.0
        assert result["total_cost"] == 0.0


def test_get_actual_cost_data_only_savings_plans():
    """Test retrieval with only Savings Plans costs (no On-Demand)."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        mock_get_cost.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Groups": [
                        {
                            "Keys": ["Savings Plans"],
                            "Metrics": {"UnblendedCost": {"Amount": "75.50", "Unit": "USD"}},
                        }
                    ],
                }
            ]
        }

        result = handler.get_actual_cost_data(lookback_days=1)

        # Verify only Savings Plans cost is recorded
        assert result["cost_by_day"][0]["savings_plans_cost"] == 75.50
        assert result["cost_by_day"][0]["on_demand_cost"] == 0.0
        assert result["cost_by_day"][0]["total_cost"] == 75.50
        assert result["total_savings_plans_cost"] == 75.50
        assert result["total_on_demand_cost"] == 0.0


def test_get_actual_cost_data_only_on_demand():
    """Test retrieval with only On-Demand costs (no Savings Plans)."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        mock_get_cost.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Groups": [
                        {
                            "Keys": ["On Demand"],
                            "Metrics": {"UnblendedCost": {"Amount": "150.25", "Unit": "USD"}},
                        }
                    ],
                }
            ]
        }

        result = handler.get_actual_cost_data(lookback_days=1)

        # Verify only On-Demand cost is recorded
        assert result["cost_by_day"][0]["savings_plans_cost"] == 0.0
        assert result["cost_by_day"][0]["on_demand_cost"] == 150.25
        assert result["cost_by_day"][0]["total_cost"] == 150.25
        assert result["total_savings_plans_cost"] == 0.0
        assert result["total_on_demand_cost"] == 150.25


def test_get_actual_cost_data_alternative_purchase_option_names():
    """Test handling of alternative purchase option naming variations."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        mock_get_cost.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Groups": [
                        {
                            "Keys": ["SavingsPlan"],  # Alternative naming
                            "Metrics": {"UnblendedCost": {"Amount": "30.00", "Unit": "USD"}},
                        },
                        {
                            "Keys": ["OnDemand"],  # Alternative naming
                            "Metrics": {"UnblendedCost": {"Amount": "70.00", "Unit": "USD"}},
                        },
                    ],
                }
            ]
        }

        result = handler.get_actual_cost_data(lookback_days=1)

        # Verify alternative naming is correctly categorized
        assert result["cost_by_day"][0]["savings_plans_cost"] == 30.00
        assert result["cost_by_day"][0]["on_demand_cost"] == 70.00
        assert result["total_savings_plans_cost"] == 30.00
        assert result["total_on_demand_cost"] == 70.00


def test_get_actual_cost_data_zero_costs():
    """Test handling of zero cost amounts."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        mock_get_cost.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Groups": [
                        {
                            "Keys": ["Savings Plans"],
                            "Metrics": {"UnblendedCost": {"Amount": "0", "Unit": "USD"}},
                        },
                        {
                            "Keys": ["On Demand"],
                            "Metrics": {"UnblendedCost": {"Amount": "0", "Unit": "USD"}},
                        },
                    ],
                }
            ]
        }

        result = handler.get_actual_cost_data(lookback_days=1)

        # Verify zero costs are handled correctly
        assert result["cost_by_day"][0]["savings_plans_cost"] == 0.0
        assert result["cost_by_day"][0]["on_demand_cost"] == 0.0
        assert result["cost_by_day"][0]["total_cost"] == 0.0
        assert result["total_cost"] == 0.0


def test_get_actual_cost_data_missing_cost_fields():
    """Test handling of missing cost amount fields."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        mock_get_cost.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Groups": [
                        {
                            "Keys": ["Savings Plans"],
                            "Metrics": {
                                "UnblendedCost": {}  # Missing Amount
                            },
                        },
                        {
                            "Keys": ["On Demand"],
                            "Metrics": {},  # Missing UnblendedCost
                        },
                    ],
                }
            ]
        }

        result = handler.get_actual_cost_data(lookback_days=1)

        # Verify missing fields default to 0.0
        assert result["cost_by_day"][0]["savings_plans_cost"] == 0.0
        assert result["cost_by_day"][0]["on_demand_cost"] == 0.0
        assert result["total_cost"] == 0.0


def test_get_actual_cost_data_no_groups():
    """Test handling of days with no purchase option groups."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        mock_get_cost.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Groups": [],  # No groups for this day
                }
            ]
        }

        result = handler.get_actual_cost_data(lookback_days=1)

        # Verify empty groups result in zero costs
        assert len(result["cost_by_day"]) == 1
        assert result["cost_by_day"][0]["savings_plans_cost"] == 0.0
        assert result["cost_by_day"][0]["on_demand_cost"] == 0.0
        assert result["cost_by_day"][0]["total_cost"] == 0.0


def test_get_actual_cost_data_unknown_purchase_option():
    """Test handling of unknown purchase option types (should be ignored)."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        mock_get_cost.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Groups": [
                        {
                            "Keys": ["Savings Plans"],
                            "Metrics": {"UnblendedCost": {"Amount": "50.00", "Unit": "USD"}},
                        },
                        {
                            "Keys": ["Reserved Instances"],  # Unknown/ignored type
                            "Metrics": {"UnblendedCost": {"Amount": "25.00", "Unit": "USD"}},
                        },
                    ],
                }
            ]
        }

        result = handler.get_actual_cost_data(lookback_days=1)

        # Verify only recognized purchase options are counted
        # Reserved Instances should be ignored (not SP or On-Demand)
        assert result["cost_by_day"][0]["savings_plans_cost"] == 50.00
        assert result["cost_by_day"][0]["on_demand_cost"] == 0.0
        assert result["cost_by_day"][0]["total_cost"] == 50.00


def test_get_actual_cost_data_client_error():
    """Test that ClientError is raised on API failure."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        error_response = {
            "Error": {"Code": "AccessDenied", "Message": "Not authorized to access Cost Explorer"}
        }
        mock_get_cost.side_effect = ClientError(error_response, "get_cost_and_usage")

        with pytest.raises(ClientError):
            handler.get_actual_cost_data(lookback_days=30)


def test_get_actual_cost_data_throttling_error():
    """Test that throttling error is raised properly."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
        mock_get_cost.side_effect = ClientError(error_response, "get_cost_and_usage")

        with pytest.raises(ClientError) as exc_info:
            handler.get_actual_cost_data(lookback_days=30)

        assert exc_info.value.response["Error"]["Code"] == "ThrottlingException"


def test_get_actual_cost_data_multiple_days_aggregation():
    """Test correct aggregation of costs across multiple days."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        mock_get_cost.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Groups": [
                        {
                            "Keys": ["Savings Plans"],
                            "Metrics": {"UnblendedCost": {"Amount": "10.00"}},
                        },
                        {"Keys": ["On Demand"], "Metrics": {"UnblendedCost": {"Amount": "20.00"}}},
                    ],
                },
                {
                    "TimePeriod": {"Start": "2026-01-11", "End": "2026-01-12"},
                    "Groups": [
                        {
                            "Keys": ["Savings Plans"],
                            "Metrics": {"UnblendedCost": {"Amount": "15.00"}},
                        },
                        {"Keys": ["On Demand"], "Metrics": {"UnblendedCost": {"Amount": "25.00"}}},
                    ],
                },
                {
                    "TimePeriod": {"Start": "2026-01-12", "End": "2026-01-13"},
                    "Groups": [
                        {
                            "Keys": ["Savings Plans"],
                            "Metrics": {"UnblendedCost": {"Amount": "12.50"}},
                        },
                        {"Keys": ["On Demand"], "Metrics": {"UnblendedCost": {"Amount": "22.50"}}},
                    ],
                },
            ]
        }

        result = handler.get_actual_cost_data(lookback_days=3)

        # Verify correct aggregation across 3 days
        assert len(result["cost_by_day"]) == 3
        assert result["total_savings_plans_cost"] == 37.50  # 10 + 15 + 12.5
        assert result["total_on_demand_cost"] == 67.50  # 20 + 25 + 22.5
        assert result["total_cost"] == 105.00  # 37.5 + 67.5


def test_get_actual_cost_data_empty_keys_list():
    """Test handling of groups with empty Keys list."""
    with patch.object(handler.ce_client, "get_cost_and_usage") as mock_get_cost:
        mock_get_cost.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Groups": [
                        {
                            "Keys": [],  # Empty keys list
                            "Metrics": {"UnblendedCost": {"Amount": "50.00"}},
                        }
                    ],
                }
            ]
        }

        result = handler.get_actual_cost_data(lookback_days=1)

        # Verify graceful handling - should be categorized as unknown and ignored
        assert result["cost_by_day"][0]["savings_plans_cost"] == 0.0
        assert result["cost_by_day"][0]["on_demand_cost"] == 0.0
        assert result["total_cost"] == 0.0


# ============================================================================
# Savings Data Tests
# ============================================================================


def test_get_savings_data_with_active_plans():
    """Test retrieval of savings data with active plans."""
    with (
        patch.object(handler.savingsplans_client, "describe_savings_plans") as mock_describe,
        patch.object(handler.ce_client, "get_savings_plans_utilization") as mock_utilization,
    ):
        mock_describe.return_value = {
            "savingsPlans": [
                {
                    "savingsPlanId": "sp-12345678",
                    "savingsPlanType": "ComputeSavingsPlans",
                    "commitment": "1.5",
                    "start": "2025-01-01T00:00:00Z",
                    "end": "2026-01-01T00:00:00Z",
                    "paymentOption": "ALL_UPFRONT",
                    "termDurationInSeconds": 31536000,  # 1 year
                },
                {
                    "savingsPlanId": "sp-87654321",
                    "savingsPlanType": "ComputeSavingsPlans",
                    "commitment": "2.0",
                    "start": "2025-06-01T00:00:00Z",
                    "end": "2028-06-01T00:00:00Z",
                    "paymentOption": "NO_UPFRONT",
                    "termDurationInSeconds": 94608000,  # 3 years
                },
            ]
        }

        mock_utilization.return_value = {
            "SavingsPlansUtilizationsByTime": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Utilization": {"UtilizationPercentage": "95.0"},
                    "Savings": {"NetSavings": "100.50", "OnDemandCostEquivalent": "500.00"},
                    "AmortizedCommitment": {"TotalAmortizedCommitment": "399.50"},
                },
                {
                    "TimePeriod": {"Start": "2026-01-11", "End": "2026-01-12"},
                    "Utilization": {"UtilizationPercentage": "97.0"},
                    "Savings": {"NetSavings": "150.75", "OnDemandCostEquivalent": "600.00"},
                    "AmortizedCommitment": {"TotalAmortizedCommitment": "449.25"},
                },
            ]
        }

        result = handler.get_savings_data()

        assert result["plans_count"] == 2
        assert result["total_commitment"] == 3.5
        assert result["average_utilization"] == 96.0
        assert result["estimated_monthly_savings"] == 251.25  # Sum of NetSavings
        assert len(result["plans"]) == 2
        assert result["plans"][0]["plan_id"] == "sp-12345678"
        assert result["plans"][0]["term_years"] == 1
        assert result["plans"][1]["term_years"] == 3

        # Verify actual_savings structure
        assert "actual_savings" in result
        assert result["actual_savings"]["net_savings"] == 251.25
        assert result["actual_savings"]["on_demand_equivalent_cost"] == 1100.00
        assert result["actual_savings"]["actual_sp_cost"] == 848.75
        assert abs(result["actual_savings"]["savings_percentage"] - 22.84) < 0.1
        assert "ComputeSavingsPlans" in result["actual_savings"]["breakdown_by_type"]
        assert (
            result["actual_savings"]["breakdown_by_type"]["ComputeSavingsPlans"]["plans_count"] == 2
        )


def test_get_savings_data_no_active_plans():
    """Test handling of no active Savings Plans."""
    with patch.object(handler.savingsplans_client, "describe_savings_plans") as mock_describe:
        mock_describe.return_value = {"savingsPlans": []}

        result = handler.get_savings_data()

        assert result["total_commitment"] == 0.0
        assert result["plans_count"] == 0
        assert result["plans"] == []
        assert result["estimated_monthly_savings"] == 0.0
        assert result["average_utilization"] == 0.0
        assert "actual_savings" in result
        assert result["actual_savings"]["net_savings"] == 0.0


def test_get_savings_data_utilization_error():
    """Test that utilization errors are handled gracefully."""
    with (
        patch.object(handler.savingsplans_client, "describe_savings_plans") as mock_describe,
        patch.object(handler.ce_client, "get_savings_plans_utilization") as mock_utilization,
    ):
        mock_describe.return_value = {
            "savingsPlans": [
                {
                    "savingsPlanId": "sp-12345678",
                    "savingsPlanType": "ComputeSavingsPlans",
                    "commitment": "1.5",
                    "start": "2025-01-01T00:00:00Z",
                    "end": "2026-01-01T00:00:00Z",
                    "paymentOption": "ALL_UPFRONT",
                    "termDurationInSeconds": 31536000,
                }
            ]
        }

        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
        mock_utilization.side_effect = ClientError(error_response, "get_savings_plans_utilization")

        result = handler.get_savings_data()

        # Should still return data, just with zero utilization and savings
        assert result["plans_count"] == 1
        assert result["average_utilization"] == 0.0
        assert "actual_savings" in result
        assert result["actual_savings"]["net_savings"] == 0.0
        assert result["actual_savings"]["on_demand_equivalent_cost"] == 0.0


def test_get_savings_data_describe_error():
    """Test that describe_savings_plans errors are raised."""
    with patch.object(handler.savingsplans_client, "describe_savings_plans") as mock_describe:
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Not authorized"}}
        mock_describe.side_effect = ClientError(error_response, "describe_savings_plans")

        with pytest.raises(ClientError):
            handler.get_savings_data()


# ============================================================================
# HTML Report Generation Tests
# ============================================================================


def test_generate_html_report_with_data():
    """Test HTML report generation with full data."""
    coverage_history = [
        {
            "date": "2026-01-10",
            "coverage_percentage": 75.0,
            "covered_hours": 300.0,
            "on_demand_hours": 100.0,
            "total_hours": 400.0,
        },
        {
            "date": "2026-01-11",
            "coverage_percentage": 80.0,
            "covered_hours": 320.0,
            "on_demand_hours": 80.0,
            "total_hours": 400.0,
        },
    ]

    savings_data = {
        "total_commitment": 3.5,
        "plans_count": 2,
        "plans": [
            {
                "plan_id": "sp-12345678901234567890",
                "plan_type": "ComputeSavingsPlans",
                "hourly_commitment": 1.5,
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2026-01-01T00:00:00Z",
                "payment_option": "ALL_UPFRONT",
                "term_years": 1,
            }
        ],
        "estimated_monthly_savings": 639.25,
        "average_utilization": 96.0,
        "actual_savings": {
            "actual_sp_cost": 1200.50,
            "on_demand_equivalent_cost": 1839.75,
            "net_savings": 639.25,
            "savings_percentage": 34.75,
            "breakdown_by_type": {
                "ComputeSavingsPlans": {"plans_count": 1, "total_commitment": 2.0},
                "SageMakerSavingsPlans": {"plans_count": 1, "total_commitment": 1.5},
            },
        },
    }

    result = handler.generate_html_report(coverage_history, savings_data)

    assert "<!DOCTYPE html>" in result
    assert "80.0%" in result  # Current coverage
    assert "77.5%" in result  # Average coverage
    assert "2 days" in result
    assert "2026-01-10" in result
    assert "ComputeSavingsPlans" in result
    assert "639" in result  # Actual net savings
    assert "sp-12345678901234567" in result  # Truncated plan ID

    # Validate actual savings calculations appear in HTML
    assert "34.75%" in result or "34.8%" in result  # Savings percentage
    assert "ComputeSavingsPlans" in result  # Plan type in breakdown
    assert "SageMakerSavingsPlans" in result  # Plan type in breakdown


def test_generate_html_report_empty_coverage():
    """Test HTML report generation with no coverage data."""
    coverage_history = []
    savings_data = {
        "total_commitment": 0.0,
        "plans_count": 0,
        "plans": [],
        "estimated_monthly_savings": 0.0,
        "average_utilization": 0.0,
        "actual_savings": {
            "actual_sp_cost": 0.0,
            "on_demand_equivalent_cost": 0.0,
            "net_savings": 0.0,
            "savings_percentage": 0.0,
            "breakdown_by_type": {},
        },
    }

    result = handler.generate_html_report(coverage_history, savings_data)

    assert "<!DOCTYPE html>" in result
    assert "0.0%" in result  # Zero coverage
    assert "No coverage data available" in result
    assert "No active Savings Plans found" in result


def test_generate_html_report_trend_up():
    """Test HTML report shows upward trend symbol."""
    coverage_history = [
        {
            "date": "2026-01-10",
            "coverage_percentage": 70.0,
            "covered_hours": 280.0,
            "on_demand_hours": 120.0,
            "total_hours": 400.0,
        },
        {
            "date": "2026-01-11",
            "coverage_percentage": 80.0,
            "covered_hours": 320.0,
            "on_demand_hours": 80.0,
            "total_hours": 400.0,
        },
    ]

    savings_data = {
        "total_commitment": 0.0,
        "plans_count": 0,
        "plans": [],
        "estimated_monthly_savings": 0.0,
        "average_utilization": 0.0,
        "actual_savings": {
            "actual_sp_cost": 0.0,
            "on_demand_equivalent_cost": 0.0,
            "net_savings": 0.0,
            "savings_percentage": 0.0,
            "breakdown_by_type": {},
        },
    }

    result = handler.generate_html_report(coverage_history, savings_data)

    assert "↑" in result


def test_generate_html_report_trend_down():
    """Test HTML report shows downward trend symbol."""
    coverage_history = [
        {
            "date": "2026-01-10",
            "coverage_percentage": 80.0,
            "covered_hours": 320.0,
            "on_demand_hours": 80.0,
            "total_hours": 400.0,
        },
        {
            "date": "2026-01-11",
            "coverage_percentage": 70.0,
            "covered_hours": 280.0,
            "on_demand_hours": 120.0,
            "total_hours": 400.0,
        },
    ]

    savings_data = {
        "total_commitment": 0.0,
        "plans_count": 0,
        "plans": [],
        "estimated_monthly_savings": 0.0,
        "average_utilization": 0.0,
        "actual_savings": {
            "actual_sp_cost": 0.0,
            "on_demand_equivalent_cost": 0.0,
            "net_savings": 0.0,
            "savings_percentage": 0.0,
            "breakdown_by_type": {},
        },
    }

    result = handler.generate_html_report(coverage_history, savings_data)

    assert "↓" in result


# ============================================================================
# JSON Report Generation Tests
# ============================================================================


def test_generate_json_report_with_data():
    """Test JSON report generation with full data."""
    import json

    coverage_history = [
        {
            "date": "2026-01-10",
            "coverage_percentage": 75.0,
            "covered_hours": 300.0,
            "on_demand_hours": 100.0,
            "total_hours": 400.0,
        },
        {
            "date": "2026-01-11",
            "coverage_percentage": 80.0,
            "covered_hours": 320.0,
            "on_demand_hours": 80.0,
            "total_hours": 400.0,
        },
    ]

    savings_data = {
        "total_commitment": 3.5,
        "plans_count": 2,
        "plans": [
            {
                "plan_id": "sp-12345678901234567890",
                "plan_type": "ComputeSavingsPlans",
                "hourly_commitment": 1.5,
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2026-01-01T00:00:00Z",
                "payment_option": "ALL_UPFRONT",
                "term_years": 1,
            }
        ],
        "estimated_monthly_savings": 639.25,
        "average_utilization": 96.0,
        "actual_savings": {
            "actual_sp_cost": 1200.50,
            "on_demand_equivalent_cost": 1839.75,
            "net_savings": 639.25,
            "savings_percentage": 34.75,
            "breakdown_by_type": {
                "ComputeSavingsPlans": {"plans_count": 1, "total_commitment": 2.0},
                "SageMakerSavingsPlans": {"plans_count": 1, "total_commitment": 1.5},
            },
        },
    }

    result = handler.generate_json_report(coverage_history, savings_data)

    # Verify it's valid JSON
    report = json.loads(result)

    # Verify metadata
    assert "report_metadata" in report
    assert report["report_metadata"]["report_type"] == "savings_plans_coverage_and_savings"
    assert report["report_metadata"]["generator"] == "sp-autopilot-reporter"
    assert report["report_metadata"]["reporting_period_days"] == 2

    # Verify coverage summary
    assert "coverage_summary" in report
    assert report["coverage_summary"]["current_coverage_percentage"] == 80.0
    assert report["coverage_summary"]["average_coverage_percentage"] == 77.5
    assert report["coverage_summary"]["trend_direction"] == "increasing"
    assert report["coverage_summary"]["trend_value"] == 5.0
    assert report["coverage_summary"]["data_points"] == 2

    # Verify coverage history is included
    assert "coverage_history" in report
    assert len(report["coverage_history"]) == 2
    assert report["coverage_history"][0]["date"] == "2026-01-10"
    assert report["coverage_history"][1]["coverage_percentage"] == 80.0

    # Verify savings summary
    assert "savings_summary" in report
    assert report["savings_summary"]["active_plans_count"] == 2
    assert report["savings_summary"]["total_hourly_commitment"] == 3.5
    assert report["savings_summary"]["total_monthly_commitment"] == 3.5 * 730
    assert report["savings_summary"]["estimated_monthly_savings"] == 639.25
    assert report["savings_summary"]["average_utilization_percentage"] == 96.0

    # Verify active savings plans are included
    assert "active_savings_plans" in report
    assert len(report["active_savings_plans"]) == 1
    assert report["active_savings_plans"][0]["plan_id"] == "sp-12345678901234567890"

    # Validate actual savings calculations are included in JSON report
    assert "actual_savings" in report
    assert report["actual_savings"]["sp_cost"] == 1200.50
    assert report["actual_savings"]["on_demand_cost"] == 1839.75
    assert report["actual_savings"]["net_savings"] == 639.25
    assert report["actual_savings"]["savings_percentage"] == 34.75
    assert "breakdown_by_type" in report["actual_savings"]
    assert len(report["actual_savings"]["breakdown_by_type"]) == 2

    # Verify breakdown by type
    breakdown = report["actual_savings"]["breakdown_by_type"]
    assert any(item["plan_type"] == "ComputeSavingsPlans" for item in breakdown)
    assert any(item["plan_type"] == "SageMakerSavingsPlans" for item in breakdown)


def test_generate_json_report_empty_coverage():
    """Test JSON report generation with no coverage data."""
    import json

    coverage_history = []
    savings_data = {
        "total_commitment": 0.0,
        "plans_count": 0,
        "plans": [],
        "estimated_monthly_savings": 0.0,
        "average_utilization": 0.0,
        "actual_savings": {
            "actual_sp_cost": 0.0,
            "on_demand_equivalent_cost": 0.0,
            "net_savings": 0.0,
            "savings_percentage": 0.0,
            "breakdown_by_type": {},
        },
    }

    result = handler.generate_json_report(coverage_history, savings_data)

    # Verify it's valid JSON
    report = json.loads(result)

    # Verify zeros/empty values
    assert report["coverage_summary"]["current_coverage_percentage"] == 0.0
    assert report["coverage_summary"]["average_coverage_percentage"] == 0.0
    assert report["coverage_summary"]["trend_direction"] == "stable"
    assert report["coverage_summary"]["data_points"] == 0
    assert report["savings_summary"]["active_plans_count"] == 0
    assert report["savings_summary"]["total_hourly_commitment"] == 0.0
    assert len(report["coverage_history"]) == 0
    assert len(report["active_savings_plans"]) == 0

    # Verify actual savings are zero
    assert "actual_savings" in report
    assert report["actual_savings"]["net_savings"] == 0.0
    assert report["actual_savings"]["sp_cost"] == 0.0
    assert report["actual_savings"]["on_demand_cost"] == 0.0
    assert report["actual_savings"]["savings_percentage"] == 0.0


def test_generate_json_report_trend_increasing():
    """Test JSON report shows increasing trend."""
    import json

    coverage_history = [
        {
            "date": "2026-01-10",
            "coverage_percentage": 70.0,
            "covered_hours": 280.0,
            "on_demand_hours": 120.0,
            "total_hours": 400.0,
        },
        {
            "date": "2026-01-11",
            "coverage_percentage": 80.0,
            "covered_hours": 320.0,
            "on_demand_hours": 80.0,
            "total_hours": 400.0,
        },
    ]

    savings_data = {
        "total_commitment": 0.0,
        "plans_count": 0,
        "plans": [],
        "estimated_monthly_savings": 0.0,
        "average_utilization": 0.0,
        "actual_savings": {
            "actual_sp_cost": 0.0,
            "on_demand_equivalent_cost": 0.0,
            "net_savings": 0.0,
            "savings_percentage": 0.0,
            "breakdown_by_type": {},
        },
    }

    result = handler.generate_json_report(coverage_history, savings_data)
    report = json.loads(result)

    assert report["coverage_summary"]["trend_direction"] == "increasing"
    assert report["coverage_summary"]["trend_value"] == 10.0


def test_generate_json_report_trend_decreasing():
    """Test JSON report shows decreasing trend."""
    import json

    coverage_history = [
        {
            "date": "2026-01-10",
            "coverage_percentage": 80.0,
            "covered_hours": 320.0,
            "on_demand_hours": 80.0,
            "total_hours": 400.0,
        },
        {
            "date": "2026-01-11",
            "coverage_percentage": 70.0,
            "covered_hours": 280.0,
            "on_demand_hours": 120.0,
            "total_hours": 400.0,
        },
    ]

    savings_data = {
        "total_commitment": 0.0,
        "plans_count": 0,
        "plans": [],
        "estimated_monthly_savings": 0.0,
        "average_utilization": 0.0,
        "actual_savings": {
            "actual_sp_cost": 0.0,
            "on_demand_equivalent_cost": 0.0,
            "net_savings": 0.0,
            "savings_percentage": 0.0,
            "breakdown_by_type": {},
        },
    }

    result = handler.generate_json_report(coverage_history, savings_data)
    report = json.loads(result)

    assert report["coverage_summary"]["trend_direction"] == "decreasing"
    assert report["coverage_summary"]["trend_value"] == -10.0


def test_generate_json_report_trend_stable():
    """Test JSON report shows stable trend."""
    import json

    coverage_history = [
        {
            "date": "2026-01-10",
            "coverage_percentage": 75.0,
            "covered_hours": 300.0,
            "on_demand_hours": 100.0,
            "total_hours": 400.0,
        },
        {
            "date": "2026-01-11",
            "coverage_percentage": 75.0,
            "covered_hours": 300.0,
            "on_demand_hours": 100.0,
            "total_hours": 400.0,
        },
    ]

    savings_data = {
        "total_commitment": 0.0,
        "plans_count": 0,
        "plans": [],
        "estimated_monthly_savings": 0.0,
        "average_utilization": 0.0,
        "actual_savings": {
            "actual_sp_cost": 0.0,
            "on_demand_equivalent_cost": 0.0,
            "net_savings": 0.0,
            "savings_percentage": 0.0,
            "breakdown_by_type": {},
        },
    }

    result = handler.generate_json_report(coverage_history, savings_data)
    report = json.loads(result)

    assert report["coverage_summary"]["trend_direction"] == "stable"
    assert report["coverage_summary"]["trend_value"] == 0.0


# ============================================================================
# S3 Upload Tests
# ============================================================================


def test_upload_report_to_s3_success(mock_env_vars):
    """Test successful S3 upload."""
    config = handler.load_configuration()

    with patch.object(handler.s3_client, "put_object") as mock_put_object:
        mock_put_object.return_value = {}

        report_content = "<html>Test Report</html>"
        result = handler.upload_report_to_s3(config, report_content, "html")

        assert result.startswith("savings-plans-report_")
        assert result.endswith(".html")

        # Verify put_object was called with correct parameters
        mock_put_object.assert_called_once()
        call_args = mock_put_object.call_args[1]
        assert call_args["Bucket"] == "test-reports-bucket"
        assert call_args["ContentType"] == "text/html"
        assert call_args["ServerSideEncryption"] == "AES256"


def test_upload_report_to_s3_json_format(mock_env_vars):
    """Test S3 upload with JSON format."""
    config = handler.load_configuration()

    with patch.object(handler.s3_client, "put_object") as mock_put_object:
        mock_put_object.return_value = {}

        report_content = '{"test": "report"}'
        result = handler.upload_report_to_s3(config, report_content, "json")

        assert result.startswith("savings-plans-report_")
        assert result.endswith(".json")

        # Verify put_object was called with correct parameters
        mock_put_object.assert_called_once()
        call_args = mock_put_object.call_args[1]
        assert call_args["Bucket"] == "test-reports-bucket"
        assert call_args["ContentType"] == "application/json"
        assert call_args["ServerSideEncryption"] == "AES256"


def test_upload_report_to_s3_error(mock_env_vars):
    """Test S3 upload error handling."""
    config = handler.load_configuration()

    with patch.object(handler.s3_client, "put_object") as mock_put_object:
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Not authorized"}}
        mock_put_object.side_effect = ClientError(error_response, "put_object")

        with pytest.raises(ClientError):
            handler.upload_report_to_s3(config, "<html>Test</html>", "html")


# ============================================================================
# Email Notification Tests
# ============================================================================


def test_send_report_email_success(mock_env_vars):
    """Test successful email notification."""
    config = handler.load_configuration()

    coverage_summary = {
        "current_coverage": 80.0,
        "avg_coverage": 77.5,
        "coverage_days": 30,
        "trend_direction": "↑",
    }

    savings_summary = {
        "plans_count": 2,
        "total_commitment": 3.5,
        "estimated_monthly_savings": 639.25,
        "average_utilization": 96.0,
        "actual_savings": {
            "actual_sp_cost": 1200.50,
            "on_demand_equivalent_cost": 1839.75,
            "net_savings": 639.25,
            "savings_percentage": 34.75,
            "breakdown_by_type": {
                "ComputeSavingsPlans": {"plans_count": 1, "total_commitment": 2.0},
                "SageMakerSavingsPlans": {"plans_count": 1, "total_commitment": 1.5},
            },
        },
    }

    with patch.object(handler.sns_client, "publish") as mock_publish:
        mock_publish.return_value = {}

        handler.send_report_email(
            config,
            "savings-plans-report_2026-01-14_12-00-00.html",
            coverage_summary,
            savings_summary,
        )

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[1]
        assert call_args["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:test-topic"
        assert "80.0%" in call_args["Subject"]
        assert "$639" in call_args["Subject"]
        assert "Actual Savings" in call_args["Subject"]
        assert "s3://test-reports-bucket/" in call_args["Message"]
        assert "ACTUAL SAVINGS SUMMARY" in call_args["Message"]
        assert "Net Savings: $639.25" in call_args["Message"]
        assert "Savings Percentage: 34.75%" in call_args["Message"]
        assert "Breakdown by Plan Type:" in call_args["Message"]
        assert "ComputeSavingsPlans" in call_args["Message"]
        assert "SageMakerSavingsPlans" in call_args["Message"]


def test_send_report_email_error(mock_env_vars):
    """Test email notification error handling."""
    config = handler.load_configuration()

    coverage_summary = {
        "current_coverage": 80.0,
        "avg_coverage": 77.5,
        "coverage_days": 30,
        "trend_direction": "↑",
    }
    savings_summary = {
        "plans_count": 2,
        "total_commitment": 3.5,
        "estimated_monthly_savings": 639.25,
        "average_utilization": 96.0,
        "actual_savings": {
            "actual_sp_cost": 1200.50,
            "on_demand_equivalent_cost": 1839.75,
            "net_savings": 639.25,
            "savings_percentage": 34.75,
            "breakdown_by_type": {},
        },
    }

    with patch.object(handler.sns_client, "publish") as mock_publish:
        error_response = {"Error": {"Code": "InvalidParameter", "Message": "Invalid topic"}}
        mock_publish.side_effect = ClientError(error_response, "publish")

        with pytest.raises(ClientError):
            handler.send_report_email(config, "s3-key", coverage_summary, savings_summary)


def test_send_error_email(mock_env_vars):
    """Test error email notification."""
    config = handler.load_configuration()

    with patch.object(handler.sns_client, "publish") as mock_publish:
        mock_publish.return_value = {}

        handler.send_error_email(config, "Test error message")

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[1]
        assert "[SP Autopilot] Reporter Lambda Failed" in call_args["Subject"]
        assert "Test error message" in call_args["Message"]


def test_send_error_email_silent_failure(mock_env_vars):
    """Test that send_error_email doesn't raise on SNS failure."""
    config = handler.load_configuration()

    with patch.object(handler.sns_client, "publish") as mock_publish:
        error_response = {"Error": {"Code": "InvalidParameter", "Message": "Invalid topic"}}
        mock_publish.side_effect = ClientError(error_response, "publish")

        # Should not raise - just log error
        handler.send_error_email(config, "Test error")


# ============================================================================
# Handler Integration Tests
# ============================================================================


def test_handler_success_with_email(mock_env_vars):
    """Test successful handler execution with email enabled."""
    with (
        patch("handler.load_configuration") as mock_load_config,
        patch("handler.get_clients") as mock_get_clients,
        patch("handler.get_coverage_history") as mock_get_coverage,
        patch("handler.get_savings_data") as mock_get_savings,
        patch("handler.generate_html_report") as mock_generate_html,
        patch("handler.upload_report_to_s3") as mock_upload,
        patch("handler.send_report_email") as mock_send_email,
    ):
        mock_load_config.return_value = {
            "reports_bucket": "test-bucket",
            "sns_topic_arn": "test-arn",
            "report_format": "html",
            "email_reports": True,
            "management_account_role_arn": None,
            "tags": {},
        }

        mock_get_clients.return_value = {
            "ce": MagicMock(),
            "savingsplans": MagicMock(),
            "sns": MagicMock(),
            "s3": MagicMock(),
        }

        mock_get_coverage.return_value = [
            {
                "date": "2026-01-10",
                "coverage_percentage": 75.0,
                "covered_hours": 300.0,
                "on_demand_hours": 100.0,
                "total_hours": 400.0,
            },
            {
                "date": "2026-01-11",
                "coverage_percentage": 80.0,
                "covered_hours": 320.0,
                "on_demand_hours": 80.0,
                "total_hours": 400.0,
            },
        ]

        mock_get_savings.return_value = {
            "plans_count": 2,
            "total_commitment": 3.5,
            "estimated_monthly_savings": 639.25,
            "average_utilization": 96.0,
            "actual_savings": {
                "actual_sp_cost": 1200.50,
                "on_demand_equivalent_cost": 1839.75,
                "net_savings": 639.25,
                "savings_percentage": 34.75,
                "breakdown_by_type": {},
            },
        }

        mock_generate_html.return_value = "<html>Test Report</html>"
        mock_upload.return_value = "savings-plans-report_2026-01-14_12-00-00.html"

        result = handler.handler({}, None)

        assert result["statusCode"] == 200
        assert "savings-plans-report_" in result["body"]
        assert mock_send_email.called


def test_handler_success_without_email(mock_env_vars, monkeypatch):
    """Test successful handler execution with email disabled."""
    monkeypatch.setenv("EMAIL_REPORTS", "false")

    with (
        patch("handler.load_configuration") as mock_load_config,
        patch("handler.get_clients") as mock_get_clients,
        patch("handler.get_coverage_history") as mock_get_coverage,
        patch("handler.get_savings_data") as mock_get_savings,
        patch("handler.generate_html_report") as mock_generate_html,
        patch("handler.upload_report_to_s3") as mock_upload,
        patch("handler.send_report_email") as mock_send_email,
    ):
        mock_load_config.return_value = {
            "reports_bucket": "test-bucket",
            "sns_topic_arn": "test-arn",
            "report_format": "html",
            "email_reports": False,
            "management_account_role_arn": None,
            "tags": {},
        }

        mock_get_clients.return_value = {
            "ce": MagicMock(),
            "savingsplans": MagicMock(),
            "sns": MagicMock(),
            "s3": MagicMock(),
        }

        mock_get_coverage.return_value = []
        mock_get_savings.return_value = {
            "plans_count": 0,
            "total_commitment": 0.0,
            "estimated_monthly_savings": 0.0,
            "average_utilization": 0.0,
            "actual_savings": {
                "actual_sp_cost": 0.0,
                "on_demand_equivalent_cost": 0.0,
                "net_savings": 0.0,
                "savings_percentage": 0.0,
                "breakdown_by_type": {},
            },
        }
        mock_generate_html.return_value = "<html>Test Report</html>"
        mock_upload.return_value = "savings-plans-report_2026-01-14_12-00-00.html"

        result = handler.handler({}, None)

        assert result["statusCode"] == 200
        assert not mock_send_email.called


def test_handler_assume_role_error(mock_env_vars, monkeypatch):
    """Test handler error handling when assume role fails."""
    monkeypatch.setenv("MANAGEMENT_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/TestRole")

    with (
        patch("handler.load_configuration") as mock_load_config,
        patch("handler.get_clients") as mock_get_clients,
        patch("handler.send_error_email") as mock_send_error,
    ):
        mock_load_config.return_value = {
            "reports_bucket": "test-bucket",
            "sns_topic_arn": "test-arn",
            "report_format": "html",
            "email_reports": True,
            "management_account_role_arn": "arn:aws:iam::123456789012:role/TestRole",
            "tags": {},
        }

        error_response = {"Error": {"Code": "AccessDenied", "Message": "Not authorized"}}
        mock_get_clients.side_effect = ClientError(error_response, "AssumeRole")

        with pytest.raises(ClientError):
            handler.handler({}, None)

        # Verify error email was sent with role ARN in message (check first call)
        assert mock_send_error.called
        # Handler calls send_error_email twice - first with role ARN, then from outer exception handler
        error_msg = mock_send_error.call_args_list[0][0][1]
        assert "arn:aws:iam::123456789012:role/TestRole" in error_msg


def test_handler_general_error(mock_env_vars):
    """Test handler error handling for general exceptions."""
    with (
        patch("handler.load_configuration") as mock_load_config,
        patch("handler.get_clients") as mock_get_clients,
        patch("handler.get_coverage_history") as mock_get_coverage,
        patch("handler.send_error_email") as mock_send_error,
    ):
        mock_load_config.return_value = {
            "reports_bucket": "test-bucket",
            "sns_topic_arn": "test-arn",
            "report_format": "html",
            "email_reports": False,
            "management_account_role_arn": None,
            "tags": {},
        }

        mock_get_clients.return_value = {
            "ce": MagicMock(),
            "savingsplans": MagicMock(),
            "sns": MagicMock(),
            "s3": MagicMock(),
        }

        mock_get_coverage.side_effect = Exception("Unexpected error")

        with pytest.raises(Exception):
            handler.handler({}, None)

        # Verify error email was sent
        assert mock_send_error.called


# ============================================================================
# Slack/Teams Notification Tests
# ============================================================================


def test_send_report_email_with_slack_notification(mock_env_vars, monkeypatch):
    """Test report email sends Slack notification when webhook URL configured."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST/WEBHOOK/URL")

    config = handler.load_configuration()

    coverage_summary = {
        "current_coverage": 80.0,
        "avg_coverage": 77.5,
        "coverage_days": 30,
        "trend_direction": "↑",
    }

    savings_summary = {
        "plans_count": 2,
        "total_commitment": 3.5,
        "estimated_monthly_savings": 639.25,
        "average_utilization": 96.0,
        "actual_savings": {
            "actual_sp_cost": 1200.50,
            "on_demand_equivalent_cost": 1839.75,
            "net_savings": 639.25,
            "savings_percentage": 34.75,
            "breakdown_by_type": {},
        },
    }

    with (
        patch.object(handler.sns_client, "publish") as mock_publish,
        patch("handler.notifications.send_slack_notification") as mock_slack,
        patch("handler.notifications.format_slack_message") as mock_format_slack,
    ):
        mock_publish.return_value = {}
        mock_slack.return_value = True
        mock_format_slack.return_value = {"text": "Test message"}

        handler.send_report_email(
            config,
            "savings-plans-report_2026-01-14_12-00-00.html",
            coverage_summary,
            savings_summary,
        )

        # Verify SNS was called
        mock_publish.assert_called_once()

        # Verify Slack notification was called with correct parameters
        mock_format_slack.assert_called_once()
        call_args = mock_format_slack.call_args
        assert "Coverage" in call_args[0][0]  # Subject contains 'Coverage'
        assert call_args[1]["severity"] == "info"

        mock_slack.assert_called_once_with(
            "https://hooks.slack.com/services/TEST/WEBHOOK/URL", {"text": "Test message"}
        )


def test_send_report_email_with_teams_notification(mock_env_vars, monkeypatch):
    """Test report email sends Teams notification when webhook URL configured."""
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://outlook.office.com/webhook/TEST")

    config = handler.load_configuration()

    coverage_summary = {
        "current_coverage": 80.0,
        "avg_coverage": 77.5,
        "coverage_days": 30,
        "trend_direction": "↑",
    }

    savings_summary = {
        "plans_count": 2,
        "total_commitment": 3.5,
        "estimated_monthly_savings": 639.25,
        "average_utilization": 96.0,
        "actual_savings": {
            "actual_sp_cost": 1200.50,
            "on_demand_equivalent_cost": 1839.75,
            "net_savings": 639.25,
            "savings_percentage": 34.75,
            "breakdown_by_type": {},
        },
    }

    with (
        patch.object(handler.sns_client, "publish") as mock_publish,
        patch("handler.notifications.send_teams_notification") as mock_teams,
        patch("handler.notifications.format_teams_message") as mock_format_teams,
    ):
        mock_publish.return_value = {}
        mock_teams.return_value = True
        mock_format_teams.return_value = {"title": "Test message"}

        handler.send_report_email(
            config,
            "savings-plans-report_2026-01-14_12-00-00.html",
            coverage_summary,
            savings_summary,
        )

        # Verify SNS was called
        mock_publish.assert_called_once()

        # Verify Teams notification was called with correct parameters
        mock_format_teams.assert_called_once()
        call_args = mock_format_teams.call_args
        assert "Coverage" in call_args[0][0]  # Subject contains 'Coverage'

        mock_teams.assert_called_once_with(
            "https://outlook.office.com/webhook/TEST", {"title": "Test message"}
        )


def test_send_report_email_without_notifications(mock_env_vars):
    """Test report email without Slack/Teams notifications when not configured."""
    config = handler.load_configuration()

    coverage_summary = {
        "current_coverage": 80.0,
        "avg_coverage": 77.5,
        "coverage_days": 30,
        "trend_direction": "↑",
    }

    savings_summary = {
        "plans_count": 2,
        "total_commitment": 3.5,
        "estimated_monthly_savings": 639.25,
        "average_utilization": 96.0,
        "actual_savings": {
            "actual_sp_cost": 1200.50,
            "on_demand_equivalent_cost": 1839.75,
            "net_savings": 639.25,
            "savings_percentage": 34.75,
            "breakdown_by_type": {},
        },
    }

    with (
        patch.object(handler.sns_client, "publish") as mock_publish,
        patch("handler.notifications.send_slack_notification") as mock_slack,
        patch("handler.notifications.send_teams_notification") as mock_teams,
    ):
        mock_publish.return_value = {}

        handler.send_report_email(
            config,
            "savings-plans-report_2026-01-14_12-00-00.html",
            coverage_summary,
            savings_summary,
        )

        # Verify SNS was called
        mock_publish.assert_called_once()

        # Verify Slack/Teams notifications were NOT called (no webhook URLs)
        assert not mock_slack.called
        assert not mock_teams.called


def test_send_report_email_slack_notification_failure(mock_env_vars, monkeypatch):
    """Test that report email continues even if Slack notification fails."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST/WEBHOOK/URL")

    config = handler.load_configuration()

    coverage_summary = {
        "current_coverage": 80.0,
        "avg_coverage": 77.5,
        "coverage_days": 30,
        "trend_direction": "↑",
    }

    savings_summary = {
        "plans_count": 2,
        "total_commitment": 3.5,
        "estimated_monthly_savings": 639.25,
        "average_utilization": 96.0,
        "actual_savings": {
            "actual_sp_cost": 1200.50,
            "on_demand_equivalent_cost": 1839.75,
            "net_savings": 639.25,
            "savings_percentage": 34.75,
            "breakdown_by_type": {},
        },
    }

    with (
        patch.object(handler.sns_client, "publish") as mock_publish,
        patch("handler.notifications.send_slack_notification") as mock_slack,
        patch("handler.notifications.format_slack_message") as mock_format_slack,
    ):
        mock_publish.return_value = {}
        mock_slack.side_effect = Exception("Slack webhook failed")
        mock_format_slack.return_value = {"text": "Test message"}

        # Should not raise - notification failures should be non-fatal
        handler.send_report_email(
            config,
            "savings-plans-report_2026-01-14_12-00-00.html",
            coverage_summary,
            savings_summary,
        )

        # Verify SNS was still called
        mock_publish.assert_called_once()


def test_send_report_email_teams_notification_failure(mock_env_vars, monkeypatch):
    """Test that report email continues even if Teams notification fails."""
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://outlook.office.com/webhook/TEST")

    config = handler.load_configuration()

    coverage_summary = {
        "current_coverage": 80.0,
        "avg_coverage": 77.5,
        "coverage_days": 30,
        "trend_direction": "↑",
    }

    savings_summary = {
        "plans_count": 2,
        "total_commitment": 3.5,
        "estimated_monthly_savings": 639.25,
        "average_utilization": 96.0,
        "actual_savings": {
            "actual_sp_cost": 1200.50,
            "on_demand_equivalent_cost": 1839.75,
            "net_savings": 639.25,
            "savings_percentage": 34.75,
            "breakdown_by_type": {},
        },
    }

    with (
        patch.object(handler.sns_client, "publish") as mock_publish,
        patch("handler.notifications.send_teams_notification") as mock_teams,
        patch("handler.notifications.format_teams_message") as mock_format_teams,
    ):
        mock_publish.return_value = {}
        mock_teams.side_effect = Exception("Teams webhook failed")
        mock_format_teams.return_value = {"title": "Test message"}

        # Should not raise - notification failures should be non-fatal
        handler.send_report_email(
            config,
            "savings-plans-report_2026-01-14_12-00-00.html",
            coverage_summary,
            savings_summary,
        )

        # Verify SNS was still called
        mock_publish.assert_called_once()


def test_send_error_email_with_slack_notification(mock_env_vars, monkeypatch):
    """Test error email sends Slack notification when webhook URL configured."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST/WEBHOOK/URL")

    config = handler.load_configuration()

    with (
        patch.object(handler.sns_client, "publish") as mock_publish,
        patch("handler.notifications.send_slack_notification") as mock_slack,
        patch("handler.notifications.format_slack_message") as mock_format_slack,
    ):
        mock_publish.return_value = {}
        mock_slack.return_value = True
        mock_format_slack.return_value = {"text": "Error message"}

        handler.send_error_email(config, "Test error message")

        # Verify SNS was called
        mock_publish.assert_called_once()

        # Verify Slack notification was called with error severity
        mock_format_slack.assert_called_once()
        call_args = mock_format_slack.call_args
        assert "Failed" in call_args[0][0]  # Subject contains 'Failed'
        assert call_args[1]["severity"] == "error"

        mock_slack.assert_called_once_with(
            "https://hooks.slack.com/services/TEST/WEBHOOK/URL", {"text": "Error message"}
        )


def test_send_error_email_with_teams_notification(mock_env_vars, monkeypatch):
    """Test error email sends Teams notification when webhook URL configured."""
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://outlook.office.com/webhook/TEST")

    config = handler.load_configuration()

    with (
        patch.object(handler.sns_client, "publish") as mock_publish,
        patch("handler.notifications.send_teams_notification") as mock_teams,
        patch("handler.notifications.format_teams_message") as mock_format_teams,
    ):
        mock_publish.return_value = {}
        mock_teams.return_value = True
        mock_format_teams.return_value = {"title": "Error message"}

        handler.send_error_email(config, "Test error message")

        # Verify SNS was called
        mock_publish.assert_called_once()

        # Verify Teams notification was called
        mock_format_teams.assert_called_once()
        call_args = mock_format_teams.call_args
        assert "Failed" in call_args[0][0]  # Subject contains 'Failed'

        mock_teams.assert_called_once_with(
            "https://outlook.office.com/webhook/TEST", {"title": "Error message"}
        )


def test_send_error_email_slack_notification_failure(mock_env_vars, monkeypatch):
    """Test that error email continues even if Slack notification fails."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST/WEBHOOK/URL")

    config = handler.load_configuration()

    with (
        patch.object(handler.sns_client, "publish") as mock_publish,
        patch("handler.notifications.send_slack_notification") as mock_slack,
        patch("handler.notifications.format_slack_message") as mock_format_slack,
    ):
        mock_publish.return_value = {}
        mock_slack.side_effect = Exception("Slack webhook failed")
        mock_format_slack.return_value = {"text": "Error message"}

        # Should not raise - error notification failures should be silent
        handler.send_error_email(config, "Test error message")

        # Verify SNS was still called
        mock_publish.assert_called_once()


def test_send_error_email_teams_notification_failure(mock_env_vars, monkeypatch):
    """Test that error email continues even if Teams notification fails."""
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://outlook.office.com/webhook/TEST")

    config = handler.load_configuration()

    with (
        patch.object(handler.sns_client, "publish") as mock_publish,
        patch("handler.notifications.send_teams_notification") as mock_teams,
        patch("handler.notifications.format_teams_message") as mock_format_teams,
    ):
        mock_publish.return_value = {}
        mock_teams.side_effect = Exception("Teams webhook failed")
        mock_format_teams.return_value = {"title": "Error message"}

        # Should not raise - error notification failures should be silent
        handler.send_error_email(config, "Test error message")

        # Verify SNS was still called
        mock_publish.assert_called_once()


def test_load_configuration_with_webhook_urls(monkeypatch):
    """Test that load_configuration includes webhook URLs."""
    monkeypatch.setenv("REPORTS_BUCKET", "test-bucket")
    monkeypatch.setenv("SNS_TOPIC_ARN", "test-sns-arn")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST")
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://outlook.office.com/webhook/TEST")

    config = handler.load_configuration()

    assert config["slack_webhook_url"] == "https://hooks.slack.com/services/TEST"
    assert config["teams_webhook_url"] == "https://outlook.office.com/webhook/TEST"


def test_load_configuration_without_webhook_urls(mock_env_vars):
    """Test that load_configuration handles missing webhook URLs."""
    config = handler.load_configuration()

    assert config["slack_webhook_url"] is None
    assert config["teams_webhook_url"] is None

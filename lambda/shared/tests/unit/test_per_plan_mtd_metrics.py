"""Unit tests for shared.savings_plans_metrics.get_per_plan_mtd_metrics.

Verifies the parsing of AWS GetSavingsPlansUtilizationDetails responses and the
defensive behavior against ClientError / malformed responses.
"""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from shared.savings_plans_metrics import get_per_plan_mtd_metrics


def _aws_details_response(items):
    return {"SavingsPlansUtilizationDetails": items}


def _item(arn, total, used, util_pct, net, ondemand):
    return {
        "SavingsPlanArn": arn,
        "Utilization": {
            "TotalCommitment": str(total),
            "UsedCommitment": str(used),
            "UnusedCommitment": str(total - used),
            "UtilizationPercentage": str(util_pct),
        },
        "Savings": {
            "NetSavings": str(net),
            "OnDemandCostEquivalent": str(ondemand),
        },
        "AmortizedCommitment": {
            "AmortizedRecurringCommitment": str(total),
            "AmortizedUpfrontCommitment": "0",
            "TotalAmortizedCommitment": str(total),
        },
    }


class TestGetPerPlanMtdMetricsHappyPath:
    def test_parses_response_into_per_arn_dict(self):
        ce = MagicMock()
        ce.get_savings_plans_utilization_details.return_value = _aws_details_response(
            [
                _item(
                    arn="arn:aws:savingsplans::123:savingsplan/aaa",
                    total=100.0,
                    used=100.0,
                    util_pct=100.0,
                    net=50.0,
                    ondemand=150.0,
                ),
                _item(
                    arn="arn:aws:savingsplans::123:savingsplan/bbb",
                    total=50.0,
                    used=40.0,
                    util_pct=80.0,
                    net=10.0,
                    ondemand=50.0,
                ),
            ]
        )

        result = get_per_plan_mtd_metrics(ce)

        assert set(result) == {
            "arn:aws:savingsplans::123:savingsplan/aaa",
            "arn:aws:savingsplans::123:savingsplan/bbb",
        }
        aaa = result["arn:aws:savingsplans::123:savingsplan/aaa"]
        assert aaa["mtd_total_commitment"] == 100.0
        assert aaa["mtd_used_commitment"] == 100.0
        assert aaa["mtd_utilization_percentage"] == 100.0
        assert aaa["mtd_net_savings"] == 50.0
        assert aaa["mtd_on_demand_equivalent"] == 150.0
        # discount = used / ondemand savings: (150 - 100) / 150 = 33.3%
        assert aaa["discount_percentage"] == pytest.approx(33.333, rel=1e-3)

    def test_calls_api_with_month_to_date_window(self):
        ce = MagicMock()
        ce.get_savings_plans_utilization_details.return_value = _aws_details_response([])
        get_per_plan_mtd_metrics(ce)
        call_args = ce.get_savings_plans_utilization_details.call_args
        time_period = call_args.kwargs["TimePeriod"]
        assert time_period["Start"].endswith("-01")  # first-of-month
        assert time_period["End"] >= time_period["Start"]


class TestGetPerPlanMtdMetricsDefensive:
    """The reporter should never fail because per-plan details aren't fetchable."""

    def test_returns_empty_on_data_unavailable(self):
        ce = MagicMock()
        ce.get_savings_plans_utilization_details.side_effect = ClientError(
            {"Error": {"Code": "DataUnavailableException", "Message": "no data"}},
            "GetSavingsPlansUtilizationDetails",
        )
        assert get_per_plan_mtd_metrics(ce) == {}

    def test_returns_empty_on_other_client_error(self):
        ce = MagicMock()
        ce.get_savings_plans_utilization_details.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "nope"}},
            "GetSavingsPlansUtilizationDetails",
        )
        assert get_per_plan_mtd_metrics(ce) == {}

    def test_returns_empty_on_unexpected_exception(self):
        ce = MagicMock()
        ce.get_savings_plans_utilization_details.side_effect = RuntimeError("boom")
        assert get_per_plan_mtd_metrics(ce) == {}

    def test_skips_items_without_arn(self):
        ce = MagicMock()
        ce.get_savings_plans_utilization_details.return_value = _aws_details_response(
            [
                {"Utilization": {"TotalCommitment": "10"}},  # no arn
                _item("arn-valid", 1.0, 1.0, 100.0, 0.5, 1.5),
            ]
        )
        result = get_per_plan_mtd_metrics(ce)
        assert list(result) == ["arn-valid"]

    def test_skips_items_with_malformed_numeric_fields(self):
        ce = MagicMock()
        ce.get_savings_plans_utilization_details.return_value = _aws_details_response(
            [
                {
                    "SavingsPlanArn": "arn-bad",
                    "Utilization": {"TotalCommitment": "not-a-number"},
                    "Savings": {},
                },
                _item("arn-good", 1.0, 1.0, 100.0, 0.5, 1.5),
            ]
        )
        result = get_per_plan_mtd_metrics(ce)
        assert list(result) == ["arn-good"]

    def test_returns_empty_when_details_is_not_a_list(self):
        ce = MagicMock()
        ce.get_savings_plans_utilization_details.return_value = {
            "SavingsPlansUtilizationDetails": "oops-not-a-list",
        }
        assert get_per_plan_mtd_metrics(ce) == {}

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from shared.demo_mode import (
    _anonymize_id,
    _generate_daily_multipliers,
    _generate_hourly_multipliers,
    _point_multiplier,
    _random_factor,
    _randomize_plan_dates,
    _scale,
    _scale_coverage_data,
    _scale_savings_data,
    is_demo_mode,
    randomize_report_data,
)


COVERAGE_DATA = {
    "compute": {
        "timeseries": [
            {"timestamp": "2026-01-01T00:00:00Z", "covered": 10.0, "total": 15.0, "coverage": 66.7},
            {"timestamp": "2026-01-01T01:00:00Z", "covered": 12.0, "total": 18.0, "coverage": 66.7},
        ],
        "summary": {
            "avg_coverage_total": 66.7,
            "avg_hourly_covered": 11.0,
            "avg_hourly_total": 16.5,
            "min_hourly_total": 15.0,
            "max_hourly_total": 18.0,
            "est_monthly_covered": 7920.0,
            "est_monthly_total": 11880.0,
        },
    },
    "database": {"timeseries": [], "summary": {}},
    "sagemaker": {"timeseries": [], "summary": {}},
}

SAVINGS_DATA = {
    "plans_count": 2,
    "total_commitment": 1.5,
    "net_savings_hourly": 0.3,
    "average_utilization": 85.0,
    "plans": [
        {"plan_id": "sp-12345678", "hourly_commitment": 1.0, "plan_type": "Compute"},
        {"plan_id": "sp-87654321", "hourly_commitment": 0.5, "plan_type": "Compute"},
    ],
    "actual_savings": {
        "actual_sp_cost_hourly": 1.2,
        "on_demand_equivalent_hourly": 1.5,
        "net_savings_hourly": 0.3,
        "savings_percentage": 20.0,
        "breakdown_by_type": {
            "Compute": {
                "plans_count": 2,
                "total_commitment": 1.5,
                "net_savings_hourly": 0.3,
                "on_demand_equivalent_hourly": 1.5,
                "actual_sp_cost_hourly": 1.2,
                "savings_percentage": 20.0,
            }
        },
    },
}


class TestIsDemoMode:
    def test_true(self):
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            assert is_demo_mode() is True

    def test_false(self):
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            assert is_demo_mode() is False

    def test_default(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DEMO_MODE", None)
            assert is_demo_mode() is False

    def test_case_insensitive(self):
        with patch.dict(os.environ, {"DEMO_MODE": "TRUE"}):
            assert is_demo_mode() is True


class TestRandomFactor:
    def test_within_range(self):
        for _ in range(100):
            f = _random_factor()
            assert 0.3 <= f <= 3.0

    def test_outside_deadband(self):
        for _ in range(100):
            f = _random_factor()
            assert f < 0.5 or f > 2.0


class TestScale:
    def test_basic(self):
        assert _scale(10.0, 2.0) == 20.0

    def test_zero(self):
        assert _scale(0.0, 5.0) == 0.0


class TestSeriesMultipliers:
    def test_hourly_length(self):
        assert len(_generate_hourly_multipliers()) == 24

    def test_daily_length(self):
        assert len(_generate_daily_multipliers()) == 7

    def test_hourly_business_hours_high(self):
        for _ in range(20):
            m = _generate_hourly_multipliers()
            for hour in range(9, 17):
                assert 1.0 <= m[hour] <= 2.0

    def test_hourly_off_hours_low(self):
        for _ in range(20):
            m = _generate_hourly_multipliers()
            for hour in (0, 1, 2, 3, 4, 5, 22, 23):
                assert 0.25 <= m[hour] <= 0.75

    def test_daily_weekdays_high(self):
        for _ in range(20):
            m = _generate_daily_multipliers()
            for day in range(5):
                assert 1.0 <= m[day] <= 2.0

    def test_daily_weekend_low(self):
        for _ in range(20):
            m = _generate_daily_multipliers()
            for day in (5, 6):
                assert 0.25 <= m[day] <= 0.75

    def test_point_multiplier_parses_timestamp(self):
        hourly = [1.0] * 24
        daily = [1.0] * 7
        hourly[14] = 1.5
        daily[3] = 0.8  # Thursday
        # 2026-01-01 is a Thursday, hour 14
        result = _point_multiplier("2026-01-01T14:00:00Z", hourly, daily)
        assert result == pytest.approx(1.5 * 0.8)

    def test_point_multiplier_bad_timestamp(self):
        assert _point_multiplier("invalid", [1.0] * 24, [1.0] * 7) == 1.0


# Flat series (all 1.0) for tests that don't need pattern reshaping
FLAT_HOURLY = [1.0] * 24
FLAT_DAILY = [1.0] * 7


class TestScaleCoverageData:
    def test_scales_timeseries(self):
        from copy import deepcopy

        data = deepcopy(COVERAGE_DATA)
        result = _scale_coverage_data(data, 3.0, FLAT_HOURLY, FLAT_DAILY)
        assert result["compute"]["timeseries"][0]["covered"] == pytest.approx(30.0)
        assert result["compute"]["timeseries"][0]["total"] == pytest.approx(45.0)

    def test_scales_summary_dollar_fields(self):
        from copy import deepcopy

        data = deepcopy(COVERAGE_DATA)
        result = _scale_coverage_data(data, 2.0, FLAT_HOURLY, FLAT_DAILY)
        assert result["compute"]["summary"]["avg_hourly_total"] == pytest.approx(33.0)
        assert result["compute"]["summary"]["est_monthly_total"] == pytest.approx(23760.0)

    def test_preserves_percentages(self):
        from copy import deepcopy

        data = deepcopy(COVERAGE_DATA)
        result = _scale_coverage_data(data, 2.5, FLAT_HOURLY, FLAT_DAILY)
        assert result["compute"]["summary"]["avg_coverage_total"] == 66.7

    def test_skips_missing_sp_types(self):
        result = _scale_coverage_data(
            {"compute": {"timeseries": [], "summary": {}}}, 2.0, FLAT_HOURLY, FLAT_DAILY
        )
        assert "database" not in result

    def test_series_multipliers_reshape_on_demand_only(self):
        from copy import deepcopy

        hourly = [1.0] * 24
        hourly[0] = 1.5
        hourly[1] = 0.7
        data = deepcopy(COVERAGE_DATA)
        result = _scale_coverage_data(data, 1.0, hourly, FLAT_DAILY)
        # covered stays uniform (factor=1.0), on-demand gets reshaped
        # point 0: covered=10, on_demand=5 -> total = 10 + 5*1.5 = 17.5
        assert result["compute"]["timeseries"][0]["covered"] == pytest.approx(10.0)
        assert result["compute"]["timeseries"][0]["total"] == pytest.approx(17.5)
        # point 1: covered=12, on_demand=6 -> total = 12 + 6*0.7 = 16.2
        assert result["compute"]["timeseries"][1]["covered"] == pytest.approx(12.0)
        assert result["compute"]["timeseries"][1]["total"] == pytest.approx(16.2)


class TestScaleSavingsData:
    def test_scales_top_level(self):
        from copy import deepcopy

        data = deepcopy(SAVINGS_DATA)
        result = _scale_savings_data(data, 3.0)
        assert result["total_commitment"] == pytest.approx(4.5)
        assert result["net_savings_hourly"] == pytest.approx(0.9)

    def test_scales_actual_savings(self):
        from copy import deepcopy

        data = deepcopy(SAVINGS_DATA)
        result = _scale_savings_data(data, 2.0)
        assert result["actual_savings"]["actual_sp_cost_hourly"] == pytest.approx(2.4)
        assert result["actual_savings"]["on_demand_equivalent_hourly"] == pytest.approx(3.0)

    def test_preserves_percentages(self):
        from copy import deepcopy

        data = deepcopy(SAVINGS_DATA)
        result = _scale_savings_data(data, 2.0)
        assert result["actual_savings"]["savings_percentage"] == 20.0
        assert (
            result["actual_savings"]["breakdown_by_type"]["Compute"]["savings_percentage"] == 20.0
        )

    def test_anonymizes_plan_ids(self):
        from copy import deepcopy

        data = deepcopy(SAVINGS_DATA)
        result = _scale_savings_data(data, 2.0)
        for plan in result["plans"]:
            assert plan["plan_id"].startswith("demo-")

    def test_scales_breakdown(self):
        from copy import deepcopy

        data = deepcopy(SAVINGS_DATA)
        result = _scale_savings_data(data, 3.0)
        breakdown = result["actual_savings"]["breakdown_by_type"]["Compute"]
        assert breakdown["total_commitment"] == pytest.approx(4.5)
        assert breakdown["net_savings_hourly"] == pytest.approx(0.9)

    def test_preserves_plan_count(self):
        from copy import deepcopy

        data = deepcopy(SAVINGS_DATA)
        result = _scale_savings_data(data, 2.0)
        assert result["plans_count"] == 2


class TestRandomizePlanDates:
    def test_shifts_dates(self):
        plan = {
            "start_date": "2025-06-01T00:00:00Z",
            "end_date": "2026-06-01T00:00:00Z",
        }
        _randomize_plan_dates(plan)
        assert plan["start_date"] != "2025-06-01T00:00:00Z"
        assert plan["end_date"] != "2026-06-01T00:00:00Z"
        assert plan["start_date"].endswith("Z")

    def test_preserves_term_length(self):
        from datetime import datetime

        plan = {
            "start_date": "2025-01-01T00:00:00Z",
            "end_date": "2026-01-01T00:00:00Z",
        }
        _randomize_plan_dates(plan)
        start = datetime.fromisoformat(plan["start_date"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(plan["end_date"].replace("Z", "+00:00"))
        assert (end - start).days == 365

    def test_skips_unknown(self):
        plan = {"start_date": "Unknown", "end_date": "Unknown"}
        _randomize_plan_dates(plan)
        assert plan["start_date"] == "Unknown"


class TestAnonymizeId:
    def test_prefix(self):
        assert _anonymize_id("sp-12345678").startswith("demo-")

    def test_deterministic(self):
        assert _anonymize_id("sp-abc") == _anonymize_id("sp-abc")

    def test_different_inputs_differ(self):
        assert _anonymize_id("sp-aaa") != _anonymize_id("sp-bbb")


class TestRandomizeReportData:
    def test_does_not_modify_originals(self):
        from copy import deepcopy

        cov = deepcopy(COVERAGE_DATA)
        sav = deepcopy(SAVINGS_DATA)
        randomize_report_data(cov, cov, sav)
        assert cov["compute"]["timeseries"][0]["covered"] == 10.0
        assert sav["plans"][0]["plan_id"] == "sp-12345678"

    def test_returns_modified_data(self):
        from copy import deepcopy

        cov = deepcopy(COVERAGE_DATA)
        sav = deepcopy(SAVINGS_DATA)
        c_out, _d_out, s_out = randomize_report_data(cov, cov, sav)
        assert c_out["compute"]["timeseries"][0]["covered"] != 10.0
        assert s_out["plans"][0]["plan_id"].startswith("demo-")

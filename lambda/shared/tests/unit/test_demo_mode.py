from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from shared.demo_mode import (
    _anonymize_id,
    _apply_fake_coverage,
    _random_factor,
    _scale,
    _scale_coverage_data,
    _scale_savings_data,
    _time_multiplier,
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


class TestTimeMultiplier:
    def test_range(self):
        for hour in range(24):
            ts = f"2026-01-15T{hour:02d}:00:00Z"
            m = _time_multiplier(ts, is_daily=False)
            assert 1.5 <= m <= 2.5

    def test_daily_varies_by_weekday(self):
        # Monday and Sunday should produce different multipliers
        mon = _time_multiplier("2026-01-19T00:00:00Z", is_daily=True)  # Monday
        sun = _time_multiplier(
            "2026-01-18T00:00:00Z", is_daily=True
        )  # Sunday (different isoweekday)
        assert mon != sun

    def test_hourly_varies_by_hour(self):
        m0 = _time_multiplier("2026-01-15T00:00:00Z", is_daily=False)
        m12 = _time_multiplier("2026-01-15T12:00:00Z", is_daily=False)
        assert m0 != m12

    def test_deterministic(self):
        a = _time_multiplier("2026-01-15T05:00:00Z", is_daily=False)
        b = _time_multiplier("2026-01-15T05:00:00Z", is_daily=False)
        assert a == b


class TestScaleCoverageData:
    def test_scales_timeseries_with_time_multiplier(self):
        from copy import deepcopy

        data = deepcopy(COVERAGE_DATA)
        factor = 3.0
        result = _scale_coverage_data(data, factor, is_daily=False)
        # Timeseries values include the time multiplier, so they won't be exactly factor * original
        ts0 = result["compute"]["timeseries"][0]
        tm = _time_multiplier("2026-01-01T00:00:00Z", is_daily=False)
        assert ts0["covered"] == pytest.approx(10.0 * factor * tm, rel=1e-4)
        assert ts0["total"] == pytest.approx(15.0 * factor * tm, rel=1e-4)

    def test_scales_summary_dollar_fields(self):
        from copy import deepcopy

        data = deepcopy(COVERAGE_DATA)
        result = _scale_coverage_data(data, 2.0, is_daily=False)
        assert result["compute"]["summary"]["avg_hourly_total"] == pytest.approx(33.0)
        assert result["compute"]["summary"]["est_monthly_total"] == pytest.approx(23760.0)

    def test_preserves_percentages(self):
        from copy import deepcopy

        data = deepcopy(COVERAGE_DATA)
        result = _scale_coverage_data(data, 2.5, is_daily=False)
        assert result["compute"]["summary"]["avg_coverage_total"] == 66.7

    def test_skips_missing_sp_types(self):
        result = _scale_coverage_data(
            {"compute": {"timeseries": [], "summary": {}}}, 2.0, is_daily=False
        )
        assert "database" not in result


class TestApplyFakeCoverage:
    def test_sets_flat_covered_line(self):
        from copy import deepcopy

        data = deepcopy(COVERAGE_DATA)
        pcts = _apply_fake_coverage(data)
        ts = data["compute"]["timeseries"]
        assert ts[0]["covered"] == ts[1]["covered"]
        assert 0.25 <= pcts["compute"] <= 0.75

    def test_covered_within_expected_range(self):
        from copy import deepcopy

        data = deepcopy(COVERAGE_DATA)
        _apply_fake_coverage(data)
        min_total = min(p["total"] for p in data["compute"]["timeseries"])
        covered = data["compute"]["timeseries"][0]["covered"]
        assert min_total * 0.25 <= covered <= min_total * 0.75

    def test_reuses_provided_percentages(self):
        from copy import deepcopy

        data = deepcopy(COVERAGE_DATA)
        pcts = _apply_fake_coverage(data, coverage_pcts={"compute": 0.5})
        covered = data["compute"]["timeseries"][0]["covered"]
        min_total = min(p["total"] for p in data["compute"]["timeseries"])
        assert covered == pytest.approx(min_total * 0.5)
        assert pcts["compute"] == 0.5

    def test_updates_summary(self):
        from copy import deepcopy

        data = deepcopy(COVERAGE_DATA)
        _apply_fake_coverage(data, coverage_pcts={"compute": 0.5})
        covered = data["compute"]["timeseries"][0]["covered"]
        assert data["compute"]["summary"]["avg_hourly_covered"] == covered
        assert data["compute"]["summary"]["est_monthly_covered"] == pytest.approx(covered * 720)

    def test_skips_empty_timeseries(self):
        data = {"database": {"timeseries": [], "summary": {}}}
        pcts = _apply_fake_coverage(data)
        assert "database" not in pcts


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
        c_out, d_out, s_out = randomize_report_data(cov, cov, sav)
        assert c_out["compute"]["timeseries"][0]["covered"] != 10.0
        assert s_out["plans"][0]["plan_id"].startswith("demo-")
        # Fake coverage produces a flat line
        ts = c_out["compute"]["timeseries"]
        assert ts[0]["covered"] == ts[1]["covered"]
        # Hourly and daily share the same coverage percentage
        assert (
            d_out["compute"]["timeseries"][0]["covered"]
            == d_out["compute"]["timeseries"][1]["covered"]
        )

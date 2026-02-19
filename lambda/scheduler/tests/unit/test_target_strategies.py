import pytest
from target_strategies import resolve_target
from target_strategies.aws_target import resolve_aws
from target_strategies.dynamic_target import resolve_dynamic
from target_strategies.fixed_target import resolve_fixed


# ============================================================================
# Dispatcher tests (target_strategies/__init__.py)
# ============================================================================


class TestResolveTarget:
    def test_dispatches_fixed(self):
        config = {"target_strategy_type": "fixed", "coverage_target_percent": 85.0}
        result = resolve_target(config)
        assert result == pytest.approx(85.0)

    def test_dispatches_aws(self):
        config = {"target_strategy_type": "aws"}
        result = resolve_target(config)
        assert result is None

    def test_unknown_strategy_raises(self):
        config = {"target_strategy_type": "nonexistent"}
        with pytest.raises(ValueError, match="Unknown target strategy 'nonexistent'"):
            resolve_target(config)


# ============================================================================
# fixed_target tests
# ============================================================================


class TestFixedTarget:
    def test_returns_config_value(self):
        config = {"coverage_target_percent": 75.0}
        assert resolve_fixed(config) == pytest.approx(75.0)

    def test_ignores_spending_data(self):
        config = {"coverage_target_percent": 90.0}
        assert resolve_fixed(config, {"compute": {}}) == pytest.approx(90.0)

    def test_ignores_sp_type_key(self):
        config = {"coverage_target_percent": 90.0}
        assert resolve_fixed(config, None, "compute") == pytest.approx(90.0)


# ============================================================================
# aws_target tests
# ============================================================================


class TestAwsTarget:
    def test_returns_none(self):
        assert resolve_aws({}) is None

    def test_returns_none_with_params(self):
        assert resolve_aws({}, {"compute": {}}, "compute") is None


# ============================================================================
# dynamic_target tests
# ============================================================================


class TestDynamicTarget:
    def _spending_data(self, costs):
        return {
            "compute": {
                "timeseries": [{"total": c} for c in costs],
            }
        }

    def test_basic_compute(self):
        spending = self._spending_data([100.0, 110.0, 120.0])
        config = {"dynamic_risk_level": "min_hourly", "savings_percentage": 30.0}
        result = resolve_dynamic(config, spending, sp_type_key="compute")
        assert result > 0

    def test_no_spending_data_raises(self):
        config = {"dynamic_risk_level": "balanced"}
        with pytest.raises(ValueError, match="requires spending data"):
            resolve_dynamic(config, spending_data=None, sp_type_key="compute")

    def test_empty_spending_data_raises(self):
        config = {"dynamic_risk_level": "balanced"}
        with pytest.raises(ValueError, match="requires spending data"):
            resolve_dynamic(config, spending_data={}, sp_type_key="compute")

    def test_no_hourly_data_falls_back(self):
        spending = {"compute": {"timeseries": []}}
        config = {"dynamic_risk_level": "balanced", "savings_percentage": 30.0}
        result = resolve_dynamic(config, spending, sp_type_key="compute")
        assert result == pytest.approx(90.0)

    def test_all_zero_costs_falls_back(self):
        spending = {"compute": {"timeseries": [{"total": 0.0}, {"total": 0.0}]}}
        config = {"dynamic_risk_level": "balanced", "savings_percentage": 30.0}
        result = resolve_dynamic(config, spending, sp_type_key="compute")
        assert result == pytest.approx(90.0)

    def test_missing_sp_type_key_checks_all(self):
        spending = {
            "compute": {"timeseries": [{"total": 100.0}]},
            "database": {"timeseries": [{"total": 50.0}]},
        }
        config = {"dynamic_risk_level": "min_hourly", "savings_percentage": 30.0}
        result = resolve_dynamic(config, spending, sp_type_key=None)
        assert result > 0

    def test_uses_per_type_savings_percentage(self):
        spending = self._spending_data([100.0, 110.0, 120.0])
        config = {
            "dynamic_risk_level": "min_hourly",
            "savings_percentage": 30.0,
            "compute_savings_percentage": 40.0,
        }
        result = resolve_dynamic(config, spending, sp_type_key="compute")
        assert result > 0

    def test_all_risk_levels_return_value(self):
        spending = self._spending_data([80.0, 90.0, 100.0, 110.0, 120.0])
        for level in ["too_prudent", "min_hourly", "balanced", "aggressive"]:
            config = {"dynamic_risk_level": level, "savings_percentage": 30.0}
            result = resolve_dynamic(config, spending, sp_type_key="compute")
            assert result > 0, f"Risk level '{level}' returned non-positive value"

    def test_skips_sp_type_without_data(self):
        spending = {"database": {"timeseries": [{"total": 50.0}]}}
        config = {"dynamic_risk_level": "min_hourly", "savings_percentage": 30.0}
        result = resolve_dynamic(config, spending, sp_type_key="compute")
        assert result == pytest.approx(90.0)

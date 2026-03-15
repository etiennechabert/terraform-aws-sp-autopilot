import pytest
from target_strategies import resolve_target
from target_strategies.aws_target import resolve_aws
from target_strategies.dynamic_target import resolve_dynamic


# ============================================================================
# Dispatcher tests (target_strategies/__init__.py)
# ============================================================================


class TestResolveTarget:
    def test_dispatches_aws(self):
        config = {"target_strategy_type": "aws"}
        result = resolve_target(config)
        assert result is None

    def test_unknown_strategy_raises(self):
        config = {"target_strategy_type": "nonexistent"}
        with pytest.raises(ValueError, match="Unknown target strategy 'nonexistent'"):
            resolve_target(config)

    def test_fixed_strategy_no_longer_exists(self):
        config = {"target_strategy_type": "fixed", "coverage_target_percent": 85.0}
        with pytest.raises(ValueError, match="Unknown target strategy 'fixed'"):
            resolve_target(config)


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
        config = {"dynamic_risk_level": "optimal"}
        with pytest.raises(ValueError, match="requires spending data"):
            resolve_dynamic(config, spending_data=None, sp_type_key="compute")

    def test_empty_spending_data_raises(self):
        config = {"dynamic_risk_level": "optimal"}
        with pytest.raises(ValueError, match="requires spending data"):
            resolve_dynamic(config, spending_data={}, sp_type_key="compute")

    def test_no_hourly_data_falls_back(self):
        spending = {"compute": {"timeseries": []}}
        config = {"dynamic_risk_level": "optimal", "savings_percentage": 30.0}
        result = resolve_dynamic(config, spending, sp_type_key="compute")
        assert result == pytest.approx(90.0)

    def test_all_zero_costs_falls_back(self):
        spending = {"compute": {"timeseries": [{"total": 0.0}, {"total": 0.0}]}}
        config = {"dynamic_risk_level": "optimal", "savings_percentage": 30.0}
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
        for level in ["prudent", "min_hourly", "optimal", "maximum"]:
            config = {"dynamic_risk_level": level, "savings_percentage": 30.0}
            result = resolve_dynamic(config, spending, sp_type_key="compute")
            assert result > 0, f"Risk level '{level}' returned non-positive value"

    def test_skips_sp_type_without_data(self):
        spending = {"database": {"timeseries": [{"total": 50.0}]}}
        config = {"dynamic_risk_level": "min_hourly", "savings_percentage": 30.0}
        result = resolve_dynamic(config, spending, sp_type_key="compute")
        assert result == pytest.approx(90.0)

    def test_prudent_percentage_configurable(self):
        """Test that prudent_percentage config controls the prudent strategy level."""
        spending = self._spending_data([100.0, 100.0, 100.0])
        # With default (85%), prudent should be 85% of min_hourly
        config_default = {"dynamic_risk_level": "prudent", "savings_percentage": 30.0}
        result_default = resolve_dynamic(config_default, spending, sp_type_key="compute")
        assert result_default == pytest.approx(85.0)

        # With custom 50%, prudent should be 50% of min_hourly
        config_custom = {
            "dynamic_risk_level": "prudent",
            "savings_percentage": 30.0,
            "prudent_percentage": 50.0,
        }
        result_custom = resolve_dynamic(config_custom, spending, sp_type_key="compute")
        assert result_custom == pytest.approx(50.0)

    def test_prudent_percentage_default_is_85(self):
        """Test that the default prudent percentage is 85%."""
        spending = self._spending_data([100.0, 100.0, 100.0])
        # No prudent_percentage in config, should default to 85%
        config = {"dynamic_risk_level": "prudent", "savings_percentage": 30.0}
        result = resolve_dynamic(config, spending, sp_type_key="compute")
        assert result == pytest.approx(85.0)

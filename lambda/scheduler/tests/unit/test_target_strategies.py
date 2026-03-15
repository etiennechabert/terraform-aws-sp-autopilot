from unittest.mock import Mock

import pytest
from target_strategies import resolve_target
from target_strategies.aws_target import resolve_aws
from target_strategies.dynamic_target import resolve_dynamic
from target_strategies.static_target import calculate_purchase_need_static


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
        config = {"target_strategy_type": "fixed"}
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


# ============================================================================
# static_target tests
# ============================================================================


class TestStaticTarget:
    def _base_config(self, **overrides):
        config = {
            "target_strategy_type": "static",
            "split_strategy_type": "one_shot",
            "static_commitment": 5.0,
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "compute_sp_payment_option": "ALL_UPFRONT",
            "compute_sp_term": "THREE_YEAR",
            "savings_percentage": 30.0,
            "min_commitment_per_plan": 0.001,
            "lookback_hours": 336,
        }
        config.update(overrides)
        return config

    def _spending_data(self, avg_covered, avg_total):
        return {
            "compute": {
                "summary": {
                    "avg_coverage_total": (avg_covered / avg_total * 100) if avg_total > 0 else 0,
                    "avg_hourly_total": avg_total,
                    "avg_hourly_covered": avg_covered,
                },
            }
        }

    def test_one_shot_purchases_full_gap(self):
        """With $0 existing commitment, one_shot should purchase the full target."""
        config = self._base_config(static_commitment=5.0)
        spending = self._spending_data(avg_covered=0.0, avg_total=100.0)
        clients = {"ce": Mock(), "savingsplans": Mock()}

        result = calculate_purchase_need_static(config, clients, spending)

        assert len(result) == 1
        assert result[0]["sp_type"] == "compute"
        assert result[0]["hourly_commitment"] == pytest.approx(5.0)
        assert result[0]["strategy"] == "static+one_shot"

    def test_gap_split_halves_gap(self):
        """Gap split with divider=2 should purchase half the commitment gap."""
        # Current covered = $14/h on-demand, with 30% savings -> commitment = 14 * 0.7 = $9.8/h
        # Target = $15/h -> gap = $5.2/h -> divided by 2 = $2.6/h
        config = self._base_config(
            static_commitment=15.0,
            split_strategy_type="gap_split",
            gap_split_divider=2.0,
            min_purchase_percent=0.1,
        )
        spending = self._spending_data(avg_covered=14.0, avg_total=100.0)
        clients = {"ce": Mock(), "savingsplans": Mock()}

        result = calculate_purchase_need_static(config, clients, spending)

        assert len(result) == 1
        assert result[0]["hourly_commitment"] == pytest.approx(2.6)

    def test_already_at_target_skips(self):
        """No purchase when existing commitment meets target."""
        # Current covered = $20/h, with 30% savings -> commitment = 20 * 0.7 = $14/h
        # Target = $10/h -> gap negative -> skip
        config = self._base_config(static_commitment=10.0)
        spending = self._spending_data(avg_covered=20.0, avg_total=100.0)
        clients = {"ce": Mock(), "savingsplans": Mock()}

        result = calculate_purchase_need_static(config, clients, spending)

        assert len(result) == 0

    def test_below_min_commitment_skips(self):
        config = self._base_config(static_commitment=0.0005, min_commitment_per_plan=0.001)
        spending = self._spending_data(avg_covered=0.0, avg_total=100.0)
        clients = {"ce": Mock(), "savingsplans": Mock()}

        result = calculate_purchase_need_static(config, clients, spending)

        assert len(result) == 0

    def test_uses_per_type_savings_percentage(self):
        """Per-type savings rate should be used for commitment conversion."""
        # With 40% savings: current_commitment = 10 * 0.6 = $6/h
        # Target = $10/h -> gap = $4/h
        config = self._base_config(
            static_commitment=10.0,
            compute_savings_percentage=40.0,
        )
        spending = self._spending_data(avg_covered=10.0, avg_total=100.0)
        clients = {"ce": Mock(), "savingsplans": Mock()}

        result = calculate_purchase_need_static(config, clients, spending)

        assert len(result) == 1
        assert result[0]["hourly_commitment"] == pytest.approx(4.0)

    def test_disabled_sp_type_skipped(self):
        config = self._base_config(enable_compute_sp=False)
        spending = self._spending_data(avg_covered=0.0, avg_total=100.0)
        clients = {"ce": Mock(), "savingsplans": Mock()}

        result = calculate_purchase_need_static(config, clients, spending)

        assert len(result) == 0

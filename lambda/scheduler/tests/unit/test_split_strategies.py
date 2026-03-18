import pytest
from split_strategies import calculate_split
from split_strategies.fixed_step_split import calculate_fixed_step_split
from split_strategies.gap_split import _resolve_min_purchase, calculate_gap_split
from split_strategies.one_shot_split import calculate_one_shot_split


# ============================================================================
# Dispatcher tests (split_strategies/__init__.py)
# ============================================================================


class TestCalculateSplit:
    def test_dispatches_one_shot(self):
        config = {"split_strategy_type": "one_shot"}
        result = calculate_split(30.0, 90.0, config)
        assert result == pytest.approx(60.0)

    def test_dispatches_fixed_step(self):
        config = {"split_strategy_type": "fixed_step", "fixed_step_percent": 10.0}
        result = calculate_split(50.0, 90.0, config)
        assert result == pytest.approx(10.0)

    def test_dispatches_gap_split(self):
        config = {
            "split_strategy_type": "gap_split",
            "gap_split_divider": 2.0,
            "min_purchase_percent": 1.0,
        }
        result = calculate_split(50.0, 90.0, config)
        assert result == pytest.approx(20.0)

    def test_unknown_strategy_raises(self):
        config = {"split_strategy_type": "nonexistent"}
        with pytest.raises(ValueError, match="Unknown split strategy 'nonexistent'"):
            calculate_split(50.0, 90.0, config)


# ============================================================================
# one_shot_split tests
# ============================================================================


class TestOneShotSplit:
    def test_positive_gap(self):
        assert calculate_one_shot_split(50.0, 90.0, {}) == pytest.approx(40.0)

    def test_no_gap(self):
        assert calculate_one_shot_split(90.0, 90.0, {}) == pytest.approx(0.0)

    def test_negative_gap(self):
        assert calculate_one_shot_split(95.0, 90.0, {}) == pytest.approx(0.0)

    def test_from_zero(self):
        assert calculate_one_shot_split(0.0, 100.0, {}) == pytest.approx(100.0)


# ============================================================================
# fixed_step_split tests
# ============================================================================


class TestFixedStepSplit:
    def test_gap_larger_than_step(self):
        config = {"fixed_step_percent": 10.0}
        assert calculate_fixed_step_split(50.0, 90.0, config) == pytest.approx(10.0)

    def test_gap_smaller_than_step(self):
        config = {"fixed_step_percent": 10.0}
        assert calculate_fixed_step_split(85.0, 90.0, config) == pytest.approx(5.0)

    def test_no_gap(self):
        config = {"fixed_step_percent": 10.0}
        assert calculate_fixed_step_split(90.0, 90.0, config) == pytest.approx(0.0)

    def test_negative_gap(self):
        config = {"fixed_step_percent": 10.0}
        assert calculate_fixed_step_split(95.0, 90.0, config) == pytest.approx(0.0)

    def test_step_caps_at_gap(self):
        config = {"fixed_step_percent": 10.0}
        assert calculate_fixed_step_split(85.0, 90.0, config) == pytest.approx(5.0)


# ============================================================================
# gap_split tests
# ============================================================================


class TestGapSplit:
    def test_no_gap(self):
        config = {"gap_split_divider": 2.0}
        assert calculate_gap_split(90.0, 90.0, config) == pytest.approx(0.0)

    def test_negative_gap(self):
        config = {"gap_split_divider": 2.0}
        assert calculate_gap_split(95.0, 90.0, config) == pytest.approx(0.0)

    def test_basic_divide(self):
        # gap=40, divider=2 → 20.0
        config = {"gap_split_divider": 2.0, "min_purchase_percent": 1.0}
        assert calculate_gap_split(50.0, 90.0, config) == pytest.approx(20.0)

    def test_large_gap(self):
        # gap=90, divider=2 → 45.0
        config = {"gap_split_divider": 2.0, "min_purchase_percent": 1.0}
        assert calculate_gap_split(0.0, 90.0, config) == pytest.approx(45.0)

    def test_divider_3(self):
        # gap=40, divider=3 → 13.3
        config = {"gap_split_divider": 3.0, "min_purchase_percent": 1.0}
        assert calculate_gap_split(50.0, 90.0, config) == pytest.approx(13.3, abs=0.1)

    def test_max_purchase_clamp(self):
        # gap=40, divider=2 → 20.0, but max=15 → 15.0
        config = {
            "gap_split_divider": 2.0,
            "min_purchase_percent": 1.0,
            "max_purchase_percent": 15.0,
        }
        assert calculate_gap_split(50.0, 90.0, config) == pytest.approx(15.0)

    def test_min_purchase_clamp(self):
        # gap=40, divider=100 → 0.4, but min=1 → 1.0
        config = {"gap_split_divider": 100.0, "min_purchase_percent": 1.0}
        assert calculate_gap_split(50.0, 90.0, config) == pytest.approx(1.0)

    def test_gap_smaller_than_min(self):
        # gap=0.5, divider=2 → 0.25, min=1, but gap(0.5) < min(1) → 0.5
        config = {"gap_split_divider": 2.0, "min_purchase_percent": 1.0}
        assert calculate_gap_split(89.5, 90.0, config) == pytest.approx(0.5)

    def test_defaults(self):
        # gap=90, divider=2, min=1 → 45.0
        config = {"gap_split_divider": 2.0, "min_purchase_percent": 1.0}
        assert calculate_gap_split(0.0, 90.0, config) == pytest.approx(45.0)

    def test_no_max_means_unlimited(self):
        # gap=80, divider=1 → 80.0 (no max set)
        config = {"gap_split_divider": 1.0, "min_purchase_percent": 1.0}
        assert calculate_gap_split(10.0, 90.0, config) == pytest.approx(80.0)

    def test_auto_min_purchase_1y(self):
        # No explicit min_purchase_percent, 1-year compute → 100/12 ≈ 8.33
        config = {
            "gap_split_divider": 100.0,
            "enable_compute_sp": True,
            "compute_sp_term": "ONE_YEAR",
        }
        # gap=40, divider=100 → 0.4, auto min=8.33 → 8.33
        assert calculate_gap_split(50.0, 90.0, config) == pytest.approx(8.3, abs=0.1)

    def test_auto_min_purchase_3y(self):
        # No explicit min_purchase_percent, 3-year compute → 100/36 ≈ 2.78
        config = {
            "gap_split_divider": 100.0,
            "enable_compute_sp": True,
            "compute_sp_term": "THREE_YEAR",
        }
        # gap=40, divider=100 → 0.4, auto min=2.78 → 2.78
        assert calculate_gap_split(50.0, 90.0, config) == pytest.approx(2.8, abs=0.1)

    def test_explicit_min_overrides_auto(self):
        config = {
            "gap_split_divider": 100.0,
            "min_purchase_percent": 5.0,
            "enable_compute_sp": True,
            "compute_sp_term": "ONE_YEAR",
        }
        # gap=40, divider=100 → 0.4, explicit min=5 → 5.0
        assert calculate_gap_split(50.0, 90.0, config) == pytest.approx(5.0)


class TestResolveMinPurchase:
    def test_explicit_value(self):
        assert _resolve_min_purchase({"min_purchase_percent": 5.0}) == 5.0

    def test_auto_1y_compute(self):
        config = {"enable_compute_sp": True, "compute_sp_term": "ONE_YEAR"}
        assert _resolve_min_purchase(config) == pytest.approx(8.33)

    def test_auto_3y_compute(self):
        config = {"enable_compute_sp": True, "compute_sp_term": "THREE_YEAR"}
        assert _resolve_min_purchase(config) == pytest.approx(2.78)

    def test_auto_uses_longest_term(self):
        config = {
            "enable_compute_sp": True,
            "compute_sp_term": "THREE_YEAR",
            "enable_database_sp": True,  # always 1-year
        }
        # 3-year is longest → 100/36
        assert _resolve_min_purchase(config) == pytest.approx(2.78)

    def test_auto_defaults_to_1y(self):
        config = {}
        assert _resolve_min_purchase(config) == pytest.approx(8.33)

    def test_none_triggers_auto(self):
        config = {
            "min_purchase_percent": None,
            "enable_compute_sp": True,
            "compute_sp_term": "ONE_YEAR",
        }
        assert _resolve_min_purchase(config) == pytest.approx(8.33)

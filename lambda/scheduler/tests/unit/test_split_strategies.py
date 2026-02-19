import pytest
from split_strategies import calculate_split
from split_strategies.dichotomy_split import (
    calculate_dichotomy_purchase_percent,
    calculate_dichotomy_split,
)
from split_strategies.linear_split import calculate_linear_split
from split_strategies.one_shot_split import calculate_one_shot_split


# ============================================================================
# Dispatcher tests (split_strategies/__init__.py)
# ============================================================================


class TestCalculateSplit:
    def test_dispatches_one_shot(self):
        config = {"split_strategy_type": "one_shot"}
        result = calculate_split(30.0, 90.0, config)
        assert result == pytest.approx(60.0)

    def test_dispatches_linear(self):
        config = {"split_strategy_type": "linear", "linear_step_percent": 10.0}
        result = calculate_split(50.0, 90.0, config)
        assert result == pytest.approx(10.0)

    def test_dispatches_dichotomy(self):
        config = {
            "split_strategy_type": "dichotomy",
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
        }
        result = calculate_split(50.0, 90.0, config)
        assert result > 0

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
# linear_split tests
# ============================================================================


class TestLinearSplit:
    def test_gap_larger_than_step(self):
        config = {"linear_step_percent": 10.0}
        assert calculate_linear_split(50.0, 90.0, config) == pytest.approx(10.0)

    def test_gap_smaller_than_step(self):
        config = {"linear_step_percent": 10.0}
        assert calculate_linear_split(85.0, 90.0, config) == pytest.approx(5.0)

    def test_no_gap(self):
        config = {"linear_step_percent": 10.0}
        assert calculate_linear_split(90.0, 90.0, config) == pytest.approx(0.0)

    def test_negative_gap(self):
        config = {"linear_step_percent": 10.0}
        assert calculate_linear_split(95.0, 90.0, config) == pytest.approx(0.0)

    def test_falls_back_to_max_purchase_percent(self):
        config = {"max_purchase_percent": 15.0}
        assert calculate_linear_split(50.0, 90.0, config) == pytest.approx(15.0)


# ============================================================================
# dichotomy_split tests
# ============================================================================


class TestDichotomyPurchasePercent:
    def test_no_gap(self):
        assert calculate_dichotomy_purchase_percent(90.0, 90.0, 50.0, 1.0) == pytest.approx(0.0)

    def test_negative_gap(self):
        assert calculate_dichotomy_purchase_percent(95.0, 90.0, 50.0, 1.0) == pytest.approx(0.0)

    def test_gap_below_min(self):
        result = calculate_dichotomy_purchase_percent(89.5, 90.0, 50.0, 1.0)
        assert result == pytest.approx(1.0)

    def test_max_fits(self):
        result = calculate_dichotomy_purchase_percent(0.0, 90.0, 50.0, 1.0)
        assert result == pytest.approx(50.0)

    def test_halving_to_fit(self):
        result = calculate_dichotomy_purchase_percent(50.0, 90.0, 50.0, 1.0)
        assert result == pytest.approx(25.0)

    def test_halving_reaches_min(self):
        result = calculate_dichotomy_purchase_percent(89.0, 90.0, 50.0, 5.0)
        assert result == pytest.approx(5.0)


class TestDichotomySplit:
    def test_uses_config_defaults(self):
        config = {}
        result = calculate_dichotomy_split(0.0, 90.0, config)
        assert result == pytest.approx(50.0)

    def test_uses_config_values(self):
        config = {"max_purchase_percent": 20.0, "min_purchase_percent": 2.0}
        result = calculate_dichotomy_split(50.0, 90.0, config)
        assert result == pytest.approx(20.0)

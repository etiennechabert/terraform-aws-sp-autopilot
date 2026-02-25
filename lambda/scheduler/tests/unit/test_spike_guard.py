from unittest.mock import Mock, patch

from shared.usage_decline_check import (
    check_usage_drop,
    check_usage_spike,
    run_purchasing_spike_guard,
    run_scheduling_spike_guard,
)


def test_check_usage_spike_flags_above_threshold():
    result = check_usage_spike(
        long_term_avgs={"compute": 1.0},
        short_term_avgs={"compute": 1.25},
        threshold_percent=20,
    )
    assert result["compute"]["flagged"] is True
    assert result["compute"]["change_percent"] == 25.0


def test_check_usage_spike_no_flag_below_threshold():
    result = check_usage_spike(
        long_term_avgs={"compute": 1.0},
        short_term_avgs={"compute": 1.10},
        threshold_percent=20,
    )
    assert result["compute"]["flagged"] is False


def test_check_usage_spike_zero_baseline():
    result = check_usage_spike(
        long_term_avgs={"compute": 0.0},
        short_term_avgs={"compute": 1.0},
        threshold_percent=20,
    )
    assert result["compute"]["flagged"] is False
    assert result["compute"]["change_percent"] == 0.0


def test_check_usage_spike_missing_short_term():
    result = check_usage_spike(
        long_term_avgs={"compute": 1.0},
        short_term_avgs={},
        threshold_percent=20,
    )
    assert result["compute"]["flagged"] is False


def test_check_usage_drop_flags_above_threshold():
    result = check_usage_drop(
        baseline_avgs={"compute": 1.0},
        current_avgs={"compute": 0.7},
        threshold_percent=20,
    )
    assert result["compute"]["flagged"] is True
    assert result["compute"]["change_percent"] == 30.0
    assert result["compute"]["baseline_avg"] == 1.0
    assert result["compute"]["current_avg"] == 0.7


def test_check_usage_drop_no_flag_below_threshold():
    result = check_usage_drop(
        baseline_avgs={"compute": 1.0},
        current_avgs={"compute": 0.95},
        threshold_percent=20,
    )
    assert result["compute"]["flagged"] is False


def test_check_usage_drop_zero_baseline():
    result = check_usage_drop(
        baseline_avgs={"compute": 0.0},
        current_avgs={"compute": 1.0},
        threshold_percent=20,
    )
    assert result["compute"]["flagged"] is False


def test_check_usage_drop_missing_current():
    result = check_usage_drop(
        baseline_avgs={"compute": 1.0},
        current_avgs={},
        threshold_percent=20,
    )
    assert result["compute"]["flagged"] is True
    assert result["compute"]["change_percent"] == 100.0


def test_check_usage_spike_multiple_types():
    result = check_usage_spike(
        long_term_avgs={"compute": 1.0, "database": 0.5},
        short_term_avgs={"compute": 1.3, "database": 0.5},
        threshold_percent=20,
    )
    assert result["compute"]["flagged"] is True
    assert result["database"]["flagged"] is False


@patch("shared.usage_decline_check.fetch_averages")
def test_run_scheduling_spike_guard(mock_fetch):
    mock_fetch.side_effect = [
        {"compute": 1.0},  # long-term
        {"compute": 1.3},  # short-term (30% spike)
    ]
    config = {
        "spike_guard_long_lookback_days": 90,
        "spike_guard_short_lookback_days": 14,
        "spike_guard_threshold_percent": 20,
    }
    short_avgs, results = run_scheduling_spike_guard(Mock(), config)
    assert results["compute"]["flagged"] is True
    assert short_avgs == {"compute": 1.3}


@patch("shared.usage_decline_check.fetch_averages")
def test_run_scheduling_spike_guard_no_spike(mock_fetch):
    mock_fetch.side_effect = [
        {"compute": 1.0},
        {"compute": 1.05},
    ]
    config = {
        "spike_guard_long_lookback_days": 90,
        "spike_guard_short_lookback_days": 14,
        "spike_guard_threshold_percent": 20,
    }
    _, results = run_scheduling_spike_guard(Mock(), config)
    assert results["compute"]["flagged"] is False


@patch("shared.usage_decline_check.fetch_averages")
def test_run_purchasing_spike_guard_detects_drop(mock_fetch):
    mock_fetch.return_value = {"compute": 0.7}  # current avg
    config = {
        "spike_guard_short_lookback_days": 14,
        "spike_guard_threshold_percent": 20,
    }
    results = run_purchasing_spike_guard(Mock(), scheduling_avgs={"compute": 1.0}, config=config)
    assert results["compute"]["flagged"] is True


@patch("shared.usage_decline_check.fetch_averages")
def test_run_purchasing_spike_guard_no_drop(mock_fetch):
    mock_fetch.return_value = {"compute": 0.95}
    config = {
        "spike_guard_short_lookback_days": 14,
        "spike_guard_threshold_percent": 20,
    }
    results = run_purchasing_spike_guard(Mock(), scheduling_avgs={"compute": 1.0}, config=config)
    assert results["compute"]["flagged"] is False

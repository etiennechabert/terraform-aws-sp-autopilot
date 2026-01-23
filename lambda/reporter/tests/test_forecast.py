"""
Tests for purchase forecast calculation.
"""

import os
import sys


# Add lambda directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


def test_calculate_purchase_forecast_with_gap():
    """Test purchase forecast calculation when coverage gap exists."""
    coverage_data = {
        "compute": {
            "summary": {
                "avg_coverage": 65.0,
                "avg_hourly_total": 10.0,
            }
        },
        "database": {
            "summary": {
                "avg_coverage": 45.0,
                "avg_hourly_total": 5.0,
            }
        },
    }

    config = {
        "coverage_target_percent": 80.0,
        "max_purchase_percent": 20.0,
        "min_commitment_per_plan": 0.01,
        "purchase_strategy_type": "fixed",
        "enable_compute_sp": True,
        "enable_database_sp": True,
        "enable_sagemaker_sp": False,
    }

    forecast = handler._calculate_purchase_forecast(coverage_data, config)

    assert len(forecast) == 2
    assert forecast[0]["sp_type"] == "Compute"
    assert forecast[0]["current_coverage"] == 65.0
    assert forecast[0]["target_coverage"] == 80.0
    assert forecast[0]["commitment"] > 0
    assert forecast[0]["monthly_cost"] > 0
    assert forecast[1]["sp_type"] == "Database"
    assert forecast[1]["commitment"] > 0


def test_calculate_purchase_forecast_no_gap():
    """Test purchase forecast when already at target coverage."""
    coverage_data = {
        "compute": {
            "summary": {
                "avg_coverage": 85.0,
                "avg_hourly_total": 10.0,
            }
        },
    }

    config = {
        "coverage_target_percent": 80.0,
        "max_purchase_percent": 20.0,
        "min_commitment_per_plan": 0.01,
        "purchase_strategy_type": "fixed",
        "enable_compute_sp": True,
        "enable_database_sp": False,
        "enable_sagemaker_sp": False,
    }

    forecast = handler._calculate_purchase_forecast(coverage_data, config)

    assert len(forecast) == 0


def test_calculate_purchase_forecast_dichotomy_strategy():
    """Test purchase forecast with dichotomy strategy."""
    coverage_data = {
        "compute": {
            "summary": {
                "avg_coverage": 60.0,
                "avg_hourly_total": 10.0,
            }
        },
    }

    config = {
        "coverage_target_percent": 80.0,
        "max_purchase_percent": 20.0,
        "min_commitment_per_plan": 0.01,
        "purchase_strategy_type": "dichotomy",
        "enable_compute_sp": True,
        "enable_database_sp": False,
        "enable_sagemaker_sp": False,
    }

    forecast = handler._calculate_purchase_forecast(coverage_data, config)

    assert len(forecast) == 1
    # Dichotomy fills halfway, so gap is 20%, fill 10%
    assert forecast[0]["gap"] == 20.0


def test_calculate_purchase_forecast_respects_max_purchase():
    """Test that forecast respects max_purchase_percent limit."""
    coverage_data = {
        "compute": {
            "summary": {
                "avg_coverage": 20.0,
                "avg_hourly_total": 10.0,
            }
        },
    }

    config = {
        "coverage_target_percent": 80.0,
        "max_purchase_percent": 10.0,  # Only allow 10% of spend
        "min_commitment_per_plan": 0.01,
        "purchase_strategy_type": "fixed",
        "enable_compute_sp": True,
        "enable_database_sp": False,
        "enable_sagemaker_sp": False,
    }

    forecast = handler._calculate_purchase_forecast(coverage_data, config)

    assert len(forecast) == 1
    # Max purchase is 10% of $10/hr = $1/hr
    assert forecast[0]["commitment"] <= 1.0


def test_calculate_purchase_forecast_min_commitment():
    """Test that forecast excludes purchases below minimum commitment."""
    coverage_data = {
        "compute": {
            "summary": {
                "avg_coverage": 79.9,  # Just 0.1% gap
                "avg_hourly_total": 1.0,
            }
        },
    }

    config = {
        "coverage_target_percent": 80.0,
        "max_purchase_percent": 20.0,
        "min_commitment_per_plan": 0.5,  # High minimum
        "purchase_strategy_type": "fixed",
        "enable_compute_sp": True,
        "enable_database_sp": False,
        "enable_sagemaker_sp": False,
    }

    forecast = handler._calculate_purchase_forecast(coverage_data, config)

    # Should be empty because commitment would be too small
    assert len(forecast) == 0


def test_calculate_purchase_forecast_disabled_sp_types():
    """Test that forecast respects SP type enable flags."""
    coverage_data = {
        "compute": {
            "summary": {
                "avg_coverage": 50.0,
                "avg_hourly_total": 10.0,
            }
        },
        "database": {
            "summary": {
                "avg_coverage": 50.0,
                "avg_hourly_total": 5.0,
            }
        },
    }

    config = {
        "coverage_target_percent": 80.0,
        "max_purchase_percent": 20.0,
        "min_commitment_per_plan": 0.01,
        "purchase_strategy_type": "fixed",
        "enable_compute_sp": True,
        "enable_database_sp": False,  # Database disabled
        "enable_sagemaker_sp": False,
    }

    forecast = handler._calculate_purchase_forecast(coverage_data, config)

    # Only compute should be in forecast
    assert len(forecast) == 1
    assert forecast[0]["sp_type"] == "Compute"

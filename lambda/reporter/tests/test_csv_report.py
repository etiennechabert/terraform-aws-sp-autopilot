"""
Tests for CSV report generation in Reporter Lambda.
Covers CSV format generation, structure validation, and data accuracy.
"""

import csv
import os
import sys


# Set up environment variables BEFORE importing handler
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

import pytest


# Add lambda directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


@pytest.fixture
def sample_coverage_history():
    """Sample coverage history data."""
    return [
        {
            "date": "2026-01-10",
            "coverage_percentage": 65.5,
            "on_demand_hours": 100.0,
            "covered_hours": 155.5,
            "total_hours": 255.5,
        },
        {
            "date": "2026-01-11",
            "coverage_percentage": 67.2,
            "on_demand_hours": 95.0,
            "covered_hours": 160.0,
            "total_hours": 255.0,
        },
        {
            "date": "2026-01-12",
            "coverage_percentage": 68.8,
            "on_demand_hours": 90.0,
            "covered_hours": 165.0,
            "total_hours": 255.0,
        },
        {
            "date": "2026-01-13",
            "coverage_percentage": 70.1,
            "on_demand_hours": 85.0,
            "covered_hours": 170.0,
            "total_hours": 255.0,
        },
        {
            "date": "2026-01-14",
            "coverage_percentage": 72.3,
            "on_demand_hours": 80.0,
            "covered_hours": 175.0,
            "total_hours": 255.0,
        },
    ]


@pytest.fixture
def sample_savings_data():
    """Sample savings data."""
    return {
        "plans_count": 5,
        "total_commitment": 15.75,
        "estimated_monthly_savings": 8500.00,
        "average_utilization": 92.5,
        "plans": [
            {
                "plan_id": "sp-12345",
                "plan_type": "ComputeSavingsPlans",
                "payment_option": "All Upfront",
                "term_years": 3,
                "hourly_commitment": 10.50,
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2028-01-01T00:00:00Z",
            },
            {
                "plan_id": "sp-67890",
                "plan_type": "DatabaseSavingsPlans",
                "payment_option": "No Upfront",
                "term_years": 3,
                "hourly_commitment": 5.25,
                "start_date": "2025-06-01T00:00:00Z",
                "end_date": "2028-06-01T00:00:00Z",
            },
        ],
        "actual_savings": {
            "actual_sp_cost": 10500.00,
            "on_demand_equivalent_cost": 19000.00,
            "net_savings": 8500.00,
            "savings_percentage": 44.74,
            "breakdown_by_type": {
                "ComputeSavingsPlans": {
                    "plans_count": 3,
                    "total_commitment": 10.50,
                },
                "DatabaseSavingsPlans": {
                    "plans_count": 2,
                    "total_commitment": 5.25,
                },
            },
        },
    }


def test_generate_csv_report_basic_structure(sample_coverage_history, sample_savings_data):
    """Test CSV report basic structure and headers."""
    result = handler.generate_csv_report(sample_coverage_history, sample_savings_data)

    # Verify CSV contains expected sections
    assert "# Savings Plans Coverage & Savings Report" in result
    assert "## Summary" in result
    assert "## Coverage History" in result
    assert "## Active Savings Plans" in result

    # Verify summary section has correct header
    assert "metric,value" in result

    # Verify coverage history section has correct header
    assert "date,coverage_percentage,on_demand_hours,covered_hours,total_hours" in result

    # Verify active savings plans section has correct header
    assert (
        "plan_id,plan_type,payment_option,term_years,hourly_commitment,start_date,end_date"
        in result
    )


def test_generate_csv_report_summary_metrics(sample_coverage_history, sample_savings_data):
    """Test CSV report summary metrics are included correctly."""
    result = handler.generate_csv_report(sample_coverage_history, sample_savings_data)

    # Verify current coverage (last item)
    assert "current_coverage_percentage,72.3" in result

    # Verify average coverage (should be ~68.78)
    assert "average_coverage_percentage," in result
    assert "68.78" in result

    # Verify trend direction (increasing from 65.5 to 72.3)
    assert "trend_direction,increasing" in result

    # Verify active plans count
    assert "active_plans_count,5" in result

    # Verify total hourly commitment
    assert "total_hourly_commitment,15.7500" in result

    # Verify monthly commitment (15.75 * 730)
    monthly_commitment = 15.75 * 730
    assert f"total_monthly_commitment,{monthly_commitment:.2f}" in result

    # Verify savings metrics
    assert "estimated_monthly_savings,8500.00" in result
    assert "average_utilization_percentage,92.50" in result
    assert "actual_sp_cost,10500.00" in result
    assert "on_demand_equivalent_cost,19000.00" in result
    assert "net_savings,8500.00" in result
    assert "savings_percentage,44.74" in result


def test_generate_csv_report_coverage_history_data(sample_coverage_history, sample_savings_data):
    """Test CSV report coverage history data rows."""
    result = handler.generate_csv_report(sample_coverage_history, sample_savings_data)

    # Verify all coverage history dates are present
    assert "2026-01-10,65.50,100.00,155.50,255.50" in result
    assert "2026-01-11,67.20,95.00,160.00,255.00" in result
    assert "2026-01-12,68.80,90.00,165.00,255.00" in result
    assert "2026-01-13,70.10,85.00,170.00,255.00" in result
    assert "2026-01-14,72.30,80.00,175.00,255.00" in result


def test_generate_csv_report_active_plans_data(sample_coverage_history, sample_savings_data):
    """Test CSV report active savings plans data rows."""
    result = handler.generate_csv_report(sample_coverage_history, sample_savings_data)

    # Verify first plan details
    assert (
        "sp-12345,ComputeSavingsPlans,All Upfront,3,10.5000,2025-01-01T00:00:00Z,2028-01-01T00:00:00Z"
        in result
    )

    # Verify second plan details
    assert (
        "sp-67890,DatabaseSavingsPlans,No Upfront,3,5.2500,2025-06-01T00:00:00Z,2028-06-01T00:00:00Z"
        in result
    )


def test_generate_csv_report_with_empty_data():
    """Test CSV report generation with empty data."""
    result = handler.generate_csv_report([], {"plans_count": 0, "total_commitment": 0.0})

    # Verify basic structure still exists
    assert "# Savings Plans Coverage & Savings Report" in result
    assert "## Summary" in result
    assert "## Coverage History" in result
    assert "## Active Savings Plans" in result

    # Verify empty coverage data
    assert "current_coverage_percentage,0.00" in result
    assert "average_coverage_percentage,0.00" in result

    # Verify empty savings data
    assert "active_plans_count,0" in result
    assert "total_hourly_commitment,0.0000" in result


def test_generate_csv_report_with_increasing_trend(sample_coverage_history, sample_savings_data):
    """Test CSV report with increasing coverage trend."""
    result = handler.generate_csv_report(sample_coverage_history, sample_savings_data)

    # Coverage is increasing from 65.5 to 72.3
    assert "trend_direction,increasing" in result
    # Trend value should be 72.3 - 65.5 = 6.8
    assert "trend_value,6.80" in result


def test_generate_csv_report_with_decreasing_trend(sample_savings_data):
    """Test CSV report with decreasing coverage trend."""
    coverage_data = [
        {"date": "2026-01-10", "coverage_percentage": 75.0},
        {"date": "2026-01-14", "coverage_percentage": 65.0},
    ]

    result = handler.generate_csv_report(coverage_data, sample_savings_data)

    assert "trend_direction,decreasing" in result
    # Trend value should be 65.0 - 75.0 = -10.0
    assert "trend_value,-10.00" in result


def test_generate_csv_report_with_stable_trend(sample_savings_data):
    """Test CSV report with stable coverage trend."""
    coverage_data = [
        {"date": "2026-01-10", "coverage_percentage": 70.0},
        {"date": "2026-01-14", "coverage_percentage": 70.0},
    ]

    result = handler.generate_csv_report(coverage_data, sample_savings_data)

    assert "trend_direction,stable" in result
    assert "trend_value,0.00" in result


def test_generate_csv_report_with_single_data_point(sample_savings_data):
    """Test CSV report with only one coverage data point (no trend)."""
    coverage_data = [{"date": "2026-01-10", "coverage_percentage": 70.0}]

    result = handler.generate_csv_report(coverage_data, sample_savings_data)

    # With only one data point, trend should be stable
    assert "trend_direction,stable" in result
    assert "trend_value,0.00" in result
    assert "current_coverage_percentage,70.00" in result


def test_generate_csv_report_parseable_format(sample_coverage_history, sample_savings_data):
    """Test that CSV report can be parsed by standard CSV reader."""
    result = handler.generate_csv_report(sample_coverage_history, sample_savings_data)

    # Extract the coverage history section for parsing
    lines = result.split("\n")
    coverage_section_start = None
    coverage_section_end = None

    for i, line in enumerate(lines):
        if "date,coverage_percentage" in line:
            coverage_section_start = i
        elif coverage_section_start is not None and line.strip() == "":
            coverage_section_end = i
            break

    assert coverage_section_start is not None, "Coverage history section not found"

    # Parse the coverage history section
    coverage_lines = lines[coverage_section_start:coverage_section_end]
    csv_reader = csv.DictReader(coverage_lines)

    rows = list(csv_reader)
    assert len(rows) == 5  # Should have 5 data rows

    # Verify first row
    assert rows[0]["date"] == "2026-01-10"
    assert float(rows[0]["coverage_percentage"]) == 65.50

    # Verify last row
    assert rows[4]["date"] == "2026-01-14"
    assert float(rows[4]["coverage_percentage"]) == 72.30


def test_generate_csv_report_no_actual_savings(sample_coverage_history):
    """Test CSV report when actual_savings data is missing."""
    savings_data = {
        "plans_count": 2,
        "total_commitment": 5.0,
        "estimated_monthly_savings": 1000.0,
        "average_utilization": 85.0,
        "plans": [],
    }

    result = handler.generate_csv_report(sample_coverage_history, savings_data)

    # Verify defaults for missing actual_savings
    assert "actual_sp_cost,0.00" in result
    assert "on_demand_equivalent_cost,0.00" in result
    assert "net_savings,0.00" in result
    assert "savings_percentage,0.00" in result


def test_generate_csv_report_contains_timestamp(sample_coverage_history, sample_savings_data):
    """Test CSV report contains generation timestamp."""
    result = handler.generate_csv_report(sample_coverage_history, sample_savings_data)

    # Verify timestamp line exists
    assert "# Generated:" in result
    assert "UTC" in result


def test_generate_csv_report_plans_with_missing_fields():
    """Test CSV report handles plans with missing optional fields."""
    coverage_data = [{"date": "2026-01-10", "coverage_percentage": 70.0}]
    savings_data = {
        "plans_count": 1,
        "total_commitment": 5.0,
        "plans": [
            {
                "plan_id": "sp-minimal",
                # Missing most fields
            }
        ],
    }

    result = handler.generate_csv_report(coverage_data, savings_data)

    # Should handle missing fields gracefully with defaults
    assert "sp-minimal" in result
    assert "## Active Savings Plans" in result

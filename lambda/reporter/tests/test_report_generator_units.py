"""Unit tests for report_generator internal functions."""

import os
import sys
from datetime import UTC, datetime


os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("REPORTS_BUCKET", "test-bucket")
os.environ.setdefault("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from report_generator import _get_type_metrics_for_report, _parse_plan_dates


class TestParsePlanDates:
    """Test _parse_plan_dates function with various date scenarios."""

    def test_parse_dates_with_iso_format(self):
        """Test parsing dates in ISO format with timezone."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01T00:00:00Z"
        end_date = "2024-12-31T23:59:59Z"

        start, end, days, expiring, tooltip = _parse_plan_dates(
            start_date, end_date, now, three_months
        )

        assert start == "2024-01-01"
        assert end == "2024-12-31"
        assert days == "213 days"
        assert expiring is False
        assert tooltip == "Start: 2024-01-01 | End: 2024-12-31"

    def test_parse_dates_without_time(self):
        """Test parsing dates without time component."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2024-12-31"

        start, end, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert start == "2024-01-01"
        assert end == "2024-12-31"
        assert days == "213 days"
        assert expiring is False

    def test_expired_plan(self):
        """Test plan that has already expired."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2024-05-31"

        _, _, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert days == "Expired"
        assert expiring is True

    def test_expiring_today(self):
        """Test plan expiring today."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2024-06-01"

        _, _, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert days == "Today"
        assert expiring is True

    def test_expiring_in_one_day(self):
        """Test plan expiring in exactly one day."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2024-06-02"

        _, _, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert days == "1 day"
        assert expiring is True

    def test_expiring_soon(self):
        """Test plan expiring within 3 months."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2024-08-15"

        _, _, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert "days" in days
        assert expiring is True

    def test_not_expiring_soon(self):
        """Test plan not expiring within 3 months."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2025-01-01"

        _, _, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert "days" in days
        assert expiring is False

    def test_invalid_date_format(self):
        """Test handling of invalid date format."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "invalid-date"
        end_date = "also-invalid"

        start, end, days, expiring, tooltip = _parse_plan_dates(
            start_date, end_date, now, three_months
        )

        assert start == "invalid-date"
        assert end == "also-invalid"
        assert days == "N/A"
        assert expiring is False
        assert tooltip == ""

    def test_mixed_date_formats(self):
        """Test with start date having time and end date without."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01T00:00:00Z"
        end_date = "2024-07-15"

        start, end, _, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert start == "2024-01-01"
        assert end == "2024-07-15"
        assert expiring is True


class TestGetTypeMetricsForReport:
    """Test _get_type_metrics_for_report function to ensure total_commitment is included."""

    def test_includes_total_commitment_from_breakdown(self):
        """Test that total_commitment is extracted from breakdown_by_type and included in metrics.

        This test verifies that the actual SP commitment amount is correctly extracted.
        Note: The commitment ($1.00/hr) will be converted to on-demand equivalent ($1.54/hr)
        in the JavaScript generation code for the simulator.
        """
        summary = {
            "avg_coverage_total": 64.9,
            "avg_hourly_total": 1.54,
            "avg_hourly_covered": 1.54,
        }
        breakdown_by_type = {
            "Database": {
                "total_commitment": 1.0,
                "savings_percentage": 34.9,
                "average_utilization": 100.0,
                "net_savings_hourly": 0.54,
            }
        }

        metrics = _get_type_metrics_for_report(summary, "Database", breakdown_by_type)

        assert metrics["total_commitment"] == 1.0
        assert metrics["sp_commitment_hourly"] == 1.0
        assert metrics["savings_percentage"] == 34.9
        assert metrics["utilization"] == 100.0

    def test_total_commitment_defaults_to_zero_when_missing(self):
        """Test that total_commitment defaults to 0.0 when not in breakdown."""
        summary = {
            "avg_coverage_total": 0.0,
            "avg_hourly_total": 0.0,
            "avg_hourly_covered": 0.0,
        }
        breakdown_by_type = {
            "Compute": {
                "savings_percentage": 0.0,
                "average_utilization": 0.0,
                "net_savings_hourly": 0.0,
            }
        }

        metrics = _get_type_metrics_for_report(summary, "Compute", breakdown_by_type)

        assert metrics["total_commitment"] == 0.0

    def test_multiple_sp_types_have_correct_commitments(self):
        """Test that different SP types get their correct total_commitment values."""
        summary_compute = {
            "avg_coverage_total": 70.0,
            "avg_hourly_total": 100.0,
            "avg_hourly_covered": 70.0,
        }
        summary_database = {
            "avg_coverage_total": 100.0,
            "avg_hourly_total": 1.54,
            "avg_hourly_covered": 1.54,
        }
        breakdown_by_type = {
            "Compute": {
                "total_commitment": 19.31,
                "savings_percentage": 30.0,
                "average_utilization": 85.0,
                "net_savings_hourly": 10.0,
            },
            "Database": {
                "total_commitment": 1.0,
                "savings_percentage": 34.9,
                "average_utilization": 100.0,
                "net_savings_hourly": 0.54,
            },
        }

        compute_metrics = _get_type_metrics_for_report(
            summary_compute, "Compute", breakdown_by_type
        )
        database_metrics = _get_type_metrics_for_report(
            summary_database, "Database", breakdown_by_type
        )

        assert compute_metrics["total_commitment"] == 19.31
        assert compute_metrics["sp_commitment_hourly"] == 19.31
        assert database_metrics["total_commitment"] == 1.0
        assert database_metrics["sp_commitment_hourly"] == 1.0
